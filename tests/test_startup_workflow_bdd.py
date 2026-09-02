"""
pytest-bdd tests for the startup and project selection workflow.

Run with:
    python3 -m pytest tests/test_startup_workflow_bdd.py -q

These tests require a display because they build the full GanttApp.
"""
import os
import tkinter as tk
from unittest.mock import MagicMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.models import Project
from gantt_app.startup_setting import StartupSettings, WelcomeModal
from gantt_app.utils.file_io import save_project


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

scenarios("features/startup_workflow.feature")


@pytest.fixture
def settings(tmp_path):
    """Temporary startup settings for a test run."""
    return StartupSettings(storage_dir=str(tmp_path), max_recent=5)


@given("the application is started with the welcome dialog", target_fixture="app")
def the_application_is_started_with_the_welcome_dialog(settings):
    import customtkinter as ctk
    from gantt_app.main import GanttApp

    ctk.set_appearance_mode("light")
    app = GanttApp(show_welcome=True, startup_settings=settings)
    app.withdraw()
    app.update_idletasks()
    yield app
    try:
        app.destroy()
    except tk.TclError:
        pass


@given("a project file exists in the recent list", target_fixture="project_file")
def a_project_file_exists_in_the_recent_list(settings, tmp_path):
    path = str(tmp_path / "recent.json")
    project = Project(name="Recent Project")
    save_project(project, path)
    settings.add(path, "Recent Project")
    return path


@given("a missing project path is in the recent list", target_fixture="missing_path")
def a_missing_project_path_is_in_the_recent_list(settings):
    path = "/nonexistent/path/project.json"
    settings.add(path, "Missing Project")
    return path


@given(parsers.parse('the application has a project named "{name}"'))
def the_application_has_a_project_named(app, name):
    app._start_new_project(name)
    assert app.project.name == name


@given("the recent list contains 7 projects")
def the_recent_list_contains_7_projects(settings):
    for i in range(7):
        settings.add(f"/tmp/project{i}.json", f"Project {i}")


@given("the Welcome modal is open", target_fixture="welcome_modal")
def the_welcome_modal_is_open(settings, app):
    modal = WelcomeModal(app, settings.recent, app._on_welcome_select)
    modal.withdraw()
    modal.update_idletasks()
    yield modal
    try:
        modal.destroy()
    except tk.TclError:
        pass


@when(parsers.parse('the user selects "{mode}" in the Welcome modal'))
def the_user_selects_in_the_welcome_modal(app, mode):
    app._shutdown_called = False
    app._shutdown = lambda: setattr(app, "_shutdown_called", True)
    app._on_welcome_select(mode)


@when("the user selects that recent project")
def the_user_selects_that_recent_project(app, project_file):
    app._on_welcome_select("recent", project_file)


@when("the user selects the missing recent project")
def the_user_selects_the_missing_recent_project(app, missing_path, monkeypatch):
    app._warning_called = False

    def _record_warning(*args, **kwargs):
        app._warning_called = True

    monkeypatch.setattr("gantt_app.main.messagebox.showwarning", _record_warning)
    app._on_welcome_select("recent", missing_path)


@when(parsers.parse('the project is saved to "{filename}"'))
def the_project_is_saved_to(app, tmp_path, filename, monkeypatch):
    path = str(tmp_path / filename)
    monkeypatch.setattr(
        "gantt_app.views.toolbar.messagebox.showinfo",
        lambda *args, **kwargs: None,
    )
    app.toolbar._write_project(path)


@then("the project has no tasks")
def the_project_has_no_tasks(app):
    assert len(app.project.tasks) == 0


@then("the project has tasks")
def the_project_has_tasks(app):
    assert len(app.project.tasks) > 0


@then(parsers.parse('the project name is "{name}"'))
def the_project_name_is(app, name):
    assert app.project.name == name


@then("the project is clean")
def the_project_is_clean(app):
    assert not app.is_dirty


@then("a warning is shown")
def a_warning_is_shown(app):
    assert app._warning_called is True


@then("the missing path is removed from the recent list")
def the_missing_path_is_removed_from_the_recent_list(app, missing_path):
    paths = [entry.get("path") for entry in app.startup_settings.recent]
    assert missing_path not in paths


@then(parsers.parse('the recent list contains "{filename}"'))
def the_recent_list_contains_filename(app, filename):
    files = [
        os.path.basename(entry.get("path", ""))
        for entry in app.startup_settings.recent
    ]
    assert filename in files


@then("the Welcome modal displays 5 recent projects")
def the_welcome_modal_displays_5_recent_projects(welcome_modal):
    import customtkinter as ctk

    items = [
        child
        for child in welcome_modal.frame_recent.winfo_children()
        if isinstance(child, ctk.CTkFrame)
    ]
    assert len(items) == 5


@given(parsers.parse('project files "{first}" and "{second}" are in the recent list in that order'),
       target_fixture="project_files")
def project_files_are_in_the_recent_list_in_that_order(settings, tmp_path, first, second):
    paths = {}
    for name in (first, second):
        path = str(tmp_path / f"{name.lower()}.json")
        project = Project(name=name)
        save_project(project, path)
        settings.add(path, name)
        paths[name] = path
    return paths


@when(parsers.parse('the user selects the project "{name}" recent project'))
def the_user_selects_the_named_recent_project(app, project_files, name):
    app._on_welcome_select("recent", project_files[name])


@then("the application closes")
def the_application_closes(app):
    assert app._shutdown_called is True


@then(parsers.parse('the first recent project is "{name}"'))
def the_first_recent_project_is(welcome_modal, name):
    text = welcome_modal.recent_project_cards[0]["name"].cget("text")
    assert name in text, f"Expected {name!r} in first card name, got {text!r}"


@then(parsers.parse('the first recent project in the list is "{name}"'))
def the_first_recent_project_in_the_list_is(app, name):
    assert app.startup_settings.recent[0]["name"] == name


@then("the first recent project shows the project name, path, and last modified")
def the_first_recent_project_shows_the_project_details(welcome_modal, project_file):
    card = welcome_modal.recent_project_cards[0]
    assert card["name"].cget("text") == "Recent Project"
    assert card["path"].cget("text") == project_file
    assert card["timestamp"].cget("text")
    assert "T" not in card["timestamp"].cget("text")


@then("the project name is visually emphasized")
def project_name_is_emphasized(welcome_modal):
    font = welcome_modal.recent_project_cards[0]["name"].cget("font")
    assert font.cget("weight") == "bold"


@then("the path uses muted text")
def path_uses_muted_text(welcome_modal):
    colour = welcome_modal.recent_project_cards[0]["path"].cget("text_color")
    assert colour != welcome_modal.recent_project_cards[0]["name"].cget("text_color")


@then("the timestamp is right aligned")
def timestamp_is_right_aligned(welcome_modal):
    assert welcome_modal.recent_project_cards[0]["timestamp"].cget("anchor") == "e"


@then("the Recent Projects heading has a divider beneath it")
def recent_projects_has_divider(welcome_modal):
    assert welcome_modal.recent_divider.winfo_manager() == "pack"
    assert welcome_modal.recent_divider.cget("height") == 1


@when("the first recent project card is clicked")
def first_recent_project_card_is_clicked(welcome_modal):
    card = welcome_modal.recent_project_cards[0]
    welcome_modal._select("recent", card["path"].cget("text"))


@when("the Welcome modal is closed with the window control")
def welcome_modal_closed_with_window_control(welcome_modal):
    welcome_modal._on_close()


@then("the application remains open")
def application_remains_open(app):
    assert app.winfo_exists()


@given(parsers.parse('a project file named "{name}" exists as "{filename}"'),
       target_fixture="project_file_path")
def a_project_file_named_exists_as(settings, tmp_path, name, filename):
    path = str(tmp_path / filename)
    project = Project(name=name)
    save_project(project, path)
    settings.add(path, name)
    return path


@when("the application starts with that file path")
def the_application_starts_with_that_file_path(app, project_file_path):
    app._load_file_path(project_file_path)


@then("the welcome dialog is not shown")
def the_welcome_dialog_is_not_shown(app):
    from gantt_app.startup_setting import WelcomeModal
    dialogs = [child for child in app.winfo_children() if isinstance(child, WelcomeModal)]
    assert len(dialogs) == 0
