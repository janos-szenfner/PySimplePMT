"""
The Deliverables tab: an Excel-like grid of what the plan owes.

WHY THIS MODULE EXISTS:
======================
The footer's third view, beside Task Planning and Resource Planning. The
rows are Deliverables - parents and sub-deliverables - not tasks, so the
grid owes the schedule nothing: no dates roll up, no dependencies apply.
What it shares with the task list is the machinery: a ttk.Treeview whose
#0 column carries the name beside the outline's indent and expander, a
read-only gutter pinned to its left for the row number and the mark box,
plain-Tk drag and drop with a drawn insertion line, and editors placed over
the cells they edit.

Marks ([ ] / [x] / [~] in the gutter) are a second, stickier selection.
The Treeview's own selection answers "where is the cursor" and is what
Indent, Move and Delete act on; the marks answer "which rows should a bulk
action take", and survive the cursor moving on. Marking a parent marks the
branch, and a parent with only some of its branch marked shows [~].

DEVELOPMENT NOTES:
------------------
Every change goes through project_tracker.run_deliverable_as_command, so a
press of Undo puts back whatever the action did - see
DeliverableSnapshotCommand in utils/undoredo. The command snapshots the
whole collection, which is also why an edit here must call
project.roll_up_deliverables() inside apply: the roll-up is part of the
change and undo has to put it back too.
"""

import csv
import json
import sys
import uuid
import tkinter as tk
import tkinter.font as tkfont
from datetime import datetime
from tkinter import ttk
from typing import Callable, Dict, List, Optional, Set

import customtkinter as ctk

from gantt_app.views import theme
from gantt_app.views import dialogs as messagebox
from gantt_app.views.modal import grab_when_visible
from gantt_app.core.models import Project
from gantt_app.core.deliverable import (
    Deliverable, DELIVERABLE_STATUSES,
    status_for_progress, progress_for_status)
from gantt_app.core.priority import PRIORITY_LEVELS, PRIORITY_MENU_ORDER
from gantt_app.views.datepicker import parse_date, DATE_FORMAT
from gantt_app.views.statusline import (
    deliverable_status_line, task_status_line)
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


#: The mark box drawn in the gutter: not marked, marked, partially marked.
MARK_NONE = '[ ]'
MARK_SET = '[x]'
MARK_SOME = '[~]'

#: The glyphs the Progress cell's bar is drawn from, six cells wide.
BAR_FILL = '▓'
BAR_EMPTY = '░'
BAR_CELLS = 6

#: The filter the status dropdown offers beyond the three real statuses.
FILTER_ALL = 'All'
FILTER_OVERDUE = 'Overdue'
STATUS_FILTERS = (FILTER_ALL,) + DELIVERABLE_STATUSES + (FILTER_OVERDUE,)

#: Fill a row takes when its due date has passed and it is not done.
OVERDUE_ROW_BG = theme.GRID_CRITICAL_BG
#: Fill a Done row takes.
DONE_ROW_BG = ('#e2f3e4', '#274a2c')


class DeliverablesBoard(ctk.CTkFrame):
    """
    The deliverables grid - the view the footer's Deliverables tab shows.

    PARAMETERS:
    -----------
    parent : widget
        The content frame this shares with the other views.
    project : Project
        The active project, whose deliverables list the grid draws.
    on_status : Callable[[str], None], optional
        Where a line for the reader goes - the footer's status bar.
    on_project_changed : Callable[[], None], optional
        Fired after a change, so the rest of the window refreshes.
    project_tracker : optional
        The undo tracker; every mutation is run through it when given.
    """

    GRID_ROW_HEIGHT = 26

    #: The line marking where a dragged row would land.
    DROP_LINE_COLOR = '#1f6aa5'
    DROP_LINE_THICKNESS = 2

    #: How far the pointer must travel before a press counts as a drag.
    DRAG_THRESHOLD_PX = 5

    #: Pointer shown while dragging a row.
    DRAG_CURSOR = 'hand2'

    #: The data columns, in display order. The name is the tree column (#0),
    #: which is what draws the indentation and the expander.
    COLUMNS = ('Status', 'Assignee', 'Tasks', 'Due Date', 'Priority',
               'Tags', 'Weight', 'Progress')

    COLUMN_WIDTHS = {
        '#0': 300, 'Status': 100, 'Assignee': 110, 'Tasks': 170,
        'Due Date': 100, 'Priority': 90, 'Tags': 140, 'Weight': 70,
        'Progress': 120,
    }

    def __init__(self, parent, project: Project,
                 on_status: Optional[Callable[[str], None]] = None,
                 on_project_changed: Optional[Callable[[], None]] = None,
                 project_tracker=None) -> None:
        super().__init__(parent)
        self.project = project
        self.on_status = on_status
        self.on_project_changed = on_project_changed
        self.project_tracker = project_tracker

        #: Rows ticked for a bulk action, by deliverable id. Kept across
        #: rebuilds, which is the point of marks over the cursor selection.
        self._marked: Set[str] = set()

        # Drag state - the same fields the task list keeps.
        self._drag_id = None
        self._drag_origin = None
        self._dragging = False
        self._drop_target = None
        self._drop_above = True
        self._drop_as_parent = False
        self._drop_parent_item = None
        self._drop_parent_tags = ()
        self._drop_line_widget = None

        #: The box open over a cell, and the row it belongs to.
        self._cell_editor = None
        self._cell_editor_id = None

        #: The column the grid was last sorted by, and which way.
        self._sort_column = None
        self._sort_reverse = False

        self._build_ui()
        self._apply_grid_style()
        self.refresh()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """The header strip, then the grid."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color='transparent')
        header.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=(10, 4))

        ctk.CTkLabel(
            header, text='Deliverables',
            font=ctk.CTkFont(weight='bold', size=14),
        ).pack(side=tk.LEFT)

        self.search_entry = ctk.CTkEntry(
            header, placeholder_text='Filter by name, tag or assignee…',
            width=220)
        self.search_entry.pack(side=tk.LEFT, padx=(16, 6))
        self.search_entry.bind('<KeyRelease>',
                               lambda _e: self.refresh())

        self.status_filter = ctk.CTkOptionMenu(
            header, values=list(STATUS_FILTERS), width=110,
            command=lambda _v: self.refresh())
        self.status_filter.set(FILTER_ALL)
        self.status_filter.pack(side=tk.LEFT, padx=6)

        ctk.CTkButton(
            header, text='+ Deliverable', width=110,
            command=lambda: self.create_deliverable(None),
        ).pack(side=tk.LEFT, padx=6)

        export_button = ctk.CTkButton(
            header, text='Export ▾', width=90,
            command=lambda: self._open_export_menu(export_button))
        export_button.pack(side=tk.LEFT, padx=6)
        self._export_button = export_button

        # The grid: a fixed gutter carrying the row number and the mark box,
        # then the tree, then the scrollbars - the task list's own layout,
        # which is how the number stays put while the columns scroll.
        grid_frame = ctk.CTkFrame(self)
        grid_frame.grid(row=1, column=0, sticky=tk.NSEW, padx=10,
                        pady=(0, 10))
        grid_frame.grid_rowconfigure(0, weight=1)
        grid_frame.grid_columnconfigure(1, weight=1)

        self.id_tree = ttk.Treeview(
            grid_frame, columns=(), show='tree headings',
            selectmode='none', takefocus=0)
        self.id_tree.heading('#0', text='No', anchor=tk.W)
        self.id_tree.column('#0', width=72, minwidth=56, stretch=False,
                            anchor=tk.W)
        self.id_tree.bind('<Button-1>', self._on_gutter_click)
        for seq in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
            self.id_tree.bind(seq, self._gutter_wheel)

        self.tree = ttk.Treeview(
            grid_frame, columns=self.COLUMNS, show='tree headings')
        self.tree.heading('#0', text='Name', anchor=tk.W,
                          command=lambda: self._heading_clicked('#0'))
        for name in self.COLUMNS:
            self.tree.heading(name, text=name, anchor=tk.W,
                              command=lambda n=name: self._heading_clicked(n))
            anchor = tk.CENTER if name in ('Status', 'Priority',
                                           'Weight', 'Progress') else tk.W
            self.tree.column(name, width=self.COLUMN_WIDTHS[name],
                             minwidth=50, stretch=False, anchor=anchor)
        self.tree.column('#0', width=self.COLUMN_WIDTHS['#0'],
                         minwidth=140, stretch=False)

        vsb = ttk.Scrollbar(grid_frame, orient=tk.VERTICAL,
                            command=self.tree.yview)
        hsb = ttk.Scrollbar(grid_frame, orient=tk.HORIZONTAL,
                            command=self.tree.xview)
        theme.style_scrollbar(vsb)
        theme.style_scrollbar(hsb)
        self._vertical_scrollbar = vsb
        self.tree.configure(yscrollcommand=self._rows_scrolled,
                            xscrollcommand=hsb.set)

        self.id_tree.grid(row=0, column=0, sticky=tk.NS)
        self.tree.grid(row=0, column=1, sticky=tk.NSEW)
        vsb.grid(row=0, column=2, sticky=tk.NS)
        hsb.grid(row=1, column=1, sticky=tk.EW)

        self.tree.bind('<Double-1>', self._on_double_click)
        self.tree.bind('<ButtonPress-1>', self._on_press)
        self.tree.bind('<ButtonRelease-1>', self._on_release)
        self.tree.bind('<B1-Motion>', self._on_drag)
        self.tree.bind('<<TreeviewSelect>>',
                       lambda _e: self._push_selection_status(),
                       add='+')
        self.tree.bind('<<TreeviewOpen>>',
                       lambda _e: self.after_idle(self._refresh_gutter),
                       add='+')
        self.tree.bind('<<TreeviewClose>>',
                       lambda _e: self.after_idle(self._refresh_gutter),
                       add='+')
        self._bind_hierarchy_hotkeys()
        self._bind_context_menu()

    def _apply_grid_style(self) -> None:
        """Colour the grid for the appearance now in force."""
        theme.style_treeview('Deliverables.Treeview',
                             row_height=self.GRID_ROW_HEIGHT)
        ttk.Style().configure('Deliverables.Treeview', indent=24)
        self.tree.configure(style='Deliverables.Treeview')
        self._apply_gutter_style()
        self._apply_row_tag_colours()

    def _apply_row_tag_colours(self) -> None:
        """
        Resolve the four row appearances against the theme now in force.

        The tag names are fixed - done, overdue, and the two bands - so a
        theme change re-colours them here rather than building new names,
        the way the task list does. Rows only ever get assigned a name.
        """
        self.tree.tag_configure(
            'done_row', background=theme.now(DONE_ROW_BG),
            foreground=theme.now(theme.GRID_TEXT))
        self.tree.tag_configure(
            'overdue_row', background=theme.now(OVERDUE_ROW_BG),
            foreground=theme.now(theme.GRID_TEXT))
        self.tree.tag_configure(
            'evenrow', background=theme.now(theme.GRID_ROW_BG),
            foreground=theme.now(theme.GRID_TEXT))
        self.tree.tag_configure(
            'oddrow', background=theme.now(theme.GRID_ROW_ALT),
            foreground=theme.now(theme.GRID_TEXT))

    def _apply_gutter_style(self) -> None:
        """Grey the fixed gutter, the same shade the task list's wears."""
        theme.style_treeview('IdGutter.Treeview',
                             row_height=self.GRID_ROW_HEIGHT)
        style = ttk.Style()
        grey = theme.now(theme.FIELD_BG_DISABLED)
        muted = theme.now(theme.MUTED_TEXT)
        style.configure('IdGutter.Treeview', background=grey,
                        fieldbackground=grey, foreground=muted, indent=0)
        style.map('IdGutter.Treeview',
                  background=[('selected', grey)],
                  foreground=[('selected', muted)])
        self.id_tree.configure(style='IdGutter.Treeview')

    # ------------------------------------------------------------------
    # The view contract - what main.py asks of every pane
    # ------------------------------------------------------------------

    def on_shown(self) -> None:
        """Called when the tab brings the board to the front."""
        self.refresh()

    def apply_theme(self) -> None:
        """Re-colour the grid for the appearance just switched to."""
        try:
            if not self.tree.winfo_exists():
                return
        except tk.TclError:
            return
        self._apply_grid_style()
        self._paint_rows()

    def refresh(self) -> None:
        """
        Rebuild every row from the project's deliverables.

        Rebuilding throws away the rows the reader had acted on, so the
        selection, the folds and the scroll position are carried across -
        the task list's update_task_list rule.
        """
        state = self._capture_view_state()

        try:
            for item in self.tree.get_children():
                self.tree.delete(item)
        except tk.TclError:
            return

        # Marks pointing at rows that have gone are dropped, or a mark
        # would live on an id nothing can un-tick.
        self._marked = {i for i in self._marked
                        if self.project.get_deliverable_by_id(i) is not None}

        visible = self._visible_ids()
        tree_items: Dict[str, str] = {}

        for deliverable in self.project.deliverable_display_order():
            if visible is not None and deliverable.id not in visible:
                continue
            parent_item = (tree_items.get(deliverable.parent_id)
                           if deliverable.parent_id else '')
            if deliverable.parent_id and parent_item is None:
                # The parent was filtered out; hang the row at the root so
                # a match is never lost under a hidden branch.
                parent_item = ''
            item_id = self.tree.insert(
                parent_item, tk.END, iid=deliverable.id,
                text=deliverable.name, open=True,
                values=self._row_values(deliverable))
            tree_items[deliverable.id] = item_id

        # Assigned tasks hang under their deliverable as read-only rows,
        # after its sub-deliverables - they are the inputs the row's
        # progress is read from, drawn where a reader looks for them.
        for deliverable in self.project.deliverable_display_order():
            parent_item = tree_items.get(deliverable.id)
            if parent_item is None:
                continue
            for task in self.project.tasks_for_deliverable(deliverable.id):
                self.tree.insert(
                    parent_item, tk.END,
                    iid=self._task_row_id(deliverable.id, task.id),
                    text=task.name or '(unnamed)', open=True,
                    values=self._task_row_values(task))

        self._paint_rows()
        self._restore_view_state(state)
        self._refresh_gutter()

    # ------------------------------------------------------------------
    # What a row shows
    # ------------------------------------------------------------------

    def _row_values(self, deliverable: Deliverable) -> tuple:
        """The data cells of one row, in COLUMNS order."""
        due = (deliverable.due_date.strftime(DATE_FORMAT)
               if deliverable.due_date else '')
        has_inputs = self._has_inputs(deliverable)
        progress = self._progress_text(deliverable.progress)
        if has_inputs:
            # A derived progress is the roll-up's answer, not the row's own
            progress = 'Σ ' + progress
        task_count = len(deliverable.task_ids)
        return (
            deliverable.status,
            ', '.join(deliverable.assignees),
            f"{task_count} task(s)" if task_count else '',
            due,
            deliverable.priority,
            ', '.join(deliverable.tags),
            ('%g' % deliverable.weight),
            progress,
        )

    @staticmethod
    def _task_row_id(deliverable_id: str, task_id: str) -> str:
        """
        The tree id a task row hangs under.

        The 'task:' prefix keeps it out of every id space the board keys
        on - a task row is drawn, never edited, marked or dragged - and
        carrying the deliverable's id lets one task sit under several rows
        without the iids colliding.
        """
        return f"task:{deliverable_id}:{task_id}"

    @staticmethod
    def _is_task_row(item: str) -> bool:
        """Whether a tree id is a task row rather than a deliverable."""
        return isinstance(item, str) and item.startswith('task:')

    def _task_row_values(self, task) -> tuple:
        """
        The cells a task row shows, in COLUMNS order.

        Read-only by design: the row answers "what is this deliverable
        waiting on and how done is it" - its own type in the Tasks cell,
        its end date as the due date, its percentage in the Progress bar.
        Editing happens in the task editor, not here.
        """
        assignee = ''
        assignments = getattr(task, 'resource_assignments', None) or []
        if assignments:
            first = assignments[0]
            resource_id = getattr(first, 'resource_id', None) or \
                (first.get('resource_id') if isinstance(first, dict)
                 else None)
            repo = self.project.resource_repository
            resource = (
                repo.resources.get(resource_id)
                or repo.teams.get(resource_id)
                or repo.costs.get(resource_id)
            ) if resource_id else None
            assignee = getattr(resource, 'name', '') or str(
                resource_id or '')
        due = task.end_date.strftime(DATE_FORMAT) if task.end_date else ''
        return (
            getattr(task, 'status', '') or '',
            assignee,
            getattr(task, 'task_type', '') or '',
            due,
            getattr(task, 'priority', '') or '',
            '',
            '',
            self._progress_text(task.progress),
        )

    @staticmethod
    def _progress_text(progress: int) -> str:
        """The bar and percentage the Progress cell shows."""
        progress = max(0, min(100, int(progress or 0)))
        filled = int(round(progress / 100 * BAR_CELLS))
        bar = BAR_FILL * filled + BAR_EMPTY * (BAR_CELLS - filled)
        return f"{bar} {progress}%"

    def _is_overdue(self, deliverable: Deliverable) -> bool:
        """Whether a row's due date has passed without it being done."""
        if deliverable.due_date is None or deliverable.is_done:
            return False
        return deliverable.due_date.date() < datetime.now().date()

    def _has_inputs(self, deliverable: Deliverable) -> bool:
        """
        Whether a row's progress is derived rather than typed.

        Children or assigned tasks both count - either one is an input the
        roll-up reads, and a row with inputs takes its number from them.
        """
        if self.project.get_sub_deliverables(deliverable.id):
            return True
        return bool(deliverable.task_ids)

    def _paint_rows(self) -> None:
        """
        Give every visible row its band or its warning colour.

        The task list's precedence rule, smaller: overdue red beats the
        banding, done green beats the banding, and a row that is both -
        finished late - reads as done rather than late.
        """
        try:
            rows = self._rows_in_display_order()
        except tk.TclError:
            return

        for index, item in enumerate(rows):
            if self._is_task_row(item):
                # Task rows keep the banding so the striping reads
                # through them, but take no warning colour of their own.
                self.tree.item(item, tags=(
                    'oddrow' if index % 2 else 'evenrow',))
                continue
            deliverable = self.project.get_deliverable_by_id(item)
            if deliverable is None:
                continue
            if deliverable.is_done:
                tag = 'done_row'
            elif self._is_overdue(deliverable):
                tag = 'overdue_row'
            else:
                tag = 'oddrow' if index % 2 else 'evenrow'
            self.tree.item(item, tags=(tag,))

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    def _visible_ids(self) -> Optional[Set[str]]:
        """
        The rows the filters leave on screen, or None when nothing is set.

        A match keeps its ancestors on screen, the way the task grid's
        filters and search do: a matching sub-deliverable floating at the
        top level reads as a root row it is not.
        """
        search = (self.search_entry.get() or '').strip().lower()
        status = self.status_filter.get()

        if not search and status == FILTER_ALL:
            return None

        today = datetime.now().date()
        matches: Set[str] = set()
        for deliverable in self.project.deliverables:
            if search:
                haystack = ' '.join(
                    [deliverable.name, ' '.join(deliverable.assignees),
                     ' '.join(deliverable.tags)]).lower()
                if search not in haystack:
                    continue
            if status in DELIVERABLE_STATUSES \
                    and deliverable.status != status:
                continue
            if status == FILTER_OVERDUE and not self._is_overdue(deliverable):
                continue
            matches.add(deliverable.id)

        # Keep the ancestors of every match.
        keep = set(matches)
        for deliverable_id in list(matches):
            keep |= self.project._deliverable_ancestor_ids(deliverable_id)
        return keep

    # ------------------------------------------------------------------
    # Marks - the gutter checkboxes
    # ------------------------------------------------------------------

    def _mark_for(self, deliverable_id: str) -> str:
        """The glyph a row's box shows: set, some of its branch, or none."""
        if deliverable_id in self._marked:
            return MARK_SET
        if self._marked & self.project._deliverable_descendant_ids(
                deliverable_id):
            return MARK_SOME
        return MARK_NONE

    def _toggle_mark(self, deliverable_id: str) -> None:
        """
        Tick or un-tick a row, taking its branch with it.

        Marking a parent marks everything under it - the bulk action meant
        the whole deliverable. Unmarking clears the branch too, so a row
        never reads [x] while a child it stands for is not.
        """
        branch = {deliverable_id} | \
            self.project._deliverable_descendant_ids(deliverable_id)
        if deliverable_id in self._marked:
            self._marked -= branch
        else:
            self._marked |= branch
        self._refresh_gutter()

    def _on_gutter_click(self, event) -> str:
        """A click in the gutter toggles the row's mark."""
        item = self.id_tree.identify_row(event.y)
        if item and not self._is_task_row(item):
            self._toggle_mark(item)
            self._say(f"{len(self._marked)} row(s) marked.")
        return 'break'

    def marked_ids(self) -> List[str]:
        """The marked rows, in display order."""
        order = [d.id for d in self.project.deliverable_display_order()]
        return [i for i in order if i in self._marked]

    def _actionable_ids(self, clicked: Optional[str] = None) -> List[str]:
        """
        What a bulk action acts on: the marks when any exist, else the
        selection, else the row the menu was opened on.
        """
        marked = self.marked_ids()
        if marked:
            return marked
        selected = [i for i in self.tree.selection()
                    if self.project.get_deliverable_by_id(i) is not None]
        if selected:
            return selected
        if clicked and not self._is_task_row(clicked):
            return [clicked]
        return []

    # ------------------------------------------------------------------
    # The gutter and scroll
    # ------------------------------------------------------------------

    def _rows_in_display_order(self) -> List[str]:
        """The row ids the grid is showing, top to bottom."""
        ordered = []

        def walk(parent=''):
            for item in self.tree.get_children(parent):
                ordered.append(item)
                walk(item)

        walk()
        return ordered

    def _refresh_gutter(self) -> None:
        """Redraw the gutter so it mirrors the visible rows."""
        gutter = getattr(self, 'id_tree', None)
        if gutter is None or not gutter.winfo_exists():
            return
        try:
            gutter.delete(*gutter.get_children(''))
        except tk.TclError:
            return

        numbers = self.project.deliverable_display_ids()
        task_numbers = self.project.display_ids()
        width = self.project.ID_WIDTH
        for item in self._rows_in_display_order():
            if self._is_task_row(item):
                # A task row carries the task's own number and no box -
                # marks are a deliverable thing.
                task_id = item.rsplit(':', 1)[-1]
                label = str(task_numbers.get(task_id, '')).zfill(width)
                gutter.insert('', tk.END, iid=item, text=f"{label}")
                continue
            number = numbers.get(item)
            label = '' if number is None else str(number).zfill(width)
            gutter.insert('', tk.END, iid=item,
                          text=f"{label} {self._mark_for(item)}")

        try:
            gutter.yview_moveto(self.tree.yview()[0])
        except (tk.TclError, IndexError):
            pass

    def _rows_scrolled(self, first, last) -> None:
        """Move the scrollbar and keep the gutter in step."""
        gutter = getattr(self, 'id_tree', None)
        if gutter is not None:
            try:
                gutter.yview_moveto(first)
            except tk.TclError:
                pass
        if getattr(self, '_vertical_scrollbar', None) is not None:
            self._vertical_scrollbar.set(first, last)

    def _gutter_wheel(self, event) -> str:
        """Route a wheel roll over the gutter to the grid beside it."""
        if getattr(event, 'num', 0) == 4:
            self.tree.yview_scroll(-1, 'units')
        elif getattr(event, 'num', 0) == 5:
            self.tree.yview_scroll(1, 'units')
        else:
            self.tree.yview_scroll(-1 if event.delta > 0 else 1, 'units')
        return 'break'

    def _capture_view_state(self) -> dict:
        """Selection, folds and scroll, before a rebuild tears them down."""
        try:
            return {
                'selection': tuple(self.tree.selection()),
                'focus': self.tree.focus(),
                'closed': {item for item in self._rows_in_display_order()
                           if not self.tree.item(item, 'open')},
                'scroll': self.tree.yview()[0],
            }
        except tk.TclError:
            return {}

    def _restore_view_state(self, state: dict) -> None:
        """Put the selection, folds and scroll back after a rebuild."""
        if not state:
            return
        try:
            for item in state.get('closed', ()):
                if self.tree.exists(item):
                    self.tree.item(item, open=False)
            alive = [i for i in state.get('selection', ())
                     if self.tree.exists(i)]
            if alive:
                self.tree.selection_set(*alive)
            focused = state.get('focus')
            if focused and self.tree.exists(focused):
                self.tree.focus(focused)
            scroll = state.get('scroll')
            if scroll is not None:
                self.tree.yview_moveto(scroll)
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # Editing cells
    # ------------------------------------------------------------------

    def _on_double_click(self, event):
        """Open the editor the clicked cell takes."""
        if self.tree.identify_region(event.x, event.y) \
                not in ('cell', 'tree'):
            return None
        item = self.tree.identify_row(event.y)
        if not item:
            return None
        if self._is_task_row(item):
            return 'break'      # a task row is read-only display

        column = self._column_name(event.x)
        if column == '#0' or column == 'Tags' or column == 'Due Date' \
                or column == 'Weight' or column == 'Progress':
            self._open_cell_editor(item, column)
        elif column == 'Status':
            self._open_status_menu(item)
        elif column == 'Priority':
            self._open_priority_menu(item)
        elif column == 'Assignee':
            self._open_assignee_menu(item)
        elif column == 'Tasks':
            self._open_task_picker([item])
        return 'break'

    def _column_name(self, x: int) -> Optional[str]:
        """Which column an x position falls in, by name."""
        try:
            reference = self.tree.identify_column(x)
        except tk.TclError:
            return None
        if reference == '#0':
            return '#0'
        try:
            index = int(reference.lstrip('#')) - 1
        except ValueError:
            return None
        shown = self.tree.cget('columns')
        return shown[index] if 0 <= index < len(shown) else None

    def _cell_box(self, item: str, column: str):
        """Where one cell is on screen, or None if it cannot be placed."""
        for attempt in (0, 1):
            try:
                box = self.tree.bbox(item, column)
                if box:
                    return box
                if attempt == 0:
                    self.tree.see(item)
                    self.tree.update_idletasks()
            except tk.TclError:
                return None
        return None

    def _open_cell_editor(self, item: str, column: str) -> None:
        """
        Put a typing box over one cell of one row.

        A plain tkinter Entry like the task list's: a CTkEntry is a frame
        holding an entry and draws corners a grid row's height cannot fit.
        """
        deliverable = self.project.get_deliverable_by_id(item)
        if deliverable is None:
            return

        if column == 'Progress' and self._has_inputs(deliverable):
            self._say("This deliverable's progress comes from its "
                      "children and assigned tasks.")
            return

        current = {
            '#0': deliverable.name,
            'Assignee': ', '.join(deliverable.assignees),
            'Due Date': (deliverable.due_date.strftime(DATE_FORMAT)
                         if deliverable.due_date else ''),
            'Tags': ', '.join(deliverable.tags),
            'Weight': '%g' % deliverable.weight,
            'Progress': str(deliverable.progress),
        }.get(column, '')

        box = self._cell_box(item, column)
        if box is None:
            return
        self._close_cell_editor()

        x, y, width, height = box
        editor = tk.Entry(self.tree, borderwidth=1, relief='solid',
                          highlightthickness=0)
        editor.insert(0, current)
        editor.select_range(0, tk.END)
        editor.place(x=x, y=y, width=width, height=height)
        editor.focus_set()

        self._cell_editor = editor
        self._cell_editor_id = item

        editor.bind('<Return>',
                    lambda _e: self._commit_cell_editor(column))
        editor.bind('<KP_Enter>',
                    lambda _e: self._commit_cell_editor(column))
        editor.bind('<Escape>', lambda _e: self._close_cell_editor())
        editor.bind('<FocusOut>',
                    lambda _e: self._commit_cell_editor(column))

    def _close_cell_editor(self) -> None:
        """Take the open editor off the grid, if there is one."""
        editor = getattr(self, '_cell_editor', None)
        self._cell_editor = None
        self._cell_editor_id = None
        if editor is not None:
            try:
                editor.destroy()
            except tk.TclError:
                pass

    def _commit_cell_editor(self, column: str) -> None:
        """
        Store what was typed over a cell.

        The editor is read and closed before anything is stored: storing
        redraws the grid, which destroys the row the entry is sitting on.
        """
        editor = self._cell_editor
        deliverable_id = self._cell_editor_id
        if editor is None or deliverable_id is None:
            return
        try:
            text = editor.get()
        except tk.TclError:
            self._close_cell_editor()
            return
        self._close_cell_editor()

        deliverable = self.project.get_deliverable_by_id(deliverable_id)
        if deliverable is None:
            return

        text = text.strip()
        if column == '#0':
            self._write(deliverable_id, {'name': text}, 'Rename Deliverable')
        elif column == 'Assignee':
            names = [part.strip() for part in text.split(',')
                     if part.strip()]
            self._write(deliverable_id, {'assignees': names},
                        'Set Assignees')
        elif column == 'Due Date':
            if not text:
                due = None
            else:
                due = parse_date(text)
                if due is None:
                    self._say("That is not a date - use YYYY-MM-DD.")
                    return
            self._write(deliverable_id, {'due_date': due},
                        'Set Due Date')
        elif column == 'Tags':
            tags = [part.strip() for part in text.split(',')
                    if part.strip()]
            self._write(deliverable_id, {'tags': tags}, 'Set Tags')
        elif column == 'Weight':
            try:
                weight = float(text)
            except (TypeError, ValueError):
                self._say("Weight is a number - 1 by default.")
                return
            self._write(deliverable_id,
                        {'weight': max(0.0, weight)}, 'Set Weight')
        elif column == 'Progress':
            try:
                progress = int(float(text))
            except (TypeError, ValueError):
                self._say("Progress is a percentage - 0 to 100.")
                return
            self._set_progress(deliverable_id,
                               max(0, min(100, progress)))

    # ------------------------------------------------------------------
    # Choice cells - status, priority, assignee pick lists
    # ------------------------------------------------------------------

    def _open_status_menu(self, item: str) -> None:
        """Offer the three statuses at the cell that was clicked."""
        deliverable = self.project.get_deliverable_by_id(item)
        if deliverable is not None and self._has_inputs(deliverable):
            self._say("Status follows the row's children and tasks.")
            return
        self._open_choice_menu(
            item, 'Status', DELIVERABLE_STATUSES,
            lambda value: self._set_status(item, value))

    def _open_priority_menu(self, item: str) -> None:
        """Offer the priority levels at the cell that was clicked."""
        self._open_choice_menu(
            item, 'Priority', PRIORITY_MENU_ORDER,
            lambda value: self._write(item, {'priority': value},
                                      'Set Priority'))

    def _open_assignee_menu(self, item: str) -> None:
        """
        Pick the people and teams the row belongs to.

        A checklist rather than the pick-one menu the other choice cells
        get: a row can belong to several people and to whole teams, so the
        gesture is tick/untick, not choose one. Free-text names already on
        the row that match nothing in the pool are listed too, so they can
        be unticked rather than silently kept.
        """
        deliverable = self.project.get_deliverable_by_id(item)
        if deliverable is None:
            return

        repository = self.project.resource_repository
        people = sorted(
            resource.name for resource in repository.resources.values()
            if getattr(resource, 'name', ''))
        teams = sorted(
            team.name for team in repository.teams.values()
            if getattr(team, 'name', ''))
        others = [name for name in deliverable.assignees
                  if name not in people and name not in teams]

        if not people and not teams and not others:
            self._open_cell_editor(item, 'Assignee')
            return

        window = ctk.CTkToplevel(self.winfo_toplevel())
        window.title('Assign to '
                     f"{deliverable.name or 'deliverable'}")
        window.geometry('360x340')
        window.transient(self.winfo_toplevel())

        checked = set(deliverable.assignees)
        variables: Dict[str, tk.BooleanVar] = {}

        scroller = ctk.CTkScrollableFrame(window)
        scroller.pack(fill=tk.BOTH, expand=True, padx=12, pady=(12, 6))

        def section(title: str, names) -> None:
            if not names:
                return
            ctk.CTkLabel(
                scroller, text=title.upper(),
                font=('Arial', 11, 'bold'), anchor=tk.W,
            ).pack(fill=tk.X, pady=(8, 2))
            for name in names:
                var = variables.setdefault(
                    name, tk.BooleanVar(value=name in checked))
                ctk.CTkCheckBox(scroller, text=name, variable=var).pack(
                    fill=tk.X, pady=1)

        section('People', people)
        section('Teams', teams)
        section('Other', others)

        buttons = ctk.CTkFrame(window, fg_color='transparent')
        buttons.pack(fill=tk.X, padx=12, pady=(0, 12))

        def apply() -> None:
            chosen = [name for name, var in variables.items()
                      if var.get()]
            window.destroy()
            self._write(item, {'assignees': chosen}, 'Set Assignees')

        ctk.CTkButton(buttons, text='Assign', width=90,
                      command=apply).pack(side=tk.RIGHT, padx=(6, 0))
        ctk.CTkButton(buttons, text='Cancel', width=90,
                      command=window.destroy).pack(side=tk.RIGHT)

        grab_when_visible(window)

    def _open_choice_menu(self, item: str, column: str, choices,
                          on_pick) -> None:
        """
        Post a small menu of fixed answers over the cell.

        A tk.Menu rather than a CTkOptionMenu: the option menu is a
        full-height button that cannot sit inside a grid row, while the
        posted menu is the desktop's own and asks no room of the cell.
        """
        box = self._cell_box(item, column)
        if box is None:
            return
        x, y, width, height = box
        menu = tk.Menu(self.tree, tearoff=0)
        for choice in choices:
            menu.add_command(label=choice,
                             command=lambda c=choice: on_pick(c))
        try:
            menu.tk_popup(self.tree.winfo_rootx() + x,
                          self.tree.winfo_rooty() + y + height)
        finally:
            menu.grab_release()

    # ------------------------------------------------------------------
    # Writes - everything that changes the plan goes through here
    # ------------------------------------------------------------------

    def _write(self, deliverable_id: str, changes: dict,
               label: str) -> None:
        """
        Set fields on one deliverable, as one undoable step, and redraw.

        The roll-up runs inside the command so a leaf's new percentage and
        the parent percentage it produces are undone together.
        """
        def apply() -> bool:
            deliverable = self.project.get_deliverable_by_id(deliverable_id)
            if deliverable is None:
                return False
            changed = False
            for name, value in changes.items():
                if getattr(deliverable, name) != value:
                    setattr(deliverable, name, value)
                    changed = True
            if not changed:
                return False
            self.project.roll_up_deliverables()
            return True

        if self.project_tracker:
            self.project_tracker.run_deliverable_as_command(apply, label)
        else:
            apply()

        self.refresh()
        if self.on_project_changed:
            self.on_project_changed()

    def _set_progress(self, deliverable_id: str, progress: int) -> None:
        """Set a leaf's percentage, with the status it implies."""
        def apply() -> bool:
            deliverable = self.project.get_deliverable_by_id(deliverable_id)
            if deliverable is None or deliverable.progress == progress:
                return False
            deliverable.progress = progress
            deliverable.status = status_for_progress(progress)
            self.project.roll_up_deliverables()
            return True

        if self.project_tracker:
            self.project_tracker.run_deliverable_as_command(
                apply, 'Set Progress')
        else:
            apply()
        self.refresh()
        if self.on_project_changed:
            self.on_project_changed()

    def _set_status(self, deliverable_id: str, status: str) -> None:
        """Set a leaf's status, writing the matching percentage."""
        def apply() -> bool:
            deliverable = self.project.get_deliverable_by_id(deliverable_id)
            if deliverable is None:
                return False
            if self._has_inputs(deliverable):
                # A row with children or tasks reads its status back from
                # the roll-up - it cannot be set directly.
                return False
            progress = progress_for_status(status, deliverable.progress)
            if (deliverable.status == status
                    and deliverable.progress == progress):
                return False
            deliverable.status = status
            deliverable.progress = progress
            self.project.roll_up_deliverables()
            return True

        if self.project_tracker:
            self.project_tracker.run_deliverable_as_command(
                apply, 'Set Status')
        else:
            apply()
        self.refresh()
        if self.on_project_changed:
            self.on_project_changed()

    # ------------------------------------------------------------------
    # Creating, duplicating, deleting
    # ------------------------------------------------------------------

    def create_deliverable(self, parent_id: Optional[str],
                           anchor_id: Optional[str] = None) -> None:
        """
        Add a deliverable - under the given parent, or at the top level.

        anchor_id is a sibling the new row should follow; without one the
        row goes at the end of its group.
        """
        new_id = self.project.next_deliverable_id()

        def apply() -> bool:
            deliverable = Deliverable.create(
                name='New Deliverable', parent_id=parent_id,
                deliverable_id=new_id)
            self.project.add_deliverable(deliverable)
            if anchor_id:
                self.project.move_deliverable_after(new_id, anchor_id)
            return True

        if self.project_tracker:
            self.project_tracker.run_deliverable_as_command(
                apply, 'New Deliverable')
        else:
            apply()

        self.refresh()
        try:
            self.tree.selection_set(new_id)
            self.tree.see(new_id)
            self.tree.focus(new_id)
        except tk.TclError:
            pass
        if self.on_project_changed:
            self.on_project_changed()
        self._open_cell_editor(new_id, '#0')

    def duplicate_deliverables(self, deliverable_ids) -> None:
        """
        Copy each chosen branch and drop the copies after the originals.

        New ids throughout: a copy that kept the original's identity would
        be two rows one of which the other cannot be told from.
        """
        ids = self.project.topmost_deliverables_of(
            self._as_ids(deliverable_ids))
        if not ids:
            return

        def apply() -> bool:
            for source_id in ids:
                source = self.project.get_deliverable_by_id(source_id)
                if source is None:
                    continue
                branch = [source_id] + sorted(
                    self.project._deliverable_descendant_ids(source_id))
                # New ids throughout, parent links remapped inside the
                # branch: a copy that kept the original's identity would
                # be two rows indistinguishable from each other.
                new_ids = {old: str(uuid.uuid4()) for old in branch}
                for old_id in branch:
                    original = self.project.get_deliverable_by_id(old_id)
                    copy_of = Deliverable.from_dict(original.to_dict())
                    copy_of.id = new_ids[old_id]
                    copy_of.parent_id = new_ids.get(
                        original.parent_id, original.parent_id)
                    if old_id == source_id:
                        copy_of.name = (original.name + ' (copy)').strip()
                    self.project.add_deliverable(copy_of)
                # The copies of children already carry their new parent,
                # so only the branch's root needs placing - right after
                # the subtree it was copied from.
                self.project.move_deliverable_after(
                    new_ids[source_id], source_id)
            self.project.roll_up_deliverables()
            return True

        if self.project_tracker:
            self.project_tracker.run_deliverable_as_command(
                apply, 'Duplicate Deliverables')
        else:
            apply()
        self.refresh()
        if self.on_project_changed:
            self.on_project_changed()

    def delete_deliverables(self, deliverable_ids) -> None:
        """Delete the chosen rows, branches included, after confirming."""
        ids = self.project.topmost_deliverables_of(
            self._as_ids(deliverable_ids))
        if not ids:
            return

        total = sum(1 + len(self.project._deliverable_descendant_ids(i))
                    for i in ids)
        if len(ids) == 1 and total == 1:
            first = self.project.get_deliverable_by_id(ids[0])
            prompt = f"Delete '{first.name}'?\n\nThis can be undone."
        elif len(ids) == 1:
            first = self.project.get_deliverable_by_id(ids[0])
            prompt = (f"Delete '{first.name}' and the {total - 1} "
                      f"item(s) under it?\n\nThis can be undone.")
        else:
            prompt = (f"Delete {len(ids)} selected deliverable(s)? "
                      f"{total} row(s) in all, sub-deliverables included."
                      f"\n\nThis can be undone.")

        if not messagebox.askyesno('Delete Deliverable', prompt,
                                   icon=messagebox.WARNING):
            return

        def apply() -> bool:
            removed = False
            for deliverable_id in ids:
                if self.project.remove_deliverable(deliverable_id):
                    removed = True
            if removed:
                self.project.roll_up_deliverables()
            return removed

        if self.project_tracker:
            self.project_tracker.run_deliverable_as_command(
                apply, 'Delete Deliverables')
        else:
            apply()

        self._marked -= set(ids)
        self.refresh()
        if self.on_project_changed:
            self.on_project_changed()

    # ------------------------------------------------------------------
    # Hierarchy gestures - indent, outdent, drag and drop
    # ------------------------------------------------------------------

    def _bind_hierarchy_hotkeys(self) -> None:
        """Bind the indent and outdent shortcuts for this platform."""
        bindings = {
            '<Tab>': self._hotkey_indent,
            '<Shift-Tab>': self._hotkey_outdent,
            '<ISO_Left_Tab>': self._hotkey_outdent,
        }
        if sys.platform == 'darwin':
            bindings.update({
                '<Command-bracketright>': self._hotkey_indent,
                '<Command-bracketleft>': self._hotkey_outdent,
            })
        else:
            bindings.update({
                '<Control-bracketright>': self._hotkey_indent,
                '<Control-bracketleft>': self._hotkey_outdent,
            })
        for sequence, callback in bindings.items():
            try:
                self.tree.bind(sequence, callback)
            except tk.TclError:
                logger.debug("Hierarchy shortcut %s unsupported", sequence)

    def _hotkey_indent(self, _event=None):
        selected = [i for i in self.tree.selection()
                    if not self._is_task_row(i)]
        if selected:
            self.indent_deliverables(selected)
        return 'break'

    def _hotkey_outdent(self, _event=None):
        selected = [i for i in self.tree.selection()
                    if not self._is_task_row(i)]
        if selected:
            self.outdent_deliverables(selected)
        return 'break'

    def indent_deliverables(self, deliverable_ids) -> None:
        """Make the chosen rows sub-deliverables of the row above them."""
        chosen = self._as_ids(deliverable_ids)
        label = ('Indent Deliverables' if len(chosen) > 1
                 else 'Indent Deliverable')
        self._apply_change(
            lambda: self.project.indent_deliverables(chosen), label)

    def outdent_deliverables(self, deliverable_ids) -> None:
        """Move the chosen rows out to sit beside their parent."""
        chosen = self._as_ids(deliverable_ids)
        label = ('Outdent Deliverables' if len(chosen) > 1
                 else 'Outdent Deliverable')
        self._apply_change(
            lambda: self.project.outdent_deliverables(chosen), label)

    def move_deliverables(self, deliverable_ids, where: str) -> None:
        """Move the chosen branches within their siblings."""
        chosen = self._as_ids(deliverable_ids)
        self._apply_change(
            lambda: self.project.move_deliverables(chosen, where),
            'Move Deliverables')

    def reparent_deliverable(self, deliverable_id: str,
                             parent_id: str) -> None:
        """Move a branch under the parent a drag dropped it onto."""
        self._apply_change(
            lambda: self.project.reparent_deliverable(
                deliverable_id, parent_id),
            'Re-parent Deliverable')

    def move_deliverable_to_line(self, deliverable_id: str,
                                 target_id: str, above: bool) -> None:
        """Move a branch to the exact line a drag dropped it on."""
        self._apply_change(
            lambda: self.project.move_deliverable_to_line(
                deliverable_id, target_id, above),
            'Move Deliverable')

    def _apply_change(self, action, label: str) -> None:
        """Run a structure change as one undoable step, then redraw."""
        if self.project_tracker:
            changed = self.project_tracker.run_deliverable_as_command(
                action, label)
        else:
            changed = action()
        if changed:
            self.refresh()
            if self.on_project_changed:
                self.on_project_changed()

    # -- drag and drop, the task list's plain-Tk shape ------------------

    def _on_press(self, event) -> None:
        """Begin a possible drag; a press on a heading or space is not one."""
        if self.tree.identify_region(event.x, event.y) == 'heading':
            self._close_cell_editor()
            return
        item = self.tree.identify_row(event.y)
        if not item or self._is_task_row(item):
            return
        self._drag_id = item
        self._drag_origin = (event.x, event.y)
        self._dragging = False

    def _on_drag(self, event) -> None:
        """Track a drag in progress and mark where the drop would land."""
        if self._drag_id is None or self._drag_origin is None:
            return
        if not self._dragging:
            if (abs(event.y - self._drag_origin[1])
                    < self.DRAG_THRESHOLD_PX):
                return
            self._dragging = True
            try:
                self.tree.configure(cursor=self.DRAG_CURSOR)
            except tk.TclError:
                pass
        self._mark_drop_target(self.tree.identify_row(event.y), event.y)

    def _on_release(self, _event) -> None:
        """Finish a drag by moving the row to where the line stood."""
        if self._drag_id is None:
            return
        if not self._dragging:
            self._end_drag()
            return

        source_id = self._drag_id
        target_id = self._drop_target
        drop_as_parent = self._drop_as_parent
        drop_above = self._drop_above
        self._end_drag()

        if target_id and drop_as_parent:
            self.reparent_deliverable(source_id, target_id)
        elif target_id:
            self.move_deliverable_to_line(source_id, target_id, drop_above)

    def _mark_drop_target(self, item, pointer_y=None) -> None:
        """Show where the dragged row would land - a line, or a parent."""
        self._clear_parent_drop_target()
        self._drop_as_parent = False

        if item and pointer_y is not None \
                and self._is_valid_parent_drop(item):
            box = self.tree.bbox(item)
            if box:
                _x, y, _w, height = box
                self._drop_as_parent = (
                    y + height / 3 <= pointer_y <= y + 2 * height / 3)

        valid = (self._is_valid_parent_drop(item) if self._drop_as_parent
                 else self._is_valid_drop(item))
        if item and not valid:
            item = None

        self._drop_target = item or None
        if self._drop_target is None:
            self._hide_drop_line()
            return

        if self._drop_as_parent:
            self._hide_drop_line()
            self._show_parent_drop_target(self._drop_target)
            self._say('Drop target: parent')
        else:
            self._show_drop_line(self._drop_target, pointer_y)

    def _is_valid_parent_drop(self, item) -> bool:
        """Whether the dragged branch may be re-parented under this row."""
        if not item or item == self._drag_id:
            return False
        return self.project.can_reparent_deliverable(self._drag_id, item)

    def _is_valid_drop(self, item) -> bool:
        """Whether the dragged row may be dropped beside this one."""
        if not item or item == self._drag_id:
            return False
        source = self.project.get_deliverable_by_id(self._drag_id)
        target = self.project.get_deliverable_by_id(item)
        if source is None or target is None:
            return False
        return not self.project.deliverable_is_descendant(
            item, self._drag_id)

    def _drop_line(self):
        """The line widget, created on first use."""
        if self._drop_line_widget is None:
            self._drop_line_widget = tk.Frame(
                self.tree, height=self.DROP_LINE_THICKNESS,
                background=self.DROP_LINE_COLOR,
                borderwidth=0, highlightthickness=0)
        return self._drop_line_widget

    def _show_drop_line(self, item, pointer_y=None) -> None:
        """Put the indicator on the edge the drop would insert against."""
        try:
            box = self.tree.bbox(item)
        except tk.TclError:
            box = None
        if not box:
            self._hide_drop_line()
            return
        x, y, width, height = box
        above = pointer_y is None or pointer_y < y + height / 2
        edge = y if above else y + height
        self._drop_above = above
        line = self._drop_line()
        line.place(x=x, y=max(0, edge - self.DROP_LINE_THICKNESS // 2),
                   width=width, height=self.DROP_LINE_THICKNESS)
        line.lift()

    def _hide_drop_line(self) -> None:
        if self._drop_line_widget is not None:
            self._drop_line_widget.place_forget()

    def _show_parent_drop_target(self, item) -> None:
        """Highlight a row as the parent that will receive the branch."""
        try:
            tags = tuple(self.tree.item(item, 'tags'))
            self._drop_parent_item = item
            self._drop_parent_tags = tags
            self.tree.tag_configure('drop_parent',
                                    background=self.DROP_LINE_COLOR)
            self.tree.item(item, tags=tags + ('drop_parent',))
        except tk.TclError:
            self._drop_parent_item = None
            self._drop_parent_tags = ()

    def _clear_parent_drop_target(self) -> None:
        """Restore the normal appearance of a parent drop target."""
        if self._drop_parent_item is not None:
            try:
                self.tree.item(self._drop_parent_item,
                               tags=self._drop_parent_tags)
            except tk.TclError:
                pass
        self._drop_parent_item = None
        self._drop_parent_tags = ()

    def _end_drag(self) -> None:
        """Clear every trace of a drag, whether it completed or not."""
        self._hide_drop_line()
        self._clear_parent_drop_target()
        self._drop_target = None
        self._drop_above = True
        self._drop_as_parent = False
        self._drag_id = None
        self._drag_origin = None
        self._dragging = False
        try:
            self.tree.configure(cursor='')
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # Sorting
    # ------------------------------------------------------------------

    def _heading_clicked(self, column: str) -> None:
        """
        Sort the grid by the heading that was clicked.

        A second click on the same heading reverses it. Sorting is a real
        reorder of the flat list - each group of siblings is sorted in
        place - so it is undoable like any other move.
        """
        if self._sort_column == column:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column = column
            self._sort_reverse = False

        key = self._sort_key(column)
        reverse = self._sort_reverse

        def apply() -> bool:
            return self.project.sort_deliverables(key, reverse=reverse)

        if self.project_tracker:
            self.project_tracker.run_deliverable_as_command(
                apply, 'Sort Deliverables')
        else:
            apply()
        self.refresh()

    def _sort_key(self, column: str):
        """The key function one column sorts siblings by."""
        if column == '#0':
            return lambda d: (d.name or '').lower()
        if column == 'Status':
            order = {name: i for i, name in enumerate(DELIVERABLE_STATUSES)}
            return lambda d: order.get(d.status, 0)
        if column == 'Assignee':
            return lambda d: ', '.join(d.assignees).lower()
        if column == 'Due Date':
            # Rows without a date sort after dated ones either way round.
            return lambda d: (d.due_date is None,
                              d.due_date or datetime.max)
        if column == 'Priority':
            order = {name: i for i, name in enumerate(PRIORITY_LEVELS)}
            return lambda d: order.get(d.priority, 0)
        if column == 'Tags':
            return lambda d: ', '.join(d.tags).lower()
        if column == 'Tasks':
            return lambda d: len(d.task_ids)
        if column == 'Weight':
            return lambda d: d.weight
        if column == 'Progress':
            return lambda d: d.progress
        return lambda d: (d.name or '').lower()

    # ------------------------------------------------------------------
    # The context menu
    # ------------------------------------------------------------------

    def _bind_context_menu(self) -> None:
        """Bind the platform's context-menu gesture to the grid."""
        try:
            windowing = self.tree.tk.call('tk', 'windowingsystem')
        except tk.TclError:
            windowing = 'x11'
        if windowing == 'aqua':
            self.tree.bind('<Button-2>', self._on_context_click)
            self.tree.bind('<Control-Button-1>', self._on_context_click)
        else:
            self.tree.bind('<Button-3>', self._on_context_click)

    def _on_context_click(self, event) -> str:
        """Open the menu on the row under the pointer."""
        item = self.tree.identify_row(event.y)
        if item and item not in self.tree.selection():
            self.tree.selection_set(item)
        self._open_context_menu(item, event.x_root, event.y_root)
        return 'break'

    def _open_context_menu(self, item, x_root, y_root) -> None:
        """Build and post the menu for the row it was opened on."""
        if item and self._is_task_row(item):
            self._open_task_row_menu(item, x_root, y_root)
            return
        menu = tk.Menu(self.tree, tearoff=0)
        chosen = self._actionable_ids(item)
        deliverable = (self.project.get_deliverable_by_id(item)
                       if item else None)

        menu.add_command(
            label='New Deliverable',
            command=lambda: self.create_deliverable(None))
        menu.add_command(
            label='New Sub-deliverable',
            state=(tk.NORMAL if deliverable is not None else tk.DISABLED),
            command=lambda: self.create_deliverable(item))
        menu.add_command(
            label='Details…',
            state=(tk.NORMAL if deliverable is not None else tk.DISABLED),
            command=lambda: self._open_details(item))
        menu.add_separator()

        menu.add_command(
            label='Indent',
            state=(tk.NORMAL if chosen else tk.DISABLED),
            command=lambda: self.indent_deliverables(chosen))
        menu.add_command(
            label='Outdent',
            state=(tk.NORMAL if chosen else tk.DISABLED),
            command=lambda: self.outdent_deliverables(chosen))
        menu.add_separator()

        move_menu = tk.Menu(menu, tearoff=0)
        for label, where in (('Move to Top', 'top'), ('Move Up', 'up'),
                             ('Move Down', 'down'),
                             ('Move to Bottom', 'bottom')):
            move_menu.add_command(
                label=label,
                state=(tk.NORMAL if chosen else tk.DISABLED),
                command=lambda w=where: self.move_deliverables(chosen, w))
        menu.add_cascade(label='Move', menu=move_menu,
                         state=(tk.NORMAL if chosen else tk.DISABLED))

        status_menu = tk.Menu(menu, tearoff=0)
        for status in DELIVERABLE_STATUSES:
            status_menu.add_command(
                label=status,
                command=lambda s=status: self._bulk_set_status(chosen, s))
        menu.add_cascade(label='Set Status', menu=status_menu,
                         state=(tk.NORMAL if chosen else tk.DISABLED))

        priority_menu = tk.Menu(menu, tearoff=0)
        for priority in PRIORITY_MENU_ORDER:
            priority_menu.add_command(
                label=priority,
                command=lambda p=priority: self._bulk_write(
                    chosen, 'priority', p, 'Set Priority'))
        menu.add_cascade(label='Set Priority', menu=priority_menu,
                         state=(tk.NORMAL if chosen else tk.DISABLED))

        tasks_menu = tk.Menu(menu, tearoff=0)
        tasks_menu.add_command(
            label='Assign Tasks…',
            state=(tk.NORMAL if chosen else tk.DISABLED),
            command=lambda: self._open_task_picker(chosen))
        if deliverable is not None and deliverable.task_ids:
            # The clicked row's assignments, ticked - picking one removes it.
            tasks_menu.add_separator()
            for task in self.project.tasks_for_deliverable(deliverable.id):
                tasks_menu.add_command(
                    label=f"☑ {task.id} {task.name or ''}".rstrip(),
                    command=lambda t=task: self._unassign_task(
                        deliverable.id, t.id))
        menu.add_cascade(label='Tasks', menu=tasks_menu,
                         state=(tk.NORMAL if chosen else tk.DISABLED))

        menu.add_separator()
        if deliverable is not None:
            marked = item in self._marked
            menu.add_command(
                label='Unmark' if marked else 'Mark',
                command=lambda: self._toggle_mark(item))
        menu.add_command(
            label='Duplicate',
            state=(tk.NORMAL if chosen else tk.DISABLED),
            command=lambda: self.duplicate_deliverables(chosen))
        menu.add_command(
            label='Delete',
            state=(tk.NORMAL if chosen else tk.DISABLED),
            command=lambda: self.delete_deliverables(chosen))
        menu.add_separator()

        export_menu = tk.Menu(menu, tearoff=0)
        for fmt in ('csv', 'json'):
            export_menu.add_command(
                label=f'Export as {fmt.upper()}',
                command=lambda f=fmt: self.export_rows(chosen, f))
        menu.add_cascade(label='Export Rows', menu=export_menu,
                         state=(tk.NORMAL if chosen else tk.DISABLED))
        menu.add_separator()

        manager = getattr(self.project_tracker, 'manager', None)
        menu.add_command(
            label='Undo',
            state=(tk.NORMAL if manager and manager.can_undo()
                   else tk.DISABLED),
            command=self._undo)
        menu.add_command(
            label='Redo',
            state=(tk.NORMAL if manager and manager.can_redo()
                   else tk.DISABLED),
            command=self._redo)

        try:
            menu.tk_popup(x_root, y_root)
        finally:
            menu.grab_release()

    def _bulk_set_status(self, deliverable_ids, status: str) -> None:
        """Set a status on every chosen leaf, as one undoable step."""
        def apply() -> bool:
            changed = False
            for deliverable_id in self._as_ids(deliverable_ids):
                deliverable = self.project.get_deliverable_by_id(
                    deliverable_id)
                if deliverable is None:
                    continue
                if self._has_inputs(deliverable):
                    continue        # a row with inputs derives its status
                progress = progress_for_status(status,
                                               deliverable.progress)
                if (deliverable.status != status
                        or deliverable.progress != progress):
                    deliverable.status = status
                    deliverable.progress = progress
                    changed = True
            if changed:
                self.project.roll_up_deliverables()
            return changed

        if self.project_tracker:
            self.project_tracker.run_deliverable_as_command(
                apply, 'Set Status')
        else:
            apply()
        self.refresh()
        if self.on_project_changed:
            self.on_project_changed()

    def _bulk_write(self, deliverable_ids, field: str, value,
                    label: str) -> None:
        """Set one field on every chosen row, as one undoable step."""
        def apply() -> bool:
            changed = False
            for deliverable_id in self._as_ids(deliverable_ids):
                deliverable = self.project.get_deliverable_by_id(
                    deliverable_id)
                if deliverable is not None \
                        and getattr(deliverable, field) != value:
                    setattr(deliverable, field, value)
                    changed = True
            if changed:
                self.project.roll_up_deliverables()
            return changed

        if self.project_tracker:
            self.project_tracker.run_deliverable_as_command(apply, label)
        else:
            apply()
        self.refresh()
        if self.on_project_changed:
            self.on_project_changed()

    # ------------------------------------------------------------------
    # Assigning tasks
    # ------------------------------------------------------------------

    def _open_task_picker(self, deliverable_ids) -> None:
        """
        Open the task checklist for the row - or the marked rows - it was
        asked for.

        Drawn as a small copy of the grid itself: the same Treeview style,
        the task list's own indent and expanders, and a [ ] / [x] mark
        column like the gutter's. Tasks every edited row already holds
        arrive ticked; Assign makes the ticked set each row's membership -
        the same write whether one row or a marked set was picked, so a
        bulk assign reads exactly like a single one.
        """
        rows = [d for d in
                (self.project.get_deliverable_by_id(i)
                 for i in self._as_ids(deliverable_ids))
                if d is not None]
        if not rows:
            return
        tasks = self.project.display_order()
        if not tasks:
            self._say('There are no tasks to assign yet.')
            return

        # A task counts as "already assigned" only when every edited row
        # holds it - anything else arrives unticked and is applied to all.
        ticked = set(rows[0].task_ids)
        for row in rows[1:]:
            ticked &= set(row.task_ids)
        checked: Set[str] = set(ticked)

        window = ctk.CTkToplevel(self.winfo_toplevel())
        title = 'Assign Tasks' if len(rows) == 1 \
            else f'Assign Tasks to {len(rows)} Deliverables'
        window.title(title)
        window.geometry('640x420')
        window.transient(self.winfo_toplevel())

        search = ctk.CTkEntry(window, placeholder_text='Filter tasks…')
        search.pack(fill=tk.X, padx=12, pady=(12, 6))

        tree_frame = ctk.CTkFrame(window, fg_color='transparent')
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 6))

        tree = ttk.Treeview(
            tree_frame, columns=('Sel', 'No', 'Type', 'Progress'),
            show='tree headings', selectmode='browse')
        theme.style_treeview('Deliverables.Treeview',
                             row_height=self.GRID_ROW_HEIGHT)
        ttk.Style().configure('Deliverables.Treeview', indent=24)
        tree.configure(style='Deliverables.Treeview')
        tree.heading('#0', text='Task', anchor=tk.W)
        tree.heading('Sel', text='', anchor=tk.CENTER)
        tree.heading('No', text='No', anchor=tk.W)
        tree.heading('Type', text='Type', anchor=tk.W)
        tree.heading('Progress', text='Progress', anchor=tk.W)
        tree.column('#0', width=280, minwidth=120)
        tree.column('Sel', width=40, minwidth=40, stretch=False,
                    anchor=tk.CENTER)
        tree.column('No', width=50, minwidth=40, stretch=False)
        tree.column('Type', width=80, minwidth=60, stretch=False)
        tree.column('Progress', width=80, minwidth=60, stretch=False)

        # The grid's look, taken whole: the banded rows, and a parent drawn
        # bold the way the task list draws one. The two tags never fight -
        # the band sets the fill and 'parent' only the font.
        tree.tag_configure('evenrow',
                           background=theme.now(theme.GRID_ROW_BG))
        tree.tag_configure('oddrow',
                           background=theme.now(theme.GRID_ROW_ALT))
        try:
            base = tkfont.nametofont('TkDefaultFont')
            tree.tag_configure(
                'parent',
                font=(base.cget('family'), base.cget('size'), 'bold'))
        except tk.TclError:
            pass        # no display font to derive from; parents stay plain

        numbers = self.project.display_ids()
        task_by_id = {task.id: task for task in tasks}
        known = set(task_by_id)
        parents = {t.parent_task_id for t in tasks if t.parent_task_id}

        def mark(task_id: str) -> str:
            return MARK_SET if task_id in checked else MARK_NONE

        def draw(filter_text: str = '') -> None:
            tree.delete(*tree.get_children())
            wanted = filter_text.strip().lower()

            # A match keeps its ancestors on screen - the same rule the
            # grid's own filter keeps, so the outline never orphans a row.
            if wanted:
                shown_ids = set()
                for task in tasks:
                    haystack = f"{numbers.get(task.id, '')} " \
                               f"{task.name or ''} {task.task_type}"
                    if wanted in haystack.lower():
                        current = task
                        while current is not None \
                                and current.id not in shown_ids:
                            shown_ids.add(current.id)
                            current = task_by_id.get(
                                current.parent_task_id)
            else:
                shown_ids = known

            drawn = 0
            for task in tasks:
                if task.id not in shown_ids:
                    continue
                parent = task.parent_task_id \
                    if task.parent_task_id in shown_ids else ''
                tags = ['evenrow' if drawn % 2 == 0 else 'oddrow']
                if task.id in parents:
                    tags.append('parent')
                tree.insert(
                    parent, tk.END, iid=task.id, open=True,
                    text=task.name or '(unnamed)', tags=tuple(tags),
                    values=(
                        mark(task.id),
                        str(numbers.get(task.id, '')),
                        task.task_type,
                        f'{task.progress}%',
                    ))
                drawn += 1

        def toggle(task_id: str) -> None:
            if task_id in checked:
                checked.discard(task_id)
            else:
                checked.add(task_id)
            if tree.exists(task_id):
                values = list(tree.item(task_id, 'values'))
                values[0] = mark(task_id)
                tree.item(task_id, values=values)

        def on_click(event) -> Optional[str]:
            if tree.identify_region(event.x, event.y) \
                    not in ('cell', 'tree'):
                return None
            if tree.identify_element(event.x, event.y) \
                    == 'Treeitem.indicator':
                return None     # the expander still folds the branch
            item = tree.identify_row(event.y)
            if not item:
                return None
            # The [ ]/[x] cell is the mark gesture, like the grid's gutter;
            # a click on any other cell of the row means the same here.
            toggle(item)
            return 'break'

        tree.bind('<Button-1>', on_click)
        tree.bind('<space>',
                  lambda _e: toggle(tree.focus()) if tree.focus() else None)
        tree.bind('<Return>',
                  lambda _e: toggle(tree.focus()) if tree.focus() else None)
        search.bind('<KeyRelease>', lambda _e: draw(search.get()))
        draw()

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL,
                                  command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.LEFT, fill=tk.Y)

        buttons = ctk.CTkFrame(window, fg_color='transparent')
        buttons.pack(fill=tk.X, padx=12, pady=(0, 12))

        def apply() -> None:
            window.destroy()
            self._assign_tasks([d.id for d in rows], set(checked))

        ctk.CTkButton(buttons, text='All', width=64,
                      command=lambda: (checked.update(
                          t.id for t in tasks), draw(search.get()))
                      ).pack(side=tk.LEFT)
        ctk.CTkButton(buttons, text='None', width=64,
                      command=lambda: (checked.clear(),
                                       draw(search.get()))
                      ).pack(side=tk.LEFT, padx=(6, 0))
        ctk.CTkButton(buttons, text='Assign', width=90,
                      command=apply).pack(side=tk.RIGHT, padx=(6, 0))
        ctk.CTkButton(buttons, text='Cancel', width=90,
                      command=window.destroy).pack(side=tk.RIGHT)

        grab_when_visible(window)

    def _assign_tasks(self, deliverable_ids, task_ids: Set[str]) -> None:
        """
        Make each given row's membership exactly the chosen task set, as one
        undoable step - the roll-up inside is what re-derives the progress
        the new membership implies.
        """
        wanted = sorted(task_ids)

        def apply() -> bool:
            changed = False
            for deliverable_id in self._as_ids(deliverable_ids):
                deliverable = self.project.get_deliverable_by_id(
                    deliverable_id)
                if deliverable is None:
                    continue
                if deliverable.task_ids != wanted:
                    deliverable.task_ids = list(wanted)
                    changed = True
            if changed:
                self.project.roll_up_deliverables()
            return changed

        if self.project_tracker:
            changed = self.project_tracker.run_deliverable_as_command(
                apply, 'Assign Tasks')
        else:
            changed = apply()
        if changed:
            logger.info("Set task membership on %d deliverable(s): %s",
                        len(self._as_ids(deliverable_ids)), wanted)
        self.refresh()
        if self.on_project_changed:
            self.on_project_changed()

    def _open_task_row_menu(self, item: str, x_root, y_root) -> None:
        """
        The right-click menu on an assigned-task row: it is display, not a
        deliverable, so all it offers is the one thing it can change -
        coming off the deliverable it hangs under.
        """
        _tag, deliverable_id, task_id = item.split(':', 2)
        task = self.project.get_task_by_id(task_id)
        label = (f"Remove '{task.name}' from deliverable"
                 if task is not None else 'Remove from deliverable')
        menu = tk.Menu(self.tree, tearoff=0)
        menu.add_command(
            label=label,
            command=lambda: self._unassign_task(deliverable_id, task_id))
        try:
            menu.tk_popup(x_root, y_root)
        finally:
            menu.grab_release()

    def _unassign_task(self, deliverable_id: str, task_id: str) -> None:
        """Take one task off one row - the submenu's one-click remove."""
        def apply() -> bool:
            deliverable = self.project.get_deliverable_by_id(deliverable_id)
            if deliverable is None or task_id not in deliverable.task_ids:
                return False
            deliverable.task_ids.remove(task_id)
            self.project.roll_up_deliverables()
            return True

        if self.project_tracker:
            changed = self.project_tracker.run_deliverable_as_command(
                apply, 'Unassign Task')
        else:
            changed = apply()
        if changed:
            logger.info("Removed task %s from deliverable %s",
                        task_id, deliverable_id)
        self.refresh()
        if self.on_project_changed:
            self.on_project_changed()

    def _undo(self) -> None:
        manager = getattr(self.project_tracker, 'manager', None)
        if manager and manager.can_undo() and manager.undo():
            self.refresh()
            if self.on_project_changed:
                self.on_project_changed()

    def _redo(self) -> None:
        manager = getattr(self.project_tracker, 'manager', None)
        if manager and manager.can_redo() and manager.redo():
            self.refresh()
            if self.on_project_changed:
                self.on_project_changed()

    # ------------------------------------------------------------------
    # The details window
    # ------------------------------------------------------------------

    def _open_details(self, deliverable_id: str) -> None:
        """
        Open a small window for the row's notes - description and
        acceptance criteria live in the one details field.
        """
        deliverable = self.project.get_deliverable_by_id(deliverable_id)
        if deliverable is None:
            return

        window = ctk.CTkToplevel(self.winfo_toplevel())
        window.title(f"Deliverable - {deliverable.name or 'untitled'}")
        window.geometry('420x400')
        window.transient(self.winfo_toplevel())

        tasks = self.project.tasks_for_deliverable(deliverable.id)
        if tasks:
            ctk.CTkLabel(
                window, text='Assigned tasks',
                anchor=tk.W).pack(fill=tk.X, padx=12, pady=(12, 2))
            numbers = self.project.display_ids()
            for task in tasks:
                line = ctk.CTkFrame(window, fg_color='transparent')
                line.pack(fill=tk.X, padx=12)
                ctk.CTkLabel(
                    line,
                    text=f"{numbers.get(task.id, '')}  "
                         f"{task.name or '(unnamed)'}",
                    anchor=tk.W).pack(side=tk.LEFT, fill=tk.X, expand=True)
                ctk.CTkButton(
                    line, text='Remove', width=64,
                    command=lambda t=task: (
                        self._unassign_task(deliverable.id, t.id),
                        window.destroy())
                ).pack(side=tk.RIGHT)

        ctk.CTkLabel(
            window, text='Description / acceptance criteria',
            anchor=tk.W).pack(fill=tk.X, padx=12, pady=(12, 4))
        text = ctk.CTkTextbox(window, wrap='word')
        text.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))
        text.insert('1.0', deliverable.details or '')

        buttons = ctk.CTkFrame(window, fg_color='transparent')
        buttons.pack(fill=tk.X, padx=12, pady=(0, 12))

        def save():
            self._write(deliverable_id,
                        {'details': text.get('1.0', tk.END).strip()},
                        'Edit Details')
            window.destroy()

        ctk.CTkButton(buttons, text='Save', width=90,
                      command=save).pack(side=tk.RIGHT, padx=(6, 0))
        ctk.CTkButton(buttons, text='Cancel', width=90,
                      command=window.destroy).pack(side=tk.RIGHT)

        grab_when_visible(window)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _open_export_menu(self, button) -> None:
        """The export choices under the header's Export button."""
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label='Export All as CSV',
                         command=lambda: self.export_rows(None, 'csv'))
        menu.add_command(label='Export All as JSON',
                         command=lambda: self.export_rows(None, 'json'))
        marked = self.marked_ids()
        menu.add_separator()
        menu.add_command(
            label=f'Export Marked as CSV ({len(marked)})',
            state=tk.NORMAL if marked else tk.DISABLED,
            command=lambda: self.export_rows(marked, 'csv'))
        menu.add_command(
            label=f'Export Marked as JSON ({len(marked)})',
            state=tk.NORMAL if marked else tk.DISABLED,
            command=lambda: self.export_rows(marked, 'json'))
        try:
            menu.tk_popup(button.winfo_rootx(),
                          button.winfo_rooty() + button.winfo_height())
        finally:
            menu.grab_release()

    def export_rows(self, deliverable_ids, fmt: str) -> None:
        """
        Write the chosen rows - or the whole list - to CSV or JSON.

        The name is indented by its depth, the Excel-like shape the spec
        asks for; a Level column carries the depth as a number as well, so
        a spreadsheet can re-derive the hierarchy without counting spaces.
        """
        if deliverable_ids:
            chosen = set(deliverable_ids)
            rows = [d for d in self.project.deliverable_display_order()
                    if d.id in chosen]
        else:
            rows = self.project.deliverable_display_order()
        if not rows:
            self._say('There is nothing to export.')
            return

        path = messagebox.asksaveasfilename(
            defaultextension=f'.{fmt}',
            filetypes=[(fmt.upper(), f'*.{fmt}'), ('All files', '*.*')],
            title='Export Deliverables')
        if not path:
            return

        numbers = self.project.deliverable_display_ids()
        try:
            if fmt == 'json':
                with open(path, 'w', encoding='utf-8') as handle:
                    json.dump([d.to_dict() for d in rows], handle,
                              indent=2, ensure_ascii=False, default=str)
            else:
                with open(path, 'w', encoding='utf-8', newline='') \
                        as handle:
                    writer = csv.writer(handle)
                    writer.writerow(
                        ['No', 'Level', 'Name', 'Status', 'Progress',
                         'Weight', 'Assignee', 'Tasks', 'Due Date',
                         'Priority', 'Tags', 'Details'])
                    for deliverable in rows:
                        level = self.project.deliverable_outline_level(
                            deliverable.id)
                        writer.writerow([
                            numbers.get(deliverable.id, ''),
                            level,
                            '    ' * (level - 1) + (deliverable.name or ''),
                            deliverable.status,
                            deliverable.progress,
                            deliverable.weight,
                            ', '.join(deliverable.assignees),
                            ', '.join(
                                task.name for task in
                                self.project.tasks_for_deliverable(
                                    deliverable.id)),
                            (deliverable.due_date.strftime(DATE_FORMAT)
                             if deliverable.due_date else ''),
                            deliverable.priority,
                            ', '.join(deliverable.tags),
                            deliverable.details,
                        ])
            logger.info("Exported %d deliverable(s) to %s", len(rows), path)
            self._say(f"Exported {len(rows)} row(s) to {path}.")
        except OSError:
            logger.exception("Could not export deliverables to %s", path)
            messagebox.showerror(
                'Export Failed',
                f'The file could not be written:\n{path}')

    # ------------------------------------------------------------------
    # Small helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _as_ids(deliverable_ids) -> List[str]:
        """One row or several, always as a list."""
        if deliverable_ids is None:
            return []
        if isinstance(deliverable_ids, str):
            return [deliverable_ids]
        return [str(i) for i in deliverable_ids]

    def _say(self, message: str) -> None:
        """Put a line into the status bar, where the application has one."""
        if self.on_status:
            try:
                self.on_status(message)
            except Exception:
                logger.debug("Could not show status %r", message)

    # ------------------------------------------------------------------
    # What the status bar shows
    # ------------------------------------------------------------------
    def selection_status(self) -> Optional[str]:
        """
        The status-bar line for the row under the cursor, or None.

        A deliverable row describes the deliverable; a task row describes
        the task it stands for, the same line the task list would write.
        """
        selection = self.tree.selection()
        if not selection:
            return None
        item = selection[0]
        if self._is_task_row(item):
            task = self.project.get_task_by_id(item.rsplit(':', 1)[-1])
            return task_status_line(task) if task is not None else None
        deliverable = self.project.get_deliverable_by_id(item)
        if deliverable is None:
            return None
        return deliverable_status_line(deliverable)

    def _push_selection_status(self) -> None:
        """Tell the status bar what is selected now, if it is listening."""
        if self.on_status:
            try:
                self.on_status(self.selection_status() or "Ready")
            except Exception:
                logger.debug("Could not show the selection status")
