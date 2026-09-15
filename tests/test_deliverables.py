"""
Tests for the Deliverables tab's data - the entity, its roll-up and the
hierarchy the grid edits.

WHY THIS MODULE EXISTS:
======================
Deliverables are not tasks: they carry no dates the scheduler works out and
take no part in the Gantt. What they share with tasks is the shape of the
list - a flat collection linked by parent_id - so every rule the task
hierarchy keeps has to hold here too: a branch moves whole, a row cannot be
made its own descendant, and the display order is the order the file keeps.

Progress has a rule of its own. A leaf's percentage is typed or set by its
status - Done is 100, To Do is 0, In Progress keeps what it has - and a
deliverable with children takes the weighted average of theirs, falling
back to the plain average when no weights are set. These tests pin both
halves down: the numbers the roll-up lands on, and the moves the hierarchy
allows and refuses.

Nothing here needs a display.
"""

import unittest
from datetime import datetime

from gantt_app.core.deliverable import (
    Deliverable, DELIVERABLE_STATUSES,
    progress_for_status, rolled_up_deliverable_progress,
    status_for_progress)
from gantt_app.core.models import Project, Task
from gantt_app.utils.undoredo import UndoRedoManager, ProjectStateTracker


def a_task(task_id: str, progress: int = 0,
           parent_task_id=None, task_type: str = 'Task') -> Task:
    """A task worth only an id and a percentage to these tests."""
    today = datetime(2026, 1, 1)
    return Task(id=task_id, name=f'Task {task_id}', start_date=today,
                end_date=today, progress=progress,
                parent_task_id=parent_task_id, task_type=task_type)


class DeliverablePlanTestCase(unittest.TestCase):
    """A plan whose deliverables are named for what they are."""

    def plan(self, *rows) -> Project:
        """A project from (id, parent) pairs, in the order given."""
        project = Project(name="Plan")
        for deliverable_id, parent in rows:
            project.deliverables.append(
                Deliverable.create(name=deliverable_id, parent_id=parent,
                                   deliverable_id=deliverable_id))
        return project

    def shown(self, project) -> list:
        """The deliverables in display order, by identity."""
        return [d.id for d in project.deliverable_display_order()]


class TestTheEntity(unittest.TestCase):
    """What a deliverable is on its own."""

    def test_defaults_are_an_unstarted_leaf(self):
        deliverable = Deliverable.create(name="A")
        self.assertEqual(deliverable.status, 'To Do')
        self.assertEqual(deliverable.progress, 0)
        self.assertEqual(deliverable.weight, 1.0)
        self.assertIsNone(deliverable.parent_id)

    def test_progress_is_clamped(self):
        self.assertEqual(Deliverable.create(progress=140).progress, 100)
        self.assertEqual(Deliverable.create(progress=-5).progress, 0)

    def test_an_unknown_status_reads_as_what_the_progress_says(self):
        deliverable = Deliverable.create(status='Blocked', progress=40)
        self.assertEqual(deliverable.status, 'In Progress')

    def test_status_for_progress_has_three_answers(self):
        self.assertEqual(status_for_progress(0), 'To Do')
        self.assertEqual(status_for_progress(40), 'In Progress')
        self.assertEqual(status_for_progress(100), 'Done')

    def test_progress_for_status(self):
        self.assertEqual(progress_for_status('Done'), 100)
        self.assertEqual(progress_for_status('To Do'), 0)
        # In Progress keeps a partial progress rather than rewriting it.
        self.assertEqual(progress_for_status('In Progress', 60), 60)
        # and starts at 1 on a row that held nothing.
        self.assertEqual(progress_for_status('In Progress', 0), 1)

    def test_statuses_are_the_three_the_grid_offers(self):
        self.assertEqual(DELIVERABLE_STATUSES,
                         ('To Do', 'In Progress', 'Done'))


class TestTheRollUp(unittest.TestCase):
    """How a deliverable takes its progress from the items under it."""

    def test_no_weights_is_the_plain_average(self):
        children = [Deliverable.create(progress=p)
                    for p in (100, 60, 40)]
        self.assertEqual(rolled_up_deliverable_progress(children), 67)

    def test_weights_shift_the_average(self):
        children = [Deliverable.create(progress=100, weight=2),
                    Deliverable.create(progress=60, weight=3),
                    Deliverable.create(progress=40, weight=1)]
        # (200 + 180 + 40) / 6
        self.assertEqual(rolled_up_deliverable_progress(children), 70)

    def test_all_zero_weights_falls_back_to_the_average(self):
        children = [Deliverable.create(progress=100, weight=0),
                    Deliverable.create(progress=0, weight=0)]
        self.assertEqual(rolled_up_deliverable_progress(children), 50)

    def test_no_children_is_zero(self):
        self.assertEqual(rolled_up_deliverable_progress([]), 0)

    def test_roll_up_reaches_every_level(self):
        """A change at the leaf lands on the grandparent, deepest first."""
        project = Project(name="Plan")
        grand = Deliverable.create(name='g', deliverable_id='g')
        parent = Deliverable.create(name='p', parent_id='g',
                                    deliverable_id='p')
        leaf = Deliverable.create(name='l', parent_id='p',
                                  deliverable_id='l', progress=100)
        project.deliverables = [grand, parent, leaf]

        project.roll_up_deliverables()

        self.assertEqual(leaf.progress, 100)
        self.assertEqual(parent.progress, 100)
        self.assertEqual(grand.progress, 100)
        self.assertEqual(grand.status, 'Done')

    def test_roll_up_reports_whether_anything_moved(self):
        project = self_plan()
        self.assertFalse(project.roll_up_deliverables())
        project.deliverables[2].progress = 50
        self.assertTrue(project.roll_up_deliverables())


class TestTheHierarchy(DeliverablePlanTestCase):
    """The moves the grid's indent, outdent and drag gestures make."""

    def test_display_order_is_each_branch_together(self):
        project = self.plan(('a', None), ('b', 'a'), ('c', 'b'), ('d', None))
        self.assertEqual(self.shown(project), ['a', 'b', 'c', 'd'])

    def test_indent_goes_under_the_row_above(self):
        project = self.plan(('a', None), ('b', None))
        self.assertTrue(project.indent_deliverables(['b']))
        self.assertEqual(project.get_deliverable_by_id('b').parent_id, 'a')
        self.assertEqual(self.shown(project), ['a', 'b'])

    def test_the_first_row_cannot_indent(self):
        project = self.plan(('a', None), ('b', None))
        self.assertFalse(project.indent_deliverables(['a']))
        self.assertIsNone(project.get_deliverable_by_id('a').parent_id)

    def test_outdent_comes_out_beside_the_parent(self):
        project = self.plan(('a', None), ('b', 'a'), ('c', 'a'))
        self.assertTrue(project.outdent_deliverables(['b']))
        self.assertIsNone(project.get_deliverable_by_id('b').parent_id)
        self.assertEqual(self.shown(project), ['a', 'c', 'b'])

    def test_reparent_moves_the_whole_branch(self):
        project = self.plan(('a', None), ('b', 'a'), ('c', 'b'),
                            ('d', None))
        self.assertTrue(project.reparent_deliverable('b', 'd'))
        self.assertEqual(project.get_deliverable_by_id('b').parent_id, 'd')
        self.assertEqual(project.get_deliverable_by_id('c').parent_id, 'b')
        self.assertEqual(self.shown(project), ['a', 'd', 'b', 'c'])

    def test_a_branch_cannot_go_under_itself(self):
        project = self.plan(('a', None), ('b', 'a'))
        self.assertFalse(project.can_reparent_deliverable('a', 'b'))
        self.assertFalse(project.reparent_deliverable('a', 'b'))

    def test_moving_to_a_line_below_a_parent_nests_inside_it(self):
        project = self.plan(('a', None), ('b', 'a'), ('c', None))
        self.assertTrue(
            project.move_deliverable_to_line('c', 'a', above=False))
        self.assertEqual(project.get_deliverable_by_id('c').parent_id, 'a')

    def test_move_after_lands_beside_the_anchor_not_inside_it(self):
        """'After' means after the whole subtree - a sibling, not a child."""
        project = self.plan(('a', None), ('b', 'a'), ('c', None))
        self.assertTrue(project.move_deliverable_after('c', 'a'))
        self.assertIsNone(project.get_deliverable_by_id('c').parent_id)
        self.assertEqual(self.shown(project), ['a', 'b', 'c'])

    def test_move_up_and_down_stay_among_siblings(self):
        project = self.plan(('a', None), ('b', 'a'), ('c', 'a'),
                            ('d', 'a'))
        self.assertTrue(project.move_deliverables(['c'], 'up'))
        self.assertEqual(self.shown(project), ['a', 'c', 'b', 'd'])
        self.assertTrue(project.move_deliverables(['c'], 'down'))
        self.assertEqual(self.shown(project), ['a', 'b', 'c', 'd'])

    def test_sorting_happens_inside_each_group(self):
        project = self.plan(('a', None), ('z', 'a'), ('b', 'a'),
                            ('d', None))
        project.sort_deliverables(lambda d: d.name)
        self.assertEqual(self.shown(project), ['a', 'b', 'z', 'd'])

    def test_topmost_of_selection_drops_the_nested_rows(self):
        project = self.plan(('a', None), ('b', 'a'), ('c', None))
        self.assertEqual(
            project.topmost_deliverables_of(['a', 'b', 'c']),
            ['a', 'c'])

    def test_removing_a_row_takes_the_branch_with_it(self):
        project = self.plan(('a', None), ('b', 'a'), ('c', 'b'),
                            ('d', None))
        self.assertTrue(project.remove_deliverable('a'))
        self.assertEqual(self.shown(project), ['d'])

    def test_next_id_counts_on_from_the_highest(self):
        project = self.plan(('001', None), ('002', None))
        self.assertEqual(project.next_deliverable_id(), '003')

    def test_display_ids_count_down_the_order(self):
        project = self.plan(('a', None), ('b', 'a'), ('c', None))
        self.assertEqual(project.deliverable_display_ids(),
                         {'a': 1, 'b': 2, 'c': 3})


class TestSerialization(unittest.TestCase):
    """Deliverables going to the file and coming back."""

    def test_round_trip_keeps_every_field(self):
        project = Project(name="Plan")
        project.deliverables.append(Deliverable.create(
            name="API", deliverable_id='001', status='In Progress',
            progress=40, weight=2.5, assignee='@Sarah',
            due_date=datetime(2026, 9, 1), priority='High',
            tags=['backend'], details='the acceptance criteria'))
        project.deliverables.append(Deliverable.create(
            name="DB schema", parent_id='001', deliverable_id='002'))

        loaded = Project.from_dict(project.to_dict())

        self.assertEqual(len(loaded.deliverables), 2)
        first = loaded.get_deliverable_by_id('001')
        self.assertEqual(first.name, 'API')
        self.assertEqual(first.progress, 40)
        self.assertEqual(first.weight, 2.5)
        self.assertEqual(first.assignee, '@Sarah')
        self.assertEqual(first.due_date, datetime(2026, 9, 1))
        self.assertEqual(first.priority, 'High')
        self.assertEqual(first.tags, ['backend'])
        self.assertEqual(first.details, 'the acceptance criteria')
        self.assertEqual(loaded.get_deliverable_by_id('002').parent_id,
                         '001')

    def test_a_file_without_the_key_loads_empty(self):
        """Every plan saved before this tab existed means none owed."""
        data = Project(name="Plan").to_dict()
        data.pop('deliverables')
        self.assertEqual(Project.from_dict(data).deliverables, [])

    def test_an_unreadable_entry_is_skipped_not_fatal(self):
        data = Project(name="Plan").to_dict()
        data['deliverables'] = ['not a dict',
                                Deliverable.create(name='ok',
                                                   deliverable_id='x')
                                .to_dict()]
        loaded = Project.from_dict(data)
        self.assertEqual([d.id for d in loaded.deliverables], ['x'])


class TestUndo(DeliverablePlanTestCase):
    """Every grid gesture lands as one undoable step."""

    def setUp(self):
        self.project = self.plan(('a', None), ('b', 'a'), ('c', None))
        self.manager = UndoRedoManager()
        self.tracker = ProjectStateTracker(self.project, self.manager)

    def test_a_change_undoes_and_redoes(self):
        leaf = self.project.get_deliverable_by_id('b')

        def apply():
            leaf.progress = 100
            leaf.status = 'Done'
            self.project.roll_up_deliverables()
            return True

        self.tracker.run_deliverable_as_command(apply, 'Finish')
        self.assertEqual(leaf.progress, 100)
        self.assertEqual(
            self.project.get_deliverable_by_id('a').progress, 100)

        self.assertTrue(self.manager.undo())
        self.assertEqual(leaf.progress, 0)
        self.assertEqual(
            self.project.get_deliverable_by_id('a').progress, 0)

        self.assertTrue(self.manager.redo())
        self.assertEqual(leaf.progress, 100)

    def test_a_restructure_undoes_to_the_old_shape(self):
        self.tracker.run_deliverable_as_command(
            lambda: self.project.reparent_deliverable('c', 'a'),
            'Re-parent')
        self.assertEqual(
            self.project.get_deliverable_by_id('c').parent_id, 'a')

        self.manager.undo()
        self.assertIsNone(
            self.project.get_deliverable_by_id('c').parent_id)
        self.assertEqual(self.shown(self.project), ['a', 'b', 'c'])

    def test_an_action_that_changed_nothing_leaves_no_entry(self):
        before = self.manager.can_undo()
        self.tracker.run_deliverable_as_command(lambda: False, 'Nothing')
        self.assertEqual(self.manager.can_undo(), before)


class TestTaskAssignment(DeliverablePlanTestCase):
    """
    The many-to-many link: tasks assigned to deliverables, and the
    progress they lend them.
    """

    def plan_with_tasks(self, *rows) -> Project:
        """A deliverable plan plus two half-done tasks."""
        project = self.plan(*rows)
        project.tasks = [a_task('t1', progress=40),
                         a_task('t2', progress=80)]
        return project

    def test_a_task_can_sit_under_several_deliverables(self):
        project = self.plan_with_tasks(('a', None), ('b', None))
        project.get_deliverable_by_id('a').task_ids = ['t1']
        project.get_deliverable_by_id('b').task_ids = ['t1']

        self.assertEqual(
            [d.id for d in project.deliverables_for_task('t1')],
            ['a', 'b'])

    def test_a_deliverable_can_hold_several_tasks(self):
        project = self.plan_with_tasks(('a', None))
        project.get_deliverable_by_id('a').task_ids = ['t1', 't2']

        self.assertEqual(
            [t.id for t in project.tasks_for_deliverable('a')],
            ['t1', 't2'])

    def test_assigned_tasks_count_into_the_progress(self):
        project = self.plan_with_tasks(('a', None))
        project.get_deliverable_by_id('a').task_ids = ['t1', 't2']

        project.roll_up_deliverables()

        self.assertEqual(
            project.get_deliverable_by_id('a').progress, 60)
        self.assertEqual(
            project.get_deliverable_by_id('a').status, 'In Progress')

    def test_children_and_tasks_count_together(self):
        """A parent's inputs are its children AND its own assigned tasks."""
        project = self.plan_with_tasks(('p', None), ('c', 'p'))
        project.get_deliverable_by_id('c').progress = 100
        project.get_deliverable_by_id('p').task_ids = ['t1']

        project.roll_up_deliverables()

        # (child 100 x weight 1 + task 40 x weight 1) / 2
        self.assertEqual(
            project.get_deliverable_by_id('p').progress, 70)

    def test_tasks_and_subtasks_and_milestones_all_count(self):
        project = self.plan(('a', None))
        project.tasks = [
            a_task('t1', progress=100),
            a_task('t2', progress=50, parent_task_id='t1',
                   task_type='Subtask'),
            a_task('t3', progress=0, task_type='Milestone'),
        ]
        project.get_deliverable_by_id('a').task_ids = ['t1', 't2', 't3']

        project.roll_up_deliverables()

        self.assertEqual(
            project.get_deliverable_by_id('a').progress, 50)

    def test_the_same_task_counts_under_each_row_it_feeds(self):
        project = self.plan_with_tasks(('a', None), ('b', None))
        project.get_deliverable_by_id('a').task_ids = ['t1']
        project.get_deliverable_by_id('b').task_ids = ['t1']

        project.roll_up_deliverables()

        self.assertEqual(project.get_deliverable_by_id('a').progress, 40)
        self.assertEqual(project.get_deliverable_by_id('b').progress, 40)

    def test_set_task_deliverables_writes_both_sides(self):
        project = self.plan_with_tasks(('a', None), ('b', None))
        project.get_deliverable_by_id('a').task_ids = ['t1']

        project.set_task_deliverables('t1', ['b'])

        self.assertEqual(project.get_deliverable_by_id('a').task_ids, [])
        self.assertEqual(project.get_deliverable_by_id('b').task_ids,
                         ['t1'])

    def test_set_task_deliverables_that_changes_nothing_is_a_noop(self):
        project = self.plan_with_tasks(('a', None))
        self.assertFalse(project.set_task_deliverables('t1', []))
        project.set_task_deliverables('t1', ['a'])
        self.assertFalse(project.set_task_deliverables('t1', ['a']))

    def test_removing_the_last_task_hands_progress_back(self):
        """With no inputs left, the roll-up leaves the row alone."""
        project = self.plan_with_tasks(('a', None))
        deliverable = project.get_deliverable_by_id('a')
        deliverable.task_ids = ['t1']
        project.roll_up_deliverables()
        self.assertEqual(deliverable.progress, 40)

        deliverable.task_ids = []
        deliverable.progress = 90
        project.roll_up_deliverables()

        self.assertEqual(deliverable.progress, 90)

    def test_removing_a_task_prunes_it_from_membership(self):
        project = self.plan_with_tasks(('a', None), ('b', None))
        project.get_deliverable_by_id('a').task_ids = ['t1', 't2']
        project.get_deliverable_by_id('b').task_ids = ['t1']

        project.remove_task('t1')

        self.assertEqual(project.get_deliverable_by_id('a').task_ids,
                         ['t2'])
        self.assertEqual(project.get_deliverable_by_id('b').task_ids, [])

    def test_removing_a_task_re_rolls_the_progress(self):
        project = self.plan_with_tasks(('a', None))
        project.get_deliverable_by_id('a').task_ids = ['t1', 't2']
        project.roll_up_deliverables()
        self.assertEqual(project.get_deliverable_by_id('a').progress, 60)

        project.remove_task('t1')

        self.assertEqual(project.get_deliverable_by_id('a').progress, 80)

    def test_membership_survives_a_round_trip(self):
        project = self.plan_with_tasks(('a', None))
        project.get_deliverable_by_id('a').task_ids = ['t2', 't1']

        loaded = Project.from_dict(project.to_dict())

        self.assertEqual(
            loaded.get_deliverable_by_id('a').task_ids, ['t2', 't1'])

    def test_ids_of_tasks_that_do_not_exist_are_pruned_on_load(self):
        project = self.plan_with_tasks(('a', None))
        data = project.to_dict()
        data['deliverables'][0]['task_ids'] = ['t1', 'ghost']

        loaded = Project.from_dict(data)

        self.assertEqual(
            loaded.get_deliverable_by_id('a').task_ids, ['t1'])

    def test_a_file_without_the_key_loads_empty(self):
        data = Deliverable.create(name='x', deliverable_id='a').to_dict()
        del data['task_ids']
        self.assertEqual(Deliverable.from_dict(data).task_ids, [])

    def test_duplicate_ids_are_kept_once(self):
        deliverable = Deliverable.create(task_ids=['t1', 't1', 't2'])
        self.assertEqual(deliverable.task_ids, ['t1', 't2'])


class TestAssignmentUndo(DeliverablePlanTestCase):
    """Assigning and removing tasks is one undoable step either way."""

    def setUp(self):
        self.project = self.plan(('a', None), ('b', None))
        self.project.tasks = [a_task('t1', progress=50)]
        self.manager = UndoRedoManager()
        self.tracker = ProjectStateTracker(self.project, self.manager)

    def test_an_assign_undoes_and_redoes(self):
        self.tracker.run_deliverable_as_command(
            lambda: self.project.set_task_deliverables('t1', ['a']),
            'Assign')

        self.assertEqual(
            self.project.get_deliverable_by_id('a').task_ids, ['t1'])

        self.assertTrue(self.manager.undo())
        self.assertEqual(
            self.project.get_deliverable_by_id('a').task_ids, [])

        self.assertTrue(self.manager.redo())
        self.assertEqual(
            self.project.get_deliverable_by_id('a').task_ids, ['t1'])

    def test_the_progress_the_assign_derived_undoes_with_it(self):
        self.tracker.run_deliverable_as_command(
            lambda: self.project.set_task_deliverables('t1', ['a']),
            'Assign')
        self.assertEqual(
            self.project.get_deliverable_by_id('a').progress, 50)

        self.manager.undo()
        deliverable = self.project.get_deliverable_by_id('a')
        self.assertEqual(deliverable.task_ids, [])
        # The derived number goes back with the membership that made it.
        self.assertEqual(deliverable.progress, 0)

    def test_undoing_a_task_delete_restores_the_membership(self):
        deliverable = self.project.get_deliverable_by_id('a')
        deliverable.task_ids = ['t1']
        self.project.roll_up_deliverables()
        self.assertEqual(deliverable.progress, 50)

        from gantt_app.utils.undoredo import RemoveTaskCommand
        self.manager.execute(RemoveTaskCommand(
            self.project, 't1',
            self.project.get_task_by_id('t1'), 0))

        self.assertEqual(deliverable.task_ids, [])

        self.assertTrue(self.manager.undo())
        self.assertEqual(
            self.project.get_deliverable_by_id('a').task_ids, ['t1'])


def self_plan() -> Project:
    """A two-child deliverable, for the roll-up flag test."""
    project = Project(name="Plan")
    parent = Deliverable.create(name='p', deliverable_id='p')
    project.deliverables = [
        parent,
        Deliverable.create(name='x', parent_id='p', deliverable_id='x'),
        Deliverable.create(name='y', parent_id='p', deliverable_id='y'),
    ]
    project.roll_up_deliverables()
    return project


if __name__ == '__main__':
    unittest.main()
