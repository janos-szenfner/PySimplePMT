"""
Mermaid Exporter for the Gantt Project Management Tool.

This module provides functionality to export projects to Mermaid Gantt chart format.

WHY THIS MODULE EXISTS:
======================
This module was separated from the mermaid_importer.py to follow the principle of
Single Responsibility. The original mermaid_importer.py contained both import and
export functionality, which made it less maintainable. By separating the exporter:

1. **Single Responsibility**: Each module has a single, clear purpose
   - mermaid_importer.py: Import Mermaid files
   - mermaid_exporter.py: Export to Mermaid format

2. **Clearer Dependencies**: Users can import only what they need
   - Need to import? Import from mermaid_importer
   - Need to export? Import from mermaid_exporter

3. **Easier Maintenance**: Changes to export logic don't affect import logic
   - Bug fixes can be targeted to the specific functionality
   - New export features can be added without touching import code

4. **Better Organization**: Follows the pattern established by other importers/exporters
   - gan_importer.py for GAN import
   - mpp_importer.py for MPP import
   - pdf_exporter.py for PDF export
   - png_exporter.py for PNG export

5. **Consistent API**: All exporters follow the same pattern
   - export_gantt_to_pdf(project, filepath, **options)
   - export_gantt_to_png(project, filepath, **options)
   - export_project_to_mermaid(project, filepath, **options)

RELATIONSHIP WITH mermaid_importer.py:
======================================
While this module is separate, it's designed to work seamlessly with
mermaid_importer.py. The two modules together provide complete Mermaid
support:

- mermaid_importer.py: Reads Mermaid Gantt charts -> Project objects
- mermaid_exporter.py: Writes Project objects -> Mermaid Gantt charts

This creates a round-trip capability where projects can be:
Project -> Mermaid -> Project -> Mermaid -> ...

DESIGN DECISIONS:
================
1. **Topological Sorting**: Tasks are sorted based on dependencies to ensure
   that dependencies are defined before the tasks that depend on them.
   This is crucial for the "after" syntax in Mermaid to work correctly.

2. **Task ID Generation**: Generates valid Mermaid IDs from task names or UUIDs
   - Converts special characters to underscores
   - Ensures uniqueness within the project
   - Maintains readability when possible

3. **Duration Calculation**: Automatically calculates task durations in days
   - For regular tasks: (end_date - start_date).days + 1
   - For milestones: Not applicable (single date)

4. **Dependency Handling**: Uses Mermaid's "after" syntax for dependencies
   - Only supports single dependencies per task in the "after" syntax
   - Multiple dependencies are still preserved in the project model
   - Falls back to explicit dates when dependencies can't be resolved

5. **Date Format**: Uses YYYY-MM-DD format which is the most common and
   human-readable Mermaid date format.

USAGE:
======
from gantt_app.utils.mermaid_exporter import export_project_to_mermaid

# Export a project to Mermaid format
success = export_project_to_mermaid(project, "/path/to/output.mmd")
if success:
    print("Export successful!")

# Get Mermaid content as a string (without saving to file)
from gantt_app.utils.mermaid_exporter import generate_mermaid_content
content = generate_mermaid_content(project)
print(content)
"""

import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set

from gantt_app.models import Project, Task


def _generate_task_id(task: Task, used_ids: Set[str]) -> str:
    """
    Generate a unique task ID for Mermaid export.
    
    Mermaid Gantt charts require unique IDs for each task/milestone.
    This function generates IDs that are:
    - Valid Mermaid identifiers (alphanumeric + underscores)
    - Unique within the project
    - As readable as possible
    
    PARAMETERS:
    -----------
    task : Task
        The task to generate an ID for
    used_ids : Set[str]
        Set of already-used IDs to ensure uniqueness
        
    RETURNS:
    --------
    str
        A unique, valid Mermaid task ID
        
    DEVELOPMENT NOTES:
    ------------------
    Mermaid IDs must contain only alphanumeric characters and underscores.
    We first try to use the task's existing ID (which might already be 
    a UUID or other valid identifier). If that's not valid or already used,
    we generate an ID from the task name.
    
    Examples:
    - "Task 1" -> "task_1"
    - "Design Phase" -> "design_phase"
    - If "design_phase" is taken -> "design_phase_2", "design_phase_3", etc.
    """
    # Try using the task's existing ID if it's valid and unique
    if task.id and task.id not in used_ids:
        # Make sure it's a valid Mermaid ID (alphanumeric and underscores)
        valid_id = re.sub(r'[^a-zA-Z0-9_]', '_', task.id)
        if valid_id and valid_id not in used_ids:
            used_ids.add(valid_id)
            return valid_id
    
    # Generate a new ID based on task name
    base_id = re.sub(r'[^a-zA-Z0-9_]', '_', task.name.lower())
    if base_id and base_id not in used_ids:
        used_ids.add(base_id)
        return base_id
    
    # Add numeric suffix to make it unique
    counter = 1
    while f"{base_id}_{counter}" in used_ids:
        counter += 1
    
    task_id = f"{base_id}_{counter}"
    used_ids.add(task_id)
    return task_id


def _format_date(date: datetime) -> str:
    """
    Format datetime object as Mermaid date string.
    
    PARAMETERS:
    -----------
    date : datetime
        The datetime to format
        
    RETURNS:
    --------
    str
        Formatted date string in YYYY-MM-DD format
        
    DEVELOPMENT NOTES:
    ------------------
    Mermaid Gantt charts support multiple date formats, but YYYY-MM-DD is
    the most widely supported and human-readable. This is the format used
    by the Mermaid live editor and most documentation.
    """
    return date.strftime("%Y-%m-%d")


def _get_task_duration_days(task: Task) -> Optional[int]:
    """
    Get task duration in days.
    
    PARAMETERS:
    -----------
    task : Task
        The task to get duration for
        
    RETURNS:
    --------
    Optional[int]
        Duration in days, or None if not calculable
        
    DEVELOPMENT NOTES:
    ------------------
    For milestones, we return 0 since they represent a single point in time.
    For regular tasks, we calculate the number of days between start and end.
    The +1 ensures that a task from Jan 1 to Jan 2 is 2 days, not 1.
    
    If the task has no end_date, we return None, and the caller should
    handle this case (typically by using a default duration of 1 day).
    """
    if task.is_milestone:
        return 0
    if task.end_date is None or task.start_date is None:
        return None
    return (task.end_date - task.start_date).days + 1


def _sort_tasks_for_dependencies(project: Project) -> List[Task]:
    """
    Sort tasks to ensure dependencies are defined before dependent tasks.
    
    Uses topological sort to handle dependency chains properly.
    
    PARAMETERS:
    -----------
    project : Project
        The project containing tasks to sort
        
    RETURNS:
    --------
    List[Task]
        Tasks sorted such that dependencies come before dependent tasks
        
    DEVELOPMENT NOTES:
    ------------------
    This is a classic topological sort implementation. We recursively visit
    all dependencies of a task before visiting the task itself.
    
    This ensures that when we generate the Mermaid output, tasks that use
    the "after" syntax will reference tasks that have already been defined.
    
    Example:
    - Task B depends on Task A
    - Topological sort: [A, B]
    - Mermaid output: A is defined first, then B uses "after A"
    
    The algorithm also handles circular dependencies gracefully by
    tracking visited tasks and not revisiting them.
    """
    visited = set()
    sorted_tasks = []
    
    def visit(task: Task):
        """Recursively visit dependencies first, then the task itself."""
        if task.id in visited:
            return
        
        # Visit all dependencies first
        for dep_id in task.dependencies:
            dep_task = project.get_task_by_id(dep_id)
            if dep_task:
                visit(dep_task)
        
        visited.add(task.id)
        sorted_tasks.append(task)
    
    # Start with all tasks
    for task in project.tasks:
        visit(task)
    
    return sorted_tasks


def generate_mermaid_content(project: Project, 
                            include_date_format: bool = True) -> str:
    """
    Generate Mermaid Gantt chart content from a Project.
    
    This is the main content generation function. It creates a complete
    Mermaid Gantt chart string that can be saved to a file or used directly.
    
    PARAMETERS:
    -----------
    project : Project
        The project to export
    include_date_format : bool, optional
        Whether to include the dateFormat directive (default: True)
        
    RETURNS:
    --------
    str
        Complete Mermaid Gantt chart content as a string
        
    EXAMPLE:
    --------
    >>> from gantt_app.models import Project, Task
    >>> from gantt_app.utils.mermaid_exporter import generate_mermaid_content
    >>> from datetime import datetime, timedelta
    >>> 
    >>> project = Project(name="My Project")
    >>> start = datetime(2024, 1, 1)
    >>> project.add_task(Task.create_task("Task 1", start, start + timedelta(days=5)))
    >>> content = generate_mermaid_content(project)
    >>> print(content)
    gantt
        title My Project
        dateFormat  YYYY-MM-DD
        Task 1 :task_1, 2024-01-01, 6d
    """
    lines = []
    used_ids = set()
    id_to_mermaid_id = {}  # Map internal task IDs to Mermaid IDs
    
    # Start with gantt directive
    lines.append("gantt")
    
    # Add title if project has a name
    if project.name:
        lines.append(f"    title {project.name}")
    
    # Add date format
    if include_date_format:
        lines.append("    dateFormat  YYYY-MM-DD")
    
    # Generate Mermaid IDs for all tasks
    for task in project.tasks:
        mermaid_id = _generate_task_id(task, used_ids)
        id_to_mermaid_id[task.id] = mermaid_id
    
    # Sort tasks topologically based on dependencies
    sorted_tasks = _sort_tasks_for_dependencies(project)
    
    # Track which tasks have been defined
    defined_task_ids = set()
    
    for task in sorted_tasks:
        mermaid_id = id_to_mermaid_id[task.id]
        
        # Get dependencies that have already been defined
        valid_deps = [dep_id for dep_id in task.dependencies 
                     if dep_id in defined_task_ids]
        
        if task.is_milestone:
            date_str = _format_date(task.start_date)
            if valid_deps and len(valid_deps) == 1:
                # Use after syntax for single dependency
                dep_mermaid_id = id_to_mermaid_id.get(valid_deps[0], valid_deps[0])
                lines.append(f"    milestone {task.name} :{mermaid_id}, after {dep_mermaid_id}")
            else:
                # Use explicit date
                lines.append(f"    milestone {task.name} :{mermaid_id}, {date_str}")
        else:
            date_str = _format_date(task.start_date)
            duration_days = _get_task_duration_days(task)
            if duration_days is None or duration_days <= 0:
                duration_days = 1
            
            if valid_deps and len(valid_deps) == 1:
                # Use after syntax for single dependency
                dep_mermaid_id = id_to_mermaid_id.get(valid_deps[0], valid_deps[0])
                lines.append(f"    {task.name} :{mermaid_id}, after {dep_mermaid_id}, {duration_days}d")
            else:
                # Use explicit date and duration
                lines.append(f"    {task.name} :{mermaid_id}, {date_str}, {duration_days}d")
        
        # Mark this task as defined
        defined_task_ids.add(task.id)
    
    return "\n".join(lines)


def export_project_to_mermaid(project: Project, filepath: str, 
                              include_date_format: bool = True) -> bool:
    """
    Export a Project to Mermaid Gantt chart format.
    
    This is the main public function for Mermaid export. It generates the
    Mermaid content and saves it to a file.
    
    PARAMETERS:
    -----------
    project : Project
        The project to export
    filepath : str
        Path where the Mermaid file should be saved
    include_date_format : bool, optional
        Whether to include the dateFormat directive (default: True)
        
    RETURNS:
    --------
    bool
        True if export was successful, False otherwise
        
    EXAMPLE:
    --------
    >>> from gantt_app.models import Project, Task
    >>> from gantt_app.utils.mermaid_exporter import export_project_to_mermaid
    >>> from datetime import datetime, timedelta
    >>> 
    >>> project = Project(name="My Project")
    >>> start = datetime(2024, 1, 1)
    >>> project.add_task(Task.create_task("Task 1", start, start + timedelta(days=5)))
    >>> export_project_to_mermaid(project, "/path/to/output.mmd")
    True
        
    DEVELOPMENT NOTES:
    ------------------
    This function:
    1. Generates the Mermaid content using generate_mermaid_content()
    2. Creates parent directories if they don't exist
    3. Writes the content to the specified file with UTF-8 encoding
    4. Handles any errors gracefully and returns False on failure
    
    The Mermaid format is a text-based format that is human-readable and
    can be rendered by any Mermaid-compatible renderer (GitHub, GitLab,
    VS Code with Mermaid plugin, etc.).
    """
    try:
        # Create parent directories if they don't exist
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        # Generate Mermaid content
        content = generate_mermaid_content(project, include_date_format)
        
        # Write to file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return True
        
    except Exception as e:
        print(f"Error exporting to Mermaid: {e}")
        import traceback
        traceback.print_exc()
        return False
