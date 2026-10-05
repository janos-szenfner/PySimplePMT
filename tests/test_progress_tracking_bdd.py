"""
What "on track" means.

The scenarios live in features/progress_tracking.feature. They pin down
that on-track completion is a share of working days, not calendar days,
and that it stays a whole percentage at every offset.

The progress toolbar - presets, thresholds, group styling - needs a
display and stays in tests/test_progress_tracking.py.
"""

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then

from gantt_app.core.models import Project, Task


scenarios('features/progress_tracking.feature')

#: Monday 17 August 2026, so the weekday of every date below is known.
MONDAY = datetime(2026, 8, 17)


@pytest.fixture
def ctx():
    return SimpleNamespace(project=None, task=None)


def _d(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%d")


def _on(ctx, task, when: datetime) -> int:
    return ctx.project.progress_on_track(task, when)


@given('the working-week task')
def the_working_week_task(ctx):
    """A five-working-day task, Monday to Friday."""
    ctx.project = Project(name="Plan")
    ctx.task = Task(id="T1", name="Work", task_type="Task",
                    start_date=MONDAY,
                    end_date=MONDAY + timedelta(days=4))
    ctx.project.add_task(ctx.task)


@given(parsers.parse('a task "{task_id}" running "{start}" to "{end}"'))
def a_task_running(ctx, task_id, start, end):
    ctx.project.add_task(Task(id=task_id, name=task_id, task_type="Task",
                              start_date=_d(start), end_date=_d(end)))


@given(parsers.parse('a milestone "{task_id}" on "{day}"'))
def a_milestone_on(ctx, task_id, day):
    ctx.project.add_task(Task(id=task_id, name=task_id,
                              task_type="Milestone", start_date=_d(day)))


@given(parsers.parse('an open-ended task "{task_id}" starting "{day}"'))
def an_open_ended_task(ctx, task_id, day):
    ctx.project.add_task(Task(id=task_id, name=task_id, task_type="Task",
                              start_date=_d(day), end_date=None))


@given(parsers.parse('"{day}" is a holiday'))
def a_holiday(ctx, day):
    ctx.project.calendar.holidays.add(_d(day).date())


@then(parsers.parse('on-track a day before it starts is {expected:d}'))
def before_it_starts(ctx, expected):
    assert _on(ctx, ctx.task, MONDAY - timedelta(days=1)) == expected


@then(parsers.parse('on-track a week in is {expected:d}'))
def a_week_in(ctx, expected):
    assert _on(ctx, ctx.task, MONDAY + timedelta(days=7)) == expected


@then(parsers.parse('on-track {offset:d} days in is {expected:d}'))
def days_in(ctx, offset, expected):
    assert _on(ctx, ctx.task, MONDAY + timedelta(days=offset)) == expected


@then(parsers.parse('on-track the first four days reads "{readings}"'))
def the_first_four_days(ctx, readings):
    wanted = [int(piece) for piece in readings.split(',')]
    assert ([_on(ctx, ctx.task, MONDAY + timedelta(days=day))
             for day in range(4)] == wanted)


@then('on-track the weekend days read the same as Friday')
def the_weekend_adds_nothing(ctx):
    friday = _on(ctx, ctx.task, MONDAY + timedelta(days=4))
    assert _on(ctx, ctx.task, MONDAY + timedelta(days=5)) == friday
    assert _on(ctx, ctx.task, MONDAY + timedelta(days=6)) == friday


@then(parsers.parse('"{task_id}" is {expected:d} on-track on "{day}"'))
def a_task_on_a_day(ctx, task_id, expected, day):
    task = ctx.project.get_task_by_id(task_id)
    assert _on(ctx, task, _d(day)) == expected


@then('on-track is a whole percentage at every offset tried')
def always_a_percentage(ctx):
    for offset in range(-10, 20):
        value = _on(ctx, ctx.task, MONDAY + timedelta(days=offset))
        assert isinstance(value, int)
        assert 0 <= value <= 100
