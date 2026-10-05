"""
pytest-bdd tests for the named calendars a plan holds, and which one a
task follows.

Run with:
    python3 -m pytest tests/test_calendar_registry_bdd.py -q

Nothing here needs a display. Dates are chosen so the weekday matters:
2026-09-10 is a Thursday, 2026-09-12 a Saturday, 2026-09-14 a Monday.
"""
from datetime import date, datetime
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.calendarregistry import (
    CalendarRegistry, NamedCalendar, PROJECT_DEFAULT_LABEL,
    default_registry, describe_week, preset_calendar, slugify,
)
from gantt_app.core.models import Project, Task
from gantt_app.core.workdaycalendar import WorkingCalendar

pytestmark = [
    pytest.mark.calendar_registry,
]

scenarios("features/calendar_registry.feature")


def _day(text):
    return datetime.strptime(text, "%Y-%m-%d")


@pytest.fixture
def ctx():
    return SimpleNamespace(
        registry=None, project=None, default=WorkingCalendar(),
        resolved=None, reopened=None, pair=[], ends_before={},
        result=None)


# ------------------------------------------------------------------
# slugs
# ------------------------------------------------------------------

@then(parsers.parse('slugifying "{name}" gives "{slug}"'))
def slugifying_gives(name, slug):
    assert slugify(name) == slug


@then(parsers.parse('slugifying a blank name gives "{slug}"'))
def slugifying_a_blank_name_gives(slug):
    assert slugify("") == slug


# ------------------------------------------------------------------
# the registry
# ------------------------------------------------------------------

@given("a registry")
def a_registry(ctx):
    ctx.registry = default_registry()


@then(parsers.parse('the calendar ids are "{ids}"'))
def the_calendar_ids_are(ctx, ids):
    expected = [item for item in ids.split(', ') if item]
    assert ctx.registry.ids() == expected


@then("the options lead with the plan's own")
def the_options_lead_with_the_plan(ctx):
    assert ctx.registry.options()[0] == (None, PROJECT_DEFAULT_LABEL)


@then("there is an option for every calendar")
def an_option_for_every_calendar(ctx):
    assert len(ctx.registry.options()) == len(ctx.registry) + 1


@when(parsers.parse('a calendar "{name}" is created'))
def a_calendar_is_created(ctx, name):
    ctx.registry.create(name)


@then(parsers.parse('the last calendar id is "{calendar_id}"'))
def the_last_calendar_id_is(ctx, calendar_id):
    assert ctx.registry.ids()[-1] == calendar_id


@when(parsers.parse('"{calendar_id}" is replaced by "{name}"'))
def a_calendar_is_replaced(ctx, calendar_id, name):
    ctx.registry.add(NamedCalendar(id=calendar_id, name=name,
                                   calendar=WorkingCalendar()))


@then(parsers.parse('"{calendar_id}" is now named "{name}"'))
def the_calendar_is_now_named(ctx, calendar_id, name):
    assert ctx.registry.get(calendar_id).name == name


@when(parsers.parse('two calendars named "{name}" are created'))
def two_calendars_are_created(ctx, name):
    ctx.pair = [ctx.registry.create(name), ctx.registry.create(name)]


@then("they hold different ids")
def they_hold_different_ids(ctx):
    assert ctx.pair[0].id != ctx.pair[1].id


@then(parsers.parse('the registry holds {count:d} calendars'))
def the_registry_holds(ctx, count):
    assert len(ctx.registry) == count


@when(parsers.parse('"{calendar_id}" is renamed "{name}"'))
def a_calendar_is_renamed(ctx, calendar_id, name):
    assert ctx.registry.rename(calendar_id, name)


@then(parsers.parse('removing "{calendar_id}" works'))
def removing_works(ctx, calendar_id):
    assert ctx.registry.remove(calendar_id)


@then(parsers.parse('removing "{calendar_id}" again does not'))
def removing_again_does_not(ctx, calendar_id):
    assert not ctx.registry.remove(calendar_id)


# ------------------------------------------------------------------
# resolution
# ------------------------------------------------------------------

@when(parsers.parse('"{calendar_id}" is resolved'))
def a_calendar_is_resolved(ctx, calendar_id):
    ctx.resolved = ctx.registry.resolve(calendar_id, ctx.default)


@when("nothing is resolved")
def nothing_is_resolved(ctx):
    ctx.resolved = ctx.registry.resolve(None, ctx.default)


@then(parsers.parse('the Saturday {day} is worked'))
def the_saturday_is_worked(ctx, day):
    assert ctx.resolved.is_working_day(_day(day).date())


@then(parsers.parse('the Saturday {day} is not worked'))
def the_saturday_is_not_worked(ctx, day):
    assert not ctx.resolved.is_working_day(_day(day).date())


@then("the plan's own week answers")
def the_plans_own_week_answers(ctx):
    assert ctx.resolved is ctx.default


@when(parsers.parse('"{calendar_id}" is removed'))
def a_calendar_is_removed(ctx, calendar_id):
    ctx.registry.remove(calendar_id)


@given("an empty registry")
def an_empty_registry(ctx):
    ctx.registry = CalendarRegistry()


@then(parsers.parse('resolving "{calendar_id}" answers the plan\'s own '
                    'week'))
def resolving_answers_the_plan(ctx, calendar_id):
    assert ctx.registry.resolve(calendar_id, ctx.default) is ctx.default


@then("resolving nothing answers the plan's own week")
def resolving_nothing_answers_the_plan(ctx):
    assert ctx.registry.resolve(None, ctx.default) is ctx.default


# ------------------------------------------------------------------
# describing a week
# ------------------------------------------------------------------

@then(parsers.parse('a calendar working Monday to Friday reads "{text}"'))
def the_standard_week_reads(text):
    assert describe_week(WorkingCalendar()) == text


@then(parsers.parse('a calendar working only the weekend reads '
                    '"{text}"'))
def the_weekend_reads(text):
    calendar = preset_calendar('w', 'W', (5, 6)).calendar
    assert describe_week(calendar) == text


@then(parsers.parse('a calendar working every day reads "{text}"'))
def every_day_reads(text):
    calendar = preset_calendar('c', 'C', range(7)).calendar
    assert describe_week(calendar) == text


@then(parsers.parse('a calendar working Monday, Wednesday and Friday '
                    'reads "{text}"'))
def an_unusual_week_reads(text):
    calendar = preset_calendar('x', 'X', (0, 2, 4)).calendar
    assert describe_week(calendar) == text


@then(parsers.parse('a calendar working nothing reads "{text}"'))
def nothing_worked_reads(text):
    calendar = WorkingCalendar(non_working_days=range(7))
    assert describe_week(calendar) == text


# ------------------------------------------------------------------
# storage
# ------------------------------------------------------------------

@given(parsers.parse('a registry where "{calendar_id}" takes {day} off '
                     'for "{reason}"'))
def a_registry_with_an_override(ctx, calendar_id, day, reason):
    ctx.registry = default_registry()
    ctx.registry.get(calendar_id).calendar.add_override(
        _day(day).date(), False, reason)


@when("the registry is saved and loaded")
def the_registry_is_saved_and_loaded(ctx):
    ctx.reopened = CalendarRegistry.from_dict(ctx.registry.to_dict())


@then("it equals what was saved")
def it_equals_what_was_saved(ctx):
    assert ctx.reopened == ctx.registry
    assert ctx.reopened.ids() == ctx.registry.ids()


@then(parsers.parse('"{calendar_id}" still holds the "{reason}" '
                    'override'))
def the_override_survives(ctx, calendar_id, reason):
    named = ctx.reopened.get(calendar_id)
    override = named.calendar.override_for(date(2026, 12, 25))
    assert override.reason == reason


@when("a dictionary keyed by id is loaded")
def a_dictionary_keyed_by_id_is_loaded(ctx):
    ctx.registry = CalendarRegistry.from_dict({
        'a': {'id': 'a', 'name': 'A', 'calendar': {}},
        'b': {'id': 'b', 'name': 'B', 'calendar': {}},
    })
    ctx.registry._ids = sorted(ctx.registry.ids())


@then(parsers.parse('the calendar ids sorted are "{ids}"'))
def the_calendar_ids_sorted(ctx, ids):
    assert ctx.registry._ids == [i for i in ids.split(', ') if i]


@when("a list with two bad entries is loaded")
def a_list_with_bad_entries_is_loaded(ctx):
    ctx.registry = CalendarRegistry.from_dict([
        {'id': 'kept', 'name': 'Kept', 'calendar': {}},
        'not a dictionary',
        {'name': 'no id at all'},
    ])


@when("nothing is loaded")
def nothing_is_loaded(ctx):
    ctx.registry = CalendarRegistry.from_dict(None)


@then("the registry is empty")
def the_registry_is_empty(ctx):
    assert len(ctx.registry) == 0


# ------------------------------------------------------------------
# a task follows its own calendar
# ------------------------------------------------------------------

@given(parsers.parse('a plan "{name}" with three tasks on three '
                     'calendars'))
def a_plan_with_three_tasks(ctx, name):
    ctx.project = Project(name=name)
    start = datetime(2026, 9, 10)           # a Thursday
    for identifier, task_name, calendar_id in (
            ("t1", "Frontend Work", None),
            ("t2", "Server Migration", "weekend-shift"),
            ("t3", "Load Test", "continuous")):
        ctx.project.add_task(Task(id=identifier, name=task_name,
                                  start_date=start, end_date=start,
                                  duration=2,
                                  calendar_id=calendar_id))


@when("the plan is rescheduled")
def the_plan_is_rescheduled(ctx):
    ctx.project.reschedule()
    ctx.ends_before = {t.id: t.end_date for t in ctx.project.tasks}
    ctx.starts_before = {t.id: t.start_date for t in ctx.project.tasks}


@then(parsers.parse('"{name}" runs {start} to {end}'))
def the_task_runs(ctx, name, start, end):
    task = _find(ctx, name)
    assert task.start_date.date() == _day(start).date()
    assert task.end_date.date() == _day(end).date()


@then(parsers.parse('"{name}" starts on {day}'))
def the_task_starts_on(ctx, name, day):
    assert _find(ctx, name).start_date.date() == _day(day).date()


@then(parsers.parse('"{name}" ends on {day}'))
def the_task_ends_on(ctx, name, day):
    assert _find(ctx, name).end_date.date() == _day(day).date()


@then(parsers.parse('every task holds {days:d} days of work'))
def every_task_holds_the_work(ctx, days):
    for task in ctx.project.tasks:
        assert ctx.project.working_duration(task) == days, task.name


@when(parsers.parse('"{calendar_id}" is removed from the plan'))
def removed_from_the_plan(ctx, calendar_id):
    ctx.project.calendars.remove(calendar_id)


@then(parsers.parse('"{name}" still follows "{calendar_id}"'))
def still_follows(ctx, name, calendar_id):
    assert _find(ctx, name).calendar_id == calendar_id


@then("every task ends where it did")
def every_task_ends_where_it_did(ctx):
    ends = {t.id: t.end_date for t in ctx.reopened.tasks}
    assert ends == ctx.ends_before


def _find(ctx, name):
    plan = ctx.reopened if ctx.reopened else ctx.project
    match = [t for t in plan.tasks if t.name == name]
    assert len(match) == 1, name
    return match[0]


# ------------------------------------------------------------------
# editing a named calendar
# ------------------------------------------------------------------

@given(parsers.parse('a plan "{name}" with "{task}" on "{calendar_id}" '
                     'for {days:d} days starting "{day}"'))
def a_plan_with_a_named_task(ctx, name, task, calendar_id, days, day):
    ctx.project = Project(name=name)
    start = _day(day)
    ctx.project.add_task(Task(id=task, name=task, start_date=start,
                              end_date=start, duration=days,
                              calendar_id=calendar_id))


@given(parsers.parse('a plan "{name}" with "{task}" on the plan\'s week '
                     'for {days:d} days starting "{day}"'))
def a_plan_with_a_plan_task(ctx, name, task, days, day):
    ctx.project = Project(name=name)
    start = _day(day)
    ctx.project.add_task(Task(id=task, name=task, start_date=start,
                              end_date=start, duration=days))


@when(parsers.parse('"{calendar_id}" gains Friday'))
def a_calendar_gains_friday(ctx, calendar_id):
    widened = default_registry()
    widened.add(preset_calendar(calendar_id, 'Weekend + Friday',
                                (4, 5, 6)))
    ctx.project.set_calendars(widened)


@then(parsers.parse('"{name}" still holds {days:d} days of work'))
def the_task_still_holds_the_work(ctx, name, days):
    assert ctx.project.working_duration(_find(ctx, name)) == days


@then(parsers.parse('"{name}" still ends where it did'))
def the_task_still_ends_where_it_did(ctx, name):
    task = _find(ctx, name)
    assert task.end_date == ctx.ends_before[task.id]


@when("the plan takes on a six-day week")
def the_plan_takes_on_a_six_day_week(ctx):
    ctx.project.set_working_week({6})


@given(parsers.parse('a plan "{name}" whose "{calendar_id}" takes '
                     '{day} off for "{reason}"'))
def a_plan_with_an_override(ctx, name, calendar_id, day, reason):
    ctx.project = Project(name=name)
    registry = default_registry()
    registry.get(calendar_id).calendar.add_override(
        _day(day).date(), False, reason)
    ctx.project.calendars = registry


@given(parsers.parse('a task "{name}" on "{calendar_id}" for {days:d} '
                     'day starting "{day}"'))
@given(parsers.parse('a task "{name}" on "{calendar_id}" for {days:d} '
                     'days starting "{day}"'))
def a_task_on_a_calendar(ctx, name, calendar_id, days, day):
    start = _day(day)
    ctx.project.add_task(Task(id=name, name=name, start_date=start,
                              end_date=start, duration=days,
                              calendar_id=calendar_id))


# ------------------------------------------------------------------
# which plans get the presets
# ------------------------------------------------------------------

@then(parsers.parse('a new plan\'s calendar ids are "{ids}"'))
def a_new_plans_calendar_ids_are(ids):
    expected = [i for i in ids.split(', ') if i]
    assert Project(name="New").calendars.ids() == expected


@then("a legacy plan gets no calendars")
def a_legacy_plan_gets_no_calendars():
    data = {'name': 'Old', 'tasks': [], 'start_date': None,
            'end_date': None}
    assert Project.from_dict(data).calendars.ids() == []


@then("a legacy plan saving an empty registry still has no calendars")
def a_legacy_empty_registry_stays_empty():
    data = {'name': 'Old', 'tasks': [], 'start_date': None,
            'end_date': None, 'calendars': []}
    assert Project.from_dict(data).calendars.ids() == []


@given(parsers.parse('a new plan with "{calendar_id}" removed'))
def a_new_plan_without(ctx, calendar_id):
    ctx.project = Project(name="New")
    ctx.project.calendars.remove(calendar_id)


@when("the plan is saved and loaded")
def the_plan_is_saved_and_loaded(ctx):
    ctx.reopened = Project.from_dict(ctx.project.to_dict())


@then(parsers.parse('the loaded plan\'s calendar ids are "{ids}"'))
def the_loaded_plans_calendar_ids_are(ctx, ids):
    expected = [i for i in ids.split(', ') if i]
    assert ctx.reopened.calendars.ids() == expected


# ------------------------------------------------------------------
# lag is counted on the plan's calendar
# ------------------------------------------------------------------

@given(parsers.parse('a follower on "{calendar}" lagging a Friday '
                     'finish by {lag:d}'))
def a_follower_lagging(ctx, calendar, lag):
    ctx.project = Project(name="Lag")
    ctx.project.add_task(Task(id="a", name="A",
                              start_date=datetime(2026, 9, 9),
                              end_date=datetime(2026, 9, 11)))
    calendar_id = None if calendar == "the plan's own" else calendar
    follower = Task(id="b", name="B", start_date=datetime(2026, 9, 14),
                    end_date=datetime(2026, 9, 14), duration=1,
                    calendar_id=calendar_id)
    follower.add_dependency("a", "FS", "Hard", lag=lag)
    ctx.project.add_task(follower)


@then(parsers.parse('the follower starts on "{day}"'))
def the_follower_starts_on(ctx, day):
    follower = ctx.project.get_task_by_id("b")
    assert follower.start_date.date() == _day(day).date()


# ------------------------------------------------------------------
# the container itself
# ------------------------------------------------------------------

@given('an empty registry')
def an_empty_registry(ctx):
    ctx.registry = CalendarRegistry()


@then('the registry answers empty')
def the_registry_answers_empty(ctx):
    assert not ctx.registry


@then('the registry is not a string')
def the_registry_is_not_a_string(ctx):
    assert not (ctx.registry == 'a string')
    assert ctx.registry != 'a string'


@given('a second registry made the same way')
def a_second_registry(ctx):
    ctx.other = default_registry()


@then('the two registries are equal')
def the_two_registries_are_equal(ctx):
    assert ctx.registry == ctx.other


@then(parsers.parse('renaming "{calendar_id}" to "{name}" says no'))
def renaming_a_ghost_says_no(ctx, calendar_id, name):
    assert ctx.registry.rename(calendar_id, name) is False


@then(parsers.parse('a saved registry of {value:d} loads empty'))
def an_unreadable_registry_loads_empty(value):
    assert CalendarRegistry.from_dict(value).ids() == []
