"""
The Task Type / Effort-Driven scheduling maths (Task_Type_FRS §8).

WHY THIS MODULE EXISTS:
======================
The Advanced tab's **Task Type** - Fixed Units, Fixed Work or Fixed Duration -
and its **Effort-Driven** toggle define a relationship between three numbers:

    W (work, hours) = D_hours (duration in hours) × U (total assignment units)

Which of the three is held fixed when another changes is what the task type
decides; whether adding or removing a resource preserves the work is what
Effort-Driven decides. The rules are fiddly and full of edge cases, so they
live here as **pure functions over a plain state object** rather than tangled
into the Task model, the scheduler and the task editor. That keeps them
exhaustively testable without a window, a project or a resource pool, and lets
the wiring in later phases stay thin.

Nothing in here reads or writes a Task, a Project or the schedule. A caller
builds an :class:`EffortState` from a task, runs an operation, and copies the
results back. Units are a fraction of one full-time equivalent - 1.0 is 100%
of one resource - and work and duration are both carried in hours; days are a
display unit, converted with ``hours_per_day``.

This module is deliberately not imported by the scheduler yet: Phase 1 lands
the engine and its tests; later phases wire it to edits and assignments.
"""

from dataclasses import dataclass, field
from typing import List, Optional

from gantt_app.models import (
    DEFAULT_HOURS_PER_DAY,
    EFFORT_FIXED_DURATION,
    EFFORT_FIXED_UNITS,
    EFFORT_FIXED_WORK,
    HARD_CONSTRAINTS,
)

#: A single resource's share of a task: which resource, and how much of one
#: full-time equivalent it is committing (1.0 = 100%).
@dataclass
class Assignment:
    resource_id: str
    units: float = 1.0


@dataclass
class EffortResult:
    """
    What an operation did, in words a caller can log or show.

    ``error`` set means the operation was refused and the state left alone;
    ``warnings`` are things the planner is allowed to do but should see (a
    resource over 100% on the task, say); ``message`` narrates the normal
    outcome for the audit log.
    """
    message: str = ""
    warnings: List[str] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass
class EffortState:
    """
    The three numbers and the settings that bind them, for one task.

    A caller lifts this off a Task (its effort_type, effort_driven, the
    duration in hours, the total work in hours, and one Assignment per
    resource), runs an operation, and writes the changed numbers back.
    """
    effort_type: str = EFFORT_FIXED_UNITS
    effort_driven: bool = True
    duration_hours: float = 0.0
    work: float = 0.0
    assignments: List[Assignment] = field(default_factory=list)
    hours_per_day: float = DEFAULT_HOURS_PER_DAY
    is_milestone: bool = False
    manually_scheduled: bool = False
    constraint_type: str = 'NA'

    @property
    def total_units(self) -> float:
        """U: the summed allocation across every assignment."""
        return sum(a.units for a in self.assignments)

    @property
    def duration_days(self) -> float:
        """The duration in display days, from its hours."""
        if self.hours_per_day <= 0:
            return 0.0
        return self.duration_hours / self.hours_per_day


# ---------------------------------------------------------------------------
# Conversions
# ---------------------------------------------------------------------------

def days_to_hours(days: float, hours_per_day: float = DEFAULT_HOURS_PER_DAY) -> float:
    """A duration in display days as the hours the maths works in."""
    return days * hours_per_day


def hours_to_days(hours: float, hours_per_day: float = DEFAULT_HOURS_PER_DAY) -> float:
    """A duration in hours back to display days."""
    if hours_per_day <= 0:
        return 0.0
    return hours / hours_per_day


# ---------------------------------------------------------------------------
# Gating - when the effort maths applies at all
# ---------------------------------------------------------------------------

def logic_applies(state: EffortState) -> bool:
    """
    Whether Task Type and Effort-Driven govern this task.

    They do not for a milestone (no duration or work), nor for a manually
    scheduled task (the planner owns the dates); Task_Type_FRS §4.4, §5.6.
    Summary rows are excluded by the caller, which knows the hierarchy.
    """
    return not state.is_milestone and not state.manually_scheduled


def effort_driven_effective(state: EffortState) -> bool:
    """
    Whether work is preserved on a resource change for this task.

    Fixed Work is effort-driven by definition, whatever the flag says
    (Task_Type_FRS §6.1); otherwise the stored toggle stands.
    """
    if state.effort_type == EFFORT_FIXED_WORK:
        return True
    return state.effort_driven


# ---------------------------------------------------------------------------
# Validation (Task_Type_FRS §5.1, §8.2)
# ---------------------------------------------------------------------------

def validate(state: EffortState) -> EffortResult:
    """
    Whether the numbers may be saved, with the first reason they may not.

    Encodes the universal rule that any task with work must have a resource
    to do it (W = D × U, so U cannot be zero while W is positive), plus the
    Fixed Work and Fixed Duration minimums.
    """
    if state.duration_hours < 0 or state.work < 0:
        return EffortResult(error="Duration, work, and resources must be "
                                  "non-negative.")
    if any(a.units < 0 for a in state.assignments):
        return EffortResult(error="Duration, work, and resources must be "
                                  "non-negative.")

    if state.effort_type == EFFORT_FIXED_WORK:
        if state.work <= 0:
            return EffortResult(
                error="Fixed Work tasks require a non-zero workload.")
        if state.total_units <= 0:
            return EffortResult(
                error="Fixed Work tasks require at least one resource.")
    elif state.effort_type == EFFORT_FIXED_DURATION:
        if state.duration_hours <= 0:
            return EffortResult(
                error="Fixed Duration tasks require a non-zero duration.")

    if state.work > 0 and state.total_units <= 0:
        return EffortResult(
            error="Tasks with work > 0 require at least one resource "
                  "assignment.")

    return EffortResult(message="Valid.")


def _high_assignment_warnings(state: EffortState) -> List[str]:
    """A warning per assignment whose units exceed one full FTE."""
    warnings = []
    for assignment in state.assignments:
        if assignment.units > 1.0:
            warnings.append(
                f"{assignment.resource_id or 'A resource'} is at "
                f"{assignment.units * 100:g}% on this task.")
    return warnings


# ---------------------------------------------------------------------------
# Recalculation from the current task type (Task_Type_FRS §8.4)
# ---------------------------------------------------------------------------

def recalculate(state: EffortState) -> EffortResult:
    """
    Bring the three numbers back into W = D_hours × U for the task type.

    Fixed Units and Fixed Work solve for duration from work and units; Fixed
    Duration solves for work from duration and units. Leaves the numbers
    alone when there is nothing to divide by.
    """
    units = state.total_units
    if state.effort_type in (EFFORT_FIXED_UNITS, EFFORT_FIXED_WORK):
        if units > 0:
            state.duration_hours = state.work / units
    elif state.effort_type == EFFORT_FIXED_DURATION:
        state.work = state.duration_hours * units
    return EffortResult(message="Recalculated.")


# ---------------------------------------------------------------------------
# Direct edits - governed by task type only (Task_Type_FRS §4.3, §8.3)
# ---------------------------------------------------------------------------

def edit_duration(state: EffortState, new_duration_hours: float) -> EffortResult:
    """A direct edit to duration. Refused for Fixed Duration (locked)."""
    if new_duration_hours < 0:
        return EffortResult(error="Duration must be a non-negative value.")

    if state.effort_type == EFFORT_FIXED_DURATION:
        return EffortResult(error="Duration is locked for Fixed Duration "
                                  "tasks.")

    if state.effort_type == EFFORT_FIXED_WORK:
        if new_duration_hours <= 0:
            return EffortResult(error="Fixed Work tasks require a non-zero "
                                      "duration.")
        state.duration_hours = new_duration_hours
        return _redistribute_units_for_work(state, "Duration updated. Units "
                                                    "recalculated.")

    # Fixed Units: work follows duration at the held units.
    state.duration_hours = new_duration_hours
    state.work = new_duration_hours * state.total_units
    return EffortResult(message="Duration updated. Work recalculated.")


def edit_work(state: EffortState, new_work: float) -> EffortResult:
    """A direct edit to work. Refused for Fixed Work (locked)."""
    if new_work < 0:
        return EffortResult(error="Work must be a non-negative value.")

    if state.effort_type == EFFORT_FIXED_WORK:
        return EffortResult(error="Work is locked for Fixed Work tasks.")

    if state.effort_type == EFFORT_FIXED_DURATION:
        state.work = new_work
        return _redistribute_units_for_work(state, "Work updated. Units "
                                                   "recalculated.")

    # Fixed Units: duration follows work at the held units.
    state.work = new_work
    if state.total_units > 0:
        state.duration_hours = new_work / state.total_units
    return EffortResult(message="Work updated. Duration recalculated.")


def edit_units(state: EffortState, index: int, new_units: float) -> EffortResult:
    """
    A direct edit to one assignment's units.

    Fixed Units holds units by definition, so an edit there is really a new
    fixed value and duration follows; Fixed Work keeps work and moves
    duration; Fixed Duration keeps duration and moves work.
    """
    if new_units < 0:
        return EffortResult(error="Resource units must be a non-negative "
                                  "value.")
    if not 0 <= index < len(state.assignments):
        return EffortResult(error="No such assignment.")

    state.assignments[index].units = new_units
    units = state.total_units

    if state.effort_type == EFFORT_FIXED_WORK:
        if units <= 0:
            return EffortResult(error="Fixed Work tasks require at least one "
                                      "resource.")
        state.duration_hours = state.work / units
        return EffortResult(message="Units updated. Duration recalculated.",
                            warnings=_high_assignment_warnings(state))

    if state.effort_type == EFFORT_FIXED_DURATION:
        state.work = state.duration_hours * units
        return EffortResult(message="Units updated. Work recalculated.",
                            warnings=_high_assignment_warnings(state))

    # Fixed Units: the edited units are the new held value; work follows.
    state.work = state.duration_hours * units
    return EffortResult(message="Units updated. Work recalculated.",
                        warnings=_high_assignment_warnings(state))


def _redistribute_units_for_work(state: EffortState, message: str) -> EffortResult:
    """
    Split the units W / D_hours evenly across assignments, warning on > 100%.

    Used where work is fixed and duration has just moved (Fixed Work manual
    duration) or duration is fixed and work has just moved (Fixed Duration
    work edit): either way the total units are pinned to W / D_hours and the
    even split matches the FRS pseudocode.
    """
    count = len(state.assignments)
    if count == 0 or state.duration_hours <= 0:
        return EffortResult(message=message)
    per = (state.work / state.duration_hours) / count
    for assignment in state.assignments:
        assignment.units = per
    return EffortResult(message=message,
                        warnings=_high_assignment_warnings(state))


# ---------------------------------------------------------------------------
# Resource add / remove - governed by Effort-Driven (Task_Type_FRS §8.3, §8.4)
# ---------------------------------------------------------------------------

def add_resource(state: EffortState, resource_id: str,
                 units: float = 1.0) -> EffortResult:
    """
    Add an assignment, letting Effort-Driven and the task type decide what
    moves: work is preserved (duration shortens, or Fixed Duration units
    redistribute) when effort-driven, else work grows and duration holds.
    """
    if units < 0:
        return EffortResult(error="Resource units must be a non-negative "
                                  "value.")
    ed = effort_driven_effective(state)

    if (state.effort_type == EFFORT_FIXED_WORK
            or (state.effort_type == EFFORT_FIXED_UNITS and ed)):
        state.assignments.append(Assignment(resource_id, units))
        total = state.total_units
        if total <= 0:
            return EffortResult(error="A resource with units is needed to do "
                                      "the work.")
        state.duration_hours = state.work / total
        return EffortResult(message="Resource added. Work preserved. Duration "
                                    "recalculated.",
                            warnings=_high_assignment_warnings(state))

    if state.effort_type == EFFORT_FIXED_DURATION and ed:
        state.assignments.append(Assignment(resource_id, units))
        total_new = state.total_units
        if total_new <= 0 or state.duration_hours <= 0:
            return EffortResult(message="Resource added.")
        target_total = state.work / state.duration_hours
        scale = target_total / total_new
        for assignment in state.assignments:
            assignment.units *= scale
        return EffortResult(message="Resource added. Work preserved. Units "
                                    "redistributed.",
                            warnings=_high_assignment_warnings(state))

    # Effort-Driven OFF: duration holds, work grows by the new resource.
    state.assignments.append(Assignment(resource_id, units))
    state.work = state.duration_hours * state.total_units
    return EffortResult(message="Resource added. Duration preserved. Work "
                                "recalculated.",
                        warnings=_high_assignment_warnings(state))


def remove_resource(state: EffortState, index: int) -> EffortResult:
    """
    Remove an assignment - the inverse of :func:`add_resource`.

    Effort-driven removal preserves work (so duration extends, or Fixed
    Duration units are shared out among those left); otherwise work shrinks
    and duration holds. Removing the last resource of an effort-driven,
    work-preserving task is refused: it would demand an infinite duration.
    """
    if not 0 <= index < len(state.assignments):
        return EffortResult(error="No such assignment.")
    ed = effort_driven_effective(state)
    del state.assignments[index]

    if (state.effort_type == EFFORT_FIXED_WORK
            or (state.effort_type == EFFORT_FIXED_UNITS and ed)):
        total = state.total_units
        if total <= 0:
            return EffortResult(error="Removing this resource would require "
                                      "infinite duration. Add more resources "
                                      "or reduce work.")
        state.duration_hours = state.work / total
        return EffortResult(message="Resource removed. Work preserved. "
                                    "Duration recalculated.",
                            warnings=_high_assignment_warnings(state))

    if state.effort_type == EFFORT_FIXED_DURATION and ed:
        total = state.total_units
        if total > 0 and state.duration_hours > 0:
            target_total = state.work / state.duration_hours
            scale = target_total / total
            for assignment in state.assignments:
                assignment.units *= scale
        return EffortResult(message="Resource removed. Work preserved. Units "
                                    "redistributed.",
                            warnings=_high_assignment_warnings(state))

    # Effort-Driven OFF: duration holds, work shrinks with the resource gone.
    state.work = state.duration_hours * state.total_units
    return EffortResult(message="Resource removed. Duration preserved. Work "
                                "recalculated.",
                        warnings=_high_assignment_warnings(state))


# ---------------------------------------------------------------------------
# Task type and Effort-Driven changes (Task_Type_FRS §8.4)
# ---------------------------------------------------------------------------

def change_effort_type(state: EffortState, new_type: str) -> EffortResult:
    """
    Switch the task type, applying its entry rules and recalculating.

    Fixed Work locks Effort-Driven on and needs work and a resource; the
    others leave the toggle to the planner. A hard constraint in force is
    reported, because it will override the type when the schedule is worked
    out (Task_Type_FRS §6.2).
    """
    if new_type not in (EFFORT_FIXED_UNITS, EFFORT_FIXED_WORK,
                        EFFORT_FIXED_DURATION):
        return EffortResult(error="Task Type is required. Select Fixed Units, "
                                  "Fixed Work, or Fixed Duration.")

    if new_type == EFFORT_FIXED_WORK:
        if state.work <= 0:
            return EffortResult(error="Fixed Work tasks require a non-zero "
                                      "workload.")
        if state.total_units <= 0:
            return EffortResult(error="Fixed Work tasks require at least one "
                                      "resource.")
        state.effort_driven = True
    elif new_type == EFFORT_FIXED_DURATION:
        if state.duration_hours <= 0:
            return EffortResult(error="Fixed Duration tasks require a non-zero "
                                      "duration.")
    elif new_type == EFFORT_FIXED_UNITS:
        if state.work > 0 and state.total_units <= 0:
            return EffortResult(error="Tasks with work > 0 require at least "
                                      "one resource.")

    state.effort_type = new_type
    recalculate(state)

    if state.constraint_type in HARD_CONSTRAINTS:
        return EffortResult(
            message=f"Task Type set to {new_type}.",
            warnings=[f"Constraint '{state.constraint_type}' overrides Task "
                      f"Type logic."])
    return EffortResult(message=f"Task Type set to {new_type}.")


#: The three numbers the maths binds, and which one each task type holds.
_VARS = ('duration', 'work', 'units')
_FIXED_BY_TYPE = {
    EFFORT_FIXED_UNITS: 'units',
    EFFORT_FIXED_WORK: 'work',
    EFFORT_FIXED_DURATION: 'duration',
}

#: How each variable reads in a message to the planner.
_VAR_LABELS = {'duration': 'Duration', 'work': 'Work',
               'units': 'Units / Resources'}


def var_label(var: str) -> str:
    """A variable name as it should read in a prompt."""
    return _VAR_LABELS.get(var, var)


@dataclass
class EditConflict:
    """
    A Save that changed both of a task type's adjustable numbers.

    The task type fixes one of duration, work and units; the other two are
    adjustable. Changing both in one Save is ambiguous - which did the
    planner mean to keep? - so the caller must ask and re-run the reconcile
    with the chosen ``preserve``.
    """
    effort_type: str
    fixed: str
    options: tuple  # the two adjustable variables, both changed

    def prompt(self) -> str:
        """The question to put to the planner."""
        a, b = (var_label(v) for v in self.options)
        return (f"You changed both {a} and {b}, but this task is "
                f"{self.effort_type}. Which should be kept? The other will be "
                f"recalculated.")


def classify_changes(old: EffortState, new: EffortState,
                     tol: float = 1e-9) -> dict:
    """Which of duration, work and total units differ between two states."""
    return {
        'duration': abs(old.duration_hours - new.duration_hours) > tol,
        'work': abs(old.work - new.work) > tol,
        'units': abs(old.total_units - new.total_units) > tol,
    }


def _scale_units_to_total(state: EffortState, new_total: float) -> None:
    """Move the assignments' units so they sum to a new total."""
    if not state.assignments:
        return
    old_total = state.total_units
    if old_total > 0:
        factor = new_total / old_total
        for assignment in state.assignments:
            assignment.units *= factor
    else:
        share = new_total / len(state.assignments)
        for assignment in state.assignments:
            assignment.units = share


def _recompute(state: EffortState, fixed: str, keep: Optional[str]) -> None:
    """
    Solve for the one variable that is neither fixed nor preserved.

    ``keep`` is the adjustable variable to hold (the planner's choice, or the
    single one they changed); None means only the fixed variable moved, and
    the canonical per-type rule decides which adjustable variable follows.
    """
    if fixed == 'units':                       # Fixed Units: hold U
        if keep == 'work':
            if state.total_units > 0:
                state.duration_hours = state.work / state.total_units
        else:                                  # keep duration, or units-only
            state.work = state.duration_hours * state.total_units
    elif fixed == 'work':                      # Fixed Work: hold W
        if keep == 'units':
            if state.total_units > 0:
                state.duration_hours = state.work / state.total_units
        else:                                  # keep duration
            if state.duration_hours > 0:
                _scale_units_to_total(state, state.work / state.duration_hours)
    else:                                      # Fixed Duration: hold D
        if keep == 'units':
            state.work = state.duration_hours * state.total_units
        else:                                  # keep work, or units-only
            if state.duration_hours > 0:
                _scale_units_to_total(state, state.work / state.duration_hours)


def reconcile(old: EffortState, new: EffortState,
              preserve: Optional[str] = None):
    """
    Bring a just-edited task back into W = D_hours × U for its task type.

    Returns ``(EffortResult, conflict)``. ``conflict`` is an EditConflict
    when both adjustable variables changed and no ``preserve`` was given -
    the caller asks the planner and calls again with their choice - and None
    otherwise. The effort maths is gated: a task with no assignment carrying
    real units (Task_Type_FRS §8.3, U_total = Σ of units > 0), or one that is
    a milestone / summary / manually scheduled, is left exactly as edited.
    """
    if not logic_applies(new) or new.total_units <= 0:
        return EffortResult(message="No effort recalculation for this task."), \
            None

    fixed = _FIXED_BY_TYPE[new.effort_type]
    adjustable = [v for v in _VARS if v != fixed]
    changed = classify_changes(old, new)
    changed_adjustable = [v for v in adjustable if changed[v]]

    if len(changed_adjustable) == 2 and preserve not in adjustable:
        return None, EditConflict(new.effort_type, fixed, tuple(adjustable))

    if preserve in adjustable:
        keep = preserve
    elif len(changed_adjustable) == 1:
        keep = changed_adjustable[0]
    else:
        keep = None

    _recompute(new, fixed, keep)
    return (EffortResult(message="Recalculated.",
                         warnings=_high_assignment_warnings(new)),
            None)


def set_effort_driven(state: EffortState, on: bool) -> EffortResult:
    """
    Toggle Effort-Driven, refusing it where it is not the planner's to set.

    Fixed Work is always effort-driven; a milestone or manually scheduled
    task has no effort logic to drive.
    """
    if state.effort_type == EFFORT_FIXED_WORK:
        return EffortResult(error="Effort-Driven is always ON for Fixed Work "
                                  "tasks.")
    if not logic_applies(state):
        return EffortResult(error="Effort-Driven is disabled for this task.")
    state.effort_driven = on
    return EffortResult(message=f"Effort-Driven {'on' if on else 'off'}.")


# ---------------------------------------------------------------------------
# The bridge between a Task and an EffortState
# ---------------------------------------------------------------------------
#
# A Task keeps duration in whole days and a resource's effort in its
# assignment dict (estimated_hours, resource_split), with no single "work" or
# "units" field. The engine works in hours and fractional FTE units, so these
# two functions lift a Task into an EffortState and write a reconciled state
# back. Duration is day-granular in the app, so it rounds on the way back -
# the finest this application schedules to - while work stays exact in hours.

def _assignment_units(assignment: dict) -> float:
    """A resource assignment's units (FTE fraction) from its saved split."""
    try:
        return float(assignment.get('resource_split', 100.0) or 0.0) / 100.0
    except (TypeError, ValueError):
        return 0.0


def _assignment_hours(assignment: dict) -> float:
    """A resource assignment's estimated work in hours."""
    try:
        return float(assignment.get('estimated_hours', 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def state_from_task(task, hours_per_day: float = DEFAULT_HOURS_PER_DAY) -> EffortState:
    """
    Build an EffortState from a Task, reading its day duration in hours.

    Work is the sum of the assignments' estimated hours; units are the sum of
    their splits as FTE fractions. A task with no assignments comes back with
    zero units, which the gate in :func:`reconcile` treats as "no effort
    logic", so nothing about it is touched.
    """
    assignments = [Assignment(a.get('resource_id', ''), _assignment_units(a))
                   for a in task.resource_assignments]
    work = sum(_assignment_hours(a) for a in task.resource_assignments)
    duration_days = task.duration or 0
    return EffortState(
        effort_type=task.effort_type,
        effort_driven=task.effort_driven,
        duration_hours=duration_days * hours_per_day,
        work=work,
        assignments=assignments,
        hours_per_day=hours_per_day,
        is_milestone=task.effective_milestone,
        manually_scheduled=getattr(task, 'manually_scheduled', False),
        constraint_type=task.constraint_type,
    )


def write_state_to_task(state: EffortState, task,
                        hours_per_day: float = DEFAULT_HOURS_PER_DAY) -> None:
    """
    Write a reconciled state's numbers back onto a Task.

    Duration rounds to whole days (at least one for any positive duration),
    the granularity the app schedules to. Each assignment keeps its own share
    of the work: its split follows its units, and its hours are that share of
    the duration, so the per-resource hours always sum to the total work.
    Assignments are matched to the task's by position, the order they were
    read in.
    """
    if state.duration_hours > 0:
        task.duration = max(1, round(state.duration_hours / hours_per_day))

    for saved, computed in zip(task.resource_assignments, state.assignments):
        saved['resource_split'] = computed.units * 100.0
        saved['estimated_hours'] = state.duration_hours * computed.units
