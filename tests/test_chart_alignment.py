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


class TestTheHeaderFitsTheMarginItIsGiven(unittest.TestCase):
    """
    The calendar strip has to fit above the first row, not push it down.

    DEVELOPMENT NOTES:
    ------------------
    The chart floors its row alignment at MARGIN_TOP - see
    GanttChart._first_row_offset - so a strip needing more room than that
    does not make the chart taller. It pushes every bar down, and the rows
    stop lining up with the list beside them.

    That is exactly what happened when the strip was first drawn at 24 and
    28 pixels a tier: MARGIN_TOP went to 104, the task list reserves about
    70, and every bar sat 35px below its row. The arithmetic is checked here
    because the symptom is only visible on screen.
    """

    def test_the_title_and_both_tiers_fit_inside_the_margin(self):
        """Or the first row is pushed below where the list puts it."""
        from gantt_app.utils import chart_render as cr

        # The title is centred on its baseline, so it reaches half a line
        # above and below it; 18pt is the size render_image draws it at.
        title_bottom = cr.TITLE_BASELINE + 9
        needed = (cr.HEADER_MONTH_HEIGHT + cr.HEADER_CELL_HEIGHT)

        self.assertLessEqual(title_bottom + needed, cr.MARGIN_TOP)

    def test_the_strip_does_not_overlap_the_title(self):
        """They are drawn into the same band of pixels."""
        from gantt_app.utils import chart_render as cr

        band_top = cr.MARGIN_TOP - cr.HEADER_MONTH_HEIGHT - cr.HEADER_CELL_HEIGHT

        self.assertGreater(band_top, cr.TITLE_BASELINE + 9)

    def test_the_margin_is_no_larger_than_a_task_list_reserves(self):
        """
        The list puts its first row about 70px down - a heading and the
        column titles - and the chart cannot ask for more than that without
        the two going out of line.

        A little slack is allowed for a platform whose headings are taller;
        35px of it is what the bug looked like.
        """
        from gantt_app.utils.chart_render import MARGIN_TOP

        self.assertLessEqual(MARGIN_TOP, 80)


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestTheRowsLineUpOnScreen(unittest.TestCase):
    """
    The measurement the arithmetic above stands in for.

    This is the one that would have caught the strip pushing the bars down:
    it asks the running application where each pane actually put its rows.
    """

    def setUp(self):
        """A window with a plan in it, given time to settle."""
        from unittest import mock
        from gantt_app import theme

        saver = mock.patch.object(theme, 'save_mode', return_value=True)
        saver.start()
        self.addCleanup(saver.stop)

        from gantt_app.main import GanttApp
        self.app = GanttApp()
        self.app.geometry("1500x900")
        self.addCleanup(self._destroy)

        # The window manager needs a moment before the tree can say where
        # its first row is; see GanttChart._first_row_offset.
        self.app.update()
        self.app.update_idletasks()

    def _destroy(self):
        """Tear the window down."""
        try:
            self.app.destroy()
        except Exception:
            pass

    def test_the_first_rows_start_within_a_pixel_of_each_other(self):
        """A constant offset drifts nothing, but it still has to be small."""
        chart = self.app.gantt_chart

        rows_top, settled = chart._task_rows_top()
        if not settled:
            self.skipTest("the window had not settled")

        listed = rows_top - chart.chart_frame.winfo_rooty()
        drawn = chart._first_row_offset()

        self.assertLessEqual(abs(drawn - listed), 2,
                             f"chart rows start {drawn - listed}px from the "
                             f"list's")

    def test_the_two_panes_use_the_same_row_height(self):
        """Equal heights are what keep a constant offset from becoming drift."""
        chart = self.app.gantt_chart
        chart.draw_chart()
        self.app.update_idletasks()

        self.assertEqual(chart._drawn_row_height,
                         self.app.task_list.GRID_ROW_HEIGHT)


if __name__ == '__main__':
    unittest.main()
