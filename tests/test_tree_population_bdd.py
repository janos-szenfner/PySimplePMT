"""
pytest-bdd tests for how the task list populates its tree.

Run with:
    python3 -m pytest tests/test_tree_population_bdd.py -q

The tree is a real widget, so these need a display. They lock the
ordering the single-pass population keeps: every depth nests, rows
whose parent cannot be placed still show at the top level, and a
parent-child loop cannot hang the refresh.
"""
from datetime import datetime
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Project, Task

pytestmark = [
    pytest.mark.tree_population,
]

scenarios("features/tree_population.feature")


def _display_available() -> bool:
    try:
        import tkinter
        root = tkinter.Tk()
    except Exception:
        return False
    root.destroy()
    return True


HAVE_DISPLAY = _display_available()

BASE = datetime(2026, 1, 5)


def _task(task_id, name, parent=None):
    task = Task(id=task_id, name=name, start_date=BASE,
                end_date=BASE, task_type="Task")
    task.parent_task_id = parent
    return task


def _view_over(project):
    """A withdrawn root and a populated DragDropTaskList."""
    import customtkinter as ctk
    from gantt_app.views.task_list import DragDropTaskList
    root = ctk.CTk()
    root.withdraw()
    view = DragDropTaskList(root, project)
    return root, view


# ------------------------------------------------------------------
# GIVEN
# ------------------------------------------------------------------

@given("a plan nesting a phase four levels deep", target_fixture="ctx")
def a_plan_four_levels_deep():
    if not HAVE_DISPLAY:
        pytest.skip("needs a display")
    project = Project(name="P", start_date=BASE)
    project.add_task(_task("phase", "Phase", None))
    project.add_task(_task("level1", "Level 1", "phase"))
    project.add_task(_task("level2", "Level 2", "level1"))
    project.add_task(_task("level3", "Level 3", "level2"))
    return SimpleNamespace(project=project)


@given("a phase with three children", target_fixture="ctx")
def a_phase_with_three_children():
    if not HAVE_DISPLAY:
        pytest.skip("needs a display")
    project = Project(name="P", start_date=BASE)
    project.add_task(_task("phase", "Phase", None))
    project.add_task(_task("first", "First", "phase"))
    project.add_task(_task("second", "Second", "phase"))
    project.add_task(_task("third", "Third", "phase"))
    return SimpleNamespace(project=project)


@given("a plan holding a task whose parent does not exist",
       target_fixture="ctx")
def a_plan_with_an_orphan():
    if not HAVE_DISPLAY:
        pytest.skip("needs a display")
    project = Project(name="P", start_date=BASE)
    project.add_task(_task("orphan", "Orphan", "gone"))
    return SimpleNamespace(project=project)


@given("a plan holding a two-task parent loop", target_fixture="ctx")
def a_plan_with_a_parent_loop():
    if not HAVE_DISPLAY:
        pytest.skip("needs a display")
    project = Project(name="P", start_date=BASE)
    project.add_task(_task("loopy", "Loopy", "looped"))
    project.add_task(_task("looped", "Looped", "loopy"))
    return SimpleNamespace(project=project)


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------

@when("the task list is populated")
def the_task_list_is_populated(ctx, request):
    ctx.root, ctx.view = _view_over(ctx.project)
    ctx.view.update_task_list()
    request.addfinalizer(lambda: _safe_destroy(ctx.root))


def _safe_destroy(root):
    try:
        root.destroy()
    except Exception:
        pass


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@then(parsers.parse('"{parent}" holds "{child}"'))
def the_row_holds(ctx, parent, child):
    assert child in ctx.view.tree.get_children(parent)


@then(parsers.parse('"{parent}" lists "{a}", "{b}" and "{c}" in that order'))
def the_row_lists_in_order(ctx, parent, a, b, c):
    assert list(ctx.view.tree.get_children(parent)) == [a, b, c]


@then(parsers.parse('"{task_id}" is a top-level row'))
def the_row_is_top_level(ctx, task_id):
    assert task_id in ctx.view.tree.get_children('')
