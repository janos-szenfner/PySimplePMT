"""
GAN file importer for the Gantt Project Management Tool.

Parses GanttProject's XML-based .gan files using xml.etree.ElementTree.

DEVELOPMENT NOTES:
------------------
GanttProject stores a task's schedule as a start date plus a duration counted
in *working* days, and never writes an end date. Reproducing the end dates the
application itself shows therefore means replaying its calendar: the weekend
definition and holiday list from the file's <calendars> block.

Two further details of the format are easy to get wrong:

  * <depend id="X"/> nested inside task A declares that X comes *after* A, so
    it names a successor. Task.dependencies holds predecessors, which means
    every edge has to be reversed on import.
  * Sub-tasks are <task> elements nested inside their parent <task>, to
    arbitrary depth, rather than carrying a parent reference.

Files written by GanttProject 3.x carry no XML namespace, while some older
versions namespaced everything under http://ganttproject.sf.net/. Namespaces
are stripped up front so both parse through the same code path.
"""

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple, Set
from pathlib import Path

from gantt_app.models import Project, Task
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


#: Dependency types used by GanttProject's <depend type="..."/> attribute.
DEPENDENCY_TYPES = {
    '1': 'SS',  # Start-Start
    '2': 'FS',  # Finish-Start (GanttProject's default)
    '3': 'FF',  # Finish-Finish
    '4': 'SF',  # Start-Finish
}


def strip_namespaces(element: ET.Element) -> ET.Element:
    """
    Remove XML namespaces from an element tree, in place.

    RETURNS:
    --------
    ET.Element
        The same element, with every tag reduced to its local name.
    """
    for node in element.iter():
        if isinstance(node.tag, str) and '}' in node.tag:
            node.tag = node.tag.split('}', 1)[1]
    return element


class GanttProjectCalendar:
    """
    The working-day calendar declared by a .gan file's <calendars> block.

    DEVELOPMENT NOTES:
    ------------------
    <default-week> marks each weekday with 0 (working) or 1 (non-working).
    <date> entries add holidays: an empty year means the holiday recurs every
    year, while a specific year pins it to that year alone. Only HOLIDAY type
    entries reduce the working calendar.
    """

    #: Attribute name per weekday index, Monday first, matching date.weekday().
    WEEKDAY_ATTRS = ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun')

    #: Guard against a malformed duration spinning the day-stepping loop.
    MAX_STEPS = 20000

    def __init__(self):
        # GanttProject's default week: Saturday and Sunday are non-working
        self.non_working_weekdays: Set[int] = {5, 6}
        self.recurring_holidays: Set[Tuple[int, int]] = set()
        self.holidays: Set[Tuple[int, int, int]] = set()

    @classmethod
    def from_element(cls, calendars_elem: Optional[ET.Element]) -> 'GanttProjectCalendar':
        """Build a calendar from a <calendars> element (defaults if absent)."""
        calendar = cls()
        if calendars_elem is None:
            return calendar

        default_week = calendars_elem.find('.//default-week')
        if default_week is not None:
            non_working = set()
            for index, attr in enumerate(cls.WEEKDAY_ATTRS):
                value = default_week.get(attr)
                if value is not None and str(value).strip() == '1':
                    non_working.add(index)
            # Only trust the element if it actually described the week
            if any(default_week.get(attr) is not None for attr in cls.WEEKDAY_ATTRS):
                calendar.non_working_weekdays = non_working

        for date_elem in calendars_elem.findall('date'):
            if (date_elem.get('type') or 'HOLIDAY').upper() != 'HOLIDAY':
                continue
            try:
                month = int(date_elem.get('month'))
                day = int(date_elem.get('date'))
            except (TypeError, ValueError):
                continue

            year_text = (date_elem.get('year') or '').strip()
            if not year_text:
                calendar.recurring_holidays.add((month, day))
            else:
                try:
                    calendar.holidays.add((int(year_text), month, day))
                except ValueError:
                    continue

        return calendar

    def is_working_day(self, day: datetime) -> bool:
        """Check whether a date counts as a working day."""
        if day.weekday() in self.non_working_weekdays:
            return False
        if (day.month, day.day) in self.recurring_holidays:
            return False
        if (day.year, day.month, day.day) in self.holidays:
            return False
        return True

    def next_working_day(self, day: datetime) -> datetime:
        """Return the first working day on or after the given date."""
        steps = 0
        current = day
        while not self.is_working_day(current) and steps < self.MAX_STEPS:
            current += timedelta(days=1)
            steps += 1
        return current

    def add_working_days(self, start: datetime, days: int) -> datetime:
        """
        Advance a date by a number of working days.

        PARAMETERS:
        -----------
        start : datetime
            The starting date. Assumed to be a working day.
        days : int
            How many working days to advance. Zero returns the start date.
        """
        if days <= 0:
            return start

        current = start
        remaining = days
        steps = 0
        while remaining > 0 and steps < self.MAX_STEPS:
            current += timedelta(days=1)
            steps += 1
            if self.is_working_day(current):
                remaining -= 1
        return current

    def end_date_for(self, start: datetime, duration_days: int) -> datetime:
        """
        Get the inclusive end date of a task.

        DEVELOPMENT NOTES:
        ------------------
        A duration of N working days covers N working days *including* the
        start, so the end is N-1 working days after it. Task.end_date is
        inclusive, matching duration_days.
        """
        if duration_days <= 1:
            return start
        return self.add_working_days(start, duration_days - 1)


class GANImporter:
    """
    Imports GanttProject (.gan) files and converts them to Project objects.

    GanttProject files are XML-based and contain tasks, resources, and
    assignments. This importer focuses on the task structure, the schedule
    and the dependencies between tasks.
    """

    def __init__(self, respect_calendar: bool = True):
        """
        PARAMETERS:
        -----------
        respect_calendar : bool, optional
            When True (default), durations are expanded into end dates using
            the file's weekend and holiday calendar, reproducing the dates
            GanttProject displays. Set to False to treat durations as plain
            calendar days.
        """
        self.default_color = "#1f6aa5"
        self.milestone_color = "#e74c3c"
        self.respect_calendar = respect_calendar

    def parse_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse a date string from a GAN file.

        GanttProject 3.x writes plain 'YYYY-MM-DD' dates. Older ISO 8601
        timestamps ('YYYY-MM-DDTHH:MM:SS', optionally with milliseconds and a
        trailing Z) are also accepted.
        """
        if not date_str or str(date_str).strip() == '':
            return None

        text = str(date_str).strip()
        if text.endswith('Z'):
            text = text[:-1]

        for fmt in ('%Y-%m-%d', '%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S',
                    '%Y-%m-%d %H:%M:%S', '%d.%m.%Y', '%Y/%m/%d'):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue

        return None

    def parse_colors(self, root: ET.Element) -> Dict[str, str]:
        """
        Parse the optional <colors> lookup table.

        RETURNS:
        --------
        Dict[str, str]
            Mapping of colour IDs to hex strings. Modern files set a 'color'
            attribute on each task instead, so this is usually empty.
        """
        colors: Dict[str, str] = {}
        colors_elem = root.find('colors')

        if colors_elem is not None:
            for color_elem in colors_elem.findall('color'):
                color_id = color_elem.get('id')
                if not color_id:
                    continue
                try:
                    r = int(color_elem.get('r', 0))
                    g = int(color_elem.get('g', 0))
                    b = int(color_elem.get('b', 0))
                except (TypeError, ValueError):
                    continue
                colors[color_id] = f"#{r:02x}{g:02x}{b:02x}"

        colors.setdefault('default', self.default_color)
        colors.setdefault('milestone', self.milestone_color)
        return colors

    def _task_color(self, task_elem: ET.Element, color_map: Dict[str, str],
                    is_milestone: bool) -> str:
        """Work out a task's colour from its attribute or the colour table."""
        raw = task_elem.get('color')
        if raw and re.match(r'^#[0-9a-fA-F]{6}$', raw.strip()):
            return raw.strip()

        # Legacy form: <color id="..."/> resolved through the <colors> table
        color_elem = task_elem.find('color')
        if color_elem is not None:
            color_id = color_elem.get('id')
            if color_id and color_id in color_map:
                return color_map[color_id]

        return self.milestone_color if is_milestone else self.default_color

    def _task_progress(self, task_elem: ET.Element) -> int:
        """Read a task's completion percentage, clamped to 0-100."""
        raw = task_elem.get('complete')
        if raw is None:
            completion_elem = task_elem.find('completion')
            if completion_elem is not None:
                raw = completion_elem.get('percentage')

        try:
            return max(0, min(100, int(float(raw))))
        except (TypeError, ValueError):
            return 0

    def _task_duration(self, task_elem: ET.Element) -> int:
        """Read a task's duration in working days."""
        raw = task_elem.get('duration')
        if raw is None:
            duration_elem = task_elem.find('duration')
            if duration_elem is not None:
                raw = duration_elem.get('length')

        try:
            return max(0, int(float(raw)))
        except (TypeError, ValueError):
            return 0

    def _is_milestone(self, task_elem: ET.Element, duration: int,
                      has_children: bool) -> bool:
        """
        Decide whether a task element is a milestone.

        GanttProject marks milestones with meeting="true"; a zero duration
        means the same thing. Summary tasks are never milestones even though
        their own duration attribute can read as zero.
        """
        if has_children:
            return False
        if str(task_elem.get('meeting', '')).strip().lower() == 'true':
            return True
        return duration == 0

    def parse_task(self, task_elem: ET.Element, color_map: Dict[str, str],
                   calendar: GanttProjectCalendar,
                   parent_id: Optional[str] = None) -> List[Task]:
        """
        Parse a task element and everything nested inside it.

        PARAMETERS:
        -----------
        task_elem : ET.Element
            XML element representing a task
        color_map : Dict[str, str]
            Colour lookup for files using a <colors> table
        calendar : GanttProjectCalendar
            Working-day calendar used to turn durations into end dates
        parent_id : Optional[str]
            ID of the enclosing task, if this is a sub-task

        RETURNS:
        --------
        List[Task]
            This task followed by its descendants, parents before children.
            Empty if the element could not be parsed.
        """
        try:
            task_id = task_elem.get('id')
            if task_id is None:
                return []
            task_id = str(task_id)

            name = task_elem.get('name') or 'Unnamed Task'

            start_date = self.parse_date(task_elem.get('start'))
            if start_date is None:
                start_elem = task_elem.find('start')
                if start_elem is not None:
                    start_date = self.parse_date(start_elem.text)
            if start_date is None:
                start_date = datetime.now()

            child_elems = task_elem.findall('task')
            duration = self._task_duration(task_elem)
            is_milestone = self._is_milestone(task_elem, duration,
                                              bool(child_elems))

            if is_milestone:
                end_date = None
            elif self.respect_calendar:
                end_date = calendar.end_date_for(start_date, duration)
            else:
                end_date = start_date + timedelta(days=max(duration - 1, 0))

            # An explicit <end> element wins if the file provides one
            end_elem = task_elem.find('end')
            if end_elem is not None and not is_milestone:
                explicit_end = self.parse_date(end_elem.text)
                if explicit_end is not None:
                    end_date = explicit_end

            task = Task(
                id=task_id,
                name=name,
                start_date=start_date,
                end_date=end_date,
                progress=self._task_progress(task_elem),
                dependencies=[],
                color=self._task_color(task_elem, color_map, is_milestone),
                is_milestone=is_milestone,
                task_type="Subtask" if parent_id else "Task",
                parent_task_id=parent_id
            )

            tasks = [task]
            for child_elem in child_elems:
                tasks.extend(self.parse_task(child_elem, color_map, calendar,
                                             parent_id=task_id))
            return tasks

        except Exception as e:
            logger.exception(f"Error parsing task: {e}")
            return []

    def parse_successor_edges(self, root: ET.Element) -> List[Dict[str, Any]]:
        """
        Collect every <depend> edge in the file.

        RETURNS:
        --------
        List[Dict[str, Any]]
            One entry per edge with 'predecessor', 'successor', 'type' and
            'lag'. The element is nested inside the *predecessor*, so the
            enclosing task's ID is the predecessor and the id attribute names
            the successor.
        """
        edges: List[Dict[str, Any]] = []

        for task_elem in root.iter('task'):
            predecessor_id = task_elem.get('id')
            if predecessor_id is None:
                continue

            for depend_elem in task_elem.findall('depend'):
                successor_id = depend_elem.get('id')
                if successor_id is None:
                    continue
                try:
                    lag = int(float(depend_elem.get('difference', 0)))
                except (TypeError, ValueError):
                    lag = 0

                # GanttProject writes hardness="Strong" or "Rubber", which
                # are exactly this application's Hard and Rubber links
                raw_hardness = str(depend_elem.get('hardness', 'Strong')).strip()
                hardness = 'Rubber' if raw_hardness.lower() == 'rubber' else 'Hard'

                edges.append({
                    'predecessor': str(predecessor_id),
                    'successor': str(successor_id),
                    'type': DEPENDENCY_TYPES.get(
                        str(depend_elem.get('type', '2')), 'FS'
                    ),
                    'hardness': hardness,
                    'lag': lag,
                })

            # Legacy form: <depends-on><dependency idref="..."/></depends-on>
            depends_on_elem = task_elem.find('depends-on')
            if depends_on_elem is not None:
                for dep_elem in depends_on_elem.findall('dependency'):
                    dep_id = dep_elem.get('idref')
                    if dep_id:
                        edges.append({
                            'predecessor': str(dep_id),
                            'successor': str(predecessor_id),
                            'type': 'FS',
                            'hardness': 'Hard',
                            'lag': 0,
                        })

        return edges

    def apply_dependencies(self, tasks: List[Task],
                           edges: List[Dict[str, Any]]) -> None:
        """
        Attach dependency edges to the tasks they belong to.

        DEVELOPMENT NOTES:
        ------------------
        Each edge is stored on the successor, since Task.dependencies lists
        the tasks that must finish first. Edges naming a task that is not in
        the file are skipped rather than left dangling.
        """
        by_id = {task.id: task for task in tasks}

        for edge in edges:
            successor = by_id.get(edge['successor'])
            predecessor = by_id.get(edge['predecessor'])
            if successor is None or predecessor is None:
                continue
            if successor.id == predecessor.id:
                continue
            # The type and the lag are parsed above; they used to be flattened
            # to SS-or-FS with the lag dropped, because the model knew only
            # those two and had nowhere to put a difference. It carries all
            # four types and a lag now, so the file's own link survives.
            successor.add_dependency(predecessor.id,
                                     dep_type=edge.get('type', 'FS'),
                                     hardness=edge.get('hardness', 'Hard'),
                                     lag=edge.get('lag', 0))

    def parse_tasks(self, root: ET.Element,
                    calendar: Optional[GanttProjectCalendar] = None) -> List[Task]:
        """
        Parse all tasks from GAN XML, including nested sub-tasks.

        RETURNS:
        --------
        List[Task]
            Every task in document order, each parent immediately followed by
            its descendants.
        """
        if calendar is None:
            calendar = GanttProjectCalendar.from_element(root.find('calendars'))

        color_map = self.parse_colors(root)
        tasks: List[Task] = []

        tasks_elem = root.find('tasks')
        if tasks_elem is not None:
            for task_elem in tasks_elem.findall('task'):
                tasks.extend(self.parse_task(task_elem, color_map, calendar))

        self.apply_dependencies(tasks, self.parse_successor_edges(root))
        return tasks

    def import_gan(self, filepath: str) -> Optional[Project]:
        """
        Import a .gan file and convert it to a Project object.

        PARAMETERS:
        -----------
        filepath : str
            Path to the .gan file

        RETURNS:
        --------
        Optional[Project]
            The imported project, or None if the file is missing or malformed.
        """
        try:
            if not Path(filepath).exists():
                logger.warning(f"File not found: {filepath}")
                return None

            tree = ET.parse(filepath)
            root = strip_namespaces(tree.getroot())

            project_name = root.get('name') or 'Imported Project'
            calendar = GanttProjectCalendar.from_element(root.find('calendars'))
            tasks = self.parse_tasks(root, calendar)

            project = Project(name=project_name, tasks=tasks)
            logger.info("Imported %d task(s) from GAN file %s",
                        len(project.tasks), filepath)
            return project

        except ET.ParseError as e:
            logger.exception(f"Error parsing GAN file: {e}")
            return None
        except Exception as e:
            logger.exception(f"Error importing GAN file: {e}")
            return None


class GANExporter:
    """
    Exports Project objects to GAN format (for potential future use).
    """

    def __init__(self):
        pass

    def export_gan(self, project: Project, filepath: str) -> bool:
        """
        Export a Project to GAN format.

        Note: This is a simplified exporter and may not include all GAN features.
        """
        try:
            # This would require implementing the full GAN XML structure
            # For now, we'll just return False as this is not a priority
            logger.warning("GAN export not yet implemented")
            return False
        except Exception as e:
            logger.exception(f"Error exporting GAN file: {e}")
            return False


# Convenience functions
def import_gan_file(filepath: str) -> Optional[Project]:
    """Import a .gan file."""
    importer = GANImporter()
    return importer.import_gan(filepath)
