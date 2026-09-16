"""
pytest-bdd tests for the new-task shortcut's window bindings.

Run with:
    python3 -m pytest tests/test_new_task_shortcut_bdd.py -q

The scenarios drive the real widget, so they skip without a display.
Converted from test_new_task_shortcut.py - every case carried over.
"""
from datetime import datetime
from types import SimpleNamespace
from unittest import mock

import pytest
from pytest_bdd import given, scenarios, then, when

from gantt_app.core.models import Project, Task
from gantt_app.utils.shortcuts import IS_MACOS

pytestmark = [
    pytest.mark.new_task_shortcut,
]

scenarios("features/new_task_shortcut.feature")


def _display_available() -> bool:
    """Whether a Tk window can be opened here."""
    try:
        import tkinter
        root = tkinter.Tk()
        root.destroy()
        return True
    except Exception:
        return False


HAVE_DISPLAY = _display_available()


def _shut_down(root) -> None:
    """
    Take a root down, children first, without raising.

    Destroying a root while a Toplevel is still on it leaves Tk running
    ttk::ThemeChanged against an interpreter that has already gone, which
    floods stderr with "can't invoke event" tracebacks.
    """
    try:
        for child in list(root.children.values()):
            try:
                child.destroy()
            except Exception:
                pass
        root.destroy()
    except Exception:
        pass


def _bindings(root):
    """Every key sequence bound to the window, as Tk spells them."""
    return [sequence for sequence in root.bind() if 'Key' in sequence]


def _stored(root, *sequences):
    """
    How Tk spells these sequences once it has stored them.

    Bound to a window of their own and read straight back, because Tk
    renames a binding as it takes it - <Command-Option-period> comes back
    as <Mod1-Mod2-Key-period> - and the renaming differs by platform.
    Asking Tk rather than writing the answer down keeps this test about
    what is bound rather than about how this Tk happens to spell it.
    """
    import tkinter as tk

    scratch = tk.Toplevel(root)
    scratch.withdraw()
    try:
        for sequence in sequences:
            scratch.bind(sequence, lambda _event: None, add='+')
        return set(scratch.bind())
    finally:
        scratch.destroy()


# ------------------------------------------------------------------
# GIVEN - needs a display
# ------------------------------------------------------------------

@given("a toolbar wired to a task list in one window", target_fixture="ctx")
def a_toolbar_wired_to_a_task_list():
    if not HAVE_DISPLAY:
        pytest.skip("needs a display")
    import customtkinter as ctk
    from gantt_app.utils.undoredo import (
        ProjectStateTracker, UndoRedoManager,
    )
    from gantt_app.views.task_list import DragDropTaskList
    from gantt_app.views.toolbar import Toolbar

    root = ctk.CTk()
    root.withdraw()

    project = Project(name="Plan")
    project.add_task(Task(id="1", name="Only row", task_type="Task",
                          start_date=datetime(2026, 1, 5),
                          end_date=datetime(2026, 1, 6)))

    manager = UndoRedoManager()
    toolbar = Toolbar(root, project, undo_redo_manager=manager)
    task_list = DragDropTaskList(
        root, project,
        project_tracker=ProjectStateTracker(project, manager))
    toolbar.set_task_list(task_list)
    root.update_idletasks()

    yield SimpleNamespace(root=root, project=project, toolbar=toolbar,
                          task_list=task_list)

    _shut_down(root)


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------

@when("the new-task hotkey fires")
def the_new_task_hotkey_fires(ctx):
    ctx.task_list.tree.focus('1')
    with mock.patch.object(type(ctx.task_list), 'create_task') as create:
        ctx.toolbar._hotkey_new_task()
    ctx.create = create


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@then("the window has key bindings")
def the_window_has_key_bindings(ctx):
    assert _bindings(ctx.root)


@then("the window binds the period with the option modifier")
def the_window_binds_the_period(ctx):
    from gantt_app.utils.shortcuts import sequences

    expected = _stored(ctx.root, *sequences('.', alt=True))
    assert expected <= set(_bindings(ctx.root))


@then("the window binds the any-key catch-all with the option modifier")
def the_window_binds_the_catch_all(ctx):
    from gantt_app.utils.shortcuts import any_key_with

    expected = _stored(ctx.root, any_key_with(alt=True))
    assert expected <= set(_bindings(ctx.root))


@then("a bare key net is bound exactly when running on macOS")
def a_bare_key_net_only_on_macos(ctx):
    bare = [sequence for sequence in _bindings(ctx.root)
            if sequence in ('<Key>', '<KeyPress>')]
    assert bool(bare) == IS_MACOS


@then("a task is created as a sibling of the focused row")
def a_task_is_created_at_the_cursor(ctx):
    ctx.create.assert_called_once_with('Task', '1')
