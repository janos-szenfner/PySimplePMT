"""
pytest-bdd cover for the dependency scheduling engine (no display needed).

Adapted from dependency-gherkin.txt and the dependency outlines in the
advanced-engine Gherkin. These pin the behaviour the Advanced tab must not
disturb: link types, lag in working days, multiple driving predecessors and
circular-link refusal. Dates are checked against the engine's own working-day
arithmetic rather than fixed timestamps, so a change in seed dates cannot make
the rule read differently.
"""
from datetime import datetime, timedelta

from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.models import Project, Task

scenarios("features/dependency_links.feature")


def _day(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%d")


@given(parsers.parse('a project scheduled from "{start}"'),
       target_fixture="plan")
def a_project(start):
    return {"project": Project(name="Dep"), "base": _day(start)}


def _add(plan, name, days):
    """A task of the given working-day length, seeded on the calendar."""
    project = plan["project"]
    base = plan["base"]
    end = project.calendar.add_working_days(base, days - 1)
    task = Task(id=name, name=name, start_date=base, end_date=end)
    project.add_task(task)
    return task


@given(parsers.re(r'task "(?P<a>[^"]+)" of (?P<da>\d+) working days and task '
                  r'"(?P<b>[^"]+)" of (?P<db>\d+) working days$'))
def two_tasks(plan, a, da, b, db):
    _add(plan, a, int(da))
    _add(plan, b, int(db))


@given(parsers.re(r'task "(?P<name>[^"]+)" of (?P<days>\d+) working days$'))
def one_task(plan, name, days):
    _add(plan, name, int(days))


@given(parsers.re(r'"(?P<succ>[^"]+)" has a "(?P<link>[^"]+)" link to '
                  r'"(?P<pred>[^"]+)"$'))
def link_plain(plan, succ, link, pred):
    plan["project"].get_task_by_id(succ).add_dependency(pred, dep_type=link)


@given(parsers.re(r'"(?P<succ>[^"]+)" has a "(?P<link>[^"]+)" link to '
                  r'"(?P<pred>[^"]+)" with lag (?P<lag>\d+)$'))
def link_lag(plan, succ, link, pred, lag):
    plan["project"].get_task_by_id(succ).add_dependency(
        pred, dep_type=link, lag=int(lag))


@when("the plan is rescheduled")
def reschedule(plan):
    plan["project"].reschedule(forward_only=False)


@when(parsers.parse('"{name}" grows to {days:d} working days'))
def grow(plan, name, days):
    task = plan["project"].get_task_by_id(name)
    task.end_date = plan["project"].calendar.add_working_days(
        task.start_date, days - 1)


def _task(plan, name):
    return plan["project"].get_task_by_id(name)


def _fs_floor(cal, predecessor):
    """Where a Finish-to-Start successor may start: the working day after."""
    return cal.get_next_working_day(predecessor.end_date + timedelta(days=1))


@then('"B" starts the working day after "A" finishes')
def b_starts_after_a(plan):
    cal = plan["project"].calendar
    a, b = _task(plan, "A"), _task(plan, "B")
    assert b.start_date.date() == _fs_floor(cal, a).date()


@then("\"B\" starts when A starts")
def b_ss(plan):
    assert _task(plan, "B").start_date.date() == _task(plan, "A").start_date.date()


@then("\"B\" finishes when A finishes")
def b_ff(plan):
    assert _task(plan, "B").end_date.date() == _task(plan, "A").end_date.date()


@then("\"B\" finishes when A starts")
def b_sf(plan):
    assert _task(plan, "B").end_date.date() == _task(plan, "A").start_date.date()


@then("\"B\" starts 2 working days after the day it would start unlagged")
def b_fs_lag(plan):
    cal = plan["project"].calendar
    a, b = _task(plan, "A"), _task(plan, "B")
    unlagged = _fs_floor(cal, a)
    # The lag is measured in working days: the lagged start is two working
    # days past where an unlagged link would have put it. working_days_between
    # counts both ends, so a two-day gap reads as a span of three.
    assert b.start_date > unlagged
    assert cal.working_days_between(unlagged, b.start_date) - 1 == 2


@then("\"C\" starts at the later of its two link floors")
def c_later_floor(plan):
    cal = plan["project"].calendar
    a, b, c = _task(plan, "A"), _task(plan, "B"), _task(plan, "C")
    fs_floor = _fs_floor(cal, a)
    ss_floor = cal.add_working_days(b.start_date, 2)
    assert c.start_date.date() == max(fs_floor, ss_floor).date()


@then(parsers.parse('making "{succ}" wait for "{pred}" would be circular'))
def would_be_circular(plan, succ, pred):
    assert plan["project"].would_create_dependency_cycle(succ, pred) is True


@then(parsers.parse('"{name}" still has exactly one link'))
def one_link(plan, name):
    assert len(_task(plan, name).dependencies) == 1
