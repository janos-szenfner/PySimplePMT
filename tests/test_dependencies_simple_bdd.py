"""
pytest-bdd tests for task dependency management (simplified version).

Run with:
    python3 -m pytest tests/test_dependencies_simple_bdd.py -q
"""

from datetime import datetime, timedelta
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.models import (
    Dependency, DependencyList, Project, Task,
    DEPENDENCY_TYPE_LABELS,
)


# Load the Gherkin scenarios
scenarios("features/dependencies_simple.feature")


@given("a base date of \"2024-01-01\"")
def base_date():
    return datetime(2024, 1, 1)


@given("a dependency created from a bare task ID", target_fixture="bare_dependency")
def bare_dependency():
    return Dependency.from_any('001')


@given("dependency type labels", target_fixture="dependency_labels")
def dependency_labels():
    return DEPENDENCY_TYPE_LABELS


@given(parsers.parse('dependency with lowercase type "{dep_type}"'), target_fixture="lowercase_dependency")
def lowercase_dependency(dep_type):
    return Dependency('1', dep_type, 'rubber')


@given("dependency with unknown type \"nonsense\"", target_fixture="unknown_dependency")
def unknown_dependency():
    return Dependency('1', 'nonsense', 'nonsense')


@given(parsers.parse('a dependency with type "{dep_type}" and hardness "{hardness}"'), target_fixture="specific_dependency")
def specific_dependency(dep_type, hardness):
    return Dependency('007', dep_type, hardness)


@when("serialized to dict and back", target_fixture="roundtrip_dependency")
def serialize_dependency(specific_dependency):
    return Dependency.from_any(specific_dependency.to_dict())


@given("an empty DependencyList", target_fixture="empty_dependency_list")
def empty_dependency_list():
    return DependencyList()


@when("a bare task ID is appended", target_fixture="dependency_list_with_id")
def append_bare_id():
    deps = DependencyList()
    deps.append('001')
    return deps


@given("a DependencyList containing \"001\"", target_fixture="dependency_list_with_001")
def dependency_list_with_001():
    return DependencyList(['001'])


@given("a task", target_fixture="simple_task")
def simple_task():
    return Task.create_task("T", datetime(2024, 1, 1), datetime(2024, 1, 1) + timedelta(days=5))


@when("assigned a list of bare IDs", target_fixture="task_with_deps")
def assign_bare_ids():
    task = Task.create_task("T", datetime(2024, 1, 1), datetime(2024, 1, 1) + timedelta(days=5))
    task.dependencies = ['001', '002']
    return task


@when("a bare ID is appended to dependencies", target_fixture="task_with_single_dep")
def append_bare_id_to_task():
    task = Task.create_task("T", datetime(2024, 1, 1), datetime(2024, 1, 1) + timedelta(days=5))
    task.dependencies.append('003')
    return task


@when(parsers.parse('a dependency is added with type "{dep_type}" and hardness "{hardness}"'), target_fixture="task_with_typed_dep")
def add_dependency_with_type(dep_type, hardness):
    task = Task.create_task("T", datetime(2024, 1, 1), datetime(2024, 1, 1) + timedelta(days=5))
    task.add_dependency('001', dep_type, hardness)
    return task


@when("the same dependency is added twice with different types", target_fixture="task_with_updated_dep")
def add_dependency_twice():
    task = Task.create_task("T", datetime(2024, 1, 1), datetime(2024, 1, 1) + timedelta(days=5))
    task.add_dependency('001', 'FS', 'Hard')
    task.add_dependency('001', 'SS', 'Rubber')
    return task


@given("a task with a dependency", target_fixture="task_with_dependency")
def task_with_dependency():
    task_obj = Task.create_task("T", datetime(2024, 1, 1), datetime(2024, 1, 1) + timedelta(days=5))
    task_obj.add_dependency('001')
    return task_obj


@when("the dependency is removed")
def remove_dependency(task_with_dependency):
    task_with_dependency.remove_dependency('001')


@given("tasks with multiple hard dependencies", target_fixture="multiple_hard_tasks")
def multiple_hard_tasks():
    project = Project(name="Scheduling")
    first = Task.create_task("First", datetime(2024, 1, 1), datetime(2024, 1, 5))
    project.add_task(first)
    
    third = Task.create_task("Third", datetime(2024, 3, 1), datetime(2024, 3, 5))
    project.add_task(third)
    
    second = Task.create_task("Second", datetime(2024, 1, 22), datetime(2024, 1, 26))
    project.add_task(second)
    
    second.dependencies = []
    second.add_dependency(first.id, 'FS', 'Hard')
    second.add_dependency(third.id, 'FS', 'Hard')
    project.apply_dependency_constraints(second)
    
    return second


@when("rescheduled")
def reschedule_multiple_hard():
    # The rescheduling is already done in the fixture
    pass


@given("a project with tasks having specific dependency types", target_fixture="project_with_typed_deps")
def project_with_typed_deps():
    project = Project(name="Persist")
    first = Task.create_task("First", datetime(2024, 1, 1), datetime(2024, 1, 5))
    project.add_task(first)
    
    second = Task.create_task("Second", datetime(2024, 1, 6), datetime(2024, 1, 10))
    second.add_dependency(first.id, 'SS', 'Rubber')
    project.add_task(second)
    
    return project


@when("serialized and deserialized", target_fixture="roundtrip_project")
def serialize_project(project_with_typed_deps):
    return Project.from_dict(project_with_typed_deps.to_dict())


# THEN STEPS

@then("the dependency type should default to \"FS\"")
def check_default_dep_type(bare_dependency):
    assert bare_dependency.dep_type == 'FS'


@then("the dependency hardness should default to \"Hard\"")
def check_default_dep_hardness(bare_dependency):
    assert bare_dependency.hardness == 'Hard'


@then(parsers.parse('"{dep_type}" should map to "{label}"'))
def check_dep_type_label(dependency_labels, dep_type, label):
    assert dependency_labels[dep_type] == label


@then("the type should be normalized to \"SS\"")
def check_type_normalization(lowercase_dependency):
    assert lowercase_dependency.dep_type == 'SS'


@then("the hardness should be normalized to \"Rubber\"")
def check_hardness_normalization(lowercase_dependency):
    assert lowercase_dependency.hardness == 'Rubber'


@then("the type should default to \"FS\"")
def check_unknown_type_default(unknown_dependency):
    assert unknown_dependency.dep_type == 'FS'


@then("the hardness should default to \"Hard\"")
def check_unknown_hardness_default(unknown_dependency):
    assert unknown_dependency.hardness == 'Hard'


@then("the restored dependency should equal the original")
def check_roundtrip_dependency(specific_dependency, roundtrip_dependency):
    assert roundtrip_dependency == specific_dependency


@then("the list should contain a Dependency object")
def check_list_contains_dependency(dependency_list_with_id):
    assert len(dependency_list_with_id) == 1
    assert isinstance(dependency_list_with_id[0], Dependency)


@then("the dependency should have the correct task ID")
def check_dependency_correct_id(dependency_list_with_id):
    assert dependency_list_with_id[0].task_id == '001'


@then("\"001\" should be in the list")
def check_001_in_list(dependency_list_with_001):
    assert '001' in dependency_list_with_001


@then("\"002\" should not be in the list")
def check_002_not_in_list(dependency_list_with_001):
    assert '002' not in dependency_list_with_001


@then("the task should have the correct dependency IDs")
def check_task_dep_ids(task_with_deps):
    assert task_with_deps.dependency_ids == ['001', '002']


@then("all dependencies should be Dependency objects")
def check_all_deps_are_objects(task_with_deps):
    assert all(isinstance(d, Dependency) for d in task_with_deps.dependencies)


@then("the task should have the appended dependency ID")
def check_task_single_dep_id(task_with_single_dep):
    assert task_with_single_dep.dependency_ids == ['003']


@then("the dependency should have the correct type")
def check_dep_correct_type(task_with_typed_dep):
    dep = task_with_typed_dep.get_dependency('001')
    assert dep.dep_type == 'SS'


@then("the dependency should have the correct hardness")
def check_dep_correct_hardness(task_with_typed_dep):
    dep = task_with_typed_dep.get_dependency('001')
    assert dep.hardness == 'Rubber'


@then("the task should have only one dependency")
def check_single_dependency(task_with_updated_dep):
    assert len(task_with_updated_dep.dependencies) == 1


@then("the dependency should have the latest type")
def check_latest_dep_type(task_with_updated_dep):
    assert task_with_updated_dep.get_dependency('001').dep_type == 'SS'


@then("the dependencies list should be empty")
def check_deps_empty(task_with_dependency):
    task = task_with_dependency
    task.remove_dependency('001')
    assert task.dependencies == []


@then("removing non-existent dependency should return False")
def check_remove_nonexistent(task_with_dependency):
    task = task_with_dependency
    task.remove_dependency('001')  # Remove the existing one first
    assert task.remove_dependency('001') is False


@then("the task should start on the latest hard constraint date")
def check_latest_hard_applies(multiple_hard_tasks):
    assert multiple_hard_tasks.start_date == datetime(2024, 3, 6)


@then("the dependencies should preserve their types and hardness")
def check_dep_serialization_preserved(project_with_typed_deps, roundtrip_project):
    restored_second = roundtrip_project.get_task_by_id(project_with_typed_deps.tasks[1].id)
    link = restored_second.get_dependency(project_with_typed_deps.tasks[0].id)
    assert link.dep_type == 'SS'
    assert link.hardness == 'Rubber'