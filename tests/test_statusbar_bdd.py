"""
pytest-bdd tests for the footer status bar following the selection of
whichever view is on top.

Run with:
    python3 -m pytest tests/test_statusbar_bdd.py -q

These tests require a display because they build the full GanttApp.
"""
import tkinter as tk

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.deliverable import Deliverable


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

scenarios("features/statusbar.feature")


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


@given("a project with a populated resource pool and tasks")
def a_project_with_a_populated_resource_pool_and_tasks(app):
    from datetime import datetime

    from gantt_app.core.models import Task
    from gantt_app.core.resource_model import (
        CostResource, MaterialResource, Resource, ResourceType, TeamPool,
    )

    project = app.project
    project.tasks.clear()
    repo = project.resource_repository
    repo.resources.clear()
    repo.teams.clear()
    repo.materials.clear()
    repo.costs.clear()

    anna = Resource(id="r1", name="Anna Dev",
                    resource_type=ResourceType.NAMED, role_type="Dev",
                    initials="AD")
    repo.add_resource(anna)
    repo.add_team(TeamPool(id="t1", name="Platform Team"))
    repo.add_material(MaterialResource(id="m1", name="Cement",
                                       material_label="bags"))
    repo.add_cost(CostResource(id="c1", name="Flight"))
    anna.team_memberships["t1"] = 0.5

    build = Task(id="k1", name="Build API",
                 start_date=datetime(2026, 1, 5),
                 end_date=datetime(2026, 1, 7), task_type="Task",
                 resource_assignments=[
                     {"resource_id": "r1", "estimated_hours": 12.0,
                      "resource_split": 100.0}])
    build.__post_init__()
    lay = Task(id="k2", name="Lay Foundations",
               start_date=datetime(2026, 1, 8),
               end_date=datetime(2026, 1, 9), task_type="Task")
    lay.__post_init__()
    project.add_task(build)
    project.add_task(lay)
    project.renumber_task_ids()
    app.update_all()
    app.update_idletasks()


@given(parsers.parse('a deliverable called "{name}"'))
def a_deliverable_called(app, name):
    app.project.deliverables.append(Deliverable(id="d1", name=name))
    app.deliverables_board.refresh()
    app.update_idletasks()


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------

@when(parsers.parse('the task "{name}" is picked in the task list'))
def the_task_is_picked(app, name):
    task = next(t for t in app.project.tasks if t.name == name)
    app.task_list.tree.selection_set(task.id)
    # <<TreeviewSelect>> is queued, and update() on a withdrawn Aqua root
    # is the crash-prone call - run the handler the event would reach.
    app.task_list.on_select(None)
    app.update_idletasks()


@when(parsers.re(r'the "(?P<name>[^"]+)" tab is selected'))
def the_tab_is_selected(app, name):
    app._show_view(name)
    app.update_idletasks()


@when("the Usage Grid toggle is pressed")
def the_usage_grid_toggle_is_pressed(app):
    app.toolbar.toggle_resource_grid()
    app.update_idletasks()


@when(parsers.parse('the resource "{name}" is picked on the board'))
def the_resource_is_picked(app, name):
    entity_id = _entity_id(app, name)
    app.resource_board._select_resource(entity_id)
    app.update_idletasks()


@when(parsers.parse('the usage-grid row for "{name}" is picked'))
def the_usage_row_is_picked(app, name):
    grid = app.resource_board._usage_grid
    iid = _find_row(grid.tree, name)
    grid.tree.selection_set(iid)
    grid._push_selection_status()
    app.update_idletasks()


@when(parsers.parse('a usage-grid task row for "{name}" is picked'))
def a_usage_task_row_is_picked(app, name):
    grid = app.resource_board._usage_grid
    iid = _find_task_row(grid.tree, name)
    grid.tree.selection_set(iid)
    grid._push_selection_status()
    app.update_idletasks()


@when(parsers.parse('the deliverable "{name}" is picked on the board'))
def the_deliverable_is_picked(app, name):
    for item in _all_rows(app.deliverables_board.tree):
        if app.deliverables_board.tree.item(item, "text") == name:
            app.deliverables_board.tree.selection_set(item)
            app.deliverables_board._push_selection_status()
            app.update_idletasks()
            return
    raise AssertionError(f"deliverable row {name!r} not found")


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@then(parsers.parse('the status bar mentions "{text}"'))
def the_status_bar_mentions(app, text):
    shown = app.status_bar.cget("text")
    assert text in shown, f"status bar shows {shown!r}, not {text!r}"


@then(parsers.parse('the status bar does not mention "{text}"'))
def the_status_bar_does_not_mention(app, text):
    shown = app.status_bar.cget("text")
    assert text not in shown, f"status bar shows {shown!r}"


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _entity_id(app, name):
    repo = app.project.resource_repository
    for pool in (repo.resources, repo.teams, repo.materials, repo.costs):
        for entity in pool.values():
            if entity.name == name:
                return entity.id
    raise AssertionError(f"pool entity {name!r} not found")


def _all_rows(tree, parent=""):
    rows = []
    for item in tree.get_children(parent):
        rows.append(item)
        rows.extend(_all_rows(tree, item))
    return rows


def _find_row(tree, text):
    for item in _all_rows(tree):
        if tree.item(item, "text") == text:
            return item
    raise AssertionError(f"row {text!r} not in grid")


def _find_task_row(tree, text):
    for item in _all_rows(tree):
        if item.startswith("task:") and tree.item(item, "text") == text:
            return item
    raise AssertionError(f"task row {text!r} not in grid")
