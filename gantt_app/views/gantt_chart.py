"""
Interactive Gantt chart visualization using Plotly for the Gantt Project Management Tool.

Uses Plotly for rendering with interactive features (zoom, pan, hover tooltips).

WHY THIS MODULE EXISTS:
======================
This module provides the visual Gantt chart display for the application.

1. **Interactive Visualization**: 
   - Uses Plotly for interactive charts with zoom, pan, and hover capabilities
   - Provides better user experience with built-in interactivity
   - Supports dynamic updates when project data changes

2. **Reusability**:
   - The core chart drawing logic can be reused for export if needed
"""

import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple, Any

import customtkinter as ctk
import plotly.graph_objects as go

from gantt_app.models import Task, Project


class GanttChart(ctk.CTkFrame):
    """
    Interactive Gantt chart visualization with tasks as bars and milestones as diamonds.
    Shows dependencies as lines between tasks.
    
    This class is responsible for:
    - Creating and displaying the Gantt chart in the GUI
    - Updating the chart when project data changes
    - Handling window resizing
    """
    
    def __init__(self, master, project: Project, 
                 width: int = 12, height: int = 8, dpi: int = 100):
        super().__init__(master)
        
        self.master = master
        self.project = project
        self.width = width
        self.height = height
        self.dpi = dpi
        
        # Colors - these match the theme used in the exporters
        self.task_color = '#1f6aa5'
        self.milestone_color = '#e74c3c'
        self.dependency_color = '#e74c3c'
        self.critical_path_color = '#f39c12'
        
        # Chart settings (can be customized via GanttChartSettingsDialog)
        self.chart_settings = {
            "font_size": 12,
            "bg_color": "#ffffff",
            "text_color": "#000000",
            "grid_color": "#ecf0f1"
        }
        
        # Create figure
        self.figure = go.Figure()
        
        # Try to import tkinterweb for embedding
        self.has_tkinterweb = False
        self.browser = None
        try:
            import tkinterweb
            self.has_tkinterweb = True
        except ImportError:
            print("tkinterweb not available, using fallback display")
        
        # Create a frame to hold the chart
        self.chart_frame = ctk.CTkFrame(self)
        self.chart_frame.pack(fill=tk.BOTH, expand=True)
        
        # Draw initial chart
        self.draw_chart()
        
        # Bind to configure events for resizing
        self.bind('<Configure>', self.on_resize)
    
    def on_resize(self, event):
        """Handle window resize by redrawing the chart."""
        self.draw_chart()
    
    def draw_chart(self):
        """Draw the complete Gantt chart using Plotly."""
        self.figure = go.Figure()
        
        if not self.project.tasks:
            self._draw_empty_chart()
            self._render_chart()
            return
        
        # Sort tasks by start date
        tasks = sorted(self.project.tasks, key=lambda t: t.start_date)
        
        # Calculate chart dimensions
        min_date, max_date, num_tasks = self._calculate_dates(tasks)
        
        # Add tasks as bars
        self._draw_tasks(tasks)
        
        # Add milestones as markers
        milestones = [t for t in tasks if t.is_milestone]
        self._draw_milestones(milestones, tasks)
        
        # Add dependencies as lines
        self._draw_dependencies(tasks)
        
        # Add critical path highlighting
        self._draw_critical_path(tasks)
        
        # Update layout
        self._update_layout(min_date, max_date, tasks)
        
        # Render the chart
        self._render_chart()
    
    def _calculate_dates(self, tasks: List[Task]) -> Tuple[datetime, datetime, int]:
        """Calculate min/max dates and task count for scaling."""
        if not tasks:
            return datetime.now(), datetime.now() + timedelta(days=30), 0
        
        start_dates = [t.start_date for t in tasks]
        end_dates = [t.end_date for t in tasks if t.end_date is not None]
        milestone_dates = [t.start_date for t in tasks if t.is_milestone]
        
        all_dates = start_dates + end_dates + milestone_dates
        
        min_date = min(all_dates) - timedelta(days=1)
        max_date = max(all_dates) + timedelta(days=1)
        
        # Add some padding
        date_range = (max_date - min_date).days
        padding_days = max(7, date_range // 10)
        min_date -= timedelta(days=padding_days)
        max_date += timedelta(days=padding_days)
        
        return min_date, max_date, len(tasks)
    
    def _draw_tasks(self, tasks: List[Task]):
        """Draw regular tasks as horizontal bars."""
        sorted_tasks = sorted(tasks, key=lambda t: t.start_date)
        
        # Get custom settings
        settings = getattr(self, 'chart_settings', {})
        
        for i, task in enumerate(sorted_tasks):
            if task.is_milestone:
                continue  # Skip milestones, they're drawn separately
            
            # Calculate duration
            start_date = task.start_date
            end_date = task.end_date or task.start_date
            
            duration_days = (end_date - start_date).days + 1 if end_date >= start_date else 1
            
            # Create hover text with rich information
            deps = [self.project.get_task_by_id(d).name if self.project.get_task_by_id(d) else d for d in task.dependencies]
            dep_str = ", ".join(deps) if deps else "None"
            
            hover_text = (
                f"<b>{task.name}</b><br>"
                f"Start: {start_date.strftime('%Y-%m-%d')}<br>"
                f"End: {end_date.strftime('%Y-%m-%d')}<br>"
                f"Duration: {duration_days} days<br>"
                f"Progress: {task.progress}%<br>"
                f"Type: {task.task_type}<br>"
                f"Dependencies: {dep_str}"
            )
            
            # Add bar for this task
            self.figure.add_trace(go.Bar(
                x=[start_date],
                y=[i],
                width=[duration_days],
                orientation='h',
                name=task.name,
                marker=dict(color=task.color, line=dict(color='black', width=1)),
                hovertemplate=hover_text + '<extra></extra>',
                showlegend=False,
                opacity=0.8
            ))
    
    def _draw_milestones(self, milestones: List[Task], all_tasks: List[Task]):
        """Draw milestones as diamond markers."""
        sorted_milestones = sorted(milestones, key=lambda t: t.start_date)
        
        # Find position of each milestone in the task list
        x_values = []
        y_values = []
        text_values = []
        color_values = []
        
        for milestone in sorted_milestones:
            try:
                index = all_tasks.index(milestone)
            except ValueError:
                continue
            
            x_values.append(milestone.start_date)
            y_values.append(index)
            text_values.append(milestone.name)
            color_values.append(milestone.color)
        
        # Add milestone markers
        if x_values:
            self.figure.add_trace(go.Scatter(
                x=x_values,
                y=y_values,
                mode='markers+text',
                marker=dict(
                    symbol='diamond',
                    size=22,
                    color=color_values,
                    line=dict(width=2, color='black')
                ),
                text=text_values,
                textposition='middle right',
                textfont=dict(size=11, color='black'),
                hovertemplate='<b>%{text}</b><br>Date: %{x|%Y-%m-%d}<extra></extra>',
                showlegend=False
            ))
    
    def _draw_dependencies(self, tasks: List[Task]):
        """Draw dependency lines between tasks."""
        for task in tasks:
            for dep_id in task.dependencies:
                dep_task = self.project.get_task_by_id(dep_id)
                if not dep_task:
                    continue
                
                # Find positions
                all_tasks = sorted(tasks, key=lambda t: t.start_date)
                
                try:
                    task_index = all_tasks.index(task)
                    dep_index = all_tasks.index(dep_task)
                except ValueError:
                    continue
                
                # Get dates for dependency
                if dep_task.is_milestone:
                    dep_x = dep_task.start_date
                    dep_y = dep_index
                else:
                    dep_x = dep_task.end_date or dep_task.start_date
                    dep_y = dep_index
                
                if task.is_milestone:
                    task_x = task.start_date
                    task_y = task_index
                else:
                    task_x = task.start_date
                    task_y = task_index
                
                # Add dependency line
                self.figure.add_trace(go.Scatter(
                    x=[dep_x, task_x],
                    y=[dep_y, task_y],
                    mode='lines',
                    line=dict(color=self.dependency_color, width=2, dash='dot'),
                    hoverinfo='skip',
                    showlegend=False,
                    opacity=0.7
                ))
    
    def _draw_critical_path(self, tasks: List[Task]):
        """Draw the critical path in a different color."""
        critical_path = self.project.get_critical_path()
        
        if critical_path:
            for task in critical_path:
                if task.is_milestone:
                    # Find position
                    all_tasks = sorted(tasks, key=lambda t: t.start_date)
                    try:
                        index = all_tasks.index(task)
                    except ValueError:
                        continue
                    
                    # Highlight milestone
                    self.figure.add_trace(go.Scatter(
                        x=[task.start_date],
                        y=[index],
                        mode='markers',
                        marker=dict(
                            symbol='diamond',
                            size=26,
                            color=self.critical_path_color,
                            line=dict(width=3, color='black')
                        ),
                        hoverinfo='skip',
                        showlegend=False
                    ))
                else:
                    # Highlight task bar
                    start_date = task.start_date
                    end_date = task.end_date or task.start_date
                    duration_days = (end_date - start_date).days + 1 if end_date >= start_date else 1
                    
                    all_tasks = sorted(tasks, key=lambda t: t.start_date)
                    try:
                        index = all_tasks.index(task)
                    except ValueError:
                        continue
                    
                    self.figure.add_trace(go.Bar(
                        x=[start_date],
                        y=[index],
                        width=[duration_days],
                        orientation='h',
                        marker=dict(color=self.critical_path_color, line=dict(width=2, color='black'), opacity=0.8),
                        hoverinfo='skip',
                        showlegend=False
                    ))
    
    def _update_layout(self, min_date: datetime, max_date: datetime, tasks: List[Task]):
        """Update the chart layout."""
        sorted_tasks = sorted(tasks, key=lambda t: t.start_date)
        task_names = [t.name[:30] + ('...' if len(t.name) > 30 else '') for t in sorted_tasks]
        
        project_name = getattr(self.project, 'name', '') or 'New Project'
        
        # Get custom settings
        settings = getattr(self, 'chart_settings', {})
        font_size = settings.get('font_size', 12)
        bg_color = settings.get('bg_color', '#ffffff')
        text_color = settings.get('text_color', '#000000')
        grid_color = settings.get('grid_color', '#ecf0f1')
        
        # Calculate height based on number of tasks
        height = max(600, len(sorted_tasks) * 40 + 100)
        
        self.figure.update_layout(
            title=dict(
                text=f"Gantt Chart: {project_name}",
                font=dict(size=18, family="Arial, sans-serif", color=text_color)
            ),
            xaxis_title="Date",
            yaxis_title="Tasks",
            yaxis=dict(
                tickmode='array',
                tickvals=list(range(len(sorted_tasks))),
                ticktext=task_names,
                tickfont=dict(size=font_size, family="Arial, sans-serif", color=text_color),
                title=dict(font=dict(size=14, color=text_color)),
                tickangle=0
            ),
            xaxis=dict(
                tickfont=dict(size=font_size, family="Arial, sans-serif", color=text_color),
                title=dict(font=dict(size=14, color=text_color)),
                tickformat='%Y-%m-%d',
                gridcolor=grid_color,
                showgrid=True
            ),
            height=height,
            width=1200,
            showlegend=False,
            plot_bgcolor=bg_color,
            paper_bgcolor=bg_color,
            margin=dict(l=180, r=50, t=80, b=80),
            hovermode='closest',
            # Invert y-axis so earliest task is at top
            yaxis_autorange='reversed',
            font=dict(size=font_size, family="Arial, sans-serif", color=text_color)
        )
        
        # Set date range
        self.figure.update_xaxes(range=[min_date - timedelta(days=1), max_date + timedelta(days=1)])
        self.figure.update_yaxes(gridcolor=grid_color, showgrid=True)
    
    def _draw_empty_chart(self):
        """Draw an empty chart with instructions."""
        self.figure = go.Figure()
        
        self.figure.update_layout(
            title=dict(
                text="No tasks to display",
                font=dict(size=18, color='#7f8c8d')
            ),
            xaxis_title="Date",
            yaxis_title="Tasks",
            height=600,
            width=1200,
            showlegend=False,
            paper_bgcolor='white',
            margin=dict(l=50, r=50, t=80, b=50),
            annotations=[dict(
                text="Add tasks to see the Gantt chart",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=16, color='#7f8c8d', family="Arial, sans-serif")
            )]
        )
    
    def _render_chart(self):
        """Render the Plotly chart in the Tkinter frame."""
        # Clear existing widgets in chart_frame
        for widget in self.chart_frame.winfo_children():
            widget.destroy()
        
        try:
            # Use tkinterweb if available
            if self.has_tkinterweb:
                import tkinterweb
                
                # Create HTML content
                html_content = self.figure.to_html(include_plotlyjs='cdn', full_html=False)
                
                # Create tkinterweb frame
                self.browser = tkinterweb.HtmlFrame(self.chart_frame)
                self.browser.load_html(html_content)
                self.browser.pack(fill=tk.BOTH, expand=True)
                
            else:
                # Fallback: Create a label with instructions
                fallback_label = ctk.CTkLabel(
                    self.chart_frame,
                    text="Plotly chart requires tkinterweb for embedding.\nInstall with: pip install tkinterweb",
                    text_color="gray"
                )
                fallback_label.pack(pady=40)
                
        except Exception as e:
            # Show error
            error_label = ctk.CTkLabel(
                self.chart_frame,
                text=f"Error rendering chart: {e}",
                text_color="red"
            )
            error_label.pack(pady=20)
            print(f"Error rendering Plotly chart: {e}")
            import traceback
            traceback.print_exc()
    
    def update_chart(self):
        """Update the chart with current project data."""
        self.draw_chart()
    
    def set_project(self, project: Project):
        """Set a new project and redraw the chart."""
        self.project = project
        self.update_chart()
    
    def clear_chart(self):
        """Clear the chart."""
        self.figure = go.Figure()
        self._draw_empty_chart()
        self._render_chart()
