"""
pytest-bdd tests for the Baseline Management Engine.

Run with:
    python3 -m pytest tests/test_baselines_bdd.py -q
"""
from datetime import datetime

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.baselines import BaselineManager
from gantt_app.models import Project, Task
from gantt_app.resource_model import (
    Resource, ResourceRepository, ResourceType, SchedulePattern,
)

scenarios("features/baselines.feature")


@pytest.fixture
def ctx():
    return {}


def _find_task(project, name):
    for task in project.tasks:
        if task.name == name:
            return task
    raise AssertionError(f"task {name!r} not found")


# ------------------------------------------------------------------
# GIVEN
# ------------------------------------------------------------------
@given("a new baseline manager")
def a_new_baseline_manager(ctx):
    ctx["manager"] = BaselineManager()


@given("a project with two tasks")
def a_project_with_two_tasks(ctx):
    project = Project(name="Baseline Test")
    for name, start, end in (
        ("Task A", datetime(2026, 1, 1), datetime(2026, 1, 2)),
        ("Task B", datetime(2026, 1, 5), datetime(2026, 1, 6)),
    ):
        task = Task(
            id=name.lower().replace(" ", "-"),
            name=name,
            start_date=start,
            end_date=end,
        )
        task.__post_init__()
        project.add_task(task)
    ctx["project"] = project


@given("a project with a parent task and two child tasks")
def a_project_with_a_parent_task_and_two_child_tasks(ctx):
    project = Project(name="Baseline Rollup")
    parent = Task(
        id="parent", name="Parent Phase", task_type="Phase",
        start_date=datetime(2026, 1, 1),
        end_date=datetime(2026, 1, 10),
    )
    parent.__post_init__()
    project.add_task(parent)
    for name, start, end in (
        ("Child 1", datetime(2026, 1, 1), datetime(2026, 1, 2)),
        ("Child 2", datetime(2026, 1, 5), datetime(2026, 1, 6)),
    ):
        task = Task(
            id=name.lower().replace(" ", "-"),
            name=name,
            start_date=start,
            end_date=end,
            parent_task_id=parent.id,
        )
        task.__post_init__()
        project.add_task(task)
    ctx["project"] = project
    ctx["parent_id"] = parent.id


@given("a project with a task scheduled for 2026-01-01 to 2026-01-02")
def a_project_with_a_task_scheduled_for_2026_01_01_to_2026_01_02(ctx):
    project = Project(name="Variance Test")
    task = Task(
        id="t1", name="Task",
        start_date=datetime(2026, 1, 1),
        end_date=datetime(2026, 1, 2),
    )
    task.__post_init__()
    project.add_task(task)
    ctx["project"] = project
    ctx["task_id"] = task.id


@given("a project with a 10 hour task assigned to a resource costing 50 per hour")
def a_project_with_a_10_hour_task_assigned_to_a_resource_costing_50_per_hour(ctx):
    project = Project(name="Cost Variance")
    repo = ResourceRepository()
    resource = Resource(
        id="r1", name="Dev", resource_type=ResourceType.NAMED,
        role_type="Dev", cost_per_hour=50.0,
        schedule_pattern=SchedulePattern.STANDARD,
    )
    repo.resources["r1"] = resource
    task = Task(
        id="t1", name="Task",
        start_date=datetime(2026, 1, 1),
        end_date=datetime(2026, 1, 2),
        resource_assignments=[{
            "resource_id": "r1",
            "estimated_hours": 10.0,
            "resource_split": 100.0,
        }],
    )
    task.__post_init__()
    project.add_task(task)
    project.resource_repository = repo
    ctx["project"] = project
    ctx["task_id"] = task.id


@given("a new baseline manager with baseline 1 set")
def a_new_baseline_manager_with_baseline_1_set(ctx):
    ctx["manager"] = BaselineManager()
    ctx["manager"].set_baseline(ctx["project"], 1)


@given(parsers.parse('a new baseline manager with slot {number:d} renamed to "{name}"'))
def a_new_baseline_manager_with_slot_renamed(ctx, number, name):
    ctx["manager"] = BaselineManager()
    ctx["manager"].rename_slot(number, name)


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------
@when(parsers.parse('the user renames slot {number:d} to "{name}"'))
def the_user_renames_slot(ctx, number, name):
    ctx["manager"].rename_slot(number, name)


@when(parsers.parse('the user sets baseline {number:d} for the entire project'))
def the_user_sets_baseline_for_the_entire_project(ctx, number):
    ctx["manager"].set_baseline(ctx["project"], number)


@when(parsers.parse('the user sets baseline {number:d} for the selected task "{task}"'))
def the_user_sets_baseline_for_the_selected_task(ctx, number, task):
    task_obj = _find_task(ctx["project"], task)
    ctx["manager"].set_baseline(ctx["project"], number, task_ids=[task_obj.id])


@when(parsers.parse('the user sets baseline {number:d} for the child tasks with roll-up'))
def the_user_sets_baseline_for_the_child_tasks_with_roll_up(ctx, number):
    child_ids = [t.id for t in ctx["project"].tasks
                 if t.parent_task_id == ctx["parent_id"]]
    ctx["manager"].set_baseline(
        ctx["project"], number, task_ids=child_ids, rollup=True)


@when(parsers.parse('the user clears baseline {number:d}'))
def the_user_clears_baseline(ctx, number):
    ctx["manager"].clear_baseline(number)


@when(parsers.parse('the task is moved to start on {start} and end on {end}'))
def the_task_is_moved_to_start_on_and_end_on(ctx, start, end):
    task = ctx["project"].tasks[0]
    task.start_date = datetime.fromisoformat(start)
    task.end_date = datetime.fromisoformat(end)
    ctx["variance"] = ctx["manager"].compare(ctx["project"])[task.id]


@when(parsers.parse('the task work is increased to {hours} hours'))
def the_task_work_is_increased_to(ctx, hours):
    hours = float(hours)
    task = ctx["project"].tasks[0]
    task.resource_assignments[0]["estimated_hours"] = hours
    ctx["variance"] = ctx["manager"].compare(ctx["project"])[task.id]


@when("the manager is serialized and restored")
def the_manager_is_serialized_and_restored(ctx):
    data = ctx["manager"].to_dict()
    ctx["manager"] = BaselineManager.from_dict(data)


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------
@then('there are 10 baseline slots')
def there_are_10_baseline_slots(ctx):
    assert len(ctx["manager"].slots) == 10


@then(parsers.parse('the first slot is named "{name}"'))
def the_first_slot_is_named(ctx, name):
    assert ctx["manager"].get_slot(1).display_name == name


@then(parsers.parse('slot {number:d} is named "{name}"'))
def slot_is_named(ctx, number, name):
    assert ctx["manager"].get_slot(number).display_name == name


@then(parsers.parse('slot {number:d} is still named "{name}"'))
def slot_is_still_named(ctx, number, name):
    assert ctx["manager"].get_slot(number).display_name == name


@then(parsers.parse('baseline {number:d} contains {count:d} task snapshots'))
def baseline_contains_task_snapshots(ctx, number, count):
    slot = ctx["manager"].get_slot(number)
    assert slot.baseline is not None
    assert len(slot.baseline.task_snapshots) == count


@then(parsers.parse('baseline {number:d} is active'))
def baseline_is_active(ctx, number):
    assert ctx["manager"].active_slot_number == number
    assert ctx["manager"].get_slot(number).active


@then(parsers.parse('baseline {number:d} is unset'))
def baseline_is_unset(ctx, number):
    slot = ctx["manager"].get_slot(number)
    assert not slot.is_set
    assert slot.saved_at is None


@then(parsers.parse('the parent task in baseline {number:d} starts on the earliest child start'))
def the_parent_task_in_baseline_starts_on_the_earliest_child_start(ctx, number):
    slot = ctx["manager"].get_slot(number)
    child_starts = [t.start_date for t in ctx["project"].tasks
                    if t.parent_task_id == ctx["parent_id"]]
    assert slot.baseline.task_snapshots[ctx["parent_id"]].start_date == min(child_starts)


@then(parsers.parse('the parent task in baseline {number:d} finishes on the latest child finish'))
def the_parent_task_in_baseline_finishes_on_the_latest_child_finish(ctx, number):
    slot = ctx["manager"].get_slot(number)
    child_finishes = [t.end_date for t in ctx["project"].tasks
                      if t.parent_task_id == ctx["parent_id"]]
    assert slot.baseline.task_snapshots[ctx["parent_id"]].finish_date == max(child_finishes)


@then(parsers.parse('the start variance is {expected} working days'))
def the_start_variance_is(ctx, expected):
    assert ctx["variance"].start_variance_days == int(expected)


@then(parsers.parse('the duration variance is {expected}'))
def the_duration_variance_is(ctx, expected):
    assert ctx["variance"].duration_variance_days == int(expected)


@then(parsers.parse('the work variance is {expected} hours'))
def the_work_variance_is(ctx, expected):
    assert ctx["variance"].work_variance_hours == float(expected)


@then(parsers.parse('the cost variance is {expected}'))
def the_cost_variance_is(ctx, expected):
    assert ctx["variance"].cost_variance == float(expected)
