"""
Tests for the resource-pool change notification (issue #125).

A resource added through Project > Resources used to reach the
Resource Planning view only when the reader switched away and back:
the settings window wrote the repository directly, nothing told the
app the pool moved, and update_all did not refresh the board anyway.

Run with:
    python3 -m pytest tests/test_resource_sync.py -q
"""
import tkinter as tk
import unittest
from unittest import mock


def _display_available() -> bool:
    """Whether a Tk window can be opened here."""
    try:
        root = tk.Tk()
        root.destroy()
        return True
    except Exception:
        return False


HAVE_DISPLAY = _display_available()


class TestTheChangeCallback(unittest.TestCase):
    """_pool_changed is how the settings window says the pool moved."""

    def _window(self, callback):
        """A bare settings window - the callback is all this asks of it."""
        from gantt_app.views.resourcesettings import ResourceSettingsWindow

        window = object.__new__(ResourceSettingsWindow)
        window.on_changed = callback
        return window

    def test_a_change_fires_the_callback(self):
        """Each apply and delete runs through here."""
        seen = []
        self._window(lambda: seen.append(1))._pool_changed()
        self.assertEqual(seen, [1])

    def test_no_callback_is_quiet(self):
        """A window opened without one still applies its edits."""
        self._window(None)._pool_changed()

    def test_a_failing_callback_is_logged_not_raised(self):
        """The window's own work is done; a bad listener cannot undo it."""
        def fail():
            raise RuntimeError("listener down")

        with self.assertLogs('gantt_app.views.resourcesettings',
                             level='ERROR'):
            self._window(fail)._pool_changed()


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestTheWiring(unittest.TestCase):
    """The toolbar hands the app refresh in as on_changed."""

    def setUp(self):
        import customtkinter as ctk
        from gantt_app.core.models import Project
        from gantt_app.utils.undoredo import UndoRedoManager
        from gantt_app.views.toolbar import Toolbar

        self.root = ctk.CTk()
        self.root.withdraw()
        self.project = Project(name="Plan")
        self.manager = UndoRedoManager()
        self.toolbar = Toolbar(
            self.root, self.project,
            on_project_changed=mock.sentinel.update_all,
            undo_redo_manager=self.manager)

    def tearDown(self):
        try:
            for child in list(self.root.children.values()):
                try:
                    child.destroy()
                except Exception:
                    pass
            self.root.destroy()
        except Exception:
            pass

    def test_open_resource_settings_hands_in_update_all(self):
        """Every apply inside the window lands as an update_all (#125)."""
        with mock.patch(
                'gantt_app.views.resourcesettings.ResourceSettingsWindow'
        ) as window:
            self.toolbar.open_resource_settings()

        kwargs = window.call_args.kwargs
        self.assertIs(kwargs.get('on_changed'),
                      self.toolbar.on_project_changed)


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestUpdateAllReachesTheBoard(unittest.TestCase):
    """
    update_all refreshes the Resource Planning view too.

    The other half of the fix: the callback firing would still leave
    the board stale if _update_all_now skipped it, as it did before
    issue #125.
    """

    def test_update_all_refreshes_the_resource_board(self):
        import customtkinter as ctk
        from gantt_app.main import GanttApp

        ctk.set_appearance_mode("light")
        app = GanttApp()
        app.withdraw()
        try:
            with mock.patch.object(app.resource_board, 'refresh',
                                   wraps=app.resource_board.refresh
                                   ) as refresh:
                app.update_all()
            self.assertTrue(refresh.called)
        finally:
            try:
                app.destroy()
            except tk.TclError:
                pass


if __name__ == '__main__':
    unittest.main()
