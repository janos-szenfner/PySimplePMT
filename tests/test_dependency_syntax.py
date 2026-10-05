"""
Tests for the Dependencies column: typing into the grid.

WHY THIS MODULE EXISTS:
======================
The grammar - what a cell takes, what it writes back, what it refuses -
and the checks a number alone cannot answer are model arithmetic and
live in tests/features/dependency_syntax.feature with their steps in
tests/test_dependency_syntax_bdd.py.

What is kept here is the column itself: what the cell shows for a task,
what committing one stores, how a bad cell is refused, and that a whole
cell is one undo step. It needs a display and skips without one.
"""

import unittest
from datetime import datetime, timedelta

from gantt_app.core.models import Project, Task

BASE = datetime(2026, 8, 25)


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
    """Whether a usable Tk display is present."""
    try:
        import tkinter
        root = tkinter.Tk()
    except Exception:
        return False
    root.destroy()
    return True


HAVE_DISPLAY = _display_available()


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class TestTypingIntoTheGrid(unittest.TestCase):
    """The column itself: what it shows, and what it stores."""

    def setUp(self):
        """A list over three tasks, with an undo history behind it."""
        import customtkinter as ctk

        from gantt_app.utils.undoredo import (
            ProjectStateTracker, UndoRedoManager,
        )
        from gantt_app.views.task_list import DragDropTaskList

        self.root = ctk.CTk()
        self.root.withdraw()

        self.project = Project(name="Plan")
        for task_id, name in (('u1', 'Planning'), ('u2', 'Design'),
                              ('u3', 'Build')):
            self.project.add_task(Task(id=task_id, name=name,
                                       task_type="Task", start_date=BASE,
                                       end_date=BASE + timedelta(days=2)))

        self.manager = UndoRedoManager()
        self.task_list = DragDropTaskList(
            self.root, self.project,
            project_tracker=ProjectStateTracker(self.project, self.manager))
        self.root.update_idletasks()

    def tearDown(self):
        """Close the window."""
        try:
            _shut_down(self.root)
        except Exception:
            pass

    def cell(self, task_id: str) -> str:
        """What the Dependencies column shows for a row."""
        return self.task_list.tree.set(task_id, 'Dependencies')

    def test_an_empty_cell_says_so(self):
        """Rather than showing nothing at all."""
        self.assertEqual(self.cell('u3'), 'None')

    def test_what_is_stored_is_shown_in_the_grammar(self):
        """So the cell can be typed straight back in."""
        links, _errors = self.project.parse_dependencies('u3', '1, 2SS+1d')

        self.task_list.set_dependencies('u3', links)

        self.assertEqual(self.cell('u3'), '1, 2SS+1d')

    def test_the_cell_normalises_to_the_same_text(self):
        """
        The round trip, through the grid this time.

        A cell that came back differently from how it went in would rewrite
        the reader's work every time they pressed Enter.
        """
        for typed in ('1', '1FS+2d', '2SS-1d', '2FF', '1SF+50%'):
            links, errors = self.project.parse_dependencies('u3', typed)
            self.assertEqual(errors, [], typed)

            self.task_list.set_dependencies('u3', links)

            self.assertEqual(self.cell('u3'), typed)

    def test_a_whole_cell_is_one_undo_step(self):
        """Typing a column of links should not cost a press each to undo."""
        links, _errors = self.project.parse_dependencies('u3', '1, 2')
        depth = len(self.manager.undo_stack)

        self.task_list.set_dependencies('u3', links)

        self.assertEqual(len(self.manager.undo_stack), depth + 1)

    def test_undo_puts_the_cell_back(self):
        """Both the links and what the column shows."""
        links, _errors = self.project.parse_dependencies('u3', '1, 2')
        self.task_list.set_dependencies('u3', links)

        self.manager.undo()
        self.task_list.update_task_list()

        self.assertEqual(self.cell('u3'), 'None')

    def test_the_task_editor_shows_what_the_grid_stored(self):
        """
        Which is the point of storing real links rather than a string.

        A cell that only changed what the column displayed would leave the
        editor showing nothing, and the next save would write that nothing
        back over it.
        """
        links, _errors = self.project.parse_dependencies('u3', '1, 2SS+1d')
        self.task_list.set_dependencies('u3', links)

        stored = self.project.get_task_by_id('u3').dependencies

        self.assertEqual([(link.task_id, link.dep_type, link.lag)
                          for link in stored],
                         [('u1', 'FS', 0), ('u2', 'SS', 1)])

    def test_a_cell_with_an_error_stores_nothing(self):
        """
        Not even the half of it that parsed.

        Storing the good half would silently drop the rest, and the reader
        would have to compare what they typed against what came back.
        """
        from unittest import mock

        self.task_list._cell_editor = mock.Mock(get=lambda: '1, 9')
        self.task_list._cell_editor_task = 'u3'

        with mock.patch('gantt_app.views.task_list.messagebox.showerror') as told:
            self.task_list._commit_dependencies()

        self.assertTrue(told.called, "the reader was not told")
        self.assertEqual(list(self.project.get_task_by_id('u3').dependencies), [])

    def test_a_cell_that_reads_stores_it(self):
        """The same path, with something it can read."""
        from unittest import mock

        self.task_list._cell_editor = mock.Mock(get=lambda: '1')
        self.task_list._cell_editor_task = 'u3'

        self.task_list._commit_dependencies()

        self.assertEqual([link.task_id for link in
                          self.project.get_task_by_id('u3').dependencies],
                         ['u1'])

    def test_clearing_the_cell_removes_the_links(self):
        """An empty cell means no links, not 'leave them alone'."""
        from unittest import mock

        links, _errors = self.project.parse_dependencies('u3', '1')
        self.task_list.set_dependencies('u3', links)

        self.task_list._cell_editor = mock.Mock(get=lambda: '')
        self.task_list._cell_editor_task = 'u3'
        self.task_list._commit_dependencies()

        self.assertEqual(list(self.project.get_task_by_id('u3').dependencies), [])

    def test_the_dependencies_column_is_the_one_that_edits(self):
        """
        Double-clicking anywhere else still folds the branch.

        The column is found by name rather than by number: adding a column
        shifts every one after it, and a check against '#8' would go on
        working and mean something else.
        """
        columns = self.task_list.tree.cget('columns')

        self.assertIn('Dependencies', columns)


if __name__ == '__main__':
    unittest.main()
