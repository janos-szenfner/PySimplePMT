"""
pytest-bdd tests for the resource-calendar hierarchy (issue #38).

Run with:
    python3 -m pytest tests/test_resource_calendars_bdd.py -q

A task is scheduled where its own calendar and the calendars of the
resources on it agree; "Scheduling ignores resource calendars" on the
Advanced tab is the escape, and it is off by default. The calendar
mechanics need no display; the @display_dependent scenarios drive the
checkbox itself and skip where no display exists.
"""
import tkinter as tk
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Dependency, Project, Task
from gantt_app.core.resource_model import (
    DaysOffRange, MaterialResource, Resource, ResourceType,
    SchedulePattern,
)

pytestmark = [
    pytest.mark.resource_calendars,
]

scenarios("features/resource_calendars.feature")


def _display_available() -> bool:
    """Whether a usable Tk display is present."""
    try:
        root = tk.Tk()
    except Exception:
        return False
    root.destroy()
    return True


HAVE_DISPLAY = _display_available()


def _shut_down(root) -> None:
    """
    Take a root down, children first, without raising.

    Destroying a root while a Toplevel is still on it leaves Tk running
    ttk::ThemeChanged against an interpreter that has already gone, which
    floods stderr with "can't invoke event" tracebacks.
    """
    try:
        for child in list(root.children.values()):
            try:
                child.destroy()
            except Exception:
                pass
        root.destroy()
    except Exception:
        pass


def _day(text):
    """Dates are ISO strings; times '2026-01-07 15:30' parse too."""
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M")
    except ValueError:
        return datetime.strptime(text, "%Y-%m-%d")


@pytest.fixture
def ctx():
    context = SimpleNamespace(
        project=None, tasks={}, resources={}, calendar_ids={},
        tab=None, root=None)
    yield context
    if context.root is not None:
        _shut_down(context.root)


# ------------------------------------------------------------------
# GIVEN - resources, their calendars, the plan
# ------------------------------------------------------------------

@given("a plan")
def a_plan(ctx):
    ctx.project = Project(name="T")
    ctx.counter = 0


def _resource(ctx, name, **overrides):
    fields = dict(id=f"r{len(ctx.resources) + 1}", name=name,
                  resource_type=ResourceType.NAMED, role_type="Dev")
    fields.update(overrides)
    resource = Resource(**fields)
    ctx.resources[name] = resource
    return resource


@given(parsers.parse('the resource "{name}" works a standard week'))
def a_standard_week_resource(ctx, name):
    _resource(ctx, name)


@given(parsers.parse('the resource "{name}" works the full week'))
def a_full_week_resource(ctx, name):
    _resource(ctx, name, schedule_pattern=SchedulePattern.FULL_WEEK)


@given(parsers.parse('the resource "{name}" never works'))
def a_never_working_resource(ctx, name):
    resource = _resource(ctx, name)
    resource.daily_capacity_hours = {
        day: 0.0 for day in resource.daily_capacity_hours}


@given(parsers.parse('"{name}" is off from "{start}" to "{end}"'))
def resource_is_off(ctx, name, start, end):
    ctx.resources[name].days_off.append(
        DaysOffRange(_day(start).date(), _day(end).date()))


def _add_task(ctx, name, start, end, duration=None):
    ctx.counter += 1
    task = Task.create_task(name, _day(start), _day(end),
                            task_id=f"T{ctx.counter}")
    if duration is not None:
        task.duration = duration
    ctx.project.add_task(task)
    ctx.tasks[name] = task
    return task


@given(parsers.parse('a task "{name}" running "{start}" to "{end}" '
                     'of {days:d} days'))
def a_task_of_days(ctx, name, start, end, days):
    _add_task(ctx, name, start, end, duration=days)


@given(parsers.parse('a task "{name}" running "{start}" to "{end}"'))
def a_task(ctx, name, start, end):
    _add_task(ctx, name, start, end)


@given(parsers.parse('a milestone "{name}" on "{date}"'))
def a_milestone(ctx, name, date):
    ctx.counter += 1
    task = Task.create_milestone(name, _day(date),
                                 task_id=f"T{ctx.counter}")
    ctx.project.add_task(task)
    ctx.tasks[name] = task


@given(parsers.parse('"{task}" is assigned to "{resource}"'))
def task_is_assigned(ctx, task, resource):
    person = ctx.resources[resource]
    ctx.project.resource_repository.add_resource(person)
    ctx.tasks[task].resource_assignments = [{"resource_id": person.id}]


@given(parsers.parse('"{task}" is assigned to both "{first}" '
                     'and "{second}"'))
def task_is_assigned_to_two(ctx, task, first, second):
    for name in (first, second):
        ctx.project.resource_repository.add_resource(
            ctx.resources[name])
    ctx.tasks[task].resource_assignments = [
        {"resource_id": ctx.resources[name].id}
        for name in (first, second)]


@given(parsers.parse('"{task}" is assigned to a resource nobody has'))
def task_is_assigned_to_a_ghost(ctx, task):
    ctx.tasks[task].resource_assignments = [{"resource_id": "ghost"}]


@given(parsers.parse('"{task}" is assigned to the material "{name}"'))
def task_is_assigned_a_material(ctx, task, name):
    ctx.tasks[task].resource_assignments = [
        {"resource_id": ctx.materials[name].id}]


@given(parsers.parse('"{task}" runs after "{predecessor}"'))
def task_runs_after(ctx, task, predecessor):
    ctx.tasks[task].dependencies.append(
        Dependency(task_id=ctx.tasks[predecessor].id))


@given(parsers.parse('the resource "{name}" works weekends only'))
def a_weekend_only_resource(ctx, name):
    _resource(ctx, name, schedule_pattern=SchedulePattern.WEEKEND_ONLY)


@given(parsers.parse('the material "{name}" exists'))
def a_material(ctx, name):
    if not hasattr(ctx, "materials"):
        ctx.materials = {}
    material = MaterialResource(id=f"m{len(ctx.materials) + 1}",
                                name=name)
    ctx.project.resource_repository.add_material(material)
    ctx.materials[name] = material


@given(parsers.parse('a calendar "{name}" that works "{date}"'))
def a_calendar_that_works(ctx, name, date):
    named = ctx.project.calendars.create(name)
    named.calendar.add_override(_day(date), is_working_day=True)
    ctx.calendar_ids[name] = named.id


@given(parsers.parse('"{task}" follows the "{calendar}" calendar'))
def task_follows_calendar(ctx, task, calendar):
    # A name the registry does not know is set as-is, so the dangling-id
    # fallback is exercised rather than sidestepped.
    ctx.tasks[task].calendar_id = ctx.calendar_ids.get(calendar,
                                                     calendar)


@given(parsers.parse('"{task}" ignores resource calendars'))
def task_ignores_resource_calendars(ctx, task):
    ctx.tasks[task].ignores_resource_calendars = True


# ------------------------------------------------------------------
# GIVEN - the Advanced tab (display)
# ------------------------------------------------------------------

def _open_tab(ctx, calendar_id=None):
    if not HAVE_DISPLAY:
        pytest.skip("no display")
    import customtkinter as ctk

    from gantt_app.views.advanced_tab import AdvancedTab
    ctx.root = ctk.CTk()
    ctx.root.withdraw()
    base = datetime(2026, 1, 5)
    task = Task(id="1", name="X", start_date=base,
                end_date=base + timedelta(days=3))
    if calendar_id is not None:
        task.calendar_id = calendar_id
    ctx.tab = AdvancedTab(ctx.root, task)


@given(parsers.parse('a task "{name}" is open on the Advanced tab'))
def a_task_on_the_advanced_tab(ctx, name):
    _open_tab(ctx)


@given(parsers.parse('a task "{name}" with a task calendar is open on '
                     'the Advanced tab'))
def a_calendared_task_on_the_advanced_tab(ctx, name):
    _open_tab(ctx, calendar_id="cal_x")


# ------------------------------------------------------------------
# WHEN - schedule, save, tick
# ------------------------------------------------------------------

@when("the work is scheduled")
def the_work_is_scheduled(ctx):
    ctx.project.apply_schedule()


@when(parsers.parse('"{task}" is saved and loaded again'))
def the_task_round_trips(ctx, task):
    ctx.tasks[task] = Task.from_dict(ctx.tasks[task].to_dict())


@given("the ignores-calendars box is ticked")
@when("the ignores-calendars box is ticked")
def the_box_is_ticked(ctx):
    ctx.tab.ignores_calendars_var.set(True)


@when("the ignores-calendars box is disabled")
def the_box_is_disabled(ctx):
    ctx.tab.set_ignores_calendars_enabled(False)


# ------------------------------------------------------------------
# THEN - who works, and where the dates land
# ------------------------------------------------------------------

@then(parsers.parse('"{name}" works on "{date}"'))
def resource_works_on(ctx, name, date):
    assert ctx.resources[name].works_on(_day(date).date())


@then(parsers.parse('"{name}" does not work on "{date}"'))
def resource_does_not_work_on(ctx, name, date):
    assert not ctx.resources[name].works_on(_day(date).date())


@then(parsers.parse('"{name}" does not work at "{moment}"'))
def resource_does_not_work_at(ctx, name, moment):
    assert not ctx.resources[name].works_on(_day(moment))


@then(parsers.parse('"{date}" is a working day for "{task}"'))
def is_a_working_day(ctx, date, task):
    assert ctx.project.calendar_for(ctx.tasks[task]) \
        .is_working_day(_day(date))


@then(parsers.parse('"{date}" is not a working day for "{task}"'))
def is_not_a_working_day(ctx, date, task):
    assert not ctx.project.calendar_for(ctx.tasks[task]) \
        .is_working_day(_day(date))


@then(parsers.parse('"{task}" starts on "{date}"'))
def task_starts_on(ctx, task, date):
    assert ctx.tasks[task].start_date.date() == _day(date).date()


@then(parsers.parse('"{task}" ends on "{date}"'))
def task_ends_on(ctx, task, date):
    assert ctx.tasks[task].end_date.date() == _day(date).date()


@then(parsers.parse('"{task}" does not ignore resource calendars'))
def does_not_ignore(ctx, task):
    assert not ctx.tasks[task].ignores_resource_calendars


@then("the loaded task ignores resource calendars")
def the_loaded_task_ignores(ctx):
    assert next(iter(ctx.tasks.values())).ignores_resource_calendars


# ------------------------------------------------------------------
# THEN - the checkbox
# ------------------------------------------------------------------

@then("the ignores-calendars box is unticked")
def the_box_is_unticked(ctx):
    assert not ctx.tab.ignores_calendars_var.get()


@then("the ignores-calendars box is disabled")
def the_box_is_disabled_check(ctx):
    assert str(ctx.tab.ignores_calendars_check.cget("state")) \
        == "disabled"


@then("the ignores-calendars box is enabled")
def the_box_is_enabled(ctx):
    assert str(ctx.tab.ignores_calendars_check.cget("state")) == "normal"


@then("the saved values ignore resource calendars")
def the_saved_values_ignore(ctx):
    assert ctx.tab.read_values()["ignores_resource_calendars"]


# ------------------------------------------------------------------
# THEN - the intersection walked backwards and measured
# ------------------------------------------------------------------

def _task_calendar(ctx, task):
    return ctx.project.calendar_for(ctx.tasks[task])


@then(parsers.parse('the "{task}" calendar looks back from "{date}" to '
                    '"{expected}"'))
def the_calendar_looks_back(ctx, task, date, expected):
    assert _task_calendar(ctx, task) \
        .get_previous_working_day(_day(date)) == _day(expected)


@then(parsers.parse('{count:d} working days back from "{date}" lands '
                    '"{task}" on "{expected}"'))
def working_days_back(ctx, count, date, task, expected):
    assert _task_calendar(ctx, task) \
        .subtract_working_days(_day(date), count) == _day(expected)


@then(parsers.parse('{count:d} working days forward from "{date}" lands '
                    '"{task}" on "{expected}"'))
def working_days_forward(ctx, count, date, task, expected):
    assert _task_calendar(ctx, task) \
        .add_working_days(_day(date), count) == _day(expected)


@then(parsers.parse('"{task}" counts {count:d} days worked between "{a}" '
                    'and "{b}"'))
def days_worked_between(ctx, task, count, a, b):
    assert _task_calendar(ctx, task) \
        .working_days_between(_day(a), _day(b)) == count


@then(parsers.parse('"{task}" measures {count:d} elapsed days between '
                    '"{a}" and "{b}"'))
def elapsed_days_between(ctx, task, count, a, b):
    assert _task_calendar(ctx, task) \
        .elapsed_days(_day(a), _day(b)) == count


@then(parsers.parse('"{task}" follows the plan\'s own calendar, not an '
                    'empty one'))
def the_never_worker_is_left_out(ctx, task):
    from gantt_app.core.workdaycalendar import IntersectingCalendar
    assert not isinstance(_task_calendar(ctx, task), IntersectingCalendar)


@then(parsers.parse('an intersection over "{name}" finds no working day '
                    'on or after "{date}"'))
def intersection_finds_none_after(ctx, name, date):
    from gantt_app.core.workdaycalendar import (
        IntersectingCalendar, WorkingCalendar)
    intersection = IntersectingCalendar(WorkingCalendar(),
                                        [ctx.resources[name]])
    assert intersection.get_next_working_day(_day(date)) == _day(date)


@then(parsers.parse('an intersection over "{name}" finds no working day '
                    'on or before "{date}"'))
def intersection_finds_none_before(ctx, name, date):
    from gantt_app.core.workdaycalendar import (
        IntersectingCalendar, WorkingCalendar)
    intersection = IntersectingCalendar(WorkingCalendar(),
                                        [ctx.resources[name]])
    assert intersection.get_previous_working_day(_day(date)) == _day(date)
