"""
pytest-bdd tests for Link Tasks and Unlink Tasks.

Run with:
    python3 -m pytest tests/test_link_tasks_bdd.py -q

Everything here is model-level: the plan, the tracker and the stand-in
key events. Nothing opens a window.
"""
import logging
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Project, Task
from gantt_app.resources.icons import (
    ACTIVE_WHEN_PROJECT_OPEN, ICON_STROKES, draw_icon,
)
from gantt_app.utils.shortcuts import (
    IS_MACOS, MODIFIER, accelerator, sequences,
)
from gantt_app.utils.undoredo import (
    ProjectStateTracker, SnapshotCommand, UndoRedoManager,
)
from gantt_app.views.toolbar import IconToolbar, Toolbar

pytestmark = [
    pytest.mark.link_tasks,
]

scenarios("features/link_tasks.feature")

BASE = datetime(2026, 8, 19)


@pytest.fixture
def ctx():
    return SimpleNamespace(project=None, made=None, manager=None,
                           tracker=None, before=None, after=None,
                           task=None)


def _four(project):
    for task_id, name in (("001", "Alpha"), ("002", "Beta"),
                          ("003", "Gamma"), ("004", "Delta")):
        project.add_task(Task(id=task_id, name=name, start_date=BASE,
                              end_date=BASE + timedelta(days=2),
                              task_type="Task"))


def _links(ctx, task_id):
    task = ctx.project.get_task_by_id(task_id)
    return [link.task_id for link in task.dependencies]


def _pairs(text):
    """Turn "001 > 002, 002 > 003" into a list of id pairs."""
    return [tuple(pair.split(' > ')) for pair in text.split(', ')]


def _dates(ctx):
    return [(t.id, t.start_date, t.end_date) for t in ctx.project.tasks]


# ------------------------------------------------------------------
# chaining
# ------------------------------------------------------------------

@given("a plan of four unlinked tasks")
def a_plan_of_four(ctx):
    ctx.project = Project(name="Plan")
    _four(ctx.project)


@given(parsers.parse('"{task_id}" already waits for "{pred_id}"'))
@given(parsers.parse('"{task_id}" also waits for "{pred_id}"'))
def a_task_waits_for(ctx, task_id, pred_id):
    ctx.project.get_task_by_id(task_id).add_dependency(pred_id)


@given(parsers.parse('"{ids}" are linked'))
@when(parsers.parse('"{ids}" are linked'))
@when(parsers.parse('"{ids}" are linked again'))
def ids_are_linked(ctx, ids):
    ctx.made = ctx.project.link_tasks([i.strip() for i in
                                       ids.split(',')])


@when(parsers.parse('"{task_id}" is linked alone'))
def one_is_linked(ctx, task_id):
    ctx.made = ctx.project.link_tasks([task_id])


@when("the whole plan is linked")
def the_whole_plan_is_linked(ctx):
    ctx.made = ctx.project.link_tasks(
        [t.id for t in ctx.project.tasks])


@when(parsers.parse('"{ids}" are unlinked'))
def ids_are_unlinked(ctx, ids):
    ctx.made = ctx.project.unlink_tasks([i.strip() for i in
                                         ids.split(',')])


@when(parsers.parse('"{task_id}" is unlinked alone'))
def one_is_unlinked(ctx, task_id):
    ctx.made = ctx.project.unlink_tasks([task_id])


@when("nothing is unlinked")
def nothing_is_unlinked(ctx):
    ctx.made = ctx.project.unlink_tasks([])


@then(parsers.parse('"{task_id}" waits for nothing'))
def waits_for_nothing(ctx, task_id):
    assert _links(ctx, task_id) == []


@then(parsers.parse('"{task_id}" waits for "{pred_id}"'))
def waits_for(ctx, task_id, pred_id):
    assert _links(ctx, task_id) == [pred_id]


@then(parsers.parse('"{task_id}" waits on both "{first_id}" and '
                    '"{second_id}"'))
def waits_on_both(ctx, task_id, first_id, second_id):
    assert sorted(_links(ctx, task_id)) == sorted([first_id, second_id])


@then(parsers.parse('the link into "{task_id}" from "{pred_id}" is a '
                    'hard finish-to-start'))
def the_link_is_hard_fs(ctx, task_id, pred_id):
    link = ctx.project.get_task_by_id(task_id).get_dependency(pred_id)
    assert link.dep_type == 'FS'
    assert link.lag == 0
    assert link.hardness == 'Hard'


@then(parsers.parse('the pairs joined are "{pairs}"'))
def the_pairs_joined_are(ctx, pairs):
    assert ctx.made == _pairs(pairs)


@then(parsers.parse('the pairs broken are "{pairs}"'))
def the_pairs_broken_are(ctx, pairs):
    assert sorted(ctx.made) == _pairs(pairs)


@then("nothing was joined")
def nothing_was_joined(ctx):
    assert ctx.made == []


@then("nothing was broken")
def nothing_was_broken(ctx):
    assert ctx.made == []


# ------------------------------------------------------------------
# undo
# ------------------------------------------------------------------

@given("two unlinked tasks tracked for undo")
def two_tasks_tracked(ctx):
    ctx.project = Project(name="Plan")
    for task_id, name in (("001", "Alpha"), ("002", "Beta")):
        ctx.project.add_task(Task(id=task_id, name=name,
                                  start_date=BASE,
                                  end_date=BASE + timedelta(days=2),
                                  task_type="Task"))
    ctx.manager = UndoRedoManager()
    ctx.tracker = ProjectStateTracker(ctx.project, ctx.manager)
    ctx.before = _dates(ctx)


@when("the link is made the way the task list makes it")
def the_link_is_made(ctx):
    def apply():
        """The link, and the dates it moves."""
        if not ctx.project.link_tasks(["001", "002"]):
            return False
        ctx.project.apply_schedule()
        return True

    ctx.tracker.run_as_command(apply, "Link Tasks")
    ctx.after = _dates(ctx)


@when("undo is run")
def undo_is_run(ctx):
    ctx.manager.undo()


@when("redo is run")
def redo_is_run(ctx):
    ctx.manager.redo()


@then("the dates moved")
def the_dates_moved(ctx):
    assert _dates(ctx) != ctx.before


@then("the dates are back")
def the_dates_are_back(ctx):
    assert _dates(ctx) == ctx.before


@then("the dates move again")
def the_dates_move_again(ctx):
    assert _dates(ctx) == ctx.after


@then(parsers.parse('the snapshot covers "{fields}"'))
def the_snapshot_covers(fields):
    for name in [f.strip() for f in fields.split(',')]:
        assert name in SnapshotCommand.FIELDS


# ------------------------------------------------------------------
# the toolbar row and its keys
# ------------------------------------------------------------------

@then(parsers.parse('"{link}" sits between "{before}" and "{after}"'))
def the_icons_are_ordered(link, before, after):
    row = [name for name, _tip, _a in IconToolbar.ICON_ACTIONS]
    assert row.index(link) + 1 == row.index(after)
    assert row.index(link) - 1 == row.index(before)


@then(parsers.parse('"{name}" is followed by a divider'))
def followed_by_a_divider(name):
    row = [n for n, _tip, _a in IconToolbar.ICON_ACTIONS]
    assert row[row.index(name) + 1] == IconToolbar.SEPARATOR


@then(parsers.parse('"{first}" and "{second}" have icons'))
def they_have_icons(first, second):
    for name in (first, second):
        assert name in ICON_STROKES
        assert draw_icon(name, 20) is not None


@then(parsers.parse('"{first}" and "{second}" are real methods'))
def they_are_real_methods(first, second):
    assert callable(getattr(Toolbar, first, None))
    assert callable(getattr(Toolbar, second, None))


@then(parsers.parse('"{first}" and "{second}" are active only with a '
                    'project open'))
def they_are_live_only_with_a_plan(first, second):
    assert first in ACTIVE_WHEN_PROJECT_OPEN
    assert second in ACTIVE_WHEN_PROJECT_OPEN


@then("F2 is bound under this platform's modifier")
def f2_is_bound():
    assert sequences('F2') == (f"<{MODIFIER}-F2>",)


@then("Shift-F2 is bound under it too")
def shift_f2_is_bound():
    assert sequences('F2', shift=True) == (f"<{MODIFIER}-Shift-F2>",)


@then("the F2 captions read like this platform's")
def the_captions_read_right():
    if IS_MACOS:
        assert accelerator('F2') == '⌘F2'
        assert accelerator('F2', shift=True) == '⇧⌘F2'
    else:
        assert accelerator('F2') == 'Ctrl+F2'
        assert accelerator('F2', shift=True) == 'Ctrl+Shift+F2'


@then(parsers.parse('the "{name}" tooltip names F2'))
def the_tooltip_names_f2(name):
    tips = {n: tip for n, tip, _a in IconToolbar.ICON_ACTIONS}
    assert accelerator('F2') in tips[name]


@then(parsers.parse('the "{name}" tooltip names Shift-F2'))
def the_tooltip_names_shift_f2(name):
    tips = {n: tip for n, tip, _a in IconToolbar.ICON_ACTIONS}
    assert accelerator('F2', shift=True) in tips[name]


# ------------------------------------------------------------------
# collectors
# ------------------------------------------------------------------

@given("a plan of two collectors each holding one row")
def a_plan_of_two_collectors(ctx):
    ctx.project = Project(name="Plan")
    rows = (
        ("001", "Project Planning", "Task", None),
        ("002", "Scoping", "Subtask", "001"),
        ("003", "Design Phase", "Task", None),
        ("004", "UI Mockups", "Subtask", "003"),
    )
    for task_id, name, task_type, parent in rows:
        ctx.project.add_task(Task(id=task_id, name=name,
                                  start_date=BASE,
                                  end_date=BASE + timedelta(days=2),
                                  duration=2, task_type=task_type,
                                  parent_task_id=parent))
    ctx.project.apply_schedule()


@when("the schedule is applied")
def the_schedule_is_applied(ctx):
    ctx.project.apply_schedule()


@then(parsers.parse('"{task_id}" starts after "{other}" ends'))
def starts_after_the_other_ends(ctx, task_id, other):
    task = ctx.project.get_task_by_id(task_id)
    leader = ctx.project.get_task_by_id(other)
    assert task.start_date > leader.end_date


@then(parsers.parse('"{held}" shares the dates of "{collector}"'))
def shares_the_dates(ctx, held, collector):
    held_task = ctx.project.get_task_by_id(held)
    collector_task = ctx.project.get_task_by_id(collector)
    assert held_task.start_date == collector_task.start_date
    assert held_task.end_date == collector_task.end_date


@then(parsers.parse('applying the schedule reports no "{message}" '
                    'warning'))
def the_schedule_reports_no_warning(ctx, message):
    records = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    logger = logging.getLogger('gantt_app.core.models')
    handler = Capture(level=logging.WARNING)
    logger.addHandler(handler)
    try:
        ctx.project.apply_schedule()
    finally:
        logger.removeHandler(handler)
    assert not [m for m in records if message in m]


@then("four more passes move nothing")
def four_more_passes_move_nothing(ctx):
    settled = {t.id: (t.start_date, t.end_date)
               for t in ctx.project.tasks}
    for _ in range(4):
        ctx.project.apply_schedule()
    assert {t.id: (t.start_date, t.end_date)
            for t in ctx.project.tasks} == settled


@when(parsers.parse('"{task_id}" claims {days:d} days'))
def a_task_claims_days(ctx, task_id, days):
    ctx.task = ctx.project.get_task_by_id(task_id)
    ctx.task.duration = days


@then(parsers.parse('"{task_id}" holds the days its bracket measures'))
def it_holds_what_its_bracket_measures(ctx, task_id):
    task = ctx.project.get_task_by_id(task_id)
    calendar = ctx.project.calendar_for(task)
    assert task.duration == calendar.working_days_between(
        task.start_date, task.end_date)


# ------------------------------------------------------------------
# the plan from issue #18
# ------------------------------------------------------------------

@given("the plan from issue 18")
def the_plan_from_issue_18(ctx):
    ctx.project = Project(name="Plan")
    rows = (
        ("001", "Project Planning", "Task", None),
        ("002", "Requirements Gathering", "Subtask", "001"),
        ("003", "Design Phase", "Task", None),
        ("004", "UI Mockups", "Subtask", "003"),
        ("005", "UX planning", "Subtask", "003"),
        ("006", "feature1", "Subtask", "005"),
        ("007", "feature3", "Subtask", "005"),
        ("008", "feature2", "Subtask", "005"),
        ("009", "Implementation", "Task", None),
        ("010", "Design Review", "Milestone", None),
        ("011", "T3", "Task", None),
    )
    for task_id, name, task_type, parent in rows:
        ctx.project.add_task(Task(id=task_id, name=name,
                                  start_date=BASE,
                                  end_date=BASE + timedelta(days=2),
                                  duration=2, task_type=task_type,
                                  parent_task_id=parent))
    ctx.project.get_task_by_id("003").add_dependency("001")
    ctx.project.get_task_by_id("009").add_dependency("003")
    review = ctx.project.get_task_by_id("010")
    review.add_dependency("003")
    review.add_dependency("009")

