"""
pytest-bdd tests for Project.reschedule_uncompleted_work (issue #89).

Run with:
    python3 -m pytest tests/test_update_project_bdd.py -q

The status date is only a marker; this is the action that catches the
plan up to it, the way Microsoft Project's Update Project window does.
Only its 'Reschedule uncompleted work' half exists - marking work
complete is Mark on Track's job - and it runs over the whole plan. No
display is needed - nothing here builds a widget.
"""
from datetime import datetime
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Dependency, Project, Task

pytestmark = [
    pytest.mark.update_project,
]

scenarios("features/update_project.feature")


def _day(text):
    """Feature dates are ISO strings; the model takes datetimes."""
    return datetime.strptime(text, "%Y-%m-%d")


# ------------------------------------------------------------------
# GIVEN - the plan and its rows
# ------------------------------------------------------------------

@given("a plan", target_fixture="ctx")
def a_plan():
    return SimpleNamespace(project=Project(name="Plan"),
                           tasks={}, moved=None, counter=0)


def _add(ctx, task):
    ctx.project.add_task(task)
    ctx.tasks[task.name] = task
    return task


@given(parsers.parse('a task "{name}" running "{start}" to "{end}"'))
def a_task(ctx, name, start, end):
    ctx.counter += 1
    _add(ctx, Task(id=f"T{ctx.counter}", name=name, task_type="Task",
                   start_date=_day(start), end_date=_day(end)))


@given(parsers.parse('a task "{name}" running "{start}" to "{end}" '
                     'at {progress:d}%'))
def a_task_at_progress(ctx, name, start, end, progress):
    ctx.counter += 1
    _add(ctx, Task(id=f"T{ctx.counter}", name=name, task_type="Task",
                   start_date=_day(start), end_date=_day(end),
                   progress=progress))


@given(parsers.parse('an inactive task "{name}" running "{start}" '
                     'to "{end}"'))
def an_inactive_task(ctx, name, start, end):
    ctx.counter += 1
    _add(ctx, Task(id=f"T{ctx.counter}", name=name, task_type="Task",
                   start_date=_day(start), end_date=_day(end),
                   status='Inactive'))


@given(parsers.parse('a task "{name}" running "{start}" to "{end}" '
                     'must start on "{date}"'))
def a_pinned_task(ctx, name, start, end, date):
    ctx.counter += 1
    _add(ctx, Task(id=f"T{ctx.counter}", name=name, task_type="Task",
                   start_date=_day(start), end_date=_day(end),
                   constraint_type='MSO', constraint_date=_day(date)))


@given(parsers.parse('a task "{name}" running "{start}" to "{end}" '
                     'inside "{parent}"'))
def a_task_inside(ctx, name, start, end, parent):
    ctx.counter += 1
    _add(ctx, Task(id=f"T{ctx.counter}", name=name, task_type="Task",
                   start_date=_day(start), end_date=_day(end),
                   parent_task_id=ctx.tasks[parent].id))


@given(parsers.parse('a task "{name}" running "{start}" to "{end}" '
                     'after "{predecessor}"'))
def a_task_after(ctx, name, start, end, predecessor):
    ctx.counter += 1
    _add(ctx, Task(id=f"T{ctx.counter}", name=name, task_type="Task",
                   start_date=_day(start), end_date=_day(end),
                   dependencies=[Dependency(
                       task_id=ctx.tasks[predecessor].id)]))


@given(parsers.parse('a milestone "{name}" on "{date}"'))
def a_milestone(ctx, name, date):
    ctx.counter += 1
    _add(ctx, Task.create_milestone(name, _day(date),
                                    task_id=f"T{ctx.counter}"))


@given(parsers.parse('a phase "{name}" running "{start}" to "{end}"'))
def a_phase(ctx, name, start, end):
    ctx.counter += 1
    _add(ctx, Task.create_phase(name, _day(start), _day(end),
                                task_id=f"T{ctx.counter}"))


# ------------------------------------------------------------------
# WHEN - the reschedule
# ------------------------------------------------------------------

@when(parsers.parse('uncompleted work is rescheduled behind "{date}"'))
def reschedule_behind(ctx, date):
    ctx.moved = ctx.project.reschedule_uncompleted_work(_day(date))


# ------------------------------------------------------------------
# THEN - where the rows landed
# ------------------------------------------------------------------

@then(parsers.parse('the moved count is {count:d}'))
def the_moved_count_is(ctx, count):
    assert ctx.moved == count


@then(parsers.parse('the task "{name}" starts on "{date}"'))
def the_task_starts_on(ctx, name, date):
    assert ctx.tasks[name].start_date.date() == _day(date).date()


@then(parsers.parse('the task "{name}" ends on "{date}"'))
def the_task_ends_on(ctx, name, date):
    assert ctx.tasks[name].end_date.date() == _day(date).date()


@then(parsers.parse('the task "{name}" starts after the task "{other}" '
                    'ends'))
def the_task_starts_after(ctx, name, other):
    assert ctx.tasks[name].start_date > ctx.tasks[other].end_date
