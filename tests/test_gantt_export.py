"""
Tests for Gantt chart rendering and export.

DEVELOPMENT NOTES:
------------------
These exercise the figure builder and the exporters directly rather than
through the GanttChart widget. The widget only wraps them, and building it
needs a display, which made the suite slow and display-dependent.

Static export is drawn with Pillow rather than handed to a browser, so every
format runs everywhere with nothing downloaded and nothing installed.
"""

import os
import re
import tempfile
import unittest
from datetime import datetime, timedelta

import plotly.graph_objects as go

from gantt_app.models import Project, Task
from gantt_app.utils.chart_figure import (
    build_gantt_figure, build_empty_figure, calculate_date_range
)
from gantt_app.utils.image_export import (
    export_gantt_to_png, export_gantt_to_pdf, export_gantt_to_svg,
    export_gantt_to_html, static_export_available
)
from gantt_app.utils.chart_render import (
    layout_chart, render_svg, render_image, find_font_file
)


def sample_project() -> Project:
    """Build a project covering tasks, a milestone and a dependency."""
    project = Project(name="Export Test")
    start = datetime(2024, 1, 1)

    first = Task.create_task("Task 1", start, start + timedelta(days=4),
                             task_id=project.next_task_id())
    project.add_task(first)

    second = Task.create_task("Task 2", start + timedelta(days=5),
                              start + timedelta(days=9),
                              dependencies=[first.id],
                              task_id=project.next_task_id())
    project.add_task(second)

    project.add_task(Task.create_milestone("Review", start + timedelta(days=10),
                                           dependencies=[second.id],
                                           task_id=project.next_task_id()))
    return project


class TestFigureBuilder(unittest.TestCase):
    """Tests for the shared Plotly figure builder."""

    def setUp(self):
        """Set up test fixtures."""
        self.project = sample_project()

    def test_builds_a_figure(self):
        """A project produces a Plotly figure with traces."""
        figure = build_gantt_figure(self.project)

        self.assertIsInstance(figure, go.Figure)
        self.assertGreater(len(figure.data), 0)

    def test_empty_project_uses_the_placeholder(self):
        """A project with no tasks still yields a usable figure."""
        figure = build_gantt_figure(Project(name="Empty"))

        self.assertIsInstance(figure, go.Figure)
        self.assertIn("No tasks", figure.layout.title.text)

    def test_earliest_task_is_at_the_top(self):
        """The y axis is reversed so the chart reads like the task list."""
        figure = build_gantt_figure(self.project)

        self.assertEqual(figure.layout.yaxis.autorange, 'reversed')

    def test_axis_labels_follow_task_order(self):
        """Y axis labels are the task names in start-date order."""
        figure = build_gantt_figure(self.project)

        self.assertEqual(list(figure.layout.yaxis.ticktext),
                         ["Task 1", "Task 2", "Review"])

    def test_title_uses_the_project_name(self):
        """The chart title names the project."""
        figure = build_gantt_figure(self.project)

        self.assertIn("Export Test", figure.layout.title.text)

    def test_settings_are_applied(self):
        """Caller settings override the defaults."""
        figure = build_gantt_figure(self.project, settings={
            'bg_color': '#101010', 'font_size': 20
        })

        self.assertEqual(figure.layout.paper_bgcolor, '#101010')
        self.assertEqual(figure.layout.font.size, 20)

    def test_date_range_is_padded(self):
        """The date range extends beyond the first and last task."""
        tasks = sorted(self.project.tasks, key=lambda t: t.start_date)
        low, high = calculate_date_range(tasks)

        self.assertLess(low, tasks[0].start_date)
        self.assertGreater(high, max(t.end_date or t.start_date for t in tasks))

    def test_empty_figure_helper(self):
        """build_empty_figure returns a figure with guidance text."""
        figure = build_empty_figure()

        self.assertIsInstance(figure, go.Figure)
        self.assertTrue(figure.layout.annotations)


class TestHTMLExport(unittest.TestCase):
    """HTML export needs no browser, so it always runs."""

    def setUp(self):
        """Set up test fixtures."""
        self.project = sample_project()

    def test_export_to_html(self):
        """A standalone HTML file is written."""
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'chart.html')

            self.assertTrue(export_gantt_to_html(self.project, path))
            self.assertTrue(os.path.exists(path))
            self.assertGreater(os.path.getsize(path), 1000)

    def test_html_is_self_contained(self):
        """
        plotly.js is inlined so the page works without a network.

        DEVELOPMENT NOTES:
        ------------------
        The check looks for a <script src="..."> pointing at a CDN rather than
        for the string 'cdn.plot.ly' anywhere in the file: the bundled
        plotly.js source mentions that host in its own code, so a plain
        substring search reports a false failure.
        """
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'chart.html')
            export_gantt_to_html(self.project, path)

            with open(path, encoding='utf-8') as handle:
                content = handle.read()

            remote_scripts = re.findall(r'<script[^>]+src=["\']([^"\']+)', content)
            self.assertEqual(
                [src for src in remote_scripts if src.startswith(('http', '//'))],
                [],
                "the page must not load anything over the network"
            )
            # The library itself is present in the page
            self.assertGreater(len(content), 1_000_000)

    def test_creates_missing_directories(self):
        """A path with missing parents is created."""
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'nested', 'deeper', 'chart.html')

            self.assertTrue(export_gantt_to_html(self.project, path))
            self.assertTrue(os.path.exists(path))

    def test_empty_project_exports(self):
        """An empty project still produces a page."""
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'empty.html')

            self.assertTrue(export_gantt_to_html(Project(name="Empty"), path))
            self.assertTrue(os.path.exists(path))


class TestStaticExport(unittest.TestCase):
    """PNG, PDF and SVG export, drawn without a browser."""

    def setUp(self):
        """Set up test fixtures."""
        self.project = sample_project()

    def test_export_to_png(self):
        """A PNG file is produced."""
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'chart.png')

            self.assertTrue(export_gantt_to_png(self.project, path))
            self.assertTrue(os.path.exists(path))
            self.assertGreater(os.path.getsize(path), 1000)

    def test_export_to_pdf(self):
        """A PDF file is produced."""
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'chart.pdf')

            self.assertTrue(export_gantt_to_pdf(self.project, path))
            self.assertTrue(os.path.exists(path))
            self.assertGreater(os.path.getsize(path), 1000)

    def test_export_to_svg(self):
        """A scalable SVG file is produced."""
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'chart.svg')

            self.assertTrue(export_gantt_to_svg(self.project, path))
            content = open(path, encoding='utf-8').read()
            self.assertTrue(content.startswith('<svg'))
            self.assertIn('</svg>', content)

    def test_export_empty_project(self):
        """An empty project exports without error."""
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'empty.png')

            self.assertTrue(export_gantt_to_png(Project(name="Empty"), path))
            self.assertTrue(os.path.exists(path))

    def test_static_export_is_always_available(self):
        """Export needs only Pillow, which the bundle always carries."""
        self.assertTrue(static_export_available())

    def test_no_network_access_during_export(self):
        """
        Every format is produced offline.

        The application must work from what it ships with, so this blocks
        outbound sockets and requires each export to still succeed.
        """
        import socket

        class Blocked(Exception):
            """Raised when anything attempts to open a connection."""

        def deny(*args, **kwargs):
            raise Blocked("network access attempted")

        originals = (socket.socket.connect, socket.create_connection)
        socket.socket.connect = deny
        socket.create_connection = deny
        try:
            with tempfile.TemporaryDirectory() as directory:
                for name, export in (('png', export_gantt_to_png),
                                     ('pdf', export_gantt_to_pdf),
                                     ('svg', export_gantt_to_svg),
                                     ('html', export_gantt_to_html)):
                    path = os.path.join(directory, f'chart.{name}')
                    self.assertTrue(export(self.project, path), name)
        finally:
            socket.socket.connect, socket.create_connection = originals


class TestChartRenderer(unittest.TestCase):
    """Tests for the browser-free renderer behind the static exports."""

    def setUp(self):
        """Set up test fixtures."""
        self.project = sample_project()

    def test_layout_places_every_task(self):
        """Each task gets a bar or a milestone marker."""
        layout = layout_chart(self.project)

        self.assertEqual(len(layout.bars) + len(layout.milestones),
                         len(self.project.tasks))
        self.assertEqual(len(layout.row_labels), len(self.project.tasks))

    def test_layout_orders_rows_by_start_date(self):
        """Rows run top to bottom in start-date order."""
        layout = layout_chart(self.project)
        ys = [y for y, _ in layout.row_labels]

        self.assertEqual(ys, sorted(ys))

    def test_dependencies_are_laid_out(self):
        """Dependency lines are produced for each edge."""
        layout = layout_chart(self.project)
        edges = sum(len(t.dependency_ids) for t in self.project.tasks)

        self.assertEqual(len(layout.dependencies), edges)

    def test_empty_project_layout(self):
        """An empty project yields a message instead of rows."""
        layout = layout_chart(Project(name="Empty"))

        self.assertIsNotNone(layout.empty_message)
        self.assertEqual(layout.bars, [])

    def test_render_image_size_follows_task_count(self):
        """A longer plan produces a taller image."""
        small = render_image(self.project, scale=1.0)

        bigger = sample_project()
        start = bigger.tasks[0].start_date
        for index in range(10):
            bigger.add_task(Task.create_task(
                f"Extra {index}", start + timedelta(days=index),
                start + timedelta(days=index + 2),
                task_id=bigger.next_task_id()))

        self.assertGreater(render_image(bigger, scale=1.0).height, small.height)

    def test_svg_escapes_task_names(self):
        """A name containing markup characters cannot break the document."""
        project = Project(name="Escaping")
        project.add_task(Task.create_task(
            "Fix <script> & \"quotes\"", datetime(2024, 1, 1),
            datetime(2024, 1, 3), task_id=project.next_task_id()))

        svg = render_svg(project)
        self.assertNotIn('<script>', svg)
        self.assertIn('&lt;script&gt;', svg)
        self.assertIn('&amp;', svg)

    def test_font_lookup_returns_path_or_none(self):
        """Font discovery answers without raising and without downloading."""
        result = find_font_file()

        self.assertTrue(result is None or isinstance(result, str))


if __name__ == '__main__':
    unittest.main()


class TestPreferredWidth(unittest.TestCase):
    """
    Tests for the width the chart is drawn at.

    DEVELOPMENT NOTES:
    ------------------
    The chart is drawn wider than its pane when a plan is long, so the canvas
    scrolls sideways instead of squeezing every bar into the visible space.
    """

    def setUp(self):
        """Set up test fixtures."""
        from gantt_app.utils.chart_render import preferred_width, MAX_WIDTH
        self.preferred_width = preferred_width
        self.max_width = MAX_WIDTH

    def _project_spanning(self, days):
        """Build a project covering a number of days."""
        project = Project(name=f"{days} days")
        start = datetime(2024, 1, 1)
        project.add_task(Task.create_task(
            "Long", start, start + timedelta(days=days),
            task_id=project.next_task_id()
        ))
        return project

    def test_uses_the_available_space_when_it_is_enough(self):
        """A short plan simply fills the pane."""
        self.assertEqual(self.preferred_width(self._project_spanning(10), 1400),
                         1400)

    def test_never_narrower_than_the_minimum(self):
        """A cramped pane still gets a legible chart."""
        from gantt_app.utils.chart_render import MIN_WIDTH

        self.assertGreaterEqual(
            self.preferred_width(self._project_spanning(10), 200), MIN_WIDTH
        )

    def test_a_long_plan_is_drawn_wider_than_the_pane(self):
        """A long plan overflows the pane so it can be scrolled."""
        width = self.preferred_width(self._project_spanning(600), 800)

        self.assertGreater(width, 800)

    def test_width_is_capped(self):
        """A multi-year plan cannot produce an unbounded image."""
        width = self.preferred_width(self._project_spanning(5000), 800)

        self.assertLessEqual(width, self.max_width)

    def test_empty_project_uses_available_space(self):
        """With no tasks there is no span to accommodate."""
        self.assertEqual(self.preferred_width(Project(name="Empty"), 1400), 1400)

    def test_rendering_at_the_preferred_width_matches(self):
        """The rendered image is the width that was asked for."""
        project = self._project_spanning(600)
        width = self.preferred_width(project, 800)
        image = render_image(project, width=width, scale=1.0)

        self.assertEqual(image.size[0], width)


class TestRenderBudget(unittest.TestCase):
    """
    Tests that a rendered chart can never grow without bound.

    DEVELOPMENT NOTES:
    ------------------
    Dragging the pane divider redraws the chart, and each redraw hands a
    fresh image to Tk, whose image memory Python does not collect. With no
    ceiling on the image size a long plan produced hundreds of megabytes per
    redraw, which was enough to lock up the machine.
    """

    def _project(self, count, span_days):
        """Build a project with a given number of tasks over a span."""
        project = Project(name=f"{count} tasks")
        start = datetime(2020, 1, 1)
        step = max(1, span_days // max(count, 1))
        for index in range(count):
            project.add_task(Task.create_task(
                f"T{index}",
                start + timedelta(days=index * step),
                start + timedelta(days=index * step + 5),
                task_id=project.next_task_id()
            ))
        return project

    def test_small_project_is_untouched(self):
        """An ordinary plan is drawn at full row height."""
        from gantt_app.utils.chart_render import layout_chart, ROW_HEIGHT

        layout = layout_chart(self._project(8, 60), width=1400)
        spacing = layout.row_labels[1][0] - layout.row_labels[0][0]

        self.assertEqual(spacing, ROW_HEIGHT)

    def test_tall_project_is_bounded(self):
        """A plan with hundreds of tasks stays within the pixel budget."""
        from gantt_app.utils.chart_render import layout_chart, MAX_PIXELS

        layout = layout_chart(self._project(1000, 3000), width=6000)

        self.assertLessEqual(layout.width * layout.height, MAX_PIXELS)

    def test_every_task_still_gets_a_row(self):
        """Rows are compressed rather than tasks being dropped."""
        from gantt_app.utils.chart_render import layout_chart

        project = self._project(1000, 3000)
        layout = layout_chart(project, width=6000)

        self.assertEqual(len(layout.row_labels), len(project.tasks))

    def test_rendered_image_respects_the_budget(self):
        """The image handed to Tk is bounded, not just the layout."""
        from gantt_app.utils.chart_render import MAX_PIXELS, preferred_width

        project = self._project(1000, 3000)
        image = render_image(project, width=preferred_width(project, 1400),
                             scale=2.0)

        self.assertLessEqual(image.size[0] * image.size[1], MAX_PIXELS)

    def test_extreme_project_still_renders(self):
        """An unreasonable plan produces an image rather than failing."""
        from gantt_app.utils.chart_render import MAX_PIXELS, preferred_width

        project = self._project(3000, 3650)
        image = render_image(project, width=preferred_width(project, 1400),
                             scale=2.0)

        self.assertLessEqual(image.size[0] * image.size[1], MAX_PIXELS)
        self.assertGreater(image.size[0], 0)
