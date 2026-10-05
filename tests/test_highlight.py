"""
Tests for the View tab's highlight filters - the painted rows.

WHY THIS MODULE EXISTS:
======================
The filters themselves - which rows each picks, the one-at-a-time
toggle, the gallery, the copies and the fields the dialog offers - are
answered without a window and live in tests/features/highlight.feature
with their steps in tests/test_highlight_bdd.py.

What is kept here is the paint: a Treeview of rows, which needs a
display, and is skipped where there is none.
"""

import unittest
from datetime import datetime

from gantt_app.core.models import Project, Task


def _shut_down(root) -> None:
    """
    Take a root down, children first, without raising.

    Destroying a root while a Toplevel is still on it leaves Tk running
    ttk::ThemeChanged against an interpreter that has already gone, which
    floods stderr with "can't invoke event" tracebacks.
    """
    try:
        for child in list(root.children.values()):
            try:
                child.destroy()
            except Exception:
                pass
        root.destroy()
    except Exception:
        pass


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


def _plan():
    """
    A plan with one row for each question the filters ask.

    The status date is pinned to the plan's own start: a real 'today'
    drifting past these fixed dates would flag every row late and age
    the assertions into lies.
    """
    base = datetime(2026, 1, 5)
    end = datetime(2026, 1, 9)
    project = Project(name="Plan")
    project.status_date = base
    project.add_task(Task(id="A", name="A", task_type="Task",
                          start_date=base, end_date=end, progress=50))
    project.add_task(Task(id="B", name="B", task_type="Task",
                          start_date=base, end_date=end, progress=100))
    project.add_task(Task(id="C", name="C", task_type="Task",
                          start_date=base, end_date=end, progress=0))
    return project


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestThePaintedRows(unittest.TestCase):
    """What the rows look like while a filter is painting them."""

    def setUp(self):
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

        self.project = _plan()
        self.task_list = DragDropTaskList(
            self.root, self.project,
            project_tracker=ProjectStateTracker(self.project,
                                                UndoRedoManager()))
        self.task_list.update_task_list()
        self.root.update_idletasks()

    def tearDown(self):
        try:
            _shut_down(self.root)
        except Exception:
            pass
        try:
            self.ctk.set_appearance_mode(self.opening_mode)
        except Exception:
            pass

    def _fill(self, task_id):
        """The background the row is actually painted with."""
        tags = [tag for tag in self.task_list.tree.item(task_id, 'tags')
                if tag.startswith('row_')]
        return str(self.task_list.tree.tag_configure(tags[0], 'background'))

    def test_matched_rows_take_the_highlight_yellow(self):
        from gantt_app.views import theme
        self.task_list.show_highlighted_rows({"A", "C"})
        self.assertEqual(self._fill("A"), theme.now(theme.GRID_HIGHLIGHT_BG))
        self.assertEqual(self._fill("C"), theme.now(theme.GRID_HIGHLIGHT_BG))

    def test_unmatched_rows_keep_their_banding(self):
        self.task_list.show_highlighted_rows({"A"})
        self.assertNotEqual(
            self._fill("B"),
            str(self.ctk.ThemeManager.theme["CTkFrame"]["fg_color"]))

    def test_the_paint_survives_a_rebuild(self):
        from gantt_app.views import theme
        self.task_list.show_highlighted_rows({"A"})
        self.task_list.update_task_list()
        self.assertEqual(self._fill("A"), theme.now(theme.GRID_HIGHLIGHT_BG))

    def test_critical_red_beats_the_yellow(self):
        """A row both critical and matched stays red."""
        from gantt_app.views import theme
        self.task_list.show_critical_path_rows({"A"})
        self.task_list.show_highlighted_rows({"A", "B"})
        self.assertEqual(self._fill("A"), theme.now(theme.GRID_CRITICAL_BG))
        self.assertEqual(self._fill("B"), theme.now(theme.GRID_HIGHLIGHT_BG))

    def test_the_yellow_follows_the_appearance(self):
        from gantt_app.views import theme
        self.task_list.show_highlighted_rows({"A"})
        self.ctk.set_appearance_mode('dark')
        self.task_list.apply_theme()
        self.assertEqual(self._fill("A"), theme.GRID_HIGHLIGHT_BG[1])

    def test_clearing_leaves_every_row_alone(self):
        self.task_list.show_highlighted_rows({"A"})
        self.task_list.clear_highlight()
        self.assertFalse(self.task_list.highlighted_rows_shown())


if __name__ == "__main__":
    unittest.main()
