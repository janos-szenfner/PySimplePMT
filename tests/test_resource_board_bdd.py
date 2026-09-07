"""
pytest-bdd tests for the 4-Panel Resource Planning Matrix.

Run with:
    python3 -m pytest tests/test_resource_board_bdd.py -q

These tests require a display because they build the full GanttApp.
"""
import tkinter as tk
from datetime import datetime, timedelta

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.models import Project, Task
from gantt_app.resource_model import (
    Resource, ResourceRepository, ResourceType, SchedulePattern, TeamPool,
)


def _display_available() -> bool:
    try:
        root = tk.Tk()
    except Exception:
        return False
    root.destroy()
    return True


HAVE_DISPLAY = _display_available()

pytestmark = [
    pytest.mark.skipif(not HAVE_DISPLAY, reason="needs a display"),
]

scenarios("features/resource_board.feature")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _find_task(project, name):
    for task in project.tasks:
        if task.name == name:
            return task
    raise AssertionError(f"task {name!r} not found")


def _find_resource(project, name):
    for resource in project.resource_repository.resources.values():
        if resource.name == name:
            return resource
    raise AssertionError(f"resource {name!r} not found")


def _find_team(project, name):
    for team in project.resource_repository.teams.values():
        if team.name == name:
            return team
    raise AssertionError(f"team {name!r} not found")


def _button_text(widget):
    try:
        return widget.cget("text") or ""
    except tk.TclError:
        return ""


def _children_texts(container):
    return [_button_text(w) for w in container.winfo_children()]


def _all_tree_items(tree):
    """Return (text, values) for every item in a ttk.Treeview."""
    result = []
    def visit(parent=""):
        for item in tree.get_children(parent):
            text = tree.item(item, "text")
            values = tree.item(item, "values")
            result.append((text, values))
            visit(item)
    visit()
    return result


def _task_list_texts(app):
    tree = app.resource_board.task_tree
    app.resource_board.update_idletasks()
    return _all_tree_items(tree)


# ------------------------------------------------------------------
# GIVEN
# ------------------------------------------------------------------
@given("the application is started", target_fixture="app")
def the_application_is_started():
    import customtkinter as ctk
    from gantt_app.main import GanttApp

    ctk.set_appearance_mode("light")
    app = GanttApp()
    app.withdraw()
    app.update_idletasks()
    yield app
    try:
        app.destroy()
    except tk.TclError:
        pass


@given("a resource board with a project that has unassigned and assigned tasks")
def a_resource_board_with_a_project_that_has_unassigned_and_assigned_tasks(app):
    _setup_common_project(app.project)

    unassigned1 = Task(
        id="rbt-001", name="Requirements Gathering",
        start_date=datetime(2026, 1, 1),
        end_date=datetime(2026, 1, 2),
        task_type="Task",
    )
    unassigned1.__post_init__()
    app.project.add_task(unassigned1)

    unassigned2 = Task(
        id="rbt-002", name="API Integration",
        start_date=datetime(2026, 1, 3),
        end_date=datetime(2026, 1, 4),
        task_type="Task",
    )
    unassigned2.__post_init__()
    app.project.add_task(unassigned2)

    assigned = Task(
        id="rbt-003", name="Database Migration",
        start_date=datetime(2026, 1, 5),
        end_date=datetime(2026, 1, 6),
        task_type="Task",
        resource_assignments=[{
            "resource_id": "r2",
            "estimated_hours": 16.0,
            "resource_split": 100.0,
        }],
    )
    assigned.__post_init__()
    app.project.add_task(assigned)

    app.project.renumber_task_ids()
    app.resource_board.refresh()
    app.resource_board.update_idletasks()


@given("a resource board with a project that has two unassigned tasks")
def a_resource_board_with_a_project_that_has_two_unassigned_tasks(app):
    _setup_common_project(app.project)

    for name, start in (
        ("Requirements Gathering", datetime(2026, 1, 1)),
        ("API Integration", datetime(2026, 1, 3)),
    ):
        task = Task(
            id=app.project.next_task_id(), name=name,
            start_date=start,
            end_date=start + timedelta(days=1),
            task_type="Task",
        )
        task.__post_init__()
        app.project.add_task(task)

    app.project.renumber_task_ids()
    app.resource_board.refresh()
    app.resource_board.update_idletasks()


@given("a resource board with a project that has resources and a team")
def a_resource_board_with_a_project_that_has_resources_and_a_team(app):
    _setup_common_project(app.project)
    app.resource_board.refresh()
    app.resource_board.update_idletasks()


@given("a resource board with a project that has an assigned task")
def a_resource_board_with_a_project_that_has_an_assigned_task(app):
    _setup_common_project(app.project)

    assigned = Task(
        id="rbt-100", name="Database Migration",
        start_date=datetime(2026, 1, 5),
        end_date=datetime(2026, 1, 6),
        task_type="Task",
        resource_assignments=[{
            "resource_id": "r1",
            "estimated_hours": 16.0,
            "resource_split": 100.0,
        }],
    )
    assigned.__post_init__()
    app.project.add_task(assigned)
    app.project.renumber_task_ids()
    app.resource_board.refresh()
    app.resource_board.update_idletasks()


@given("a resource board with an overloaded resource")
def a_resource_board_with_an_overloaded_resource(app):
    _setup_common_project(app.project)

    overloaded = Task(
        id="rbt-200", name="Overtime Task",
        start_date=datetime(2026, 1, 5),
        end_date=datetime(2026, 1, 5),
        task_type="Task",
        resource_assignments=[{
            "resource_id": "r1",
            "estimated_hours": 60.0,
            "resource_split": 100.0,
        }],
    )
    overloaded.__post_init__()
    app.project.add_task(overloaded)
    app.project.renumber_task_ids()
    app.resource_board.refresh()
    app.resource_board.update_idletasks()


def _setup_common_project(project: Project):
    project.tasks.clear()
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
    project.resource_repository = repo


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------
@when("the user turns on resource planning")
def the_user_turns_on_resource_planning(app):
    app._resource_switch_var.set("on")
    app._on_resource_view_toggled()
    app.update_idletasks()


@when("the user turns off resource planning")
def the_user_turns_off_resource_planning(app):
    app._resource_switch_var.set("off")
    app._on_resource_view_toggled()
    app.update_idletasks()


@when(parsers.parse('the user searches the task list for "{text}"'))
def the_user_searches_the_task_list_for(app, text):
    app.resource_board.backlog_search.delete(0, tk.END)
    app.resource_board.backlog_search.insert(0, text)
    app.resource_board._filter_task_list()
    app.resource_board.update_idletasks()


@when(parsers.parse('the user selects the "{name}" task'))
def the_user_selects_the_task(app, name):
    task = _find_task(app.project, name)
    tree = app.resource_board.task_tree
    tree.selection_set(task.id)
    tree.event_generate("<<TreeviewSelect>>")
    app.resource_board.update()


@when(parsers.parse(
    'the user selects the "{name}" task without rebuilding the task list'))
def the_user_selects_without_rebuilding(app, name, monkeypatch):
    rebuilds = []
    monkeypatch.setattr(
        app.resource_board, "_filter_task_list", lambda: rebuilds.append(True))
    the_user_selects_the_task(app, name)
    assert not rebuilds, "selecting a task rebuilt the tree and risks recursion"


@when(parsers.parse('the user selects the "{name}" resource'))
def the_user_selects_the_resource(app, name):
    entity = _find_resource(app.project, name)
    app.resource_board._select_resource(entity.id)
    app.resource_board.update_idletasks()


@when("the user assigns the selected resource")
def the_user_assigns_the_selected_resource(app):
    app.resource_board._assign_selected()
    app.resource_board.update_idletasks()


@when("the user selects the assigned task in the inspector")
def the_user_selects_the_assigned_task_in_the_inspector(app):
    for task in app.project.tasks:
        if task.resource_assignments:
            app.resource_board._selected_task_id = task.id
            app.resource_board._show_task(task.id)
            app.resource_board.update_idletasks()
            return
    raise AssertionError("no assigned task found")


@when("the user de-assigns the selected task")
def the_user_de_assigns_the_selected_task(app):
    app.resource_board._deassign_selected()
    app.resource_board.update_idletasks()


@when(parsers.parse('the user filters the resource pool to "{filter}"'))
def the_user_filters_the_resource_pool_to(app, filter):
    app.resource_board.pool_filter.set(filter)
    app.resource_board._filter_pool()
    app.resource_board.update_idletasks()


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------
@then(parsers.parse('the footer contains the "{label}" label'))
def the_footer_contains_the_label(app, label):
    texts = []
    for child in app.resource_switch_frame.winfo_children():
        try:
            texts.append(child.cget("text"))
        except (tk.TclError, AttributeError):
            pass
    assert label in texts, f"expected {label!r} in footer labels, got {texts}"


@then(parsers.parse('the footer contains a "{text}" button'))
def the_footer_contains_a_button(app, text):
    assert app.close_button.cget("text") == text


@then('the "Close" button is to the right of the switch')
def the_close_button_is_to_the_right_of_the_switch(app):
    close_col = int(app.close_button.grid_info().get("column", -1))
    switch_col = int(app.resource_switch_frame.grid_info().get("column", -1))
    assert close_col > switch_col, (
        f"Close column {close_col} not to the right of switch column {switch_col}")


@then("the resource planning switch is off")
def the_resource_planning_switch_is_off(app):
    assert app._resource_switch_var.get() == "off"


@then("the resource planning switch is on")
def the_resource_planning_switch_is_on(app):
    assert app._resource_switch_var.get() == "on"


@then("the Task Planning view is on top")
def the_task_planning_view_is_on_top(app):
    assert app._resource_switch_var.get() == "off"
    assert app.content_panes.winfo_exists()
    assert app.resource_board.winfo_exists()


@then("the Resource Planning view is on top")
def the_resource_planning_view_is_on_top(app):
    assert app._resource_switch_var.get() == "on"
    assert app.content_panes.winfo_exists()
    assert app.resource_board.winfo_exists()


@then(parsers.parse('the task list contains "{name}" with status "{status}"'))
def the_task_list_contains_with_status(app, name, status):
    for text, values in _task_list_texts(app):
        if name in text:
            assert status in values[-1], (
                f"expected {name!r} status {status!r}, got {values}")
            return
    raise AssertionError(f"expected task {name!r} in task list")


@then(parsers.parse('the task list shows only the task named "{name}"'))
def the_task_list_shows_only_the_task_named(app, name):
    items = _task_list_texts(app)
    assert len(items) == 1, f"expected one task, got {items}"
    assert name in items[0][0], f"expected {name!r}, got {items[0][0]!r}"


@then(parsers.parse('the task list shows "{name}" with status "{status}"'))
def the_task_list_shows_with_status(app, name, status):
    for text, values in _task_list_texts(app):
        if name in text:
            assert status in values[-1], (
                f"expected {name!r} status {status!r}, got {values}")
            return
    raise AssertionError(f"expected task {name!r} in task list")


@then(parsers.parse('the inspector shows "{text}"'))
def the_inspector_shows(app, text):
    widget = app.resource_board.inspector_text
    widget.configure(state="normal")
    content = widget.get("0.0", "end")
    widget.configure(state="disabled")
    assert text in content, f"expected {text!r} in inspector, got {content!r}"


@then(parsers.parse('the resource pool contains "{name}"'))
def the_resource_pool_contains(app, name):
    texts = _children_texts(app.resource_board.pool_frame.content)
    assert any(name in t for t in texts), (
        f"expected {name!r} in resource pool, got {texts}")


@then(parsers.parse('the resource pool contains only "{name}"'))
def the_resource_pool_contains_only(app, name):
    texts = _children_texts(app.resource_board.pool_frame.content)
    assert len(texts) == 1, f"expected one pool card, got {texts}"
    assert name in texts[0], f"expected {name!r}, got {texts[0]!r}"


@then(parsers.parse('the preview label contains "{name}"'))
def the_preview_label_contains(app, name):
    text = app.resource_board.preview_label.cget("text")
    assert name in text, f"expected {name!r} in preview, got {text!r}"


@then(parsers.parse('the task "{name}" has an assignment to "{resource}"'))
def the_task_has_an_assignment_to(app, name, resource):
    task = _find_task(app.project, name)
    res = _find_resource(app.project, resource)
    assert any(a.get("resource_id") == res.id for a in task.resource_assignments), (
        f"task {name} is not assigned to {resource}")


@then("the task has no resource assignments")
def the_task_has_no_resource_assignments(app):
    for task in app.project.tasks:
        if task.name == "Database Migration":
            assert task.resource_assignments == [], (
                f"task still has assignments: {task.resource_assignments}")
            return
    raise AssertionError("Database Migration task not found")


@then("the heatmap canvas has drawing items")
def the_heatmap_canvas_has_drawing_items(app):
    items = app.resource_board.heatmap_canvas.find_all()
    assert len(items) > 0, "heatmap canvas is empty"


@then(parsers.parse('the heatmap contains text for "{name}"'))
def the_heatmap_contains_text_for(app, name):
    canvas = app.resource_board.heatmap_canvas
    texts = [canvas.itemcget(i, "text")
             for i in canvas.find_all()
             if canvas.type(i) == "text"]
    assert any(name in t for t in texts), (
        f"expected {name!r} in heatmap texts, got {texts}")


@then("the heatmap contains an over-capacity rectangle")
def the_heatmap_contains_an_over_capacity_rectangle(app):
    canvas = app.resource_board.heatmap_canvas
    fills = [canvas.itemcget(i, "fill")
             for i in canvas.find_all()
             if canvas.type(i) == "rectangle"]
    assert "#e74c3c" in fills, (
        f"expected over-capacity red, got {fills}")


@then(parsers.parse('the resource pool card for "{name}" shows a percentage above 100'))
def the_resource_pool_card_for_shows_a_percentage_above_100(app, name):
    texts = _children_texts(app.resource_board.pool_frame.content)
    for text in texts:
        if name in text:
            import re
            match = re.search(r'\((\d+)%', text)
            assert match, f"no percentage found in {text!r}"
            assert int(match.group(1)) > 100, (
                f"expected percentage above 100 in {text!r}")
            return
    raise AssertionError(f"card for {name!r} not found")
