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
                task_type="Subtask", parent_task_id="002",
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
            task_type="Subtask", parent_task_id="missing",
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
            task_type="Subtask", parent_task_id="002",
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


class TestIndent(unittest.TestCase):
    """Indenting makes a task a sub-task of the row above it."""

    def setUp(self):
        """Three root tasks."""
        self.project = Project(name="Test Project")
        base = datetime(2026, 1, 1)
        for task_id in ("A", "B", "C"):
            self.project.add_task(Task(
                id=task_id, name=task_id, start_date=base,
                end_date=base + timedelta(days=2),
            ))

    def parent_of(self, task_id):
        """The parent ID recorded on a task."""
        return self.project.get_task_by_id(task_id).parent_task_id

    def test_it_goes_under_the_row_above(self):
        """The preceding sibling becomes the parent."""
        self.assertTrue(self.project.indent_task("B"))

        self.assertEqual(self.parent_of("B"), "A")

    def test_it_keeps_its_type(self):
        """
        The level changes; what the row is does not.

        A Task indented under a Task used to come back a Subtask, which took
        away its ability to hold the sub-tasks it was built with.
        """
        self.project.indent_task("B")

        self.assertEqual(self.project.get_task_by_id("B").task_type, "Task")

    def test_the_first_row_cannot_indent(self):
        """There is nothing above it to go under."""
        self.assertFalse(self.project.can_indent("A"))
        self.assertFalse(self.project.indent_task("A"))

    def test_it_can_nest_further(self):
        """Indenting twice puts a task two levels down."""
        self.project.indent_task("B")
        self.project.indent_task("C")

        self.assertTrue(self.project.indent_task("C"))

        self.assertEqual(self.parent_of("C"), "B")

    def test_a_task_carries_its_subtasks(self):
        """The whole branch moves down a level."""
        self.project.add_task(Task(
            id="B1", name="B1", start_date=datetime(2026, 1, 1),
            task_type="Subtask", parent_task_id="B",
        ))

        self.project.indent_task("B")

        self.assertEqual(self.parent_of("B"), "A")
        self.assertEqual(self.parent_of("B1"), "B")

    def test_a_milestone_cannot_take_children(self):
        """
        Indenting under a milestone is refused.

        A milestone marks a moment rather than spanning one, so it cannot
        bracket sub-tasks - and the next reschedule would promote them
        straight back out again.
        """
        milestone = self.project.get_task_by_id("A")
        milestone.is_milestone = True
        milestone.end_date = None

        self.assertFalse(self.project.can_indent("B"))
        self.assertFalse(self.project.indent_task("B"))

    def test_indenting_under_a_predecessor_is_allowed(self):
        """
        A task can go under something it waits for.

        This is the ordinary way a phase gets built out of the work that
        follows it. Refusing it left Indent greyed out on nearly every row
        of a normal plan, where each task follows the one above.
        """
        self.project.get_task_by_id("B").add_dependency("A", 'FS', 'Hard')

        self.assertTrue(self.project.can_indent("B"))
        self.assertTrue(self.project.indent_task("B"))

    def test_the_link_to_the_new_parent_is_dropped(self):
        """
        A task cannot wait for something it is now part of.

        A summary takes its finish from its children, so a child that must
        also start after that summary finishes has no possible date: every
        pass pushes the child out, which pushes the summary out with it, and
        the schedule never settles.
        """
        self.project.get_task_by_id("B").add_dependency("A", 'FS', 'Hard')

        self.project.indent_task("B")

        self.assertEqual(self.project.get_task_by_id("B").dependency_ids, [])

    def test_an_unrelated_link_survives_the_indent(self):
        """Only links onto the new ancestors go."""
        self.project.get_task_by_id("B").add_dependency("C", 'FS', 'Hard')

        self.project.indent_task("B")

        self.assertEqual(self.project.get_task_by_id("B").dependency_ids,
                         ["C"])

    def test_a_subtask_link_to_the_new_parent_is_dropped_too(self):
        """The whole branch is checked, not only the task itself."""
        self.project.add_task(Task(
            id="B1", name="B1", start_date=datetime(2026, 1, 1),
            task_type="Subtask", parent_task_id="B",
        ))
        self.project.get_task_by_id("B1").add_dependency("A", 'FS', 'Hard')

        self.project.indent_task("B")

        self.assertEqual(self.project.get_task_by_id("B1").dependency_ids, [])

    def test_the_plan_still_settles_afterwards(self):
        """
        The point of dropping the link.

        Left in place it makes the schedule unsatisfiable, and rescheduling
        gives up after its pass limit instead of settling.
        """
        self.project.get_task_by_id("B").add_dependency("A", 'FS', 'Hard')
        self.project.indent_task("B")

        self.project.reschedule()

        self.assertFalse(self.project.reschedule())

    def test_a_cycle_in_the_links_does_not_hang(self):
        """The walk is guarded, so a corrupt file cannot lock it up."""
        self.project.get_task_by_id("B").add_dependency("C", 'FS', 'Hard')
        self.project.get_task_by_id("C").add_dependency("B", 'FS', 'Hard')

        self.project.indent_task("C")       # must return

    def test_the_row_stays_in_place(self):
        """A task indented under the row above does not jump elsewhere."""
        self.project.indent_task("B")

        self.assertEqual(ids(self.project), ["A", "B", "C"])

    def test_an_unknown_task_is_ignored(self):
        """Indenting something that is not there does nothing."""
        self.assertFalse(self.project.indent_task("nope"))


class TestOutdent(unittest.TestCase):
    """Outdenting lifts a task to sit beside its parent."""

    def setUp(self):
        """A parent with two sub-tasks, and a task after it."""
        self.project = Project(name="Test Project")
        base = datetime(2026, 1, 1)
        self.project.add_task(Task(id="A", name="A", start_date=base,
                                   end_date=base + timedelta(days=2)))
        for task_id in ("B", "C"):
            self.project.add_task(Task(
                id=task_id, name=task_id, start_date=base,
                end_date=base + timedelta(days=2),
                task_type="Subtask", parent_task_id="A",
            ))
        self.project.add_task(Task(id="D", name="D", start_date=base,
                                   end_date=base + timedelta(days=2)))

    def test_it_leaves_its_parent(self):
        """The task rises to its parent's level."""
        self.assertTrue(self.project.outdent_task("B"))

        self.assertIsNone(self.project.get_task_by_id("B").parent_task_id)

    def test_it_keeps_its_type_at_the_top_level(self):
        """The top of the plan is a position rather than a type."""
        self.project.outdent_task("B")

        self.assertEqual(self.project.get_task_by_id("B").task_type,
                         "Subtask")

    def test_it_stays_a_subtask_when_still_nested(self):
        """Coming out of a nested level leaves it a sub-task."""
        self.project.indent_task("C")          # C under B, both under A

        self.project.outdent_task("C")         # C back beside B, still in A

        task = self.project.get_task_by_id("C")
        self.assertEqual(task.parent_task_id, "A")
        self.assertEqual(task.task_type, "Subtask")

    def test_a_root_task_cannot_outdent(self):
        """There is no level above the top one."""
        self.assertFalse(self.project.can_outdent("A"))
        self.assertFalse(self.project.outdent_task("A"))

    def test_it_lands_after_its_old_parent(self):
        """The task slots in behind the branch it came out of."""
        self.project.outdent_task("B")

        self.assertEqual(ids(self.project), ["A", "C", "B", "D"])

    def test_it_carries_its_subtasks(self):
        """The whole branch comes up a level."""
        self.project.indent_task("C")          # C under B

        self.project.outdent_task("B")         # B out to the top level

        self.assertIsNone(self.project.get_task_by_id("B").parent_task_id)
        self.assertEqual(self.project.get_task_by_id("C").parent_task_id, "B")

    def test_an_unknown_task_is_ignored(self):
        """Outdenting something that is not there does nothing."""
        self.assertFalse(self.project.outdent_task("nope"))

    def test_outdent_then_indent_restores_the_level(self):
        """
        A task put back returns to the parent it came from.

        Its position among that parent's children does not come back: going
        out moved it past its former siblings, and coming in again puts it at
        the end. That is what every planner does, and Move up is the way back.
        """
        self.project.outdent_task("B")
        self.project.indent_task("B")

        task = self.project.get_task_by_id("B")
        self.assertEqual(task.parent_task_id, "A")
        self.assertEqual(task.task_type, "Subtask")
        self.assertEqual(ids(self.project), ["A", "C", "B", "D"])


class TestStructureSnapshot(unittest.TestCase):
    """
    Capturing the hierarchy for undo.

    DEVELOPMENT NOTES:
    ------------------
    Indenting rewrites parent_task_id and task_type on the tasks themselves,
    so restoring an ordering alone leaves every parent where the indent put
    it - both orderings hold the same objects.
    """

    def setUp(self):
        """Three root tasks."""
        self.project = Project(name="Test Project")
        base = datetime(2026, 1, 1)
        for task_id in ("A", "B", "C"):
            self.project.add_task(Task(id=task_id, name=task_id,
                                       start_date=base,
                                       end_date=base + timedelta(days=2)))

    def test_it_restores_the_hierarchy(self):
        """Parent and type come back, not just the order."""
        snapshot = self.project.structure_snapshot()
        self.project.indent_task("B")

        self.project.restore_structure(snapshot)

        task = self.project.get_task_by_id("B")
        self.assertIsNone(task.parent_task_id)
        self.assertEqual(task.task_type, "Task")

    def test_it_restores_the_order(self):
        """The list comes back as it was."""
        snapshot = self.project.structure_snapshot()
        self.project.move_task("C", 'top')

        self.project.restore_structure(snapshot)

        self.assertEqual(ids(self.project), ["A", "B", "C"])


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
                task_type="Subtask", parent_task_id="002",
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
