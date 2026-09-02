"""
pytest-bdd tests for utility functions and project helper functionality.

Run with:
    python3 -m pytest tests/test_utils_bdd.py -q
"""

from datetime import datetime, timedelta
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.models import Project, Task


# Load the Gherkin scenarios
scenarios("features/utils.feature")


# BASE DATE FIXTURE
@given('a base date of "2024-01-01"')
def base_date():
    return datetime(2024, 1, 1)


# PROJECT DATE CALCULATION TESTS
@given("a project with tasks having different start dates", target_fixture="project_with_different_dates")
def project_with_different_dates():
    base_date = datetime(2024, 1, 1)
    
    task1 = Task.create_task(
        name="Earliest Task",
        start_date=base_date,
        end_date=base_date + timedelta(days=3)
    )
    
    task2 = Task.create_task(
        name="Middle Task",
        start_date=base_date + timedelta(days=5),
        end_date=base_date + timedelta(days=10)
    )
    
    task3 = Task.create_task(
        name="Latest Task",
        start_date=base_date + timedelta(days=15),
        end_date=base_date + timedelta(days=20)
    )
    
    return Project(name="Date Test", tasks=[task1, task2, task3])


@then("the project start_date should be the earliest task start")
def check_project_earliest_start(project_with_different_dates):
    base_date = datetime(2024, 1, 1)
    assert project_with_different_dates.start_date == base_date


@then("the project end_date should be the latest task end")
def check_project_latest_end(project_with_different_dates):
    base_date = datetime(2024, 1, 1)
    assert project_with_different_dates.end_date == base_date + timedelta(days=20)


@given("an empty project for date testing", target_fixture="empty_project_dates")
def empty_project_dates():
    return Project(name="Empty Project")


@then("the project start_date should be None")
def check_empty_project_start_none(empty_project_dates):
    assert empty_project_dates.start_date is None


@then("the project end_date should be None")
def check_empty_project_end_none(empty_project_dates):
    assert empty_project_dates.end_date is None


@given("a project with a single task for date testing", target_fixture="project_with_single_task_dates")
def project_with_single_task_dates():
    base_date = datetime(2024, 1, 1)
    task = Task.create_task(
        name="Single Task",
        start_date=base_date,
        end_date=base_date + timedelta(days=3)
    )
    return Project(name="Single Task", tasks=[task])


@then("the project start_date should be the task start")
def check_single_task_start(project_with_single_task_dates):
    base_date = datetime(2024, 1, 1)
    assert project_with_single_task_dates.start_date == base_date


@then("the project end_date should be the task end")
def check_single_task_end(project_with_single_task_dates):
    base_date = datetime(2024, 1, 1)
    assert project_with_single_task_dates.end_date == base_date + timedelta(days=3)


# CIRCULAR DEPENDENCY TESTS
@given("a project with circular dependencies", target_fixture="project_with_circular_deps")
def project_with_circular_deps():
    base_date = datetime(2024, 1, 1)
    
    task1 = Task.create_task(
        name="Task 1",
        start_date=base_date,
        end_date=base_date + timedelta(days=3)
    )
    task2 = Task.create_task(
        name="Task 2",
        start_date=base_date + timedelta(days=4),
        end_date=base_date + timedelta(days=8),
        dependencies=[task1.id]
    )
    
    project = Project(name="Circular Test", tasks=[task1, task2])
    
    # Add circular dependency
    task1.dependencies.append(task2.id)
    
    return {'project': project, 'task1': task1, 'task2': task2}


@when("getting dependencies for a task in the circle", target_fixture="circular_deps_result")
def get_dependencies_for_circular_task(project_with_circular_deps):
    project = project_with_circular_deps['project']
    task1 = project_with_circular_deps['task1']
    return project.get_dependencies(task1.id)


@then("it should return only direct dependencies without infinite loop")
def check_no_infinite_loop_circular(circular_deps_result):
    assert len(circular_deps_result) == 1  # Should not infinite loop


# COMPLEX DEPENDENCY TESTS
@given("a project with complex dependency chains", target_fixture="project_with_complex_deps")
def project_with_complex_deps():
    base_date = datetime(2024, 1, 1)
    
    task1 = Task.create_task(
        name="Task 1",
        start_date=base_date,
        end_date=base_date + timedelta(days=3)
    )
    task2 = Task.create_task(
        name="Task 2",
        start_date=base_date + timedelta(days=4),
        end_date=base_date + timedelta(days=8),
        dependencies=[task1.id]
    )
    task3 = Task.create_task(
        name="Task 3",
        start_date=base_date + timedelta(days=9),
        end_date=base_date + timedelta(days=12),
        dependencies=[task2.id]
    )
    task4 = Task.create_task(
        name="Task 4",
        start_date=base_date + timedelta(days=9),
        end_date=base_date + timedelta(days=15),
        dependencies=[task1.id, task2.id]  # Depends on multiple tasks
    )
    
    project = Project(name="Complex", tasks=[task1, task2, task3, task4])
    
    return {'project': project, 'task1': task1, 'task2': task2, 'task3': task3, 'task4': task4}


@given("a project with complex dependency chains for dependents testing", target_fixture="project_with_complex_deps_for_dependents")
def project_with_complex_deps_for_dependents():
    base_date = datetime(2024, 1, 1)
    
    task1 = Task.create_task(
        name="Task 1",
        start_date=base_date,
        end_date=base_date + timedelta(days=3)
    )
    task2 = Task.create_task(
        name="Task 2",
        start_date=base_date + timedelta(days=4),
        end_date=base_date + timedelta(days=8),
        dependencies=[task1.id]
    )
    task3 = Task.create_task(
        name="Task 3",
        start_date=base_date + timedelta(days=9),
        end_date=base_date + timedelta(days=12),
        dependencies=[task2.id]
    )
    task4 = Task.create_task(
        name="Task 4",
        start_date=base_date + timedelta(days=9),
        end_date=base_date + timedelta(days=15),
        dependencies=[task1.id, task2.id]  # Depends on multiple tasks
    )
    
    project = Project(name="Complex", tasks=[task1, task2, task3, task4])
    
    return {'project': project, 'task1': task1, 'task2': task2, 'task3': task3, 'task4': task4}


@when("getting dependencies for a task with multiple dependencies in complex chains", target_fixture="complex_deps_result")
def get_dependencies_for_complex_task(project_with_complex_deps):
    project = project_with_complex_deps['project']
    task4 = project_with_complex_deps['task4']
    return project.get_dependencies(task4.id)


@then("it should return all direct dependencies")
def check_complex_dependencies(complex_deps_result):
    assert len(complex_deps_result) == 2


@when("getting dependents for a task", target_fixture="complex_dependents_result")
def get_dependents_for_task(project_with_complex_deps_for_dependents):
    project = project_with_complex_deps_for_dependents['project']
    task1 = project_with_complex_deps_for_dependents['task1']
    return project.get_dependents(task1.id)


@then("it should return all dependent tasks")
def check_complex_dependents(complex_dependents_result):
    assert len(complex_dependents_result) == 2  # task2 and task4


# TASK DURATION TESTS
@given("tasks with various date ranges", target_fixture="tasks_with_date_ranges")
def tasks_with_date_ranges():
    test_cases = [
        ("Monday alone", datetime(2024, 1, 1), datetime(2024, 1, 1), 1),
        ("Mon to Tue", datetime(2024, 1, 1), datetime(2024, 1, 2), 2),
        ("Mon to Fri", datetime(2024, 1, 1), datetime(2024, 1, 5), 5),
        ("over a weekend", datetime(2024, 1, 1), datetime(2024, 1, 10), 8),
    ]
    
    tasks = []
    for name, start, end, expected_duration in test_cases:
        task = Task(
            id=f"test_{name}",
            name=name,
            start_date=start,
            end_date=end
        )
        task.expected_duration = expected_duration
        tasks.append(task)
    
    return tasks


@then("the duration should be calculated correctly for each task")
def check_duration_calculation(tasks_with_date_ranges):
    for task in tasks_with_date_ranges:
        assert task.duration_days == task.expected_duration


# SERIALIZATION TESTS
@given("a regular task with all fields set", target_fixture="regular_task_all_fields")
def regular_task_all_fields():
    start_date = datetime(2024, 1, 15, 10, 30, 45)
    end_date = datetime(2024, 2, 20, 14, 20, 30)
    
    return Task(
        id="unique-id-123",
        name="Complex Task",
        start_date=start_date,
        end_date=end_date,
        progress=75,
        dependencies=["dep1", "dep2", "dep3"],
        color="#abcdef",
        is_milestone=False
    )


@when("serialized to dict and deserialized back to task", target_fixture="restored_regular_task")
def serialize_deserialize_regular_task(regular_task_all_fields):
    task_dict = regular_task_all_fields.to_dict()
    return Task.from_dict(task_dict)


@then("all fields should be preserved correctly")
def check_roundtrip_preserves_all_fields(restored_regular_task, regular_task_all_fields):
    assert restored_regular_task.id == regular_task_all_fields.id
    assert restored_regular_task.name == regular_task_all_fields.name
    assert restored_regular_task.start_date == regular_task_all_fields.start_date
    assert restored_regular_task.end_date == regular_task_all_fields.end_date
    assert restored_regular_task.progress == regular_task_all_fields.progress
    assert restored_regular_task.dependency_ids == regular_task_all_fields.dependency_ids
    assert restored_regular_task.color == regular_task_all_fields.color
    assert restored_regular_task.is_milestone == regular_task_all_fields.is_milestone


@given("a milestone with all fields set", target_fixture="milestone_with_all_fields")
def milestone_with_all_fields():
    return Task.create_milestone(
        name="Important Milestone",
        date=datetime(2024, 6, 15),
        color="#ff0000",
        dependencies=["task1"]
    )


@when("serialized to dict and deserialized back to milestone", target_fixture="restored_milestone")
def serialize_deserialize_milestone(milestone_with_all_fields):
    milestone_dict = milestone_with_all_fields.to_dict()
    return Task.from_dict(milestone_dict)


@then("all milestone fields should be preserved correctly")
def check_milestone_roundtrip(restored_milestone):
    assert restored_milestone.name == "Important Milestone"
    assert restored_milestone.start_date == datetime(2024, 6, 15)
    assert restored_milestone.end_date is None
    assert restored_milestone.is_milestone is True
    assert restored_milestone.color == "#ff0000"
    assert restored_milestone.dependency_ids == ["task1"]


# CRITICAL PATH TESTS
@given("an empty project", target_fixture="empty_project_cp")
def empty_project_cp():
    return Project(name="Empty")


@then("the critical path should be empty")
def check_empty_critical_path(empty_project_cp):
    critical_path = empty_project_cp.get_critical_path()
    assert critical_path == []


@given("a project with a single task", target_fixture="single_task_project_cp")
def single_task_project_cp():
    base_date = datetime(2024, 1, 1)
    task = Task.create_task(
        name="Only Task",
        start_date=base_date,
        end_date=base_date + timedelta(days=5)
    )
    return {'project': Project(name="Single", tasks=[task]), 'task': task}


@then("the critical path should contain that task")
def check_single_task_critical_path(single_task_project_cp):
    critical_path = single_task_project_cp['project'].get_critical_path()
    assert len(critical_path) == 1
    assert critical_path[0].id == single_task_project_cp['task'].id


@given("a project with parallel tasks", target_fixture="parallel_tasks_project")
def parallel_tasks_project():
    base_date = datetime(2024, 1, 1)
    
    task1 = Task.create_task(
        name="Short Task",
        start_date=base_date,
        end_date=base_date + timedelta(days=3)
    )
    task2 = Task.create_task(
        name="Long Task",
        start_date=base_date,
        end_date=base_date + timedelta(days=10)
    )
    
    return {'project': Project(name="Parallel", tasks=[task1, task2]), 'task2': task2}


@then("the critical path should include the longest task")
def check_parallel_critical_path(parallel_tasks_project):
    critical_path = parallel_tasks_project['project'].get_critical_path()
    assert len(critical_path) >= 1
    task_ids = [t.id for t in critical_path]
    assert parallel_tasks_project['task2'].id in task_ids


@given("a project with complex dependency network", target_fixture="complex_network_project")
def complex_network_project():
    base_date = datetime(2024, 1, 1)
    
    # Task 1 -> Task 2 -> Task 4
    # Task 1 -> Task 3 -> Task 5
    # Task 5 -> Task 6
    
    task1 = Task.create_task(
        name="Start",
        start_date=base_date,
        end_date=base_date + timedelta(days=2)
    )
    task2 = Task.create_task(
        name="Path A-1",
        start_date=base_date + timedelta(days=3),
        end_date=base_date + timedelta(days=5),
        dependencies=[task1.id]
    )
    task3 = Task.create_task(
        name="Path B-1",
        start_date=base_date + timedelta(days=3),
        end_date=base_date + timedelta(days=8),  # Longer path
        dependencies=[task1.id]
    )
    task4 = Task.create_task(
        name="Path A-2",
        start_date=base_date + timedelta(days=6),
        end_date=base_date + timedelta(days=10),
        dependencies=[task2.id]
    )
    task5 = Task.create_task(
        name="Path B-2",
        start_date=base_date + timedelta(days=9),
        end_date=base_date + timedelta(days=12),
        dependencies=[task3.id]
    )
    task6 = Task.create_task(
        name="Final",
        start_date=base_date + timedelta(days=13),
        end_date=base_date + timedelta(days=15),
        dependencies=[task5.id]
    )
    
    return Project(name="Complex", tasks=[task1, task2, task3, task4, task5, task6])


@then("the critical path should follow the longest dependency chain")
def check_complex_critical_path(complex_network_project):
    critical_path = complex_network_project.get_critical_path()
    
    # Critical path should include the longest path
    assert len(critical_path) >= 3
    
    # Verify it's a valid path (all dependencies are satisfied)
    for i in range(1, len(critical_path)):
        current_task = critical_path[i]
        prev_task = critical_path[i-1]
        assert prev_task.id in current_task.dependency_ids