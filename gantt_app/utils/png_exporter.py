"""
PNG Exporter for the Gantt Project Management Tool.

This module provides functionality to export Gantt charts to PNG image format.

WHY THIS MODULE EXISTS:
======================
The PNG export functionality was originally embedded directly in the GanttChart class
in gantt_chart.py. However, this made the code less modular and harder to maintain.
By separating PNG export into its own module, we achieve:

1. **Separation of Concerns**: The GanttChart class focuses on visualization, 
   while this module focuses solely on PNG export functionality.

2. **Reusability**: The PNG export logic can be reused independently of the 
   GanttChart class, making it easier to test and maintain.

3. **Easier Testing**: Export functionality can be tested in isolation without 
   needing to instantiate the full GanttChart GUI component.

4. **Consistent Pattern**: Following the same pattern as pdf_exporter.py 
   creates a consistent architecture for all export formats.

5. **Configurable Quality**: PNG export supports configurable DPI (dots per inch)
   which is important for different use cases (screen display vs. printing).

DESIGN DECISIONS:
================
- Uses matplotlib's built-in PNG export capability via Figure.savefig()
- Creates a new Figure for export to avoid interfering with the displayed chart
- Uses bbox_inches='tight' to prevent cropping of chart elements
- Automatically creates parent directories if they don't exist
- Returns boolean success/failure for easy error handling
- Supports configurable DPI for quality control

RELATIONSHIP WITH pdf_exporter.py:
===================================
This module shares significant code with pdf_exporter.py, specifically the
_draw_gantt_chart_on_axes() function and all its helper functions. This is
intentional to ensure consistency between export formats. The code duplication
is acceptable because:

1. The drawing logic is the same regardless of export format
2. Each exporter is self-contained and can be used independently
3. The alternative (importing from pdf_exporter) would create circular dependencies
4. Future refactoring could extract the drawing logic to a separate module

USAGE:
======
from gantt_app.utils.png_exporter import export_gantt_to_png

# Export a project's Gantt chart to PNG
success = export_gantt_to_png(
    project, 
    filepath, 
    width=10, 
    height=6, 
    dpi=300  # High DPI for print quality
)
if success:
    print("Export successful!")
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use("Agg")  # Use non-interactive backend for export
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.patches import Polygon, Rectangle, Arrow
from matplotlib.backends.backend_agg import FigureCanvasAgg

from gantt_app.models import Project, Task


def _draw_gantt_chart_on_axes(ax, project: Project):
    """
    Draw a Gantt chart on the given matplotlib axes.
    
    This is the core rendering logic for Gantt charts, shared with pdf_exporter.py
    to ensure consistency between export formats.
    
    PARAMETERS:
    -----------
    ax : matplotlib.axes.Axes
        The axes object to draw the chart on
    project : Project
        The project data containing tasks and milestones
        
    DEVELOPMENT NOTES:
    ------------------
    This function is duplicated from pdf_exporter.py to avoid circular imports.
    The logic is identical to ensure that PNG and PDF exports produce the same
    visual output (aside from format-specific differences).
    
    See pdf_exporter.py for detailed comments on each helper function.
    """
    ax.clear()
    
    # Colors - matching the main GanttChart colors
    task_color = '#1f6aa5'
    milestone_color = '#e74c3c'
    dependency_color = '#e74c3c'
    critical_path_color = '#f39c12'
    grid_color = '#ecf0f1'
    
    if not project.tasks:
        _draw_empty_chart_on_axes(ax, grid_color)
        return
    
    # Sort tasks by start date
    tasks = sorted(project.tasks, key=lambda t: t.start_date)
    
    # Calculate chart dimensions and scaling
    min_date, max_date, num_tasks = _calculate_dates(tasks)
    
    # Set up axes
    _setup_axes_on_axes(ax, min_date, max_date, num_tasks, grid_color)
    
    # Draw tasks
    _draw_tasks_on_axes(ax, tasks, task_color, grid_color)
    
    # Draw milestones
    milestones = [t for t in tasks if t.is_milestone]
    _draw_milestones_on_axes(ax, milestones, tasks, milestone_color)
    
    # Draw dependencies
    _draw_dependencies_on_axes(ax, tasks, project, dependency_color)
    
    # Draw critical path
    _draw_critical_path_on_axes(ax, tasks, project, critical_path_color)
    
    # Add labels and title
    _add_labels_to_axes(ax, project)


def _calculate_dates(tasks: list) -> tuple:
    """Calculate min/max dates and task count for scaling."""
    if not tasks:
        today = datetime.now()
        return today, today + timedelta(days=30), 0
    
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


def _setup_axes_on_axes(ax, min_date: datetime, max_date: datetime, 
                       num_tasks: int, grid_color: str):
    """Set up axes with proper scaling and formatting."""
    # Set date formatter
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    
    # Set date limits
    ax.set_xlim(min_date, max_date)
    
    # Set y-axis limits and labels
    ax.set_ylim(-1, num_tasks)
    ax.set_yticks(range(num_tasks))
    
    # Rotate date labels for better readability
    plt.setp(ax.get_xticklabels(), rotation=45, ha='right')
    
    # Grid
    ax.grid(True, which='both', linestyle='-', linewidth=0.5, color=grid_color)
    ax.set_axisbelow(True)
    
    # Remove spines for cleaner look
    for spine in ax.spines.values():
        spine.set_visible(False)


def _draw_empty_chart_on_axes(ax, grid_color: str):
    """Draw an empty chart with instructions."""
    ax.clear()
    today = datetime.now()
    ax.set_xlim(today, today + timedelta(days=30))
    ax.set_ylim(0, 1)
    
    ax.text(0.5, 0.5, "No tasks to display\nAdd tasks to see the Gantt chart",
             ha='center', va='center', transform=ax.transAxes,
             fontsize=14, color='#7f8c8d')
    
    # Remove spines
    for spine in ax.spines.values():
        spine.set_visible(False)


def _draw_tasks_on_axes(ax, tasks: list, default_color: str, grid_color: str):
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
        ax.add_patch(patch)
    
    # Add labels
    for x, y, text in task_labels:
        ax.text(x, y, text, va='center', ha='left', fontsize=8, 
                     bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', pad=1))
    
    for x, y, text in progress_labels:
        ax.text(x, y, text, va='center', ha='center', fontsize=8, 
                     color='white', fontweight='bold')


def _draw_milestones_on_axes(ax, milestones: list, all_tasks: list, 
                             milestone_color: str):
    """Draw milestones as diamonds."""
    sorted_milestones = sorted(milestones, key=lambda t: t.start_date)
    
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
        
        ax.add_patch(diamond)
        
        # Add milestone name label
        label_x = x + timedelta(days=2)
        ax.text(label_x, y, milestone.name, va='center', ha='left', 
                     fontsize=8, bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', pad=1))
        
        # Add milestone marker (diamond symbol)
        ax.text(x, y, '\u2666', va='center', ha='center', fontsize=12, color='white')


def _draw_dependencies_on_axes(ax, tasks: list, project: Project, 
                              dependency_color: str):
    """Draw dependency arrows between tasks."""
    for task in tasks:
        for dep_id in task.dependencies:
            dep_task = project.get_task_by_id(dep_id)
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
            _draw_arrow_on_axes(ax, dep_x, dep_y, task_x, task_y, dependency_color)


def _draw_arrow_on_axes(ax, x1: datetime, y1: float, x2: datetime, y2: float,
                        color: str):
    """Draw an arrow from (x1, y1) to (x2, y2)."""
    # Convert dates to numeric values for matplotlib
    x1_num = mdates.date2num(x1)
    x2_num = mdates.date2num(x2)
    
    # Adjust y positions for better visibility
    y1_adj = y1 + 0.3
    y2_adj = y2 - 0.3
    
    # Draw arrow line
    arrow = Arrow(x1_num, y1_adj, x2_num - x1_num, y2_adj - y1_adj,
                  width=0.1, facecolor=color, edgecolor=color,
                  linestyle='-', alpha=0.8)
    ax.add_patch(arrow)
    
    # Add arrowhead for better visual cue
    # Calculate arrowhead position (at the end of the arrow)
    arrowhead_x = x2_num - 0.1
    arrowhead_y = y2_adj - 0.1 * ((y2_adj - y1_adj) / max(abs(y2_adj - y1_adj), 1))
    
    arrowhead = Arrow(arrowhead_x, arrowhead_y,
                      (x2_num - x1_num) * 0.1, (y2_adj - y1_adj) * 0.1,
                      width=0.3, facecolor=color, edgecolor=color)
    ax.add_patch(arrowhead)


def _draw_critical_path_on_axes(ax, tasks: list, project: Project,
                               critical_path_color: str):
    """Draw the critical path in a different color."""
    critical_path = project.get_critical_path()
    
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
                ], facecolor=critical_path_color, edgecolor='black', linewidth=2)
                ax.add_patch(diamond)
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
                    facecolor=critical_path_color,
                    edgecolor='black',
                    linewidth=2,
                    alpha=0.8
                )
                ax.add_patch(rect)


def _add_labels_to_axes(ax, project: Project):
    """Add labels and title to the chart."""
    if hasattr(project, 'name') and project.name:
        ax.set_title(f"Gantt Chart: {project.name}", 
                         fontdict={'fontsize': 14, 'fontweight': 'bold'}, pad=20)
    else:
        ax.set_title("Gantt Chart", fontdict={'fontsize': 14, 'fontweight': 'bold'}, pad=20)
    
    ax.set_ylabel("Tasks", fontdict={'fontsize': 10})
    
    # Set task names on y-axis
    sorted_tasks = sorted(project.tasks, key=lambda t: t.start_date)
    task_names = [t.name[:20] + ('...' if len(t.name) > 20 else '') for t in sorted_tasks]
    ax.set_yticklabels(task_names)


def export_gantt_to_png(project: Project, filepath: str, 
                       width: float = 10, height: float = 6, 
                       dpi: int = 300) -> bool:
    """
    Export a project's Gantt chart to PNG format.
    
    This is the main public function for PNG export. It creates a complete
    Gantt chart visualization and saves it to a PNG file.
    
    PARAMETERS:
    -----------
    project : Project
        The project to visualize and export
    filepath : str
        Path where the PNG file should be saved
    width : float, optional
        Width of the output figure in inches (default: 10)
    height : float, optional
        Height of the output figure in inches (default: 6)
    dpi : int, optional
        Dots per inch for the output (default: 300 for high quality)
        
    RETURNS:
    --------
    bool
        True if export was successful, False otherwise
        
    EXAMPLE:
    --------
    >>> from gantt_app.models import Project, Task
    >>> from gantt_app.utils.png_exporter import export_gantt_to_png
    >>> from datetime import datetime, timedelta
    >>> 
    >>> project = Project(name="My Project")
    >>> start = datetime(2024, 1, 1)
    >>> project.add_task(Task.create_task("Task 1", start, start + timedelta(days=5)))
    >>> export_gantt_to_png(project, "/path/to/output.png", dpi=600)
    True
        
    DEVELOPMENT NOTES:
    ------------------
    This function is nearly identical to export_gantt_to_pdf() in pdf_exporter.py.
    The main differences are:
    
    1. Default DPI is 300 (higher than PDF's 100) for better image quality
    2. Uses format='png' in savefig() call
    3. Same figure creation and drawing logic
    
    The higher default DPI for PNG is intentional because:
    - PNG is a raster format, so higher DPI means better quality
    - Users often want high-quality images for presentations or documents
    - Modern displays have high pixel density, so 300 DPI provides good quality
    
    The function automatically creates parent directories if they don't exist,
    making it more user-friendly.
    """
    try:
        # Create parent directories if they don't exist
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        # Create figure with non-interactive backend
        # We set the figure size and DPI based on parameters
        fig = Figure(figsize=(width, height), dpi=dpi)
        
        # Create axes
        ax = fig.add_subplot(111)
        
        # Draw the Gantt chart
        _draw_gantt_chart_on_axes(ax, project)
        
        # Save to PNG
        # bbox_inches='tight' prevents cropping of chart elements
        fig.savefig(filepath, dpi=dpi, bbox_inches='tight', format='png')
        
        # Clean up
        # Note: We don't need to explicitly close the canvas or clear the figure
        # as they will be garbage collected. The savefig() call handles cleanup.
        plt.close(fig)
        
        return True
        
    except Exception as e:
        print(f"Error exporting to PNG: {e}")
        import traceback
        traceback.print_exc()
        return False
