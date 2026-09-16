"""
pytest-bdd tests for a dependency on a collection row (issue #25).

Run with:
    python3 -m pytest tests/test_collection_dependency_bdd.py -q

Converted from test_collection_dependency.py - every case carried
over.
"""
import logging
from datetime import datetime
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Dependency, Project, Task

pytestmark = [
    pytest.mark.collection_dependency,
]

scenarios("features/collection_dependency.feature")

BASE = datetime(2026, 9, 14)  # a Monday


def _child(id, name, parent, start, end, dur=None, deps=None):
    return Task(id=id, name=name, start_date=start, end_date=end,
                task_type="Subtask", parent_task_id=parent, duration=dur,
                dependencies=[Dependency(task_id=x, dep_type="FS",
                                         hardness="Hard")
                              for x in (deps or [])])


def _task(id, start, end, **kwargs):
    return Task(id=id, name=id, start_date=start, end_date=end, **kwargs)


# ------------------------------------------------------------------
# GIVEN
# ------------------------------------------------------------------

@given("a task-typed parent of 10 stored days with two children",
       target_fixture="ctx")
def a_task_typed_parent_with_children():
    p = Project(name="Conv", start_date=datetime(2026, 9, 7))
    p.add_task(_task("P", BASE, datetime(2026, 9, 25), task_type="Task",
                     duration=10))
    p.add_task(_child("A", "A", "P", BASE, datetime(2026, 9, 16), dur=3))
    p.add_task(_child("B", "B", "P", datetime(2026, 9, 21),
                      datetime(2026, 9, 25), dur=5))
    return SimpleNamespace(project=p)


@given("the collection plan waiting on UI Mockups", target_fixture="ctx")
def the_collection_plan_waiting_on_mockups():
    p = Project(name="Coll", start_date=datetime(2026, 9, 7))
    # UI Mockups ends Friday 09-11; the collection waits for it.
    p.add_task(_task("M", datetime(2026, 9, 11), datetime(2026, 9, 11)))
    p.add_task(_task("UX", BASE, datetime(2026, 9, 28), task_type="Subtask",
                     dependencies=[Dependency(task_id="M", dep_type="FS",
                                              hardness="Hard")]))
    # feature1 sits at the collection start; feature3 later with no
    # link; feature2 waits for feature3.
    p.add_task(_child("F1", "feature1", "UX", BASE,
                      datetime(2026, 9, 16), dur=3))
    p.add_task(_child("F3", "feature3", "UX", datetime(2026, 9, 21),
                      datetime(2026, 9, 25), dur=5))
    p.add_task(_child("F2", "feature2", "UX", datetime(2026, 9, 28),
                      datetime(2026, 9, 28), dur=1, deps=["F3"]))
    p.reschedule()
    return SimpleNamespace(project=p)


@given("a free collection with children X and Y", target_fixture="ctx")
def a_free_collection_with_children():
    p = Project(name="Free", start_date=datetime(2026, 9, 7))
    p.add_task(_task("G", BASE, datetime(2026, 9, 25), task_type="Subtask"))
    p.add_task(_child("X", "X", "G", BASE, datetime(2026, 9, 16), dur=3))
    p.add_task(_child("Y", "Y", "G", datetime(2026, 9, 21),
                      datetime(2026, 9, 25), dur=5))
    p.reschedule()
    return SimpleNamespace(project=p)


@given(parsers.parse("a lone top-level task from {start}"),
       target_fixture="ctx")
def a_lone_top_level_task(start):
    p = Project(name="Top", start_date=datetime(2026, 9, 7))
    p.add_task(_task("T", datetime.strptime(start, "%Y-%m-%d"),
                     datetime(2026, 9, 25)))
    p.reschedule()
    return SimpleNamespace(project=p)


@given("a nested plan with an outer and an inner constrained ancestor",
       target_fixture="ctx")
def a_nested_plan_with_two_ancestors():
    p = Project(name="Nested", start_date=datetime(2026, 9, 7))
    p.add_task(_task("M", datetime(2026, 9, 11), datetime(2026, 9, 11)))
    p.add_task(_task("G", datetime(2026, 9, 18), datetime(2026, 9, 18)))
    p.add_task(_task("OUT", BASE, datetime(2026, 9, 28),
                     task_type="Subtask",
                     dependencies=[Dependency(task_id="M", dep_type="FS",
                                              hardness="Hard")]))
    p.add_task(_task("IN", datetime(2026, 9, 21), datetime(2026, 9, 28),
                     task_type="Subtask", parent_task_id="OUT",
                     dependencies=[Dependency(task_id="G", dep_type="FS",
                                              hardness="Hard")]))
    p.add_task(_child("K", "K", "IN", datetime(2026, 9, 25),
                      datetime(2026, 9, 28), dur=2))
    p.reschedule()
    return SimpleNamespace(project=p)


@given("the plan is rescheduled")
def the_plan_is_rescheduled(ctx):
    ctx.project.reschedule()


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------

@when("the plan is rescheduled under logging")
def the_plan_is_rescheduled_under_logging(ctx, caplog):
    with caplog.at_level(logging.WARNING, logger='gantt_app.core.models'):
        ctx.project.reschedule()
    ctx.caplog = caplog


@when("the plan is scheduled again")
def the_plan_is_scheduled_again(ctx):
    ctx.moved = ctx.project.reschedule()


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@then(parsers.parse('no "{fragment}" warning was logged'))
def no_warning_was_logged(ctx, fragment):
    messages = [r.message for r in ctx.caplog.records]
    assert not [m for m in messages if fragment in m]


@then("the reschedule reports nothing moved")
def the_reschedule_reports_nothing_moved(ctx):
    assert ctx.moved is False


@then(parsers.parse('task "{task_id}" starts when task "{other}" starts'))
def task_starts_when_other_starts(ctx, task_id, other):
    task = ctx.project.get_task_by_id(task_id)
    anchor = ctx.project.get_task_by_id(other)
    assert task.start_date == anchor.start_date


@then(parsers.parse('task "{task_id}" starts on {date}'))
def task_starts_on(ctx, task_id, date):
    task = ctx.project.get_task_by_id(task_id)
    assert task.start_date == datetime.strptime(date, "%Y-%m-%d")


@then(parsers.parse('task "{task_id}" spans tasks "{csv}"'))
def task_spans_children(ctx, task_id, csv):
    parent = ctx.project.get_task_by_id(task_id)
    kids = [ctx.project.get_task_by_id(i) for i in csv.split(",")]
    assert parent.start_date == min(k.start_date for k in kids)
    assert parent.end_date == max(k.end_date for k in kids)


@then(parsers.parse('task "{task_id}" does not start when task "{other}" '
                    'starts'))
def task_does_not_start_when_other_starts(ctx, task_id, other):
    task = ctx.project.get_task_by_id(task_id)
    anchor = ctx.project.get_task_by_id(other)
    assert task.start_date != anchor.start_date


@then(parsers.parse('task "{task_id}" still starts on {date}'))
def task_still_starts_on(ctx, task_id, date):
    task = ctx.project.get_task_by_id(task_id)
    assert task.start_date == datetime.strptime(date, "%Y-%m-%d")
