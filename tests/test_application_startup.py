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
class TestItOpensToFitTheScreen(unittest.TestCase):
    """
    The window is sized to the screen it opens on.

    WHY THESE LOOK LIKE THIS:
    =========================
    It used to open at a flat 1400x900 with a minimum of 1200x800. That is
    larger than a 1366x768 laptop screen in both directions, and the minimum
    made it unfixable - the window could not be shrunk to fit the display it
    had just opened too large for.

    The screen this runs on cannot be chosen, so the two cases worth pinning
    down are simulated by answering the two questions the sizing asks: how
    much room the window manager allows, and what CustomTkinter multiplies a
    requested geometry by.
    """

    def app(self, work_area=None, scaling=None):
        """The application, optionally told what screen it is opening on."""
        from gantt_app.main import GanttApp

        class Fixed(GanttApp):
            """A GanttApp on a screen of the test's choosing."""

            if work_area is not None:
                def wm_maxsize(self, *_args):
                    return work_area

            if scaling is not None:
                def _window_scaling(self):
                    return scaling

        built = Fixed()
        built.withdraw()
        built.update_idletasks()
        self.addCleanup(self._close, built)
        return built

    @staticmethod
    def _close(app):
        """Tear one down, whatever state it reached."""
        try:
            app.destroy()
        except Exception:
            pass

    def test_it_fills_the_usable_area(self):
        """Not the whole display: the Dock and the taskbar are not ours."""
        app = self.app(work_area=(1600, 900))

        self.assertEqual((app._current_width, app._current_height), (1600, 900))

    def test_it_asks_the_window_manager_rather_than_the_display(self):
        """
        winfo_screenwidth is the whole screen, menu bar and Dock included.

        Sizing to that puts the bottom of the window behind the Dock.
        """
        app = self.app()

        self.assertEqual(app._usable_screen_area(), app.wm_maxsize())

    def test_a_small_screen_gets_a_smaller_minimum(self):
        """
        The fault this replaced.

        A minimum taller than the screen is a window that cannot be resized
        to fit the display it is already on.
        """
        app = self.app(work_area=(1366, 728))

        self.assertLessEqual(app._min_width, 1366)
        self.assertLessEqual(app._min_height, 728)

    def test_a_large_screen_keeps_the_designed_minimum(self):
        """The layout still needs its room; it is a floor, not a target."""
        app = self.app(work_area=(2560, 1400))

        self.assertEqual((app._min_width, app._min_height),
                         app.PREFERRED_MINIMUM)

    def test_the_minimum_never_exceeds_what_was_opened(self):
        """
        Whatever the screen turns out to be.

        Each window is torn down before the next is built. Two live Tk roots
        share one image registry and the second one's icons resolve against
        the first, which fails with "image pyimageN doesn't exist" - nothing
        to do with what is being tested here, and the reason every other
        test in this module builds one application at a time.
        """
        for area in ((1024, 640), (1366, 728), (1920, 1080)):
            with self.subTest(screen=area):
                app = self.app(work_area=area)
                try:
                    self.assertLessEqual(app._min_width, app._current_width)
                    self.assertLessEqual(app._min_height, app._current_height)
                finally:
                    self._close(app)

    def test_a_scaled_desktop_does_not_get_a_window_off_the_edge(self):
        """
        CustomTkinter multiplies a requested geometry by the scaling.

        Handed screen pixels it asks for a window that much larger than the
        screen - which looks right on a Mac, where the scaling is 1, and
        opens half off the edge on Windows at 150%.
        """
        app = self.app(work_area=(2880, 1560), scaling=1.5)

        self.assertEqual((app._current_width, app._current_height),
                         (1920, 1040))

    def test_a_window_manager_that_will_not_say_still_gets_a_window(self):
        """Wrong by the height of a panel beats no window at all."""
        app = self.app(work_area=(0, 0))

        self.assertEqual(app._usable_screen_area(),
                         (app.winfo_screenwidth(), app.winfo_screenheight()))


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
