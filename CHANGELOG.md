# Changelog

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
