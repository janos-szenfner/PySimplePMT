"""
Tests for typed dependency links and the scheduling they imply.
"""

import unittest
from datetime import datetime, timedelta

from gantt_app.models import (
    Dependency, DependencyList, Project, Task,
    DEPENDENCY_TYPE_LABELS,
)


class TestDependency(unittest.TestCase):
    """Tests for the Dependency value object."""

    def test_defaults_to_a_hard_finish_start_link(self):
        """A bare task ID becomes the most common kind of link."""
        dependency = Dependency.from_any('001')

        self.assertEqual(dependency.task_id, '001')
        self.assertEqual(dependency.dep_type, 'FS')
        self.assertEqual(dependency.hardness, 'Hard')

    def test_labels_match_the_user_interface(self):
        """The stored codes map onto the labels shown in the dialog."""
        self.assertEqual(DEPENDENCY_TYPE_LABELS['SS'], 'Start - Start')
        self.assertEqual(DEPENDENCY_TYPE_LABELS['FS'], 'End - Start')
        self.assertEqual(Dependency('1', 'SS').type_label, 'Start - Start')

    def test_values_are_normalised(self):
        """Case and unknown values settle on something valid."""
        self.assertEqual(Dependency('1', 'ss', 'rubber').dep_type, 'SS')
        self.assertEqual(Dependency('1', 'ss', 'rubber').hardness, 'Rubber')
        self.assertEqual(Dependency('1', 'nonsense', 'nonsense').dep_type, 'FS')
        self.assertEqual(Dependency('1', 'nonsense', 'nonsense').hardness, 'Hard')

    def test_round_trips_through_a_dictionary(self):
        """A link survives serialization."""
        original = Dependency('007', 'SS', 'Rubber')
        restored = Dependency.from_any(original.to_dict())

        self.assertEqual(restored, original)


class TestDependencyList(unittest.TestCase):
    """Tests for the list that keeps dependencies normalised."""

    def test_append_accepts_a_bare_id(self):
        """Existing code appends task IDs; they are coerced."""
        links = DependencyList()
        links.append('001')

        self.assertIsInstance(links[0], Dependency)
        self.assertEqual(links[0].task_id, '001')

    def test_membership_by_id(self):
        """`'001' in links` works as it did before links had a type."""
        links = DependencyList(['001'])

        self.assertIn('001', links)
        self.assertNotIn('002', links)

    def test_task_assignment_is_coerced(self):
        """Assigning a plain list of IDs to a task still works."""
        task = Task.create_task("T", datetime(2024, 1, 1), datetime(2024, 1, 5))
        task.dependencies = ['001', '002']

        self.assertEqual(task.dependency_ids, ['001', '002'])
        self.assertTrue(all(isinstance(d, Dependency) for d in task.dependencies))

    def test_append_on_the_task_is_coerced(self):
        """task.dependencies.append(id) does not leave a raw string behind."""
        task = Task.create_task("T", datetime(2024, 1, 1), datetime(2024, 1, 5))
        task.dependencies.append('003')

        self.assertEqual(task.dependency_ids, ['003'])


class TestTaskDependencyHelpers(unittest.TestCase):
    """Tests for adding, finding and removing links on a task."""

    def setUp(self):
        """Set up test fixtures."""
        self.task = Task.create_task("T", datetime(2024, 1, 1),
                                     datetime(2024, 1, 5))

    def test_add_dependency(self):
        """A link is stored with its type and hardness."""
        self.task.add_dependency('001', 'SS', 'Rubber')
        link = self.task.get_dependency('001')

        self.assertEqual(link.dep_type, 'SS')
        self.assertEqual(link.hardness, 'Rubber')

    def test_adding_twice_updates_rather_than_duplicates(self):
        """The same predecessor cannot be linked twice."""
        self.task.add_dependency('001', 'FS', 'Hard')
        self.task.add_dependency('001', 'SS', 'Rubber')

        self.assertEqual(len(self.task.dependencies), 1)
        self.assertEqual(self.task.get_dependency('001').dep_type, 'SS')

    def test_remove_dependency(self):
        """A link can be removed by predecessor ID."""
        self.task.add_dependency('001')

        self.assertTrue(self.task.remove_dependency('001'))
        self.assertEqual(self.task.dependencies, [])
        self.assertFalse(self.task.remove_dependency('001'))


class TestDependencyScheduling(unittest.TestCase):
    """Tests for the start date each link type and hardness produces."""

    def setUp(self):
        """A predecessor running 1 to 5 January, and a later dependent task."""
        self.project = Project(name="Scheduling")
        self.first = Task.create_task("First", datetime(2024, 1, 1),
                                      datetime(2024, 1, 5),
                                      task_id=self.project.next_task_id())
        self.project.add_task(self.first)

        self.second = Task.create_task("Second", datetime(2024, 1, 20),
                                       datetime(2024, 1, 24),
                                       task_id=self.project.next_task_id())
        self.project.add_task(self.second)

    def _link(self, dep_type, hardness):
        """Attach a single link and reschedule."""
        self.second.start_date = datetime(2024, 1, 20)
        self.second.end_date = datetime(2024, 1, 24)
        self.second.dependencies = []
        self.second.add_dependency(self.first.id, dep_type, hardness)
        self.project.apply_dependency_constraints(self.second)

    def test_end_start_hard_starts_after_the_predecessor(self):
        """End - Start pins the task to the day after the predecessor ends."""
        self._link('FS', 'Hard')

        self.assertEqual(self.second.start_date, datetime(2024, 1, 6))

    def test_start_start_hard_matches_the_predecessor_start(self):
        """Start - Start pins the task to the predecessor's start."""
        self._link('SS', 'Hard')

        self.assertEqual(self.second.start_date, datetime(2024, 1, 1))

    def test_hard_link_preserves_duration(self):
        """Moving a task keeps its length."""
        self._link('FS', 'Hard')

        self.assertEqual(self.second.duration_days, 5)
        self.assertEqual(self.second.end_date, datetime(2024, 1, 10))

    def test_rubber_allows_a_later_start(self):
        """A Rubber link is a floor, so a later start is left alone."""
        self._link('FS', 'Rubber')

        self.assertEqual(self.second.start_date, datetime(2024, 1, 20))

    def test_rubber_pushes_an_earlier_start_forward(self):
        """A Rubber link still forbids starting too early."""
        self.second.start_date = datetime(2024, 1, 2)
        self.second.end_date = datetime(2024, 1, 6)
        self.second.dependencies = []
        self.second.add_dependency(self.first.id, 'FS', 'Rubber')
        self.project.apply_dependency_constraints(self.second)

        self.assertEqual(self.second.start_date, datetime(2024, 1, 6))

    def test_a_hard_link_wins_over_a_rubber_one(self):
        """Hard links fix the date regardless of any rubber floor."""
        third = Task.create_task("Third", datetime(2024, 2, 1),
                                 datetime(2024, 2, 5),
                                 task_id=self.project.next_task_id())
        self.project.add_task(third)

        self.second.dependencies = []
        self.second.add_dependency(self.first.id, 'SS', 'Hard')
        self.second.add_dependency(third.id, 'FS', 'Rubber')
        self.project.apply_dependency_constraints(self.second)

        self.assertEqual(self.second.start_date, self.first.start_date)

    def test_latest_hard_link_applies(self):
        """With several hard links, the latest requirement wins."""
        third = Task.create_task("Third", datetime(2024, 3, 1),
                                 datetime(2024, 3, 5),
                                 task_id=self.project.next_task_id())
        self.project.add_task(third)

        self.second.dependencies = []
        self.second.add_dependency(self.first.id, 'FS', 'Hard')
        self.second.add_dependency(third.id, 'FS', 'Hard')
        self.project.apply_dependency_constraints(self.second)

        self.assertEqual(self.second.start_date, datetime(2024, 3, 6))

    def test_milestone_predecessor_uses_its_own_date(self):
        """A milestone has no end, so both types resolve to its date."""
        milestone = Task.create_milestone("Gate", datetime(2024, 1, 15),
                                          task_id=self.project.next_task_id())
        self.project.add_task(milestone)

        for dep_type in ('SS', 'FS'):
            self.second.start_date = datetime(2024, 1, 20)
            self.second.dependencies = []
            self.second.add_dependency(milestone.id, dep_type, 'Hard')
            self.project.apply_dependency_constraints(self.second)
            self.assertEqual(self.second.start_date, datetime(2024, 1, 15),
                             dep_type)

    def test_no_links_leaves_the_task_alone(self):
        """A task with no dependencies is never moved."""
        self.second.dependencies = []

        self.assertIsNone(self.project.constrained_start_date(self.second))
        self.assertFalse(self.project.apply_dependency_constraints(self.second))

    def test_missing_predecessor_is_ignored(self):
        """A link to a task that is not in the project does not crash."""
        self.second.dependencies = []
        self.second.add_dependency('does-not-exist', 'FS', 'Hard')

        self.assertIsNone(self.project.constrained_start_date(self.second))


class TestDependencyPersistence(unittest.TestCase):
    """Tests that links survive saving and loading."""

    def test_project_round_trip_keeps_type_and_hardness(self):
        """Serialising a project preserves each link's settings."""
        project = Project(name="Persist")
        first = Task.create_task("First", datetime(2024, 1, 1),
                                 datetime(2024, 1, 5),
                                 task_id=project.next_task_id())
        project.add_task(first)

        second = Task.create_task("Second", datetime(2024, 1, 6),
                                  datetime(2024, 1, 10),
                                  task_id=project.next_task_id())
        second.add_dependency(first.id, 'SS', 'Rubber')
        project.add_task(second)

        restored = Project.from_dict(project.to_dict())
        link = restored.get_task_by_id(second.id).get_dependency(first.id)

        self.assertIsNotNone(link)
        self.assertEqual(link.dep_type, 'SS')
        self.assertEqual(link.hardness, 'Rubber')

    def test_old_projects_still_load(self):
        """A file saved when dependencies were bare IDs loads unchanged."""
        old_format = {
            'name': 'Legacy',
            'start_date': None,
            'end_date': None,
            'tasks': [
                {
                    'id': '001', 'name': 'First',
                    'start_date': '2024-01-01T00:00:00',
                    'end_date': '2024-01-05T00:00:00',
                    'progress': 0, 'dependencies': [], 'color': '#1f6aa5',
                    'is_milestone': False, 'task_type': 'Task',
                    'parent_task_id': None,
                },
                {
                    'id': '002', 'name': 'Second',
                    'start_date': '2024-01-06T00:00:00',
                    'end_date': '2024-01-10T00:00:00',
                    'progress': 0, 'dependencies': ['001'], 'color': '#1f6aa5',
                    'is_milestone': False, 'task_type': 'Task',
                    'parent_task_id': None,
                },
            ],
        }

        project = Project.from_dict(old_format)
        link = project.get_task_by_id('002').get_dependency('001')

        self.assertIsNotNone(link)
        self.assertEqual(link.dep_type, 'FS')
        self.assertEqual(link.hardness, 'Hard')


class TestGanttProjectLinks(unittest.TestCase):
    """Tests that GanttProject's own link settings are carried across."""

    def test_hardness_is_read_from_the_file(self):
        """GanttProject writes Strong or Rubber; both are understood."""
        import os
        import tempfile

        from gantt_app.utils.gan_importer import import_gan_file

        xml = '''<?xml version="1.0" encoding="UTF-8"?>
<project name="Links">
    <tasks>
        <task id="1" name="First" start="2024-01-01" duration="3">
            <depend id="2" type="2" difference="0" hardness="Strong"/>
            <depend id="3" type="1" difference="0" hardness="Rubber"/>
        </task>
        <task id="2" name="Second" start="2024-01-04" duration="2"/>
        <task id="3" name="Third" start="2024-01-01" duration="2"/>
    </tasks>
</project>
'''
        directory = tempfile.mkdtemp()
        path = os.path.join(directory, 'links.gan')
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write(xml)

        project = import_gan_file(path)

        second = project.get_task_by_id('2').get_dependency('1')
        self.assertEqual(second.dep_type, 'FS')
        self.assertEqual(second.hardness, 'Hard')

        third = project.get_task_by_id('3').get_dependency('1')
        self.assertEqual(third.dep_type, 'SS')
        self.assertEqual(third.hardness, 'Rubber')


if __name__ == '__main__':
    unittest.main()
