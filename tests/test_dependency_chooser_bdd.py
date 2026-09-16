"""
pytest-bdd tests for the dependency editor's candidate chooser.

Run with:
    python3 -m pytest tests/test_dependency_chooser_bdd.py -q

The scenarios drive the real widget, so they skip without a display.
Converted from test_dependency_chooser.py - every case carried over.
"""
import time
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest import mock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Project, Task
from gantt_app.views.dependency_editor import DependencyEditor

pytestmark = [
    pytest.mark.dependency_chooser,
]

scenarios("features/dependency_chooser.feature")

BASE = datetime(2026, 8, 19)


def _display_available() -> bool:
    try:
        import tkinter
        root = tkinter.Tk()
    except Exception:
        return False
    root.destroy()
    return True


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


def _editor_over(size):
    """A plan of that many tasks and an editor for its first."""
    import customtkinter as ctk

    root = ctk.CTk()
    root.withdraw()

    project = Project(name="Plan")
    for number in range(1, size + 1):
        project.add_task(Task(
            id=str(number).zfill(3), name=f"Task {number}",
            start_date=BASE + timedelta(days=number),
            end_date=BASE + timedelta(days=number + 1),
            task_type="Task"))

    editor = DependencyEditor(root, project, project.tasks[0])
    return root, project, editor


# ------------------------------------------------------------------
# GIVEN - needs a display
# ------------------------------------------------------------------

@given(parsers.parse("an editor over a {size:d}-task plan"),
       target_fixture="ctx")
def an_editor_over_a_plan(size):
    if not HAVE_DISPLAY:
        pytest.skip("needs a display")
    root, project, editor = _editor_over(size)
    yield SimpleNamespace(root=root, project=project, editor=editor)
    _shut_down(root)


@given(parsers.parse('tasks "{csv}" share the name "{name}"'))
def tasks_share_the_name(ctx, csv, name):
    for task_id in csv.split(","):
        ctx.project.get_task_by_id(task_id).name = name


@given("the chooser is refreshed")
def the_chooser_is_refreshed(ctx):
    ctx.editor.refresh(notify=False)


@given("the first task sits in a summary the second waits on")
def the_first_task_in_a_summary(ctx):
    from gantt_app.core.models import Dependency

    parent = Task(id="S", name="Summary", task_type="Phase",
                  start_date=BASE, end_date=BASE + timedelta(days=40))
    ctx.project.add_task(parent)
    # The task being edited becomes a child of the summary.
    ctx.project.tasks[0].parent_task_id = parent.id
    # The candidate waits on the summary, so it waits on the child.
    ctx.project.get_task_by_id("002").dependencies = [
        Dependency("S", "FS", "Hard")]
    ctx.editor.refresh(notify=False)


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------

@when("the chooser is refreshed while counting hierarchy walks")
def refreshed_counting_walks(ctx):
    counted = {'n': 0}
    real = Project.display_order

    def counting(project):
        counted['n'] += 1
        return real(project)

    Project.display_order = counting
    try:
        ctx.editor.refresh(notify=False)
    finally:
        Project.display_order = real
    ctx.walks = counted['n']


@when("a small editor and the large editor are each refreshed")
def both_editors_refreshed(ctx):
    small = Project(name="Small")
    small.add_task(Task(id="001", name="Only", start_date=BASE,
                        end_date=BASE, task_type="Task"))
    small_editor = DependencyEditor(ctx.root, small, small.tasks[0])

    start = time.time()
    small_editor.refresh(notify=False)
    ctx.one_row = time.time() - start

    start = time.time()
    ctx.editor.refresh(notify=False)
    ctx.forty_rows = time.time() - start

    small_editor.destroy()


@when("the shown candidate is added")
def the_shown_candidate_is_added(ctx):
    ctx.chosen = ctx.editor.candidate_var.get()
    ctx.editor.add_selected()


@when("the third candidate is added")
def the_third_candidate_is_added(ctx):
    values = ctx.editor.candidate_menu.cget('values')
    ctx.chosen = values[2]
    ctx.editor.candidate_var.set(values[2])
    ctx.editor.add_selected()


@when(parsers.parse('the label "{label}" is added'))
def a_label_that_names_nothing_is_added(ctx, label):
    ctx.editor.candidate_var.set(label)
    with mock.patch(
            'gantt_app.views.dependency_editor.messagebox.showinfo'
    ) as prompt:
        ctx.editor.add_selected()
    ctx.prompt = prompt


@when(parsers.parse('the candidate ending "{suffix}" is added'))
def the_candidate_ending_is_added(ctx, suffix):
    values = ctx.editor.candidate_menu.cget('values')
    label = next(v for v in values if v.endswith(suffix))
    ctx.editor.candidate_var.set(label)
    with mock.patch(
            'gantt_app.views.dependency_editor.messagebox.showerror'
    ) as prompt:
        ctx.editor.add_selected()
    ctx.prompt = prompt


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@then(parsers.parse('task "{task_id}" is labelled "{label}"'))
def task_is_labelled(ctx, task_id, label):
    numbers = ctx.project.display_ids()
    task = ctx.project.get_task_by_id(task_id)
    assert ctx.editor._label_for(task, numbers) == label


@then("every candidate label is distinct")
def every_candidate_label_is_distinct(ctx):
    numbers = ctx.project.display_ids()
    labels = [ctx.editor._label_for(task, numbers)
              for task in ctx.editor.candidate_tasks()]
    assert len(labels) == len(set(labels))


@then(parsers.parse('a stray task is labelled "{label}"'))
def a_stray_task_is_labelled(ctx, label):
    stray = Task(id="999", name="Elsewhere", start_date=BASE,
                 end_date=BASE, task_type="Task")
    assert ctx.editor._label_for(stray, {}) == label


@then("the plan was walked once")
def the_plan_was_walked_once(ctx):
    assert ctx.walks == 1


@then("the large refresh stays within the shape bound")
def the_large_refresh_stays_in_bound(ctx):
    assert ctx.forty_rows < max(ctx.one_row * 40, 0.5)


@then("one link was made")
def one_link_was_made(ctx):
    assert len(ctx.editor.links) == 1


@then("no link was made")
def no_link_was_made(ctx):
    assert ctx.editor.links == []


@then("it links the task the label names")
def it_links_the_named_task(ctx):
    linked = ctx.project.get_task_by_id(ctx.editor.links[0].task_id)
    assert ctx.chosen.endswith(linked.name)


@then("the linked task is the one the third label names")
def the_linked_task_is_the_third(ctx):
    linked = ctx.project.get_task_by_id(ctx.editor.links[0].task_id)
    assert ctx.chosen == (f"{ctx.project.display_id(linked.id)} - "
                          f"{linked.name}")


@then("the user was told")
def the_user_was_told(ctx):
    assert ctx.prompt.called, "the user was told nothing"


@then("the user was shown the error")
def the_user_was_shown_the_error(ctx):
    assert ctx.prompt.called, "the user was told nothing"


@then("that label no longer appears among the candidates")
def that_label_no_longer_appears(ctx):
    values = ctx.editor.candidate_menu.cget('values')
    assert ctx.chosen not in values
