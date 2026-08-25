"""
What an interchange exporter needs from a plan.

WHY THIS MODULE EXISTS:
======================
The GanttProject and Microsoft Project exporters write completely different
XML and agree on almost nothing about how a file looks. They agree entirely on
what a plan *is*: an outline of tasks numbered from one, each holding a
duration counted in working days, over a calendar of days that are not worked.

Both formats state a schedule as a start plus a duration rather than as a pair
of dates, so both have to count working days the way this application counts
them, and both have to hand over the calendar that counting was done against -
otherwise the dates the reader sees are not the dates the plan says. That is
the same four pieces of arithmetic twice, so it is done once, here.

DEVELOPMENT NOTES:
------------------
Nothing here knows about XML. An exporter asks what the plan looks like and
then writes its own file; the day a third format is added it asks the same
questions rather than working them out again.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

from gantt_app.models import Project, Task
from gantt_app.utils.log import get_logger
from gantt_app.workdaycalendar import WorkingCalendar, as_date

logger = get_logger(__name__)


#: How far past the end of the plan the calendar is still written out.
#:
#: A plan gets extended far more often than it gets shortened, and a reader
#: who pushes the last task out by a month should not find the holidays stop
#: the day the plan used to end.
HOLIDAY_HORIZON_DAYS = 365

#: Ceiling on the day-by-day walk in calendar_exceptions. A plan whose dates
#: have been corrupted into the year 9999 should produce a short file and a
#: line in the log, not a walk of three million days.
MAX_EXCEPTION_DAYS = 366 * 25


@dataclass(frozen=True)
class PlanRow:
    """
    One task, placed in the outline the exporters write.

    ATTRIBUTES:
    -----------
    task : Task
        The task itself.
    number : int
        The number the application shows beside the row - its position in the
        list, counted from one; see Project.display_ids. Both formats
        identify a task by an integer, so this is what an exporter writes as
        the ID and what a dependency refers to, which means an exported file
        and the task list name a task by the same number.
    level : int
        Depth in the outline, a root task being level 1.
    outline_number : str
        The dotted position - "2.1.3" - that Microsoft Project calls the WBS.
    parent : Optional[Task]
        The task this one sits under, or None at the top of the plan.
    children : Tuple[Task, ...]
        The tasks sitting directly under this one, in plan order.
    """

    task: Task
    number: int
    level: int
    outline_number: str
    parent: Optional[Task]
    children: Tuple[Task, ...]

    @property
    def is_summary(self) -> bool:
        """Whether this row brackets other rows rather than being work."""
        return bool(self.children)


def outline(project: Project) -> List[PlanRow]:
    """
    Every task in the plan, in outline order, each placed in the hierarchy.

    PARAMETERS:
    -----------
    project : Project
        The plan to walk.

    RETURNS:
    --------
    List[PlanRow]
        Parents before their children, siblings in plan order.

    DEVELOPMENT NOTES:
    ------------------
    A task naming a parent that is not in the plan, or caught in a parent
    cycle, is never reached by walking down from the roots. Anything left over
    is appended at the top level rather than dropped: an export that quietly
    loses work would be far worse than one showing a task at an odd level.
    """
    # The numbers the application shows beside these rows. Written into the
    # files rather than a count kept here, so what a reader sees in the task
    # list and what they see in an exported file are the same number - and
    # so there is one definition of the order rather than two that agree
    # until somebody changes one. See Project.display_ids.
    numbers = project.display_ids()

    children: Dict[Optional[str], List[Task]] = {}
    known = {task.id for task in project.tasks}
    for task in project.tasks:
        parent_id = (task.parent_task_id
                     if task.parent_task_id in known else None)
        children.setdefault(parent_id, []).append(task)

    by_id = {task.id: task for task in project.tasks}
    rows: List[PlanRow] = []
    seen = set()

    def walk(parent_id: Optional[str], level: int, prefix: str) -> None:
        """Emit one level of the outline, then everything under it."""
        for position, task in enumerate(children.get(parent_id, []), start=1):
            if task.id in seen:
                continue
            seen.add(task.id)
            number = f"{prefix}.{position}" if prefix else str(position)
            rows.append(PlanRow(
                task=task,
                number=numbers.get(task.id, len(rows) + 1),
                level=level,
                outline_number=number,
                parent=by_id.get(parent_id) if parent_id else None,
                children=tuple(children.get(task.id, [])),
            ))
            walk(task.id, level + 1, number)

    walk(None, 1, "")

    for task in project.tasks:
        if task.id not in seen:
            seen.add(task.id)
            logger.warning("Task %r sits under a parent that is not in the "
                           "plan; exporting it at the top level", task.name)
            rows.append(PlanRow(
                task=task,
                number=numbers.get(task.id, len(rows) + 1),
                level=1,
                outline_number=str(len(rows) + 1),
                parent=None,
                children=(),
            ))

    return rows


def numbering(rows: Sequence[PlanRow]) -> Dict[str, int]:
    """
    The integer each task is written as, by task ID.

    RETURNS:
    --------
    Dict[str, int]
        Task ID to the number it is written as - the one the task list shows
        beside it. Both formats identify a task by an integer and this
        application's identities are opaque strings the reader never sees, so
        every reference in a file goes through here.
    """
    return {row.task.id: row.number for row in rows}


def duration_in_working_days(calendar: WorkingCalendar, task: Task) -> int:
    """
    How many working days a task occupies, counted against one calendar.

    PARAMETERS:
    -----------
    calendar : WorkingCalendar
        The calendar to count against. Which one that is belongs to the
        exporter: a format holding a single calendar counts everything
        against the plan's own, so the dates it shows are the plan's dates.
    task : Task
        The task to measure.

    RETURNS:
    --------
    int
        Zero for a milestone, which takes no time. At least one for anything
        else, including a task with no end date.

    DEVELOPMENT NOTES:
    ------------------
    The dates are counted rather than Task.duration being read, even where the
    task states one. A file that says "starts here, lasts this long" is
    expanded back into an end date by whatever opens it, so the number written
    has to be the one that lands on the end date this application shows. Where
    the two disagree - a duration left behind by an edit that moved the dates
    - the dates are what the plan means.
    """
    if task.effective_milestone:
        return 0
    if task.end_date is None:
        return 1
    return max(calendar.working_days_between(task.start_date, task.end_date), 1)


def plan_span(project: Project) -> Optional[Tuple[date, date]]:
    """
    The first and last day any task in the plan touches.

    RETURNS:
    --------
    Optional[Tuple[date, date]]
        Earliest start and latest finish, or None for an empty plan.
    """
    starts = [as_date(task.start_date) for task in project.tasks
              if task.start_date is not None]
    if not starts:
        return None

    finishes = [as_date(task.end_date) for task in project.tasks
                if task.end_date is not None]
    return min(starts), max(finishes + starts)


def calendar_exceptions(calendar: WorkingCalendar, first: date,
                        last: date) -> Tuple[List[date], List[date]]:
    """
    The dates where a calendar disagrees with its own working week.

    PARAMETERS:
    -----------
    calendar : WorkingCalendar
        The calendar to interrogate.
    first, last : date
        The span to look over, inclusive.

    RETURNS:
    --------
    Tuple[List[date], List[date]]
        Dates not worked that the week alone would have worked, then dates
        worked that the week alone would have taken off. Both in date order.

    DEVELOPMENT NOTES:
    ------------------
    A calendar takes days off for four separate reasons - a listed holiday, a
    recurring one, a public holiday in an observed country, and a manual
    override - and gives one back for a fifth. Asking is_working_day for every
    date in the span collapses all five into the only two answers a file can
    hold, and does it without this module needing to know there are five.

    The walk is capped. Every caller feeds it dates read from a project file,
    and a corrupted one reaching into the year 9999 should cost a warning
    rather than a hang inside an export.
    """
    not_worked: List[date] = []
    worked: List[date] = []

    if last < first:
        return not_worked, worked

    if (last - first).days > MAX_EXCEPTION_DAYS:
        logger.warning("Plan spans %d days; writing the calendar for the "
                       "first %d only", (last - first).days,
                       MAX_EXCEPTION_DAYS)
        last = first + timedelta(days=MAX_EXCEPTION_DAYS)

    current = first
    while current <= last:
        by_the_week = current.weekday() not in calendar.non_working_days
        actually = calendar.is_working_day(current)
        if actually != by_the_week:
            (worked if actually else not_worked).append(current)
        current += timedelta(days=1)

    return not_worked, worked
