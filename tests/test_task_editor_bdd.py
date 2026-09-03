"""
pytest-bdd tests for opening a task's editor.

Run with:
    python3 -m pytest tests/test_task_editor_bdd.py -q

These tests require a display because they build the real application.

WHY THIS MODULE EXISTS:
======================
Issue #6: the Name field in the editor could not be typed into. Two faults
underneath it, both of which these scenarios pin.

Every open built another window. Six opens of one row left six identical
dialogs stacked over each other, each racing the others for the input grab -
whichever won took the typing and the rest took nothing, so the window the
reader was looking at did nothing when typed into. That is the reporter's
"after about 6 opens it suddenly becomes uneditable" exactly.

And the form focused nothing when it opened: focus_get() answered None, so
until something was clicked there was nowhere for a keystroke to go.

DEVELOPMENT NOTES:
------------------
The focus scenario forces the window to look mapped and records what is asked
to take the focus. A withdrawn window never becomes viewable and never gets
keyboard focus from the window manager, so asserting on focus_get() here
would assert on the test's own conditions rather than on the code.
"""
import tkinter as tk

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.views.taskdialogs import EditTaskDialog


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

scenarios("features/task_editor.feature")


@given("an application with a plan in it", target_fixture="app")
def an_application_with_a_plan_in_it():
    from gantt_app.main import GanttApp

    app = GanttApp()
    app.withdraw()
    app.update_idletasks()
    assert len(app.project.tasks) >= 2, "the sample plan should have rows"
    yield app
    try:
        app.destroy()
    except tk.TclError:
        pass


@pytest.fixture
def opened():
    """Every window an open returned, in the order they were asked for."""
    return []


def _editors(app):
    """The editor windows currently alive under the application."""
    return [child for child in app.winfo_children()
            if isinstance(child, EditTaskDialog) and child.winfo_exists()]


@when("the user opens the editor for the first task")
@when("the user opens the editor for the first task again")
def the_user_opens_the_first_task(app, opened):
    opened.append(app.edit_task(app.project.tasks[0]))
    app.update_idletasks()


@when("the user opens the editor for the second task")
def the_user_opens_the_second_task(app, opened):
    opened.append(app.edit_task(app.project.tasks[1]))
    app.update_idletasks()


@when(parsers.parse(
    "the user opens the editor for the first task {count:d} times"))
def the_user_opens_the_first_task_repeatedly(app, opened, count):
    for _ in range(count):
        opened.append(app.edit_task(app.project.tasks[0]))
        app.update_idletasks()


@when("the user closes the editor")
def the_user_closes_the_editor(app, opened):
    opened[-1].destroy()
    app.update_idletasks()


@when("the window is mapped")
def the_window_is_mapped(opened):
    """
    Stand in for the window manager, and record what takes the focus.

    A withdrawn window is never viewable, so the retry that waits for it
    would run out rather than focus anything.
    """
    dialog = opened[-1]
    dialog.winfo_viewable = lambda: True
    focused = []
    dialog.name_entry.focus_set = lambda: focused.append(dialog.name_entry)
    dialog._focused_for_test = focused
    dialog._focus_when_visible()


@then("the cursor is in the Name field")
def the_cursor_is_in_the_name_field(opened):
    dialog = opened[-1]
    assert dialog._focused_for_test == [dialog.name_entry], (
        "the form opened with nothing focused, so the first keystroke "
        "went nowhere")


@then("only one editor is open")
def only_one_editor_is_open(app):
    editors = _editors(app)
    assert len(editors) == 1, f"expected one editor, got {len(editors)}"


@then(parsers.parse("{count:d} editors are open"))
def editors_are_open(app, count):
    editors = _editors(app)
    assert len(editors) == count, f"expected {count}, got {len(editors)}"


@then("both opens returned the same window")
def both_opens_returned_the_same_window(opened):
    assert opened[0] is opened[1], "the second open built another window"


@then("the reopened window is a new one")
def the_reopened_window_is_a_new_one(opened):
    assert opened[-1] is not opened[0], (
        "a closed editor was handed back rather than a new one")
