"""
pytest-bdd tests for color palette functionality.

Run with:
    python3 -m pytest tests/test_color_palette_bdd.py -q

These tests require a display for widget tests.
"""
import re
import tkinter as tk
from datetime import datetime, timedelta

import customtkinter as ctk
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.models import Project, Task
from gantt_app.views.colorpicker import (
    ColorEntry, FULL_PALETTE, DEFAULT_COLOR, normalise,
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
# What the palette holds, which needs no display
# ---------------------------------------------------------------------------

@when("checking all palette entries", target_fixture="palette_entries")
def checking_all_palette_entries():
    """The palette, for the Then steps to look through."""
    return FULL_PALETTE


@then("every entry value should be a valid hex color")
def check_every_entry_is_hex_color(palette_entries):
    """A swatch that is not a colour draws nothing."""
    for value, _name in palette_entries:
        assert re.match(r'^#[0-9a-f]{6}$', value), f"{value} is not a colour"


@then("every entry should have a non-empty name")
def check_every_entry_has_name(palette_entries):
    """The name is the tooltip; an empty one says nothing."""
    for value, name in palette_entries:
        assert name.strip(), f"{value} has no name"


@then("there should be no duplicate color values")
def check_no_duplicate_colors(palette_entries):
    """Two swatches of one colour is one swatch and a puzzle."""
    values = [value for value, _name in palette_entries]
    assert len(values) == len(set(values))


@then(parsers.parse('the palette should contain "{color}"'))
def check_palette_contains_color(palette_entries, color):
    """The colours the application itself opens rows in."""
    values = {value for value, _name in palette_entries}
    assert color in values, f"{color} is not in the palette"


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
# The picker the entry opens
# ---------------------------------------------------------------------------

@when("opening the color picker", target_fixture="popup")
@when("opening the picker", target_fixture="popup")
def opening_the_picker(widget):
    """The swatch grid."""
    return widget.open_picker()


@when("opening the picker first time", target_fixture="first")
def opening_the_picker_first_time(widget):
    """Once."""
    return widget.open_picker()


@when("opening the picker second time", target_fixture="second")
def opening_the_picker_second_time(widget):
    """And again, which must not build a second window."""
    return widget.open_picker()


@when("opening the picker and updating", target_fixture="popup")
def opening_the_picker_and_updating(widget):
    """Opened and laid out, so its size can be read."""
    popup = widget.open_picker()
    popup.update_idletasks()
    return popup


@then("the popup should be None")
def check_popup_is_none(widget):
    """Nothing is built until somebody asks for it."""
    assert widget._popup is None


@then("the popup should have buttons for all palette entries")
def check_popup_has_all_buttons(popup):
    """Every colour is reachable."""
    assert len(popup._buttons) == len(FULL_PALETTE)


@then("both open calls should return the same popup")
def check_same_popup(first, second):
    """Opening it twice reuses the window."""
    assert first is second


@then("the popup width should be at least the grid frame required width")
def check_popup_width(popup):
    """It opens at the size of what is in it."""
    assert int(popup._canvas.cget('width')) >= \
        popup._grid_frame.winfo_reqwidth()


@then("the popup height should be at least the grid frame required height")
def check_popup_height(popup):
    """The same, the other way up."""
    assert int(popup._canvas.cget('height')) >= \
        popup._grid_frame.winfo_reqheight()


@then("the scrollbar should not be visible")
def check_scrollbar_not_visible(popup):
    """A palette that fits needs none."""
    assert popup._scrollbar.winfo_manager() == ""


@then("the swatch buttons should have mouse wheel binding")
def check_swatch_mousewheel_binding(popup):
    """The wheel scrolls the grid rather than stopping on a swatch."""
    swatch = next(iter(popup._buttons.values()))
    assert swatch.bind('<MouseWheel>')


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
    """A task opens blue, a milestone red; see DEFAULT_COLORS."""
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
