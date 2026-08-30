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

        # Where the cell is on screen is answered by the widget, and a
        # window that has never been mapped does not always have an answer:
        # locally the first row had geometry and the rest did not, and on CI
        # under xvfb it differed again. That is the environment rather than
        # the code, and it is not what any of these tests are about - so the
        # box is a fixed rectangle and everything downstream of it runs the
        # same way everywhere. _cell_box's own behaviour is checked in
        # TestFindingTheCell, which does not stub it.
        self.task_list._cell_box = lambda _task_id, _column: (0, 0, 200, 20)

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

    def slow_click(self, task_id: str):
        """
        Click a row that is already selected, and let the rename run.

        The gesture a file manager renames with: two clicks with a pause
        between them. The first selects; the second - this one - starts a
        rename that waits RENAME_DELAY_MS in case a quick second click is
        coming. Here the wait is skipped and the box opened directly.
        """
        self.task_list.tree.selection_set(task_id)
        self.task_list.tree.identify_row = lambda y, item=task_id: item
        self.task_list._column_name = lambda x: '#0'
        self.task_list.on_press(SimpleNamespace(x=5, y=0))
        self.task_list.on_release(SimpleNamespace(x=5, y=0))
        started = self.task_list._rename_pending is not None
        self.task_list._cancel_rename()
        assert started, "the slow click did not start a rename"
        self.task_list.edit_name_cell(task_id)

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
        self.slow_click('u1')

        self.assertIsNotNone(self.task_list._cell_editor)
        self.assertEqual(self.task_list._cell_editor.get(), 'Planning')

    def test_the_editor_knows_which_row_it_is_over(self):
        """Or a commit would rename whichever task was edited last."""
        self.slow_click('u2')

        self.assertEqual(self.task_list._cell_editor_task, 'u2')

    def test_it_does_not_fold_the_branch(self):
        """
        Folding is on the expander, where it is in every other tree.

        Having it here too meant a double-click on a parent's name folded
        the branch away instead of letting the name be typed over.
        """
        self.assertTrue(self.task_list.tree.item('u1', 'open'))

        self.slow_click('u1')

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
            self.slow_click('u1')

        sent.assert_called_once_with('u1')

    def test_another_column_opens_nothing(self):
        """Only the two that are typed over are typed over."""
        self.double_click('u1', column='Start')

        self.assertIsNone(self.task_list._cell_editor)


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class TestTheTwoSpeedsOfClicking(InlineEditingTestCase):
    """
    Which of the two gestures opens which editor.

    Two quick clicks open the task editor. A click, a pause and a second
    click open the name box in the grid. They start the same way - the
    second click of either lands on a row that the first one selected - so
    the rename is scheduled and then called off if a double-click arrives
    inside RENAME_DELAY_MS.
    """

    def press_and_release(self, task_id='u1'):
        """The second click of a gesture, without running the rename."""
        self.task_list.tree.selection_set(task_id)
        self.task_list.tree.identify_row = lambda y, item=task_id: item
        self.task_list._column_name = lambda x: '#0'
        self.task_list.on_press(SimpleNamespace(x=5, y=0))
        self.task_list.on_release(SimpleNamespace(x=5, y=0))

    def test_the_first_click_on_an_unselected_row_schedules_nothing(self):
        """
        Or clicking down a list would leave a name box open behind you.

        A rename is only ever the second click of a pair, so the row has to
        have been selected before the click that starts it.
        """
        self.task_list.tree.selection_set('u2')
        self.task_list.tree.identify_row = lambda _y: 'u1'
        self.task_list._column_name = lambda _x: '#0'

        self.task_list.on_press(SimpleNamespace(x=5, y=0))
        self.task_list.on_release(SimpleNamespace(x=5, y=0))

        self.assertIsNone(self.task_list._rename_pending)

    def test_clicking_a_row_that_is_already_selected_schedules_one(self):
        """The slow rename, waiting to see whether a second click comes."""
        self.press_and_release('u1')

        self.assertIsNotNone(self.task_list._rename_pending)
        self.task_list._cancel_rename()

    def test_a_quick_second_click_calls_the_rename_off(self):
        """
        And opens the task editor instead.

        Both gestures start with the same press, so the double-click has to
        cancel what that press scheduled. Without it the editor opened and
        the name box appeared over the list behind it a moment later.
        """
        from unittest import mock

        self.press_and_release('u1')
        self.assertIsNotNone(self.task_list._rename_pending)

        with mock.patch.object(self.task_list, 'edit_task') as opened:
            self.double_click('u1')

        self.assertIsNone(self.task_list._rename_pending,
                          "the rename should have been called off")
        opened.assert_called_once_with('u1')

    def test_the_rename_stands_down_if_the_selection_moved(self):
        """
        The wait is long enough for anything to have happened in it.

        Asked again when it fires rather than trusted from when it was
        scheduled.
        """
        from unittest import mock

        with mock.patch.object(self.task_list, 'edit_name_cell') as opened:
            self.task_list.tree.selection_set('u2')
            self.task_list._rename_if_still_wanted('u1')

        opened.assert_not_called()

    def test_the_rename_stands_down_if_the_row_has_gone(self):
        """Deleted under the wait, which leaves a box over nothing."""
        from unittest import mock

        self.task_list.tree.delete('u1')

        with mock.patch.object(self.task_list, 'edit_name_cell') as opened:
            self.task_list._rename_if_still_wanted('u1')

        opened.assert_not_called()

    def test_a_pending_rename_does_not_outlive_the_list(self):
        """A timer firing into a destroyed widget is a Tk error."""
        self.press_and_release('u1')

        self.task_list.destroy()

        self.assertIsNone(self.task_list._rename_pending)


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class TestFindingTheCell(InlineEditingTestCase):
    """
    Where a cell is, which is the one thing the environment decides.

    Everything else in this module stubs it; this is what checks it, and it
    checks the answers that do not depend on a window being on screen.
    """

    def setUp(self):
        """Undo the stub the other tests rely on."""
        super().setUp()
        del self.task_list._cell_box

    def test_a_row_that_is_not_there_has_no_cell(self):
        """The commit runs from a focus change, so the row may have gone."""
        self.assertIsNone(self.task_list._cell_box('nobody', '#0'))

    def test_no_geometry_means_no_editor_rather_than_a_crash(self):
        """
        A box cannot be placed over a cell nobody can point at.

        Opening one at 0,0 instead would put a typing box in the corner of
        the grid over whatever row happened to be there.
        """
        self.task_list._cell_box = lambda _task_id, _column: None

        self.task_list.edit_name_cell('u1')

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
        self.slow_click('u1')
        self.type_into_editor('Project Planning')

        self.task_list._commit_name()

        self.assertEqual(self.name(), 'Project Planning')

    def test_the_grid_shows_it(self):
        """The column redraws from the task."""
        self.slow_click('u1')
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
        self.slow_click('u1')
        self.type_into_editor('Renamed')

        self.task_list._commit_name()

        self.assertIsNone(self.task_list._cell_editor)

    def test_escape_leaves_the_name_alone(self):
        """What was typed is discarded."""
        self.slow_click('u1')
        self.type_into_editor('Not saved')

        self.task_list._close_cell_editor()

        self.assertEqual(self.name(), 'Planning')

    def test_an_empty_name_puts_the_old_one_back(self):
        """
        A row has to be called something.

        Quietly reverting says so and gets out of the way; a dialog would be
        a reprimand for clicking away from a box somebody had cleared.
        """
        self.slow_click('u1')
        self.type_into_editor('   ')

        self.task_list._commit_name()

        self.assertEqual(self.name(), 'Planning')

    def test_surrounding_space_is_trimmed(self):
        """A name is what was meant, not what the keyboard left behind."""
        self.slow_click('u1')
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
        self.slow_click('u1')
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


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class TestChoosingTheTypeInTheGrid(InlineEditingTestCase):
    """
    The Type cell offers its four answers in a dropdown.

    WHY THESE EXIST:
    ================
    Changing a type meant opening the editor, and for a nested row not even
    that: the editor's Type menu was greyed out for anything with a parent.
    The column is the fast way, and the type is the one field most often
    changed after a row is made.
    """

    def open_chooser(self, task_id='u1'):
        """Double-click the Type cell of one row."""
        self.task_list.tree.identify_row = lambda _y: task_id
        self.task_list._column_name = lambda _x: 'Type'
        self.task_list.on_double_click(SimpleNamespace(x=5, y=0))
        return self.task_list._cell_editor

    def type_of(self, task_id='u1'):
        """What the plan says the row is."""
        return self.project.get_task_by_id(task_id).task_type

    def test_a_double_click_on_the_type_cell_opens_a_list(self):
        """Not a typing box: the answer is one of four."""
        from tkinter import ttk

        chooser = self.open_chooser()

        self.assertIsInstance(chooser, ttk.Combobox)

    def test_it_offers_every_type_in_the_system(self):
        """All of them, so none has to be reached another way."""
        from gantt_app.models import TASK_TYPES

        chooser = self.open_chooser()

        self.assertEqual(list(chooser.cget('values')), list(TASK_TYPES))

    def test_it_opens_showing_what_the_row_is(self):
        """Or picking the current type would look like a change."""
        self.assertEqual(self.open_chooser().get(), 'Task')

    def test_it_cannot_be_typed_into(self):
        """A cell whose only valid answers are listed takes no others."""
        self.assertEqual(str(self.open_chooser().cget('state')), 'readonly')

    def test_a_nested_row_gets_the_same_list(self):
        """
        Which the editor used to refuse.

        A sub-task could not change type without being moved first, so a
        row nested by mistake had no way to say what it was.
        """
        from gantt_app.models import TASK_TYPES

        chooser = self.open_chooser('u2')

        self.assertEqual(list(chooser.cget('values')), list(TASK_TYPES))

    def test_choosing_stores_it(self):
        """There is nothing to confirm about picking from a list."""
        self.task_list.set_task_type('u1', 'Phase')

        self.assertEqual(self.type_of(), 'Phase')

    def test_the_column_shows_it(self):
        """The grid and the plan agree."""
        self.task_list.set_task_type('u1', 'Phase')

        self.assertEqual(self.task_list.tree.set('u1', 'Type'), 'Phase')

    def test_the_editor_shows_it(self):
        """A change stored in the grid is the task's, not the column's."""
        self.task_list.set_task_type('u2', 'Task')

        self.assertEqual(
            self.project.get_task_by_id('u2').task_type, 'Task')

    def test_it_is_one_step_in_the_undo_history(self):
        """Like every other edit."""
        self.task_list.set_task_type('u1', 'Phase')

        self.assertTrue(self.manager.can_undo())

    def test_undo_puts_the_old_type_back(self):
        """And redo brings the new one again."""
        self.task_list.set_task_type('u1', 'Phase')

        self.manager.undo()
        self.assertEqual(self.type_of(), 'Task')

        self.manager.redo()
        self.assertEqual(self.type_of(), 'Phase')

    def test_choosing_the_type_it_already_is_costs_nothing(self):
        """No undo step for a change that changed nothing."""
        self.task_list.set_task_type('u1', 'Task')

        self.assertFalse(self.manager.can_undo())

    def test_a_type_that_is_not_one_is_refused(self):
        """The list cannot offer one, but the method is callable."""
        self.task_list.set_task_type('u1', 'Deliverable')

        self.assertEqual(self.type_of(), 'Task')


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class TestTheMilestoneFlagFollowsTheType(InlineEditingTestCase):
    """
    Typing a row Milestone in the grid ticks the editor's milestone box.

    WHY THESE EXIST:
    ================
    Task.effective_milestone is true for either the type or the flag, so the
    two say the same thing and have to be written together. Setting only the
    type left the flag behind: a row typed back from Milestone to Task still
    carried it, drew as a diamond and had no end date.
    """

    def task(self, task_id='u1'):
        """The row itself."""
        return self.project.get_task_by_id(task_id)

    def test_choosing_milestone_sets_the_flag(self):
        """So the editor opens with the switch on."""
        self.task_list.set_task_type('u1', 'Milestone')

        self.assertTrue(self.task().is_milestone)
        self.assertTrue(self.task().effective_milestone)

    def test_choosing_anything_else_clears_it(self):
        """Or a Task would go on drawing as a diamond."""
        self.task_list.set_task_type('u1', 'Milestone')

        self.task_list.set_task_type('u1', 'Task')

        self.assertFalse(self.task().is_milestone)
        self.assertFalse(self.task().effective_milestone)

    def test_undo_takes_the_flag_back_with_the_type(self):
        """Both were written in one step, so both come back in one."""
        self.task_list.set_task_type('u1', 'Milestone')

        self.manager.undo()

        self.assertEqual(self.task().task_type, 'Task')
        self.assertFalse(self.task().is_milestone)

    def test_the_editor_opens_with_the_box_ticked(self):
        """Which is what the request asked to be able to see."""
        from unittest import mock
        from gantt_app.views.taskdialogs import EditTaskDialog

        self.task_list.set_task_type('u1', 'Milestone')

        dialog = EditTaskDialog(self.root, self.task(), self.project,
                                on_save=lambda t: None,
                                on_delete=lambda i: None)
        dialog.withdraw()
        try:
            self.assertTrue(dialog.is_milestone_var.get())
            self.assertEqual(dialog.task_type_var.get(), 'Milestone')
        finally:
            dialog.destroy()


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class TestTheEditorCanRetypeAnyRow(InlineEditingTestCase):
    """
    The Type menu is live for every row, nested or not.

    WHY THESE EXIST:
    ================
    It was greyed out for anything with a parent, and the save skipped the
    field for the same rows - so a sub-task's type was decided by where it
    sat and could not be stated. The type is the user's; where the row sits
    is a separate statement.
    """

    def dialog(self, task_id):
        """An edit dialog over one row."""
        from gantt_app.views.taskdialogs import EditTaskDialog

        dialog = EditTaskDialog(self.root, self.project.get_task_by_id(task_id),
                                self.project, on_save=lambda t: None,
                                on_delete=lambda i: None)
        dialog.withdraw()
        dialog.update_idletasks()
        return dialog

    def test_a_nested_row_can_be_retyped_from_the_editor(self):
        """The menu is not greyed out any more."""
        import tkinter as tk

        dialog = self.dialog('u2')
        try:
            self.assertNotEqual(str(dialog.task_type_menu.cget('state')),
                                tk.DISABLED)
        finally:
            dialog.destroy()

    def test_saving_a_nested_row_writes_the_type(self):
        """Which the save used to skip for a row with a parent."""
        dialog = self.dialog('u2')
        try:
            dialog.task_type_var.set('Task')
            dialog.save()
        finally:
            if dialog.winfo_exists():
                dialog.destroy()

        self.assertEqual(self.project.get_task_by_id('u2').task_type, 'Task')

    def test_the_row_keeps_its_parent(self):
        """Retyping says what a row is, not where it sits."""
        dialog = self.dialog('u2')
        try:
            dialog.task_type_var.set('Task')
            dialog.save()
        finally:
            if dialog.winfo_exists():
                dialog.destroy()

        self.assertEqual(self.project.get_task_by_id('u2').parent_task_id,
                         'u1')


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class TestMakingATaskFromTheKeyboard(InlineEditingTestCase):
    """
    Option+Command+. on a Mac, Ctrl+Alt+. elsewhere.

    WHY THESE EXIST:
    ================
    Creating a row was a menu or a right-click away, and the right-click
    needs a row to open on - so the first row of a plan could only be made
    from the menu.
    """

    def test_it_creates_beside_the_focused_row(self):
        """Where the cursor is, which is where the reader is looking."""
        from unittest import mock

        self.task_list.tree.selection_set('u2')
        self.task_list.tree.focus('u2')

        with mock.patch.object(self.task_list, 'create_task') as made:
            self.task_list.create_task_at_cursor()

        made.assert_called_once_with('Task', 'u2')

    def test_it_goes_at_the_end_with_no_cursor(self):
        """A list nobody has clicked in yet still makes a row."""
        from unittest import mock

        self.task_list.tree.selection_remove(*self.task_list.tree.selection())
        self.task_list.tree.focus('')

        with mock.patch.object(self.task_list, 'create_task') as made:
            self.task_list.create_task_at_cursor()

        made.assert_called_once_with('Task', None)

    def test_the_key_is_the_platform_s(self):
        """Option on a Mac, Alt elsewhere, with the usual modifier."""
        from gantt_app.shortcuts import (
            ALT, IS_MACOS, MODIFIER, accelerator, sequences,
        )

        self.assertEqual(sequences('.', alt=True),
                         (f"<{MODIFIER}-{ALT}-period>",))
        self.assertEqual(accelerator('.', alt=True),
                         '⌥⌘.' if IS_MACOS else 'Ctrl+Alt+.')

    def test_it_does_not_collide_with_plain_period(self):
        """Plain Cmd+. is not bound, but this shortcut still requires Option."""
        from gantt_app.shortcuts import sequences

        self.assertNotEqual(set(sequences('.')), set(sequences('.', alt=True)))
