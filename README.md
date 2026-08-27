# PySimplePMT - Gantt Project Management Tool

A cross-platform desktop application for project management with Gantt chart visualization, drag-and-drop task management, and support for importing MS Project, GanttProject, Mermaid and Excel files.

## Overview

This is a complete implementation of a project management tool with:
- Interactive Gantt chart visualization
- Drag-and-drop task list for arranging the plan by hand
- Support for milestones (single-date tasks)
- JSON storage and file import for GAN/MS Project/Mermaid files
- Modern UI using CustomTkinter

## Features

- **Gantt Chart**: Tasks, milestones and dependency arrows, drawn with Pillow so nothing is downloaded and no browser is involved. Zoom in, out, Fit and Reset beneath it. It opens framed on the plan — a day of calendar before the first bar and room after the last for its label. The dates run across the top as a **calendar strip**: a month band, and a cell per day beneath it carrying the day number. Days nobody works are shaded down the whole chart and today's column is tinted
- **Drag-and-Drop Task List**: Reorder tasks by dragging a row — a thin blue line shows where it will land — or from the right-click menu (Move to top / up / down / bottom)
- **Foldable Hierarchy**: A task with sub-tasks shows an expander; the arrow beside a row folds its branch away
- **Progress in one press**: 0/25/50/75/100% buttons set the completion of a whole selection at once, and **Mark on Track** works it out from the dates instead — finished work to 100%, unstarted work to 0%, and everything in between to the share of its *working* days that have elapsed. The arrow beside it applies the same to the entire project
- **Row Formatting**: Mark rows up where the work happens — text colour, background fill, bold/italic/underline, and four one-press presets (Financial Milestone, Work Complete, Phase Gate, Summary Phase) from a dedicated group on the icon bar. Applies to a whole selection at once, undoes in one step, and is saved with the plan
- **Project Settings**: One panel for what the whole plan is built from — title, start date, finish date, which end it is scheduled from, calendar, status date and priority. Changing the start date moves the entire plan, keeping every duration and every gap
- **Backward scheduling**: Schedule from the finish date and the work is packed As Late As Possible against a deadline, rather than starting as soon as its links allow
- **Retype in the grid**: Double-click the **Type** cell for a dropdown of every type. Picking one stores it — one undo step, and the editor shows it. Choosing `Milestone` sets the milestone flag with it, so the editor opens with the switch on; choosing anything else clears it again
- **New task from the keyboard**: `⌥⌘I` on a Mac, `Ctrl+Alt+I` elsewhere, creates a task beside the row the cursor is on and opens its editor. With no cursor it goes at the end of the plan
- **Two speeds of click**: Two quick clicks on a row open the task editor. A click, a pause and a second click open the name for typing over, in the grid — the gesture a file manager renames with. Enter or clicking away saves, Escape cancels. The name goes on the task, so the editor shows it and Undo takes it back. Neither gesture folds a branch; the arrow beside the row does that
- **Type dependencies into the grid**: The Dependencies column takes the notation every planning tool uses — `3`, `3SS+1d`, `3FS-2d`, `3SF+50%`, several per cell. Double-click, type, Enter. It resolves the numbers, refuses a self-reference, an unknown task, a duplicate or anything that would run in a circle, reschedules, and writes the cell back in the same form
- **Sequential IDs that keep up**: The ID column numbers rows 1..N down the list with no gaps, and follows every insert, delete, drag and indent. The number is a *position*; dependencies are held against the task itself, so a link never breaks when the numbers move — it just shows a different one
- **Outline You Can Scan**: Any row with work under it is drawn in bold and its children are indented — true whatever the Type column says, and whether or not that column is on screen. The task name lives in the tree column, so the indentation is drawn against the name itself, and an **Outline Level** column gives the same depth as a number (1 at the top, 2 under it), the way Microsoft Project does
- **Keyboard-first task editing**: Enter saves and closes the task editor, Escape cancels, and Enter still types a newline in the Details box (Cmd/Ctrl+Enter saves from in there). Save & Close is drawn as the primary button, Cancel as the secondary one
- **Shortcuts follow the platform**: Command on macOS, Control everywhere else — and the hover text names whichever key the machine actually answers to
- **The list keeps its place**: Formatting, indenting or outdenting a row leaves it selected and leaves folded branches folded, so a run of changes takes one click rather than one click each
- **Milestone Support**: Special single-date markers with diamond icons
- **JSON Storage**: Save and load projects in JSON format
- **File Import**: Import from GanttProject (.gan), MS Project (MSPDI .xml), Mermaid (.mmd), and Excel (.xlsx) files. Every reader is standard library or an already-bundled package, so no import needs anything installed
- **Hierarchy on Import**: Source-file grouping (Mermaid sections, spreadsheet phases, nested GanttProject tasks) is preserved as parent tasks with sub-tasks
- **File Export**: Export the plan to a three page PDF — work item list beside the chart, the chart alone, then the list as a full table — to PNG, projects to Mermaid format, and the plan to Excel XLSX as a live project-plan sheet - editable durations, WORKDAY dates and a week-by-week bar chart
- **Planning Tool Export**: Hand the plan to GanttProject as a .gan file, or to Microsoft Project as MSPDI .xml. Both carry the hierarchy, the links with their types and lags, the progress, the notes and the working calendar; both are written so the dates the other tool shows are the dates shown here
- **Work Item Hierarchy**: Phase > Task > Subtask, with milestones at any level. Indenting and outdenting keep a task's type wherever the new parent can hold it, so a Task moved under a Phase stays a Task and keeps being able to hold sub-tasks of its own
- **Opens to fit the screen**: The window is sized to the area the desktop actually allows — the menu bar, Dock or taskbar excluded — rather than to a fixed 1400x900 that overflowed a 1366x768 laptop. The minimum is clamped to what was opened, so the window can always be resized to fit the display it is on
- **Modern UI**: Built with CustomTkinter for a professional look
- **Native Dialogs**: Message boxes and file choosers use the platform's own on macOS and Windows. On Linux, where Tk draws its own, message boxes are rebuilt to match the window and file choosers hand off to zenity or kdialog when present
- **Rows that line up**: the chart draws the rows the task list is showing, in its order and at its row height, so a bar sits on the line of the task it belongs to. Fold a branch away and its bars go with it; scroll the list and the chart follows
- **Critical Path**: Automatic calculation and visualization of the critical path. The icon on the bar paints every critical row light red in the task list — press it again to clear — and **View → Critical Path...** opens the full float table
- **Dependency Types**: Finish-Start, Start-Start, Finish-Finish and Start-Finish, each with lead/lag in **working** days and Hard/Rubber link hardness. A start link and a finish link on the same task state a span - Start-Start onto the first task and Finish-Finish onto the last makes a row cover the stretch between them, and its duration follows from the two dates rather than being carried over. A hard link pins a date but still has to clear any rubber floor set by another link
- **Earliest Begin Date**: a floor on when a task's work can start, applied alongside the links and the working calendar
- **Checked as you type**: The task editor outlines a name or a date it cannot use and says why beneath the form, rather than waiting for Save
- **Auto-Scheduling**: Moving a task drags whatever depends on it, so links stay satisfied
- **Working-Day Calendar**: A duration is working effort, so a task crossing a weekend keeps its length and its bar reaches further out. Nothing is ever scheduled to start or finish on a Saturday, and a plan imported from a file that declared holidays keeps them
- **Public Holidays**: Actions → Calendar Settings... → National Holidays picks any of the ~250 countries the `holidays` package knows — **and their regions**, so Bavaria's three extra holidays are observed rather than Germany's national list alone. A search box finds a country or a region by name, and the 27 EU member states sit behind one button. A date that is a public holiday in *any* selected country or region becomes a non-working day. Easter Monday and the rest of the movable feasts are worked out per year, so a task spanning one is pushed out rather than losing the work planned for it
- **Search**: a box on the icon bar finds a row by anything written on it — name, ID, type, **notes** (so a ticket number pasted into the details is findable), either date, duration, progress, priority, what it depends on, and which calendar it follows. A match brings its parents along so you can see where it sits, and a `2 of 40` count sits beside the box so a filtered list is never mistaken for a short plan
- **Built-in Help**: the **?** on the icon bar and **View → Help** open one searchable guide covering every field, the scheduling rules, the task types and hierarchy, the calendars, dependencies, float, and the import/export formats. The search box matches any text or number, highlights every hit, counts them, and walks them with Enter / Shift+Enter. Two shorter references stay where they were needed — a Help button on the task editor — searchable too, covering every field, how the calculated date is worked out, and how the working calendar decides — and one on the Dependency tab for the link types
- **Day / Night Theme**: follows the desktop by default and keeps following it — the window switches when the OS does. The toolbar's ☀ **Day** / 🌙 **Night** button flips it by hand and detaches from the OS; **Sync with system** appears beside it only while that override is in force. Also under View → System UI mode. The choice is remembered between runs
- **Per-Task Calendars**: a task may follow a calendar of its own instead of the plan's — a weekend-only shift for a migration that can only touch production on a Saturday, a 24/7 run for an unattended load test. Set from the task editor's **Working calendar** dropdown, which re-dates the task as soon as it is picked. Three presets come with every plan; a task that names none follows the project's calendar exactly as before
- **Working Week**: Actions → Calendar Settings... → Working Week sets which weekdays are worked at all — a six-day week, a four-day week, or the standard Monday to Friday. Durations are held and finishes move, so putting Saturday to work pulls finishes in rather than lengthening tasks. A week with no working day in it is refused
- **Manual Date Overrides**: Actions → Calendar Settings... → Manual Overrides rules on one named date at a time, and **outranks everything else** — a Saturday named as a make-up day is worked, and an ordinary Tuesday named as a company shutdown is not, whatever the weekend and holiday rules say. Each carries an optional reason, and deleting one puts the date back under the ordinary rules. Saved with the project
- **Critical Path Analysis**: both passes of the critical path method, giving every task its early and late dates and its float in working days. *Every* zero-float task is critical, not one chain through them, so two parallel strands that both drive the finish are both reported
- **Work Item Types**: Phase, Task, Subtask and Milestone, each with its own colour, and dates and progress that roll up through the levels
- **Summary Roll-Up**: Anything with children spans them, and completion works its way up the levels. A Subtask carries its own percentage; a Task averages its sub-tasks' percentages evenly, or keeps the percentage typed on it when it has none; a Phase averages its tasks evenly. An empty container reads 0%
- **Copy, Cut and Paste act on what you selected**: from the right-click menu, the Edit menu or Cmd/Ctrl+C, X and V - the same result from all three. What you paste takes the place of the row your cursor is on, at that row's own level, and pushes it down; putting rows *inside* a row is the separate **Paste as Sub-Task** entry that says so. Copying a row copies everything under it - a phase brings its tasks and their sub-tasks, nested as they were - and a link between two rows you copied together follows the copies. Cut rows are greyed until they land. Right-click the empty space below the last row to paste at the end of the plan, the same gesture that creates a task there; a paste with nothing selected and nothing pointed at is refused and says so, rather than dropping the row somewhere you were not looking. The whole paste is one step in the undo history. Copied rows reach the desktop clipboard too, as a readable list that pastes into anything
- **Link and Unlink Tasks**: Select the rows that run one after another and press the chain icon (`⌘F2` on a Mac, `Ctrl+F2` elsewhere) to chain them Finish-to-Start down the list; the broken-chain icon beside it (`⇧⌘F2` / `Ctrl+Shift+F2`) takes those links out again. The chain is built in the order the rows are shown, not the order they were clicked, and the plan reschedules the moment it is made. A row keeps any link it already had to something outside the selection, and a pair that would run in a circle is skipped rather than refusing the whole chain
- **Scheduling Modes**: Choose which of the start date, end date and duration the form works out from the other two; the calculated one fills itself in as you type, counted in working days
- **Menu bar and action bar**: a menu bar naming everything the application does, and an action bar of drawn icons under it for the handful worth reaching for directly. The icons are drawn rather than set as emoji, so they need no font installed
- **Log Viewer**: A "Log" button opens the application log for troubleshooting, with no console needed

## Project Structure

```
gantt_app/
├── __init__.py
├── models.py              # Task and Project data models
├── workdaycalendar.py     # Working days, weekends, holidays, overrides
├── calendarregistry.py    # Named calendars, and which one a task follows
├── theme.py               # Light or dark, who decides it, and the palette
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
│   ├── holidaydialog.py   # Working week, public holidays, date overrides
│   ├── searchbox.py       # Finding a row by anything written on it
│   ├── criticalpath.py    # The critical path analysis, task by task
│   ├── gantt_chart.py     # The Gantt chart pane, drawn beside the task list
│   ├── ganttsettingsw.py  # Gantt chart appearance settings dialog
│   ├── log_window.py      # Application log viewer
│   ├── modal.py           # Makes a dialog modal, and hands the grab to a popup
│   ├── buttonstyle.py     # How a secondary button is drawn, in one place
│   └── toolbar.py         # The menu bar and the icon action bar
│
├── help/
│   ├── __init__.py
│   ├── reference.py       # The window both Help buttons open
│   ├── editorhelp.py      # Task editor reference behind its Help button
│   ├── dependencyhelp.py  # Dependency reference behind the Help button
│   └── userguide.py       # The full guide behind ? and View → Help
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
│   ├── gan_exporter.py     # GAN (GanttProject) file export
│   ├── mpp_importer.py     # Which of the two MS Project formats a file is
│   ├── msproject_importer.py # MS Project (MSPDI .xml) import
│   ├── msproject_exporter.py # MS Project (MSPDI .xml) export
│   ├── plan_export.py      # What both interchange exporters ask of a plan
│   ├── mermaid_importer.py # Mermaid (.mmd) file import
│   ├── mermaid_exporter.py # Mermaid (.mmd) file export
│   ├── xlsx_importer.py    # Excel XLSX project plan import
│   ├── log.py              # Application logging (file, memory, stderr)
│   ├── chart_figure.py     # Shared Plotly figure builder
│   ├── image_export.py     # PNG, PDF, SVG and HTML export
│   ├── chart_render.py     # Browser-free static chart drawing
│   ├── page_render.py      # The pages of the PDF: work item list and chart
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
- **Work Item Types**: `Phase`, `Task`, `Subtask`, `Milestone`. `Phase` is a container, taking its dates and progress from what is inside it; `Subtask` and `Milestone` hold nothing. Two older types are rewritten when a task is built, so plans saved by earlier versions load unchanged: the hyphenated `Sub-Task` becomes `Subtask`, and `Deliverable` - a level that used to sit between `Phase` and `Task` - becomes `Task`, which is the level it always described
- **The Levels, and Moving Between Them**: the types describe a three-level plan, `Phase > Task > Subtask`, with a `Milestone` allowed at any level. **A row keeps its type wherever it is moved.** Indent and outdent change where it sits and nothing else, so a `Task` indented under another `Task` is still a `Task` and can still hold sub-tasks of its own. `child_type_for()` still settles the type of a row *created* under a parent, or read out of an imported outline that states depth and nothing else — a row arriving without a type anybody chose — but it is no longer applied to one being moved
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

1. **The calendar** names the non-working weekdays - Saturday and Sunday
   unless the plan says otherwise (see below) - plus any holidays: fixed
   dates, dates recurring every year, and the public holidays of any countries
   the project observes. It belongs to the project and is saved with it, so a
   plan imported from a GanttProject file keeps the week and the holidays that
   file declared.
1a. **A manual override beats all of it.** A date the user has ruled on by
   hand is worked, or not worked, exactly as they said - see below. It is the
   first thing the calendar consults and nothing else can overturn it, because
   the reason a plan needs an override at all is that the general rules got
   that one date wrong.
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

#### The date header (`utils/chart_render.py`)

The dates are a **calendar strip** across the top rather than labels under
the chart: a band naming the month, and beneath it a cell per day carrying
just the day number.

Moving the month and the year into the band is what buys the density. A full
`2026-08-17` label needs about 82px, so a 1400px chart fits 13 of them; a day
number needs about 22px, so the same chart fits **50** — near four times as
many dates, which is what makes every day labellable at all.

There is no weekday letter under the number. It would not have made the
columns any narrower — `22` is wider than `W` — and without it the strip is a
row shorter and draws half the text.

**The axis stays linear in calendar days.** Dropping the non-working columns
is what most calendar strips do and cannot be done here: a task may follow a
calendar of its own, so one on the 24/7 preset genuinely works Saturdays and
would have nowhere to be drawn, and the whole point of a manual override is
to make one particular Saturday a working day. Non-working days are **shaded
down the chart** instead, which says the same thing and costs a fill rather
than a semantic argument. Which days those are comes from the *project's*
calendar — it is the one frame every task is drawn against, and a strip
honouring several would have to shade a column two ways at once.

Three densities, chosen from the room available: a cell per day, a cell per
week, or the month band alone. The band survives all three, since a bare
`17` needs it to mean anything.

**The strip has to fit inside `MARGIN_TOP`**, which is what keeps the
chart's rows level with the task list's. The chart floors its row alignment
at that constant, so a strip needing more room does not make the chart
taller — it pushes every bar down and out of line with the list. The list
reserves about 70px above its first row (a heading and the column titles),
so the title and both tiers are sized to fit inside it. Two tests hold that:
one on the arithmetic, one that asks the running window where each pane
actually put its first row.

#### Searching the plan (`views/searchbox.py`)

One box, no field to choose first — somebody who knew which field it was in
would not need to search. It matches against everything a work item carries:
name, ID, type, notes, both dates, earliest begin, duration, progress,
priority, shape, each dependency's target and kind, and the calendar the task
follows.

Dates go in as `YYYY-MM-DD`, so `2026-09` finds a September and `2026-09-14`
finds the day. Numbers go in bare, so `40` finds progress as well as a
duration. Matching is case-insensitive and **literal**, so a ticket number or
a date finds itself rather than being read as a pattern.

**A match brings its ancestors, not its children.** Without the parents a
matching sub-task floats at the top level with no sign of what it belongs to,
and the indentation would be showing a structure that is not there; those
context rows are greyed, because they are on screen to say *where* rather than
because they hit. Bringing children instead would mean one broad word putting
the whole plan back on screen.

The predecessor's *name* is deliberately **not** searchable, though its id is.
Including it meant searching a task by name also returned everything depending
on it — so the commonest search of all came back padded with rows that merely
mentioned the thing being looked for. `T1` still finds both, which is the
precise way to ask.

**It is a view, not an edit.** Nothing in `models.py` consults the list, so the
schedule, the roll-up and the critical path are all measured on every task
whether or not it is showing. The chart narrows with the list for free: it
draws from `visible_rows()`, which reads the tree.

Typing is debounced by 120ms — each keystroke would otherwise rebuild the tree
and redraw the chart with it, which is eight renders nobody sees while somebody
types "milestone".

#### The user guide (`help/userguide.py`)

**?** on the icon bar and **View → Help** open the same window — one
instance, so pressing either while it is up raises the copy that is there
rather than stacking a second.

It is the long-form documentation: what the four levels mean and how work
moves between them, every field of the task editor, the three scheduling
modes, working days against calendar days, all four calendar rules and the
priority between them, per-task calendars, the link types with lag and
hardness, float and the critical path, progress roll-up, every import and
export format, and a section on why a task moved when you did not move it.

**The search box** across the top matches any text or number, taken
literally and without regard to case — so `24/7`, `100%` and `2026` find
themselves rather than being read as patterns. Every hit is highlighted where
it sits, the current one more strongly, with a `3 of 12` count beside the
box; Enter walks forward, Shift+Enter back, Escape clears. Hits are
highlighted **in place** rather than the guide being filtered down to
matching sections: a reference is read for its context, and the paragraph a
number sits in is usually the answer.

The window is `ReferenceWindow` with a search bar, the same base the two
short references use — the search is opt-in per subclass, since a screen or
two is faster read than searched.

**Every date in the worked examples is real.** They were produced by the
scheduler rather than typed from memory, and a test re-derives each one,
because a guide that disagrees with the application is worse than no guide:
the reader believes it, and the disagreement is found later by somebody who
has already acted on it.

#### Light and dark (`theme.py`)

Two things decide what the window looks like, and they are deliberately
separate: the **mode** is what the user asked for, and the **appearance** is
what that resolves to today. Only one mode can have the two drift apart.

| Mode | Appearance | Follows the OS |
| --- | --- | --- |
| `system` (default) | whatever the desktop says | yes, continuously |
| `light` | always Day | no |
| `dark` | always Night | no |

**The toolbar control** sits at the end of the icon row behind its own
divider — it is a setting rather than an action on the plan. It shows a sun
and *Day* while light, a moon and *Night* while dark: the appearance it is
**in**, not what a press would do, which is the only reading that makes sense
next to a sun. Pressing it flips the appearance and takes manual control.

**Sync with system** appears beside it *only while a manual choice is in
force*, and its presence is the status indicator. A permanent "Following
system" badge is chrome nobody reads after the first day; a control that
appears when — and only when — there is something to undo says the same thing
and costs nothing the rest of the time. The same three modes are under
**View → System UI mode**.

The desktop setting is **polled**, once every few seconds, and only while the
mode is `system`. There is no portable way to subscribe to it, and
CustomTkinter's own `set_appearance_mode("system")` re-reads it thirty times a
second — which on Linux means running `gsettings` in a subprocess thirty times
a second, for a setting that changes about twice a day. That is why this
application stopped using it. An explicit light or dark choice stops the poll
entirely, since there is then nothing for it to discover.

**Every colour is a (light, dark) pair.** That is the whole of the second
half of this module, and it is not a style preference. CustomTkinter uses a
colour written as a *single* string in **both** appearances, so a form full of
them reads perfectly to whoever wrote it and turns into near-black labels on a
near-black panel for everyone in dark mode — which is exactly what the task
editor did. The light half of every pair is the colour the application already
used, so the Day appearance is unchanged to the pixel; the dark half is chosen
to hold the same *contrast* against its own background rather than the same
hue. A test measures the WCAG ratio of every text-on-background combination in
both appearances, because eyes are what missed it the first time.

**The panes that are not CustomTkinter are told separately.** The task list
is a ttk Treeview, whose style resolves its colours once and keeps them; the
critical-path and dependency tables are the same; the chart is a picture
drawn with Pillow, with the old colours baked into it. None of them notices a
theme change on its own, so a flip left a white grid and a white chart inside
a dark window. `GanttApp._theme_changed` repaints them, guarded per pane
because the desktop poll can fire while the window is being torn down.

**Exports stay light whatever the window is set to.** A PNG or a PDF is
shared and printed, and a dark chart on paper is a page of ink — so the
screen and the exporters part company at `GanttChartView.screen_settings`,
and only the screen follows the theme. A colour the user picked in
View → Settings beats the theme in both.

The toolbar icons are drawn **twice**, once in each ink. `CTkImage` picks
between a light and a dark image, and handing it the same near-black drawing
for both made every icon on the row vanish into the bar the moment the window
went dark. The sun and moon are drawn from coordinates in
`resources/icons.py` like every other icon — nothing is bundled and nothing is
fetched, so they carry no licence beyond this project's, and they render on a
desktop with no colour emoji font, where `☀️` comes out as a dotted box.

#### Per-task calendars (`calendarregistry.py`)

A plan does not always run on one week. A migration that can only touch
production at the weekend, a load test that runs unattended around the clock,
and the ordinary Monday-to-Friday work around them are three different answers
to "is this day worked" inside one project.

So a calendar can be **named**, and a task can follow it instead of the plan's.
`calendarregistry.py` holds the naming — a `CalendarRegistry` of
`NamedCalendar`s, each an id, a readable name, and an ordinary
`WorkingCalendar`. There is deliberately no second calendar class: everything
a named calendar can express — the week, listed and recurring holidays,
observed countries, manual date overrides and the priority between them — it
expresses through the same `WorkingCalendar` the project has always used, so
the day-by-day arithmetic exists once.

The resolution rule is one line, and `Project.calendar_for(task)` is what every
piece of scheduling asks:

> a task whose `calendar_id` names a registered calendar follows it;
> every other task follows the project's own.

That covers all three cases that matter — the task naming nothing, the task
written before the registry existed, and the task naming a calendar that has
since been **deleted**. The last one falls back rather than raising: a calendar
can be removed while tasks still point at it, and a plan that will not open —
or a task with no calendar at all, which would hang the day-by-day walks — is a
far worse answer than a task quietly back on the standard week.

Three presets come with every **new** plan, so nobody has to build a weekend
calendar from scratch to find out what the feature does. A plan saved before
this existed gets none — nothing is invented for a file its author did not put
it in — and the settings dialog's **New...** is one click away either way:

| Calendar | Week | A 3-day task starting Thu 10 Sep 2026 |
| --- | --- | --- |
| Project Default | Mon–Fri | Thu 10 → Mon 14 |
| Weekend-Only Shift | Sat–Sun | **Sat 12** → Sat 19 |
| 24/7 Continuous Run | every day | Thu 10 → Sat 12 |

The weekend row starts on the Saturday, not the Thursday it was given: a task
cannot begin on a day nobody works, and that rule is now read on the task's own
calendar rather than the plan's.

**Two things stay on the project's calendar, deliberately.**

*Float*, because it is the one number every task is compared on. Both ends of
every task are read off that single ruler — a task's finish is looked up on the
axis rather than added to its start as a length, since the length is counted on
the task's own week. Adding one to the other reported a 24/7 task as finishing
two days past where it actually was, which came back as two days of **negative
float on a task that was never late**. Where a plan runs on one calendar the
two agree exactly, so no existing plan's numbers move.

*Lag*, because it is a number somebody types onto a link and it has to mean one
thing. Counted on the successor's week, the same lag of 2 was two days for an
ordinary task, two for a 24/7 run, and eight calendar days for a weekend-only
shift. The successor's own calendar still decides where it may start once the
wait is over, so nothing about its week is lost — only the length of the wait
is held steady. The dependency editor says so beside the box.

**In the task editor**, a *Working calendar* dropdown lists the plan's default
and every named calendar, each with its week beside it. Picking one re-dates
the task immediately — the start is rolled onto a day that calendar actually
works and the finish recalculated — rather than waiting for Save, so the form
never shows a Thursday start for a task that will begin on the Saturday. The
dropdown is not built at all when a plan holds no named calendars, since a
control whose only entry is "Project Default" cannot be used.

**In Calendar Settings**, an *Editing:* selector at the top switches all three
tabs between the project's calendar and each named one, so a weekend calendar
gets the same working week, public holidays and manual overrides as the plan's.
Everything is edited on copies and applied together, so Cancel still means
Cancel.

Beside it, **New...**, **Rename...** and **Delete**. New starts from whatever
calendar is on screen, so it doubles as "duplicate this one" — building a
second weekend shift that differs by one holiday is the case that matters, and
starting from a bare week means rebuilding it. Renaming keeps the id, because
that is what every task following it names. Deleting asks first and says what
it does: any task following the calendar goes back to the project's own, which
is why there is nothing to repair afterwards. The project's own calendar cannot
be renamed or deleted — it is the fallback everything depends on — and the
selector is built even when a plan holds no named calendars at all, so an
emptied registry is not a dead end.

Editing a named calendar goes through `Project.set_calendars()`, which applies
it the same way the other three do — durations are read under the old calendar
and dates rebuilt under the new one — so widening a weekend calendar to include
Friday pulls its tasks' finishes **in** rather than handing each of them
another day of effort. Tasks on other calendars are not touched, and changing
the *plan's* week no longer drags a task that follows its own calendar back
onto it.

#### The working week (`views/holidaydialog.py`)

**Actions → Calendar Settings... → Working Week** sets which weekdays are
worked at all. It is the base rule everything else is read on top of: the
public holidays and the manual overrides both assume a week to subtract from.

The boxes are ticked for the days that **are** worked, and the inversion to
the `non_working_days` the calendar stores happens in one place on the way
out. Asking somebody to tick the days they are off is the double negative that
gets set backwards once and then disbelieved forever.

Applying goes through `Project.set_working_week()`, the third sibling of
`set_holiday_countries()` and `set_date_overrides()` and applied the same way -
by `apply_calendar()`, which reads every task's working duration under the old
week and rebuilds its dates under the new one. So putting Saturday to work
pulls finishes **in** rather than lengthening tasks:

| | Start | Finish | Effort |
| --- | --- | --- | --- |
| Five-day week | Fri 11 Sep | Wed 16 Sep | 4 days |
| Six-day week (Sat worked) | Fri 11 Sep | Tue 15 Sep | 4 days |
| Four-day week (Fri off) | **Mon 14 Sep** | Thu 17 Sep | 4 days |

The effort is the same on every row; only the dates move. The third row moves
its *start* as well, because a task cannot begin on a day nobody works - rule
4 above - so taking Friday off pushes it to the Monday.

Assigning the calendar directly and rescheduling would not do this.
`enforce_working_calendar()` re-derives a task's duration from its dates every
time it runs, so the same change made that way silently grows the task to five
days of effort instead of moving its finish. That is the whole reason
`apply_calendar()` exists.

**A week with no working day in it is refused**, in the dialog, before
anything is applied and before the window closes - and the tab is brought
forward so the refusal sits beside the boxes that caused it.
`WorkingCalendar` would accept such a week: it treats one as working *every*
day, which stops a corrupted file from hanging the day-by-day walks looking
for a working day that does not exist. But that is damage limitation for bad
data, and applying it to a deliberate choice would answer "no days" with seven
of them and say so only in the log. `set_working_week()` refuses it too, so
the guarantee does not depend on the dialog being the only caller.

#### Public holidays across the EU (`views/holidaydialog.py`)

**Actions → Calendar Settings... → National Holidays** opens a picker listing
every country the `holidays` package knows, with an EU button for the 27
member states and All and Clear buttons for the whole list. The selection is
saved with the project.

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

A selection entry is a country — `DE` — or a country and one of its regions —
`DE-BY` for Bavaria, which keeps three public holidays the rest of Germany
works through. That is the ISO 3166-2 form, so a selection stays a plain list
of strings and a calendar saved before regions existed reads back unchanged. A
region the package no longer knows falls back to its country's national
holidays rather than being dropped, since losing the entry would schedule work
straight through them.

The picker lists countries; a region appears when it is searched for or when it
is already selected. The names of all ~1,200 regions are indexed when the
dialog opens (a thirtieth of a second), but their check boxes are built a
country at a time — a thousand of them takes half a second, which is a stutter
on every keystroke. Searching for a region needs two characters for the same
reason.

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

#### Manual date overrides (`views/holidaydialog.py`)

No country list can say that this particular Saturday is being worked to make
a deadline, or that the office is shut the week of the 20th. Those are
decisions about one named date rather than rules, and the only place they can
come from is the person running the plan.

**Actions → Calendar Settings... → Manual Overrides** is where they say so. An
override is a date, a type - Working Day or Non-Working Day - and an optional
reason for whoever reads the list back in six months. The table lists them in
date order with a delete button on each; deleting one puts the date back under
the ordinary rules.

The priority is strict, and overrides are at the top of it:

| Priority | Rule | Beats |
| --- | --- | --- |
| **1 (highest)** | Manual override | Everything below |
| 2 | Public holidays of the observed countries and regions | Weekends |
| 3 | Listed and recurring holidays | Weekends |
| 4 (lowest) | Non-working weekdays (Saturday and Sunday) | — |

So a date named as a working day *is* a working day even if it is a Saturday
and Christmas Day at once. That is deliberate: someone typing that date into
the list could see what it was, and meant it anyway. The reverse holds too - an
ordinary Tuesday named as non-working is not worked.

A date can only be ruled on one way, so adding an override for a date that
already has one replaces it. That is also how one gets edited.

Applying goes through `Project.set_date_overrides()`, the sibling of
`set_holiday_countries()` and applied the same way: every task's working
duration is read under the *old* calendar and its dates rebuilt under the new
one. Naming a Saturday as worked therefore pulls the finishes of the tasks
crossing it **in** by a day rather than handing each an extra day of effort,
and a shutdown pushes them **out** rather than quietly eating the work planned
for it. Deleting the override moves the plan back; it is not on the undo stack.

Both tabs are applied together by Apply, and neither touches the project before
then - so Cancel means the same thing on both. The overrides tab needs no
optional dependency: a date named by hand is honoured whether or not `holidays`
is installed.

### Completion

Each level counts what is under it in the way that suits what that level is:

| Level | How its completion is worked out |
| --- | --- |
| **Subtask** | Its own percentage, like every other row. It was a tick box until the Task above it learned to average percentages |
| **Task** | With sub-tasks, the even average of their percentages - counted, not weighted, a checklist being a checklist. Without, the percentage typed on it |
| **Phase** | Its tasks averaged evenly. One being longer is not a reason for it to count for more |
| **Anything else with children** | Weighted by how long they run, so a fortnight counts for more than an afternoon. This was the `Deliverable`'s rule; it stays as the answer for a parent that is neither a `Phase` nor a `Task`, which a plan read from another format can hold |
| **Empty container** | 0%. No work under it, none of it done |

Percentages are clamped as they are read, so a child carrying something
outside 0 to 100 - which nothing writes, but an imported file can hold -
cannot pull its parent outside it either.

### Task List View (`views/task_list.py`)
- **Drag-and-Drop**: Rows are reordered by dragging, in plain Tkinter. A row moves within its own set of siblings, so a sub-task stays under its parent, and a thin blue line marks the edge it would drop against
- **Context Menu** (`views/contextmenu.py`): Right-click (two-finger click on macOS) any row for Move to top / up / down / bottom, Indent and Outdent, a Create submenu (Phase, Task, Subtask, Milestone), Edit and Delete, Copy, Cut, Paste and Paste as Sub-Task, then Undo and Redo; entries that would do nothing are greyed out. Deleting asks first, says how many sub-tasks go with the task, and is undoable. Right-clicking a row that is already part of a multi-row selection keeps the whole selection, so Copy and Cut act on all of it
- **Create at a Row**: Create builds the chosen type at the row the menu was opened on — a sub-task inside it, a task or milestone beside it — rather than at the end of the plan. Right-clicking the empty space below the last row opens the menu too, and creates at the end of the plan
- **Indent / Outdent**: Indent moves a task under the row above it; outdent lifts it beside its parent. **Neither changes what the row is** — see *The Levels, and Moving Between Them* above. **Both act on every selected row**, as Copy and Cut do, and land them side by side rather than in a staircase: indent runs top to bottom so each row goes under the same sibling, outdent runs bottom to top so the rows keep their order. Selecting a parent and its children moves the branch once, not twice. A branch moves as a whole, one press is one undo, and the moved rows stay selected
- **EditTaskDialog** (`views/taskdialogs.py`): The task form over an existing task. Buttons read Help and Delete (set apart), then Close, Save & Close, Save & New
- **CreateTaskDialog** (`views/taskdialogs.py`): The same form over a new one, for any of the five work item types
- **Treeview Display**: ID, Name, Type, Duration (Days), Start Date, End Date, Progress, Dependencies, Milestone. Columns keep whatever width they are dragged to, and the horizontal scrollbar reaches anything that no longer fits
- **Hierarchical Display**: Sub-tasks are visually indented under their parent tasks with tree structure
- **Cut rows are held apart**: a row waiting to be pasted somewhere is greyed until it lands
- **Features**:
  - Two quick clicks open the editor; a slow second click renames in place; the arrow expands and collapses
  - Create tasks with all fields visible at once (no more one-by-one input)
  - Circular dependency prevention (including parent-child relationships)
  - Milestone toggle with automatic end_date handling
  - Colour chosen from a popup palette, built the first time it is opened
  - Start and end dates picked from a calendar, or typed as YYYY-MM-DD
  - Save & Close, or Save & New to keep entering tasks without reopening the dialog
  - Dependencies set on the form's own Dependency tab, which is built the first time it is looked at
  - Parent Task display for sub-tasks

### The Task Form (`views/taskform.py`)

The form both dialogs show, across three tabs: **General**, **Notes** and
**Dependency**.

Every section but the first opens under a rule; Basic Information opens the
tab, where the top of the panel already does the dividing.

The three long dropdowns — Scheduling options, Working calendar and Shape —
are held to `MENU_WIDTH` and anchored left rather than filling their column.
Stretched across the form a menu is several times wider than the longest thing
it can say, and it grew with the window, so the mismatch got worse the more
room there was. One width for all three: they sit in three different sections,
and a ragged right edge down the form reads worse than a little slack after
"Rounded".

The fields run down the General tab in reading order, and the **Scheduling
options** menu sits directly above **Start Date** because it says which of the
three boxes under it — start, end, duration — the form fills in for you. Read
*after* them it explained a shaded box the user had already tried to type in.

The notes have a tab of their own. They were the last row of the field grid
once, so a box meant for paragraphs sat under everything else at the height of
one; then a column beside the fields, which gave it the height it wanted but
took half the width of the form to do it, on every edit, whether or not the
task had any notes at all. A tab costs the fields nothing and gives the notes
the whole window when they are what you came for.

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
- **Progress**: a percentage on every row that carries its own, and
  nothing to fill in on a container that takes its own from its children
- **Built to be quick**: the form is built in a scrolling frame of the
  application's own (`views/scrollframe.py`) rather than CustomTkinter's, whose
  scrollbar forces a full layout pass of the window on every draw - 3.2ms a
  wheel notch against 0.11ms. The Dependency tab and the colour palette are
  both built the first time they are asked for

### Copy, Cut and Paste (`utils/copypastecut.py`)
- **Acts on the selection**: from the right-click menu, the Edit menu, or
  Cmd/Ctrl+C, X and V - the modifier is the platform's; see
  `gantt_app.shortcuts`. Shortcuts stand aside while the focus is in a text
  box, so editing text behaves normally
- **One answer to where a paste goes**: `ClipboardService.resolve_target`.
  Three routes ask - the keyboard, the toolbar and the right-click menu - and
  each of them used to work it out for itself, in three different ways, so the
  same paste landed in three different places. A paste **takes the position of
  the row the cursor is on, at that row's own level**, and pushes that row
  down, which is what the reference tool does
- **Inside is a separate action**: `Paste as Sub-Task` on the right-click menu.
  A row is where you stand, not what you paste into
- **The end of the plan is a place you can point at**: the right-click menu
  passes no row when it was opened over the empty space below the last row,
  and that means the end of the plan - the same gesture that creates a task
  there. It used to be filled in from the selection instead, so the rows
  landed beside whatever happened to be selected halfway up the plan while
  the entry sat there enabled, looking like it had worked. `FROM_CURSOR`
  tells the two apart: `None` is the end of the plan, the sentinel is
  wherever the cursor is
- **Refused rather than guessed at**: a paste with nothing selected *and*
  nothing pointed at says what is wrong in the status bar, as does a paste
  into a level that cannot hold it
- **A row stands for the work under it**: copying a phase copies the phase,
  its tasks and their sub-tasks, nested as they were. This
  was the other way round on purpose - a plan is a tree, and duplicating a
  branch is not what picking one row means - until the project manager using
  it pointed out that there is no insert key, so copy and paste is how a plan
  gets filled in, and a copy that empties every container it touches makes
  you rebuild by hand exactly what you were copying to avoid rebuilding by
  hand
- **A cut moves the branch by moving its top**: the rows under it go on
  pointing at it, so they travel with it without being named. Naming a child
  as well as its parent would move that child in its own right, out of the
  parent it is meant to be travelling inside - so what goes on the clipboard
  is the topmost row of each branch, while the greying covers all of it
- **Links follow what was copied**: a dependency between two rows in the same
  selection is re-pointed at their copies; one pointing outside the selection
  is dropped, rather than wiring the new row into the plan the moment it
  appears. A cut keeps its links, having moved rather than been remade
- **Held to the levels of the plan**: a phase belongs at the top, a task
  in a phase, a sub-task in a task. Paste is greyed out where an item does not
  belong, and a selection with one item that does not fit is refused whole.
  Pasting a task inside itself is refused
- **One step in the undo history**: the paste is recorded as what the task list
  looked like before it and after it - including every row's dates, so an
  action that reschedules can be undone whole; see `SnapshotCommand.FIELDS`. It used to reach
  the project directly and be recorded as nothing at all, so undo reached past
  it to whatever the user had done before, deleting a row they had made
  earlier while the pasted one stayed
- **Numbered like the rest**: nothing is renumbered, because the number beside
  a row is where it sits; see `Project.display_ids`
- **One place answers each question**: whether Copy and Cut apply was answered
  on the task list, on `ClipboardService` and on `ClipboardManager`, and only
  the task list's was ever asked - so the one deciding what the user sees was
  the one with no test. None of the three consulted the clipboard either,
  because the clipboard is not what decides: copying needs a selection, and
  the selection is the task list's to report. The manager's surface is now
  what the application actually calls
- **Let go of when another plan is opened**: every handler that replaces the
  plan on screen already cleared the undo history, for the obvious reason
  that edits to a plan no longer open cannot be applied to the one that is.
  The clipboard is the same argument and was not making it - a row cut from
  the previous plan stayed on the clipboard, and the paste that followed
  looked its ID up in the new plan, where that number belongs to a different
  task. See `Toolbar._forget_the_previous_plan`
- **Reaches the desktop clipboard**: through Tk's own, so it needs no extra
  package. What is written is a readable list of what was copied, then a
  marker, then the same thing as JSON - so it pastes into a mail as text and
  back into this application as tasks

### Link and Unlink Tasks (`Project.link_tasks`, `Project.unlink_tasks`)
- **Chains the selection Finish-to-Start**: one link per neighbouring pair,
  top to bottom, with no lag - the first row becomes the predecessor of the
  second, the second of the third. `⌘F2` on a Mac and `Ctrl+F2` elsewhere, or
  the chain icon on the row
- **Chained at the level you are working at**: the topmost rows of the
  selection. A row that holds work is bracketed by that work, so selecting a
  branch and the rows inside it is one thing running after another, not four
  - and chaining every row in reading order tied each container to the first
  row inside it, which is a contradiction rather than a chain: the
  container's dates are rolled up from its children, so a child made to wait
  for its own parent waits for a date computed from itself. The plan then
  never settled, and every action moved it further out
- **A collector is moved by moving what is inside it**: a link *to* a row
  that holds work used to be drawn on the chart and never obeyed, because
  the scheduling pass skipped such rows - their dates come from below. The
  whole branch is shifted instead, by the same number of days, so the row
  goes on bracketing its own work; see `Project._pull_branch_after_its_links`
- **In the order the rows are shown, not the order they were clicked**: a
  Treeview reports a selection in the order rows were added to it, so
  shift-clicking upwards from the bottom of a group hands them back
  bottom-first and a chain built from that would run backwards through the
  plan. `Project._in_display_order` is what settles it
- **Adds rather than states**: a row goes on waiting for anything outside the
  selection that it already waited for
- **A pair that would close a loop is skipped**, and the rest of the chain is
  still made. Refusing the whole thing would leave a selection with one
  awkward pair in the middle of it doing nothing at all, with the reason
  buried
- **Unlink takes out what is between the chosen rows** and nothing else, so a
  link to a row nobody pointed at survives. A single row has no "between", so
  what goes is every link it is part of, in both directions
- **The plan reschedules immediately**: a link that has just been stated is
  one the dates are supposed to obey, and a button that accepted a link and
  moved nothing would look like it had not worked
- **One entry in the undo history** for the whole chain, however many pairs it
  joined - and the rescheduling runs inside that entry, so undoing a link puts
  the dates back as well as the link. Taking the link out and leaving the row
  where the link had pushed it left the column and the dates disagreeing; see
  `SnapshotCommand.FIELDS`

### What Is On Which Menu (`views/toolbar.py`)
- **File**: opening, creating and saving a plan
- **Actions**: import and export, each a submenu of formats - what is *done
  to* a plan, rather than the plan's own file
- **Settings**: the three panels that describe the whole plan - Project,
  Calendar and **Gantt Settings**
- **Edit**: **Create** first, because everything under it acts on a row that
  has to exist already, then Undo, Redo, Cut, Copy and Paste
- **View**: what is about this window - the day/night mode, **Critical
  Path...** and Help

**File is what a file menu is called.** It held the imports and exports while
a second menu called **Project** held the new/open/save that every other
application puts under File, so the one place a reader looks first for Save
was the one place it was not. The imports and exports are the pair that needed
the other name: they are things done to a plan rather than to its file.

**Critical Path is under View** because it changes what the window shows
rather than what the plan says — as does the icon beside it, which paints the
critical rows into the list instead of opening the report.

### Menus That Open Out Of Menus (`views/toolbar.py`)
- **Hover text is held back while a menu is open.** It is scheduled on a
  delay and shown by a timer, so one started by the pointer passing over a
  toolbar button on its way to a menu arrived after the menu had opened and
  drew itself on top - an always-on-top window over another one. Opening
  Actions showed "Bold  (Cmd B)" written across its entries. Held back
  rather than switched off: the pointer is still where it was, so the text
  comes back when the menu goes. Counted rather than flagged, because a
  submenu is open while its parent is; see `tooltip.hold_back`
- **Every pixel of a row runs it.** A row is bigger than the button in it:
  the chevron on a row that opens a submenu is a label with nothing bound to
  it, so the right-hand end of those rows was dead, as was the padding around
  any entry. The row, its own canvas and everything beside the button carry
  the action now; see `CTkDropdownMenu._answer_across_the_row`
- **And a row answers every click, not every other one.** CustomTkinter runs
  a button's command from `<ButtonRelease-1>`, but only while `_mouse_inside`
  is set - and `_on_release` clears it *before* running the command, so a
  button that has been clicked once will not answer again until the pointer
  has left it and come back. In a menu, which appears under a pointer that
  then barely moves, that is a row ignoring clicks for no reason the user can
  see. A press on the entry says the pointer is on the entry, so the press
  re-arms it. The command is left in place rather than replaced, so `invoke()`
  still works and the press still animates
- **A menu knows what opened it.** A menu dismisses itself when a click
  lands outside it, and the click that opens one always does: the row or the
  button that brings a menu up is not part of the menu it brings up. The
  opener counts as inside; see `CTkDropdownMenu._opener`
- **This is what broke Create, Import and Export.** A submenu is watched by
  the window it is opened over, and for a menu that is the menu itself
  rather than the application window - so the press on Create was delivered
  straight to the submenu it had just built, landed on a row belonging to
  the parent, and was read as a click somewhere else. The submenu destroyed
  itself before it was ever drawn, with all of its rows already in it
- **`CustomMenuBar` had the guard for the row of buttons along the top** and
  nothing had it anywhere else, which is why the top-level menus opened and
  the ones inside them did not

### One Registry Per Icon (`resources/icons.py`)
- **An icon is a list of strokes in a unit square**, painted with Pillow at
  whatever size and ink the row asks for; see `ICON_STROKES` and `draw_icon`
- **There used to be three registries**: an emoji per icon, an SVG path per
  icon, and the strokes. Both of the first two were complete, carefully kept
  in step, and unreachable from the application - the toolbar paints from the
  strokes and falls back to the name's first letter, never to an emoji. So
  adding an icon meant editing three dictionaries, one of which changed
  anything on screen
- **The tests followed them**, asserting that the two unused dictionaries were
  complete. They now assert that every icon on the toolbar row has a drawing
  and that every drawing actually puts ink down, which is the failure worth
  catching: a button with nothing on it
- **`ICON_NAMES` is taken from the drawings** rather than kept as a list of
  its own, so the two cannot drift apart

### A Form Opened From A Menu Is Not Waited On (`GanttApp.edit_task`)
Choosing Edit on a sub-task left the application with a spinning cursor and
nothing on screen, recoverable only by Force Quit. The log stopped dead after
the line that opens the form.

The edit and create forms were opened and then waited on with
`wait_window()`, which runs a second event loop until the form closes.
Nothing needed the result - both hand their work back through the callbacks
they are given - so the wait bought nothing and cost the caller its ability
to return. And the caller is reached from the right-click menu, which on
macOS is a native menu whose tracking loop `tk_popup` does not return from
until the menu has finished; see `TaskContextMenu._after_menu`, which defers
those entries onto the idle queue for exactly that reason. A second loop
entered from inside the first is a place an application can stop and not
come back from.

The forms are still modal - through their own grab, which is where modality
belongs.

### Mark On Track Only Ever Brings A Row Forward (`Toolbar.mark_on_track`)
A figure on a row is something somebody reported. The on-track figure is what
the calendar expects of it. Where the two disagree and the report is higher,
the report is the one that knows something - so a row further along than its
dates suggest is left exactly as it is.

It used to write the expectation over the report either way. A project
manager reported a morning's progress against work whose dates were still
ahead, pressed the button with **Entire Project** chosen, and watched 25% and
75% become 0%, because the calendar expects nothing of work that has not
started. A morning's reporting gone on one press, with nothing but Undo to
get it back.

When nothing is behind, it says so, and says how many rows it left alone for
being further along than that.

### A Summary's Length Is Its Span (`Project.roll_up_summaries`)
A row with children brackets them: its dates are rolled up from below on
every scheduling pass. Its stored `duration` was not, so it kept the number
it was created with - and the working-calendar pass believed that number,
rebuilding the finish from it while the roll-up rebuilt the finish from the
children. The two took turns for all twelve passes of the reschedule loop,
which then reported a cycle in links that had none and left the dates
wherever the last pass happened to put them. Every later action ran the loop
again and left them somewhere else, which is what a plan "scrambling" its
collectors looks like from the outside. The roll-up writes the duration too
now, so the two agree and the loop settles.

### How Far Along A Row Is (`views/taskform.py`)
- **Every row carries a percentage**, including a sub-task. It was a tick
  box - done or not - because the Task above it counted how many of its
  sub-tasks were ticked, so a 60% would have been a number the form took and
  the plan ignored
- **A Task averages its sub-tasks' percentages**, evenly. That is what
  counting ticks was all along: a checklist holds nothing but 0 and 100, and
  the average of those is the proportion ticked. Two of four ticked was 50
  and still is, so every plan written before this reads exactly as it did -
  what is new is that a sub-task half done now says so instead of counting
  for nothing
- **Still counted rather than weighted.** Four sub-tasks of an hour each are
  four entries like any other four; how long a thing runs is the Phase's
  business, one level up
- **Nothing about the form asks the machine.** This began as "the progress
  bar is not viewable on a different Mac", with two editors side by side -
  one showing `Progress (%)` and one showing `Completed`. They were a Task
  and a Sub-task. `tests/test_progress_field.py` fails if the choice ever
  starts asking the platform

### The Dependency Chooser (`views/dependency_editor.py`)
- **Names a task by its number and its name**, because the number is what the
  reader is looking at in the ID column; see `Project.display_ids`
- **Walks the plan once per redraw.** It used to call `Project.display_id`
  per row, which builds the whole map to answer for one task - so drawing the
  dropdown walked the hierarchy once per row it was about to draw. A plan of
  eight hundred tasks walked its own hierarchy 799 times and took 0.175s to
  open the dialog; it now walks it once and takes 0.020s
- **Reads the choice from what the dropdown was built from**, not by
  formatting every candidate's label again and matching the string. The
  labels were never ambiguous - two rows cannot share a number, so two tasks
  with the same name are still told apart - but re-deriving the list to read
  a choice out of it means the answer depends on nothing having changed in
  between

### Reading XML From Elsewhere (`utils/safexml.py`)
- **Entity declarations are refused**: the `.gan` and MSPDI importers read
  files that arrive from outside, and read them with `ElementTree` straight -
  which the standard library's own documentation lists as vulnerable to entity
  expansion. Measured against this application's own parser, a 700-byte file
  expanded to three million characters and a 150-kilobyte one to a hundred
  megabytes; each further level of nesting multiplies by ten. Nothing in a
  plan needs an entity of its own, so none is allowed
- **Refused before anything is expanded**: expat parses the document once with
  a single handler registered, one that raises the moment an entity is
  declared. Declarations come before the references that use them, so a
  hostile file is stopped at the DOCTYPE - the measurements above become
  fractions of a millisecond
- **External entities were never a risk**: `ElementTree` does not resolve
  them and raises on an undefined entity instead. That was checked rather
  than assumed
- **No new package**: the guard is one expat handler saying no, and the
  standard library already has expat. `defusedxml` is the usual answer and
  would work, but this application bundles what it ships - see
  `requirements.txt` and the note there about what is deliberately left out
- **The refusal is a `ParseError`**, which is what it means to an importer:
  a file that will not be read. Both already turn one into a logged failure

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
- **Summary Bars**: Any other task with sub-tasks - a `Task` with work under it - is drawn as a spanning bracket rather than a solid bar
- **Labels**: Task names displayed next to milestones
- **Date Formatting**: Proper date display with tick formatting
- **Empty State**: Helpful message when no tasks exist
- **Dynamic Sizing**: Chart height adjusts based on number of tasks

### Menu Bar and Action Bar (`views/toolbar.py`)

Two rows, one above the other, because they are two different things.

**The menu bar** names everything the application can do, the way a menu bar
on any desktop does:

- **File**: New Project, Load Project, Save Project, Save Project As
- **Actions**: Import (MS Project, GAN, Mermaid, XLSX) and Export (GAN, MS
  Project, Mermaid, HTML, SVG, PNG, PDF, XLSX)
- **Settings**: Project Settings, Calendar Settings, Gantt Settings
- **Edit**: Create (Phase, Task, Subtask, Milestone), Undo, Redo, Cut, Copy,
  Paste - the clipboard three carry the key they answer to, written the way
  this platform writes it (`⌘X` on a Mac, `Ctrl+X` elsewhere)
- **View**: System UI mode, Critical Path..., Help
- **Log**: Opens the application log window, at the end of the row

**The action bar** under it carries the handful worth reaching for without
opening a menu, in groups divided by a hairline:

- save, save as
- edit the selected task, indent it, outdent it
- the formatting group — B, I, U, text colour, background fill, presets,
  clear — set apart by a hairline on each side, because it changes how the
  plan is *drawn* rather than what the plan says
- the progress group beside it — 0/25/50/75/100% and Mark on Track — which is
  the other thing done to a row already picked out: mark it up, then say
  where it has got to
- link and unlink, which chain the selected rows Finish-to-Start and break
  those links again. They act on what is selected, like the three before them
- critical path, alone between two hairlines: it neither edits a row nor
  moves one about, so it belongs to neither group beside it
- cut, copy, paste, delete, undo, redo

Against the right edge, reading from the right: the **?**, a divider, the
**day/night toggle** with the **sync** button beside it, a divider, the
**search box**, and a divider. Sync is a drawing with "Sync with the System"
on hover rather than the sentence written out - as a caption it was 124
pixels of text in a row of 36-pixel icons, the widest thing on that side, and
it pushed the search box that far in from the edge. It is also packed beside
the toggle by name: packed only by side it landed at the end of the
right-hand group, which by the time an appearance is chosen is past the
search box, so it turned up at the far left of the row against undo and redo.

Opening and creating a plan are on the **File** menu rather than here, as
are the work item types, which are on **Edit → Create**. What is left
on the bar is what gets used repeatedly while a plan is being built, which is
the only thing an icon earns its place with.

**The pencil edits the selected task**, not the project title. It used to open
the project title box, which is a different kind of thing entirely: a plan has
one title and a great many tasks, and an icon sitting among the actions that
work on a row reads as the one that edits a row. Renaming the plan is on
**Actions → Project Title**, beside the other project-wide settings.

**Every button says what it is on hover** (`views/tooltip.py`). The captions
had been written from the start — one per entry in `ICON_ACTIONS` — and were
stored on the button as an attribute that nothing ever read, so the row was
legible only to whoever drew it.

The icons are **drawn** (`resources/icons.py`), a few strokes each painted with
Pillow at four times the size and reduced. They were set in "Segoe UI Emoji"
before, a font that ships with Windows and with nothing else, so the whole row
came out blank on Linux. Drawing depends on no font being installed.

**Save writes back; Save As asks.** Save used to open a file chooser every
time, which made it a second Save As under a different name — saving twice
meant picking the same file twice and confirming the overwrite. It now writes
to wherever the plan was last saved or loaded from, and only asks when there
is nowhere to write yet. A new plan clears that path, so Save on a new plan
asks rather than writing over the file the last one came from.

### Keyboard Shortcuts (`shortcuts.py`)

Every shortcut in the application was written out as `Control`. On a Mac that
is not the key anybody reaches for, and it is not the key macOS reports when
they press Cmd — so the shortcuts did nothing there while their captions
promised otherwise.

The sequence Tk binds and the text a tooltip shows come from the same place,
because they have to agree: a caption naming a key that is not bound is worse
than no caption, and the two drift the moment they are written separately.
Both letter cases are bound, since Tk reports the upper case one under caps
lock.

One thing worth knowing when testing this: Tk stores a binding under a
spelling of its own choosing — `<Command-b>` comes back as `<Mod1-Key-b>` —
so a test cannot check the modifier by reading the binding back. Which
modifier goes *in* is pinned exactly in `test_shortcuts.py`; the tests that
bind them check only that something arrived for each key.

### Progress Tracking (`views/progressgroup.py`)

**Reporting is a weekly job over forty rows, and almost none of it involves
choosing a number.** A task is not started, underway, or done — and the rest of
the time what is wanted is "this is where it should be by now". Typing a
percentage into a task editor one row at a time is the slowest possible way to
say any of that.

**Mark on Track counts working days, not calendar days**, and the difference
shows up every weekend: a five-day task starting on a Friday is 20% through by
Sunday, because one of its five days has been worked — not 40% because two
nights have passed. Both halves of the fraction use the task's own calendar, so
a holiday inside the span comes off the elapsed count and off the total alike.
See `Project.progress_on_track`.

**A summary is never written to directly.** Its completion is rolled up from
its children and would be replaced by the next reschedule, so pressing a
percentage on a phase marks the work underneath it instead — ignoring the press
would be worse, since selecting a phase and pressing 100% has one obvious
meaning.

The status date is today. The specification allows for one named by the reader,
and there is nowhere to name it yet, so the log and the messages say which date
was used rather than leaving it to be guessed at.

### Row Formatting (`taskstyle.py`, `views/stylebar.py`)

**The chart is for sanity-checking dependencies; the task list is where the
work happens.** A plan of any size is scanned rather than read, and the rows
worth finding again — the payment milestones, the phase gates, the things that
are finished — have to be findable at a glance. A Type column does not do
that, because scanning is exactly the activity that skips columns.

So a row carries a `TaskStyle`: an ink, a fill, and three emphases. It travels
with the plan, it goes through the undo history, and marking forty rows and
pressing undo once puts all forty back.

**The emphasis flags are three-valued, and that is not fussiness.** A summary
row is bold without anybody asking. With a plain `True`/`False` that automatic
bold would be indistinguishable from one somebody chose, and two things would
break: pressing **B** on a summary would appear to do nothing (it is already
bold), and clearing a row's formatting would leave a summary looking like a
leaf. `None` means "whatever this kind of row is by default"; see
`taskstyle.resolve`.

**A default style serialises to nothing.** Almost every row in almost every
plan carries no formatting, so writing five nulls per task would grow every
saved file for nothing.

**What the selection says.** With several rows selected, a toggle reads as on
only when every one of them has it and a colour only when they all carry the
same one. Showing the first row's formatting would be a lie about the rest,
and pressing **B** would then turn bold *off* for the rows that had it rather
than on for the rows that did not.

The group sits on the icon bar between two hairlines, with `Ctrl+B` / `Ctrl+I`
/ `Ctrl+U` bound on the window so they work wherever the focus is. Both cases
of each letter are bound: Tk reports `<Control-B>` when caps lock is on, and a
shortcut that stops working with caps lock is the kind of fault nobody reports
and everybody notices.

### Menus That Can Always Be Dismissed (`views/toolbar.py`)

Menus were going behind the main window and leaving the application looking
unresponsive, and the cause was a binding that removed more than it was asked
to.

Every popup bound `<Button-1>` on the main window to notice a click outside
itself, and unbound it on close. **`tkinter`'s `unbind(sequence, funcid)` does
not remove one binding** — it clears every binding for that sequence on the
widget and then deletes the one command. With two popups open, the first to
close took the second's dismissal with it. The second, being borderless and
always-on-top, then had nothing able to close it: it stayed on screen and
dropped behind the main window the next time that was raised. Recovering meant
going out to the window manager, which is what breaks the deadlock.

`watch_for_click_elsewhere` binds the window **once** and keeps a list of
watchers. Registering and unregistering is list mutation, so nothing touches
Tk's binding table after the first popup and no popup can disturb another's
watch — nor the window's own bindings, the formatting shortcuts among them,
which were being cleared too.

Two other faults fell out of the same investigation. `CTkDropdownMenu` relied
on `<FocusOut>` alone, and an `overrideredirect` window does not reliably take
focus on macOS, so the event may never come — it watches for clicks now, and
`lift()`s when it opens. And the menus opened from the formatting bar and the
progress group had no dismissal of any kind; they inherit it now that the menu
class carries its own.

This is the third time this exact `unbind` has caused a bug in this codebase.

### Project Settings (`views/projectsettings.py`)

Everything on this panel used to be either unreachable or spread across three
places: the title behind a one-line prompt, the calendar behind a different
dialog, and the start date not settable at all — it was whatever the earliest
task happened to say, so moving a plan meant editing every task in it.

**The form is a grid, and every control is a child of the frame it sits in.**
The first version built them all with the window as their master and packed
them into per-row frames. Tk permits that — the frame shares the controls'
master ancestry — and then lays them out against the *toplevel* rather than
the frame: labels cascading down the top left, controls stacked at the bottom,
half the text off the right-hand edge. Nothing raised, and every test of the
time passed, because they all asked what the panel *did* rather than what
shape it was. There are now tests for the shape.

**Not everything on it is a setting.** The start date is not a field on a
project — it is derived from the tasks — so that box is a *command*: typing a
date moves the whole plan. Every task shifts by the same number of calendar
days, which is what preserves it. Rescheduling from the new date instead would
pull everything up against its links and collapse every gap somebody had put
there on purpose.

The finish date is the same while the plan runs forward, where it is an answer
rather than a question, so the box and its calendar button are both shut — one
that accepted a date and then ignored it would be worse than one that refused.
Switch **Schedule from** to the finish date and it becomes the deadline.

**Backward scheduling reuses the backward pass that was already there.**
`schedule_analysis` computes a `late_start` and `late_finish` per task — the
definition of "as late as this can be without the project finishing later" —
and until now those were read for the float and thrown away.
`apply_backward_schedule` writes them onto the tasks and then anchors the
packed plan against the deadline. There is no second scheduler.

Nothing is rescheduled afterwards, deliberately: `reschedule` only ever moves a
task *later*, which is what the backward pass has just finished doing on
purpose. The late dates satisfy every link by construction. The behaviour that
tells this apart from merely sliding the plan is a task with float — a slide
keeps it early, and As Late As Possible pushes it up against the finish.

`Project.apply_schedule` dispatches on the direction and is what every refresh
now calls. A plan scheduled forward gets `reschedule` and nothing else, which
is the whole of the previous behaviour.

### Editing in the Grid (`views/task_list.py`)

Two cells are typed over in place rather than through a dialog: the task's
name and its dependencies. Both go through one editor — a plain `tk.Entry`
placed over the cell, committed by Enter or by the focus leaving, abandoned by
Escape.

A plain entry rather than a `CTkEntry`, deliberately: a `CTkEntry` is a frame
holding an entry and draws its own border and corners, which at the height of
a grid row leaves the text clipped and the cell it is covering showing round
the edges.

**The editor is taken away before anything is stored.** Storing redraws the
list, which destroys the row the entry is sitting on — and an entry left over a
row that no longer exists is a box floating over the wrong task.

**Double-click no longer folds a branch.** Folding is on the expander beside
the row, where it is in every other tree, and where it already was — having it
on both meant a double-click on a parent's *name* folded the branch away
instead of letting the name be typed over, which is what somebody
double-clicking a name wants.

**Two clicks mean two different things, and the pause is what tells them
apart.** Two quick clicks open the task editor; a click, a pause and a second
click open the name for typing over. Both gestures start with the same press
on an already-selected row, so the slow one cannot commit at that moment: the
release schedules the rename `RENAME_DELAY_MS` (600ms) out and `on_double_click`
cancels it if a double-click arrives inside that. Without the cancel the editor
opened and the name box appeared over the list behind it a moment later.

The wait is long enough for anything to have happened in it, so
`_rename_if_still_wanted` asks again when it fires rather than trusting what
was true when it was scheduled — the row may have gone, or the selection may
have moved. `destroy()` cancels a pending one, for the same reason it cancels a
pending status message: a timer firing into a destroyed widget is a Tk error.

A name typed here goes onto the task through the undo tracker, so the editor
reads it and one Undo takes it back. An empty name puts the old one back
without saying anything: a row has to be called something, and a dialog thrown
up because somebody clicked away from a box they had cleared would be a
reprimand for a slip.

### The Dependencies Column (`dependencysyntax.py`)

`003SS+1d` is how every planning tool has spelt a dependency for thirty years,
and the column now takes it. The grammar is a predecessor's number, then
optionally the kind of link, then optionally a signed lag with a unit —
everything else is defaults: no type means Finish-Start, no unit means days.

**The grammar is a contract**, because the cell is normalised after every
edit: what is written back has to be readable by the same parser, or the
column rewrites the reader's work every time they press Enter. There is a test
that round-trips every form in the specification's table.

**Nothing is guessed at and nothing vanishes.** A cell that cannot be read
entirely is not stored at all — not even the part that parsed, because
storing half of it would silently drop the rest and leave the reader comparing
what they typed against what came back. The four things a number alone cannot
answer — a task that is not there, a task naming itself, the same task twice,
and a link that closes a loop — are all checked against the plan, and each
link is checked against the ones already accepted from the same cell as well
as against what the task already holds. `1, 2` where 2 already waits for 1 is
a loop that only exists once both have been taken.

**The number is the display id, not the identity** — the column asks for what
is on screen. Resolving it to the task it names happens in
`Project.parse_dependencies`, which is also where the guards live, because
every one of them needs the plan.

Lag gained a unit: days, or a percentage of the predecessor's own duration, so
a plan can say "start this when that one is half done" without working out
what half of it is and reworking it whenever that task changes length.

**The scheduling engine is unchanged for every link that already existed.**
Adding a unit put a branch in front of every read of a lag, and that branch
has to be invisible: `Project.lag_days` returns a lag in days untouched, so
the forward pass, the backward pass and the float all compute exactly what
they computed before. A percentage is the only new arithmetic, and it can only
apply to a link that could not previously be stated at all. It rounds half
away from zero rather than through `round()`, which rounds half to even —
half of a five-day task came out as two days and half of a seven-day task as
four, which is not a rule anybody would guess at.

The unit had to reach four other places to avoid being silently dropped: the
undo snapshot, the clipboard, the reversed graph the backward pass walks, and
the signature the critical-path cache is keyed on — a signature that could not
see the change would hand back a stale float for as long as the window stayed
open.

### Two Identifiers (`Project.display_ids`)

A task carries two numbers that used to be one.

**`Task.id` is the identity.** Dependencies, parents, the clipboard, the
tree's row ids and every entry in the undo history are keyed on it, and it
never changes because a row moved. It is also **never shown**: it is a key,
and a key in the column where every other row shows its position would be read
as a position. The task editor, the dependency chooser and the search all use
the display number instead.

**The display id is where the row currently sits**, counted from one down the
list — and it is *derived*, not stored. That is the whole design. A stored
number would have to be rewritten on every reorder, insert, delete and indent,
and each of those is already recorded in the undo history against `Task.id`;
renumbering a stored field after the change would leave that history pointing
at numbers naming nothing, so undo would restore an order of rows that had
ceased to exist. Derived, there is nothing to renumber and nothing to undo,
and the number is right the moment the row moves.

The Predecessors column shows those same numbers rather than task names, so a
link renumbers with the rows while still pointing at the task it always
pointed at.

**The exports carry the number, not the identity.** A GanttProject file, an
MSPDI file and the spreadsheet all name a task by what the task list calls it
— otherwise a file read back against the plan names rows by a key the reader
was never shown. Both XML exporters take it from `Project.display_ids` through
the shared plan walk, so neither can drift from the list.

The spreadsheet's numbers have gaps where phases sit, because it holds one row
per piece of work and shows phases as a column beside them. That is the right
way round: a sheet read against the plan has to call a task what the plan
calls it.

Mermaid is the exception. Its ids are a syntax token that `after` references
point at inside the same file, not a number anybody looks up, and they carry
the lossless round trip — so they are left alone.

### How a Row Is Painted (`views/task_list.py`)

**One tag per row, carrying everything.** A `ttk.Treeview` row with two tags
that both set a background leaves it to Tk which one wins. The whole
appearance — banding, the row's fill and ink, the outline's bold, the greying
of a cut row — is resolved in Python onto a single tag instead, so the
precedence is something this application states and a test can check rather
than something the platform decides.

The order is: **what a row is doing beats what it was given.** A row waiting
to be pasted, or on screen only to say where a search match sits, is greyed
whatever ink it carries — those mean "not the row you are looking at", which
outranks decoration. Its fill is left alone, so a marked-up row is still
recognisable while you are moving it.

Tags are shared by every row that resolves the same way, so a plan with forty
rows marked as financial milestones configures one tag rather than forty.

**Fonts are specifications, not objects.** A `tkinter.font.Font` is a thing in
the Tk interpreter with a lifetime; one built here outlives the root that made
it, and deleting it later reaches into an interpreter that may already be
gone. A `(family, size, modifiers)` tuple is just a description — Tk reads it
when the tag is configured and nothing owns anything afterwards.

**The banding is applied after the rows are in place**, in the order the tree
actually draws them. Roots are inserted first and their children follow in
later passes, so counting at insert time put a phase and the task nested under
it in the same shade with the banding restarting underneath them.

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

**The round trip is lossless.** Mermaid has one grouping level where a plan has
four, two states of progress where it has a percentage, and one kind of link
where it has four — so a plan exported and read back came home flattened,
untyped, at 0% and, worst of all, on dates it never held.

Two things fix that:

- **The chart itself is written correctly.** `after X` means "the day after X
  finishes" and nothing else, so it is only written where it reproduces the
  date the task actually has — checked against the answer first, the same way
  the spreadsheet export checks its `WORKDAY` formulas. A Start-Start link, or
  one carrying a lag, gets the date written out instead. Progress is written as
  Mermaid's own `done` and `active` tags.
- **What Mermaid cannot say travels in a `%%` comment**, which every renderer
  ignores: the work item types, the levels below the one section a chart can
  show, the exact percentage behind `active`, the colours, and which kind of
  link each dependency is.

The file is still plain, valid Mermaid — it just carries more than it draws. A
chart written by anything else imports exactly as before, including its `done`
/ `active` / `crit` tags and rows that name no ID; an unreadable metadata line
is stepped over rather than costing the whole file.

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

### GAN Exporter (`utils/gan_exporter.py`)

Writes the plan as a **GanttProject file**, the format the application has
read since the beginning. Reading a format without writing it makes the other
tool a source and this one a destination, which is the wrong shape for a plan
that gets passed around.

**GanttProject never stores an end date.** It stores a start and a duration
counted in working days, and works the finish out by replaying the
`<calendars>` block in the file — so an export can be perfectly well-formed
and still show a plan finishing on the wrong day. Two things prevent that: the
calendar goes with the plan, and every duration is counted against that same
calendar.

That is also why a task following a **named calendar of its own** has its
duration counted against the *plan's* calendar rather than its own. A .gan
holds one calendar, so counting any other way would land the finish on a
different day. Such a task keeps its dates and loses the number of days it was
given, which is the right way round: a date somebody can act on beats a number
nobody reads.

- **Hierarchy**: sub-tasks are nested `<task>` elements, to any depth
- **Dependencies**: `<depend>` hangs off the *predecessor* and names the
  successor, so every edge is reversed on the way out — the mirror image of
  what `gan_importer` does on the way in. All four link types and the lag
  travel, and Hard/Rubber map onto GanttProject's own Strong/Rubber
- **Calendar**: the working week as `<default-week>`, recurring holidays with
  an empty year, and everything else a calendar takes off — listed holidays,
  public holidays in an observed country, days taken off by hand — as dated
  entries, written from the plan's first day to a year past its last
- **Task IDs**: the format wants integers and this application has strings, so
  each task is written as its outline position. A file exported and read back
  comes home renumbered from 1, which is what GanttProject would have done
  with it too
- **What does not survive**: a named calendar per task (above), and a day the
  plan *works* that its own week says it should not — a `<date>` entry only
  ever takes a day off. Both are logged rather than written wrong

### MS Project Exporter (`utils/msproject_exporter.py`)

Writes the plan as **MSPDI**, the XML interchange format Microsoft publishes
and Project opens with File > Open. It is not `.mpp`: that is an undocumented
binary format whose only complete writer is Project itself, and the readers
that exist — this application's own MPP import among them — are
reverse-engineered. MSPDI is also what every other planning tool reads, which
`.mpp` is not.

**The dates are pinned.** MSPDI states a schedule the way Project thinks about
one — a duration, a set of links, and a constraint saying what the task is
allowed to do — so handing over durations and links alone hands Project a plan
it will re-solve: every task without a predecessor collapses onto the project
start, and anything scheduled here through something MSPDI cannot say moves.
Each piece of work therefore carries a **Start No Earlier Than** constraint on
the date the plan says. That is a floor rather than a pin: the links are still
written and still push a task out when its predecessor slips, but nothing is
pulled earlier than it was planned. Summary rows carry no constraint, since
Project computes those from their children and refuses a summary that
disagrees.

The rule is the one the spreadsheet export follows for its formulas: a file
that recalculates is worth having, and a file that recalculates to something
other than the plan is worth less than one that does not recalculate at all.

- **Hierarchy**: one flat `<Task>` list with `OutlineLevel` and `WBS` — the
  opposite of the .gan file, where the same hierarchy is nesting
- **Dependencies**: `<PredecessorLink>` sits on the successor, which is how
  `Task.dependencies` already holds it, so nothing is reversed. Lag is written
  in tenths of a minute, the unit MSPDI counts every span in whatever
  `LagFormat` says the reader should display
- **Per-task calendars**: written as separate `<Calendar>` elements and named
  by the task's `CalendarUID`. This is the one thing MSPDI holds and the
  GanttProject format cannot
- **Calendar**: the working week from Sunday (MSPDI numbers Sunday 1 where
  Python starts at Monday), then every date that departs from it — including a
  Saturday the plan *works*, which the .gan export cannot express at all
- **Element order**: MSPDI's schema is a sequence and Project rejects a file
  that reorders it. `CalendarUID` really does belong between `ConstraintType`
  and `ConstraintDate`; the links really do come after every scalar field,
  `Notes` included. Both look like mistakes, so both are pinned down by tests
- **What does not survive**: task colours, which MSPDI has no field for, and
  the difference between a Phase and a summary Task, since Project has one kind
  of summary row. Everything that decides a date goes across

### PDF Export (`utils/page_render.py`)

Three pages, each answering a different question:

| Page | Holds |
| --- | --- |
| 1 | The work item list **beside** the chart — the plan as the application shows it |
| 2 | The chart alone, across the width of the page |
| 3 | The work item list as a full table, every column, no chart |

A PDF of the chart on its own was half a plan: the bars say *when* work happens
and nothing else — not what a row is called past the few characters that fit
beside it, not how long it is, not what it waits for.

On page 1 the chart is given the table's row height and heading height, so row
one of the list sits level with bar one. That is the same `RowPlan` the
on-screen view uses to keep its two panes in step.

**The page is a real page.** A PDF page is pixels plus a number saying how many
of them go in an inch, and the old export saved a 2800-pixel image at 150 dpi —
a page eighteen inches wide that every printer then shrank by an amount of its
own choosing. Pages are now A4 landscape (`PAGE_INCHES`) drawn at
`PAGE_DPI = 200`, so A4 comes out A4. 200 rather than 150 because at 150 the
table is legible on screen and ragged on paper, which is where a plan of this
kind ends up.

Table columns are keyed rather than positional, so page 1 asking for five of
the eight gets the right values in them — paired by position it put Type under
Start and Duration under End, every cell filled and every one of them wrong.

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
| Key Deliverable | The task's own notes - what that piece of work delivers |
| Pred. | Predecessor row numbers - `4`, `4SS`, `4FS+2` |
| Duration (wd) | Working days, editable (shaded, blue text) |
| Start / End | `WORKDAY` formulas over the duration |
| Status | `Not started`, `Ongoing - 30%`, or `Done` |
| … | One column per week, drawing the bar |

**The sheet is live.** Duration is a number the reader can change; Start and
End are WORKDAY formulas over it, so re-planning in Excel behaves the way
re-planning here does - weekends are skipped, and a task pushed out drags the
chain behind it. The timeline bars are formulas over Start and End, so they
follow. Changing the one start-date cell moves the whole plan.

**A formula is only written where it reproduces the date this application
already worked out.** The arithmetic is done first, against the calendar
WORKDAY actually implements rather than the project's own, and where a WORKDAY
chain could not say what the plan says - a task with no predecessor, or one
held by a Start-Start or Finish-Finish link, or one with a lag - the real date
is written instead. A sheet that is live but wrong would be worse than one
that is merely static.

Where the project observes public holidays, they are written to a hidden
`Holidays` sheet and the formulas become `WORKDAY(…, Holidays!$A:$A)`, so
Excel recalculates onto the same dates this application schedules. A **manual
override that takes a day off** is just another date on that sheet and stays
live. One that puts a **weekend day to work** cannot be expressed at all -
WORKDAY's week is fixed at Monday to Friday and no holiday list can widen it -
so any task whose span reaches such a day has its finish written as a date.
The sheet keeps saying what the plan says; those rows simply stop
recalculating.

Rows are the **leaves** of the plan: the work. A Phase, or any row that
brackets other rows rather than being work of its own, appears as the Phase
column and the colour banding, which is how this layout expresses grouping.
Nesting deeper than that is flattened - the layout has one grouping column -
and the Key Deliverable column carries the row's own notes, so what a piece of
work produces stays readable beside it.

- **Optional Dependency**: Gracefully handles missing openpyxl library
- **Directory Creation**: Automatically creates parent directories

### MS Project Importer (`utils/mpp_importer.py`, `utils/msproject_importer.py`)

**"Import MS Project" is offered two entirely different files.** One is
`.mpp`, Project's own binary save. The other is MSPDI, the XML Microsoft
publishes a schema for, which Project writes from File > Save As > XML. Only
the second can be read by anything that is not Project, so `mpp_importer`
sniffs the file it is given — the extension is not trusted, because MSPDI
arrives named `.mpp` more often than not — and sends the XML to
`msproject_importer`.

**Nothing is optional.** MSPDI is read with the standard library, so the
feature works in a source checkout and in the packaged build alike, with
nothing installed and nothing bundled.

This module used to call `tasklib.ProjectFile(filepath)` behind a check for
whether `tasklib` was installed, and reported "install tasklib" whenever the
import produced nothing — which was always. `tasklib` is the official Python
library for **Taskwarrior**, the command-line to-do list; it has no
`ProjectFile` and nothing to do with Microsoft Project, so the call raised
`AttributeError`, the surrounding `except` swallowed it, and the import
returned `None`. Installing the recommended package would not have changed
that. MS Project import had never worked, and nothing caught it because
nothing tested the reading of an actual file.

What comes back from an MSPDI file:

- **Hierarchy**: `OutlineLevel` is the only statement of it — tasks are a flat
  list and a parent is the nearest row above at one level less, so this walks
  a stack. An outline that skips a level attaches to the deepest row above it
  rather than dropping the task
- **Dates**: a Microsoft finish is a moment and an end date here is an
  inclusive day. A finish at midnight means the start of the day after the
  last one worked, so the day before is taken
- **Links**: held on the successor, as they are here, so nothing is reversed.
  Lag arrives in tenths of a minute whatever `LagFormat` says
- **Calendars**: the working week (`DayType` numbers Sunday 1 where Python
  starts at Monday), both exception forms — the older `WeekDay`/`TimePeriod`
  one this application writes and the `<Exceptions>` block Project itself
  writes — and the per-task calendars, which land in the registry
- **Not imported**: a task at outline level 0, which is the project summary
  row rather than work, and a row marked `IsNull`

**Binary `.mpp` is identified, not guessed at.** It is an OLE2 compound
document holding undocumented, partly compressed streams whose layout changes
with every release of Project; the one complete reader is MPXJ, a large Java
library, and the JPype bridge to it was removed from this application for
exactly the reason it could not be brought back — a JVM and a jar cannot go
inside a self-contained package. A plan is acted on, so a file that
half-parses into tasks with plausible names and wrong dates is more expensive
than one that refuses to open and says why. Choosing a `.mpp` gets the step
that fixes it — Save As, XML Format — in an information dialog rather than an
error, and it is not recorded as an error in the log either: the file is
intact and the user did nothing wrong
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
- Python 3.8 or higher. CI runs the suite on 3.11, 3.12 and 3.13; the macOS
  and Debian packages are built against 3.11

**One trap worth knowing about if you develop on an older interpreter.**
`classmethod` stacked on `property` — the old spelling of a "class property" —
was deprecated in 3.11 and **removed in 3.13**, and what it does on 3.13 is
not raise: the attribute hands back the `property` object itself. `Task`
carried one on `working_calendar`, so on 3.13 every caller that wanted a
task's length failed with `AttributeError: 'property' object has no attribute
'working_days_between'` — while drawing a row, opening a form or rendering a
page. The suite passed on 3.9 and the application could not show a task list
on 3.13. `tests/test_task_hierarchy.py` now reads the source for that stacking
on *every* version, so it fails before the code reaches a Python that has
removed it.
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

`holidays` supplies the public holidays behind Actions → Calendar Settings.... Without
it the app still runs and the picker still saves a selection, but no holiday is
applied and plans are scheduled on weekends alone.

### Optional Dependencies
```bash
# For GAN file import (included in standard library)
pip install lxml  # For better XML parsing performance

# Nothing further. MS Project import reads MSPDI with the standard library
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
covers every file attached to the release, and the exact library set is
recorded in the build's own artifacts, under the Actions run that produced
it — off the release page, which carries only the two packages, the macOS
instructions and the checksums.

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
   - **Actions -> Create** offers Phase, Task, Subtask and
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
   - Double-click a row, or choose Edit from its right-click menu. Folding
     is on the arrow beside the row, as it is in any other tree
   - Modify properties, dependencies, notes and colours
   - Save & Close, Save & New, or Delete
   - Help opens a reference on what each field means

7. **Copy, Cut and Paste**
   - From a row's right-click menu, the Edit menu, or Cmd/Ctrl+C, X and V
   - Acts on every row selected, and copies only those rows - copying a phase
     does not duplicate the work under it, though a task copied with its
     sub-tasks keeps them
   - What you paste takes the place of the row the cursor is on and pushes it
     down; the pasted rows are left selected
   - **Paste as Sub-Task** on the right-click menu puts them inside that row
     instead
   - Paste is offered only where the item belongs: a phase does not go inside
     a task, and a paste that cannot land says why in the status bar
   - One press of Undo takes the whole paste back

8. **Save Project**
   - Choose **Project -> Save Project...** or the save icon
   - Writes back to the file the plan was last saved or loaded from
   - Asks where to put it the first time, when there is no such file yet
   - **Save Project As...** always asks, and the plan follows the new file
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
    - "MS Project..." to import an MSPDI `.xml` written by Project (File -> Save As -> XML)
    - "GAN..." to import GanttProject files
    - "Mermaid..." to import Mermaid Gantt chart files (.mmd, .mermaid)
    - "XLSX..." to import an Excel project plan (requires openpyxl)
    - Importing replaces the current project and clears the undo/redo history

12. **Export Projects**
    - Choose **File -> Export** and pick the format:
    - "GAN..." to hand the plan to GanttProject
    - "MS Project..." to write Microsoft Project's MSPDI `.xml`, which Project opens with File -> Open
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
- **Double-click** a row to open its editor; click it, pause, and click again to rename it in place; the arrow beside it expands and collapses
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
- `task_type`: One of 'Phase', 'Task', 'Subtask', 'Milestone'
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

### MS Project Import
Reads MSPDI `.xml` with nothing installed:
- Tasks, summary rows and milestones, with the outline turned back into a hierarchy
- Dependencies with their type and lag
- Progress, notes and priorities
- Dates and durations, and the working calendar they were counted against
- Per-task calendars, which land in the calendar registry

A binary `.mpp` is identified and answered with the one step that fixes it,
rather than being guessed at.

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

### 3. Import That Does Not Trust the File Name
- MS Project's two formats are told apart by sniffing the file, not the extension
- MSPDI named `.mpp` still imports; a binary save named `.xml` still does not
- The unreadable case is answered with the action that fixes it, not an error

### 4. Critical Path Analysis

`Project.schedule_analysis()` runs **both passes of the critical path method**
and returns a `TaskFloat` per task: early start and finish, late start and
finish, total float, and whether it is critical.

- **Forward pass**: where each task is, *as scheduled*, rather than recomputed
  from the network. A task deliberately held back — by an earliest begin date,
  or simply placed later — is measured where it actually is. Recomputing would
  answer a different question ("how early could everything be") and would call
  a task critical that has a fortnight of air in front of it
- **Backward pass**: the latest each task could finish without moving the
  project's finish. The **link types are honoured**: a Finish-Start successor
  needs its predecessor finished, while a Start-Start one only needs it
  started, and the two allow very different amounts of float
- **Total float** is the gap between the two, and a task with none of it is
  critical. That finds **every** such task rather than one chain through them —
  two parallel strands can both drive the finish, and highlighting only one of
  them hid half the risk. This is what `get_critical_path()` now returns
- Counted in **working days**, the only unit float means anything in: the
  weekend between two tasks is not slack anybody can spend
- Negative float is reported rather than clamped. It means the links require a
  finish the plan cannot reach, which is worth seeing
- Summary tasks are left out — they bracket work rather than being it — but a
  dependency **on** a summary resolves to the work inside it, so grouping does
  not sever the network
- Cycle-safe and iterative: an edge that cannot be measured contributes
  nothing and is logged, rather than the analysis failing on a plan that has
  one
- Shown three ways. The critical tasks are highlighted in the Gantt chart;
  the **critical path icon** on the bar paints those same rows light red in
  the task list and clears them again when pressed a second time; and
  **View → Critical Path...** opens the full table with each task's float. A
  colour says *which* tasks are critical, in whichever pane is being read;
  only the table says how close the rest are to becoming so, and one day of
  float is the thing worth knowing about before it is spent

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

### 7. A popup over a modal dialog takes the grab

A Tk grab is **exclusive**: while a dialog holds one, every click goes to it
and to the widgets inside it. A popup opened on top — the colour palette, the
calendar — is a *separate window*, not a child, so it receives nothing. Its
buttons draw normally, its swatches highlight on hover, and not one of them
responds.

`views/modal.take_grab()` is the fix: the popup takes the grab for as long as
it is up and hands it back to whatever held it before, so the dialog
underneath is not left non-modal either. `<Destroy>` fires for every widget
inside a window as well as for the window itself, so the handler checks which
it was given — restoring on a child's teardown would give the grab away while
the popup was still up.

### 8. Secondary buttons are drawn, not left transparent

`fg_color='transparent'` keeps CustomTkinter's button text colour, which is
white because it is meant to sit on the filled blue. On a light window that is
white on white. `views/buttonstyle.secondary_button()` gives the quieter
button a fill and a text colour of its own, both as (light, dark) pairs so it
is legible in either appearance mode.

### 9. Fields are watched through variables, not the keyboard
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
- ✅ **Models**: Task and Project classes, serialization, the schedule
- ✅ **File I/O**: JSON save/load, datetime handling, error cases
- ✅ **GAN Import**: Real GanttProject 3.x fixtures - working-day calendar, nested sub-tasks, successor-to-predecessor edge reversal, milestones, colors, namespaced files
- ✅ **Mermaid Import/Export**: Inclusive working-day durations, dependency chains, section grouping, frontmatter, state tags, rows with no ID, and a round trip that loses nothing - levels, types, exact progress, colours, link kinds and dates all compared field by field
- ✅ **XLSX Import**: Header detection, column aliases, Excel serial dates, working-day durations, phase grouping, dependency resolution, lossless export round-trip
- ✅ **Task Hierarchy**: Sub-task creation, parent candidate ordering, cycle safety, the type a task takes when it is indented or outdented between levels, and moving several selected rows at once in the order that keeps them together
- ✅ **Logging**: Buffer capacity and filtering, file output, failure paths, importer errors reaching the log
- ✅ **Gantt Export**: PNG and PDF rendering
- ✅ **Undo/Redo**: Command stack behaviour
- ✅ **Utilities**: Project utilities, validation, edge cases
- ✅ **Completion**: Each level's roll-up rule, empty containers, clamping, the whole cascade from a part-finished sub-task to the phase above it, and that a plan of ticks and empty boxes reads exactly what counting ticks used to give
- ✅ **Task Editor**: That the boxes survive being checked, what the form complains about and when, what a refused save leaves alone, and that a keystroke changing no verdict touches no widget
- ✅ **Copy, Cut and Paste**: What goes on the clipboard, what may be pasted where, that a paste lands beside the row rather than inside it, that a paste with nothing selected is refused, that links and parentage follow what was copied, that a task cannot be pasted inside itself, that one Undo takes the whole paste back, and that the shortcuts bind this platform's modifier in both letter cases
- ✅ **Forms opened from a menu**: That neither the edit nor the create form is waited on, and that both still hand their result back through a callback
- ✅ **Mark on Track**: That work behind its dates is brought forward, that a figure already reported is never lowered - over a selection or over the whole project - and that being ahead of schedule is reported rather than corrected
- ✅ **Linking rows that hold work**: That a row is never linked to what it holds, that a selection is chained at its top level, that a collector and everything in it move together when it is linked, that the plan settles, that the dates stop moving, and that a collector stops claiming a length it does not have
- ✅ **Link and Unlink**: That the chain runs in grid order whatever order the rows were selected in, that it is Finish-to-Start with no lag, that existing links survive, that a pair closing a loop is skipped without losing the rest, what unlinking one row takes out against what unlinking several does, and that both buttons carry a drawing, a handler and this platform's key
- ✅ **Dependency Chooser**: That a label carries the number the list shows, that two identically named tasks are still told apart, that the hierarchy is walked once per redraw however many candidates there are, and that the task linked is the one the dropdown was showing
- ✅ **No test opens a dialog**: importing `tests/__init__.py` stands every blocking dialog down for the whole suite, because one that opens waits for somebody to click it and there is nobody on a build machine. A test that means to exercise a prompt patches it and asserts on the call; the one file that tests the dialog layer itself puts the real ones back in `setUpModule`. In the package rather than in a `conftest.py`, because the build runs `run_tests.py`, which is unittest - a guard that only holds under a runner nobody uses is not a guard
- ✅ **Completion control**: That every type is offered a percentage - a Sub-task included, which used to get a tick - and that a row with children shows its rolled-up figure rather than taking one of its own
- ✅ **Menus**: That no part of a menu row is dead - the padding, the chevron and the entry all run it - that CustomTkinter's own click gate is still the thing being worked around, that a submenu survives the click that opened it, that moving to another row or clicking outside still closes it, that a click inside it leaves it open, and that a menu naming no opener behaves as it always did
- ✅ **Icons**: That every icon on the toolbar row has a drawing, that every drawing paints at the sizes and inks asked for and is not blank, and that an unknown name answers None so the button can fall back to a letter
- ✅ **Reading XML From Elsewhere**: That an entity-expansion file is refused by both importers and by the reader itself, that the refusal names the entity and reads as a parse error, and that ordinary namespaced plans using the predefined entities still import unchanged
- ✅ **Chart Alignment**: That the chart draws the rows the list is showing, in its order, at its row height, and drops its label column beside a grid
- ✅ **Scroll Frame**: The scrolling container the task form is built in
- ✅ **Row Formatting**: What a default style serialises to, that a summary can be un-bolded on purpose and comes back bold when cleared, that an ordinary edit does not strip a row's formatting or its calendar, and that rows formatted alike share one tag
- ✅ **Keyboard Shortcuts**: The platform branch, both letter cases, that a named key is bound once, and that the caption names the key that is actually bound
- ✅ **Task Editor Exits**: That Enter saves and claims the key, that it leaves a multi-line box alone under either of the two widgets Tk might report as focused, that Escape discards, and that the primary and secondary buttons look different
- ✅ **Progress Tracking**: The five thresholds over a whole selection, that a phase marks the work under it, that past work goes to 100% and future work stays at 0%, that a weekend and a holiday both count correctly, that a milestone is done or not done, and that a whole press is one undo step
- ✅ **The Formatting Bar**: That it is greyed with nothing selected, what it shows for a selection that disagrees, that pressing a toggle then applies to every selected row, the presets, the one-press clear, one undo step per press, and the hotkeys in both letter cases
- ✅ **The List Keeps Its Place**: That the selection, the folded branches and the scroll position all survive a rebuild — the refresh that used to throw the selection away on every change — and that a row deleted underneath it is not reselected
- ✅ **Menu Dismissal**: That two watchers can coexist and removing one leaves the other, that the window's own bindings survive, that a menu closes on a click outside and not on one inside, that closing it stops the watch, and the exact two-menu sequence that used to leave one undismissable
- ✅ **The Settings Layout**: That every control belongs to the frame it is gridded into rather than to the window, that labels and controls are in their own columns, that the notes wrap rather than running off the edge, and that the window opens big enough for what is in it
- ✅ **Project Settings**: That the settings survive a saved file and an older one opens with the defaults, that a priority out of range is clamped rather than refusing the plan, that moving the plan keeps every duration and gap and carries the earliest-begin floors with it, and that the panel refuses a backward schedule with no deadline
- ✅ **Backward Scheduling**: That the plan ends on the deadline, that durations survive, that every link is still satisfied without a reschedule afterwards, that a task with float moves late rather than staying early, that a deadline in the past still moves the plan, and that a forward plan is settled byte for byte as it was before
- ✅ **Inline Editing**: — the tests stub where a cell is, because that is the widget's answer and a window that has never been mapped does not reliably have one; `_cell_box`'s own behaviour is checked separately.
- ✅ **Inline Editing (behaviour)**: That a double-click opens an editor over the right cell and routes the name and the dependencies to their own, that Enter stores the name and Escape does not, that an empty name reverts, that a row deleted under the editor is not renamed, that it is one undo step, and that renaming does not disturb the rest of the task
- ✅ **The Type column**: That a double-click opens a read-only dropdown of every type, that a nested row gets the same list, that choosing stores it as one undo step, that choosing the type it already is costs nothing, and that the milestone flag is written and cleared with the type in both directions
- ✅ **A row keeps its type when it moves**: That indent and outdent leave every type alone, including the cases the older rule retyped, and that an indent/outdent round trip lands where it started
- ✅ **New task from the keyboard**: That it creates beside the focused row, at the end of the plan with no cursor, that the key is the platform's and does not collide with italic, and that the I key is recognised from its keysym, its character or — on macOS — its physical keycode, so the Option compose key cannot hide it
- ✅ **The two speeds of clicking**: That the first click on an unselected row schedules no rename, that a click on one already selected does, that a quick second click calls it off and opens the editor instead, that the rename stands down if the selection moved or the row has gone, and that a pending one does not outlive the list
- ✅ **The critical path painted into the list**: That the critical rows go light red and a row with float does not, that the highlight beats a fill the row was given, that it survives the list being rebuilt, that clearing it puts the banding back, and that no window is opened
- ✅ **Where the fields sit**: That the four sections read Basic Information, Schedule, Calendar, Display; that each title has its row to itself and every section after the first opens under a rule; that the three long dropdowns are held to one width and do not stretch when the window grows; that short fields sit two to a row and one with nothing beside it keeps the left; that the Scheduling options menu is immediately above Start Date, that the calculated box is shaded from the moment the form opens, that the tabs read General / Notes / Dependency, that the notes box is on its own tab and still opens holding and saves what the task says
- ✅ **Dependency Grammar**: Every row of the specification's token table, commas and semicolons, case and spacing, a lag with no type and a type with no lag, and a round trip through every form the cell can hold
- ✅ **The Dependencies Column**: That an unreadable cell stores nothing and says so, that the four guards refuse what they should, that the plan is left untouched by a check that fails, that a whole cell is one undo step, and that the task editor shows what the grid stored
- ✅ **Exported IDs**: That the GanttProject and MSPDI files number tasks the way the list does, that the shared plan walk agrees with `display_ids` rather than counting for itself, that the spreadsheet's ID column holds numbers the plan shows, and that no identity reaches either file
- ✅ **Display IDs**: The specification's table row by row — inserting between pushes the rest down, a drag swaps two numbers, a delete leaves no gap, an indent renumbers what moved past it — and, on the other side, that identities, dependencies and parents are all untouched while it happens
- ✅ **Outline Level**: Counting from one at the top, following an indent and an outdent, an unknown row, a missing parent, and a parent cycle that must not hang the redraw
- ✅ **Visual Hierarchy**: That a row with children is bold whatever its Type says, that an empty Phase still reads as one, and that the greying of a cut row outranks the ink it was given
- ✅ **Icon Toolbar**: That every icon carries a drawing and reaches the handler connected to it, which buttons the row holds, where the dividers fall, and that nothing on it is live without a plan open
- ✅ **Hover Text**: That every button's caption reaches the canvas the pointer will actually be over - a CTkButton is a frame and the mouse is never on it - and that attaching does not bind the same handler twice
- ✅ **Working-Day Calendar**: Weekends, holidays, recurring holidays, a week with no working day in it, durations to dates and back, the EU public holidays including the movable Easter feasts, and the manual date overrides that outrank all of them
- ✅ **Scheduling**: Each link type and the edge it holds, lead and lag in working days, hard against rubber, a span stated by two links, the earliest begin date, roll-up through nested containers, and that the pass settles
- ✅ **Holiday Dialog**: What it offers, searching a couple of hundred countries and a thousand regions, when regions appear, the batch buttons, what Apply hands back and what Cancel does not
- ✅ **Country Regions**: That every country the holidays package knows is placed in exactly one region and none is left out — this is the check that fires when a new release of the package adds a country, and it names the one to add — and that a subdivision code is grouped by its country
- ✅ **Desktop Integration**: That the packaged icon is named what the desktop entry asks for, at every size the theme wants, and that the window class matches what the entry declares
- ✅ **Dialog Chrome**: That every toolbar icon reaches a handler, that a secondary button is visible and tells itself apart from the primary one, that a popup opened over a modal dialog takes the input grab and hands it back, and that opening a submenu does not dismiss the menu it belongs to
- ✅ **Critical Path**: Float per task, both parallel strands coming out critical, each link type on the backward pass, summaries left out, cycles not hanging, and what the analysis window shows
- ✅ **XLSX Export**: The plan sheet's shape, which tasks get rows, the live formulas, that a formula is never written where it would disagree with the plan, and that an ongoing task carries its percentage
- ✅ **GAN Export**: Nesting, the reversed dependency edge, milestones written both ways, durations counted over a holiday, both kinds of holiday in the calendar block, and a round trip through the importer that compares every date against the plan that went in
- ✅ **MS Project Import**: A round trip against the exporter comparing every field that decides a date, the newer `<Exceptions>` calendar block Project itself writes, a project summary row at outline level 0, an outline that skips a level, a finish stated at midnight, and that a pin on a task's own start is not read back as a floor it never had
- ✅ **MS Project Format Sniffing**: That the extension is not trusted in either direction - MSPDI named `.mpp` imports, a binary save named `.xml` does not - that a byte order mark does not hide the XML, and that the unreadable case names the step that fixes it without recording an error
- ✅ **MS Project Export**: The pinned dates and the unpinned summaries, the outline levels and WBS, lag in tenths of a minute, the weekday numbering that starts at Sunday, the per-task calendars, a worked Saturday written as an exception, and the schema's element order at the two places it looks wrong
- ✅ **PDF Pages**: That there are three, that they are all one physical size, what the work item table holds, and that the written page is the size it claims to be
- ✅ **Window Sizing**: That the window fills the usable area rather than the whole display, that a small screen gets a smaller minimum so it stays resizable, and that a scaled desktop does not get a window asked for at the scaling factor twice over
- ✅ **Application Icon**: That it draws at every packaged size, in the Python colours, identically every time, and reaches the window

The GAN fixtures deliberately mirror the format GanttProject actually writes.
An earlier version of these tests used an invented schema, which let the
importer pass its whole suite while reading zero tasks from real `.gan` files.

### Test Status
1474 tests, all passing.

## Known Limitations

1. **MPP Import**: Binary `.mpp` is not read — it is an undocumented OLE2 container with no Python reader to bundle. Save it as XML from Project and import that; MSPDI import needs nothing installed
2. **Public holidays from source**: the `holidays` package is in `requirements.txt` and is bundled into every packaged build, so a released build always has it. Only a source checkout installed without its requirements lacks it — and there the picker still saves a selection and says on its face that the choice takes effect once the package is installed, rather than silently dropping it
3. **Performance**: large plans are slow to draw, though far less so than they were. Measured on synthetic plans with hierarchy and dependencies: ~140ms at 100 tasks, ~350ms at 500, ~580ms at 1000 — down from 180ms / 575ms / 1165ms. Past ~500 tasks the row heights are still compressed to stay inside a 24-megapixel budget, so the chart is squeezed as well as slow.

   What remains is almost entirely **text**: about 95% of a render is `draw.text`, and the whole plan is rasterised even though a window shows perhaps 5% of it. Drawing only the visible band is the fix that would remove the limitation rather than shrink it, and it is not done — it inverts a deliberate trade-off (scrolling currently only moves a pre-rendered image) and needs care with the row alignment and the exports.

   What *is* done: the critical-path analysis is cached against a signature of the plan, so a redraw that changes nothing costs 9ms instead of 155ms; the float axis is a table built once rather than counted per task, taking a cold analysis from 120ms to 2.8ms; `works_any_weekday` is cached, which `is_working_day` asks before every other rule; and the chart prefers Helvetica over Arial, which are metric compatible to the pixel while Helvetica rasterises in half the time
4. **Subdivision names come from the `holidays` package**, so a region it has no name for is listed by its code
5. **XLSX Import**: Reads cached formula results. A workbook generated without a calculation pass has empty date columns; rows carrying a duration and predecessors are rescheduled from the plan's start date instead, and rows carrying neither are skipped
6. **XLSX Export**: The `Responsible (A)` column is written empty - the model has no owner field - and hierarchy below the phase level is flattened, since the layout has one grouping column
7. **No resources**: A task has no owner or assignee, so nothing is levelled and nothing is costed
8. **GAN Export of a per-task calendar**: a `.gan` file holds one calendar, so a task following a named calendar of its own is written with its duration counted against the plan's calendar instead. The dates survive; the number of days shown against that task in GanttProject does not match the one shown here. Export to MS Project where the per-task calendars matter
9. **GAN Export of a worked weekend**: a `<date>` entry only ever takes a day off, so a day the plan works that its own week says it should not cannot be expressed. Those days are counted and logged rather than written wrong
10. **MS Project Export is MSPDI, not `.mpp`**: nothing outside Project writes the binary format. The `.xml` opens with File -> Open. Task colours have no field in MSPDI and are dropped; everything that decides a date goes across
11. **XLSX Export of a worked weekend**: a Saturday or Sunday that is worked - whether by an override or by the working week itself - cannot be written as a live formula, since Excel's `WORKDAY` has a fixed Monday-to-Friday week. Tasks reaching such a day get their finish written as a date and stop recalculating; the sheet still says what the plan says. A day taken *off* stays live, because that is just another date on the holiday sheet

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
- [x] Public holidays for any country, not just the EU
- [x] Regional and state holidays, not only national ones
- [x] Full critical path analysis - both passes, so every zero-float task
- [x] Manual date overrides, outranking holidays and weekends alike
- [x] Editing the weekend rule from the application
- [x] Per-task calendars, so one strand of work can follow a different week
- [x] GAN file export, with the calendar the durations were counted against
- [x] Microsoft Project export as MSPDI, with the dates pinned so Project does not re-solve them

Still to do:

- [ ] Resource management
- [ ] Filtering and grouping
- [ ] Recursive copy of a whole branch
- [ ] Undo for paste
- [ ] Undo for a calendar change
- [ ] Multiple projects support
- [ ] Settings/preferences dialog
- [ ] Resource levelling off the back of the float analysis

---

**Project Status**: Active Development
**Version**: 1.58.2
**Last Updated**: 2026-08-26
