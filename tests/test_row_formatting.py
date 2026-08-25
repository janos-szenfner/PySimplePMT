"""
Tests for how a row is painted: the hierarchy, and the formatting on top.

WHY THIS MODULE EXISTS:
======================
Two separate promises meet on one Treeview row.

The first is the outline: a row that brackets other rows is bold and its
children are indented, and that has to be true whether or not the Type column
is on screen - a reader scanning the list is not reading columns.

The second is the formatting somebody applied. That has to survive alongside
the banding, the greying of a cut row and the outline's own bold, and a
Treeview settles which of two tags wins in a way this application should not
be relying on. So the whole appearance is resolved in Python onto one tag, and
what that tag ends up saying is what these check.

DEVELOPMENT NOTES:
------------------
The module skips without a display; CI provides one through xvfb. Rows are
inspected through the tags on them rather than by looking at pixels.
"""

import unittest
from datetime import datetime, timedelta

from gantt_app.models import Project, Task
from gantt_app.taskstyle import TaskStyle

BASE = datetime(2026, 7, 6)


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
class RowTestCase(unittest.TestCase):
    """A plan with a phase, work under it, and a standalone task."""

    def setUp(self):
        """Build the window and the list."""
        import customtkinter as ctk

        from gantt_app.views.task_list import DragDropTaskList

        self.root = ctk.CTk()
        self.root.withdraw()

        self.project = Project(name="Plan")
        self.project.add_task(Task(id="P1", name="Phase", task_type="Phase",
                                   start_date=BASE,
                                   end_date=BASE + timedelta(days=10)))
        self.project.add_task(Task(id="T1", name="Under it", task_type="Task",
                                   parent_task_id="P1", start_date=BASE,
                                   end_date=BASE + timedelta(days=2)))
        self.project.add_task(Task(id="T2", name="On its own",
                                   task_type="Task", start_date=BASE,
                                   end_date=BASE + timedelta(days=2)))
        self.task_list = DragDropTaskList(self.root, self.project)
        self.root.update_idletasks()

    def tearDown(self):
        """Close the window."""
        try:
            self.root.destroy()
        except Exception:
            pass

    def appearance(self, task_id: str) -> dict:
        """What the row's own visual tag was configured with."""
        tags = self.task_list.tree.item(task_id, 'tags')
        visual = [tag for tag in tags if tag.startswith('row_')]
        self.assertEqual(len(visual), 1,
                         f"{task_id} should carry exactly one visual tag")
        return self.task_list.tree.tag_configure(visual[0])

    def font_of(self, task_id: str) -> str:
        """The row's font specification, as Tk stored it."""
        return str(self.appearance(task_id)['font'])


class TestTheOutlineReadsWithoutTheTypeColumn(RowTestCase):
    """
    Bold and indentation carry the hierarchy, not a column.

    A reader scanning the list is not reading columns, and the Type column
    can be scrolled out of view or turned off entirely.
    """

    def test_a_container_row_is_bold(self):
        """A Phase brackets what is under it, so it reads as a heading."""
        self.assertIn('bold', self.font_of('P1'))

    def test_work_under_it_is_not(self):
        """Bold everywhere would say nothing anywhere."""
        self.assertNotIn('bold', self.font_of('T1'))

    def test_a_task_with_children_is_bold_too(self):
        """
        Whatever its Type says.

        Having work nested under it is what makes a row a summary of that
        work; the type column is for scheduling, not for grouping.
        """
        self.project.add_task(Task(id="T3", name="Nested", task_type="Subtask",
                                   parent_task_id="T2", start_date=BASE,
                                   end_date=BASE + timedelta(days=1)))
        self.task_list.update_task_list()

        self.assertTrue(self.task_list.is_summary_row(
            self.project.get_task_by_id("T2")))
        self.assertIn('bold', self.font_of('T2'))

    def test_an_empty_phase_still_reads_as_one(self):
        """It is the bracket it is, whether anything is in it yet or not."""
        self.assertEqual(self.project.get_subtasks('P1')[0].id, 'T1')
        self.project.remove_task('T1')
        self.task_list.update_task_list()

        self.assertIn('bold', self.font_of('P1'))

    def test_the_child_hangs_under_its_parent_in_the_tree(self):
        """
        Which is what draws the indent and the chevron.

        The Treeview supplies both from the parent-child relation, so this
        is the assertion behind "indented one level with an expander".
        """
        self.assertEqual(self.task_list.tree.parent('T1'), 'P1')
        self.assertEqual(self.task_list.tree.parent('P1'), '')


class TestTheFormattingReachesTheRow(RowTestCase):
    """What somebody applied, on top of all of that."""

    def style(self, task_id: str, style: TaskStyle):
        """Give a task a style and redraw."""
        self.project.get_task_by_id(task_id).style = style
        self.task_list.update_task_list()

    def test_a_fill_becomes_the_row_background(self):
        """Rather than the banding it replaces."""
        self.style('T2', TaskStyle(fill_color='#fff2cc'))

        self.assertEqual(str(self.appearance('T2')['background']), '#fff2cc')

    def test_an_ink_becomes_the_row_foreground(self):
        """The task name is drawn in it."""
        self.style('T2', TaskStyle(text_color='#c0392b'))

        self.assertEqual(str(self.appearance('T2')['foreground']), '#c0392b')

    def test_every_emphasis_reaches_the_font(self):
        """All three at once, which is what the red italic preset needs."""
        self.style('T2', TaskStyle(bold=True, italic=True, underline=True))
        font = self.font_of('T2')

        for modifier in ('bold', 'italic', 'underline'):
            self.assertIn(modifier, font)

    def test_a_summary_keeps_its_bold_when_given_a_colour(self):
        """Setting one thing must not quietly clear another."""
        self.style('P1', TaskStyle(text_color='#c0392b'))

        self.assertIn('bold', self.font_of('P1'))
        self.assertEqual(str(self.appearance('P1')['foreground']), '#c0392b')

    def test_a_summary_can_be_told_not_to_be_bold(self):
        """An explicit choice outranks the default for the row type."""
        self.style('P1', TaskStyle(bold=False))

        self.assertNotIn('bold', self.font_of('P1'))

    def test_an_unformatted_row_still_gets_its_banding(self):
        """The alternating shading is on the same tag as everything else."""
        backgrounds = {str(self.appearance(task_id)['background'])
                       for task_id in ('P1', 'T1')}

        self.assertEqual(len(backgrounds), 2,
                         "consecutive rows should band differently")

    def test_rows_formatted_alike_share_one_tag(self):
        """
        Forty rows marked as financial milestones configure one tag.

        Worth pinning: a tag per row would leave the widget carrying one
        configuration per task in the plan.
        """
        marked = TaskStyle(fill_color='#fff2cc', bold=True)
        self.project.get_task_by_id('T1').style = marked
        self.project.get_task_by_id('T2').style = marked
        self.task_list.update_task_list()

        tags = [next(tag for tag in self.task_list.tree.item(task_id, 'tags')
                     if tag.startswith('row_'))
                for task_id in ('T1', 'T2')]

        self.assertEqual(tags[0], tags[1])


class TestWhatTheRowIsDoingOutranksHowItLooks(RowTestCase):
    """
    A row waiting to be pasted, or shown only for context, is greyed.

    Both mean "this is not the row you are looking at", which has to beat
    whatever ink it was given - otherwise a red row stays red while it is
    cut and there is no sign it is going anywhere.
    """

    def test_a_cut_row_is_greyed_whatever_ink_it_carries(self):
        """The formatting is still on the task; it just is not drawn now."""
        self.project.get_task_by_id('T2').style = TaskStyle(text_color='#c0392b')
        self.task_list._cut_task_ids = lambda: {'T2'}
        self.task_list.update_task_list()

        self.assertNotEqual(str(self.appearance('T2')['foreground']), '#c0392b')

    def test_the_fill_is_left_alone_while_a_row_is_cut(self):
        """
        Only the ink says "not this one".

        Dropping the fill as well would make a marked-up row unrecognisable
        the moment it was cut, and the user has to be able to see what they
        are about to move.
        """
        self.project.get_task_by_id('T2').style = TaskStyle(fill_color='#fff2cc')
        self.task_list._cut_task_ids = lambda: {'T2'}
        self.task_list.update_task_list()

        self.assertEqual(str(self.appearance('T2')['background']), '#fff2cc')


class TestTheMarkersStayOnTheRow(RowTestCase):
    """
    What a row is, kept apart from how it is painted.

    The markers carry no colours of their own. Two tags both setting a
    background leaves Tk to decide which wins, which is the thing the single
    resolved tag exists to avoid.
    """

    def test_a_subtask_is_still_marked_as_one(self):
        """The marker is what the rest of the file identifies rows by."""
        self.project.add_task(Task(id="S1", name="Sub", task_type="Subtask",
                                   parent_task_id="T2", start_date=BASE,
                                   end_date=BASE + timedelta(days=1)))
        self.task_list.update_task_list()

        self.assertIn('subtask', self.task_list.tree.item('S1', 'tags'))

    def test_the_markers_paint_nothing(self):
        """Every colour is on the resolved tag, and only there."""
        for marker in ('subtask', 'cut', 'search_context', 'oddrow', 'evenrow'):
            configured = self.task_list.tree.tag_configure(marker)
            self.assertFalse(str(configured.get('background') or ''), marker)
            self.assertFalse(str(configured.get('foreground') or ''), marker)


if __name__ == '__main__':
    unittest.main()
