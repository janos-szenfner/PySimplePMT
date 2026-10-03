"""pytest-bdd regressions for multi-row movement."""
import tkinter as tk
from datetime import datetime, timedelta

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Project, Task
from gantt_app.utils.undoredo import ProjectStateTracker, UndoRedoManager


def _display_available() -> bool:
    try:
        root = tk.Tk()
    except Exception:
        return False
    root.destroy()
    return True


HAVE_DISPLAY = _display_available()
pytestmark = [pytest.mark.skipif(not HAVE_DISPLAY, reason="needs a display")]
scenarios("features/subtask_creation_and_group_move.feature")


@given("a project with four root tasks", target_fixture="move_context")
def a_project_with_four_root_tasks():
    import customtkinter as ctk

    start = datetime(2026, 9, 7)
    tasks = [
        Task(id=str(index), name=name, task_type="Task",
             start_date=start + timedelta(days=index),
             end_date=start + timedelta(days=index + 1))
        for index, name in enumerate(("First", "Second", "Third", "Fourth"), 1)
    ]
    root = ctk.CTk()
    root.withdraw()
    context = {"root": root, "project": Project(name="Move BDD", tasks=tasks)}
    yield context
    try:
        root.destroy()
    except tk.TclError:
        pass


@given("the task list and toolbar are open")
def task_list_and_toolbar_are_open(move_context):
    from gantt_app.views.task_list import DragDropTaskList
    from gantt_app.views.toolbar import Toolbar

    manager = UndoRedoManager(max_history=20)
    manager.set_project(move_context["project"])
    tracker = ProjectStateTracker(move_context["project"], manager)
    toolbar = Toolbar(move_context["root"], move_context["project"],
                      undo_redo_manager=manager)
    task_list = DragDropTaskList(
        move_context["root"], move_context["project"],
        project_tracker=tracker,
    )
    toolbar.set_task_list(task_list)
    move_context.update(toolbar=toolbar, task_list=task_list, manager=manager)


@given("the second root task is selected")
def second_root_selected(move_context):
    move_context["task_list"].tree.selection_set("2")


@given("the second and third root tasks are selected")
def second_and_third_selected(move_context):
    move_context["task_list"].tree.selection_set("2", "3")


@given("the third and fourth root tasks are selected")
def third_and_fourth_selected(move_context):
    move_context["task_list"].tree.selection_set("3", "4")


@given("the first and second root tasks are selected")
def first_and_second_selected(move_context):
    move_context["task_list"].tree.selection_set("1", "2")


@given("the second and fourth root tasks are selected")
def second_and_fourth_selected(move_context):
    move_context["task_list"].tree.selection_set("2", "4")


@given("the second root task has a child")
def second_root_has_child(move_context):
    start = datetime(2026, 9, 9)
    child = Task(id="child", name="Child", task_type="Task",
                 parent_task_id="2", start_date=start,
                 end_date=start + timedelta(days=1))
    move_context["project"].add_task(child)
    move_context["task_list"].update_task_list()


@given("the second root task and its child are selected")
def second_and_child_selected(move_context):
    move_context["task_list"].tree.selection_set("2", "child")


@when(parsers.parse("Move {direction} is invoked on the {clicked} selected task"))
def move_is_invoked(move_context, direction, clicked):
    targets = {"Up": "up", "Down": "down",
               "to Top": "top", "to Bottom": "bottom"}
    clicked_ids = {"first": "1", "second": "2", "third": "3", "fourth": "4"}
    menu = move_context["task_list"].context_menu
    chosen = menu._selection_including(clicked_ids[clicked])
    menu._invoke_move(chosen, targets[direction])


@when("the move is undone")
def move_is_undone(move_context):
    move_context["manager"].undo()


@then(parsers.parse('the root task order is "{names}"'))
def root_task_order(move_context, names):
    actual = [task.name for task in move_context["project"].get_root_tasks()]
    assert actual == names.split(", ")


@then("the second and third root tasks remain selected")
def second_and_third_remain_selected(move_context):
    assert set(move_context["task_list"].tree.selection()) == {"2", "3"}


@then("the second and fourth root tasks remain selected")
def second_and_fourth_remain_selected(move_context):
    assert set(move_context["task_list"].tree.selection()) == {"2", "4"}


@then("the second root task branch appears before the first root task")
def second_branch_before_first(move_context):
    roots = [task.id for task in move_context["project"].get_root_tasks()]
    assert roots.index("2") < roots.index("1")


@then("the child remains under the second root task")
def child_remains_under_second(move_context):
    assert move_context["project"].get_task_by_id("child").parent_task_id == "2"
