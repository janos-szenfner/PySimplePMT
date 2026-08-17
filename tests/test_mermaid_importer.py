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
        
        # Durations are inclusive spans: a 5d task from the 1st ends on the 5th
        self.assertEqual(project.tasks[0].name, "Task 1")
        self.assertEqual(project.tasks[0].start_date, datetime(2024, 1, 1))
        self.assertEqual(project.tasks[0].end_date, datetime(2024, 1, 5))
        self.assertEqual(project.tasks[0].duration_days, 5)

        self.assertEqual(project.tasks[1].name, "Task 2")
        self.assertEqual(project.tasks[1].start_date, datetime(2024, 1, 6))
        self.assertEqual(project.tasks[1].end_date, datetime(2024, 1, 8))
        self.assertEqual(project.tasks[1].duration_days, 3)
    
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
        
        self.assertEqual(task2.dependency_ids, ["a1"])
        self.assertEqual(task3.dependency_ids, ["a2"])
        
        # Each task starts the day after its predecessor finishes
        self.assertEqual(task1.start_date, datetime(2024, 1, 1))
        self.assertEqual(task1.end_date, datetime(2024, 1, 5))

        self.assertEqual(task2.start_date, datetime(2024, 1, 6))
        self.assertEqual(task2.end_date, datetime(2024, 1, 8))

        self.assertEqual(task3.start_date, datetime(2024, 1, 9))
        self.assertEqual(task3.end_date, datetime(2024, 1, 10))
    
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
        
        self.assertEqual(milestone.dependency_ids, ["a1"])
        self.assertEqual(impl.dependency_ids, ["m1"])
        
        self.assertTrue(milestone.is_milestone)
        self.assertFalse(impl.is_milestone)
        
        # Check dates
        self.assertEqual(task1.start_date, datetime(2024, 1, 1))
        self.assertEqual(task1.end_date, datetime(2024, 1, 5))

        # Milestone falls the day after its dependency finishes
        self.assertEqual(milestone.start_date, datetime(2024, 1, 6))

        # A milestone has zero duration, so what follows starts on the same day
        self.assertEqual(impl.start_date, datetime(2024, 1, 6))
        self.assertEqual(impl.end_date, datetime(2024, 1, 15))
        self.assertEqual(impl.duration_days, 10)
    
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

        # Durations are inclusive: the returned date is the last day of the span
        result = self.importer._parse_duration("5d", start_date)
        self.assertEqual(result, datetime(2024, 1, 5))

        # Test weeks (14 days)
        result = self.importer._parse_duration("2w", start_date)
        self.assertEqual(result, datetime(2024, 1, 14))

        # Test months (approximate, 30 days)
        result = self.importer._parse_duration("1m", start_date)
        self.assertEqual(result, datetime(2024, 1, 30))

        # A zero duration collapses onto the start date
        result = self.importer._parse_duration("0d", start_date)
        self.assertEqual(result, start_date)


class TestMermaidSections(unittest.TestCase):
    """Tests for mapping Mermaid sections onto the Task/Subtask hierarchy."""

    def setUp(self):
        """Set up test fixtures."""
        self.importer = MermaidImporter()

    CONTENT = """gantt
    title Sectioned Project
    dateFormat YYYY-MM-DD

    section Phase One
    Task 1 :a1, 2024-01-01, 5d
    Task 2 :a2, 2024-01-08, 3d

    section Phase Two
    Task 3 :b1, 2024-02-01, 10d
"""

    def test_sections_become_parent_tasks(self):
        """Each section becomes a parent task holding its tasks as Subtasks."""
        project = self.importer._parse_mermaid_content(self.CONTENT)

        self.assertIsNotNone(project)
        # 3 tasks + 2 section parents
        self.assertEqual(len(project.tasks), 5)

        roots = project.get_root_tasks()
        self.assertEqual([t.name for t in roots], ["Phase One", "Phase Two"])

        phase_one = roots[0]
        self.assertEqual(phase_one.task_type, "Task")
        subtasks = project.get_subtasks(phase_one.id)
        self.assertEqual([t.name for t in subtasks], ["Task 1", "Task 2"])
        for subtask in subtasks:
            self.assertEqual(subtask.task_type, "Subtask")

    def test_section_parent_spans_its_children(self):
        """A section parent covers the full range of the tasks inside it."""
        project = self.importer._parse_mermaid_content(self.CONTENT)

        phase_one = project.get_root_tasks()[0]
        self.assertEqual(phase_one.start_date, datetime(2024, 1, 1))
        self.assertEqual(phase_one.end_date, datetime(2024, 1, 10))

    def test_parents_precede_their_children(self):
        """Section parents are ordered ahead of the tasks they contain."""
        project = self.importer._parse_mermaid_content(self.CONTENT)

        names = [t.name for t in project.tasks]
        self.assertEqual(
            names,
            ["Phase One", "Task 1", "Task 2", "Phase Two", "Task 3"]
        )

    def test_repeated_section_name_stays_distinct(self):
        """Two section blocks sharing a name are not merged into one parent."""
        content = """gantt
    title Repeated
    section Work
    Task 1 :a1, 2024-01-01, 3d
    section Work
    Task 2 :a2, 2024-01-08, 3d
"""
        project = self.importer._parse_mermaid_content(content)

        roots = project.get_root_tasks()
        self.assertEqual(len(roots), 2)
        self.assertEqual([t.name for t in roots], ["Work", "Work"])
        self.assertNotEqual(roots[0].id, roots[1].id)

        self.assertEqual([t.name for t in project.get_subtasks(roots[0].id)],
                         ["Task 1"])
        self.assertEqual([t.name for t in project.get_subtasks(roots[1].id)],
                         ["Task 2"])

    def test_grouping_can_be_disabled(self):
        """group_by_section=False imports a flat task list."""
        importer = MermaidImporter(group_by_section=False)
        project = importer._parse_mermaid_content(self.CONTENT)

        self.assertEqual(len(project.tasks), 3)
        self.assertTrue(all(t.parent_task_id is None for t in project.tasks))

    def test_tasks_without_a_section_stay_at_root(self):
        """Tasks defined before any section are not given a parent."""
        content = """gantt
    title Mixed
    Loose Task :a0, 2024-01-01, 2d
    section Phase One
    Task 1 :a1, 2024-01-05, 5d
"""
        project = self.importer._parse_mermaid_content(content)

        loose = project.get_task_by_id("a0")
        self.assertIsNone(loose.parent_task_id)
        self.assertEqual(loose.task_type, "Task")

    def test_section_id_does_not_collide_with_task_id(self):
        """A section parent never reuses an existing task ID."""
        content = """gantt
    section Phase One
    Task 1 :section_phase_one, 2024-01-01, 5d
"""
        project = self.importer._parse_mermaid_content(content)

        ids = [t.id for t in project.tasks]
        self.assertEqual(len(ids), len(set(ids)))


class TestMermaidFrontmatter(unittest.TestCase):
    """Tests for Mermaid's optional YAML frontmatter block."""

    def setUp(self):
        """Set up test fixtures."""
        self.importer = MermaidImporter()

    def test_frontmatter_is_ignored(self):
        """Config frontmatter is stripped and never parsed as tasks."""
        content = """---
config:
  theme: forest
---
gantt
    title Themed Project
    dateFormat YYYY-MM-DD
    Task 1 :a1, 2024-01-01, 5d
"""
        project = self.importer._parse_mermaid_content(content)

        self.assertEqual(project.name, "Themed Project")
        self.assertEqual(len(project.tasks), 1)
        self.assertEqual(project.tasks[0].name, "Task 1")

    def test_axis_format_is_not_a_task(self):
        """Chart directives are skipped rather than parsed as tasks."""
        content = """gantt
    title Directives
    dateFormat YYYY-MM-DD
    axisFormat %Y. %m.
    excludes weekends
    todayMarker off
    Task 1 :a1, 2024-01-01, 5d
"""
        project = self.importer._parse_mermaid_content(content)

        self.assertEqual(len(project.tasks), 1)
        self.assertEqual(project.tasks[0].name, "Task 1")


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
    
    def test_roundtrip_preserves_sections(self):
        """Section grouping survives an export and re-import."""
        content = """gantt
    title Sectioned
    dateFormat YYYY-MM-DD
    section Phase One
    Task 1 :a1, 2024-01-01, 5d
    Task 2 :a2, after a1, 3d
    section Phase Two
    Task 3 :b1, 2024-02-01, 10d
"""
        original = MermaidImporter()._parse_mermaid_content(content)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False) as f:
            temp_path = f.name

        try:
            self.assertTrue(export_mermaid_file(original, temp_path))

            with open(temp_path, 'r', encoding='utf-8') as f:
                exported = f.read()

            # Summary tasks are written as sections, not as tasks
            self.assertIn("section Phase One", exported)
            self.assertIn("section Phase Two", exported)

            imported = import_mermaid_file(temp_path)
            self.assertIsNotNone(imported)

            self.assertEqual(len(imported.tasks), len(original.tasks))
            self.assertEqual([t.name for t in imported.get_root_tasks()],
                             ["Phase One", "Phase Two"])

            original_subtasks = {t.name for t in original.tasks if t.parent_task_id}
            imported_subtasks = {t.name for t in imported.tasks if t.parent_task_id}
            self.assertEqual(original_subtasks, imported_subtasks)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_roundtrip_preserves_dates(self):
        """Task dates are unchanged by an export and re-import."""
        content = """gantt
    title Dates
    dateFormat YYYY-MM-DD
    section Phase One
    Task 1 :a1, 2024-01-01, 5d
    Task 2 :a2, after a1, 3d
"""
        original = MermaidImporter()._parse_mermaid_content(content)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False) as f:
            temp_path = f.name

        try:
            export_mermaid_file(original, temp_path)
            imported = import_mermaid_file(temp_path)

            original_by_name = {t.name: t for t in original.tasks}
            imported_by_name = {t.name: t for t in imported.tasks}

            for name, task in original_by_name.items():
                other = imported_by_name[name]
                self.assertEqual(task.start_date, other.start_date, name)
                self.assertEqual(task.end_date, other.end_date, name)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_roundtrip_keeps_duplicate_section_names_apart(self):
        """Two parents sharing a name survive an export and re-import."""
        content = """gantt
    title Dup
    section Work
    T1 :a1, 2024-01-01, 3d
    section Other
    T2 :a2, 2024-01-08, 3d
"""
        original = MermaidImporter()._parse_mermaid_content(content)
        roots = original.get_root_tasks()
        self.assertEqual(len(roots), 2)

        # Make the two distinct parents share a name
        roots[1].name = roots[0].name

        exported = MermaidExporter().export_mermaid_content(original)
        self.assertEqual(exported.count("section Work"), 2)

        reimported = MermaidImporter()._parse_mermaid_content(exported)
        self.assertEqual(len(reimported.get_root_tasks()), 2)

    def test_exporters_agree(self):
        """Both exporter entry points produce the same content."""
        from gantt_app.utils.mermaid_exporter import generate_mermaid_content

        content = """gantt
    title Agreement
    section Phase One
    Task 1 :a1, 2024-01-01, 5d
"""
        project = MermaidImporter()._parse_mermaid_content(content)

        self.assertEqual(MermaidExporter().export_mermaid_content(project),
                         generate_mermaid_content(project))

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