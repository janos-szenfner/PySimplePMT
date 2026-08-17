"""
Mermaid file importer and exporter for the Gantt Project Management Tool.

Handles importing and exporting Mermaid Gantt chart syntax.
Mermaid Gantt charts use a text-based format that can include project information,
tasks, milestones, and dependencies.

Example Mermaid Gantt syntax:
```mermaid
gantt
    title Project Name
    dateFormat  YYYY-MM-DD
    section Section 1
    Task 1 :a1, 2024-01-01, 7d
    Task 2 :a2, after a1, 5d
    milestone Milestone 1 :a3, after a2
    section Section 2
    Task 3 :a4, 2024-01-10, 3d
```
"""

import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path

from gantt_app.models import Project, Task
from gantt_app.workdaycalendar import WorkingCalendar
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


class MermaidImporter:
    """
    Imports Mermaid Gantt chart files and converts them to Project objects.
    
    Mermaid Gantt charts use a specific text-based syntax to define tasks,
    milestones, and their relationships.
    """

    #: The calendar a stated duration is counted against: Monday to Friday.
    #: An imported chart declares no holidays, and the standard week is what
    #: the application schedules on - see gantt_app.workdaycalendar.
    CALENDAR = WorkingCalendar()

    def __init__(self, group_by_section: bool = True):
        """
        PARAMETERS:
        -----------
        group_by_section : bool, optional
            When True (default), each 'section' in the Mermaid chart becomes a
            parent Task and the tasks below it become Sub-Tasks of it, so the
            chart's grouping survives the import. Set to False to import a
            flat task list instead.
        """
        self.default_color = "#1f6aa5"
        self.milestone_color = "#e74c3c"
        self.section_color = "#34495e"
        self.group_by_section = group_by_section

    def _parse_date(self, date_str: str, date_format: str = "%Y-%m-%d") -> Optional[datetime]:
        """Parse date string from Mermaid file."""
        if not date_str or date_str.strip() == '':
            return None
        try:
            return datetime.strptime(date_str.strip(), date_format)
        except (ValueError, TypeError):
            return None
    
    #: Working days per week and per month, for a duration written in either.
    #: A week of work is five days and a month is four of those - the same
    #: convention every planning tool uses, and the one that makes "2w" mean
    #: two weeks of work rather than ten working days spread over a fortnight
    #: and a bit.
    DAYS_PER_WEEK = 5
    DAYS_PER_MONTH = 20

    def _parse_duration(self, duration_str: str, start_date: datetime) -> Optional[datetime]:
        """
        Parse duration string and calculate the inclusive end date.

        DEVELOPMENT NOTES:
        ------------------
        A duration is working days, as everywhere else in the application - see
        gantt_app.workdaycalendar. A "5d" task starting on a Thursday therefore
        runs to the following Wednesday rather than to the Monday, having spent
        none of itself over the weekend.

        Mermaid itself counts a bare duration in calendar days unless the chart
        declares `excludes weekends`, so this does read some charts a few days
        long. Agreeing with the rest of the application is worth more: a plan
        imported from Mermaid and the same plan typed into the editor have to
        come out with the same dates, and a task whose stated length is spent
        on a Saturday is wrong in a way nobody can see in the chart.

        Task.end_date is inclusive, so the last day worked is returned rather
        than the first day after it. Returning the exclusive end here made
        every imported bar one day too long.
        """
        if not duration_str or duration_str.strip() == '':
            return None

        duration_str = duration_str.strip().lower()
        match = re.match(r'^(\d+)\s*([a-z]*)$', duration_str)
        if not match:
            return None

        number = int(match.group(1))
        unit = match.group(2)

        if unit in ['w', 'week', 'weeks']:
            days = number * self.DAYS_PER_WEEK
        elif unit in ['m', 'month', 'months']:
            days = number * self.DAYS_PER_MONTH
        else:
            # 'd'/'day'/'days' and any unrecognised unit are treated as days
            days = number

        if days <= 0:
            return start_date

        return self.CALENDAR.add_working_days(start_date, days)
    
    #: Chart-level directives that never describe a task.
    DIRECTIVES = (
        'title', 'dateFormat', 'axisFormat', 'excludes', 'includes',
        'todayMarker', 'tickInterval', 'weekday', 'weekend',
    )

    def _strip_indentation(self, line: str) -> str:
        """Remove leading whitespace from a line."""
        return line.strip()

    def _is_directive(self, line: str) -> bool:
        """Check whether a stripped line is a chart-level directive."""
        for directive in self.DIRECTIVES:
            if line == directive or line.startswith(directive + ' '):
                return True
        return False

    def _strip_frontmatter(self, content: str) -> str:
        """
        Remove a leading YAML frontmatter block from Mermaid content.

        DEVELOPMENT NOTES:
        ------------------
        Mermaid allows an optional '---' delimited YAML header carrying
        rendering config (theme, look, etc.). None of it maps onto the
        project model, and its 'key: value' lines could otherwise be
        mistaken for task definitions.
        """
        lines = content.split('\n')
        first = 0
        while first < len(lines) and not lines[first].strip():
            first += 1

        if first >= len(lines) or lines[first].strip() != '---':
            return content

        for index in range(first + 1, len(lines)):
            if lines[index].strip() in ('---', '...'):
                return '\n'.join(lines[index + 1:])

        # Unterminated frontmatter - leave the content untouched
        return content

    def _extract_section(self, line: str) -> Optional[str]:
        """Return the section name if the line opens a section, else None."""
        line = self._strip_indentation(line)
        if not line.startswith('section'):
            return None
        name = line[len('section'):].strip()
        return name or None

    def _extract_task_info(self, line: str) -> Optional[Dict[str, Any]]:
        """Extract task information from a Mermaid Gantt line."""
        line = self._strip_indentation(line)
        
        if not line or line.startswith('section') or line.startswith('%'):
            return None
        if line == 'gantt' or self._is_directive(line):
            return None

        is_milestone = False
        if line.startswith('milestone'):
            is_milestone = True
            line = line[len('milestone'):].strip()
        
        pattern = r'^(.+?)\s*:\s*([^,]+),\s*(.+)$'
        match = re.match(pattern, line)
        if not match:
            pattern = r'^([^:]+)\s*:\s*([^,]+),\s*(.+)$'
            match = re.match(pattern, line)
            if not match:
                return None
        
        name = match.group(1).strip()
        task_id = match.group(2).strip()
        rest = match.group(3).strip()
        
        task_info = {
            'name': name,
            'id': task_id,
            'is_milestone': is_milestone
        }
        
        after_match = re.match(r'after\s+([^,]+),\s*(.+)$', rest, re.IGNORECASE)
        if after_match:
            task_info['dependency'] = after_match.group(1).strip()
            task_info['duration'] = after_match.group(2).strip()
        else:
            after_simple_match = re.match(r'after\s+([^,\s].*)$', rest, re.IGNORECASE)
            if after_simple_match:
                task_info['dependency'] = after_simple_match.group(1).strip()
                if not is_milestone:
                    task_info['duration'] = '1d'
            else:
                date_part = rest.split(',')[0].strip() if ',' in rest else rest.strip()
                parsed_date = self._parse_date(date_part)
                if parsed_date:
                    task_info['start_date'] = date_part
                    if ',' in rest:
                        duration_str = rest.split(',', 1)[1].strip()
                        task_info['duration'] = duration_str
                else:
                    task_info['duration'] = rest
        
        return task_info
    
    def _extract_metadata(self, content: str) -> Dict[str, str]:
        """Extract metadata (title, dateFormat) from Mermaid content."""
        metadata = {
            'title': "Imported Mermaid Project",
            'dateFormat': "YYYY-MM-DD"
        }
        
        lines = content.split('\n')
        for line in lines:
            stripped_line = self._strip_indentation(line)
            if stripped_line.startswith('title'):
                parts = stripped_line.split(maxsplit=1)
                if len(parts) > 1:
                    metadata['title'] = stripped_line.split(' ', 1)[1].strip()
            elif stripped_line.startswith('dateFormat'):
                parts = stripped_line.split(maxsplit=1)
                if len(parts) > 1:
                    metadata['dateFormat'] = stripped_line.split(' ', 1)[1].strip()
        
        return metadata
    
    def _convert_mermaid_to_python_format(self, mermaid_format: str) -> str:
        """Convert Mermaid date format to Python datetime format."""
        format_map = {
            "YYYY-MM-DD": "%Y-%m-%d",
            "MM/DD/YYYY": "%m/%d/%Y",
            "DD/MM/YYYY": "%d/%m/%Y",
            "YYYY/MM/DD": "%Y/%m/%d",
            "DD-MM-YYYY": "%d-%m-%Y",
            "MM-DD-YYYY": "%m-%d-%Y",
        }
        return format_map.get(mermaid_format, "%Y-%m-%d")
    
    def _calculate_task_dates(self, tasks_info: List[Dict], task_map: Dict) -> None:
        """Calculate task dates based on dependencies."""
        # First pass: set explicit start dates and calculate end dates for tasks with explicit start
        for info in tasks_info:
            task_id = info['id']
            if task_id in task_map:
                task = task_map[task_id]
                if 'start_date' in info and info['start_date']:
                    start_date = self._parse_date(info['start_date'])
                    if start_date:
                        task.start_date = start_date
                
                if 'duration' in info and not info.get('is_milestone', False):
                    if task.start_date:
                        end_date = self._parse_duration(info['duration'], task.start_date)
                        if end_date:
                            task.end_date = end_date
        
        # Multiple passes to resolve dependency chains
        max_passes = len(tasks_info)
        for _ in range(max_passes):
            changed = False
            for info in tasks_info:
                task_id = info['id']
                if task_id in task_map and 'dependency' in info:
                    task = task_map[task_id]
                    dep_id = info['dependency']
                    
                    if dep_id in task_map:
                        dep_task = task_map[dep_id]
                        # A dependent task starts the next working day after
                        # its predecessor finishes - the Monday, for one
                        # following a task that ends on a Friday. Milestones
                        # have zero duration, so anything following one starts
                        # on the milestone date itself.
                        new_start_date = None
                        if dep_task.is_milestone and dep_task.start_date:
                            new_start_date = dep_task.start_date
                        elif dep_task.end_date:
                            new_start_date = self.CALENDAR.get_next_working_day(
                                dep_task.end_date + timedelta(days=1))

                        if new_start_date and new_start_date != task.start_date:
                            task.start_date = new_start_date
                            
                            # Recalculate end date based on duration
                            if 'duration' in info and not info.get('is_milestone', False):
                                task.end_date = self._parse_duration(info['duration'], task.start_date)
                            elif info.get('is_milestone', False):
                                # For milestones, we might have a duration that's actually a date offset
                                # But typically milestones have explicit dates or use dependency date
                                task.end_date = None
                            changed = True
            
            if not changed:
                break
    
    def _make_section_id(self, section_name: str, used_ids: set) -> str:
        """Build a task ID for a section that cannot collide with a task ID."""
        base = re.sub(r'[^a-zA-Z0-9_]', '_', section_name.strip().lower()).strip('_')
        candidate = f"section_{base}" if base else "section"

        if candidate not in used_ids:
            return candidate

        counter = 2
        while f"{candidate}_{counter}" in used_ids:
            counter += 1
        return f"{candidate}_{counter}"

    def _build_section_hierarchy(self, tasks_info: List[Dict], task_map: Dict,
                                 tasks: List[Task]) -> List[Task]:
        """
        Turn Mermaid sections into parent tasks holding their tasks as Sub-Tasks.

        RETURNS:
        --------
        List[Task]
            The full task list, with each section's parent task inserted
            immediately before the tasks belonging to it. Tasks that appear
            before any section stay at the root level.

        DEVELOPMENT NOTES:
        ------------------
        Section parents are derived, not declared: their span is the envelope
        of their children, computed after _calculate_task_dates has resolved
        every 'after' chain. Milestones contribute only their start date since
        they carry no end_date.
        """
        # Keyed by the (occurrence, name) pair assigned while parsing, so two
        # sections sharing a name stay distinct
        section_members: Dict[tuple, List[Task]] = {}
        section_order: List[tuple] = []

        for info in tasks_info:
            section = info.get('section')
            task = task_map.get(info['id'])
            if not section or task is None:
                continue
            if section not in section_members:
                section_members[section] = []
                section_order.append(section)
            section_members[section].append(task)

        if not section_members:
            return tasks

        used_ids = set(task_map.keys())
        section_tasks: Dict[tuple, Task] = {}

        for section in section_order:
            members = section_members[section]
            section_name = section[1]

            starts = [t.start_date for t in members if t.start_date]
            ends = [t.end_date for t in members if t.end_date]
            # A milestone-only section still needs a span to draw
            ends.extend(t.start_date for t in members if t.end_date is None and t.start_date)

            if not starts:
                continue

            section_id = self._make_section_id(section_name, used_ids)
            used_ids.add(section_id)

            parent = Task(
                id=section_id,
                name=section_name,
                start_date=min(starts),
                end_date=max(ends) if ends else None,
                progress=0,
                dependencies=[],
                color=self.section_color,
                is_milestone=False,
                task_type="Task",
                parent_task_id=None
            )
            section_tasks[section] = parent

            for member in members:
                member.task_type = "Subtask"
                member.parent_task_id = section_id

        # Rebuild the list so each parent precedes the tasks it contains
        ordered: List[Task] = []
        emitted_sections = set()

        for info in tasks_info:
            task = task_map.get(info['id'])
            if task is None or task in ordered:
                continue
            section = info.get('section')
            if section in section_tasks and section not in emitted_sections:
                ordered.append(section_tasks[section])
                emitted_sections.add(section)
            ordered.append(task)

        # Preserve anything the info list did not account for
        for task in tasks:
            if task not in ordered:
                ordered.append(task)

        return ordered

    def _parse_mermaid_content(self, content: str) -> Optional[Project]:
        """Parse Mermaid Gantt content and create a Project object."""
        try:
            content = self._strip_frontmatter(content)
            metadata = self._extract_metadata(content)
            project_name = metadata.get('title', "Imported Mermaid Project")
            python_date_format = self._convert_mermaid_to_python_format(
                metadata.get('dateFormat', "YYYY-MM-DD")
            )

            lines = content.split('\n')
            tasks_info = []
            current_section = None
            section_count = 0

            for line in lines:
                section = self._extract_section(line)
                if section is not None:
                    # Each 'section' line opens a new group, keyed by its
                    # position rather than its name. Mermaid renders two
                    # blocks that share a name as two separate sections, and
                    # keying by name alone silently merged them into one
                    # parent task.
                    section_count += 1
                    current_section = (section_count, section)
                    continue

                task_info = self._extract_task_info(line)
                if task_info:
                    task_info['section'] = current_section
                    tasks_info.append(task_info)

            tasks = []
            task_map = {}
            
            for info in tasks_info:
                task_id = info['id']
                name = info['name']
                is_milestone = info.get('is_milestone', False)
                
                start_date = datetime.now()
                
                if 'start_date' in info:
                    parsed_date = self._parse_date(info['start_date'], python_date_format)
                    if parsed_date:
                        start_date = parsed_date
                
                end_date = None
                if 'duration' in info and not is_milestone:
                    parsed_duration = self._parse_duration(info['duration'], start_date)
                    if parsed_duration:
                        end_date = parsed_duration
                
                color = self.milestone_color if is_milestone else self.default_color
                
                task = Task(
                    id=task_id,
                    name=name,
                    start_date=start_date,
                    end_date=end_date,
                    progress=0,
                    dependencies=[],
                    color=color,
                    is_milestone=is_milestone
                )
                
                tasks.append(task)
                task_map[task_id] = task
            
            for info in tasks_info:
                task_id = info['id']
                if task_id in task_map and 'dependency' in info:
                    dep_id = info['dependency']
                    task = task_map[task_id]
                    task.add_dependency(dep_id)
            
            self._calculate_task_dates(tasks_info, task_map)

            if self.group_by_section:
                tasks = self._build_section_hierarchy(tasks_info, task_map, tasks)

            project = Project(name=project_name, tasks=tasks)
            return project
            
        except Exception as e:
            logger.exception(f"Error parsing Mermaid content: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def import_mermaid(self, filepath: str) -> Optional[Project]:
        """Import a Mermaid file and convert it to a Project object."""
        try:
            if not Path(filepath).exists():
                logger.warning(f"File not found: {filepath}")
                return None
            
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            project = self._parse_mermaid_content(content)
            if project is not None:
                logger.info("Imported %d task(s) from Mermaid file %s",
                            len(project.tasks), filepath)
            return project
            
        except Exception as e:
            logger.exception(f"Error importing Mermaid file: {e}")
            return None


class MermaidExporter:
    """
    Exports Project objects to Mermaid Gantt chart format.

    DEVELOPMENT NOTES:
    ------------------
    Kept for backwards compatibility. The real implementation lives in
    mermaid_exporter.py, which is what the toolbar calls; this class delegates
    to it so the two cannot drift apart. They previously did, and only the
    toolbar's copy learned to write sections.
    """

    def __init__(self):
        pass

    def _generate_task_id(self, task: Task, used_ids: set) -> str:
        """Generate a unique task ID for Mermaid export."""
        if task.id and task.id not in used_ids:
            valid_id = re.sub(r'[^a-zA-Z0-9_]', '_', task.id)
            if valid_id and valid_id not in used_ids:
                used_ids.add(valid_id)
                return valid_id
        
        base_id = re.sub(r'[^a-zA-Z0-9_]', '_', task.name.lower())
        if base_id and base_id not in used_ids:
            used_ids.add(base_id)
            return base_id
        
        counter = 1
        while f"{base_id}_{counter}" in used_ids:
            counter += 1
        
        task_id = f"{base_id}_{counter}"
        used_ids.add(task_id)
        return task_id
    
    def _format_date(self, date: datetime) -> str:
        """Format datetime object as Mermaid date string."""
        return date.strftime("%Y-%m-%d")
    
    def _get_task_duration_days(self, task: Task) -> Optional[int]:
        """Get task duration in days."""
        if task.is_milestone:
            return 0
        if task.end_date is None or task.start_date is None:
            return None
        return (task.end_date - task.start_date).days + 1
    
    def export_mermaid(self, project: Project, filepath: str, 
                     include_date_format: bool = True) -> bool:
        """Export a Project to Mermaid Gantt chart format."""
        try:
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            content = self._generate_mermaid_content_with_dependencies(project, include_date_format)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception as e:
            logger.exception(f"Error exporting Mermaid file: {e}")
            return False
    
    def _generate_mermaid_content_with_dependencies(self, project: Project,
                                                   include_date_format: bool = True) -> str:
        """Generate Mermaid content with proper dependency handling."""
        from gantt_app.utils.mermaid_exporter import generate_mermaid_content

        return generate_mermaid_content(project, include_date_format)

    def _sort_tasks_for_dependencies(self, project: Project) -> List[Task]:
        """Sort tasks to ensure dependencies are defined before dependent tasks."""
        visited = set()
        sorted_tasks = []
        
        def visit(task: Task):
            if task.id in visited:
                return
            for dep_id in task.dependency_ids:
                dep_task = project.get_task_by_id(dep_id)
                if dep_task:
                    visit(dep_task)
            visited.add(task.id)
            sorted_tasks.append(task)
        
        for task in project.tasks:
            visit(task)
        
        return sorted_tasks
    
    def export_mermaid_content(self, project: Project) -> str:
        """Generate Mermaid Gantt chart content string."""
        return self._generate_mermaid_content_with_dependencies(project)


def import_mermaid_file(filepath: str) -> Optional[Project]:
    """Import a Mermaid file and return a Project object."""
    importer = MermaidImporter()
    return importer.import_mermaid(filepath)

def export_mermaid_file(project: Project, filepath: str) -> bool:
    """Export a Project to a Mermaid file."""
    exporter = MermaidExporter()
    return exporter.export_mermaid(project, filepath)