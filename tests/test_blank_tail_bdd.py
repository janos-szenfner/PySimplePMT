"""
pytest-bdd tests for the grid's uncommitted blank tail (issue #111).

Run with:
    python3 -m pytest tests/test_blank_tail_bdd.py -q

The scenarios drive the real widget, so they skip without a display.
"""
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Project, Task

pytestmark = [
    pytest.mark.blank_tail,
]

scenarios("features/blank_tail.feature")


def _display_available() -> bool:
    """Whether a Tk window can be opened here."""
    try:
        import tkinter
        root = tkinter.Tk()
        root.destroy()
        return True
    except Exception:
        return False


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


def _commit_name_cell(task_list, iid, text):
    """Open the name editor on a row and commit the given text."""
    task_list.edit_name_cell(iid)
    assert task_list._cell_editor is not None, \
        "the cell editor did not open"
    task_list._cell_editor.insert(0, text)
    task_list._commit_name()


# ------------------------------------------------------------------
# GIVEN - needs a display
# ------------------------------------------------------------------

@given("a task list holding two tasks", target_fixture="ctx")
def a_task_list_holding_two_tasks():
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
    for i in range(2):
        project.add_task(Task(
            id=f"t{i}", name=f"Task {i}", task_type="Task",
            start_date=datetime(2026, 1, 5),
            end_date=datetime(2026, 1, 5) + timedelta(days=2)))

    manager = UndoRedoManager()
    task_list = DragDropTaskList(
        root, project,
        project_tracker=ProjectStateTracker(project, manager))
    task_list.update_task_list = MagicMock(wraps=task_list.update_task_list)
    root.update_idletasks()
    task_list.update_task_list.reset_mock()
    task_list.update_task_list()

    # Where a cell is on screen is answered by the widget, and a window
    # that has never been mapped does not have an answer - the same
    # standing-in test_inline_editing makes, for the same reason.
    task_list._cell_box = lambda _task_id, _column: (0, 0, 200, 20)

    yield SimpleNamespace(root=root, project=project, task_list=task_list)

    _shut_down(root)


@given("the plan is emptied")
def the_plan_is_emptied(ctx):
    for task in list(ctx.project.tasks):
        ctx.project.remove_task(task.id)
    ctx.task_list.update_task_list()


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------

@when(parsers.parse('"{name}" is typed into the first blank row\'s name '
                    'cell'))
def text_typed_into_the_first_blank(ctx, name):
    _commit_name_cell(ctx.task_list, ctx.task_list._blank_rows[0], name)


@when(parsers.parse('"{name}" is typed into the third blank row\'s name '
                    'cell'))
def text_typed_into_the_third_blank(ctx, name):
    _commit_name_cell(ctx.task_list, ctx.task_list._blank_rows[2], name)


@when("the first blank row's name cell is opened and left empty")
def the_first_blank_name_cell_is_left(ctx):
    _commit_name_cell(ctx.task_list, ctx.task_list._blank_rows[0], '')


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@then("the tasks are followed by at least twenty-five blank rows")
def a_tail_of_at_least_twenty_five(ctx):
    task_list = ctx.task_list
    items = task_list.tree.get_children()
    n_tasks = len(ctx.project.tasks)
    assert list(task_list._blank_rows) == list(items[n_tasks:]), \
        "the tail is not sitting after the tasks"
    assert len(task_list._blank_rows) >= task_list.BLANK_TAIL_ROWS


@then("no blank row has a task behind it")
def no_blank_row_has_a_task(ctx):
    for iid in ctx.task_list._blank_rows:
        assert iid.startswith(ctx.task_list.BLANK_IID_PREFIX)
        assert ctx.project.get_task_by_id(iid) is None
        for value in ctx.task_list.tree.item(iid, 'values'):
            assert value == ''


@then("a blank row picked out selects nothing")
def a_blank_row_selects_nothing(ctx):
    ctx.task_list.tree.selection_set(ctx.task_list._blank_rows[0])
    assert ctx.task_list.get_selected_task_ids() == []


@then(parsers.parse('the plan gains one row called "{name}"'))
def the_plan_gains_one_named_row(ctx, name):
    gained = [task for task in ctx.project.tasks if task.name == name]
    assert len(gained) == 1, \
        f"expected one new {name} row, plan has {len(ctx.project.tasks)}"
    assert not gained[0].is_placeholder


@then("the plan gains no rows")
def the_plan_gains_no_rows(ctx):
    assert len(ctx.project.tasks) == 2


@then("the plan gains three rows")
def the_plan_gains_three_rows(ctx):
    assert len(ctx.project.tasks) == 5


@then("the first two are undecided placeholders")
def the_first_two_are_placeholders(ctx):
    assert ctx.project.tasks[2].is_placeholder
    assert ctx.project.tasks[3].is_placeholder


@then(parsers.parse('the third is called "{name}"'))
def the_third_carries_the_name(ctx, name):
    assert ctx.project.tasks[4].name == name
    assert not ctx.project.tasks[4].is_placeholder


@then("the blank tail is as long as before")
def the_tail_is_as_long_as_before(ctx):
    task_list = ctx.task_list
    items = task_list.tree.get_children()
    n_tasks = len(ctx.project.tasks)
    assert list(task_list._blank_rows) == list(items[n_tasks:])
    assert len(task_list._blank_rows) >= task_list.BLANK_TAIL_ROWS
