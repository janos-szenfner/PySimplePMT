"""
Tests that the application starts.

WHY THIS MODULE EXISTS:
======================
Nothing built the real GanttApp. Every other test that needs widgets makes
the one widget it is about and hands it a project, which says nothing about
the order main.py builds things in - and that order is a real thing to get
wrong. A call to the chart was once placed three lines before the chart was
built, so `self.gantt_chart` did not exist yet and the application would not
start at all. Every one of the eight hundred tests passed against it.

What is checked here is only that it comes up and that the panes have been
introduced to one another. Anything finer belongs with the widget it is
about; this is the smoke test that says the application exists.

DEVELOPMENT NOTES:
------------------
The window is withdrawn rather than shown, and torn down at the end of each
test. The module skips without a display; CI provides one through xvfb.
"""

import unittest


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
class TestTheApplicationStarts(unittest.TestCase):
    """It builds, and its parts have found one another."""

    def setUp(self):
        """Build the application, without showing it."""
        from gantt_app.main import GanttApp

        self.app = GanttApp()
        self.app.withdraw()
        self.app.update_idletasks()

    def tearDown(self):
        """Tear it down."""
        try:
            self.app.destroy()
        except Exception:
            pass

    def test_it_builds_every_pane(self):
        """The toolbar, the task list and the chart are all there."""
        for part in ('toolbar', 'task_list', 'gantt_chart', 'status_bar'):
            self.assertTrue(hasattr(self.app, part),
                            f"the application has no {part}")

    def test_the_chart_knows_the_task_list(self):
        """
        Which is what lines their rows up.

        Introducing them is a line in main.py, and it once sat three lines
        before the chart was built.
        """
        self.assertIs(self.app.gantt_chart.task_list, self.app.task_list)

    def test_the_toolbar_knows_the_task_list(self):
        """Copy, Cut, Paste and Delete all ask it what is selected."""
        self.assertIs(self.app.toolbar.task_list, self.app.task_list)

    def test_the_toolbar_knows_the_chart(self):
        """The exports draw from it."""
        self.assertIs(self.app.toolbar.gantt_chart, self.app.gantt_chart)

    def test_the_clipboard_can_reach_the_desktops(self):
        """It is given a widget to do it with; see set_clipboard_widget."""
        self.assertIsNotNone(
            self.app.clipboard_manager.service.clipboard_widget)

    def test_the_chart_drew_the_rows_the_list_is_showing(self):
        """The two panes agree from the first draw, not only after a change."""
        self.assertEqual(self.app.gantt_chart._drawn_rows,
                         self.app.task_list.visible_rows())

    def test_the_rows_stay_lined_up_across_a_redraw(self):
        """
        Selecting a task must not move the chart's rows.

        Where the first row goes was measured afresh on every draw, from the
        canvas when there was one and from the frame when there was not -
        two different widgets, and a window still settling reports positions
        that go on changing. Clicking a task redraws the chart, and the bars
        stepped out of line with the rows they belong to.

        DEVELOPMENT NOTES:
        ------------------
        The offset is settled first. Until the panes have been laid out there
        is nothing to measure and the chart's own margin stands in, so the
        first draw of a window still coming up is expected to differ from
        the ones after it - that is the measurement arriving, not the rows
        moving. What must not change is anything from there on.
        """
        chart = self.app.gantt_chart
        chart.draw_chart()
        self.app.update_idletasks()
        settled = chart._drawn_top_margin

        self.app.task_list.tree.selection_set(
            self.app.task_list.visible_rows()[0])
        self.app.update_all()
        self.app.update_idletasks()
        after_a_click = chart._drawn_top_margin

        chart.draw_chart()
        self.app.update_idletasks()
        after_a_redraw = chart._drawn_top_margin

        self.assertEqual([settled, settled], [after_a_click, after_a_redraw],
                         "the chart's first row moved between draws")

    def test_the_chart_keeps_room_for_its_own_axis(self):
        """
        The bars never start above the title and the date ticks.

        Lining up with a task list whose rows begin higher than the chart's
        own furniture needs would draw the first bar over the dates.
        """
        from gantt_app.views.gantt_chart import CHART_TOP_MARGIN

        self.app.gantt_chart.draw_chart()
        self.app.update_idletasks()

        self.assertGreaterEqual(self.app.gantt_chart._drawn_top_margin,
                                CHART_TOP_MARGIN)

    def test_the_rows_still_match_after_a_redraw(self):
        """The chart draws the list's rows however often it is redrawn."""
        self.app.update_all()
        self.app.update_idletasks()

        self.assertEqual(self.app.gantt_chart._drawn_rows,
                         self.app.task_list.visible_rows())


if __name__ == '__main__':
    unittest.main()
