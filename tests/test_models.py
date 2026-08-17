"""
Unit tests for data models (Task and Project classes).
"""

import unittest
import json
from datetime import datetime, timedelta
import uuid

from gantt_app.models import Task, Project


class TestTask(unittest.TestCase):
    """Test cases for the Task class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_id = str(uuid.uuid4())
        self.start_date = datetime(2024, 1, 1)
        self.end_date = datetime(2024, 1, 10)
        self.task_name = "Test Task"
    
    def test_create_task_basic(self):
        """Test creating a basic task."""
        task = Task(
            id=self.test_id,
            name=self.task_name,
            start_date=self.start_date,
            end_date=self.end_date
        )
        
        self.assertEqual(task.id, self.test_id)
        self.assertEqual(task.name, self.task_name)
        self.assertEqual(task.start_date, self.start_date)
        self.assertEqual(task.end_date, self.end_date)
        self.assertEqual(task.progress, 0)
        self.assertEqual(task.dependency_ids, [])
        self.assertEqual(task.color, "#1f6aa5")
        self.assertFalse(task.is_milestone)
    
    def test_create_task_factory_method(self):
        """Test the create_task factory method."""
        task = Task.create_task(
            name="Factory Task",
            start_date=self.start_date,
            end_date=self.end_date,
            color="#3498db",
            progress=50,
            dependencies=["dep1", "dep2"]
        )
        
        self.assertIsNotNone(task.id)
        self.assertEqual(task.name, "Factory Task")
        self.assertEqual(task.start_date, self.start_date)
        self.assertEqual(task.end_date, self.end_date)
        self.assertEqual(task.color, "#3498db")
        self.assertEqual(task.progress, 50)
        self.assertEqual(task.dependency_ids, ["dep1", "dep2"])
        self.assertFalse(task.is_milestone)
    
    def test_create_milestone_factory_method(self):
        """Test the create_milestone factory method."""
        milestone = Task.create_milestone(
            name="Test Milestone",
            date=self.start_date,
            color="#e74c3c",
            dependencies=["dep1"]
        )
        
        self.assertIsNotNone(milestone.id)
        self.assertEqual(milestone.name, "Test Milestone")
        self.assertEqual(milestone.start_date, self.start_date)
        self.assertIsNone(milestone.end_date)
        self.assertEqual(milestone.color, "#e74c3c")
        self.assertEqual(milestone.dependency_ids, ["dep1"])
        self.assertTrue(milestone.is_milestone)
    
    def test_task_empty_name_validation(self):
        """Test that empty task names raise ValueError."""
        with self.assertRaises(ValueError):
            Task(id="test", name="", start_date=self.start_date)
    
    def test_task_progress_validation(self):
        """Test that invalid progress values raise ValueError."""
        with self.assertRaises(ValueError):
            Task(id="test", name="Test", start_date=self.start_date, progress=-1)
        
        with self.assertRaises(ValueError):
            Task(id="test", name="Test", start_date=self.start_date, progress=101)
    
    def test_milestone_end_date_handling(self):
        """Test that milestones with end_date get it set to None."""
        # Create a milestone with end_date
        milestone = Task(
            id="milestone1",
            name="Test Milestone",
            start_date=self.start_date,
            end_date=self.end_date,
            is_milestone=True
        )
        # The __post_init__ should have set end_date to None
        self.assertIsNone(milestone.end_date)
    
    def test_duration_days_regular_task(self):
        """
        Duration is the working days a task covers, both ends included.

        The fixture starts on Monday 1 January 2024 and runs to the Wednesday
        of the following week: ten calendar days holding eight days of work,
        the Saturday and Sunday between them being worked by nobody. See
        gantt_app.workdaycalendar.
        """
        task = Task(
            id="test",
            name="Test",
            start_date=self.start_date,
            end_date=self.start_date + timedelta(days=9)
        )
        self.assertEqual(task.duration_days, 8)
        self.assertEqual(task.total_elapsed_days, 10)

    def test_duration_days_within_one_week(self):
        """A task inside a single working week counts every day of it."""
        task = Task(
            id="test",
            name="Test",
            start_date=self.start_date,                       # Monday
            end_date=self.start_date + timedelta(days=4)      # Friday
        )
        self.assertEqual(task.duration_days, 5)
        self.assertEqual(task.total_elapsed_days, 5)

    def test_duration_days_ignores_a_weekend_tail(self):
        """
        A span running into the weekend holds no more work for it.

        Monday to Sunday is seven calendar days and five days of work, which
        is the whole point of separating the two.
        """
        task = Task(
            id="test",
            name="Test",
            start_date=self.start_date,                       # Monday
            end_date=self.start_date + timedelta(days=6)      # Sunday
        )
        self.assertEqual(task.duration_days, 5)
        self.assertEqual(task.total_elapsed_days, 7)

    def test_a_manual_duration_is_taken_as_given(self):
        """A duration written onto the task wins over its dates."""
        task = Task(
            id="test",
            name="Test",
            start_date=self.start_date,
            end_date=self.start_date + timedelta(days=4),
            duration=3
        )
        self.assertEqual(task.duration_days, 3)


    def test_duration_days_milestone(self):
        """Test duration calculation for milestones."""
        milestone = Task.create_milestone(
            name="Test Milestone",
            date=self.start_date
        )
        self.assertEqual(milestone.duration_days, 0)
    
    def test_duration_days_no_end_date(self):
        """Test duration calculation when end_date is None."""
        task = Task(
            id="test",
            name="Test",
            start_date=self.start_date,
            end_date=None
        )
        self.assertIsNone(task.duration_days)
    
    def test_to_dict(self):
        """Test serialization to dictionary."""
        task = Task(
            id="test123",
            name="Test Task",
            start_date=self.start_date,
            end_date=self.end_date,
            progress=25,
            dependencies=["dep1"],
            color="#3498db",
            is_milestone=False
        )
        
        task_dict = task.to_dict()
        
        self.assertEqual(task_dict['id'], "test123")
        self.assertEqual(task_dict['name'], "Test Task")
        self.assertEqual(task_dict['start_date'], "2024-01-01T00:00:00")
        self.assertEqual(task_dict['end_date'], "2024-01-10T00:00:00")
        self.assertEqual(task_dict['progress'], 25)
        # Dependencies serialise with their type and hardness
        self.assertEqual(task_dict['dependencies'],
                         [{'task_id': 'dep1', 'dep_type': 'FS',
                           'hardness': 'Hard', 'lag': 0}])
        self.assertEqual(task_dict['color'], "#3498db")
        self.assertFalse(task_dict['is_milestone'])
    
    def test_from_dict(self):
        """Test deserialization from dictionary."""
        task_dict = {
            'id': 'test123',
            'name': 'Test Task',
            'start_date': '2024-01-01T00:00:00',
            'end_date': '2024-01-10T00:00:00',
            'progress': 25,
            'dependencies': ['dep1'],
            'color': '#3498db',
            'is_milestone': False
        }
        
        task = Task.from_dict(task_dict)
        
        self.assertEqual(task.id, "test123")
        self.assertEqual(task.name, "Test Task")
        self.assertEqual(task.start_date, datetime(2024, 1, 1))
        self.assertEqual(task.end_date, datetime(2024, 1, 10))
        self.assertEqual(task.progress, 25)
        self.assertEqual(task.dependency_ids, ['dep1'])
        self.assertEqual(task.color, '#3498db')
        self.assertFalse(task.is_milestone)


class TestProject(unittest.TestCase):
    """Test cases for the Project class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.start_date = datetime(2024, 1, 1)
        self.end_date = datetime(2024, 1, 10)
        
        # Create sample tasks
        self.task1 = Task.create_task(
            name="Task 1",
            start_date=self.start_date,
            end_date=self.start_date + timedelta(days=3)
        )
        
        self.task2 = Task.create_task(
            name="Task 2",
            start_date=self.start_date + timedelta(days=4),
            end_date=self.start_date + timedelta(days=8)
        )
        
        self.milestone = Task.create_milestone(
            name="Milestone 1",
            date=self.start_date + timedelta(days=8)
        )
    
    def test_create_empty_project(self):
        """Test creating an empty project."""
        project = Project(name="Empty Project")
        
        self.assertEqual(project.name, "Empty Project")
        self.assertEqual(project.tasks, [])
        self.assertIsNone(project.start_date)
        self.assertIsNone(project.end_date)
    
    def test_create_project_with_tasks(self):
        """Test creating a project with tasks."""
        tasks = [self.task1, self.task2]
        project = Project(name="Test Project", tasks=tasks)
        
        self.assertEqual(project.name, "Test Project")
        self.assertEqual(len(project.tasks), 2)
        # Project dates should be calculated from tasks
        self.assertEqual(project.start_date, self.start_date)
        # task2 ends on start_date + 8 days = start_date + timedelta(days=8)
        self.assertEqual(project.end_date, self.start_date + timedelta(days=8))
    
    def test_add_task(self):
        """Test adding a task to a project."""
        project = Project(name="Test Project")
        project.add_task(self.task1)
        
        self.assertEqual(len(project.tasks), 1)
        self.assertEqual(project.tasks[0].name, "Task 1")
        self.assertEqual(project.start_date, self.start_date)
        self.assertEqual(project.end_date, self.start_date + timedelta(days=3))
    
    def test_add_multiple_tasks(self):
        """Test adding multiple tasks to a project."""
        project = Project(name="Test Project")
        project.add_task(self.task1)
        project.add_task(self.task2)
        project.add_task(self.milestone)
        
        self.assertEqual(len(project.tasks), 3)
        # Start date should be earliest task
        self.assertEqual(project.start_date, self.start_date)
        # End date should be latest end date
        self.assertEqual(project.end_date, self.start_date + timedelta(days=8))
    
    def test_remove_task(self):
        """Test removing a task from a project."""
        project = Project(name="Test Project", tasks=[self.task1, self.task2])
        
        # Remove task1
        result = project.remove_task(self.task1.id)
        self.assertTrue(result)
        self.assertEqual(len(project.tasks), 1)
        self.assertEqual(project.tasks[0].id, self.task2.id)
        
        # Try to remove non-existent task
        result = project.remove_task("non-existent-id")
        self.assertFalse(result)
    
    def test_remove_task_updates_dependencies(self):
        """Test that removing a task also removes it from other tasks' dependencies."""
        # Create tasks with dependencies
        task1 = Task.create_task(name="Task 1", start_date=self.start_date, end_date=self.start_date + timedelta(days=3))
        task2 = Task.create_task(
            name="Task 2", 
            start_date=self.start_date + timedelta(days=4),
            end_date=self.start_date + timedelta(days=8),
            dependencies=[task1.id]
        )
        
        project = Project(name="Test Project", tasks=[task1, task2])
        
        # Remove task1
        project.remove_task(task1.id)
        
        # task2 should no longer have the dependency
        remaining_task2 = project.get_task_by_id(task2.id)
        self.assertEqual(remaining_task2.dependency_ids, [])
    
    def test_get_task_by_id(self):
        """Test getting a task by ID."""
        project = Project(name="Test Project", tasks=[self.task1, self.task2])
        
        retrieved = project.get_task_by_id(self.task1.id)
        self.assertEqual(retrieved.name, "Task 1")
        
        # Test non-existent task
        self.assertIsNone(project.get_task_by_id("non-existent-id"))
    
    def test_get_dependencies(self):
        """Test getting dependencies for a task."""
        task1 = Task.create_task(name="Task 1", start_date=self.start_date, end_date=self.start_date + timedelta(days=3))
        task2 = Task.create_task(
            name="Task 2", 
            start_date=self.start_date + timedelta(days=4),
            end_date=self.start_date + timedelta(days=8),
            dependencies=[task1.id]
        )
        
        project = Project(name="Test Project", tasks=[task1, task2])
        
        dependencies = project.get_dependencies(task2.id)
        self.assertEqual(len(dependencies), 1)
        self.assertEqual(dependencies[0].id, task1.id)
    
    def test_get_dependents(self):
        """Test getting tasks that depend on a given task."""
        task1 = Task.create_task(name="Task 1", start_date=self.start_date, end_date=self.start_date + timedelta(days=3))
        task2 = Task.create_task(
            name="Task 2", 
            start_date=self.start_date + timedelta(days=4),
            end_date=self.start_date + timedelta(days=8),
            dependencies=[task1.id]
        )
        
        project = Project(name="Test Project", tasks=[task1, task2])
        
        dependents = project.get_dependents(task1.id)
        self.assertEqual(len(dependents), 1)
        self.assertEqual(dependents[0].id, task2.id)
    
    def test_to_dict(self):
        """Test serialization of project to dictionary."""
        project = Project(name="Test Project", tasks=[self.task1, self.task2])
        
        project_dict = project.to_dict()
        
        self.assertEqual(project_dict['name'], "Test Project")
        self.assertEqual(len(project_dict['tasks']), 2)
        self.assertEqual(project_dict['start_date'], "2024-01-01T00:00:00")
        # task2 ends on start_date + 8 days = 2024-01-09
        self.assertEqual(project_dict['end_date'], "2024-01-09T00:00:00")
    
    def test_from_dict(self):
        """Test deserialization of project from dictionary."""
        project_dict = {
            'name': 'Test Project',
            'tasks': [
                {
                    'id': 'task1',
                    'name': 'Task 1',
                    'start_date': '2024-01-01T00:00:00',
                    'end_date': '2024-01-03T00:00:00',
                    'progress': 0,
                    'dependencies': [],
                    'color': '#1f6aa5',
                    'is_milestone': False
                },
                {
                    'id': 'task2',
                    'name': 'Task 2',
                    'start_date': '2024-01-04T00:00:00',
                    'end_date': '2024-01-08T00:00:00',
                    'progress': 0,
                    'dependencies': ['task1'],
                    'color': '#1f6aa5',
                    'is_milestone': False
                }
            ],
            'start_date': '2024-01-01T00:00:00',
            'end_date': '2024-01-08T00:00:00'
        }
        
        project = Project.from_dict(project_dict)
        
        self.assertEqual(project.name, "Test Project")
        self.assertEqual(len(project.tasks), 2)
        self.assertEqual(project.start_date, datetime(2024, 1, 1))
        self.assertEqual(project.end_date, datetime(2024, 1, 8))
    
    def test_critical_path_simple(self):
        """Test critical path calculation for simple project."""
        # Create a linear sequence of tasks
        task1 = Task.create_task(
            name="Task 1",
            start_date=self.start_date,
            end_date=self.start_date + timedelta(days=3)
        )
        task2 = Task.create_task(
            name="Task 2",
            start_date=self.start_date + timedelta(days=4),
            end_date=self.start_date + timedelta(days=8),
            dependencies=[task1.id]
        )
        task3 = Task.create_task(
            name="Task 3",
            start_date=self.start_date + timedelta(days=9),
            end_date=self.start_date + timedelta(days=15),
            dependencies=[task2.id]
        )
        
        project = Project(name="Linear Project", tasks=[task1, task2, task3])
        critical_path = project.get_critical_path()
        
        # Critical path should include all tasks in sequence
        self.assertEqual(len(critical_path), 3)
        self.assertEqual(critical_path[0].id, task1.id)
        self.assertEqual(critical_path[1].id, task2.id)
        self.assertEqual(critical_path[2].id, task3.id)
    
    def test_critical_path_with_milestones(self):
        """Test critical path calculation with milestones."""
        task1 = Task.create_task(
            name="Task 1",
            start_date=self.start_date,
            end_date=self.start_date + timedelta(days=3)
        )
        milestone = Task.create_milestone(
            name="Review",
            date=self.start_date + timedelta(days=4),
            dependencies=[task1.id]
        )
        task2 = Task.create_task(
            name="Task 2",
            start_date=self.start_date + timedelta(days=5),
            end_date=self.start_date + timedelta(days=10),
            dependencies=[milestone.id]
        )
        
        project = Project(name="Milestone Project", tasks=[task1, milestone, task2])
        critical_path = project.get_critical_path()
        
        # Critical path should include the longest path
        self.assertTrue(len(critical_path) >= 2)
        # Should include the milestone if it's on the critical path
        task_ids = [t.id for t in critical_path]
        self.assertIn(milestone.id, task_ids)

    def test_critical_path_excludes_summary_tasks(self):
        """A parent task spanning its sub-tasks stays off the critical path."""
        parent = Task.create_task(
            name="Phase",
            start_date=self.start_date,
            end_date=self.start_date + timedelta(days=10)
        )
        child = Task.create_subtask(
            name="Work",
            parent_task=parent,
            end_date=self.start_date + timedelta(days=10)
        )

        project = Project(name="Summary Project", tasks=[parent, child])
        critical_path = project.get_critical_path()

        task_ids = [t.id for t in critical_path]
        self.assertNotIn(parent.id, task_ids)
        self.assertIn(child.id, task_ids)

    def test_critical_path_reaches_the_final_task(self):
        """The path runs through to the task that finishes last."""
        # Two predecessors of the finish, one on a longer chain
        first = Task.create_task(
            name="First", start_date=self.start_date,
            end_date=self.start_date + timedelta(days=9)
        )
        long_branch = Task.create_task(
            name="Long branch", start_date=self.start_date + timedelta(days=10),
            end_date=self.start_date + timedelta(days=19),
            dependencies=[first.id]
        )
        short_branch = Task.create_task(
            name="Short branch", start_date=self.start_date + timedelta(days=10),
            end_date=self.start_date + timedelta(days=12),
            dependencies=[first.id]
        )
        finish = Task.create_task(
            name="Finish", start_date=self.start_date + timedelta(days=20),
            end_date=self.start_date + timedelta(days=22),
            dependencies=[long_branch.id, short_branch.id]
        )

        project = Project(name="Converging",
                          tasks=[first, long_branch, short_branch, finish])
        critical_path = project.get_critical_path()

        self.assertEqual([t.name for t in critical_path],
                         ["First", "Long branch", "Finish"])

    def test_critical_path_ignores_weekend_gaps(self):
        """Gaps between a task and its successor do not break the chain."""
        # Friday finish, Monday start - a two day calendar gap
        friday = datetime(2024, 1, 5)
        monday = datetime(2024, 1, 8)

        first = Task.create_task(name="Before weekend",
                                 start_date=datetime(2024, 1, 1), end_date=friday)
        second = Task.create_task(name="After weekend", start_date=monday,
                                  end_date=datetime(2024, 1, 12),
                                  dependencies=[first.id])

        project = Project(name="Working Days", tasks=[first, second])
        critical_path = project.get_critical_path()

        self.assertEqual([t.name for t in critical_path],
                         ["Before weekend", "After weekend"])

    def test_critical_path_through_a_summary_dependency(self):
        """Depending on a summary task links to the work inside it."""
        phase = Task.create_task(
            name="Phase", start_date=self.start_date,
            end_date=self.start_date + timedelta(days=9)
        )
        inner = Task.create_subtask(
            name="Inner work", parent_task=phase,
            end_date=self.start_date + timedelta(days=9)
        )
        after = Task.create_task(
            name="After the phase",
            start_date=self.start_date + timedelta(days=10),
            end_date=self.start_date + timedelta(days=15),
            dependencies=[phase.id]
        )

        project = Project(name="Summary Dependency",
                          tasks=[phase, inner, after])
        critical_path = project.get_critical_path()

        names = [t.name for t in critical_path]
        self.assertEqual(names, ["Inner work", "After the phase"])
        self.assertNotIn("Phase", names)

    def test_critical_path_survives_a_dependency_cycle(self):
        """A cyclic dependency returns a path instead of hanging."""
        first = Task.create_task(name="A", start_date=self.start_date,
                                 end_date=self.start_date + timedelta(days=2))
        second = Task.create_task(name="B",
                                  start_date=self.start_date + timedelta(days=3),
                                  end_date=self.start_date + timedelta(days=5))
        first.dependencies = [second.id]
        second.dependencies = [first.id]

        project = Project(name="Cyclic", tasks=[first, second])
        critical_path = project.get_critical_path()

        self.assertTrue(len(critical_path) >= 1)
        self.assertEqual(len({t.id for t in critical_path}), len(critical_path))

    def test_get_summary_task_ids(self):
        """Tasks referenced as a parent are reported as summary tasks."""
        parent = Task.create_task(
            name="Phase",
            start_date=self.start_date,
            end_date=self.start_date + timedelta(days=5)
        )
        child = Task.create_subtask(name="Work", parent_task=parent)
        standalone = Task.create_task(
            name="Standalone",
            start_date=self.start_date,
            end_date=self.start_date + timedelta(days=2)
        )

        project = Project(name="Summary IDs", tasks=[parent, child, standalone])

        self.assertEqual(project.get_summary_task_ids(), {parent.id})


class TestTaskValidation(unittest.TestCase):
    """Test validation logic for Task class."""
    
    def test_progress_validation_low(self):
        """Test that progress < 0 raises ValueError."""
        with self.assertRaises(ValueError):
            Task(id="test", name="Test", start_date=datetime.now(), progress=-5)
    
    def test_progress_validation_high(self):
        """Test that progress > 100 raises ValueError."""
        with self.assertRaises(ValueError):
            Task(id="test", name="Test", start_date=datetime.now(), progress=105)
    
    def test_empty_name_validation(self):
        """Test that empty name raises ValueError."""
        with self.assertRaises(ValueError):
            Task(id="test", name="", start_date=datetime.now())


if __name__ == '__main__':
    unittest.main()

class TestPropertiesAreNotCalled(unittest.TestCase):
    """
    Guards against using a model property as if it were a method.

    DEVELOPMENT NOTES:
    ------------------
    main.py called task.duration_days(), which raises
    "TypeError: 'int' object is not callable" the moment a task is selected.
    Nothing caught it because the failure only happens in a GUI callback,
    where Tk sends the traceback to a stderr that a packaged build has no
    console for. This scans the source instead.
    """

    def test_model_properties_are_never_called(self):
        """No source file calls a Task or Project property as a method."""
        import ast
        import pathlib

        from gantt_app import models

        properties = {
            name for cls in (models.Task, models.Project)
            for name, value in vars(cls).items()
            if isinstance(value, property)
        }
        self.assertIn('duration_days', properties)

        offenders = []
        root = pathlib.Path(models.__file__).parent.parent
        for path in sorted(root.rglob('*.py')):
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and node.func.attr in properties):
                    offenders.append(
                        f"{path.relative_to(root)}:{node.lineno} "
                        f"calls .{node.func.attr}()"
                    )

        self.assertEqual(offenders, [], "properties must be read, not called")
