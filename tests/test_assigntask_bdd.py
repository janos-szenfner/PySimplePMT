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
from gantt_app.views.assigntask import (
    _resource_load, _workload_text, TaskResourceTab,
)


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


# ---------------------------------------------------------------------------
# The helper functions, which need no display
#
# One step per line of the feature. These were written twice - a @given that
# built the resource and a @when of the same wording that used it - and the
# feature says When, so the @given never ran and the @when asked for a
# fixture nothing had made. Every one of these scenarios failed on
# "fixture 'resource_no_memberships' not found".
# ---------------------------------------------------------------------------

def _resource(capacity, memberships=None):
    """One named resource, with the memberships a scenario gives it."""
    return Resource(
        id="r1", name="Jane Smith",
        resource_type=ResourceType.NAMED, role_type="Dev",
        weekly_capacity_hours=capacity,
        team_memberships=memberships or {},
        schedule_pattern=SchedulePattern.STANDARD)


@when(parsers.parse("calculating resource load for a resource with no "
                    "memberships and {capacity:g} weekly capacity"),
      target_fixture="result")
def resource_load_with_no_memberships(capacity):
    """A resource on no teams uses none of its capacity."""
    return _resource_load(_resource(capacity))


@when(parsers.parse("calculating resource load for a resource with team "
                    "memberships totaling {total:g} and {capacity:g} "
                    "weekly capacity"),
      target_fixture="result")
def resource_load_with_memberships(total, capacity):
    """A share of a team is a share of the resource's week."""
    memberships = {"team1": total} if total > 0 else {}
    return _resource_load(_resource(capacity, memberships))


@when(parsers.parse("calculating workload text for an overloaded resource "
                    "with {allocation:g} allocation and {capacity:g} "
                    "weekly capacity"),
      target_fixture="result")
def workload_text_for_an_overloaded_resource(allocation, capacity):
    """More allocated than there are hours in the week."""
    resource = _resource(capacity, {"team1": allocation})
    return _workload_text(resource, [resource])


@when(parsers.parse("calculating workload text for an available resource "
                    "with {allocation:g} allocation and {capacity:g} "
                    "weekly capacity"),
      target_fixture="result")
def workload_text_for_an_available_resource(allocation, capacity):
    """Room left in the week."""
    resource = _resource(capacity, {"team1": allocation})
    return _workload_text(resource, [resource])


@then(parsers.parse("the used capacity should be {used:g}"))
def check_used_capacity(result, used):
    """The hours the memberships come to."""
    actual = result[0] if isinstance(result, tuple) else result
    assert actual == used


@then(parsers.parse("the total capacity should be {capacity:g}"))
def check_total_capacity(result, capacity):
    """The hours there are."""
    assert isinstance(result, tuple), result
    assert result[1] == capacity


@then(parsers.parse('the text should contain "{text}"'))
def check_text_contains(result, text):
    """What the reader is shown."""
    actual = result[0] if isinstance(result, tuple) else result
    assert text in actual, f"{text!r} not in {actual!r}"


@then(parsers.parse("the percentage should be {pct:g}"))
def check_percentage(result, pct):
    """And the number behind it."""
    assert isinstance(result, tuple) and len(result) == 3, result
    assert result[2] == pct


# ---------------------------------------------------------------------------
# The Resource tab, which needs a display
#
# One task fixture and one tab fixture between all the scenarios. There were
# four steps reading "a task resource tab for that task", each making a tab
# under a different name; pytest-bdd keeps one definition per step text, so
# three of those names were never created and the scenarios reaching for them
# failed. The task a tab is built on comes from whichever Given ran before
# it, which is what the wording already says.
# ---------------------------------------------------------------------------

@pytest.fixture
def root():
    """A window to build the tab in."""
    root = ctk.CTk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except tk.TclError:
        pass


@pytest.fixture
def resource_repository():
    """One person and one team to assign."""
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
    """A plan holding them."""
    return Project(name="Test Project",
                   resource_repository=resource_repository)


def _assigned_task(task_id, name, assignments):
    """A task carrying the assignments a scenario asks for."""
    return Task(
        id=task_id, name=name,
        start_date=datetime(2026, 1, 1),
        end_date=datetime(2026, 1, 10),
        resource_assignments=assignments)


@given("a task with resource assignments", target_fixture="task")
@given("a task with existing resource assignments", target_fixture="task")
def a_task_with_resource_assignments():
    """One assignment already on it."""
    return _assigned_task("001", "Test Task", [
        {"resource_id": "r1", "estimated_hours": 8.0,
         "resource_split": 50.0},
    ])


@given("an empty task", target_fixture="task")
def an_empty_task():
    """Nothing assigned yet."""
    return Task(id="002", name="Empty", start_date=datetime(2026, 1, 1))


@given("a task with multiple resource assignments", target_fixture="task")
def a_task_with_multiple_resource_assignments():
    """Two rows in the tab, so their cells can be compared."""
    return _assigned_task("002", "Align", [
        {"resource_id": "r1", "estimated_hours": 8.0,
         "resource_split": 50.0},
        {"resource_id": "t1", "estimated_hours": 16.0,
         "resource_split": 100.0},
    ])


@given("a task resource tab for that task", target_fixture="tab")
def a_task_resource_tab_for_that_task(root, project, task):
    """The tab, on whichever task the Given before it set up."""
    tab = TaskResourceTab(root, project, task)
    tab.update_idletasks()
    return tab


@given("a task resource tab with resources", target_fixture="tab")
@given("a task resource tab with existing assignments", target_fixture="tab")
def a_task_resource_tab_on_an_assigned_task(root, project):
    """
    A tab that opens with one assignment already on it.

    These two scenarios name no task of their own - the wording carries it -
    so the task is made here rather than asked for as a fixture. Asking
    would fail: nothing before them produces one.
    """
    task = _assigned_task("003", "Assigned", [
        {"resource_id": "r1", "estimated_hours": 8.0,
         "resource_split": 50.0},
    ])
    tab = TaskResourceTab(root, project, task)
    tab.update_idletasks()
    return tab


@when("the tab is created and updated")
def the_tab_is_created_and_updated(tab):
    """Already built by the Given; this settles its layout."""
    tab.update_idletasks()


@when("a team is picked for assignment")
def a_team_is_picked_for_assignment(tab):
    """Choosing the team from the dropdown."""
    tab._on_picked("t1")
    tab.update_idletasks()


@when("the assignment is removed")
def the_assignment_is_removed(tab):
    """Clearing the first row."""
    tab._remove(0)
    tab.update_idletasks()


@when("the same resource is picked again")
def the_same_resource_is_picked_again(tab):
    """Which must not assign it twice."""
    tab._on_picked("r1")
    tab.update_idletasks()


@when(parsers.parse('the search text is set to "{text}"'))
def the_search_text_is_set_to(tab, text):
    """Typing into the search box."""
    tab.search_var.set(text)


@when("the search is triggered")
def the_search_is_triggered(tab):
    """And the filter running."""
    tab._on_search()
    tab.update_idletasks()


@when("the first filtered resource is confirmed")
def the_first_filtered_resource_is_confirmed(tab):
    """Enter, on the first match."""
    tab._confirm_first()
    tab.update_idletasks()


@when(parsers.parse("the effort field is changed to {value:d}"))
def the_effort_field_is_changed_to(tab, value):
    """Typing over the hours on the first row."""
    entry = SimpleNamespace(get=lambda: str(value))
    tab._make_updater(0, "estimated_hours", entry)(None)


@when(parsers.parse("the split field is changed to {value:d}"))
def the_split_field_is_changed_to(tab, value):
    """Typing over the split on the first row."""
    entry = SimpleNamespace(get=lambda: str(value))
    tab._make_updater(0, "resource_split", entry)(None)


@then("the tab should return the same assignments as the task")
def check_roundtrip_assignments(tab, task):
    """What went in comes back out."""
    assert tab.get_assignments() == task.resource_assignments


@then(parsers.parse("the tab should have {count:d} assignment"))
@then(parsers.parse("the tab should have {count:d} assignments"))
@then(parsers.parse("the tab should still have {count:d} assignment"))
def check_assignment_count(tab, count):
    """How many rows the tab holds."""
    assert len(tab.get_assignments()) == count


@then(parsers.parse('the assignment resource ID should be "{resource_id}"'))
def check_assignment_resource_id(tab, resource_id):
    """And who the first one names."""
    assignments = tab.get_assignments()
    assert assignments, "no assignments at all"
    assert assignments[0]["resource_id"] == resource_id


@then('the dropdown should only show the "t1" resource')
def check_dropdown_filtered(tab):
    """The filter leaves the one match."""
    children = tab.dropdown.tree.get_children()
    assert children == ("t1",), children


@then(parsers.parse(
    'the assignments should include both "{first}" and "{second}"'))
def check_assignments_include_both(tab, first, second):
    """Confirming a match adds it beside what was there."""
    ids = [row["resource_id"] for row in tab.get_assignments()]
    assert first in ids and second in ids, ids


@then(parsers.parse(
    "the first assignment estimated hours should be {hours:g}"))
def check_first_assignment_effort(tab, hours):
    """The hours typed reach the assignment."""
    assignments = tab.get_assignments()
    assert assignments, "no assignments at all"
    assert assignments[0]["estimated_hours"] == hours


@then(parsers.parse(
    "the first assignment resource split should be {split:g}"))
def check_first_assignment_split(tab, split):
    """And so does the split."""
    assignments = tab.get_assignments()
    assert assignments, "no assignments at all"
    assert assignments[0]["resource_split"] == split


@then("all assignment row cells should have the same width and position")
def check_assignment_cells_align(tab):
    """Two rows of cells line up as one grid."""
    assert len(tab._row_cells) == 2
    first = tab._row_cells[0]
    for row in tab._row_cells:
        assert len(row) == len(first)
        for index, cell in enumerate(row):
            assert cell.winfo_width() == first[index].winfo_width()
            assert cell.winfo_x() == first[index].winfo_x()
