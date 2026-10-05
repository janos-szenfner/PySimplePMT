"""
pytest-bdd tests for the Deliverables tab's data - the entity, its
roll-up, the hierarchy the grid edits, and the many-to-many task
assignment.

Run with:
    python3 -m pytest tests/test_deliverables_bdd.py -q

Nothing here needs a display.
"""
from datetime import datetime
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.deliverable import (
    DELIVERABLE_STATUSES, Deliverable, progress_for_status,
    rolled_up_deliverable_progress, status_for_progress,
)
from gantt_app.core.models import Project, Task
from gantt_app.utils.undoredo import (
    ProjectStateTracker, RemoveTaskCommand, UndoRedoManager,
)

pytestmark = [
    pytest.mark.deliverables,
]

scenarios("features/deliverables.feature")


@pytest.fixture
def ctx():
    return SimpleNamespace(project=None, item=None, result=None,
                           moved=None, manager=None, tracker=None,
                           loaded=None)


def _task(task_id, progress=0, parent_task_id=None, task_type='Task'):
    today = datetime(2026, 1, 1)
    return Task(id=task_id, name=f'Task {task_id}', start_date=today,
                end_date=today, progress=progress,
                parent_task_id=parent_task_id, task_type=task_type)


def _plan(ctx, datatable):
    """A project from an id/parent table."""
    ctx.project = Project(name="Plan")
    for row in datatable[1:]:
        deliverable_id, parent = row[0].strip(), row[1].strip() or None
        ctx.project.deliverables.append(
            Deliverable.create(name=deliverable_id, parent_id=parent,
                               deliverable_id=deliverable_id))


def _deliverable(ctx, deliverable_id):
    return ctx.project.get_deliverable_by_id(deliverable_id)


def _ids(text):
    return [item.strip() for item in text.split(',') if item.strip()]


# ------------------------------------------------------------------
# the entity
# ------------------------------------------------------------------

@when("a deliverable is created plain")
def a_plain_deliverable(ctx):
    ctx.item = Deliverable.create(name="A")


@then(parsers.parse('its status is "{status}"'))
def its_status_is(ctx, status):
    assert ctx.item.status == status


@then(parsers.parse('it reads {progress:d} percent'))
def it_reads_percent(ctx, progress):
    assert ctx.item.progress == progress


@then(parsers.parse('its weight is {weight}'))
def its_weight_is(ctx, weight):
    assert ctx.item.weight == float(weight)


@then("it has no parent")
def it_has_no_parent(ctx):
    assert ctx.item.parent_id is None


@then(parsers.parse('a deliverable at {progress:d} reads {read:d} '
                    'percent'))
def progress_is_clamped(progress, read):
    assert Deliverable.create(progress=progress).progress == read


@then(parsers.parse('a deliverable at {progress:d} marked "{status}" '
                    'reads status "{result}"'))
def an_unknown_status_reads_as_progress(progress, status, result):
    item = Deliverable.create(status=status, progress=progress)
    assert item.status == result


@then(parsers.parse('progress {progress:d} reads as status "{status}"'))
def status_for_progress_answers(progress, status):
    assert status_for_progress(progress) == status


@then(parsers.parse('status "{status}" on a row at {held:d} reads '
                    '{progress:d} percent'))
def progress_for_status_answers(status, held, progress):
    assert progress_for_status(status, held) == progress


@then(parsers.parse('the statuses offered are "{statuses}"'))
def the_statuses_offered_are(statuses):
    assert list(DELIVERABLE_STATUSES) == _ids(statuses)


# ------------------------------------------------------------------
# the roll-up
# ------------------------------------------------------------------

@then(parsers.parse('children at "{progresses}" roll up to {total:d}'))
def unweighted_children_roll_up(progresses, total):
    children = [Deliverable.create(progress=int(p))
                for p in progresses.split(', ')]
    assert rolled_up_deliverable_progress(children) == total


@then(parsers.parse('children at "{progresses}" weighted "{weights}" '
                    'roll up to {total:d}'))
def weighted_children_roll_up(progresses, weights, total):
    children = [
        Deliverable.create(progress=int(p), weight=float(w))
        for p, w in zip(progresses.split(', '), weights.split(', '))]
    assert rolled_up_deliverable_progress(children) == total


@then(parsers.parse('no children roll up to {total:d}'))
def no_children_roll_up(total):
    assert rolled_up_deliverable_progress([]) == total


@given("a deliverable plan")
def a_deliverable_plan(ctx, datatable):
    _plan(ctx, datatable)


@given("a deliverable plan with two tasks")
def a_deliverable_plan_with_tasks(ctx, datatable):
    _plan(ctx, datatable)
    ctx.project.tasks = [_task('t1', progress=40),
                         _task('t2', progress=80)]


@given(parsers.parse('"{deliverable_id}" is set to {progress:d} '
                     'percent'))
@when(parsers.parse('"{deliverable_id}" is set to {progress:d} '
                    'percent'))
def it_is_set_to_percent(ctx, deliverable_id, progress):
    _deliverable(ctx, deliverable_id).progress = progress


@when("the roll-up runs")
def the_roll_up_runs(ctx):
    ctx.moved = ctx.project.roll_up_deliverables()


@given("the roll-up has settled")
def the_roll_up_has_settled(ctx):
    ctx.project.roll_up_deliverables()


@then("the roll-up reports nothing moved")
def the_roll_up_reports_nothing(ctx):
    assert not ctx.project.roll_up_deliverables()


@then("the roll-up reports it moved")
def the_roll_up_reports_it_moved(ctx):
    assert ctx.project.roll_up_deliverables()


@then(parsers.parse('"{deliverable_id}" reads {progress:d} percent'))
def it_reads(ctx, deliverable_id, progress):
    assert _deliverable(ctx, deliverable_id).progress == progress


@then(parsers.parse('"{deliverable_id}" reads status "{status}"'))
def it_reads_status(ctx, deliverable_id, status):
    assert _deliverable(ctx, deliverable_id).status == status


# ------------------------------------------------------------------
# hierarchy moves
# ------------------------------------------------------------------

@then(parsers.parse('the display order is "{ids}"'))
def the_display_order_is(ctx, ids):
    assert [d.id for d in
            ctx.project.deliverable_display_order()] == _ids(ids)


@when(parsers.parse('"{deliverable_id}" is indented'))
def it_is_indented(ctx, deliverable_id):
    ctx.result = ctx.project.indent_deliverables([deliverable_id])


@when(parsers.parse('"{deliverable_id}" is outdented'))
def it_is_outdented(ctx, deliverable_id):
    ctx.result = ctx.project.outdent_deliverables([deliverable_id])


@then("the move worked")
def the_move_worked(ctx):
    assert ctx.result


@then("the move was refused")
def the_move_was_refused(ctx):
    assert not ctx.result


@then(parsers.parse('"{deliverable_id}" sits under "{parent}"'))
def it_sits_under(ctx, deliverable_id, parent):
    assert _deliverable(ctx, deliverable_id).parent_id == parent


@then(parsers.parse('"{deliverable_id}" is at the top level'))
def it_is_at_the_top(ctx, deliverable_id):
    assert _deliverable(ctx, deliverable_id).parent_id is None


@when(parsers.parse('"{deliverable_id}" is re-parented under '
                    '"{parent}"'))
def it_is_reparented(ctx, deliverable_id, parent):
    ctx.result = ctx.project.reparent_deliverable(deliverable_id,
                                                  parent)


@then(parsers.parse('re-parenting "{deliverable_id}" under "{parent}" '
                    'is refused twice'))
def reparenting_is_refused(ctx, deliverable_id, parent):
    assert not ctx.project.can_reparent_deliverable(deliverable_id,
                                                    parent)
    assert not ctx.project.reparent_deliverable(deliverable_id, parent)


@when(parsers.parse('"{deliverable_id}" is moved to the line below '
                    '"{anchor}"'))
def moved_to_the_line_below(ctx, deliverable_id, anchor):
    ctx.result = ctx.project.move_deliverable_to_line(
        deliverable_id, anchor, above=False)


@when(parsers.parse('"{deliverable_id}" is moved after "{anchor}"'))
def moved_after(ctx, deliverable_id, anchor):
    ctx.result = ctx.project.move_deliverable_after(deliverable_id,
                                                    anchor)


@when(parsers.parse('"{deliverable_id}" is moved "{direction}"'))
def moved_up_or_down(ctx, deliverable_id, direction):
    ctx.result = ctx.project.move_deliverables([deliverable_id],
                                               direction)


@when("the deliverables are sorted by name")
def sorted_by_name(ctx):
    ctx.project.sort_deliverables(lambda d: d.name)


@then(parsers.parse('the topmost of "{ids}" are "{expected}"'))
def the_topmost_are(ctx, ids, expected):
    assert ctx.project.topmost_deliverables_of(_ids(ids)) == \
        _ids(expected)


@when(parsers.parse('"{deliverable_id}" is removed'))
def it_is_removed(ctx, deliverable_id):
    ctx.result = ctx.project.remove_deliverable(deliverable_id)


@then(parsers.parse('the next deliverable id is "{next_id}"'))
def the_next_id_is(ctx, next_id):
    assert ctx.project.next_deliverable_id() == next_id


@then(parsers.parse('the display ids are "{mapping}"'))
def the_display_ids_are(ctx, mapping):
    expected = {pair.split(':')[0].strip(): int(pair.split(':')[1])
                for pair in mapping.split(',')}
    assert ctx.project.deliverable_display_ids() == expected


# ------------------------------------------------------------------
# serialization
# ------------------------------------------------------------------

@given('a plan holding an "API" deliverable with every field set')
def a_plan_with_every_field(ctx):
    ctx.project = Project(name="Plan")
    ctx.project.deliverables.append(Deliverable.create(
        name="API", deliverable_id='001', status='In Progress',
        progress=40, weight=2.5, assignees=['@Sarah', '@Tom'],
        due_date=datetime(2026, 9, 1), priority='High',
        tags=['backend'], details='the acceptance criteria'))
    ctx.project.deliverables.append(Deliverable.create(
        name="DB schema", parent_id='001', deliverable_id='002'))


@when("the plan is saved and loaded")
def the_plan_is_saved_and_loaded(ctx):
    ctx.loaded = Project.from_dict(ctx.project.to_dict())


@then('"001" kept its name, progress, weight, assignees, due date, '
      'priority, tags and details')
def the_first_kept_everything(ctx):
    first = ctx.loaded.get_deliverable_by_id('001')
    assert first.name == 'API'
    assert first.progress == 40
    assert first.weight == 2.5
    assert first.assignees == ['@Sarah', '@Tom']
    assert first.due_date == datetime(2026, 9, 1)
    assert first.priority == 'High'
    assert first.tags == ['backend']
    assert first.details == 'the acceptance criteria'


@then(parsers.parse('"{deliverable_id}" still sits under "{parent}"'))
def it_still_sits_under(ctx, deliverable_id, parent):
    loaded = ctx.loaded.get_deliverable_by_id(deliverable_id)
    assert loaded.parent_id == parent


@when("a plan saved without the deliverables key is loaded")
def a_plan_without_the_key(ctx):
    data = Project(name="Plan").to_dict()
    data.pop('deliverables')
    ctx.loaded = Project.from_dict(data)


@then("it carries no deliverables")
def it_carries_no_deliverables(ctx):
    assert ctx.loaded.deliverables == []


@then(parsers.parse('a saved deliverable with assignee "{assignee}" '
                    'loads assignees "{assignees}"'))
def a_legacy_assignee_loads(assignee, assignees):
    data = Deliverable.create(name='x', deliverable_id='a').to_dict()
    del data['assignees']
    data['assignee'] = assignee
    loaded = Deliverable.from_dict(data)
    assert loaded.assignees == _ids(assignees)


@then(parsers.parse('assignees written "{raw}" load as "{loaded}"'))
def written_assignees_normalise(raw, loaded):
    assert Deliverable.create(assignees=raw).assignees == _ids(loaded)


@then(parsers.parse('assignees listed as "{raw}" load as "{loaded}"'))
def listed_assignees_normalise(raw, loaded):
    items = ['' if item.strip() == '(blank)' else item.strip()
             for item in raw.split(',')] + ['  ']
    assert Deliverable.create(assignees=items).assignees == \
        _ids(loaded)


@when("a plan whose deliverables hold a bad entry is loaded")
def a_plan_with_a_bad_entry(ctx):
    data = Project(name="Plan").to_dict()
    data['deliverables'] = [
        'not a dict',
        Deliverable.create(name='ok', deliverable_id='x').to_dict()]
    ctx.loaded = Project.from_dict(data)


@then(parsers.parse('the deliverables are "{ids}"'))
def the_deliverables_are(ctx, ids):
    assert [d.id for d in ctx.loaded.deliverables] == _ids(ids)


# ------------------------------------------------------------------
# undo
# ------------------------------------------------------------------

@given(parsers.parse('a tracked deliverable plan of "{shape}"'))
def a_tracked_deliverable_plan(ctx, shape):
    ctx.project = Project(name="Plan")
    for part in shape.split(', '):
        if ' under ' in part:
            deliverable_id, parent = part.split(' under ')
        else:
            deliverable_id, parent = part, None
        ctx.project.deliverables.append(Deliverable.create(
            name=deliverable_id, parent_id=parent,
            deliverable_id=deliverable_id))
    ctx.manager = UndoRedoManager()
    ctx.tracker = ProjectStateTracker(ctx.project, ctx.manager)


@given(parsers.parse('a tracked deliverable plan of "{shape}" with '
                     'task "{task_id}" at {progress:d}'))
def a_tracked_plan_with_a_task(ctx, shape, task_id, progress):
    a_tracked_deliverable_plan(ctx, shape)
    ctx.project.tasks = [_task(task_id, progress=progress)]


@when(parsers.parse('"{deliverable_id}" is finished the way the grid '
                    'does'))
def it_is_finished(ctx, deliverable_id):
    leaf = _deliverable(ctx, deliverable_id)

    def apply():
        leaf.progress = 100
        leaf.status = 'Done'
        ctx.project.roll_up_deliverables()
        return True

    ctx.tracker.run_deliverable_as_command(apply, 'Finish')


@when(parsers.parse('"{deliverable_id}" is re-parented under '
                    '"{parent}" the way the grid does'))
def it_is_reparented_as_a_command(ctx, deliverable_id, parent):
    ctx.tracker.run_deliverable_as_command(
        lambda: ctx.project.reparent_deliverable(deliverable_id,
                                                 parent),
        'Re-parent')


@when("a command that changes nothing runs")
def a_noop_command_runs(ctx):
    ctx.tracker.run_deliverable_as_command(lambda: False, 'Nothing')


@when("undo is run")
def undo_is_run(ctx):
    assert ctx.manager.undo()


@when("redo is run")
def redo_is_run(ctx):
    assert ctx.manager.redo()


@then("undo is not offered")
def undo_is_not_offered(ctx):
    assert not ctx.manager.can_undo()


# ------------------------------------------------------------------
# task assignment
# ------------------------------------------------------------------

@given(parsers.parse('"{deliverable_id}" takes task "{task_id}"'))
def it_takes_a_task(ctx, deliverable_id, task_id):
    _deliverable(ctx, deliverable_id).task_ids.append(task_id)


@given(parsers.parse('"{deliverable_id}" takes tasks "{task_ids}"'))
def it_takes_tasks(ctx, deliverable_id, task_ids):
    _deliverable(ctx, deliverable_id).task_ids = _ids(task_ids)


@given(parsers.parse('"{deliverable_id}" takes "{first}" at '
                     '{p1:d}, its subtask "{second}" at {p2:d} and '
                     'milestone "{third}" at {p3:d}'))
def it_takes_typed_tasks(ctx, deliverable_id, first, p1, second, p2,
                         third, p3):
    ctx.project.tasks = [
        _task(first, progress=p1),
        _task(second, progress=p2, parent_task_id=first,
              task_type='Subtask'),
        _task(third, progress=p3, task_type='Milestone'),
    ]
    _deliverable(ctx, deliverable_id).task_ids = [first, second, third]


@then(parsers.parse('"{task_id}" is listed under "{deliverable_ids}"'))
def it_is_listed_under(ctx, task_id, deliverable_ids):
    found = [d.id for d in ctx.project.deliverables_for_task(task_id)]
    assert found == _ids(deliverable_ids)


@then(parsers.parse('"{deliverable_id}" is fed by "{task_ids}"'))
def it_is_fed_by(ctx, deliverable_id, task_ids):
    found = [t.id for t in
             ctx.project.tasks_for_deliverable(deliverable_id)]
    assert found == _ids(task_ids)


@then(parsers.parse('"{deliverable_id}" holds tasks "{task_ids}"'))
def it_holds_tasks(ctx, deliverable_id, task_ids):
    assert _deliverable(ctx, deliverable_id).task_ids == _ids(task_ids)


@then(parsers.parse('"{deliverable_id}" holds no tasks'))
def it_holds_no_tasks(ctx, deliverable_id):
    assert _deliverable(ctx, deliverable_id).task_ids == []


@when(parsers.parse('"{task_id}" is assigned to "{deliverable_ids}"'))
def it_is_assigned(ctx, task_id, deliverable_ids):
    ctx.result = ctx.project.set_task_deliverables(task_id,
                                                   _ids(deliverable_ids))


@then(parsers.parse('assigning "{task_id}" to nothing changes '
                    'nothing'))
def assigning_nothing_changes_nothing(ctx, task_id):
    assert not ctx.project.set_task_deliverables(task_id, [])


@then(parsers.parse('assigning "{task_id}" to "{deliverable_ids}" '
                    'again changes nothing'))
def assigning_again_changes_nothing(ctx, task_id, deliverable_ids):
    assert not ctx.project.set_task_deliverables(task_id,
                                                 _ids(deliverable_ids))


@when(parsers.parse('"{deliverable_id}" drops its tasks'))
def it_drops_its_tasks(ctx, deliverable_id):
    _deliverable(ctx, deliverable_id).task_ids = []


@when(parsers.parse('task "{task_id}" is deleted'))
def the_task_is_deleted(ctx, task_id):
    ctx.project.remove_task(task_id)


@when(parsers.parse('the saved file names "{task_id}" and a ghost '
                    'under "{deliverable_id}"'))
def the_file_names_a_ghost(ctx, task_id, deliverable_id):
    data = ctx.project.to_dict()
    index = next(i for i, d in enumerate(data['deliverables'])
                 if d.get('id') == deliverable_id)
    data['deliverables'][index]['task_ids'] = [task_id, 'ghost']
    ctx.project = Project.from_dict(data)


@then("a saved deliverable with no task_ids key holds no tasks")
def no_task_ids_key():
    data = Deliverable.create(name='x', deliverable_id='a').to_dict()
    del data['task_ids']
    assert Deliverable.from_dict(data).task_ids == []


@then(parsers.parse('a deliverable holding "{task_ids}" holds tasks '
                    '"{expected}"'))
def duplicate_ids_are_kept_once(task_ids, expected):
    item = Deliverable.create(task_ids=_ids(task_ids))
    assert item.task_ids == _ids(expected)


# ------------------------------------------------------------------
# assignment undo
# ------------------------------------------------------------------

@when(parsers.parse('"{task_id}" is assigned to "{deliverable_id}" the '
                    'way the grid does'))
def assigned_as_a_command(ctx, task_id, deliverable_id):
    ctx.tracker.run_deliverable_as_command(
        lambda: ctx.project.set_task_deliverables(
            task_id, [deliverable_id]),
        'Assign')


@when(parsers.parse('task "{task_id}" is deleted as a command'))
def deleted_as_a_command(ctx, task_id):
    ctx.manager.execute(RemoveTaskCommand(
        ctx.project, task_id,
        ctx.project.get_task_by_id(task_id), 0))


# ------------------------------------------------------------------
# coercion - a saved file can carry anything
# ------------------------------------------------------------------

@when(parsers.parse('a deliverable is made with progress "{progress}"'))
def made_with_progress(ctx, progress):
    ctx.item = Deliverable.create(name="A")
    ctx.item.progress = progress
    Deliverable.__post_init__(ctx.item)


@when(parsers.parse('a deliverable is made with weight "{weight}"'))
def made_with_weight(ctx, weight):
    ctx.item = Deliverable.create(name="A", weight=weight)


@when(parsers.parse('a deliverable is made with assignees "{names}"'))
def made_with_assignees(ctx, names):
    ctx.item = Deliverable.create(name="A", assignees=names)


@then(parsers.parse('its weight is {weight:g}'))
def its_weight_is(ctx, weight):
    assert ctx.item.weight == weight


@then(parsers.parse('its assignees are "{names}"'))
def its_assignees_are(ctx, names):
    assert ctx.item.assignees == _ids(names)


@then('it is not done')
def it_is_not_done(ctx):
    assert not ctx.item.is_done


@when(parsers.parse('its progress becomes {progress:d}'))
def its_progress_becomes(ctx, progress):
    ctx.item.progress = progress


@then('it is done')
def it_is_done(ctx):
    assert ctx.item.is_done


@then(parsers.parse('a saved due date of "{text}" loads as none'))
def a_bad_due_date_loads_as_none(text):
    item = Deliverable.from_dict({'name': 'D', 'due_date': text})
    assert item.due_date is None


@given(parsers.parse('a plan of deliverables "{ids}"'))
def a_plan_of_deliverables(ctx, ids):
    ctx.project = Project(name="Plan")
    for deliverable_id in _ids(ids):
        ctx.project.deliverables.append(
            Deliverable.create(name=deliverable_id,
                               deliverable_id=deliverable_id))


@given(parsers.parse('"{parent}" takes child "{child}" weighing '
                     '"{weight}" at {progress:d} percent'))
def a_typed_child(ctx, parent, child, weight, progress):
    ctx.child_progress = getattr(ctx, 'child_progress', [])
    ctx.children = getattr(ctx, 'children', [])
    w = weight if weight == 'banana' else float(weight)
    row = Deliverable.create(name=child, deliverable_id=child)
    row.progress = progress
    row.weight = w
    # create() already coerced a good weight; put the bad one back the
    # way a corrupted file would.
    if weight == 'banana':
        row.weight = 'banana'
    ctx.children.append(row)


@then(parsers.parse('"{deliverable_id}" rolls up to {progress:d} percent'))
def it_rolls_up(ctx, deliverable_id, progress):
    assert rolled_up_deliverable_progress(ctx.children) == progress
