"""
pytest-bdd tests for file I/O functionality.

Run with:
    python3 -m pytest tests/test_file_io_bdd.py -q

Display-free; files land in pytest's tmp_path instead of the mkdtemp
the original swept up in tearDown. Converted from test_file_io.py -
every case carried over.
"""
import json
import os
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Task, Project
from gantt_app.core.resource_model import Resource, ResourceType, TeamPool
from gantt_app.utils.file_io import JSONFileIO, save_project, load_project

pytestmark = [
    pytest.mark.file_io,
]

scenarios("features/file_io.feature")

START = datetime(2024, 1, 1)


def _two_task_project():
    """The two-task project the original built in setUp."""
    task1 = Task.create_task(
        name="Task 1", start_date=START,
        end_date=START + timedelta(days=3))
    task2 = Task.create_task(
        name="Task 2", start_date=START + timedelta(days=4),
        end_date=START + timedelta(days=8), dependencies=[task1.id])
    return Project(name="Test Project", tasks=[task1, task2])


# ------------------------------------------------------------------
# GIVEN
# ------------------------------------------------------------------

@given("a two-task project", target_fixture="ctx")
def a_two_task_project(tmp_path):
    return SimpleNamespace(project=_two_task_project(),
                           dir=str(tmp_path))


@given(parsers.parse('a two-task project saved to "{name}"'),
       target_fixture="ctx")
def a_two_task_project_saved(tmp_path, name):
    ctx = SimpleNamespace(project=_two_task_project(), dir=str(tmp_path))
    ctx.path = os.path.join(ctx.dir, name)
    JSONFileIO.save_project(ctx.project, ctx.path)
    return ctx


@given("a two-task project with a named resource in a team",
       target_fixture="ctx")
def a_project_with_a_named_resource(tmp_path):
    project = _two_task_project()
    repository = project.resource_repository
    repository.add_resource(Resource(
        id="res_1", name="John Doe", resource_type=ResourceType.NAMED,
        role_type="QA Manager", weekly_capacity_hours=40,
        cost_per_hour=75, assigned_project_ids=["Test Project"],
    ))
    repository.add_team(TeamPool(id="team_1", name="Core QA"))
    repository.set_team_allocation("res_1", "team_1", 60)
    return SimpleNamespace(project=project, dir=str(tmp_path))


@given("a two-task project with a generic resource in a team",
       target_fixture="ctx")
def a_project_with_a_generic_resource(tmp_path):
    project = _two_task_project()
    repository = project.resource_repository
    repository.add_resource(Resource(
        id="res_1", name="DevOps Engineer #1",
        resource_type=ResourceType.GENERIC, role_type="DevOps",
        team_memberships={"team_1": 0.4},
    ))
    repository.add_team(TeamPool(id="team_1", name="Infrastructure"))
    return SimpleNamespace(project=project, dir=str(tmp_path))


@given(parsers.parse('a file "{name}" holding "{content}"'),
       target_fixture="ctx")
def a_file_holding(tmp_path, name, content):
    path = os.path.join(str(tmp_path), name)
    with open(path, 'w') as stream:
        stream.write(content)
    return SimpleNamespace(dir=str(tmp_path))


@given("a task and a milestone project", target_fixture="ctx")
def a_task_and_a_milestone_project(tmp_path):
    task1 = Task.create_task(
        name="Task 1", start_date=START,
        end_date=START + timedelta(days=3))
    milestone = Task.create_milestone(
        name="Review", date=START + timedelta(days=5),
        dependencies=[task1.id])
    project = Project(name="Milestone Project",
                      tasks=[task1, milestone])
    return SimpleNamespace(project=project, dir=str(tmp_path))


@given("a project with a task that has no end date",
       target_fixture="ctx")
def a_project_with_no_end_date(tmp_path):
    task = Task(id="test1", name="Task No End", start_date=START,
                end_date=None)
    project = Project(name="No End Date Project", tasks=[task])
    return SimpleNamespace(project=project, dir=str(tmp_path))


@given("a project with an Inactive task", target_fixture="ctx")
def a_project_with_an_inactive_task(tmp_path):
    project = Project(name="Test Project")
    task = Task(id="1", name="Test Task", start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 1, 10), status="Inactive")
    project.add_task(task)
    return SimpleNamespace(project=project, dir=str(tmp_path))


@given("a legacy project file without a status field",
       target_fixture="ctx")
def a_legacy_project_file(tmp_path):
    project_data = {
        'name': 'Legacy Project',
        'tasks': [{
            'id': '1',
            'name': 'Legacy Task',
            'start_date': '2024-01-01T00:00:00',
            'end_date': '2024-01-10T00:00:00',
            'progress': 0,
            'dependencies': [],
            'color': '#1f6aa5',
            'is_milestone': False,
            'task_type': 'Task',
            'parent_task_id': None,
            'duration': None,
            'priority': 'Normal',
            'shape': 'Default',
            'show_in_timeline': True,
            'details': '',
            'calendar_id': None,
            'style': None
        }],
        'start_date': '2024-01-01T00:00:00',
        'end_date': '2024-01-10T00:00:00',
        'calendar': {'week_start': 1, 'holidays': [],
                     'nonworking_days': []},
        'calendars': {'default': {'name': 'Default', 'week_start': 1,
                                  'holidays': [], 'nonworking_days': []}},
        'schedule_from': 'Start',
        'deadline': None,
        'status_date': None,
        'priority': 500
    }
    path = os.path.join(str(tmp_path), "legacy.json")
    with open(path, 'w') as stream:
        json.dump(project_data, stream)
    return SimpleNamespace(dir=str(tmp_path))


@given("a one-task project", target_fixture="ctx")
def a_one_task_project(tmp_path):
    task1 = Task.create_task(
        name="Task 1", start_date=START,
        end_date=START + timedelta(days=3))
    project = Project(name="Test Project", tasks=[task1])
    return SimpleNamespace(project=project, dir=str(tmp_path))


@given(parsers.parse('a one-task project saved to "{name}"'),
       target_fixture="ctx")
def a_one_task_project_saved(tmp_path, name):
    ctx = SimpleNamespace(dir=str(tmp_path))
    ctx.path = os.path.join(ctx.dir, name)
    task1 = Task.create_task(
        name="Task 1", start_date=START,
        end_date=START + timedelta(days=3))
    save_project(Project(name="Test Project", tasks=[task1]), ctx.path)
    return ctx


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------

@when(parsers.parse('the project is saved to "{name}"'))
def the_project_is_saved(ctx, name):
    ctx.path = os.path.join(ctx.dir, name)
    ctx.result = JSONFileIO.save_project(ctx.project, ctx.path)


@when(parsers.parse('the project is saved to "{name}" through the '
                    'helper'))
def the_project_is_saved_through_the_helper(ctx, name):
    ctx.path = os.path.join(ctx.dir, name)
    ctx.result = save_project(ctx.project, ctx.path)


@when("the file is loaded")
def the_file_is_loaded(ctx):
    ctx.loaded = JSONFileIO.load_project(ctx.path)


@when(parsers.parse('"{name}" is loaded'))
def a_named_file_is_loaded(ctx, name):
    ctx.loaded = JSONFileIO.load_project(os.path.join(ctx.dir, name))


@when("the file is loaded through the helper")
def the_file_is_loaded_through_the_helper(ctx):
    ctx.loaded = load_project(ctx.path)


@when("the project dictionary loses its resources and teams")
def the_project_dictionary_loses_resources(ctx):
    data = ctx.project.to_dict()
    data.pop("resources")
    data.pop("teams")
    ctx.loaded = Project.from_dict(data)


@when(parsers.parse("a task built at {start} to {end} is dictified"),
      target_fixture="ctx")
def a_task_is_dictified(start, end):
    task = Task.create_task(
        name="Test",
        start_date=datetime.strptime(start, "%Y-%m-%dT%H:%M:%S"),
        end_date=datetime.strptime(end, "%Y-%m-%dT%H:%M:%S"))
    return SimpleNamespace(task_dict=task.to_dict())


@when("a task dictionary is built from ISO dates", target_fixture="ctx")
def a_task_dictionary_is_built():
    return SimpleNamespace(task=Task.from_dict({
        'id': 'test',
        'name': 'Test',
        'start_date': '2024-01-15T10:30:45',
        'end_date': '2024-02-20T14:20:00',
        'progress': 0,
        'dependencies': [],
        'color': '#1f6aa5',
        'is_milestone': False
    }))


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@then("the save answered True and the file exists")
def the_save_answered_true(ctx):
    assert ctx.result
    assert os.path.exists(ctx.path)


@then(parsers.parse('the loaded project is "{name}" with {count:d} tasks'))
def the_loaded_project_is(ctx, name, count):
    assert ctx.loaded is not None
    assert ctx.loaded.name == name
    assert len(ctx.loaded.tasks) == count


@then(parsers.parse('its tasks are named "{first}" and "{second}"'))
def its_tasks_are_named(ctx, first, second):
    assert ctx.loaded.tasks[0].name == first
    assert ctx.loaded.tasks[1].name == second


@then("every task field survived the round trip")
def every_task_field_survived(ctx):
    assert ctx.loaded.name == ctx.project.name
    assert len(ctx.loaded.tasks) == len(ctx.project.tasks)
    for original, loaded in zip(ctx.project.tasks, ctx.loaded.tasks):
        assert loaded.id == original.id
        assert loaded.name == original.name
        assert loaded.start_date == original.start_date
        assert loaded.end_date == original.end_date
        assert loaded.progress == original.progress
        assert loaded.dependencies == original.dependencies
        assert loaded.color == original.color
        assert loaded.is_milestone == original.is_milestone


@then(parsers.parse('the JSON holds "{resource}" and "{team}" and no '
                    'sidecar file'))
def the_json_holds_resources(ctx, resource, team):
    with open(ctx.path, encoding="utf-8") as stream:
        data = json.load(stream)
    assert data["resources"][0]["name"] == resource
    assert data["teams"][0]["name"] == team
    assert not os.path.exists(os.path.join(ctx.dir, "resources.json"))


@then(parsers.parse('the resource pool holds "{resource}" and "{team}"'))
def the_resource_pool_holds(ctx, resource, team):
    pool = ctx.loaded.resource_repository
    assert pool.resources["res_1"].name == resource
    assert pool.teams["team_1"].name == team


@then("the membership is 40 percent")
def the_membership_is_40_percent(ctx):
    assert ctx.loaded.resource_repository.resources[
        "res_1"].team_memberships == {"team_1": 0.4}


@then("the rebuilt project's pools are empty")
def the_rebuilt_pools_are_empty(ctx):
    assert ctx.loaded.resource_repository.resources == {}
    assert ctx.loaded.resource_repository.teams == {}


@then("nothing was loaded")
def nothing_was_loaded(ctx):
    assert ctx.loaded is None


@then(parsers.parse("the loaded project has {count:d} tasks"))
def the_loaded_project_has_tasks(ctx, count):
    assert ctx.loaded is not None
    assert len(ctx.loaded.tasks) == count


@then(parsers.parse('the milestone is "{name}" with no end date'))
def the_milestone_is(ctx, name):
    milestone = [t for t in ctx.loaded.tasks if t.is_milestone][0]
    assert milestone.name == name
    assert milestone.is_milestone
    assert milestone.end_date is None


@then("the loaded task has no end date")
def the_loaded_task_has_no_end(ctx):
    assert ctx.loaded is not None
    assert ctx.loaded.tasks[0].end_date is None


@then("the file parses with the project and task fields")
def the_file_parses_with_the_fields(ctx):
    with open(ctx.path, 'r') as stream:
        data = json.load(stream)
    for key in ('name', 'tasks', 'start_date', 'end_date'):
        assert key in data
    for task in data['tasks']:
        for key in ('id', 'name', 'start_date', 'end_date', 'progress',
                    'dependencies', 'color', 'is_milestone'):
            assert key in task


@then(parsers.parse('the loaded task\'s status is "{status}"'))
def the_loaded_task_status_is(ctx, status):
    assert ctx.loaded is not None
    assert ctx.loaded.get_task_by_id("1").status == status


@then(parsers.parse('the loaded project is "{name}"'))
def the_loaded_project_is_named(ctx, name):
    assert ctx.loaded is not None
    assert ctx.loaded.name == name


@then(parsers.parse('the dates read "{start}" and "{end}"'))
def the_dates_read(ctx, start, end):
    assert ctx.task_dict['start_date'] == start
    assert ctx.task_dict['end_date'] == end


@then(parsers.parse("the task dates are {start} and {end}"))
def the_task_dates_are(ctx, start, end):
    assert ctx.task.start_date == datetime.strptime(start,
                                                  "%Y-%m-%dT%H:%M:%S")
    assert ctx.task.end_date == datetime.strptime(end,
                                                "%Y-%m-%dT%H:%M:%S")
