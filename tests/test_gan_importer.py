"""
Unit tests for GAN file importer.
"""

import unittest
import os
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import shutil

from gantt_app.utils.gan_importer import GANImporter, import_gan_file


class TestGANImporter(unittest.TestCase):
    """Test cases for GAN file import."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.importer = GANImporter()
    
    def tearDown(self):
        """Clean up test files."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def _create_gan_file(self, content: str) -> str:
        """Create a temporary GAN file with the given XML content."""
        filepath = os.path.join(self.test_dir, "test.gan")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return filepath
    
    def test_parse_date_iso_with_milliseconds(self):
        """Test parsing ISO date with milliseconds."""
        date_str = "2024-01-01T10:30:45.123Z"
        result = self.importer.parse_date(date_str)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2024)
        self.assertEqual(result.month, 1)
        self.assertEqual(result.day, 1)
        self.assertEqual(result.hour, 10)
        self.assertEqual(result.minute, 30)
        self.assertEqual(result.second, 45)
    
    def test_parse_date_iso_without_milliseconds(self):
        """Test parsing ISO date without milliseconds."""
        date_str = "2024-01-01T10:30:45Z"
        result = self.importer.parse_date(date_str)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2024)
        self.assertEqual(result.month, 1)
        self.assertEqual(result.day, 1)
        self.assertEqual(result.hour, 10)
        self.assertEqual(result.minute, 30)
        self.assertEqual(result.second, 45)
    
    def test_parse_date_none(self):
        """Test parsing None date."""
        result = self.importer.parse_date(None)
        self.assertIsNone(result)
    
    def test_parse_date_empty_string(self):
        """Test parsing empty string date."""
        result = self.importer.parse_date("")
        self.assertIsNone(result)
    
    def test_parse_date_invalid(self):
        """Test parsing invalid date string."""
        result = self.importer.parse_date("invalid-date")
        self.assertIsNone(result)
    
    def test_parse_colors_empty(self):
        """Test parsing colors from empty XML."""
        root = ET.Element('project')
        colors = self.importer.parse_colors(root)
        
        # Should have default colors
        self.assertIn('default', colors)
        self.assertIn('milestone', colors)
        self.assertEqual(colors['default'], '#1f6aa5')
        self.assertEqual(colors['milestone'], '#e74c3c')
    
    def test_parse_colors_from_xml(self):
        """Test parsing colors from XML."""
        # Create XML with color definitions
        xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
        <project xmlns="http://ganttproject.sf.net/">
            <colors>
                <color id="color1" r="255" g="0" b="0"/>
                <color id="color2" r="0" g="255" b="0"/>
            </colors>
        </project>'''
        
        # Parse the XML
        root = ET.fromstring(xml_content)
        colors = self.importer.parse_colors(root)
        
        # Check parsed colors
        self.assertIn('color1', colors)
        self.assertIn('color2', colors)
        self.assertEqual(colors['color1'], '#ff0000')  # Red
        self.assertEqual(colors['color2'], '#00ff00')  # Green
    
    def test_import_gan_nonexistent_file(self):
        """Test importing a non-existent GAN file."""
        filepath = os.path.join(self.test_dir, "nonexistent.gan")
        result = self.importer.import_gan(filepath)
        
        self.assertIsNone(result)
    
    def test_import_gan_basic(self):
        """Test importing a basic GAN file."""
        # Create a basic GAN file
        gan_content = '''<?xml version="1.0" encoding="UTF-8"?>
        <project name="Test Project" xmlns="http://ganttproject.sf.net/">
            <tasks>
                <task id="task1" name="Test Task">
                    <start>2024-01-01T00:00:00.000Z</start>
                    <end>2024-01-10T00:00:00.000Z</end>
                    <duration length="10"/>
                </task>
            </tasks>
        </project>'''
        
        filepath = self._create_gan_file(gan_content)
        result = self.importer.import_gan(filepath)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "Test Project")
        self.assertEqual(len(result.tasks), 1)
        self.assertEqual(result.tasks[0].name, "Test Task")
    
    def test_import_gan_with_milestone(self):
        """Test importing a GAN file with milestones."""
        gan_content = '''<?xml version="1.0" encoding="UTF-8"?>
        <project name="Milestone Project" xmlns="http://ganttproject.sf.net/">
            <tasks>
                <task id="task1" name="Regular Task">
                    <start>2024-01-01T00:00:00.000Z</start>
                    <end>2024-01-10T00:00:00.000Z</end>
                    <duration length="10"/>
                </task>
                <task id="milestone1" name="Review Milestone">
                    <start>2024-01-11T00:00:00.000Z</start>
                    <duration length="0"/>
                </task>
            </tasks>
        </project>'''
        
        filepath = self._create_gan_file(gan_content)
        result = self.importer.import_gan(filepath)
        
        self.assertIsNotNone(result)
        self.assertEqual(len(result.tasks), 2)
        
        # Find the milestone
        milestone = [t for t in result.tasks if t.is_milestone]
        self.assertEqual(len(milestone), 1)
        self.assertEqual(milestone[0].name, "Review Milestone")
        self.assertTrue(milestone[0].is_milestone)
    
    def test_import_gan_with_dependencies(self):
        """Test importing a GAN file with task dependencies."""
        gan_content = '''<?xml version="1.0" encoding="UTF-8"?>
        <project name="Dependencies Project" xmlns="http://ganttproject.sf.net/">
            <tasks>
                <task id="task1" name="Task 1">
                    <start>2024-01-01T00:00:00.000Z</start>
                    <end>2024-01-10T00:00:00.000Z</end>
                    <duration length="10"/>
                </task>
                <task id="task2" name="Task 2">
                    <start>2024-01-11T00:00:00.000Z</start>
                    <end>2024-01-20T00:00:00.000Z</end>
                    <duration length="10"/>
                    <depends-on>
                        <dependency idref="task1"/>
                    </depends-on>
                </task>
            </tasks>
        </project>'''
        
        filepath = self._create_gan_file(gan_content)
        result = self.importer.import_gan(filepath)
        
        self.assertIsNotNone(result)
        self.assertEqual(len(result.tasks), 2)
        
        # Check dependencies
        task2 = result.get_task_by_id("task2")
        self.assertIsNotNone(task2)
        self.assertIn("task1", task2.dependencies)
    
    def test_import_gan_with_colors(self):
        """Test importing a GAN file with custom colors."""
        gan_content = '''<?xml version="1.0" encoding="UTF-8"?>
        <project name="Color Project" xmlns="http://ganttproject.sf.net/">
            <colors>
                <color id="color1" r="255" g="100" b="50"/>
            </colors>
            <tasks>
                <task id="task1" name="Colored Task">
                    <start>2024-01-01T00:00:00.000Z</start>
                    <end>2024-01-10T00:00:00.000Z</end>
                    <color id="color1"/>
                    <duration length="10"/>
                </task>
            </tasks>
        </project>'''
        
        filepath = self._create_gan_file(gan_content)
        result = self.importer.import_gan(filepath)
        
        self.assertIsNotNone(result)
        self.assertEqual(len(result.tasks), 1)
        
        # Check color
        task = result.tasks[0]
        self.assertEqual(task.color, '#ff6432')  # RGB(255,100,50)
    
    def test_import_gan_with_progress(self):
        """Test importing a GAN file with task progress."""
        gan_content = '''<?xml version="1.0" encoding="UTF-8"?>
        <project name="Progress Project" xmlns="http://ganttproject.sf.net/">
            <tasks>
                <task id="task1" name="In Progress Task">
                    <start>2024-01-01T00:00:00.000Z</start>
                    <end>2024-01-10T00:00:00.000Z</end>
                    <completion percentage="50"/>
                    <duration length="10"/>
                </task>
            </tasks>
        </project>'''
        
        filepath = self._create_gan_file(gan_content)
        result = self.importer.import_gan(filepath)
        
        self.assertIsNotNone(result)
        task = result.tasks[0]
        self.assertEqual(task.progress, 50)
    
    def test_convenience_function(self):
        """Test the import_gan_file convenience function."""
        gan_content = '''<?xml version="1.0" encoding="UTF-8"?>
        <project name="Convenience Test" xmlns="http://ganttproject.sf.net/">
            <tasks>
                <task id="task1" name="Convenience Task">
                    <start>2024-01-01T00:00:00.000Z</start>
                    <end>2024-01-10T00:00:00.000Z</end>
                    <duration length="10"/>
                </task>
            </tasks>
        </project>'''
        
        filepath = self._create_gan_file(gan_content)
        result = import_gan_file(filepath)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "Convenience Test")
    
    def test_import_invalid_xml(self):
        """Test importing a file with invalid XML."""
        filepath = os.path.join(self.test_dir, "invalid.xml")
        with open(filepath, 'w') as f:
            f.write("<invalid xml>")
        
        result = self.importer.import_gan(filepath)
        
        self.assertIsNone(result)


class TestGANEdgeCases(unittest.TestCase):
    """Test edge cases for GAN import."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.importer = GANImporter()
    
    def tearDown(self):
        """Clean up test files."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_empty_tasks_list(self):
        """Test importing GAN file with empty tasks list."""
        gan_content = '''<?xml version="1.0" encoding="UTF-8"?>
        <project name="Empty Project" xmlns="http://ganttproject.sf.net/">
            <tasks></tasks>
        </project>'''
        
        filepath = os.path.join(self.test_dir, "empty.gan")
        with open(filepath, 'w') as f:
            f.write(gan_content)
        
        result = self.importer.import_gan(filepath)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "Empty Project")
        self.assertEqual(len(result.tasks), 0)
    
    def test_missing_project_name(self):
        """Test importing GAN file without project name."""
        gan_content = '''<?xml version="1.0" encoding="UTF-8"?>
        <project xmlns="http://ganttproject.sf.net/">
            <tasks>
                <task id="task1" name="Test Task">
                    <start>2024-01-01T00:00:00.000Z</start>
                    <end>2024-01-10T00:00:00.000Z</end>
                    <duration length="10"/>
                </task>
            </tasks>
        </project>'''
        
        filepath = os.path.join(self.test_dir, "no_name.gan")
        with open(filepath, 'w') as f:
            f.write(gan_content)
        
        result = self.importer.import_gan(filepath)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "Imported Project")  # Default name
    
    def test_task_without_dates(self):
        """Test importing task without start/end dates."""
        gan_content = '''<?xml version="1.0" encoding="UTF-8"?>
        <project name="No Dates Project" xmlns="http://ganttproject.sf.net/">
            <tasks>
                <task id="task1" name="No Dates Task">
                    <duration length="5"/>
                </task>
            </tasks>
        </project>'''
        
        filepath = os.path.join(self.test_dir, "no_dates.gan")
        with open(filepath, 'w') as f:
            f.write(gan_content)
        
        result = self.importer.import_gan(filepath)
        
        self.assertIsNotNone(result)
        # Task should be created with current date as fallback
        self.assertEqual(result.tasks[0].name, "No Dates Task")


if __name__ == '__main__':
    unittest.main()