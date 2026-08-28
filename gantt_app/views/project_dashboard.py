"""
Project Analytics Dashboard for PySimplePMT

This module provides a standalone dashboard that visualizes project metrics
using Plotly charts embedded in a CustomTkinter window via tkinterweb.

DASHBOARD ELEMENTS:
===================
1. Task Progress Bar Chart
   - Measures completion level per primary task (Outline Level = 1)
   - Formula: Progress % = Progress Value * 100
   - Weighted Project Progress = SUM(Task Duration * Progress) / SUM(Task Duration)

2. Duration Allocation Donut Chart
   - Categorizes total work duration by item Type (Task, Subtask, Milestone)
   - Formula: Type Share % = (SUM(Duration by Type) / SUM(Total Duration)) * 100

3. Item Workload Distribution Bar Chart
   - Displays individual work duration per item ID across the project lifecycle
   - Formula: Item Duration = End Date - Start Date + 1

4. KPI Summary Overview Box
   - Aggregates critical high-level project metrics:
     * Total Project Scope = SUM(Duration of Level 1 Tasks)
     * Milestone Ratio = Count of items where Type == 'Milestone'
     * Overall Completion = Weighted Progress

DEPENDENCIES:
=============
- customtkinter: UI toolkit for the dashboard window
- plotly: Chart rendering engine
- tkinterweb: Embeds Plotly charts in Tkinter

USAGE:
======
This is a standalone module that can be run directly:
    python project_dashboard.py

Or imported and used programmatically:
    from project_dashboard import ProjectDashboard
    dashboard = ProjectDashboard(project)
    dashboard.run()

The dashboard is intentionally separate from the main application and can be
integrated into the menu system later as needed.
"""

import tkinter as tk
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

import customtkinter as ctk
from tkinterweb import HtmlFrame
import plotly.graph_objects as go
from plotly.subplots import make_subplots


class ProjectDashboard:
    """
    A standalone dashboard for visualizing project metrics.
    
    This class creates a CustomTkinter window containing Plotly charts that
    display various project metrics including task progress, duration allocation,
    workload distribution, and KPI summaries.
    
    ATTRIBUTES:
    -----------
    project_data : List[Dict[str, Any]]
        List of dictionaries containing task data with keys:
        - ID: Task identifier
        - Task Name: Name of the task
        - Type: Task type (Task, Subtask, Milestone, Phase)
        - Duration: Duration in days
        - Progress: Progress percentage (0-100)
        - Level: Outline level (1 for primary tasks)
        - Start Date: Start date of the task
        - End Date: End date of the task
    
    METHODS:
    --------
    run()
        Creates and displays the dashboard window.
    generate_dashboard_html()
        Generates the HTML content for the dashboard using Plotly.
    """
    
    def __init__(self, project_data: Optional[List[Dict[str, Any]]] = None):
        """
        Initialize the ProjectDashboard.
        
        PARAMETERS:
        -----------
        project_data : List[Dict[str, Any]], optional
            List of task data dictionaries. If None, uses sample data.
        """
        self.project_data = project_data or self._create_sample_data()
        # Store data as list of dicts, no pandas dependency
    
    def _create_sample_data(self) -> List[Dict[str, Any]]:
        """
        Create sample project data for demonstration.
        
        RETURNS:
        --------
        List[Dict[str, Any]]
            Sample task data matching the screenshot requirements.
        """
        base_date = datetime(2026, 1, 1)
        return [
            {
                "ID": "001",
                "Task Name": "Project Planning",
                "Type": "Task",
                "Duration": 2,
                "Progress": 0,
                "Level": 1,
                "Start Date": base_date,
                "End Date": base_date + timedelta(days=1)
            },
            {
                "ID": "002",
                "Task Name": "Requirements Gathering",
                "Type": "Subtask",
                "Duration": 1,
                "Progress": 0,
                "Level": 2,
                "Start Date": base_date + timedelta(days=2),
                "End Date": base_date + timedelta(days=2)
            },
            {
                "ID": "003",
                "Task Name": "Design Phase",
                "Type": "Task",
                "Duration": 5,
                "Progress": 0,
                "Level": 1,
                "Start Date": base_date + timedelta(days=3),
                "End Date": base_date + timedelta(days=7)
            },
            {
                "ID": "004",
                "Task Name": "UI Mockups",
                "Type": "Subtask",
                "Duration": 3,
                "Progress": 0,
                "Level": 2,
                "Start Date": base_date + timedelta(days=8),
                "End Date": base_date + timedelta(days=10)
            },
            {
                "ID": "005",
                "Task Name": "Implementation",
                "Type": "Task",
                "Duration": 8,
                "Progress": 30,
                "Level": 1,
                "Start Date": base_date + timedelta(days=11),
                "End Date": base_date + timedelta(days=18)
            },
            {
                "ID": "006",
                "Task Name": "Design Review",
                "Type": "Milestone",
                "Duration": 0,
                "Progress": 0,
                "Level": 1,
                "Start Date": base_date + timedelta(days=19),
                "End Date": base_date + timedelta(days=19)
            },
            {
                "ID": "007",
                "Task Name": "Testing",
                "Type": "Task",
                "Duration": 3,
                "Progress": 0,
                "Level": 1,
                "Start Date": base_date + timedelta(days=20),
                "End Date": base_date + timedelta(days=22)
            },
            {
                "ID": "008",
                "Task Name": "Deployment",
                "Type": "Task",
                "Duration": 3,
                "Progress": 0,
                "Level": 1,
                "Start Date": base_date + timedelta(days=23),
                "End Date": base_date + timedelta(days=25)
            },
        ]
    
    def _calculate_weighted_progress(self) -> float:
        """
        Calculate weighted project progress.
        
        Formula: SUM(Task Duration * Progress) / SUM(Task Duration)
        Only considers primary tasks (Level = 1).
        
        RETURNS:
        --------
        float
            Weighted progress as a decimal (0-100).
        """
        main_tasks = [t for t in self.project_data if t['Level'] == 1]
        if not main_tasks:
            return 0.0
        
        total_duration = sum(t['Duration'] for t in main_tasks)
        if total_duration == 0:
            return 0.0
        
        weighted_sum = sum(t['Duration'] * t['Progress'] for t in main_tasks)
        return weighted_sum / total_duration
    
    def _calculate_kpi_metrics(self) -> Dict[str, Any]:
        """
        Calculate all KPI metrics for the project.
        
        RETURNS:
        --------
        Dict[str, Any]
            Dictionary containing:
            - total_project_scope: Total duration of Level 1 tasks
            - total_items_tracked: Total number of items
            - milestones_count: Number of milestone items
            - average_progress: Average progress percentage
            - active_status: Status summary
        """
        main_tasks = [t for t in self.project_data if t['Level'] == 1]
        total_scope = sum(t['Duration'] for t in main_tasks)
        total_items = len(self.project_data)
        milestones_count = len([t for t in self.project_data if t['Type'] == 'Milestone'])
        
        # Active Status calculation
        active_count = len([t for t in self.project_data if t['Progress'] > 0])
        active_percentage = (active_count / total_items * 100) if total_items > 0 else 0
        
        return {
            'total_project_scope': total_scope,
            'total_items_tracked': total_items,
            'milestones_count': milestones_count,
            'average_progress': self._calculate_weighted_progress(),
            'active_status': f"{active_percentage:.0f}% Active (A)" if active_percentage > 0 else "0% Active (A)"
        }
    
    def generate_dashboard_html(self) -> str:
        """
        Generate the HTML content for the dashboard using Plotly.
        
        Creates a 2x2 grid layout with:
        - Top Left: Task Progress Bar Chart (horizontal bars)
        - Top Right: Duration Allocation Donut Chart
        - Bottom Left: Item Workload Distribution Bar Chart
        - Bottom Right: KPI Summary Overview Box
        
        RETURNS:
        --------
        str
            HTML string containing the complete dashboard.
        """
        # Calculate metrics
        kpi_metrics = self._calculate_kpi_metrics()
        
        # Create subplot grid
        fig = make_subplots(
            rows=2, cols=2,
            specs=[
                [{"type": "bar"}, {"type": "domain"}],
                [{"type": "bar"}, {"type": "xy"}]
            ],
            subplot_titles=(
                "Task Progress (%) Breakdown",
                "Duration Allocation by Task Type (Days)",
                "Duration per Item (Days)",
                "Dashboard Summary KPIs"
            ),
            vertical_spacing=0.1,
            horizontal_spacing=0.1
        )
        
        # 1. Task Progress Bar Chart (Top Left)
        # Only show primary tasks (Level = 1)
        main_tasks = [t for t in self.project_data if t['Level'] == 1]
        
        # Sort by ID for consistent ordering
        main_tasks = sorted(main_tasks, key=lambda t: t['ID'])
        
        fig.add_trace(
            go.Bar(
                x=[t['Progress'] for t in main_tasks],
                y=[t['Task Name'] for t in main_tasks],
                orientation='h',
                marker=dict(color='#38bdf8'),
                name="Progress %",
                text=[f"{t['Progress']}%" for t in main_tasks],
                textposition='outside',
                hovertemplate='<b>%{y}</b><br>Progress: %{x:.0f}%<extra></extra>'
            ),
            row=1, col=1
        )
        
        # Update x-axis for progress chart to show percentage
        fig.update_xaxes(
            title_text="Progress (%)",
            range=[0, 100],
            ticksuffix="%",
            row=1, col=1
        )
        
        # Update y-axis for progress chart
        fig.update_yaxes(
            title_text="",
            autorange='reversed',
            row=1, col=1
        )
        
        # 2. Duration Allocation Donut Chart (Top Right)
        # Group by Type and sum Duration
        type_duration = {}
        for t in self.project_data:
            task_type = t['Type']
            if task_type not in type_duration:
                type_duration[task_type] = 0
            type_duration[task_type] += t['Duration']
        
        # Convert to sorted lists for consistent ordering
        types_sorted = sorted(type_duration.keys())
        durations = [type_duration[t] for t in types_sorted]
        
        fig.add_trace(
            go.Pie(
                labels=types_sorted,
                values=durations,
                hole=0.5,
                marker=dict(colors=['#6366f1', '#10b981', '#f59e0b', '#ef4444']),
                name="Duration Share",
                textinfo='label+percent',
                textposition='outside',
                hovertemplate='<b>%{label}</b><br>Duration: %{value} days<br>Share: %{percent}<extra></extra>'
            ),
            row=1, col=2
        )
        
        # 3. Item Workload Distribution Bar Chart (Bottom Left)
        # Sort by ID for consistent ordering
        sorted_tasks = sorted(self.project_data, key=lambda t: t['ID'])
        
        fig.add_trace(
            go.Bar(
                x=[t['Task Name'] for t in sorted_tasks],
                y=[t['Duration'] for t in sorted_tasks],
                marker=dict(color='#818cf8'),
                name="Days",
                text=[f"{t['Duration']}d" for t in sorted_tasks],
                textposition='outside',
                hovertemplate='<b>%{x}</b><br>Duration: %{y} days<extra></extra>'
            ),
            row=2, col=1
        )
        
        # Update axes for workload chart
        fig.update_xaxes(
            title_text="",
            tickangle=-45,
            row=2, col=1
        )
        
        fig.update_yaxes(
            title_text="Duration (Days)",
            row=2, col=1
        )
        
        # 4. KPI Summary Overview Box (Bottom Right)
        # Create a custom annotation for the KPI box
        kpi_text = (
            f"<b>PROJECT METRICS OVERVIEW</b><br><br>"
            f"&bull; Total Project Scope: <b>{kpi_metrics['total_project_scope']} Days</b><br>"
            f"&bull; Total Items Tracked: <b>{kpi_metrics['total_items_tracked']} Items</b><br>"
            f"&bull; Milestones Count: <b>{kpi_metrics['milestones_count']} Milestone</b><br>"
            f"&bull; Average Progress: <b>{kpi_metrics['average_progress']:.2f}%</b><br>"
            f"&bull; Active Status: <b>{kpi_metrics['active_status']}</b>"
        )
        
        # Add invisible scatter trace to reserve space
        fig.add_trace(
            go.Scatter(
                x=[0],
                y=[0],
                mode='markers',
                marker=dict(size=0),
                hoverinfo='skip',
                showlegend=False
            ),
            row=2, col=2
        )
        
        # Add annotation for KPI box
        fig.add_annotation(
            x=0.5,
            y=0.5,
            xref="x2",
            yref="y2",
            text=kpi_text,
            showarrow=False,
            font=dict(size=12, color='#ffffff'),
            bgcolor='#2d3748',
            bordercolor='#4a5568',
            borderwidth=2,
            borderpad=10,
            align="left",
            xanchor="center",
            yanchor="middle"
        )
        
        # Theme and Layout Configurations
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor='#1a1a1a',
            plot_bgcolor='#1a1a1a',
            showlegend=False,
            margin=dict(l=20, r=20, t=40, b=20),
            height=800,
            width=1200
        )
        
        # Adjust subplot margins
        fig.update_annotations(
            font=dict(size=14, color='#ffffff'),
            selector=dict(text="Task Progress")
        )
        
        # Export Plotly figure to HTML string
        return fig.to_html(include_plotlyjs='cdn', full_html=True)
    
    def run(self):
        """
        Create and display the dashboard window.
        
        This method initializes the CustomTkinter application, sets up the
        theme, and embeds the Plotly dashboard in a tkinterweb HtmlFrame.
        """
        # Create the main application window
        app = ctk.CTk()
        
        # Set CustomTkinter theme to match dark Plotly theme
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")
        
        # Configure window
        app.title("Project Analytics Dashboard")
        app.geometry("1200x900")
        
        # Title Label
        title_label = ctk.CTkLabel(
            app,
            text="Project Metrics & Analytics Dashboard",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title_label.pack(pady=10)
        
        # Subtitle Label
        subtitle_label = ctk.CTkLabel(
            app,
            text="Interactive visualization of project progress, duration allocation, and workload distribution",
            font=ctk.CTkFont(size=12, weight="normal"),
            text_color="#888888"
        )
        subtitle_label.pack(pady=5)
        
        # Create HTML frame for embedding Plotly charts
        html_frame = HtmlFrame(app)
        html_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Generate and load dashboard HTML
        raw_html = self.generate_dashboard_html()
        html_frame.load_html(raw_html)
        
        # Handle window resize
        def on_resize(event):
            """Regenerate HTML on window resize for responsive charts."""
            # Regenerate HTML with updated dimensions
            new_width = max(event.width, 800)
            new_height = max(event.height - 100, 600)
            
            fig = self._create_figure_only(new_width, new_height)
            html_content = fig.to_html(include_plotlyjs='cdn', full_html=True)
            html_frame.load_html(html_content)
        
        app.bind('<Configure>', on_resize)
        
        # Run the application
        app.mainloop()
    
    def _create_figure_only(self, width: int = 1200, height: int = 800) -> go.Figure:
        """
        Create only the Plotly figure without HTML generation.
        
        This is used for responsive resizing.
        
        PARAMETERS:
        -----------
        width : int
            Figure width in pixels.
        height : int
            Figure height in pixels.
        
        RETURNS:
        --------
        go.Figure
            The Plotly figure object.
        """
        # Calculate metrics
        kpi_metrics = self._calculate_kpi_metrics()
        
        # Create subplot grid
        fig = make_subplots(
            rows=2, cols=2,
            specs=[
                [{"type": "bar"}, {"type": "domain"}],
                [{"type": "bar"}, {"type": "xy"}]
            ],
            subplot_titles=(
                "Task Progress (%) Breakdown",
                "Duration Allocation by Task Type (Days)",
                "Duration per Item (Days)",
                "Dashboard Summary KPIs"
            ),
            vertical_spacing=0.1,
            horizontal_spacing=0.1
        )
        
        # 1. Task Progress Bar Chart
        main_tasks = sorted([t for t in self.project_data if t['Level'] == 1], key=lambda t: t['ID'])
        fig.add_trace(
            go.Bar(
                x=[t['Progress'] for t in main_tasks],
                y=[t['Task Name'] for t in main_tasks],
                orientation='h',
                marker=dict(color='#38bdf8'),
                name="Progress %",
                text=[f"{t['Progress']}%" for t in main_tasks],
                textposition='outside',
                hovertemplate='<b>%{y}</b><br>Progress: %{x:.0f}%<extra></extra>'
            ),
            row=1, col=1
        )
        
        fig.update_xaxes(
            title_text="Progress (%)",
            range=[0, 100],
            ticksuffix="%",
            row=1, col=1
        )
        
        fig.update_yaxes(
            title_text="",
            autorange='reversed',
            row=1, col=1
        )
        
        # 2. Duration Allocation Donut Chart
        type_duration = {}
        for t in self.project_data:
            task_type = t['Type']
            if task_type not in type_duration:
                type_duration[task_type] = 0
            type_duration[task_type] += t['Duration']
        
        types_sorted = sorted(type_duration.keys())
        durations = [type_duration[t] for t in types_sorted]
        
        fig.add_trace(
            go.Pie(
                labels=types_sorted,
                values=durations,
                hole=0.5,
                marker=dict(colors=['#6366f1', '#10b981', '#f59e0b', '#ef4444']),
                name="Duration Share",
                textinfo='label+percent',
                textposition='outside',
                hovertemplate='<b>%{label}</b><br>Duration: %{value} days<br>Share: %{percent}<extra></extra>'
            ),
            row=1, col=2
        )
        
        # 3. Item Workload Distribution Bar Chart
        sorted_tasks = sorted(self.project_data, key=lambda t: t['ID'])
        fig.add_trace(
            go.Bar(
                x=[t['Task Name'] for t in sorted_tasks],
                y=[t['Duration'] for t in sorted_tasks],
                marker=dict(color='#818cf8'),
                name="Days",
                text=[f"{t['Duration']}d" for t in sorted_tasks],
                textposition='outside',
                hovertemplate='<b>%{x}</b><br>Duration: %{y} days<extra></extra>'
            ),
            row=2, col=1
        )
        
        fig.update_xaxes(
            title_text="",
            tickangle=-45,
            row=2, col=1
        )
        
        fig.update_yaxes(
            title_text="Duration (Days)",
            row=2, col=1
        )
        
        # 4. KPI Summary Overview Box
        kpi_text = (
            f"<b>PROJECT METRICS OVERVIEW</b><br><br>"
            f"&bull; Total Project Scope: <b>{kpi_metrics['total_project_scope']} Days</b><br>"
            f"&bull; Total Items Tracked: <b>{kpi_metrics['total_items_tracked']} Items</b><br>"
            f"&bull; Milestones Count: <b>{kpi_metrics['milestones_count']} Milestone</b><br>"
            f"&bull; Average Progress: <b>{kpi_metrics['average_progress']:.2f}%</b><br>"
            f"&bull; Active Status: <b>{kpi_metrics['active_status']}</b>"
        )
        
        fig.add_trace(
            go.Scatter(
                x=[0],
                y=[0],
                mode='markers',
                marker=dict(size=0),
                hoverinfo='skip',
                showlegend=False
            ),
            row=2, col=2
        )
        
        fig.add_annotation(
            x=0.5,
            y=0.5,
            xref="x2",
            yref="y2",
            text=kpi_text,
            showarrow=False,
            font=dict(size=12, color='#ffffff'),
            bgcolor='#2d3748',
            bordercolor='#4a5568',
            borderwidth=2,
            borderpad=10,
            align="left",
            xanchor="center",
            yanchor="middle"
        )
        
        # Theme and Layout
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor='#1a1a1a',
            plot_bgcolor='#1a1a1a',
            showlegend=False,
            margin=dict(l=20, r=20, t=40, b=20),
            height=height,
            width=width
        )
        
        return fig


def create_sample_dashboard():
    """
    Create and run a dashboard with sample data.
    
    This is a convenience function for testing and demonstration.
    """
    dashboard = ProjectDashboard()
    dashboard.run()


if __name__ == "__main__":
    create_sample_dashboard()
