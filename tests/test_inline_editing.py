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
        self.project.add_task(Task(id='u2', name='Sub', task_type='Task',
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
            _shut_down(self.root)
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
            # Tk counts the columns on show, not the full set: with one
            # hidden, '#4' means the fourth *displayed* column.
            columns = self.task_list._shown_columns()
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

    def test_a_leaf_s_progress_cell_is_routed_to_its_own_editor(self):
        """
        Issue #61: the completion is typed in place, like the dates.

        u2 is the leaf; the percentage it carries is its own, so the grid
        takes the typing rather than opening the form.
        """
        from unittest import mock

        with mock.patch.object(self.task_list, 'edit_progress_cell') as sent:
            self.double_click('u2', column='Progress')

        sent.assert_called_once_with('u2')

    def test_a_summary_s_progress_cell_opens_the_form(self):
        """
        Its figure is rolled up from the work beneath it.

        Typing over it would be overwritten by the next roll-up, so the
        cell does what a summary's schedule cells do - opens the editor,
        where the field explains it is derived.
        """
        from unittest import mock

        with mock.patch.object(self.task_list, 'edit_task') as sent:
            self.double_click('u1', column='Progress')

        sent.assert_called_once_with('u1')

    def test_a_schedule_column_is_routed_to_its_own_editor(self):
        """
        A leaf's Duration, Start and End are typed in place (issues #23, #31).

        u2 is the leaf; u1 has a child, so it rolls its dates up and its
        schedule cells open the form instead.
        """
        from unittest import mock

        for column in ('Duration', 'Start', 'End'):
            with mock.patch.object(self.task_list,
                                   'edit_schedule_cell') as sent:
                self.double_click('u2', column=column)
            sent.assert_called_once_with('u2', column)


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

    def test_an_empty_name_clears_the_name(self):
        """
        A row need not be called anything, so clearing one clears it.

        The create dialog makes blank rows too; the grid clearing a name is
        the same choice one level down. See issue #3.
        """
        self.slow_click('u1')
        self.type_into_editor('   ')

        self.task_list._commit_name()

        self.assertEqual(self.name(), '')

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
        from gantt_app.core.models import TASK_TYPES

        chooser = self.open_chooser()

        self.assertEqual(list(chooser.cget('values')), list(TASK_TYPES))

    def test_milestone_is_not_one_of_them(self):
        """
        Issue #73: a milestone is a flag, not a type.

        Choosing it here used to write both the type and the flag; the
        switch on the form and a nought in the Duration cell say it now.
        """
        self.assertNotIn('Milestone', self.open_chooser().cget('values'))

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
        from gantt_app.core.models import TASK_TYPES

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

    def test_it_closes_on_focus_leaving_for_the_tree(self):
        """
        Clicking off the Type cell without choosing takes the dropdown away.

        It used to stay open and editable, so the row looked stuck. The
        settle step reads where the focus came to rest; here it is the tree
        the chooser sits over - the gesture of clicking another line - so the
        chooser closes. Driven directly rather than through a real click,
        because whether a withdrawn test window takes focus is unreliable.
        """
        chooser = self.open_chooser()
        self.assertIsNotNone(self.task_list._cell_editor)

        popdown = chooser.tk.call('ttk::combobox::PopdownWindow', chooser)
        stays = self.task_list._focus_within_chooser(
            str(chooser), str(popdown), str(self.task_list.tree))
        self.assertFalse(stays)
        # What settle does when the focus has left: take the field away.
        self.task_list._close_cell_editor()
        self.assertIsNone(self.task_list._cell_editor)

    def test_leaving_without_a_pick_keeps_the_original_type(self):
        """The abandoned edit changes nothing and adds no undo step."""
        self.open_chooser()
        self.task_list._close_cell_editor()

        self.assertEqual(self.type_of(), 'Task')
        self.assertFalse(self.manager.can_undo())


class TestTheTypeChooserFocusDecision(unittest.TestCase):
    """
    Where the focus comes to rest decides whether the chooser stays open.

    WHY THESE EXIST:
    ================
    The chooser must ignore focus moving into its own dropdown list - that
    happens the instant the list opens - while closing when focus genuinely
    leaves. The tree the chooser sits over is the trap: its path is a prefix
    of the chooser's, so a naive "starts with" test the wrong way round would
    read a click on another row as staying. This is pure path logic, so it is
    checked without a display.
    """

    from gantt_app.views.task_list import DragDropTaskList
    decide = staticmethod(DragDropTaskList._focus_within_chooser)

    CHOOSER = '.!treeview.!combobox'
    POPDOWN = '.!treeview.!combobox.popdown'

    def test_focus_on_the_chooser_itself_stays(self):
        self.assertTrue(self.decide(self.CHOOSER, self.POPDOWN, self.CHOOSER))

    def test_focus_inside_the_dropdown_list_stays(self):
        listbox = self.POPDOWN + '.f.l'
        self.assertTrue(self.decide(self.CHOOSER, self.POPDOWN, listbox))

    def test_focus_on_a_child_of_the_chooser_stays(self):
        self.assertTrue(
            self.decide(self.CHOOSER, self.POPDOWN, self.CHOOSER + '.entry'))

    def test_focus_on_the_tree_it_sits_over_leaves(self):
        """The prefix trap: the tree's path is shorter, not inside."""
        self.assertFalse(self.decide(self.CHOOSER, self.POPDOWN, '.!treeview'))

    def test_focus_on_an_unrelated_widget_leaves(self):
        self.assertFalse(
            self.decide(self.CHOOSER, self.POPDOWN, '.!frame.!button'))

    def test_no_focus_at_all_leaves(self):
        self.assertFalse(self.decide(self.CHOOSER, self.POPDOWN, ''))


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class TestTheMilestoneFlagFollowsTheDuration(InlineEditingTestCase):
    """
    A nought typed into the Duration cell is how a row becomes a milestone.

    WHY THESE EXIST:
    ================
    Milestone stopped being a type in issue #73 - it is a flag saying a
    task takes no time, and the length typed into the grid is what writes
    it. A nought sets the flag, a real length on a milestone brings the
    row back to a task, and both travel as one undoable step.
    """

    def task(self, task_id='u1'):
        """The row itself."""
        return self.project.get_task_by_id(task_id)

    def set_duration(self, days):
        """The write a Duration-cell commit ends in."""
        task = self.task()
        start, end, _d, snet = self.project.reconcile_schedule(
            task, task.start_date, task.end_date, days)
        self.task_list.set_schedule('u1', start, end, _d, snet)

    def test_typing_nought_sets_the_flag(self):
        """So the row draws as a diamond and the editor's switch is on."""
        self.set_duration(0)

        self.assertTrue(self.task().is_milestone)
        self.assertTrue(self.task().effective_milestone)
        self.assertEqual(self.task().end_date, self.task().start_date)

    def test_a_real_length_clears_it(self):
        """Or a milestone typed back to a length would go on drawing as one."""
        self.set_duration(0)

        self.set_duration(3)

        self.assertFalse(self.task().is_milestone)
        self.assertFalse(self.task().effective_milestone)
        self.assertNotEqual(self.task().end_date, self.task().start_date)

    def test_undo_takes_the_flag_back_with_the_length(self):
        """Both were written in one step, so both come back in one."""
        self.set_duration(0)

        self.manager.undo()

        self.assertFalse(self.task().is_milestone)
        self.assertNotEqual(self.task().end_date, self.task().start_date)

    def test_the_editor_opens_with_the_box_ticked(self):
        """Which is what the request asked to be able to see."""
        from gantt_app.views.taskdialogs import EditTaskDialog

        self.set_duration(0)

        dialog = EditTaskDialog(self.root, self.task(), self.project,
                                on_save=lambda t: None,
                                on_delete=lambda i: None)
        dialog.withdraw()
        try:
            self.assertTrue(dialog.is_milestone_var.get())
            self.assertEqual(dialog.task_type_var.get(), 'Task')
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

    def tracked_dialog(self, task_id):
        """An edit dialog wired to the undo history."""
        from gantt_app.views.taskdialogs import EditTaskDialog

        dialog = EditTaskDialog(
            self.root, self.project.get_task_by_id(task_id), self.project,
            on_save=lambda t: None, on_delete=lambda i: None,
            project_tracker=self.task_list.project_tracker)
        dialog.withdraw()
        dialog.update_idletasks()
        return dialog

    def save_as_milestone(self, task_id):
        """Retype a row through the editor, as the issue's reader did."""
        dialog = self.tracked_dialog(task_id)
        try:
            dialog.task_type_var.set('Milestone')
            dialog.is_milestone_var.set(True)
            dialog.save()
        finally:
            if dialog.winfo_exists():
                dialog.destroy()

    def test_a_group_retyped_as_a_milestone_promotes_its_rows_one_level(self):
        """
        Issue #58: they join the milestone's level, not the top of the plan.

        The normalise pass used to set every orphan's parent to None, so a
        sub-task group turned milestone dropped its rows at the top of the
        plan - and the reparenting ran inside the refresh, outside the
        save's undo record, so undo could not put them back.
        """
        self.project.add_task(Task(
            id='u3', name='Grand', task_type='Task', parent_task_id='u2',
            start_date=BASE, end_date=BASE + timedelta(days=1)))

        self.save_as_milestone('u2')

        promoted = self.project.get_task_by_id('u3')
        self.assertEqual(promoted.parent_task_id, 'u1')
        self.assertEqual(promoted.task_type, 'Task')

        self.assertTrue(self.manager.undo())
        restored = self.project.get_task_by_id('u3')
        self.assertEqual(restored.parent_task_id, 'u2')
        self.assertEqual(
            self.project.get_task_by_id('u2').task_type, 'Task')

    def test_a_promoted_group_keeps_the_rows_under_it(self):
        """
        Issue #58's second example: a nested group stays a group.

        Only the milestone's own children move, each up one level; what
        sat under one of them keeps the parent it had.
        """
        self.project.add_task(Task(
            id='u3', name='Inner group', task_type='Task',
            parent_task_id='u2', start_date=BASE,
            end_date=BASE + timedelta(days=2)))
        self.project.add_task(Task(
            id='u4', name='Deep', task_type='Task', parent_task_id='u3',
            start_date=BASE, end_date=BASE + timedelta(days=1)))

        self.save_as_milestone('u2')

        group = self.project.get_task_by_id('u3')
        self.assertEqual(group.parent_task_id, 'u1')
        self.assertEqual(
            self.project.get_task_by_id('u4').parent_task_id, 'u3')

        self.assertTrue(self.manager.undo())
        self.assertEqual(
            self.project.get_task_by_id('u3').parent_task_id, 'u2')
        self.assertEqual(
            self.project.get_task_by_id('u4').parent_task_id, 'u3')


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class TestTypingIntoTheProgressCell(InlineEditingTestCase):
    """
    The Progress column typed into in place (issue #61).

    WHY THESE EXIST:
    ================
    Completion used to be reachable only through the editor's Progress
    field or the ribbon's preset buttons. The column shows the figure
    already, so the fast path is typing over it - the same gesture the
    Duration, Start and End columns take.
    """

    def progress_of(self, task_id='u2') -> int:
        """What the plan says the row has done."""
        return self.project.get_task_by_id(task_id).progress

    def progress_cell(self, task_id='u2') -> str:
        """What the grid says the row has done."""
        columns = list(self.task_list.tree.cget('columns'))
        index = columns.index('Progress')
        return self.task_list.tree.item(task_id, 'values')[index]

    def test_the_box_opens_holding_the_number(self):
        """Bare, so a sign need not be typed off first."""
        self.project.get_task_by_id('u2').progress = 30
        self.task_list.update_task_list()

        self.task_list.edit_progress_cell('u2')

        self.assertIsNotNone(self.task_list._cell_editor)
        self.assertEqual(self.task_list._cell_editor.get(), '30')

    def test_enter_stores_it(self):
        """On the task and in the cell, which is what makes it real."""
        self.task_list.edit_progress_cell('u2')
        self.type_into_editor('60')

        self.task_list._commit_progress()

        self.assertEqual(self.progress_of(), 60)
        self.assertEqual(self.progress_cell(), '60%')

    def test_the_sign_the_cell_shows_is_accepted_back(self):
        """Typing what was there - percent sign and all - is no offence."""
        self.task_list.edit_progress_cell('u2')
        self.type_into_editor('75%')

        self.task_list._commit_progress()

        self.assertEqual(self.progress_of(), 75)

    def test_past_the_ends_is_clamped(self):
        """As the ribbon's own buttons clamp theirs."""
        self.task_list.set_progress('u2', 150)
        self.assertEqual(self.progress_of(), 100)

        self.task_list.set_progress('u2', -10)
        self.assertEqual(self.progress_of(), 0)

    def test_something_that_is_not_a_number_is_refused(self):
        """Nothing is stored, and the reader is told why."""
        from unittest import mock

        self.task_list.edit_progress_cell('u2')
        self.type_into_editor('halfway')
        with mock.patch('gantt_app.views.task_list.messagebox.showerror'
                        ) as told:
            self.task_list._commit_progress()

        told.assert_called_once()
        self.assertEqual(self.progress_of(), 0)

    def test_it_is_one_step_in_the_undo_history(self):
        """Like a percentage typed into the editor."""
        depth = len(self.manager.undo_stack)

        self.task_list.set_progress('u2', 60)

        self.assertEqual(len(self.manager.undo_stack), depth + 1)

    def test_undo_puts_the_old_figure_back(self):
        """And redo brings the new one again."""
        self.task_list.set_progress('u2', 60)

        self.manager.undo()
        self.assertEqual(self.progress_of(), 0)

        self.manager.redo()
        self.assertEqual(self.progress_of(), 60)

    def test_writing_what_is_already_there_costs_nothing(self):
        """No undo step for a change that changed nothing."""
        depth = len(self.manager.undo_stack)

        self.task_list.set_progress('u2', 0)

        self.assertEqual(len(self.manager.undo_stack), depth)

    def test_the_parent_reads_the_new_figure(self):
        """A leaf's progress is what its summary's roll-up is made of."""
        self.task_list.set_progress('u2', 60)

        self.assertEqual(
            self.project.get_task_by_id('u1').progress, 60)

    def test_an_empty_box_is_not_a_complaint(self):
        """
        Clearing the cell, then letting the commit run, is "never mind".

        Issue #117: the reader clears the 0 and presses a preset button.
        The focus leaving the box commits what is in it - and an empty
        box used to pop an error before the button's own answer arrived.
        """
        from unittest import mock

        self.task_list.edit_progress_cell('u2')
        self.type_into_editor('')
        with mock.patch('gantt_app.views.task_list.messagebox.showerror'
                        ) as told:
            self.task_list._commit_progress()

        told.assert_not_called()
        self.assertEqual(self.progress_of(), 0)

    def test_n_a_is_not_a_complaint_either(self):
        """The figure a derived cell shows is not a number to store."""
        from unittest import mock

        self.task_list.edit_progress_cell('u2')
        self.type_into_editor('N/A')
        with mock.patch('gantt_app.views.task_list.messagebox.showerror'
                        ) as told:
            self.task_list._commit_progress()

        told.assert_not_called()
        self.assertEqual(self.progress_of(), 0)

    def test_a_preset_after_clearing_still_lands(self):
        """
        The button answers after the empty box's commit does nothing.

        The press on 50% is what the focus left the box for; it sets the
        selected rows itself, so the row ends at 50, not still at 0
        (issue #117).
        """
        self.task_list.edit_progress_cell('u2')
        self.type_into_editor('')
        self.task_list._commit_progress()

        self.task_list.set_progress('u2', 50)

        self.assertEqual(self.progress_of(), 50)


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

    def test_it_creates_a_placeholder_beside_the_focused_row(self):
        """Where the cursor is, which is where the reader is looking."""
        self.task_list.tree.selection_set('u2')
        self.task_list.tree.focus('u2')

        self.task_list.create_task_at_cursor()

        made = [t for t in self.project.tasks if t.is_placeholder]
        self.assertEqual(len(made), 1)
        # The insert rule: the empty row takes the focused row's place.
        self.assertLess(self.project.tasks.index(made[0]),
                        self.project.tasks.index(
                            self.project.get_task_by_id('u2')))

    def test_it_goes_at_the_end_with_no_cursor(self):
        """A list nobody has clicked in yet still makes a row."""
        self.task_list.tree.selection_remove(*self.task_list.tree.selection())
        self.task_list.tree.focus('')

        self.task_list.create_task_at_cursor()

        made = [t for t in self.project.tasks if t.is_placeholder]
        self.assertEqual(len(made), 1)
        self.assertIs(made[0], self.project.tasks[-1])

    def new_task(self, task_id='new1'):
        """The task a saved dialog would hand back."""
        return Task(id=task_id, name='New', task_type='Task',
                    start_date=BASE, end_date=BASE + timedelta(days=1))

    def top_order(self):
        """The top-level rows, in the order they read."""
        return [task.id for task in self.project.get_root_tasks()]

    def test_the_new_row_takes_the_focused_row_s_place(self):
        """
        Above it, not below - issue #59.

        The shortcut landed the new row under the one it was made on. The
        insert rule, here and in the reference tool, is that the new row
        takes the selected row's place and pushes it down.
        """
        self.task_list._save_created(self.new_task(), 'u1', None, above=True)

        self.assertEqual(self.top_order(), ['new1', 'u1'])

    def test_the_new_row_inside_a_group_lands_above_its_anchor(self):
        """The same insert between siblings, one level down."""
        self.task_list._save_created(self.new_task(), 'u2', 'u1',
                                     above=True)

        self.assertEqual(
            [task.id for task in self.project.get_subtasks('u1')],
            ['new1', 'u2'])

    def test_the_right_click_create_still_lands_below(self):
        """Opening the menu on a row asks for a row underneath it."""
        self.task_list._save_created(self.new_task(), 'u1', None)

        self.assertEqual(self.top_order(), ['u1', 'new1'])

    def test_a_new_row_beside_a_subtask_is_a_task(self):
        """
        Its level's type, whatever the dialog offered.

        A sub-task is a Task with a parent now (issue #63), so a row
        created beside one is a Task - the parent link under u1 is what
        the next assertion checks.
        """
        self.task_list._save_created(self.new_task(), 'u2', 'u1',
                                     above=True)

        new_row = self.project.get_task_by_id('new1')
        self.assertEqual(new_row.task_type, 'Task')
        self.assertEqual(new_row.parent_task_id, 'u1')

    def test_a_new_row_beside_a_phase_s_task_stays_a_task(self):
        """
        Issue #59's default: inside a phase the new row is a Task.

        The shortcut's blanket Subtask retype is what made rows made inside
        a phase come out as sub-tasks; the level under a phase is the task
        level, so the type is left alone.
        """
        self.project.add_task(Task(
            id='p1', name='Phase', task_type='Phase', start_date=BASE,
            end_date=BASE + timedelta(days=5)))
        self.project.add_task(Task(
            id='p2', name='Inner', task_type='Task', parent_task_id='p1',
            start_date=BASE, end_date=BASE + timedelta(days=2)))

        self.task_list._save_created(self.new_task(), 'p2', 'p1',
                                     above=True)

        new_row = self.project.get_task_by_id('new1')
        self.assertEqual(new_row.task_type, 'Task')
        self.assertEqual(new_row.parent_task_id, 'p1')
        self.assertEqual(
            [task.id for task in self.project.get_subtasks('p1')],
            ['new1', 'p2'])

    def test_the_key_is_the_platform_s(self):
        """Option on a Mac, Alt elsewhere, with the usual modifier."""
        from gantt_app.utils.shortcuts import (
            ALT, IS_MACOS, MODIFIER, accelerator, sequences,
        )

        self.assertEqual(sequences('.', alt=True),
                         (f"<{MODIFIER}-{ALT}-period>",))
        self.assertEqual(accelerator('.', alt=True),
                         '⌥⌘.' if IS_MACOS else 'Ctrl+Alt+.')

    def test_it_does_not_collide_with_plain_period(self):
        """Plain Cmd+. is not bound, but this shortcut still requires Option."""
        from gantt_app.utils.shortcuts import sequences

        self.assertNotEqual(set(sequences('.')), set(sequences('.', alt=True)))


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class TestTheLabelColumn(InlineEditingTestCase):
    """
    A free-text Label column beside the name, editable in place (#52).

    WHY THESE EXIST:
    ================
    The label is a short tag that rides along with the row - shown in the
    grid, written in the editor under the title, and typed over in the cell
    like the name and the schedule boxes. It never takes part in
    scheduling, which is what makes it editable on every row, containers
    included.
    """

    def setUp(self):
        """Show the column under test - the grid hides it by default now."""
        super().setUp()
        self.project.hidden_grid_columns = []
        self.task_list.apply_column_visibility()

    def label_of(self, task_id='u1') -> str:
        """What the plan says the row is tagged with."""
        return self.project.get_task_by_id(task_id).label

    def label_cell(self, task_id='u1') -> str:
        """What the grid says the row is tagged with."""
        columns = list(self.task_list.tree.cget('columns'))
        index = columns.index('Label')
        return self.task_list.tree.item(task_id, 'values')[index]

    def test_the_column_sits_beside_the_name(self):
        """Right of the tree column, with only the alert flag before it."""
        columns = list(self.task_list.tree.cget('columns'))
        self.assertEqual(columns[0], 'Alert')
        self.assertEqual(columns[1], 'Label')

    def test_the_heading_says_label(self):
        """The column is called what the issue calls it."""
        self.assertEqual(
            self.task_list.tree.heading('Label', 'text'), 'Label')

    def test_a_double_click_opens_a_box_over_the_cell(self):
        """Routed like the other cells that keep their own editors."""
        from unittest import mock

        with mock.patch.object(self.task_list, 'edit_label_cell') as sent:
            self.double_click('u1', column='Label')

        sent.assert_called_once_with('u1')

    def test_the_box_opens_holding_the_label(self):
        """Ready to be replaced, like the name box."""
        self.project.get_task_by_id('u1').label = 'urgent'
        self.task_list.update_task_list()

        self.task_list.edit_label_cell('u1')

        self.assertIsNotNone(self.task_list._cell_editor)
        self.assertEqual(self.task_list._cell_editor.get(), 'urgent')

    def test_enter_stores_it(self):
        """On the task, which is what makes it real."""
        self.double_click('u1', column='Label')
        self.type_into_editor('urgent')

        self.task_list._commit_label()

        self.assertEqual(self.label_of(), 'urgent')
        self.assertEqual(self.label_cell(), 'urgent')

    def test_a_container_row_can_carry_one(self):
        """u1 has a child; the label says nothing about its dates."""
        self.task_list.edit_label_cell('u1')
        self.type_into_editor('phase one')

        self.task_list._commit_label()

        self.assertEqual(self.label_of(), 'phase one')

    def test_an_empty_box_clears_it(self):
        """Like the name, a label need not be there at all."""
        self.project.get_task_by_id('u1').label = 'urgent'

        self.task_list.edit_label_cell('u1')
        self.type_into_editor('   ')
        self.task_list._commit_label()

        self.assertEqual(self.label_of(), '')

    def test_surrounding_space_is_trimmed(self):
        """The label is what was meant, not what the keyboard left."""
        self.task_list.edit_label_cell('u1')
        self.type_into_editor('  blocked  ')

        self.task_list._commit_label()

        self.assertEqual(self.label_of(), 'blocked')

    def test_writing_what_is_already_there_costs_nothing(self):
        """No redraw, and nothing added to undo."""
        depth = len(self.manager.undo_stack)

        self.task_list.set_task_label('u1', '')

        self.assertEqual(len(self.manager.undo_stack), depth)

    def test_it_is_one_step_in_the_undo_history(self):
        """Like a label typed into the editor."""
        depth = len(self.manager.undo_stack)

        self.task_list.set_task_label('u1', 'urgent')

        self.assertEqual(len(self.manager.undo_stack), depth + 1)

    def test_undo_puts_the_old_label_back(self):
        """In the model and in the grid."""
        self.task_list.set_task_label('u1', 'urgent')

        self.manager.undo()
        self.task_list.update_task_list()

        self.assertEqual(self.label_of(), '')
        self.assertEqual(self.label_cell(), '')

    def test_labelling_does_not_disturb_the_rest_of_the_task(self):
        """
        The tracker rebuilds a task from a list of fields, so anything
        missing from that list is reset by any update at all.
        """
        task = self.project.get_task_by_id('u1')
        task.calendar_id = 'weekend'
        task.progress = 40

        self.task_list.set_task_label('u1', 'urgent')

        task = self.project.get_task_by_id('u1')
        self.assertEqual(task.calendar_id, 'weekend')
        self.assertEqual(task.progress, 40)


class TestTheLabelField(unittest.TestCase):
    """The field itself: on the task, and in the saved file."""

    def test_a_task_defaults_to_no_label(self):
        """Plans written before the field existed carry none."""
        task = Task(id='t1', name='One', start_date=BASE)

        self.assertEqual(task.label, '')

    def test_the_label_survives_a_save_and_load(self):
        """Round-tripped through the file like every other field."""
        task = Task(id='t1', name='One', start_date=BASE, label='urgent')

        again = Task.from_dict(task.to_dict())

        self.assertEqual(again.label, 'urgent')

    def test_a_file_written_before_the_field_opens_without_one(self):
        """The key is simply absent, and the task loads blank."""
        task = Task(id='t1', name='One', start_date=BASE)
        saved = task.to_dict()
        del saved['label']

        self.assertEqual(Task.from_dict(saved).label, '')

    def test_a_null_label_reads_as_blank(self):
        """A hand-edited file can hold anything."""
        task = Task(id='t1', name='One', start_date=BASE)
        saved = task.to_dict()
        saved['label'] = None

        self.assertEqual(Task.from_dict(saved).label, '')

    def test_the_search_finds_a_row_by_its_label(self):
        """A field left out of the haystack reads as search being broken."""
        from gantt_app.views.searchbox import task_matches

        task = Task(id='t1', name='One', start_date=BASE, label='legal')

        self.assertTrue(task_matches(task, 'legal'))


class TestPlaceholderRows(InlineEditingTestCase):
    """
    The empty row the insert shortcut makes, and how it grows (issue #115).

    WHY THESE EXIST:
    ================
    The shortcut used to open the whole create form for a gesture meant to
    be one keystroke. What it makes now is a blank line - nothing typed,
    nothing decided - and the first field filled is what turns it into a
    task. Each way in was a different place for the rule to silently not
    apply, which is why there is a test per cell.
    """

    def _placeholder(self, anchor='u2'):
        """The row the insert shortcut adds above the cursor."""
        self.task_list.tree.selection_set(anchor)
        self.task_list.tree.focus(anchor)
        self.task_list.create_task_at_cursor()
        made = [t for t in self.project.tasks if t.is_placeholder]
        assert made, "the shortcut did not leave an empty row"
        return made[0]

    def test_the_new_row_is_totally_empty(self):
        """No name, no type, no dates decided - it shows as a blank line."""
        task = self._placeholder()

        self.assertEqual(task.name, '')
        self.assertEqual(task.task_type, '')
        self.assertIsNone(task.end_date)
        self.assertIsNone(task.duration)
        self.assertFalse(task.is_milestone)

    def test_the_grid_draws_it_as_a_blank_line(self):
        """N/A where the plan's empty cells wear it; nothing else at all."""
        task = self._placeholder()
        self.task_list.update_task_list()

        item = self.task_list.tree.item(task.id)
        values = item['values']
        self.assertEqual(item['text'], '')
        # (alert, label, type, status, duration, start, end, progress,
        #  deps, milestone, level, ...)
        self.assertEqual(values[2], 'N/A')   # Type
        self.assertEqual(values[4], 'N/A')   # Duration
        self.assertEqual(values[5], 'N/A')   # Start
        self.assertEqual(values[6], 'N/A')   # End
        self.assertEqual(values[7], '')      # Progress
        self.assertEqual(values[9], '')      # Milestone

    def test_a_name_grows_it_into_a_one_day_task(self):
        """Typing the name fills in the rest: a Task, a day long."""
        task = self._placeholder()

        self.task_list.set_task_name(task.id, 'Roofing')
        row = self.project.get_task_by_id(task.id)

        self.assertFalse(row.is_placeholder)
        self.assertEqual(row.name, 'Roofing')
        self.assertEqual(row.task_type, 'Task')
        self.assertEqual(row.duration, 1)
        # A day is inclusive here: a one-day task ends on the day it starts
        self.assertEqual(row.end_date, row.start_date)
        self.assertFalse(row.is_milestone)

    def test_a_duration_grows_it_and_stretches_the_end(self):
        """A length typed first lands start, end and the Task type."""
        task = self._placeholder()

        self.task_list.edit_schedule_cell(task.id, 'Duration')
        self.type_into_editor('5')
        self.task_list._commit_schedule_cell('Duration')
        row = self.project.get_task_by_id(task.id)

        self.assertFalse(row.is_placeholder)
        self.assertEqual(row.task_type, 'Task')
        self.assertEqual(row.duration, 5)
        # Four working days in from the inclusive start
        self.assertGreaterEqual(
            (row.end_date - row.start_date).days, 4)
        self.assertFalse(row.is_milestone)

    def test_a_duration_of_zero_makes_a_milestone(self):
        """Nought days is a moment, on an empty row as anywhere (#73)."""
        task = self._placeholder()

        self.task_list.set_schedule(task.id, task.start_date,
                                    task.start_date, 0, None)
        row = self.project.get_task_by_id(task.id)

        self.assertFalse(row.is_placeholder)
        self.assertTrue(row.is_milestone)

    def test_a_start_grows_it_into_a_day(self):
        """A date typed first lands a one-day Task pinned where typed."""
        task = self._placeholder()
        typed = '2026-09-14'     # a Monday

        self.task_list.edit_schedule_cell(task.id, 'Start')
        self.type_into_editor(typed)
        self.task_list._commit_schedule_cell('Start')
        row = self.project.get_task_by_id(task.id)

        self.assertFalse(row.is_placeholder)
        self.assertEqual(row.task_type, 'Task')
        self.assertEqual(row.duration, 1)
        self.assertEqual(row.start_date.strftime('%Y-%m-%d'), typed)
        self.assertEqual(row.end_date, row.start_date)
        # The same pin any typed start earns (issue #31)
        self.assertEqual(row.constraint_type, 'SNET')

    def test_a_type_choice_grows_it(self):
        """Picking Phase from the dropdown fills in the rest the same way."""
        task = self._placeholder()

        self.task_list.set_task_type(task.id, 'Phase')
        row = self.project.get_task_by_id(task.id)

        self.assertFalse(row.is_placeholder)
        self.assertEqual(row.task_type, 'Phase')
        self.assertEqual(row.duration, 1)
        self.assertEqual(row.end_date, row.start_date)

    def test_leaving_the_name_empty_keeps_it_a_placeholder(self):
        """A name box committed blank decides nothing."""
        task = self._placeholder()

        self.task_list.set_task_name(task.id, '')

        self.assertTrue(task.is_placeholder)

    def test_it_survives_a_save_and_load(self):
        """The empty type round-trips through the file like any field."""
        task = Task(id='ph1', name='', task_type='', start_date=BASE,
                    end_date=None, duration=None)

        again = Task.from_dict(task.to_dict())

        self.assertTrue(again.is_placeholder)
        self.assertEqual(again.task_type, '')
        self.assertIsNone(again.duration)

    def test_undo_takes_the_row_back_out(self):
        """The insert is one command; undo removes the whole row."""
        task = self._placeholder()

        self.manager.undo()

        self.assertIsNone(self.project.get_task_by_id(task.id))


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class TestTheBlankTail(InlineEditingTestCase):
    """
    The uncommitted empty rows the grid always ends with (issue #111).

    WHY THESE EXIST:
    ================
    An empty plan used to show a bare canvas - nothing to click, nothing
    to type into, and no hint that typing was the way to start. The grid
    now ends with a block of blank rows like a spreadsheet's unused ones:
    drawn, selectable and editable, but with no task behind them until a
    cell is typed into - which is what turns them into rows of the plan.
    """

    def blanks(self):
        """The tail rows' iids, in the order they are drawn."""
        return list(self.task_list._blank_rows)

    def test_a_plan_shows_a_tail_of_blank_rows(self):
        """Every task is followed by empty rows to type into."""
        rows = self.task_list._visible_row_items()

        self.assertTrue(self.blanks())
        self.assertEqual(rows[:2], ['u1', 'u2'])
        self.assertEqual(rows[2:], self.blanks())
        # ...while the task-facing answer carries tasks alone
        self.assertEqual(self.task_list.visible_rows(), ['u1', 'u2'])

    def test_an_empty_plan_is_not_a_blank_canvas(self):
        """The welcome line: an empty project still shows rows to type."""
        for task in list(self.project.tasks):
            self.project.remove_task(task.id)
        self.task_list.update_task_list()

        self.assertEqual(self.project.tasks, [])
        self.assertTrue(self.blanks())
        self.assertEqual(self.task_list._visible_row_items(),
                         self.blanks())
        self.assertEqual(self.task_list.visible_rows(), [])

    def test_blank_rows_are_not_part_of_the_plan(self):
        """No task, no number - drawn, but nothing the file would store."""
        for iid in self.blanks():
            self.assertIsNone(self.project.get_task_by_id(iid))
            self.assertNotIn(iid, self.task_list._display_ids)

    def test_a_blank_selected_is_not_a_task_selected(self):
        """Commands read the selection as empty when only blanks are."""
        self.task_list.tree.selection_set(self.blanks()[0])
        self.task_list.tree.focus(self.blanks()[0])

        self.assertEqual(self.task_list.get_selected_task_ids(), [])
        self.assertIsNone(self.task_list.focused_task_id())

    def test_typing_a_name_materializes_the_row(self):
        """The first piece of information makes it a row of the plan."""
        before = len(self.project.tasks)
        iid = self.blanks()[0]

        self.task_list.edit_name_cell(iid)
        self.type_into_editor('Roofing')
        self.task_list._commit_name()

        self.assertEqual(len(self.project.tasks), before + 1)
        row = self.project.tasks[-1]
        self.assertEqual(row.name, 'Roofing')
        self.assertEqual(row.task_type, 'Task')
        self.assertFalse(row.is_placeholder)

    def test_an_empty_commit_leaves_the_blank_uncommitted(self):
        """Opening a cell and clicking away is not a decision."""
        before = len(self.project.tasks)

        self.task_list.edit_name_cell(self.blanks()[0])
        self.task_list._commit_name()

        self.assertEqual(len(self.project.tasks), before)

    def test_a_later_blank_takes_the_rows_between_with_it(self):
        """
        Typing into the third blank adds three rows, not one.

        The two before it land as undecided placeholder rows - in the plan,
        numbered, but still showing nothing - so the typed row keeps the
        position it was pointed at rather than sliding up to meet the list.
        """
        before = len(self.project.tasks)
        iid = self.blanks()[2]

        self.task_list.edit_name_cell(iid)
        self.type_into_editor('Roofing')
        self.task_list._commit_name()

        self.assertEqual(len(self.project.tasks), before + 3)
        new = self.project.tasks[-3:]
        self.assertTrue(new[0].is_placeholder)
        self.assertTrue(new[1].is_placeholder)
        self.assertEqual(new[2].name, 'Roofing')
        self.assertFalse(new[2].is_placeholder)

    def test_the_tail_refills_once_a_row_is_taken(self):
        """There is always somewhere left to type."""
        self.task_list.edit_name_cell(self.blanks()[0])
        self.type_into_editor('Roofing')
        self.task_list._commit_name()

        self.assertEqual(len(self.blanks()),
                         self.task_list._blank_tail_count())
        self.assertEqual(
            self.task_list._visible_row_items()[-len(self.blanks()):],
            self.blanks())

    def test_a_type_chosen_on_a_blank_materializes_it(self):
        """The chooser commits without the entry's text path."""
        iid = self.blanks()[0]

        self.task_list.set_task_type(iid, 'Phase')

        row = self.project.tasks[-1]
        self.assertEqual(row.task_type, 'Phase')
        self.assertFalse(row.is_placeholder)

    def test_a_schedule_cell_materializes_it(self):
        """A duration typed on a blank lands a three-day Task."""
        self.task_list.edit_schedule_cell(self.blanks()[0], 'Duration')
        self.type_into_editor('3')
        self.task_list._commit_schedule_cell('Duration')

        row = self.project.tasks[-1]
        self.assertEqual(row.task_type, 'Task')
        self.assertEqual(row.duration, 3)

    def test_undo_takes_the_added_rows_back(self):
        """
        Materializing is one step; the field typed is the next.

        The first undo returns the typed-into row to its undecided state,
        the second lifts the whole group out of the plan again.
        """
        before = len(self.project.tasks)
        self.task_list.edit_name_cell(self.blanks()[1])
        self.type_into_editor('Roofing')
        self.task_list._commit_name()
        self.assertEqual(len(self.project.tasks), before + 2)

        self.manager.undo()
        made = self.project.tasks[-2:]
        self.assertTrue(all(t.is_placeholder for t in made))
        self.assertEqual(made[-1].name, '')

        self.manager.undo()
        self.assertEqual(len(self.project.tasks), before)

    def test_double_click_on_other_cells_starts_the_row_by_name(self):
        """
        A blank has nothing for the whole-row editor to describe.

        Double-clicking it opens the same typing box the insert shortcut
        opens, rather than a form for a task that is not there yet.
        """
        iid = self.blanks()[0]
        self.double_click(iid, column='Milestone')

        self.assertIsNotNone(self.task_list._cell_editor)
        self.assertEqual(self.task_list._cell_editor_task, iid)

    def test_double_click_on_a_schedule_cell_types_into_it(self):
        """Duration, Start and End take typing on a blank like on a leaf."""
        iid = self.blanks()[0]
        self.double_click(iid, column='Start')

        self.assertIsNotNone(self.task_list._cell_editor)
        self.assertEqual(self.task_list._cell_editor_task, iid)
