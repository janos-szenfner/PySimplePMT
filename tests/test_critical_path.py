"""
Tests for the critical path analysis - the parts that need a display.

WHY THIS MODULE EXISTS:
======================
The analysis itself - the float, the criticality, the link types, the
cache - is all arithmetic over the model and lives in
tests/features/critical_path.feature with its steps in
tests/test_critical_path_bdd.py.

What is kept here is what no feature file can reach:

- the window the View menu opens, listing every task with its float,
- the icon's answer painted into the task list - the critical rows in
  light red, surviving the rebuilds every edit causes.

Both are skipped where there is no display.
"""

import unittest
from datetime import datetime

from gantt_app.core.models import Project, Task


class CriticalPathTestCase(unittest.TestCase):
    """Helpers for building a small network and reading it back."""

    def plan(self, rows):
        """
        A project from (id, start, end, [(predecessor, type, lag)]) rows.

        Dates are (year, month, day) tuples; an end of None is a milestone.
        """
        project = Project(name="Analysis")
        for task_id, start, end, links in rows:
            task = Task(
                id=task_id, name=task_id,
                start_date=datetime(*start),
                end_date=datetime(*end) if end else None,
                is_milestone=end is None,
            )
            for predecessor, dep_type, lag in links:
                task.add_dependency(predecessor, dep_type, 'Hard', lag)
            project.add_task(task)
        return project


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


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestTheWindowItOpens(CriticalPathTestCase):
    """
    What the reader is shown.

    A colour on the chart says which tasks are critical and nothing else.
    The question a plan raises is the next one - how much slack has
    everything else got - and one day of float is the thing worth knowing
    about before it is spent.
    """

    def setUp(self):
        """A root window and the two-strand plan."""
        import customtkinter as ctk

        self.root = ctk.CTk()
        self.root.withdraw()
        self.project = self.plan([
            ("A", (2026, 1, 5), (2026, 1, 9), []),
            ("B", (2026, 1, 12), (2026, 1, 23), [("A", 'FS', 0)]),
            ("C", (2026, 1, 12), (2026, 1, 13), [("A", 'FS', 0)]),
            ("D", (2026, 1, 26), (2026, 1, 30), [("B", 'FS', 0),
                                                 ("C", 'FS', 0)]),
        ])
        self.project.reschedule()

    def tearDown(self):
        """Tear the root window down, analysis windows first."""
        _shut_down(self.root)

    def window(self):
        """The analysis window over the fixture."""
        from gantt_app.views.criticalpath import CriticalPathWindow

        found = CriticalPathWindow(self.root, self.project)
        found.update_idletasks()
        return found

    def rows(self, window):
        """Each row as a dict of column to value."""
        keys = [key for key, *_rest in window.COLUMNS]
        return {
            iid: dict(zip(keys, window.tree.item(iid, 'values')))
            for iid in window.tree.get_children()
        }

    def test_every_task_that_holds_work_gets_a_row(self):
        """Summaries are left out; everything else is listed."""
        self.assertEqual(set(self.rows(self.window())), {"A", "B", "C", "D"})

    def test_the_float_is_shown_per_task(self):
        """Which is the number a colour on the chart cannot give."""
        rows = self.rows(self.window())

        self.assertEqual(rows["C"]['float'], '8')
        self.assertEqual(rows["B"]['float'], '0')

    def test_the_critical_rows_are_marked_and_shaded(self):
        """Both in the column and in the row's colour."""
        window = self.window()
        rows = self.rows(window)

        self.assertEqual(rows["B"]['critical'], 'Yes')
        self.assertEqual(rows["C"]['critical'], '')
        self.assertIn('critical', window.tree.item("B", 'tags'))

    def test_the_latest_dates_are_dates(self):
        """
        The analysis counts in working days; the reader wants a calendar.

        "Day 14 of the plan" is honest and useless.
        """
        rows = self.rows(self.window())

        self.assertEqual(rows["C"]['late_finish'], '2026-01-23')

    def test_the_summary_counts_the_critical_tasks(self):
        """The headline above the table."""
        text = self.window().summary_label.cget('text')

        self.assertIn("3 of 4 tasks are critical", text)

    def test_it_opens_on_an_empty_plan(self):
        """A report with nothing to report says so rather than raising."""
        from gantt_app.views.criticalpath import CriticalPathWindow

        window = CriticalPathWindow(self.root, Project(name="Empty"))
        window.update_idletasks()

        self.assertEqual(window.tree.get_children(), ())
        self.assertIn("no work", window.summary_label.cget('text'))


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestThePathPaintedIntoTheList(unittest.TestCase):
    """
    The icon's answer: the critical rows, in light red, in the grid.

    WHY THESE EXIST:
    ================
    "Which of these rows cannot slip" is asked while reading the plan, and
    the report answered it in a window covering the plan being read. The
    same answer painted onto the rows themselves needs no window at all.
    """

    def setUp(self):
        """Two linked tasks that cannot slip, and one with float."""
        import customtkinter as ctk

        from gantt_app.utils.undoredo import (
            ProjectStateTracker, UndoRedoManager,
        )
        from gantt_app.views.task_list import DragDropTaskList

        self.root = ctk.CTk()
        self.root.withdraw()

        base = datetime(2026, 1, 5)
        self.project = Project(name="Plan")
        for task_id in ("A", "B"):
            self.project.add_task(Task(id=task_id, name=task_id,
                                       task_type="Task", start_date=base,
                                       end_date=base, duration=5))
        self.project.add_task(Task(id="C", name="Slack", task_type="Task",
                                   start_date=base, end_date=base,
                                   duration=1))
        self.project.get_task_by_id("B").add_dependency("A", 'FS', 'Hard')
        self.project.reschedule()

        self.task_list = DragDropTaskList(
            self.root, self.project,
            project_tracker=ProjectStateTracker(self.project,
                                                UndoRedoManager()))
        self.task_list.update_task_list()
        self.root.update_idletasks()

    def tearDown(self):
        """Close the window, children first."""
        _shut_down(self.root)

    def fill(self, task_id: str) -> str:
        """The background the row is painted with."""
        tags = [tag for tag in self.task_list.tree.item(task_id, 'tags')
                if tag.startswith('row_')]
        return str(self.task_list.tree.tag_configure(tags[0], 'background'))

    def critical(self):
        """The ids the plan calls critical."""
        return [task.id for task in self.project.get_critical_path()]

    def paint(self):
        """Turn the highlight on, and say how many rows it took."""
        return self.task_list.show_critical_path_rows(self.critical())

    def test_the_plan_has_a_critical_path_to_paint(self):
        """The fixture, checked before anything is asserted about it."""
        self.assertEqual(sorted(self.critical()), ["A", "B"])

    def test_the_critical_rows_go_light_red(self):
        """Which is the whole request."""
        from gantt_app.views import theme

        self.paint()

        self.assertEqual(self.fill("A"), theme.now(
            self.task_list.CRITICAL_ROW_BG))
        self.assertEqual(self.fill("B"), theme.now(
            self.task_list.CRITICAL_ROW_BG))

    def test_a_row_with_float_is_left_alone(self):
        """Or the highlight would say nothing about anything."""
        from gantt_app.views import theme

        self.paint()

        self.assertNotEqual(self.fill("C"), theme.now(
            self.task_list.CRITICAL_ROW_BG))

    def test_it_says_how_many_rows_it_painted(self):
        """What the status line reports back."""
        self.assertEqual(self.paint(), 2)

    def test_it_beats_a_fill_the_row_was_given(self):
        """
        For the reason the greying beats a row's ink: it says what the row
        is doing now, and the reader turned it on to see exactly that.
        """
        from gantt_app.views import theme
        from gantt_app.core.taskstyle import TaskStyle

        self.project.get_task_by_id("A").style = TaskStyle(
            fill_color="#ffff00")
        self.task_list.update_task_list()

        self.paint()

        self.assertEqual(self.fill("A"), theme.now(
            self.task_list.CRITICAL_ROW_BG))

    def test_it_survives_the_list_being_rebuilt(self):
        """
        Which every edit does.

        Held as ids rather than as rows for exactly this: an answer that
        vanished the next time anything was typed would not be worth
        turning on.
        """
        from gantt_app.views import theme

        self.paint()

        self.task_list.update_task_list()

        self.assertEqual(self.fill("A"), theme.now(
            self.task_list.CRITICAL_ROW_BG))

    def test_clearing_it_puts_the_banding_back(self):
        """There has to be a way to put it down again."""
        before = self.fill("A")

        self.paint()
        self.task_list.clear_critical_path_rows()

        self.assertEqual(self.fill("A"), before)

    def test_the_list_says_whether_it_is_on(self):
        """Which is what makes the icon a toggle."""
        self.assertFalse(self.task_list.critical_path_rows_shown())

        self.paint()
        self.assertTrue(self.task_list.critical_path_rows_shown())

        self.task_list.clear_critical_path_rows()
        self.assertFalse(self.task_list.critical_path_rows_shown())

    def test_no_window_is_opened(self):
        """The point of the change: the answer arrives without one."""
        from unittest import mock

        with mock.patch('gantt_app.views.criticalpath.show_critical_path') as opened:
            self.paint()

        opened.assert_not_called()


if __name__ == '__main__':
    unittest.main()
