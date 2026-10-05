"""
The search box's matching.

The scenarios live in features/searchbox.feature. They pin down which
fields the needle is looked for in, that a match brings its ancestors
and nothing else, and that searching touches the view and not the plan.

The box itself and the list it filters need a display and stay in
tests/test_searchbox.py.
"""

from datetime import datetime
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Project, Task


scenarios('features/searchbox.feature')


@pytest.fixture
def ctx():
    return SimpleNamespace(project=None)


def _search_plan() -> Project:
    """A small plan with something in every field."""
    project = Project(name="Search")

    phase = Task(id="P1", name="Design Phase",
                 start_date=datetime(2026, 9, 7),
                 end_date=datetime(2026, 9, 18),
                 task_type='Phase')
    task = Task(id="T1", name="UI Mockups",
                start_date=datetime(2026, 9, 7),
                end_date=datetime(2026, 9, 11),
                parent_task_id="P1", duration=5, progress=40,
                priority="High",
                details="Blocked by JIRA-4821, waiting on vendor")
    subtask = Task(id="S1", name="Wireframe",
                   start_date=datetime(2026, 9, 7),
                   end_date=datetime(2026, 9, 8),
                   parent_task_id="T1")
    other = Task(id="T2", name="Server migration",
                 start_date=datetime(2026, 9, 14),
                 end_date=datetime(2026, 9, 15),
                 calendar_id="weekend-shift")
    other.add_dependency("T1", "FS", "Hard", lag=2)

    for row in (phase, task, subtask, other):
        project.add_task(row)
    return project


def _found(ctx, needle):
    """The names that match, in plan order."""
    from gantt_app.views.searchbox import matching_task_ids
    ids = matching_task_ids(ctx.project, needle)
    return [t.name for t in ctx.project.tasks if t.id in ids]


def _ids(text: str):
    return {piece.strip() for piece in text.split(',')}


@given('the search plan')
def the_search_plan(ctx):
    ctx.project = _search_plan()


@given(parsers.parse('a plan holding the milestone "{name}" on "{day}"'))
def a_milestone_plan(ctx, name, day):
    ctx.project = Project(name="M")
    ctx.project.add_task(Task(
        id="M1", name=name,
        start_date=datetime.strptime(day, "%Y-%m-%d"),
        is_milestone=True))


# ---- finding -------------------------------------------------------------------------

@then(parsers.parse('"{needle}" finds "{names}"'))
def finds_exactly(ctx, needle, names):
    assert _found(ctx, needle) == [name.strip() for name in names.split(',')]


@then(parsers.parse('"{needle}" finds "{name}" at least'))
def finds_at_least(ctx, needle, name):
    assert name in _found(ctx, needle)


@then(parsers.parse('"{needle}" finds {count:d} names'))
def finds_that_many(ctx, needle, count):
    assert len(_found(ctx, needle)) == count


@then(parsers.parse('"{needle}" finds nothing'))
def finds_nothing(ctx, needle):
    assert _found(ctx, needle) == []


@then(parsers.parse('"{task_id}\'s" shown number finds "{name}"'))
def the_shown_number_finds(ctx, task_id, name):
    shown = ctx.project.display_ids()[task_id]
    assert name in _found(ctx, str(shown))


@then(parsers.parse('"{task_id}\'s" shown number padded finds "{name}"'))
def the_padded_number_finds(ctx, task_id, name):
    shown = ctx.project.display_ids()[task_id]
    assert name in _found(ctx, str(shown).zfill(ctx.project.ID_WIDTH))


@then(parsers.parse('"{needle}" finds "{name}" and nothing else'))
def finds_and_nothing_else(ctx, needle, name):
    assert _found(ctx, needle) == [name]


@then(parsers.parse('"{first}" finds what "{second}" finds'))
def finds_the_same(ctx, first, second):
    assert _found(ctx, first) == _found(ctx, second)


@then(parsers.parse('an empty search and "{spaces}" match every task'))
def an_empty_search_matches_everything(ctx, spaces):
    from gantt_app.views.searchbox import task_matches
    for task in ctx.project.tasks:
        assert task_matches(task, "", ctx.project)
        assert task_matches(task, spaces, ctx.project)


@then('an empty visible search is unasked')
def an_empty_search_asks_nothing(ctx):
    from gantt_app.views.searchbox import visible_task_ids
    assert visible_task_ids(ctx.project, "") is None


@then(parsers.parse('"{task_id}\'s" haystack is one lower-case string'))
def the_haystack_is_lower_case(ctx, task_id):
    from gantt_app.views.searchbox import task_haystack
    task = ctx.project.get_task_by_id(task_id)
    haystack = task_haystack(task, ctx.project)
    assert isinstance(haystack, str)
    assert haystack == haystack.lower()


# ---- what stays on screen ---------------------------------------------------------------

@then(parsers.parse('"{needle}" leaves "{ids}" on screen'))
def leaves_on_screen(ctx, needle, ids):
    from gantt_app.views.searchbox import visible_task_ids
    assert visible_task_ids(ctx.project, needle) == _ids(ids)


@then(parsers.parse('"{needle}" leaves "{task_id}" on screen at least'))
def leaves_on_screen_at_least(ctx, needle, task_id):
    from gantt_app.views.searchbox import visible_task_ids
    assert task_id in visible_task_ids(ctx.project, needle)


@then(parsers.parse('"{needle}" leaves nothing on screen'))
def leaves_nothing(ctx, needle):
    from gantt_app.views.searchbox import visible_task_ids
    assert visible_task_ids(ctx.project, needle) == set()


@then(parsers.parse('"{needle}" matches "{ids}"'))
def matches(ctx, needle, ids):
    from gantt_app.views.searchbox import matching_task_ids
    assert matching_task_ids(ctx.project, needle) == _ids(ids)


@when(parsers.parse('"{task_id}" is made a child of "{parent}"'))
def a_parent_loop(ctx, task_id, parent):
    ctx.project.get_task_by_id(task_id).parent_task_id = parent


# ---- it must not touch the plan ------------------------------------------------------------

@when(parsers.parse('"{needle}" is searched'))
def a_search_is_made(ctx, needle):
    ctx.count = len(ctx.project.tasks)
    from gantt_app.views.searchbox import visible_task_ids
    visible_task_ids(ctx.project, needle)


@then(parsers.parse('the plan still holds {count:d} tasks'))
def the_plan_is_untouched(ctx, count):
    assert len(ctx.project.tasks) == count == ctx.count


@when(parsers.parse('the plan is rescheduled and "{needle}" is searched '
                    'and it is rescheduled'))
def a_search_between_reschedules(ctx, needle):
    from gantt_app.views.searchbox import visible_task_ids
    ctx.project.reschedule()
    phase = ctx.project.get_task_by_id('P1')
    ctx.span = (phase.start_date, phase.end_date)
    visible_task_ids(ctx.project, needle)
    ctx.project.reschedule()


@then(parsers.parse('"{task_id}\'s" span is what it was'))
def the_span_is_unchanged(ctx, task_id):
    task = ctx.project.get_task_by_id(task_id)
    assert (task.start_date, task.end_date) == ctx.span
