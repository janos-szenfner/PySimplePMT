"""
pytest-bdd tests for the formatting a row carries, and the defaults
folded into it (gantt_app/core/taskstyle.py).

Run with:
    python3 -m pytest tests/test_taskstyle_bdd.py -q

Nothing here needs a display.
"""
from datetime import datetime
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Project, Task
from gantt_app.core.taskstyle import (
    FILL_COLOURS, PRESETS, TEXT_COLOURS, TaskStyle, normalise_colour,
    resolve,
)
from gantt_app.utils.undoredo import (
    ProjectStateTracker, UndoRedoManager,
)

pytestmark = [
    pytest.mark.taskstyle,
]

scenarios("features/task_style.feature")


#: What the feature's words stand for when the value is not text.
NON_TEXT = {
    'nothing': None,
    'a number': 42,
    'a list': [],
}

NOT_A_COLOUR_TEXT = {
    'empty': '',
    'spaces': '   ',
    'red': 'red',
    '#12345': '#12345',
    '#gggggg': '#gggggg',
}

NOT_A_STYLE = {
    'nothing': None,
    'empty': {},
    'nonsense': 'nonsense',
    'a number': 7,
    'a list': [],
}


@pytest.fixture
def ctx():
    return SimpleNamespace(style=None, resolved=None, result=None,
                           task=None, project=None)


# ------------------------------------------------------------------
# WHEN - normalising colours
# ------------------------------------------------------------------

@when(parsers.parse('the colour "{text}" is normalised'))
def the_colour_is_normalised(ctx, text):
    ctx.result = normalise_colour(text)


@when(parsers.parse('the colour value {value} is normalised'))
def the_colour_value_is_normalised(ctx, value):
    ctx.result = normalise_colour(
        NON_TEXT.get(value, NOT_A_COLOUR_TEXT.get(value)))


# ------------------------------------------------------------------
# GIVEN - styles
# ------------------------------------------------------------------

@given("a fresh style")
def a_fresh_style(ctx):
    ctx.style = TaskStyle()


@given("a style marked bold")
def a_style_marked_bold(ctx):
    ctx.style = TaskStyle(bold=True)


@given("a fully marked style")
def a_fully_marked_style(ctx):
    ctx.style = TaskStyle(text_color='#c0392b', fill_color='#fff2cc',
                          bold=True, italic=False, underline=True)


@given(parsers.parse('a style with text colour "{colour}"'))
def a_style_with_text_colour(ctx, colour):
    ctx.style = TaskStyle(text_color=colour)


# ------------------------------------------------------------------
# WHEN - reading, changing, resolving
# ------------------------------------------------------------------

@when(parsers.parse('a saved style of {value} is read'))
def a_saved_style_is_read(ctx, value):
    ctx.style = TaskStyle.from_any(NOT_A_STYLE[value])


@when("the style is written and read back")
def the_style_round_trips(ctx):
    ctx.result = TaskStyle.from_any(ctx.style.to_dict())


@when("it is changed to be italic")
def it_is_changed_to_italic(ctx):
    ctx.original = ctx.style
    ctx.style = ctx.style.with_changes(italic=True)


@when(parsers.parse('a {level} row wearing nothing is resolved'))
def a_row_wearing_nothing_is_resolved(ctx, level):
    ctx.resolved = resolve(TaskStyle(), is_summary=(level == 'summary'))


@when("a summary row wearing a style marked not bold is resolved")
def a_summary_wearing_not_bold_is_resolved(ctx):
    ctx.resolved = resolve(TaskStyle(bold=False), is_summary=True)


@when(parsers.parse('a summary row wearing text colour "{colour}" '
                    'is resolved'))
def a_summary_wearing_colour_is_resolved(ctx, colour):
    ctx.resolved = resolve(TaskStyle(text_color=colour),
                           is_summary=True)


@when("no style is resolved for a leaf")
def no_style_is_resolved(ctx):
    ctx.resolved = resolve(None, is_summary=False)


# ------------------------------------------------------------------
# GIVEN/WHEN - the model
# ------------------------------------------------------------------

def _task(**kwargs):
    options = dict(id='1', name='X', start_date=datetime(2026, 7, 6))
    options.update(kwargs)
    return Task(**options)


@given("a task")
def a_task(ctx):
    ctx.task = _task()


@given("a task wearing a style")
def a_task_wearing_a_style(ctx):
    ctx.task = _task(style=TaskStyle(text_color='#c0392b', italic=True))


@given("a task saved without a style entry")
def a_task_saved_before_formatting(ctx):
    data = _task().to_dict()
    del data['style']
    ctx.task = Task.from_dict(data)


@given("a task with a calendar and a style")
def a_task_with_calendar_and_style(ctx):
    ctx.project = Project(name='P')
    ctx.task = _task(calendar_id='weekend', style=TaskStyle(bold=True))
    ctx.project.add_task(ctx.task)


@when("its style is set from a plain dictionary")
def its_style_is_set_from_a_dict(ctx):
    ctx.task.style = {'bold': True, 'fill_color': 'fff2cc'}


@when("the task is saved and read back")
def the_task_round_trips(ctx):
    ctx.task = Task.from_dict(ctx.task.to_dict())


@when("it is renamed through the undo tracker")
def it_is_renamed_through_the_tracker(ctx):
    tracker = ProjectStateTracker(ctx.project, UndoRedoManager())
    tracker.update_task(ctx.task.id, name='Renamed')
    ctx.task = ctx.project.get_task_by_id(ctx.task.id)


# ------------------------------------------------------------------
# THEN - colours and styles
# ------------------------------------------------------------------

@then(parsers.parse('the colour reads as "{colour}"'))
def the_colour_reads_as(ctx, colour):
    assert ctx.result == colour


@then("no colour comes out")
def no_colour_comes_out(ctx):
    assert ctx.result is None


@then("it is the default")
def it_is_the_default(ctx):
    assert ctx.style.is_default


@then("it writes nothing")
def it_writes_nothing(ctx):
    assert ctx.style.to_dict() is None


@then(parsers.parse('it writes only "{written}"'))
def it_writes_only(ctx, written):
    key, _, value = written.partition(': ')
    assert ctx.style.to_dict() == {key: value == 'True'}


@then("it comes back the same")
def it_comes_back_the_same(ctx):
    assert ctx.result == ctx.style


@then(parsers.parse('its text colour reads as "{colour}"'))
def its_text_colour_reads_as(ctx, colour):
    worn = ctx.resolved if ctx.resolved is not None else ctx.style
    assert worn.text_color == colour


@then("it has no fill colour")
def it_has_no_fill_colour(ctx):
    assert ctx.resolved.fill_color is None


@then("two styles marked bold are equal")
def two_bold_styles_are_equal(ctx):
    assert TaskStyle(bold=True) == TaskStyle(bold=True)


@then("they share one set entry")
def they_share_one_set_entry(ctx):
    assert len({TaskStyle(bold=True), TaskStyle(bold=True)}) == 1


@then("the new style is italic")
def the_new_style_is_italic(ctx):
    assert ctx.style.italic


@then("the original still is not")
def the_original_still_is_not(ctx):
    assert ctx.original.italic is None


@then("it is bold")
def it_is_bold(ctx):
    assert ctx.resolved.bold


@then("it is not bold")
def it_is_not_bold(ctx):
    assert not ctx.resolved.bold


@then("it is not italic and not underlined")
def it_is_plain_text(ctx):
    assert not ctx.resolved.italic
    assert not ctx.resolved.underline


# ------------------------------------------------------------------
# THEN - palettes and presets
# ------------------------------------------------------------------

@then("every colour the bar offers is usable")
def every_offered_colour_is_usable(ctx):
    for name, value in TEXT_COLOURS + FILL_COLOURS:
        assert name
        if value is not None:
            assert normalise_colour(value) == value, name


@then("both palettes offer a way back to default")
def both_palettes_offer_a_way_back(ctx):
    assert None in [value for _name, value in TEXT_COLOURS]
    assert None in [value for _name, value in FILL_COLOURS]


@then(parsers.parse('the presets are "{first}", "{second}", "{third}" '
                    'and "{fourth}"'))
def the_presets_are(ctx, first, second, third, fourth):
    assert [name for name, _style in PRESETS] == \
        [first, second, third, fourth]


@then(parsers.parse('the "{preset}" preset fills "{colour}" and is '
                    'bold'))
def the_preset_fills_and_is_bold(ctx, preset, colour):
    style = dict(PRESETS)[preset]
    assert style.fill_color == colour
    assert style.bold


@then(parsers.parse('the "{preset}" preset is "{colour}" bold and '
                    'italic'))
def the_preset_is_red_bold_italic(ctx, preset, colour):
    style = dict(PRESETS)[preset]
    assert style.text_color == colour
    assert style.bold
    assert style.italic


@then("no preset is the default")
def no_preset_is_the_default(ctx):
    for name, style in PRESETS:
        assert not style.is_default, name


# ------------------------------------------------------------------
# THEN - the model
# ------------------------------------------------------------------

@then("it wears no formatting")
def it_wears_no_formatting(ctx):
    assert ctx.task.style.is_default


@then(parsers.parse('it wears a real style with fill "{colour}"'))
def it_wears_a_real_style(ctx, colour):
    assert isinstance(ctx.task.style, TaskStyle)
    assert ctx.task.style.fill_color == colour


@then("its formatting came back the same")
def its_formatting_came_back(ctx):
    expected = TaskStyle(text_color='#c0392b', italic=True)
    assert ctx.task.style == expected


@then("its style and calendar survived")
def its_style_and_calendar_survived(ctx):
    assert ctx.task.style == TaskStyle(bold=True)
    assert ctx.task.calendar_id == 'weekend'
