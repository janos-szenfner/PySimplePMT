# Changelog

## 1.69.4 - 2026-09-15

- **Filters can be named, saved and written as a query.** The Filter
  window now has two tabs. **Basic** keeps the per-column rules - a
  contains-box for text, a from/to pair for numbers and dates, a tick per
  value for the fixed-set columns. **Advanced** takes a query the way
  Jira's JQL asks questions: `name ~ "art" AND progress < 50`, `type in
  (...)`, `start within 2026-09-01, 2026-09-30`, empty checks, AND/OR/NOT
  and parentheses, with dates read dashed, dotted or slashed. The entry is
  checked as it is typed - the verdict line names the error and where it
  sits, or counts the rows the query matches - a suggestion list offers
  fields and values for the cursor's spot, and recent queries are kept.
  What the Basic tab can say converts into a query, and a simple query
  converts back. **More Filters** lists the standard and saved filters
  with Apply, Highlight, New, Edit, Copy and Delete - one definition, both
  uses - and the builder is MS Project's Filter Definition grid: And/Or
  joins that start new groups, a test list that follows the field's kind,
  and a value box that adapts to it. Saved definitions live in the project
  file; a show-in-menu filter appears in the Highlight gallery and the
  Filter button's new dropdown, and picking the active one again turns it
  off.
- **Reset Task List Visibility.** A button beside Reset Task List Layout
  in Project Settings → Task Grid puts the columns back to the
  application's default - Label hidden, everything else shown - repaints
  the grid and marks the plan changed in one press.
- **Check for Updates works in the packaged build.** The frozen
  interpreter carried no CA certificates, so every HTTPS call to GitHub
  failed certificate verification and the About window could only say it
  could not check. certifi is now bundled, and both the check and the
  download open their connections against it.
- **The code is organised into packages.** gantt_app/ was a flat list of
  modules; it now separates the domain and scheduling logic (`core/`) from
  the windows and their furniture (`views/`) and the file-format and
  platform machinery (`utils/`). No behaviour changes.

## 1.69.2 - 2026-09-15

- **The View tab grew a column Filter.** A new Filter group opens a window
  with one rule per visible grid column: a contains-box for the text
  columns (which reads from the third letter, so "art" finds Draft
  artwork), a from/to pair for the number and date columns with either end
  openable, and a tick per value for the fixed-set columns - Type, Status,
  Milestone, Alert and Task Calendar. Apply shows only the rows every set
  rule passes, keeping a match's phase above it for context; the columns
  combine with AND the way MS Project's AutoFilter does. A separate Clear
  button and the window's own Clear All put every row back. The filters
  are a view, not data - nothing is written to the plan, and opening,
  closing or replacing the plan clears them.
- **Date boxes accept dots and slashes.** Typing 2026.09.01 or 2026/09/01
  into any date field now parses as the date it plainly is, alongside the
  displayed 2026-09-01 form.
- **Ribbon groups no longer clip their buttons.** The band is taller, so
  large-button captions like Critical Path Analysis and New Task fit inside
  their frames, and small buttons wrap after three to a column - Unlink no
  longer spills past the Outline group's edge.
- **Task-grid settings dropdowns open again.** The cell editor committed on
  focus loss, and opening a Hidden/Viewable list moved focus into the
  popup - firing the commit and destroying the list the instant it
  appeared. The editor now waits for focus to settle, the way the task
  list's own in-place editor does.
- **Dark-mode leftovers repainted.** The black band under the Gantt chart
  after a night-to-day switch was the chart frame's own canvas, shadowed by
  a name collision - renamed, and given an explicit colour where its paned
  parent hid it from the theme. The dark gaps between Resource Pool cards
  had the same cause in the scroll frame's content, which now resamples its
  transparent background on a theme change.
- **Checking for updates is more forgiving.** A look at the latest release
  now falls back to the releases list when GitHub answers "latest" with a
  404 - which is what it does while a release is still publishing - and the
  request gets a longer timeout.

## 1.69.1 - 2026-09-14

- **The Event Log now records everything you do.** Every ribbon, backstage,
  quick-access and split-button press is logged under the caption the
  button carries, and every gallery pick - each import and export format,
  baseline compares, recent projects - logs as `Menu: Export: PNG...`.
  Silent paths got lines of their own: file-chooser cancels on every open,
  save, import and export; critical-path report and highlight toggles with
  the row count; Gantt zoom in/out/fit/reset; the task search with its
  match count; ribbon tab switches, ribbon folding and the File backstage
  opening and closing; declined delete confirmations and cancelled task
  dialogs; link and unlink results including the already-linked and
  nothing-to-remove cases; branch folding in the task list; and the Log
  window's own Copy, Save As, level filter and close. Custom-preset saves
  and resource assignments made in the task editor are logged too.
- **The year header can no longer go blank on wide fonts.** On the
  coarsest chart header every band carries a name - a band too narrow for
  "2026" or "'26" falls back to the two-digit year rather than showing
  nothing. Which face the chart text uses is the platform's business, and
  DejaVu measures wider than Helvetica at the same size, which is how the
  strip could empty out on Linux while looking fine elsewhere.

## 1.69.0 - 2026-09-14

- **The window grew a ribbon.** The two stacked rows it opened with - a text
  menu bar over a long row of icon buttons - are now the arrangement
  LibreOffice and Microsoft Project use: a strip of tabs along the top, and
  under it a band of captioned groups, each holding the commands that belong
  together. The group caption says what the buttons are for before the
  pointer arrives. Three tabbed pages: **Task** (Clipboard, Insert, Tasks,
  Outline, Font, Progress), **View** (Views, Analysis, Appearance, Window)
  and **Project** (Properties, Baseline, Calendar, Resources). The File tab
  opens a backstage panel over the whole window - New/Open/Save/Save As/
  Close Project, the Import and Export galleries, the recent-projects list,
  Project Settings, and User Guide / About / Changelog. Save, Save As, Undo
  and Redo sit as quick-access icons on the strip; help, day/night and
  search at its right edge. Every button runs exactly what the old menu
  entry ran - it is wiring, not behaviour.
- **The task grid's columns are the plan's to arrange.** Every data column
  can be hidden from the new **Task Grid** tab in Project Settings - a
  checklist styled like the grid itself - and the column headers drag into
  whatever order suits the plan; the layout is saved with the project file.
  The **Alert** column is pinned at the front while it is on show, where MS
  Project keeps Indicators: it cannot be dragged and nothing may be dropped
  before it. While a baseline compare runs, its ten columns stand as a block
  after the reader's own columns rather than splitting the grid, and
  switching the compare off puts back exactly the layout that was there.
- **The warning flag got its own column, and slack now counts to the
  deadline** (fixes #39). The flag for a finish past its deadline rode in
  front of the Status letter, where it read as a status that never cleared;
  it now stands alone in the pinned Alert column and the Status cell is just
  the letter again. The backward pass honours the deadline too: a task's
  slack is measured against its deadline rather than the plan's end, so a
  finish past it reports the negative float it is - and counts as critical,
  as it does in Project.
- **Resource calendars now drive the schedule** (fixes #38). A resourced
  task is read against the intersection of its own calendar and its
  resources' - a member's empty weekday or booked days off are days the task
  cannot spend, so the finish stretches rather than spending effort nobody
  has. Several resources work in parallel (a day counts when any of them can
  work it), and a resource that never works at all is left out rather than
  leaving the task no working day. The Advanced tab gains **Scheduling
  ignores resource calendars**, MS Project's escape: unticked by default,
  enabled while the task follows a named calendar, saved with the plan and
  carried through undo.
- **The chart header steps down through the calendar** (fixes #48). Fitting
  a long plan into the window left the header either drawing labels it had
  no room for or falling back to one bare month band. The strip now picks
  the finest unit its cells can still label - day, week, month, quarter,
  half-year, year - with the band above naming what contains them. A band
  too narrow for "SEPTEMBER 2026" shortens through "SEP 2026" to "SEP"
  rather than colliding, and the coarsest header of all is a row of years,
  so even a decade-deep fit still says where it is.
- **The critical-path highlight paints the chart too.** The chart always
  drew its critical tasks in an orange nobody had asked for, whether the
  highlight was on or not. Bars, milestone diamonds and phase brackets now
  go the red the highlight already means - on screen and in the exports -
  and only while it is on.
- **Mermaid export asks first.** File → Share → Export → Mermaid opens an
  options sheet - text size and theme seeded from what the chart is drawn
  with, destination through the native save box - and the picks are written
  into the file's init directive so a renderer draws the chart in them. The
  Gantt tab left the Settings hub (its editors were the chart's own, not the
  project's), and rows created now take their type's colour: tasks the
  button blue, phases green, milestones orange - the names the palette
  already gives them, and what the chart's milestone marker, the Default
  theme and every importer's fallback now agree on.
- **Effort-Driven is honoured when the roster changes** (fixes #30). The
  add/remove rules now run on a changed roster as well as on edited numbers:
  with the toggle on, a removed resource's hours pass to those left and the
  duration (or Fixed Duration's units) follows; off, the duration holds and
  the work moves with the roster. The Resource Planning board's quick assign
  reconciles the same way - it commits through the undo tracker and reschedules,
  where before it ran none of it.
- **Dependency loops through summary roll-up are caught** (fixes #47). A
  child linking to anything that waits on one of its ancestors closed a loop
  the link-walk alone could not see - each reschedule pass moved the child
  past the end the summary had just rolled up until durations read in the
  thousands. The cycle check now follows roll-up edges too, and both the
  Dependencies column and the editor's Add refuse ancestor/descendant links.
  A link typed into the Dependencies column is a deliberate edit, so it
  schedules without the forward-only licence - a Start-Start or Start-Finish
  link may now pull its task earlier instead of looking unapplied.
- **A Label field** (fixes #52): a short free-text tag on every task - its
  own grid column with in-place editing, a box under the title in the task
  editor, saved with the plan, undoable, and searchable.
- **A Task Calendar column** (fixes #37) at the end of the grid names the
  calendar each task follows.
- **Link Tasks chains the whole selection** (fixes #18), not just its top
  level - a branch and the rows inside it chain in reading order, with the
  descendant guard refusing the parent/child pairs that would contradict.
  A successor that already waits for a listed predecessor keeps that link
  rather than gaining a second one.
- **Row numbers are a fixed grey "No" gutter** in the list's first column,
  like MS Project's: read-only, flush for every row whatever its type or
  depth, following every insert, delete, drag and indent - while the Task
  Name keeps its fold triangles and indentation in the tree column beside it.
- **As Late As Possible tasks are scheduled** (refs #26) instead of ignored:
  an ALAP task is pushed as late as its summary and its successors allow, so
  a row set that way ends level with the phase it sits in.
- **Start, End and Duration are all editable**, in the task editor and
  inline in the grid, with no scheduling-options mode to set first
  (refs #23, #24, #31): a new Duration moves the End (Start held), a new End
  moves the Start (Duration held), and a new Start sets a Start No Earlier
  Than so auto-scheduling cannot drag it back.
- **A collection's link-less children are driven by its predecessor**
  (refs #25): a link on a collection reaches the work inside it, so a child
  with no link of its own begins when the collection can. Task- and
  Subtask-typed rows that grew children now settle instead of alternating
  with the roll-up forever.
- **Start/Finish No Later Than conflicts are detected wherever they come
  from** (refs #28) - a task held past its date by its parent summary now
  raises the conflict dialog just as a direct link does. The dialog gains a
  **Remove Predecessors** choice: it clears the links holding the task late
  and pulls it onto the working day on or before its date, keeping the
  constraint.
- **The Earliest begin field is gone**, kept as the ordinary Start No
  Earlier Than constraint (refs #32) - one way to say the same thing, with
  old files migrated on load.
- **Status is two checkboxes**, Estimated and Inactive (refs #36): neither
  ticked means Active, both ticked reads as Inactive while the Estimated
  intent is remembered, so clearing Inactive returns the row to Estimated.
- **System UI mode moved into Project Settings** as its own tab (refs #35),
  beside the new Task Grid tab.
- **Copy puts a readable table on the desktop clipboard** (refs #16): the
  task name indented to show nesting, then Type, Start, End, Duration and
  Status - it pastes straight into a spreadsheet or a note. The plan's own
  paste never reads the desktop clipboard, so copying rows in another
  program cannot land them in the plan.
- **The About window checks for updates** (refs #41): it asks GitHub whether
  the running release is the latest and says so. **Download & Install...**
  fetches this platform's installer from the release, verifies it against
  the release's published SHA256SUMS - a failed check is never opened - and
  only then hands it to the operating system to open.
- **Delete removes the whole selection** (refs #17): right-click Delete, the
  ribbon's Delete and the Delete key all delete every selected row - reduced
  to its topmost so a parent never takes an already-deleted child twice - as
  one confirmed, undoable step.
- **File → Close Project** (refs #21) puts the current plan down and leaves
  a fresh blank one open, offering to save unsaved work first; closing the
  window now asks the same rather than quitting on a stray click.
- **Add to Timeline** (refs #34) on the right-click menu turns
  Show-in-timeline on for every selected row as one undoable step - the
  companion to a newly created task starting off the timeline (refs #33), so
  the chart shows only the rows the planner puts on it.
- Fixed the resource grids' columns sitting one place left of their headings
  (fixes #54) - the tree column's '#0' name collided with a data column of
  the same name.
- Fixed scrollbars staying light in a dark window on Tk 8.5 builds, where
  `ttk.Scrollbar` constructs a classic scrollbar that takes no style: the
  theme now configures the widget options directly at each scrollbar's
  construction, and a live theme flip re-colours the existing ones.
- README updated throughout for the ribbon, the column layout and the new
  fields; the in-app help covers the same changes.

## 1.68.2 - 2026-09-09

- Restyled the task editor's **Resource** tab so the assignment table reads
  as one grid, like the task list, instead of white header and cell tiles
  floating on the tab. The header is now a continuous heading bar over a
  bordered card of contiguous, alternating rows, in the grid's own colours
  and dark-mode aware. Only the look changed - adding, removing and editing
  assignments (Effort and Split) works exactly as before.

## 1.68.1 - 2026-09-09

- New top-level **About** menu, beside View, holding **About PySimplePMT**
  (moved out of the View menu) and a new **Changelog** item that opens the
  release history in a scrolling, searchable window read the same way as the
  Help guide.
- On macOS the built-in **Help > PySimplePMT Help** item now opens the user
  guide instead of reporting no help, and the application menu's **About
  PySimplePMT** opens the About window - both wired through the Tk Aqua menu
  commands. The changelog file is bundled into the packaged app so the
  Changelog window finds it when frozen.
- Fixed the task list's inline **Type** dropdown staying open and editable
  when clicked away from without a choice; it now closes and keeps the
  original type. The decision is made on where focus comes to rest, so the
  dropdown list opening no longer tears the editor down.
- Added **Task Type (Effort Behavior)** and **Effort-Driven** to the task
  editor's Advanced tab, following MS Project / PMP (Task_Type_FRS). Task
  Type fixes one of the three quantities in `Work = Duration × Units` (in the
  project's working hours per day): Fixed Units (default) holds each
  resource's allocation, Fixed Work holds the total hours, Fixed Duration
  holds the length. Effort-Driven decides whether adding or removing a
  resource keeps the total work (shortening the duration) or changes it;
  Fixed Work is always effort-driven and its checkbox is locked on.
- The effort maths applies only to a leaf task with at least one resource
  assigned above 0%. An unresourced task stays purely duration-driven,
  exactly as before, and milestones, summaries and manually scheduled tasks
  have both controls disabled - so existing plans are unaffected.
- Editing a resourced task's duration, work or resource units recomputes the
  others per the Task Type. When a single Save changes two of the three at
  once, the editor asks which to keep and recomputes the other rather than
  guessing; a resource pushed over 100% is allowed but flagged.
- New project setting **hours per day** (default 8) for the day-to-hours
  conversion; the effort engine lives in `gantt_app/effort.py`. All new
  fields save and load with backward-compatible defaults and are carried
  through undo/redo.
- Documented the feature in the in-app help and the README.

## 1.68.0 - 2026-09-09

- Gave the application a real logo. The hexagonal "P / IT-Space" mark now
  drives the window icon, the macOS `.app`/Dock icon, and the Linux desktop
  and pixmap icons, all built from the one image (`gantt_app/resources/
  logo_source.png`) so they cannot drift apart. A Windows `.ico` builder is
  in place for the Windows package to come.
- Added an **About PySimplePMT** window showing the logo, version, author and
  MIT licence. On macOS the built-in **About PySimplePMT** item in the
  application menu now opens it; on every platform it is also reachable from
  the in-window **View > About PySimplePMT** menu.

## 1.67.0 - 2026-09-08

- Added an **Advanced** tab to the task editor (between General and Notes, in
  `gantt_app/views/advanced_tab.py`) holding a **Deadline** and a scheduling
  **Constraint**. Both are saved with the project and drawn on the Gantt
  chart.
- Deadline: a target finish that does not move the schedule, but a forecast
  finish past it flags the task with a red downward arrow, a dashed guide
  line, a red bar outline, a variance in the hover text and a warning sign in
  the task list's Status column. "Reset to N/A" clears it.
- Constraints now **drive the schedule** (PMP/CPM): Must Start On and Must
  Finish On hard-lock the start/finish to the constraint date and override
  predecessor delays; Start/Finish No Earlier Than floor the start/finish and
  push the task later. Start/Finish No Later Than bound the late dates. A task
  left at N/A - every task until a planner sets one - stays purely
  dependency-driven, so unconstrained plans schedule exactly as before.
- Gantt markers per constraint: a blue bracket for the semi-flexible
  constraints and As Late As Possible, a red lock for Must Start/Finish On.
- Conflict resolution: saving a constraint that contradicts the network - a
  Must Finish On earlier than a predecessor allows, a No-Later date the links
  cannot meet - raises a dialog naming the impacted predecessor, with Keep
  Constraint (force it and flag the negative float) or Cancel Constraint
  (revert to N/A). Constraint and deadline changes are single undo/redo steps
  and are logged like every other task edit.
- Resource Planning view: the four panels now sit in a draggable split kept
  at their default proportions, the task list scrolls with the wheel, and the
  heatmap opens left-aligned.
- README: refreshed the project-structure file list, and documented the
  Resource Planning view and the Advanced tab.

## 1.66.10 - 2026-09-08

- Re-release of the 1.66.9 changes after that release build failed on the
  test suite. No change to the application itself; the fixes are in the
  tests.
- Fixed a headless-CI failure in the baseline Save-footer test: it now
  asserts the button and its status message by pack order rather than by
  pixel coordinates, which are 0 when the window is never mapped on screen.
- Routed the image-pixel tests through a Pillow-version-tolerant helper, so
  Pillow's `getdata()` deprecation no longer warns on the newer Pillow while
  the older one keeps working.

## 1.66.9 - 2026-09-08

- Replaced the task editor's footer view tabs (Task Planning, Resource
  Planning, Deliverables) with a segmented control matching the Settings
  window's tabs, so the bar looks like the rest of the app. Deliverables
  stays visible but is not interactive yet - selecting it snaps the choice
  back to the active tab.
- Moved Save Settings in `Settings > Baseline` into a fixed footer so it is
  always in view without scrolling past the ten slots, with the status
  message ("Settings saved." or a duplicate-name error) beside it on the
  right instead of stacked above it.

## 1.66.8 - 2026-09-08

- Centred Gantt milestone diamonds on their day cell, in line with where a
  one-day task on the same day sits, and pointed a dependency arrow into a
  milestone at the diamond itself rather than half a day short of it.
- Stopped a saved baseline appearing on the Gantt chart automatically. A
  baseline is now stored without turning comparison on and stays off the
  chart until it is picked from `Actions > Baseline > Compare Baseline`;
  choosing a slot there also moves the [Active] marker in the menu.

## 1.66.7 - 2026-09-08

- Fixed Gantt bar alignment for tasks whose start/end dates carry a time of day
  (e.g. imported schedules using 12:00). Bars are now positioned by calendar
  date, so a one-day task occupies exactly one day column and the first and last
  days are drawn full width.

## 1.66.6 - 2026-09-08

- Added Shift+Up/Down range selection to the task list. Click a task and then
  press Shift+Down or Shift+Up to extend the selection to the next or previous
  visible row, including the originally clicked task.

## 1.66.5 - 2026-09-08

- Fixed the Gantt baseline overlay so the baseline and current bars do not hide
  one another when they overlap. Baseline bars now sit in the top half of each
  row and current bars in the bottom half, so both schedule changes are visible
  (for example, a task that grew from 5 to 10 days shows both the original and
  the new bar).
- Clarified day boundaries in the Gantt chart by drawing the weekend shading and
  vertical day rules on top of the bars. A one-day task now ends at the day
  boundary and no longer looks like it extends into the next day or the weekend.
- Added regression tests for the split baseline overlay rendering.

## 1.66.4 - 2026-09-08

- Fixed the task editor so it captures the pre-edit task snapshot *before*
  mutating the live task, making Undo/Redo restore the real previous duration,
  dates and dependent-task positions.
- Added a pytest-bdd scenario that exercises the actual task-editor save path
  for duration changes and verifies Undo pulls the dependent task back.

## 1.66.3 - 2026-09-08

- Fixed undo/redo for task duration edits so dependent tasks reschedule in both directions: shortening a predecessor now pulls successors earlier, and undo/redo restores the original schedule.
- Added command-name logging to `UndoRedoManager` so Undo and Redo actions are visible in the Log window.
- Added a color picker for each baseline slot in `Settings > Baseline`; the chosen color is saved per slot and used for the Gantt baseline overlay.
- Updated the `Actions > Baseline > Compare Baseline` menu to show each slot's saved/empty status and timestamp, and to refresh automatically when slots are renamed or changed.
- Persisted baseline slot names, colors, snapshots and active slot with the project JSON file.
- Extended pytest-bdd coverage for duration undo/redo, dependent-task rescheduling, undo/redo logging, baseline color picker, dynamic compare menu labels, Gantt overlay color, and baseline persistence across save/load.

## 1.66.2 - 2026-09-08

- Moved the "Compare with Baseline" control from the toolbar into the
  `Actions > Baseline > Compare Baseline` cascading sub-menu, with a list of
  ten slots and `None (Current Only)`.
- Restored the Log button to the far right of the menu row.
- Fixed `Toolbar._refresh_baseline_views()` so that setting or clearing a
  baseline propagates the active baseline to the task list and Gantt chart
  immediately, ensuring variances are computed for the changed task itself.
- Updated baseline and toolbar menu tests for the new location and cascading
  menu.

## 1.66.1 - 2026-09-08

- Fixed settings-window BDD test to expect the new Baseline tab.
- Fixed toolbar menu tests to expect the new Actions > Baseline submenu.
- Full test suite now passes with the baseline and resource-planning changes.

## 1.66.0 - 2026-09-08

- Added the Baseline Management engine in `gantt_app/baselines.py` with ten slots, capture, clear, rename, active comparison and variance analysis.
- Added `Actions > Baseline > Set Baseline...` and `Clear Baseline...` dialogs with full-project, selected-task and roll-up scope.
- Added `Settings > Baseline` tab for renaming slots, validating uniqueness and clearing individual slots.
- Added a `Compare with Baseline` dropdown on the toolbar that activates task-list variance columns and a grey Gantt baseline overlay.
- Added baseline and variance columns to the task list: Baseline Start, Start Variance, Baseline Finish, Finish Variance, Baseline Duration, Duration Variance, Baseline Work, Work Variance, Baseline Cost and Cost Variance.
- Added a grey baseline bar behind the current bar in the Gantt chart for visual comparison.
- Added comprehensive pytest-bdd coverage for baselines, including end-to-end UI scenarios.
- Added Resource Planning view documentation to the in-app help guide.
- Updated README.md with baseline and resource planning features.

## 1.65.13 - 2026-09-07

- Made Resource Pool booking badges use existing team allocations and task-assignment hours, matching the inspector preview and heatmap.
- Showed overbooked resources as red in the Resource Pool with accurate booked hours and percentages.
- Added direct task assignment to teams and refreshed team booking hours, percentages, preview, and heatmap immediately after assignment.
- Combined direct team task assignments with applicable member workload in team heatmap rows.
- Prevented the assignee preview from counting an already-assigned task twice.
- Added pytest-bdd scenarios for overbooked resource cards and team booking updates after assignment.

## 1.65.12 - 2026-09-07

- Reduced the Task Inspector and Resource Pool panels to half their previous width while preserving the Task List width.
- Reallocated the freed space to the heatmap, producing a 2:1:1:4 panel ratio.
- Kept long resource and assignee text wrapped inside the narrower panels.
- Added regression coverage that enforces the compact panel proportions after selecting a long-named resource.

## 1.65.11 - 2026-09-07

- Kept all four Resource Planning panels equal in width when long resource names are selected.
- Wrapped long resource names and assignee preview text within their panels.
- Made the Resource Planning task list, resource canvas, cards, preview, and heatmap repaint immediately when switching between day and night modes.
- Extended the heatmap from a fixed week to the complete project timeline, with month-aware date headers and horizontal scrolling.
- Included existing team allocations in daily resource load so already-overbooked resources are shown in red.
- Added regression coverage for stable panel sizing, wrapped text, live day/night changes, multi-week timelines, and resource-and-date-specific overbooking.
- Made the theme preference test independent of the user's saved appearance mode.

## 1.65.10 - 2026-09-07

- Made the Resource Planning selection regression test portable to Linux by avoiding nested Tk event-loop processing.
- Includes the Resource Planning interaction fixes and cumulative changelog introduced for 1.65.9, whose package workflow did not complete.

## 1.65.9 - 2026-09-07

- Prevented the Resource Planning task list from freezing when a task is selected by removing the recursive tree rebuild from the selection callback.
- Added a regression scenario that exercises the real Treeview selection event and fails if task selection rebuilds the tree.
- Added a drag threshold so clicking a task or its expansion arrow no longer starts drag-and-drop or creates a drag preview.
- Limited resource assignment drops to actual drag operations.
- Corrected the drag preview position to follow coordinates relative to the task tree.
- Reduced the Resource Planning switch width so its label sits closer to the control.

## 1.65.8 - 2026-09-07

- Rebalanced the four Resource Planning panels to use equal-width columns.
- Improved the task hierarchy with expandable rows and Task, Effort, Duration, and Status columns.
- Added live task search while preserving hierarchy and expansion state.
- Added resource-pool filtering for named, generic, and team resources.
- Improved capacity badges and the scrollable workload heatmap.
- Refined the Task Planning and Resource Planning footer toggle layout.
- Updated Resource Planning BDD coverage for the revised layout and behavior.

## 1.65.7 - 2026-09-07

- Hardened the scaled-desktop startup test to verify requested window geometry reliably.

## 1.65.6 - 2026-09-07

- Released the accumulated Resource Planning changes without additional user-facing changes.

## 1.65.5 - 2026-09-07

- Added the four-panel Resource Planning Matrix with Task List, Task Inspector, Resource Pool, and Live Stacking and Heatmap panels.
- Added the footer switch between Task Planning and Resource Planning views.
- Added task search, task and resource selection, assignment, de-assignment, resource-type filtering, capacity indicators, and heatmap rendering.
- Added pytest-bdd coverage for the Resource Planning workflow.
- Fixed task-type filtering, date-based workload lookup, heatmap date range selection, and assignee preview behavior found by the new tests.
- Documented recursive task-branch copying and marked it complete.
