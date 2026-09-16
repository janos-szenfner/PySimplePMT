"""
pytest-bdd tests for the completion field and the roll-up.

Run with:
    python3 -m pytest tests/test_progress_field_bdd.py -q

The editor scenarios skip without a display; the roll-up scenarios are
model-only. Converted from test_progress_field.py - every case carried
over.
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Project, Task

pytestmark = [
    pytest.mark.progress_field,
]

scenarios("features/progress_field.feature")

BASE = datetime(2026, 1, 13)


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


def _editor_for(ctx, task_id):
    """The edit dialog for one row, built but never shown."""
    from gantt_app.views.taskdialogs import EditTaskDialog

    def nothing(*_args, **_kwargs):
        """A callback the dialog needs and this test does not."""

    task = ctx.project.get_task_by_id(task_id)
    dialog = EditTaskDialog(ctx.root, task, ctx.project, nothing, nothing)
    dialog.withdraw()
    return dialog


def _subtask(progress):
    """A sub-task at a given percentage."""
    return Task(id=f"s{progress}", name="s", start_date=BASE,
                end_date=BASE, task_type="Subtask", progress=progress)


def _rolled(percentages):
    """What a Task holding those sub-tasks reads."""
    from gantt_app.core.models import rolled_up_progress

    parent = Task(id="T", name="t", start_date=BASE, end_date=BASE,
                  task_type="Task")
    return rolled_up_progress(parent, [_subtask(p) for p in percentages])


# ------------------------------------------------------------------
# GIVEN
# ------------------------------------------------------------------

@given("a plan with a phase, tasks, a subtask and a milestone",
       target_fixture="ctx")
def a_plan_with_a_row_of_every_type():
    if not HAVE_DISPLAY:
        pytest.skip("needs a display")
    import customtkinter as ctk

    root = ctk.CTk()
    root.withdraw()

    project = Project(name="Plan")
    rows = (
        ("001", "Preparation", "Phase", None),
        ("002", "Handover", "Task", "001"),
        ("003", "Implementation", "Task", "001"),
        ("004", "Defining goals", "Subtask", "003"),
        ("005", "Sign-off", "Milestone", None),
    )
    for task_id, name, task_type, parent in rows:
        project.add_task(Task(
            id=task_id, name=name, start_date=BASE, end_date=BASE,
            task_type=task_type, parent_task_id=parent))

    yield SimpleNamespace(root=root, project=project)

    _shut_down(root)


@given("a nested plan with a subtask at 60 percent", target_fixture="ctx")
def a_nested_plan_with_a_subtask_at_60():
    project = Project(name="Plan")
    rows = (("001", "Preparation", "Phase", None, 0),
            ("003", "Implementation", "Task", "001", 0),
            ("004", "Goals", "Subtask", "003", 60),
            ("005", "Criteria", "Subtask", "003", 0),
            ("006", "Scope", "Subtask", "003", 100))
    for task_id, name, task_type, parent, progress in rows:
        project.add_task(Task(id=task_id, name=name, start_date=BASE,
                              end_date=BASE, task_type=task_type,
                              parent_task_id=parent, progress=progress))
    return SimpleNamespace(project=project)


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------

@when("the summaries are rolled up")
def the_summaries_are_rolled_up(ctx):
    ctx.project.roll_up_summaries()


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@then(parsers.parse('the editor for "{task_id}" offers a percentage box'))
def the_editor_offers_a_percentage(ctx, task_id):
    assert _editor_for(ctx, task_id).progress_entry is not None


@then(parsers.parse('the editors for "{csv}" offer a percentage box'))
def the_editors_offer_a_percentage(ctx, csv):
    for task_id in csv.split(","):
        assert _editor_for(ctx, task_id).progress_entry is not None, \
            f"{task_id} has no progress box"


@then(parsers.parse('the editors for "{csv}" offer no tick'))
def the_editors_offer_no_tick(ctx, csv):
    for task_id in csv.split(","):
        editor = _editor_for(ctx, task_id)
        assert not hasattr(editor, 'progress_done_var'), \
            f"{task_id} still has a tick"


@then("the progress builder's source names no platform")
def the_progress_builder_names_no_platform():
    import inspect

    from gantt_app.views import taskform

    source = inspect.getsource(taskform.TaskFormDialog._build_progress)
    for machine_dependent in ('platform', 'sys.', 'darwin',
                              'winfo_screen'):
        assert machine_dependent not in source


@then("every checklist rolls up to its proportion ticked")
def every_checklist_rolls_up():
    for percentages in ([0, 0, 0, 0], [100, 0], [100, 100, 0, 0],
                        [100, 100], [100, 0, 0]):
        ticked = round(sum(1 for p in percentages if p >= 100)
                       / len(percentages) * 100)
        assert _rolled(percentages) == ticked, \
            f"{percentages} used to read {ticked}%"


@then(parsers.parse('subtasks "{csv}" roll up to {expected:d}'))
def subtasks_roll_up_to(csv, expected):
    percentages = [int(p) for p in csv.split(",")]
    assert _rolled(percentages) == expected


@then("a done one-day subtask and an empty twenty-day one average to 50")
def counted_rather_than_weighted():
    from gantt_app.core.models import rolled_up_progress

    short = Task(id="a", name="a", start_date=BASE,
                 end_date=BASE + timedelta(days=1),
                 task_type="Subtask", progress=100)
    long = Task(id="b", name="b", start_date=BASE,
                end_date=BASE + timedelta(days=20),
                task_type="Subtask", progress=0)
    parent = Task(id="T", name="t", start_date=BASE, end_date=BASE,
                  task_type="Task")

    assert rolled_up_progress(parent, [short, long]) == 50


@then(parsers.parse('tasks "{csv}" read {percent:d} percent'))
def tasks_read_percent(ctx, csv, percent):
    for task_id in csv.split(","):
        assert ctx.project.get_task_by_id(task_id).progress == percent
