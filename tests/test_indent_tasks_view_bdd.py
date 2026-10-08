"""
pytest-bdd tests for View > Show Indent Tasks / Hide Indent Tasks
(issue #113).

Run with:
    python3 -m pytest tests/test_indent_tasks_view_bdd.py -q

The menu-contents scenario reads the toolbar's menu tree; the folding
scenarios drive the real widget, so they skip without a display.
"""
from datetime import datetime
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Project, Task

pytestmark = [
    pytest.mark.indent_tasks_view,
]

scenarios("features/indent_tasks_view.feature")


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


def _needs_display(ctx) -> None:
    """Skip a fold scenario where no window can be opened."""
    if not HAVE_DISPLAY:
        pytest.skip("needs a display")


# ------------------------------------------------------------------
# GIVEN
# ------------------------------------------------------------------

@given("a task list over a phase with nested children",
       target_fixture="ctx")
def a_task_list_over_nested_children():
    ctx = SimpleNamespace(root=None, project=None, task_list=None)
    if not HAVE_DISPLAY:
        return ctx

    import customtkinter as ctk
    from gantt_app.utils.undoredo import (
        ProjectStateTracker, UndoRedoManager,
    )
    from gantt_app.views.task_list import DragDropTaskList

    root = ctk.CTk()
    root.withdraw()

    project = Project(name="Plan")
    project.add_task(Task(id="p", name="Build", task_type="Phase",
                          start_date=datetime(2026, 1, 5),
                          end_date=datetime(2026, 1, 9)))
    project.add_task(Task(id="c1", name="Frame", task_type="Task",
                          parent_task_id="p",
                          start_date=datetime(2026, 1, 5),
                          end_date=datetime(2026, 1, 6)))
    project.add_task(Task(id="c2", name="Joists", task_type="Task",
                          parent_task_id="c1",
                          start_date=datetime(2026, 1, 6),
                          end_date=datetime(2026, 1, 7)))
    project.add_task(Task(id="s", name="Sweep up", task_type="Task",
                          start_date=datetime(2026, 1, 8),
                          end_date=datetime(2026, 1, 9)))

    manager = UndoRedoManager()
    task_list = DragDropTaskList(
        root, project,
        project_tracker=ProjectStateTracker(project, manager))
    root.update_idletasks()

    ctx.root = root
    ctx.project = project
    ctx.task_list = task_list
    yield ctx
    _shut_down(root)


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------

@when("the phase is picked and Hide Indent Tasks runs")
def the_phase_is_picked_and_hide_runs(ctx):
    _needs_display(ctx)
    ctx.task_list.tree.selection_set("p")
    ctx.folded = ctx.task_list.hide_indent_tasks()


@when("every branch is folded and the phase is picked")
def every_branch_is_folded_and_the_phase_picked(ctx):
    _needs_display(ctx)
    ctx.task_list.tree.item("c1", open=False)
    ctx.task_list.tree.item("p", open=False)
    ctx.task_list.tree.selection_set("p")


@when("Show Indent Tasks runs")
def show_indent_tasks_runs(ctx):
    _needs_display(ctx)
    ctx.opened = ctx.task_list.show_indent_tasks()


@when("a leaf row is picked")
def a_leaf_row_is_picked(ctx):
    _needs_display(ctx)
    ctx.task_list.tree.selection_set("s")


@when("a blank tail row is picked")
def a_blank_tail_row_is_picked(ctx):
    _needs_display(ctx)
    ctx.task_list.tree.selection_set(ctx.task_list._blank_rows[0])


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@then(parsers.parse('"View" offers "{first}" and "{second}"'))
def the_view_menu_offers(first, second):
    from tests.menuhelp import find, labels, menu_tree

    offered = labels(find(menu_tree(), "View")["items"])
    assert first in offered, f"View menu offers {offered}"
    assert second in offered, f"View menu offers {offered}"


@then("only the phase and the rows beside it remain on screen")
def only_the_phase_and_its_neighbours_remain(ctx):
    assert ctx.folded == 1
    assert ctx.task_list.visible_rows() == ["p", "s"]


@then("all the children are on screen again")
def all_the_children_are_on_screen_again(ctx):
    assert ctx.opened == 2
    assert ctx.task_list.visible_rows() == ["p", "c1", "c2", "s"]


@then("Hide Indent Tasks folds nothing")
def hide_indent_tasks_folds_nothing(ctx):
    assert ctx.task_list.hide_indent_tasks() == 0


@then("Show Indent Tasks opens nothing")
def show_indent_tasks_opens_nothing(ctx):
    assert ctx.task_list.show_indent_tasks() == 0
