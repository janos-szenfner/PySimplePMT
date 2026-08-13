# PySimplePMT - Gantt Project Management Tool

A cross-platform desktop application for project management with Gantt chart visualization, drag-and-drop task management, and support for importing MS Project, GanttProject, Mermaid and Excel files.

## Overview

This is a complete implementation of a project management tool with:
- Interactive Gantt chart visualization
- Drag-and-drop task list for dependency management
- Support for milestones (single-date tasks)
- JSON storage and file import for GAN/MPP/Mermaid files
- Modern UI using CustomTkinter

## Features

- **Interactive Gantt Chart Visualization**: Visual representation of tasks and milestones with dependency arrows, using Plotly for zoom, pan, and hover tooltips
- **Drag-and-Drop Task List**: Reorder tasks and set dependencies by dragging
- **Milestone Support**: Special single-date markers with diamond icons
- **JSON Storage**: Save and load projects in JSON format
- **File Import**: Import from GanttProject (.gan), MS Project (.mpp), Mermaid (.mmd), and Excel (.xlsx) files
- **Hierarchy on Import**: Source-file grouping (Mermaid sections, spreadsheet phases, nested GanttProject tasks) is preserved as parent tasks with sub-tasks
- **File Export**: Export Gantt charts to PNG and PDF formats, projects to Mermaid format, and tasks to Excel XLSX
- **Modern UI**: Built with CustomTkinter for a professional look
- **Critical Path**: Automatic calculation and visualization of the critical path
- **Log Viewer**: A "Log" button opens the application log for troubleshooting, with no console needed
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
│   ├── gantt_chart.py     # Interactive Plotly Gantt chart
│   ├── ganttsettingsw.py  # Gantt chart appearance settings dialog
│   ├── log_window.py      # Application log viewer
│   └── toolbar.py         # Action buttons and file operations
│
├── utils/
│   ├── __init__.py
│   ├── file_io.py          # JSON save/load functionality
│   ├── gan_importer.py     # GAN (GanttProject) file import
│   ├── mpp_importer.py     # MPP (MS Project) file import
│   ├── mermaid_importer.py # Mermaid (.mmd) file import
│   ├── mermaid_exporter.py # Mermaid (.mmd) file export
│   ├── xlsx_importer.py    # Excel XLSX project plan import
│   ├── log.py              # Application logging (file, memory, stderr)
│   ├── chart_figure.py     # Shared Plotly figure builder
│   ├── image_export.py     # PNG, PDF, SVG and HTML export
│   ├── chart_render.py     # Browser-free static chart drawing
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
- **EditTaskDialog**: Comprehensive task editing interface with all fields visible
- **CreateTaskDialog**: New dialog for creating tasks, sub-tasks, and milestones with all fields in a single popup
- **Treeview Display**: ID, Name, Type, Duration (Days), Start Date, End Date, Progress, Dependencies, Milestone
- **Hierarchical Display**: Sub-tasks are visually indented under their parent tasks with tree structure
- **Features**:
  - Double-click to edit tasks
  - Create tasks with all fields visible at once (no more one-by-one input)
  - Circular dependency prevention (including parent-child relationships)
  - Milestone toggle with automatic end_date handling
  - Progress slider with percentage display
  - Dependency management via checkboxes (select multiple tasks and subtasks for all task types including milestones)
  - Task Type selection (Task or Sub-Task)
  - Parent Task display for sub-tasks
  - Duration calculation display

### Gantt Chart View (`views/gantt_chart.py`)
- **Interactive Visualization**: Built with Plotly for rich interactivity
- **Task Bars**: Horizontal bars colored by task.color
- **Milestone Diamonds**: Special diamond shapes for milestones
- **Dependency Lines**: Red dotted lines connecting dependent tasks
- **Critical Path**: Highlighted in orange
- **Hover Tooltips**: Detailed information on hover (name, dates, duration, progress, dependencies)
- **Zoom & Pan**: Built-in Plotly interactivity
- **Labels**: Task names displayed next to milestones
- **Date Formatting**: Proper date display with tick formatting
- **Empty State**: Helpful message when no tasks exist
- **Dynamic Sizing**: Chart height adjusts based on number of tasks

### Toolbar (`views/toolbar.py`)
The toolbar has been redesigned with dropdown menus for better organization:

- **Create**: Dropdown with Task, Sub-Task, Milestone
- **Project**: Dropdown with New Project, Load Project, Save Project
- **Import**: Dropdown with MPP, GAN, Mermaid, XLSX import
- **Export**: Dropdown with Mermaid, PNG, PDF, XLSX export
- **Edit**: Dropdown with Undo, Redo
- **View**: Dropdown with Project Info, Toggle Theme
- **Log**: Opens the application log window (dark yellow button)
- **Dialog Integration**: File dialogs, input validation, parent task selection for subtasks
- **Color Scheme**: All main buttons are blue with white text, dropdown items are dark green with white text, Log button is dark yellow with white text

### File I/O (`utils/file_io.py`)
- **JSON Serialization**: Handles datetime objects and None values
- **Save/Load**: Full project save and load functionality
- **Error Handling**: Graceful error handling for file operations

### GAN Importer (`utils/gan_importer.py`)
- **XML Parsing**: Uses xml.etree.ElementTree for GAN files
- **Namespace Handling**: Reads both GanttProject 3.x files (no namespace) and older namespaced files
- **Working-Day Calendar**: Replays the file's `<calendars>` block (weekend definition plus recurring and year-specific holidays) to turn each task's working-day duration into an end date, reproducing the dates GanttProject displays
- **Date Parsing**: Handles plain `YYYY-MM-DD` dates and legacy ISO 8601 timestamps
- **Nested Sub-Tasks**: Tasks nested inside other tasks are imported to any depth as Sub-Tasks with the correct parent
- **Dependency Direction**: `<depend>` names a *successor*, so edges are reversed onto the dependent task; the legacy `<depends-on><dependency idref=""/>` form is also supported
- **Milestones**: Detected from `meeting="true"` or a zero duration; summary tasks are never treated as milestones
- **Colors**: Reads the per-task `color` attribute, with an optional `<colors>` lookup table as a fallback

### Mermaid Importer (`utils/mermaid_importer.py`)
- **Syntax Parsing**: Parses Mermaid Gantt chart text format
- **Task Extraction**: Extracts tasks, milestones, and dependencies
- **Section Grouping**: Each `section` becomes a parent task and its tasks become Sub-Tasks (disable with `MermaidImporter(group_by_section=False)`)
- **Frontmatter**: An optional `---` delimited YAML config block is stripped before parsing
- **Directives**: `title`, `dateFormat`, `axisFormat`, `excludes`, `todayMarker` and similar lines are skipped
- **Date Handling**: Supports various date formats with automatic detection
- **Inclusive Durations**: A `5d` task starting on the 1st ends on the 5th, and a dependent task starts the day after its predecessor finishes
- **Dependency Resolution**: Calculates task dates based on "after" dependencies

### XLSX Importer (`utils/xlsx_importer.py`)
- **Header-Driven**: Locates the task table by scoring rows against known column names, so a title block above the table is fine
- **Column Aliases**: Recognises common English and Hungarian headers (`Task`/`Feladat`, `Start`/`Kezdés`, `Pred.`/`Előzmény`, `Duration (wd)`/`Munkanap`, …)
- **Date Handling**: Reads real datetimes, Excel day serial numbers, and common date strings; formula columns are read from their cached values
- **Duration Fallback**: Derives a missing end date from the duration, skipping weekends when the column is labelled in working days
- **Phase Grouping**: Each distinct Phase value becomes a parent task (disable with `XLSXImporter(group_by_phase=False)`); an explicit `Parent Task` column takes precedence
- **Dependencies**: Splits multi-predecessor cells (`6;7`), resolves references by ID or by task name, ignores `–`/`n/a` placeholders, and drops references to tasks that are not present
- **Progress**: Taken from a Progress column, or mapped from Status text (`Done` → 100, `Ongoing` → 50, `Not started` → 0)
- **Optional Dependency**: Requires openpyxl, and reports a clear error when it is missing

### Mermaid Exporter (`utils/mermaid_exporter.py`)
- **Syntax Generation**: Creates valid Mermaid Gantt chart syntax
- **Topological Sorting**: Orders tasks based on dependencies
- **Section Output**: Parent tasks are written as `section` headers rather than as tasks, so hierarchy survives an export/import round-trip; tasks are grouped so each header appears once
- **ID Generation**: Creates valid Mermaid IDs from task names
- **Date Formatting**: Uses YYYY-MM-DD format for maximum compatibility

Note that Mermaid sections do not nest, so a hierarchy deeper than two levels
collapses onto its top-level ancestor on export. The full parent chain is
preserved in the project's own JSON format.

`MermaidExporter` in `mermaid_importer.py` is a backwards-compatible wrapper
that delegates here, so the two cannot drift apart.

### PNG Exporter (`utils/png_exporter.py`)
- **High-Quality Export**: Creates PNG images with configurable DPI (default 300)
- **Browser-Free**: Drawn with Pillow; nothing is downloaded and no browser is involved
- **Automatic Scaling**: Properly scales chart elements for image output
- **Directory Creation**: Automatically creates parent directories

### PDF Exporter (`utils/pdf_exporter.py`)
- **Vector Export**: Creates PDF documents with crisp, scalable graphics
- **Browser-Free**: Drawn with Pillow at 150 dpi; export to SVG for scalable output
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
- **Pure Python**: Uses the Tasklib reader; no Java runtime involved
- **Optional Dependency**: Absent Tasklib disables MPP import and is reported at info level, not as an error
- **Date Conversion**: Java Date to Python datetime
- **Task Properties**: Full task import with dependencies and progress
- **Error Handling**: Graceful degradation when libraries not available

### Logging (`utils/log.py`)
- **Three Destinations**: A rotating log file on disk, an in-memory buffer for the Log window, and stderr when started from a terminal
- **Log Window**: The "Log" button in the toolbar opens `views/log_window.py`, with level filtering, auto-refresh, and Copy / Save As / Clear actions
- **Why In-Memory**: A packaged desktop build has no console, so anything printed to stdout is lost. The bounded buffer (5000 records) is what makes errors visible to a user who can't run the app from a terminal
- **Full Tracebacks**: Import and export failures are logged with `logger.exception`, so the stack trace is captured rather than just the message
- **Uncaught Exceptions**: `install_exception_hook()` routes anything that escapes into the log before the app dies
- **Never Fatal**: Logging degrades to memory-and-stderr if the log directory cannot be written; it never prevents startup

Log file locations:

| Platform | Path |
|---|---|
| Linux | `$XDG_STATE_HOME/pysimplepmt/` (default `~/.local/state/pysimplepmt/`) |
| macOS | `~/Library/Logs/PySimplePMT/` |
| Windows | `%LOCALAPPDATA%\PySimplePMT\logs\` |

Print the active path with `pysimplepmt --log-file`.

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
pip install customtkinter plotly tkinterweb pillow openpyxl
```

Or install everything from the requirements file:
```bash
pip install -r requirements.txt
```

`openpyxl` is required for Excel XLSX import and export. Without it the app
still runs, but the Import XLSX and Export XLSX actions report an error.

### Optional Dependencies
```bash
# For GAN file import (included in standard library)
pip install lxml  # For better XML parsing performance

# For MPP file import
pip install tasklib  # Pure Python MPP reader

# For enhanced drag-and-drop (recommended)
pip install tkinterdnd2
```

## Usage

### Installing on Ubuntu / Debian

Download the `.deb` from the [Releases page](../../releases) and install it:

```bash
sudo apt install ./pysimplepmt_1.0.0_amd64.deb
```

The package is **self-contained**: the Python interpreter, the Tcl/Tk runtime
and every third-party library are bundled, so no Python installation and no
pip packages are required. See [packaging/README.md](packaging/README.md) for
what it does still rely on and how it is built.

### Running the Application
```bash
# Method 1: Run directly
python3 run.py

# Method 2: Run from the gantt_app directory
python3 -m gantt_app.main

# Installed from the .deb
pysimplepmt
```

Command line options:

```bash
pysimplepmt --version       # print the version
pysimplepmt --self-check    # verify every dependency imports
pysimplepmt --log-file      # print the log file path
```

### Basic Operations

1. **Create a New Project**
   - Click "New Project" button
   - Enter project name
   - Start adding tasks and milestones

2. **Add Tasks**
   - Click **Create** dropdown menu and select "Task..."
   - Enter task name and duration in days
   - Set start date and other properties

3. **Add Sub-Tasks**
   - Click **Create** dropdown menu and select "Sub-Task..."
   - Enter subtask name and duration in days
   - Select a parent task from the list (must have at least one task)
   - Any task can be the parent, **including an existing sub-task**, so hierarchies can go deeper than two levels
   - The list is indented to show how deep each candidate sits
   - Milestones are not offered as parents (they are single-date markers with no span)
   - Sub-tasks automatically inherit the start date from their parent
   - Sub-tasks appear indented under their parent in the task list

4. **Add Milestones**
   - Click **Create** dropdown menu and select "Milestone..."
   - Enter milestone name and date
   - Milestones appear as diamonds in the Gantt chart

5. **Set Dependencies**
   - Drag a task onto another task in the task list
   - Or edit dependencies in the task edit dialog (select multiple tasks and subtasks as dependencies)
   - Dependencies appear as red arrows in the Gantt chart
   - Cannot create circular dependencies (a task cannot depend on itself or its own subtasks)

6. **Edit Tasks**
   - Double-click on a task in the task list
   - Modify properties, dependencies, and colors
   - Save changes or delete the task

7. **Save Project**
   - Click **Project** dropdown menu and select "Save Project..."
   - Choose file location and name
   - Project is saved in JSON format

8. **Load Project**
   - Click **Project** dropdown menu and select "Load Project..."
   - Select a previously saved JSON file

9. **Create New Project**
   - Click **Project** dropdown menu and select "New Project..."
   - Enter project name
   - Start adding tasks and milestones

10. **Import Projects**
    - Click **Import** dropdown menu and select the format:
    - "MPP..." to import MS Project files (requires Tasklib)
    - "GAN..." to import GanttProject files
    - "Mermaid..." to import Mermaid Gantt chart files (.mmd, .mermaid)
    - "XLSX..." to import an Excel project plan (requires openpyxl)
    - Importing replaces the current project and clears the undo/redo history

11. **Export Projects**
    - Click **Export** dropdown menu and select the format:
    - "Mermaid..." to export project to Mermaid format
    - "PNG..." to export Gantt chart as PNG image
    - "PDF..." to export Gantt chart as PDF document
    - "XLSX..." to export all tasks to Excel format

12. **Undo/Redo**
    - Click **Edit** dropdown menu and select "Undo" to revert the last action
    - Click **Edit** dropdown menu and select "Redo" to reapply the last undone action
    - Menu items are disabled when no actions are available
    - Supports undo/redo for: adding tasks, removing tasks, updating tasks, editing project info, setting dependencies

13. **View Project Information**
    - Click **View** dropdown menu and select "Project Info"
    - Edit the project name

14. **Toggle Theme**
    - Click **View** dropdown menu and select "Toggle Theme"
    - Switch between light and dark modes

15. **View the Log**
    - Click the **Log** button in the top right (dark yellow button)
    - Filter by level, auto-refresh, and copy or save the log to a file
    - Import and export failures appear here with full tracebacks
    - The log is also written to a file; see the Logging section for its location

### Keyboard Shortcuts
- **Double-click** on tasks to edit
- **Drag and drop** to set dependencies
- Use **View** dropdown menu and select "Toggle Theme" to switch between light/dark modes

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
Supports GanttProject XML files (`.gan`), as written by GanttProject 3.x and
earlier namespaced versions:
- Tasks scheduled as a start date plus a working-day duration
- End dates computed against the file's weekend and holiday calendar
- Milestones (`meeting="true"` or zero duration)
- Sub-tasks nested to any depth
- Dependencies, reversed from GanttProject's successor-based `<depend>` elements
- Custom colors

Note that GanttProject stores durations in working days and never writes an end
date, so the `<calendars>` block is what makes the imported dates line up with
what GanttProject shows. Holidays declared with an empty `year` recur annually.

### XLSX Import
Supports spreadsheet project plans (`.xlsx`, `.xlsm`). The importer finds the
task table by its header row rather than by fixed positions, so a title block
above the table and extra columns beside it are both fine.

Recognised columns (any subset; a task/name column plus a start date or
duration is the minimum):

| Column | Purpose |
|---|---|
| ID / Azonosító | Task identifier used by the predecessor column |
| Task / Name / Feladat | Task name (**required**) |
| Phase / Section / Fázis | Grouping - becomes a parent task |
| Parent Task | Explicit parent, used instead of Phase grouping |
| Start / Kezdés | Start date |
| End / Befejezés | End date |
| Duration / Duration (wd) / Munkanap | Duration; `wd` headers skip weekends |
| Pred. / Predecessors / Előzmény | Dependencies, e.g. `6;7` |
| Progress (%) / Készültség | Completion percentage |
| Status / Státusz | Mapped to progress when no Progress column exists |
| Milestone / Type / Color | Milestone flag, task type, bar colour |

Files produced by this application's own XLSX export can be read back, since
its `ID` / `Name` / `Parent Task` / `Start Date` / `End Date` headers are
recognised too. The round-trip is lossless: task count, project name (read
from the `Project Name:` label on the Summary sheet), dates, progress,
milestone flags, colours, dependencies and hierarchy all survive.

Dependencies are exported as task **names**. The importer therefore tries the
whole cell as a single name before splitting it, so a task called
"Analysis, phase 2" is not torn in half. Only `;`, `,` and `|` separate
references - `/` does not, because names such as "Education / training"
contain one.

### MPP Import
Supports Microsoft Project files (when Tasklib is available):
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
- Longest chain of dependent tasks, ending at the task that finishes last
- Measured by **accumulated duration**, not by comparing calendar dates: plans
  scheduled in working days leave weekend and holiday gaps between a task and
  its successor, and a date-based comparison reads those gaps as slack, which
  drops most of the chain
- Summary tasks are excluded from the chain, but a dependency **on** a summary
  task resolves to the work inside it, so grouping does not sever the network
- Ties on the finish date are broken by chain length, so the path always
  reaches the project's real finish
- Cycle-safe and iterative, so deep chains cannot exhaust recursion
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
python3 run_tests.py test_mermaid_importer
python3 run_tests.py test_xlsx_importer
python3 run_tests.py test_gantt_export
python3 run_tests.py test_task_hierarchy
python3 run_tests.py test_log
python3 run_tests.py test_undoredo
python3 run_tests.py test_utils
```

### Test Coverage

Unit tests cover:
- ✅ **Models**: Task and Project classes, serialization, critical path calculation
- ✅ **File I/O**: JSON save/load, datetime handling, error cases
- ✅ **GAN Import**: Real GanttProject 3.x fixtures - working-day calendar, nested sub-tasks, successor-to-predecessor edge reversal, milestones, colors, namespaced files
- ✅ **Mermaid Import/Export**: Inclusive durations, dependency chains, section grouping, frontmatter, round-trip
- ✅ **XLSX Import**: Header detection, column aliases, Excel serial dates, working-day durations, phase grouping, dependency resolution, lossless export round-trip
- ✅ **Task Hierarchy**: Three-level sub-task creation, parent candidate ordering, cycle safety
- ✅ **Logging**: Buffer capacity and filtering, file output, failure paths, importer errors reaching the log
- ✅ **Gantt Export**: PNG and PDF rendering
- ✅ **Undo/Redo**: Command stack behaviour
- ✅ **Utilities**: Project utilities, validation, edge cases

The GAN fixtures deliberately mirror the format GanttProject actually writes.
An earlier version of these tests used an invented schema, which let the
importer pass its whole suite while reading zero tasks from real `.gan` files.

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
2. **MPP Import**: Requires the optional Tasklib package and is not bundled into the packaged build
3. **Performance**: Large projects (>100 tasks) may impact chart rendering
4. **Critical Path**: Returns the single longest chain rather than every zero-float task, so parallel critical activities are not all highlighted
5. **XLSX Import**: Reads cached formula results, so a workbook generated without a calculation pass will have empty date columns
6. **GAN Import**: Dependency lag (`difference`) and non finish-start dependency types are read but not yet applied to the schedule

## Future Enhancements

- [x] Full tkinterdnd2 integration
- [x] PDF/PNG export for Gantt charts
- [x] XLSX import
- [x] Application log viewer
- [ ] **Shared working-day calendar model** (see below)
- [ ] GAN file export
- [ ] Apply GAN dependency lag and SS/FF/SF dependency types
- [ ] Resource management
- [ ] Timeline zoom/pan
- [ ] Filtering and grouping
- [x] Undo/Redo functionality
- [ ] Multiple projects support
- [ ] Settings/preferences dialog

### Planned: shared working-day calendar model

Today the notion of a working day exists in two places and belongs to neither:
`GanttProjectCalendar` in `gan_importer.py`, which replays the weekend and
holiday rules from a `.gan` file, and a weekends-only helper in
`xlsx_importer.py` used when a spreadsheet gives a duration but no end date.
The application core has no calendar at all, so anything created or edited in
the app is scheduled in plain calendar days.

The plan is to promote this into a first-class model - roughly
`utils/calendar.py`, with a `WorkCalendar` owned by the `Project` and
serialised alongside it:

- **One definition of a working day**: a weekend rule plus a holiday list,
  populated from whichever file was imported and editable afterwards.
- **Calendar-aware scheduling**: adding or dragging a task lands on working
  days, so a plan imported from GanttProject keeps its shape when edited
  rather than drifting onto weekends.
- **Round-trip fidelity**: GanttProject durations are working days. Without a
  calendar in the model, exporting back to `.gan` cannot reconstruct the
  durations the file started with.
- **Full critical path analysis**: this is the blocker for proper CPM float.
  A backward pass computing late start/finish needs to measure slack in
  *working* days; measured in calendar days, the weekend between a task
  finishing on Friday and its successor starting on Monday reads as two days
  of float, and almost every task falls off the critical path. That is why
  `get_critical_path()` currently uses accumulated duration along the longest
  chain instead, and why it returns a single chain rather than every
  zero-float task.
- **Holiday presets**: GanttProject ships regional calendars (the sample file
  carries a Hungarian one); the same list could be offered when starting a
  project from scratch.

---

**Project Status**: Active Development
**Version**: 1.0.0
**Last Updated**: 2026-08-13
