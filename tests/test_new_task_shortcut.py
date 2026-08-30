"""
Tests that the new-task shortcut is actually bound to the window.

WHY THIS MODULE EXISTS:
======================
Cmd+Option+. creates a task where the cursor is. It had been written twice
and reported as doing nothing both times, and every test of it checked the
handlers rather than the bindings - so a shortcut that was never wired to the
window at all would have passed all of them.

What the handlers do with an event is checked in test_toolbar_menus. This
checks the other half: that a window handed a task list comes away with
something bound for the keystroke to land on.

DEVELOPMENT NOTES:
------------------
The sequences cannot be compared as they were written. Tk stores a binding
under a name of its own choosing - <Command-Option-period> comes back as
<Mod1-Mod2-Key-period> - so these ask how many key bindings arrived and that
the catch-all is among them, rather than matching the spelling.

Needs a display.
"""

import unittest
from datetime import datetime

from gantt_app.models import Project, Task
from gantt_app.shortcuts import IS_MACOS


def _display_available() -> bool:
    """Whether a Tk window can be opened here."""
    try:
        import tkinter
        root = tkinter.Tk()
        root.destroy()
        return True
    except Exception:
        return False


HAVE_DISPLAY = _display_available()


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestTheShortcutReachesTheWindow(unittest.TestCase):
    """What is bound after the toolbar is given a task list."""

    def setUp(self):
        """A toolbar and a list in one window, wired as the app wires them."""
        import customtkinter as ctk

        from gantt_app.utils.undoredo import (
            ProjectStateTracker, UndoRedoManager,
        )
        from gantt_app.views.task_list import DragDropTaskList
        from gantt_app.views.toolbar import Toolbar

        self.root = ctk.CTk()
        self.root.withdraw()

        self.project = Project(name="Plan")
        self.project.add_task(Task(id="1", name="Only row", task_type="Task",
                                   start_date=datetime(2026, 1, 5),
                                   end_date=datetime(2026, 1, 6)))

        manager = UndoRedoManager()
        self.toolbar = Toolbar(self.root, self.project,
                               undo_redo_manager=manager)
        self.task_list = DragDropTaskList(
            self.root, self.project,
            project_tracker=ProjectStateTracker(self.project, manager))
        self.toolbar.set_task_list(self.task_list)
        self.root.update_idletasks()

    def tearDown(self):
        """Close the window."""
        try:
            self.root.destroy()
        except Exception:
            pass

    def bindings(self):
        """Every key sequence bound to the window, as Tk spells them."""
        return [sequence for sequence in self.root.bind()
                if 'Key' in sequence]

    def test_the_window_has_key_bindings_at_all(self):
        """The wiring runs when the toolbar is handed the list."""
        self.assertTrue(self.bindings())

    def stored(self, *sequences):
        """
        How Tk spells these sequences once it has stored them.

        Bound to a window of their own and read straight back, because Tk
        renames a binding as it takes it - <Command-Option-period> comes back
        as <Mod1-Mod2-Key-period> - and the renaming differs by platform.
        Asking Tk rather than writing the answer down keeps this test about
        what is bound rather than about how this Tk happens to spell it.
        """
        import tkinter as tk

        scratch = tk.Toplevel(self.root)
        scratch.withdraw()
        try:
            for sequence in sequences:
                scratch.bind(sequence, lambda _event: None, add='+')
            return set(scratch.bind())
        finally:
            scratch.destroy()

    def test_the_period_is_bound_with_both_modifiers(self):
        """The plain sequence; see shortcuts.sequences."""
        from gantt_app.shortcuts import sequences

        expected = self.stored(*sequences('.', alt=True))

        self.assertTrue(expected <= set(self.bindings()),
                        (expected, self.bindings()))

    def test_the_modifier_catch_all_is_bound(self):
        """
        For a keystroke Option has taken the letter out of. Tk matches the
        modifiers and is_key works out the key.
        """
        from gantt_app.shortcuts import any_key_with

        expected = self.stored(any_key_with(alt=True))

        self.assertTrue(expected <= set(self.bindings()),
                        (expected, self.bindings()))

    def test_the_bare_key_net_is_there_on_a_mac_only(self):
        """
        It exists for a macOS fault, and every key in the window goes
        through it - so it is not carried anywhere it earns nothing.
        """
        bare = [sequence for sequence in self.bindings()
                if sequence in ('<Key>', '<KeyPress>')]

        self.assertEqual(bool(bare), IS_MACOS, self.bindings())

    def test_the_handler_makes_a_task_where_the_cursor_is(self):
        """
        The end of the chain: the row the cursor is on gets a sibling.

        The dialog is stubbed out. What is being checked is that the
        keyboard route reaches the same creation the right-click menu does,
        at the focused row rather than at the end of the plan.
        """
        from unittest import mock

        with mock.patch.object(type(self.task_list), 'create_task') as create:
            self.task_list.tree.focus('1')
            self.toolbar._hotkey_new_task()

        create.assert_called_once_with('Task', '1')


if __name__ == '__main__':
    unittest.main()
