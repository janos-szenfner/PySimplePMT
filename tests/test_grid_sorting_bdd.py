"""
pytest-bdd tests for sorting and autofiltering the task grid.

Run with:
    python3 -m pytest tests/test_grid_sorting_bdd.py -q

Issues #45 (the three-level Sort By), #46 (heading-click sorting) and
#81 (the AutoFilter dropdowns) all live on the same view state: a row
of sort keys and a per-column tick map, both applied when the tree is
built and neither touching the plan's own order. The ordering and the
checklist answers are pure helpers, so most scenarios run without a
display; the @display_dependent ones drive a real tree and skip where
no display exists.
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Project, Task
from gantt_app.views import gridsort
from gantt_app.views.gridfilter import (
    autofilter_values, autofilter_visible_ids)

pytestmark = [
    pytest.mark.grid_sorting,
]

scenarios("features/grid_sorting.feature")

BASE = datetime(2026, 1, 5)  # a Monday


def _sorting_plan() -> Project:
    """
    The plan every scenario shares.

    Roots in plan order: the phase P (three sub-tasks), the milestone M,
    and the tasks E and C. P spans Jan 5-30 - twenty working days; C
    holds thirteen, E five, the milestone none. A, B and D all hold five
    days, so the multi-level scenario is decided by Start and Progress
    alone; only E carries a deadline, so Deadline sorts one real value
    over a run of blanks.
    """
    project = Project(name="Plan")
    phase = Task.create_phase("Phase One", BASE,
                              BASE + timedelta(days=25), task_id="P")
    # create_phase leaves the finish for the roll-up to answer; here the
    # span is stated so the Duration column reads the twenty days the
    # sort is asked about.
    phase.end_date = BASE + timedelta(days=25)
    project.add_task(phase)
    project.add_task(Task(id="A", name="Draft artwork", task_type="Task",
                          start_date=BASE,
                          end_date=BASE + timedelta(days=4),
                          progress=10, label="design",
                          parent_task_id="P"))
    project.add_task(Task(id="B", name="Build chart", task_type="Task",
                          start_date=BASE,
                          end_date=BASE + timedelta(days=4),
                          progress=90, parent_task_id="P"))
    project.add_task(Task(id="D", name="Review", task_type="Task",
                          start_date=BASE + timedelta(days=7),
                          end_date=BASE + timedelta(days=11),
                          progress=50, parent_task_id="P"))
    project.add_task(Task.create_milestone(
        "Sign-off", BASE + timedelta(days=28), task_id="M"))
    project.add_task(Task(id="E", name="Estimate", task_type="Task",
                          start_date=BASE,
                          end_date=BASE + timedelta(days=4),
                          progress=20,
                          deadline=BASE + timedelta(days=15)))
    project.add_task(Task(id="C", name="Checklist", task_type="Task",
                          start_date=BASE,
                          end_date=BASE + timedelta(days=16),
                          progress=30))
    return project


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


def _siblings(project, parent_id=None):
    """A level of the outline in plan order - the sort's unit."""
    return [task for task in project.tasks
            if (task.parent_task_id or None) == parent_id]


def _sorted_ids(project, keys, parent_id=None):
    """What the tree would draw at one level under the given sort."""
    return [task.id for task in
            gridsort.sort_tasks(_siblings(project, parent_id),
                                keys, project)]


# ------------------------------------------------------------------
# GIVEN
# ------------------------------------------------------------------

@given("a plan whose rows are out of order", target_fixture="ctx")
def a_plan_whose_rows_are_out_of_order():
    return SimpleNamespace(project=_sorting_plan(), keys=[])


@given("a toolbar and a list over the sorting plan", target_fixture="ctx")
def a_toolbar_and_a_list_over_the_sorting_plan():
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

    project = _sorting_plan()
    manager = UndoRedoManager()
    toolbar = Toolbar(root, project, undo_redo_manager=manager)
    task_list = DragDropTaskList(
        root, project,
        project_tracker=ProjectStateTracker(project, manager))
    toolbar.set_task_list(task_list)
    task_list.on_project_changed = task_list.update_task_list
    toolbar.on_project_changed = task_list.update_task_list
    root.update()

    ctx = SimpleNamespace(root=root, project=project, manager=manager,
                          toolbar=toolbar, task_list=task_list)
    try:
        yield ctx
    finally:
        _shut_down(root)


def _set_sort(ctx, *pairs):
    """The sort state the scenario starts from, as (column, dir) keys."""
    ctx.keys = [
        (column, 'desc' if direction == 'descending' else 'asc')
        for column, direction in pairs]


@given(parsers.parse('the sort is "{column}" {direction}'))
def the_sort_is(ctx, column, direction):
    _set_sort(ctx, (column, direction))


@when(parsers.parse('the sort is "{column}" {direction} and '
                    '"{column2}" {direction2}'))
def the_sort_is_two_levels(ctx, column, direction, column2, direction2):
    _set_sort(ctx, (column, direction), (column2, direction2))


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------

@when(parsers.parse('the "{column}" heading is clicked {times}'))
def the_heading_is_clicked(ctx, column, times):
    """next_column_sort is exactly what a heading press runs."""
    ctx.keys = gridsort.next_column_sort(ctx.keys, column)


@when(parsers.parse('the grid is sorted by "{column}" "{direction}"'))
def the_grid_is_sorted(ctx, column, direction):
    ctx.keys = [(column,
                 'desc' if direction == 'descending' else 'asc')]


@when(parsers.parse('the grid is sorted in levels by "{c1}" "{d1}", '
                    'then "{c2}" "{d2}", then "{c3}" "{d3}"'))
def the_grid_is_sorted_three_levels(ctx, c1, d1, c2, d2, c3, d3):
    def key(column, direction):
        return (column, 'desc' if direction == 'descending' else 'asc')
    ctx.keys = [key(c1, d1), key(c2, d2), key(c3, d3)]


@when(parsers.parse('the autofilter keeps "{values}" in the '
                    '"{column}" column'))
def the_autofilter_keeps(ctx, values, column):
    ctx.allowed = {column: set(values.split(','))}
    ctx.visible = autofilter_visible_ids(ctx.project, ctx.allowed)


@when(parsers.parse('the autofilter keeps nothing in the '
                    '"{column}" column'))
def the_autofilter_keeps_nothing(ctx, column):
    ctx.allowed = {column: set()}
    ctx.visible = autofilter_visible_ids(ctx.project, ctx.allowed)


@when(parsers.parse('the "{column}" heading is pressed'))
def the_heading_is_pressed(ctx, column):
    ctx.task_list._heading_pressed(column)
    ctx.root.update()


@when("AutoFilter is switched on")
def autofilter_is_switched_on(ctx):
    ctx.toolbar.toggle_autofilter(True)
    ctx.root.update()


@when("AutoFilter is switched off")
def autofilter_is_switched_off(ctx):
    ctx.toolbar.toggle_autofilter(False)
    ctx.root.update()


@when(parsers.parse('the "{column}" dropdown is opened and only '
                    '"{value}" is kept'))
def the_dropdown_keeps_only(ctx, column, value):
    """
    The real popup, driven the way its Apply button is.

    The checklist's variables are set to keep the named value alone -
    the same end state as unticking the rest - then Apply runs, which
    hands the ticked set to the list exactly as a click does.
    """
    # No root.update() while the popup lives: a CTkToplevel reschedules
    # its own polling with after(), so the queue never empties and
    # update() would spin forever. None of this needs it - the build is
    # synchronous and _apply drives the list's rebuild itself.
    ctx.task_list._open_autofilter(column)
    popup = ctx.task_list._autofilter_popup
    assert popup is not None
    for text, var in popup._vars.items():
        var.set(text == value)
    popup._apply()
    ctx.root.update()


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@then(parsers.parse('the sort keys are "{column}" {direction}'))
def the_sort_keys_are(ctx, column, direction):
    expected = 'desc' if direction == 'descending' else 'asc'
    assert ctx.keys == [(column, expected)]


@then("there is no sort")
def there_is_no_sort(ctx):
    assert ctx.keys == []


@then(parsers.parse('the roots come in the order "{order}"'))
def the_roots_come_in_the_order(ctx, order):
    assert _sorted_ids(ctx.project, ctx.keys) == order.split(',')


@then(parsers.parse('the children of "{parent}" come in the order '
                    '"{order}"'))
def the_children_come_in_the_order(ctx, parent, order):
    assert _sorted_ids(ctx.project, ctx.keys, parent_id=parent) \
        == order.split(',')


@then(parsers.parse('the "{column}" heading reads "{marker}"'))
def the_heading_reads(ctx, column, marker):
    assert gridsort.sort_indicator(column, ctx.keys) == marker


@then(parsers.parse('the "{column}" heading reads ""'))
def the_heading_reads_nothing(ctx, column):
    assert gridsort.sort_indicator(column, ctx.keys) == ''


@then(parsers.parse('the visible roots are "{order}"'))
def the_visible_roots_are(ctx, order):
    roots = [task.id for task in ctx.project.get_root_tasks()
             if task.id in ctx.visible]
    assert roots == order.split(',')


@then(parsers.parse('the visible rows are "{order}"'))
def the_visible_rows_are(ctx, order):
    rows = [task.id for task in ctx.project.tasks
            if task.id in ctx.visible]
    assert rows == order.split(',')


@then("no rows are visible")
def no_rows_are_visible(ctx):
    assert ctx.visible == set()


@then(parsers.parse('the "{column}" column offers "{values}"'))
def the_column_offers(ctx, column, values):
    assert autofilter_values(ctx.project, column) == values.split(',')


@then(parsers.parse('the grid rows are "{order}"'))
def the_grid_rows_are(ctx, order):
    rows = [item for item in ctx.task_list._rows_in_display_order()
            if item not in ctx.task_list._blank_set]
    assert rows == order.split(',')


@then(parsers.parse('the "{column}" heading wears "{marker}"'))
def the_heading_wears(ctx, column, marker):
    text = ctx.task_list.tree.heading(column, 'text')
    assert marker in text
