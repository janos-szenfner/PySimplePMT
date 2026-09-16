"""
pytest-bdd tests for the completion a parent takes from the work
under it.

Run with:
    python3 -m pytest tests/test_completion_bdd.py -q

Model-level, no display needed. Converted from test_completion.py -
every case carried over.
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Project, Task, rolled_up_progress

pytestmark = [
    pytest.mark.completion,
]

scenarios("features/completion.feature")


def _task(task_id, task_type, progress=0, days=1, parent=None,
          start=datetime(2026, 1, 1)):
    """A task of a given type, length and progress."""
    return Task(
        id=task_id, name=task_id, task_type=task_type, progress=progress,
        start_date=start, end_date=start + timedelta(days=days - 1),
        parent_task_id=parent,
    )


def _progress_of(ctx, task_id):
    """The progress of one task after a reschedule."""
    return ctx.project.get_task_by_id(task_id).progress


# ------------------------------------------------------------------
# GIVEN
# ------------------------------------------------------------------

@given(parsers.parse('a "{task_type}" parent'), target_fixture="ctx")
def a_parent(task_type):
    return SimpleNamespace(parent=_task("X", task_type))


@given("a phase over a sub-tasked task and a part-done task",
       target_fixture="ctx")
def a_phase_over_tasks():
    """A phase over two tasks, one of them over sub-tasks."""
    project = Project(name="Test Project")
    base = datetime(2026, 1, 1)

    project.add_task(_task("P", "Phase", start=base))

    # A task of ten days holding two sub-tasks
    project.add_task(_task("T1", "Task", parent="P", days=10,
                           start=base))
    project.add_task(_task("S1", "Subtask", parent="T1", start=base))
    project.add_task(_task("S2", "Subtask", parent="T1", start=base))

    # A task of ten days with no sub-tasks, part done
    project.add_task(_task("T2", "Task", parent="P", days=10,
                           progress=40, start=base))
    return SimpleNamespace(project=project)


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------

@when(parsers.parse('it holds two "{child_type}" children at {first:d} '
                    'and {second:d} percent'))
def two_children_at(ctx, child_type, first, second):
    ctx.children = [_task("C1", child_type, progress=first),
                    _task("C2", child_type, progress=second)]


@when(parsers.parse('it holds two "{child_type}" children of '
                    '{days1:d} and {days2:d} days at {first:d} and '
                    '{second:d} percent'))
def two_children_of_days_at(ctx, child_type, days1, days2, first, second):
    ctx.children = [_task("C1", child_type, progress=first, days=days1),
                    _task("C2", child_type, progress=second, days=days2)]


@when(parsers.parse('it holds three "{child_type}" children at '
                    '{first:d}, {second:d} and {third:d} percent'))
def three_children_at(ctx, child_type, first, second, third):
    ctx.children = [_task("C1", child_type, progress=first),
                    _task("C2", child_type, progress=second),
                    _task("C3", child_type, progress=third)]


@when(parsers.parse('it holds a "{child_type}" child set past its guard '
                    'to {progress:d} percent'))
def a_child_set_past_its_guard(ctx, child_type, progress):
    child = _task("C1", child_type, days=1)
    child.progress = progress
    ctx.children = [child]


@when(parsers.parse('subtask "{task_id}" is ticked and the plan is '
                    'settled'))
def subtask_is_ticked_and_settled(ctx, task_id):
    ctx.project.get_task_by_id(task_id).progress = 100
    ctx.project.reschedule()


@when(parsers.parse('subtask "{task_id}" is unticked and the plan is '
                    'settled'))
def subtask_is_unticked_and_settled(ctx, task_id):
    ctx.project.get_task_by_id(task_id).progress = 0
    ctx.project.reschedule()


@when("the plan is settled")
def the_plan_is_settled(ctx):
    ctx.project.reschedule()


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@then(parsers.parse('a "{task_type}" at {progress:d} percent is '
                    'completed'))
def at_percent_is_completed(task_type, progress):
    assert _task("S", task_type, progress=progress).is_completed


@then(parsers.parse('a "{task_type}" at {progress:d} percent is not '
                    'completed'))
def at_percent_is_not_completed(task_type, progress):
    assert not _task("S", task_type, progress=progress).is_completed


@then(parsers.parse("the roll-up is {expected:d}"))
def the_rollup_is(ctx, expected):
    assert rolled_up_progress(ctx.parent, ctx.children) == expected


@then(parsers.parse('an empty "{first_type}" rolls up {first:d} and an '
                    'empty "{second_type}" rolls up {second:d}'))
def empty_containers_roll_up_nothing(first_type, first, second_type,
                                     second):
    assert rolled_up_progress(_task("P", first_type), []) == first
    assert rolled_up_progress(_task("D", second_type), []) == second


@then(parsers.parse('"{first_id}" reads {first:d}, "{second_id}" reads '
                    '{second:d} and "{third_id}" reads {third:d}'))
def three_tasks_read(ctx, first_id, first, second_id, second, third_id,
                     third):
    assert _progress_of(ctx, first_id) == first
    assert _progress_of(ctx, second_id) == second
    assert _progress_of(ctx, third_id) == third


@then(parsers.parse('"{first_id}" reads {first:d} and "{second_id}" '
                    'reads {second:d}'))
def two_tasks_read(ctx, first_id, first, second_id, second):
    assert _progress_of(ctx, first_id) == first
    assert _progress_of(ctx, second_id) == second


@then(parsers.re(r'"(?P<task_id>[^"]+)" reads (?P<expected>\d+)$'))
def one_task_reads(ctx, task_id, expected):
    assert _progress_of(ctx, task_id) == int(expected)
