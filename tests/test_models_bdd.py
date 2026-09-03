"""
pytest-bdd tests for Task and Project model functionality.

Run with:
    python3 -m pytest tests/test_models_bdd.py -q
"""

from datetime import datetime, timedelta
from pytest_bdd import given, parsers, scenarios, then, when
import pytest
import uuid

from gantt_app.models import Project, Task


# Load the Gherkin scenarios
scenarios("features/models.feature")


# BASE DATE FIXTURE
@given('a base date of "2024-01-01"')
def base_date():
    return datetime(2024, 1, 1)


# BASIC TASK CREATION
@given("a task with id, name, start_date, and end_date", target_fixture="basic_task")
def basic_task():
    base_date = datetime(2024, 1, 1)
    test_id = str(uuid.uuid4())
    task_name = "Test Task"
    end_date = base_date + timedelta(days=9)
    
    return {
        'task': Task(
            id=test_id,
            name=task_name,
            start_date=base_date,
            end_date=end_date
        ),
        'test_id': test_id,
        'task_name': task_name,
        'start_date': base_date,
        'end_date': end_date
    }


@then("the task should have the correct id")
def check_task_id(basic_task):
    assert basic_task['task'].id == basic_task['test_id']


@then("the task should have the correct name")
def check_task_name(basic_task):
    assert basic_task['task'].name == basic_task['task_name']


@then("the task should have the correct start_date")
def check_task_start_date(basic_task):
    assert basic_task['task'].start_date == basic_task['start_date']


@then("the task should have the correct end_date")
def check_task_end_date(basic_task):
    assert basic_task['task'].end_date == basic_task['end_date']


@then("the task progress should default to 0")
def check_task_progress_default(basic_task):
    assert basic_task['task'].progress == 0


@then("the task dependencies should default to empty list")
def check_task_dependencies_default(basic_task):
    assert basic_task['task'].dependency_ids == []


@then('the task color should default to "#1f6aa5"')
def check_task_color_default(basic_task):
    assert basic_task['task'].color == "#1f6aa5"


@then("the task should not be a milestone")
def check_task_not_milestone(basic_task):
    assert not basic_task['task'].is_milestone


@then("the task should not be a factory milestone")
def check_factory_task_not_milestone(factory_task):
    assert not factory_task.is_milestone


# FACTORY METHOD CREATION
@given("a task created with Task.create_task", target_fixture="factory_task")
def factory_task():
    base_date = datetime(2024, 1, 1)
    end_date = base_date + timedelta(days=9)
    return Task.create_task(
        name="Factory Task",
        start_date=base_date,
        end_date=end_date,
        color="#3498db",
        progress=50,
        dependencies=["dep1", "dep2"]
    )


@then("the task should have an auto-generated factory id")
def check_factory_task_id(factory_task):
    assert factory_task.id is not None


@then("the task should have the specified factory name")
def check_factory_task_name(factory_task):
    assert factory_task.name == "Factory Task"


@then("the task should have the specified factory dates")
def check_factory_task_dates(factory_task):
    base_date = datetime(2024, 1, 1)
    assert factory_task.start_date == base_date
    assert factory_task.end_date == base_date + timedelta(days=9)


@then("the task should have the specified factory color")
def check_factory_task_color(factory_task):
    assert factory_task.color == "#3498db"


@then("the task should have the specified factory progress")
def check_factory_task_progress(factory_task):
    assert factory_task.progress == 50


@then("the task should have the specified factory dependencies")
def check_factory_task_dependencies(factory_task):
    assert factory_task.dependency_ids == ["dep1", "dep2"]


# MILESTONE CREATION
@given("a milestone created with Task.create_milestone", target_fixture="milestone_task")
def milestone_task():
    base_date = datetime(2024, 1, 1)
    return Task.create_milestone(
        name="Test Milestone",
        date=base_date,
        color="#e74c3c",
        dependencies=["dep1"]
    )


@then("the milestone should have an auto-generated milestone id")
def check_milestone_id(milestone_task):
    assert milestone_task.id is not None


@then("the milestone should have the specified milestone name")
def check_milestone_name(milestone_task):
    assert milestone_task.name == "Test Milestone"


@then("the milestone should have the specified milestone date as start_date")
def check_milestone_date(milestone_task):
    base_date = datetime(2024, 1, 1)
    assert milestone_task.start_date == base_date


@then("the milestone end_date should be None")
def check_milestone_end_date_none(milestone_task):
    assert milestone_task.end_date is None


@then("the milestone should have the specified milestone color")
def check_milestone_color(milestone_task):
    assert milestone_task.color == "#e74c3c"


@then("the milestone should have the specified milestone dependencies")
def check_milestone_dependencies(milestone_task):
    assert milestone_task.dependency_ids == ["dep1"]


@then("the milestone should be marked as a milestone")
def check_milestone_is_milestone(milestone_task):
    assert milestone_task.is_milestone


# VALIDATION TESTS
@when("creating a task with empty name")
def create_task_empty_name():
    with pytest.raises(ValueError):
        Task(id="test", name="", start_date=datetime(2024, 1, 1))


@then("a ValueError should be raised")
def check_value_error_raised():
    # This will be handled by the When step raising the exception
    pass


@when("creating a task with progress -1")
def create_task_invalid_progress_low():
    with pytest.raises(ValueError):
        Task(id="test", name="Test", start_date=datetime(2024, 1, 1), progress=-1)


@when("creating a task with progress 101")
def create_task_invalid_progress_high():
    with pytest.raises(ValueError):
        Task(id="test", name="Test", start_date=datetime(2024, 1, 1), progress=101)


# MILESTONE END DATE HANDLING
@given("a milestone with end_date initially set", target_fixture="milestone_with_end_date")
def milestone_with_end_date():
    base_date = datetime(2024, 1, 1)
    milestone = Task(
        id="milestone1",
        name="Test Milestone",
        start_date=base_date,
        end_date=base_date + timedelta(days=5),
        is_milestone=True
    )
    return milestone


@then("the end_date should be None after creation")
def check_milestone_end_date_none_after_creation(milestone_with_end_date):
    assert milestone_with_end_date.end_date is None


# DURATION CALCULATION TESTS
@given("a task spanning Monday to Friday", target_fixture="task_mon_to_fri")
def task_mon_to_fri():
    base_date = datetime(2024, 1, 1)
    return Task(
        id="test",
        name="Test",
        start_date=base_date,  # Monday
        end_date=base_date + timedelta(days=4)  # Friday
    )


@then("the duration should be 5 days")
def check_duration_5_days(task_mon_to_fri):
    assert task_mon_to_fri.duration_days == 5


@then("the total elapsed days should be 5 days")
def check_elapsed_days_5(task_mon_to_fri):
    assert task_mon_to_fri.total_elapsed_days == 5


@given("a task spanning 10 calendar days including weekend", target_fixture="task_10_days")
def task_10_days():
    base_date = datetime(2024, 1, 1)
    return Task(
        id="test",
        name="Test",
        start_date=base_date,  # Monday
        end_date=base_date + timedelta(days=9)  # 10 calendar days later
    )


@then("the duration should be 8 working days")
def check_duration_8_days(task_10_days):
    assert task_10_days.duration_days == 8


@then("the total elapsed days should be 10 days")
def check_elapsed_days_10(task_10_days):
    assert task_10_days.total_elapsed_days == 10


@given("a task with explicit duration of 3 days", target_fixture="task_explicit_duration")
def task_explicit_duration():
    base_date = datetime(2024, 1, 1)
    return Task(
        id="test",
        name="Test",
        start_date=base_date,
        end_date=base_date + timedelta(days=4),
        duration=3
    )


@then("the duration_days should be 3")
def check_explicit_duration_3(task_explicit_duration):
    assert task_explicit_duration.duration_days == 3


@given("a milestone", target_fixture="simple_milestone")
def simple_milestone():
    base_date = datetime(2024, 1, 1)
    return Task.create_milestone(name="Test", date=base_date)


@then("the duration_days should be 0")
def check_milestone_duration_zero(simple_milestone):
    assert simple_milestone.duration_days == 0


@given("a task with end_date None", target_fixture="task_no_end_date")
def task_no_end_date():
    base_date = datetime(2024, 1, 1)
    return Task(
        id="test",
        name="Test",
        start_date=base_date,
        end_date=None
    )


@then("the duration_days should be None")
def check_duration_none(task_no_end_date):
    assert task_no_end_date.duration_days is None


# PROJECT TESTS
@given("an empty project", target_fixture="empty_project")
def empty_project():
    return Project(name="Empty Project")


@then("the project name should be correct")
def check_empty_project_name(empty_project):
    assert empty_project.name == "Empty Project"


@then("the project tasks should be empty")
def check_empty_project_tasks(empty_project):
    assert empty_project.tasks == []


@then("the project start_date should be None")
def check_empty_project_start_none(empty_project):
    assert empty_project.start_date is None


@then("the project end_date should be None")
def check_empty_project_end_none(empty_project):
    assert empty_project.end_date is None


@given("a project with multiple tasks", target_fixture="project_with_tasks")
def project_with_tasks():
    base_date = datetime(2024, 1, 1)
    task1 = Task.create_task(
        name="Task 1",
        start_date=base_date,
        end_date=base_date + timedelta(days=3)
    )
    
    task2 = Task.create_task(
        name="Task 2",
        start_date=base_date + timedelta(days=5),
        end_date=base_date + timedelta(days=10)
    )
    
    task3 = Task.create_task(
        name="Task 3",
        start_date=base_date + timedelta(days=2),
        end_date=base_date + timedelta(days=8)
    )
    
    return Project(name="Test Project", tasks=[task1, task2, task3])


@then("the project should contain the created tasks")
def check_project_contains_all_tasks(project_with_tasks):
    assert len(project_with_tasks.tasks) == 3


@then("the project start_date should be the earliest task start")
def check_project_earliest_start(project_with_tasks):
    base_date = datetime(2024, 1, 1)
    assert project_with_tasks.start_date == base_date


@then("the project end_date should be the latest task end")
def check_project_latest_end(project_with_tasks):
    base_date = datetime(2024, 1, 1)
    assert project_with_tasks.end_date == base_date + timedelta(days=10)


@given("a project", target_fixture="simple_project")
def simple_project():
    return Project(name="Test Project")


@when("a task is added to the project", target_fixture="project_with_added_task")
def add_task_to_project(simple_project):
    base_date = datetime(2024, 1, 1)
    project = simple_project
    task = Task.create_task(
        name="Added Task",
        start_date=base_date,
        end_date=base_date + timedelta(days=3)
    )
    project.add_task(task)
    return {'project': project, 'task': task, 'start_date': base_date}


@then("the project should contain the task")
def check_project_contains_task(project_with_added_task):
    assert len(project_with_added_task['project'].tasks) == 1
    assert project_with_added_task['project'].tasks[0].name == "Added Task"


@then("the project start_date should be the task start")
def check_project_start_is_task_start(project_with_added_task):
    assert project_with_added_task['project'].start_date == project_with_added_task['start_date']


@then("the project end_date should be the task end")
def check_project_end_is_task_end(project_with_added_task):
    expected_end = project_with_added_task['start_date'] + timedelta(days=3)
    assert project_with_added_task['project'].end_date == expected_end


@when("multiple tasks are added", target_fixture="project_with_multiple_tasks")
def add_multiple_tasks(simple_project):
    base_date = datetime(2024, 1, 1)
    project = simple_project
    
    task1 = Task.create_task(
        name="First",
        start_date=base_date + timedelta(days=2),
        end_date=base_date + timedelta(days=5)
    )
    
    task2 = Task.create_task(
        name="Second",
        start_date=base_date,
        end_date=base_date + timedelta(days=3)
    )
    
    task3 = Task.create_task(
        name="Third",
        start_date=base_date + timedelta(days=10),
        end_date=base_date + timedelta(days=15)
    )
    
    project.add_task(task1)
    project.add_task(task2)
    project.add_task(task3)
    
    return project


@then("the project should contain all added tasks")
def check_project_contains_all_multiple_tasks(project_with_multiple_tasks):
    assert len(project_with_multiple_tasks.tasks) == 3


@then("the project start_date should be the earliest start")
def check_project_earliest_start_multiple(project_with_multiple_tasks):
    base_date = datetime(2024, 1, 1)
    assert project_with_multiple_tasks.start_date == base_date


@then("the project end_date should be the latest end")
def check_project_latest_end_multiple(project_with_multiple_tasks):
    base_date = datetime(2024, 1, 1)
    assert project_with_multiple_tasks.end_date == base_date + timedelta(days=15)


@given("a project with tasks", target_fixture="project_with_tasks_for_removal")
def project_with_tasks_for_removal():
    base_date = datetime(2024, 1, 1)
    task1 = Task.create_task(
        name="Task 1",
        start_date=base_date,
        end_date=base_date + timedelta(days=3)
    )
    
    task2 = Task.create_task(
        name="Task 2",
        start_date=base_date + timedelta(days=5),
        end_date=base_date + timedelta(days=10)
    )
    
    project = Project(name="Test Project", tasks=[task1, task2])
    return {'project': project, 'task1': task1, 'task2': task2}


@when("a task is removed from the project", target_fixture="project_after_task_removal")
def remove_task_from_project(project_with_tasks_for_removal):
    project = project_with_tasks_for_removal['project']
    task1 = project_with_tasks_for_removal['task1']
    
    # Remove task1 and return the modified project state
    result = project.remove_task(task1.id)
    return {'project': project, 'task1': task1, 'task2': project_with_tasks_for_removal['task2'], 'result': result}


@then("the project should no longer contain the task")
def check_task_removed(project_after_task_removal):
    assert len(project_after_task_removal['project'].tasks) == 1
    assert project_after_task_removal['project'].tasks[0].id == project_after_task_removal['task2'].id


@then("removing non-existent task should return False")
def check_remove_nonexistent_task(project_with_tasks_for_removal):
    project = project_with_tasks_for_removal['project']
    result = project.remove_task("non-existent-id")
    assert result is False


@given("a project with dependent tasks", target_fixture="project_with_dependencies")
def project_with_dependencies():
    base_date = datetime(2024, 1, 1)
    task1 = Task.create_task(
        name="Predecessor",
        start_date=base_date,
        end_date=base_date + timedelta(days=3)
    )
    
    task2 = Task.create_task(
        name="Dependent",
        start_date=base_date + timedelta(days=4),
        end_date=base_date + timedelta(days=8),
        dependencies=[task1.id]
    )
    
    project = Project(name="Test Project", tasks=[task1, task2])
    return {'project': project, 'predecessor': task1, 'dependent': task2}


@when("the predecessor task is removed", target_fixture="project_after_predecessor_removal")
def remove_predecessor_task(project_with_dependencies):
    project = project_with_dependencies['project']
    predecessor = project_with_dependencies['predecessor']
    
    project.remove_task(predecessor.id)
    return project


@then("the dependent task should have no dependencies")
def check_dependent_task_no_dependencies(project_after_predecessor_removal):
    # Find the remaining task (should be the dependent one)
    remaining_task = project_after_predecessor_removal.tasks[0]
    assert remaining_task.dependency_ids == []


@when("getting a task by its ID", target_fixture="retrieved_task")
def get_task_by_id(project_with_tasks_for_removal):
    project = project_with_tasks_for_removal['project']
    task1 = project_with_tasks_for_removal['task1']
    return project.get_task_by_id(task1.id)


@then("the correct task should be returned")
def check_correct_task_returned(retrieved_task, project_with_tasks_for_removal):
    assert retrieved_task.name == project_with_tasks_for_removal['task1'].name


@then("getting non-existent task should return None")
def check_nonexistent_task_returns_none(project_with_tasks_for_removal):
    project = project_with_tasks_for_removal['project']
    result = project.get_task_by_id("non-existent-id")
    assert result is None


@when("getting dependencies for a dependent task", target_fixture="dependencies_result")
def get_dependencies(project_with_dependencies):
    project = project_with_dependencies['project']
    dependent = project_with_dependencies['dependent']
    return project.get_dependencies(dependent.id)


@then("all direct dependencies should be returned")
def check_all_dependencies_returned(dependencies_result, project_with_dependencies):
    assert len(dependencies_result) == 1
    assert dependencies_result[0].id == project_with_dependencies['predecessor'].id


@when("getting dependents for a predecessor task", target_fixture="dependents_result")
def get_dependents(project_with_dependencies):
    project = project_with_dependencies['project']
    predecessor = project_with_dependencies['predecessor']
    return project.get_dependents(predecessor.id)


@then("all dependent tasks should be returned")
def check_all_dependents_returned(dependents_result, project_with_dependencies):
    assert len(dependents_result) == 1
    assert dependents_result[0].id == project_with_dependencies['dependent'].id


# SERIALIZATION TESTS
@given("a task with all fields for serialization", target_fixture="task_with_all_fields")
def task_with_all_fields():
    base_date = datetime(2024, 1, 1)
    end_date = base_date + timedelta(days=9)
    return Task(
        id="test123",
        name="Test Task",
        start_date=base_date,
        end_date=end_date,
        progress=25,
        dependencies=["dep1"],
        color="#3498db",
        is_milestone=False
    )


@when("serialized to dict with all fields", target_fixture="serialized_task")
def serialize_task_to_dict(task_with_all_fields):
    return task_with_all_fields.to_dict()


@then("the dict should contain all fields with correct values")
def check_serialized_task_dict(serialized_task):
    assert serialized_task['id'] == "test123"
    assert serialized_task['name'] == "Test Task"
    assert serialized_task['start_date'] == "2024-01-01T00:00:00"
    assert serialized_task['end_date'] == "2024-01-10T00:00:00"
    assert serialized_task['progress'] == 25
    assert serialized_task['color'] == "#3498db"
    assert serialized_task['is_milestone'] is False


@given("a task dictionary for deserialization", target_fixture="task_dict")
def task_dict():
    return {
        'id': 'test123',
        'name': 'Test Task',
        'start_date': '2024-01-01T00:00:00',
        'end_date': '2024-01-10T00:00:00',
        'progress': 25,
        'dependencies': ['dep1'],
        'color': '#3498db',
        'is_milestone': False
    }


@when("deserialized to Task object", target_fixture="deserialized_task")
def deserialize_task(task_dict):
    return Task.from_dict(task_dict)


@then("all task fields should be correctly restored")
def check_deserialized_task_fields(deserialized_task):
    assert deserialized_task.id == "test123"
    assert deserialized_task.name == "Test Task"
    assert deserialized_task.start_date == datetime(2024, 1, 1)
    assert deserialized_task.end_date == datetime(2024, 1, 10)
    assert deserialized_task.progress == 25
    assert deserialized_task.dependency_ids == ['dep1']
    assert deserialized_task.color == '#3498db'
    assert deserialized_task.is_milestone is False


@given("a project with tasks for serialization", target_fixture="project_for_serialization")
def project_for_serialization():
    base_date = datetime(2024, 1, 1)
    task1 = Task.create_task(
        name="Task 1",
        start_date=base_date,
        end_date=base_date + timedelta(days=3)
    )
    
    task2 = Task.create_task(
        name="Task 2",
        start_date=base_date + timedelta(days=4),
        end_date=base_date + timedelta(days=8)
    )
    
    return Project(name="Test Project", tasks=[task1, task2])


@when("serialized to dict", target_fixture="serialized_project")
def serialize_project(project_for_serialization):
    return project_for_serialization.to_dict()


@then("the dict should contain project name, tasks, start_date, and end_date")
def check_serialized_project_dict(serialized_project, project_for_serialization):
    assert serialized_project['name'] == "Test Project"
    assert len(serialized_project['tasks']) == 2
    assert 'start_date' in serialized_project
    assert 'end_date' in serialized_project


@given("a project dictionary", target_fixture="project_dict")
def project_dict():
    return {
        'name': 'Test Project',
        'tasks': [
            {
                'id': 'task1',
                'name': 'Task 1',
                'start_date': '2024-01-01T00:00:00',
                'end_date': '2024-01-03T00:00:00',
                'progress': 0,
                'dependencies': [],
                'color': '#1f6aa5',
                'is_milestone': False
            },
            {
                'id': 'task2',
                'name': 'Task 2',
                'start_date': '2024-01-04T00:00:00',
                'end_date': '2024-01-08T00:00:00',
                'progress': 0,
                'dependencies': ['task1'],
                'color': '#1f6aa5',
                'is_milestone': False
            }
        ],
        'start_date': '2024-01-01T00:00:00',
        'end_date': '2024-01-08T00:00:00'
    }


@when("deserialized to Project object", target_fixture="deserialized_project")
def deserialize_project(project_dict):
    return Project.from_dict(project_dict)


@then("all project fields should be correctly restored")
def check_deserialized_project_fields(deserialized_project):
    assert deserialized_project.name == "Test Project"
    assert len(deserialized_project.tasks) == 2
    assert deserialized_project.start_date == datetime(2024, 1, 1)
    assert deserialized_project.end_date == datetime(2024, 1, 8)


# STATUS TESTS
@given("a task without status specified", target_fixture="task_no_status")
def task_no_status():
    base_date = datetime(2024, 1, 1)
    return Task(id="test", name="Test", start_date=base_date)


@then("the created task status should default to \"Active\"")
def check_status_default_active(task_no_status):
    assert task_no_status.status == "Active"


@then("the task status should default to \"Active\"")
def check_status_default_active_base(task_no_status):
    assert task_no_status.status == "Active"


@given(parsers.parse('valid status values "{status1}" and "{status2}"'), target_fixture="valid_statuses")
def valid_statuses(status1, status2):
    return [status1, status2]


@when("creating tasks with these statuses", target_fixture="tasks_with_valid_statuses")
def create_tasks_with_valid_statuses(valid_statuses):
    base_date = datetime(2024, 1, 1)
    tasks = []
    for status in valid_statuses:
        task = Task(id=f"test_{status}", name=f"Test {status}", start_date=base_date, status=status)
        tasks.append(task)
    return tasks


@then("the tasks should have the specified statuses")
def check_tasks_have_specified_statuses(tasks_with_valid_statuses, valid_statuses):
    for i, status in enumerate(valid_statuses):
        assert tasks_with_valid_statuses[i].status == status


@given("an invalid status value", target_fixture="invalid_status")
def invalid_status():
    return "Invalid"


@when("creating a task with this status", target_fixture="task_with_invalid_status")
def create_task_with_invalid_status(invalid_status):
    base_date = datetime(2024, 1, 1)
    return Task(id="test", name="Test", start_date=base_date, status=invalid_status)


@then("the task status should default to \"Active\"")
def check_invalid_status_defaults_to_active(task_with_invalid_status):
    assert task_with_invalid_status.status == "Active"


@then("the invalid task status should default to \"Active\"")
def check_invalid_status_defaults_to_active_fallback(task_with_invalid_status):
    assert task_with_invalid_status.status == "Active"


@given('a task with status "Draft"', target_fixture="task_with_draft_status")
def task_with_draft_status():
    base_date = datetime(2024, 1, 1)
    return Task(id="test", name="Test", start_date=base_date, status="Draft")


@when("serialized to dict to check status", target_fixture="serialized_task_with_status")
def serialize_task_with_status_to_dict(task_with_draft_status):
    return task_with_draft_status.to_dict()


@then("the dict should include the status field")
def check_serialized_task_includes_status(serialized_task_with_status):
    assert 'status' in serialized_task_with_status
    assert serialized_task_with_status['status'] == "Draft"


@given("a task dict with status \"Draft\" for deserialization", target_fixture="task_dict_with_status")
def task_dict_with_status():
    return {
        'id': 'test',
        'name': 'Test',
        'start_date': '2024-01-01T00:00:00',
        'end_date': None,
        'progress': 0,
        'dependencies': [],
        'color': '#1f6aa5',
        'is_milestone': False,
        'task_type': 'Task',
        'parent_task_id': None,
        'duration': None,
        'priority': 'Normal',
        'status': 'Draft',
        'shape': 'Default',
        'show_in_timeline': True,
        'earliest_begin': None,
        'scheduling_options': 'End date is calculated',
        'details': '',
        'calendar_id': None,
        'style': None
    }


@when("deserialized to Task to check status", target_fixture="deserialized_task_with_status")
def deserialize_task_with_status(task_dict_with_status):
    return Task.from_dict(task_dict_with_status)


@then("the task should have status \"Draft\"")
def check_deserialized_task_has_draft_status(deserialized_task_with_status):
    assert deserialized_task_with_status.status == "Draft"


@given("a task dict without status", target_fixture="task_dict_without_status")
def task_dict_without_status():
    return {
        'id': 'test',
        'name': 'Test',
        'start_date': '2024-01-01T00:00:00',
        'end_date': None,
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
        'earliest_begin': None,
        'scheduling_options': 'End date is calculated',
        'details': '',
        'calendar_id': None,
        'style': None
    }


@when("deserialized to Task", target_fixture="deserialized_task_without_status")
def deserialize_task_without_status(task_dict_without_status):
    return Task.from_dict(task_dict_without_status)


@then("the deserialized task status should be \"Active\"")
def check_deserialized_task_defaults_to_active(deserialized_task_without_status):
    assert deserialized_task_without_status.status == "Active"

# ---------------------------------------------------------------------------
# Resource assignments through the dictionary, and the property-call guard
#
# Restored from test_models.py. The status round-trips came across; these did
# not, and nothing else in the suite covers a task's assignments surviving
# to_dict/from_dict, the old single-resource fields being converted on load,
# or the guard that stops a property being called as a method.
# ---------------------------------------------------------------------------

@given("a task carrying two resource assignments",
       target_fixture="assigned_task")
def a_task_carrying_two_resource_assignments():
    """A named resource and a team, each with hours and a split."""
    assignments = [
        {'resource_id': 'r1', 'estimated_hours': 10.5,
         'resource_split': 50.0},
        {'resource_id': 't1', 'estimated_hours': 2.0,
         'resource_split': 25.0},
    ]
    task = Task(id="test", name="Test", start_date=datetime(2024, 1, 1),
                resource_assignments=assignments)
    return task, assignments


@when("the task is serialized and read back", target_fixture="round_tripped")
def the_task_is_serialized_and_read_back(assigned_task):
    """Out through to_dict and back through from_dict."""
    task, assignments = assigned_task
    task_dict = task.to_dict()
    return task_dict, Task.from_dict(task_dict), assignments


@then("the read-back assignments should equal the originals")
def check_assignments_round_trip(round_tripped):
    """The dict carries them, and the rebuilt task holds them."""
    task_dict, restored, assignments = round_tripped
    assert task_dict['resource_assignments'] == assignments
    assert restored.resource_assignments == assignments


@given("a task dict with the old resource_id, estimated_hours and split",
       target_fixture="legacy_resource_dict")
def a_task_dict_with_the_old_resource_fields():
    """A file saved before a task could hold several resources."""
    return {
        'id': 'test', 'name': 'Test',
        'start_date': datetime(2024, 1, 1).isoformat(),
        'progress': 0,
        'dependencies': [],
        'color': '#1f6aa5',
        'is_milestone': False,
        'resource_id': 'r1',
        'estimated_hours': 8.0,
        'resource_split': 100.0,
    }


@when("the legacy dict is deserialized to Task",
      target_fixture="deserialized_task")
def the_legacy_dict_is_deserialized(legacy_resource_dict):
    """Read back into a task, which the loader converts."""
    return Task.from_dict(legacy_resource_dict)


@then("the task should carry one assignment built from those fields")
def check_legacy_fields_converted(deserialized_task):
    """The three old fields become the one assignment they described."""
    assert deserialized_task.resource_assignments == [{
        'resource_id': 'r1',
        'estimated_hours': 8.0,
        'resource_split': 100.0,
    }]


@when("every source file is scanned for calls to a model property",
      target_fixture="property_call_offenders")
def scan_for_property_calls():
    """
    Every place a Task or Project property is called rather than read.

    A property read looks like task.duration_days; called as a method it is
    task.duration_days(), which returns the value and then tries to call it -
    a bug that hides until the line runs. Found by walking the syntax tree
    rather than by grepping, so a name that is a property on one class and a
    method on another is not a false alarm.
    """
    import ast
    import pathlib

    from gantt_app import models

    properties = {
        name for cls in (models.Task, models.Project)
        for name, value in vars(cls).items()
        if isinstance(value, property)
    }
    # The guard is only worth having if it knows about a real one
    assert 'duration_days' in properties

    offenders = []
    root = pathlib.Path(models.__file__).parent.parent
    for path in sorted(root.rglob('*.py')):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr in properties):
                offenders.append(
                    f"{path.relative_to(root)}:{node.lineno} "
                    f"calls .{node.func.attr}()")
    return offenders


@then("no file should call one")
def check_no_property_is_called(property_call_offenders):
    """A property is read, not called."""
    assert property_call_offenders == [], property_call_offenders
