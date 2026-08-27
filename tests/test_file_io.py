"""
Unit tests for file I/O functionality.
"""

import unittest
import os
import tempfile
import json
from datetime import datetime, timedelta
import shutil

from gantt_app.models import Task, Project
from gantt_app.utils.file_io import JSONFileIO, save_project, load_project


class TestJSONFileIO(unittest.TestCase):
    """Test cases for JSON file I/O operations."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.start_date = datetime(2024, 1, 1)
        
        # Create sample project
        self.task1 = Task.create_task(
            name="Task 1",
            start_date=self.start_date,
            end_date=self.start_date + timedelta(days=3)
        )
        self.task2 = Task.create_task(
            name="Task 2",
            start_date=self.start_date + timedelta(days=4),
            end_date=self.start_date + timedelta(days=8),
            dependencies=[self.task1.id]
        )
        self.project = Project(name="Test Project", tasks=[self.task1, self.task2])
    
    def tearDown(self):
        """Clean up test files."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_save_project_basic(self):
        """Test saving a project to JSON file."""
        filepath = os.path.join(self.test_dir, "test_project.json")
        
        result = JSONFileIO.save_project(self.project, filepath)
        
        self.assertTrue(result)
        self.assertTrue(os.path.exists(filepath))
    
    def test_save_project_creates_directory(self):
        """Test that save_project creates parent directories if needed."""
        nested_dir = os.path.join(self.test_dir, "nested", "dir")
        filepath = os.path.join(nested_dir, "test_project.json")
        
        result = JSONFileIO.save_project(self.project, filepath)
        
        self.assertTrue(result)
        self.assertTrue(os.path.exists(filepath))
    
    def test_load_project_basic(self):
        """Test loading a project from JSON file."""
        # First save the project
        filepath = os.path.join(self.test_dir, "test_project.json")
        JSONFileIO.save_project(self.project, filepath)
        
        # Then load it
        loaded_project = JSONFileIO.load_project(filepath)
        
        self.assertIsNotNone(loaded_project)
        self.assertEqual(loaded_project.name, "Test Project")
        self.assertEqual(len(loaded_project.tasks), 2)
        self.assertEqual(loaded_project.tasks[0].name, "Task 1")
        self.assertEqual(loaded_project.tasks[1].name, "Task 2")
    
    def test_save_load_roundtrip(self):
        """Test that save and load preserve all data."""
        filepath = os.path.join(self.test_dir, "roundtrip_project.json")
        
        # Save project
        JSONFileIO.save_project(self.project, filepath)
        
        # Load project
        loaded_project = JSONFileIO.load_project(filepath)
        
        # Compare original and loaded
        self.assertEqual(loaded_project.name, self.project.name)
        self.assertEqual(len(loaded_project.tasks), len(self.project.tasks))
        
        # Check task properties
        for original_task, loaded_task in zip(self.project.tasks, loaded_project.tasks):
            self.assertEqual(loaded_task.id, original_task.id)
            self.assertEqual(loaded_task.name, original_task.name)
            self.assertEqual(loaded_task.start_date, original_task.start_date)
            self.assertEqual(loaded_task.end_date, original_task.end_date)
            self.assertEqual(loaded_task.progress, original_task.progress)
            self.assertEqual(loaded_task.dependencies, original_task.dependencies)
            self.assertEqual(loaded_task.color, original_task.color)
            self.assertEqual(loaded_task.is_milestone, original_task.is_milestone)
    
    def test_load_nonexistent_file(self):
        """Test loading a file that doesn't exist."""
        filepath = os.path.join(self.test_dir, "nonexistent.json")
        
        result = JSONFileIO.load_project(filepath)
        
        self.assertIsNone(result)
    
    def test_load_invalid_json(self):
        """Test loading a file with invalid JSON."""
        filepath = os.path.join(self.test_dir, "invalid.json")
        
        # Create a file with invalid JSON
        with open(filepath, 'w') as f:
            f.write("{ invalid json }")
        
        result = JSONFileIO.load_project(filepath)
        
        self.assertIsNone(result)
    
    def test_save_load_with_milestones(self):
        """Test saving and loading projects with milestones."""
        milestone = Task.create_milestone(
            name="Review",
            date=self.start_date + timedelta(days=5),
            dependencies=[self.task1.id]
        )
        
        project = Project(name="Milestone Project", tasks=[self.task1, milestone])
        filepath = os.path.join(self.test_dir, "milestone_project.json")
        
        # Save and load
        JSONFileIO.save_project(project, filepath)
        loaded_project = JSONFileIO.load_project(filepath)
        
        self.assertIsNotNone(loaded_project)
        self.assertEqual(len(loaded_project.tasks), 2)
        
        # Check milestone properties
        milestone_task = [t for t in loaded_project.tasks if t.is_milestone][0]
        self.assertEqual(milestone_task.name, "Review")
        self.assertTrue(milestone_task.is_milestone)
        self.assertIsNone(milestone_task.end_date)
    
    def test_save_load_with_none_dates(self):
        """Test saving and loading with None dates."""
        task_no_end = Task(
            id="test1",
            name="Task No End",
            start_date=self.start_date,
            end_date=None
        )
        
        project = Project(name="No End Date Project", tasks=[task_no_end])
        filepath = os.path.join(self.test_dir, "no_end_date.json")
        
        # Save and load
        JSONFileIO.save_project(project, filepath)
        loaded_project = JSONFileIO.load_project(filepath)
        
        self.assertIsNotNone(loaded_project)
        loaded_task = loaded_project.tasks[0]
        self.assertIsNone(loaded_task.end_date)
    
    def test_json_format_validity(self):
        """Test that saved JSON is valid and parseable."""
        filepath = os.path.join(self.test_dir, "valid_json.json")
        
        JSONFileIO.save_project(self.project, filepath)
        
        # Read the file and parse as JSON
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # Verify structure
        self.assertIn('name', data)
        self.assertIn('tasks', data)
        self.assertIn('start_date', data)
        self.assertIn('end_date', data)
        
        # Verify task structure
        for task in data['tasks']:
            self.assertIn('id', task)
            self.assertIn('name', task)
            self.assertIn('start_date', task)
            self.assertIn('end_date', task)
            self.assertIn('progress', task)
            self.assertIn('dependencies', task)
            self.assertIn('color', task)
            self.assertIn('is_milestone', task)

    def test_save_load_with_status(self):
        """Test that status field is saved and loaded correctly."""
        project = Project(name="Test Project")
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 10)
        task = Task(id="1", name="Test Task", start_date=start, end_date=end, status="Draft")
        project.add_task(task)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            filepath = f.name

        try:
            JSONFileIO.save_project(project, filepath)
            loaded_project = JSONFileIO.load_project(filepath)
            self.assertIsNotNone(loaded_project)
            loaded_task = loaded_project.get_task_by_id("1")
            self.assertEqual(loaded_task.status, "Draft")
        finally:
            os.unlink(filepath)

    def test_load_legacy_file_without_status(self):
        """Test that files without status field load with default 'Active'."""
        project_data = {
            'name': 'Legacy Project',
            'tasks': [{
                'id': '1',
                'name': 'Legacy Task',
                'start_date': '2024-01-01T00:00:00',
                'end_date': '2024-01-10T00:00:00',
                'progress': 0,
                'dependencies': [],
                'color': '#1f6aa5',
                'is_milestone': False,
                'task_type': 'Task',
                'parent_task_id': None,
                'duration': None,
                'priority': 'Normal',
                'shape': 'Default',
                'show_in_timeline': True,
                'earliest_begin': None,
                'scheduling_options': 'End date is calculated',
                'details': '',
                'calendar_id': None,
                'style': None
            }],
            'start_date': '2024-01-01T00:00:00',
            'end_date': '2024-01-10T00:00:00',
            'calendar': {'week_start': 1, 'holidays': [], 'nonworking_days': []},
            'calendars': {'default': {'name': 'Default', 'week_start': 1, 'holidays': [], 'nonworking_days': []}},
            'schedule_from': 'Start',
            'deadline': None,
            'status_date': None,
            'priority': 500
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            filepath = f.name
            json.dump(project_data, f)

        try:
            loaded_project = JSONFileIO.load_project(filepath)
            self.assertIsNotNone(loaded_project)
            loaded_task = loaded_project.get_task_by_id("1")
            self.assertEqual(loaded_task.status, "Active")
        finally:
            os.unlink(filepath)


class TestConvenienceFunctions(unittest.TestCase):
    """Test convenience functions for file I/O."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.start_date = datetime(2024, 1, 1)
        
        self.task1 = Task.create_task(
            name="Task 1",
            start_date=self.start_date,
            end_date=self.start_date + timedelta(days=3)
        )
        self.project = Project(name="Test Project", tasks=[self.task1])
    
    def tearDown(self):
        """Clean up test files."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_save_project_function(self):
        """Test the save_project convenience function."""
        filepath = os.path.join(self.test_dir, "convenience_save.json")
        
        result = save_project(self.project, filepath)
        
        self.assertTrue(result)
        self.assertTrue(os.path.exists(filepath))
    
    def test_load_project_function(self):
        """Test the load_project convenience function."""
        filepath = os.path.join(self.test_dir, "convenience_load.json")
        save_project(self.project, filepath)
        
        loaded_project = load_project(filepath)
        
        self.assertIsNotNone(loaded_project)
        self.assertEqual(loaded_project.name, "Test Project")


class TestDatetimeSerialization(unittest.TestCase):
    """Test datetime serialization and deserialization."""
    
    def test_datetime_serialization(self):
        """Test that datetime objects are properly serialized to ISO format."""
        task = Task.create_task(
            name="Test",
            start_date=datetime(2024, 1, 15, 10, 30, 45),
            end_date=datetime(2024, 2, 20, 14, 20, 0)
        )
        
        task_dict = task.to_dict()
        
        self.assertEqual(task_dict['start_date'], "2024-01-15T10:30:45")
        self.assertEqual(task_dict['end_date'], "2024-02-20T14:20:00")
    
    def test_datetime_deserialization(self):
        """Test that ISO format datetime strings are properly deserialized."""
        task_dict = {
            'id': 'test',
            'name': 'Test',
            'start_date': '2024-01-15T10:30:45',
            'end_date': '2024-02-20T14:20:00',
            'progress': 0,
            'dependencies': [],
            'color': '#1f6aa5',
            'is_milestone': False
        }
        
        task = Task.from_dict(task_dict)
        
        self.assertEqual(task.start_date, datetime(2024, 1, 15, 10, 30, 45))
        self.assertEqual(task.end_date, datetime(2024, 2, 20, 14, 20, 0))


if __name__ == '__main__':
    unittest.main()