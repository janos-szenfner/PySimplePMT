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

import time
import unittest
from datetime import datetime, timedelta

from gantt_app.core.models import Project, Task
from gantt_app.utils.chart_render import layout_chart, RowPlan, MARGIN_LEFT
from tests.pixels import flat_pixels


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
            self.project.add_task(Task(show_in_timeline=True, 
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

    def test_nothing_takes_a_row_after_the_last_one(self):
        """
        Issue #70: a control strip used to ride in the chart's pane and take
        the height of a row or two, so the last bar could never sit level
        with the last row of the list. The image ends a margin after the
        final row - there is no room for anything else.
        """
        from gantt_app.utils.chart_render import MARGIN_BOTTOM
        given = self.tasks("001", "002", "003", "004", "005")
        top_margin, row_height = 80, 26

        layout = layout_chart(
            self.project, width=1000,
            rows=plan_of(self.project, given,
                         row_height=row_height, top_margin=top_margin))

        self.assertEqual(layout.height,
                         top_margin + len(given) * row_height
                         + MARGIN_BOTTOM)
        self.assertLessEqual(layout.height - max(row_centres(layout)),
                             row_height // 2 + MARGIN_BOTTOM)


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
            self.project.add_task(Task(show_in_timeline=True, 
                id=task_id, name=f"{kind} {task_id}", task_type=kind,
                parent_task_id=parent, start_date=BASE,
                end_date=BASE + timedelta(days=4),
            ))

        self.task_list = DragDropTaskList(self.root, self.project)

    def tearDown(self):
        """Tear the root window down."""
        try:
            _shut_down(self.root)
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

    DEVELOPMENT NOTES:
    ------------------
    The only test here that puts a window on screen, and the only one that
    can be affected by the desktop it runs on. It skips rather than waits if
    the window does not map; see setUp for why waiting is the wrong answer.
    """

    #: How long the window is given to appear before the test gives up on
    #: the desktop rather than on the code.
    SETTLE_SECONDS = 5.0

    def setUp(self):
        """A window with a plan in it, given time to settle."""
        from unittest import mock
        from gantt_app.views import theme

        saver = mock.patch.object(theme, 'save_mode', return_value=True)
        saver.start()
        self.addCleanup(saver.stop)

        from gantt_app.main import GanttApp
        self.app = GanttApp()
        self.app.geometry("1500x900")
        self.addCleanup(self._destroy)

        # This is the one test that needs a window actually on screen: it
        # asks the running application where each pane put its rows, and a
        # withdrawn window has no answer.
        #
        # It is given a deadline rather than being waited on. update() on a
        # mapped window hands control to the window server, and on a desktop
        # that is slow to map one - a Mac under load, a session with no
        # compositor - it may not come back for minutes. That leaves a
        # window sitting on somebody's screen mid-run, and closing it by
        # hand raises the application's own "save before exiting?" prompt,
        # which then blocks the suite until it is answered. A test suite
        # must not need a person.
        deadline = time.monotonic() + self.SETTLE_SECONDS
        while time.monotonic() < deadline:
            self.app.update_idletasks()
            if self.app.winfo_viewable():
                break
        else:
            self.skipTest("the window never became viewable")

        # Viewable is not settled. On a desktop under load - a CI runner
        # mid-build - the panes keep moving for a while after the window
        # maps, and an offset read mid-move is a wrong answer the test
        # quite rightly refuses. So the panes are asked where they are
        # until they stop moving - two matching reads - before any test
        # asks where the rows are. The same deadline stands; a desktop
        # that never settles is skipped by the tests' own not-settled
        # guards rather than hung on here.
        previous = None
        deadline = time.monotonic() + self.SETTLE_SECONDS
        while time.monotonic() < deadline:
            self.app.update_idletasks()
            time.sleep(0.05)
            positions = (self.app.gantt_chart.chart_frame.winfo_rooty(),
                         self.app.task_list.tree.winfo_rooty())
            if positions == previous:
                break
            previous = positions

        self.app.update_idletasks()

    def _destroy(self):
        """
        Tear the window down without going through the close handler.

        destroy() is not the window manager's close button, so the exit
        prompt is not reached - which is what keeps the teardown silent.
        The window is withdrawn first so that nothing is left on screen for
        somebody to close by hand while the rest of the suite runs.
        """
        try:
            self.app.withdraw()
        except Exception:
            pass
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

    def test_the_offset_survives_the_redraw_an_edit_causes(self):
        """
        Issue #70: a good task edit shattered the alignment.

        The redraw a save triggers asked the list where its rows were while
        it was still rebuilding, got an unsettled answer, and drew every bar
        a margin too high or low. Once measured, the offset is kept until the
        panes themselves move - it is the panes that have to stay put, not
        the answer that has to keep being asked for.
        """
        chart = self.app.gantt_chart

        rows_top, settled = chart._task_rows_top()
        if not settled:
            self.skipTest("the window had not settled")

        before = chart._first_row_offset()

        chart.draw_chart()
        self.app.update_idletasks()
        # The list answering 'not yet' mid-redraw must not move the rows
        chart._task_rows_top = lambda: (0, False)

        self.assertEqual(chart._first_row_offset(), before)

    def test_a_redraw_keeps_the_chart_where_the_list_scrolled_it(self):
        """
        Issue #70: the rebuilt canvas opened at the top whatever the list
        was showing.

        Every draw rebuilds the canvas, and a fresh canvas sits at scroll
        position zero while the list beside it is wherever the reader put
        it - so the draw hands the position back before the gap can show.
        """
        chart = self.app.gantt_chart

        # Enough rows to have somewhere to scroll to
        for i in range(40):
            self.app.project.add_task(Task(show_in_timeline=True, 
                id=f"x{i:03d}", name=f"Filler {i}", task_type="Task",
                start_date=BASE, end_date=BASE + timedelta(days=4)))
        self.app.task_list.update_task_list()
        chart.draw_chart()
        self.app.update_idletasks()

        self.app.task_list.tree.yview_moveto(0.5)
        self.app.update_idletasks()

        chart.draw_chart()
        self.app.update_idletasks()

        self.assertGreater(chart._chart_canvas.yview()[0], 0.0,
                           "the redrawn chart went back to the top")


class TestTheChartFontIsChosenForSpeedToo(unittest.TestCase):
    """
    Which face the chart draws with is a performance decision.

    DEVELOPMENT NOTES:
    ------------------
    Text is some 95% of the cost of drawing a chart - 2,247 draw.text calls
    on a thousand-task plan - so the face matters. Arial and Helvetica are
    metric compatible, measure the same to the pixel, and Helvetica
    rasterises in about half the time, so it leads on macOS.
    """

    def test_the_candidates_are_all_absolute_paths(self):
        """
        Nothing is fetched; only what is already on the machine is used.

        Checked by shape rather than with os.path.isabs, which only knows
        the conventions of the platform it is running on - the Windows
        entries are not absolute to a Mac.
        """
        from gantt_app.utils.chart_render import FONT_CANDIDATES

        for candidate in FONT_CANDIDATES:
            windows = len(candidate) > 2 and candidate[1:3] == ':\\'
            self.assertTrue(candidate.startswith('/') or windows, candidate)

    def test_helvetica_is_preferred_to_arial(self):
        """
        The two are interchangeable to the pixel; one is twice as fast.

        Pinned because the order looks arbitrary and is not.
        """
        from gantt_app.utils.chart_render import FONT_CANDIDATES

        paths = list(FONT_CANDIDATES)
        helvetica = next((i for i, p in enumerate(paths) if 'Helvetica' in p),
                         None)
        arial = next((i for i, p in enumerate(paths)
                      if p.endswith('Supplemental/Arial.ttf')), None)

        if helvetica is None or arial is None:
            self.skipTest("the macOS candidates are not in the list")
        self.assertLess(helvetica, arial)

    def test_the_chosen_face_measures_the_labels_the_same(self):
        """
        The header's column widths are derived from the font.

        A face with different metrics would change how many dates fit, so
        the two have to agree - which is what metric compatible means.
        """
        from gantt_app.utils.chart_render import _font, find_font_file
        import os

        if not find_font_file():
            self.skipTest("no system font was found")

        arial = '/System/Library/Fonts/Supplemental/Arial.ttf'
        if not os.path.exists(arial):
            self.skipTest("Arial is not on this machine")

        from PIL import ImageFont
        chosen = _font(10)
        other = ImageFont.truetype(arial, 10)

        self.assertEqual(chosen.getbbox('2026-08-17')[2],
                         other.getbbox('2026-08-17')[2])

    def test_accented_text_still_renders(self):
        """
        The reason the candidate list exists at all.

        Pillow's built-in face turns "kialakítása" into a row of boxes.
        """
        from PIL import Image, ImageDraw
        from gantt_app.utils.chart_render import _font

        font = _font(14)
        image = Image.new('L', (400, 30), 255)
        ImageDraw.Draw(image).text((2, 2), "árvíztűrő ÁÉÍÓŐÚŰ",
                                   font=font, fill=0)

        self.assertGreater(sum(1 for p in flat_pixels(image) if p < 128), 200)


if __name__ == '__main__':
    unittest.main()
