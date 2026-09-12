"""
The System UI tab in Project Settings (moved from the View menu).

The old View > System UI mode submenu became a day/night toggle and a
Sync with System button on a Settings tab, wired to the same ThemeController.
Display-gated, like the other Settings-window tests.
"""

import unittest

from gantt_app import theme
from gantt_app.models import Project


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


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class TestSystemUITab(unittest.TestCase):
    def _window(self, controller):
        import customtkinter as ctk
        from gantt_app.views.settingswindow import SettingsWindow

        self.root = ctk.CTk()
        self.root.withdraw()
        noop = lambda: None
        window = SettingsWindow(
            self.root, Project(name="P"),
            open_project=noop, open_resource=noop,
            open_calendar=noop,
            theme_controller=controller)
        window.withdraw()
        window.update_idletasks()
        return window

    def tearDown(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_there_is_a_system_ui_tab(self):
        window = self._window(FakeController())
        self.assertIn("System UI", window.tabs)

    def test_the_toggle_reflects_a_dark_appearance(self):
        window = self._window(FakeController(theme.MODE_DARK, theme.DARK))
        self.assertTrue(window._theme_switch.get())

    def test_toggling_on_sets_night_mode(self):
        controller = FakeController(theme.MODE_SYSTEM, theme.LIGHT)
        window = self._window(controller)
        window._theme_switch.select()
        window._on_theme_switch()
        self.assertEqual(controller._mode, theme.MODE_DARK)

    def test_toggling_off_sets_day_mode(self):
        controller = FakeController(theme.MODE_DARK, theme.DARK)
        window = self._window(controller)
        window._theme_switch.deselect()
        window._on_theme_switch()
        self.assertEqual(controller._mode, theme.MODE_LIGHT)

    def test_the_sync_button_follows_the_system(self):
        controller = FakeController(theme.MODE_DARK, theme.DARK)
        window = self._window(controller)
        window._on_sync_system()
        self.assertEqual(controller._mode, theme.MODE_SYSTEM)

    def test_the_status_names_who_is_deciding(self):
        window = self._window(FakeController(theme.MODE_SYSTEM, theme.LIGHT))
        self.assertIn("Following the system",
                      window._theme_status.cget("text"))

    def test_without_a_controller_the_controls_are_disabled(self):
        window = self._window(None)
        self.assertEqual(str(window._theme_switch.cget("state")), "disabled")


if __name__ == "__main__":
    unittest.main()
