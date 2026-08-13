"""
Unit tests for utility functions and helpers.
"""

import unittest
from datetime import datetime, timedelta

from gantt_app.models import Task, Project


class TestProjectUtilities(unittest.TestCase):
    """Test project utility methods."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.start_date = datetime(2024, 1, 1)
        
        # Create tasks with different start dates
        self.task1 = Task.create_task(
            name="Earliest Task",
            start_date=self.start_date,
            end_date=self.start_date + timedelta(days=3)
        )
        
        self.task2 = Task.create_task(
            name="Middle Task",
            start_date=self.start_date + timedelta(days=5),
            end_date=self.start_date + timedelta(days=10)
        )
        
        self.task3 = Task.create_task(
            name="Latest Task",
            start_date=self.start_date + timedelta(days=15),
            end_date=self.start_date + timedelta(days=20)
        )
    
    def test_project_date_calculation(self):
        """Test that project dates are calculated from tasks."""
        project = Project(name="Date Test", tasks=[self.task1, self.task2, self.task3])
        
        self.assertEqual(project.start_date, self.start_date)
        self.assertEqual(project.end_date, self.start_date + timedelta(days=20))
    
    def test_project_empty_dates(self):
        """Test project dates with no tasks."""
        project = Project(name="Empty Project")
        
        self.assertIsNone(project.start_date)
        self.assertIsNone(project.end_date)
    
    def test_project_single_task_dates(self):
        """Test project dates with single task."""
        project = Project(name="Single Task", tasks=[self.task1])
        
        self.assertEqual(project.start_date, self.start_date)
        self.assertEqual(project.end_date, self.start_date + timedelta(days=3))
    
    def test_circular_dependency_detection(self):
        """Test detection of circular dependencies."""
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
        
        project = Project(name="Circular Test", tasks=[task1, task2])
        
        # Add circular dependency
        task1.dependencies.append(task2.id)
        
        # This should not create infinite loop in get_dependencies
        dependencies = project.get_dependencies(task1.id)
        self.assertEqual(len(dependencies), 1)  # Should not infinite loop
    
    def test_complex_dependencies(self):
        """Test complex dependency chains."""
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
            end_date=self.start_date + timedelta(days=12),
            dependencies=[task2.id]
        )
        task4 = Task.create_task(
            name="Task 4",
            start_date=self.start_date + timedelta(days=9),
            end_date=self.start_date + timedelta(days=15),
            dependencies=[task1.id, task2.id]  # Depends on multiple tasks
        )
        
        project = Project(name="Complex", tasks=[task1, task2, task3, task4])
        
        # Check dependencies
        task4_deps = project.get_dependencies(task4.id)
        self.assertEqual(len(task4_deps), 2)
        
        # Check dependents
        task1_dependents = project.get_dependents(task1.id)
        self.assertEqual(len(task1_dependents), 2)  # task2 and task4
    
    def test_task_duration_calculation(self):
        """Test duration calculation for tasks."""
        # Test various durations
        test_cases = [
            (datetime(2024, 1, 1), datetime(2024, 1, 1), 1),  # Same day
            (datetime(2024, 1, 1), datetime(2024, 1, 2), 2),  # 2 days
            (datetime(2024, 1, 1), datetime(2024, 1, 10), 10),  # 10 days
        ]
        
        for start, end, expected_duration in test_cases:
            task = Task(
                id="test",
                name="Test",
                start_date=start,
                end_date=end
            )
            self.assertEqual(task.duration_days, expected_duration)


class TestTaskSerialization(unittest.TestCase):
    """Test task serialization and deserialization edge cases."""
    
    def test_roundtrip_preserves_all_fields(self):
        """Test that serialization preserves all task fields."""
        start_date = datetime(2024, 1, 15, 10, 30, 45)
        end_date = datetime(2024, 2, 20, 14, 20, 30)
        
        original_task = Task(
            id="unique-id-123",
            name="Complex Task",
            start_date=start_date,
            end_date=end_date,
            progress=75,
            dependencies=["dep1", "dep2", "dep3"],
            color="#abcdef",
            is_milestone=False
        )
        
        # Serialize and deserialize
        task_dict = original_task.to_dict()
        restored_task = Task.from_dict(task_dict)
        
        # Check all fields
        self.assertEqual(restored_task.id, original_task.id)
        self.assertEqual(restored_task.name, original_task.name)
        self.assertEqual(restored_task.start_date, original_task.start_date)
        self.assertEqual(restored_task.end_date, original_task.end_date)
        self.assertEqual(restored_task.progress, original_task.progress)
        self.assertEqual(restored_task.dependencies, original_task.dependencies)
        self.assertEqual(restored_task.color, original_task.color)
        self.assertEqual(restored_task.is_milestone, original_task.is_milestone)
    
    def test_milestone_serialization(self):
        """Test serialization of milestones."""
        original_milestone = Task.create_milestone(
            name="Important Milestone",
            date=datetime(2024, 6, 15),
            color="#ff0000",
            dependencies=["task1"]
        )
        
        # Serialize and deserialize
        milestone_dict = original_milestone.to_dict()
        restored_milestone = Task.from_dict(milestone_dict)
        
        self.assertEqual(restored_milestone.name, "Important Milestone")
        self.assertEqual(restored_milestone.start_date, datetime(2024, 6, 15))
        self.assertIsNone(restored_milestone.end_date)
        self.assertTrue(restored_milestone.is_milestone)
        self.assertEqual(restored_milestone.color, "#ff0000")
        self.assertEqual(restored_milestone.dependencies, ["task1"])


class TestCriticalPath(unittest.TestCase):
    """Test critical path calculation algorithms."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.start_date = datetime(2024, 1, 1)
    
    def test_empty_project_critical_path(self):
        """Test critical path for empty project."""
        project = Project(name="Empty")
        critical_path = project.get_critical_path()
        
        self.assertEqual(critical_path, [])
    
    def test_single_task_critical_path(self):
        """Test critical path for single task project."""
        task = Task.create_task(
            name="Only Task",
            start_date=self.start_date,
            end_date=self.start_date + timedelta(days=5)
        )
        project = Project(name="Single", tasks=[task])
        critical_path = project.get_critical_path()
        
        self.assertEqual(len(critical_path), 1)
        self.assertEqual(critical_path[0].id, task.id)
    
    def test_parallel_tasks_critical_path(self):
        """Test critical path with parallel tasks."""
        # Create parallel tasks (no dependencies)
        task1 = Task.create_task(
            name="Short Task",
            start_date=self.start_date,
            end_date=self.start_date + timedelta(days=3)
        )
        task2 = Task.create_task(
            name="Long Task",
            start_date=self.start_date,
            end_date=self.start_date + timedelta(days=10)
        )
        
        project = Project(name="Parallel", tasks=[task1, task2])
        critical_path = project.get_critical_path()
        
        # Critical path should include the longest task
        self.assertTrue(len(critical_path) >= 1)
        # The longest task should be on the critical path
        task_ids = [t.id for t in critical_path]
        self.assertIn(task2.id, task_ids)
    
    def test_complex_network_critical_path(self):
        """Test critical path in complex dependency network."""
        # Task 1 -> Task 2 -> Task 4
        # Task 1 -> Task 3 -> Task 5
        # Task 5 -> Task 6
        
        task1 = Task.create_task(
            name="Start",
            start_date=self.start_date,
            end_date=self.start_date + timedelta(days=2)
        )
        task2 = Task.create_task(
            name="Path A-1",
            start_date=self.start_date + timedelta(days=3),
            end_date=self.start_date + timedelta(days=5),
            dependencies=[task1.id]
        )
        task3 = Task.create_task(
            name="Path B-1",
            start_date=self.start_date + timedelta(days=3),
            end_date=self.start_date + timedelta(days=8),  # Longer path
            dependencies=[task1.id]
        )
        task4 = Task.create_task(
            name="Path A-2",
            start_date=self.start_date + timedelta(days=6),
            end_date=self.start_date + timedelta(days=10),
            dependencies=[task2.id]
        )
        task5 = Task.create_task(
            name="Path B-2",
            start_date=self.start_date + timedelta(days=9),
            end_date=self.start_date + timedelta(days=12),
            dependencies=[task3.id]
        )
        task6 = Task.create_task(
            name="Final",
            start_date=self.start_date + timedelta(days=13),
            end_date=self.start_date + timedelta(days=15),
            dependencies=[task5.id]
        )
        
        project = Project(name="Complex", tasks=[task1, task2, task3, task4, task5, task6])
        critical_path = project.get_critical_path()
        
        # Critical path should include the longest path
        # In this case: task1 -> task3 -> task5 -> task6
        self.assertTrue(len(critical_path) >= 3)
        
        # Verify it's a valid path (all dependencies are satisfied)
        for i in range(1, len(critical_path)):
            current_task = critical_path[i]
            prev_task = critical_path[i-1]
            self.assertIn(prev_task.id, current_task.dependencies)


if __name__ == '__main__':
    unittest.main()