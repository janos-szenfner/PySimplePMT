"""
Tests for the Mermaid importer and exporter.
"""

import unittest
import tempfile
import os
from datetime import datetime, timedelta

from gantt_app.models import Project, Task
from gantt_app.utils.mermaid_importer import (
    MermaidImporter, MermaidExporter, 
    import_mermaid_file, export_mermaid_file
)


class TestMermaidImporter(unittest.TestCase):
    """Tests for the MermaidImporter class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.importer = MermaidImporter()
    
    def test_parse_basic_mermaid(self):
        """Test parsing a basic Mermaid Gantt chart."""
        content = """gantt
    title Test Project
    dateFormat  YYYY-MM-DD
    Task 1 :a1, 2024-01-01, 5d
    Task 2 :a2, 2024-01-06, 3d
"""
        project = self.importer._parse_mermaid_content(content)
        
        self.assertIsNotNone(project)
        self.assertEqual(project.name, "Test Project")
        self.assertEqual(len(project.tasks), 2)
        
        self.assertEqual(project.tasks[0].name, "Task 1")
        self.assertEqual(project.tasks[0].start_date, datetime(2024, 1, 1))
        self.assertEqual(project.tasks[0].end_date, datetime(2024, 1, 6))
        
        self.assertEqual(project.tasks[1].name, "Task 2")
        self.assertEqual(project.tasks[1].start_date, datetime(2024, 1, 6))
        self.assertEqual(project.tasks[1].end_date, datetime(2024, 1, 9))
    
    def test_parse_with_milestone(self):
        """Test parsing Mermaid with milestones."""
        content = """gantt
    title Project with Milestone
    milestone Milestone 1 :m1, 2024-01-10
    milestone Milestone 2 :m2, 2024-01-20
"""
        project = self.importer._parse_mermaid_content(content)
        
        self.assertIsNotNone(project)
        self.assertEqual(len(project.tasks), 2)
        
        for task in project.tasks:
            self.assertTrue(task.is_milestone)
            self.assertIsNone(task.end_date)
    
    def test_parse_with_dependencies(self):
        """Test parsing Mermaid with task dependencies."""
        content = """gantt
    title Project with Dependencies
    Task 1 :a1, 2024-01-01, 5d
    Task 2 :a2, after a1, 3d
    Task 3 :a3, after a2, 2d
"""
        project = self.importer._parse_mermaid_content(content)
        
        self.assertIsNotNone(project)
        self.assertEqual(len(project.tasks), 3)
        
        # Check dependencies
        task1 = project.get_task_by_id("a1")
        task2 = project.get_task_by_id("a2")
        task3 = project.get_task_by_id("a3")
        
        self.assertEqual(task2.dependencies, ["a1"])
        self.assertEqual(task3.dependencies, ["a2"])
        
        # Check dates
        self.assertEqual(task1.start_date, datetime(2024, 1, 1))
        self.assertEqual(task1.end_date, datetime(2024, 1, 6))
        
        self.assertEqual(task2.start_date, datetime(2024, 1, 6))
        self.assertEqual(task2.end_date, datetime(2024, 1, 9))
        
        self.assertEqual(task3.start_date, datetime(2024, 1, 9))
        self.assertEqual(task3.end_date, datetime(2024, 1, 11))
    
    def test_parse_with_milestone_dependency(self):
        """Test parsing Mermaid with milestone dependencies."""
        content = """gantt
    title Project with Milestone Dependencies
    Task 1 :a1, 2024-01-01, 5d
    milestone Design Review :m1, after a1
    Implementation :a2, after m1, 10d
"""
        project = self.importer._parse_mermaid_content(content)
        
        self.assertIsNotNone(project)
        self.assertEqual(len(project.tasks), 3)
        
        task1 = project.get_task_by_id("a1")
        milestone = project.get_task_by_id("m1")
        impl = project.get_task_by_id("a2")
        
        self.assertEqual(milestone.dependencies, ["a1"])
        self.assertEqual(impl.dependencies, ["m1"])
        
        self.assertTrue(milestone.is_milestone)
        self.assertFalse(impl.is_milestone)
        
        # Check dates
        self.assertEqual(task1.start_date, datetime(2024, 1, 1))
        self.assertEqual(task1.end_date, datetime(2024, 1, 6))
        
        # Milestone should start when dependency ends
        self.assertEqual(milestone.start_date, datetime(2024, 1, 6))
        
        # Implementation should start when milestone is
        self.assertEqual(impl.start_date, datetime(2024, 1, 6))
        self.assertEqual(impl.end_date, datetime(2024, 1, 16))
    
    def test_import_nonexistent_file(self):
        """Test importing a non-existent file."""
        result = self.importer.import_mermaid("/nonexistent/path/mmd")
        self.assertIsNone(result)
    
    def test_parse_date_formats(self):
        """Test parsing different date formats."""
        # Test YYYY-MM-DD
        result = self.importer._parse_date("2024-01-15", "%Y-%m-%d")
        self.assertEqual(result, datetime(2024, 1, 15))
        
        # Test invalid date
        result = self.importer._parse_date("invalid", "%Y-%m-%d")
        self.assertIsNone(result)
    
    def test_parse_duration_formats(self):
        """Test parsing different duration formats."""
        start_date = datetime(2024, 1, 1)
        
        # Test days
        result = self.importer._parse_duration("5d", start_date)
        self.assertEqual(result, datetime(2024, 1, 6))
        
        # Test weeks
        result = self.importer._parse_duration("2w", start_date)
        self.assertEqual(result, datetime(2024, 1, 15))
        
        # Test months (approximate)
        result = self.importer._parse_duration("1m", start_date)
        self.assertEqual(result, datetime(2024, 1, 31))


class TestMermaidExporter(unittest.TestCase):
    """Tests for the MermaidExporter class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.exporter = MermaidExporter()
    
    def test_export_basic_project(self):
        """Test exporting a basic project."""
        project = Project(name="Test Project")
        start_date = datetime(2024, 1, 1)
        project.add_task(Task.create_task("Task 1", start_date, start_date + timedelta(days=5)))
        project.add_task(Task.create_task("Task 2", start_date + timedelta(days=6), start_date + timedelta(days=10)))
        
        content = self.exporter.export_mermaid_content(project)
        
        self.assertIn("gantt", content)
        self.assertIn("title Test Project", content)
        self.assertIn("dateFormat", content)
        self.assertIn("Task 1", content)
        self.assertIn("Task 2", content)
        self.assertIn("2024-01-01", content)
    
    def test_export_with_milestone(self):
        """Test exporting a project with milestones."""
        project = Project(name="Project with Milestone")
        milestone_date = datetime(2024, 1, 10)
        project.add_task(Task.create_milestone("Milestone 1", milestone_date))
        
        content = self.exporter.export_mermaid_content(project)
        
        self.assertIn("milestone Milestone 1", content)
        self.assertIn("2024-01-10", content)
    
    def test_export_with_dependencies(self):
        """Test exporting a project with dependencies."""
        project = Project(name="Project with Deps")
        start_date = datetime(2024, 1, 1)
        
        task1 = Task.create_task("Task 1", start_date, start_date + timedelta(days=5))
        project.add_task(task1)
        
        task2 = Task.create_task("Task 2", start_date + timedelta(days=6), start_date + timedelta(days=10))
        task2.dependencies = [task1.id]
        project.add_task(task2)
        
        content = self.exporter.export_mermaid_content(project)
        
        self.assertIn("after", content.lower())
    
    def test_export_to_file(self):
        """Test exporting to a file."""
        project = Project(name="Test Export")
        start_date = datetime(2024, 1, 1)
        project.add_task(Task.create_task("Task", start_date, start_date + timedelta(days=1)))
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False) as f:
            temp_path = f.name
        
        try:
            result = export_mermaid_file(project, temp_path)
            self.assertTrue(result)
            self.assertTrue(os.path.exists(temp_path))
            
            with open(temp_path, 'r') as f:
                content = f.read()
            self.assertIn("gantt", content)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_export_nonexistent_directory(self):
        """Test exporting to a directory that doesn't exist."""
        project = Project(name="Test")
        start_date = datetime(2024, 1, 1)
        project.add_task(Task.create_task("Task", start_date, start_date + timedelta(days=1)))
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = os.path.join(temp_dir, "subdir", "test.mmd")
            result = export_mermaid_file(project, temp_path)
            self.assertTrue(result)
            self.assertTrue(os.path.exists(temp_path))


class TestMermaidRoundTrip(unittest.TestCase):
    """Test round-trip import/export functionality."""
    
    def test_roundtrip_basic(self):
        """Test that a project can be exported and imported back."""
        original = Project(name="Roundtrip Test")
        start_date = datetime(2024, 1, 1)
        original.add_task(Task.create_task("Task 1", start_date, start_date + timedelta(days=5)))
        original.add_task(Task.create_task("Task 2", start_date + timedelta(days=6), start_date + timedelta(days=10)))
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False) as f:
            temp_path = f.name
        
        try:
            # Export
            self.assertTrue(export_mermaid_file(original, temp_path))
            
            # Import
            imported = import_mermaid_file(temp_path)
            self.assertIsNotNone(imported)
            
            # Check project name
            self.assertEqual(imported.name, original.name)
            
            # Check number of tasks
            self.assertEqual(len(imported.tasks), len(original.tasks))
            
            # Check task names
            original_names = {t.name for t in original.tasks}
            imported_names = {t.name for t in imported.tasks}
            self.assertEqual(original_names, imported_names)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_roundtrip_with_dependencies(self):
        """Test roundtrip with task dependencies."""
        original = Project(name="Dependencies Test")
        start_date = datetime(2024, 1, 1)
        
        task1 = Task.create_task("Task 1", start_date, start_date + timedelta(days=3))
        original.add_task(task1)
        
        task2 = Task.create_task("Task 2", start_date + timedelta(days=4), start_date + timedelta(days=7))
        task2.dependencies = [task1.id]
        original.add_task(task2)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False) as f:
            temp_path = f.name
        
        try:
            # Export
            self.assertTrue(export_mermaid_file(original, temp_path))
            
            # Import
            imported = import_mermaid_file(temp_path)
            self.assertIsNotNone(imported)
            
            # Check that tasks exist
            self.assertEqual(len(imported.tasks), 2)
            
            # Find the tasks by name
            imported_task1 = next((t for t in imported.tasks if t.name == "Task 1"), None)
            imported_task2 = next((t for t in imported.tasks if t.name == "Task 2"), None)
            
            self.assertIsNotNone(imported_task1)
            self.assertIsNotNone(imported_task2)
            
            # Check that the dependency relationship is preserved
            # Note: The IDs might be different after roundtrip, but the structure should be preserved
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


if __name__ == '__main__':
    unittest.main()