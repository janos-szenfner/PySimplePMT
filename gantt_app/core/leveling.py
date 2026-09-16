"""
Resource levelling: resolving overallocations by spending float.

WHY THIS MODULE EXISTS:
======================
The resource board can *show* that Alex has 70 hours in a 40-hour week, but
nothing in the application could do anything about it. This is the doing:
the same float the critical path analysis computes is spent to delay tasks
until nobody is booked beyond their capacity, the way Microsoft Project's
Resource Leveling does it.

DEVELOPMENT NOTES:
------------------
The engine is deliberately delay-only. Splitting a task mid-flight - the
other lever Microsoft Project offers - would mean inventing work segments
the task model does not have, and moving a whole task answers most real
overloads anyway. Reassignment is likewise out of scope: where no delay
can fix a day, the plan records it as unresolved with the advice to
reassign, which is the same thing Project prints.

Work is measured per day the way the heatmap already measures it - an
assignment's hours spread evenly over the task's working days - so the
leveler fixes exactly the overloads the user was looking at. Material and
cost assignments hold no hours and never register as load.

Two float caps exist because they answer different questions:

  * total float - how far a task can slip before the *project* finishes
    later. Spending it may drag successors but keeps the deadline.
  * free float - how far it can slip before *any successor's* dates move.
    Spending it is invisible to the rest of the plan. This is the default,
    and the safer of the two.

Tasks locked by a Must Start On / Must Finish On constraint are never
moved - levelling must not quietly break a promise somebody typed. A
deadline is a soft cap: a task is not pushed past it, and the block is
reported rather than silently failing the day.
"""

import copy
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

from gantt_app.core.models import Project, Task
from gantt_app.core.priority import priority_rank
from gantt_app.core.resource_model import DAYS, ResourceRepository
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)

#: How many move-and-rescan passes a run may take before it gives up. A
#: cyclic link set could otherwise spin forever; two hundred moves is also
#: far past any plan a human levels by hand.
DEFAULT_MAX_PASSES = 200


@dataclass
class LevelingOptions:
    """
    The knobs Microsoft Project's Leveling Options dialog exposes, cut to
    what the engine honours.

    ATTRIBUTES:
    -----------
    within_free_float : bool
        True (the default) delays a task only as far as its free float -
        no successor's dates move, so levelling stays invisible to the
        rest of the plan. False allows spending total float, which can
        push successors but still cannot move the project's finish.
    respect_deadlines : bool
        A task is never pushed past its deadline; the shortfall is
        reported instead. Off means deadlines are ignored - the deadline
        flag still shows the slip afterwards.
    max_passes : int
        The loop guard; see DEFAULT_MAX_PASSES.
    """
    within_free_float: bool = True
    respect_deadlines: bool = True
    max_passes: int = DEFAULT_MAX_PASSES


@dataclass
class LevelingMove:
    """One task the run would move, or did move."""
    task_id: str
    task_name: str
    resource_name: str       # the resource whose overload caused it; ''
                             # for a successor dragged by a dependency
    old_start: Optional[datetime]
    old_finish: Optional[datetime]
    new_start: Optional[datetime]
    new_finish: Optional[datetime]
    delay_days: int          # working days of slip, on the plan's calendar


@dataclass
class LevelingIssue:
    """An overload no delay could clear."""
    resource_name: str
    day: date
    over_by: float           # hours still beyond capacity
    detail: str              # what to do about it instead


@dataclass
class LevelingPlan:
    """
    Everything a levelling run decided, before or without applying it.

    The preview dialog shows moves + unresolved + skipped; Apply replays
    the engine on the real project, which is deterministic given the same
    plan, so what is shown is what happens.
    """
    moves: List[LevelingMove] = field(default_factory=list)
    unresolved: List[LevelingIssue] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    overallocations_found: int = 0
    finish_before: Optional[datetime] = None
    finish_after: Optional[datetime] = None
    gave_up: bool = False    # the pass cap was reached

    @property
    def finish_slipped(self) -> bool:
        """Whether the run moved the plan's last finish."""
        return (self.finish_before is not None
                and self.finish_after is not None
                and self.finish_after > self.finish_before)


def _assignment_hours(task: Task, entity_id: str) -> float:
    """The effort one entity's assignments put on a task's days."""
    hours = 0.0
    for assignment in task.resource_assignments:
        if assignment.get("resource_id") != entity_id:
            continue
        estimated = float(assignment.get("estimated_hours", 0.0) or 0.0)
        split = float(assignment.get("resource_split", 100.0) or 0.0) / 100.0
        hours += estimated * split
    return hours


def _task_working_days(project: Project, task: Task) -> List[date]:
    """The days a task's load is spread over, on its own calendar."""
    start = task.start_date
    end = task.end_date or start
    if not start or not end:
        return []
    calendar = project.calendar_for(task)
    return [
        day.date() if isinstance(day, datetime) else day
        for day in (start + timedelta(days=i)
                    for i in range((end - start).days + 1))
        if calendar.is_working_day(day)
    ]


def daily_assignment_load(entity_id: str, project: Project) -> Dict[date, float]:
    """
    An entity's assigned hours on each date.

    The same arithmetic the resource board's heatmap draws - effort spread
    evenly over each task's working days - kept here so the leveler works
    on the numbers the user sees. Duplicated rather than imported because
    views may not reach into views, and moving the board's copy would
    drag the whole panel's helpers with it.
    """
    load: Dict[date, float] = {}
    for task in project.tasks:
        if task.is_milestone:
            continue
        effort = _assignment_hours(task, entity_id)
        if effort <= 0:
            continue
        workdays = _task_working_days(project, task)
        if not workdays:
            continue
        per_day = effort / len(workdays)
        for day in workdays:
            load[day] = load.get(day, 0.0) + per_day
    return load


def _capacity_on(repo: ResourceRepository, entity_id: str,
                 resources_by_id: Dict[str, object], day: date) -> float:
    """
    The hours an entity can offer on a date.

    A resource answers its own weekday capacity, less days off; a team
    answers the sum of its members' capacity, each weighted by the
    membership ratio - the same accounting the team heatmap rows use.
    """
    resource = resources_by_id.get(entity_id)
    if resource is not None:
        if not resource.works_on(day):
            return 0.0
        return float(resource.daily_capacity_hours.get(
            DAYS[day.weekday()], 0.0))
    team = repo.teams.get(entity_id)
    if team is None:
        return 0.0
    return float(team.calculate_daily_capacity(
        list(resources_by_id.values())).get(DAYS[day.weekday()], 0.0))


def _overallocated(project: Project) -> Dict[str, Dict[date, float]]:
    """
    Every (entity, day) booked past capacity, and by how many hours.

    Only work-holding entities are scanned - resources and teams. Material
    and cost resources hold no hours, so they cannot be overallocated.
    """
    repo = project.resource_repository
    resources_by_id = repo.resources
    over: Dict[str, Dict[date, float]] = {}
    for entity_id in list(resources_by_id) + list(repo.teams):
        for day, hours in daily_assignment_load(entity_id, project).items():
            capacity = _capacity_on(repo, entity_id, resources_by_id, day)
            extra = hours - capacity
            if extra > 1e-6:
                over.setdefault(entity_id, {})[day] = extra
    return over


def _entity_name(repo: ResourceRepository, entity_id: str) -> str:
    """The name a scan result names, whichever pool the id lives in."""
    entity = (repo.resources.get(entity_id)
              or repo.teams.get(entity_id))
    return entity.name if entity is not None else entity_id


def _hard_locked(task: Task) -> Optional[str]:
    """The reason a task cannot be levelled, or None."""
    constraint = getattr(task, 'constraint_type', 'NA')
    if constraint in ('MSO', 'MFO'):
        return f"locked by a {constraint} constraint"
    return None


def _allowed_delay(project: Project, task: Task, free_room: int,
                   options: LevelingOptions) -> Tuple[int, Optional[str]]:
    """
    How many working days a task may slip, and what limited it.

    The float cap comes from the option in force; the deadline is a cap of
    its own, so a task is never pushed past a date somebody cares about -
    the blocker is named so the preview can say why.
    """
    cap = free_room
    blocker = None
    deadline = getattr(task, 'deadline', None)
    if options.respect_deadlines and deadline is not None and task.end_date:
        headroom = project.calendar.working_days_between(
            task.end_date, deadline) - 1
        if headroom < cap:
            cap = max(headroom, 0)
            blocker = "its deadline"
    return cap, blocker


def _delay_task(project: Project, task: Task, days: int) -> bool:
    """
    Shift a task later by working days on its own calendar.

    Both ends move together so the duration survives; the finish is the
    same working-day count out from the new start. Returns False when the
    move lands nowhere - a task calendar with no working day after the
    start cannot slip at all.
    """
    calendar = project.calendar_for(task)
    new_start = calendar.add_working_days(task.start_date, days + 1)
    if new_start <= task.start_date:
        return False
    span = calendar.working_days_between(task.start_date,
                                         task.end_date or task.start_date)
    task.start_date = new_start
    if task.end_date is not None:
        task.end_date = calendar.add_working_days(new_start, max(span, 1))
    return True


def _tasks_loading(project: Project, entity_id: str, day: date,
                   summary_ids: Set[str]) -> List[Task]:
    """The tasks whose assignments to the entity cover the given day."""
    found = []
    for task in project.tasks:
        if task.is_milestone or task.id in summary_ids:
            continue
        if _assignment_hours(task, entity_id) <= 0:
            continue
        if day in _task_working_days(project, task):
            found.append(task)
    return found


def level_resources(project: Project,
                    options: Optional[LevelingOptions] = None
                    ) -> LevelingPlan:
    """
    Delay tasks until no resource is booked past its capacity.

    PARAMETERS:
    -----------
    project : Project
        The plan to level - a scratch copy for a preview, the live plan
        for an apply. The function writes task dates directly.
    options : LevelingOptions
        See the dataclass; defaults are the safe set.

    RETURNS:
    --------
    LevelingPlan
        Every move the run made (including successors the reschedule
        dragged), the overloads it could not clear, and what it refused
        to touch.

    DEVELOPMENT NOTES:
    ------------------
    One pass handles one (resource, day): the lowest-priority,
    latest-starting, roomiest-float task on it is delayed just past the
    day - or as far as its cap allows - successors are rescheduled, and
    the loads are measured again. Repeating until nothing moves or the
    cap lands keeps the loop simple; each pass either clears a day or
    marks it unfixable, so it always terminates.
    """
    options = options or LevelingOptions()
    repo = project.resource_repository
    plan = LevelingPlan()

    # The "before" positions, so successors the reschedule drags are
    # reported beside the tasks the engine chose - a preview that only
    # listed its own picks would hide half of what Apply does.
    before = {task.id: (task.start_date, task.end_date)
              for task in project.tasks}
    plan.finish_before = max((task.end_date or task.start_date)
                             for task in project.tasks
                             if task.start_date is not None) \
        if project.tasks else None

    # (entity, day) pairs no candidate could clear, and tasks refused once
    # - either stops the loop revisiting them forever.
    dead_days: Set[Tuple[str, date]] = set()
    refused: Set[Tuple[str, str, date]] = set()
    skipped_notes: Set[str] = set()

    # Summary rows never move directly - levelling moves the work, and the
    # summaries roll up from it in the reschedule.
    summary_ids = project.get_summary_task_ids()

    over = _overallocated(project)
    plan.overallocations_found = sum(len(days) for days in over.values())

    for _pass in range(options.max_passes):
        over = _overallocated(project)
        pending = [(entity_id, day)
                   for entity_id, days in over.items()
                   for day in days
                   if (entity_id, day) not in dead_days]
        if not pending:
            break

        entity_id, day = min(pending, key=lambda pair: (pair[1], pair[0]))
        candidates = _tasks_loading(project, entity_id, day, summary_ids)
        analysis = project.schedule_analysis()  # recomputed post-move

        def rank(task: Task):
            found = analysis.get(task.id)
            free_room = (found.free_float if options.within_free_float
                         else found.total_float) if found else 0
            # Lower priority first, then the later start, then the more
            # room - Microsoft Project's Standard order, cut to the three
            # keys this model carries.
            return (priority_rank(task.priority),
                    -(task.start_date or datetime.min).toordinal(),
                    -free_room)

        moved = False
        for task in sorted(candidates, key=rank):
            if (task.id, entity_id, day) in refused:
                continue
            locked = _hard_locked(task)
            if locked is not None:
                note = f"{task.name}: skipped - {locked}"
                if note not in skipped_notes:
                    skipped_notes.add(note)
                    plan.skipped.append(note)
                refused.add((task.id, entity_id, day))
                continue

            found = analysis.get(task.id)
            room = (found.free_float if options.within_free_float
                    else found.total_float) if found else 0
            cap, _blocker = _allowed_delay(project, task,
                                           max(room, 0), options)

            # The delay that clears the day: the task must start on the
            # first of its working days after it.
            calendar = project.calendar_for(task)
            clear_to = calendar.add_working_days(day, 2)
            needed = calendar.working_days_between(
                task.start_date, clear_to) - 1
            if needed <= 0:
                needed = 1
            if cap < needed:
                # Cannot clear this day without breaking the cap; a
                # partial move still covers it, so it buys nothing.
                refused.add((task.id, entity_id, day))
                continue

            old_start = task.start_date
            if not _delay_task(project, task, needed):
                refused.add((task.id, entity_id, day))
                continue
            project.reschedule()
            logger.info("Levelling delayed %r by %s working day(s) off %s "
                        "for %s (cap was %s)",
                        task.name, needed, day.isoformat(),
                        _entity_name(repo, entity_id), cap)
            moved = True
            break

        if not moved:
            dead_days.add((entity_id, day))
    else:
        plan.gave_up = True
        logger.warning("Levelling gave up after %s passes; "
                       "the plan may contain a dependency cycle",
                       options.max_passes)

    # The moves: everything whose dates differ from before, whether the
    # engine picked it or a dragged successor - both are "what changed".
    for task in project.tasks:
        old_start, old_end = before.get(task.id, (None, None))
        if (task.start_date, task.end_date) == (old_start, old_end):
            continue
        delay = project.calendar.working_days_between(
            old_start, task.start_date) - 1 if old_start else 0
        plan.moves.append(LevelingMove(
            task_id=task.id,
            task_name=task.name,
            resource_name='',
            old_start=old_start,
            old_finish=old_end,
            new_start=task.start_date,
            new_finish=task.end_date,
            delay_days=max(delay, 0),
        ))

    # Whatever is still over capacity is the unresolved list - named with
    # the advice Project gives rather than left as a bare number.
    remaining = _overallocated(project)
    for entity_id, days in remaining.items():
        for day, extra in sorted(days.items()):
            plan.unresolved.append(LevelingIssue(
                resource_name=_entity_name(repo, entity_id),
                day=day,
                over_by=extra,
                detail="consider reassigning, or allow levelling "
                       "beyond float",
            ))

    plan.finish_after = max((task.end_date or task.start_date)
                            for task in project.tasks
                            if task.start_date is not None) \
        if project.tasks else None

    logger.info("Levelling: %s overloaded day(s), %s task(s) moved, "
                "%s unresolved, %s skipped%s",
                plan.overallocations_found, len(plan.moves),
                len(plan.unresolved), len(plan.skipped),
                "; gave up at the pass cap" if plan.gave_up else "")
    return plan


def preview(project: Project,
            options: Optional[LevelingOptions] = None) -> LevelingPlan:
    """
    What levelling would do, on a copy the caller can throw away.

    The plan's own deepcopy is deliberately not used - Project copies
    through __dict__ (the undo history relies on it), which leaves the
    analysis cache holding the *original's* signature. A fresh deepcopy is
    the honest scratch, and its cost is one leveling run's noise.
    """
    scratch = copy.deepcopy(project)
    return level_resources(scratch, options)
