"""
pytest-bdd tests for As Late As Possible scheduling (issue #26).

Run with:
    python3 -m pytest tests/test_alap_bdd.py -q

Converted from test_alap.py - every case carried over.
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Dependency, Project, Task

pytestmark = [
    pytest.mark.alap,
]

scenarios("features/alap.feature")


def _sub(id, name, parent, start, end, dur=None, ctype='NA', deps=None):
    return Task(id=id, name=name, start_date=start, end_date=end,
                task_type="Subtask", parent_task_id=parent, duration=dur,
                constraint_type=ctype,
                dependencies=[Dependency(task_id=x, dep_type="FS",
                                         hardness="Hard")
                              for x in (deps or [])])


# ------------------------------------------------------------------
# GIVEN - the plans
# ------------------------------------------------------------------

@given("the ALAP plan under a summary", target_fixture="ctx")
def the_alap_plan_under_a_summary():
    p = Project(name="P", start_date=datetime(2026, 9, 7))
    p.add_task(Task(id="S", name="Phase", start_date=datetime(2026, 9, 14),
                    end_date=datetime(2026, 9, 28), task_type="Subtask"))
    p.add_task(_sub("A", "feature1", "S", datetime(2026, 9, 14),
                    datetime(2026, 9, 16), dur=3, ctype='ALAP'))
    p.add_task(_sub("B", "feature3", "S", datetime(2026, 9, 21),
                    datetime(2026, 9, 25), dur=5, ctype='ALAP'))
    p.add_task(_sub("C", "feature2", "S", datetime(2026, 9, 28),
                    datetime(2026, 9, 28), dur=1, deps=["B"]))
    p.reschedule()
    return SimpleNamespace(project=p)


@given("a summary with a predecessor and an ALAP child",
       target_fixture="ctx")
def a_summary_with_a_predecessor_and_an_alap_child():
    p = Project(name="P", start_date=datetime(2026, 9, 7))
    p.add_task(Task(id="M", name="Mock", start_date=datetime(2026, 9, 11),
                    end_date=datetime(2026, 9, 11)))
    p.add_task(Task(id="S", name="Phase", start_date=datetime(2026, 9, 14),
                    end_date=datetime(2026, 9, 28), task_type="Subtask",
                    dependencies=[Dependency(task_id="M", dep_type="FS",
                                             hardness="Hard")]))
    p.add_task(_sub("A", "feature1", "S", datetime(2026, 9, 14),
                    datetime(2026, 9, 16), dur=3, ctype='ALAP'))
    p.add_task(_sub("C", "feature2", "S", datetime(2026, 9, 28),
                    datetime(2026, 9, 28), dur=1))
    p.reschedule()
    return SimpleNamespace(project=p)


@given("a summary whose last child is ALAP", target_fixture="ctx")
def a_summary_whose_last_child_is_alap():
    p = Project(name="P", start_date=datetime(2026, 9, 7))
    p.add_task(Task(id="S", name="Phase", start_date=datetime(2026, 9, 14),
                    end_date=datetime(2026, 9, 25), task_type="Subtask"))
    p.add_task(_sub("A", "early", "S", datetime(2026, 9, 14),
                    datetime(2026, 9, 16), dur=3))
    p.add_task(_sub("B", "late", "S", datetime(2026, 9, 21),
                    datetime(2026, 9, 25), dur=5, ctype='ALAP'))
    p.reschedule()
    return SimpleNamespace(project=p)


@given(parsers.parse("a top-level ALAP task from {start} for {days:d} days"),
       target_fixture="ctx")
def a_top_level_alap_task(start, days):
    start = datetime.strptime(start, "%Y-%m-%d")
    p = Project(name="P", start_date=datetime(2026, 9, 7))
    p.add_task(Task(id="T", name="T", start_date=start,
                    end_date=start + timedelta(days=2), duration=days,
                    constraint_type='ALAP'))
    p.reschedule()
    return SimpleNamespace(project=p)


@given("a summary holding work and an ALAP milestone", target_fixture="ctx")
def a_summary_holding_work_and_an_alap_milestone():
    p = Project(name="P", start_date=datetime(2026, 9, 7))
    p.add_task(Task(id="S", name="Phase", start_date=datetime(2026, 9, 14),
                    end_date=datetime(2026, 9, 25), task_type="Subtask"))
    p.add_task(_sub("A", "work", "S", datetime(2026, 9, 14),
                    datetime(2026, 9, 25), dur=9))
    p.add_task(Task(id="MS", name="gate", start_date=datetime(2026, 9, 14),
                    task_type="Milestone", parent_task_id="S",
                    constraint_type='ALAP'))
    p.reschedule()
    return SimpleNamespace(project=p)


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------

@when("the plan is scheduled again")
def the_plan_is_scheduled_again(ctx):
    ctx.moved = ctx.project.reschedule()


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@then(parsers.parse('task "{task_id}" ends level with its summary'))
def task_ends_level_with_its_summary(ctx, task_id):
    task = ctx.project.get_task_by_id(task_id)
    summary = ctx.project.get_task_by_id("S")
    assert task.end_date == summary.end_date


@then(parsers.parse('task "{task_id}" ends the working day before task '
                    '"{other_id}" starts'))
def task_ends_the_working_day_before(ctx, task_id, other_id):
    task = ctx.project.get_task_by_id(task_id)
    other = ctx.project.get_task_by_id(other_id)
    assert task.end_date < other.start_date
    # As late as it can be: the working day before the sibling starts.
    assert task.end_date == ctx.project.calendar.get_previous_working_day(
        other.start_date - timedelta(days=1))


@then(parsers.parse('task "{task_id}" still takes {days:d} working days'))
def task_still_takes_working_days(ctx, task_id, days):
    task = ctx.project.get_task_by_id(task_id)
    assert ctx.project.working_duration(task) == days


@then("the reschedule reports nothing moved")
def the_reschedule_reports_nothing_moved(ctx):
    assert ctx.moved is False


@then(parsers.parse('task "{task_id}" starts after {date}'))
def task_starts_after(ctx, task_id, date):
    task = ctx.project.get_task_by_id(task_id)
    assert task.start_date > datetime.strptime(date, "%Y-%m-%d")


@then(parsers.parse('task "{task_id}" still ends on {date}'))
def task_still_ends_on(ctx, task_id, date):
    task = ctx.project.get_task_by_id(task_id)
    assert task.end_date == datetime.strptime(date, "%Y-%m-%d")


@then(parsers.parse('task "{task_id}" still starts on {date}'))
def task_still_starts_on(ctx, task_id, date):
    task = ctx.project.get_task_by_id(task_id)
    assert task.start_date == datetime.strptime(date, "%Y-%m-%d")


@then(parsers.parse("the milestone starts after {date}"))
def the_milestone_starts_after(ctx, date):
    moved = ctx.project.get_task_by_id("MS").start_date
    assert moved > datetime.strptime(date, "%Y-%m-%d")


@then("the milestone sits at its summary's end")
def the_milestone_sits_at_its_summarys_end(ctx):
    moved = ctx.project.get_task_by_id("MS").start_date
    assert moved == ctx.project.get_task_by_id("S").end_date
