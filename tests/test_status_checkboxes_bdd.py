"""
pytest-bdd tests for the two status checkboxes (issue #36).

Run with:
    python3 -m pytest tests/test_status_checkboxes_bdd.py -q

The model scenarios need no display; the editor ones skip without
one. Converted from test_status_checkboxes.py - every case carried
over.
"""
import json
from datetime import datetime
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Project, Task

pytestmark = [
    pytest.mark.status_checkboxes,
]

scenarios("features/status_checkboxes.feature")


def _display_available() -> bool:
    try:
        import tkinter
        root = tkinter.Tk()
    except Exception:
        return False
    root.destroy()
    return True


HAVE_DISPLAY = _display_available()

BASE = datetime(2026, 1, 1)


def _task(**kwargs):
    kwargs.setdefault("id", "001")
    kwargs.setdefault("name", "A")
    kwargs.setdefault("start_date", BASE)
    return Task(**kwargs)


# ------------------------------------------------------------------
# GIVEN - the model
# ------------------------------------------------------------------

@given("a plain task", target_fixture="ctx")
def a_plain_task():
    return SimpleNamespace(task=_task())


@given(parsers.parse('a task with status "{status}"'), target_fixture="ctx")
def a_task_with_a_status(status):
    return SimpleNamespace(task=_task(status=status))


@given("an inactive task that remembers estimated", target_fixture="ctx")
def an_inactive_task_remembering_estimated():
    return SimpleNamespace(task=_task(status="Inactive", estimated=True))


@given(parsers.parse('a task saved as "{status}" without the flag'),
       target_fixture="ctx")
def a_task_saved_before_the_flag(status):
    ctx = SimpleNamespace()
    ctx.data = _task(status=status).to_dict()
    ctx.data.pop("estimated", None)
    return ctx


# ------------------------------------------------------------------
# WHEN - the model
# ------------------------------------------------------------------

@when("the task is saved and loaded again")
def the_task_round_trips(ctx):
    ctx.task = Task.from_dict(json.loads(json.dumps(ctx.task.to_dict())))


@when("the task is loaded")
def the_task_is_loaded(ctx):
    ctx.task = Task.from_dict(ctx.data)


# ------------------------------------------------------------------
# THEN - the model
# ------------------------------------------------------------------

@then(parsers.parse('its status is "{status}"'))
def its_status_is(ctx, status):
    assert ctx.task.status == status


@then("it is estimated")
def it_is_estimated(ctx):
    assert ctx.task.estimated


@then("it is not estimated")
def it_is_not_estimated(ctx):
    assert not ctx.task.estimated


# ------------------------------------------------------------------
# GIVEN - the editor, needs a display
# ------------------------------------------------------------------

@given(parsers.parse('the task editor is open on an "{status}" task'),
       target_fixture="ctx")
def the_editor_on_a_task(status):
    if not HAVE_DISPLAY:
        pytest.skip("needs a display")
    import customtkinter as ctk
    from gantt_app.views.taskdialogs import EditTaskDialog
    root = ctk.CTk()
    root.withdraw()
    ctx = SimpleNamespace(root=root, project=Project(name="P"))
    ctx.task = _task(status=status)
    ctx.project.add_task(ctx.task)
    ctx.dialog = EditTaskDialog(root, ctx.task, ctx.project,
                                on_save=lambda t: None,
                                on_delete=lambda i: None)
    ctx.dialog.update_idletasks()
    yield ctx
    try:
        root.destroy()
    except Exception:
        pass


@given("the task editor is open on an inactive task that remembers "
       "estimated", target_fixture="ctx")
def the_editor_on_an_inactive_estimated_task():
    if not HAVE_DISPLAY:
        pytest.skip("needs a display")
    import customtkinter as ctk
    from gantt_app.views.taskdialogs import EditTaskDialog
    root = ctk.CTk()
    root.withdraw()
    ctx = SimpleNamespace(root=root, project=Project(name="P"))
    ctx.task = _task(status="Inactive", estimated=True)
    ctx.project.add_task(ctx.task)
    ctx.dialog = EditTaskDialog(root, ctx.task, ctx.project,
                                on_save=lambda t: None,
                                on_delete=lambda i: None)
    ctx.dialog.update_idletasks()
    yield ctx
    try:
        root.destroy()
    except Exception:
        pass


# ------------------------------------------------------------------
# WHEN / THEN - the editor
# ------------------------------------------------------------------

@when("the inactive box is cleared")
def the_inactive_box_is_cleared(ctx):
    ctx.dialog.inactive_var.set(False)


@when("the estimated box is cleared")
def the_estimated_box_is_cleared(ctx):
    ctx.dialog.estimated_var.set(False)


@then("the estimated box is clear")
def the_estimated_box_is_clear(ctx):
    assert not ctx.dialog.estimated_var.get()


@then("the inactive box is clear")
def the_inactive_box_is_clear(ctx):
    assert not ctx.dialog.inactive_var.get()


@then("the estimated box is ticked")
def the_estimated_box_is_ticked(ctx):
    assert ctx.dialog.estimated_var.get()


@then("the inactive box is ticked")
def the_inactive_box_is_ticked(ctx):
    assert ctx.dialog.inactive_var.get()


@then(parsers.parse('the status reads "{status}"'))
def the_status_reads(ctx, status):
    assert ctx.dialog.status_value() == status


@then("the estimated flag is still held")
def the_estimated_flag_is_held(ctx):
    assert ctx.dialog.estimated_flag()
