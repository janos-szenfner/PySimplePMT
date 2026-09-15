"""
pytest-bdd tests for resource levelling - the float-driven engine and the
preview window that shows its answers before applying them.

Run with:
    python3 -m pytest tests/test_leveling_bdd.py -q

The engine scenarios build a bare Project and need no display; the one
marked needs_display builds the full GanttApp for the preview window.
"""
import tkinter as tk
from datetime import datetime, timedelta

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.leveling import LevelingOptions, level_resources, preview
from gantt_app.core.models import Project, Task, Dependency
from gantt_app.core.priority import normalize_priority
from gantt_app.core.resource_model import (
    Resource, ResourceType, SchedulePattern,
)

BASE = datetime(2026, 1, 5)          # a Monday
D = timedelta(days=1)


def _display_available() -> bool:
    try:
        root = tk.Tk()
    except Exception:
        return False
    root.destroy()
    return True


HAVE_DISPLAY = _display_available()

pytestmark = [
    pytest.mark.leveling,
]

scenarios("features/leveling.feature")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _plan():
    """An empty project holding one full-time resource."""
    project = Project(name="Plan")
    project.tasks.clear()
    repo = project.resource_repository
    repo.resources.clear()
    repo.teams.clear()
    repo.materials.clear()
    repo.costs.clear()
    repo.add_resource(Resource(
        id="r1", name="Alex", resource_type=ResourceType.NAMED,
        role_type="Dev", schedule_pattern=SchedulePattern.STANDARD))
    return project


def _work(project, task_id, name, start, days, hours=40.0, deps=None,
          priority="Medium", constraint="NA", deadline=None):
    """A task on r1, spread over `days` working days from `start`."""
    task = Task(
        id=task_id, name=name, task_type="Task", priority=priority,
        start_date=start, end_date=start + timedelta(days=days - 1),
        dependencies=[Dependency(task_id=d) for d in (deps or [])],
        constraint_type=constraint, deadline=deadline,
        resource_assignments=[{
            "resource_id": "r1",
            "estimated_hours": hours,
            "resource_split": 100.0,
        }])
    task.__post_init__()
    project.add_task(task)
    return task


def _named(project, name):
    for task in project.tasks:
        if task.name == name:
            return task
    raise AssertionError(f"task {name!r} not found")


# ------------------------------------------------------------------
# GIVEN - the engine plans
# ------------------------------------------------------------------

@given("a levelling plan with a double-booked resource",
       target_fixture="project")
def a_plan_with_a_double_booked_resource():
    """
    Alex carries two 40h tasks in one 40h week. Design has float - Test,
    which depends on Build, is what makes Build critical, and the pair of
    them pin the finish, so only Design can move.
    """
    project = _plan()
    _work(project, "a", "Design", BASE, 5)
    _work(project, "b", "Build", BASE, 5)
    _work(project, "c", "Test", BASE + 7 * D, 5, deps=["b"])
    project.renumber_task_ids()
    return project


@given("a levelling plan where nothing has float",
       target_fixture="project")
def a_plan_where_nothing_has_float():
    """Both tasks end on the plan's finish, so nobody has a day to give."""
    project = _plan()
    _work(project, "a", "Design", BASE, 5)
    _work(project, "b", "Build", BASE, 5)
    project.renumber_task_ids()
    return project


@given("a levelling plan with a locked task in the overload",
       target_fixture="project")
def a_plan_with_a_locked_task():
    project = _plan()
    _work(project, "a", "Fixed Launch", BASE, 5, constraint="MSO")
    _work(project, "b", "Build", BASE, 5)
    _work(project, "c", "Test", BASE + 7 * D, 5, deps=["b"])
    project.renumber_task_ids()
    return project


@given("a levelling plan where the float task has a deadline",
       target_fixture="project")
def a_plan_where_the_float_task_has_a_deadline():
    """Design may slip, but only until its deadline mid-float."""
    project = _plan()
    _work(project, "a", "Design", BASE, 5, deadline=BASE + 11 * D)
    _work(project, "b", "Build", BASE, 5)
    _work(project, "c", "Test", BASE + 14 * D, 5, deps=["b"])
    project.renumber_task_ids()
    return project


@given("a levelling plan where both overloaded tasks differ in priority",
       target_fixture="project")
def a_plan_where_tasks_differ_in_priority():
    project = _plan()
    _work(project, "a", "Design", BASE, 5, priority="Critical")
    _work(project, "b", "Build", BASE, 5, priority="Low")
    _work(project, "c", "Test", BASE + 14 * D, 5, deps=["b"])
    project.renumber_task_ids()
    return project


@given("a levelling plan where each overloaded task feeds a tight successor",
       target_fixture="project")
def a_plan_where_tasks_feed_tight_successors():
    """
    Both week-one tasks have exactly five days of free float: their
    successors start a working day after that runs out, so whichever one
    the leveler moves, it must stop short of pushing what follows it.
    """
    project = _plan()
    _work(project, "a", "Design", BASE, 5)
    _work(project, "b", "Build", BASE, 5)
    _work(project, "c", "Test", BASE + 14 * D, 5, deps=["b"])
    _work(project, "d", "Slide", BASE + 14 * D, 5, deps=["a"])
    project.renumber_task_ids()
    return project


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------

@when("the plan is levelled", target_fixture="plan")
def the_plan_is_levelled(project):
    return level_resources(project)


@when("the plan is levelled within free float", target_fixture="plan")
def the_plan_is_levelled_within_free_float(project):
    return level_resources(project,
                           LevelingOptions(within_free_float=True))


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@then("the float task is delayed within its free float")
def the_float_task_is_delayed(project, plan):
    design = _named(project, "Design")
    assert design.start_date > BASE
    assert plan.moves, "expected at least one move"
    assert not plan.finish_slipped


@then("the critical task did not move")
def the_critical_task_did_not_move(project):
    assert _named(project, "Build").start_date == BASE


@then("the project finish did not slip")
def the_project_finish_did_not_slip(plan):
    assert plan.finish_after <= plan.finish_before


@then("no task moved")
def no_task_moved(plan):
    assert plan.moves == []


@then("the unresolved list names the resource and the day")
def the_unresolved_list_names_the_day(plan):
    assert plan.unresolved, "expected unresolved overloads"
    issue = plan.unresolved[0]
    assert issue.resource_name == "Alex"
    assert issue.over_by > 0
    assert "reassign" in issue.detail


@then("the locked task kept its dates")
def the_locked_task_kept_its_dates(project):
    assert _named(project, "Fixed Launch").start_date == BASE


@then("the skipped list says why")
def the_skipped_list_says_why(plan):
    assert any("MSO" in note for note in plan.skipped)


@then("the task is not pushed past its deadline")
def the_task_is_not_pushed_past_its_deadline(project):
    design = _named(project, "Design")
    assert design.end_date <= BASE + 11 * D


@then("the lower-priority task moved first")
def the_lower_priority_task_moved_first(project, plan):
    build = _named(project, "Build")
    design = _named(project, "Design")
    assert build.start_date > BASE
    if design.start_date > BASE:
        # If both moved, the low-priority one moved at least as far.
        assert build.start_date >= design.start_date


@then("the successors kept their dates")
def the_successors_kept_their_dates(project):
    assert _named(project, "Slide").start_date == BASE + 14 * D
    assert _named(project, "Test").start_date == BASE + 14 * D


# ------------------------------------------------------------------
# Priority migration
# ------------------------------------------------------------------

@given(parsers.re(r'a task saved with the legacy priority "(?P<old>[^"]+)"'),
       target_fixture="legacy_task")
def a_task_with_a_legacy_priority(old):
    return Task(id="t", name="T", task_type="Task", priority=old,
                start_date=BASE)


@then(parsers.re(r'its priority reads "(?P<new>[^"]+)"'))
def its_priority_reads(legacy_task, new):
    assert legacy_task.priority == new
    assert normalize_priority(legacy_task.priority) == new


# ------------------------------------------------------------------
# The preview window
# ------------------------------------------------------------------

@given("the application is started", target_fixture="app")
def the_application_is_started():
    import customtkinter as ctk
    from gantt_app.main import GanttApp

    ctk.set_appearance_mode("light")
    app = GanttApp()
    app.withdraw()
    app.update_idletasks()
    yield app
    try:
        app.destroy()
    except tk.TclError:
        pass


@given("a project with an overallocated resource")
def a_project_with_an_overallocated_resource(app):
    project = app.project
    project.tasks.clear()
    repo = project.resource_repository
    repo.resources.clear()
    repo.add_resource(Resource(
        id="r1", name="Alex", resource_type=ResourceType.NAMED,
        role_type="Dev", schedule_pattern=SchedulePattern.STANDARD))
    _work(project, "a", "Design", BASE, 5)
    _work(project, "b", "Build", BASE, 5)
    _work(project, "c", "Test", BASE + 14 * D, 5, deps=["b"])
    project.renumber_task_ids()


@when("the levelling preview is opened", target_fixture="leveling_window")
def the_levelling_preview_is_opened(app):
    app.toolbar.preview_leveling()
    app.update_idletasks()
    for widget in app.winfo_children():
        if type(widget).__name__ == "LevelingPreviewWindow":
            return widget
    raise AssertionError("the levelling preview did not open")


@then("the table lists the move")
def the_table_lists_the_move(leveling_window):
    rows = [leveling_window.tree.item(row, "values")
            for row in leveling_window.tree.get_children()]
    assert any(row[0] == "Design" for row in rows)


@then("the plan itself has not changed")
def the_plan_itself_has_not_changed(app):
    assert _named(app.project, "Design").start_date == BASE


@when("the preview is applied")
def the_preview_is_applied(leveling_window):
    leveling_window._apply()
    leveling_window.update_idletasks()


@then("the task moved")
def the_task_moved(app):
    assert _named(app.project, "Design").start_date > BASE


@then("one undo takes the whole run back")
def one_undo_takes_the_whole_run_back(app):
    assert app.undo_redo_manager.undo()
    assert _named(app.project, "Design").start_date == BASE
