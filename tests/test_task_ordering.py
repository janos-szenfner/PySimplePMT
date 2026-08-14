"""
Tests for reordering tasks within a project.

DEVELOPMENT NOTES:
------------------
Ordering lives on Project rather than in the task list widget, so the rules a
move has to obey - staying among siblings, carrying sub-tasks along, never
losing a task - are all checked here without needing a display. The widget
tests only cover the gesture that triggers a move.
"""

import unittest
from datetime import datetime, timedelta

from gantt_app.models import Project, Task


def ids(project):
    """The project's task IDs in order."""
    return [task.id for task in project.tasks]


class TestMoveTask(unittest.TestCase):
    """Moving a task among its siblings."""

    def setUp(self):
        """Three root tasks, the middle one carrying two sub-tasks."""
        self.project = Project(name="Test Project")
        base = datetime(2026, 1, 1)

        for task_id, name in [("001", "Alpha"), ("002", "Beta"),
                              ("003", "Gamma")]:
            self.project.add_task(Task(
                id=task_id, name=name, start_date=base,
                end_date=base + timedelta(days=2),
            ))

        for task_id, name in [("004", "Beta one"), ("005", "Beta two")]:
            self.project.add_task(Task(
                id=task_id, name=name, start_date=base,
                end_date=base + timedelta(days=1),
                task_type="Sub-Task", parent_task_id="002",
            ))

    def test_starting_order_is_insertion_order(self):
        """
        Tasks start in the order they were added.

        add_task appends, so sub-tasks added after the root tasks sit at the
        end of the list rather than behind their parent. The tree nests them
        correctly either way, and the first move rebuilds the list into
        hierarchy order. This is pinned so the expectations below read
        against a known starting point.
        """
        self.assertEqual(ids(self.project),
                         ["001", "002", "003", "004", "005"])

    def test_a_move_groups_subtasks_behind_their_parent(self):
        """Rebuilding the list puts each task's children directly after it."""
        self.project.move_task("001", 'down')

        self.assertEqual(ids(self.project),
                         ["002", "004", "005", "001", "003"])

    def test_move_to_top(self):
        """A task moves to the front of its siblings."""
        self.assertTrue(self.project.move_task("003", 'top'))

        self.assertEqual(ids(self.project),
                         ["003", "001", "002", "004", "005"])

    def test_move_up(self):
        """A task swaps with the sibling above it."""
        self.assertTrue(self.project.move_task("003", 'up'))

        self.assertEqual(ids(self.project),
                         ["001", "003", "002", "004", "005"])

    def test_move_down(self):
        """A task swaps with the sibling below it."""
        self.assertTrue(self.project.move_task("001", 'down'))

        self.assertEqual(ids(self.project),
                         ["002", "004", "005", "001", "003"])

    def test_move_to_bottom(self):
        """A task moves behind all of its siblings."""
        self.assertTrue(self.project.move_task("001", 'bottom'))

        self.assertEqual(ids(self.project),
                         ["002", "004", "005", "003", "001"])

    def test_a_parent_carries_its_subtasks(self):
        """Moving a parent takes its sub-tasks with it."""
        self.assertTrue(self.project.move_task("002", 'top'))

        self.assertEqual(ids(self.project),
                         ["002", "004", "005", "001", "003"])

    def test_subtasks_move_among_themselves(self):
        """A sub-task reorders inside its parent, not into the root list."""
        self.assertTrue(self.project.move_task("005", 'top'))

        self.assertEqual(ids(self.project),
                         ["001", "002", "005", "004", "003"])
        self.assertEqual(
            self.project.get_task_by_id("005").parent_task_id, "002"
        )

    def test_moving_past_the_end_does_nothing(self):
        """A task already at one end reports that it did not move."""
        self.assertFalse(self.project.move_task("001", 'up'))
        self.assertFalse(self.project.move_task("001", 'top'))
        self.assertFalse(self.project.move_task("003", 'down'))
        self.assertFalse(self.project.move_task("003", 'bottom'))

        # Refused moves leave the list exactly as it was
        self.assertEqual(ids(self.project),
                         ["001", "002", "003", "004", "005"])

    def test_an_only_child_cannot_move(self):
        """A sub-task with no siblings has nowhere to go."""
        self.project.remove_task("005")

        self.assertFalse(self.project.move_task("004", 'top'))
        self.assertFalse(self.project.move_task("004", 'bottom'))

    def test_unknown_task_is_ignored(self):
        """Moving a task that is not in the project is a no-op."""
        self.assertFalse(self.project.move_task("nope", 'top'))

    def test_unknown_target_is_rejected(self):
        """A misspelled move target raises rather than moving silently."""
        with self.assertRaises(ValueError):
            self.project.move_task("001", 'sideways')

    def test_no_task_is_lost(self):
        """Every move keeps the full set of tasks."""
        before = set(ids(self.project))

        for task_id, where in [("003", 'top'), ("002", 'bottom'),
                               ("005", 'up'), ("001", 'down')]:
            self.project.move_task(task_id, where)
            self.assertEqual(set(ids(self.project)), before)

    def test_an_orphaned_task_survives_a_move(self):
        """
        A sub-task whose parent is missing is kept.

        Rebuilding the list by walking down from the roots never reaches an
        orphan, so one would vanish on the first move without the sweep that
        collects whatever the walk missed.
        """
        base = datetime(2026, 1, 1)
        self.project.add_task(Task(
            id="099", name="Orphan", start_date=base,
            task_type="Sub-Task", parent_task_id="missing",
        ))

        self.project.move_task("003", 'top')

        self.assertIn("099", ids(self.project))


class TestMoveTaskBefore(unittest.TestCase):
    """Dropping a task onto the position of one of its siblings."""

    def setUp(self):
        """Three root tasks and one sub-task."""
        self.project = Project(name="Test Project")
        base = datetime(2026, 1, 1)

        for task_id, name in [("001", "Alpha"), ("002", "Beta"),
                              ("003", "Gamma")]:
            self.project.add_task(Task(
                id=task_id, name=name, start_date=base,
                end_date=base + timedelta(days=2),
            ))
        self.project.add_task(Task(
            id="004", name="Beta one", start_date=base,
            task_type="Sub-Task", parent_task_id="002",
        ))

    def test_moves_into_the_target_position(self):
        """The dragged task takes the row the target occupied."""
        self.assertTrue(self.project.move_task_before("003", "001"))

        self.assertEqual(ids(self.project), ["003", "001", "002", "004"])

    def test_dropping_onto_a_non_sibling_is_refused(self):
        """A sub-task cannot be dropped onto a root task."""
        self.assertFalse(self.project.move_task_before("004", "001"))

        self.assertEqual(ids(self.project), ["001", "002", "003", "004"])

    def test_dropping_onto_itself_does_nothing(self):
        """A task dropped on its own row stays put."""
        self.assertFalse(self.project.move_task_before("001", "001"))

    def test_unknown_ids_are_ignored(self):
        """A drop involving a task that is gone is a no-op."""
        self.assertFalse(self.project.move_task_before("001", "nope"))
        self.assertFalse(self.project.move_task_before("nope", "001"))


class TestGetSiblings(unittest.TestCase):
    """The sibling group a move is confined to."""

    def setUp(self):
        """Two root tasks, one with a pair of sub-tasks."""
        self.project = Project(name="Test Project")
        base = datetime(2026, 1, 1)
        self.project.add_task(Task(id="001", name="Alpha", start_date=base))
        self.project.add_task(Task(id="002", name="Beta", start_date=base))
        for task_id in ("003", "004"):
            self.project.add_task(Task(
                id=task_id, name=f"Sub {task_id}", start_date=base,
                task_type="Sub-Task", parent_task_id="002",
            ))

    def test_root_tasks_are_siblings(self):
        """Root tasks share the same group."""
        self.assertEqual([t.id for t in self.project.get_siblings("001")],
                         ["001", "002"])

    def test_subtasks_group_under_their_parent(self):
        """A sub-task's siblings are the other children of its parent."""
        self.assertEqual([t.id for t in self.project.get_siblings("003")],
                         ["003", "004"])

    def test_unknown_task_has_no_siblings(self):
        """An ID that is not in the project yields nothing."""
        self.assertEqual(self.project.get_siblings("nope"), [])


if __name__ == '__main__':
    unittest.main()
