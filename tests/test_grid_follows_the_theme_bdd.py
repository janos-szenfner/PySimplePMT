"""
pytest-bdd tests for the grid repainting when the appearance changes.

Run with:
    python3 -m pytest tests/test_grid_follows_the_theme_bdd.py -q

The scenarios drive the real widget, so they skip without a display.
Converted from test_grid_follows_the_theme.py - every case carried
over.
"""
from datetime import datetime
from types import SimpleNamespace

import pytest
from pytest_bdd import given, scenarios, then, when

from gantt_app.core.models import Project, Task
from gantt_app.views import theme

pytestmark = [
    pytest.mark.grid_follows_the_theme,
]

scenarios("features/grid_follows_the_theme.feature")


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


def _fills(task_list):
    """The background each row is actually painted with."""
    painted = {}
    for task_id in ("A", "B", "C"):
        tags = [tag for tag in task_list.tree.item(task_id, 'tags')
                if tag.startswith('row_')]
        painted[task_id] = str(
            task_list.tree.tag_configure(tags[0], 'background'))
    return painted


# ------------------------------------------------------------------
# GIVEN - needs a display
# ------------------------------------------------------------------

@given("a task list over three rows in the light appearance",
       target_fixture="ctx")
def a_task_list_in_the_light_appearance():
    if not HAVE_DISPLAY:
        pytest.skip("needs a display")
    import customtkinter as ctk
    from gantt_app.utils.undoredo import (
        ProjectStateTracker, UndoRedoManager,
    )
    from gantt_app.views.task_list import DragDropTaskList

    opening_mode = str(ctk.get_appearance_mode())
    ctk.set_appearance_mode('light')

    root = ctk.CTk()
    root.withdraw()

    base = datetime(2026, 1, 5)
    project = Project(name="Plan")
    for task_id in ("A", "B", "C"):
        project.add_task(Task(id=task_id, name=task_id, task_type="Task",
                              start_date=base, end_date=base, duration=2))

    task_list = DragDropTaskList(
        root, project,
        project_tracker=ProjectStateTracker(project, UndoRedoManager()))
    task_list.update_task_list()
    root.update_idletasks()

    yield SimpleNamespace(root=root, project=project,
                          task_list=task_list, ctk=ctk)

    _shut_down(root)
    try:
        ctk.set_appearance_mode(opening_mode)
    except Exception:
        pass


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------

@when("the appearance goes dark")
def the_appearance_goes_dark(ctx):
    ctx.before = len(set(_fills(ctx.task_list).values()))
    ctx.ctk.set_appearance_mode('dark')
    ctx.task_list.apply_theme()
    ctx.root.update_idletasks()


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@then("every row fill is a light colour")
def every_row_fill_is_a_light_colour(ctx):
    light = {theme.GRID_ROW_BG[0], theme.GRID_ROW_ALT[0]}
    assert set(_fills(ctx.task_list).values()) <= light


@then("every row fill is a dark colour")
def every_row_fill_is_a_dark_colour(ctx):
    dark = {theme.GRID_ROW_BG[1], theme.GRID_ROW_ALT[1]}
    assert set(_fills(ctx.task_list).values()) <= dark


@then("the rows still alternate in as many shades as before")
def the_banding_survives(ctx):
    assert len(set(_fills(ctx.task_list).values())) == ctx.before


@then("the row text is the dark ink")
def the_row_text_is_the_dark_ink(ctx):
    tags = [tag for tag in ctx.task_list.tree.item('A', 'tags')
            if tag.startswith('row_')]
    ink = str(ctx.task_list.tree.tag_configure(tags[0], 'foreground'))
    assert ink == theme.GRID_TEXT[1]


@then("the grid's field background is the dark row colour")
def the_grids_field_background_is_dark(ctx):
    import tkinter.ttk as ttk
    style = ttk.Style()
    assert style.lookup('Gantt.Treeview', 'fieldbackground') == \
        theme.GRID_ROW_BG[1]
