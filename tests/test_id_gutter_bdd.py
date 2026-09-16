"""
pytest-bdd tests for the fixed "No" gutter down the left of the task list.

Run with:
    python3 -m pytest tests/test_id_gutter_bdd.py -q

The gutter is a real tree widget, so these need a display. Converted
from test_id_gutter.py - every case carried over.
"""
from datetime import datetime
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Project, Task

pytestmark = [
    pytest.mark.id_gutter,
]

scenarios("features/id_gutter.feature")


def _display_available() -> bool:
    try:
        import tkinter
        root = tkinter.Tk()
    except Exception:
        return False
    root.destroy()
    return True


HAVE_DISPLAY = _display_available()


# ------------------------------------------------------------------
# GIVEN
# ------------------------------------------------------------------

@given("a task list over a mixed plan", target_fixture="ctx")
def a_task_list_over_a_mixed_plan():
    if not HAVE_DISPLAY:
        pytest.skip("needs a display")
    import customtkinter as ctk
    from gantt_app.views.task_list import DragDropTaskList

    root = ctk.CTk()
    root.withdraw()
    project = Project(name="P", start_date=datetime(2026, 1, 1))
    # A phase with a child, a milestone, and a plain task - a mix of
    # types and depths, so the numbering can be shown to be uniform.
    project.add_task(Task(
        id="a", name="Phase", start_date=datetime(2026, 1, 1),
        end_date=datetime(2026, 1, 8), task_type="Phase"))
    project.add_task(Task(
        id="b", name="Child", start_date=datetime(2026, 1, 1),
        end_date=datetime(2026, 1, 3), task_type="Subtask",
        parent_task_id="a"))
    project.add_task(Task(
        id="m", name="Gate", start_date=datetime(2026, 1, 9),
        task_type="Milestone"))
    project.add_task(Task(
        id="c", name="Task2", start_date=datetime(2026, 1, 12),
        end_date=datetime(2026, 1, 14)))
    view = DragDropTaskList(root, project)
    view.update_task_list()
    ctx = SimpleNamespace(root=root, project=project, view=view)
    yield ctx
    try:
        root.destroy()
    except Exception:
        pass


def _gutter(ctx):
    tree = ctx.view.id_tree
    return [tree.item(i, 'text') for i in tree.get_children('')]


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------

@when(parsers.parse('the "{name}" branch is folded away'))
def the_branch_is_folded_away(ctx, name):
    task_id = next(t.id for t in ctx.project.tasks if t.name == name)
    ctx.view.tree.item(task_id, open=False)
    ctx.view._refresh_id_gutter()


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@then(parsers.parse('the main tree has no "{column}" column'))
def the_main_tree_has_no_column(ctx, column):
    assert column not in ctx.view.tree.cget('columns')


@then(parsers.parse('the gutter\'s header reads "{text}"'))
def the_gutter_header_reads(ctx, text):
    assert ctx.view.id_tree.heading('#0', 'text') == text


@then(parsers.parse('the gutter reads "{a}", "{b}", "{c}" and "{d}"'))
def the_gutter_reads_four(ctx, a, b, c, d):
    assert _gutter(ctx) == [a, b, c, d]


@then(parsers.parse('the gutter reads "{a}", "{b}" and "{c}"'))
def the_gutter_reads_three(ctx, a, b, c):
    assert _gutter(ctx) == [a, b, c]


@then("the gutter holds as many numbers as there are visible rows")
def the_gutter_mirrors_the_rows(ctx):
    assert len(_gutter(ctx)) == len(ctx.view.visible_rows())


@then(parsers.parse('the visible rows are "{a}", "{b}" and "{c}"'))
def the_visible_rows_are(ctx, a, b, c):
    assert ctx.view.visible_rows() == [a, b, c]


@then("the gutter accepts no selection")
def the_gutter_is_read_only(ctx):
    assert str(ctx.view.id_tree.cget('selectmode')) == 'none'
