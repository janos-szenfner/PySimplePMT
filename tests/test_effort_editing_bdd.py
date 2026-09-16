"""
pytest-bdd tests for the task editor's effort reconciliation (phase 3b).

Run with:
    python3 -m pytest tests/test_effort_editing_bdd.py -q

Converted from test_effort_editing.py - every case carried over.
"""
from datetime import datetime
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import (
    EFFORT_FIXED_DURATION,
    EFFORT_FIXED_UNITS,
    Project,
    Task,
)
from gantt_app.views.taskform import TaskFormDialog

pytestmark = [
    pytest.mark.effort_editing,
]

scenarios("features/effort_editing.feature")


def _task(**kwargs):
    kwargs.setdefault('id', 'T')
    kwargs.setdefault('name', 'A task')
    kwargs.setdefault('start_date', datetime(2026, 9, 9))
    return Task(**kwargs)


def _reconcile(project, old_task, duration, assignments,
               effort_type=EFFORT_FIXED_UNITS, effort_driven=True):
    """Call the dialog method with a stand-in that only carries the project."""
    stub = SimpleNamespace(project=project)
    return TaskFormDialog._reconcile_effort(
        stub, old_task, duration, assignments, effort_type, effort_driven)


def _assignment(resource_id, hours, split):
    return {'resource_id': resource_id, 'estimated_hours': hours,
            'resource_split': split}


# ------------------------------------------------------------------
# GIVEN
# ------------------------------------------------------------------

@given("a project on an eight-hour day", target_fixture="ctx")
def a_project_on_an_eight_hour_day():
    project = Project(name='P')
    project.hours_per_day = 8.0
    return SimpleNamespace(project=project)


@given(parsers.parse("a fixed-units task of {days:d} days with {res} at "
                     "{hours:f} hours and {split:f} percent"))
def a_fixed_units_task(ctx, days, res, hours, split):
    ctx.old = _task(duration=days, effort_type=EFFORT_FIXED_UNITS,
                    resource_assignments=[_assignment(res, hours, split)])


@given(parsers.parse("a task of {days:d} days with {res} at "
                     "{hours:f} hours and {split:f} percent"))
def a_task_with_assignment(ctx, days, res, hours, split):
    ctx.old = _task(duration=days,
                    resource_assignments=[_assignment(res, hours, split)])


@given(parsers.parse("a fixed-duration task of {days:d} days with {res} at "
                     "{hours:f} hours and {split:f} percent"))
def a_fixed_duration_task(ctx, days, res, hours, split):
    ctx.old = _task(duration=days, effort_type=EFFORT_FIXED_DURATION,
                    resource_assignments=[_assignment(res, hours, split)])


@given(parsers.parse("a plain task of {days:d} days"))
def a_plain_task(ctx, days):
    ctx.old = _task(duration=days)


def _resourced_task(effort_driven, days=10):
    """A Fixed Units task with one 100% resource, work = duration."""
    return _task(duration=days, effort_type=EFFORT_FIXED_UNITS,
                 effort_driven=effort_driven,
                 resource_assignments=[
                     _assignment('R1', days * 8.0, 100.0)])


@given(parsers.parse("an effort-driven fixed-units task of {days:d} days "
                     "with R1 at {hours:f} hours"))
def an_effort_driven_task(ctx, days, hours):
    ctx.old = _resourced_task(effort_driven=True, days=days)


@given(parsers.parse("a non-effort-driven fixed-units task of {days:d} days "
                     "with R1 at {hours:f} hours"))
def a_non_effort_driven_task(ctx, days, hours):
    ctx.old = _resourced_task(effort_driven=False, days=days)


@given(parsers.parse("an effort-driven task of {days:d} days shared by R1 "
                     "and R2 at {hours:f} hours each"))
def an_effort_driven_shared_task(ctx, days, hours):
    ctx.old = _task(duration=days, effort_type=EFFORT_FIXED_UNITS,
                    effort_driven=True,
                    resource_assignments=[
                        _assignment('R1', hours, 100.0),
                        _assignment('R2', hours, 100.0)])


# ------------------------------------------------------------------
# WHEN - the save
# ------------------------------------------------------------------

def _save(ctx, duration, assignments, effort_type=EFFORT_FIXED_UNITS,
          effort_driven=True):
    ctx.duration, ctx.out = _reconcile(
        ctx.project, ctx.old, duration, assignments,
        effort_type=effort_type, effort_driven=effort_driven)


@when(parsers.parse("the form is saved with duration {duration:d} and {res} "
                    "at {hours:f} hours and {split:f} percent"))
def saved_with_one_assignment(ctx, duration, res, hours, split):
    _save(ctx, duration, [_assignment(res, hours, split)])


@when(parsers.parse("the form is saved as fixed-duration with duration "
                    "{duration:d} and {res} at {hours:f} hours and "
                    "{split:f} percent"))
def saved_fixed_duration(ctx, duration, res, hours, split):
    _save(ctx, duration, [_assignment(res, hours, split)],
          effort_type=EFFORT_FIXED_DURATION)


@when(parsers.parse("the form is saved with duration {duration:d} and no "
                    "assignments"))
def saved_with_no_assignments(ctx, duration):
    _save(ctx, duration, [])


@when(parsers.parse('the form is saved effort-driven with duration '
                    '{duration:d} and a second resource "{res}" seeded '
                    'empty'))
def saved_effort_driven_second_resource(ctx, duration, res):
    _save(ctx, duration,
          [_assignment('R1', 80.0, 100.0),
           _assignment(res, 0.0, 100.0)])   # seeded by the Assign tab


@when(parsers.parse('the form is saved not effort-driven with duration '
                    '{duration:d} and a second resource "{res}" seeded '
                    'empty'))
def saved_not_effort_driven_second_resource(ctx, duration, res):
    _save(ctx, duration,
          [_assignment('R1', 80.0, 100.0),
           _assignment(res, 0.0, 100.0)],
          effort_driven=False)


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@then(parsers.parse("the saved duration is {expected:d}"))
def the_saved_duration_is(ctx, expected):
    assert ctx.duration == expected


@then(parsers.parse('the saved assignment "{res}" carries {hours:f} hours'))
def the_saved_assignment_carries_hours(ctx, res, hours):
    found = [a for a in ctx.out if a['resource_id'] == res]
    assert found[0]['estimated_hours'] == hours


@then(parsers.parse('the saved assignment "{res}" carries {split:f} '
                    'percent'))
def the_saved_assignment_carries_percent(ctx, res, split):
    found = [a for a in ctx.out if a['resource_id'] == res]
    assert found[0]['resource_split'] == split


@then("no assignments come back")
def no_assignments_come_back(ctx):
    assert ctx.out == []


@then(parsers.parse("the saved assignments total {hours:f} hours"))
def the_saved_assignments_total(ctx, hours):
    assert sum(a['estimated_hours'] for a in ctx.out) == hours
