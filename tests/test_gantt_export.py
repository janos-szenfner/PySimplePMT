"""
Tests for Gantt chart export functionality (PNG and PDF).
"""

import unittest
import tempfile
import os
from datetime import datetime, timedelta

import tkinter as tk

from gantt_app.models import Project, Task
from gantt_app.views.gantt_chart import GanttChart


class TestGanttChartExport(unittest.TestCase):
    """Tests for GanttChart export functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.root = tk.Tk()
        self.root.withdraw()
        
        self.project = Project(name="Export Test")
        start_date = datetime(2024, 1, 1)
        self.project.add_task(Task.create_task("Task 1", start_date, start_date + timedelta(days=5)))
        self.project.add_task(Task.create_task("Task 2", start_date + timedelta(days=6), start_date + timedelta(days=10)))
        
        self.chart = GanttChart(self.root, self.project, width=8, height=6, dpi=100)
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.root.destroy()
    
    def test_export_to_png(self):
        """Test exporting Gantt chart to PNG."""
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            png_path = f.name
        
        try:
            result = self.chart.export_to_png(png_path)
            self.assertTrue(result)
            self.assertTrue(os.path.exists(png_path))
            
            # Check file size is reasonable
            file_size = os.path.getsize(png_path)
            self.assertGreater(file_size, 1000)  # Should be at least 1KB
        finally:
            if os.path.exists(png_path):
                os.unlink(png_path)
    
    def test_export_to_pdf(self):
        """Test exporting Gantt chart to PDF."""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            pdf_path = f.name
        
        try:
            result = self.chart.export_to_pdf(pdf_path)
            self.assertTrue(result)
            self.assertTrue(os.path.exists(pdf_path))
            
            # Check file size is reasonable
            file_size = os.path.getsize(pdf_path)
            self.assertGreater(file_size, 1000)  # Should be at least 1KB
        finally:
            if os.path.exists(pdf_path):
                os.unlink(pdf_path)
    
    def test_export_png_with_milestones(self):
        """Test PNG export with milestones."""
        project_with_milestone = Project(name="Milestone Test")
        start_date = datetime(2024, 1, 1)
        project_with_milestone.add_task(Task.create_task("Task 1", start_date, start_date + timedelta(days=5)))
        project_with_milestone.add_task(Task.create_milestone("Milestone", start_date + timedelta(days=6)))
        
        chart = GanttChart(self.root, project_with_milestone, width=8, height=6, dpi=100)
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            png_path = f.name
        
        try:
            result = chart.export_to_png(png_path)
            self.assertTrue(result)
            self.assertTrue(os.path.exists(png_path))
        finally:
            if os.path.exists(png_path):
                os.unlink(png_path)
    
    def test_export_pdf_with_dependencies(self):
        """Test PDF export with task dependencies."""
        project_with_deps = Project(name="Dependencies Test")
        start_date = datetime(2024, 1, 1)
        
        task1 = Task.create_task("Task 1", start_date, start_date + timedelta(days=5))
        project_with_deps.add_task(task1)
        
        task2 = Task.create_task("Task 2", start_date + timedelta(days=6), start_date + timedelta(days=10))
        task2.dependencies = [task1.id]
        project_with_deps.add_task(task2)
        
        chart = GanttChart(self.root, project_with_deps, width=8, height=6, dpi=100)
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            pdf_path = f.name
        
        try:
            result = chart.export_to_pdf(pdf_path)
            self.assertTrue(result)
            self.assertTrue(os.path.exists(pdf_path))
        finally:
            if os.path.exists(pdf_path):
                os.unlink(pdf_path)
    
    def test_export_custom_dpi(self):
        """Test PNG export with custom DPI."""
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            png_path = f.name
        
        try:
            # Export with high DPI
            result = self.chart.export_to_png(png_path, dpi=600)
            self.assertTrue(result)
            self.assertTrue(os.path.exists(png_path))
            
            # Higher DPI should result in larger file
            file_size = os.path.getsize(png_path)
            self.assertGreater(file_size, 50000)  # Should be larger with 600 DPI
        finally:
            if os.path.exists(png_path):
                os.unlink(png_path)
    
    def test_export_empty_project(self):
        """Test exporting a project with no tasks."""
        empty_project = Project(name="Empty Project")
        chart = GanttChart(self.root, empty_project, width=8, height=6, dpi=100)
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            png_path = f.name
        
        try:
            result = chart.export_to_png(png_path)
            self.assertTrue(result)
            self.assertTrue(os.path.exists(png_path))
        finally:
            if os.path.exists(png_path):
                os.unlink(png_path)
    
    def test_export_nonexistent_directory(self):
        """Test exporting to a directory that doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            png_path = os.path.join(temp_dir, "subdir", "chart.png")
            
            result = self.chart.export_to_png(png_path)
            self.assertTrue(result)
            self.assertTrue(os.path.exists(png_path))


if __name__ == '__main__':
    unittest.main()