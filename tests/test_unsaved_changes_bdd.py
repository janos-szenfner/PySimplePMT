"""
pytest-bdd tests for unsaved-changes protection.

Run with:
    python3 -m pytest tests/test_unsaved_changes_bdd.py -q

These tests require a display because they build the full GanttApp.
"""
import tkinter as tk

import pytest
from pytest_bdd import given, parsers, scenarios, then, when


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

# Load the Gherkin scenarios from tests/features/unsaved_changes.feature.
scenarios("features/unsaved_changes.feature")


@given("the application is open", target_fixture="app")
def the_application_is_open():
    import customtkinter as ctk
    from gantt_app.main import GanttApp

    ctk.set_appearance_mode("light")
    app = GanttApp()
    app.withdraw()
    app.project.name = "Test Project"
    app.mark_clean()
    yield app
    try:
        app.destroy()
    except tk.TclError:
        pass


@given("the project has no unsaved changes")
def the_project_has_no_unsaved_changes(app):
    assert not app.is_dirty


@given("the project has unsaved changes")
def the_project_has_unsaved_changes(app):
    app.mark_dirty()
    assert app.is_dirty


@given(parsers.parse('the user will choose "{choice}"'))
def the_user_will_choose(choice, monkeypatch):
    result = {"save": True, "discard": False, "cancel": None}[choice]
    monkeypatch.setattr(
        "gantt_app.main.messagebox.askyesnocancel",
        lambda *args, **kwargs: result,
    )


@given("saving will succeed")
def saving_will_succeed(app, monkeypatch):
    monkeypatch.setattr(app.toolbar, "save_project", app.mark_clean)


@given(parsers.parse('the new project name will be "{name}"'))
def the_new_project_name_will_be(name, monkeypatch):
    monkeypatch.setattr(
        "tkinter.simpledialog.askstring",
        lambda *args, **kwargs: name,
    )


@when("the user tries to close the application")
def the_user_tries_to_close_the_application(app):
    app._shutdown_called = False
    app._shutdown = lambda: setattr(app, "_shutdown_called", True)
    app.on_close()


@when("the user tries to create a new project")
def the_user_tries_to_create_a_new_project(app):
    app.toolbar.new_project()


@then("the application exits")
def the_application_exits(app):
    assert app._shutdown_called is True


@then("the application stays open")
def the_application_stays_open(app):
    assert app._shutdown_called is False


@then("the current project is unchanged")
def the_current_project_is_unchanged(app):
    assert app.project.name == "Test Project"
    assert len(app.project.tasks) > 0


@then("a new empty project is created")
def a_new_empty_project_is_created(app):
    assert app.project.name == "New Project"
    assert len(app.project.tasks) == 0


@then("the project is no longer dirty")
def the_project_is_no_longer_dirty(app):
    assert not app.is_dirty


@then("the project is still dirty")
def the_project_is_still_dirty(app):
    assert app.is_dirty
