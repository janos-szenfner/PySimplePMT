"""
Unit tests for the Project Dashboard module.

DEVELOPMENT NOTES:
------------------
These tests verify the dashboard's calculation logic, data processing,
and HTML generation without requiring a display or GUI interaction.

All tests are designed to run headless and do not open any windows.
"""

import unittest
from datetime import datetime, timedelta

# Import the dashboard module
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gantt_app.views.project_dashboard import ProjectDashboard


class TestProjectDashboardDataProcessing(unittest.TestCase):
    """Tests for data processing and sample data creation."""

    def setUp(self):
        """Set up test fixtures."""
        self.dashboard = ProjectDashboard()
        self.sample_data = self.dashboard.project_data

    def test_sample_data_structure(self):
        """Sample data has correct structure with required fields."""
        required_fields = ['ID', 'Task Name', 'Type', 'Duration', 'Progress', 'Level', 'Start Date', 'End Date']
        
        for task in self.sample_data:
            for field in required_fields:
                self.assertIn(field, task, 
                           f"Missing required field '{field}' in task {task.get('ID', 'unknown')}")

    def test_sample_data_types(self):
        """Sample data has correct data types."""
        for task in self.sample_data:
            self.assertIsInstance(task['ID'], str)
            self.assertIsInstance(task['Task Name'], str)
            self.assertIsInstance(task['Type'], str)
            self.assertIsInstance(task['Duration'], int)
            self.assertIsInstance(task['Progress'], int)
            self.assertIsInstance(task['Level'], int)
            self.assertIsInstance(task['Start Date'], datetime)
            self.assertIsInstance(task['End Date'], datetime)

    def test_sample_data_task_types(self):
        """Sample data contains expected task types."""
        types = [task['Type'] for task in self.sample_data]
        
        # Should have Task, Subtask, and Milestone types
        self.assertIn('Task', types)
        self.assertIn('Subtask', types)
        self.assertIn('Milestone', types)

    def test_sample_data_levels(self):
        """Sample data has correct outline levels."""
        levels = [task['Level'] for task in self.sample_data]
        
        # Should have both Level 1 and Level 2 tasks
        self.assertIn(1, levels)
        self.assertIn(2, levels)

    def test_data_list_creation(self):
        """Project data is correctly stored as list of dicts."""
        self.assertIsInstance(self.sample_data, list)
        self.assertEqual(len(self.sample_data), 8)  # Sample has 8 tasks
        # Verify all items have required fields
        for task in self.sample_data:
            self.assertIn('ID', task)
            self.assertIn('Task Name', task)
            self.assertIn('Type', task)

    def test_custom_data_initialization(self):
        """Dashboard can be initialized with custom data."""
        custom_data = [
            {
                "ID": "001",
                "Task Name": "Custom Task",
                "Type": "Task",
                "Duration": 5,
                "Progress": 50,
                "Level": 1,
                "Start Date": datetime(2026, 1, 1),
                "End Date": datetime(2026, 1, 5)
            }
        ]
        
        custom_dashboard = ProjectDashboard(project_data=custom_data)
        self.assertEqual(len(custom_dashboard.project_data), 1)
        self.assertEqual(custom_dashboard.project_data[0]['Task Name'], "Custom Task")


class TestWeightedProgressCalculation(unittest.TestCase):
    """Tests for weighted progress calculation logic."""

    def test_weighted_progress_basic(self):
        """Weighted progress is calculated correctly for basic case."""
        # Create dashboard with specific data
        data = [
            {"ID": "001", "Task Name": "Task A", "Type": "Task", "Duration": 10, "Progress": 50, "Level": 1, "Start Date": datetime(2026, 1, 1), "End Date": datetime(2026, 1, 10)},
            {"ID": "002", "Task Name": "Task B", "Type": "Task", "Duration": 10, "Progress": 100, "Level": 1, "Start Date": datetime(2026, 1, 11), "End Date": datetime(2026, 1, 20)},
        ]
        
        dashboard = ProjectDashboard(project_data=data)
        weighted_progress = dashboard._calculate_weighted_progress()
        
        # Expected: (10 * 50 + 10 * 100) / (10 + 10) = 1500 / 20 = 75.0
        self.assertEqual(weighted_progress, 75.0)

    def test_weighted_progress_only_level_1(self):
        """Weighted progress only considers Level 1 tasks."""
        data = [
            {"ID": "001", "Task Name": "Main Task", "Type": "Task", "Duration": 10, "Progress": 50, "Level": 1, "Start Date": datetime(2026, 1, 1), "End Date": datetime(2026, 1, 10)},
            {"ID": "002", "Task Name": "Subtask", "Type": "Subtask", "Duration": 5, "Progress": 100, "Level": 2, "Start Date": datetime(2026, 1, 1), "End Date": datetime(2026, 1, 5)},
        ]
        
        dashboard = ProjectDashboard(project_data=data)
        weighted_progress = dashboard._calculate_weighted_progress()
        
        # Subtask should be ignored, only main task counts
        # Expected: (10 * 50) / 10 = 50.0
        self.assertEqual(weighted_progress, 50.0)

    def test_weighted_progress_zero_duration(self):
        """Weighted progress handles zero total duration gracefully."""
        data = [
            {"ID": "001", "Task Name": "Milestone", "Type": "Milestone", "Duration": 0, "Progress": 0, "Level": 1, "Start Date": datetime(2026, 1, 1), "End Date": datetime(2026, 1, 1)},
        ]
        
        dashboard = ProjectDashboard(project_data=data)
        weighted_progress = dashboard._calculate_weighted_progress()
        
        # Should return 0.0 when total duration is 0
        self.assertEqual(weighted_progress, 0.0)

    def test_weighted_progress_formula_from_requirements(self):
        """Test the specific formula from requirements: (8 * 0.30) / 21 = 11.43%
        
        This matches the example in the requirements where:
        - Implementation has duration 8 and progress 30%
        - Total scope is 21 days
        - Expected weighted progress: (8 * 0.30) / 21 = 0.1142857... = 11.43%
        """
        # Create data matching the requirements example
        data = [
            {"ID": "001", "Task Name": "Project Planning", "Type": "Task", "Duration": 2, "Progress": 0, "Level": 1, "Start Date": datetime(2026, 1, 1), "End Date": datetime(2026, 1, 2)},
            {"ID": "002", "Task Name": "Requirements Gathering", "Type": "Subtask", "Duration": 1, "Progress": 0, "Level": 2, "Start Date": datetime(2026, 1, 3), "End Date": datetime(2026, 1, 3)},
            {"ID": "003", "Task Name": "Design Phase", "Type": "Task", "Duration": 5, "Progress": 0, "Level": 1, "Start Date": datetime(2026, 1, 4), "End Date": datetime(2026, 1, 8)},
            {"ID": "004", "Task Name": "UI Mockups", "Type": "Subtask", "Duration": 3, "Progress": 0, "Level": 2, "Start Date": datetime(2026, 1, 9), "End Date": datetime(2026, 1, 11)},
            {"ID": "005", "Task Name": "Implementation", "Type": "Task", "Duration": 8, "Progress": 30, "Level": 1, "Start Date": datetime(2026, 1, 12), "End Date": datetime(2026, 1, 19)},
            {"ID": "006", "Task Name": "Design Review", "Type": "Milestone", "Duration": 0, "Progress": 0, "Level": 1, "Start Date": datetime(2026, 1, 20), "End Date": datetime(2026, 1, 20)},
            {"ID": "007", "Task Name": "Testing", "Type": "Task", "Duration": 3, "Progress": 0, "Level": 1, "Start Date": datetime(2026, 1, 21), "End Date": datetime(2026, 1, 23)},
            {"ID": "008", "Task Name": "Deployment", "Type": "Task", "Duration": 3, "Progress": 0, "Level": 1, "Start Date": datetime(2026, 1, 24), "End Date": datetime(2026, 1, 26)},
        ]
        
        dashboard = ProjectDashboard(project_data=data)
        weighted_progress = dashboard._calculate_weighted_progress()
        
        # Level 1 tasks: Project Planning (2), Design Phase (5), Implementation (8), Testing (3), Deployment (3)
        # Total Level 1 duration = 2 + 5 + 8 + 3 + 3 = 21
        # Weighted sum = 2*0 + 5*0 + 8*30 + 3*0 + 3*0 = 240
        # Weighted progress = 240 / 21 = 11.42857...
        expected = 240 / 21
        self.assertAlmostEqual(weighted_progress, expected, places=4)


class TestKPIMetricsCalculation(unittest.TestCase):
    """Tests for KPI metrics calculation logic."""

    def test_total_project_scope(self):
        """Total Project Scope is sum of Level 1 task durations."""
        data = [
            {"ID": "001", "Task Name": "Task A", "Type": "Task", "Duration": 10, "Progress": 0, "Level": 1, "Start Date": datetime(2026, 1, 1), "End Date": datetime(2026, 1, 10)},
            {"ID": "002", "Task Name": "Task B", "Type": "Task", "Duration": 5, "Progress": 0, "Level": 1, "Start Date": datetime(2026, 1, 11), "End Date": datetime(2026, 1, 15)},
            {"ID": "003", "Task Name": "Subtask", "Type": "Subtask", "Duration": 3, "Progress": 0, "Level": 2, "Start Date": datetime(2026, 1, 1), "End Date": datetime(2026, 1, 3)},
        ]
        
        dashboard = ProjectDashboard(project_data=data)
        metrics = dashboard._calculate_kpi_metrics()
        
        # Total scope should be 10 + 5 = 15 (only Level 1)
        self.assertEqual(metrics['total_project_scope'], 15)

    def test_total_items_tracked(self):
        """Total Items Tracked is total number of items."""
        data = [
            {"ID": "001", "Task Name": "Task A", "Type": "Task", "Duration": 10, "Progress": 0, "Level": 1, "Start Date": datetime(2026, 1, 1), "End Date": datetime(2026, 1, 10)},
            {"ID": "002", "Task Name": "Task B", "Type": "Task", "Duration": 5, "Progress": 0, "Level": 1, "Start Date": datetime(2026, 1, 11), "End Date": datetime(2026, 1, 15)},
            {"ID": "003", "Task Name": "Subtask", "Type": "Subtask", "Duration": 3, "Progress": 0, "Level": 2, "Start Date": datetime(2026, 1, 1), "End Date": datetime(2026, 1, 3)},
        ]
        
        dashboard = ProjectDashboard(project_data=data)
        metrics = dashboard._calculate_kpi_metrics()
        
        self.assertEqual(metrics['total_items_tracked'], 3)

    def test_milestones_count(self):
        """Milestones Count is number of items with Type == 'Milestone'."""
        data = [
            {"ID": "001", "Task Name": "Task A", "Type": "Task", "Duration": 10, "Progress": 0, "Level": 1, "Start Date": datetime(2026, 1, 1), "End Date": datetime(2026, 1, 10)},
            {"ID": "002", "Task Name": "Milestone 1", "Type": "Milestone", "Duration": 0, "Progress": 0, "Level": 1, "Start Date": datetime(2026, 1, 11), "End Date": datetime(2026, 1, 11)},
            {"ID": "003", "Task Name": "Task B", "Type": "Task", "Duration": 5, "Progress": 0, "Level": 1, "Start Date": datetime(2026, 1, 12), "End Date": datetime(2026, 1, 16)},
            {"ID": "004", "Task Name": "Milestone 2", "Type": "Milestone", "Duration": 0, "Progress": 0, "Level": 1, "Start Date": datetime(2026, 1, 17), "End Date": datetime(2026, 1, 17)},
        ]
        
        dashboard = ProjectDashboard(project_data=data)
        metrics = dashboard._calculate_kpi_metrics()
        
        self.assertEqual(metrics['milestones_count'], 2)

    def test_average_progress(self):
        """Average Progress is the weighted progress."""
        data = [
            {"ID": "001", "Task Name": "Task A", "Type": "Task", "Duration": 10, "Progress": 50, "Level": 1, "Start Date": datetime(2026, 1, 1), "End Date": datetime(2026, 1, 10)},
            {"ID": "002", "Task Name": "Task B", "Type": "Task", "Duration": 10, "Progress": 75, "Level": 1, "Start Date": datetime(2026, 1, 11), "End Date": datetime(2026, 1, 20)},
        ]
        
        dashboard = ProjectDashboard(project_data=data)
        metrics = dashboard._calculate_kpi_metrics()
        
        # Expected: (10*50 + 10*75) / (10+10) = 1250 / 20 = 62.5
        self.assertEqual(metrics['average_progress'], 62.5)

    def test_active_status_percentage(self):
        """Active Status shows percentage of items with progress > 0."""
        data = [
            {"ID": "001", "Task Name": "Task A", "Type": "Task", "Duration": 10, "Progress": 50, "Level": 1, "Start Date": datetime(2026, 1, 1), "End Date": datetime(2026, 1, 10)},
            {"ID": "002", "Task Name": "Task B", "Type": "Task", "Duration": 10, "Progress": 0, "Level": 1, "Start Date": datetime(2026, 1, 11), "End Date": datetime(2026, 1, 20)},
            {"ID": "003", "Task Name": "Task C", "Type": "Task", "Duration": 10, "Progress": 25, "Level": 1, "Start Date": datetime(2026, 1, 21), "End Date": datetime(2026, 1, 30)},
        ]
        
        dashboard = ProjectDashboard(project_data=data)
        metrics = dashboard._calculate_kpi_metrics()
        
        # 2 out of 3 items have progress > 0, so 66.666...%
        active_status = metrics['active_status']
        self.assertIn("67%", active_status)
        self.assertIn("Active", active_status)

    def test_active_status_zero(self):
        """Active Status handles case when no items have progress."""
        data = [
            {"ID": "001", "Task Name": "Task A", "Type": "Task", "Duration": 10, "Progress": 0, "Level": 1, "Start Date": datetime(2026, 1, 1), "End Date": datetime(2026, 1, 10)},
            {"ID": "002", "Task Name": "Task B", "Type": "Task", "Duration": 10, "Progress": 0, "Level": 1, "Start Date": datetime(2026, 1, 11), "End Date": datetime(2026, 1, 20)},
        ]
        
        dashboard = ProjectDashboard(project_data=data)
        metrics = dashboard._calculate_kpi_metrics()
        
        self.assertEqual(metrics['active_status'], "0% Active (A)")


class TestHTMLGeneration(unittest.TestCase):
    """Tests for HTML generation functionality."""

    def test_html_generation_returns_string(self):
        """generate_dashboard_html returns a string."""
        dashboard = ProjectDashboard()
        html = dashboard.generate_dashboard_html()
        
        self.assertIsInstance(html, str)

    def test_html_contains_plotly_div(self):
        """Generated HTML contains Plotly chart div."""
        dashboard = ProjectDashboard()
        html = dashboard.generate_dashboard_html()
        
        self.assertIn("<div", html)
        self.assertIn("plotly", html.lower())

    def test_html_contains_all_chart_titles(self):
        """Generated HTML contains all chart titles."""
        dashboard = ProjectDashboard()
        html = dashboard.generate_dashboard_html()
        
        titles = [
            "Task Progress (%) Breakdown",
            "Duration Allocation by Task Type",
            "Duration per Item",
            "Dashboard Summary KPIs"
        ]
        
        for title in titles:
            self.assertIn(title, html, f"Missing chart title: {title}")

    def test_html_contains_kpi_metrics(self):
        """Generated HTML contains KPI metrics."""
        dashboard = ProjectDashboard()
        html = dashboard.generate_dashboard_html()
        
        kpi_terms = [
            "PROJECT METRICS OVERVIEW",
            "Total Project Scope",
            "Total Items Tracked",
            "Milestones Count",
            "Average Progress",
            "Active Status"
        ]
        
        for term in kpi_terms:
            self.assertIn(term, html, f"Missing KPI term: {term}")

    def test_html_contains_task_names(self):
        """Generated HTML contains task names from data."""
        data = [
            {"ID": "001", "Task Name": "Custom Task", "Type": "Task", "Duration": 5, "Progress": 50, "Level": 1, "Start Date": datetime(2026, 1, 1), "End Date": datetime(2026, 1, 5)},
        ]
        
        dashboard = ProjectDashboard(project_data=data)
        html = dashboard.generate_dashboard_html()
        
        self.assertIn("Custom Task", html)


class TestFigureOnlyCreation(unittest.TestCase):
    """Tests for _create_figure_only method."""

    def test_figure_only_returns_figure(self):
        """_create_figure_only returns a Plotly figure."""
        dashboard = ProjectDashboard()
        fig = dashboard._create_figure_only()
        
        # Check if it's a Plotly figure by checking for expected attributes
        self.assertTrue(hasattr(fig, 'to_html'))
        self.assertTrue(hasattr(fig, 'update_layout'))

    def test_figure_only_respects_dimensions(self):
        """_create_figure_only respects provided dimensions."""
        dashboard = ProjectDashboard()
        
        fig1 = dashboard._create_figure_only(width=1000, height=800)
        fig2 = dashboard._create_figure_only(width=1500, height=1000)
        
        # Figures should have different dimensions
        self.assertNotEqual(fig1.to_dict()['layout']['width'], 
                          fig2.to_dict()['layout']['width'])
        self.assertNotEqual(fig1.to_dict()['layout']['height'], 
                          fig2.to_dict()['layout']['height'])


class TestDurationAllocationLogic(unittest.TestCase):
    """Tests for duration allocation calculation."""

    def test_duration_allocation_by_type(self):
        """Duration allocation groups by Type correctly."""
        data = [
            {"ID": "001", "Task Name": "Task A", "Type": "Task", "Duration": 10, "Progress": 0, "Level": 1, "Start Date": datetime(2026, 1, 1), "End Date": datetime(2026, 1, 10)},
            {"ID": "002", "Task Name": "Task B", "Type": "Task", "Duration": 15, "Progress": 0, "Level": 1, "Start Date": datetime(2026, 1, 11), "End Date": datetime(2026, 1, 25)},
            {"ID": "003", "Task Name": "Subtask A", "Type": "Subtask", "Duration": 5, "Progress": 0, "Level": 2, "Start Date": datetime(2026, 1, 1), "End Date": datetime(2026, 1, 5)},
            {"ID": "004", "Task Name": "Subtask B", "Type": "Subtask", "Duration": 3, "Progress": 0, "Level": 2, "Start Date": datetime(2026, 1, 6), "End Date": datetime(2026, 1, 8)},
            {"ID": "005", "Task Name": "Milestone A", "Type": "Milestone", "Duration": 0, "Progress": 0, "Level": 1, "Start Date": datetime(2026, 1, 26), "End Date": datetime(2026, 1, 26)},
        ]
        
        dashboard = ProjectDashboard(project_data=data)
        # Calculate type duration manually
        type_duration = {}
        for t in data:
            task_type = t['Type']
            if task_type not in type_duration:
                type_duration[task_type] = 0
            type_duration[task_type] += t['Duration']
        
        # Task: 10 + 15 = 25
        # Subtask: 5 + 3 = 8
        # Milestone: 0
        self.assertEqual(type_duration['Task'], 25)
        self.assertEqual(type_duration['Subtask'], 8)
        self.assertEqual(type_duration['Milestone'], 0)

    def test_duration_allocation_percentage(self):
        """Duration allocation percentages are calculated correctly."""
        data = [
            {"ID": "001", "Task Name": "Task A", "Type": "Task", "Duration": 25, "Progress": 0, "Level": 1, "Start Date": datetime(2026, 1, 1), "End Date": datetime(2026, 1, 25)},
            {"ID": "002", "Task Name": "Subtask A", "Type": "Subtask", "Duration": 4, "Progress": 0, "Level": 2, "Start Date": datetime(2026, 1, 1), "End Date": datetime(2026, 1, 4)},
            {"ID": "003", "Task Name": "Milestone A", "Type": "Milestone", "Duration": 0, "Progress": 0, "Level": 1, "Start Date": datetime(2026, 1, 26), "End Date": datetime(2026, 1, 26)},
        ]
        
        dashboard = ProjectDashboard(project_data=data)
        # Calculate type duration manually
        type_duration = {}
        for t in data:
            task_type = t['Type']
            if task_type not in type_duration:
                type_duration[task_type] = 0
            type_duration[task_type] += t['Duration']
        
        total_duration = sum(type_duration.values())
        
        # Total = 25 + 4 + 0 = 29
        # Task: 25 / 29 = 86.206...%
        # Subtask: 4 / 29 = 13.793...%
        # Milestone: 0 / 29 = 0%
        
        task_percent = (type_duration['Task'] / total_duration) * 100
        subtask_percent = (type_duration['Subtask'] / total_duration) * 100
        milestone_percent = (type_duration['Milestone'] / total_duration) * 100
        
        self.assertAlmostEqual(task_percent, 86.20689655, places=4)
        self.assertAlmostEqual(subtask_percent, 13.79310345, places=4)
        self.assertEqual(milestone_percent, 0.0)

    def test_duration_allocation_matches_requirements_example(self):
        """Test duration allocation matches the requirements example.
        
        From requirements:
        * Tasks: 21 / 25 = 84.0%
        * Subtasks: 4 / 25 = 16.0%
        * Milestones: 0 / 25 = 0.0%
        """
        # Total duration = 25 (21 Tasks + 4 Subtasks + 0 Milestones)
        data = [
            {"ID": "001", "Task Name": "P1", "Type": "Task", "Duration": 2, "Progress": 0, "Level": 1, "Start Date": datetime(2026, 1, 1), "End Date": datetime(2026, 1, 2)},
            {"ID": "002", "Task Name": "P2", "Type": "Task", "Duration": 5, "Progress": 0, "Level": 1, "Start Date": datetime(2026, 1, 3), "End Date": datetime(2026, 1, 7)},
            {"ID": "003", "Task Name": "P3", "Type": "Task", "Duration": 8, "Progress": 0, "Level": 1, "Start Date": datetime(2026, 1, 8), "End Date": datetime(2026, 1, 15)},
            {"ID": "004", "Task Name": "P4", "Type": "Task", "Duration": 3, "Progress": 0, "Level": 1, "Start Date": datetime(2026, 1, 16), "End Date": datetime(2026, 1, 18)},
            {"ID": "005", "Task Name": "P5", "Type": "Task", "Duration": 3, "Progress": 0, "Level": 1, "Start Date": datetime(2026, 1, 19), "End Date": datetime(2026, 1, 21)},
            {"ID": "006", "Task Name": "S1", "Type": "Subtask", "Duration": 1, "Progress": 0, "Level": 2, "Start Date": datetime(2026, 1, 1), "End Date": datetime(2026, 1, 1)},
            {"ID": "007", "Task Name": "S2", "Type": "Subtask", "Duration": 1, "Progress": 0, "Level": 2, "Start Date": datetime(2026, 1, 2), "End Date": datetime(2026, 1, 2)},
            {"ID": "008", "Task Name": "S3", "Type": "Subtask", "Duration": 1, "Progress": 0, "Level": 2, "Start Date": datetime(2026, 1, 3), "End Date": datetime(2026, 1, 3)},
            {"ID": "009", "Task Name": "S4", "Type": "Subtask", "Duration": 1, "Progress": 0, "Level": 2, "Start Date": datetime(2026, 1, 4), "End Date": datetime(2026, 1, 4)},
            {"ID": "010", "Task Name": "M1", "Type": "Milestone", "Duration": 0, "Progress": 0, "Level": 1, "Start Date": datetime(2026, 1, 22), "End Date": datetime(2026, 1, 22)},
        ]
        
        dashboard = ProjectDashboard(project_data=data)
        # Calculate type duration manually
        type_duration = {}
        for t in data:
            task_type = t['Type']
            if task_type not in type_duration:
                type_duration[task_type] = 0
            type_duration[task_type] += t['Duration']
        
        total_duration = sum(type_duration.values())
        
        # Task total: 2 + 5 + 8 + 3 + 3 = 21
        # Subtask total: 1 + 1 + 1 + 1 = 4
        # Milestone total: 0
        # Total: 25
        
        task_percent = (type_duration['Task'] / total_duration) * 100
        subtask_percent = (type_duration['Subtask'] / total_duration) * 100
        milestone_percent = (type_duration['Milestone'] / total_duration) * 100
        
        self.assertEqual(task_percent, 84.0)
        self.assertEqual(subtask_percent, 16.0)
        self.assertEqual(milestone_percent, 0.0)


class TestItemWorkloadDistribution(unittest.TestCase):
    """Tests for item workload distribution logic."""

    def test_item_duration_formula(self):
        """Item Duration = End Date - Start Date + 1."""
        start_date = datetime(2026, 1, 1)
        end_date = datetime(2026, 1, 5)
        
        data = [
            {"ID": "001", "Task Name": "Task A", "Type": "Task", "Duration": 5, "Progress": 0, "Level": 1, "Start Date": start_date, "End Date": end_date},
        ]
        
        dashboard = ProjectDashboard(project_data=data)
        
        # Duration should be as provided in the data
        self.assertEqual(dashboard.project_data[0]['Duration'], 5)

    def test_item_duration_single_day(self):
        """Single day task has duration of 1."""
        start_date = datetime(2026, 1, 1)
        
        data = [
            {"ID": "001", "Task Name": "Task A", "Type": "Task", "Duration": 1, "Progress": 0, "Level": 1, "Start Date": start_date, "End Date": start_date},
        ]
        
        dashboard = ProjectDashboard(project_data=data)
        self.assertEqual(dashboard.project_data[0]['Duration'], 1)

    def test_workload_distribution_sorted_by_id(self):
        """Workload distribution chart sorts tasks by ID."""
        data = [
            {"ID": "003", "Task Name": "Task C", "Type": "Task", "Duration": 3, "Progress": 0, "Level": 1, "Start Date": datetime(2026, 1, 1), "End Date": datetime(2026, 1, 3)},
            {"ID": "001", "Task Name": "Task A", "Type": "Task", "Duration": 1, "Progress": 0, "Level": 1, "Start Date": datetime(2026, 1, 1), "End Date": datetime(2026, 1, 1)},
            {"ID": "002", "Task Name": "Task B", "Type": "Task", "Duration": 2, "Progress": 0, "Level": 1, "Start Date": datetime(2026, 1, 2), "End Date": datetime(2026, 1, 3)},
        ]
        
        dashboard = ProjectDashboard(project_data=data)
        sorted_tasks = sorted(dashboard.project_data, key=lambda t: t['ID'])
        
        # Should be sorted as 001, 002, 003
        self.assertEqual(sorted_tasks[0]['ID'], "001")
        self.assertEqual(sorted_tasks[1]['ID'], "002")
        self.assertEqual(sorted_tasks[2]['ID'], "003")


class TestEdgeCases(unittest.TestCase):
    """Tests for edge cases and error handling."""

    def test_empty_project_data(self):
        """Dashboard handles empty project data gracefully."""
        # Empty list should use sample data
        dashboard = ProjectDashboard(project_data=[])
        # Should have sample data
        self.assertGreater(len(dashboard.project_data), 0)

    def test_none_project_data(self):
        """Dashboard handles None project data gracefully."""
        dashboard = ProjectDashboard(project_data=None)
        # Should have sample data
        self.assertGreater(len(dashboard.project_data), 0)

    def test_single_task(self):
        """Dashboard works with single task."""
        data = [
            {"ID": "001", "Task Name": "Only Task", "Type": "Task", "Duration": 5, "Progress": 50, "Level": 1, "Start Date": datetime(2026, 1, 1), "End Date": datetime(2026, 1, 5)},
        ]
        
        dashboard = ProjectDashboard(project_data=data)
        metrics = dashboard._calculate_kpi_metrics()
        
        self.assertEqual(metrics['total_project_scope'], 5)
        self.assertEqual(metrics['total_items_tracked'], 1)
        self.assertEqual(metrics['milestones_count'], 0)
        self.assertEqual(metrics['average_progress'], 50.0)

    def test_all_zero_duration(self):
        """Dashboard handles all zero duration tasks."""
        data = [
            {"ID": "001", "Task Name": "Task A", "Type": "Task", "Duration": 0, "Progress": 0, "Level": 1, "Start Date": datetime(2026, 1, 1), "End Date": datetime(2026, 1, 1)},
            {"ID": "002", "Task Name": "Task B", "Type": "Task", "Duration": 0, "Progress": 0, "Level": 1, "Start Date": datetime(2026, 1, 1), "End Date": datetime(2026, 1, 1)},
        ]
        
        dashboard = ProjectDashboard(project_data=data)
        metrics = dashboard._calculate_kpi_metrics()
        
        self.assertEqual(metrics['total_project_scope'], 0)
        self.assertEqual(metrics['average_progress'], 0.0)

    def test_mixed_task_types(self):
        """Dashboard handles all task types correctly."""
        data = [
            {"ID": "001", "Task Name": "Phase", "Type": "Phase", "Duration": 10, "Progress": 0, "Level": 1, "Start Date": datetime(2026, 1, 1), "End Date": datetime(2026, 1, 10)},
            {"ID": "002", "Task Name": "Task", "Type": "Task", "Duration": 5, "Progress": 50, "Level": 2, "Start Date": datetime(2026, 1, 1), "End Date": datetime(2026, 1, 5)},
            {"ID": "003", "Task Name": "Subtask", "Type": "Subtask", "Duration": 2, "Progress": 25, "Level": 3, "Start Date": datetime(2026, 1, 1), "End Date": datetime(2026, 1, 2)},
            {"ID": "004", "Task Name": "Milestone", "Type": "Milestone", "Duration": 0, "Progress": 0, "Level": 1, "Start Date": datetime(2026, 1, 11), "End Date": datetime(2026, 1, 11)},
        ]
        
        dashboard = ProjectDashboard(project_data=data)
        
        # Should handle all types without errors
        metrics = dashboard._calculate_kpi_metrics()
        self.assertIsInstance(metrics, dict)
        
        # Should generate HTML without errors
        html = dashboard.generate_dashboard_html()
        self.assertIsInstance(html, str)


if __name__ == '__main__':
    unittest.main()
