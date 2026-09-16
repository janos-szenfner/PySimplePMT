"""
pytest-bdd tests for SNLT/FNLT conflict detection and resolution (issue #28).

Run with:
    python3 -m pytest tests/test_snlt_conflict_bdd.py -q

Converted from test_snlt_conflict.py - every case carried over.
"""
from datetime import datetime
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Dependency, Project, Task

pytestmark = [
    pytest.mark.snlt_conflict,
]

scenarios("features/snlt_conflict.feature")


def _date(text):
    return datetime.strptime(text, "%Y-%m-%d")


# ------------------------------------------------------------------
# GIVEN
# ------------------------------------------------------------------

@given(parsers.parse("a plan starting {start}"), target_fixture="ctx")
def a_plan_starting(start):
    return SimpleNamespace(
        project=Project(name="P", start_date=_date(start)))


@given(parsers.parse('task "{task_id}" from {start} to {end} constrained '
                     '"{ctype}" to {cdate}'))
def a_constrained_task(ctx, task_id, start, end, ctype, cdate):
    task = Task(id=task_id, name=task_id, start_date=_date(start),
                end_date=_date(end), constraint_type=ctype,
                constraint_date=_date(cdate))
    ctx.project.add_task(task)


@given(parsers.parse('task "{task_id}" from {start} constrained "{ctype}" '
                     'to {cdate}'))
def a_constrained_task_no_end(ctx, task_id, start, ctype, cdate):
    task = Task(id=task_id, name=task_id, start_date=_date(start),
                constraint_type=ctype, constraint_date=_date(cdate))
    ctx.project.add_task(task)


@given(parsers.parse('a phase "{phase_id}" from {start} to {end}'))
def a_phase(ctx, phase_id, start, end):
    ctx.project.add_task(Task(id=phase_id, name="Phase",
                              start_date=_date(start), end_date=_date(end),
                              task_type="Phase"))


@given(parsers.parse('task "{task_id}" under "{parent}" from {start} to '
                     '{end} constrained "{ctype}" to {cdate}'))
def a_child_constrained_task(ctx, task_id, parent, start, end, ctype, cdate):
    task = Task(id=task_id, name=task_id, start_date=_date(start),
                end_date=_date(end), parent_task_id=parent,
                constraint_type=ctype, constraint_date=_date(cdate))
    ctx.project.add_task(task)


@given(parsers.parse('a linked plan where "{task_id}" is constrained '
                     '"{ctype}" to {cdate}'), target_fixture="ctx")
def a_linked_plan(task_id, ctype, cdate):
    p = Project(name="P", start_date=datetime(2026, 10, 1))
    p.add_task(Task(id="A", name="A", start_date=datetime(2026, 10, 1),
                    end_date=datetime(2026, 10, 7)))
    b = Task(id="B", name="B", start_date=datetime(2026, 10, 8),
             end_date=datetime(2026, 10, 9),
             dependencies=[Dependency(task_id="A", dep_type="FS",
                                      hardness="Hard")])
    p.add_task(b)
    p.reschedule()
    b.constraint_type = ctype
    b.constraint_date = _date(cdate)
    return SimpleNamespace(project=p)


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------

@when(parsers.parse('the meeting dates are asked for task "{task_id}"'))
def the_meeting_dates_are_asked(ctx, task_id):
    task = ctx.project.get_task_by_id(task_id)
    ctx.meeting = ctx.project.dates_meeting_constraint(task)


@when(parsers.parse('the predecessors of "{task_id}" are removed and the '
                    'meeting dates applied'))
def the_predecessors_are_removed(ctx, task_id):
    task = ctx.project.get_task_by_id(task_id)
    start, end = ctx.project.dates_meeting_constraint(task)
    task.dependencies = []
    if start is not None:
        task.start_date, task.end_date = start, end
    ctx.project.apply_schedule()


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@given(parsers.parse('task "{task_id}" reports a constraint conflict'))
@then(parsers.parse('task "{task_id}" reports a constraint conflict'))
def task_reports_a_conflict(ctx, task_id):
    task = ctx.project.get_task_by_id(task_id)
    assert ctx.project.constraint_conflict(task) is not None


@then(parsers.parse('task "{task_id}" reports no constraint conflict'))
def task_reports_no_conflict(ctx, task_id):
    task = ctx.project.get_task_by_id(task_id)
    assert ctx.project.constraint_conflict(task) is None


@then(parsers.parse('task "{task_id}" is among the conflicts'))
def task_is_among_the_conflicts(ctx, task_id):
    assert task_id in ctx.project.tasks_in_conflict()


@then(parsers.parse("the meeting start is {date}"))
def the_meeting_start_is(ctx, date):
    start, _end = ctx.meeting
    assert start == _date(date)


@then(parsers.parse("the meeting end is {date}"))
def the_meeting_end_is(ctx, date):
    _start, end = ctx.meeting
    assert end == _date(date)


@then("there are no meeting dates")
def there_are_no_meeting_dates(ctx):
    assert ctx.meeting == (None, None)


@then(parsers.parse('task "{task_id}" has no dependencies'))
def task_has_no_dependencies(ctx, task_id):
    assert ctx.project.get_task_by_id(task_id).dependencies == []


@then(parsers.parse('task "{task_id}" starts on {date}'))
def task_starts_on(ctx, task_id, date):
    assert ctx.project.get_task_by_id(task_id).start_date == _date(date)


@then(parsers.parse('task "{task_id}" ends on {date}'))
def task_ends_on(ctx, task_id, date):
    assert ctx.project.get_task_by_id(task_id).end_date == _date(date)
