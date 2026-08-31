"""
pytest-bdd tests for the Resource tab.

Run with:
    python3 -m pytest tests/test_resource_bdd.py -q

These tests require a display because they build customtkinter widgets.
"""
import tkinter as tk

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.models import Project, Task
from gantt_app.resource_model import (
    Resource, ResourceRepository, ResourceType, SchedulePattern, TeamPool,
)
from gantt_app.views.assigntask import TaskResourceTab


def _display_available() -> bool:
    try:
        import tkinter
        root = tkinter.Tk()
    except Exception:
        return False
    root.destroy()
    return True


HAVE_DISPLAY = _display_available()

pytestmark = [
    pytest.mark.skipif(not HAVE_DISPLAY, reason="needs a display"),
]

# Load the Gherkin scenarios from tests/features/resource_assignment.feature.
scenarios("features/resource_assignment.feature")


@given("a project with resources and teams", target_fixture="project")
def a_project_with_resources_and_teams():
    repo = ResourceRepository()
    repo.resources["r1"] = Resource(
        id="r1", name="Jane Smith",
        resource_type=ResourceType.NAMED, role_type="Dev",
        weekly_capacity_hours=40.0,
        schedule_pattern=SchedulePattern.STANDARD)
    repo.resources["r2"] = Resource(
        id="r2", name="John Doe",
        resource_type=ResourceType.NAMED, role_type="QA",
        weekly_capacity_hours=40.0,
        schedule_pattern=SchedulePattern.STANDARD)
    repo.teams["t1"] = TeamPool(
        id="t1", name="Core QA Team",
        schedule_pattern=SchedulePattern.STANDARD,
        is_fixed_capacity=True, fixed_hours=80.0)
    project = Project(name="BDD Project", resource_repository=repo)
    return project


@given("a task open in the Resource tab", target_fixture="tab")
def a_task_open_in_the_resource_tab(project):
    import customtkinter as ctk
    from datetime import datetime

    root = ctk.CTk()
    root.withdraw()
    task = Task(
        id="bdd-001", name="BDD Task",
        start_date=datetime(2026, 1, 1),
        end_date=datetime(2026, 1, 10))
    tab = TaskResourceTab(root, project, task)
    tab.update_idletasks()
    yield tab
    root.destroy()


@given("the task already has a resource assignment")
def the_task_already_has_a_resource_assignment(tab):
    tab._on_picked("r1")
    tab.update_idletasks()
    assert len(tab.get_assignments()) == 1


@when(parsers.parse('the user searches for "{text}"'))
def the_user_searches_for(tab, text):
    tab.search_var.set(text)
    tab._on_search()


@when("selects the first matching resource")
def selects_the_first_matching_resource(tab):
    tab._confirm_first()
    tab.update_idletasks()


@when("the user clears the first assignment")
def the_user_clears_the_first_assignment(tab):
    tab._remove(0)
    tab.update_idletasks()


@when(parsers.parse('the user changes the effort to "{hours}"'))
def the_user_changes_the_effort_to(tab, hours):
    # The effort CTkEntry is the only child of the Effort cell frame.
    effort = tab._row_cells[0][3].winfo_children()[0]
    effort.delete(0, tk.END)
    effort.insert(0, hours)
    tab._make_updater(0, "estimated_hours", effort)(None)
    tab.update_idletasks()


@then("the dropdown shows only matching resources or teams")
def the_dropdown_shows_only_matching_resources_or_teams(tab):
    children = tab.dropdown.tree.get_children()
    assert children == ("t1",), f"expected only team t1, got {children}"


@then("the resource appears in the assignments list")
def the_resource_appears_in_the_assignments_list(tab):
    assert len(tab.get_assignments()) == 1
    assert tab.get_assignments()[0]["resource_id"] == "r1"


@then("the assignments list is empty")
def the_assignments_list_is_empty(tab):
    assert tab.get_assignments() == []


@then("the workload reflects the new projected load")
def the_workload_reflects_the_new_projected_load(tab):
    text = tab._workload_labels[0].cget("text")
    assert "100" in text, f"expected 100 in workload text, got {text!r}"
    assert "OVERLOADED" in text or "loaded" in text, f"unexpected text {text!r}"
