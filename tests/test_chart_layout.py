"""
Tests for how the chart lays a project out.

DEVELOPMENT NOTES:
------------------
These go against layout_chart rather than the rendered image: the geometry is
computed once and handed to both emitters, so testing the layout covers the
window, the PNG/PDF exports and the SVG at once. Nothing here needs a display.
"""

import unittest
from datetime import datetime, timedelta

from gantt_app.models import Project, Task
from gantt_app.utils.chart_render import layout_chart, MIN_WIDTH


def labels(layout):
    """Row labels in the order the chart draws them."""
    return [label for _y, label in layout.row_labels]


class ChartLayoutTestCase(unittest.TestCase):
    """Shared fixture: two root tasks, one with sub-tasks, and a milestone."""

    def setUp(self):
        """Build a project with a summary task, leaves and a milestone."""
        self.project = Project(name="Test Project")
        base = datetime(2026, 1, 1)

        self.project.add_task(Task(
            id="001", name="Phase One", start_date=base,
            end_date=base + timedelta(days=20),
        ))
        for task_id, name, offset in [("002", "Design", 0), ("003", "Build", 5)]:
            self.project.add_task(Task(
                id=task_id, name=name,
                start_date=base + timedelta(days=offset),
                end_date=base + timedelta(days=offset + 4),
                task_type="Subtask", parent_task_id="001",
            ))
        self.project.add_task(Task(
            id="004", name="Phase Two",
            start_date=base + timedelta(days=21),
            end_date=base + timedelta(days=30),
        ))
        self.project.add_task(Task(
            id="005", name="Sign-off",
            start_date=base + timedelta(days=31), is_milestone=True,
        ))


class TestRowOrder(ChartLayoutTestCase):
    """
    Chart rows follow the task list.

    DEVELOPMENT NOTES:
    ------------------
    Rows were sorted by start date on every layout, so a row moved by hand in
    the task list stayed put in the chart. The two panes disagreed and a
    reorder looked like it had done nothing at all.
    """

    def test_rows_follow_the_project_order(self):
        """The chart draws tasks in the order the project holds them."""
        layout = layout_chart(self.project, width=1200)

        self.assertEqual(labels(layout),
                         ["Phase One", "Design", "Build",
                          "Phase Two", "Sign-off"])

    def test_rows_are_not_sorted_by_date(self):
        """A task starting late keeps its position in the list."""
        self.project.get_task_by_id("001").start_date = datetime(2026, 9, 1)

        layout = layout_chart(self.project, width=1200)

        self.assertEqual(labels(layout)[0], "Phase One")

    def test_reordering_moves_the_chart_row(self):
        """Moving a task in the model moves it in the chart."""
        self.project.move_task("004", 'top')

        layout = layout_chart(self.project, width=1200)

        self.assertEqual(labels(layout)[0], "Phase Two")


class TestSummaryBars(ChartLayoutTestCase):
    """A task with sub-tasks is drawn as a bracket, not a bar."""

    def test_a_parent_becomes_a_summary(self):
        """The parent is emitted as a summary rather than a plain bar."""
        layout = layout_chart(self.project, width=1200)

        self.assertEqual([s['label'] for s in layout.summaries], ["Phase One"])

    def test_a_leaf_stays_a_bar(self):
        """Tasks without sub-tasks keep their solid bars."""
        layout = layout_chart(self.project, width=1200)

        self.assertEqual(sorted(b['label'] for b in layout.bars),
                         ["Build", "Design", "Phase Two"])

    def test_a_summary_is_not_also_a_bar(self):
        """The parent appears once, not in both collections."""
        layout = layout_chart(self.project, width=1200)

        self.assertNotIn("Phase One", [b['label'] for b in layout.bars])

    def test_a_milestone_is_neither(self):
        """Milestones stay diamonds."""
        layout = layout_chart(self.project, width=1200)

        self.assertEqual([m['label'] for m in layout.milestones], ["Sign-off"])
        self.assertNotIn("Sign-off", [s['label'] for s in layout.summaries])

    def test_the_summary_spans_its_children(self):
        """The bracket covers the whole parent span."""
        layout = layout_chart(self.project, width=1200)
        summary = layout.summaries[0]

        self.assertLess(summary['x0'], summary['x1'])

    def test_removing_the_children_makes_it_a_bar_again(self):
        """A task stops being a summary when nothing hangs off it."""
        self.project.remove_task("002")
        self.project.remove_task("003")

        layout = layout_chart(self.project, width=1200)

        self.assertEqual(layout.summaries, [])
        self.assertIn("Phase One", [b['label'] for b in layout.bars])


class TestPhaseShape(unittest.TestCase):
    """
    A Phase is drawn as a bar ending in a point.

    DEVELOPMENT NOTES:
    ------------------
    A Phase is the top of the plan, and the reader wants to see where it runs
    to, so it gets a solid bar with an arrow head at its finish rather than the
    thin bracket every other parent row is drawn with.
    """

    def setUp(self):
        """A Phase over a Task, and a sub-task under that."""
        self.project = Project(name="Shapes")
        base = datetime(2026, 1, 5)

        self.project.add_task(Task(
            id="P", name="Phase", start_date=base,
            end_date=base + timedelta(days=20), task_type="Phase",
        ))
        self.project.add_task(Task(
            id="D", name="Grouping task", start_date=base,
            end_date=base + timedelta(days=10), task_type="Task",
            parent_task_id="P",
        ))
        self.project.add_task(Task(
            id="W", name="Work", start_date=base,
            end_date=base + timedelta(days=4), task_type="Subtask",
            parent_task_id="D",
        ))

    def shapes(self):
        """The shape drawn for each summary row, by label."""
        layout = layout_chart(self.project, width=1200)
        return {s['label']: s['shape'] for s in layout.summaries}

    def test_a_phase_is_drawn_as_a_phase(self):
        """The Phase row asks for the pointed shape."""
        self.assertEqual(self.shapes()['Phase'], 'phase')

    def test_other_parents_keep_the_bracket(self):
        """A Task brackets the work beneath it, as before."""
        self.assertEqual(self.shapes()['Grouping task'], 'bracket')

    def test_an_empty_phase_is_still_a_phase(self):
        """
        A Phase with nothing in it yet gets the same shape.

        Otherwise the row changed shape the moment the first task was put
        in it, which read as two different kinds of row.
        """
        project = Project(name="Empty phase")
        project.add_task(Task(id="P", name="Phase",
                              start_date=datetime(2026, 1, 5),
                              end_date=datetime(2026, 1, 9),
                              task_type="Phase"))

        layout = layout_chart(project, width=1200)

        self.assertEqual([s['shape'] for s in layout.summaries], ['phase'])
        self.assertEqual(layout.bars, [])

    def test_the_outline_is_a_pointed_bar(self):
        """
        Five corners: a full-height bar with its right end drawn to a point.

        The point sits at the far end, halfway up, and is the only thing that
        reaches it - which is what makes the shape read as an arrow rather than
        as a bar with a notch.
        """
        from gantt_app.utils.chart_render import _summary_outline

        points = _summary_outline({'x0': 0.0, 'x1': 200.0, 'y0': 0.0,
                                   'y1': 20.0, 'color': '#000000',
                                   'label': 'x', 'shape': 'phase'})

        self.assertEqual(len(points), 5)
        self.assertEqual(points[2], (200.0, 10.0))
        self.assertEqual([x for x, _y in points].count(200.0), 1)
        # Full height at the blunt end, unlike the bracket's thin spine
        self.assertEqual(points[0], (0.0, 0.0))
        self.assertEqual(points[4], (0.0, 20.0))

    def test_a_short_phase_does_not_fold_through_itself(self):
        """
        A phase spanning a couple of pixels collapses to a triangle.

        Without clamping, the head reaches back further than the span is wide
        and the polygon turns inside out.
        """
        from gantt_app.utils.chart_render import _summary_outline

        points = _summary_outline({'x0': 100.0, 'x1': 103.0, 'y0': 0.0,
                                   'y1': 20.0, 'color': '#000000',
                                   'label': 'x', 'shape': 'phase'})

        self.assertTrue(all(x >= 100.0 for x, _y in points))


class TestSummaryOutline(unittest.TestCase):
    """The bracket shape itself."""

    def _outline(self, x0, x1):
        """Outline for a summary spanning x0..x1 on a 20px row."""
        from gantt_app.utils.chart_render import _summary_outline

        return _summary_outline({'x0': x0, 'x1': x1, 'y0': 0.0, 'y1': 20.0,
                                 'color': '#000000', 'label': 'x'})

    def test_it_is_a_closed_polygon(self):
        """Six points: the spine plus a foot dropping at each end."""
        self.assertEqual(len(self._outline(0.0, 200.0)), 6)

    def test_the_ends_reach_below_the_spine(self):
        """The feet extend past the spine, which is what forms the bracket."""
        points = self._outline(0.0, 200.0)
        spine_y = points[4][1]
        foot_y = points[2][1]

        self.assertGreater(foot_y, spine_y)

    def test_a_short_summary_does_not_cross_over(self):
        """
        A bracket spanning a couple of pixels collapses to a wedge.

        Without clamping, the feet reach further than the span is wide and
        the polygon folds through itself.
        """
        points = self._outline(100.0, 104.0)
        left_foot_x = points[4][0]
        right_foot_x = points[3][0]

        self.assertLessEqual(left_foot_x, right_foot_x)


class TestWidthFloor(ChartLayoutTestCase):
    """The minimum width, which the on-screen zoom lowers."""

    def test_the_default_floor_applies(self):
        """A narrow request is widened to stay readable."""
        layout = layout_chart(self.project, width=200)

        self.assertEqual(layout.width, MIN_WIDTH)

    def test_the_floor_can_be_lowered(self):
        """
        Zooming out passes a smaller floor.

        Held at the default, the zoom-out button stopped having any effect
        one step below the pane width.
        """
        layout = layout_chart(self.project, width=400, min_width=320)

        self.assertEqual(layout.width, 400)


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
class TestZoomControls(unittest.TestCase):
    """The zoom buttons under the chart."""

    def setUp(self):
        """Build a chart widget over a small project."""
        import customtkinter as ctk
        from gantt_app.views.gantt_chart import GanttChart

        self.root = ctk.CTk()
        self.root.withdraw()

        self.project = Project(name="Test Project")
        base = datetime(2026, 1, 1)
        self.project.add_task(Task(id="001", name="Alpha", start_date=base,
                                   end_date=base + timedelta(days=5)))

        self.chart = GanttChart(self.root, self.project)

    def tearDown(self):
        """Tear the root window down."""
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_it_starts_fitted(self):
        """The chart opens at 100%."""
        self.assertEqual(self.chart._zoom, 1.0)
        self.assertEqual(self.chart._zoom_label.cget('text'), "100%")

    def test_zoom_in_widens(self):
        """Zooming in raises the level."""
        self.chart.zoom_in()

        self.assertGreater(self.chart._zoom, 1.0)

    def test_zoom_out_narrows(self):
        """Zooming out lowers the level."""
        self.chart.zoom_out()

        self.assertLess(self.chart._zoom, 1.0)

    def test_reset_returns_to_one(self):
        """Reset goes back to 100%."""
        self.chart.zoom_in()
        self.chart.zoom_in()

        self.chart.zoom_reset()

        self.assertEqual(self.chart._zoom, 1.0)

    def test_fit_scales_the_chart_to_the_pane(self):
        """
        Fit works out how much narrower the pane is and zooms out by that.

        At 100% a long plan is drawn wider than the pane on purpose, so
        every day keeps enough pixels to stay readable and the chart
        scrolls. Fitting is what removes the scrolling.
        """
        from gantt_app.utils.chart_render import preferred_width

        available = 700
        self.chart.chart_frame.winfo_width = lambda: available
        natural = preferred_width(self.project, available)

        self.chart.zoom_to_fit()

        self.assertAlmostEqual(self.chart._zoom, available / natural, places=4)

    def test_fit_leaves_nothing_to_scroll_to(self):
        """The rendered width comes out as the width available."""
        from gantt_app.utils.chart_render import preferred_width

        available = 700
        self.chart.chart_frame.winfo_width = lambda: available

        self.chart.zoom_to_fit()
        rendered = preferred_width(self.project, available) * self.chart._zoom

        self.assertAlmostEqual(rendered, available, places=2)

    def test_fit_and_reset_are_different(self):
        """
        Fit is not 100%.

        Fit used to be wired to zoom_reset, so the button did not fit
        anything - it just went back to the width the chart draws itself at.
        """
        self.chart.chart_frame.winfo_width = lambda: 700

        self.chart.zoom_to_fit()

        self.assertNotEqual(self.chart._zoom, 1.0)

    def test_fit_before_the_pane_is_sized_does_nothing(self):
        """There is nothing to fit to until the pane has a width."""
        self.chart.chart_frame.winfo_width = lambda: 1
        self.chart.set_zoom(2.0)

        self.chart.zoom_to_fit()

        self.assertEqual(self.chart._zoom, 2.0)

    def test_the_label_follows_the_level(self):
        """The percentage beside the buttons tracks the zoom."""
        self.chart.set_zoom(2.0)

        self.assertEqual(self.chart._zoom_label.cget('text'), "200%")

    def test_it_clamps_at_the_top(self):
        """Holding zoom in stops at the maximum."""
        from gantt_app.views.gantt_chart import ZOOM_MAX

        for _ in range(40):
            self.chart.zoom_in()

        self.assertEqual(self.chart._zoom, ZOOM_MAX)

    def test_it_clamps_at_the_bottom(self):
        """Holding zoom out stops at the minimum."""
        from gantt_app.views.gantt_chart import ZOOM_MIN

        for _ in range(40):
            self.chart.zoom_out()

        self.assertEqual(self.chart._zoom, ZOOM_MIN)

    def test_a_redraw_at_the_same_level_is_skipped(self):
        """
        Setting the level it already has does not rasterise again.

        Each redraw builds a multi-megapixel image, and the buttons are easy
        to hold down once a limit is reached.
        """
        calls = []
        self.chart.draw_chart = lambda: calls.append(1)

        self.chart.set_zoom(self.chart._zoom)

        self.assertEqual(calls, [])


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestTheResizeTimerDoesNotOutliveTheChart(unittest.TestCase):
    """A settle timer left pending would redraw a chart that has gone."""

    def setUp(self):
        """Build a chart widget over a small project."""
        import customtkinter as ctk
        from gantt_app.views.gantt_chart import GanttChart

        self.root = ctk.CTk()
        self.root.withdraw()
        self.project = Project(name="Test Project")
        base = datetime(2026, 1, 1)
        self.project.add_task(Task(id="001", name="Alpha", start_date=base,
                                   end_date=base + timedelta(days=5)))
        self.chart = GanttChart(self.root, self.project)

    def tearDown(self):
        """Tear the root window down."""
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_destroying_the_chart_cancels_a_pending_resize(self):
        """
        Arm the resize debounce, then tear the chart down before it fires.

        The job is cleared rather than left to run _resize_settled on a dead
        widget.
        """
        self.chart._resize_job = self.chart.after(10000, lambda: None)

        self.chart.destroy()

        self.assertIsNone(self.chart._resize_job)


if __name__ == '__main__':
    unittest.main()
