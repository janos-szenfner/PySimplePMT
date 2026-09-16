"""
pytest-bdd tests for multi-row Delete and Add-to-Timeline (issues #17, #34).

Run with:
    python3 -m pytest tests/test_multi_delete_and_timeline_bdd.py -q

The scenarios drive the real widget, so they skip without a display.
Converted from test_multi_delete_and_timeline.py - every case carried
over.
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Project, Task
from gantt_app.views import dialogs as messagebox

pytestmark = [
    pytest.mark.multi_delete_and_timeline,
]

scenarios("features/multi_delete_and_timeline.feature")

BASE = datetime(2026, 9, 10)


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


# ------------------------------------------------------------------
# GIVEN - the list, needs a display
# ------------------------------------------------------------------

@given("a task list over four tasks", target_fixture="ctx")
def a_task_list_over_four_tasks():
    if not HAVE_DISPLAY:
        pytest.skip("needs a display")
    import customtkinter as ctk
    from gantt_app.utils.undoredo import (
        ProjectStateTracker, UndoRedoManager,
    )
    from gantt_app.views.task_list import DragDropTaskList

    root = ctk.CTk()
    root.withdraw()

    project = Project(name="Plan")
    for n in range(1, 5):
        project.add_task(Task(
            id=f"t{n}", name=f"Task {n}", task_type="Task",
            start_date=BASE, end_date=BASE + timedelta(days=2)))

    manager = UndoRedoManager()
    task_list = DragDropTaskList(
        root, project,
        project_tracker=ProjectStateTracker(project, manager))
    root.update_idletasks()

    # Confirmations answer Yes without a real dialog.
    orig_askyesno = messagebox.askyesno
    messagebox.askyesno = lambda *a, **k: True

    yield SimpleNamespace(root=root, project=project, manager=manager,
                          task_list=task_list)

    messagebox.askyesno = orig_askyesno
    _shut_down(root)


@given("the confirmation answers No")
def the_confirmation_answers_no(ctx):
    messagebox.askyesno = lambda *a, **k: False


@given("no task is on the timeline")
def no_task_is_on_the_timeline(ctx):
    for t in ctx.project.tasks:
        t.show_in_timeline = False


@given(parsers.parse('task "{task_id}" is already on the timeline'))
def task_is_already_on_the_timeline(ctx, task_id):
    ctx.project.get_task_by_id(task_id).show_in_timeline = True


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------

@when(parsers.parse('rows "{csv}" are deleted'))
def rows_are_deleted(ctx, csv):
    ctx.task_list.delete_tasks(csv.split(","))


@when(parsers.parse('row "{task_id}" is deleted'))
def a_row_is_deleted(ctx, task_id):
    ctx.task_list.delete_tasks(task_id)


@when(parsers.parse('rows "{csv}" are added to the timeline'))
def rows_are_added_to_the_timeline(ctx, csv):
    ctx.task_list.add_to_timeline(csv.split(","))


@when("the delete is undone")
@when("the add is undone")
def the_action_is_undone(ctx):
    assert ctx.manager.can_undo()
    ctx.manager.undo()


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@then(parsers.parse('the plan holds tasks "{csv}"'))
def the_plan_holds_tasks(ctx, csv):
    assert [t.id for t in ctx.project.tasks] == csv.split(",")


@then(parsers.parse('the plan holds all of tasks "{csv}"'))
def the_plan_holds_all_of_tasks(ctx, csv):
    # After an undo the order is not the assertion - the set is.
    assert {t.id for t in ctx.project.tasks} == set(csv.split(","))


@then(parsers.parse("the plan still holds {count:d} tasks"))
def the_plan_still_holds(ctx, count):
    assert len(ctx.project.tasks) == count


@then(parsers.parse('tasks "{csv}" are on the timeline'))
def tasks_are_on_the_timeline(ctx, csv):
    flags = {t.id: t.show_in_timeline for t in ctx.project.tasks}
    for task_id in csv.split(","):
        assert flags[task_id]


@then(parsers.parse('tasks "{csv}" are not on the timeline'))
def tasks_are_not_on_the_timeline(ctx, csv):
    flags = {t.id: t.show_in_timeline for t in ctx.project.tasks}
    for task_id in csv.split(","):
        assert not flags[task_id]


@then("no task is on the timeline")
def then_no_task_is_on_the_timeline(ctx):
    assert not any(t.show_in_timeline for t in ctx.project.tasks)


@then("there is nothing to undo")
def there_is_nothing_to_undo(ctx):
    assert not ctx.manager.can_undo()


@then("the Gantt shows nothing yet")
def the_gantt_shows_nothing_yet(ctx):
    from gantt_app.utils.chart_render import _get_visible_tasks
    assert _get_visible_tasks(ctx.project) == []


@then(parsers.parse('the Gantt-visible tasks are "{csv}"'))
def the_gantt_visible_tasks_are(ctx, csv):
    from gantt_app.utils.chart_render import _get_visible_tasks
    visible = {t.id for t in _get_visible_tasks(ctx.project)}
    assert visible == set(csv.split(","))


@then(parsers.parse('task "{task_id}" reads on the timeline'))
def task_reads_on_the_timeline(ctx, task_id):
    assert ctx.project.get_task_by_id(task_id).show_in_timeline
