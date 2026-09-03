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


# ============================================
# PALETTE CONTENT TESTS (no display needed)
# ============================================

@when("checking all palette entries")
def check_all_palette_entries():
    """Return the palette entries for checking."""
    return FULL_PALETTE


@then("every entry value should be a valid hex color")
def check_every_entry_is_hex_color(palette_entries):
    """Check that every palette entry is a valid hex color."""
    for value, _name in palette_entries:
        assert re.match(r'^#[0-9a-f]{6}$', value), f"{value} is not a valid hex color"


@then("every entry should have a non-empty name")
def check_every_entry_has_name(palette_entries):
    """Check that every palette entry has a non-empty name."""
    for _value, name in palette_entries:
        assert name.strip(), f"Name '{name}' is empty or whitespace"


@then("there should be no duplicate color values")
def check_no_duplicate_colors(palette_entries):
    """Check that there are no duplicate color values."""
    values = [value for value, _name in palette_entries]
    assert len(values) == len(set(values)), "Duplicate color values found"


@then("the palette should contain \"#3498db\"")
def check_palette_contains_3498db(palette_entries):
    """Check that palette contains #3498db."""
    values = {value for value, _name in palette_entries}
    assert '#3498db' in values


@then("the palette should contain \"#9b59b6\"")
def check_palette_contains_9b59b6(palette_entries):
    """Check that palette contains #9b59b6."""
    values = {value for value, _name in palette_entries}
    assert '#9b59b6' in values


@then(parsers.parse('the palette should contain "{color}"'))
def check_palette_contains_color(palette_entries, color):
    """Check that palette contains the specified color."""
    values = {value for value, _name in palette_entries}
    assert color in values, f"Color {color} not found in palette"


# ============================================
# COLOR ENTRY WIDGET TESTS
# ============================================

@pytest.fixture
def root():
    """Create a root window for testing."""
    root = ctk.CTk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except tk.TclError:
        pass


@given(parsers.parse('a color entry widget with color "{color}"'),
       target_fixture="color_entry_widget")
def color_entry_widget_with_color(root, color):
    """Create a color entry widget with the specified color."""
    widget = ColorEntry(root, color=color)
    return widget


@given("a color entry widget", target_fixture="color_entry_default")
def color_entry_default_widget(root):
    """Create a default color entry widget."""
    widget = ColorEntry(root)
    return widget


@given("a color entry widget", target_fixture="color_entry_empty")
def color_entry_empty_widget(root):
    """Create an empty color entry widget."""
    widget = ColorEntry(root, color='')
    return widget


@given("a color entry widget with change callback",
       target_fixture="color_entry_with_callback")
def color_entry_with_callback_widget(root):
    """Create a color entry widget with change callback."""
    changes = []
    widget = ColorEntry(root, color='#1abc9c', on_change=changes.append)
    return widget, changes


@given(parsers.parse('a color entry widget with color "{color}" and change callback'),
       target_fixture="color_entry_same_color")
def color_entry_same_color_widget(root, color):
    """Create a color entry widget with the same color and change callback."""
    changes = []
    widget = ColorEntry(root, color=color, on_change=changes.append)
    return widget, changes


# WHEN FIXTURES

@when("the widget is created")
def widget_created(widget):
    """Return the widget after creation."""
    return widget


@when(parsers.parse('setting the color to "{color}"'))
def set_widget_color(widget, color):
    """Set the widget color to the specified value."""
    widget.set(color)
    return widget


@when("setting the default color")
def set_default_color(widget):
    """Set the widget to default color."""
    widget.set_default()
    return widget


@when("getting the color")
def get_widget_color(widget):
    """Get the widget color."""
    return widget.get()


# THEN FIXTURES

@then(parsers.parse('the widget color should be "{color}"'))
def check_widget_color(widget, color):
    """Check that the widget color matches the expected value."""
    assert widget.get() == color


@then("the widget color should be the default color")
def check_widget_color_is_default(widget):
    """Check that the widget color is the default color."""
    assert widget.get() == DEFAULT_COLOR


@then(parsers.parse('the change callback should have been called with "{color}"'))
def check_change_callback_called(widget_and_changes, color):
    """Check that the change callback was called with the expected color."""
    widget, changes = widget_and_changes
    assert changes == [color]


@then("the change callback should not have been called")
def check_change_callback_not_called(widget_and_changes):
    """Check that the change callback was not called."""
    widget, changes = widget_and_changes
    assert changes == []


@then("the color should start with \"#\"")
def check_color_starts_with_hash(color):
    """Check that the color starts with #."""
    assert color.startswith('#')


# ============================================
# COLOR NORMALIZATION TESTS
# ============================================

@when(parsers.parse('normalizing "{color}"'))
def normalize_color(color):
    """Normalize the specified color."""
    return normalise(color)


@then(parsers.parse('the result should be "{expected}"'))
def check_normalization_result(result, expected):
    """Check that the normalization result matches the expected value."""
    assert result == expected


@then("the result should be the default color")
def check_result_is_default_color(result):
    """Check that the result is the default color."""
    assert result == DEFAULT_COLOR


# ============================================
# PALETTE BUILDING TESTS
# ============================================

@when("opening the color picker")
def open_color_picker(widget):
    """Open the color picker popup."""
    return widget.open_picker()


@when("opening the picker first time")
def open_picker_first_time(widget):
    """Open the picker for the first time."""
    first = widget.open_picker()
    return first


@when("opening the picker second time")
def open_picker_second_time(widget):
    """Open the picker for the second time."""
    second = widget.open_picker()
    return second


@when("opening the picker and updating")
def open_picker_and_update(widget):
    """Open the picker and update idletasks."""
    popup = widget.open_picker()
    popup.update_idletasks()
    return popup


@then("the popup should be None")
def check_popup_is_none(widget):
    """Check that the popup is None."""
    assert widget._popup is None


@then("the popup should have buttons for all palette entries")
def check_popup_has_all_buttons(popup):
    """Check that the popup has buttons for all palette entries."""
    assert len(popup._buttons) == len(FULL_PALETTE)


@then("both open calls should return the same popup")
def check_same_popup(first, second):
    """Check that both open calls return the same popup."""
    assert first is second


@then("the popup width should be at least the grid frame required width")
def check_popup_width(popup):
    """Check that popup width is at least grid frame required width."""
    assert int(popup._canvas.cget('width')) >= popup._grid_frame.winfo_reqwidth()


@then("the popup height should be at least the grid frame required height")
def check_popup_height(popup):
    """Check that popup height is at least grid frame required height."""
    assert int(popup._canvas.cget('height')) >= popup._grid_frame.winfo_reqheight()


@then("the scrollbar should not be visible")
def check_scrollbar_not_visible(popup):
    """Check that the scrollbar is not visible."""
    assert popup._scrollbar.winfo_manager() == ""


@then("the swatch buttons should have mouse wheel binding")
def check_swatch_mousewheel_binding(popup):
    """Check that swatch buttons have mouse wheel binding."""
    swatch = next(iter(popup._buttons.values()))
    assert swatch.bind('<MouseWheel>')


# ============================================
# DIALOG COLOR PICKING TESTS
# ============================================

@pytest.fixture
def project():
    """Create a project for testing."""
    return Project(name="Test Project")


@given("a project with a task colored \"#2ecc71\"",
       target_fixture="project_with_colored_task")
def project_with_colored_task_fixture():
    """Create a project with a colored task."""
    project = Project(name="Test Project")
    base = datetime(2026, 1, 1)
    task = Task(id="001", name="Alpha", start_date=base,
                end_date=base + timedelta(days=2), color='#2ecc71')
    project.add_task(task)
    return project


@given("a project with a task", target_fixture="project_with_task")
def project_with_task_fixture():
    """Create a project with a task."""
    project = Project(name="Test Project")
    base = datetime(2026, 1, 1)
    task = Task(id="001", name="Alpha", start_date=base,
                end_date=base + timedelta(days=2))
    project.add_task(task)
    return project


@given("an edit task dialog for the task",
       target_fixture="edit_dialog")
def edit_task_dialog(root, project_with_colored_task):
    """Create an edit task dialog."""
    from gantt_app.views.taskdialogs import EditTaskDialog
    
    task = project_with_colored_task.tasks[0]
    dialog = EditTaskDialog(root, task, project_with_colored_task,
                            on_save=lambda t: None,
                            on_delete=lambda i: None)
    return dialog, task


@given("an edit task dialog for the task",
       target_fixture="edit_dialog_for_saving")
def edit_dialog_for_saving(root, project_with_task):
    """Create an edit task dialog for saving test."""
    from gantt_app.views.taskdialogs import EditTaskDialog
    
    task = project_with_task.tasks[0]
    dialog = EditTaskDialog(root, task, project_with_task,
                            on_save=lambda t: None,
                            on_delete=lambda i: None)
    return dialog, task


@when("setting the color entry to \"#f39c12\"")
def set_dialog_color(edit_dialog):
    """Set the dialog color entry."""
    dialog, task = edit_dialog
    dialog.color_entry.set('#f39c12')
    return edit_dialog


@when("saving the dialog")
def save_dialog(edit_dialog):
    """Save the dialog."""
    dialog, task = edit_dialog
    dialog.save()
    return edit_dialog


@then("the color entry should show \"#2ecc71\"")
def check_color_entry_shows_2ecc71(edit_dialog):
    """Check that the color entry shows the expected color."""
    dialog, task = edit_dialog
    assert dialog.color_entry.get() == '#2ecc71'


@then("the task color should be \"#f39c12\"")
def check_task_color_is_f39c12(edit_dialog):
    """Check that the task color was updated."""
    dialog, task = edit_dialog
    assert task.color == '#f39c12'


@given(parsers.parse('creating a task dialog for "{task_type}" type'),
       target_fixture="create_dialog")
def create_task_dialog(root, task_type):
    """Create a create task dialog for the specified task type."""
    from gantt_app.views.taskdialogs import CreateTaskDialog
    
    dialog = CreateTaskDialog(root, project(), task_type=task_type, on_save=lambda t: None)
    return dialog


@then(parsers.parse('the color entry should default to "{color}"'))
def check_create_dialog_color_default(create_dialog, color):
    """Check that the create dialog color entry defaults to the expected color."""
    assert create_dialog.color_entry.get() == color
    create_dialog.destroy()


# ============================================
# COLUMN SIZING TESTS
# ============================================

@given("a task list with columns", target_fixture="task_list")
def task_list_with_columns(root, project):
    """Create a task list with columns."""
    from gantt_app.views.task_list import DragDropTaskList
    
    task_list = DragDropTaskList(root, project)
    root.update_idletasks()
    return task_list


@when("checking all columns")
def check_all_columns(task_list):
    """Return all column identifiers."""
    return ('#0',) + task_list.tree.cget('columns')


@when(parsers.parse('setting column "{column}" width to {width:d}'))
def set_column_width(task_list, column, width):
    """Set the specified column width."""
    task_list.tree.column(column, width=width)
    return task_list


@when("refreshing the task list")
def refresh_task_list(task_list):
    """Refresh the task list."""
    task_list.update_task_list()
    return task_list


@then("no column should have stretch enabled")
def check_no_columns_stretch(columns):
    """Check that no columns have stretch enabled."""
    for column in columns:
        assert not task_list.tree.column(column, 'stretch'), f"{column} still stretches"


@then("every column should have minimum width greater than 0")
def check_columns_have_min_width(columns):
    """Check that every column has a minimum width."""
    for column in columns:
        assert task_list.tree.column(column, 'minwidth') > 0, column


@then(parsers.parse('the column "{column}" width should still be {width:d}'))
def check_column_width_unchanged(task_list, column, width):
    """Check that the column width is unchanged after refresh."""
    assert task_list.tree.column(column, 'width') == width


@then("the name column should be the widest")
def check_name_column_widest(task_list):
    """Check that the name column (#0) is the widest."""
    columns = ('#0',) + task_list.tree.cget('columns')
    widths = {c: task_list.tree.column(c, 'width') for c in columns}
    assert max(widths, key=widths.get) == '#0'