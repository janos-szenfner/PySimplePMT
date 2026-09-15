"""
pytest-bdd tests for Gantt chart rendering and export.

Run with:
    python3 -m pytest tests/test_gantt_export_bdd.py -q

Nothing here needs a display. Converted from test_gantt_export.py -
every case carried over.
"""
import re
import socket
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

import plotly.graph_objects as go

from gantt_app.core.models import Project, Task
from gantt_app.utils.chart_figure import (
    build_gantt_figure, build_empty_figure, calculate_date_range
)
from gantt_app.utils.image_export import (
    export_gantt_to_png, export_gantt_to_pdf, export_gantt_to_svg,
    export_gantt_to_html, static_export_available
)
from gantt_app.utils.chart_render import (
    layout_chart, render_svg, render_image, find_font_file,
    preferred_width, MIN_WIDTH, MAX_WIDTH, MAX_PIXELS, ROW_HEIGHT,
)

pytestmark = [
    pytest.mark.gantt_export,
]

scenarios("features/gantt_export.feature")

EXPORTERS = {
    'png': export_gantt_to_png,
    'pdf': export_gantt_to_pdf,
    'svg': export_gantt_to_svg,
    'html': export_gantt_to_html,
}


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

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


def project_spanning(days) -> Project:
    """Build a project covering a number of days."""
    project = Project(name=f"{days} days")
    start = datetime(2024, 1, 1)
    project.add_task(Task.create_task(
        "Long", start, start + timedelta(days=days),
        task_id=project.next_task_id()))
    return project


def project_with(count, span_days) -> Project:
    """Build a project with a given number of tasks over a span."""
    project = Project(name=f"{count} tasks")
    start = datetime(2020, 1, 1)
    step = max(1, span_days // max(count, 1))
    for index in range(count):
        project.add_task(Task.create_task(
            f"T{index}",
            start + timedelta(days=index * step),
            start + timedelta(days=index * step + 5),
            task_id=project.next_task_id()))
    return project


# ------------------------------------------------------------------
# GIVEN
# ------------------------------------------------------------------

@given("the sample export plan", target_fixture="ctx")
def the_sample_export_plan():
    return SimpleNamespace(project=sample_project())


@given(parsers.parse('an empty plan named "{name}"'), target_fixture="ctx")
def an_empty_plan(name):
    return SimpleNamespace(project=Project(name=name))


@given(parsers.parse('a plan holding a task named "{name}"'),
       target_fixture="ctx")
def a_plan_holding_a_named_task(name):
    name = name.replace('\\"', '"')
    project = Project(name="Escaping")
    project.add_task(Task.create_task(
        name, datetime(2024, 1, 1), datetime(2024, 1, 3),
        task_id=project.next_task_id()))
    return SimpleNamespace(project=project)


@given(parsers.parse('a plan spanning {days:d} days'), target_fixture="ctx")
def a_plan_spanning(days):
    return SimpleNamespace(project=project_spanning(days))


@given("an empty plan", target_fixture="ctx")
def an_empty_plan_unnamed():
    return SimpleNamespace(project=Project(name="Empty"))


@given(parsers.parse('a plan holding {count:d} tasks over {span:d} days'),
       target_fixture="ctx")
def a_plan_holding_tasks(count, span):
    return SimpleNamespace(project=project_with(count, span))


# ------------------------------------------------------------------
# WHEN - figures
# ------------------------------------------------------------------

@when("a Gantt figure is built for it")
def a_gantt_figure_is_built(ctx):
    ctx.figure = build_gantt_figure(ctx.project)


@when("a Gantt figure is built with a dark background and font size 20")
def a_gantt_figure_is_built_with_settings(ctx):
    ctx.figure = build_gantt_figure(
        ctx.project, settings={'bg_color': '#101010', 'font_size': 20})


@when("the figure's date range is calculated")
def the_date_range_is_calculated(ctx):
    ctx.tasks = sorted(ctx.project.tasks, key=lambda t: t.start_date)
    ctx.low, ctx.high = calculate_date_range(ctx.tasks)


@when("an empty figure is built", target_fixture="ctx")
def an_empty_figure_is_built():
    return SimpleNamespace(figure=build_empty_figure())


# ------------------------------------------------------------------
# THEN - figures
# ------------------------------------------------------------------

@then("it is a Plotly figure holding traces")
def it_is_a_figure_with_traces(ctx):
    assert isinstance(ctx.figure, go.Figure)
    assert len(ctx.figure.data) > 0


@then(parsers.parse('the figure\'s title reads "{text}"'))
def the_title_reads(ctx, text):
    assert isinstance(ctx.figure, go.Figure)
    assert text in ctx.figure.layout.title.text


@then(parsers.parse('the y axis autorange is "{value}"'))
def the_yaxis_autorange(ctx, value):
    assert ctx.figure.layout.yaxis.autorange == value


@then(parsers.parse('the y axis labels are "{a}", "{b}" and "{c}"'))
def the_yaxis_labels(ctx, a, b, c):
    assert list(ctx.figure.layout.yaxis.ticktext) == [a, b, c]


@then(parsers.parse('the figure\'s title names "{text}"'))
def the_title_names(ctx, text):
    assert text in ctx.figure.layout.title.text


@then(parsers.parse('the paper background is "{color}" and the font size is '
                    '{size:d}'))
def the_settings_are_applied(ctx, color, size):
    assert ctx.figure.layout.paper_bgcolor == color
    assert ctx.figure.layout.font.size == size


@then("it starts before the first task and ends after the last")
def the_range_is_padded(ctx):
    assert ctx.low < ctx.tasks[0].start_date
    assert ctx.high > max(t.end_date or t.start_date for t in ctx.tasks)


@then("it is a Plotly figure holding annotations")
def it_is_a_figure_with_annotations(ctx):
    assert isinstance(ctx.figure, go.Figure)
    assert ctx.figure.layout.annotations


# ------------------------------------------------------------------
# WHEN - file exports
# ------------------------------------------------------------------

@when(parsers.parse('the chart is exported as "{filename}"'))
def the_chart_is_exported(ctx, tmp_path, filename):
    path = tmp_path / filename
    fmt = filename.rsplit('.', 1)[-1]
    ctx.exported_ok = EXPORTERS[fmt](ctx.project, str(path))
    ctx.path = path


@when("all four formats are exported with the network blocked")
def all_formats_exported_offline(ctx, tmp_path):
    class Blocked(Exception):
        """Raised when anything attempts to open a connection."""

    def deny(*args, **kwargs):
        raise Blocked("network access attempted")

    originals = (socket.socket.connect, socket.create_connection)
    socket.socket.connect = deny
    socket.create_connection = deny
    ctx.results = {}
    try:
        for name, export in EXPORTERS.items():
            ctx.results[name] = export(ctx.project,
                                       str(tmp_path / f'chart.{name}'))
    finally:
        socket.socket.connect, socket.create_connection = originals


@when("the plan is rendered as SVG")
def the_plan_is_rendered_as_svg(ctx):
    ctx.svg = render_svg(ctx.project)


# ------------------------------------------------------------------
# THEN - file exports
# ------------------------------------------------------------------

@then("the file exists and holds more than 1000 bytes")
def the_file_exists_over_1000(ctx):
    assert ctx.exported_ok
    assert ctx.path.exists()
    assert ctx.path.stat().st_size > 1000


@then("the file exists")
def the_file_exists(ctx):
    assert ctx.exported_ok
    assert ctx.path.exists()


@then("no script tag loads from a remote source")
def no_remote_scripts(ctx):
    content = ctx.path.read_text(encoding='utf-8')
    ctx.content = content
    remote_scripts = re.findall(r'<script[^>]+src=["\']([^"\']+)', content)
    assert [src for src in remote_scripts
            if src.startswith(('http', '//'))] == [], \
        "the page must not load anything over the network"


@then("the file holds more than a megabyte")
def the_file_is_over_a_megabyte(ctx):
    assert len(ctx.content) > 1_000_000


@then(parsers.parse('the file starts with "{start}" and ends with "{end}"'))
def the_file_is_svg(ctx, start, end):
    assert ctx.exported_ok
    content = ctx.path.read_text(encoding='utf-8')
    assert content.startswith(start)
    assert end in content


@then("static export is available")
def static_export_is_available():
    assert static_export_available()


@then("every export succeeded")
def every_export_succeeded(ctx):
    for name, ok in ctx.results.items():
        assert ok, name


@then("the SVG escapes the script and the ampersand")
def the_svg_escapes(ctx):
    assert '<script>' not in ctx.svg
    assert '&lt;script&gt;' in ctx.svg
    assert '&amp;' in ctx.svg


@then("the font lookup returns a path or nothing")
def the_font_lookup():
    result = find_font_file()
    assert result is None or isinstance(result, str)


# ------------------------------------------------------------------
# WHEN/THEN - the layout
# ------------------------------------------------------------------

@when("the chart is laid out")
def the_chart_is_laid_out(ctx):
    ctx.layout = layout_chart(ctx.project)


@when(parsers.parse('the chart is laid out at {width:d} pixels wide'))
def the_chart_is_laid_out_wide(ctx, width):
    ctx.layout = layout_chart(ctx.project, width=width)


@then("every task has a bar or marker and a row label")
def every_task_placed(ctx):
    assert len(ctx.layout.bars) + len(ctx.layout.milestones) == \
        len(ctx.project.tasks)
    assert len(ctx.layout.row_labels) == len(ctx.project.tasks)


@then("the row labels are in order")
def the_rows_are_ordered(ctx):
    ys = [y for y, _ in ctx.layout.row_labels]
    assert ys == sorted(ys)


@then("one dependency line exists per edge")
def the_dependencies_are_laid_out(ctx):
    edges = sum(len(t.dependency_ids) for t in ctx.project.tasks)
    assert len(ctx.layout.dependencies) == edges


@then("the layout holds an empty message and no bars")
def the_layout_is_empty(ctx):
    assert ctx.layout.empty_message is not None
    assert ctx.layout.bars == []


@then("the rows are a full row height apart")
def the_rows_are_full_height(ctx):
    spacing = ctx.layout.row_labels[1][0] - ctx.layout.row_labels[0][0]
    assert spacing == ROW_HEIGHT


@then("the layout is within the pixel budget")
def the_layout_is_bounded(ctx):
    assert ctx.layout.width * ctx.layout.height <= MAX_PIXELS


@then("every task still has a row label")
def every_task_has_a_row(ctx):
    assert len(ctx.layout.row_labels) == len(ctx.project.tasks)


# ------------------------------------------------------------------
# Rendered images
# ------------------------------------------------------------------

@when("ten extra tasks are added and both plans are rendered")
def both_plans_are_rendered(ctx):
    ctx.small = render_image(ctx.project, scale=1.0)

    bigger = sample_project()
    start = bigger.tasks[0].start_date
    for index in range(10):
        bigger.add_task(Task.create_task(
            f"Extra {index}", start + timedelta(days=index),
            start + timedelta(days=index + 2),
            task_id=bigger.next_task_id()))
    ctx.big = render_image(bigger, scale=1.0)


@then("the bigger plan's image is taller")
def the_bigger_image_is_taller(ctx):
    assert ctx.big.height > ctx.small.height


# ------------------------------------------------------------------
# Preferred width
# ------------------------------------------------------------------

@then(parsers.parse('its preferred width in a {pane:d}-pixel pane is '
                    '{width:d}'))
def the_preferred_width_is(ctx, pane, width):
    assert preferred_width(ctx.project, pane) == width


@then(parsers.parse('its preferred width in a {pane:d}-pixel pane is at '
                    'least the minimum'))
def the_preferred_width_is_at_least_the_minimum(ctx, pane):
    assert preferred_width(ctx.project, pane) >= MIN_WIDTH


@then(parsers.parse('its preferred width in a {pane:d}-pixel pane is more '
                    'than {width:d}'))
def the_preferred_width_is_more(ctx, pane, width):
    assert preferred_width(ctx.project, pane) > width


@then(parsers.parse('its preferred width in a {pane:d}-pixel pane is at '
                    'most the cap'))
def the_preferred_width_is_capped(ctx, pane):
    assert preferred_width(ctx.project, pane) <= MAX_WIDTH


@then(parsers.parse("an empty plan's preferred width in a {pane:d}-pixel "
                    "pane is {width:d}"))
def an_empty_plans_preferred_width(pane, width):
    assert preferred_width(Project(name="Empty"), pane) == width


@when(parsers.parse('it is rendered at its preferred width for a '
                    '{pane:d}-pixel pane'))
def it_is_rendered_at_its_preferred_width(ctx, pane):
    ctx.width = preferred_width(ctx.project, pane)
    ctx.image = render_image(ctx.project, width=ctx.width, scale=1.0)


@when(parsers.parse('it is rendered at its preferred width for a '
                    '{pane:d}-pixel pane at scale {scale:d}'))
def it_is_rendered_at_scale(ctx, pane, scale):
    ctx.width = preferred_width(ctx.project, pane)
    ctx.image = render_image(ctx.project, width=ctx.width, scale=float(scale))


@then("the image is that wide")
def the_image_is_that_wide(ctx):
    assert ctx.image.size[0] == ctx.width


@then("the image is within the pixel budget")
def the_image_is_bounded(ctx):
    assert ctx.image.size[0] * ctx.image.size[1] <= MAX_PIXELS


@then("the image is wider than nothing")
def the_image_has_width(ctx):
    assert ctx.image.size[0] > 0
