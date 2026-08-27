"""
Tests that the task grid repaints when the appearance changes.

WHY THIS MODULE EXISTS:
======================
The grid is a ttk Treeview, and every row's colour comes from a tag named
after the colours it carries. Nothing about that follows a theme on its own:
the style has to be reconfigured and the rows have to be painted again, with
tags under new names. Only the first of those was being done, so flipping to
dark mode darkened the heading and the empty space below the rows and left
every row white between them - the one thing a reader would notice.

DEVELOPMENT NOTES:
------------------
The rows are read back through the widget rather than through the task list's
own bookkeeping, because the fault was precisely that the two disagreed: the
cache of tag names had been cleared while the rows on screen still wore the
old ones.

Needs a display. Skipped where there is none, as the other widget tests are.
"""

import unittest
from datetime import datetime

from gantt_app import theme
from gantt_app.models import Project, Task


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
class TestTheGridFollowsTheTheme(unittest.TestCase):
    """What the rows look like after the appearance changes under them."""

    def setUp(self):
        """A three-row plan in a list, drawn in the light appearance."""
        import customtkinter as ctk

        from gantt_app.utils.undoredo import (
            ProjectStateTracker, UndoRedoManager,
        )
        from gantt_app.views.task_list import DragDropTaskList

        self.ctk = ctk
        self.opening_mode = str(ctk.get_appearance_mode())
        ctk.set_appearance_mode('light')

        self.root = ctk.CTk()
        self.root.withdraw()

        base = datetime(2026, 1, 5)
        self.project = Project(name="Plan")
        for task_id in ("A", "B", "C"):
            self.project.add_task(Task(id=task_id, name=task_id,
                                       task_type="Task", start_date=base,
                                       end_date=base, duration=2))

        self.task_list = DragDropTaskList(
            self.root, self.project,
            project_tracker=ProjectStateTracker(self.project,
                                                UndoRedoManager()))
        self.task_list.update_task_list()
        self.root.update_idletasks()

    def tearDown(self):
        """Put the appearance back, and close the window."""
        try:
            self.root.destroy()
        except Exception:
            pass
        try:
            self.ctk.set_appearance_mode(self.opening_mode)
        except Exception:
            pass

    def fills(self):
        """The background each row is actually painted with."""
        painted = {}
        for task_id in ("A", "B", "C"):
            tags = [tag for tag in self.task_list.tree.item(task_id, 'tags')
                    if tag.startswith('row_')]
            painted[task_id] = str(
                self.task_list.tree.tag_configure(tags[0], 'background'))
        return painted

    def go_dark(self):
        """Flip the appearance and tell the list about it."""
        self.ctk.set_appearance_mode('dark')
        self.task_list.apply_theme()
        self.root.update_idletasks()

    def test_the_rows_start_in_the_light_palette(self):
        """The fixture is what it claims to be."""
        light = {theme.GRID_ROW_BG[0], theme.GRID_ROW_ALT[0]}

        self.assertTrue(set(self.fills().values()) <= light, self.fills())

    def test_every_row_takes_the_dark_palette(self):
        """
        The fault itself: a row kept the colour it was drawn in.

        The banding means a row is one of two colours, so both halves of
        the dark pair are allowed and neither light one is.
        """
        self.go_dark()

        dark = {theme.GRID_ROW_BG[1], theme.GRID_ROW_ALT[1]}
        self.assertTrue(set(self.fills().values()) <= dark, self.fills())

    def test_the_banding_survives_the_change(self):
        """Two shades after the flip, as there were before it."""
        before = len(set(self.fills().values()))

        self.go_dark()

        self.assertEqual(len(set(self.fills().values())), before)

    def test_the_ink_follows_as_well(self):
        """Dark text on a dark grid would be worse than not repainting."""
        self.go_dark()

        tags = [tag for tag in self.task_list.tree.item('A', 'tags')
                if tag.startswith('row_')]
        ink = str(self.task_list.tree.tag_configure(tags[0], 'foreground'))

        self.assertEqual(ink, theme.GRID_TEXT[1])

    def test_the_style_follows_too(self):
        """The empty space below the rows is the style, not the tags."""
        import tkinter.ttk as ttk

        self.go_dark()

        style = ttk.Style()
        self.assertEqual(style.lookup('Gantt.Treeview', 'fieldbackground'),
                         theme.GRID_ROW_BG[1])


if __name__ == '__main__':
    unittest.main()
