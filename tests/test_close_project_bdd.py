"""
pytest-bdd tests for File > Close Project (issue #21).

Run with:
    python3 -m pytest tests/test_close_project_bdd.py -q

close_project runs on a Toolbar built without its widgets, so no display
is needed. Converted from test_close_project.py - every case carried over.
"""
from datetime import datetime
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Project, Task
from gantt_app.views.toolbar import Toolbar

pytestmark = [
    pytest.mark.close_project,
]

scenarios("features/close_project.feature")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _toolbar(project, unsaved_choice="discard", save_ok=True):
    toolbar = Toolbar.__new__(Toolbar)
    toolbar.project = project
    toolbar.undo_redo_manager = None      # keeps _forget_the_previous_plan quiet
    toolbar.clipboard_manager = None
    toolbar.current_file_path = "/tmp/plan.json"
    toolbar._changed = False
    toolbar.on_project_changed = lambda: setattr(toolbar, "_changed", True)
    toolbar.master = SimpleNamespace(
        check_unsaved_changes=lambda **k: unsaved_choice,
        save_project=lambda: save_ok,
        mark_clean=lambda: setattr(toolbar, "_marked_clean", True),
    )
    toolbar._marked_clean = False
    return toolbar


# ------------------------------------------------------------------
# GIVEN
# ------------------------------------------------------------------

@given(parsers.parse('a plan called "{name}" holding one task'),
       target_fixture="ctx")
def a_plan_holding_one_task(name):
    project = Project(name=name)
    project.add_task(Task(id="t1", name="A",
                          start_date=datetime(2026, 9, 10)))
    return SimpleNamespace(project=project, toolbar=None)


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------

@when("the project is closed, discarding unsaved work")
def the_project_is_closed_discarding(ctx):
    ctx.toolbar = _toolbar(ctx.project, unsaved_choice="discard")
    ctx.toolbar.close_project()


@when("the project is closed and the save prompt is cancelled")
def the_project_is_closed_but_cancelled(ctx):
    ctx.toolbar = _toolbar(ctx.project, unsaved_choice="cancel")
    ctx.toolbar.close_project()


@when("the project is closed and the save fails")
def the_project_is_closed_but_the_save_fails(ctx):
    ctx.toolbar = _toolbar(ctx.project, unsaved_choice="save",
                           save_ok=False)
    ctx.toolbar.close_project()


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@then("the plan holds no tasks")
def the_plan_holds_no_tasks(ctx):
    assert ctx.project.tasks == []


@then(parsers.parse('the plan is called "{name}"'))
def the_plan_is_called(ctx, name):
    assert ctx.project.name == name


@then("the toolbar holds no file path")
def the_toolbar_holds_no_file_path(ctx):
    assert ctx.toolbar.current_file_path is None


@then("the change was announced")
def the_change_was_announced(ctx):
    assert ctx.toolbar._changed is True


@then("the plan was marked clean")
def the_plan_was_marked_clean(ctx):
    assert ctx.toolbar._marked_clean is True


@then("the plan still holds its one task")
def the_plan_still_holds_its_task(ctx):
    assert [t.id for t in ctx.project.tasks] == ["t1"]


@then(parsers.parse('the plan is still called "{name}"'))
def the_plan_is_still_called(ctx, name):
    assert ctx.project.name == name


@then("the toolbar still holds its file path")
def the_toolbar_still_holds_its_file_path(ctx):
    assert ctx.toolbar.current_file_path == "/tmp/plan.json"
