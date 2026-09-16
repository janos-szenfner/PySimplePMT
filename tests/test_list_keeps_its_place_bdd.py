"""
pytest-bdd tests that the task list survives being rebuilt.

Run with:
    python3 -m pytest tests/test_list_keeps_its_place_bdd.py -q

Display-gated the same way the unittest was: the Given builds a real
CTk root, toolbar and task list, so every scenario skips without a
display (CI provides one through xvfb). The refresh is driven through
the methods the buttons call, which is the same path a press takes.
Converted from test_list_keeps_its_place.py - every case carried over.
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Project, Task

pytestmark = [
    pytest.mark.list_keeps_its_place,
]

scenarios("features/list_keeps_its_place.feature")

BASE = datetime(2026, 8, 19)


def _display_available() -> bool:
    """Whether a usable Tk display is present."""
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
    ttk::ThemeChanged against an interpreter that has already gone,
    which floods stderr with "can't invoke event" tracebacks.
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


def _select(ctx, *task_ids):
    """Select rows, and let the toolbar hear about it."""
    ctx.task_list.tree.selection_set(task_ids)
    ctx.root.update()


# ------------------------------------------------------------------
# GIVEN
# ------------------------------------------------------------------

@given("a toolbar and a list over a small plan", target_fixture="ctx")
def a_toolbar_and_a_list():
    """Build everything, including the refresh the application does."""
    if not HAVE_DISPLAY:
        pytest.skip("no display")
    import customtkinter as ctk

    from gantt_app.utils.undoredo import (
        ProjectStateTracker, UndoRedoManager,
    )
    from gantt_app.views.task_list import DragDropTaskList
    from gantt_app.views.toolbar import Toolbar

    root = ctk.CTk()
    root.withdraw()

    project = Project(name="Plan")
    for task_id, name in (("1", "Előkészítés"),
                          ("2", "Követelmények összegyűjtése"),
                          ("3", "Pénzügyi követelmények"),
                          ("4", "IT követelmények")):
        project.add_task(Task(id=task_id, name=name,
                              task_type="Task", start_date=BASE,
                              end_date=BASE + timedelta(days=1)))

    manager = UndoRedoManager()
    toolbar = Toolbar(root, project, undo_redo_manager=manager)
    task_list = DragDropTaskList(
        root, project,
        project_tracker=ProjectStateTracker(project, manager))
    toolbar.set_task_list(task_list)

    # What the application does when anything changes: rebuild the
    # list. This is the refresh that used to throw the selection away.
    task_list.on_project_changed = task_list.update_task_list
    toolbar.on_project_changed = task_list.update_task_list
    root.update()

    ctx = SimpleNamespace(root=root, project=project, manager=manager,
                          toolbar=toolbar, task_list=task_list,
                          bar=toolbar.icon_toolbar.style_bar)
    try:
        yield ctx
    finally:
        _shut_down(root)


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------

@when(parsers.parse('row "{task_id}" is selected and made bold'))
def row_selected_and_made_bold(ctx, task_id):
    _select(ctx, task_id)
    ctx.toolbar.apply_task_style('bold', True)
    ctx.root.update()


@when(parsers.parse('row "{task_id}" is selected and made bold, italic '
                    'and filled "{colour}"'))
def row_selected_and_styled_thrice(ctx, task_id, colour):
    _select(ctx, task_id)
    ctx.toolbar.apply_task_style('bold', True)
    ctx.root.update()
    ctx.toolbar.apply_task_style('italic', True)
    ctx.root.update()
    ctx.toolbar.apply_task_style('fill_color', colour)
    ctx.root.update()


@when(parsers.parse('row "{task_id}" is selected and indented'))
def row_selected_and_indented(ctx, task_id):
    _select(ctx, task_id)
    ctx.toolbar.indent_selected()
    ctx.root.update()


@when(parsers.parse('row "{task_id}" is selected and indented twice'))
def row_selected_and_indented_twice(ctx, task_id):
    _select(ctx, task_id)
    ctx.toolbar.indent_selected()
    ctx.root.update()
    ctx.toolbar.indent_selected()
    ctx.root.update()


@when(parsers.parse('row "{task_id}" is indented'))
def row_is_indented(ctx, task_id):
    _select(ctx, task_id)
    ctx.toolbar.indent_selected()
    ctx.root.update()


@when("the selection is outdented")
def the_selection_is_outdented(ctx):
    ctx.toolbar.outdent_selected()
    ctx.root.update()


@when(parsers.parse('rows "{first}" and "{second}" are selected and made '
                    'bold'))
def rows_selected_and_made_bold(ctx, first, second):
    _select(ctx, first, second)
    ctx.toolbar.apply_task_style('bold', True)
    ctx.root.update()


@when(parsers.parse('row "{task_id}" is selected and then removed'))
def row_selected_and_removed(ctx, task_id):
    _select(ctx, task_id)
    ctx.project.remove_task(task_id)
    ctx.task_list.update_task_list()


@when(parsers.parse('row "{task_id}" is folded and the list is rebuilt'))
def row_folded_and_list_rebuilt(ctx, task_id):
    ctx.task_list.tree.item(task_id, open=False)
    ctx.task_list.update_task_list()


@when("the list is rebuilt")
def the_list_is_rebuilt(ctx):
    ctx.task_list.update_task_list()


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@then(parsers.re(r'the selection is "(?P<task_id>[^"]+)"$'))
def the_selection_is(ctx, task_id):
    assert ctx.task_list.tree.selection() == (task_id,)


@then(parsers.parse('the selection is "{first}" and "{second}"'))
def the_selection_is_both(ctx, first, second):
    assert set(ctx.task_list.tree.selection()) == {first, second}


@then("nothing is selected")
def nothing_is_selected(ctx):
    assert ctx.task_list.tree.selection() == ()


@then("the formatting bar is enabled")
def the_formatting_bar_is_enabled(ctx):
    assert ctx.bar.enabled


@then(parsers.parse('task "{task_id}" is bold, italic and filled '
                    '"{colour}"'))
def the_task_is_styled_thrice(ctx, task_id, colour):
    style = ctx.project.get_task_by_id(task_id).style
    assert style.bold
    assert style.italic
    assert style.fill_color == colour


@then(parsers.parse('task "{task_id}" sits at outline level {level:d}'))
def the_task_sits_at_outline_level(ctx, task_id, level):
    assert ctx.project.outline_level(task_id) == level


@then(parsers.parse('row "{task_id}" is folded'))
def row_is_folded(ctx, task_id):
    assert not ctx.task_list.tree.item(task_id, 'open')


@then(parsers.parse('row "{task_id}" is open'))
def row_is_open(ctx, task_id):
    assert ctx.task_list.tree.item(task_id, 'open')


@then(parsers.parse('the tree text on "{task_id}" is "{text}"'))
def the_tree_text_is(ctx, task_id, text):
    assert ctx.task_list.tree.item(task_id, 'text') == text


@then(parsers.parse('the tree has an "{column}" column headed '
                    '"{heading}"'))
def the_tree_has_a_column(ctx, column, heading):
    assert column in ctx.task_list.tree.cget('columns')
    assert ctx.task_list.tree.heading(column, 'text') == heading


@then(parsers.parse('row "{task_id}" shows outline level "{level}"'))
def row_shows_outline_level(ctx, task_id, level):
    assert ctx.task_list.tree.set(task_id, 'Outline') == level


@then(parsers.parse('row "{task_id}" hangs under "{parent_id}"'))
def row_hangs_under(ctx, task_id, parent_id):
    assert ctx.task_list.tree.parent(task_id) == parent_id


@then(parsers.parse('row "{task_id}" hangs at the top'))
def row_hangs_at_the_top(ctx, task_id):
    assert ctx.task_list.tree.parent(task_id) == ''
