"""
Tests that the Gantt chart draws the rows the task list is showing.

WHY THIS MODULE EXISTS:
======================
The two panes are read as one table: a bar means the task on its line. The
chart used to choose its own rows, in its own order, at its own height - 34
pixels against the list's 26, so the two drifted a whole row apart every four
tasks - and a branch folded away in the list still had its bars in the chart.

DEVELOPMENT NOTES:
------------------
The layout is checked rather than the picture. Where a bar is drawn is
arithmetic, and arithmetic can be asserted; whether the rendered pixels line
up on a particular desktop is a matter of what the window manager made of
the panes, which no test here can see.
"""

import unittest
from datetime import datetime, timedelta

from gantt_app.models import Project, Task
from gantt_app.utils.chart_render import layout_chart, RowPlan, MARGIN_LEFT


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

BASE = datetime(2026, 1, 1)


def plan_of(project, tasks, row_height=26, top_margin=80):
    """A row plan over the given tasks."""
    return RowPlan(tasks=tasks, row_height=row_height,
                   top_margin=top_margin, label_width=0)


def row_centres(layout):
    """Where every drawn row sits, top to bottom."""
    centres = []
    for item in layout.bars + layout.summaries:
        centres.append((item['y0'] + item['y1']) / 2)
    centres.extend(item['y'] for item in layout.milestones)
    return sorted(centres)


class ChartTestCase(unittest.TestCase):
    """A small plan of one phase, two tasks, a sub-task and a milestone."""

    def setUp(self):
        """Build the plan."""
        self.project = Project(name="Plan")
        for task_id, kind, parent in (("001", "Phase", None),
                                      ("002", "Task", "001"),
                                      ("003", "Subtask", "002"),
                                      ("004", "Task", None),
                                      ("005", "Milestone", None)):
            self.project.add_task(Task(
                id=task_id, name=f"{kind} {task_id}", task_type=kind,
                parent_task_id=parent, start_date=BASE,
                end_date=BASE + timedelta(days=4),
            ))

    def tasks(self, *ids):
        """The tasks with those IDs, in the order given."""
        return [self.project.get_task_by_id(task_id) for task_id in ids]


class TestTheRowsAreTheListsRows(ChartTestCase):
    """What the list shows is what the chart draws."""

    def test_one_row_is_drawn_for_each_task_given(self):
        """No more, and none left out."""
        given = self.tasks("001", "002", "004")

        layout = layout_chart(self.project, width=1000,
                              rows=plan_of(self.project, given))

        self.assertEqual(len(row_centres(layout)), len(given))

    def test_a_folded_away_branch_is_not_drawn(self):
        """
        A row the reader cannot see has no bar.

        Folding a branch in the list takes its rows off screen; the chart
        used to go on drawing them, so every bar below the fold was a row
        out of place.
        """
        showing = self.tasks("001", "002", "004", "005")

        layout = layout_chart(self.project, width=1000,
                              rows=plan_of(self.project, showing))

        self.assertEqual(len(row_centres(layout)), 4)

    def test_the_rows_keep_the_order_they_are_given(self):
        """The chart does not sort; the list decides what comes first."""
        given = self.tasks("004", "001", "002")

        layout = layout_chart(self.project, width=1000,
                              rows=plan_of(self.project, given))
        drawn = {round(item['y0'] + item['y1']) / 2: item['label']
                 for item in layout.bars + layout.summaries}
        top_to_bottom = [drawn[key] for key in sorted(drawn)]

        self.assertEqual(top_to_bottom[0], "Task 004")


class TestTheRowsLineUp(ChartTestCase):
    """Row n of the chart sits where row n of the list sits."""

    def test_rows_are_one_row_height_apart(self):
        """Whatever height the list is using."""
        for height in (20, 26, 34):
            layout = layout_chart(
                self.project, width=1000,
                rows=plan_of(self.project, self.tasks("001", "002", "004"),
                             row_height=height))
            centres = row_centres(layout)
            gaps = [b - a for a, b in zip(centres, centres[1:])]

            self.assertTrue(all(gap == height for gap in gaps),
                            f"at row height {height} the gaps were {gaps}")

    def test_the_first_row_sits_at_the_given_offset(self):
        """
        Half a row below the top margin, which is the row's centre.

        The margin is what the list uses above its first row, measured at
        runtime, so the two panes start level.
        """
        layout = layout_chart(
            self.project, width=1000,
            rows=plan_of(self.project, self.tasks("001"),
                         row_height=26, top_margin=100))

        self.assertEqual(row_centres(layout)[0], 100 + 13)

    def test_the_chart_is_tall_enough_for_every_row(self):
        """A row below the bottom of the image would not be drawn at all."""
        given = self.tasks("001", "002", "003", "004", "005")

        layout = layout_chart(self.project, width=1000,
                              rows=plan_of(self.project, given))

        self.assertGreater(layout.height, max(row_centres(layout)))


class TestTheNamesAreNotPrintedTwice(ChartTestCase):
    """Beside a task list, the chart drops its own label column."""

    def test_no_row_labels_when_a_list_supplies_them(self):
        """The grid is already showing every name."""
        layout = layout_chart(self.project, width=1000,
                              rows=plan_of(self.project, self.tasks("001")))

        self.assertEqual(layout.row_labels, [])

    def test_labels_are_printed_when_the_chart_stands_alone(self):
        """
        An exported chart has no grid beside it, so it names its own rows.

        This is the PNG, PDF and SVG path, which passes no row plan.
        """
        layout = layout_chart(self.project, width=1000)

        self.assertTrue(layout.row_labels)

    def test_a_standalone_chart_keeps_room_for_them(self):
        """The bars start after the label column rather than over it."""
        layout = layout_chart(self.project, width=1000)
        first = min(item['x0'] for item in layout.bars + layout.summaries)

        self.assertGreaterEqual(first, MARGIN_LEFT)


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestWhatTheListReports(unittest.TestCase):
    """visible_rows is what the chart draws from."""

    def setUp(self):
        """A task list over a nested plan."""
        import customtkinter as ctk
        from gantt_app.views.task_list import DragDropTaskList

        self.root = ctk.CTk()
        self.root.withdraw()

        self.project = Project(name="Plan")
        for task_id, kind, parent in (("001", "Phase", None),
                                      ("002", "Task", "001"),
                                      ("003", "Subtask", "002"),
                                      ("004", "Task", None)):
            self.project.add_task(Task(
                id=task_id, name=f"{kind} {task_id}", task_type=kind,
                parent_task_id=parent, start_date=BASE,
                end_date=BASE + timedelta(days=4),
            ))

        self.task_list = DragDropTaskList(self.root, self.project)

    def tearDown(self):
        """Tear the root window down."""
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_every_row_is_reported_when_nothing_is_folded(self):
        """Parents and children alike, in the order they are drawn."""
        self.assertEqual(self.task_list.visible_rows(),
                         ["001", "002", "003", "004"])

    def test_a_folded_branch_reports_only_its_top(self):
        """Its children are not on screen, so they are not on the list."""
        self.task_list.tree.item("002", open=False)

        self.assertEqual(self.task_list.visible_rows(),
                         ["001", "002", "004"])

    def test_folding_the_outermost_branch_hides_everything_under_it(self):
        """Including rows two levels down."""
        self.task_list.tree.item("001", open=False)

        self.assertEqual(self.task_list.visible_rows(), ["001", "004"])

    def test_a_reorder_is_reported_in_the_new_order(self):
        """The chart follows a row moved by hand."""
        self.project.move_task("004", 'top')
        self.task_list.update_task_list()

        self.assertEqual(self.task_list.visible_rows()[0], "004")


if __name__ == '__main__':
    unittest.main()
