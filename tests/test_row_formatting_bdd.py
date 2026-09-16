"""
pytest-bdd tests for how a row is painted: the hierarchy, and the
formatting on top.

Run with:
    python3 -m pytest tests/test_row_formatting_bdd.py -q

Display-gated the same way the unittest was: the Given builds a real
CTk root and a DragDropTaskList, so every scenario skips without a
display (CI provides one through xvfb). Rows are inspected through the
tags on them rather than by looking at pixels. Converted from
test_row_formatting.py - every case carried over.
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Project, Task
from gantt_app.core.taskstyle import TaskStyle

pytestmark = [
    pytest.mark.row_formatting,
]

scenarios("features/row_formatting.feature")

BASE = datetime(2026, 7, 6)


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


def _appearance(ctx, task_id: str) -> dict:
    """What the row's own visual tag was configured with."""
    tags = ctx.task_list.tree.item(task_id, 'tags')
    visual = [tag for tag in tags if tag.startswith('row_')]
    assert len(visual) == 1, \
        f"{task_id} should carry exactly one visual tag"
    return ctx.task_list.tree.tag_configure(visual[0])


def _font_of(ctx, task_id: str) -> str:
    """The row's font specification, as Tk stored it."""
    return str(_appearance(ctx, task_id)['font'])


def _style(ctx, task_id: str, style: TaskStyle):
    """Give a task a style and redraw."""
    ctx.project.get_task_by_id(task_id).style = style
    ctx.task_list.update_task_list()


# ------------------------------------------------------------------
# GIVEN
# ------------------------------------------------------------------

@given("a plan with a phase, work under it and a standalone task",
       target_fixture="ctx")
def a_plan_with_a_phase_work_and_a_standalone():
    """Build the window and the list."""
    if not HAVE_DISPLAY:
        pytest.skip("no display")
    import customtkinter as ctk
    from gantt_app.views.task_list import DragDropTaskList

    root = ctk.CTk()
    root.withdraw()

    project = Project(name="Plan")
    project.add_task(Task(id="P1", name="Phase", task_type="Phase",
                          start_date=BASE,
                          end_date=BASE + timedelta(days=10)))
    project.add_task(Task(id="T1", name="Under it", task_type="Task",
                          parent_task_id="P1", start_date=BASE,
                          end_date=BASE + timedelta(days=2)))
    project.add_task(Task(id="T2", name="On its own",
                          task_type="Task", start_date=BASE,
                          end_date=BASE + timedelta(days=2)))
    task_list = DragDropTaskList(root, project)
    root.update_idletasks()
    try:
        yield SimpleNamespace(root=root, project=project,
                              task_list=task_list)
    finally:
        _shut_down(root)


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------

@when(parsers.parse('a subtask is nested under "{task_id}"'))
def a_subtask_is_nested_under(ctx, task_id):
    ctx.project.add_task(Task(id="S1", name="Nested", task_type="Subtask",
                              parent_task_id=task_id, start_date=BASE,
                              end_date=BASE + timedelta(days=1)))
    ctx.task_list.update_task_list()


@when(parsers.parse('the task under "{task_id}" is removed'))
def the_task_under_is_removed(ctx, task_id):
    assert ctx.project.get_subtasks(task_id)[0].id == 'T1'
    ctx.project.remove_task('T1')
    ctx.task_list.update_task_list()


@when(parsers.parse('"{task_id}" is styled with fill "{colour}"'))
def styled_with_fill(ctx, task_id, colour):
    _style(ctx, task_id, TaskStyle(fill_color=colour))


@when(parsers.parse('"{task_id}" is styled with ink "{colour}"'))
def styled_with_ink(ctx, task_id, colour):
    _style(ctx, task_id, TaskStyle(text_color=colour))


@when(parsers.parse('"{task_id}" is styled bold, italic and underlined'))
def styled_with_every_emphasis(ctx, task_id):
    _style(ctx, task_id, TaskStyle(bold=True, italic=True, underline=True))


@when(parsers.parse('"{task_id}" is styled explicitly not bold'))
def styled_explicitly_not_bold(ctx, task_id):
    _style(ctx, task_id, TaskStyle(bold=False))


@when(parsers.parse('"{first_id}" and "{second_id}" are styled with fill '
                    '"{colour}" and bold'))
def two_styled_alike(ctx, first_id, second_id, colour):
    marked = TaskStyle(fill_color=colour, bold=True)
    ctx.project.get_task_by_id(first_id).style = marked
    ctx.project.get_task_by_id(second_id).style = marked
    ctx.task_list.update_task_list()


@when(parsers.parse('"{task_id}" is styled with ink "{colour}" and cut'))
def styled_with_ink_and_cut(ctx, task_id, colour):
    ctx.project.get_task_by_id(task_id).style = TaskStyle(text_color=colour)
    ctx.task_list._cut_task_ids = lambda: {task_id}
    ctx.task_list.update_task_list()


@when(parsers.parse('"{task_id}" is styled with fill "{colour}" and cut'))
def styled_with_fill_and_cut(ctx, task_id, colour):
    ctx.project.get_task_by_id(task_id).style = TaskStyle(fill_color=colour)
    ctx.task_list._cut_task_ids = lambda: {task_id}
    ctx.task_list.update_task_list()


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@then(parsers.parse('the font on "{task_id}" reads bold'))
def the_font_reads_bold(ctx, task_id):
    assert 'bold' in _font_of(ctx, task_id)


@then(parsers.parse('the font on "{task_id}" is not bold'))
def the_font_is_not_bold(ctx, task_id):
    assert 'bold' not in _font_of(ctx, task_id)


@then(parsers.parse('"{task_id}" is a summary row'))
def is_a_summary_row(ctx, task_id):
    assert ctx.task_list.is_summary_row(
        ctx.project.get_task_by_id(task_id))


@then(parsers.parse('"{child_id}" hangs under "{parent_id}" and '
                    '"{parent_id}" hangs at the top'))
def the_child_hangs_under_its_parent(ctx, child_id, parent_id):
    assert ctx.task_list.tree.parent(child_id) == parent_id
    assert ctx.task_list.tree.parent(parent_id) == ''


@then(parsers.parse('the background on "{task_id}" is "{colour}"'))
def the_background_is(ctx, task_id, colour):
    assert str(_appearance(ctx, task_id)['background']) == colour


@then(parsers.parse('the foreground on "{task_id}" is "{colour}"'))
def the_foreground_is(ctx, task_id, colour):
    assert str(_appearance(ctx, task_id)['foreground']) == colour


@then(parsers.parse('the foreground on "{task_id}" is not "{colour}"'))
def the_foreground_is_not(ctx, task_id, colour):
    assert str(_appearance(ctx, task_id)['foreground']) != colour


@then(parsers.parse('the font on "{task_id}" carries bold, italic and '
                    'underline'))
def the_font_carries_every_emphasis(ctx, task_id):
    font = _font_of(ctx, task_id)
    for modifier in ('bold', 'italic', 'underline'):
        assert modifier in font


@then(parsers.parse('the backgrounds on "{first_id}" and "{second_id}" '
                    'differ'))
def the_backgrounds_differ(ctx, first_id, second_id):
    backgrounds = {str(_appearance(ctx, task_id)['background'])
                   for task_id in (first_id, second_id)}
    assert len(backgrounds) == 2, \
        "consecutive rows should band differently"


@then(parsers.parse('the visual tags on "{first_id}" and "{second_id}" '
                    'are the same tag'))
def the_visual_tags_match(ctx, first_id, second_id):
    tags = [next(tag for tag in ctx.task_list.tree.item(task_id, 'tags')
                 if tag.startswith('row_'))
            for task_id in (first_id, second_id)]
    assert tags[0] == tags[1]


@then(parsers.parse('the tags on the new subtask include "{marker}"'))
def the_tags_include(ctx, marker):
    assert marker in ctx.task_list.tree.item('S1', 'tags')


@then("no marker tag paints a colour")
def no_marker_tag_paints_a_colour(ctx):
    for marker in ('subtask', 'cut', 'search_context', 'oddrow',
                   'evenrow'):
        configured = ctx.task_list.tree.tag_configure(marker)
        assert not str(configured.get('background') or ''), marker
        assert not str(configured.get('foreground') or ''), marker
