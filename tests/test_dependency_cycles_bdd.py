"""
pytest-bdd tests for circular links through the roll-up, and links
obeyed when they are typed (issue #47).

Run with:
    python3 -m pytest tests/test_dependency_cycles_bdd.py -q

Model-level, no display needed. Converted from
test_dependency_cycles.py - every case carried over.
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Dependency, Project, Task

pytestmark = [
    pytest.mark.dependency_cycles,
]

scenarios("features/dependency_cycles.feature")

BASE = datetime(2026, 9, 14)  # a Monday


def _task(id, name, start, end, dur=None, parent=None, deps=None):
    """A subtask-shaped row, the shape the report's plan was built from."""
    return Task(id=id, name=name, start_date=start, end_date=end,
                task_type="Subtask", parent_task_id=parent, duration=dur,
                dependencies=[Dependency(x, dep_type, "Hard")
                              for x, dep_type in (deps or [])])


def _plan():
    """
    The report's plan, simplified.

    A phase holds a summary, the summary holds the linked leaf, and a
    chain hangs off the phase - so a link from the leaf to anywhere on
    the chain runs in a circle through the roll-up, whatever the type.
    """
    p = Project(name="P", start_date=datetime(2026, 9, 7))
    p.add_task(Task(id="P1", name="Phase", task_type="Phase",
                    start_date=datetime(2026, 9, 7),
                    end_date=datetime(2026, 11, 27)))
    p.add_task(_task("M", "Mockups", datetime(2026, 9, 11),
                     datetime(2026, 9, 11), dur=1, parent="P1"))
    p.add_task(_task("UX", "UX planning", BASE, datetime(2026, 11, 27),
                     parent="P1", deps=[("M", "FS")]))
    p.add_task(_task("F1", "feature1", BASE, datetime(2026, 10, 23),
                     dur=30, parent="UX"))
    p.add_task(_task("F3", "feature3", BASE, datetime(2026, 10, 23),
                     dur=30, parent="UX"))
    p.add_task(_task("F2", "feature2", datetime(2026, 10, 26),
                     datetime(2026, 11, 23), dur=21, parent="UX",
                     deps=[("F3", "FS")]))
    start = datetime(2026, 11, 30)
    for tid, dep in (("I", "P1"), ("DR", "I"), ("T3", "DR"),
                     ("TE", "T3"), ("DE", "TE")):
        end = start + timedelta(days=13)
        p.add_task(Task(id=tid, name=tid, start_date=start, end_date=end,
                        duration=10,
                        dependencies=[Dependency(dep, "FS", "Hard")]))
        start = end + timedelta(days=3)
    return p


# ------------------------------------------------------------------
# GIVEN
# ------------------------------------------------------------------

@given("the reported plan", target_fixture="ctx")
def the_reported_plan():
    return SimpleNamespace(p=_plan())


@given("a summary whose child waits on the leaf", target_fixture="ctx")
def a_summary_whose_child_waits_on_the_leaf():
    p = Project(name="Loop", start_date=BASE)
    p.add_task(Task(id="L", name="Leaf", start_date=BASE,
                    end_date=datetime(2026, 9, 16)))
    p.add_task(Task(id="S", name="Summary", task_type="Phase",
                    start_date=BASE, end_date=datetime(2026, 9, 25)))
    p.add_task(_task("C", "Child", BASE, datetime(2026, 9, 16),
                     parent="S", deps=[("L", "FS")]))
    return SimpleNamespace(p=p)


@given("the reported plan settled with F2 after F3", target_fixture="ctx")
def the_reported_plan_settled():
    """feature2 sits after feature3, waiting on it Finish-to-Start."""
    p = _plan()
    p.reschedule()
    return SimpleNamespace(p=p, f2=p.get_task_by_id("F2"),
                           f3=p.get_task_by_id("F3"))


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------

@when(parsers.parse('"{task_id}" is typed the number of "{other_id}"'))
def typed_the_number(ctx, task_id, other_id):
    number = ctx.p.display_ids()[other_id]
    ctx.links, ctx.errors = ctx.p.parse_dependencies(task_id,
                                                     str(number))


@when(parsers.parse('"{task_id}" is typed the number of "{other_id}" '
                    'with type "{dep_type}"'))
def typed_the_number_with_type(ctx, task_id, other_id, dep_type):
    number = ctx.p.display_ids()[other_id]
    ctx.links, ctx.errors = ctx.p.parse_dependencies(
        task_id, f"{number}{dep_type}")


@when("the plan is settled")
def the_plan_is_settled(ctx):
    ctx.changed = ctx.p.reschedule()


@when(parsers.parse('"{task_id}" is given a Hard "{dep_type}" link to '
                    '"{other_id}" and settled by the edit'))
def given_a_link_and_settled_by_the_edit(ctx, task_id, dep_type, other_id):
    """What set_dependencies does with a cell that was just typed."""
    ctx.f2.dependencies = [Dependency(other_id, dep_type, "Hard")]
    ctx.p.apply_schedule(forward_only=False)


@when(parsers.parse('"{task_id}" is moved to {start} to {end} with a '
                    'Rubber "{dep_type}" link to "{other_id}"'))
def moved_with_a_rubber_link(ctx, task_id, start, end, dep_type, other_id):
    ctx.f2.start_date = datetime.strptime(start, "%Y-%m-%d")
    ctx.f2.end_date = datetime.strptime(end, "%Y-%m-%d")
    ctx.f2.dependencies = [Dependency(other_id, dep_type, "Rubber")]


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@then(parsers.parse('"{task_id}" waiting on "{other_id}" would close a '
                    'circle'))
def waiting_would_close_a_circle(ctx, task_id, other_id):
    assert ctx.p.would_create_dependency_cycle(task_id, other_id)


@then(parsers.parse('"{task_id}" waiting on "{other_id}" would not close '
                    'a circle'))
def waiting_would_not_close_a_circle(ctx, task_id, other_id):
    assert not ctx.p.would_create_dependency_cycle(task_id, other_id)


@then(parsers.parse('no links were parsed and the error says "{text}"'))
def no_links_and_the_error_says(ctx, text):
    assert ctx.links == []
    assert text in ctx.errors[0]


@then(parsers.parse('"{task_id}" covers fewer than {days:d} working days'))
def covers_fewer_working_days(ctx, task_id, days):
    task = ctx.p.get_task_by_id(task_id)
    assert ctx.p.calendar.working_days_between(task.start_date,
                                             task.end_date) < days


@then("settling again changes nothing")
def settling_again_changes_nothing(ctx):
    assert not ctx.p.reschedule()


@then(parsers.parse('"{task_id}" starts where "{other_id}" starts'))
def starts_where_other_starts(ctx, task_id, other_id):
    assert ctx.f2.start_date.date() == ctx.f3.start_date.date()


@then(parsers.parse('"{task_id}" ends where "{other_id}" ends'))
def ends_where_other_ends(ctx, task_id, other_id):
    assert ctx.f2.end_date.date() == ctx.f3.end_date.date()


@then(parsers.parse('"{task_id}" ends where "{other_id}" starts'))
def ends_where_other_starts(ctx, task_id, other_id):
    assert ctx.f2.end_date.date() == ctx.f3.start_date.date()


@then(parsers.parse('"{task_id}" still starts {date}'))
def still_starts(ctx, task_id, date):
    assert ctx.f2.start_date == datetime.strptime(date, "%Y-%m-%d")
