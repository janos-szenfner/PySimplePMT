"""pytest-bdd coverage for the unified tabbed Settings window."""
import tkinter as tk
from unittest.mock import MagicMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.models import Project
from gantt_app.resource_model import ResourceRepository
from gantt_app.views.settingswindow import SettingsWindow


def _display_available() -> bool:
    try:
        root = tk.Tk()
    except Exception:
        return False
    root.destroy()
    return True


HAVE_DISPLAY = _display_available()
pytestmark = [pytest.mark.skipif(not HAVE_DISPLAY, reason="needs a display")]
scenarios("features/settings_window.feature")


@given("a project with resources and calendars", target_fixture="settings_context")
def a_project_with_resources_and_calendars():
    import customtkinter as ctk

    root = ctk.CTk()
    root.withdraw()
    repository = ResourceRepository()
    repository.resources["r1"] = MagicMock(name="Designer")
    repository.resources["r2"] = MagicMock(name="Developer")
    repository.teams["t1"] = MagicMock(name="Core Team")
    project = Project(
        name="Modern Settings",
        priority=650,
        resource_repository=repository,
    )
    project.calendar.countries = {"US", "DE"}
    callbacks = {name: MagicMock(name=f"open_{name.lower()}")
                 for name in SettingsWindow.TABS}
    context = {
        "root": root,
        "project": project,
        "callbacks": callbacks,
        "original": (project.name, project.priority, project.schedule_from),
    }
    yield context
    try:
        root.destroy()
    except tk.TclError:
        pass


@given("the unified Settings window is open", target_fixture="settings_window")
def the_unified_settings_window_is_open(settings_context):
    callbacks = settings_context["callbacks"]
    window = SettingsWindow(
        settings_context["root"],
        settings_context["project"],
        open_project=callbacks["Project"],
        open_resource=callbacks["Resource"],
        open_gantt=callbacks["Gantt"],
        open_calendar=callbacks["Calendar"],
    )
    window.withdraw()
    window.update_idletasks()
    settings_context["window"] = window
    return window


def _widget_texts(widget):
    texts = []
    for child in widget.winfo_children():
        try:
            text = child.cget("text")
        except (ValueError, tk.TclError):
            text = None
        if text:
            texts.append(str(text))
        texts.extend(_widget_texts(child))
    return texts


@when(parsers.parse("the {tab} tab is selected"))
def the_tab_is_selected(settings_window, tab):
    settings_window.tabview.set(tab)


@when(parsers.parse('the "{tab}" tab editor button is invoked'))
def the_tab_editor_button_is_invoked(settings_window, tab):
    settings_window.open_editor(tab)


@when("the unified Settings window is closed")
def the_settings_window_is_closed(settings_window):
    settings_window.close()


@given("the Settings hub was opened from the toolbar")
def the_settings_hub_was_opened_from_the_toolbar(settings_context, settings_window):
    from gantt_app.views.toolbar import Toolbar

    settings_window.destroy()
    toolbar = Toolbar(settings_context["root"], settings_context["project"])
    toolbar.pack()
    window = toolbar.open_settings()
    window.withdraw()
    window.update_idletasks()
    settings_context["toolbar"] = toolbar
    settings_context["window"] = window


@when("Settings is opened again on the Calendar tab")
def settings_is_opened_again(settings_context):
    settings_context["second_window"] = settings_context["toolbar"].open_settings(
        "Calendar"
    )


@then(parsers.parse('the Settings tabs are "{tab_names}"'))
def the_settings_tabs_are(settings_window, tab_names):
    assert tuple(tab_names.split(", ")) == SettingsWindow.TABS
    assert tuple(settings_window.tabs) == SettingsWindow.TABS


@then("the Project tab shows the project name, scheduling direction, and priority")
def project_tab_shows_summary(settings_window):
    text = "\n".join(_widget_texts(settings_window.tabs["Project"]))
    assert "Modern Settings" in text
    assert "Project start date" in text
    assert "650" in text


@then("the Resource tab shows resource and team counts")
def resource_tab_shows_counts(settings_window):
    text = "\n".join(_widget_texts(settings_window.tabs["Resource"]))
    assert "Resources" in text and "2" in text
    assert "Teams" in text and "1" in text


@then("the Gantt tab offers the existing Gantt settings editor")
def gantt_tab_offers_editor(settings_window):
    text = "\n".join(_widget_texts(settings_window.tabs["Gantt"]))
    assert "Open Gantt Settings" in text


@then("the Calendar tab shows working days, holiday countries, and named calendars")
def calendar_tab_shows_counts(settings_window):
    text = "\n".join(_widget_texts(settings_window.tabs["Calendar"]))
    assert "Working days" in text and "5" in text
    assert "Holiday countries" in text and "2" in text
    assert "Named calendars" in text


@then(parsers.parse('the "{tab}" settings editor callback is called'))
def settings_editor_callback_is_called(settings_context, tab):
    settings_context["callbacks"][tab].assert_called_once_with()


@then("the unified Settings window closes")
def unified_settings_window_closes(settings_window):
    assert not settings_window.winfo_exists()


@then("the project settings remain unchanged")
def project_settings_remain_unchanged(settings_context):
    project = settings_context["project"]
    assert (project.name, project.priority, project.schedule_from) == settings_context["original"]


@then("only one unified Settings window exists")
def only_one_settings_window_exists(settings_context):
    assert settings_context["second_window"] is settings_context["window"]
    windows = [child for child in settings_context["root"].winfo_children()
               if isinstance(child, SettingsWindow) and child.winfo_exists()]
    assert len(windows) == 1


@then("the Calendar tab is selected")
def calendar_tab_is_selected(settings_context):
    assert settings_context["window"].tabview.get() == "Calendar"
