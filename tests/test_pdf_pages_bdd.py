"""
pytest-bdd tests for the pages of the exported PDF.

Run with:
    python3 -m pytest tests/test_pdf_pages_bdd.py -q

Display-free; the written files land in pytest's tmp_path instead of
the tempfile list the original kept. Converted from
test_pdf_pages.py - every case carried over.
"""
import os
import re
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Project, Task

pytestmark = [
    pytest.mark.pdf_pages,
]

scenarios("features/pdf_pages.feature")


# ------------------------------------------------------------------
# GIVEN
# ------------------------------------------------------------------

@given("the four-row rollout plan", target_fixture="ctx")
def the_four_row_rollout_plan(tmp_path):
    project = Project(name="Rollout")
    base = datetime(2026, 8, 18)

    project.add_task(Task(id="001", name="Planning", task_type="Phase",
                          start_date=base, end_date=base))
    project.add_task(Task(
        id="002", name="Kick-off", task_type="Subtask",
        parent_task_id="001", start_date=base, end_date=base,
        progress=100))
    project.add_task(Task(
        id="003", name="Requirements Gathering", task_type="Subtask",
        parent_task_id="001", start_date=base,
        end_date=base + timedelta(days=6), progress=60))
    project.get_task_by_id("003").add_dependency("002", 'FS', 'Hard')
    project.add_task(Task(
        id="004", name="Go-Live", task_type="Milestone",
        start_date=base + timedelta(days=20)))
    project.reschedule()
    return SimpleNamespace(project=project, tmp_path=tmp_path)


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------

@when("the plan is exported to a PDF")
def the_plan_is_exported(ctx):
    from gantt_app.utils.image_export import export_gantt_to_pdf

    ctx.pdf = str(ctx.tmp_path / "plan.pdf")
    assert export_gantt_to_pdf(ctx.project, ctx.pdf)


@when("an empty plan is exported to a PDF")
def an_empty_plan_is_exported(ctx):
    from gantt_app.utils.image_export import export_gantt_to_pdf

    ctx.pdf = str(ctx.tmp_path / "empty.pdf")
    ctx.exported = export_gantt_to_pdf(Project(name="Empty"), ctx.pdf)


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@then(parsers.parse("the plan renders {count:d} pages"))
def the_plan_renders_pages(ctx, count):
    from gantt_app.utils.page_render import render_pages
    assert len(render_pages(ctx.project)) == count


@then("every rendered page is the declared page size")
def every_page_is_the_declared_size(ctx):
    from gantt_app.utils.page_render import page_size, render_pages
    for page in render_pages(ctx.project):
        assert page.size == page_size()


@then(parsers.parse("an empty plan renders {count:d} pages"))
def an_empty_plan_renders(count):
    from gantt_app.utils.page_render import render_pages
    assert len(render_pages(Project(name="Empty"))) == count


@then(parsers.parse("the task table is heading plus {rows:d} rows tall"))
def the_task_table_height(ctx, rows):
    from gantt_app.utils.page_render import render_task_table
    table = render_task_table(ctx.project, width=800, row_height=30,
                              font_size=12, heading_height=30)
    assert table.height == 30 + rows * 30


@then(parsers.parse('the cells for "{task_id}" carry every summary column'))
def the_cells_carry_every_column(ctx, task_id):
    from gantt_app.utils.page_render import SUMMARY_COLUMNS, _cells
    cells = _cells(ctx.project, ctx.project.get_task_by_id(task_id))
    for key, _heading, _part in SUMMARY_COLUMNS:
        assert key in cells


@then(parsers.parse('the cells for "{task_id}" read type "{type_}" and '
                    'progress "{progress}"'))
def the_cells_read_type_and_progress(ctx, task_id, type_, progress):
    from gantt_app.utils.page_render import _cells
    cells = _cells(ctx.project, ctx.project.get_task_by_id(task_id))
    assert cells['type'] == type_
    assert cells['progress'] == progress


@then(parsers.parse('the cell for "{parent_id}" starts flush and '
                    '"{child_id}" indented'))
def the_hierarchy_is_indented(ctx, parent_id, child_id):
    from gantt_app.utils.page_render import _cells
    parent = _cells(ctx.project, ctx.project.get_task_by_id(parent_id))
    child = _cells(ctx.project, ctx.project.get_task_by_id(child_id))
    assert not parent['name'].startswith(' ')
    assert child['name'].startswith(' ')


@then(parsers.parse('the cell for "{task_id}" shows a non-zero duration'))
def the_container_shows_its_span(ctx, task_id):
    from gantt_app.utils.page_render import _cells
    phase = _cells(ctx.project, ctx.project.get_task_by_id(task_id))
    assert phase['duration'] != '0'
    assert phase['duration']


@then(parsers.parse('the cell for "{task_id}" shows an em-dash end'))
def the_milestone_has_no_finish(ctx, task_id):
    from gantt_app.utils.page_render import _cells
    milestone = _cells(ctx.project, ctx.project.get_task_by_id(task_id))
    assert milestone['end'] == '—'


@then(parsers.parse("a long name is ellipsised inside {pixels:d} pixels"))
def a_long_name_is_ellipsised(pixels):
    from PIL import Image, ImageDraw
    from gantt_app.utils.chart_render import _font
    from gantt_app.utils.page_render import _fit

    draw = ImageDraw.Draw(Image.new('RGB', (10, 10)))
    font = _font(14)
    trimmed = _fit(draw, "A name far too long for the space given", font,
                   pixels)
    assert trimmed.endswith('…')
    assert draw.textlength(trimmed, font=font) <= pixels


@then(parsers.parse("the file holds {count:d} MediaBoxes"))
def the_file_holds_mediaboxes(ctx, count):
    data = open(ctx.pdf, 'rb').read()
    assert len(re.findall(rb'/MediaBox', data)) == count


@then("every MediaBox is within a tenth of an inch of the page size")
def every_mediabox_matches_the_page(ctx):
    from gantt_app.utils.page_render import PAGE_INCHES

    boxes = re.findall(rb'/MediaBox\s*\[([^\]]*)\]',
                       open(ctx.pdf, 'rb').read())
    assert boxes
    for box in boxes:
        numbers = [float(value) for value in box.split()]
        inches = ((numbers[2] - numbers[0]) / 72,
                  (numbers[3] - numbers[1]) / 72)
        assert inches[0] == pytest.approx(PAGE_INCHES[0], abs=0.1)
        assert inches[1] == pytest.approx(PAGE_INCHES[1], abs=0.1)


@then("the declared page is wider than it is tall")
def the_declared_page_is_landscape():
    from gantt_app.utils.page_render import PAGE_INCHES
    assert PAGE_INCHES[0] > PAGE_INCHES[1]


@then("the written file is not empty")
def the_written_file_is_not_empty(ctx):
    assert ctx.exported
    assert os.path.getsize(ctx.pdf) > 0
