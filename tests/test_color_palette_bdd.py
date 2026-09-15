"""
pytest-bdd tests for color palette functionality.

Run with:
    python3 -m pytest tests/test_color_palette_bdd.py -q

These tests require a display for widget tests.
"""
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import colorchooser

import customtkinter as ctk
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Project, Task
from gantt_app.views.colorpicker import (
    ColorEntry, DEFAULT_COLOR, normalise,
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

scenarios("features/color_palette.feature")


# ---------------------------------------------------------------------------
# The colour entry
#
# One fixture named widget between all of these. There were four Given steps
# building one, under four names, two of them sharing the step text "a color
# entry widget" - pytest-bdd keeps one definition per step text, so the other
# was never registered and every step asking for widget failed.
# ---------------------------------------------------------------------------

@pytest.fixture
def root():
    """A window to build the entry in."""
    root = ctk.CTk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except tk.TclError:
        pass


@pytest.fixture
def changes():
    """What the change callback was told, for the scenarios that watch it."""
    return []


@given(parsers.parse('a color entry widget with color "{color}"'),
       target_fixture="widget")
def a_color_entry_widget_with_color(root, color, changes):
    """Opened on a colour the scenario names."""
    return ColorEntry(root, color=color, on_change=changes.append)


@given("a color entry widget", target_fixture="widget")
def a_color_entry_widget(root, changes):
    """Opened on whatever it defaults to."""
    return ColorEntry(root, on_change=changes.append)


@given("a color entry widget with empty color", target_fixture="widget")
def a_color_entry_widget_with_empty_color(root, changes):
    """Opened on nothing at all, which is what a new row can carry."""
    return ColorEntry(root, color='', on_change=changes.append)


@given("a color entry widget with change callback", target_fixture="widget")
def a_color_entry_widget_with_change_callback(root, changes):
    """
    On its default colour, so the scenario's choice is a change.

    It was built on #1abc9c - the very colour the scenario then sets it to -
    so the change it exists to report was no change at all. The scenario
    below is the one that means to reselect what is already there, and it
    says so in its own wording.
    """
    return ColorEntry(root, on_change=changes.append)


@given(parsers.parse(
    'a color entry widget with color "{color}" and change callback'),
    target_fixture="widget")
def a_color_entry_widget_with_color_and_callback(root, color, changes):
    """Opened on the colour it will be set to again."""
    return ColorEntry(root, color=color, on_change=changes.append)


@when("the widget is created")
def the_widget_is_created(widget):
    """Built by the Given; this is where the scenario reads."""
    assert widget is not None


@when(parsers.parse('setting the color to "{color}"'))
def setting_the_color_to(widget, color):
    """Choosing a colour."""
    widget.set(color)


@when("setting the default color")
def setting_the_default_color(widget):
    """The Default button."""
    widget.set_default()


@when("getting the color", target_fixture="color")
def getting_the_color(widget):
    """Reading it back."""
    return widget.get()


@then(parsers.parse('the widget color should be "{color}"'))
def check_widget_color(widget, color):
    """What the entry is showing."""
    assert widget.get() == color


@then("the widget color should be the default color")
def check_widget_color_is_default(widget):
    """The blue a row opens in."""
    assert widget.get() == DEFAULT_COLOR


@then(parsers.parse(
    'the change callback should have been called with "{color}"'))
def check_change_callback_called(changes, color):
    """A change is reported once, with what it changed to."""
    assert changes == [color], changes


@then("the change callback should not have been called")
def check_change_callback_not_called(changes):
    """Reselecting the colour it already had is not a change."""
    assert changes == [], changes


@then('the color should start with "#"')
def check_color_starts_with_hash(color):
    """A missing colour reads back as a real one."""
    assert color.startswith('#'), color


# ---------------------------------------------------------------------------
# Normalising what a colour was written as
# ---------------------------------------------------------------------------

@when(parsers.parse('normalizing "{color}"'), target_fixture="result")
def normalizing_a_written_colour(color):
    """A hex value, with or without its hash, or a colour name."""
    return normalise(color)


@when("normalizing empty string", target_fixture="result")
def normalizing_an_empty_string():
    """Which the feature cannot write inside quotes."""
    return normalise('')


@when("normalizing None", target_fixture="result")
def normalizing_none():
    """A row that carries no colour at all."""
    return normalise(None)


@then(parsers.parse('the result should be "{expected}"'))
def check_normalization_result(result, expected):
    """What came back."""
    assert result == expected


@then("the result should be the default color")
def check_result_is_default_color(result):
    """Nothing becomes the blue a row opens in."""
    assert result == DEFAULT_COLOR


# ---------------------------------------------------------------------------
# The picker the entry opens - the platform's own chooser, stubbed
# ---------------------------------------------------------------------------

@pytest.fixture
def chooser_calls():
    """What the stubbed colour chooser was asked with."""
    return []


@when(parsers.parse('opening the picker and the chooser answers "{color}"'))
def opening_picker_chooses(widget, monkeypatch, chooser_calls, color):
    """The chooser comes back with the colour the scenario names."""
    def fake_askcolor(**options):
        chooser_calls.append(options)
        return ((0, 0, 0), color)

    monkeypatch.setattr(colorchooser, 'askcolor', fake_askcolor)
    widget.open_picker()


@when("opening the picker and the chooser is cancelled")
def opening_picker_cancelled(widget, monkeypatch, chooser_calls):
    """Closing it without choosing is a (None, None) answer."""
    def fake_askcolor(**options):
        chooser_calls.append(options)
        return (None, None)

    monkeypatch.setattr(colorchooser, 'askcolor', fake_askcolor)
    widget.open_picker()


@then(parsers.parse('the chooser should have opened on "{color}"'))
def check_chooser_opened_on(chooser_calls, color):
    """It is seeded with the colour the entry shows."""
    assert chooser_calls and chooser_calls[0].get('color') == color


# ---------------------------------------------------------------------------
# The colour on a task, through the dialogs
# ---------------------------------------------------------------------------

def _project_with_task(color=None):
    """A plan holding one task, coloured or not."""
    project = Project(name="Test Project")
    base = datetime(2026, 1, 1)
    task = Task(id="001", name="Alpha", start_date=base,
                end_date=base + timedelta(days=2),
                **({'color': color} if color else {}))
    project.add_task(task)
    return project


@given("a project", target_fixture="project")
def a_project():
    """An empty plan, for the create dialog's defaults."""
    return Project(name="Test Project")


@given(parsers.parse('a project with a task colored "{color}"'),
       target_fixture="project")
def a_project_with_a_coloured_task(color):
    """A task that already carries a colour."""
    return _project_with_task(color)


@given("a project with a task", target_fixture="project")
def a_project_with_a_task():
    """A task on whatever colour it opened with."""
    return _project_with_task()


@given("an edit task dialog for the task", target_fixture="edit_dialog")
def an_edit_task_dialog_for_the_task(root, project):
    """
    The editor, on the plan's one task.

    One step, on whichever project the Given before it made. There were two
    of these under the same step text, so only one was ever registered and
    the scenario reaching for the other's fixture failed.
    """
    from gantt_app.views.taskdialogs import EditTaskDialog

    task = project.tasks[0]
    dialog = EditTaskDialog(root, task, project,
                            on_save=lambda _task: None,
                            on_delete=lambda _id: None)
    return dialog, task


@when(parsers.parse('setting the color entry to "{color}"'))
def setting_the_color_entry_to(edit_dialog, color):
    """Choosing a colour in the editor."""
    dialog, _task = edit_dialog
    dialog.color_entry.set(color)


@when("saving the dialog")
def saving_the_dialog(edit_dialog):
    """Save."""
    dialog, _task = edit_dialog
    dialog.save()


@then(parsers.parse('the color entry should show "{color}"'))
def check_color_entry_shows(edit_dialog, color):
    """The editor opens on the colour the task carries."""
    dialog, _task = edit_dialog
    assert dialog.color_entry.get() == color


@then(parsers.parse('the task color should be "{color}"'))
def check_task_color_is(edit_dialog, color):
    """And saving puts the chosen one on the task."""
    _dialog, task = edit_dialog
    assert task.color == color


@when(parsers.parse('creating a task dialog for "{task_type}" type'),
      target_fixture="create_dialog")
def creating_a_task_dialog_for(root, project, task_type):
    """The create dialog, which colours a new row by its type."""
    from gantt_app.views.taskdialogs import CreateTaskDialog

    return CreateTaskDialog(root, project, task_type=task_type,
                            on_save=lambda _task: None)


@then(parsers.parse('the color entry should default to "{color}"'))
def check_create_dialog_color_default(create_dialog, color):
    """A task opens blue, a milestone orange; see DEFAULT_COLORS."""
    assert create_dialog.color_entry.get() == color
    create_dialog.destroy()


# ---------------------------------------------------------------------------
# The task list's columns
# ---------------------------------------------------------------------------

@given("a task list with columns", target_fixture="task_list")
def a_task_list_with_columns(root):
    """The grid, with the columns it ships with."""
    from gantt_app.views.task_list import DragDropTaskList

    task_list = DragDropTaskList(root, Project(name="Test Project"))
    root.update_idletasks()
    return task_list


@when("checking all columns", target_fixture="columns")
@when("checking all column widths", target_fixture="columns")
def checking_all_columns(task_list):
    """Every column, the name column included."""
    return ('#0',) + tuple(task_list.tree.cget('columns'))


@when(parsers.parse('setting column "{column}" width to {width:d}'))
def setting_a_column_width(task_list, column, width):
    """Dragging a column edge."""
    task_list.tree.column(column, width=width)


@when("refreshing the task list")
def refreshing_the_task_list(task_list):
    """Which rebuilds every row."""
    task_list.update_task_list()


@then("no column should have stretch enabled")
def check_no_columns_stretch(task_list, columns):
    """A stretching column takes the width a reader set by hand."""
    for column in columns:
        assert not task_list.tree.column(column, 'stretch'), column


@then("every column should have minimum width greater than 0")
def check_columns_have_min_width(task_list, columns):
    """A column with no floor can be dragged out of existence."""
    for column in columns:
        assert task_list.tree.column(column, 'minwidth') > 0, column


@then(parsers.parse('the column "{column}" width should still be {width:d}'))
def check_column_width_unchanged(task_list, column, width):
    """A refresh redraws the rows, not the columns."""
    assert task_list.tree.column(column, 'width') == width


@then("the name column should be the widest")
def check_name_column_widest(task_list, columns):
    """It holds the longest text and the indentation as well."""
    widths = {column: task_list.tree.column(column, 'width')
              for column in columns}
    assert max(widths, key=widths.get) == '#0', widths
