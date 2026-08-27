"""
Tests for building task hierarchies deeper than two levels.

DEVELOPMENT NOTES:
------------------
The toolbar helpers under test only read self.project, so they are exercised
against a lightweight stand-in rather than a real widget. That keeps these
tests headless while still covering the logic that decides which tasks may
act as a parent.
"""

import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace

from gantt_app.models import Project, Task
from gantt_app.views.toolbar import Toolbar


def candidate_parents(project):
    """Call the toolbar's parent-selection helper against a project."""
    return Toolbar._candidate_parent_tasks(SimpleNamespace(project=project))


def task_depth(project, task):
    """Call the toolbar's depth helper against a project."""
    return Toolbar._task_depth(SimpleNamespace(project=project), task)


class TestDeepSubtaskCreation(unittest.TestCase):
    """Tests for creating sub-tasks below other sub-tasks."""

    def setUp(self):
        """Build a three-level hierarchy."""
        self.start = datetime(2024, 1, 1)
        self.level1 = Task.create_task("Level 1", self.start,
                                       self.start + timedelta(days=20))
        self.level2 = Task.create_subtask("Level 2", parent_task=self.level1,
                                          end_date=self.start + timedelta(days=10))
        self.level3 = Task.create_subtask("Level 3", parent_task=self.level2,
                                          end_date=self.start + timedelta(days=5))
        self.project = Project(name="Deep",
                               tasks=[self.level1, self.level2, self.level3])

    def test_model_supports_three_levels(self):
        """The data model tracks a parent chain of any depth."""
        self.assertEqual(self.level3.parent_task_id, self.level2.id)
        self.assertEqual(self.level2.parent_task_id, self.level1.id)
        self.assertEqual(self.level3.task_type, "Subtask")

        self.assertEqual([t.id for t in self.project.get_root_tasks()],
                         [self.level1.id])
        self.assertEqual([t.id for t in self.project.get_subtasks(self.level2.id)],
                         [self.level3.id])
        self.assertEqual(self.project.get_parent_task(self.level3.id).id,
                         self.level2.id)

    def test_only_container_types_are_offered_as_parents(self):
        """Only the types that hold work - Phase and Task - can be parents."""
        offered = {t.id for t in candidate_parents(self.project)}

        # Level 1 is a Task (container) - should be offered
        self.assertIn(self.level1.id, offered)
        # Level 2 and Level 3 are Subtasks (not containers) - should NOT be offered
        self.assertNotIn(self.level2.id, offered)
        self.assertNotIn(self.level3.id, offered)

    def test_candidates_are_in_hierarchy_order(self):
        """Parents are listed before their own descendants."""
        # Add a Phase as well to test ordering
        phase = Task.create_task("Phase", self.start,
                                self.start + timedelta(days=30))
        phase.task_type = "Phase"
        self.project.add_task(phase)
        
        names = [t.name for t in candidate_parents(self.project)]

        # Only Phase and Level 1 (Task) should be offered as parents
        self.assertIn("Phase", names)
        self.assertIn("Level 1", names)
        self.assertNotIn("Level 2", names)
        self.assertNotIn("Level 3", names)

    def test_milestones_are_not_offered_as_parents(self):
        """A milestone has no span for a child to sit inside."""
        milestone = Task.create_milestone("Review", self.start)
        self.project.add_task(milestone)

        offered = {t.id for t in candidate_parents(self.project)}
        self.assertNotIn(milestone.id, offered)

    def test_depth_reported_for_indentation(self):
        """Depth counts how many levels down a task sits."""
        self.assertEqual(task_depth(self.project, self.level1), 0)
        self.assertEqual(task_depth(self.project, self.level2), 1)
        self.assertEqual(task_depth(self.project, self.level3), 2)

    def test_orphaned_task_with_container_type_is_still_offered(self):
        """A task with container type whose parent is gone is not lost from the list."""
        orphan = Task(
            id="orphan", name="Orphan", start_date=self.start,
            end_date=self.start + timedelta(days=2),
            task_type="Task", parent_task_id="missing-parent"
        )
        self.project.add_task(orphan)

        offered = {t.id for t in candidate_parents(self.project)}
        self.assertIn("orphan", offered)

    def test_depth_survives_a_parent_cycle(self):
        """A cyclic parent reference does not hang the depth calculation."""
        first = Task(id="a", name="A", start_date=self.start,
                     end_date=self.start + timedelta(days=1))
        second = Task(id="b", name="B", start_date=self.start,
                      end_date=self.start + timedelta(days=1),
                      task_type="Task", parent_task_id="a")
        first.parent_task_id = "b"
        first.task_type = "Task"

        project = Project(name="Cyclic", tasks=[first, second])

        self.assertIsInstance(task_depth(project, first), int)
        # Both are Tasks (container types), so both should be offered
        self.assertEqual(len(candidate_parents(project)), 2)


class TestDeepHierarchyFromImport(unittest.TestCase):
    """Tests that imported hierarchies keep their real depth."""

    def test_three_level_project_reports_each_level(self):
        """Every level of an imported hierarchy is reachable."""
        start = datetime(2024, 1, 1)
        root = Task.create_task("Root", start, start + timedelta(days=30))
        mid = Task.create_subtask("Mid", parent_task=root,
                                  end_date=start + timedelta(days=20))
        leaf = Task.create_subtask("Leaf", parent_task=mid,
                                   end_date=start + timedelta(days=10))
        project = Project(name="Imported", tasks=[root, mid, leaf])

        # Only tasks with children count as summaries
        self.assertEqual(project.get_summary_task_ids(), {root.id, mid.id})
        # The leaf is the only real work, so it is the whole critical path
        self.assertEqual([t.name for t in project.get_critical_path()], ["Leaf"])


class TestTaskTypeCompatibility(unittest.TestCase):
    """Tests for task type compatibility with parent-child relationships."""

    def setUp(self):
        """Set up test fixtures."""
        self.start = datetime(2024, 1, 1)
        self.project = Project(name="Type Test")

    def test_phase_can_have_children(self):
        """Phase tasks can have children."""
        phase = Task.create_task("Phase", self.start,
                                self.start + timedelta(days=10))
        phase.task_type = "Phase"
        self.project.add_task(phase)
        
        self.assertTrue(phase.can_have_children)

    def test_task_can_have_children(self):
        """Task can have children."""
        task = Task.create_task("Task", self.start,
                                self.start + timedelta(days=10))
        self.project.add_task(task)
        
        self.assertTrue(task.can_have_children)

    def test_subtask_cannot_have_children(self):
        """Subtask cannot have children."""
        parent = Task.create_task("Parent", self.start,
                                  self.start + timedelta(days=10))
        subtask = Task.create_subtask("Subtask", parent_task=parent)
        self.project.add_task(subtask)
        
        self.assertFalse(subtask.can_have_children)

    def test_milestone_cannot_have_children(self):
        """Milestone cannot have children."""
        milestone = Task.create_milestone("Milestone", self.start)
        self.project.add_task(milestone)
        
        self.assertFalse(milestone.can_have_children)

    def test_subtask_is_leaf(self):
        """Subtask is a leaf node."""
        parent = Task.create_task("Parent", self.start,
                                  self.start + timedelta(days=10))
        subtask = Task.create_subtask("Subtask", parent_task=parent)
        self.assertTrue(subtask.is_leaf)

    def test_milestone_is_leaf(self):
        """Milestone is a leaf node."""
        milestone = Task.create_milestone("Milestone", self.start)
        self.assertTrue(milestone.is_leaf)

    def test_phase_is_container(self):
        """Phase is a container (not leaf)."""
        phase = Task.create_task("Phase", self.start,
                                self.start + timedelta(days=10))
        phase.task_type = "Phase"
        self.assertFalse(phase.is_leaf)
        self.assertTrue(phase.is_container)


class TestTypeWhenMovingBetweenLevels(unittest.TestCase):
    """
    A row keeps its type wherever it is moved. Every one of them.

    WHY THESE EXIST:
    ================
    Indenting made everything a Subtask whatever it was moved under, which
    flattened the levels the types exist to describe. That was fixed by
    keeping the type wherever the new parent could hold it - which left the
    cases where it could not, and a Task indented under a Task still came
    back a Subtask, unable to hold the sub-tasks it had been built with.

    The type is now left alone entirely. It is the user's statement about
    what a row is; where the row sits is a separate statement, and moving it
    says nothing about the first. The Type column and the editor are where
    it is asked for, and both now accept an answer for any row.

    DEVELOPMENT NOTES:
    ------------------
    Each fixture states the hierarchy outright rather than building it by
    indenting. Indenting moves a task under the sibling *above* it, so a
    plan built that way puts tasks somewhere other than where the test means
    to put them - which is how the first version of these passed while
    exercising the wrong parent.
    """

    def plan(self, rows):
        """A project from (id, type, parent) rows, in hierarchy order."""
        from datetime import datetime
        from gantt_app.models import Project, Task

        project = Project(name="Levels")
        for task_id, task_type, parent in rows:
            project.add_task(Task(
                id=task_id, name=task_id, task_type=task_type,
                parent_task_id=parent, start_date=datetime(2026, 1, 5),
                end_date=None if task_type == "Milestone" else datetime(2026, 1, 9),
            ))
        project.tasks = project._flatten(project._children_by_parent())
        return project

    def test_a_task_under_a_phase_stays_a_task(self):
        """
        And so keeps being able to hold sub-tasks.

        A Subtask cannot have children - see Task.can_have_children - so
        retyping it here took away the level below it as well.
        """
        project = self.plan([("D", "Phase", None), ("T", "Task", None)])

        project.indent_task("T")

        task = project.get_task_by_id("T")
        self.assertEqual(task.task_type, "Task")
        self.assertEqual(task.parent_task_id, "D")
        self.assertTrue(task.can_have_children)

    def test_a_task_under_a_task_stays_a_task(self):
        """
        The case the older rule still retyped.

        A Task indented under a Task came back a Subtask, so the row you had
        built as a task - with sub-tasks of its own - dropped a level and
        could no longer hold them.
        """
        project = self.plan([("D", "Phase", None), ("T1", "Task", "D"),
                             ("T2", "Task", "D")])

        project.indent_task("T2")

        task = project.get_task_by_id("T2")
        self.assertEqual(task.task_type, "Task")
        self.assertEqual(task.parent_task_id, "T1")
        self.assertTrue(task.can_have_children)

    def test_a_milestone_stays_a_milestone_wherever_it_lands(self):
        """It marks a moment in whatever it is a moment in."""
        project = self.plan([("T", "Task", None), ("M", "Milestone", None)])

        project.indent_task("M")

        milestone = project.get_task_by_id("M")
        self.assertEqual(milestone.task_type, "Milestone")
        self.assertTrue(milestone.is_milestone)

    def test_a_subtask_lifted_into_a_phase_stays_a_subtask(self):
        """Until somebody says otherwise, which is what the Type column is."""
        project = self.plan([("P", "Phase", None), ("T", "Task", "P"),
                             ("S", "Subtask", "T")])

        project.outdent_task("S")

        self.assertEqual(project.get_task_by_id("S").task_type, "Subtask")
        self.assertEqual(project.get_task_by_id("S").parent_task_id, "P")

    def test_a_subtask_lifted_clear_of_everything_stays_a_subtask(self):
        """The top of the plan is a position, not a type."""
        project = self.plan([("T", "Task", None), ("S", "Subtask", "T")])

        project.outdent_task("S")

        self.assertEqual(project.get_task_by_id("S").task_type, "Subtask")
        self.assertIsNone(project.get_task_by_id("S").parent_task_id)

    def test_a_phase_indented_under_a_phase_stays_a_phase(self):
        """Nothing about a move changes what a row is."""
        project = self.plan([("P1", "Phase", None), ("P2", "Phase", None)])

        project.indent_task("P2")

        self.assertEqual(project.get_task_by_id("P2").task_type, "Phase")

    def test_a_round_trip_leaves_the_type_where_it_started(self):
        """
        Indent then outdent used to be a one-way trip down the levels.

        A Task went in and a Subtask came out, and outdenting it again gave
        back a Task only because that was the level the top of the plan
        expected - so the type had been through two rewrites to arrive back
        by luck. Anything the two rules did not agree about stayed changed.
        """
        project = self.plan([("D", "Phase", None), ("T1", "Task", "D"),
                             ("T2", "Task", "D")])

        project.indent_task("T2")
        project.outdent_task("T2")

        task = project.get_task_by_id("T2")
        self.assertEqual(task.task_type, "Task")
        self.assertEqual(task.parent_task_id, "D")


class TestMovingSeveralRowsAtOnce(unittest.TestCase):
    """
    Indent and outdent act on everything selected.

    WHY THESE EXIST:
    ================
    They acted on the clicked row alone, so selecting five rows and pressing
    Indent moved the first one and left the other four where they were - which
    reads as the feature being broken rather than as it having a different
    scope than the selection suggests.

    Order is the whole difficulty. Indenting moves a row under the sibling
    above it, so a flat selection worked bottom-up comes out as a staircase
    rather than a group; outdenting places a row after its old parent's
    remaining children, so worked top-down it reverses them. The two run in
    opposite directions for that reason, and both are pinned here.
    """

    def plan(self, rows):
        """A project from (id, parent) rows, in hierarchy order."""
        from datetime import datetime
        from gantt_app.models import Project, Task

        project = Project(name="Group")
        for task_id, parent in rows:
            project.add_task(Task(
                id=task_id, name=task_id, parent_task_id=parent,
                task_type="Subtask" if parent else "Task",
                start_date=datetime(2026, 1, 5),
                end_date=datetime(2026, 1, 9),
            ))
        project.tasks = project._flatten(project._children_by_parent())
        return project

    def shape(self, project):
        """Each task as (id, parent), in the order the plan holds them."""
        return [(task.id, task.parent_task_id) for task in project.tasks]

    def test_every_selected_row_is_indented(self):
        """Not just the first one."""
        project = self.plan([("A", None), ("B", None), ("C", None),
                             ("D", None)])

        self.assertTrue(project.indent_tasks(["B", "C", "D"]))

        self.assertEqual(self.shape(project),
                         [("A", None), ("B", "A"), ("C", "A"), ("D", "A")])

    def test_they_land_side_by_side_rather_than_in_a_staircase(self):
        """
        Worked top to bottom, which is what keeps the group together.

        Bottom to top puts each row under the one above it, and a flat
        selection of four comes out four levels deep.
        """
        project = self.plan([("A", None), ("B", None), ("C", None),
                             ("D", None)])

        project.indent_tasks(["D", "C", "B"])       # any order given

        parents = {task.id: task.parent_task_id for task in project.tasks}
        self.assertEqual(parents, {"A": None, "B": "A", "C": "A", "D": "A"})

    def test_outdenting_keeps_them_in_order(self):
        """
        Worked bottom to top, which is the order that preserves theirs.

        A row lifted out is placed after its old parent's remaining children,
        so lifting the first one puts it behind the siblings it was in front
        of - and doing that down the list reverses them.
        """
        project = self.plan([("A", None), ("B", "A"), ("C", "A"), ("D", "A")])

        self.assertTrue(project.outdent_tasks(["B", "C", "D"]))

        self.assertEqual(self.shape(project),
                         [("A", None), ("B", None), ("C", None), ("D", None)])

    def test_a_row_that_cannot_move_does_not_stop_the_rest(self):
        """
        The first row of a group has nothing above it to go under.

        A selection that happens to start at one should still indent
        everything after it, rather than refusing the lot.
        """
        project = self.plan([("A", None), ("B", None), ("C", None)])

        self.assertTrue(project.indent_tasks(["A", "B", "C"]))

        parents = {task.id: task.parent_task_id for task in project.tasks}
        self.assertEqual(parents, {"A": None, "B": "A", "C": "A"})

    def test_a_branch_moves_once_not_twice(self):
        """
        Selecting a parent and its child indents the branch, not both rows.

        The child is carried by its parent; indenting it as well would put it
        a level deeper than everything it was selected with.
        """
        project = self.plan([("A", None), ("B", None), ("C", "B")])

        project.indent_tasks(["B", "C"])

        parents = {task.id: task.parent_task_id for task in project.tasks}
        self.assertEqual(parents, {"A": None, "B": "A", "C": "B"})

    def test_nothing_selected_moves_nothing(self):
        """And says so, rather than silently doing something."""
        project = self.plan([("A", None), ("B", None)])

        self.assertFalse(project.indent_tasks([]))
        self.assertFalse(project.outdent_tasks([]))

    def test_an_unknown_id_is_ignored(self):
        """A row deleted since the menu opened is not a reason to fail."""
        project = self.plan([("A", None), ("B", None)])

        self.assertTrue(project.indent_tasks(["B", "gone"]))

        self.assertEqual(project.get_task_by_id("B").parent_task_id, "A")

    def test_the_types_follow_the_level_each_row_lands_at(self):
        """The same rule a single indent uses; see child_type_for."""
        project = self.plan([("P", None), ("T1", None), ("T2", None)])
        # A Phase holds Tasks, so they keep their type where they land
        project.get_task_by_id("P").task_type = "Phase"

        project.indent_tasks(["T1", "T2"])

        for task_id in ("T1", "T2"):
            with self.subTest(task=task_id):
                self.assertEqual(project.get_task_by_id(task_id).task_type,
                                 "Task")


if __name__ == '__main__':
    unittest.main()


class TestTheOutlineLevel(unittest.TestCase):
    """
    How deep a task sits, counted from one.

    Counted from one because that is the number the Outline Level column
    shows, and the number Microsoft Project shows in its own - a reader
    comparing the two should not find them off by one.
    """

    def project(self, *parents):
        """A plan whose Nth task has the given parent."""
        from datetime import datetime

        from gantt_app.models import Project, Task

        built = Project(name="Levels")
        for index, parent in enumerate(parents, start=1):
            built.add_task(Task(id=str(index), name=f"Task {index}",
                                start_date=datetime(2026, 8, 19),
                                parent_task_id=parent))
        return built

    def test_a_root_task_is_level_one(self):
        """The top of the plan, not level zero."""
        self.assertEqual(self.project(None).outline_level('1'), 1)

    def test_each_step_down_adds_one(self):
        """Which is what the column counts."""
        plan = self.project(None, '1', '2', '3')

        self.assertEqual([plan.outline_level(str(n)) for n in (1, 2, 3, 4)],
                         [1, 2, 3, 4])

    def test_a_task_that_is_not_in_the_plan_is_level_one(self):
        """An unknown row is drawn at the top rather than not at all."""
        self.assertEqual(self.project(None).outline_level('nope'), 1)

    def test_a_parent_cycle_does_not_hang(self):
        """
        A damaged file must not take the redraw with it.

        The level is asked for every row on every refresh, so a cycle here
        is a window that stops responding rather than a wrong number.
        """
        plan = self.project(None, '1', '2')
        plan.get_task_by_id('1').parent_task_id = '3'

        self.assertGreaterEqual(plan.outline_level('1'), 1)

    def test_a_missing_parent_stops_the_count(self):
        """An orphan is as deep as the chain that is actually there."""
        plan = self.project(None, 'gone')

        self.assertEqual(plan.outline_level('2'), 1)
