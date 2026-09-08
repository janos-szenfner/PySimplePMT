"""
pytest-bdd cover for the Advanced tab's constraints and deadlines.

Adapted from advanced-tab-gherkin.txt and advancede2e-gherkin.txt. The
application treats constraints and deadlines as recorded, saved and drawn
planner settings that do not drive the scheduler, so the scenarios verify
storage, serialization, the Gantt markers, and - the point of the whole
exercise - that adding a constraint changes neither the dependency-driven
schedule nor the bar geometry. No display is needed.
"""
import json
import os
import tempfile
import tkinter as tk
from datetime import datetime, timedelta

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.models import Project, Task
from gantt_app.utils import chart_render as cr
from gantt_app.utils.file_io import JSONFileIO
from gantt_app.utils.undoredo import ProjectStateTracker, UndoRedoManager


def _display_available() -> bool:
    try:
        root = tk.Tk()
    except Exception:
        return False
    root.destroy()
    return True


HAVE_DISPLAY = _display_available()

BASE = datetime(2026, 10, 1)

scenarios("features/advanced_constraints.feature")


def _day(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%d")


@given(parsers.parse('a project scheduled from "{start}"'),
       target_fixture="plan")
def a_project(start):
    return {"project": Project(name="Adv"), "base": _day(start)}


def _add(plan, name, days):
    project = plan["project"]
    base = plan["base"]
    end = project.calendar.add_working_days(base, days - 1)
    task = Task(id=name, name=name, start_date=base, end_date=end)
    project.add_task(task)
    return task


def _markers(project, task_id, kind):
    layout = cr.layout_chart(project, width=1200)
    return [m for m in layout.markers
            if m["kind"] == kind and m.get("task_id") == task_id]


# --- task creation ---------------------------------------------------------
@given(parsers.re(r'a two-day task "(?P<name>[^"]+)" with constraint '
                  r'"(?P<enum>[^"]+)" on "(?P<date>[\d-]+)"$'))
def task_with_dated_constraint(plan, name, enum, date):
    task = _add(plan, name, 2)
    task.constraint_type = enum
    task.constraint_date = _day(date)


@given(parsers.re(r'a two-day task "(?P<name>[^"]+)" with constraint '
                  r'"(?P<enum>[^"]+)"$'))
def task_with_undated_constraint(plan, name, enum):
    task = _add(plan, name, 2)
    task.constraint_type = enum


@given(parsers.parse('a two-day task "{name}" starting "{start}"'))
def two_day_task(plan, name, start):
    plan["base"] = _day(start)
    _add(plan, name, 2)


@given(parsers.re(r'task "(?P<a>[^"]+)" of (?P<da>\d+) working days and task '
                  r'"(?P<b>[^"]+)" of (?P<db>\d+) working days$'))
def two_tasks(plan, a, da, b, db):
    _add(plan, a, int(da))
    _add(plan, b, int(db))


@given(parsers.re(r'tasks "(?P<a>[^"]+)", "(?P<b>[^"]+)" and "(?P<c>[^"]+)" '
                  r'each of (?P<days>\d+) working days$'))
def three_tasks(plan, a, b, c, days):
    for name in (a, b, c):
        _add(plan, name, int(days))


@given(parsers.re(r'"(?P<succ>[^"]+)" has a "(?P<link>[^"]+)" link to '
                  r'"(?P<pred>[^"]+)"$'))
def link(plan, succ, link, pred):
    plan["project"].get_task_by_id(succ).add_dependency(pred, dep_type=link)


@given(parsers.parse('"{name}" has a deadline of "{date}"'))
def has_deadline(plan, name, date):
    plan["project"].get_task_by_id(name).deadline = _day(date)


# --- scheduling / remembering ----------------------------------------------
@given("the plan is rescheduled")
@when("the plan is rescheduled")
def reschedule(plan):
    plan["project"].reschedule(forward_only=False)


@given("\"B\"'s start is remembered")
def remember_b_start(plan):
    plan["b_start"] = plan["project"].get_task_by_id("B").start_date


@when(parsers.re(r'"(?P<name>[^"]+)" is given a "(?P<enum>[^"]+)" constraint '
                 r'on "(?P<date>[\d-]+)"$'))
def give_constraint(plan, name, enum, date):
    task = plan["project"].get_task_by_id(name)
    task.constraint_type = enum
    task.constraint_date = _day(date)


@then("\"B\"'s start is unchanged")
def b_start_unchanged(plan):
    assert plan["project"].get_task_by_id("B").start_date == plan["b_start"]


@then(parsers.re(r'"(?P<name>[^"]+)" starts on "(?P<date>[\d-]+)"$'))
def task_starts_on(plan, name, date):
    assert plan["project"].get_task_by_id(name).start_date.date() \
        == _day(date).date()


@when("the bar geometry is remembered")
def remember_geometry(plan):
    layout = cr.layout_chart(plan["project"], width=1200)
    plan["geometry"] = {b["task_id"]: (b["x0"], b["x1"], b["y0"], b["y1"])
                        for b in layout.bars}


@then("the bar geometry is unchanged apart from the added markers")
def geometry_unchanged(plan):
    layout = cr.layout_chart(plan["project"], width=1200)
    now = {b["task_id"]: (b["x0"], b["x1"], b["y0"], b["y1"])
           for b in layout.bars}
    assert now == plan["geometry"]
    assert layout.markers  # the constraint did add a marker


# --- assertions on one task ------------------------------------------------
@then(parsers.parse('the task\'s constraint type is "{enum}"'))
def constraint_type_is(plan, enum):
    assert plan["project"].get_task_by_id("T").constraint_type == enum


@then(parsers.parse('the task\'s constraint date is "{date}"'))
def constraint_date_is(plan, date):
    assert plan["project"].get_task_by_id("T").constraint_date == _day(date)


@then("the task's constraint date is not set")
def constraint_date_not_set(plan):
    assert plan["project"].get_task_by_id("T").constraint_date is None


@then(parsers.parse('the reloaded task\'s constraint date is "{date}"'))
def reloaded_constraint_date(plan, date):
    task = plan["project"].get_task_by_id("T")
    reread = Task.from_dict(json.loads(json.dumps(task.to_dict())))
    assert reread.constraint_date == _day(date)


@then(parsers.re(r'the Gantt shows a "(?P<kind>[^"]+)" marker in '
                 r'"(?P<color>[^"]+)" for "(?P<name>[^"]+)"$'))
def gantt_shows_marker(plan, kind, color, name):
    marks = _markers(plan["project"], name, kind)
    assert marks, f"no {kind} marker for {name}"
    assert marks[0]["color"] == color


# --- deadline slip / reset -------------------------------------------------
@then(parsers.parse('the "{name}" bar is marked slipped'))
def bar_slipped(plan, name):
    layout = cr.layout_chart(plan["project"], width=1200)
    bar = next(b for b in layout.bars if b["task_id"] == name)
    assert bar.get("slipped")


@then(parsers.parse('the "{name}" bar is not marked slipped'))
def bar_not_slipped(plan, name):
    layout = cr.layout_chart(plan["project"], width=1200)
    bar = next(b for b in layout.bars if b["task_id"] == name)
    assert not bar.get("slipped")


@then(parsers.parse('the deadline marker for "{name}" is red'))
def deadline_red(plan, name):
    marks = _markers(plan["project"], name, "deadline")
    assert marks and marks[0]["color"] == cr.DEADLINE_SLIPPED


@when(parsers.parse('the deadline for "{name}" is reset to N/A'))
def reset_deadline(plan, name):
    plan["project"].get_task_by_id(name).deadline = None


@then(parsers.parse('there is no deadline marker for "{name}"'))
def no_deadline_marker(plan, name):
    assert not _markers(plan["project"], name, "deadline")


# --- persistence -----------------------------------------------------------
@when("the project is saved and loaded from disk")
def save_and_load(plan):
    handle = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    handle.close()
    try:
        JSONFileIO.save_project(plan["project"], handle.name)
        plan["project"] = JSONFileIO.load_project(handle.name)
    finally:
        os.unlink(handle.name)


@then(parsers.re(r'the reloaded "(?P<name>[^"]+)" has constraint '
                 r'"(?P<enum>[^"]+)" on "(?P<date>[\d-]+)"$'))
def reloaded_has_constraint(plan, name, enum, date):
    task = plan["project"].get_task_by_id(name)
    assert task.constraint_type == enum
    assert task.constraint_date == _day(date)


@then(parsers.parse('the reloaded "{name}" has a deadline of "{date}"'))
def reloaded_has_deadline(plan, name, date):
    assert plan["project"].get_task_by_id(name).deadline == _day(date)


@when(parsers.re(r'each is given a "(?P<enum>[^"]+)" constraint on '
                 r'"(?P<date>[\d-]+)"$'))
def each_given_constraint(plan, enum, date):
    for task in plan["project"].tasks:
        task.constraint_type = enum
        task.constraint_date = _day(date)


@then(parsers.re(r'each of "(?P<a>[^"]+)", "(?P<b>[^"]+)", "(?P<c>[^"]+)" has '
                 r'constraint "(?P<enum>[^"]+)" on "(?P<date>[\d-]+)"$'))
def each_has_constraint(plan, a, b, c, enum, date):
    for name in (a, b, c):
        task = plan["project"].get_task_by_id(name)
        assert task.constraint_type == enum
        assert task.constraint_date == _day(date)


# --- undo / redo -----------------------------------------------------------
@when(parsers.parse('a deadline of "{date}" is applied to "{name}" through '
                    'the tracker'))
def apply_deadline_tracked(plan, date, name):
    tracker = ProjectStateTracker(plan["project"], UndoRedoManager())
    plan["tracker"] = tracker
    tracker.update_task(name, deadline=_day(date))


@then(parsers.parse('"{name}" has a deadline of "{date}"'))
def has_deadline_now(plan, name, date):
    assert plan["project"].get_task_by_id(name).deadline == _day(date)


@then(parsers.parse('"{name}" has no deadline'))
def has_no_deadline(plan, name):
    assert plan["project"].get_task_by_id(name).deadline is None


@when("the change is undone")
def undo(plan):
    plan["tracker"].manager.undo()


@when("the change is redone")
def redo(plan):
    plan["tracker"].manager.redo()


# --- conflict detection & negative float -----------------------------------
@then(parsers.parse('"{name}" is reported in conflict with predecessor '
                    '"{pred}"'))
def reported_conflict(plan, name, pred):
    conflict = plan["project"].constraint_conflict(
        plan["project"].get_task_by_id(name))
    assert conflict is not None, "expected a conflict"
    names = [n for _num, n in conflict["predecessors"]]
    assert plan["project"].get_task_by_id(pred).name in names


@then(parsers.parse('"{name}" is flagged at negative float'))
def flagged_negative_float(plan, name):
    assert name in plan["project"].tasks_in_conflict()


@then(parsers.parse('"{name}" is not reported in conflict'))
def not_in_conflict(plan, name):
    assert plan["project"].constraint_conflict(
        plan["project"].get_task_by_id(name)) is None


@then("no task is flagged at negative float")
def none_flagged(plan):
    assert plan["project"].tasks_in_conflict() == set()


# --- the conflict dialog ----------------------------------------------------
@given("a conflict report for a task", target_fixture="conflict")
def a_conflict_report():
    return {"task_id": "B", "constraint_type": "MFO",
            "constraint_date": datetime(2026, 10, 2), "reason": "predecessor",
            "predecessors": [(1, "Alpha")]}


@then(parsers.parse('answering the conflict dialog "{choice}" returns '
                    '"{expected}"'))
def answering_the_dialog(conflict, choice, expected):
    if not HAVE_DISPLAY:
        pytest.skip("needs a display")
    import customtkinter as ctk
    from gantt_app.views.advanced_tab import ConstraintConflictDialog

    root = ctk.CTk()
    root.withdraw()
    try:
        dialog = ConstraintConflictDialog(root, conflict)
        dialog.update_idletasks()
        if choice == "keep":
            dialog._keep()
        else:
            dialog._cancel()
        assert dialog.result == expected
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass


@given("an Advanced tab set to Must Finish On", target_fixture="tab_ctx")
def an_advanced_tab_mfo():
    if not HAVE_DISPLAY:
        pytest.skip("needs a display")
    import customtkinter as ctk
    from gantt_app.views.advanced_tab import AdvancedTab

    root = ctk.CTk()
    root.withdraw()
    task = Task(id="1", name="X", start_date=BASE,
                end_date=BASE + timedelta(days=3))
    tab = AdvancedTab(root, task)
    tab.constraint_var.set("Must Finish On")
    tab._on_constraint_changed()
    tab.constraint_date_entry.set_date(datetime(2026, 10, 9))
    return {"root": root, "tab": tab}


@when("the tab is reverted to N/A")
def revert_tab(tab_ctx):
    tab_ctx["tab"].revert_to_na()


@then(parsers.parse('the tab\'s chosen constraint is "{enum}"'))
def tab_chosen_constraint(tab_ctx):
    try:
        assert tab_ctx["tab"].constraint_enum() == "NA"
    finally:
        pass


@then("the tab reports no constraint date")
def tab_no_constraint_date(tab_ctx):
    try:
        assert tab_ctx["tab"].read_values()["constraint_date"] is None
    finally:
        try:
            tab_ctx["root"].destroy()
        except tk.TclError:
            pass
