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
        self.assertEqual(self.level3.task_type, "Sub-Task")

        self.assertEqual([t.id for t in self.project.get_root_tasks()],
                         [self.level1.id])
        self.assertEqual([t.id for t in self.project.get_subtasks(self.level2.id)],
                         [self.level3.id])
        self.assertEqual(self.project.get_parent_task(self.level3.id).id,
                         self.level2.id)

    def test_subtasks_are_offered_as_parents(self):
        """A sub-task can be chosen as the parent of a new sub-task."""
        offered = {t.id for t in candidate_parents(self.project)}

        self.assertIn(self.level1.id, offered)
        self.assertIn(self.level2.id, offered)
        self.assertIn(self.level3.id, offered)

    def test_candidates_are_in_hierarchy_order(self):
        """Parents are listed before their own descendants."""
        names = [t.name for t in candidate_parents(self.project)]

        self.assertEqual(names, ["Level 1", "Level 2", "Level 3"])

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

    def test_orphaned_subtask_is_still_offered(self):
        """A sub-task whose parent is gone is not lost from the list."""
        orphan = Task(
            id="orphan", name="Orphan", start_date=self.start,
            end_date=self.start + timedelta(days=2),
            task_type="Sub-Task", parent_task_id="missing-parent"
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
                      task_type="Sub-Task", parent_task_id="a")
        first.parent_task_id = "b"
        first.task_type = "Sub-Task"

        project = Project(name="Cyclic", tasks=[first, second])

        self.assertIsInstance(task_depth(project, first), int)
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


if __name__ == '__main__':
    unittest.main()
