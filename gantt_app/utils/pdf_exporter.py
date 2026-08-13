"""
PDF Exporter for the Gantt Project Management Tool.

This module provides functionality to export Gantt charts to PDF format.

WHY THIS MODULE EXISTS:
======================
The PDF export functionality was originally embedded directly in the GanttChart class
in gantt_chart.py. However, this made the code less modular and harder to maintain.
By separating PDF export into its own module, we achieve:

1. **Separation of Concerns**: The GanttChart class focuses on visualization, 
   while this module focuses solely on PDF export functionality.

2. **Reusability**: The PDF export logic can be reused independently of the 
   GanttChart class, making it easier to test and maintain.

3. **Easier Testing**: Export functionality can be tested in isolation without 
   needing to instantiate the full GanttChart GUI component.

4. **Future Extensions**: New export formats can be added as separate modules 
   following the same pattern without modifying existing code.

5. **Dependency Management**: All PDF-specific dependencies and logic are 
   contained in one place, making it easier to understand and modify.

DESIGN DECISIONS:
================
- Uses matplotlib's built-in PDF export capability via Figure.savefig()
- Creates a new Figure for export to avoid interfering with the displayed chart
- Uses bbox_inches='tight' to prevent cropping of chart elements
- Automatically creates parent directories if they don't exist
- Returns boolean success/failure for easy error handling

USAGE:
======
from gantt_app.utils.pdf_exporter import export_gantt_to_pdf

# Export a project's Gantt chart to PDF
success = export_gantt_to_pdf(project, filepath, width=10, height=6, dpi=100)
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
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


def _draw_gantt_chart_on_axes(ax, project: Project):
    """
    Draw a Gantt chart on the given matplotlib axes.
    
    This is the core rendering logic for Gantt charts, extracted from GanttChart
    class to be reusable across different export formats.
    
    PARAMETERS:
    -----------
    ax : matplotlib.axes.Axes
        The axes object to draw the chart on
    project : Project
        The project data containing tasks and milestones
        
    DEVELOPMENT NOTES:
    ------------------
    This function was extracted from the GanttChart class to avoid code duplication
    between the GUI visualization and export functionality. The logic is identical
    to what's used in the main GanttChart._draw_chart_on_axes() method but adapted
    to work without the full GanttChart class context.
    
    The function handles:
    - Empty project state (shows helpful message)
    - Task rendering as horizontal bars
    - Milestone rendering as diamonds
    - Dependency arrows between tasks
    - Critical path highlighting
    - Proper date formatting and axis setup
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
    """
    Calculate min/max dates and task count for scaling.
    
    PARAMETERS:
    -----------
    tasks : list of Task
        List of tasks to calculate dates from
        
    RETURNS:
    --------
    tuple : (min_date, max_date, num_tasks)
        Minimum date, maximum date, and number of tasks
        
    DEVELOPMENT NOTES:
    ------------------
    This adds padding around the date range to ensure the chart doesn't 
    start/end exactly at task boundaries, which would make it harder to read.
    The padding is calculated as a percentage of the total date range.
    """
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
    """
    Set up axes with proper scaling and formatting.
    
    PARAMETERS:
    -----------
    ax : matplotlib.axes.Axes
        The axes to configure
    min_date : datetime
        Minimum date for x-axis
    max_date : datetime
        Maximum date for x-axis
    num_tasks : int
        Number of tasks for y-axis
    grid_color : str
        Color for grid lines
        
    DEVELOPMENT NOTES:
    ------------------
    The date formatting uses matplotlib.dates which handles datetime objects
    natively. The rotation of x-axis labels improves readability for longer
    date ranges.
    """
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
    """
    Draw an empty chart with instructions.
    
    PARAMETERS:
    -----------
    ax : matplotlib.axes.Axes
        The axes to draw on
    grid_color : str
        Color for grid lines (not used in empty state)
        
    DEVELOPMENT NOTES:
    ------------------
    This provides a user-friendly message when there are no tasks to display,
    rather than showing an empty or confusing chart.
    """
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
    """
    Draw regular tasks as horizontal bars.
    
    PARAMETERS:
    -----------
    ax : matplotlib.axes.Axes
        The axes to draw on
    tasks : list of Task
        List of tasks to draw
    default_color : str
        Default color for tasks (not used directly, each task has its own color)
    grid_color : str
        Color for grid lines (not used here)
        
    DEVELOPMENT NOTES:
    ------------------
    Each task is drawn as a Rectangle patch. The key challenge here is that
    matplotlib's Rectangle expects numeric values for its coordinates, but we're
    working with datetime objects. We use mdates.date2num() to convert datetimes
    to numeric values that matplotlib can use.
    
    The width of each task bar is calculated as the difference between the numeric
    values of the start and end dates, which gives us the width in "days" in
    matplotlib's date coordinate system.
    """
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
    """
    Draw milestones as diamonds.
    
    PARAMETERS:
    -----------
    ax : matplotlib.axes.Axes
        The axes to draw on
    milestones : list of Task
        List of milestone tasks to draw
    all_tasks : list of Task
        Full list of tasks (used to determine y-position)
    milestone_color : str
        Default color for milestones (each milestone has its own color)
        
    DEVELOPMENT NOTES:
    ------------------
    Milestones are represented as diamond-shaped Polygons rather than rectangles.
    This visual distinction makes it easy to identify milestones in the chart.
    Each milestone is positioned at its start_date on the x-axis and at its
    index in the task list on the y-axis.
    """
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
    """
    Draw dependency arrows between tasks.
    
    PARAMETERS:
    -----------
    ax : matplotlib.axes.Axes
        The axes to draw on
    tasks : list of Task
        List of tasks to process
    project : Project
        The project containing all tasks (used for ID lookup)
    dependency_color : str
        Color for dependency arrows
        
    DEVELOPMENT NOTES:
    ------------------
    Dependencies are drawn as Arrow patches connecting the end of one task
    to the start of another. For milestones, we use their start_date as both
    the start and end point (since milestones are single-date markers).
    
    The arrows are positioned slightly above/below the task bars to avoid
    overlapping with the bars themselves.
    """
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
    """
    Draw an arrow from (x1, y1) to (x2, y2).
    
    PARAMETERS:
    -----------
    ax : matplotlib.axes.Axes
        The axes to draw on
    x1, y1 : datetime, float
        Start point coordinates
    x2, y2 : datetime, float
        End point coordinates
    color : str
        Color for the arrow
        
    DEVELOPMENT NOTES:
    ------------------
    The arrow is drawn as a combination of a line and an arrowhead. The y-positions
    are adjusted to place the arrow above/below the task bars for better
    visibility. This prevents the arrows from overlapping with the task bars.
    """
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
    """
    Draw the critical path in a different color.
    
    PARAMETERS:
    -----------
    ax : matplotlib.axes.Axes
        The axes to draw on
    tasks : list of Task
        List of all tasks
    project : Project
        The project containing all tasks
    critical_path_color : str
        Color for critical path highlighting
        
    DEVELOPMENT NOTES:
    ------------------
    The critical path is calculated by the Project.get_critical_path() method.
    We then highlight each task on the critical path by drawing it again with
    the critical path color. This is done after drawing the regular tasks so
    that the highlighting appears on top.
    """
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
    """
    Add labels and title to the chart.
    
    PARAMETERS:
    -----------
    ax : matplotlib.axes.Axes
        The axes to add labels to
    project : Project
        The project being visualized
        
    DEVELOPMENT NOTES:
    ------------------
    This adds the chart title (which includes the project name) and y-axis
    label. It also sets the y-axis tick labels to the task names, truncated
    if they're too long.
    """
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

    # Earliest task at the top, matching the task list and the on-screen chart
    if not ax.yaxis_inverted():
        ax.invert_yaxis()


def export_gantt_to_pdf(project: Project, filepath: str, 
                       width: float = 10, height: float = 6, 
                       dpi: int = 100) -> bool:
    """
    Export a project's Gantt chart to PDF format.
    
    This is the main public function for PDF export. It creates a complete
    Gantt chart visualization and saves it to a PDF file.
    
    PARAMETERS:
    -----------
    project : Project
        The project to visualize and export
    filepath : str
        Path where the PDF file should be saved
    width : float, optional
        Width of the output figure in inches (default: 10)
    height : float, optional
        Height of the output figure in inches (default: 6)
    dpi : int, optional
        Dots per inch for the output (default: 100)
        
    RETURNS:
    --------
    bool
        True if export was successful, False otherwise
        
    EXAMPLE:
    --------
    >>> from gantt_app.models import Project, Task
    >>> from gantt_app.utils.pdf_exporter import export_gantt_to_pdf
    >>> from datetime import datetime, timedelta
    >>> 
    >>> project = Project(name="My Project")
    >>> start = datetime(2024, 1, 1)
    >>> project.add_task(Task.create_task("Task 1", start, start + timedelta(days=5)))
    >>> export_gantt_to_pdf(project, "/path/to/output.pdf")
    True
        
    DEVELOPMENT NOTES:
    ------------------
    This function creates a new matplotlib Figure specifically for export.
    This is necessary because:
    1. The main GanttChart uses an interactive Tkinter backend which can
       interfere with PDF export
    2. We want the export to be independent of the GUI state
    3. We can customize the size and DPI for the export without affecting
       the displayed chart
    
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
        
        # Save to PDF
        # bbox_inches='tight' prevents cropping of chart elements
        fig.savefig(filepath, format='pdf', bbox_inches='tight')
        
        # Clean up
        # Note: We don't need to explicitly close the canvas or clear the figure
        # as they will be garbage collected. The savefig() call handles cleanup.
        plt.close(fig)
        
        return True
        
    except Exception as e:
        logger.exception(f"Error exporting to PDF: {e}")
        import traceback
        traceback.print_exc()
        return False
