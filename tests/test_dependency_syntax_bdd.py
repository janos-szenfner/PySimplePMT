"""
The Dependencies column's grammar.

The scenarios live in features/dependency_syntax.feature. They pin the
grammar down as a contract: what a reader types, and what is written
back into the cell afterwards, have to be the same language or the
column loses work every time it normalises.

Typing into the grid itself needs a display and stays in
tests/test_dependency_syntax.py.
"""

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.dependencysyntax import format_links, parse
from gantt_app.core.models import Dependency, Project, Task


scenarios('features/dependency_syntax.feature')


BASE = datetime(2026, 8, 25)


@pytest.fixture
def ctx():
    return SimpleNamespace(project=None, links=None, errors=None)


# ---- parsing the cell ----------------------------------------------------------

@when(parsers.parse('"{text}" is parsed'))
def a_cell_is_parsed(ctx, text):
    ctx.links, ctx.errors = parse(text)


@then(parsers.parse('it gives {count:d} link and no errors'))
@then(parsers.parse('it gives {count:d} links and no errors'))
def it_gives_links_and_no_errors(ctx, count):
    assert ctx.errors == []
    assert len(ctx.links) == count


@then(parsers.parse('it gives {count:d} link'))
@then(parsers.parse('it gives {count:d} links'))
def it_gives_links(ctx, count):
    assert len(ctx.links) == count


@then('it gives no links')
def it_gives_no_links(ctx):
    assert ctx.links == []


@then(parsers.parse('the link reads as "{number}" {dep_type} lag {lag:d} '
                    '"{unit}"'))
def the_link_reads(ctx, number, dep_type, lag, unit):
    link = ctx.links[0]
    assert link.number == number
    assert link.dep_type == dep_type
    assert link.lag == lag
    assert link.lag_unit == unit


@then(parsers.parse('they read as "{first}" {first_type} lag {first_lag:d} '
                    '"{first_unit}" and "{second}" {second_type} '
                    'lag {second_lag:d} "{second_unit}"'))
def they_read_as(ctx, first, first_type, first_lag, first_unit,
                 second, second_type, second_lag, second_unit):
    found = [(link.number, link.dep_type, link.lag, link.lag_unit)
             for link in ctx.links]
    assert found == [(first, first_type, first_lag, first_unit),
                     (second, second_type, second_lag, second_unit)]


@then(parsers.parse('the link\'s unit is "{unit}"'))
def the_links_unit(ctx, unit):
    assert ctx.links[0].lag_unit == unit


@then('an empty cell gives no links and no errors')
def an_empty_cell(ctx):
    assert parse('') == ([], [])


@then(parsers.parse('"{text}" gives no links and no errors'))
def a_cell_of_separators(ctx, text):
    assert parse(text) == ([], [])


@then(parsers.parse('{count:d} error mentioning "{fragment}"'))
def errors_mentioning(ctx, count, fragment):
    assert len(ctx.errors) == count
    assert fragment in ctx.errors[0]


@then(parsers.parse('an error mentions "{fragment}"'))
def an_error_mentions(ctx, fragment):
    assert any(fragment in error for error in ctx.errors)


@then(parsers.parse('{count:d} error'))
@then(parsers.parse('{count:d} errors'))
def that_many_errors(ctx, count):
    assert len(ctx.errors) == count


@then('an error is given')
def an_error_is_given(ctx):
    assert ctx.errors


# ---- writing them back ----------------------------------------------------------

@when(parsers.parse('a "{dep_type}" link of lag {lag:d} "{unit}" is written '
                    'for number {number:d}'))
def a_link_is_written(ctx, dep_type, lag, unit, number):
    link = Dependency('the-key', dep_type, 'Hard', lag, unit)
    ctx.written = link.to_syntax_string(number)


@then(parsers.parse('it reads back as "{number}" "{dep_type}" lag {lag:d} '
                    '"{unit}"'))
def it_reads_back(ctx, number, dep_type, lag, unit):
    links, errors = parse(ctx.written)
    assert errors == []
    assert len(links) == 1, ctx.written
    link = links[0]
    assert link.number == number, ctx.written
    assert link.dep_type == dep_type, ctx.written
    assert link.lag == lag, ctx.written
    assert link.lag_unit == unit, ctx.written


@then(parsers.parse('a plain link writes as "{text}"'))
def a_plain_link_writes(text):
    assert Dependency('k').to_syntax_string(text) == text


@then(parsers.parse('an FS link of lag {lag:d} days writes as "{text}"'))
def a_lagged_link_writes(lag, text):
    assert Dependency('k', 'FS', 'Hard', lag).to_syntax_string(3) == text


@then(parsers.parse('links to tasks 1 and 3 write as "{text}"'))
def links_are_written_comma_separated(text):
    numbers = {'a': 1, 'b': 3}
    links = [Dependency('a'), Dependency('b', 'SS', 'Hard', 1)]
    assert format_links(links, numbers) == text


@then('a link to a missing task writes as nothing')
def a_gone_link_writes_nothing():
    assert format_links([Dependency('gone')], {'a': 1}) == ''


@then(parsers.parse('an SF link of lag {lag:d} percent keeps its unit '
                    'through a save'))
def the_unit_survives_a_save(lag):
    link = Dependency('k', 'SF', 'Hard', lag, 'percent')
    assert Dependency.from_any(link.to_dict()).lag_unit == 'percent'


@then(parsers.parse('a saved link with no unit reads as "{unit}"'))
def a_link_before_units(unit):
    assert (Dependency.from_any({'task_id': 'k', 'lag': 2}).lag_unit
            == unit)


# ---- the cell checked against the plan ---------------------------------------------

@given('a plan of three tasks')
def a_plan_of_three(ctx):
    """Three tasks, numbered 1 to 3."""
    ctx.project = Project(name="Plan")
    for task_id in ('first', 'second', 'third'):
        ctx.project.add_task(Task(id=task_id, name=task_id,
                                  task_type="Task", start_date=BASE,
                                  end_date=BASE + timedelta(days=2)))


@given(parsers.parse('"{task_id}" already waits on "{predecessor}"'))
def already_waits_on(ctx, task_id, predecessor):
    ctx.project.get_task_by_id(task_id).add_dependency(predecessor)


@given(parsers.parse('"{task_id}" sits under "{parent}"'))
def sits_under(ctx, task_id, parent):
    ctx.project.get_task_by_id(task_id).parent_task_id = parent


@when(parsers.parse('"{task_id}" reads "{text}"'))
def a_task_reads(ctx, task_id, text):
    ctx.deps_before = list(
        ctx.project.get_task_by_id(task_id).dependencies)
    ctx.links, ctx.errors = ctx.project.parse_dependencies(task_id, text)


@when(parsers.parse('"{task_id}" reads the number of "{other}"'))
def a_task_reads_a_number(ctx, task_id, other):
    # The number is looked up rather than written here: moving a task
    # under another changes the display order, so which task '1' names
    # changes with it. That is the numbering working, not a hazard - but
    # a test that hard-coded the number would be asserting about a
    # different task than it meant to.
    number = ctx.project.display_ids()[other]
    ctx.links, ctx.errors = ctx.project.parse_dependencies(
        task_id, str(number))


@then(parsers.parse('the links point at "{ids}"'))
def the_links_point_at(ctx, ids):
    wanted = [piece.strip() for piece in ids.split(',')]
    assert [link.task_id for link in ctx.links] == wanted


@then(parsers.parse('"{task_id}" holds the links it always did'))
def holds_the_links_it_always_did(ctx, task_id):
    # The probe's links must not be left on the task after a failed
    # check - a plan holding them is a worse fault than the one guarded
    # against.
    assert (list(ctx.project.get_task_by_id(task_id).dependencies)
            == ctx.deps_before)


# ---- the engine is unchanged ---------------------------------------------------------

@given(parsers.parse('two five-day tasks beginning "{start}"'))
def two_five_day_tasks(ctx, start):
    """Two five-day tasks, the second free to wait on the first."""
    monday = _day(start)
    ctx.project = Project(name="Plan")
    ctx.project.add_task(Task(id='first', name='First', task_type='Task',
                              start_date=monday,
                              end_date=monday + timedelta(days=4)))
    ctx.project.add_task(Task(id='second', name='Second', task_type='Task',
                              start_date=monday,
                              end_date=monday + timedelta(days=4)))


def _day(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%d")


def _link(ctx):
    return ctx.project.get_task_by_id('second').dependencies[0]


@when(parsers.parse('"{task_id}" waits on "{predecessor}"'))
@given(parsers.parse('"{task_id}" waits on "{predecessor}"'))
def waits_on(ctx, task_id, predecessor):
    ctx.project.get_task_by_id(task_id).add_dependency(
        predecessor, 'FS', 'Hard')
    ctx.project.reschedule()


@when(parsers.parse('"{task_id}" waits on "{predecessor}" with lag {lag:d} '
                    '"{unit}"'))
@given(parsers.parse('"{task_id}" waits on "{predecessor}" with lag {lag:d} '
                     '"{unit}"'))
def waits_on_with_lag(ctx, task_id, predecessor, lag, unit):
    ctx.project.get_task_by_id(task_id).add_dependency(
        predecessor, 'FS', 'Hard', lag, unit)
    ctx.project.reschedule()


@then(parsers.parse('"{task_id}" begins "{start}"'))
def begins(ctx, task_id, start):
    task = ctx.project.get_task_by_id(task_id)
    assert task.start_date.date().isoformat() == start


@then(parsers.parse('a lag of {lag:d} days starts "{task_id}" before '
                    'a plain link does'))
def a_lead_pulls_it_back(ctx, lag, task_id):
    task = ctx.project.get_task_by_id(task_id)
    task.add_dependency('first', 'FS', 'Hard', lag)
    ctx.project.reschedule()
    early = task.start_date

    plain = Project(name="Plain")
    plain.add_task(Task(id='first', name='First', task_type='Task',
                        start_date=_day('2026-08-17'),
                        end_date=_day('2026-08-17') + timedelta(days=4)))
    plain.add_task(Task(id='second', name='Second', task_type='Task',
                        start_date=_day('2026-08-17'),
                        end_date=_day('2026-08-17') + timedelta(days=4)))
    plain.get_task_by_id('second').add_dependency('first', 'FS', 'Hard')
    plain.reschedule()

    assert early < plain.get_task_by_id(task_id).start_date


@then(parsers.parse('the link\'s lag days are {days:d}'))
def the_lag_days_are(ctx, days):
    assert ctx.project.lag_days(_link(ctx)) == days


@then('the lag days equal the link\'s lag')
def the_days_path_is_untouched(ctx):
    link = _link(ctx)
    assert ctx.project.lag_days(link) == link.lag


@then(parsers.parse('"{task_id}" works {days:d} days'))
def works_days(ctx, task_id, days):
    assert ctx.project.working_duration(
        ctx.project.get_task_by_id(task_id)) == days


@when(parsers.parse('the link\'s predecessor is changed to "{task_id}"'))
def the_predecessor_is_changed(ctx, task_id):
    _link(ctx).task_id = task_id


@when(parsers.parse('the link\'s unit becomes "{unit}"'))
def the_unit_becomes(ctx, unit):
    ctx.signature = ctx.project._analysis_signature()
    _link(ctx).lag_unit = unit


@then('the analysis signature has moved')
def the_signature_moved(ctx):
    assert ctx.project._analysis_signature() != ctx.signature


@then(parsers.parse('the undo snapshot keeps the unit "{unit}" on "{task_id}"'))
def the_snapshot_keeps_the_unit(ctx, unit, task_id):
    _order, _parents, links = ctx.project.structure_snapshot()
    assert links[task_id][0].lag_unit == unit


@then(parsers.parse('the clipboard keeps the unit "{unit}" on "{task_id}"'))
def the_clipboard_keeps_the_unit(ctx, unit, task_id):
    from gantt_app.utils.copypastecut import ClipboardService

    data = ctx.project.get_task_by_id(task_id).to_dict()
    rebuilt = ClipboardService(ctx.project)._dict_to_task(data)
    assert rebuilt.dependencies[0].lag_unit == unit
