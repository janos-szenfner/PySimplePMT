"""pytest-bdd regressions for subtask creation and multi-row movement."""
import tkinter as tk
from datetime import datetime, timedelta

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.models import Project, Task
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


@given("the selected row is a milestone")
def selected_row_is_milestone(move_context):
    milestone = move_context["project"].get_task_by_id("2")
    milestone.task_type = "Milestone"
    milestone.is_milestone = True
    move_context["task_list"].tree.selection_set("2")


@given("the second root task has a child")
def second_root_has_child(move_context):
    start = datetime(2026, 9, 9)
    child = Task(id="child", name="Child", task_type="Subtask",
                 parent_task_id="2", start_date=start,
                 end_date=start + timedelta(days=1))
    move_context["project"].add_task(child)
    move_context["task_list"].update_task_list()


@given("the second root task and its child are selected")
def second_and_child_selected(move_context):
    move_context["task_list"].tree.selection_set("2", "child")


class _FakeCreateDialog:
    saved_task_name = None
    cancel = False
    captured_parent = None

    def __init__(self, master, project, task_type, parent_task=None,
                 on_save=None, **kwargs):
        type(self).captured_parent = parent_task
        if not type(self).cancel and on_save is not None:
            start = parent_task.start_date if parent_task else datetime(2026, 9, 7)
            on_save(Task(id=project.next_task_id(),
                         name=type(self).saved_task_name or "Child",
                         task_type="Subtask", parent_task_id=(
                             parent_task.id if parent_task else None),
                         start_date=start, end_date=start + timedelta(days=1)))

    def wait_window(self):
        return None


@when(parsers.parse('the user creates and saves a subtask named "{name}"'))
def create_and_save_subtask(move_context, name, monkeypatch):
    _FakeCreateDialog.saved_task_name = name
    _FakeCreateDialog.cancel = False
    monkeypatch.setattr("gantt_app.views.taskdialogs.CreateTaskDialog", _FakeCreateDialog)
    monkeypatch.setattr(
        move_context["toolbar"], "_select_parent_task",
        lambda _candidates: pytest.fail("selected parent should skip chooser"),
    )
    move_context["toolbar"].add_subtask()


@when("the user cancels subtask creation")
def cancel_subtask_creation(move_context, monkeypatch):
    _FakeCreateDialog.cancel = True
    monkeypatch.setattr("gantt_app.views.taskdialogs.CreateTaskDialog", _FakeCreateDialog)
    monkeypatch.setattr(
        move_context["toolbar"], "_select_parent_task",
        lambda _candidates: pytest.fail("selected parent should skip chooser"),
    )
    move_context["toolbar"].add_subtask()


@when("the user requests a new subtask")
def request_new_subtask(move_context, monkeypatch):
    _FakeCreateDialog.cancel = True
    _FakeCreateDialog.captured_parent = None
    monkeypatch.setattr("gantt_app.views.taskdialogs.CreateTaskDialog", _FakeCreateDialog)
    monkeypatch.setattr(move_context["toolbar"], "_select_parent_task",
                        lambda candidates: candidates[0])
    move_context["toolbar"].add_subtask()


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


@then(parsers.parse('"{name}" exists in the project'))
def task_exists(move_context, name):
    assert any(task.name == name for task in move_context["project"].tasks)


@then(parsers.parse('"{name}" is a child of the second root task'))
def task_is_child_of_second(move_context, name):
    task = next(task for task in move_context["project"].tasks if task.name == name)
    assert task.parent_task_id == "2"


@then(parsers.parse('"{name}" appears directly under the second root task'))
def task_appears_under_second(move_context, name):
    order = [task.name for task in move_context["project"].display_order()]
    assert order.index(name) == order.index("Second") + 1


@then("the project still contains four tasks")
def project_still_has_four(move_context):
    assert len(move_context["project"].tasks) == 4


@then("the parent chooser is used instead of the milestone")
def chooser_used_not_milestone(move_context):
    assert _FakeCreateDialog.captured_parent is not None
    assert not _FakeCreateDialog.captured_parent.is_milestone


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
