"""
pytest-bdd end-to-end tests for undoing task duration changes.

Run with:
    python3 -m pytest tests/test_undo_duration_bdd.py -q

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

scenarios("features/undo_duration.feature")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _find_task(project, name):
    for task in project.tasks:
        if task.name == name:
            return task
    raise AssertionError(f"task {name!r} not found")


def _next_working_day_after(date, calendar):
    nxt = date + timedelta(days=1)
    while not calendar.is_working_day(nxt):
        nxt += timedelta(days=1)
    return nxt


# ------------------------------------------------------------------
# GIVEN
# ------------------------------------------------------------------
@given("the application is started", target_fixture="app")
def the_application_is_started():
    import customtkinter as ctk
    from gantt_app.main import GanttApp
    from gantt_app.utils.log import setup_logging, clear_log

    setup_logging(to_file=False)
    clear_log()
    ctk.set_appearance_mode("light")
    app = GanttApp()
    app.withdraw()
    app.update_idletasks()
    yield app
    try:
        app.destroy()
    except tk.TclError:
        pass


@given("a project with linked tasks exists")
def a_project_with_linked_tasks_exists(app):
    app.project.tasks = []

    start = datetime(2026, 9, 1)
    task1 = Task(
        id="dur-task-1",
        name="Task 1",
        start_date=start,
        end_date=start + timedelta(days=4),
        task_type="Task",
        duration=5,
    )
    task1.__post_init__()
    app.project.add_task(task1)

    finish = _next_working_day_after(task1.end_date, app.project.calendar)
    task2 = Task(
        id="dur-task-2",
        name="Task 2",
        start_date=finish,
        end_date=finish + timedelta(days=4),
        task_type="Task",
        duration=5,
    )
    task2.__post_init__()
    task2.add_dependency(task1.id)
    app.project.add_task(task2)

    app.update_all()
    app.update_idletasks()

    app._original_task1_end = task1.end_date
    app._original_task2_start = task2.start_date


@given(parsers.parse('the user has changed the duration of "{name}" to {days:d} days'))
def the_user_has_changed_the_duration_of_to_days(app, name, days):
    the_user_changes_the_duration_of_to_days(app, name, days)


@given("the user has undone the last change")
def the_user_has_undone_the_last_change(app):
    the_user_undoes_the_last_change(app)


@given(parsers.parse('the user has opened the task editor for "{name}"'))
def the_user_has_opened_the_task_editor_for(app, name):
    from gantt_app.views.taskdialogs import EditTaskDialog

    task = _find_task(app.project, name)
    app.undo_redo_manager.clear()

    def on_save(_task):
        app.update_all()
        app.update_idletasks()

    dialog = EditTaskDialog(
        app,
        task=task,
        project=app.project,
        on_save=on_save,
        on_delete=lambda _id: None,
        project_tracker=app.project_tracker,
    )
    dialog.withdraw()
    app._test_dialog = dialog
    app.update_idletasks()


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------
@when(parsers.parse('the user changes the duration of "{name}" to {days:d} days'))
def the_user_changes_the_duration_of_to_days(app, name, days):
    task = _find_task(app.project, name)
    new_end = app.project.calendar.add_working_days(task.start_date, days - 1)
    # Use the real UI tracker path so undo records the edit.
    app.undo_redo_manager.clear()
    app.project_tracker.update_task(
        task.id,
        start_date=task.start_date,
        end_date=new_end,
        duration=days,
    )
    app.update_all()
    app.update_idletasks()


@when("the user undoes the last change")
def the_user_undoes_the_last_change(app):
    app.toolbar.undo()
    app.update_all()
    app.update_idletasks()


@when("the user redoes the last change")
def the_user_redoes_the_last_change(app):
    app.toolbar.redo()
    app.update_all()
    app.update_idletasks()


@when(parsers.parse('the user changes the dialog duration to {days:d} days and saves'))
def the_user_changes_the_dialog_duration_to_days_and_saves(app, days):
    dialog = app._test_dialog
    # Set the scheduling mode so duration drives the end date.
    dialog.scheduling_options_var.set("End date is calculated")
    dialog._on_scheduling_mode_changed()
    dialog.duration_var.set(str(days))
    dialog._recalculate_schedule()
    dialog._apply()
    try:
        dialog.destroy()
    except tk.TclError:
        pass
    app.update_all()
    app.update_idletasks()


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------
@then('"Task 2" starts after "Task 1" finishes')
def task_2_starts_after_task_1_finishes(app):
    task1 = _find_task(app.project, "Task 1")
    task2 = _find_task(app.project, "Task 2")
    expected = _next_working_day_after(task1.end_date, app.project.calendar)
    assert task2.start_date == expected, \
        f"expected Task 2 to start on {expected.date()}, got {task2.start_date.date()}"


@then('"Task 1" has its original duration')
def task_1_has_its_original_duration(app):
    task1 = _find_task(app.project, "Task 1")
    assert task1.end_date == app._original_task1_end, \
        f"expected {app._original_task1_end.date()}, got {task1.end_date.date()}"


@then('"Task 2" has its original start date')
def task_2_has_its_original_start_date(app):
    task2 = _find_task(app.project, "Task 2")
    assert task2.start_date == app._original_task2_start, \
        f"expected {app._original_task2_start.date()}, got {task2.start_date.date()}"


@then(parsers.parse('"{name}" has a duration of {days:d} days'))
def task_has_a_duration_of_days(app, name, days):
    task = _find_task(app.project, name)
    assert task.duration_days == days, \
        f"expected duration {days}, got {task.duration_days}"


@then("the log contains an undo entry")
def the_log_contains_an_undo_entry(app):
    from gantt_app.views.log_window import LogWindow
    lw = LogWindow.show(app)
    lw.refresh()
    text = lw.textbox.get("1.0", tk.END)
    assert "Undo" in text, f"expected undo log entry, got:\n{text}"


@then(parsers.parse('the log contains "{text}"'))
def the_log_contains_text(app, text):
    from gantt_app.views.log_window import LogWindow
    lw = LogWindow.show(app)
    lw.refresh()
    content = lw.textbox.get("1.0", tk.END)
    assert text in content, f"expected {text!r} in log, got:\n{content}"


@then("the log contains a redo entry")
def the_log_contains_a_redo_entry(app):
    from gantt_app.views.log_window import LogWindow
    lw = LogWindow.show(app)
    lw.refresh()
    text = lw.textbox.get("1.0", tk.END)
    assert "Redo" in text, f"expected redo log entry, got:\n{text}"
