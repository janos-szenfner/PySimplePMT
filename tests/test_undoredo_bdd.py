"""
BDD steps for tests/features/undoredo.feature - the command pattern,
the manager's stacks, the state tracker, and the delete/reorder/pool
snapshots. Pure domain, no widgets.
"""

import copy
import pytest
from pytest_bdd import given, parsers, scenario, then, when

from datetime import datetime, timedelta
from types import SimpleNamespace

from gantt_app.core.models import Project, Task
from gantt_app.core.resource_model import Resource, ResourceType
from gantt_app.utils.undoredo import (
    AddTaskCommand,
    CompoundCommand,
    ProjectStateTracker,
    RemoveTaskCommand,
    UndoRedoManager,
    UpdateProjectNameCommand,
    UpdateTaskCommand,
    create_add_task_command,
    create_compound_command,
    create_remove_task_command,
    create_update_project_name_command,
    create_update_task_command,
)

START = datetime(2024, 1, 1)
BASE = datetime(2026, 1, 1)


@pytest.fixture
def ctx():
    return SimpleNamespace(project=None, manager=None, tracker=None,
                           command=None, result=None, task=None,
                           old_copy=None, recording=None, repo_obj=None)


# ---- commands --------------------------------------------------------------


@scenario('features/undoredo.feature',
          'AddTaskCommand puts a task in and takes it back out')
def test_add_task_command():
    pass


@scenario('features/undoredo.feature',
          'RemoveTaskCommand deletes a task and restores it')
def test_remove_task_command():
    pass


@scenario('features/undoredo.feature',
          'UpdateTaskCommand swaps a task and swaps it back')
def test_update_task_command():
    pass


@scenario('features/undoredo.feature',
          'UpdateProjectNameCommand renames and restores')
def test_update_project_name_command():
    pass


# ---- the manager --------------------------------------------------------------


@scenario('features/undoredo.feature',
          'Executing through the manager makes it undoable')
def test_execute_add_task():
    pass


@scenario('features/undoredo.feature', 'Undo through the manager')
def test_undo_add_task():
    pass


@scenario('features/undoredo.feature', 'Redo through the manager')
def test_redo_add_task():
    pass


@scenario('features/undoredo.feature',
          'A fresh edit clears the redo stack')
def test_undo_clears_redo_stack():
    pass


@scenario('features/undoredo.feature',
          'The history keeps only the newest few')
def test_max_history_limit():
    pass


@scenario('features/undoredo.feature', 'Undo on an empty stack says no')
def test_cannot_undo_or_redo_when_empty():
    pass


@scenario('features/undoredo.feature', 'Clear empties both stacks')
def test_clear():
    pass


@scenario('features/undoredo.feature',
          'The undo description names the command')
def test_get_undo_description():
    pass


@scenario('features/undoredo.feature',
          'The redo description names the command')
def test_get_redo_description():
    pass


# ---- compound commands ----------------------------------------------------------


@scenario('features/undoredo.feature',
          'A compound command executes its members')
def test_execute_compound_command():
    pass


@scenario('features/undoredo.feature',
          'A compound command undoes its members')
def test_undo_compound_command():
    pass


# ---- factories --------------------------------------------------------------------


@scenario('features/undoredo.feature',
          'Factories build each command kind')
def test_factories_build_each_command_kind():
    pass


# ---- the state tracker ------------------------------------------------------------------


@scenario('features/undoredo.feature', 'The tracker adds a task undoably')
def test_tracker_add_task():
    pass


@scenario('features/undoredo.feature', 'The tracker removes a task undoably')
def test_tracker_remove_task():
    pass


@scenario('features/undoredo.feature', 'The tracker updates a task undoably')
def test_tracker_update_task():
    pass


@scenario('features/undoredo.feature',
          'The tracker renames the project undoably')
def test_tracker_update_project_name():
    pass


@scenario('features/undoredo.feature',
          'The tracker undoes and redoes an add')
def test_tracker_undo_redo():
    pass


# ---- undoing a dependency change -------------------------------------------------------------


@scenario('features/undoredo.feature',
          'Undo takes a newly linked dependency back off')
def test_undo_removes_an_added_dependency():
    pass


@scenario('features/undoredo.feature', 'Redo puts the dependency back')
def test_redo_puts_the_dependency_back():
    pass


@scenario('features/undoredo.feature',
          'The undo snapshot is independent of the live task')
def test_undo_snapshot_is_independent_of_the_live_task():
    pass


# ---- undoing a delete -----------------------------------------------------------------------------


@scenario('features/undoredo.feature',
          'Deleting a parent takes its sub-tasks')
def test_deleting_a_parent_takes_its_subtasks():
    pass


@scenario('features/undoredo.feature', 'Undo restores the sub-tasks')
def test_undo_restores_the_subtasks():
    pass


@scenario('features/undoredo.feature',
          'Undo restores dependencies on surviving tasks')
def test_undo_restores_dependencies_on_surviving_tasks():
    pass


@scenario('features/undoredo.feature', 'Undo restores the link details')
def test_undo_restores_the_link_details():
    pass


@scenario('features/undoredo.feature', 'Redo deletes the branch again')
def test_redo_deletes_the_branch_again():
    pass


@scenario('features/undoredo.feature', 'Undo after redo still restores')
def test_undo_after_redo_still_restores():
    pass


@scenario('features/undoredo.feature',
          'Deleting a childless task is undoable')
def test_deleting_a_childless_task_is_undoable():
    pass


# ---- undoing a reorder ----------------------------------------------------------------------------------


@scenario('features/undoredo.feature',
          'Undo puts a moved task back where it was')
def test_undo_restores_the_previous_order():
    pass


@scenario('features/undoredo.feature', 'Redo reapplies the move')
def test_redo_reapplies_the_move():
    pass


@scenario('features/undoredo.feature',
          'The recorded orders are independent')
def test_the_recorded_orders_are_independent():
    pass


# ---- the resource pool -------------------------------------------------------------------------------------


@scenario('features/undoredo.feature', 'A pool command undoes a creation')
def test_pool_command_undoes_a_creation():
    pass


@scenario('features/undoredo.feature',
          'A modal\'s own write is recorded, not re-run')
def test_record_pool_change_after_the_fact():
    pass


@scenario('features/undoredo.feature',
          'An unchanged pool makes no history entry')
def test_record_pool_change_noop():
    pass


@scenario('features/undoredo.feature',
          'The task snapshot restores assignments and pool')
def test_task_snapshot_restores_assignments_and_pool():
    pass


@scenario('features/undoredo.feature',
          'The snapshot survives an in-place assignment edit')
def test_snapshot_survives_in_place_assignment_edit():
    pass


@scenario('features/undoredo.feature',
          'Pool restore keeps the repository object')
def test_pool_restore_keeps_the_repository_object():
    pass


# ---- helpers -----------------------------------------------------------------------------------------------


def _task(name, days=5, task_id=None, **kwargs):
    return Task.create_task(name, START, START + timedelta(days=days),
                            **kwargs) if task_id is None else Task(
        id=task_id, name=name, start_date=START,
        end_date=START + timedelta(days=days), **kwargs)


def _resource(resource_id="r1", name="Anna"):
    return Resource(id=resource_id, name=name,
                    resource_type=ResourceType.NAMED,
                    role_type="dev", initials=name[:2].upper())


def _ids(project):
    return [task.id for task in project.tasks]


# ---- Givens: bare commands -------------------------------------------------------


@given('an undoable project')
def an_undoable_project(ctx):
    ctx.project = Project(name="Test Project")


@given(parsers.parse('an undoable project holding "{name}"'))
def an_undoable_project_holding(ctx, name):
    an_undoable_project(ctx)
    ctx.task = _task(name)
    ctx.project.add_task(ctx.task)


@given(parsers.parse('an undoable project named "{name}"'))
def an_undoable_project_named(ctx, name):
    ctx.project = Project(name=name)


@given(parsers.parse('an add-task command for "{name}"'))
def an_add_task_command(ctx, name):
    ctx.task = _task(name)
    ctx.command = AddTaskCommand(project=ctx.project, task=ctx.task)


@given('a remove-task command for it')
def a_remove_task_command(ctx):
    index = ctx.project.tasks.index(ctx.task)
    ctx.command = RemoveTaskCommand(project=ctx.project, task_id=ctx.task.id,
                                    task=ctx.task, index=index)


@given(parsers.parse('an update-task command renaming it to "{name}"'))
def an_update_task_command(ctx, name):
    old_task = copy.copy(ctx.task)
    new_task = Task(
        id=ctx.task.id, name=name,
        start_date=ctx.task.start_date, end_date=ctx.task.end_date,
        progress=ctx.task.progress, dependencies=ctx.task.dependencies,
        color=ctx.task.color, is_milestone=ctx.task.is_milestone,
    )
    ctx.command = UpdateTaskCommand(project=ctx.project, task_id=ctx.task.id,
                                    old_task=old_task, new_task=new_task)


@given(parsers.parse('an update-name command changing it to "{name}"'))
def an_update_name_command(ctx, name):
    ctx.command = UpdateProjectNameCommand(project=ctx.project,
                                         old_name=ctx.project.name,
                                         new_name=name)


@given(parsers.parse('a compound command "{name}" of two adds'))
def a_compound_command(ctx, name):
    commands = [AddTaskCommand(project=ctx.project, task=_task("Task 1")),
                AddTaskCommand(project=ctx.project,
                               task=Task.create_task(
                                   "Task 2", START + timedelta(days=6),
                                   START + timedelta(days=10)))]
    ctx.command = CompoundCommand(commands=commands, name=name)


# ---- Givens: the manager ------------------------------------------------------------


@given('a project with a manager')
def a_project_with_a_manager(ctx):
    ctx.project = Project(name="Test Project")
    ctx.manager = UndoRedoManager(max_history=10)
    ctx.manager.set_project(ctx.project)


@given(parsers.parse('a project with a manager of history {limit:d}'))
def a_project_with_a_limited_manager(ctx, limit):
    ctx.project = Project(name="Test Project")
    ctx.manager = UndoRedoManager(max_history=limit)
    ctx.manager.set_project(ctx.project)


@given(parsers.parse('the manager added "{name}"'))
def the_manager_added(ctx, name):
    ctx.manager.execute(
        AddTaskCommand(project=ctx.project, task=_task(name)))


@given('the manager undid')
def the_manager_undid(ctx):
    ctx.manager.undo()


@given('the manager redid')
def the_manager_redid(ctx):
    ctx.manager.redo()


# ---- Givens: the tracker -----------------------------------------------------------


@given('a project with a tracker')
def a_project_with_a_tracker(ctx):
    ctx.project = Project(name="Test Project")
    ctx.manager = UndoRedoManager()
    ctx.tracker = ProjectStateTracker(ctx.project, ctx.manager)


@given(parsers.parse('the project holds a task "{name}"'))
def the_project_holds_a_task(ctx, name):
    ctx.task = _task(name)
    ctx.project.add_task(ctx.task)


@given(parsers.parse('the tracker added "{name}"'))
def the_tracker_added(ctx, name):
    ctx.tracker.add_task(_task(name))


# ---- Givens: the dependency pair -----------------------------------------------------


@given('a project with a tracker holding "First" and "Second"')
def a_tracker_holding_first_and_second(ctx):
    ctx.project = Project(name="Test Project")
    ctx.first = Task(id="001", name="First", start_date=BASE,
                     end_date=BASE + timedelta(days=2))
    ctx.second = Task(id="002", name="Second",
                      start_date=BASE + timedelta(days=3),
                      end_date=BASE + timedelta(days=5))
    ctx.project.add_task(ctx.first)
    ctx.project.add_task(ctx.second)
    ctx.manager = UndoRedoManager()
    ctx.manager.set_project(ctx.project)
    ctx.tracker = ProjectStateTracker(ctx.project, ctx.manager)


@given('"Second" already waits for "001" hard')
def second_already_waits(ctx):
    # Keep the live object - it is the one update_task replaces, and the
    # scenario mutates it after the fact to prove the snapshot's copy is
    # independent.
    ctx.old_copy = ctx.project.get_task_by_id("002")
    ctx.old_copy.add_dependency("001", "FS", "Hard")


@given(parsers.parse('the tracker gave "{name}" the dependencies "{ids}"'))
def the_tracker_gave_dependencies(ctx, name, ids):
    ctx.tracker.update_task(name_to_id(ctx.project, name),
                            dependencies=ids.split(', '))


def name_to_id(project, name):
    return next(t.id for t in project.tasks if t.name == name)


# ---- Givens: the branch to delete ------------------------------------------------------


@given('a tracked project of a parent, two children and a dependent')
def a_tracked_branch(ctx):
    ctx.project = Project(name="Test Project")
    ctx.project.add_task(Task(id="001", name="Parent", start_date=BASE,
                              end_date=BASE + timedelta(days=5)))
    for task_id, name in [("002", "Child A"), ("003", "Child B")]:
        ctx.project.add_task(Task(id=task_id, name=name, start_date=BASE,
                                  task_type="Subtask",
                                  parent_task_id="001"))
    later = Task(id="004", name="Later", start_date=BASE + timedelta(days=6),
                 end_date=BASE + timedelta(days=8))
    later.add_dependency("001", "FS", "Hard")
    ctx.project.add_task(later)
    ctx.manager = UndoRedoManager()
    ctx.manager.set_project(ctx.project)
    ctx.tracker = ProjectStateTracker(ctx.project, ctx.manager)


@given(parsers.parse('the tracker removed "{task_id}"'))
def the_tracker_removed(ctx, task_id):
    ctx.tracker.remove_task(task_id)


# ---- Givens: the reorder trio ----------------------------------------------------------


@given(parsers.parse('a tracked project of "{names}"'))
def a_tracked_trio(ctx, names):
    ctx.project = Project(name="Test Project")
    for index, name in enumerate(names.split(', '), start=1):
        ctx.project.add_task(Task(id=f"{index:03d}", name=name,
                                  start_date=BASE,
                                  end_date=BASE + timedelta(days=2)))
    ctx.manager = UndoRedoManager()
    ctx.manager.set_project(ctx.project)
    ctx.tracker = ProjectStateTracker(ctx.project, ctx.manager)


@given(parsers.parse('"{name}" moved to the top, recorded'))
def moved_to_top_recorded(ctx, name):
    before = list(ctx.project.tasks)
    ctx.project.move_task(name_to_id(ctx.project, name), 'top')
    ctx.tracker.reorder_tasks(before, list(ctx.project.tasks))


# ---- Givens: the pool -------------------------------------------------------------------


@given('a tracked project\'s pool')
def a_tracked_pool(ctx):
    ctx.project = Project(name="Test Project")
    ctx.manager = UndoRedoManager()
    ctx.tracker = ProjectStateTracker(ctx.project, ctx.manager)
    ctx.repo_obj = ctx.project.resource_repository


@given('a tracked project\'s pool holding "r1"')
def a_tracked_pool_holding(ctx):
    a_tracked_pool(ctx)
    ctx.project.resource_repository.add_resource(_resource())


@given('a tracked project\'s pool holding "r1" assigned to "Build"')
def a_tracked_pool_assigned(ctx):
    a_tracked_pool_holding(ctx)
    ctx.project.add_task(Task(
        id="001", name="Build", start_date=BASE,
        end_date=BASE + timedelta(days=2),
        resource_assignments=[{"resource_id": "r1",
                               "estimated_hours": 8.0,
                               "resource_split": 100.0}]))


@given(parsers.parse('the pool holds a resource "{rid}" "{name}"'))
def the_pool_holds_a_resource(ctx, rid, name):
    ctx.project.resource_repository.add_resource(_resource(rid, name))


# ---- Whens: commands, manager, tracker ---------------------------------------------


@when('the command executes')
def the_command_executes(ctx):
    ctx.result = ctx.command.execute()
    assert ctx.result


@when('the command undoes')
def the_command_undoes(ctx):
    ctx.result = ctx.command.undo()
    assert ctx.result


@when(parsers.parse('the manager adds "{name}"'))
def the_manager_adds(ctx, name):
    ctx.result = ctx.manager.execute(
        AddTaskCommand(project=ctx.project, task=_task(name)))
    assert ctx.result


@when(parsers.parse('the manager adds {count:d} tasks'))
def the_manager_adds_many(ctx, count):
    for i in range(count):
        ctx.manager.execute(AddTaskCommand(
            project=ctx.project,
            task=Task.create_task(f"Task {i}", START,
                                  START + timedelta(days=i + 1))))


@when('the manager undoes')
def the_manager_undoes(ctx):
    ctx.result = ctx.manager.undo()
    assert ctx.result


@when('the manager redoes')
def the_manager_redoes(ctx):
    ctx.result = ctx.manager.redo()
    assert ctx.result


@when('the manager is cleared')
def the_manager_is_cleared(ctx):
    ctx.manager.clear()


@when(parsers.parse('the tracker adds "{name}"'))
def the_tracker_adds(ctx, name):
    ctx.result = ctx.tracker.add_task(_task(name))
    assert ctx.result


@when('the tracker removes it')
def the_tracker_removes_it(ctx):
    ctx.result = ctx.tracker.remove_task(ctx.task.id)
    assert ctx.result


@when(parsers.parse('the tracker removes "{task_id}"'))
def the_tracker_removes(ctx, task_id):
    ctx.result = ctx.tracker.remove_task(task_id)
    assert ctx.result


@when(parsers.parse('the tracker renames it to "{name}"'))
def the_tracker_renames_it(ctx, name):
    ctx.result = ctx.tracker.update_task(ctx.task.id, name=name)
    assert ctx.result


@when(parsers.parse('the tracker renames the project to "{name}"'))
def the_tracker_renames_the_project(ctx, name):
    ctx.result = ctx.tracker.update_project_name(name)
    assert ctx.result


@when('the tracker undoes')
def the_tracker_undoes(ctx):
    ctx.result = ctx.tracker.undo()
    assert ctx.result


@when('the tracker redoes')
def the_tracker_redoes(ctx):
    ctx.result = ctx.tracker.redo()
    assert ctx.result


@when(parsers.parse('the tracker gives "{name}" the dependencies "{ids}"'))
def the_tracker_gives_dependencies(ctx, name, ids):
    task_id = name_to_id(ctx.project, name)
    ctx.old_copy = ctx.project.get_task_by_id(task_id)
    ctx.result = ctx.tracker.update_task(
        task_id, dependencies=list(ctx.old_copy.dependencies) +
        ids.split(', '))


@when(parsers.parse('the tracker gives "{name}" the dependencies "{ids}" '
                    'and renames it "{new_name}"'))
def the_tracker_gives_and_renames(ctx, name, ids, new_name):
    task_id = name_to_id(ctx.project, name)
    ctx.result = ctx.tracker.update_task(
        task_id, dependencies=ids.split(', '), name=new_name)


@when(parsers.parse('the old copy grows a "{pid}" dependency of "{hard}" '
                    'hardness'))
def the_old_copy_grows(ctx, pid, hard):
    ctx.old_copy.dependencies.append(pid)
    ctx.old_copy.dependencies[0].hardness = hard


@when(parsers.parse('"{name}" moves to the top, recorded'))
def moves_to_top_recorded(ctx, name):
    moved_to_top_recorded(ctx, name)


@when(parsers.parse('a command adds resource "{rid}" "{name}"'))
def a_command_adds_resource(ctx, rid, name):
    repo = ctx.project.resource_repository
    ctx.tracker.run_resource_as_command(
        lambda: (repo.add_resource(_resource(rid, name)) or True),
        "New Resource")


@when(parsers.parse('the pool change "{label}" records "{rid}" taking '
                    'initials "{initials}"'))
def the_pool_change_records(ctx, label, rid, initials):
    repo = ctx.project.resource_repository
    before = repo.to_dict()
    repo.resources[rid].initials = initials
    ctx.recording = ctx.tracker.record_resource_pool_change(before, label)


@when(parsers.parse('the pool change "{label}" records nothing changed'))
def the_pool_change_records_nothing(ctx, label):
    before = ctx.project.resource_repository.to_dict()
    ctx.recording = ctx.tracker.record_resource_pool_change(before, label)


@when(parsers.parse('a command deletes "{rid}" and its assignments'))
def a_command_deletes_resource(ctx, rid):
    def delete_resource():
        ctx.project.resource_repository.remove_resource(rid)
        for each in ctx.project.tasks:
            each.resource_assignments = [
                a for a in each.resource_assignments
                if a.get("resource_id") != rid]
        return True
    ctx.tracker.run_as_command(delete_resource, "Delete Resource")


@when(parsers.parse('a command clears "{name}"\'s assignments in place'))
def a_command_clears_assignments(ctx, name):
    def clear_in_place():
        task = ctx.project.get_task_by_id(name_to_id(ctx.project, name))
        task.resource_assignments.clear()
        return True
    ctx.tracker.run_as_command(clear_in_place, "Clear Assignments")


@when(parsers.parse('a command removes "{rid}" from the pool'))
def a_command_removes_from_pool(ctx, rid):
    repo = ctx.project.resource_repository
    ctx.tracker.run_resource_as_command(
        lambda: (repo.remove_resource(rid) or True), "Delete Resource")


# ---- Thens: bare command outcomes ------------------------------------------------


@then(parsers.parse('the project holds {count:d} task'))
@then(parsers.parse('the project holds {count:d} tasks'))
def the_project_holds(ctx, count):
    assert len(ctx.project.tasks) == count


@then(parsers.parse('the project calls it "{name}"'))
def the_project_calls_it(ctx, name):
    assert ctx.project.tasks[0].name == name


@then(parsers.parse('the project is called "{name}"'))
def the_project_is_called(ctx, name):
    assert ctx.project.name == name


# ---- Thens: stacks ----------------------------------------------------------------


@then('it can undo but not redo')
def can_undo_not_redo(ctx):
    assert ctx.manager.can_undo()
    assert not ctx.manager.can_redo()


@then('it can redo but not undo')
def can_redo_not_undo(ctx):
    assert ctx.manager.can_redo()
    assert not ctx.manager.can_undo()


@then('it cannot redo')
def cannot_redo(ctx):
    assert not ctx.manager.can_redo()


@then('it can undo')
def can_undo(ctx):
    assert ctx.manager.can_undo()


@then('it cannot undo')
def cannot_undo(ctx):
    assert not ctx.manager.can_undo()


@then('the manager\'s undo is refused')
def the_managers_undo_is_refused(ctx):
    assert not ctx.manager.undo()


@then('the manager\'s redo is refused')
def the_managers_redo_is_refused(ctx):
    assert not ctx.manager.redo()


@then(parsers.parse('the undo stack holds {count:d} commands'))
def the_undo_stack_holds(ctx, count):
    assert len(ctx.manager.undo_stack) == count


@then(parsers.parse('the undo description mentions "{text}"'))
def the_undo_description_mentions(ctx, text):
    assert text in ctx.manager.get_undo_description()


@then(parsers.parse('the redo description mentions "{text}"'))
def the_redo_description_mentions(ctx, text):
    assert text in ctx.manager.get_redo_description()


# ---- Thens: factories ----------------------------------------------------------------


@then('the add factory makes an AddTaskCommand on the project')
def the_add_factory(ctx):
    command = create_add_task_command(ctx.project, _task("Another"))
    assert isinstance(command, AddTaskCommand)
    assert command.project is ctx.project


@then('the remove factory makes a RemoveTaskCommand')
def the_remove_factory(ctx):
    task = ctx.project.tasks[0]
    index = ctx.project.tasks.index(task)
    command = create_remove_task_command(ctx.project, task.id, task, index)
    assert isinstance(command, RemoveTaskCommand)


@then('the update factory makes an UpdateTaskCommand')
def the_update_factory(ctx):
    task = ctx.project.tasks[0]
    new_task = Task(id=task.id, name="Updated",
                    start_date=task.start_date, end_date=task.end_date)
    command = create_update_task_command(ctx.project, task.id,
                                         copy.copy(task), new_task)
    assert isinstance(command, UpdateTaskCommand)


@then('the rename factory makes an UpdateProjectNameCommand')
def the_rename_factory(ctx):
    command = create_update_project_name_command(ctx.project, "Old", "New")
    assert isinstance(command, UpdateProjectNameCommand)


@then('the compound factory makes a CompoundCommand')
def the_compound_factory(ctx):
    assert isinstance(create_compound_command([], "Test"),
                      CompoundCommand)


# ---- Thens: tracker ------------------------------------------------------------------


@then('the tracker can undo')
def the_tracker_can_undo(ctx):
    assert ctx.tracker.can_undo()


# ---- Thens: dependencies ----------------------------------------------------------------


@then(parsers.parse('"{name}" waits for "{ids}"'))
def waits_for(ctx, name, ids):
    task = ctx.project.get_task_by_id(name_to_id(ctx.project, name))
    assert task.dependency_ids == ids.split(', ')


@then(parsers.parse('"{name}" waits for nothing'))
def waits_for_nothing(ctx, name):
    task = ctx.project.get_task_by_id(name_to_id(ctx.project, name))
    assert task.dependency_ids == []


@then(parsers.parse('"{name}"\'s "{pid}" link is "{dtype}" and "{hard}"'))
def link_details(ctx, name, pid, dtype, hard):
    task = ctx.project.get_task_by_id(name_to_id(ctx.project, name))
    link = task.get_dependency(pid)
    assert link is not None
    assert link.dep_type == dtype
    assert link.hardness == hard


@then(parsers.parse('task "{task_id}" waits for nothing'))
def id_waits_for_nothing(ctx, task_id):
    assert ctx.project.get_task_by_id(task_id).dependency_ids == []


@then(parsers.parse('task "{task_id}" waits for "{ids}"'))
def id_waits_for(ctx, task_id, ids):
    assert ctx.project.get_task_by_id(task_id).dependency_ids == \
        ids.split(', ')


@then(parsers.parse('task "{task_id}"\'s "{pid}" link is "{dtype}" and '
                    '"{hard}"'))
def id_link_details(ctx, task_id, pid, dtype, hard):
    link = ctx.project.get_task_by_id(task_id).get_dependency(pid)
    assert link is not None
    assert link.dep_type == dtype
    assert link.hardness == hard


@then(parsers.parse('the ids are "{ids}"'))
def the_ids_are(ctx, ids):
    assert _ids(ctx.project) == ids.split(', ')


# ---- Thens: the pool ----------------------------------------------------------------------


@then(parsers.parse('the pool holds "{rid}"'))
def the_pool_holds(ctx, rid):
    assert rid in ctx.project.resource_repository.resources


@then(parsers.parse('the pool does not hold "{rid}"'))
def the_pool_does_not_hold(ctx, rid):
    assert rid not in ctx.project.resource_repository.resources


@then(parsers.parse('the pool calls "{rid}" "{name}"'))
def the_pool_calls(ctx, rid, name):
    assert ctx.project.resource_repository.resources[rid].name == name


@then('the recording was made')
def the_recording_was_made(ctx):
    assert ctx.recording


@then('the recording was not made')
def the_recording_was_not_made(ctx):
    assert not ctx.recording


@then('the manager cannot undo')
def the_manager_cannot_undo(ctx):
    assert not ctx.manager.can_undo()


@then(parsers.parse('the pool\'s "{rid}" initials are "{initials}"'))
def the_pool_initials(ctx, rid, initials):
    assert ctx.project.resource_repository.resources[rid].initials == \
        initials


@then(parsers.parse('"{name}" has {count:d} assignment'))
@then(parsers.parse('"{name}" has {count:d} assignments'))
def has_assignments(ctx, name, count):
    task = ctx.project.get_task_by_id(name_to_id(ctx.project, name))
    assert len(task.resource_assignments) == count


@then(parsers.parse('"{name}" has {count:d} assignment of {hours:g} hours '
                    'at {pct:g} percent'))
def has_assignment_details(ctx, name, count, hours, pct):
    task = ctx.project.get_task_by_id(name_to_id(ctx.project, name))
    assert len(task.resource_assignments) == count
    assert task.resource_assignments[0]['estimated_hours'] == hours
    assert task.resource_assignments[0]['resource_split'] == pct


@then('the repository is the same object')
def the_repository_is_the_same(ctx):
    assert ctx.project.resource_repository is ctx.repo_obj
