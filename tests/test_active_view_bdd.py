"""
pytest-bdd tests for menu items, buttons and shortcuts answering the
view on top (issue #116).

Run with:
    python3 -m pytest tests/test_active_view_bdd.py -q

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

scenarios("features/active_view.feature")


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


@given(parsers.parse('the task "{name}" is picked in the task list'))
def the_task_is_picked(app, name):
    task = next(t for t in app.project.tasks if t.name == name)
    app.task_list.tree.selection_set(task.id)
    app.task_list.on_select(None)
    app.update_idletasks()


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------

@when(parsers.re(r'the "(?P<name>[^"]+)" tab is selected'))
def the_tab_is_selected(app, name):
    _watch_focus(app)
    app._show_view(name)
    # focus_view runs on after_idle; let it land before asking.
    app.update_idletasks()


def _watch_focus(app):
    """
    Record which grid each view switch asks to take the keyboard.

    A withdrawn window never owns the focus, so focus_get() cannot answer
    "which view got the keyboard" - Tk reports None whatever the code did.
    What can be watched is the call: every focus_view ends in focus_force
    on its grid's tree, and the recording is made before _show_view runs.
    """
    trees = [app.task_list.tree, app.deliverables_board.tree,
             app.resource_board.task_tree,
             app.resource_board._usage_grid.tree,
             app.dashboard_frame.canvas]
    calls = []
    for tree in trees:
        original = tree.focus_force
        tree.focus_force = _recording(calls, tree, original)
    calls.append(app)  # marker: the newest entry answers "last asked"
    app._focus_calls = calls


def _recording(calls, tree, original):
    """A focus_force that remembers it was asked, then does its work."""
    def run():
        calls.append(tree)
        return original()
    return run


@when("the Usage Grid toggle is pressed")
def the_usage_grid_toggle_is_pressed(app):
    app.toolbar.toggle_resource_grid()
    app.update_idletasks()


@when("the Copy shortcut runs")
def the_copy_shortcut_runs(app):
    app.toolbar.copy_tasks()
    app.update_idletasks()


@when("the Delete command runs")
def the_delete_command_runs(app):
    # Deleting asks first; the answer here is yes, so the test is about
    # where the command lands rather than whether the reader agreed.
    from unittest import mock

    with mock.patch('gantt_app.views.dialogs.askyesno',
                    return_value=True):
        app.toolbar._delete_selected_tasks()
    app.update_idletasks()


@when("the New Task command runs")
def the_new_task_command_runs(app):
    app.toolbar.add_task()
    app.update_idletasks()


@when("the Dashboard command runs")
def the_dashboard_command_runs(app):
    _watch_focus(app)
    app.toolbar.show_dashboard()
    app.update_idletasks()


@when(parsers.parse('the deliverable "{name}" is picked on the board'))
def the_deliverable_is_picked(app, name):
    def rows(parent=""):
        found = []
        for item in app.deliverables_board.tree.get_children(parent):
            found.append(item)
            found.extend(rows(item))
        return found

    for item in rows():
        if app.deliverables_board.tree.item(item, "text") == name:
            app.deliverables_board.tree.selection_set(item)
            app.deliverables_board._push_selection_status()
            app.update_idletasks()
            return
    raise AssertionError(f"deliverable row {name!r} not found")


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@then("the task grid holds the keyboard focus")
def the_task_grid_holds_focus(app):
    assert app._focus_calls[-1] is app.task_list.tree


@then("the deliverables grid holds the keyboard focus")
def the_deliverables_grid_holds_focus(app):
    assert app._focus_calls[-1] is app.deliverables_board.tree


@then("the resource board's list holds the keyboard focus")
def the_resource_board_holds_focus(app):
    assert app._focus_calls[-1] is app.resource_board.task_tree


@then("the usage grid's list holds the keyboard focus")
def the_usage_grid_holds_focus(app):
    assert app._focus_calls[-1] is app.resource_board._usage_grid.tree


@then("the dashboard canvas holds the keyboard focus")
def the_dashboard_holds_focus(app):
    assert app._focus_calls[-1] is app.dashboard_frame.canvas


@then(parsers.parse('the "{name}" view is on top'))
def the_view_is_on_top(app, name):
    assert app._active_view == name
    shown = app._view_widgets[name]
    assert shown.winfo_manager(), f"{name} is not on screen"


@then("nothing is on the plan's clipboard")
def nothing_on_the_clipboard(app):
    assert app.clipboard_manager.is_empty()


@then(parsers.parse("the plan still has {count:d} tasks"))
def the_plan_still_has_tasks(app, count):
    assert len(app.project.tasks) == count


@then(parsers.parse('there is no deliverable called "{name}"'))
def no_deliverable_called(app, name):
    assert all(d.name != name for d in app.project.deliverables)


@then(parsers.parse('the status bar mentions "{text}"'))
def the_status_bar_mentions(app, text):
    assert text in app.status_bar.cget("text")


@then(parsers.parse('ribbon buttons "{keys}" are disabled'))
def ribbon_buttons_disabled(app, keys):
    for key in keys.split(','):
        button = app.toolbar.icon_toolbar.icon_buttons[key]
        assert str(button.cget('state')) == 'disabled', \
            f"button {key!r} was not greyed"


@then(parsers.parse('ribbon buttons "{keys}" are enabled'))
def ribbon_buttons_enabled(app, keys):
    for key in keys.split(','):
        button = app.toolbar.icon_toolbar.icon_buttons[key]
        assert str(button.cget('state')) == 'normal', \
            f"button {key!r} was not live"
