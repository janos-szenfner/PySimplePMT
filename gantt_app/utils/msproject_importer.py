"""
Microsoft Project import: reading an MSPDI (.xml) file back into a plan.

WHY THIS MODULE EXISTS:
======================
Microsoft Project's own interchange format is MSPDI, an XML document whose
schema Microsoft publishes. It is what Project writes from File > Save As >
XML, what every other planning tool reads and writes, and what this
application's own msproject_exporter produces - so it is the format that
completes the round trip, and the only Microsoft format that can be read with
nothing installed.

It is not .mpp. That is an undocumented binary container, and reading one
means the kind of reverse engineering nobody has done in Python; see
mpp_importer, which sniffs a file and sends the XML here.

Everything here is the standard library. There is no optional dependency to
install, nothing to bundle, and nothing that can be missing at run time.

WHAT COMES BACK:
================
The hierarchy, the dates, the links with their types and lags, progress,
notes, priorities, the working calendar, and the per-task calendars. In other
words everything msproject_exporter writes, which is what the round-trip test
checks field by field.

Two things do not, because MSPDI has nowhere to keep them: a task's colour,
and how deep a summary row sat. Colours are assigned
from the same defaults the GanttProject import uses, and the summary levels
are worked out from the outline depth.

DEVELOPMENT NOTES:
------------------
Three details of the format are easy to read wrongly:

  * <OutlineLevel> is the *only* statement of hierarchy. Tasks are a flat
    list and a task's parent is the nearest task above it at one level less,
    which is why this walks a stack rather than looking up a parent ID.
  * <LinkLag> is counted in tenths of a minute whatever <LagFormat> says the
    reader should display, so a lag of two days arrives as 9600.
  * <WeekDay><DayType> numbers Sunday 1 and Saturday 7, where date.weekday()
    starts at Monday. A file read with that offset wrong produces a plan that
    works Sundays and rests on Mondays, and every date follows it.
"""

import xml.etree.ElementTree as ET

from gantt_app.utils import safexml
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from gantt_app.calendarregistry import CalendarRegistry
from gantt_app.models import Project, Task, child_type_for
# The same stripping the GanttProject reader does, and for the same reason:
# a file may or may not carry its namespace and both should parse through one
# code path. It lives there because that reader needed it first.
from gantt_app.utils.gan_importer import strip_namespaces
from gantt_app.utils.log import get_logger
from gantt_app.workdaycalendar import WorkingCalendar

logger = get_logger(__name__)


#: <PredecessorLink><Type> codes, the reverse of what the exporter writes.
DEPENDENCY_TYPES = {'0': 'FF', '1': 'FS', '2': 'SF', '3': 'SS'}

#: MSPDI counts every span in tenths of a minute, over an eight-hour day.
TENTHS_PER_DAY = 4800

#: Project scores priority out of 1000; these are the five this application
#: has, at the scores the exporter writes. Anything else takes the nearest.
PRIORITY_SCORES = {
    100: 'Lowest',
    300: 'Low',
    500: 'Normal',
    700: 'High',
    900: 'Highest',
}

#: Start No Earlier Than, the only constraint that maps onto anything here.
CONSTRAINT_START_NO_EARLIER_THAN = '4'

#: Colours, matching the GanttProject import so a plan does not change
#: appearance depending on which format it arrived in.
DEFAULT_COLOR = '#1f6aa5'
MILESTONE_COLOR = '#e74c3c'

#: Ceiling on expanding one calendar exception that names a range of dates.
MAX_EXCEPTION_SPAN = 366 * 5


def _child_text(element: ET.Element, tag: str,
                default: Optional[str] = None) -> Optional[str]:
    """The stripped text of one child element, or a default when absent."""
    child = element.find(tag)
    if child is None or child.text is None:
        return default
    text = child.text.strip()
    return text if text else default


def _parse_datetime(text: Optional[str]) -> Optional[datetime]:
    """
    One MSPDI timestamp, which is ISO 8601 without a zone.

    RETURNS:
    --------
    Optional[datetime]
        The moment, or None when the text is missing or unreadable.
    """
    if not text:
        return None

    cleaned = text.strip().rstrip('Z')
    for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f',
                '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue

    logger.warning("Ignoring unreadable date %r", text)
    return None


def _parse_duration_days(text: Optional[str]) -> Optional[int]:
    """
    An MSPDI duration - PT32H0M0S - as a number of eight-hour days.

    RETURNS:
    --------
    Optional[int]
        Whole days, rounded to the nearest. None when there is no duration
        to read, which is different from a duration of zero.
    """
    if not text:
        return None

    body = text.strip().upper()
    if not body.startswith('PT'):
        return None

    number = ''
    hours = minutes = 0.0
    for character in body[2:]:
        if character.isdigit() or character == '.':
            number += character
            continue
        try:
            value = float(number) if number else 0.0
        except ValueError:
            value = 0.0
        number = ''
        if character == 'H':
            hours = value
        elif character == 'M':
            minutes = value

    return int(round((hours + minutes / 60) / 8))


def _inclusive_end(start: datetime, finish: Optional[datetime]) -> Optional[datetime]:
    """
    The last day a task covers, from a Microsoft finish timestamp.

    DEVELOPMENT NOTES:
    ------------------
    Task.end_date is inclusive here and a Microsoft finish is a moment: a task
    ending on Friday finishes at 17:00 on the Friday, so the date part is the
    answer. The exception is a finish at midnight, which some writers use to
    mean the start of the day after the last one worked - taking its date
    would add a day the plan does not hold, so the day before is used instead.
    """
    if finish is None:
        return None

    day = datetime(finish.year, finish.month, finish.day)
    if (finish.hour, finish.minute, finish.second) == (0, 0, 0) and day > start:
        day -= timedelta(days=1)
    return max(day, datetime(start.year, start.month, start.day))


# ---------------------------------------------------------------------------
# Calendars
# ---------------------------------------------------------------------------

def _weekday_index(day_type: str) -> Optional[int]:
    """
    One MSPDI DayType as a date.weekday() index.

    RETURNS:
    --------
    Optional[int]
        Monday 0 through Sunday 6, or None for DayType 0, which is not a
        weekday at all but a dated exception.
    """
    try:
        code = int(day_type)
    except (TypeError, ValueError):
        return None
    if code == 1:
        return 6                      # Sunday
    if 2 <= code <= 7:
        return code - 2               # Monday through Saturday
    return None


def _exception_dates(period: Optional[ET.Element]) -> List[date]:
    """
    Every date one exception covers.

    DEVELOPMENT NOTES:
    ------------------
    An exception names a range rather than a day, and a company shutdown is
    written as one entry rather than five. The range is expanded because a
    calendar here holds individual dates, and capped because a corrupted file
    naming a century of shutdown should cost a warning rather than a hang.
    """
    if period is None:
        return []

    first = _parse_datetime(_child_text(period, 'FromDate'))
    last = _parse_datetime(_child_text(period, 'ToDate')) or first
    if first is None:
        return []

    start, finish = first.date(), last.date()
    if finish < start:
        return [start]

    span = (finish - start).days
    if span > MAX_EXCEPTION_SPAN:
        logger.warning("Calendar exception covers %d days; reading the first "
                       "%d", span, MAX_EXCEPTION_SPAN)
        span = MAX_EXCEPTION_SPAN

    return [start + timedelta(days=offset) for offset in range(span + 1)]


def _parse_calendar(element: ET.Element) -> WorkingCalendar:
    """
    One <Calendar> as a working calendar.

    DEVELOPMENT NOTES:
    ------------------
    Both exception forms are read. The older one is a WeekDay with DayType 0
    carrying a TimePeriod, which is what this application's exporter writes
    and what every reader has understood since Project 2003; the newer one is
    an <Exceptions> block, which is what Project itself writes now. A file
    can hold either, and one that holds both is not a contradiction - they
    are merged, and a date named twice is simply named twice.
    """
    calendar = WorkingCalendar()
    non_working = set()
    stated_week = False

    for weekday in element.findall('WeekDays/WeekDay'):
        day_type = _child_text(weekday, 'DayType')
        working = _child_text(weekday, 'DayWorking') == '1'
        index = _weekday_index(day_type)

        if index is not None:
            stated_week = True
            if not working:
                non_working.add(index)
            continue

        # DayType 0: a dated exception rather than a weekday
        for day in _exception_dates(weekday.find('TimePeriod')):
            if working:
                calendar.add_override(day, is_working_day=True,
                                      reason="Working day (MS Project)")
            else:
                calendar.holidays.add(day)

    for exception in element.findall('Exceptions/Exception'):
        working = _child_text(exception, 'DayWorking') == '1'
        for day in _exception_dates(exception.find('TimePeriod')):
            if working:
                calendar.add_override(day, is_working_day=True,
                                      reason=_child_text(exception, 'Name')
                                      or "Working day (MS Project)")
            else:
                calendar.holidays.add(day)

    # A file that never described the week keeps the standard one rather than
    # being read as working every day of it
    if stated_week:
        calendar.non_working_days = non_working

    return calendar


def _parse_calendars(root: ET.Element) -> Tuple[WorkingCalendar,
                                                Dict[str, WorkingCalendar],
                                                Dict[str, str]]:
    """
    Every calendar in the file, and which one the plan itself follows.

    RETURNS:
    --------
    Tuple[WorkingCalendar, Dict[str, WorkingCalendar], Dict[str, str]]
        The plan's own calendar, then the others by their MSPDI UID, then
        those UIDs' names.
    """
    calendars: Dict[str, WorkingCalendar] = {}
    names: Dict[str, str] = {}

    for element in root.findall('Calendars/Calendar'):
        uid = _child_text(element, 'UID')
        if uid is None:
            continue
        calendars[uid] = _parse_calendar(element)
        names[uid] = _child_text(element, 'Name') or f"Calendar {uid}"

    base_uid = _child_text(root, 'CalendarUID')
    if base_uid not in calendars:
        base_uid = next(iter(calendars), None)

    base = calendars.pop(base_uid, None) if base_uid else None
    if base_uid is not None:
        names.pop(base_uid, None)

    return base or WorkingCalendar(), calendars, names


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

def _task_type(is_milestone: bool, is_summary: bool, level: int) -> str:
    """
    What a task starts out as, before its parent gets a say.

    DEVELOPMENT NOTES:
    ------------------
    Project has one kind of summary row, so the depth decides: the top
    level is a Phase and anything below it a Task. child_type_for then moves
    it to whatever its parent can actually hold, which is what keeps a
    summary three levels down a Task, so its own children can be Subtasks.
    """
    if is_milestone:
        return 'Milestone'
    if is_summary:
        return 'Phase' if level <= 1 else 'Task'
    return 'Task'


def _parse_priority(text: Optional[str]) -> str:
    """The nearest named priority to a score out of 1000."""
    try:
        score = int(float(text))
    except (TypeError, ValueError):
        return 'Normal'
    return PRIORITY_SCORES[min(PRIORITY_SCORES, key=lambda k: abs(k - score))]


def _parse_dependencies(element: ET.Element,
                        by_uid: Dict[str, str]) -> List[dict]:
    """
    The links a task waits on, as this application states them.

    DEVELOPMENT NOTES:
    ------------------
    MSPDI holds a link on the successor and names the predecessor, which is
    the way Task.dependencies holds it too - so unlike the GanttProject
    reader, nothing is reversed here.

    Hardness has no equivalent in the format. Every Project link is a floor,
    which is what a Rubber link is, but Hard is this application's default and
    the one a reader means by an ordinary link, so that is what they become.
    """
    links = []

    for link in element.findall('PredecessorLink'):
        predecessor_uid = _child_text(link, 'PredecessorUID')
        predecessor = by_uid.get(predecessor_uid)
        if predecessor is None:
            logger.warning("Link to task UID %r, which is not in the file; "
                           "the link is dropped", predecessor_uid)
            continue

        try:
            lag_tenths = float(_child_text(link, 'LinkLag', '0'))
        except (TypeError, ValueError):
            lag_tenths = 0.0

        links.append({
            'task_id': predecessor,
            'dep_type': DEPENDENCY_TYPES.get(_child_text(link, 'Type', '1'),
                                             'FS'),
            'hardness': 'Hard',
            'lag': int(round(lag_tenths / TENTHS_PER_DAY)),
        })

    return links


def _parse_tasks(root: ET.Element, calendar_ids: Dict[str, str],
                 base_calendar: WorkingCalendar) -> List[Task]:
    """
    Every task in the file, in outline order and with its parent attached.

    DEVELOPMENT NOTES:
    ------------------
    Two passes. The first builds the tasks and records which MSPDI UID each
    one came from; the second attaches the links, because a task may name a
    predecessor that appears after it in the file and there is no ordering
    rule saying otherwise.

    Hierarchy comes off a stack indexed by outline level. A file that skips a
    level - straight from 1 to 3, which Project does not write but other
    tools do - attaches the task to the deepest open row above it rather than
    being dropped.
    """
    elements = []
    by_uid: Dict[str, str] = {}
    tasks: List[Task] = []
    stack: List[Task] = []

    for element in root.findall('Tasks/Task'):
        if _child_text(element, 'IsNull') == '1':
            continue

        # A task at outline level 0 is the project summary row, which is the
        # plan itself rather than work in it
        if _child_text(element, 'OutlineLevel') == '0':
            continue

        try:
            level = max(int(_child_text(element, 'OutlineLevel', '1')), 1)
        except (TypeError, ValueError):
            level = 1

        uid = _child_text(element, 'UID')
        name = _child_text(element, 'Name') or 'Unnamed Task'
        start = _parse_datetime(_child_text(element, 'Start'))
        if start is None:
            logger.warning("Task %r has no start date; it is not imported",
                           name)
            continue
        start = datetime(start.year, start.month, start.day)

        is_summary = _child_text(element, 'Summary') == '1'
        duration_days = _parse_duration_days(_child_text(element, 'Duration'))
        finish = _parse_datetime(_child_text(element, 'Finish'))
        is_milestone = (_child_text(element, 'Milestone') == '1'
                        or (duration_days == 0 and not is_summary))

        end = None if is_milestone else _inclusive_end(start, finish)
        if end is None and not is_milestone and duration_days:
            calendar = base_calendar
            end = calendar.add_working_days(start, max(duration_days - 1, 0))

        del stack[level - 1:]
        parent = stack[-1] if stack else None

        try:
            progress = max(0, min(100, int(float(
                _child_text(element, 'PercentComplete', '0')))))
        except (TypeError, ValueError):
            progress = 0

        task = Task(
            id=uid or str(len(tasks) + 1),
            name=name,
            start_date=start,
            end_date=end,
            progress=progress,
            dependencies=[],
            color=MILESTONE_COLOR if is_milestone else DEFAULT_COLOR,
            task_type=_task_type(is_milestone, is_summary, level),
            parent_task_id=parent.id if parent else None,
            priority=_parse_priority(_child_text(element, 'Priority')),
            details=_child_text(element, 'Notes', '') or '',
            calendar_id=calendar_ids.get(_child_text(element, 'CalendarUID')),
        )
        task.task_type = child_type_for(parent, task)

        constraint = _child_text(element, 'ConstraintType')
        constraint_date = _parse_datetime(_child_text(element,
                                                      'ConstraintDate'))
        # A Start No Earlier Than sitting on the task's own start says only
        # "stay where you are", which the dates already say. Only a floor
        # naming some other date is carrying information worth keeping.
        if (constraint == CONSTRAINT_START_NO_EARLIER_THAN
                and constraint_date is not None
                and constraint_date.date() != start.date()):
            task.earliest_begin = datetime(constraint_date.year,
                                           constraint_date.month,
                                           constraint_date.day)

        if uid is not None:
            by_uid[uid] = task.id
        tasks.append(task)
        stack.append(task)
        elements.append((task, element))

    for task, element in elements:
        for link in _parse_dependencies(element, by_uid):
            if link['task_id'] == task.id:
                continue
            task.add_dependency(link['task_id'], dep_type=link['dep_type'],
                                hardness=link['hardness'], lag=link['lag'])

    return tasks


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def parse_msproject(root: ET.Element) -> Project:
    """
    Build a project from a parsed MSPDI document.

    PARAMETERS:
    -----------
    root : ET.Element
        The <Project> element. Namespaces are stripped here, so a document
        may arrive with or without them.

    RETURNS:
    --------
    Project
        The plan the file describes.
    """
    root = strip_namespaces(root)

    base_calendar, named_calendars, names = _parse_calendars(root)

    registry = CalendarRegistry()
    calendar_ids: Dict[str, str] = {}
    for uid, calendar in named_calendars.items():
        named = registry.create(names.get(uid, f"Calendar {uid}"), calendar)
        calendar_ids[uid] = named.id

    tasks = _parse_tasks(root, calendar_ids, base_calendar)

    name = (_child_text(root, 'Title')
            or _child_text(root, 'Name', 'Imported Project'))
    if name.lower().endswith('.xml'):
        name = name[:-4]

    return Project(name=name, tasks=tasks, calendar=base_calendar,
                   calendars=registry)


def import_msproject_file(filepath: str) -> Optional[Project]:
    """
    Import a Microsoft Project MSPDI (.xml) file.

    PARAMETERS:
    -----------
    filepath : str
        Path to the file.

    RETURNS:
    --------
    Optional[Project]
        The plan, or None when the file is missing or cannot be read.

    EXAMPLE:
    --------
    >>> from gantt_app.utils.msproject_importer import import_msproject_file
    >>> project = import_msproject_file("/path/to/plan.xml")
    """
    try:
        if not Path(filepath).exists():
            logger.warning("File not found: %s", filepath)
            return None

        root = safexml.parse(filepath).getroot()
        project = parse_msproject(root)
        logger.info("Imported %d task(s) from the MS Project file %s",
                    len(project.tasks), filepath)
        return project

    except ET.ParseError:
        logger.exception("Could not parse the MS Project file %s", filepath)
        return None
    except Exception:
        logger.exception("Could not import the MS Project file %s", filepath)
        return None
