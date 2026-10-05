"""
The user guide, its editor reference, and the chart's framing.

The scenarios live in features/user_guide.feature. Two kinds of quiet
failure are pinned down there: a guide whose worked examples disagree
with the scheduler, and a chart framing that wasted a quarter of its
width on empty calendar.

The windows the guide opens in and the buttons that reach it need a
display and stay in tests/test_user_guide.py.
"""

from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import TASK_TYPES, Project, Task
from gantt_app.core.workdaycalendar import WorkingCalendar
from gantt_app.help.userguide import GUIDE_SECTIONS
from gantt_app.utils.chart_figure import calculate_date_range


scenarios('features/user_guide.feature')


@pytest.fixture
def ctx():
    return SimpleNamespace(project=None, tasks=None, layout=None)


def _day(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%d")


def _body(sections) -> str:
    """Every word of a help document, lower case, as one string."""
    return '\n'.join(
        heading + '\n' + '\n'.join(paragraphs)
        for heading, paragraphs in sections
    ).lower()


def _phrases(text):
    """A comma-separated cell as a list of phrases."""
    return [piece.strip() for piece in text.split(',')]


# ---- what the guide covers -----------------------------------------------------

@then(parsers.parse('the guide runs to more than {count:d} sections'))
def the_guide_is_a_guide(count):
    assert len(GUIDE_SECTIONS) > count


@then(parsers.parse('its body runs past {count:d} characters'))
def its_body_runs_past(count):
    assert len(_body(GUIDE_SECTIONS)) > count


@then('every guide section has a heading and a non-empty paragraph')
def every_section_is_filled():
    for heading, paragraphs in GUIDE_SECTIONS:
        assert heading.strip(), heading
        assert paragraphs, heading
        for paragraph in paragraphs:
            assert paragraph.strip(), heading


@then('the guide mentions every task type')
def the_guide_explains_the_types():
    body = _body(GUIDE_SECTIONS)
    for task_type in TASK_TYPES:
        assert task_type.lower() in body, task_type


@then(parsers.parse('the guide mentions "{phrases}"'))
def the_guide_mentions(phrases):
    body = _body(GUIDE_SECTIONS)
    for phrase in _phrases(phrases):
        assert phrase in body, phrase


# ---- the worked examples are true -----------------------------------------------

@then(parsers.parse('{days:d} working days from "{start}" land on "{end}", '
                    'a {weekday}'))
def working_days_land(days, start, end, weekday):
    finish = WorkingCalendar().add_working_days(
        _day(start).date(), days)
    assert finish == _day(end).date()
    assert finish.strftime('%A') == weekday


@given(parsers.parse('a task "{task_id}" from "{start}" to "{end}"'))
def a_task(ctx, task_id, start, end):
    ctx.project = Project(name="Guide")
    ctx.project.add_task(Task(show_in_timeline=True, id=task_id,
                            name=task_id,
                            start_date=_day(start), end_date=_day(end)))
    ctx.project.reschedule()


@then(parsers.parse('"{task_id}" ends "{end}" and works {days:d} days'))
def ends_and_works(ctx, task_id, end, days):
    task = ctx.project.get_task_by_id(task_id)
    assert task.end_date.date() == _day(end).date()
    assert ctx.project.working_duration(task) == days


@when(parsers.parse('the working week gains {weekday:d}'))
def the_working_week_gains(ctx, weekday):
    ctx.project.set_working_week({weekday})


@given(parsers.parse('three-day tasks "{ids}" from "{start}" on the plan, '
                     'weekend-shift and continuous calendars'))
def the_three_calendar_tasks(ctx, ids, start):
    ctx.project = Project(name="Guide")
    for identifier, calendar_id in zip(
            [piece.strip() for piece in ids.split(',')],
            (None, "weekend-shift", "continuous")):
        ctx.project.add_task(Task(
            show_in_timeline=True, id=identifier, name=identifier,
            start_date=_day(start), end_date=_day(start),
            duration=3, calendar_id=calendar_id))
    ctx.project.reschedule()


@then(parsers.parse('"{task_id}" runs "{start}" to "{end}"'))
def runs_from_to(ctx, task_id, start, end):
    task = ctx.project.get_task_by_id(task_id)
    assert task.start_date.date() == _day(start).date()
    assert task.end_date.date() == _day(end).date()


@then(parsers.parse('"{task_id}" starts "{start}"'))
def starts_on(ctx, task_id, start):
    task = ctx.project.get_task_by_id(task_id)
    assert task.start_date.date() == _day(start).date()


# ---- the editor reference ------------------------------------------------------------

@then(parsers.parse('the editor reference mentions "{phrases}"'))
def the_reference_mentions(phrases):
    from gantt_app.help.editorhelp import HELP_SECTIONS

    body = _body(HELP_SECTIONS)
    for phrase in _phrases(phrases):
        assert phrase in body, phrase


@then(parsers.parse('three-day tasks "{ids}" from "{start}" end "{d_end}", '
                    'start "{w_start}" and end "{c_end}"'))
def the_reference_examples_are_true(ids, start, d_end, w_start, c_end):
    project = Project(name="Editor help")
    for identifier, calendar_id in zip(
            [piece.strip() for piece in ids.split(',')],
            (None, "weekend-shift", "continuous")):
        project.add_task(Task(
            show_in_timeline=True, id=identifier, name=identifier,
            start_date=_day(start), end_date=_day(start),
            duration=3, calendar_id=calendar_id))
    project.reschedule()

    first, second, third = [piece.strip() for piece in ids.split(',')]
    assert project.get_task_by_id(first).end_date.date() == _day(d_end).date()
    assert (project.get_task_by_id(second).start_date.date()
            == _day(w_start).date())
    assert project.get_task_by_id(third).end_date.date() == _day(c_end).date()


# ---- the chart's framing ------------------------------------------------------------

@given(parsers.parse('a one-task plan of {days:d} days'))
def a_one_task_plan(ctx, days):
    """One task spanning a given number of days."""
    start = datetime(2026, 8, 18)
    ctx.tasks = [Task(show_in_timeline=True, id="a", name="A",
                      start_date=start,
                      end_date=start + timedelta(days=days))]


def _range(days):
    """The framing for one task of the given span."""
    start = datetime(2026, 8, 18)
    tasks = [Task(show_in_timeline=True, id="a", name="A",
                  start_date=start,
                  end_date=start + timedelta(days=days))]
    return calculate_date_range(tasks), tasks[0]


@then(parsers.parse('the chart range leads the first bar by {days:d} day'))
def the_lead_in_is_a_day(ctx, days):
    low, _high = calculate_date_range(ctx.tasks)
    assert (ctx.tasks[0].start_date - low).days == days


@then(parsers.parse('the lead-in is under {percent:d} percent of the width'))
def the_lead_in_is_a_sliver(ctx, percent):
    low, high = calculate_date_range(ctx.tasks)
    wasted = (ctx.tasks[0].start_date - low).days / (high - low).days
    assert wasted < percent / 100


@then(parsers.parse('the chart range trails the last bar by at least '
                    '{days:d} days'))
def the_trail_is_roomy(ctx, days):
    _low, high = calculate_date_range(ctx.tasks)
    assert (high - ctx.tasks[0].end_date).days >= days


@then(parsers.parse('a {long:d}-day plan trails further than a '
                    '{short:d}-day plan'))
def a_long_plan_trails_further(long, short):
    (_sl, short_high), short_task = _range(short)
    (_ll, long_high), long_task = _range(long)

    assert (long_high - long_task.end_date).days > \
           (short_high - short_task.end_date).days


@then(parsers.parse('the lead-in stays {days:d} day for plans of 10, 100 '
                    'and 365 days'))
def the_lead_in_does_not_grow(days):
    for span in (10, 100, 365):
        (low, _high), task = _range(span)
        assert (task.start_date - low).days == days, span


@then('the chart range for no tasks is still a range')
def an_empty_plan_still_ranges():
    low, high = calculate_date_range([])
    assert low < high


# ---- the calendar strip --------------------------------------------------------------

def _strip_plan(days=24, start=datetime(2026, 8, 18)):
    """A project spanning a given number of days."""
    project = Project(name="Strip")
    project.add_task(Task(show_in_timeline=True, id="a", name="A",
                          start_date=start,
                          end_date=start + timedelta(days=days)))
    project.reschedule()
    return project


@given('a strip plan')
def a_strip_plan(ctx):
    ctx.build = _strip_plan


@given(parsers.parse('a strip plan of {days:d} days'))
def a_strip_plan_of(ctx, days):
    ctx.project = _strip_plan(days=days)


@given(parsers.parse('a strip plan of {days:d} days around today'))
def a_strip_plan_around_today(ctx, days):
    ctx.project = _strip_plan(days=days,
                              start=datetime.now() - timedelta(days=3))


@given(parsers.parse('a strip plan of {days:d} days from "{start}"'))
def a_strip_plan_from(ctx, days, start):
    ctx.project = _strip_plan(days=days, start=_day(start))


@when(parsers.parse('the chart is laid out at {width:d}px'))
def the_chart_is_laid_out(ctx, width):
    from gantt_app.utils.chart_render import layout_chart
    ctx.layout = layout_chart(ctx.project, width=width)


@then(parsers.parse('the header mode is "{mode}"'))
def the_header_mode_is(ctx, mode):
    assert ctx.layout.header_mode == mode


@then(parsers.parse('there are more than {count:d} day cells'))
def there_are_day_cells(ctx, count):
    assert len(ctx.layout.day_cells) > count


@then('every day cell is a bare day number')
def the_cells_are_day_numbers(ctx):
    for _x0, _x1, label, *_rest in ctx.layout.day_cells:
        assert label.isdigit(), label
        assert int(label) <= 31


@then(parsers.parse('the month bands read "{names}"'))
def the_month_bands_read(ctx, names):
    found = [label for _x0, _x1, label in ctx.layout.month_bands]
    assert found == _phrases(names)


@then('the day cells run edge to edge')
def the_cells_run_edge_to_edge(ctx):
    for (_a0, a1, *_x), (b0, _b1, *_y) in zip(ctx.layout.day_cells,
                                             ctx.layout.day_cells[1:]):
        assert a1 == pytest.approx(b0, abs=1e-3)


@then('the cells mark working and non-working days alike')
def both_kinds_are_marked(ctx):
    working = [cell[4] for cell in ctx.layout.day_cells]
    assert True in working
    assert False in working


@then('every non-working cell still has width')
def non_working_cells_have_width(ctx):
    non_working = [cell for cell in ctx.layout.day_cells if not cell[4]]
    assert non_working
    for x0, x1, *_rest in non_working:
        assert x1 > x0


@then(parsers.parse('exactly {count:d} cell is flagged today'))
def one_cell_is_today(ctx, count):
    assert sum(1 for cell in ctx.layout.day_cells if cell[3]) == count


@then('no cell is flagged today')
def no_cell_is_today(ctx):
    assert [cell for cell in ctx.layout.day_cells if cell[3]] == []


@then('the week-start flags match the date ticks')
def the_week_starts_are_flagged(ctx):
    starts = [cell for cell in ctx.layout.day_cells if cell[5]]
    assert starts
    assert len(starts) == len(ctx.layout.date_ticks)


@then('these plans get these header modes')
def the_modes_fall_back(ctx, datatable):
    from gantt_app.utils.chart_render import layout_chart

    for days, width, mode in (row for row in datatable[1:]):
        layout = layout_chart(_strip_plan(days=int(days)),
                              width=int(width))
        assert layout.header_mode == mode, (days, width)


@then(parsers.parse('a {days:d}-day plan at {width:d}px names cells "{names}"'))
def the_coarse_cells_are_named(ctx, days, width, names):
    from gantt_app.utils.chart_render import layout_chart

    layout = layout_chart(_strip_plan(days=days), width=width)
    assert [cell[2] for cell in layout.day_cells[:3]] == _phrases(names)


@then(parsers.parse('a {days:d}-day plan at {width:d}px names every cell '
                    'starting "{prefix}"'))
def every_cell_names_its_unit(ctx, days, width, prefix):
    from gantt_app.utils.chart_render import layout_chart

    layout = layout_chart(_strip_plan(days=days), width=width)
    assert all(cell[2].startswith(prefix) for cell in layout.day_cells)


@then(parsers.parse('a {days:d}-day plan at {width:d}px carries bands '
                    '"{names}"'))
def the_band_carries_years(ctx, days, width, names):
    from gantt_app.utils.chart_render import layout_chart

    layout = layout_chart(_strip_plan(days=days), width=width)
    assert [band[2] for band in layout.month_bands] == _phrases(names)


@then(parsers.parse('a band for "{day}" fits {width:d}px as "{label}"'))
def a_band_shortens(day, width, label):
    from gantt_app.utils.chart_render import _fit_label

    when = _day(day)
    full = (when.strftime('%B %Y').upper(),
            when.strftime('%b %Y').upper(),
            when.strftime('%b').upper())
    assert _fit_label(full, width, 12) == label


@then(parsers.parse('a band for "{day}" in {width:d}px is left blank'))
def a_band_is_left_blank(day, width):
    from gantt_app.utils.chart_render import _fit_label

    when = _day(day)
    full = (when.strftime('%B %Y').upper(),
            when.strftime('%b %Y').upper(),
            when.strftime('%b').upper())
    assert _fit_label(full, width, 12) == ''


@then(parsers.parse('an {days:d}-day plan at {width:d}px has no cells and '
                    'names its bands'))
def the_year_floor_names_its_bands(ctx, days, width):
    from gantt_app.utils.chart_render import layout_chart

    layout = layout_chart(_strip_plan(days=days), width=width)
    assert layout.day_cells == []
    assert all(band[2] for band in layout.month_bands)


@then('these plans still carry a month band')
def the_band_survives_every_mode(ctx, datatable):
    from gantt_app.utils.chart_render import layout_chart

    for days, width in (row for row in datatable[1:]):
        layout = layout_chart(_strip_plan(days=int(days)), width=int(width))
        assert layout.month_bands, f"{days}d at {width}px"


@then(parsers.parse('the svg names "{text}" and the image draws'))
def both_renderers_draw_it(ctx, text):
    from gantt_app.utils.chart_render import render_image, render_svg

    svg = render_svg(ctx.project, width=1200)
    image = render_image(ctx.project, width=1200, scale=1)

    assert text in svg
    assert image is not None


@then('the header colours match the default settings')
def the_header_colours_match():
    from gantt_app.utils.chart_figure import DEFAULT_SETTINGS
    from gantt_app.views import theme

    for key in DEFAULT_SETTINGS:
        if key.startswith('header_'):
            assert (DEFAULT_SETTINGS[key]
                    == getattr(theme, key.upper())[0]), key
