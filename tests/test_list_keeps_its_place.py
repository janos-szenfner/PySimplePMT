"""
Tests that the task list survives being rebuilt.

WHY THIS MODULE EXISTS:
======================
Every refresh destroys every row and builds them again, and until now nothing
was carried across that. The consequence was not subtle: pressing Bold cleared
the selection, the formatting bar - which is only live while something is
selected - greyed itself out, and the row had to be clicked again between
every single change. Indent and outdent did the same, because they restored
the selection themselves and then told the application the project had
changed, which rebuilt the list a second time underneath them.

Folding had the same fault from the other side. Every rebuilt row is inserted
open, so a branch folded away sprang back open on the next change anywhere in
the plan.

DEVELOPMENT NOTES:
------------------
The module skips without a display; CI provides one through xvfb. The refresh
is driven through the methods the buttons call, which is the same path a press
takes.
"""

import unittest
from datetime import datetime, timedelta

from gantt_app.models import Project, Task

BASE = datetime(2026, 8, 19)


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
class ListTestCase(unittest.TestCase):
    """A toolbar and a list over a small plan, wired as the application is."""

    def setUp(self):
        """Build everything, including the refresh the application does."""
        import customtkinter as ctk

        from gantt_app.utils.undoredo import (
            ProjectStateTracker, UndoRedoManager,
        )
        from gantt_app.views.task_list import DragDropTaskList
        from gantt_app.views.toolbar import Toolbar

        self.root = ctk.CTk()
        self.root.withdraw()

        self.project = Project(name="Plan")
        for task_id, name in (("1", "Előkészítés"),
                              ("2", "Követelmények összegyűjtése"),
                              ("3", "Pénzügyi követelmények"),
                              ("4", "IT követelmények")):
            self.project.add_task(Task(id=task_id, name=name,
                                       task_type="Task", start_date=BASE,
                                       end_date=BASE + timedelta(days=1)))

        self.manager = UndoRedoManager()
        self.toolbar = Toolbar(self.root, self.project,
                               undo_redo_manager=self.manager)
        self.task_list = DragDropTaskList(
            self.root, self.project,
            project_tracker=ProjectStateTracker(self.project, self.manager))
        self.toolbar.set_task_list(self.task_list)

        # What the application does when anything changes: rebuild the list.
        # This is the refresh that used to throw the selection away.
        self.task_list.on_project_changed = self.task_list.update_task_list
        self.toolbar.on_project_changed = self.task_list.update_task_list
        self.root.update()

        self.bar = self.toolbar.icon_toolbar.style_bar

    def tearDown(self):
        """Close the window."""
        try:
            self.root.destroy()
        except Exception:
            pass

    def select(self, *task_ids):
        """Select rows, and let the toolbar hear about it."""
        self.task_list.tree.selection_set(task_ids)
        self.root.update()


class TestTheSelectionSurvives(ListTestCase):
    """The fault this replaced, one action at a time."""

    def test_formatting_a_row_keeps_it_selected(self):
        """Otherwise the next change means clicking the row again."""
        self.select('2')

        self.toolbar.apply_task_style('bold', True)
        self.root.update()

        self.assertEqual(self.task_list.tree.selection(), ('2',))

    def test_and_the_formatting_bar_stays_live(self):
        """
        Which is the part the reader actually notices.

        The bar is only enabled while something is selected, so a lost
        selection greys out every control the moment one is used.
        """
        self.select('2')

        self.toolbar.apply_task_style('bold', True)
        self.root.update()

        self.assertTrue(self.bar.enabled)

    def test_several_changes_run_together(self):
        """Bold then italic then a colour, without reselecting."""
        self.select('2')

        self.toolbar.apply_task_style('bold', True)
        self.root.update()
        self.toolbar.apply_task_style('italic', True)
        self.root.update()
        self.toolbar.apply_task_style('fill_color', '#fff2cc')
        self.root.update()

        style = self.project.get_task_by_id('2').style
        self.assertTrue(style.bold)
        self.assertTrue(style.italic)
        self.assertEqual(style.fill_color, '#fff2cc')

    def test_indent_keeps_the_row_selected(self):
        """So it can be indented twice without picking it out again."""
        self.select('2')

        self.toolbar.indent_selected()
        self.root.update()

        self.assertEqual(self.task_list.tree.selection(), ('2',))

    def test_indenting_twice_gets_two_levels(self):
        """
        Which is only possible if the first press left it selected.

        The row above has to be indented first, or there is nothing at the
        deeper level for the second press to go under; see
        test_a_first_child_cannot_indent_further.
        """
        self.select('2')
        self.toolbar.indent_selected()
        self.root.update()

        self.select('3')
        self.toolbar.indent_selected()
        self.root.update()
        self.toolbar.indent_selected()
        self.root.update()

        self.assertEqual(self.project.outline_level('3'), 3)

    def test_a_first_child_cannot_indent_further(self):
        """
        There is nothing above it at its own level to go under.

        Microsoft Project refuses the same press for the same reason, so
        the row stays where it is rather than being pushed somewhere it
        does not belong.
        """
        self.select('3')
        self.toolbar.indent_selected()
        self.root.update()
        self.assertEqual(self.project.outline_level('3'), 2)

        self.toolbar.indent_selected()
        self.root.update()

        self.assertEqual(self.project.outline_level('3'), 2)
        self.assertEqual(self.task_list.tree.selection(), ('3',))

    def test_outdent_keeps_the_row_selected(self):
        """The same, on the way back out."""
        self.select('2')
        self.toolbar.indent_selected()
        self.root.update()

        self.toolbar.outdent_selected()
        self.root.update()

        self.assertEqual(self.task_list.tree.selection(), ('2',))

    def test_a_whole_selection_survives(self):
        """Several rows marked at once stay marked."""
        self.select('2', '3')

        self.toolbar.apply_task_style('bold', True)
        self.root.update()

        self.assertEqual(set(self.task_list.tree.selection()), {'2', '3'})

    def test_a_deleted_row_is_not_reselected(self):
        """
        A selection naming a row that has gone would raise.

        This runs on every refresh in the application, so it has to cope
        with the rows having changed underneath it.
        """
        self.select('2')
        self.project.remove_task('2')

        self.task_list.update_task_list()

        self.assertEqual(self.task_list.tree.selection(), ())


class TestTheFoldsSurvive(ListTestCase):
    """A branch folded away stays folded."""

    def test_a_folded_branch_does_not_spring_back_open(self):
        """Every rebuilt row is inserted open, so this has to be restored."""
        self.select('2')
        self.toolbar.indent_selected()
        self.root.update()

        self.task_list.tree.item('1', open=False)
        self.task_list.update_task_list()

        self.assertFalse(self.task_list.tree.item('1', 'open'))

    def test_an_open_branch_stays_open(self):
        """The restore puts back what was there, not what it prefers."""
        self.select('2')
        self.toolbar.indent_selected()
        self.root.update()

        self.task_list.update_task_list()

        self.assertTrue(self.task_list.tree.item('1', 'open'))


class TestTheOutlineIsVisible(ListTestCase):
    """What the columns say about where a task sits."""

    def test_the_name_is_in_the_column_that_indents_it(self):
        """
        Column #0 is the only one that draws the indentation.

        A name anywhere else sits flush left however deep the task is.
        """
        self.assertEqual(self.task_list.tree.item('1', 'text'), "Előkészítés")

    def test_there_is_an_outline_level_column(self):
        """Named as Microsoft Project names it, so the two read alike."""
        self.assertIn('Outline', self.task_list.tree.cget('columns'))
        self.assertEqual(
            self.task_list.tree.heading('Outline', 'text'), 'Outline Level')

    def test_it_counts_from_one_at_the_top(self):
        """Matching the screenshot: the top is 1, under it is 2."""
        self.assertEqual(self.task_list.tree.set('1', 'Outline'), '1')

    def test_it_follows_an_indent(self):
        """The number and the indentation say the same thing."""
        self.select('2')

        self.toolbar.indent_selected()
        self.root.update()

        self.assertEqual(self.task_list.tree.set('2', 'Outline'), '2')

    def test_the_row_really_moves_under_its_parent(self):
        """Which is what draws the indent and the expander beside it."""
        self.select('2')

        self.toolbar.indent_selected()
        self.root.update()

        self.assertEqual(self.task_list.tree.parent('2'), '1')

    def test_it_follows_an_outdent_back(self):
        """And back out again."""
        self.select('2')
        self.toolbar.indent_selected()
        self.root.update()

        self.toolbar.outdent_selected()
        self.root.update()

        self.assertEqual(self.task_list.tree.set('2', 'Outline'), '1')
        self.assertEqual(self.task_list.tree.parent('2'), '')

    def test_a_deep_row_counts_all_the_way_down(self):
        """Four levels, as the screenshot has."""
        self.select('2')
        self.toolbar.indent_selected()
        self.root.update()
        self.select('3')
        self.toolbar.indent_selected()
        self.root.update()
        self.toolbar.indent_selected()
        self.root.update()

        self.assertEqual(self.task_list.tree.set('3', 'Outline'), '3')


if __name__ == '__main__':
    unittest.main()
