"""
Tests for typing over a task's name in the grid.

WHY THIS MODULE EXISTS:
======================
Renaming a task meant opening a dialog, changing one field and saving. It is
the commonest edit there is, and the grid already had the machinery for typing
into a cell - the Dependencies column uses it - so the name uses it too.

What has to be true is that the grid is not keeping a string of its own: the
name goes onto the task, so the editor shows it and the undo history can take
it back. A cell that only changed what the column displayed would leave the
editor showing the old name, and the next save would write that back over it.

Double-clicking no longer folds a branch. It was on both the expander and this
gesture, which meant double-clicking a parent's name folded it away instead of
letting the name be typed over - and the name is what somebody double-clicking
it wants.

DEVELOPMENT NOTES:
------------------
Double-clicks cannot be delivered to an unmapped window, so the row and column
the event would have landed on are stood in for and the handler is called
directly. That is the same code a press reaches.
"""

import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace

from gantt_app.models import Project, Task

BASE = datetime(2026, 8, 25)


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
class InlineEditingTestCase(unittest.TestCase):
    """A parent with a sub-task under it, and an undo history."""

    def setUp(self):
        """Build the list."""
        import customtkinter as ctk

        from gantt_app.utils.undoredo import (
            ProjectStateTracker, UndoRedoManager,
        )
        from gantt_app.views.task_list import DragDropTaskList

        self.root = ctk.CTk()
        self.root.withdraw()

        self.project = Project(name="Plan")
        self.project.add_task(Task(id='u1', name='Planning', task_type='Task',
                                   start_date=BASE,
                                   end_date=BASE + timedelta(days=2)))
        self.project.add_task(Task(id='u2', name='Sub', task_type='Subtask',
                                   parent_task_id='u1', start_date=BASE,
                                   end_date=BASE + timedelta(days=1)))

        self.manager = UndoRedoManager()
        self.task_list = DragDropTaskList(
            self.root, self.project,
            project_tracker=ProjectStateTracker(self.project, self.manager))
        self.root.update_idletasks()

    def tearDown(self):
        """Close the window."""
        try:
            self.root.destroy()
        except Exception:
            pass

    def double_click(self, task_id: str, column: str = '#0'):
        """
        Double-click one cell of one row.

        The column is named here and turned into the reference Tk would
        have given - '#4' and the like, counting the data columns from one.
        Standing in with the name instead means the handler's own lookup is
        skipped, and it is the lookup that decides which editor opens.
        """
        if column == '#0':
            reference = '#0'
        else:
            columns = list(self.task_list.tree.cget('columns'))
            reference = f"#{columns.index(column) + 1}"

        self.task_list.tree.identify_row = lambda _y: task_id
        self.task_list.tree.identify_column = lambda _x: reference
        return self.task_list.on_double_click(SimpleNamespace(x=5, y=0))

    def type_into_editor(self, text: str):
        """Replace what the open editor holds."""
        editor = self.task_list._cell_editor
        editor.delete(0, 'end')
        editor.insert(0, text)

    def name(self, task_id='u1') -> str:
        """What the task is called now."""
        return self.project.get_task_by_id(task_id).name


class TestDoubleClickingTheName(InlineEditingTestCase):
    """The gesture, and what it opens."""

    def test_it_opens_an_editor_over_the_name(self):
        """Holding what the task is called, ready to be replaced."""
        self.double_click('u1')

        self.assertIsNotNone(self.task_list._cell_editor)
        self.assertEqual(self.task_list._cell_editor.get(), 'Planning')

    def test_the_editor_knows_which_row_it_is_over(self):
        """Or a commit would rename whichever task was edited last."""
        self.double_click('u2')

        self.assertEqual(self.task_list._cell_editor_task, 'u2')

    def test_it_does_not_fold_the_branch(self):
        """
        Folding is on the expander, where it is in every other tree.

        Having it here too meant a double-click on a parent's name folded
        the branch away instead of letting the name be typed over.
        """
        self.assertTrue(self.task_list.tree.item('u1', 'open'))

        self.double_click('u1')

        self.assertTrue(self.task_list.tree.item('u1', 'open'))

    def test_the_dependencies_cell_is_routed_to_its_own_editor(self):
        """
        The two share the machinery; they do not share a column.

        Checked by where the double-click is sent rather than by whether a
        box appeared: placing one needs the column laid out at its final
        width, which it is not on a window that has never been mapped.
        """
        from unittest import mock

        with mock.patch.object(self.task_list, 'edit_dependencies_cell') as sent:
            self.double_click('u1', column='Dependencies')

        sent.assert_called_once_with('u1')

    def test_the_name_cell_is_routed_to_the_name_editor(self):
        """The other half of the same routing."""
        from unittest import mock

        with mock.patch.object(self.task_list, 'edit_name_cell') as sent:
            self.double_click('u1', column='#0')

        sent.assert_called_once_with('u1')

    def test_another_column_opens_nothing(self):
        """Only the two that are typed over are typed over."""
        self.double_click('u1', column='Start')

        self.assertIsNone(self.task_list._cell_editor)

    def test_the_default_handler_is_suppressed(self):
        """
        ttk's own double-click would toggle the row underneath the editor
        that has just been placed over it.
        """
        self.assertEqual(self.double_click('u1'), 'break')


class TestSavingTheName(InlineEditingTestCase):
    """Enter, and clicking away."""

    def test_enter_stores_it(self):
        """On the task, which is what makes it real."""
        self.double_click('u1')
        self.type_into_editor('Project Planning')

        self.task_list._commit_name()

        self.assertEqual(self.name(), 'Project Planning')

    def test_the_grid_shows_it(self):
        """The column redraws from the task."""
        self.double_click('u1')
        self.type_into_editor('Project Planning')

        self.task_list._commit_name()

        self.assertEqual(self.task_list.tree.item('u1', 'text'),
                         'Project Planning')

    def test_the_editor_is_taken_away(self):
        """
        Before anything is stored, because storing redraws the list.

        An entry left over a row that has just been destroyed is a box
        floating over the wrong task.
        """
        self.double_click('u1')
        self.type_into_editor('Renamed')

        self.task_list._commit_name()

        self.assertIsNone(self.task_list._cell_editor)

    def test_escape_leaves_the_name_alone(self):
        """What was typed is discarded."""
        self.double_click('u1')
        self.type_into_editor('Not saved')

        self.task_list._close_cell_editor()

        self.assertEqual(self.name(), 'Planning')

    def test_an_empty_name_puts_the_old_one_back(self):
        """
        A row has to be called something.

        Quietly reverting says so and gets out of the way; a dialog would be
        a reprimand for clicking away from a box somebody had cleared.
        """
        self.double_click('u1')
        self.type_into_editor('   ')

        self.task_list._commit_name()

        self.assertEqual(self.name(), 'Planning')

    def test_surrounding_space_is_trimmed(self):
        """A name is what was meant, not what the keyboard left behind."""
        self.double_click('u1')
        self.type_into_editor('  Project Planning  ')

        self.task_list._commit_name()

        self.assertEqual(self.name(), 'Project Planning')

    def test_renaming_it_to_what_it_is_costs_nothing(self):
        """No redraw, and nothing added to undo."""
        depth = len(self.manager.undo_stack)

        self.task_list.set_task_name('u1', 'Planning')

        self.assertEqual(len(self.manager.undo_stack), depth)

    def test_a_row_deleted_under_the_editor_is_not_renamed(self):
        """The commit runs from a focus change, which can happen at any time."""
        self.double_click('u1')
        self.type_into_editor('Renamed')
        self.project.remove_task('u1')

        self.task_list._commit_name()

        self.assertIsNone(self.project.get_task_by_id('u1'))


class TestItReachesTheRestOfTheApplication(InlineEditingTestCase):
    """What the user asked for: the editor sees it, and undo takes it back."""

    def test_the_task_editor_shows_the_new_name(self):
        """
        The grid stores the name on the task rather than keeping a string.

        A cell that only changed the column would leave the editor showing
        the old name, and its next save would write that back over it.
        """
        self.task_list.set_task_name('u1', 'Project Planning')

        self.assertEqual(self.project.get_task_by_id('u1').name,
                         'Project Planning')

    def test_it_is_one_step_in_the_undo_history(self):
        """Like a rename typed into the editor."""
        depth = len(self.manager.undo_stack)

        self.task_list.set_task_name('u1', 'Project Planning')

        self.assertEqual(len(self.manager.undo_stack), depth + 1)

    def test_undo_puts_the_old_name_back(self):
        """In the model and in the grid."""
        self.task_list.set_task_name('u1', 'Project Planning')

        self.manager.undo()
        self.task_list.update_task_list()

        self.assertEqual(self.name(), 'Planning')
        self.assertEqual(self.task_list.tree.item('u1', 'text'), 'Planning')

    def test_redo_brings_it_back(self):
        """The other direction."""
        self.task_list.set_task_name('u1', 'Project Planning')
        self.manager.undo()

        self.manager.redo()

        self.assertEqual(self.name(), 'Project Planning')

    def test_renaming_does_not_disturb_the_rest_of_the_task(self):
        """
        The tracker rebuilds a task from a list of fields, so anything
        missing from that list is reset by any update at all.
        """
        task = self.project.get_task_by_id('u1')
        task.calendar_id = 'weekend'
        task.progress = 40

        self.task_list.set_task_name('u1', 'Renamed')

        task = self.project.get_task_by_id('u1')
        self.assertEqual(task.calendar_id, 'weekend')
        self.assertEqual(task.progress, 40)


if __name__ == '__main__':
    unittest.main()
