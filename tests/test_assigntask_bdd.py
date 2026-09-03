"""
pytest-bdd tests for resource assignment task functionality.

Run with:
    python3 -m pytest tests/test_assigntask_bdd.py -q

These tests require a display for widget tests.
"""
import tkinter as tk
from datetime import datetime
from types import SimpleNamespace

import customtkinter as ctk
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.models import Project, Task
from gantt_app.resource_model import (
    Resource, ResourceRepository, ResourceType, SchedulePattern, TeamPool,
)
from gantt_app.views.assigntask import _resource_load, _workload_text, TaskResourceTab


def _display_available() -> bool:
    try:
        root = tk.Tk()
    except Exception:
        return False
    root.destroy()
    return True


HAVE_DISPLAY = _display_available()

# Only skip widget tests if no display is available
pytestmark = [
    pytest.mark.skipif(not HAVE_DISPLAY, reason="needs a display"),
]

scenarios("features/assigntask.feature")


# FIXTURES FOR HELPER FUNCTION TESTS (no display needed)

@given(parsers.parse("calculating resource load for a resource with no memberships and {capacity:g} weekly capacity"),
       target_fixture="resource_no_memberships")
def resource_with_no_memberships(capacity):
    """Create a resource with no memberships."""
    return Resource(
        id="r1", name="Jane Smith",
        resource_type=ResourceType.NAMED, role_type="Dev",
        weekly_capacity_hours=capacity,
        schedule_pattern=SchedulePattern.STANDARD)


@given(parsers.parse("calculating resource load for a resource with team memberships totaling {total:g} and {capacity:g} weekly capacity"),
       target_fixture="resource_with_memberships")
def resource_with_team_memberships(total, capacity):
    """Create a resource with team memberships totaling the specified amount."""
    # Create memberships that sum to the specified total
    memberships = {}
    if total > 0:
        memberships["team1"] = total
    
    return Resource(
        id="r1", name="Jane Smith",
        resource_type=ResourceType.NAMED, role_type="Dev",
        weekly_capacity_hours=capacity,
        team_memberships=memberships,
        schedule_pattern=SchedulePattern.STANDARD)


@given(parsers.parse("calculating workload text for an overloaded resource with {allocation:g} allocation and {capacity:g} weekly capacity"),
       target_fixture="overloaded_resource")
def overloaded_resource_data(allocation, capacity):
    """Create an overloaded resource for workload text calculation."""
    resource = Resource(
        id="r1", name="Jane Smith",
        resource_type=ResourceType.NAMED, role_type="Dev",
        weekly_capacity_hours=capacity,
        team_memberships={"team1": allocation},
        schedule_pattern=SchedulePattern.STANDARD)
    return resource, [resource]  # resource and resource list


@given(parsers.parse("calculating workload text for an available resource with {allocation:g} allocation and {capacity:g} weekly capacity"),
       target_fixture="available_resource")
def available_resource_data(allocation, capacity):
    """Create an available resource for workload text calculation."""
    resource = Resource(
        id="r1", name="Jane Smith",
        resource_type=ResourceType.NAMED, role_type="Dev",
        weekly_capacity_hours=capacity,
        team_memberships={"team1": allocation},
        schedule_pattern=SchedulePattern.STANDARD)
    return resource, [resource]  # resource and resource list


# WHEN FIXTURES FOR HELPER FUNCTIONS

@when(parsers.parse("calculating resource load for a resource with no memberships and {capacity:g} weekly capacity"))
def calculate_resource_load_no_memberships(resource_no_memberships):
    """Calculate resource load for resource with no memberships."""
    return _resource_load(resource_no_memberships)


@when(parsers.parse("calculating resource load for a resource with team memberships totaling {total:g} and {capacity:g} weekly capacity"))
def calculate_resource_load_with_memberships(resource_with_memberships):
    """Calculate resource load for resource with memberships."""
    return _resource_load(resource_with_memberships)


@when(parsers.parse("calculating workload text for an overloaded resource with {allocation:g} allocation and {capacity:g} weekly capacity"))
def calculate_workload_text_overloaded(overloaded_resource):
    """Calculate workload text for overloaded resource."""
    resource, resource_list = overloaded_resource
    return _workload_text(resource, resource_list)


@when(parsers.parse("calculating workload text for an available resource with {allocation:g} allocation and {capacity:g} weekly capacity"))
def calculate_workload_text_available(available_resource):
    """Calculate workload text for available resource."""
    resource, resource_list = available_resource
    return _workload_text(resource, resource_list)


# THEN FIXTURES FOR HELPER FUNCTIONS

@then(parsers.parse("the used capacity should be {used:g}"))
def check_used_capacity(result, used):
    """Check that the used capacity matches the expected value."""
    if isinstance(result, tuple):
        actual_used, _ = result
        assert actual_used == used
    else:
        assert result == used


@then(parsers.parse("the total capacity should be {capacity:g}"))
def check_total_capacity(result, capacity):
    """Check that the total capacity matches the expected value."""
    if isinstance(result, tuple):
        _, actual_capacity = result
        assert actual_capacity == capacity


@then(parsers.parse('the text should contain "{text}"'))
def check_text_contains(result, text):
    """Check that the result text contains the specified text."""
    if isinstance(result, tuple):
        actual_text, _, _ = result
    else:
        actual_text = result
    assert text in actual_text


@then(parsers.parse("the percentage should be {pct:g}"))
def check_percentage(result, pct):
    """Check that the percentage matches the expected value."""
    if isinstance(result, tuple):
        _, _, actual_pct = result
        assert actual_pct == pct


# FIXTURES FOR WIDGET TESTS (need display)

@pytest.fixture
def resource_repository():
    """Create a resource repository for testing."""
    repo = ResourceRepository()
    repo.resources["r1"] = Resource(
        id="r1", name="Jane Smith",
        resource_type=ResourceType.NAMED, role_type="Dev",
        weekly_capacity_hours=40.0,
        schedule_pattern=SchedulePattern.STANDARD)
    repo.teams["t1"] = TeamPool(
        id="t1", name="Core QA Team",
        schedule_pattern=SchedulePattern.STANDARD,
        is_fixed_capacity=True, fixed_hours=80.0)
    return repo


@pytest.fixture
def project(resource_repository):
    """Create a project for testing."""
    return Project(name="Test Project", resource_repository=resource_repository)


@given("a task with resource assignments", target_fixture="task_with_assignments")
def task_with_resource_assignments(project):
    """Create a task with existing resource assignments."""
    return Task(
        id="001", name="Test Task",
        start_date=datetime(2026, 1, 1),
        end_date=datetime(2026, 1, 10),
        resource_assignments=[
            {"resource_id": "r1", "estimated_hours": 8.0, "resource_split": 50.0},
        ])


@given("an empty task", target_fixture="empty_task")
def empty_task():
    """Create an empty task."""
    return Task(
        id="002", name="Empty",
        start_date=datetime(2026, 1, 1))


@given("a task with multiple resource assignments", target_fixture="task_with_multiple_assignments")
def task_with_multiple_assignments(project):
    """Create a task with multiple resource assignments."""
    return Task(
        id="002", name="Align",
        start_date=datetime(2026, 1, 1),
        resource_assignments=[
            {"resource_id": "r1", "estimated_hours": 8.0, "resource_split": 50.0},
            {"resource_id": "t1", "estimated_hours": 16.0, "resource_split": 100.0},
        ])


@given("a task resource tab for that task", target_fixture="resource_tab")
def task_resource_tab(root, project, task_with_assignments):
    """Create a task resource tab for the specified task."""
    tab = TaskResourceTab(root, project, task_with_assignments)
    tab.update_idletasks()
    return tab


@given("a task resource tab for that task", target_fixture="empty_resource_tab")
def empty_task_resource_tab(root, project, empty_task):
    """Create a task resource tab for the empty task."""
    tab = TaskResourceTab(root, project, empty_task)
    tab.update_idletasks()
    return tab


@given("a task resource tab for that task", target_fixture="multi_assignment_tab")
def multi_assignment_resource_tab(root, project, task_with_multiple_assignments):
    """Create a task resource tab for the task with multiple assignments."""
    tab = TaskResourceTab(root, project, task_with_multiple_assignments)
    tab.update_idletasks()
    return tab


@given("a task resource tab for that task", target_fixture="resource_tab_with_resources")
def task_resource_tab_with_resources(root, project, task_with_assignments):
    """Create a task resource tab with resources for testing."""
    tab = TaskResourceTab(root, project, task_with_assignments)
    tab.update_idletasks()
    return tab


@given("a task resource tab with resources", target_fixture="search_tab")
def task_resource_tab_for_search(root, project, empty_task):
    """Create a task resource tab for search testing."""
    tab = TaskResourceTab(root, project, empty_task)
    tab.update_idletasks()
    return tab


@given("a task resource tab with existing assignments", target_fixture="effort_tab")
def task_resource_tab_for_effort(root, project, task_with_assignments):
    """Create a task resource tab for effort testing."""
    tab = TaskResourceTab(root, project, task_with_assignments)
    tab.update_idletasks()
    return tab


@given("a task resource tab with existing assignments", target_fixture="split_tab")
def task_resource_tab_for_split(root, project, task_with_assignments):
    """Create a task resource tab for split testing."""
    tab = TaskResourceTab(root, project, task_with_assignments)
    tab.update_idletasks()
    return tab


@pytest.fixture
def root():
    """Create a root window for testing."""
    root = ctk.CTk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except tk.TclError:
        pass


# WHEN FIXTURES FOR WIDGET TESTS

@when("the tab is created and updated")
def tab_created_and_updated(resource_tab):
    """Return the tab after creation and update."""
    return resource_tab


@when("a team is picked for assignment")
def pick_team_for_assignment(empty_resource_tab):
    """Pick a team for assignment."""
    empty_resource_tab._on_picked("t1")
    return empty_resource_tab


@when("the assignment is removed")
def remove_assignment(tab):
    """Remove the assignment at index 0."""
    tab._remove(0)
    return tab


@when("the same resource is picked again")
def pick_same_resource_again(resource_tab):
    """Pick the same resource again."""
    resource_tab._on_picked("r1")
    return resource_tab


@when(parsers.parse('the search text is set to "{text}"'))
def set_search_text(search_tab, text):
    """Set the search text."""
    search_tab.search_var.set(text)
    return search_tab


@when("the search is triggered")
def trigger_search(search_tab):
    """Trigger the search."""
    search_tab._on_search()
    return search_tab


@when("the first filtered resource is confirmed")
def confirm_first_resource(search_tab):
    """Confirm the first filtered resource."""
    search_tab._confirm_first()
    return search_tab


@when(parsers.parse("the effort field is changed to {value:d}"))
def change_effort_field(effort_tab, value):
    """Change the effort field to the specified value."""
    entry = SimpleNamespace(get=lambda: str(value))
    effort_tab._make_updater(0, "estimated_hours", entry)(None)
    return effort_tab


@when(parsers.parse("the split field is changed to {value:d}"))
def change_split_field(split_tab, value):
    """Change the split field to the specified value."""
    entry = SimpleNamespace(get=lambda: str(value))
    split_tab._make_updater(0, "resource_split", entry)(None)
    return split_tab


# THEN FIXTURES FOR WIDGET TESTS

@then("the tab should return the same assignments as the task")
def check_roundtrip_assignments(resource_tab, task_with_assignments):
    """Check that the tab returns the same assignments as the original task."""
    assert resource_tab.get_assignments() == task_with_assignments.resource_assignments


@then(parsers.parse("the tab should have {count:d} assignment"))
def check_assignment_count(tab, count):
    """Check that the tab has the expected number of assignments."""
    assert len(tab.get_assignments()) == count


@then(parsers.parse('the assignment resource ID should be "{resource_id}"'))
def check_assignment_resource_id(tab, resource_id):
    """Check that the first assignment has the expected resource ID."""
    assignments = tab.get_assignments()
    assert len(assignments) > 0
    assert assignments[0]["resource_id"] == resource_id


@then("the dropdown should only show the \"t1\" resource")
def check_dropdown_filtered(search_tab):
    """Check that the dropdown only shows the t1 resource after filtering."""
    children = search_tab.dropdown.tree.get_children()
    assert children == ("t1",)


@then(parsers.parse('the assignments should include both "{first}" and "{second}"'))
def check_assignments_include_both(tab, first, second):
    """Check that the assignments include both specified resource IDs."""
    ids = [a["resource_id"] for a in tab.get_assignments()]
    assert first in ids
    assert second in ids


@then(parsers.parse("the first assignment estimated hours should be {hours:g}"))
def check_first_assignment_effort(tab, hours):
    """Check that the first assignment has the expected estimated hours."""
    assignments = tab.get_assignments()
    assert len(assignments) > 0
    assert assignments[0]["estimated_hours"] == hours


@then(parsers.parse("the first assignment resource split should be {split:g}"))
def check_first_assignment_split(tab, split):
    """Check that the first assignment has the expected resource split."""
    assignments = tab.get_assignments()
    assert len(assignments) > 0
    assert assignments[0]["resource_split"] == split


@then("all assignment row cells should have the same width and position")
def check_assignment_cells_align(multi_assignment_tab):
    """Check that all assignment row cells have the same width and position."""
    assert len(multi_assignment_tab._row_cells) == 2
    first = multi_assignment_tab._row_cells[0]
    for row in multi_assignment_tab._row_cells:
        assert len(row) == len(first)
        for i, cell in enumerate(row):
            assert cell.winfo_width() == first[i].winfo_width()
            assert cell.winfo_x() == first[i].winfo_x()