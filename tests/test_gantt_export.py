"""
Tests for Gantt chart rendering and export.

DEVELOPMENT NOTES:
------------------
These exercise the figure builder and the exporters directly rather than
through the GanttChart widget. The widget only wraps them, and building it
needs a display, which made the suite slow and display-dependent.

PNG and PDF export runs Kaleido, which drives a Chrome or Chromium browser.
Those tests skip when no browser is installed instead of failing, so the suite
still passes on a machine without one. HTML export and figure construction
need no browser and always run.
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
    export_gantt_to_png, export_gantt_to_pdf, export_gantt_to_html,
    static_export_available, find_browser
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


class TestBrowserDetection(unittest.TestCase):
    """Tests for the guard that keeps Kaleido from hanging."""

    def test_find_browser_returns_path_or_none(self):
        """Detection answers without raising and without downloading."""
        result = find_browser()

        self.assertTrue(result is None or isinstance(result, str))

    def test_static_export_available_is_a_bool(self):
        """Availability is reported as a plain boolean."""
        self.assertIsInstance(static_export_available(), bool)

    def test_export_fails_cleanly_without_a_browser(self):
        """
        Without a browser the export returns False rather than hanging.

        Kaleido would otherwise try to download a browser, blocking the
        application for minutes with no feedback.
        """
        if static_export_available():
            self.skipTest("a browser is installed, so this path is not taken")

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'chart.png')
            self.assertFalse(export_gantt_to_png(sample_project(), path))


@unittest.skipUnless(static_export_available(),
                     "no Chrome or Chromium available for Kaleido")
class TestStaticExport(unittest.TestCase):
    """PNG and PDF export, when a browser is present to render them."""

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

    def test_export_empty_project(self):
        """An empty project exports without error."""
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'empty.png')

            self.assertTrue(export_gantt_to_png(Project(name="Empty"), path))
            self.assertTrue(os.path.exists(path))


if __name__ == '__main__':
    unittest.main()
