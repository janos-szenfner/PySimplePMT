"""
pytest-bdd tests for the resource usage grid - the Resource Planning
tab's tree-of-assignments face.

Run with:
    python3 -m pytest tests/test_resource_usage_bdd.py -q

These tests require a display because they build the full GanttApp.
"""
import tkinter as tk
from datetime import datetime

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Task
from gantt_app.core.resource_model import (
    CostResource, MaterialResource, Resource, ResourceType, TeamPool,
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

scenarios("features/resource_usage.feature")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _grid(app):
    return app.resource_board._usage_grid


def _task(app, name):
    for task in app.project.tasks:
        if task.name == name:
            return task
    raise AssertionError(f"task {name!r} not found")


def _entity_id(app, name):
    repo = app.project.resource_repository
    for pool in (repo.resources, repo.teams, repo.materials, repo.costs):
        for entity in pool.values():
            if entity.name == name:
                return entity.id
    raise AssertionError(f"pool entity {name!r} not found")


def _rows(tree):
    """(iid, text, values, tags) for every row, in display order."""
    rows = []

    def visit(parent=""):
        for item in tree.get_children(parent):
            rows.append((item, tree.item(item, "text"),
                         tree.item(item, "values"),
                         tree.item(item, "tags")))
            visit(item)
    visit()
    return rows


def _texts_under(tree, parent_iid):
    return [tree.item(i, "text") for i in tree.get_children(parent_iid)]


def _find_row(tree, text):
    for iid, row_text, _values, _tags in _rows(tree):
        if row_text == text:
            return iid
    raise AssertionError(f"row {text!r} not in grid")


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
    bob = Resource(id="r2", name="Bob Builder",
                   resource_type=ResourceType.GENERIC, role_type="Ops")
    repo.add_resource(anna)
    repo.add_resource(bob)
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
                      "resource_split": 100.0},
                     {"resource_id": "c1", "kind": "cost",
                      "cost": 300.0, "actual_cost": 0.0}])
    build.__post_init__()
    lay = Task(id="k2", name="Lay Foundations",
               start_date=datetime(2026, 1, 8),
               end_date=datetime(2026, 1, 9), task_type="Task")
    lay.__post_init__()
    project.add_task(build)
    project.add_task(lay)
    project.renumber_task_ids()
    app.resource_board.refresh()
    app.update_idletasks()


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------

@when(parsers.re(r'the "(?P<name>[^"]+)" tab is selected'))
def the_tab_is_selected(app, name):
    app._show_view(name)
    app.update_idletasks()


@when("the Usage Grid toggle is pressed")
def the_usage_grid_toggle_is_pressed(app):
    app.toolbar.toggle_resource_grid()
    app.update_idletasks()


@when(parsers.re(r'"(?P<entity>[^"]+)" is assigned to "(?P<task>[^"]+)"'))
def an_entity_is_assigned_to_a_task(app, entity, task):
    _grid(app)._assign_tasks(
        [_entity_id(app, entity)], {_task(app, task).id})
    app.update_idletasks()


@when(parsers.re(r'"(?P<task>[^"]+)" is removed from "(?P<entity>[^"]+)"'))
def a_task_is_removed_from_an_entity(app, task, entity):
    _grid(app)._unassign_entity(_entity_id(app, entity),
                                _task(app, task).id)
    app.update_idletasks()


@when(parsers.re(r'"(?P<entity>[^"]+)" is deleted from the pool'))
def an_entity_is_deleted_from_the_pool(app, entity, monkeypatch):
    from gantt_app.views import dialogs
    monkeypatch.setattr(dialogs, "askyesno", lambda *a, **k: True)
    # The id is kept for the assertions after the name is gone from the
    # pool - _entity_id cannot find it then.
    app._deleted_entity_id = _entity_id(app, entity)
    _grid(app).delete_entities([app._deleted_entity_id])
    app.update_idletasks()


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@then("the View page's Resources group is hidden")
def the_resources_group_is_hidden(app):
    group = app.toolbar.icon_toolbar._groups.get(("View", "Resources"))
    assert group is not None
    assert not group.winfo_manager()


@then("the View page's Resources group is shown")
def the_resources_group_is_shown(app):
    group = app.toolbar.icon_toolbar._groups.get(("View", "Resources"))
    assert group is not None
    assert group.winfo_manager() == "pack"


@then("the resource board is showing the usage grid")
def the_board_shows_the_usage_grid(app):
    assert app.resource_board._mode == "grid"
    assert app.toolbar.resource_grid_var.get()


@then("the resource board is showing the matrix")
def the_board_shows_the_matrix(app):
    assert app.resource_board._mode == "matrix"
    assert not app.toolbar.resource_grid_var.get()


@then(parsers.re(
    r'the grid shows "(?P<a>[^"]+)" before "(?P<b>[^"]+)" before '
    r'"(?P<c>[^"]+)" before "(?P<d>[^"]+)" before "(?P<e>[^"]+)"'))
def the_grid_sections_are_ordered(app, a, b, c, d, e):
    top = [text for _iid, text, _v, _t in _rows(_grid(app).tree)
           if not _iid.startswith(("task:", "alias:"))]
    expected = [a, b, c, d, e]
    positions = [top.index(name) for name in expected]
    assert positions == sorted(positions), \
        f"expected {expected} in that order, got {top}"


@then(parsers.re(
    r'"(?P<entity>[^"]+)" expands to a read-only row for '
    r'"(?P<task>[^"]+)"'))
def an_entity_expands_to_its_task(app, entity, task):
    entity_row = _find_row(_grid(app).tree, entity)
    children = _texts_under(_grid(app).tree, entity_row)
    assert task in children
    task_row = _find_row(_grid(app).tree, task)
    assert task_row.startswith("task:")


@then(parsers.re(
    r'"(?P<entity>[^"]+)" expands to a row for "(?P<task>[^"]+)" worth '
    r'"(?P<detail>[^"]+)"'))
def a_cost_entity_expands_to_its_task(app, entity, task, detail):
    entity_row = _find_row(_grid(app).tree, entity)
    for child in _grid(app).tree.get_children(entity_row):
        if _grid(app).tree.item(child, "text") == task:
            values = _grid(app).tree.item(child, "values")
            assert detail in values
            return
    raise AssertionError(f"{task!r} not found under {entity!r}")


@then(parsers.re(
    r'"(?P<member>[^"]+)" appears under "(?P<team>[^"]+)" in italic'))
def a_member_appears_under_its_team_in_italic(app, member, team):
    tree = _grid(app).tree
    team_row = _find_row(tree, team)
    for child in tree.get_children(team_row):
        if tree.item(child, "text") == member:
            assert child.startswith("alias:")
            assert "alias" in tree.item(child, "tags")
            return
    raise AssertionError(f"{member!r} not under {team!r}")


@then(parsers.re(
    r'"(?P<member>[^"]+)" still has her own row in the Named section'))
def the_member_keeps_her_canonical_row(app, member):
    tree = _grid(app).tree
    canonical = [iid for iid, text, _v, _t in _rows(tree)
                 if text == member and iid.startswith("res:")]
    assert canonical, f"{member!r} has no canonical row"


@then(parsers.re(
    r'"(?P<task>[^"]+)" carries "(?P<entity>[^"]+)"'))
def the_task_carries_the_entity(app, task, entity):
    live = _task(app, task)
    entity_id = _entity_id(app, entity)
    assert any(a.get("resource_id") == entity_id
               for a in live.resource_assignments)


@then("undo removes the assignment")
def undo_removes_the_assignment(app):
    assert app.undo_redo_manager.undo()
    live = _task(app, "Lay Foundations")
    assert not any(a.get("resource_id") == "r2"
                   for a in live.resource_assignments)


@then(parsers.re(
    r'"(?P<task>[^"]+)" no longer carries "(?P<entity>[^"]+)"'))
def the_task_no_longer_carries_the_entity(app, task, entity):
    live = _task(app, task)
    entity_id = _entity_id(app, entity)
    assert not any(a.get("resource_id") == entity_id
                   for a in live.resource_assignments)


@then("undo restores the assignment")
def undo_restores_the_assignment(app):
    assert app.undo_redo_manager.undo()
    live = _task(app, "Build API")
    assert any(a.get("resource_id") == "r1"
               for a in live.resource_assignments)


@then(parsers.re(r'the pool no longer holds "(?P<name>[^"]+)"'))
def the_pool_no_longer_holds_the_entity(app, name):
    with pytest.raises(AssertionError):
        _entity_id(app, name)


@then(parsers.re(
    r'"(?P<task>[^"]+)" no longer carries the deleted entity'))
def the_task_no_longer_carries_the_deleted_entity(app, task):
    live = _task(app, task)
    assert not any(a.get("resource_id") == app._deleted_entity_id
                   for a in live.resource_assignments)


@then("undo restores the resource and the assignment")
def undo_restores_resource_and_assignment(app):
    assert app.undo_redo_manager.undo()
    assert _entity_id(app, "Anna Dev") == "r1"
    live = _task(app, "Build API")
    assert any(a.get("resource_id") == "r1"
               for a in live.resource_assignments)
