"""
GAN export: the plan as a GanttProject file.

WHY THIS MODULE EXISTS:
======================
GanttProject reads and writes .gan, and this application has read it since the
beginning - see gan_importer. Reading a format without writing it makes the
other tool a source and this one a destination, which is the wrong shape for a
plan that gets passed around: whoever sent the file expects it back.

WHAT A .gan CAN AND CANNOT HOLD:
================================
GanttProject states a task as a start date plus a duration counted in working
days, and never writes an end date. The dates it displays are therefore not in
the file at all - they are replayed from the duration against the <calendars>
block - so the export is only right if the calendar goes with it and the
durations were counted against that same calendar. Both are done here, and it
is why every duration is counted against the *plan's* calendar even where the
task follows a named one of its own: the file holds one calendar, so counting
against any other would put the task's finish on a different day than the plan
shows. The duration written for such a task is not the number this application
displays; the date it lands on is the date this application displays, and a
date somebody can act on beats a number nobody reads.

Three things do not survive, and are logged rather than written wrong:

  * A named calendar per task. The format has one calendar, per above.
  * A day the plan works that its week says it should not - a Saturday
    make-up day. <date> entries only take days off.
  * Priorities finer than GanttProject's own five, which happen to be the
    same five - so this one does survive, through PRIORITY_CODES.

DEVELOPMENT NOTES:
------------------
Two details of the format are easy to get backwards, and gan_importer's own
notes say the same from the other side:

  * <depend id="X"/> nested inside task A says X comes *after* A. The element
    is written on the predecessor and names the successor, which is the
    reverse of Task.dependencies.
  * Sub-tasks are <task> elements nested inside their parent, to any depth,
    rather than carrying a parent reference.

Task IDs are integers in this format and strings here, so the outline position
is written instead - see plan_export.numbering. A file this module writes and
gan_importer reads back therefore comes home renumbered from 1, which is what
GanttProject would have done with it too.
"""

import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

from gantt_app.models import Project
from gantt_app.utils.log import get_logger
from gantt_app.utils.plan_export import (
    HOLIDAY_HORIZON_DAYS, PlanRow, calendar_exceptions,
    duration_in_working_days, numbering, outline, plan_span,
)
from gantt_app.workdaycalendar import WorkingCalendar, as_date

logger = get_logger(__name__)


#: The GanttProject release the file claims to come from. Written because the
#: attribute is always there in a real file; nothing reads it back.
GANTTPROJECT_VERSION = '3.2.3230'

#: <default-week> names the days by these attributes, Monday first, which is
#: how date.weekday() numbers them.
WEEKDAY_ATTRS = ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun')

#: A weekday is marked '0' when it is worked and '1' when it is not.
WEEKDAY_WORKING, WEEKDAY_OFF = '0', '1'

#: <depend type="..."/> codes, the reverse of gan_importer.DEPENDENCY_TYPES.
DEPENDENCY_TYPE_CODES = {'SS': '1', 'FS': '2', 'FF': '3', 'SF': '4'}

#: What this application calls Hard and Rubber, GanttProject calls these.
HARDNESS_CODES = {'Hard': 'Strong', 'Rubber': 'Rubber'}

#: GanttProject's priority numbers. Low, Normal and High were numbered first
#: and Highest and Lowest were added afterwards, which is why the sequence
#: does not run in order of priority.
PRIORITY_CODES = {
    'Low': '0',
    'Normal': '1',
    'High': '2',
    'Highest': '3',
    'Lowest': '4',
}

#: The task columns GanttProject shows, declared the way it declares them. It
#: writes this block into every file and reads its own display settings back
#: out of it; a file without one opens with no columns in the task table.
TASK_PROPERTIES = (
    ('tpd0', 'type', 'icon'),
    ('tpd1', 'priority', 'icon'),
    ('tpd2', 'info', 'icon'),
    ('tpd3', 'name', 'text'),
    ('tpd4', 'begindate', 'date'),
    ('tpd5', 'enddate', 'date'),
    ('tpd6', 'duration', 'int'),
    ('tpd7', 'completion', 'int'),
    ('tpd8', 'coordinator', 'text'),
    ('tpd9', 'predecessorsr', 'text'),
)


def _iso(moment) -> str:
    """One date as GanttProject writes it: plain YYYY-MM-DD, no time."""
    return as_date(moment).isoformat()


# ---------------------------------------------------------------------------
# The calendar
# ---------------------------------------------------------------------------

def _write_calendars(root: ET.Element, project: Project) -> None:
    """
    Write the <calendars> block: the working week and the days off.

    DEVELOPMENT NOTES:
    ------------------
    Recurring holidays are written as GanttProject writes them, with an empty
    year, so a plan running over several years keeps meaning "every year"
    rather than being flattened into one entry per year.

    Everything else a calendar takes off - a listed holiday, a public holiday
    in an observed country, a day taken off by hand - is written as a dated
    entry, because that is the only other thing the format holds. The span
    covered runs from the plan's first day to a year past its last, so a
    reader who pushes the end out still has the holidays that follow.

    A day the plan *works* that its week says it should not cannot be written
    at all: a <date> entry only ever takes a day off. Those are counted and
    logged, since the alternative is a file that silently schedules over them.
    """
    calendar = project.calendar
    calendars = ET.SubElement(root, 'calendars', {'base-id': 'none'})
    day_types = ET.SubElement(calendars, 'day-types')
    ET.SubElement(day_types, 'day-type', {'id': '0'})
    ET.SubElement(day_types, 'day-type', {'id': '1'})

    week = {'id': '1', 'name': 'default'}
    for index, attr in enumerate(WEEKDAY_ATTRS):
        week[attr] = (WEEKDAY_OFF if index in calendar.non_working_days
                      else WEEKDAY_WORKING)
    ET.SubElement(day_types, 'default-week', week)

    ET.SubElement(day_types, 'only-show-weekends', {'value': 'false'})
    ET.SubElement(day_types, 'overriden-day-types')
    ET.SubElement(day_types, 'days')

    for month, day in sorted(calendar.recurring_holidays):
        ET.SubElement(calendars, 'date', {
            'year': '', 'month': str(month), 'date': str(day),
            'type': 'HOLIDAY',
        })

    span = plan_span(project)
    if span is None:
        return

    first, last = span
    days_off, days_worked = calendar_exceptions(
        calendar, first, last + timedelta(days=HOLIDAY_HORIZON_DAYS))

    for day in days_off:
        if (day.month, day.day) in calendar.recurring_holidays:
            continue
        ET.SubElement(calendars, 'date', {
            'year': str(day.year), 'month': str(day.month),
            'date': str(day.day), 'type': 'HOLIDAY',
        })

    if days_worked:
        logger.warning(
            "%d day(s) this plan works are weekend or off days in its own "
            "week, and a .gan file cannot say so; GanttProject will show "
            "them as not worked (first is %s)",
            len(days_worked), days_worked[0].isoformat())


# ---------------------------------------------------------------------------
# The tasks
# ---------------------------------------------------------------------------

def _task_attributes(row: PlanRow, calendar: WorkingCalendar) -> Dict[str, str]:
    """
    Everything that goes on one <task> element as an attribute.

    DEVELOPMENT NOTES:
    ------------------
    A milestone is written both ways round - meeting="true" and a duration of
    zero - because GanttProject writes both and readers in the wild trust
    whichever they were built against, this application's own importer
    included.

    An Earliest begin date becomes thirdDate with its constraint flag set,
    which is where GanttProject keeps the same idea.
    """
    task = row.task
    milestone = task.effective_milestone

    attributes = {
        'id': str(row.number),
        'name': task.name,
        'color': task.color or '#8cb6ce',
        'meeting': 'true' if milestone else 'false',
        'start': _iso(task.start_date),
        'duration': str(duration_in_working_days(calendar, task)),
        'complete': str(max(0, min(100, int(task.progress or 0)))),
        'expand': 'true',
    }

    priority = PRIORITY_CODES.get(task.priority)
    if priority is not None and task.priority != 'Normal':
        attributes['priority'] = priority

    # Only a status that is not the default is written, so a plan of
    # ordinary tasks exports the same file it always did
    if task.status != 'Active':
        attributes['status'] = task.status
        logger.debug("Exporting task %r with status %s", task.name,
                     task.status)

    if task.earliest_begin is not None:
        attributes['thirdDate'] = _iso(task.earliest_begin)
        attributes['thirdDate-constraint'] = '1'

    return attributes


def _write_task(parent: ET.Element, row: PlanRow, rows: Dict[str, PlanRow],
                numbers: Dict[str, int], successors: Dict[str, List[dict]],
                calendar: WorkingCalendar) -> None:
    """Write one task, its notes, its outgoing links, then its children."""
    element = ET.SubElement(parent, 'task', _task_attributes(row, calendar))

    if row.task.details:
        notes = ET.SubElement(element, 'notes')
        notes.text = row.task.details

    for link in successors.get(row.task.id, []):
        ET.SubElement(element, 'depend', {
            'id': str(link['successor']),
            'type': DEPENDENCY_TYPE_CODES.get(link['type'], '2'),
            'difference': str(link['lag']),
            'hardness': HARDNESS_CODES.get(link['hardness'], 'Strong'),
        })

    for child in row.children:
        child_row = rows.get(child.id)
        if child_row is not None:
            _write_task(element, child_row, rows, numbers, successors, calendar)


def _successor_links(rows: List[PlanRow],
                     numbers: Dict[str, int]) -> Dict[str, List[dict]]:
    """
    Every dependency, turned round to hang off its predecessor.

    RETURNS:
    --------
    Dict[str, List[dict]]
        Predecessor task ID to the links leaving it, each naming the
        successor by the integer it is written as.

    DEVELOPMENT NOTES:
    ------------------
    Task.dependencies lists what a task waits for; a .gan lists what a task
    holds up. Every edge is therefore reversed on the way out, exactly as
    gan_importer reverses it on the way in.

    A link naming a task that is not in the plan is dropped with a warning.
    Writing it would produce a <depend> pointing at an id no reader can
    resolve, which GanttProject refuses the whole file over.
    """
    links: Dict[str, List[dict]] = {}

    for row in rows:
        for dependency in row.task.dependencies:
            if dependency.task_id not in numbers:
                logger.warning("Task %r depends on %r, which is not in the "
                               "plan; the link is not exported",
                               row.task.name, dependency.task_id)
                continue
            links.setdefault(dependency.task_id, []).append({
                'successor': numbers[row.task.id],
                'type': dependency.dep_type,
                'hardness': dependency.hardness,
                'lag': dependency.lag,
            })

    return links


def _write_tasks(root: ET.Element, project: Project,
                 rows: List[PlanRow]) -> None:
    """Write the <tasks> block: the column set, then the outline."""
    tasks = ET.SubElement(root, 'tasks', {'empty-milestones': 'true'})
    properties = ET.SubElement(tasks, 'taskproperties')
    for identifier, name, value_type in TASK_PROPERTIES:
        ET.SubElement(properties, 'taskproperty', {
            'id': identifier, 'name': name,
            'type': 'default', 'valuetype': value_type,
        })

    numbers = numbering(rows)
    successors = _successor_links(rows, numbers)
    by_id = {row.task.id: row for row in rows}

    named_calendars = {row.task.calendar_id for row in rows
                       if row.task.calendar_id}
    if named_calendars:
        logger.warning(
            "%d task(s) follow a named calendar, which a .gan file cannot "
            "hold; their durations are counted against the plan's own "
            "calendar so the dates still land where the plan says",
            sum(1 for row in rows if row.task.calendar_id))

    for row in rows:
        if row.level == 1:
            _write_task(tasks, row, by_id, numbers, successors,
                        project.calendar)


# ---------------------------------------------------------------------------
# The document
# ---------------------------------------------------------------------------

def build_gan_tree(project: Project) -> ET.ElementTree:
    """
    Build the whole .gan document for a project.

    RETURNS:
    --------
    ET.ElementTree
        The document, ready to be written or inspected. Exposed separately
        from the file writing so the tests can read the tree back without
        going through a temporary file.
    """
    rows = outline(project)
    start = project.start_date or (rows[0].task.start_date if rows
                                   else datetime.now())

    root = ET.Element('project', {
        'name': project.name or 'Project',
        'company': '',
        'webLink': '',
        'view-date': _iso(start),
        'view-index': '0',
        'gantt-divider-location': '300',
        'resource-divider-location': '300',
        'version': GANTTPROJECT_VERSION,
        'locale': 'en_US',
    })

    ET.SubElement(root, 'description')
    ET.SubElement(root, 'view', {'zooming-state': 'default:3',
                                 'id': 'gantt-chart'})
    ET.SubElement(root, 'view', {'id': 'resource-table'})

    _write_calendars(root, project)
    _write_tasks(root, project, rows)

    # GanttProject writes these whether or not they hold anything, and some
    # readers - its own older releases among them - expect the elements to be
    # there. This application has no resources to put in them.
    ET.SubElement(root, 'resources')
    ET.SubElement(root, 'allocations')
    ET.SubElement(root, 'vacations')
    ET.SubElement(root, 'previous')
    ET.SubElement(root, 'roles', {'roleset-name': 'Default'})

    logger.info("Built a GanttProject document of %d task(s) for %r",
                len(rows), project.name)
    return ET.ElementTree(root)


def generate_gan_content(project: Project) -> str:
    """
    The .gan file for a project, as text.

    RETURNS:
    --------
    str
        The complete XML document, including its declaration.
    """
    tree = build_gan_tree(project)
    ET.indent(tree, space='    ')
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            + ET.tostring(tree.getroot(), encoding='unicode') + '\n')


def export_project_to_gan(project: Project, filepath: str) -> bool:
    """
    Export a Project to a GanttProject (.gan) file.

    PARAMETERS:
    -----------
    project : Project
        The project to export.
    filepath : str
        Where to write the file. Parent directories are created.

    RETURNS:
    --------
    bool
        True when the file was written.

    EXAMPLE:
    --------
    >>> from gantt_app.models import Project, Task
    >>> from gantt_app.utils.gan_exporter import export_project_to_gan
    >>> from datetime import datetime, timedelta
    >>>
    >>> project = Project(name="My Project")
    >>> start = datetime(2024, 1, 1)
    >>> project.add_task(Task.create_task("Task 1", start, start + timedelta(days=5)))
    >>> export_project_to_gan(project, "/path/to/output.gan")
    True
    """
    try:
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as handle:
            handle.write(generate_gan_content(project))
        logger.info("Exported %r to %s", project.name, filepath)
        return True
    except Exception:
        logger.exception("Could not export %r to %s", project.name, filepath)
        return False
