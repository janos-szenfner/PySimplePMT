"""
pytest-bdd tests for reordering tasks within a project.

Run with:
    python3 -m pytest tests/test_task_ordering_bdd.py -q

Ordering lives on Project rather than in the task list widget, so every
rule here is model-level. Nothing needs a display.
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Project, Task

pytestmark = [
    pytest.mark.task_ordering,
]

scenarios("features/task_ordering.feature")

BASE = datetime(2026, 1, 1)


@pytest.fixture
def ctx():
    return SimpleNamespace(project=None, result=None, snapshot=None)


def _task(task_id, name=None, parent=None, days=2, task_type="Task"):
    return Task(id=task_id, name=name or task_id, start_date=BASE,
                end_date=BASE + timedelta(days=days),
                task_type=task_type, parent_task_id=parent)


def _ids(ctx):
    return [t.id for t in ctx.project.tasks]


def _listed(text):
    return [item.strip() for item in text.split(',') if item.strip()]


def _get(ctx, task_id):
    return ctx.project.get_task_by_id(task_id)


# ------------------------------------------------------------------
# plans
# ------------------------------------------------------------------

@given("the ordering plan")
def the_ordering_plan(ctx):
    """Three roots; the middle one carries two sub-tasks."""
    ctx.project = Project(name="Test Project")
    for task_id, name in [("001", "Alpha"), ("002", "Beta"),
                          ("003", "Gamma")]:
        ctx.project.add_task(_task(task_id, name))
    for task_id, name in [("004", "Beta one"), ("005", "Beta two")]:
        ctx.project.add_task(_task(task_id, name, parent="002",
                                   days=1))


@given("the drop plan")
def the_drop_plan(ctx):
    """Three root tasks and one sub-task."""
    ctx.project = Project(name="Test Project")
    for task_id, name in [("001", "Alpha"), ("002", "Beta"),
                          ("003", "Gamma")]:
        ctx.project.add_task(_task(task_id, name))
    ctx.project.add_task(_task("004", "Beta one", parent="002"))


@given(parsers.parse('three root tasks "{task_ids}"'))
def three_root_tasks(ctx, task_ids):
    ctx.project = Project(name="Test Project")
    for task_id in _listed(task_ids):
        ctx.project.add_task(_task(task_id))


@given("the outdent plan")
def the_outdent_plan(ctx):
    """A parent with two sub-tasks, and a task after it."""
    ctx.project = Project(name="Test Project")
    ctx.project.add_task(_task("A", "A"))
    for task_id in ("B", "C"):
        ctx.project.add_task(_task(task_id, task_id, parent="A"))
    ctx.project.add_task(_task("D", "D"))


@given(parsers.parse('a plan of phase "{phase_id}" and root '
                     '"{root_id}"'))
def a_phase_and_a_root(ctx, phase_id, root_id):
    ctx.project = Project(name="Test Project")
    ctx.project.add_task(_task(phase_id, "Phase", days=9,
                               task_type="Phase"))
    ctx.project.add_task(_task(root_id, "Root"))


@given("the siblings plan")
def the_siblings_plan(ctx):
    ctx.project = Project(name="Test Project")
    ctx.project.add_task(_task("001", "Alpha", days=0))
    ctx.project.add_task(_task("002", "Beta", days=0))
    for task_id in ("003", "004"):
        ctx.project.add_task(Task(id=task_id, name=f"Sub {task_id}",
                                  start_date=BASE,
                                  task_type="Task",
                                  parent_task_id="002"))


# ------------------------------------------------------------------
# moving
# ------------------------------------------------------------------

@when(parsers.parse('"{task_id}" is moved "{direction}"'))
def it_is_moved(ctx, task_id, direction):
    ctx.result = ctx.project.move_task(task_id, direction)


@then("the move worked")
def the_move_worked(ctx):
    assert ctx.result


@then("the move was refused")
def the_move_was_refused(ctx):
    assert not ctx.result


@then(parsers.parse('the order reads "{task_ids}"'))
def the_order_reads(ctx, task_ids):
    assert _ids(ctx) == _listed(task_ids)


@then(parsers.parse('"{task_id}" still belongs to "{parent}"'))
def it_still_belongs(ctx, task_id, parent):
    assert _get(ctx, task_id).parent_task_id == parent


@then(parsers.parse('"{task_id}" refuses to move "{direction}"'))
def it_refuses_to_move(ctx, task_id, direction):
    assert not ctx.project.move_task(task_id, direction)


@when(parsers.parse('"{task_id}" is removed'))
def it_is_removed(ctx, task_id):
    ctx.project.remove_task(task_id)


@then(parsers.parse('moving "{task_id}" "{direction}" raises an '
                    'error'))
def moving_raises(ctx, task_id, direction):
    with pytest.raises(ValueError):
        ctx.project.move_task(task_id, direction)


@then(parsers.parse('moving "{moves}" loses no task'))
def no_task_is_lost(ctx, moves):
    before = set(_ids(ctx))
    for step in moves.split(', '):
        task_id, direction = step.split(':')
        ctx.project.move_task(task_id, direction)
        assert set(_ids(ctx)) == before


@given(parsers.parse('the orphan "{task_id}" is added'))
def an_orphan_is_added(ctx, task_id):
    ctx.project.add_task(Task(id=task_id, name="Orphan",
                              start_date=BASE, task_type="Task",
                              parent_task_id="missing"))


@then(parsers.parse('"{task_id}" is still there'))
def it_is_still_there(ctx, task_id):
    assert task_id in _ids(ctx)


# ------------------------------------------------------------------
# dropping before a sibling
# ------------------------------------------------------------------

@when(parsers.parse('"{task_id}" is dropped before "{target}"'))
def it_is_dropped_before(ctx, task_id, target):
    ctx.result = ctx.project.move_task_before(task_id, target)


@then(parsers.parse('dropping "{task_id}" before "{target}" is '
                    'refused'))
def dropping_is_refused(ctx, task_id, target):
    assert not ctx.project.move_task_before(task_id, target)


# ------------------------------------------------------------------
# indent and outdent
# ------------------------------------------------------------------

@given(parsers.parse('"{task_id}" holds the sub-task "{sub_id}"'))
def it_holds_a_subtask(ctx, task_id, sub_id):
    ctx.project.add_task(_task(sub_id, sub_id, parent=task_id, days=0))


@given(parsers.parse('"{task_id}" is made a milestone'))
def it_is_made_a_milestone(ctx, task_id):
    task = _get(ctx, task_id)
    task.is_milestone = True
    task.end_date = None


@given(parsers.parse('"{task_id}" waits for "{pred_id}"'))
def it_waits_for(ctx, task_id, pred_id):
    _get(ctx, task_id).add_dependency(pred_id, 'FS', 'Hard')


@when(parsers.parse('"{task_id}" is indented'))
def it_is_indented(ctx, task_id):
    ctx.result = ctx.project.indent_task(task_id)


@when(parsers.parse('"{task_id}" is outdented'))
def it_is_outdented(ctx, task_id):
    ctx.result = ctx.project.outdent_task(task_id)


@then(parsers.parse('indenting "{task_id}" is refused'))
def indenting_is_refused(ctx, task_id):
    assert not ctx.project.indent_task(task_id)


@then(parsers.parse('outdenting "{task_id}" is refused'))
def outdenting_is_refused(ctx, task_id):
    assert not ctx.project.outdent_task(task_id)


@then(parsers.parse('"{task_id}" cannot indent'))
def it_cannot_indent(ctx, task_id):
    assert not ctx.project.can_indent(task_id)


@then(parsers.parse('"{task_id}" can indent'))
def it_can_indent(ctx, task_id):
    assert ctx.project.can_indent(task_id)
    assert ctx.project.indent_task(task_id)


@then(parsers.parse('"{task_id}" cannot outdent'))
def it_cannot_outdent(ctx, task_id):
    assert not ctx.project.can_outdent(task_id)


@then(parsers.parse('"{task_id}" sits under "{parent}"'))
def it_sits_under(ctx, task_id, parent):
    assert _get(ctx, task_id).parent_task_id == parent


@then(parsers.parse('"{task_id}" is at the top level'))
def it_is_at_the_top(ctx, task_id):
    assert _get(ctx, task_id).parent_task_id is None


@then(parsers.parse('"{task_id}" is a "{task_type}"'))
def it_is_a(ctx, task_id, task_type):
    assert _get(ctx, task_id).task_type == task_type


@then(parsers.parse('"{task_id}" waits for nothing'))
def it_waits_for_nothing(ctx, task_id):
    assert _get(ctx, task_id).dependency_ids == []


@then(parsers.parse('"{task_id}" waits for "{pred_id}"'))
def it_waits_for_that(ctx, task_id, pred_id):
    assert _get(ctx, task_id).dependency_ids == [pred_id]


@then("rescheduling settles")
def rescheduling_settles(ctx):
    ctx.project.reschedule()


@then("rescheduling again changes nothing")
def rescheduling_again_changes_nothing(ctx):
    assert not ctx.project.reschedule()


# ------------------------------------------------------------------
# the structure snapshot
# ------------------------------------------------------------------

@given("a structure snapshot")
def a_structure_snapshot(ctx):
    ctx.snapshot = ctx.project.structure_snapshot()


@when("the snapshot is restored")
def the_snapshot_is_restored(ctx):
    ctx.project.restore_structure(ctx.snapshot)


# ------------------------------------------------------------------
# plan order is display order
# ------------------------------------------------------------------

@when(parsers.parse('a child "{task_id}" is added under "{parent}"'))
def a_child_is_added(ctx, task_id, parent):
    ctx.project.add_task(_task(task_id, "Child", parent=parent,
                               days=1))


@then("the stored order is the display order")
def the_stored_order_is_the_display_order(ctx):
    assert _ids(ctx) == [t.id for t in ctx.project.display_order()]


@then(parsers.parse('the numbers read "{mapping}"'))
def the_numbers_read(ctx, mapping):
    expected = {pair.split(':')[0].strip(): int(pair.split(':')[1])
                for pair in mapping.split(',')}
    assert ctx.project.display_ids() == expected


@when(parsers.parse('the saved file gains a child "{task_id}" under '
                    '"{parent}" at the end'))
def a_divergent_file_is_loaded(ctx, task_id, parent):
    data = ctx.project.to_dict()
    child = Task(id=task_id, name="Child", task_type="Task",
                 start_date=BASE, parent_task_id=parent).to_dict()
    data['tasks'].append(child)
    ctx.project = Project.from_dict(data)


# ------------------------------------------------------------------
# siblings
# ------------------------------------------------------------------

@then(parsers.parse('the siblings of "{task_id}" are "{task_ids}"'))
def the_siblings_are(ctx, task_id, task_ids):
    found = [t.id for t in ctx.project.get_siblings(task_id)]
    assert found == _listed(task_ids)


@then(parsers.parse('"{task_id}" has no siblings'))
def it_has_no_siblings(ctx, task_id):
    assert ctx.project.get_siblings(task_id) == []
