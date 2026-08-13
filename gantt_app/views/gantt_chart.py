"""
Static Gantt chart visualization for the Gantt Project Management Tool.

Uses Matplotlib for rendering and FigureCanvasTkAgg for embedding in Tkinter.

WHY THIS MODULE EXISTS:
======================
This module provides the visual Gantt chart display for the application.
It was designed with the following principles:

1. **Separation of Visualization and Export**: 
   - This module focuses solely on displaying the Gantt chart in the GUI
   - Export functionality (PNG, PDF, Mermaid) has been moved to separate
     modules in the utils/ directory
   - This makes the code more modular and easier to maintain

2. **Reusability of Drawing Logic**:
   - The core chart drawing logic is defined here
   - Export modules have their own copies of the drawing functions to ensure
     they work independently without the GUI

3. **Matplotlib Integration**:
   - Uses matplotlib's date handling capabilities for proper date formatting
   - Creates interactive charts that can be embedded in Tkinter
   - Supports dynamic updates when project data changes

RELATIONSHIP WITH EXPORT MODULES:
=================================
The export functionality has been separated into:
- gantt_app/utils/png_exporter.py - PNG export
- gantt_app/utils/pdf_exporter.py - PDF export  
- gantt_app/utils/mermaid_exporter.py - Mermaid format export

This separation allows:
- Each export format to be developed and tested independently
- The GUI visualization to be optimized without affecting export
- Users to use export functionality without the GUI
"""

import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple, Any
import math

import customtkinter as ctk
import matplotlib
matplotlib.use("TkAgg")  # Use Tkinter backend for GUI display
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.patches import Polygon, Rectangle, Arrow
import numpy as np

from gantt_app.models import Task, Project


class GanttChart(ctk.CTkFrame):
    """
    Static Gantt chart visualization with tasks as bars and milestones as diamonds.
    Shows dependencies as red arrows between tasks.
    
    This class is responsible for:
    - Creating and displaying the Gantt chart in the GUI
    - Updating the chart when project data changes
    - Handling window resizing
    """
    
    def __init__(self, master, project: Project, 
                 width: int = 8, height: int = 6, dpi: int = 100):
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
        self.grid_color = '#ecf0f1'
        
        # Create figure for display
        self.figure = Figure(figsize=(width, height), dpi=dpi)
        self.ax = self.figure.add_subplot(111)
        
        # Create canvas for Tkinter
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.canvas.draw()
        
        # Layout
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Draw initial chart
        self.draw_chart()
        
        # Bind to configure events for resizing
        self.bind('<Configure>', self.on_resize)
    
    def on_resize(self, event):
        """Handle window resize by redrawing the chart."""
        self.draw_chart()
        self.canvas.draw()
    
    def draw_chart(self):
        """Draw the complete Gantt chart."""
        self.ax.clear()
        
        if not self.project.tasks:
            self._draw_empty_chart()
            return
        
        # Sort tasks by start date
        tasks = sorted(self.project.tasks, key=lambda t: t.start_date)
        
        # Calculate chart dimensions and scaling
        min_date, max_date, num_tasks = self._calculate_dates(tasks)
        
        # Set up axes
        self._setup_axes(min_date, max_date, num_tasks)
        
        # Draw tasks
        self._draw_tasks(tasks)
        
        # Draw milestones
        milestones = [t for t in tasks if t.is_milestone]
        self._draw_milestones(milestones)
        
        # Draw dependencies
        self._draw_dependencies(tasks)
        
        # Draw critical path (optional)
        self._draw_critical_path(tasks)
        
        # Add labels and title
        self._add_labels()
        
        # Redraw canvas
        self.canvas.draw()
    
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
    
    def _setup_axes(self, min_date: datetime, max_date: datetime, num_tasks: int):
        """Set up axes with proper scaling and formatting."""
        # Set date formatter
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        self.ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        
        # Set date limits
        self.ax.set_xlim(min_date, max_date)
        
        # Set y-axis limits and labels
        self.ax.set_ylim(-1, num_tasks)
        self.ax.set_yticks(range(num_tasks))
        
        # Rotate date labels for better readability
        plt.setp(self.ax.get_xticklabels(), rotation=45, ha='right')
        
        # Grid
        self.ax.grid(True, which='both', linestyle='-', linewidth=0.5, color=self.grid_color)
        self.ax.set_axisbelow(True)
        
        # Remove spines for cleaner look
        for spine in self.ax.spines.values():
            spine.set_visible(False)
    
    def _draw_tasks(self, tasks: List[Task]):
        """Draw regular tasks as horizontal bars."""
        sorted_tasks = sorted(tasks, key=lambda t: t.start_date)
        
        patches = []
        task_labels = []
        progress_labels = []
        
        for i, task in enumerate(sorted_tasks):
            if task.is_milestone:
                continue  # Skip milestones, they're drawn separately
            
            # Calculate bar position and dimensions
            start_date = task.start_date
            end_date = task.end_date or task.start_date
            
            y_pos = i
            height = 0.6
            
            # Convert dates to numeric values for matplotlib
            start_x_num = mdates.date2num(start_date)
            end_x_num = mdates.date2num(end_date)
            width_days = end_x_num - start_x_num if end_x_num > start_x_num else 1
            
            rect = Rectangle(
                (start_x_num, y_pos - height/2),
                width_days,
                height,
                facecolor=task.color,
                edgecolor='black',
                linewidth=1
            )
            patches.append(rect)
            
            # Add task name label
            label_x = start_date + timedelta(days=2)
            task_labels.append((label_x, y_pos, task.name))
            
            # Add progress label if > 0
            if task.progress > 0:
                progress_text = f"{task.progress}%"
                progress_seconds = (end_date - start_date).total_seconds() * (task.progress / 100)
                progress_x = start_date + timedelta(seconds=progress_seconds)
                progress_labels.append((progress_x, y_pos, progress_text))
        
        # Add patches to axes
        for patch in patches:
            self.ax.add_patch(patch)
        
        # Add labels
        for x, y, text in task_labels:
            self.ax.text(x, y, text, va='center', ha='left', fontsize=8, 
                         bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', pad=1))
        
        for x, y, text in progress_labels:
            self.ax.text(x, y, text, va='center', ha='center', fontsize=8, 
                         color='white', fontweight='bold')
    
    def _draw_milestones(self, milestones: List[Task]):
        """Draw milestones as diamonds."""
        sorted_milestones = sorted(milestones, key=lambda t: t.start_date)
        
        # Find position of each milestone in the task list
        all_tasks = sorted(self.project.tasks, key=lambda t: t.start_date)
        
        for milestone in sorted_milestones:
            try:
                # Find index in task list
                index = all_tasks.index(milestone)
            except ValueError:
                continue
            
            x = milestone.start_date
            y = index
            x_num = mdates.date2num(x)
            
            # Create diamond shape
            diamond = Polygon([
                (x_num, y - 0.3),    # Top
                (x_num + 0.3, y),   # Right
                (x_num, y + 0.3),    # Bottom
                (x_num - 0.3, y)    # Left
            ], facecolor=milestone.color, edgecolor='black', linewidth=1)
            
            self.ax.add_patch(diamond)
            
            # Add milestone name label
            label_x = x + timedelta(days=2)
            self.ax.text(label_x, y, milestone.name, va='center', ha='left', 
                         fontsize=8, bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', pad=1))
            
            # Add milestone marker (diamond symbol)
            self.ax.text(x, y, '\u2666', va='center', ha='center', fontsize=12, color='white')
    
    def _draw_dependencies(self, tasks: List[Task]):
        """Draw dependency arrows between tasks."""
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
                
                # Start and end dates for dependency
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
                
                # Draw arrow from dependency to task
                self._draw_arrow(dep_x, dep_y, task_x, task_y)
    
    def _draw_arrow(self, x1: datetime, y1: float, x2: datetime, y2: float):
        """Draw an arrow from (x1, y1) to (x2, y2)."""
        # Convert dates to numeric values for matplotlib
        x1_num = mdates.date2num(x1)
        x2_num = mdates.date2num(x2)
        
        # Adjust y positions for better visibility
        y1_adj = y1 + 0.3
        y2_adj = y2 - 0.3
        
        # Draw arrow line
        arrow = Arrow(x1_num, y1_adj, x2_num - x1_num, y2_adj - y1_adj,
                      width=0.1, facecolor=self.dependency_color, edgecolor=self.dependency_color,
                      linestyle='-', alpha=0.8)
        self.ax.add_patch(arrow)
        
        # Add arrowhead for better visual cue
        arrowhead_x = x2_num - 0.1
        arrowhead_y = y2_adj - 0.1 * ((y2_adj - y1_adj) / max(abs(y2_adj - y1_adj), 1))
        
        arrowhead = Arrow(arrowhead_x, arrowhead_y,
                        (x2_num - x1_num) * 0.1, (y2_adj - y1_adj) * 0.1,
                        width=0.3, facecolor=self.dependency_color, edgecolor=self.dependency_color)
        self.ax.add_patch(arrowhead)
    
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
                    x = task.start_date
                    y = index
                    x_num = mdates.date2num(x)
                    diamond = Polygon([
                        (x_num, y - 0.3),
                        (x_num + 0.3, y),
                        (x_num, y + 0.3),
                        (x_num - 0.3, y)
                    ], facecolor=self.critical_path_color, edgecolor='black', linewidth=2)
                    self.ax.add_patch(diamond)
                else:
                    # Highlight task bar
                    start_date = task.start_date
                    end_date = task.end_date or task.start_date
                    
                    all_tasks = sorted(tasks, key=lambda t: t.start_date)
                    try:
                        index = all_tasks.index(task)
                    except ValueError:
                        continue
                    
                    y_pos = index
                    height = 0.6
                    
                    # Convert dates to numeric values
                    start_x_num = mdates.date2num(start_date)
                    end_x_num = mdates.date2num(end_date)
                    width_days = end_x_num - start_x_num if end_x_num > start_x_num else 1
                    
                    rect = Rectangle(
                        (start_x_num, y_pos - height/2),
                        width_days,
                        height,
                        facecolor=self.critical_path_color,
                        edgecolor='black',
                        linewidth=2,
                        alpha=0.8
                    )
                    self.ax.add_patch(rect)
    
    def _draw_empty_chart(self):
        """Draw an empty chart with instructions."""
        self.ax.clear()
        self.ax.set_xlim(datetime.now(), datetime.now() + timedelta(days=30))
        self.ax.set_ylim(0, 1)
        
        self.ax.text(0.5, 0.5, "No tasks to display\nAdd tasks to see the Gantt chart",
                     ha='center', va='center', transform=self.ax.transAxes,
                     fontsize=14, color='#7f8c8d')
        
        # Remove spines
        for spine in self.ax.spines.values():
            spine.set_visible(False)
    
    def _add_labels(self):
        """Add labels and title to the chart."""
        if hasattr(self.project, 'name') and self.project.name:
            self.ax.set_title(f"Gantt Chart: {self.project.name}", 
                             fontdict={'fontsize': 14, 'fontweight': 'bold'}, pad=20)
        else:
            self.ax.set_title("Gantt Chart", fontdict={'fontsize': 14, 'fontweight': 'bold'}, pad=20)
        
        self.ax.set_ylabel("Tasks", fontdict={'fontsize': 10})
        
        # Set task names on y-axis
        sorted_tasks = sorted(self.project.tasks, key=lambda t: t.start_date)
        task_names = [t.name[:20] + ('...' if len(t.name) > 20 else '') for t in sorted_tasks]
        self.ax.set_yticklabels(task_names)
    
    def update_chart(self):
        """Update the chart with current project data."""
        self.draw_chart()
    
    def set_project(self, project: Project):
        """Set a new project and redraw the chart."""
        self.project = project
        self.update_chart()
    
    def clear_chart(self):
        """Clear the chart."""
        self.ax.clear()
        self._draw_empty_chart()
        self.canvas.draw()
    
    # Convenience methods for export (delegates to the new exporter modules)
    def export_to_png(self, filepath: str, dpi: int = 300) -> bool:
        """
        Export the Gantt chart to PNG file.
        
        This is a convenience method that delegates to the png_exporter module.
        
        Args:
            filepath: Path to save the PNG file
            dpi: Dots per inch for the output image
            
        Returns:
            True if successful, False otherwise
        """
        from gantt_app.utils.png_exporter import export_gantt_to_png
        return export_gantt_to_png(self.project, filepath, 
                                  width=self.width, height=self.height, dpi=dpi)
    
    def export_to_pdf(self, filepath: str) -> bool:
        """
        Export the Gantt chart to PDF file.
        
        This is a convenience method that delegates to the pdf_exporter module.
        
        Args:
            filepath: Path to save the PDF file
            
        Returns:
            True if successful, False otherwise
        """
        from gantt_app.utils.pdf_exporter import export_gantt_to_pdf
        return export_gantt_to_pdf(self.project, filepath,
                                  width=self.width, height=self.height, dpi=self.dpi)
