"""
pytest-bdd tests for editing start, end and duration (issues #23, #31).

Run with:
    python3 -m pytest tests/test_schedule_editing_bdd.py -q

The reconcile scenarios are model-only; the grid ones skip without a
display. Converted from test_schedule_editing.py - every case carried
over.
"""
from datetime import datetime
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Project, Task

pytestmark = [
    pytest.mark.schedule_editing,
]

scenarios("features/schedule_editing.feature")


def _d(text):
    return datetime.strptime(text, "%Y-%m-%d")


def _display_available() -> bool:
    try:
        import tkinter
        root = tkinter.Tk()
    except Exception:
        return False
    root.destroy()
    return True


HAVE_DISPLAY = _display_available()


def _shut_down(root) -> None:
    """Take a root down, children first, without raising."""
    try:
        for child in list(root.children.values()):
            try:
                child.destroy()
            except Exception:
                pass
        root.destroy()
    except Exception:
        pass


def _project():
    p = Project(name="P", start_date=datetime(2026, 10, 1))
    task = Task(id="T", name="T", start_date=datetime(2026, 10, 5),
                end_date=datetime(2026, 10, 9), duration=5)
    p.add_task(task)
    return p, task


# ------------------------------------------------------------------
# GIVEN
# ------------------------------------------------------------------

@given(parsers.parse("a task from {start} to {end} for {days:d} days"),
       target_fixture="ctx")
def a_task(start, end, days):
    project, task = _project()
    return SimpleNamespace(project=project, task=task)


@given(parsers.parse("a milestone on {date}"), target_fixture="ctx")
def a_milestone(date):
    p = Project(name="P", start_date=datetime(2026, 10, 1))
    m = Task(id="M", name="M", start_date=_d(date), task_type="Milestone")
    p.add_task(m)
    return SimpleNamespace(project=p, task=m)


@given("a task list over the five-day task", target_fixture="ctx")
def a_task_list_over_the_task():
    if not HAVE_DISPLAY:
        pytest.skip("needs a display")
    import customtkinter as ctk
    from gantt_app.utils.undoredo import (
        ProjectStateTracker, UndoRedoManager,
    )
    from gantt_app.views.task_list import DragDropTaskList

    root = ctk.CTk()
    root.withdraw()
    project, task = _project()
    tracker = ProjectStateTracker(project, UndoRedoManager())
    view = DragDropTaskList(root, project, project_tracker=tracker)
    view.update_task_list()

    yield SimpleNamespace(root=root, project=project, task=task,
                          view=view, tracker=tracker)

    _shut_down(root)


@given(parsers.parse('a phase "{phase_id}" holding task "{task_id}"'))
def a_phase_holding_the_task(ctx, phase_id, task_id):
    ctx.project.add_task(Task(id=phase_id, name="Phase", task_type="Phase",
                              start_date=datetime(2026, 10, 5),
                              end_date=datetime(2026, 10, 9)))
    ctx.project.get_task_by_id(task_id).parent_task_id = phase_id


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------

@when(parsers.parse("the schedule is reconciled with duration {days:d}"))
def reconciled_with_duration(ctx, days):
    t = ctx.task
    ctx.result = ctx.project.reconcile_schedule(
        t, t.start_date, t.end_date, days)


@when(parsers.parse("the schedule is reconciled with end {end}"))
def reconciled_with_end(ctx, end):
    t = ctx.task
    ctx.result = ctx.project.reconcile_schedule(
        t, t.start_date, _d(end), t.duration)


@when(parsers.parse("the schedule is reconciled with start {start}"))
def reconciled_with_start(ctx, start):
    t = ctx.task
    ctx.result = ctx.project.reconcile_schedule(
        t, _d(start), t.end_date, t.duration)


@when("the schedule is reconciled unchanged")
def reconciled_unchanged(ctx):
    t = ctx.task
    ctx.result = ctx.project.reconcile_schedule(
        t, t.start_date, t.end_date, 5)


@when(parsers.parse("the schedule is reconciled with start {start} and "
                    "end {end}"))
def reconciled_with_start_and_end(ctx, start, end):
    t = ctx.task
    ctx.result = ctx.project.reconcile_schedule(
        t, _d(start), _d(end), 5)


@when(parsers.parse("the milestone is reconciled to start {start}"))
def the_milestone_is_reconciled(ctx, start):
    ctx.result = ctx.project.reconcile_schedule(
        ctx.task, _d(start), None, None)


@when(parsers.parse("the grid sets duration {days:d} and end {end}"))
def the_grid_sets_duration(ctx, days, end):
    ctx.view.set_schedule("T", ctx.task.start_date, _d(end), days, None)


@when(parsers.parse("the grid sets start {start} with a floor"))
def the_grid_sets_start(ctx, start):
    ctx.view.set_schedule("T", _d(start), ctx.task.end_date, 3, _d(start))


@when("the edit is undone")
def the_edit_is_undone(ctx):
    ctx.tracker.manager.undo()


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@then(parsers.parse("the reconciled start is {date}"))
def the_reconciled_start_is(ctx, date):
    assert ctx.result[0] == _d(date)


@then("the reconciled end is empty")
def the_reconciled_end_is_empty(ctx):
    assert ctx.result[1] is None


@then(parsers.re(r"the reconciled end is (?P<date>\d{4}-\d{2}-\d{2})"))
def the_reconciled_end_is(ctx, date):
    assert ctx.result[1] == _d(date)


@then(parsers.parse("the reconciled duration is {days:d}"))
def the_reconciled_duration_is(ctx, days):
    assert ctx.result[2] == days


@then("no floor is set")
def no_floor_is_set(ctx):
    assert ctx.result[3] is None


@then(parsers.parse("the floor is {date}"))
def the_floor_is(ctx, date):
    assert ctx.result[3] == _d(date)


@then(parsers.parse("the reconciled row reads {start} to {end} for "
                    "{days:d} days"))
def the_reconciled_row_reads(ctx, start, end, days):
    assert ctx.result[:3] == (_d(start), _d(end), days)


@then(parsers.parse('task "{task_id}" has duration {days:d}'))
def task_has_duration(ctx, task_id, days):
    assert ctx.project.get_task_by_id(task_id).duration == days


@then(parsers.parse('task "{task_id}" ends on {date}'))
def task_ends_on(ctx, task_id, date):
    assert ctx.project.get_task_by_id(task_id).end_date == _d(date)


@then(parsers.parse('task "{task_id}" starts on {date}'))
def task_starts_on(ctx, task_id, date):
    assert ctx.project.get_task_by_id(task_id).start_date == _d(date)


@then(parsers.parse('task "{task_id}" is constrained "{ctype}" to {date}'))
def task_is_constrained(ctx, task_id, ctype, date):
    task = ctx.project.get_task_by_id(task_id)
    assert task.constraint_type == ctype
    assert task.constraint_date == _d(date)


@then(parsers.parse('the "{column}" cell of "{task_id}" is not editable'))
def the_cell_is_not_editable(ctx, column, task_id):
    assert not ctx.view._schedule_cell_editable(task_id, column)


@then(parsers.parse('the "{column}" cell of "{task_id}" is editable'))
def the_cell_is_editable(ctx, column, task_id):
    assert ctx.view._schedule_cell_editable(task_id, column)
