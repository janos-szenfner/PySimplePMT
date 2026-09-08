# Changelog

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
