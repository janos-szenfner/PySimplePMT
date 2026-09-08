"""
pytest-bdd end-to-end tests for the baseline management UI.

Run with:
    python3 -m pytest tests/test_baseline_ui_bdd.py -q

These tests require a display because they build the full GanttApp.
"""
import tkinter as tk
from datetime import datetime, timedelta

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.models import Project, Task


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
    app.toolbar._refresh_baseline_selector()
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
    app.toolbar._refresh_baseline_selector()
    app.update_idletasks()


@when("the user sets baseline 1 for the entire project")
def the_user_sets_baseline_1_for_the_entire_project(app):
    app.baseline_manager.set_baseline(app.project, 1)
    app.toolbar._refresh_baseline_selector()
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
    app.toolbar._refresh_baseline_selector()
    app.update_idletasks()


@when("the user clears baseline 1 for the entire project")
def the_user_clears_baseline_1_for_the_entire_project(app):
    app.baseline_manager.clear_baseline(1)
    app.toolbar._refresh_baseline_selector()
    app.update_idletasks()


@when("the user clears the selected task from baseline 1")
def the_user_clears_the_selected_task_from_baseline_1(app):
    selected = app.task_list.get_selected_task_ids()
    app.baseline_manager.clear_baseline(1, task_ids=selected)
    app.update_idletasks()


@when(parsers.parse('the user selects "{label}" from the compare dropdown'))
def the_user_selects_from_the_compare_dropdown(app, label):
    app.toolbar._on_baseline_selected(label)
    app.update_idletasks()


@when('the task "Task A" is shifted one day later')
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


@then(parsers.parse('the baseline compare dropdown shows "{label}"'))
def the_baseline_compare_dropdown_shows(app, label):
    values = app.toolbar._baseline_menu.cget("values")
    assert any(label in v for v in values), \
        f"expected a value containing {label!r} in {values!r}"


@then("the baseline compare dropdown lists ten empty baseline slots")
def the_baseline_compare_dropdown_lists_ten_empty_baseline_slots(app):
    values = app.toolbar._baseline_menu.cget("values")
    assert "None (Current Only)" in values
    for n in range(1, 11):
        expected = f"Baseline {n} (Unset)"
        assert expected in values, f"missing {expected!r} in {values!r}"


@then("the settings window shows 10 baseline rows")
def the_settings_window_shows_10_baseline_rows(app):
    settings = app.toolbar._settings_window
    assert len(settings._baseline_entries) == 10


@then(parsers.parse('the first slot is named "{name}"'))
def the_first_slot_is_named(app, name):
    settings = app.toolbar._settings_window
    assert settings._baseline_entries[1].get() == name


@then(parsers.parse('the toolbar dropdown labels include "{name}"'))
def the_toolbar_dropdown_labels_include(app, name):
    values = app.toolbar._baseline_menu.cget("values")
    assert any(name in v for v in values), f"{name!r} not in {values!r}"


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
