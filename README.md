# PySimplePMT - Gantt Project Management Tool

A cross-platform desktop application for project management with Gantt chart visualization, drag-and-drop task management, and support for importing MS Project and GanttProject files.

## Overview

This is a complete implementation of a project management tool with:
- Static Gantt chart visualization
- Drag-and-drop task list for dependency management
- Support for milestones (single-date tasks)
- JSON storage and file import for GAN/MPP/Mermaid files
- Modern UI using CustomTkinter

## Features

- **Static Gantt Chart Visualization**: Visual representation of tasks and milestones with dependency arrows
- **Drag-and-Drop Task List**: Reorder tasks and set dependencies by dragging
- **Milestone Support**: Special single-date markers with diamond icons
- **JSON Storage**: Save and load projects in JSON format
- **File Import**: Import from GanttProject (.gan), MS Project (.mpp), and Mermaid (.mmd) files
- **File Export**: Export Gantt charts to PNG and PDF formats, projects to Mermaid format, and tasks to Excel XLSX
- **Modern UI**: Built with CustomTkinter for a professional look
- **Critical Path**: Automatic calculation and visualization of the critical path
- **Progress Tracking**: Track completion percentage for each task

## Project Structure

```
gantt_app/
├── __init__.py
├── models.py              # Task and Project data models
├── main.py                # Main application entry point
├── run.py                 # Entry point script
│
├── views/
│   ├── __init__.py
│   ├── task_list.py       # Drag-and-drop task list with EditTaskDialog
│   ├── gantt_chart.py     # Static Gantt chart visualization
│   └── toolbar.py         # Action buttons and file operations
│
├── utils/
│   ├── __init__.py
│   ├── file_io.py          # JSON save/load functionality
│   ├── gan_importer.py     # GAN (GanttProject) file import
│   ├── mpp_importer.py     # MPP (MS Project) file import
│   ├── mermaid_importer.py # Mermaid (.mmd) file import
│   ├── mermaid_exporter.py # Mermaid (.mmd) file export
│   ├── pdf_exporter.py     # PDF export for Gantt charts
│   ├── png_exporter.py     # PNG export for Gantt charts
│   └── xlsx_exporter.py     # Excel XLSX export for tasks data
│
└── assets/                # For icons, themes, etc.
```

## Implemented Features

### Core Data Models (`models.py`)
- **Task Class**: id, name, start_date, end_date, progress, dependencies, color, is_milestone
- **Project Class**: name, tasks, start_date, end_date
- **Methods**: add_task, remove_task, get_task_by_id, get_dependencies, get_dependents
- **Serialization**: to_dict(), from_dict() for JSON compatibility
- **Critical Path**: get_critical_path() algorithm for project analysis
- **Factory Methods**: create_task(), create_milestone() for easy object creation

### Task List View (`views/task_list.py`)
- **Drag-and-Drop**: Full tkinterdnd2 integration with enhanced drag-and-drop for setting dependencies, graceful fallback to basic implementation
- **EditTaskDialog**: Comprehensive task editing interface
- **Treeview Display**: ID, Name, Type, Duration (Days), Start Date, End Date, Progress, Dependencies, Milestone
- **Hierarchical Display**: Sub-tasks are visually indented under their parent tasks with tree structure
- **Features**:
  - Double-click to edit tasks
  - Circular dependency prevention (including parent-child relationships)
  - Milestone toggle with automatic end_date handling
  - Progress slider with percentage display
  - Dependency management via checkboxes (select multiple tasks and subtasks)
  - Task Type selection (Task or Sub-Task)
  - Parent Task display for sub-tasks
  - Duration calculation display

### Gantt Chart View (`views/gantt_chart.py`)
- **Task Bars**: Horizontal bars colored by task.color
- **Milestone Diamonds**: Special diamond shapes for milestones
- **Dependency Arrows**: Red arrows connecting dependent tasks
- **Critical Path**: Highlighted in orange
- **Labels**: Task names, progress percentages
- **Date Formatting**: Proper date display and scaling
- **Empty State**: Helpful message when no tasks exist

### Toolbar (`views/toolbar.py`)
- **Undo/Redo**: Undo and Redo buttons with visual state indication
- **Project Management**: Add Task, Add Sub-Task, Add Milestone, Project Info
- **File Operations**: Save Project, Load Project, New Project
- **Import**: Import GAN, Import MPP, Import Mermaid
- **Export**: Export Mermaid, Export PNG, Export PDF
- **Theme Toggle**: Switch between light/dark modes
- **Dialog Integration**: File dialogs, input validation, parent task selection for subtasks

### File I/O (`utils/file_io.py`)
- **JSON Serialization**: Handles datetime objects and None values
- **Save/Load**: Full project save and load functionality
- **Error Handling**: Graceful error handling for file operations

### GAN Importer (`utils/gan_importer.py`)
- **XML Parsing**: Uses xml.etree.ElementTree for GAN files
- **Date Parsing**: Handles various date formats from GAN files
- **Color Mapping**: Converts GAN color definitions to hex
- **Task Parsing**: Extracts tasks, milestones, dependencies
- **Project Import**: Full project structure import

### Mermaid Importer (`utils/mermaid_importer.py`)
- **Syntax Parsing**: Parses Mermaid Gantt chart text format
- **Task Extraction**: Extracts tasks, milestones, and dependencies
- **Date Handling**: Supports various date formats with automatic detection
- **Dependency Resolution**: Calculates task dates based on "after" dependencies

### Mermaid Exporter (`utils/mermaid_exporter.py`)
- **Syntax Generation**: Creates valid Mermaid Gantt chart syntax
- **Topological Sorting**: Orders tasks based on dependencies
- **ID Generation**: Creates valid Mermaid IDs from task names
- **Date Formatting**: Uses YYYY-MM-DD format for maximum compatibility

### PNG Exporter (`utils/png_exporter.py`)
- **High-Quality Export**: Creates PNG images with configurable DPI (default 300)
- **Matplotlib Integration**: Uses matplotlib's built-in PNG export
- **Automatic Scaling**: Properly scales chart elements for image output
- **Directory Creation**: Automatically creates parent directories

### PDF Exporter (`utils/pdf_exporter.py`)
- **Vector Export**: Creates PDF documents with crisp, scalable graphics
- **Matplotlib Integration**: Uses matplotlib's built-in PDF export
- **Consistent Output**: Produces same visual output as PNG export
- **Directory Creation**: Automatically creates parent directories

### XLSX Exporter (`utils/xlsx_exporter.py`)
- **Excel Export**: Creates Excel XLSX files with comprehensive task data
- **Multiple Worksheets**: Tasks, Dependencies, and Summary sheets for organized data
- **Complete Data Export**: All task properties including hierarchy, dependencies, dates, progress
- **Professional Styling**: Headers with background colors, borders, and proper alignment
- **Auto-Sizing**: Automatic column width adjustment based on content
- **Project Statistics**: Summary sheet with task counts, progress breakdown, and project metrics
- **Optional Dependency**: Gracefully handles missing openpyxl library
- **Directory Creation**: Automatically creates parent directories

### MPP Importer (`utils/mpp_importer.py`)
- **Dual Implementation**: Tasklib (pure Python) and JPype+mpxj (Java bridge)
- **Fallback Mechanism**: Tries Tasklib first, then JPype
- **Date Conversion**: Java Date to Python datetime
- **Task Properties**: Full task import with dependencies and progress
- **Error Handling**: Graceful degradation when libraries not available

### Undo/Redo Manager (`utils/undoredo.py`)
- **Command Pattern**: Encapsulates actions as command objects with execute/undo methods
- **Two Stacks**: Uses undo stack (past actions) and redo stack (future actions)
- **Command Types**: AddTask, RemoveTask, UpdateTask, UpdateProjectName, Compound
- **ProjectStateTracker**: Helper class for easier integration with application logic
- **Factory Functions**: create_add_task_command, create_remove_task_command, etc.
- **Max History**: Configurable limit (default 100) to prevent excessive memory usage
- **Memory Management**: Automatically clears redo stack on new actions

### Main Application (`main.py`)
- **Sample Data**: Pre-populated with example tasks and milestones
- **Layout**: Responsive grid layout with toolbar, task list, and Gantt chart
- **Status Bar**: Shows current selection and project statistics
- **Event Handling**: Task selection, editing, project changes
- **Exit Handling**: Save confirmation on close

## Installation

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Required Dependencies
```bash
pip install customtkinter matplotlib numpy
```

### Optional Dependencies
```bash
# For GAN file import (included in standard library)
pip install lxml  # For better XML parsing performance

# For MPP file import
pip install tasklib  # Pure Python MPP reader (recommended)
# OR
pip install JPype1  # For Java bridge with mpxj (requires Java JDK 8+)

# For enhanced drag-and-drop (recommended)
pip install tkinterdnd2

# For Excel XLSX export
pip install openpyxl
```

## Usage

### Running the Application
```bash
# Method 1: Run directly
python3 run.py

# Method 2: Run from the gantt_app directory
python3 -m gantt_app.main
```

### Basic Operations

1. **Create a New Project**
   - Click "New Project" button
   - Enter project name
   - Start adding tasks and milestones

2. **Add Tasks**
   - Click "Add Task" button
   - Enter task name and duration in days
   - Set start date and other properties

3. **Add Sub-Tasks**
   - Click "Add Sub-Task" button
   - Enter subtask name and duration in days
   - Select a parent task from the list (must have at least one task)
   - Sub-tasks automatically inherit the start date from their parent
   - Sub-tasks appear indented under their parent in the task list

4. **Add Milestones**
   - Click "Add Milestone" button
   - Enter milestone name and date
   - Milestones appear as diamonds in the Gantt chart

4. **Set Dependencies**
   - Drag a task onto another task in the task list
   - Or edit dependencies in the task edit dialog (select multiple tasks and subtasks as dependencies)
   - Dependencies appear as red arrows in the Gantt chart
   - Cannot create circular dependencies (a task cannot depend on itself or its own subtasks)

5. **Edit Tasks**
   - Double-click on a task in the task list
   - Modify properties, dependencies, and colors
   - Save changes or delete the task

6. **Save Project**
   - Click "Save Project" button
   - Choose file location and name
   - Project is saved in JSON format

7. **Load Project**
   - Click "Load Project" button
   - Select a previously saved JSON file

8. **Import Projects**
   - Click "Import GAN" to import GanttProject files
   - Click "Import MPP" to import MS Project files (requires Tasklib or JPype)
   - Click "Import Mermaid" to import Mermaid Gantt chart files (.mmd, .mermaid)

9. **Export Projects**
   - Click "Export Mermaid" to export project to Mermaid format
   - Click "Export PNG" to export Gantt chart as PNG image
   - Click "Export PDF" to export Gantt chart as PDF document
   - Click "Export XLSX" to export all tasks to Excel format

10. **Undo/Redo**
    - Click "Undo" to revert the last action
    - Click "Redo" to reapply the last undone action
    - Buttons are disabled when no actions are available
    - Supports undo/redo for: adding tasks, removing tasks, updating tasks, editing project info, setting dependencies

### Keyboard Shortcuts
- **Double-click** on tasks to edit
- **Drag and drop** to set dependencies
- **Toggle Theme** button to switch between light/dark modes

## Sample Data

The application starts with a complete sample project with tasks and subtasks:

1. **Project Planning** (3 days) - Blue
   - **Requirements Gathering** (Sub-Task, 1 day) - Purple
2. **Design Phase** (7 days, depends on Planning) - Green
   - **UI Mockups** (Sub-Task, 3 days) - Dark Purple
3. **Design Review** (Milestone, depends on Design) - Red
4. **Implementation** (10 days, depends on Design, 30% complete) - Orange
5. **Testing** (5 days, depends on Implementation + Design Review) - Purple
6. **Deployment** (3 days, depends on Testing) - Teal

## Data Models

### Task
- `id`: Unique identifier
- `name`: Task name
- `start_date`: Start date
- `end_date`: End date (None for milestones)
- `progress`: Completion percentage (0-100)
- `dependencies`: List of task IDs this task depends on
- `color`: Hex color for visualization
- `is_milestone`: Boolean flag for milestones
- `task_type`: Type of task - 'Task' or 'Sub-Task'
- `parent_task_id`: ID of parent task (for Sub-Tasks only, None for regular Tasks)
- `duration_days`: Calculated property - number of days between start_date and end_date (inclusive)

### Project
- `name`: Project name
- `tasks`: List of Task objects
- `start_date`: Earliest start date
- `end_date`: Latest end date

## File Formats

### JSON Format
Projects are saved as JSON files with the following structure:
```json
{
  "name": "Project Name",
  "tasks": [
    {
      "id": "task-uuid",
      "name": "Task Name",
      "start_date": "2024-01-01T00:00:00",
      "end_date": "2024-01-07T00:00:00",
      "progress": 0,
      "dependencies": [],
      "color": "#1f6aa5",
      "is_milestone": false,
      "task_type": "Task",
      "parent_task_id": null
    },
    {
      "id": "subtask-uuid",
      "name": "Sub-Task Name",
      "start_date": "2024-01-01T00:00:00",
      "end_date": "2024-01-03T00:00:00",
      "progress": 0,
      "dependencies": [],
      "color": "#9b59b6",
      "is_milestone": false,
      "task_type": "Sub-Task",
      "parent_task_id": "task-uuid"
    }
  ],
  "start_date": "2024-01-01T00:00:00",
  "end_date": "2024-01-07T00:00:00"
}
```

### GAN Import
Supports GanttProject XML files:
- Tasks with start/end dates
- Milestones (tasks with 0 duration)
- Dependencies
- Custom colors

### MPP Import
Supports Microsoft Project files (when Tasklib or JPype+mpxj is available):
- Tasks and milestones
- Dependencies (predecessors)
- Progress tracking
- Dates and durations

### Mermaid Import/Export
Supports Mermaid Gantt chart format:
- Import: Parse Mermaid Gantt chart syntax with tasks, milestones, and dependencies
- Export: Generate valid Mermaid Gantt chart syntax from projects
- Supports date formats, durations, and "after" dependency syntax

### Gantt Chart Export (PNG/PDF)
Export the visual Gantt chart to image and document formats:
- **PNG Export**: High-resolution image export with configurable DPI
- **PDF Export**: Vector-based PDF export for printing and sharing
- Preserves all visual elements: tasks, milestones, dependencies, critical path

## Configuration

### Themes
The application uses CustomTkinter's theming system. You can switch between light and dark modes using the "Toggle Theme" button.

### Default Colors
- **Tasks**: `#1f6aa5` (Blue)
- **Milestones**: `#e74c3c` (Red)
- **Critical Path**: `#f39c12` (Orange)
- **Dependencies**: `#e74c3c` (Red)

## Key Technical Decisions

### 1. Matplotlib Integration
- Used `FigureCanvasTkAgg` for embedding in Tkinter
- Matplotlib dates handled via `matplotlib.dates`
- Custom date formatting for better readability

### 2. Drag-and-Drop Implementation
- Full tkinterdnd2 integration with enhanced drag-and-drop functionality
- Graceful fallback to basic Tkinter bindings when tkinterdnd2 not available
- Circular dependency prevention algorithm
- Visual feedback during drag operations
- Support for drag initiation, positioning, and drop events

### 3. MPP Import Flexibility
- Multiple import methods with automatic fallback
- Graceful degradation when libraries not available
- Clear error messages for users

### 4. Critical Path Calculation
- Simplified algorithm suitable for most projects
- Forward pass to calculate early start/finish dates
- Backward pass to identify critical tasks
- Visual highlighting in Gantt chart

### 5. Color Management
- Default colors for tasks and milestones
- Custom colors per task
- Critical path highlighting
- Color serialization in JSON

## Error Handling

### File Operations
- Graceful handling of missing files
- Proper error messages for JSON parsing
- Validation of datetime formats

### Import Operations
- Checks for library availability
- Clear error messages for users
- Fallback mechanisms where possible

### UI Operations
- Input validation for dates and numbers
- Confirmation dialogs for destructive operations
- Status bar feedback for user actions

## Testing

### Running Tests

Run all unit tests with:
```bash
python3 run_tests.py
```

Run specific test modules:
```bash
python3 run_tests.py test_models
python3 run_tests.py test_file_io
python3 run_tests.py test_gan_importer
python3 run_tests.py test_utils
```

### Test Coverage

Unit tests cover:
- ✅ **Models**: Task and Project classes, serialization, critical path calculation
- ✅ **File I/O**: JSON save/load, datetime handling, error cases
- ✅ **GAN Import**: XML parsing, date parsing, color mapping, dependencies
- ✅ **Utilities**: Project utilities, validation, edge cases

### Test Status
All modules import successfully and all tests pass:
- ✅ `gantt_app.models`
- ✅ `gantt_app.utils.file_io`
- ✅ `gantt_app.utils.gan_importer`
- ✅ `gantt_app.utils.mpp_importer`
- ✅ `gantt_app.views.task_list`
- ✅ `gantt_app.views.gantt_chart`
- ✅ `gantt_app.views.toolbar`
- ✅ `gantt_app.main`

## Known Limitations

1. **Drag-and-Drop**: Full tkinterdnd2 integration implemented with graceful fallback
2. **MPP Import**: Requires external libraries (Tasklib or JPype+mpxj)
3. **Performance**: Large projects (>100 tasks) may impact chart rendering
4. **Printing**: No built-in print/export functionality yet

## Future Enhancements

- [x] Full tkinterdnd2 integration
- [x] PDF/PNG export for Gantt charts
- [ ] GAN file export
- [ ] Resource management
- [ ] Timeline zoom/pan
- [ ] Filtering and grouping
- [x] Undo/Redo functionality
- [ ] Multiple projects support
- [ ] Settings/preferences dialog

---

**Project Status**: Active Development
**Version**: 1.0.0
**Last Updated**: 2026-08-13
