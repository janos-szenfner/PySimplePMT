"""
Microsoft Project export: the plan as an MSPDI (.xml) file.

WHY THIS MODULE EXISTS:
======================
Microsoft Project is what a plan gets asked for in, and .mpp is what people
mean when they ask. Nothing writes .mpp: it is an undocumented binary format
whose only complete writer is Project itself, and the readers that exist -
this application's own MPP import among them, see mpp_importer - are
reverse-engineered. So the plan is written as MSPDI instead, the XML
interchange format Microsoft publishes and Project opens directly with File >
Open. It is also what every other planning tool reads, which .mpp is not.

WHY THE DATES ARE PINNED:
========================
MSPDI states a schedule the way Project thinks about one: a duration, a set of
links, and a constraint saying what the task is allowed to do. Handing over
durations and links alone and letting Project derive the dates - the obvious
export, and the wrong one - hands it a plan it will re-solve. Every task
without a predecessor collapses onto the project start date, and every task
whose dates this application arrived at through something MSPDI cannot say - a
rubber link, an earliest-begin floor, a per-task calendar - moves.

So every piece of work is written with a Start No Earlier Than constraint on
the date the plan says. That is a floor rather than a pin: the links are still
written and still push a task out when its predecessor slips, which is the
behaviour a reader wants. What it will not do is pull a task earlier than this
application scheduled it. Summary rows carry no constraint, because Project
computes those from their children and would refuse a summary that disagreed.

The rule is the one the spreadsheet export follows for its formulas: a file
that recalculates is worth having, and a file that recalculates to something
other than the plan is worth less than one that does not recalculate at all.

WHAT DOES NOT SURVIVE:
======================
Task colours - MSPDI has no field for one - and the distinction between a
Phase and a Task that has children, since Project has one kind of summary row.
Both are cosmetic.

A task's status - Active, Estimated or Inactive - does not survive either.
MSPDI's <Task> is
a fixed sequence of the elements the schema names, and Status is not one of
them - Project has a Status of its own but it is a calculated field, not
something a file may state. An element the schema does not know sits in the
middle of that sequence and makes the file invalid, so a plan carrying one may
not open in Project at all: a field that does not cross is a smaller loss than
an export that cannot be read. It crosses in the .gan and Mermaid exports and
in the application's own files, which is where a round trip is expected.

Everything that decides a date goes across, including the per-task calendars,
which is the one thing MSPDI holds and the .gan export cannot.

DEVELOPMENT NOTES:
------------------
MSPDI's schema is a sequence, so element order inside <Project> and <Task> is
not decoration - Project rejects a file that reorders them. The order used
here is the schema's own; ELEMENT ORDER comments mark the two places where it
looks wrong and is not.

Lag is written in tenths of a minute, which is the unit MSPDI counts every
duration-like number in, whatever LagFormat says the reader should display.
"""

import os
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from gantt_app.models import Project
from gantt_app.utils.log import get_logger
from gantt_app.utils.plan_export import (
    HOLIDAY_HORIZON_DAYS, PlanRow, calendar_exceptions,
    duration_in_working_days, numbering, outline, plan_span,
)
from gantt_app.workdaycalendar import WorkingCalendar, as_date

logger = get_logger(__name__)


#: The MSPDI namespace. Written as a plain attribute on the root element
#: rather than through ElementTree's namespace machinery, which would prefix
#: every tag; MSPDI wants the default namespace and no prefixes anywhere.
MSPDI_NAMESPACE = 'http://schemas.microsoft.com/project'

#: Which Project release the file claims to be from. 14 is Project 2010, the
#: oldest version whose schema everything still current reads.
SAVE_VERSION = '14'

#: The working day, and the day Project counts durations in. A task of one day
#: is 8 hours because of these two numbers, not because of anything in the
#: plan: this application counts in whole days and has no notion of hours.
DAY_START, DAY_END = '08:00:00', '17:00:00'
MINUTES_PER_DAY = 480

#: Lunch, which is only here because a working day stated as one unbroken
#: 08:00-17:00 block would be nine hours and disagree with MinutesPerDay.
LUNCH_START, LUNCH_END = '12:00:00', '13:00:00'

#: MSPDI counts every span in tenths of a minute, so a day of lag is this.
TENTHS_PER_DAY = MINUTES_PER_DAY * 10

#: Duration display format: 7 is days. Applies to durations and to lag.
DURATION_FORMAT_DAYS = '7'

#: Fixed Duration. The plan has no resources, so effort cannot drive
#: anything, and a task's duration is exactly what this application says.
TASK_TYPE_FIXED_DURATION = '1'

#: Constraint codes. 0 is As Soon As Possible; 4 is Start No Earlier Than.
CONSTRAINT_ASAP = '0'
CONSTRAINT_START_NO_EARLIER_THAN = '4'

#: PredecessorLink type codes.
DEPENDENCY_TYPE_CODES = {'FF': '0', 'FS': '1', 'SF': '2', 'SS': '3'}

#: Project scores priority out of 1000 rather than by name, 500 being normal.
PRIORITY_SCORES = {
    'Lowest': '100',
    'Low': '300',
    'Normal': '500',
    'High': '700',
    'Highest': '900',
}

#: Weekday codes: Sunday is 1 and Saturday is 7, where date.weekday() has
#: Monday at 0. DayType 0 marks a dated exception rather than a weekday.
DAY_TYPE_EXCEPTION = '0'

#: The calendar every task follows unless it names another.
BASE_CALENDAR_UID = 1
BASE_CALENDAR_NAME = 'Standard'


def _day_type(weekday: int) -> str:
    """One weekday as MSPDI numbers it, from a date.weekday() index."""
    return str(1 if weekday == 6 else weekday + 2)


def _moment(day, time_of_day: str) -> str:
    """One date and time as MSPDI writes them: YYYY-MM-DDTHH:MM:SS."""
    return f"{as_date(day).isoformat()}T{time_of_day}"


def _duration(days: int) -> str:
    """A number of working days as an MSPDI duration."""
    return f"PT{days * 8}H0M0S"


def _text(parent: ET.Element, tag: str, value) -> ET.Element:
    """Add a leaf element holding a value."""
    element = ET.SubElement(parent, tag)
    element.text = str(value)
    return element


# ---------------------------------------------------------------------------
# Calendars
# ---------------------------------------------------------------------------

def _write_working_times(weekday: ET.Element) -> None:
    """Write the two blocks either side of lunch that make up a working day."""
    times = ET.SubElement(weekday, 'WorkingTimes')
    for start, finish in ((DAY_START, LUNCH_START), (LUNCH_END, DAY_END)):
        period = ET.SubElement(times, 'WorkingTime')
        _text(period, 'FromTime', start)
        _text(period, 'ToTime', finish)


def _write_exception(week_days: ET.Element, day: date, working: bool) -> None:
    """
    Write one dated exception to the working week.

    DEVELOPMENT NOTES:
    ------------------
    An exception is a WeekDay with DayType 0 and a TimePeriod naming the date,
    which is the form every MSPDI reader has understood since Project 2003.
    Project 2007 added an <Exceptions> block that says the same thing and can
    also express a recurrence; it is not used here because nothing this
    application holds recurs in a way Project's recurrence rules can state,
    and the older form is the one with no version floor under it.
    """
    weekday = ET.SubElement(week_days, 'WeekDay')
    _text(weekday, 'DayType', DAY_TYPE_EXCEPTION)
    _text(weekday, 'DayWorking', '1' if working else '0')
    period = ET.SubElement(weekday, 'TimePeriod')
    _text(period, 'FromDate', _moment(day, '00:00:00'))
    _text(period, 'ToDate', _moment(day, '23:59:00'))
    if working:
        _write_working_times(weekday)


def _write_calendar(calendars: ET.Element, uid: int, name: str,
                    calendar: WorkingCalendar,
                    span: Optional[Tuple[date, date]]) -> None:
    """Write one <Calendar>: the week, then every date that departs from it."""
    element = ET.SubElement(calendars, 'Calendar')
    _text(element, 'UID', uid)
    _text(element, 'Name', name)
    _text(element, 'IsBaseCalendar', '1')
    # -1 is MSPDI for "this calendar is not derived from another one"
    _text(element, 'BaseCalendarUID', '-1')

    week_days = ET.SubElement(element, 'WeekDays')
    for index in range(7):
        working = index not in calendar.non_working_days
        weekday = ET.SubElement(week_days, 'WeekDay')
        _text(weekday, 'DayType', _day_type(index))
        _text(weekday, 'DayWorking', '1' if working else '0')
        if working:
            _write_working_times(weekday)

    if span is None:
        return

    first, last = span
    days_off, days_worked = calendar_exceptions(
        calendar, first, last + timedelta(days=HOLIDAY_HORIZON_DAYS))
    for day in days_off:
        _write_exception(week_days, day, working=False)
    for day in days_worked:
        _write_exception(week_days, day, working=True)


def _calendar_uids(project: Project) -> Dict[str, int]:
    """
    A UID for each named calendar a task actually follows.

    RETURNS:
    --------
    Dict[str, int]
        Calendar ID to UID, numbered after the plan's own calendar.

    DEVELOPMENT NOTES:
    ------------------
    Only calendars in use are written. An unused one in the registry says
    nothing about the plan, and a Calendar element nothing points at is a
    thing for the reader to wonder about rather than information.
    """
    uids: Dict[str, int] = {}
    for task in project.tasks:
        calendar_id = task.calendar_id
        if not calendar_id or calendar_id in uids:
            continue
        if project.calendars.get(calendar_id) is None:
            continue
        uids[calendar_id] = BASE_CALENDAR_UID + 1 + len(uids)
    return uids


def _write_calendars(root: ET.Element, project: Project,
                     uids: Dict[str, int]) -> None:
    """Write the plan's calendar, then every named calendar in use."""
    span = plan_span(project)
    calendars = ET.SubElement(root, 'Calendars')
    _write_calendar(calendars, BASE_CALENDAR_UID, BASE_CALENDAR_NAME,
                    project.calendar, span)

    for calendar_id, uid in sorted(uids.items(), key=lambda pair: pair[1]):
        named = project.calendars.get(calendar_id)
        _write_calendar(calendars, uid, named.name, named.calendar, span)


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

def _write_predecessors(element: ET.Element, row: PlanRow,
                        numbers: Dict[str, int]) -> None:
    """
    Write the links this task waits on.

    DEVELOPMENT NOTES:
    ------------------
    MSPDI stores a link on the successor and names the predecessor, which is
    the way Task.dependencies already holds it - so unlike the GanttProject
    export, nothing is reversed here.

    Hardness has no equivalent. Every Project link is a floor: a successor may
    sit later than its predecessor requires but never earlier. That is exactly
    a Rubber link, and it is what a Hard link does too in any plan where the
    successor has no float, which is the usual case.
    """
    for dependency in row.task.dependencies:
        predecessor = numbers.get(dependency.task_id)
        if predecessor is None:
            logger.warning("Task %r depends on %r, which is not in the plan; "
                           "the link is not exported",
                           row.task.name, dependency.task_id)
            continue
        link = ET.SubElement(element, 'PredecessorLink')
        _text(link, 'PredecessorUID', predecessor)
        _text(link, 'Type', DEPENDENCY_TYPE_CODES.get(dependency.dep_type, '1'))
        _text(link, 'CrossProject', '0')
        _text(link, 'LinkLag', dependency.lag * TENTHS_PER_DAY)
        _text(link, 'LagFormat', DURATION_FORMAT_DAYS)


def _write_task(tasks: ET.Element, row: PlanRow, project: Project,
                numbers: Dict[str, int], uids: Dict[str, int]) -> None:
    """Write one <Task>, in the order the MSPDI schema demands."""
    task = row.task
    milestone = task.effective_milestone
    calendar = project.calendar_for(task)
    days = duration_in_working_days(calendar, task)
    finish = task.start_date if milestone or task.end_date is None else task.end_date

    element = ET.SubElement(tasks, 'Task')
    _text(element, 'UID', row.number)
    _text(element, 'ID', row.number)
    _text(element, 'Name', task.name)
    _text(element, 'Type', TASK_TYPE_FIXED_DURATION)
    _text(element, 'IsNull', '0')
    _text(element, 'WBS', row.outline_number)
    _text(element, 'OutlineNumber', row.outline_number)
    _text(element, 'OutlineLevel', row.level)
    _text(element, 'Priority', PRIORITY_SCORES.get(task.priority, '500'))
    _text(element, 'Start', _moment(task.start_date, DAY_START))
    _text(element, 'Finish', _moment(finish, DAY_START if milestone else DAY_END))
    _text(element, 'Duration', _duration(days))
    _text(element, 'DurationFormat', DURATION_FORMAT_DAYS)
    _text(element, 'Work', _duration(0))
    _text(element, 'Estimated', '0')
    _text(element, 'Milestone', '1' if milestone else '0')
    _text(element, 'Summary', '1' if row.is_summary else '0')
    _text(element, 'PercentComplete', max(0, min(100, int(task.progress or 0))))

    constraint, constraint_date = _constraint(row)
    _text(element, 'ConstraintType', constraint)
    # ELEMENT ORDER: CalendarUID really does sit between the constraint's type
    # and its date in the schema's sequence. Moving it next to the other
    # identifiers at the top reads better and produces a file Project refuses.
    if task.calendar_id in uids:
        _text(element, 'CalendarUID', uids[task.calendar_id])
    if constraint_date is not None:
        _text(element, 'ConstraintDate', constraint_date)

    if task.details:
        _text(element, 'Notes', task.details)

    # ELEMENT ORDER: the links come after every scalar field, Notes included.
    _write_predecessors(element, row, numbers)


def _constraint(row: PlanRow) -> Tuple[str, Optional[str]]:
    """
    What a task is allowed to do, and from when.

    RETURNS:
    --------
    Tuple[str, Optional[str]]
        The constraint code and the date it applies from, or None where the
        constraint takes no date.

    DEVELOPMENT NOTES:
    ------------------
    See the note on the module for why work is pinned and summaries are not.
    An Earliest begin date is the same idea as Start No Earlier Than and wins
    where it is set, since it is a floor the user typed rather than one this
    export inferred - and the two agree anyway whenever the floor is what put
    the task where it is.
    """
    if row.is_summary:
        return CONSTRAINT_ASAP, None

    task = row.task
    floor = task.earliest_begin or task.start_date
    return CONSTRAINT_START_NO_EARLIER_THAN, _moment(floor, DAY_START)


def _write_tasks(root: ET.Element, project: Project, rows: List[PlanRow],
                 uids: Dict[str, int]) -> None:
    """Write the <Tasks> block, in outline order."""
    tasks = ET.SubElement(root, 'Tasks')
    numbers = numbering(rows)
    for row in rows:
        _write_task(tasks, row, project, numbers, uids)


# ---------------------------------------------------------------------------
# The document
# ---------------------------------------------------------------------------

def _write_properties(root: ET.Element, project: Project) -> None:
    """
    Write the project-level settings, in the order the schema demands.

    DEVELOPMENT NOTES:
    ------------------
    MinutesPerWeek follows the plan's own week rather than being the usual
    2400. A plan that works six days has a 2880-minute week, and a reader told
    otherwise converts every duration expressed in weeks wrongly.
    """
    span = plan_span(project)
    worked_weekdays = sum(1 for weekday in range(7)
                          if weekday not in project.calendar.non_working_days)

    _text(root, 'SaveVersion', SAVE_VERSION)
    _text(root, 'Name', f"{project.name or 'Project'}.xml")
    _text(root, 'Title', project.name or 'Project')
    _text(root, 'CreationDate', datetime.now().replace(microsecond=0).isoformat())
    _text(root, 'ScheduleFromStart', '1')
    if span is not None:
        _text(root, 'StartDate', _moment(span[0], DAY_START))
        _text(root, 'FinishDate', _moment(span[1], DAY_END))
    _text(root, 'CalendarUID', BASE_CALENDAR_UID)
    _text(root, 'DefaultStartTime', DAY_START)
    _text(root, 'DefaultFinishTime', DAY_END)
    _text(root, 'MinutesPerDay', MINUTES_PER_DAY)
    _text(root, 'MinutesPerWeek', MINUTES_PER_DAY * max(worked_weekdays, 1))
    _text(root, 'DaysPerMonth', '20')
    _text(root, 'DefaultTaskType', TASK_TYPE_FIXED_DURATION)
    _text(root, 'DurationFormat', DURATION_FORMAT_DAYS)
    _text(root, 'WorkFormat', '2')
    # The setting that makes the constraints above mean anything: told not to
    # honour them, Project drags every task back onto its links and undoes the
    # whole point of writing a date. It defaults to on and is stated anyway,
    # because a default is not a promise.
    _text(root, 'HonorConstraints', '1')


def build_msproject_tree(project: Project) -> ET.ElementTree:
    """
    Build the whole MSPDI document for a project.

    RETURNS:
    --------
    ET.ElementTree
        The document, ready to be written or inspected. Exposed separately
        from the file writing so the tests can read the tree back without
        going through a temporary file.
    """
    rows = outline(project)
    uids = _calendar_uids(project)

    root = ET.Element('Project', {'xmlns': MSPDI_NAMESPACE})
    _write_properties(root, project)
    _write_calendars(root, project, uids)
    _write_tasks(root, project, rows, uids)
    ET.SubElement(root, 'Resources')
    ET.SubElement(root, 'Assignments')

    logger.info("Built a Microsoft Project document of %d task(s) and %d "
                "calendar(s) for %r", len(rows), len(uids) + 1, project.name)
    return ET.ElementTree(root)


def generate_msproject_content(project: Project) -> str:
    """
    The MSPDI file for a project, as text.

    RETURNS:
    --------
    str
        The complete XML document, including its declaration.
    """
    tree = build_msproject_tree(project)
    ET.indent(tree, space='    ')
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            + ET.tostring(tree.getroot(), encoding='unicode') + '\n')


def export_project_to_msproject(project: Project, filepath: str) -> bool:
    """
    Export a Project to a Microsoft Project (MSPDI .xml) file.

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
    >>> from gantt_app.utils.msproject_exporter import export_project_to_msproject
    >>> from datetime import datetime, timedelta
    >>>
    >>> project = Project(name="My Project")
    >>> start = datetime(2024, 1, 1)
    >>> project.add_task(Task.create_task("Task 1", start, start + timedelta(days=5)))
    >>> export_project_to_msproject(project, "/path/to/output.xml")
    True
    """
    temp_path = Path(f"{filepath}.tmp")
    try:
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(temp_path, 'w', encoding='utf-8') as handle:
            handle.write(generate_msproject_content(project))
        if path.exists():
            os.replace(path, Path(f"{filepath}.bak"))
        os.replace(temp_path, path)
        logger.info("Exported %r to %s", project.name, filepath)
        return True
    except Exception:
        logger.exception("Could not export %r to %s", project.name, filepath)
        return False
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass
