"""
pytest-bdd end-to-end tests for the baseline management UI.

Run with:
    python3 -m pytest tests/test_baseline_ui_bdd.py -q

These tests require a display because they build the full GanttApp.
"""
import json
import os
import tempfile
import tkinter as tk
from datetime import datetime, timedelta

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.models import Project, Task
from gantt_app.utils.chart_render import render_image


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

scenarios("features/baseline_ui.feature")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _find_task(project, name):
    for task in project.tasks:
        if task.name == name:
            return task
    raise AssertionError(f"task {name!r} not found")


def _tree_values_for_task(task_list, task_id):
    return task_list.tree.item(task_id, "values")


def _tree_display_columns(task_list):
    return task_list.tree.cget("displaycolumns")


def _column_index(task_list, column):
    return list(task_list.tree.cget("columns")).index(column)


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


@given("a project with sample tasks exists")
def a_project_with_sample_tasks_exists(app):
    app.project.tasks = []
    app.project.calendar = app.project.calendar

    task_a = Task(
        id="bui-task-a",
        name="Task A",
        start_date=datetime(2026, 6, 1),
        end_date=datetime(2026, 6, 5),
        task_type="Task",
        duration=5,
    )
    task_a.__post_init__()
    app.project.add_task(task_a)

    task_b = Task(
        id="bui-task-b",
        name="Task B",
        start_date=datetime(2026, 6, 6),
        end_date=datetime(2026, 6, 10),
        task_type="Task",
        duration=5,
    )
    task_b.__post_init__()
    app.project.add_task(task_b)

    app.update_all()
    app.update_idletasks()


@given("the user has set baseline 1 for the entire project")
def the_user_has_set_baseline_1_for_the_entire_project(app):
    app.baseline_manager.set_baseline(app.project, 1)
    app.toolbar._refresh_baseline_views()
    app.update_idletasks()


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------
@when("the user opens the baseline settings tab")
def the_user_opens_the_baseline_settings_tab(app):
    app.toolbar._settings_window = app.toolbar.open_settings("Baseline")
    app.update_idletasks()


@when(parsers.parse('the user renames slot {number:d} to "{name}"'))
def the_user_renames_slot_to(app, number, name):
    settings = app.toolbar._settings_window
    entry = settings._baseline_entries[number]
    entry.delete(0, tk.END)
    entry.insert(0, name)
    settings.update_idletasks()


@when("the user saves the baseline settings")
def the_user_saves_the_baseline_settings(app):
    app.toolbar._settings_window._save_baseline_settings()
    app.toolbar._refresh_baseline_views()
    app.update_idletasks()


@when("the user sets baseline 1 for the entire project")
def the_user_sets_baseline_1_for_the_entire_project(app):
    app.baseline_manager.set_baseline(app.project, 1)
    app.toolbar._refresh_baseline_views()
    app.update_idletasks()


@when(parsers.parse('the user selects the task named "{name}"'))
def the_user_selects_the_task_named(app, name):
    task = _find_task(app.project, name)
    app.task_list.tree.selection_set(task.id)
    app.task_list.update_idletasks()


@when("the user sets baseline 1 for selected tasks with roll-up")
def the_user_sets_baseline_1_for_selected_tasks_with_roll_up(app):
    selected = app.task_list.get_selected_task_ids()
    app.baseline_manager.set_baseline(
        app.project, 1, task_ids=selected, rollup=True)
    app.toolbar._refresh_baseline_views()
    app.update_idletasks()


@when("the user clears baseline 1 for the entire project")
def the_user_clears_baseline_1_for_the_entire_project(app):
    app.baseline_manager.clear_baseline(1)
    app.toolbar._refresh_baseline_views()
    app.update_idletasks()


@when("the user clears the selected task from baseline 1")
def the_user_clears_the_selected_task_from_baseline_1(app):
    selected = app.task_list.get_selected_task_ids()
    app.baseline_manager.clear_baseline(1, task_ids=selected)
    app.update_idletasks()


@when(parsers.parse('the user selects "{label}" from the Compare Baseline sub-menu'))
def the_user_selects_from_the_compare_baseline_sub_menu(app, label):
    if label == "None (Current Only)":
        number = None
    elif label.startswith("Baseline "):
        # Dynamic labels are "Baseline N (Saved: ...)"; the number is second token.
        number = int(label.split()[1])
    else:
        number = int(label.split()[-1])
    app.toolbar._compare_baseline_selected(number)
    app.update_idletasks()


@when('the task "Task A" is shifted one day later')
@given('the task "Task A" is shifted one day later')
def the_task_task_a_is_shifted_one_day_later(app):
    task = _find_task(app.project, "Task A")
    task.start_date += timedelta(days=1)
    task.end_date += timedelta(days=1)
    app.update_all()
    app.update_idletasks()


@when("the Gantt chart is drawn")
def the_gantt_chart_is_drawn(app):
    app.gantt_chart.draw_chart()
    app.update_idletasks()


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------
@then("the toolbar owns the baseline manager")
def the_toolbar_owns_the_baseline_manager(app):
    assert app.toolbar.baseline_manager is not None
    assert app.toolbar.baseline_manager is app.baseline_manager


@then(parsers.parse('the Compare Baseline menu offers "{label}"'))
def the_compare_baseline_menu_offers(app, label):
    menu_config = app.toolbar.menu_bar.menu_config
    actions = menu_config['Actions']
    baseline = next(d for d in actions if d.get('label') == 'Baseline')
    compare = next(d for d in baseline['items'] if d.get('label') == 'Compare Baseline')
    values = [item['label'] for item in compare['items']]
    assert any(label in v for v in values), \
        f"expected a value containing {label!r} in {values!r}"


@then("the settings window shows 10 baseline rows")
def the_settings_window_shows_10_baseline_rows(app):
    settings = app.toolbar._settings_window
    assert len(settings._baseline_entries) == 10


@then(parsers.parse('the first slot is named "{name}"'))
def the_first_slot_is_named(app, name):
    settings = app.toolbar._settings_window
    assert settings._baseline_entries[1].get() == name


@then("a baseline settings error is shown")
def a_baseline_settings_error_is_shown(app):
    settings = app.toolbar._settings_window
    text = settings._baseline_error.cget("text")
    assert text and "Duplicate" in text


@then("baseline 1 is set")
def baseline_1_is_set(app):
    slot = app.baseline_manager.get_slot(1)
    assert slot.is_set
    assert slot.baseline is not None


@then("the selected task has a baseline snapshot")
def the_selected_task_has_a_baseline_snapshot(app):
    selected = app.task_list.get_selected_task_ids()
    slot = app.baseline_manager.get_slot(1)
    for task_id in selected:
        assert task_id in slot.baseline.task_snapshots


@then("baseline 1 is unset")
def baseline_1_is_unset(app):
    slot = app.baseline_manager.get_slot(1)
    assert not slot.is_set


@then("the selected task has no baseline snapshot")
def the_selected_task_has_no_baseline_snapshot(app):
    selected = app.task_list.get_selected_task_ids()
    slot = app.baseline_manager.get_slot(1)
    for task_id in selected:
        assert task_id not in slot.baseline.task_snapshots


@then("the active baseline is 1")
def the_active_baseline_is_1(app):
    assert app.baseline_manager.active_slot_number == 1


@then("the task list shows the baseline variance columns")
def the_task_list_shows_the_baseline_variance_columns(app):
    columns = _tree_display_columns(app.task_list)
    assert "Baseline Start" in columns
    assert "Start Variance" in columns
    assert "Baseline Cost" in columns


@then(parsers.parse('the task list row for "{name}" shows start variance of "{value}"'))
def the_task_list_row_for_shows_start_variance_of(app, name, value):
    task = _find_task(app.project, name)
    values = _tree_values_for_task(app.task_list, task.id)
    idx = _column_index(app.task_list, "Start Variance")
    assert values[idx] == value, f"expected {value!r}, got {values[idx]!r}"


@then("the Gantt chart has an active baseline slot")
def the_gantt_chart_has_an_active_baseline_slot(app):
    assert app.gantt_chart._baseline_slot == 1


@then("the rendered image contains the baseline overlay")
def the_rendered_image_contains_the_baseline_overlay(app):
    from gantt_app.utils.chart_render import render_image

    slot = app.baseline_manager.get_slot(1)
    image = render_image(
        app.project,
        baseline=slot.baseline,
        width=800,
        scale=1.0,
    )
    assert image is not None
    assert image.size[0] > 0 and image.size[1] > 0


@then("the Gantt chart is drawn with the baseline overlay")
def the_gantt_chart_is_drawn_with_the_baseline_overlay(app):
    assert app.gantt_chart._baseline_slot == 1
    app.gantt_chart.draw_chart()
    app.update_idletasks()


# ------------------------------------------------------------------
# Color picker and persistence
# ------------------------------------------------------------------
@then("a color picker is shown for every baseline slot")
def a_color_picker_is_shown_for_every_baseline_slot(app):
    settings = app.toolbar._settings_window
    assert len(settings._baseline_color_vars) == 10
    for slot in app.baseline_manager.slots:
        assert slot.number in settings._baseline_color_vars


@when(parsers.parse('the user picks "{color}" as the color for slot {number:d}'))
def the_user_picks_the_color_for_slot(app, color, number):
    settings = app.toolbar._settings_window
    from gantt_app.views import settingswindow
    original = settingswindow.colorchooser.askcolor
    settingswindow.colorchooser.askcolor = lambda *args, **kwargs: ((255, 0, 0), color)
    try:
        settings._pick_baseline_color(number)
    finally:
        settingswindow.colorchooser.askcolor = original
    settings.update_idletasks()


@then(parsers.parse('baseline slot {number:d} has color "{color}"'))
def baseline_slot_has_color(app, number, color):
    slot = app.baseline_manager.get_slot(number)
    assert slot.color == color, f"expected color {color!r}, got {slot.color!r}"


@given(parsers.parse('baseline slot {number:d} has color "{color}"'))
def given_baseline_slot_has_color(app, number, color):
    app.baseline_manager.set_slot_color(number, color)


@given("the active baseline is 1")
def given_the_active_baseline_is_1(app):
    app.baseline_manager.set_active(1)


@then("the rendered image contains red baseline overlay pixels")
def the_rendered_image_contains_red_baseline_overlay_pixels(app):
    slot = app.baseline_manager.get_slot(1)
    image = render_image(
        app.project,
        baseline=slot.baseline,
        baseline_color=slot.effective_color,
        width=800,
        scale=1.0,
    )
    pixels = list(image.getdata())
    red_pixels = [
        p for p in pixels
        if isinstance(p, (tuple, list)) and len(p) >= 3
        and p[0] > 200 and p[1] < 50 and p[2] < 50
    ]
    assert red_pixels, "expected red baseline overlay pixels in the rendered image"


@when("the project is saved to a temporary file")
def the_project_is_saved_to_a_temporary_file(app):
    import gantt_app.views.toolbar as toolbar_mod
    original_info = toolbar_mod.messagebox.showinfo
    original_error = toolbar_mod.messagebox.showerror
    toolbar_mod.messagebox.showinfo = lambda *a, **k: None
    toolbar_mod.messagebox.showerror = lambda *a, **k: None
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    app._test_temp_file = path
    try:
        app.toolbar._write_project(path)
    finally:
        toolbar_mod.messagebox.showinfo = original_info
        toolbar_mod.messagebox.showerror = original_error


@when("the project is loaded from the temporary file")
def the_project_is_loaded_from_the_temporary_file(app):
    import gantt_app.views.toolbar as toolbar_mod
    original_info = toolbar_mod.messagebox.showinfo
    original_error = toolbar_mod.messagebox.showerror
    toolbar_mod.messagebox.showinfo = lambda *a, **k: None
    toolbar_mod.messagebox.showerror = lambda *a, **k: None
    try:
        app.toolbar.load_project_path(app._test_temp_file)
    finally:
        toolbar_mod.messagebox.showinfo = original_info
        toolbar_mod.messagebox.showerror = original_error
    app.update_all()
    app.update_idletasks()


@then("baseline 1 is still set")
def baseline_1_is_still_set(app):
    slot = app.baseline_manager.get_slot(1)
    assert slot.is_set, "expected baseline 1 to still be set after load"


@then(parsers.parse('baseline slot {number:d} still has color "{color}"'))
def baseline_slot_still_has_color(app, number, color):
    slot = app.baseline_manager.get_slot(number)
    assert slot.color == color, f"expected color {color!r}, got {slot.color!r}"


@then(parsers.parse('the saved task snapshot for "{name}" is restored'))
def the_saved_task_snapshot_for_is_restored(app, name):
    task = _find_task(app.project, name)
    slot = app.baseline_manager.get_slot(1)
    assert slot.is_set, "expected baseline 1 to be set after load"
    snapshot = slot.baseline.task_snapshots.get(task.id)
    assert snapshot is not None, f"snapshot for {name!r} missing after load"
    assert snapshot.start_date == task.start_date, \
        "snapshot start date does not match the restored task"
    assert snapshot.finish_date == task.end_date, \
        "snapshot finish date does not match the restored task"
