# PySimplePMT - Gantt Project Management Tool

A cross-platform desktop application for project management with Gantt chart visualization, drag-and-drop task management, and support for importing MS Project, GanttProject, Mermaid and Excel files.

## Overview

This is a complete implementation of a project management tool with:
- Interactive Gantt chart visualization
- Drag-and-drop task list for arranging the plan by hand
- Support for milestones (single-date tasks)
- JSON storage and file import for GAN/MPP/Mermaid files
- Modern UI using CustomTkinter

## Features

- **Gantt Chart**: Tasks, milestones and dependency arrows, drawn with Pillow so nothing is downloaded and no browser is involved. Zoom in, out, Fit and Reset beneath it
- **Drag-and-Drop Task List**: Reorder tasks by dragging a row — a thin blue line shows where it will land — or from the right-click menu (Move to top / up / down / bottom)
- **Foldable Hierarchy**: A task with sub-tasks shows an expander; double-click any row to fold its branch away
- **Milestone Support**: Special single-date markers with diamond icons
- **JSON Storage**: Save and load projects in JSON format
- **File Import**: Import from GanttProject (.gan), MS Project (.mpp), Mermaid (.mmd), and Excel (.xlsx) files
- **Hierarchy on Import**: Source-file grouping (Mermaid sections, spreadsheet phases, nested GanttProject tasks) is preserved as parent tasks with sub-tasks
- **File Export**: Export Gantt charts to PNG and PDF formats, projects to Mermaid format, and the plan to Excel XLSX as a live project-plan sheet - editable durations, WORKDAY dates and a week-by-week bar chart
- **Work Item Hierarchy**: Phase > Deliverable > Task > Subtask, with milestones at any level. Indenting and outdenting keep a task's type wherever the new parent can hold it, so a Task moved under a Deliverable stays a Task
- **Modern UI**: Built with CustomTkinter for a professional look
- **Native Dialogs**: Message boxes and file choosers use the platform's own on macOS and Windows. On Linux, where Tk draws its own, message boxes are rebuilt to match the window and file choosers hand off to zenity or kdialog when present
- **Rows that line up**: the chart draws the rows the task list is showing, in its order and at its row height, so a bar sits on the line of the task it belongs to. Fold a branch away and its bars go with it; scroll the list and the chart follows
- **Critical Path**: Automatic calculation and visualization of the critical path
- **Dependency Types**: Finish-Start, Start-Start, Finish-Finish and Start-Finish, each with lead/lag in **working** days and Hard/Rubber link hardness. A start link and a finish link on the same task state a span - Start-Start onto the first task and Finish-Finish onto the last makes a row cover the stretch between them, and its duration follows from the two dates rather than being carried over. A hard link pins a date but still has to clear any rubber floor set by another link
- **Earliest Begin Date**: a floor on when a task's work can start, applied alongside the links and the working calendar
- **Built-in Help**: A Help button on the task editor and on the Dependency tab opens a full reference - the fields of the form in one, link types, lead/lag and hardness in the other
- **Checked as you type**: The task editor outlines a name or a date it cannot use and says why beneath the form, rather than waiting for Save
- **Auto-Scheduling**: Moving a task drags whatever depends on it, so links stay satisfied
- **Working-Day Calendar**: A duration is working effort, so a task crossing a weekend keeps its length and its bar reaches further out. Nothing is ever scheduled to start or finish on a Saturday, and a plan imported from a file that declared holidays keeps them
- **EU Public Holidays**: Actions → EU Holidays... picks any of the 27 member states, and a date that is a public holiday in *any* of them becomes a non-working day. Easter Monday and the rest of the movable feasts are worked out per year, so a task spanning one is pushed out rather than losing the work planned for it
- **Work Item Types**: Phase, Deliverable, Task, Subtask and Milestone, each with its own colour, and dates and progress that roll up through the levels
- **Summary Roll-Up**: Anything with children spans them, and completion works its way up the four levels. A Subtask is a tick box; a Task reads how many of its sub-tasks are ticked, or keeps the percentage typed on it when it has none; a Deliverable weights its tasks by how long they run; a Phase averages its deliverables evenly. An empty container reads 0%
- **Copy, Cut and Paste act on what you selected**: from the right-click menu, the Edit menu or Ctrl/Cmd+C, X and V. Copying a phase copies the phase row, not the work underneath it; cut rows are greyed until they are pasted, and what arrives lands beside the row you pasted from and is left selected. Paste is offered only where the item belongs - a phase does not go inside a task. Copied rows reach the desktop clipboard too, as a readable list that pastes into anything
- **Scheduling Modes**: Choose which of the start date, end date and duration the form works out from the other two; the calculated one fills itself in as you type, counted in working days
- **Menu bar and action bar**: a menu bar naming everything the application does, and an action bar of drawn icons under it for the handful worth reaching for directly. The icons are drawn rather than set as emoji, so they need no font installed
- **Log Viewer**: A "Log" button opens the application log for troubleshooting, with no console needed

## Project Structure

```
gantt_app/
├── __init__.py
├── models.py              # Task and Project data models
├── workdaycalendar.py     # Working days, weekends and holidays
├── main.py                # Main application entry point
├── run.py                 # Entry point script
│
├── views/
│   ├── __init__.py
│   ├── task_list.py       # Drag-to-reorder task list
│   ├── taskform.py        # The task form shared by creating and editing
│   ├── taskdialogs.py     # The Create Task and Edit Task dialogs
│   ├── formcheck.py       # Checks the task form as it is filled in
│   ├── scrollframe.py     # Scrolling container the task form is built in
│   ├── contextmenu.py     # Right-click move/edit/delete menu for the task list
│   ├── colorpicker.py     # Color picker with popup for task dialogs
│   ├── datepicker.py      # Date box with a calendar, used by the task dialogs
│   ├── dialogs.py         # Message boxes and file choosers, native per platform
│   ├── dependency_editor.py # Dependency tab shared by the task dialogs
│   ├── holidaydialog.py   # Picks whose public holidays the plan observes
│   ├── gantt_chart.py     # The Gantt chart pane, drawn beside the task list
│   ├── ganttsettingsw.py  # Gantt chart appearance settings dialog
│   ├── log_window.py      # Application log viewer
│   ├── modal.py           # Makes a dialog modal once the window manager shows it
│   └── toolbar.py         # The menu bar and the icon action bar
│
├── help/
│   ├── __init__.py
│   ├── reference.py       # The window both Help buttons open
│   ├── editorhelp.py      # Task editor reference behind its Help button
│   └── dependencyhelp.py  # Dependency reference behind the Help button
│
├── priority.py            # The priority levels a work item can carry
│
├── resources/
│   ├── __init__.py
│   ├── appicon.py          # The application icon, drawn rather than shipped
│   └── icons.py            # The toolbar's icons
│
├── utils/
│   ├── __init__.py
│   ├── copypastecut.py     # The clipboard behind Copy, Cut and Paste
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
│   └── xlsx_exporter.py    # Excel XLSX export as a live plan sheet
│
└── assets/                # Bundled into the packaged build when it holds anything
```

Alongside it, `packaging/` holds the builds for both platforms:
`build_deb.sh` and the desktop entry for Linux; `build_dmg.sh`,
`make_icns.py` and `README-macOS.md` for macOS; the PyInstaller spec, which
produces the one-directory bundle both wrap and the `.app` on macOS; and
`make_icon.py`, which writes the icon above out at each size the Linux
desktop asks for.

## Implemented Features

### Core Data Models (`models.py`)
- **Task Class**: id, name, task_type, start_date, end_date, duration, progress, dependencies, color, is_milestone, parent_task_id, priority, shape, show_in_timeline, earliest_begin, scheduling_options, details
- **Work Item Types**: `Phase`, `Deliverable`, `Task`, `Subtask`, `Milestone`. `Phase` and `Deliverable` are containers, taking their dates and progress from what is inside them; `Subtask` and `Milestone` hold nothing. The older hyphenated `Sub-Task` is rewritten to `Subtask` when a task is built, so plans saved by earlier versions load unchanged
- **The Levels, and Moving Between Them**: the types describe a four-level plan, `Phase > Deliverable > Task > Subtask`, with a `Milestone` allowed at any level. `child_type_for()` decides what a task becomes when it is moved, and it keeps the task's own type wherever the new parent can hold it: a `Task` indented under a `Deliverable` **stays a `Task`**, and so keeps being able to hold sub-tasks of its own. Only a type the parent cannot hold is changed - a `Task` under another `Task` becomes a `Subtask`, a `Subtask` lifted into a `Phase` becomes a `Task` - and a `Milestone` stays a milestone wherever it lands. Creating a task under a parent settles it the same way, so indenting and creating agree
- **Project Class**: name, tasks, start_date, end_date, calendar
- **Methods**: add_task, remove_task, get_task_by_id, get_dependencies, get_dependents, move_task, move_task_before, next_task_id
- **Completion Roll-Up**: `rolled_up_progress()` gives each level its own rule - see *Completion* below - and `roll_up_summaries()` applies it deepest-first, so ticking one sub-task reaches the phase above it in the same pass
- **Serialization**: to_dict(), from_dict() for JSON compatibility
- **Critical Path**: get_critical_path() algorithm for project analysis
- **Factory Methods**: create_task(), create_milestone() for easy object creation

### The Working Day Calendar (`workdaycalendar.py`)

A plan has two different notions of "days", and conflating them is what makes a
schedule wrong over a weekend:

| | What it measures |
| --- | --- |
| **Working days** (`Task.duration_days`) | The effort a task holds. A weekend does not change it |
| **Calendar days** (`Task.total_elapsed_days`) | How far apart its two ends sit. A weekend stretches it, and this is the span the chart draws |

A duration is stated in the first and drawn in the second. The rules:

1. **The calendar** names the non-working weekdays - Saturday and Sunday by
   default - plus any holidays: fixed dates, dates recurring every year, and
   the public holidays of any countries the project observes (see below). It
   belongs to the project and is saved with it, so a plan imported from a
   GanttProject file keeps the holidays that file declared.
2. **A finish is walked, not added.** Starting at the start date, the calendar
   is stepped through a day at a time and one day of duration is spent only on
   a working day.
3. **A weekend is crossed for free.** A task reaching one pauses on the
   Saturday and resumes on the Monday, finishing further out in calendar time
   without holding any more work. Five days from a Thursday ends on the
   following Wednesday.
4. **A task cannot start on a day nobody works.** One scheduled or moved onto a
   Saturday starts on the Monday instead.

`Project.enforce_working_calendar()` applies rules 3 and 4 to the whole plan,
and runs inside `reschedule()` so a task moved by a dependency link lands on
working days too. It reads the duration before either date moves and writes it
back afterwards, which is what makes it leave the effort alone: the task ends
up somewhere else in calendar time holding exactly the work it held. Running it
twice changes nothing, which is what lets it sit inside the reschedule loop.

Everything that turns a duration into dates goes through it - the task form's
three scheduling modes, the dependency scheduler, and the GanttProject,
spreadsheet and Mermaid importers - so the same plan comes out with the same
dates whichever way it arrived.

#### Public holidays across the EU (`views/holidaydialog.py`)

**Actions → EU Holidays...** opens a picker listing the 27 member states, with
All and Clear buttons for the whole list. The selection is saved with the
project.

The rule is the **union**: a date that is a public holiday in *any* selected
country is a non-working day for the plan. That is what a project worked in
several countries at once needs - work does not happen on a day half the team
is off. Selecting nothing leaves the plan on weekends alone.

Holidays are resolved a calendar year at a time through the
[`holidays`](https://pypi.org/project/holidays/) package, which is why the
Easter-dependent ones - Good Friday, Easter Monday, Whit Monday - and the
substitutions several member states make when a holiday falls on a weekend all
come out right without anything being listed by hand. What is stored is the
country codes, not the dates: a plan reopened in a later year needs that year's
holidays, and a list worked out today would run out.

Applying a selection goes through `Project.set_holiday_countries()`, which reads
every task's working duration under the *old* calendar and rebuilds its dates
under the new one. A day that has just become a holiday therefore pushes
finishes out rather than quietly eating the work that was planned for it - ten
days of work stay ten days of work. Changing the selection back moves the plan
back, which is how the change is undone; it is not on the undo stack.

`holidays` is an optional dependency, like openpyxl for the spreadsheets.
Without it the picker still opens and still saves the selection - so a plan
carrying one is not silently emptied - but it says on the face of it that the
choice takes effect once the package is installed, and the plan is scheduled on
weekends alone until then.

### Completion

Each level counts what is under it in the way that suits what that level is:

| Level | How its completion is worked out |
| --- | --- |
| **Subtask** | A tick box: done or not, nothing in between. The editor offers a checkbox rather than a percentage |
| **Task** | With sub-tasks, how many are ticked - counted, not weighted, a checklist being a checklist. Without, the percentage typed on it |
| **Deliverable** | Its tasks weighted by how long they run, so a fortnight counts for more than an afternoon. With nothing to weight by - all milestones, say - a plain average |
| **Phase** | Its deliverables averaged evenly. One being longer is not a reason for it to count for more |
| **Empty container** | 0%. No work under it, none of it done |

Percentages are clamped as they are read, so a child carrying something
outside 0 to 100 - which nothing writes, but an imported file can hold -
cannot pull its parent outside it either.

### Task List View (`views/task_list.py`)
- **Drag-and-Drop**: Rows are reordered by dragging, in plain Tkinter. A row moves within its own set of siblings, so a sub-task stays under its parent, and a thin blue line marks the edge it would drop against
- **Context Menu** (`views/contextmenu.py`): Right-click (two-finger click on macOS) any row for Move to top / up / down / bottom, Indent and Outdent, a Create submenu (Phase, Deliverable, Task, Subtask, Milestone), Edit and Delete, Copy, Cut and Paste, then Undo and Redo; entries that would do nothing are greyed out. Deleting asks first, says how many sub-tasks go with the task, and is undoable. Right-clicking a row that is already part of a multi-row selection keeps the whole selection, so Copy and Cut act on all of it
- **Create at a Row**: Create builds the chosen type at the row the menu was opened on — a sub-task inside it, a task or milestone beside it — rather than at the end of the plan. Right-clicking the empty space below the last row opens the menu too, and creates at the end of the plan
- **Indent / Outdent**: Indent moves a task under the row above it; outdent lifts it beside its parent. It keeps its own type wherever the new parent can hold it - a `Task` indented under a `Deliverable` stays a `Task` - and only takes a new one where the old is not a level that parent can hold; see *The Levels, and Moving Between Them* above. A branch moves as a whole, and both are undoable
- **EditTaskDialog** (`views/taskdialogs.py`): The task form over an existing task. Buttons read Help and Delete (set apart), then Close, Save & Close, Save & New
- **CreateTaskDialog** (`views/taskdialogs.py`): The same form over a new one, for any of the five work item types
- **Treeview Display**: ID, Name, Type, Duration (Days), Start Date, End Date, Progress, Dependencies, Milestone. Columns keep whatever width they are dragged to, and the horizontal scrollbar reaches anything that no longer fits
- **Hierarchical Display**: Sub-tasks are visually indented under their parent tasks with tree structure
- **Cut rows are held apart**: a row waiting to be pasted somewhere is greyed until it lands
- **Features**:
  - Double-click a row to expand or collapse its sub-tasks; edit from the right-click menu
  - Create tasks with all fields visible at once (no more one-by-one input)
  - Circular dependency prevention (including parent-child relationships)
  - Milestone toggle with automatic end_date handling
  - Colour chosen from a popup palette, built the first time it is opened
  - Start and end dates picked from a calendar, or typed as YYYY-MM-DD
  - Save & Close, or Save & New to keep entering tasks without reopening the dialog
  - Dependencies set on the form's own Dependency tab, which is built the first time it is looked at
  - Parent Task display for sub-tasks

### The Task Form (`views/taskform.py`)

The form both dialogs show. The fields run down the left; the notes fill the
column beside them, having the height of the form to use rather than one line
under everything else.

- **Grouped fields**: name, ID, type and parent; then the dates, duration and
  milestone flag; then progress, priority, timeline visibility and shape; then
  the colour
- **Scheduling modes**: whichever of the start date, the end date and the
  duration the mode names is worked out from the other two and greyed out, and
  fills itself in as the other two are typed. Durations are inclusive, so a
  task running from the 1st to the 5th lasts five days
- **Checked as it is filled in** (`views/formcheck.py`): a name or a date that
  cannot be used is outlined, and the reason written on a line under the form
  which keeps its place whether or not it has anything to say. A box is only
  complained about for being empty once the user has been in it, so a new task
  does not open covered in red. Fields are watched through a variable rather
  than the keyboard, so a date arriving from the calendar or from a dependency
  is checked too
- **Help**: a Help button beside Delete opens a reference on the form's own
  fields (`help/editorhelp.py`)
- **Progress**: a percentage for most rows, a tick box for a sub-task, and
  nothing to fill in on a container that takes its own from its children
- **Built to be quick**: the form is built in a scrolling frame of the
  application's own (`views/scrollframe.py`) rather than CustomTkinter's, whose
  scrollbar forces a full layout pass of the window on every draw - 3.2ms a
  wheel notch against 0.11ms. The Dependency tab and the colour palette are
  both built the first time they are asked for

### Copy, Cut and Paste (`utils/copypastecut.py`)
- **Acts on the selection**: from the right-click menu, the Edit menu, or
  Ctrl/Cmd+C, X and V. Shortcuts stand aside while the focus is in a text box,
  so editing text behaves normally
- **What is selected is what is copied**: copying a phase copies the phase row.
  The work under it is not brought along and is not duplicated
- **Held to the levels of the plan**: a phase belongs at the top, a deliverable
  in a phase, a sub-task in a task. Paste is greyed out where an item does not
  belong, and a selection with one item that does not fit is refused whole
- **Lands where it was asked for**: pasted rows go directly after the row the
  menu was opened over, and are left selected. Pasting a task inside itself is
  refused
- **Numbered like the rest**: a pasted copy takes the next ID in the project's
  own sequence
- **Reaches the desktop clipboard**: through Tk's own, so it needs no extra
  package. What is written is a readable list of what was copied, then a
  marker, then the same thing as JSON - so it pastes into a mail as text and
  back into this application as tasks

### Gantt Chart View (`views/gantt_chart.py`)
- **Drawn, not downloaded**: The chart on screen is painted with Pillow
  (`utils/chart_render.py`). Plotly is still used to build the interactive
  figure behind the HTML export, but nothing is fetched and no browser is
  involved in showing a chart
- **Rows line up with the task list**: the chart draws the rows the list is
  showing, in its order and at its row height, so a bar sits on the line of the
  task it belongs to. Fold a branch away and its bars go with it; scroll the
  list and the chart follows. Because the grid beside it is already showing
  every name, the chart drops its own label column and gives the width to the
  bars - an exported chart, having no grid beside it, keeps them
- **Task Bars**: Horizontal bars colored by task.color
- **Milestone Diamonds**: Special diamond shapes for milestones
- **Dependency Lines**: Red dotted lines connecting dependent tasks
- **Critical Path**: Highlighted in orange
- **Hover Tooltips**: Detailed information on hover (name, dates, working duration, elapsed calendar days, progress, dependencies)
- **Zoom**: Zoom in, zoom out, Fit and Reset buttons beneath the chart. Fit scales the chart to exactly the width available so nothing scrolls; Reset returns to 100%, where a long plan is drawn wider than the pane to keep it readable
- **Phase Bars**: A `Phase` is drawn as a solid bar ending in an arrow head pointing at its finish, whether or not anything hangs off it yet - it is the top of the plan, and the reader wants to see where it runs to
- **Summary Bars**: Any other task with sub-tasks - a `Deliverable`, or a plain `Task` with work under it - is drawn as a spanning bracket rather than a solid bar
- **Labels**: Task names displayed next to milestones
- **Date Formatting**: Proper date display with tick formatting
- **Empty State**: Helpful message when no tasks exist
- **Dynamic Sizing**: Chart height adjusts based on number of tasks

### Menu Bar and Action Bar (`views/toolbar.py`)

Two rows, one above the other, because they are two different things.

**The menu bar** names everything the application can do, the way a menu bar
on any desktop does:

- **Project**: New Project, Load Project, Save Project
- **File**: Import (MPP, GAN, Mermaid, XLSX) and Export (Mermaid, HTML, SVG,
  PNG, PDF, XLSX)
- **Actions**: Create (Phase, Deliverable, Task, Subtask, Milestone),
  Project Title, and EU Holidays
- **Edit**: Undo, Redo, Cut, Copy, Paste
- **View**: Toggle Theme, Settings
- **Log**: Opens the application log window, at the end of the row

**The action bar** under it carries the handful worth reaching for without
opening a menu, in three groups divided by a hairline:

- open, new, save
- edit, and the five work item types outermost first: Phase, Deliverable,
  Task, Subtask, Milestone
- cut, copy, paste, delete, undo, redo

The icons are **drawn** (`resources/icons.py`), a few strokes each painted with
Pillow at four times the size and reduced. They were set in "Segoe UI Emoji"
before, a font that ships with Windows and with nothing else, so the whole row
came out blank on Linux. Drawing depends on no font being installed.

### File I/O (`utils/file_io.py`)
- **JSON Serialization**: Handles datetime objects and None values
- **Save/Load**: Full project save and load functionality
- **Error Handling**: Graceful error handling for file operations

### GAN Importer (`utils/gan_importer.py`)
- **XML Parsing**: Uses xml.etree.ElementTree for GAN files
- **Namespace Handling**: Reads both GanttProject 3.x files (no namespace) and older namespaced files
- **Working-Day Calendar**: Replays the file's `<calendars>` block (weekend definition plus recurring and year-specific holidays) to turn each task's working-day duration into an end date, reproducing the dates GanttProject displays. The same calendar becomes the imported project's own, so the application goes on scheduling it the way GanttProject did
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
- **Duration Fallback**: Derives a missing end date from the duration - or a missing start date, for a sheet that gives the end instead - skipping weekends when the column is labelled in working days
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

### Chart Export (`utils/image_export.py`, `utils/chart_render.py`)
- **PNG**: Configurable DPI, 300 by default
- **PDF**: Drawn at 150 dpi; export to SVG where scalable output is wanted
- **SVG and HTML**: The vector and the interactive Plotly form of the same chart
- **Browser-Free**: Everything but the HTML export is drawn with Pillow, so
  nothing is downloaded and no browser is involved
- **Standalone Layout**: An exported chart has no task list beside it, so it
  chooses its own rows and prints its own task names down the left - which is
  what the on-screen chart drops in favour of the grid
- **Directory Creation**: Automatically creates parent directories

### XLSX Exporter (`utils/xlsx_exporter.py`)

Writes the project as a **plan sheet** - the layout project plans are actually
kept in - rather than as a dump of the model. A spreadsheet is where a plan
gets circulated and argued over, and three sheets of raw fields (which is what
this used to write) were a faithful record and no use to anybody who wanted to
look at the plan.

The sheet carries a title, an editable project start date, one row per piece
of work grouped by phase, and a week-by-week bar chart drawn in the cells to
the right:

| Column | Holds |
| --- | --- |
| ID | Row number, which the `Pred.` column points at |
| Phase | The phase the work sits under, colour-banded down the sheet |
| Task | The work itself |
| Responsible (A) | Left blank for the reader to fill in; the model has no owner field |
| Key Deliverable | The Deliverable the row sits under, or the task's notes |
| Pred. | Predecessor row numbers - `4`, `4SS`, `4FS+2` |
| Duration (wd) | Working days, editable (shaded, blue text) |
| Start / End | `WORKDAY` formulas over the duration |
| Status | Not started / Ongoing / Done, from progress |
| … | One column per week, drawing the bar |

**The sheet is live.** Duration is a number the reader can change; Start and
End are WORKDAY formulas over it, so re-planning in Excel behaves the way
re-planning here does - weekends are skipped, and a task pushed out drags the
chain behind it. The timeline bars are formulas over Start and End, so they
follow. Changing the one start-date cell moves the whole plan.

**A formula is only written where it reproduces the date this application
already worked out.** The arithmetic is done first, with the project's own
calendar, and where a WORKDAY chain could not say what the plan says - a task
with no predecessor, or one held by a Start-Start or Finish-Finish link, or
one with a lag - the real date is written instead. A sheet that is live but
wrong would be worse than one that is merely static.

Where the project observes public holidays, they are written to a hidden
`Holidays` sheet and the formulas become `WORKDAY(…, Holidays!$A:$A)`, so
Excel recalculates onto the same dates this application schedules.

Rows are the **leaves** of the plan: the work. A Phase or a Deliverable
brackets other rows rather than being work of its own, so it appears as the
Phase column and the colour banding, which is how this layout expresses
grouping. Nesting deeper than that is flattened - the layout has one grouping
column - and the Key Deliverable column names the deliverable a row sits under
so the level stays readable.

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
- **Window Icon**: set from `resources/appicon.py` at startup and passed to every dialog the application opens

### The Application Icon (`resources/appicon.py`)

The icon is **drawn from code**, not stored as a file. That buys one property
worth having: the window, the desktop entry and the packaged build all come
from the same drawing, so they cannot drift apart, and there is no binary blob
in version control that nobody can diff.

What is in it:

- **Python's own colours** - both published blues (`#306998`, `#4B8BBE`) and
  both yellows (`#FFD43B`, `#FFE873`), meeting on the diagonal the language's
  logo is built on.
- **A Gantt chart** - three staggered bars, a Finish-Start link dropping from
  the first to the second, and a milestone diamond closing the last. Four
  marks, and the whole vocabulary of a project plan.
- **SZJ**, the author's initials, set in the same rounded-bar language as the
  chart so they read as part of it rather than as a caption underneath.

Every stroke is geometry - no font is used. A font would make the icon depend
on what happens to be installed, so the same script would produce a different
image on every machine that built the package. It is drawn at four times the
requested size and reduced with a high quality filter, which is what keeps the
diagonals clean at the 32 pixels a title bar asks for.

The artwork is original and the palette is the Python Software Foundation's
published logo colours, so the icon carries the project's own MIT licence with
no third-party asset in it.

`packaging/make_icon.py` writes it out during the `.deb` build at every size
the hicolor theme asks for - 16, 24, 32, 48, 64, 128 and 256 - so menus, docks
and task switchers each get the size they want rather than scaling one down.

## Installation

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Required Dependencies
```bash
pip install customtkinter plotly tkinterweb pillow openpyxl holidays
```

Or install everything from the requirements file:
```bash
pip install -r requirements.txt
```

`openpyxl` is required for Excel XLSX import and export. Without it the app
still runs, but the Import XLSX and Export XLSX actions report an error.

`holidays` supplies the public holidays behind Actions → EU Holidays.... Without
it the app still runs and the picker still saves a selection, but no holiday is
applied and plans are scheduled on weekends alone.

### Optional Dependencies
```bash
# For GAN file import (included in standard library)
pip install lxml  # For better XML parsing performance

# For MPP file import
pip install tasklib  # Pure Python MPP reader
```

## Usage

### Packages

Each release on the [Releases page](../../releases) carries:

| Platform | Files |
| --- | --- |
| **macOS** | `.dmg`, and the `.app` bundle zipped. **Apple Silicon / arm64 only — not Intel** |
| **Linux** | `.deb` for Ubuntu and Debian, amd64 |

Both are **self-contained**: the Python interpreter, the Tcl/Tk runtime and
every third-party library are bundled, so no Python installation and no pip
packages are required, and nothing is downloaded at runtime. `SHA256SUMS`
covers every file, and the exact library set is recorded in
`dependency-manifest.txt` and `dependency-manifest-macos.txt`.

### Installing on macOS

Mount the `.dmg`, drag **PySimplePMT** onto **Applications**, and then — for
the **first launch only** — **right-click** it in Applications and choose
**Open**, then **Open** again in the dialog.

The build is **unsigned**: it carries no Apple Developer certificate, because
that is a paid annual subscription and this is a free project. Double-clicking
an unsigned app the first time gets a refusal with no way past it; right-click
→ Open is the way past. Every launch after that is an ordinary double-click.

[packaging/README-macOS.md](packaging/README-macOS.md) has the full
instructions, including the different route macOS Sequoia (15) takes, and
travels inside the DMG so it is there when it is needed.

Apple Silicon only. PyInstaller bundles the interpreter and the libraries of
the machine that built it, and the release is built on an arm64 runner; on an
Intel Mac, run from source instead.

### Installing on Ubuntu / Debian

Download the `.deb` from the [Releases page](../../releases) and install it:

```bash
sudo apt install ./pysimplepmt_1.28.0_amd64.deb
```

See [packaging/README.md](packaging/README.md) for what the package still
relies on and how it is built.

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

2. **Add Work Items**
   - **Actions -> Create** offers Phase, Deliverable, Task, Subtask and
     Milestone, as does the Create submenu on any row's right-click menu
   - Creating from a row puts the new item beside it - or inside it, for a
     sub-task - rather than at the end of the plan
   - Enter the name, and whichever two of start date, end date and duration the
     scheduling mode leaves you to fill in

3. **Add Sub-Tasks**
   - Choose "Subtask..." from either Create menu
   - Enter subtask name and duration in days
   - Select a parent task from the list (must have at least one task)
   - Any task can be the parent, **including an existing sub-task**, so hierarchies can go deeper than two levels
   - The list is indented to show how deep each candidate sits
   - Milestones are not offered as parents (they are single-date markers with no span)
   - Sub-tasks automatically inherit the start date from their parent
   - Sub-tasks appear indented under their parent in the task list

4. **Add Milestones**
   - Choose "Milestone..." from either Create menu
   - Enter milestone name and date
   - Milestones appear as diamonds in the Gantt chart

5. **Set Dependencies**
   - Open a task and use its Dependency tab, where the link type (Start-Start,
     End-Start) and hardness (Hard, Rubber) can be chosen
   - Dependencies appear as red arrows in the Gantt chart
   - Cannot create circular dependencies (a task cannot depend on itself or its own subtasks)

6. **Edit Tasks**
   - Choose Edit from a row's right-click menu. Double-click folds a branch
     away instead, as it does in any other tree
   - Modify properties, dependencies, notes and colours
   - Save & Close, Save & New, or Delete
   - Help opens a reference on what each field means

7. **Copy, Cut and Paste**
   - From a row's right-click menu, the Edit menu, or Ctrl/Cmd+C, X and V
   - Acts on every row selected, and copies only those rows - copying a phase
     does not duplicate the work under it
   - Pasted rows land after the row the menu was opened over, and stay selected
   - Paste is offered only where the item belongs: a phase does not go inside
     a task

8. **Save Project**
   - Choose **Project -> Save Project...**
   - Choose file location and name
   - Project is saved in JSON format

9. **Load Project**
   - Choose **Project -> Load Project...**
   - Select a previously saved JSON file

10. **Create New Project**
   - Choose **Project -> New Project...**
   - Enter project name
   - Start adding tasks and milestones

11. **Import Projects**
    - Choose **File -> Import** and pick the format:
    - "MPP..." to import MS Project files (requires Tasklib)
    - "GAN..." to import GanttProject files
    - "Mermaid..." to import Mermaid Gantt chart files (.mmd, .mermaid)
    - "XLSX..." to import an Excel project plan (requires openpyxl)
    - Importing replaces the current project and clears the undo/redo history

12. **Export Projects**
    - Choose **File -> Export** and pick the format:
    - "Mermaid..." to export project to Mermaid format
    - "PNG..." to export Gantt chart as PNG image
    - "PDF..." to export Gantt chart as PDF document
    - "XLSX..." to export all tasks to Excel format

13. **Undo/Redo**
    - Choose **Edit -> Undo** to revert the last action
    - Choose **Edit -> Redo** to reapply the last undone action
    - Menu items are disabled when no actions are available
    - Supports undo/redo for: adding tasks, removing tasks, updating tasks, editing project info, setting dependencies

14. **Rename the Project**
    - Choose **Actions -> Project Title...**
    - Edit the project name

15. **Toggle Theme**
    - Choose **View -> Toggle Theme**
    - Switch between light and dark modes

16. **View the Log**
    - Click the **Log** button at the end of the menu bar
    - Filter by level, auto-refresh, and copy or save the log to a file
    - Import and export failures appear here with full tracebacks
    - The log is also written to a file; see the Logging section for its location

### Mouse and Keyboard
- **Double-click** a row to expand or collapse its sub-tasks
- **Drag** a row to reorder it within its siblings
- **Right-click** a row (two-finger click on macOS) to move, edit or delete it
- Choose **View -> Toggle Theme** to switch between light and dark modes

## Sample Data

The application starts with a complete sample project with tasks and subtasks:

2. **Project Planning** (3 days) - Blue
   - **Requirements Gathering** (Sub-Task, 1 day) - Purple
3. **Design Phase** (7 days, depends on Planning) - Green
   - **UI Mockups** (Sub-Task, 3 days) - Dark Purple
4. **Design Review** (Milestone, depends on Design) - Red
5. **Implementation** (10 days, depends on Design, 30% complete) - Orange
6. **Testing** (5 days, depends on Implementation + Design Review) - Purple
7. **Deployment** (3 days, depends on Testing) - Teal

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
- `task_type`: One of 'Phase', 'Deliverable', 'Task', 'Subtask', 'Milestone'
- `parent_task_id`: ID of the parent row, None at the top level
- `duration`: Length in working days when one has been set; None leaves it derived
- `priority`: One of the levels in `priority.py`; 'Normal' by default
- `shape`: How the bar is drawn - 'Default', 'Rectangle' or 'Rounded'
- `show_in_timeline`: Whether the task appears in the chart at all
- `earliest_begin`: A date the task may not start before, or None
- `scheduling_options`: Which of the three the form derives - 'Start date is
  calculated', 'End date is calculated' or 'Duration is calculated'
- `details`: Free text, shown in the notes panel beside the form
- `duration_days`: Calculated property - working days from start to end
  inclusive, 0 for a milestone or a container, None where there is no end date
- `total_elapsed_days`: Calculated property - calendar days from start to end
  inclusive, weekends and holidays included. This is the span the chart draws

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
      "id": "001",
      "name": "Task Name",
      "start_date": "2024-01-01T00:00:00",
      "end_date": "2024-01-07T00:00:00",
      "progress": 0,
      "dependencies": [],
      "color": "#1f6aa5",
      "is_milestone": false,
      "task_type": "Task",
      "parent_task_id": null,
      "duration": null,
      "priority": "Normal",
      "shape": "Default",
      "show_in_timeline": true,
      "earliest_begin": null,
      "scheduling_options": "End date is calculated",
      "details": ""
    },
    {
      "id": "002",
      "name": "Subtask Name",
      "start_date": "2024-01-01T00:00:00",
      "end_date": "2024-01-03T00:00:00",
      "progress": 0,
      "dependencies": [],
      "color": "#9b59b6",
      "is_milestone": false,
      "task_type": "Subtask",
      "parent_task_id": "001",
      "duration": null,
      "priority": "Normal",
      "shape": "Default",
      "show_in_timeline": true,
      "earliest_begin": null,
      "scheduling_options": "End date is calculated",
      "details": ""
    }
  ],
  "start_date": "2024-01-01T00:00:00",
  "end_date": "2024-01-07T00:00:00"
}
```

A file written by an earlier version carries fewer fields than this. Anything
missing takes its default when the file is read, and `Sub-Task` is rewritten
to `Subtask`, so older plans open unchanged.

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

Files produced by this application's own XLSX export can be read back: the
export writes this same `ID` / `Phase` / `Task` / `Pred.` / `Duration (wd)` /
`Start` / `End` / `Status` layout.

Its date columns are formulas, and openpyxl reads a formula's *cached* value -
which a file that has never been opened by Excel does not have. So a row whose
dates read as empty is placed at the plan's start date (taken from the
`Project Start Date:` cell, parsed from its `DATE()` call if need be) and left
for the scheduler: the duration is a plain number and the predecessors are
plain row references, and the Finish-Start rule the scheduler applies is the
same rule the WORKDAY chain encodes, so the rows land where the formulas would
have put them.

What survives the round trip: task count, project name (read from the
`Project Name:` label on the Summary sheet), dates, progress, milestone flags,
dependencies, and the phase grouping. What does not: the `Responsible (A)`
column and any nesting below the phase level, neither of which the model has
somewhere to keep.

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

### 1. The chart is drawn, not rendered by a browser
- Matplotlib and numpy were removed; Kaleido was never adopted. Plotly can
  only rasterise a figure through Kaleido, which does it by driving a Chrome
  or Chromium browser and downloading one at runtime when none is installed -
  which a self-contained desktop package cannot do
- The chart on screen and every image export are painted with Pillow
  (`utils/chart_render.py`), which fetches nothing
- Plotly remains for the interactive HTML export, where a browser is the
  point

### 2. Drag-and-Drop Implementation
- Rows are reordered by dragging, implemented in plain Tkinter. tkinterdnd2 is
  not used: it exchanges drops with other applications, while moving a row
  inside one Treeview needs only the pointer position
- A thin blue line marks where the dragged row will land
- Moves are confined to a task's own siblings, so nothing is reparented by accident
- A press becomes a drag only past a small threshold, leaving clicks alone

### 3. MPP Import Flexibility
- Multiple import methods with automatic fallback
- Graceful degradation when libraries not available
- Clear error messages for users

### 4. Critical Path Calculation
- Longest chain of dependent tasks, ending at the task that finishes last
- Measured by **accumulated working duration**, not by comparing calendar
  dates: plans scheduled in working days leave weekend and holiday gaps between
  a task and its successor, and a date-based comparison reads those gaps as
  slack, which drops most of the chain
- Summary tasks are excluded from the chain, but a dependency **on** a summary
  task resolves to the work inside it, so grouping does not sever the network
- Ties on the finish date are broken by chain length, so the path always
  reaches the project's real finish
- Cycle-safe and iterative, so deep chains cannot exhaust recursion
- Visual highlighting in Gantt chart

### 5. Color Management
- A colour per work item type, so the five levels are told apart before
  anybody picks anything
- Custom colours per task, chosen from a popup palette that is built the first
  time it is opened rather than with every task dialog
- Critical path highlighting
- Colour serialization in JSON

### 6. No font is relied on for a glyph
- The calendar button's icon and the whole action bar are drawn with Pillow.
  Emoji and icon fonts are a Windows and macOS assumption: a stock Linux
  desktop has neither, and both came out blank there before they were drawn

### 7. Fields are watched through variables, not the keyboard
- The task form checks a field through a Tk variable rather than a
  `<KeyRelease>` binding, so a value arriving from the calendar, from a
  dependency or from the scheduling calculation is seen as readily as a typed
  one
- Nothing is reconfigured while a field's verdict is unchanged: a
  CustomTkinter widget redraws its canvas on every `configure()`, so
  reasserting a border on each keystroke cost more than working the answer
  out

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

Run a single module by name:
```bash
python3 run_tests.py test_models
```

Some of the suite builds real widgets, so those modules skip when no display
is available and CI runs them under xvfb.

### Test Coverage

Unit tests cover:
- ✅ **Models**: Task and Project classes, serialization, critical path calculation
- ✅ **File I/O**: JSON save/load, datetime handling, error cases
- ✅ **GAN Import**: Real GanttProject 3.x fixtures - working-day calendar, nested sub-tasks, successor-to-predecessor edge reversal, milestones, colors, namespaced files
- ✅ **Mermaid Import/Export**: Inclusive working-day durations, dependency chains, section grouping, frontmatter, round-trip
- ✅ **XLSX Import**: Header detection, column aliases, Excel serial dates, working-day durations, phase grouping, dependency resolution, lossless export round-trip
- ✅ **Task Hierarchy**: Sub-task creation, parent candidate ordering, cycle safety, and the type a task takes when it is indented or outdented between levels
- ✅ **Logging**: Buffer capacity and filtering, file output, failure paths, importer errors reaching the log
- ✅ **Gantt Export**: PNG and PDF rendering
- ✅ **Undo/Redo**: Command stack behaviour
- ✅ **Utilities**: Project utilities, validation, edge cases
- ✅ **Completion**: Each level's roll-up rule, empty containers, clamping, and the whole cascade from a ticked sub-task to the phase above it
- ✅ **Task Editor**: That the boxes survive being checked, what the form complains about and when, what a refused save leaves alone, and that a keystroke changing no verdict touches no widget
- ✅ **Copy, Cut and Paste**: What goes on the clipboard, what may be pasted where, where pasted rows land, that a task cannot be pasted inside itself, and that the selection reaches the clipboard at all
- ✅ **Chart Alignment**: That the chart draws the rows the list is showing, in its order, at its row height, and drops its label column beside a grid
- ✅ **Scroll Frame**: The scrolling container the task form is built in
- ✅ **Icon Toolbar**: That every icon carries a drawing and reaches the handler connected to it
- ✅ **Working-Day Calendar**: Weekends, holidays, recurring holidays, a week with no working day in it, durations to dates and back, and the EU public holidays including the movable Easter feasts
- ✅ **Scheduling**: Each link type and the edge it holds, lead and lag in working days, hard against rubber, a span stated by two links, the earliest begin date, roll-up through nested containers, and that the pass settles
- ✅ **EU Holiday Dialog**: What it offers, the batch buttons, what Apply hands back and what Cancel does not
- ✅ **XLSX Export**: The plan sheet's shape, which tasks get rows, the live formulas, and that a formula is never written where it would disagree with the plan
- ✅ **Application Icon**: That it draws at every packaged size, in the Python colours, identically every time, and reaches the window

The GAN fixtures deliberately mirror the format GanttProject actually writes.
An earlier version of these tests used an invented schema, which let the
importer pass its whole suite while reading zero tasks from real `.gan` files.

### Test Status
1062 tests, all passing.

## Known Limitations

1. **MPP Import**: Requires the optional Tasklib package and is not bundled into the packaged build
2. **Public holidays**: Need the optional `holidays` package. Without it the picker still saves a selection and says so, but plans are scheduled on weekends alone
3. **Performance**: Large projects (>100 tasks) may impact chart rendering
4. **Critical Path**: Returns the single longest chain rather than every zero-float task, so parallel critical activities are not all highlighted
5. **XLSX Import**: Reads cached formula results. A workbook generated without a calculation pass has empty date columns; rows carrying a duration and predecessors are rescheduled from the plan's start date instead, and rows carrying neither are skipped
6. **XLSX Export**: The `Responsible (A)` column is written empty - the model has no owner field - and hierarchy below the phase level is flattened, since the layout has one grouping column
7. **No resources**: A task has no owner or assignee, so nothing is levelled and nothing is costed
8. **The weekend rule is not editable in the app**: which weekdays are worked can be carried in from an imported file but not changed afterwards

## Future Enhancements

Done:

- [x] Drag-and-drop row reordering
- [x] PDF/PNG export for Gantt charts
- [x] XLSX import
- [x] XLSX export as a live project-plan sheet
- [x] Application log viewer
- [x] Shared working-day calendar model (`workdaycalendar.py`)
- [x] EU public holidays, chosen per project
- [x] Apply GAN dependency lag and SS/FF/SF dependency types
- [x] Earliest begin date honoured by the scheduler
- [x] Timeline zoom/pan
- [x] Undo/Redo functionality
- [x] Copy, Cut and Paste
- [x] Work item hierarchy with completion roll-up
- [x] Types preserved when indenting and outdenting between levels
- [x] Chart rows aligned to the task list
- [x] Phases drawn as a pointed bar rather than a bracket
- [x] An application icon of its own, on the window and in the package

Still to do:

- [ ] GAN file export
- [ ] Resource management
- [ ] Filtering and grouping
- [ ] Recursive copy of a whole branch
- [ ] Undo for paste
- [ ] Undo for a calendar change
- [ ] Multiple projects support
- [ ] Settings/preferences dialog
- [ ] Editing the weekend rule from the application
- [ ] Countries outside the EU in the holiday picker
- [ ] Full critical path analysis (a backward pass, so every zero-float task)

---

**Project Status**: Active Development
**Version**: 1.28.0
**Last Updated**: 2026-08-18
