"""
The settings a whole plan is built from.

The scenarios live in features/project_settings.feature. They pin down
the four settings a project carries, that shifting a plan to a new start
moves it rather than rebuilding it, and that scheduling backward packs
the plan against its deadline.

The settings panel needs a display and stays in
tests/test_project_settings.py.
"""

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import (
    DEFAULT_PROJECT_PRIORITY, MAX_PROJECT_PRIORITY, MIN_PROJECT_PRIORITY,
    SCHEDULE_FROM_FINISH, SCHEDULE_FROM_START, Project, Task,
)


scenarios('features/project_settings.feature')

#: Monday 17 August 2026, so every weekday below is known.
MONDAY = datetime(2026, 8, 17)

DIRECTIONS = {'start': SCHEDULE_FROM_START, 'finish': SCHEDULE_FROM_FINISH}
PRIORITIES = {'max': MAX_PROJECT_PRIORITY, 'min': MIN_PROJECT_PRIORITY,
              'default': DEFAULT_PROJECT_PRIORITY}


@pytest.fixture
def ctx():
    return SimpleNamespace(project=None)


def _d(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%d")


# ---- what a project holds -----------------------------------------------------

@then(parsers.parse('a new plan schedules from "{direction}"'))
def a_new_plan_is_forward(direction):
    assert Project(name="P").schedule_from == DIRECTIONS[direction]


@then(parsers.parse('a plan asking for direction "{direction}" schedules '
                    'from "{expected}"'))
def an_unknown_direction_falls_back(direction, expected):
    assert (Project(name="P", schedule_from=direction).schedule_from
            == DIRECTIONS[expected])


@then(parsers.parse('a plan with priority {given} holds {expected}'))
def the_priority_is_clamped(given, expected):
    try:
        given = int(given)
    except ValueError:
        pass
    assert Project(name="P", priority=given).priority == PRIORITIES[expected]


@given(parsers.parse('a plan scheduled from "{direction}" with deadline '
                     '"{deadline}", status "{status}" and priority '
                     '{priority:d}'))
def a_configured_plan(ctx, direction, deadline, status, priority):
    ctx.saved = Project(name="P", schedule_from=DIRECTIONS[direction],
                        deadline=_d(deadline), status_date=_d(status),
                        priority=priority)


@when('the plan is saved and read back')
def saved_and_read_back(ctx):
    ctx.project = Project.from_dict(ctx.saved.to_dict())


@given('a saved plan with the settings removed')
def a_plan_before_the_settings(ctx):
    ctx.saved = Project(name="P").to_dict()
    for key in ('schedule_from', 'deadline', 'status_date', 'priority'):
        del ctx.saved[key]


@given(parsers.parse('a saved plan with deadline "{deadline}"'))
def a_plan_with_a_bad_date(ctx, deadline):
    ctx.saved = Project(name="P").to_dict()
    ctx.saved['deadline'] = deadline


@when('the plan is read back')
def the_plan_is_read_back(ctx):
    ctx.project = Project.from_dict(ctx.saved)


@then(parsers.parse('it schedules from "{direction}"'))
def it_schedules_from(ctx, direction):
    assert ctx.project.schedule_from == DIRECTIONS[direction]


@then(parsers.parse('its deadline is "{deadline}"'))
def its_deadline_is(ctx, deadline):
    assert ctx.project.deadline == _d(deadline)


@then(parsers.parse('its status date is "{status}"'))
def its_status_date_is(ctx, status):
    assert ctx.project.status_date == _d(status)


@then(parsers.parse('its priority is {priority:d}'))
def its_priority_is(ctx, priority):
    assert ctx.project.priority == priority


@then('it has no deadline')
def it_has_no_deadline(ctx):
    assert ctx.project.deadline is None


@then('it has no status date')
def it_has_no_status_date(ctx):
    assert ctx.project.status_date is None


@then('its priority is the default')
def its_priority_is_the_default(ctx):
    assert ctx.project.priority == DEFAULT_PROJECT_PRIORITY


# ---- the fixture: a chain of three plus one with float ----------------------------

def _chain_plan() -> Project:
    """The fixture, settled forward."""
    project = Project(name="Plan")
    for task_id in ('a', 'b', 'c'):
        project.add_task(Task(id=task_id, name=task_id.upper(),
                              task_type="Task", start_date=MONDAY,
                              end_date=MONDAY + timedelta(days=4)))
    project.add_task(Task(id='slack', name="Slack", task_type="Task",
                          start_date=MONDAY,
                          end_date=MONDAY + timedelta(days=1)))
    project.get_task_by_id('b').add_dependency('a')
    project.get_task_by_id('c').add_dependency('b')
    project.get_task_by_id('slack').add_dependency('a')
    project.reschedule()
    return project


def _spans(project):
    """Each task's working duration, by id."""
    return {task.id: project.working_duration(task)
            for task in project.tasks}


@given('the chain plan')
def the_chain_plan(ctx):
    ctx.project = _chain_plan()
    ctx.spans = _spans(ctx.project)
    ctx.gap = (ctx.project.get_task_by_id('c').start_date
               - ctx.project.get_task_by_id('a').start_date)


@given('two identical chain plans')
def two_chain_plans(ctx):
    ctx.one, ctx.other = _chain_plan(), _chain_plan()


@given(parsers.parse('"{task_id}" is pinned "{constraint}" to "{day}"'))
def is_pinned(ctx, task_id, constraint, day):
    task = ctx.project.get_task_by_id(task_id)
    task.constraint_type = constraint
    task.constraint_date = _d(day)
    ctx.floor = task.constraint_date


# ---- moving the whole plan ----------------------------------------------------------

@when(parsers.parse('the plan is shifted to "{start}"'))
def the_plan_is_shifted(ctx, start):
    ctx.moved = ctx.project.shift_to_start(_d(start))


@then(parsers.parse('the plan starts "{start}"'))
def the_plan_starts(ctx, start):
    assert ctx.project.start_date.date() == _d(start).date()


@then('every working duration is what it was')
def every_duration_survives(ctx):
    assert _spans(ctx.project) == ctx.spans


@then(parsers.parse('the gap between "{first}" and "{last}" is what it was'))
def the_gaps_survive(ctx, first, last):
    gap_now = (ctx.project.get_task_by_id(last).start_date
               - ctx.project.get_task_by_id(first).start_date)
    assert gap_now == ctx.gap


@then(parsers.parse('"{task_id}" is pinned later than "{day}"'))
def is_pinned_later(ctx, task_id, day):
    assert (ctx.project.get_task_by_id(task_id).constraint_date
            > _d(day))


@then('shifting the plan to its own start says nothing moved')
def shifting_to_itself(ctx):
    assert ctx.project.shift_to_start(ctx.project.start_date) is False


@then('an empty plan says nothing moved')
def an_empty_plan_is_not_moved():
    assert Project(name="P").shift_to_start(MONDAY) is False


# ---- As Late As Possible -------------------------------------------------------------

@when(parsers.parse('it is scheduled backward to "{deadline}"'))
def scheduled_backward(ctx, deadline):
    ctx.project.schedule_from = SCHEDULE_FROM_FINISH
    ctx.project.deadline = _d(deadline)
    ctx.project.apply_schedule()


@then(parsers.parse('the plan ends "{end}"'))
def the_plan_ends(ctx, end):
    assert ctx.project.end_date.date() == _d(end).date()


@then(parsers.parse('"{task_id}" still starts after "{predecessor}" ends'))
def the_links_hold(ctx, task_id, predecessor):
    follower = ctx.project.get_task_by_id(task_id)
    leader = ctx.project.get_task_by_id(predecessor)
    assert follower.start_date > leader.end_date


@then(parsers.parse('"{task_id}" finishes later in the plan than '
                    'forward-scheduled'))
def float_is_spent(ctx, task_id):
    forward = _chain_plan()
    early = (forward.get_task_by_id(task_id).end_date
             - forward.start_date).days
    late = (ctx.project.get_task_by_id(task_id).end_date
            - ctx.project.start_date).days
    assert late > early


@when('one applies its schedule and the other reschedules')
def one_applies_the_other_reschedules(ctx):
    ctx.one.apply_schedule()
    ctx.other.reschedule()


@then("they agree on every task's dates")
def they_agree(ctx):
    assert ([(t.id, t.start_date, t.end_date) for t in ctx.one.tasks]
            == [(t.id, t.start_date, t.end_date) for t in ctx.other.tasks])
