"""
Tests for the pages of the exported PDF.

WHY THIS MODULE EXISTS:
======================
The export was one page of chart, which is half a plan: the bars say when work
happens and nothing else - not what a row is called past the few characters
that fit beside it, not how long it is, not what it waits for. Printed and
handed round, that was a picture rather than a document.

It is three pages now, and the things worth pinning down are the ones a reader
would notice: that there are three, that each carries what it is meant to, and
that the page is the physical size it claims to be. That last one is what made
the old export print badly - a 2800 pixel image saved at 150 dpi is a page
eighteen inches wide, which every printer then shrank by an amount of its own
choosing.

DEVELOPMENT NOTES:
------------------
The pages are compared as geometry and as content, never pixel by pixel: they
are drawings, and pinning their pixels would fail on every deliberate change.
The PDF itself is read back for its page boxes, which is the only way to know
what a printer will be told.
"""

import os
import re
import tempfile
import unittest
from datetime import datetime, timedelta

from gantt_app.models import Project, Task


class PageTestCase(unittest.TestCase):
    """A small plan with every kind of row in it."""

    def setUp(self):
        """Build the plan."""
        self.temp_files = []
        self.project = Project(name="Rollout")
        base = datetime(2026, 8, 18)

        self.project.add_task(Task(id="001", name="Planning", task_type="Phase",
                                   start_date=base, end_date=base))
        self.project.add_task(Task(
            id="002", name="Kick-off", task_type="Subtask",
            parent_task_id="001", start_date=base, end_date=base,
            progress=100))
        self.project.add_task(Task(
            id="003", name="Requirements Gathering", task_type="Subtask",
            parent_task_id="001", start_date=base,
            end_date=base + timedelta(days=6), progress=60))
        self.project.get_task_by_id("003").add_dependency("002", 'FS', 'Hard')
        self.project.add_task(Task(
            id="004", name="Go-Live", task_type="Milestone",
            start_date=base + timedelta(days=20)))
        self.project.reschedule()

    def tearDown(self):
        """Remove anything written."""
        for path in self.temp_files:
            if os.path.exists(path):
                os.unlink(path)

    def temp_pdf(self):
        """A path to write a PDF to."""
        handle = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
        path = handle.name
        handle.close()
        self.temp_files.append(path)
        return path


class TestThePagesThemselves(PageTestCase):
    """What comes out of the renderer."""

    def test_there_are_three(self):
        """The list beside the chart, the chart alone, and the full table."""
        from gantt_app.utils.page_render import render_pages

        self.assertEqual(len(render_pages(self.project)), 3)

    def test_they_are_all_the_same_size(self):
        """Or the PDF prints as three shapes rather than one document."""
        from gantt_app.utils.page_render import page_size, render_pages

        for index, page in enumerate(render_pages(self.project), start=1):
            with self.subTest(page=index):
                self.assertEqual(page.size, page_size())

    def test_a_plan_with_no_work_still_renders(self):
        """An empty project is a document that says so, not a failure."""
        from gantt_app.utils.page_render import render_pages

        pages = render_pages(Project(name="Empty"))

        self.assertEqual(len(pages), 3)


class TestTheWorkItemTable(PageTestCase):
    """The list, which is the half the export used to be missing."""

    def test_it_draws_a_row_for_every_task(self):
        """Height follows the row count, so the rows are all there."""
        from gantt_app.utils.page_render import render_task_table

        table = render_task_table(self.project, width=800, row_height=30,
                                  font_size=12, heading_height=30)

        self.assertEqual(table.height, 30 + 4 * 30)

    def test_a_page_asking_for_fewer_columns_gets_the_right_values(self):
        """
        Columns are picked by key, not by position.

        Paired by position, a page showing five of the eight put Type under
        Start and Duration under End - every cell filled and every one of
        them wrong.
        """
        from gantt_app.utils.page_render import (
            SUMMARY_COLUMNS, TABLE_COLUMNS, _cells,
        )

        cells = _cells(self.project, self.project.get_task_by_id("003"))

        for key, _heading, _part in SUMMARY_COLUMNS:
            with self.subTest(column=key):
                self.assertIn(key, cells)
        self.assertEqual(cells['type'], 'Subtask')
        self.assertEqual(cells['progress'], '60%')

    def test_the_hierarchy_is_indented(self):
        """A sub-task reads as one, the way it does in the window."""
        from gantt_app.utils.page_render import _cells

        parent = _cells(self.project, self.project.get_task_by_id("001"))
        child = _cells(self.project, self.project.get_task_by_id("002"))

        self.assertFalse(parent['name'].startswith(' '))
        self.assertTrue(child['name'].startswith(' '))

    def test_a_container_shows_the_span_it_covers(self):
        """
        Not the nought that duration_days answers for one.

        Printed beside two dates a fortnight apart, a nought says the phase
        takes no time - which is the one thing it does not mean.
        """
        from gantt_app.utils.page_render import _cells

        phase = _cells(self.project, self.project.get_task_by_id("001"))

        self.assertNotEqual(phase['duration'], '0')
        self.assertTrue(phase['duration'])

    def test_a_milestone_has_no_finish_to_show(self):
        """It marks a moment, so the column says so rather than lying."""
        from gantt_app.utils.page_render import _cells

        milestone = _cells(self.project, self.project.get_task_by_id("004"))

        self.assertEqual(milestone['end'], '—')

    def test_a_name_too_long_for_its_column_is_trimmed(self):
        """Measured, not counted: twenty narrow letters fit where twenty
        wide ones do not."""
        from PIL import Image, ImageDraw
        from gantt_app.utils.chart_render import _font
        from gantt_app.utils.page_render import _fit

        draw = ImageDraw.Draw(Image.new('RGB', (10, 10)))
        font = _font(14)

        trimmed = _fit(draw, "A name far too long for the space given", font,
                       60)

        self.assertTrue(trimmed.endswith('…'))
        self.assertLessEqual(draw.textlength(trimmed, font=font), 60)


class TestTheWrittenPDF(PageTestCase):
    """What a printer is actually told."""

    def test_it_writes_three_pages(self):
        """Read back out of the file rather than assumed."""
        from gantt_app.utils.image_export import export_gantt_to_pdf

        path = self.temp_pdf()
        self.assertTrue(export_gantt_to_pdf(self.project, path))

        data = open(path, 'rb').read()
        self.assertEqual(len(re.findall(rb'/MediaBox', data)), 3)

    def test_every_page_is_the_size_it_claims(self):
        """
        A4 landscape, in points, which is what a printer reads.

        The old export saved a 2800 pixel image at 150 dpi - a page eighteen
        inches wide - and every printer shrank it by an amount of its own
        choosing. The page is now drawn at exactly the size it is declared
        to be.
        """
        from gantt_app.utils.image_export import export_gantt_to_pdf
        from gantt_app.utils.page_render import PAGE_INCHES

        path = self.temp_pdf()
        export_gantt_to_pdf(self.project, path)

        boxes = re.findall(rb'/MediaBox\s*\[([^\]]*)\]',
                           open(path, 'rb').read())
        self.assertTrue(boxes)

        for box in boxes:
            numbers = [float(value) for value in box.split()]
            inches = ((numbers[2] - numbers[0]) / 72,
                      (numbers[3] - numbers[1]) / 72)
            self.assertAlmostEqual(inches[0], PAGE_INCHES[0], places=1)
            self.assertAlmostEqual(inches[1], PAGE_INCHES[1], places=1)

    def test_it_is_landscape(self):
        """A plan is wider than it is tall, and a portrait page wastes half
        of itself."""
        from gantt_app.utils.page_render import PAGE_INCHES

        self.assertGreater(PAGE_INCHES[0], PAGE_INCHES[1])

    def test_an_empty_plan_still_writes_a_file(self):
        """Exporting nothing is not an error."""
        from gantt_app.utils.image_export import export_gantt_to_pdf

        path = self.temp_pdf()

        self.assertTrue(export_gantt_to_pdf(Project(name="Empty"), path))
        self.assertGreater(os.path.getsize(path), 0)


if __name__ == '__main__':
    unittest.main()
