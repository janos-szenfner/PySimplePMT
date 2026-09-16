"""
pytest-bdd tests for the Task Type / Effort-Driven fields on the model.

Run with:
    python3 -m pytest tests/test_effort_model_bdd.py -q

Pure model, no display. Converted from test_effort_model.py - every
case carried over.
"""
import json
from datetime import datetime
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import (
    DEFAULT_HOURS_PER_DAY,
    EFFORT_FIXED_UNITS,
    EFFORT_FIXED_WORK,
    Project,
    Task,
)
from gantt_app.utils.undoredo import ProjectStateTracker, UndoRedoManager

pytestmark = [
    pytest.mark.effort_model,
]

scenarios("features/effort_model.feature")


def _task(**kwargs):
    kwargs.setdefault('id', 'T')
    kwargs.setdefault('name', 'A task')
    kwargs.setdefault('start_date', datetime(2026, 9, 9))
    return Task(**kwargs)


# ------------------------------------------------------------------
# GIVEN
# ------------------------------------------------------------------

@given("a plain task", target_fixture="ctx")
def a_plain_task():
    return SimpleNamespace(task=_task())


@given(parsers.parse('a task with effort type "{effort_type}"'),
       target_fixture="ctx")
def a_task_with_an_effort_type(effort_type):
    return SimpleNamespace(task=_task(effort_type=effort_type))


@given("a fixed-work task with effort driven off", target_fixture="ctx")
def a_fixed_work_task_without_effort_driven():
    return SimpleNamespace(
        task=_task(effort_type=EFFORT_FIXED_WORK, effort_driven=False))


@given("a fixed-work, effort driven, manually scheduled task",
       target_fixture="ctx")
def a_fully_set_task():
    return SimpleNamespace(
        task=_task(effort_type=EFFORT_FIXED_WORK, effort_driven=True,
                   manually_scheduled=True))


@given("a task saved without the effort fields", target_fixture="ctx")
def a_task_saved_before_the_feature():
    # A task dict saved before the feature existed.
    data = _task().to_dict()
    for key in ('effort_type', 'effort_driven', 'manually_scheduled'):
        data.pop(key, None)
    return SimpleNamespace(data=data)


@given("a project whose day is 7.5 hours", target_fixture="ctx")
def a_project_with_a_shorter_day():
    project = Project(name='P')
    project.hours_per_day = 7.5
    return SimpleNamespace(project=project)


@given("a project saved without hours per day", target_fixture="ctx")
def a_project_saved_before_hours_per_day():
    data = Project(name='P').to_dict()
    data.pop('hours_per_day', None)
    ctx = SimpleNamespace(data=data)
    ctx.project = Project.from_dict(data)
    return ctx


@given("a tracked project holding a fixed-work task", target_fixture="ctx")
def a_tracked_project_with_a_fixed_work_task():
    project = Project(name='P')
    project.add_task(_task(effort_type=EFFORT_FIXED_WORK,
                           effort_driven=True))
    ctx = SimpleNamespace(project=project)
    ctx.tracker = ProjectStateTracker(project, UndoRedoManager())
    return ctx


@given("a tracked project holding a plain task", target_fixture="ctx")
def a_tracked_project_with_a_plain_task():
    project = Project(name='P')
    project.add_task(_task())
    ctx = SimpleNamespace(project=project)
    ctx.tracker = ProjectStateTracker(project, UndoRedoManager())
    return ctx


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------

@when("the task is saved and loaded again")
def the_task_round_trips(ctx):
    ctx.task = Task.from_dict(json.loads(json.dumps(ctx.task.to_dict())))


@when("the task is loaded")
def the_task_is_loaded(ctx):
    ctx.task = Task.from_dict(ctx.data)


@when("the project is saved and loaded again")
def the_project_round_trips(ctx):
    ctx.project = Project.from_dict(
        json.loads(json.dumps(ctx.project.to_dict())))


@when("the task is renamed through the tracker")
def the_task_is_renamed(ctx):
    # Change only the name; the effort fields must be preserved.
    ctx.tracker.update_task('T', name='Renamed')


@when("the task's effort type is set to fixed work through the tracker")
def the_effort_type_is_set(ctx):
    ctx.tracker.update_task('T', effort_type=EFFORT_FIXED_WORK)


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@then("its effort type is fixed units")
def the_effort_type_is_fixed_units(ctx):
    assert ctx.task.effort_type == EFFORT_FIXED_UNITS


@then("its effort type is fixed work")
def the_effort_type_is_fixed_work(ctx):
    assert ctx.task.effort_type == EFFORT_FIXED_WORK


@then("the tracked task's effort type is fixed work")
def the_tracked_tasks_effort_type_is_fixed_work(ctx):
    task = ctx.project.get_task_by_id('T')
    assert task.effort_type == EFFORT_FIXED_WORK


@then("its effort type is still fixed work")
def the_effort_type_is_still_fixed_work(ctx):
    task = ctx.project.get_task_by_id('T')
    assert task.effort_type == EFFORT_FIXED_WORK


@then("it is effort driven")
def it_is_effort_driven(ctx):
    assert ctx.task.effort_driven


@then("it is still effort driven")
def it_is_still_effort_driven(ctx):
    assert ctx.project.get_task_by_id('T').effort_driven


@then("it is not manually scheduled")
def it_is_not_manually_scheduled(ctx):
    assert not ctx.task.manually_scheduled


@then("it is manually scheduled")
def it_is_manually_scheduled(ctx):
    assert ctx.task.manually_scheduled


@then("a new project's hours per day is the default")
def a_new_projects_hours_per_day():
    assert Project(name='P').hours_per_day == DEFAULT_HOURS_PER_DAY


@then(parsers.parse('its hours per day is {hours:g}'))
def its_hours_per_day_is(ctx, hours):
    assert ctx.project.hours_per_day == hours


@then("its hours per day is the default")
def its_hours_per_day_is_default(ctx):
    assert ctx.project.hours_per_day == DEFAULT_HOURS_PER_DAY


@then(parsers.parse('hours per day of {a:g}, {b:g} and "{c}" each read as '
                    'the default'))
def bad_hours_per_day_read_as_default(a, b, c):
    for bad in (a, b, c):
        data = Project(name='P').to_dict()
        data['hours_per_day'] = bad
        assert Project.from_dict(data).hours_per_day == DEFAULT_HOURS_PER_DAY
