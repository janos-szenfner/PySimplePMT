"""
XLSX Exporter for the Gantt Project Management Tool.

This module provides functionality to export projects to Excel XLSX format.

WHY THIS MODULE EXISTS:
======================
This module was created to provide Excel spreadsheet export capability,
allowing users to analyze project data in spreadsheet applications like
Microsoft Excel, Google Sheets, or LibreOffice Calc.

By separating XLSX export into its own module, we achieve:

1. **Separation of Concerns**: The main application and data models focus on
   project management, while this module focuses solely on Excel export.

2. **Optional Dependency**: Excel export requires the openpyxl library, which
   is not required for basic application functionality. This keeps the
   core dependencies minimal.

3. **Reusability**: The export logic can be reused independently of the GUI
   components, making it easier to test and integrate with other systems.

4. **Extensibility**: New export formats can be added following the same
   pattern without modifying existing code.

5. **Comprehensive Data Export**: Exports all task information including
   hierarchy, dependencies, dates, progress, and custom properties.

DESIGN DECISIONS:
================
- Uses openpyxl library for Excel file creation (most popular Python Excel library)
- Creates a new workbook for each export to avoid conflicts
- Exports data in a structured format with multiple worksheets:
  - Tasks: Main task data with all properties
  - Dependencies: Dependency relationships between tasks
  - Summary: Project overview and statistics
- Automatically creates parent directories if they don't exist
- Returns boolean success/failure for easy error handling
- Gracefully handles missing optional dependencies
- Uses pandas-compatible data structures for potential future integration

USAGE:
======
from gantt_app.utils.xlsx_exporter import export_project_to_xlsx

# Export a project to Excel
success = export_project_to_xlsx(project, "/path/to/output.xlsx")
if success:
    print("Export successful!")

# Get Excel content as bytes (without saving to file)
from gantt_app.utils.xlsx_exporter import generate_xlsx_bytes
xlsx_bytes = generate_xlsx_bytes(project)
"""

import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, TYPE_CHECKING

try:
    import openpyxl
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
    from openpyxl.styles.colors import Color
    from openpyxl.utils import get_column_letter
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False
    Workbook = None  # type: ignore

from gantt_app.models import Project, Task
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    # For type hints only - this won't cause import errors at runtime
    if OPENPYXL_AVAILABLE:
        from openpyxl import Workbook as WorkbookType
    else:
        WorkbookType = Any  # type: ignore


def _get_task_data_dict(task: Task, project: Project) -> Dict[str, Any]:
    """
    Convert a Task object to a dictionary of exportable data.
    
    PARAMETERS:
    -----------
    task : Task
        The task to convert
    project : Project
        The project containing the task (for dependency name resolution)
        
    RETURNS:
    --------
    Dict[str, Any]
        Dictionary containing task data suitable for Excel export
        
    DEVELOPMENT NOTES:
    ------------------
    This function extracts all relevant task data and formats it appropriately
    for Excel export. It handles special cases like milestones, subtasks,
    and missing end dates.
    """
    # Get parent task name for subtasks
    parent_name = ""
    if task.parent_task_id:
        parent_task = project.get_task_by_id(task.parent_task_id)
        if parent_task:
            parent_name = parent_task.name
    
    # Get dependency names
    dependency_names = []
    for dep_id in task.dependency_ids:
        dep_task = project.get_task_by_id(dep_id)
        if dep_task:
            dependency_names.append(dep_task.name)
    
    # Format dates
    start_date_str = task.start_date.strftime('%Y-%m-%d') if task.start_date else ""
    end_date_str = task.end_date.strftime('%Y-%m-%d') if task.end_date else ""
    
    # Calculate duration
    duration_days = task.duration_days
    duration_str = str(duration_days) if duration_days is not None else ""
    
    return {
        'ID': task.id,
        'Name': task.name,
        'Type': task.task_type,
        'Parent Task': parent_name,
        'Start Date': start_date_str,
        'End Date': end_date_str,
        'Duration (Days)': duration_str,
        'Progress (%)': task.progress,
        'Dependencies': ', '.join(dependency_names) if dependency_names else "",
        'Milestone': 'Yes' if task.is_milestone else 'No',
        'Color': task.color,
    }


def _create_tasks_workbook(project: Project):
    """
    Create a workbook with tasks data.
    
    PARAMETERS:
    -----------
    project : Project
        The project to export
        
    RETURNS:
    --------
    Workbook
        An openpyxl Workbook object with tasks data
        
    DEVELOPMENT NOTES:
    ------------------
    Creates multiple worksheets:
    1. Tasks - Main task data
    2. Dependencies - Dependency relationships
    3. Summary - Project overview
    """
    wb = Workbook()
    
    # Remove default sheet - we'll create our own
    del wb['Sheet']
    
    # Create Tasks worksheet
    ws_tasks = wb.create_sheet("Tasks")
    
    # Define headers
    headers = [
        'ID', 'Name', 'Type', 'Parent Task', 'Start Date', 'End Date', 
        'Duration (Days)', 'Progress (%)', 'Dependencies', 'Milestone', 'Color'
    ]
    
    # Write headers with styling
    for col_num, header in enumerate(headers, 1):
        cell = ws_tasks.cell(row=1, column=col_num, value=header)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color='DDDDDD', end_color='DDDDDD', fill_type='solid')
        cell.border = Border(left=Side(style='thin'), right=Side(style='thin'), 
                             top=Side(style='thin'), bottom=Side(style='thin'))
        cell.alignment = Alignment(horizontal='center', vertical='center')
    
    # Write task data
    for row_num, task in enumerate(project.tasks, 2):
        task_data = _get_task_data_dict(task, project)
        
        for col_num, header in enumerate(headers, 1):
            cell = ws_tasks.cell(row=row_num, column=col_num, value=task_data[header])
            cell.border = Border(left=Side(style='thin'), right=Side(style='thin'), 
                                 top=Side(style='thin'), bottom=Side(style='thin'))
            
            # Apply special formatting
            if header == 'Progress (%)':
                # Center progress percentages
                cell.alignment = Alignment(horizontal='center')
            elif header == 'Milestone':
                # Center milestone indicator
                cell.alignment = Alignment(horizontal='center')
            elif header == 'Duration (Days)':
                # Right-align numbers
                cell.alignment = Alignment(horizontal='right')
    
    # Auto-adjust column widths
    for col_num, header in enumerate(headers, 1):
        max_length = len(header)
        column_letter = get_column_letter(col_num)
        
        # Check all rows for this column
        for row_num in range(2, len(project.tasks) + 2):
            cell_value = str(ws_tasks[column_letter + str(row_num)].value or '')
            max_length = max(max_length, len(cell_value))
        
        # Set column width with some padding
        ws_tasks.column_dimensions[column_letter].width = min(max_length + 2, 50)
    
    # Create Dependencies worksheet
    ws_deps = wb.create_sheet("Dependencies")
    
    # Write dependency headers
    deps_headers = ['Source Task', 'Target Task', 'Dependency Type']
    for col_num, header in enumerate(deps_headers, 1):
        cell = ws_deps.cell(row=1, column=col_num, value=header)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color='DDDDDD', end_color='DDDDDD', fill_type='solid')
        cell.border = Border(left=Side(style='thin'), right=Side(style='thin'), 
                             top=Side(style='thin'), bottom=Side(style='thin'))
        cell.alignment = Alignment(horizontal='center', vertical='center')
    
    # Write dependency data
    row_num = 2
    for task in project.tasks:
        for dep_id in task.dependency_ids:
            dep_task = project.get_task_by_id(dep_id)
            if dep_task:
                ws_deps.cell(row=row_num, column=1, value=task.name)
                ws_deps.cell(row=row_num, column=2, value=dep_task.name)
                ws_deps.cell(row=row_num, column=3, value='Finish-to-Start')
                
                # Apply borders
                for col_num in range(1, 4):
                    cell = ws_deps.cell(row=row_num, column=col_num)
                    cell.border = Border(left=Side(style='thin'), right=Side(style='thin'), 
                                         top=Side(style='thin'), bottom=Side(style='thin'))
                
                row_num += 1
    
    # Auto-adjust dependency column widths
    for col_num, header in enumerate(deps_headers, 1):
        max_length = len(header)
        column_letter = get_column_letter(col_num)
        
        for row_num in range(2, row_num):  # row_num is one past the last data row
            cell_value = str(ws_deps[column_letter + str(row_num)].value or '')
            max_length = max(max_length, len(cell_value))
        
        ws_deps.column_dimensions[column_letter].width = min(max_length + 2, 50)
    
    # Create Summary worksheet
    ws_summary = wb.create_sheet("Summary")
    
    # Write summary data
    summary_data = [
        ['Project Name:', project.name or ''],
        ['Total Tasks:', len(project.tasks)],
        ['Start Date:', project.start_date.strftime('%Y-%m-%d') if project.start_date else ''],
        ['End Date:', project.end_date.strftime('%Y-%m-%d') if project.end_date else ''],
        ['Project Duration (Days):', (project.end_date - project.start_date).days + 1 if project.start_date and project.end_date else ''],
    ]
    
    # Count task types
    regular_tasks = [t for t in project.tasks if t.task_type == 'Task' and not t.effective_milestone]
    subtasks = [t for t in project.tasks if t.task_type == 'Subtask']
    milestones = [t for t in project.tasks if t.effective_milestone]
    
    summary_data.extend([
        ['Regular Tasks:', len(regular_tasks)],
        ['Subtasks:', len(subtasks)],
        ['Milestones:', len(milestones)],
    ])
    
    # Count tasks by progress
    completed = [t for t in project.tasks if t.progress >= 100]
    in_progress = [t for t in project.tasks if 0 < t.progress < 100]
    not_started = [t for t in project.tasks if t.progress == 0]
    
    summary_data.extend([
        ['Completed:', len(completed)],
        ['In Progress:', len(in_progress)],
        ['Not Started:', len(not_started)],
    ])
    
    # Write summary data with styling
    for row_num, (label, value) in enumerate(summary_data, 1):
        label_cell = ws_summary.cell(row=row_num, column=1, value=label)
        value_cell = ws_summary.cell(row=row_num, column=2, value=value)
        
        label_cell.font = Font(bold=True)
        label_cell.border = Border(left=Side(style='thin'), right=Side(style='thin'), 
                                   top=Side(style='thin'), bottom=Side(style='thin'))
        value_cell.border = Border(left=Side(style='thin'), right=Side(style='thin'), 
                                   top=Side(style='thin'), bottom=Side(style='thin'))
    
    # Set summary column widths
    ws_summary.column_dimensions['A'].width = 25
    ws_summary.column_dimensions['B'].width = 30
    
    # Add a title to summary sheet
    title_cell = ws_summary.cell(row=1, column=1, value='Project Summary')
    title_cell.font = Font(bold=True, size=14)
    title_cell.fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
    title_cell.alignment = Alignment(horizontal='center')
    
    # Merge title across columns
    ws_summary.merge_cells(start_row=1, start_column=1, end_row=1, end_column=2)
    
    # Move summary data down one row to accommodate title
    for row_num, (label, value) in enumerate(summary_data, 2):
        label_cell = ws_summary.cell(row=row_num, column=1, value=label)
        value_cell = ws_summary.cell(row=row_num, column=2, value=value)
        
        label_cell.font = Font(bold=True)
        label_cell.border = Border(left=Side(style='thin'), right=Side(style='thin'), 
                                   top=Side(style='thin'), bottom=Side(style='thin'))
        value_cell.border = Border(left=Side(style='thin'), right=Side(style='thin'), 
                                   top=Side(style='thin'), bottom=Side(style='thin'))
    
    return wb


def generate_xlsx_bytes(project: Project) -> Optional[bytes]:
    """
    Generate XLSX content as bytes from a Project.
    
    PARAMETERS:
    -----------
    project : Project
        The project to export
        
    RETURNS:
    --------
    Optional[bytes]
        XLSX file content as bytes, or None if export failed
        
    DEVELOPMENT NOTES:
    ------------------
    This function creates the Excel workbook in memory and returns it as bytes.
    This is useful for web applications or when you want to manipulate the
    data further before saving to disk.
    """
    if not OPENPYXL_AVAILABLE:
        logger.error("Error: openpyxl library is required for Excel export")
        logger.warning("Install it with: pip install openpyxl")
        return None
    
    try:
        wb = _create_tasks_workbook(project)
        
        # Save workbook to bytes
        from io import BytesIO
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        
        return output.getvalue()
        
    except Exception as e:
        logger.exception(f"Error generating XLSX: {e}")
        import traceback
        traceback.print_exc()
        return None


def export_project_to_xlsx(project: Project, filepath: str) -> bool:
    """
    Export a Project to Excel XLSX format.
    
    This is the main public function for XLSX export. It generates the
    Excel workbook and saves it to a file.
    
    PARAMETERS:
    -----------
    project : Project
        The project to export
    filepath : str
        Path where the XLSX file should be saved
        
    RETURNS:
    --------
    bool
        True if export was successful, False otherwise
        
    EXAMPLE:
    --------
    >>> from gantt_app.models import Project, Task
    >>> from gantt_app.utils.xlsx_exporter import export_project_to_xlsx
    >>> from datetime import datetime, timedelta
    >>> 
    >>> project = Project(name="My Project")
    >>> start = datetime(2024, 1, 1)
    >>> project.add_task(Task.create_task("Task 1", start, start + timedelta(days=5)))
    >>> export_project_to_xlsx(project, "/path/to/output.xlsx")
    True
        
    DEVELOPMENT NOTES:
    ------------------
    This function:
    1. Creates the Excel workbook using _create_tasks_workbook()
    2. Creates parent directories if they don't exist
    3. Saves the workbook to the specified file
    4. Handles any errors gracefully and returns False on failure
    
    The Excel file contains:
    - Tasks worksheet: All task data with full details
    - Dependencies worksheet: Dependency relationships between tasks
    - Summary worksheet: Project overview and statistics
    
    If openpyxl is not installed, this function will print an error message
    and return False.
    """
    if not OPENPYXL_AVAILABLE:
        logger.error("Error: openpyxl library is required for Excel export")
        logger.warning("Install it with: pip install openpyxl")
        return False
    
    try:
        # Create parent directories if they don't exist
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        # Create and save workbook
        wb = _create_tasks_workbook(project)
        wb.save(filepath)
        
        return True
        
    except Exception as e:
        logger.exception(f"Error exporting to XLSX: {e}")
        import traceback
        traceback.print_exc()
        return False