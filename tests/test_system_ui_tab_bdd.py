"""
pytest-bdd tests for the System UI tab in Project Settings.

Run with:
    python3 -m pytest tests/test_system_ui_tab_bdd.py -q

Display-gated, like the other Settings-window tests. Converted from
test_system_ui_tab.py - every case carried over.
"""
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.views import theme
from gantt_app.core.models import Project

pytestmark = [
    pytest.mark.system_ui_tab,
]

scenarios("features/system_ui_tab.feature")


def _display_available() -> bool:
    try:
        import tkinter
        root = tkinter.Tk()
    except Exception:
        return False
    root.destroy()
    return True


HAVE_DISPLAY = _display_available()


class FakeController:
    """A stand-in ThemeController recording the mode it was asked for."""

    def __init__(self, mode=theme.MODE_SYSTEM, appearance=theme.LIGHT):
        self._mode = mode
        self._appearance = appearance

    @property
    def is_dark(self):
        return self._appearance == theme.DARK

    @property
    def following_system(self):
        return self._mode == theme.MODE_SYSTEM

    @property
    def appearance(self):
        return self._appearance

    def set_mode(self, mode, remember=True):
        self._mode = mode
        if mode == theme.MODE_DARK:
            self._appearance = theme.DARK
        elif mode == theme.MODE_LIGHT:
            self._appearance = theme.LIGHT
        return True

    def sync_with_system(self):
        self._mode = theme.MODE_SYSTEM
        return True

    def subscribe(self, listener, owner=None):
        self._listener = listener


def _open_window(controller):
    """Build a withdrawn Settings window; returns (root, window)."""
    import customtkinter as ctk
    from gantt_app.views.settingswindow import SettingsWindow

    root = ctk.CTk()
    root.withdraw()
    noop = lambda: None
    window = SettingsWindow(
        root, Project(name="P"),
        open_project=noop, open_resource=noop,
        open_calendar=noop,
        theme_controller=controller)
    window.withdraw()
    window.update_idletasks()
    return root, window


def _window_ctx(controller):
    if not HAVE_DISPLAY:
        pytest.skip("no display")
    root, window = _open_window(controller)
    ctx = SimpleNamespace(root=root, window=window, controller=controller)
    yield ctx
    try:
        root.destroy()
    except Exception:
        pass


# ------------------------------------------------------------------
# GIVEN
# ------------------------------------------------------------------

@given("a settings window on a system-following controller",
       target_fixture="ctx")
def a_window_on_a_system_controller():
    yield from _window_ctx(
        FakeController(theme.MODE_SYSTEM, theme.LIGHT))


@given("a settings window on a dark controller", target_fixture="ctx")
def a_window_on_a_dark_controller():
    yield from _window_ctx(
        FakeController(theme.MODE_DARK, theme.DARK))


@given("a settings window without a controller", target_fixture="ctx")
def a_window_without_a_controller():
    yield from _window_ctx(None)


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------

@when("the theme toggle is switched on")
def the_toggle_is_switched_on(ctx):
    ctx.window._theme_switch.select()
    ctx.window._on_theme_switch()


@when("the theme toggle is switched off")
def the_toggle_is_switched_off(ctx):
    ctx.window._theme_switch.deselect()
    ctx.window._on_theme_switch()


@when("sync with system is pressed")
def sync_with_system_is_pressed(ctx):
    ctx.window._on_sync_system()


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@then(parsers.parse('"{tab}" is among the tabs'))
def the_tab_is_among_the_tabs(ctx, tab):
    assert tab in ctx.window.tabs


@then("the theme toggle is on")
def the_theme_toggle_is_on(ctx):
    assert ctx.window._theme_switch.get()


@then("the controller is asked for dark mode")
def the_controller_is_asked_for_dark(ctx):
    assert ctx.controller._mode == theme.MODE_DARK


@then("the controller is asked for light mode")
def the_controller_is_asked_for_light(ctx):
    assert ctx.controller._mode == theme.MODE_LIGHT


@then("the controller follows the system")
def the_controller_follows_the_system(ctx):
    assert ctx.controller._mode == theme.MODE_SYSTEM


@then(parsers.parse('the theme status says "{text}"'))
def the_theme_status_says(ctx, text):
    assert text in ctx.window._theme_status.cget("text")


@then("the theme toggle is disabled")
def the_theme_toggle_is_disabled(ctx):
    assert str(ctx.window._theme_switch.cget("state")) == "disabled"
