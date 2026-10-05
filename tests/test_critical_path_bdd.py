"""
Critical path analysis - the arithmetic behind it.

The scenarios live in features/critical_path.feature. What they pin down
is the critical path method itself: the float the two passes produce,
that every zero-float task is found rather than one chain through them,
and that the link types are honoured on the way back.

The window it opens and the rows it paints need a display and are kept
in tests/test_critical_path.py.

A network is written as a table - id, start, end, and its links as
predecessor:type:lag triples. An empty end is a milestone.
"""

import copy as copy_module
from datetime import date, datetime
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Project, Task


scenarios('features/critical_path.feature')


def _d(text: str) -> datetime:
    """An ISO feature date as the datetime the model carries."""
    return datetime.strptime(text, "%Y-%m-%d")


def _ids(text: str):
    """A "A, B, C" cell as a list of task ids."""
    return [piece.strip() for piece in text.split(',')]


def _network(datatable):
    """A project from the feature's id/start/end/links table."""
    project = Project(name="Analysis")
    for row in datatable[1:]:
        task_id = row[0].strip()
        end = row[2].strip()
        task = Task(
            id=task_id, name=task_id,
            start_date=_d(row[1].strip()),
            end_date=_d(end) if end else None,
            is_milestone=end == '',
        )
        links = row[3].strip()
        for link in links.split(',') if links else []:
            predecessor, dep_type, lag = link.strip().split(':')
            task.add_dependency(predecessor, dep_type, 'Hard', int(lag))
        project.add_task(task)
    return project


def _floats(project):
    """Total float per task id."""
    return {task_id: found.total_float
            for task_id, found in project.schedule_analysis().items()}


def _critical(project):
    """The ids the analysis calls critical, sorted."""
    return sorted(t.id for t in project.get_critical_path())


@pytest.fixture
def ctx():
    return SimpleNamespace(project=None)


# ---- networks ---------------------------------------------------------------

@given('an analysed network')
def an_analysed_network(ctx, datatable):
    ctx.project = _network(datatable)
    ctx.project.reschedule()


@given('a network')
def a_network(ctx, datatable):
    ctx.project = _network(datatable)


@when('it is analysed')
def it_is_analysed(ctx):
    ctx.analysis = ctx.project.schedule_analysis()


@given(parsers.parse('a phase "{phase}" over a subtask "{task_id}" '
                     'of the same span'))
def a_phase_over_a_subtask(ctx, phase, task_id):
    ctx.project = Project(name="Nested")
    ctx.project.add_task(Task(id=phase, name=phase, task_type="Phase",
                              start_date=datetime(2026, 1, 5),
                              end_date=datetime(2026, 1, 9)))
    ctx.project.add_task(Task(id=task_id, name=task_id, task_type="Subtask",
                              parent_task_id=phase,
                              start_date=datetime(2026, 1, 5),
                              end_date=datetime(2026, 1, 9)))
    ctx.project.reschedule()


@when('the plan is analysed')
def the_plan_is_analysed(ctx):
    ctx.analysis = ctx.project.schedule_analysis()


# ---- deadline plans ---------------------------------------------------------

@given(parsers.parse('a plan with "{task_id}" from "{start}" to "{end}" '
                     'due "{deadline}"'))
def a_plan_with_a_deadline(ctx, task_id, start, end, deadline):
    ctx.project = Project(name="Deadline")
    ctx.project.add_task(Task(
        id=task_id, name=task_id,
        start_date=_d(start), end_date=_d(end), deadline=_d(deadline)))


@given(parsers.parse('a plan with "{task_id}" from "{start}" to "{end}"'))
def a_plan_with_dates(ctx, task_id, start, end):
    ctx.project = Project(name="Deadline")
    task = Task(id=task_id, name=task_id,
                start_date=_d(start), end_date=_d(end))
    ctx.project.add_task(task)
    ctx.task = task


@given(parsers.parse('it also holds "{task_id}" from "{start}" to "{end}"'))
def it_also_holds(ctx, task_id, start, end):
    ctx.project.add_task(Task(id=task_id, name=task_id,
                              start_date=_d(start), end_date=_d(end)))


@given('it is analysed once')
def it_is_analysed_once(ctx):
    ctx.before = ctx.project.schedule_analysis()


@given('a twin plan without the deadline')
def a_twin_plan(ctx):
    twin = Project(name="Plain")
    for task in ctx.project.tasks:
        twin.add_task(Task(
            id=task.id, name=task.name,
            start_date=task.start_date, end_date=task.end_date))
    ctx.twin = twin


@when(parsers.parse('"{task_id}" is given a deadline of "{deadline}"'))
def a_deadline_is_given(ctx, task_id, deadline):
    ctx.task.deadline = _d(deadline)


# ---- float and criticality assertions ----------------------------------------

@then(parsers.parse('the floats are "{pairs}"'))
def the_floats_are(ctx, pairs):
    floats = _floats(ctx.project)
    for pair in pairs.split(','):
        task_id, expected = pair.strip().split('=')
        assert floats[task_id] == int(expected), task_id


@then(parsers.parse('the float of "{task_id}" is {expected:d}'))
def the_float_is(ctx, task_id, expected):
    assert _floats(ctx.project)[task_id] == expected


@then(parsers.parse('the float of "{task_id}" is negative'))
def the_float_is_negative(ctx, task_id):
    assert _floats(ctx.project)[task_id] < 0


@then(parsers.parse('the critical tasks are "{ids}"'))
def the_critical_tasks_are(ctx, ids):
    assert _critical(ctx.project) == _ids(ids)


@then(parsers.parse('"{ids}" have their late dates equal their early dates'))
def late_equals_early(ctx, ids):
    analysis = ctx.project.schedule_analysis()
    for task_id in _ids(ids):
        found = analysis[task_id]
        assert found.late_start == found.early_start, task_id
        assert found.late_finish == found.early_finish, task_id


@then(parsers.parse('"{task_id}" may finish {days:d} days later'))
def may_finish_later(ctx, task_id, days):
    found = ctx.project.schedule_analysis()[task_id]
    assert found.late_finish == found.early_finish + days


# ---- link types ---------------------------------------------------------------

@then(parsers.parse('"{first}" may finish no earlier than "{second}" '
                    'starts early'))
def may_run_on(ctx, first, second):
    analysis = ctx.project.schedule_analysis()
    assert (analysis[first].late_finish
            >= analysis[second].early_start)


@then(parsers.parse('"{first}" must finish strictly before "{second}" '
                    'starts early'))
def must_finish_first(ctx, first, second):
    analysis = ctx.project.schedule_analysis()
    assert (analysis[first].late_finish
            < analysis[second].early_start)


@then(parsers.parse('"{short}" finishes late when "{long}" does'))
def finishes_tied(ctx, short, long):
    analysis = ctx.project.schedule_analysis()
    assert (analysis[short].late_finish
            == analysis[long].late_finish)


@then(parsers.parse('"{task_id}" has some float'))
def has_some_float(ctx, task_id):
    assert ctx.project.schedule_analysis()[task_id].total_float > 0


# ---- what is left out ---------------------------------------------------------

@then(parsers.parse('"{task_id}" is not in the analysis'))
def not_analysed(ctx, task_id):
    assert task_id not in ctx.analysis


@then(parsers.parse('"{task_id}" is in the analysis'))
def is_analysed(ctx, task_id):
    assert task_id in ctx.analysis


@then(parsers.parse('"{task_id}" takes no time'))
def takes_no_time(ctx, task_id):
    found = ctx.project.schedule_analysis()[task_id]
    assert found.early_start == found.early_finish


@then(parsers.parse('"{task_id}" is critical'))
def is_critical(ctx, task_id):
    assert task_id in _critical(ctx.project)


@then('an empty plan analyses to nothing')
def an_empty_plan():
    assert Project(name="Empty").schedule_analysis() == {}
    assert Project(name="Empty").get_critical_path() == []


# ---- deadline assertions -------------------------------------------------------

@then(parsers.parse('"{task_id}" is not critical'))
def is_not_critical(ctx, task_id):
    assert task_id not in _critical(ctx.project)


@then('the analysis is recomputed')
def the_analysis_is_recomputed(ctx):
    assert ctx.project.schedule_analysis() is not ctx.before


@then(parsers.parse('the two answers agree on "{task_id}"'))
def the_two_answers_agree(ctx, task_id):
    assert _floats(ctx.project)[task_id] == _floats(ctx.twin)[task_id]


@then(parsers.parse('the analysis covers "{ids}"'))
def the_analysis_covers(ctx, ids):
    assert set(ctx.analysis) == set(_ids(ids))


# ---- the shape of what comes back ----------------------------------------------

@then('each finding is internally consistent')
def each_finding_is_consistent(ctx):
    for task_id, found in ctx.project.schedule_analysis().items():
        assert found.task_id == task_id
        assert (found.early_finish - found.early_start
                == found.late_finish - found.late_start)
        assert found.total_float == found.late_finish - found.early_finish
        assert found.is_critical == (found.total_float <= 0)


@then(parsers.parse('"{task_id}" has early start {offset:d}'))
def has_early_start(ctx, task_id, offset):
    assert ctx.project.schedule_analysis()[task_id].early_start == offset


@then(parsers.parse('"{task_id}" has early span {start:d} to {finish:d}'))
def has_early_span(ctx, task_id, start, finish):
    found = ctx.project.schedule_analysis()[task_id]
    assert found.early_start == start, task_id
    assert found.early_finish == finish, task_id


# ---- where it is reached from ---------------------------------------------------

@then(parsers.parse('"{icon}" sits between two separators'))
def between_two_separators(icon):
    from gantt_app.views.toolbar import IconToolbar

    row = [name for name, _tip, _action in IconToolbar.ICON_ACTIONS]
    index = row.index(icon)
    assert row[index - 1] == IconToolbar.SEPARATOR
    assert row[index + 1] == IconToolbar.SEPARATOR


@then(parsers.parse('"{before}" precedes it and "{after}" follows it'))
def the_neighbouring_icons(before, after):
    from gantt_app.views.toolbar import IconToolbar

    row = [name for name, _tip, _action in IconToolbar.ICON_ACTIONS]
    index = row.index('critical_path')
    assert row[index - 2] == before
    assert row[index + 2] == after


@then(parsers.parse('"{icon}" has icon strokes and a Toolbar method'))
def has_a_drawing_and_a_handler(icon):
    from gantt_app.resources.icons import ICON_STROKES
    from gantt_app.views.toolbar import Toolbar

    assert icon in ICON_STROKES
    assert callable(getattr(Toolbar, 'show_critical_path', None))


@then(parsers.parse('"{menu}" offers "{item}"'))
def the_menu_offers(menu, item):
    from tests.menuhelp import find, labels, menu_tree

    assert item in labels(find(menu_tree(), menu)['items'])


@then(parsers.parse('the icon actions include "{action}" but not "{absent}"'))
def the_icon_actions(action, absent):
    from gantt_app.views.toolbar import IconToolbar

    actions = [action for _i, _t, action in IconToolbar.ICON_ACTIONS]
    assert action in actions
    assert absent not in actions


@then(parsers.parse('"{method}" is a real Toolbar method'))
def is_a_toolbar_method(method):
    from gantt_app.views.toolbar import Toolbar

    assert callable(getattr(Toolbar, method, None))


# ---- tasks on calendars of their own ---------------------------------------------

@given(parsers.parse('a 24/7 task "{first}" of {days:d} days '
                     'followed by "{second}" of {other:d}'))
def a_mixed_plan(ctx, first, days, second, other):
    ctx.project = Project(name="Mixed")
    start = datetime(2026, 9, 10)                # a Thursday
    ctx.project.add_task(Task(id=first, name=first, start_date=start,
                              end_date=start, duration=days,
                              calendar_id="continuous"))
    follower = Task(id=second, name=second, start_date=start, end_date=start,
                    duration=other)
    follower.add_dependency(first, "FS", "Hard")
    ctx.project.add_task(follower)
    ctx.project.reschedule()


@given(parsers.parse('a weekend-shift task "{task_id}" of {days:d} days '
                     'from "{start}"'))
def a_weekend_shift_task(ctx, task_id, days, start):
    ctx.project = Project(name="Weekend")
    when = _d(start)
    ctx.project.add_task(Task(id=task_id, name=task_id, start_date=when,
                              end_date=when, duration=days,
                              calendar_id="weekend-shift"))
    ctx.project.reschedule()


@then(parsers.parse('"{task_id}" really starts "{start}"'))
def really_starts(ctx, task_id, start):
    task = ctx.project.get_task_by_id(task_id)
    assert task.start_date.date().isoformat() == start


@then(parsers.parse('"{task_id}" has equal early bounds and no float'))
def covers_none_of_the_axis(ctx, task_id):
    found = ctx.project.schedule_analysis()[task_id]
    assert found.early_start == found.early_finish
    assert found.total_float == 0


# ---- the cache ---------------------------------------------------------------------

@given('an analysed plan of three')
def a_plan_of_three(ctx):
    ctx.project = Project(name="Analysis")
    for task_id, start, end, links in (
            ("A", (2026, 3, 2), (2026, 3, 6), []),
            ("B", (2026, 3, 9), (2026, 3, 13), [("A", 'FS', 0)]),
            ("C", (2026, 3, 9), (2026, 3, 11), [("A", 'FS', 0)])):
        task = Task(id=task_id, name=task_id,
                    start_date=datetime(*start), end_date=datetime(*end))
        for predecessor, dep_type, lag in links:
            task.add_dependency(predecessor, dep_type, 'Hard', lag)
        ctx.project.add_task(task)
    ctx.project.reschedule()
    ctx.before = ctx.project.schedule_analysis()
    ctx.signature = ctx.project._analysis_signature_seen


@when('it is analysed twice')
def analysed_twice(ctx):
    ctx.second = ctx.project.schedule_analysis()


@then('the same answer object comes back')
def the_same_answer(ctx):
    assert ctx.second is ctx.before


@when(parsers.parse('"{task_id}" is stretched to "{end}"'))
def a_task_is_stretched(ctx, task_id, end):
    ctx.project.get_task_by_id(task_id).end_date = _d(end)


@when(parsers.parse('"{task_id}" loses its links'))
def loses_its_links(ctx, task_id):
    ctx.project.get_task_by_id(task_id).dependencies = []


@then('the signature has moved')
def the_signature_has_moved(ctx):
    assert ctx.project._analysis_signature() != ctx.signature


@when(parsers.parse('"{task_id}" is added from "{start}" to "{end}"'))
def a_task_is_added(ctx, task_id, start, end):
    ctx.project.add_task(Task(id=task_id, name=task_id,
                              start_date=_d(start), end_date=_d(end)))


@when(parsers.parse('"{day}" is ruled off as "{name}" on the plan'))
def ruled_off_on_the_plan(ctx, day, name):
    when = _d(day).date()
    ctx.project.calendar.add_override(when, False, name)


@when(parsers.parse('"{calendar_id}" gets "{day}" ruled off as "{name}"'))
def ruled_off_on_a_named_calendar(ctx, calendar_id, day, name):
    when = _d(day).date()
    ctx.project.calendars.get(calendar_id).calendar.add_override(
        when, False, name)


@then('the cached and computed answers agree')
def the_cached_answer_is_right(ctx):
    cached = ctx.before
    fresh = ctx.project._compute_schedule_analysis()
    assert dict(cached) == dict(fresh)


@when('the analysis is invalidated')
def the_analysis_is_invalidated(ctx):
    ctx.project.invalidate_schedule_analysis()


@then('a shallow copy still analyses')
def a_shallow_copy(ctx):
    assert copy_module.copy(ctx.project).schedule_analysis()


@then('a deep copy still analyses')
def a_deep_copy(ctx):
    assert copy_module.deepcopy(ctx.project).schedule_analysis()


@then('a bare restore still analyses')
def a_bare_restore(ctx):
    bare = Project.__new__(Project)
    bare.__dict__.update(ctx.project.__dict__)
    assert bare.schedule_analysis()


# ---- the axis it is measured on -------------------------------------------------------

@given('an axis plan')
def an_axis_plan(ctx):
    """Tasks over a span with weekends and a holiday in it."""
    ctx.project = Project(name="Axis")
    for task_id, start, end, links in (
            ("A", (2026, 3, 2), (2026, 3, 6), []),
            ("B", (2026, 3, 9), (2026, 3, 20), [("A", "FS", 0)]),
            ("C", (2026, 3, 9), (2026, 3, 11), [("A", "FS", 0)]),
            ("D", (2026, 3, 23), (2026, 3, 27), [("B", "FS", 0)])):
        task = Task(id=task_id, name=task_id,
                    start_date=datetime(*start), end_date=datetime(*end))
        for predecessor, dep_type, lag in links:
            task.add_dependency(predecessor, dep_type, 'Hard', lag)
        ctx.project.add_task(task)
    ctx.project.calendar.add_override(date(2026, 3, 17), False, "shutdown")
    ctx.project.reschedule()


def _counted(project):
    """The analysis with the axis taken away, so offsets are counted."""
    original = Project._working_day_axis
    Project._working_day_axis = lambda self, origin, tasks: {}
    try:
        return project._compute_schedule_analysis()
    finally:
        Project._working_day_axis = original


@then('the indexed and counted analyses agree')
def indexed_matches_counted(ctx):
    indexed = ctx.project._compute_schedule_analysis()
    counted = _counted(ctx.project)

    assert set(indexed) == set(counted)
    for task_id, found in indexed.items():
        assert found == counted[task_id], task_id


@then("the axis covers every task's start and end")
def the_axis_covers(ctx):
    tasks = list(ctx.project.tasks)
    origin = min(t.start_date for t in tasks)
    axis = ctx.project._working_day_axis(origin, tasks)

    for task in tasks:
        assert task.start_date.date() in axis, task.id
        if task.end_date is not None:
            assert task.end_date.date() in axis, task.id


@then('every axis offset equals the walked count')
def the_axis_counts(ctx):
    tasks = list(ctx.project.tasks)
    origin = min(t.start_date for t in tasks)
    axis = ctx.project._working_day_axis(origin, tasks)

    for day, offset in axis.items():
        walked = max(
            ctx.project.calendar.working_days_between(origin, day) - 1, 0)
        assert offset == walked, day


@then('the computed analysis is non-empty')
def the_fallback_still_answers(ctx):
    # The counted comparison above is what exercises the fallback path;
    # this pins down that the axis-built one is not empty either.
    assert ctx.project._compute_schedule_analysis()
