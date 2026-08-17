"""
Task list view for the Gantt Project Management Tool.

Rows are reordered by dragging them, or through the right-click menu in
contextmenu.py. The dialog a row is opened into is in taskdialogs.py.

DEVELOPMENT NOTES:
------------------
Drag-and-drop used to be routed through tkinterdnd2, behind a guard that
tested for tkinterdnd2.TkinterDnD.Treeview and .Scrollbar. That library
provides neither - it exposes Tk, DnDWrapper and the DND_* constants - so the
guard was always false, every tkinterdnd2 branch was unreachable, and the
plain-Tk fallback it fell back to had an empty <B1-Motion> handler. Nothing
responded to a drag on any platform.

tkinterdnd2 is not needed for this in any case: it exists to exchange drops
with other applications, whereas moving a row inside one Treeview is a matter
of the pointer position, which plain Tk reports perfectly well.
"""

import tkinter as tk
from tkinter import ttk
# See gantt_app/views/dialogs.py: native on macOS and Windows, drawn
# to match the application on X11
from gantt_app.views import dialogs as messagebox
from typing import Callable, Optional, List

import customtkinter as ctk

from gantt_app.models import Task, Project
from gantt_app.utils.undoredo import ProjectStateTracker
from gantt_app.views.contextmenu import TaskContextMenu
from gantt_app.views.taskdialogs import CreateTaskDialog
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


class DragDropTaskList(ctk.CTkFrame):
    """
    Task list whose rows can be reordered by dragging or from a right-click
    menu.

    DEVELOPMENT NOTES:
    ------------------
    Dragging moves a row within its own set of siblings; the same moves are
    offered by the context menu in contextmenu.py. Dependencies are set on
    the Dependency tab of the task dialog, which can express the link type
    and hardness that a drag cannot.
    """

    #: Light grey grid palette for the task table.
    GRID_LINE = '#d0d0d0'        # cell separators
    GRID_ROW_BASE = '#ffffff'    # even rows
    GRID_ROW_ALT = '#f4f4f4'     # odd rows, giving the banded grid look
    GRID_HEADING_BG = '#e4e4e4'
    GRID_TEXT = '#1a1a1a'
    GRID_SELECT_BG = '#cfe2f3'
    GRID_ROW_HEIGHT = 26

    #: The line marking where a dragged task would land.
    DROP_LINE_COLOR = '#1f6aa5'
    DROP_LINE_THICKNESS = 2

    #: How far the pointer must travel before a press counts as a drag,
    #: so a click that wobbles by a pixel still selects rather than moves.
    DRAG_THRESHOLD_PX = 5

    #: Pointer shown while dragging a row.
    DRAG_CURSOR = 'hand2'

    #: Text colour of a row that has been cut and not yet pasted.
    CUT_ROW_TEXT = '#9aa0a6'

    def _apply_grid_style(self):
        """
        Give the task table a light grey grid.

        DEVELOPMENT NOTES:
        ------------------
        ttk.Treeview has no border option, so the grid is drawn by the theme:
        the 'clam' theme is the only stock one that honours bordercolor and
        relief on Treeview cells, and alternating row tags supply the
        horizontal banding. Both are needed - borders alone look flat, and
        banding alone gives no column separation.

        The style is namespaced under 'Gantt.Treeview' so it cannot disturb
        any other ttk widget in the application.
        """
        style = ttk.Style()

        try:
            style.theme_use('clam')
        except tk.TclError:
            # Fall back to whatever theme is active; banding still applies
            logger.debug("The 'clam' ttk theme is unavailable; grid lines may "
                         "not render on this platform")

        style.configure(
            'Gantt.Treeview',
            background=self.GRID_ROW_BASE,
            fieldbackground=self.GRID_ROW_BASE,
            foreground=self.GRID_TEXT,
            rowheight=self.GRID_ROW_HEIGHT,
            borderwidth=1,
            relief='solid',
            bordercolor=self.GRID_LINE,
            lightcolor=self.GRID_LINE,
            darkcolor=self.GRID_LINE
        )
        style.configure(
            'Gantt.Treeview.Heading',
            background=self.GRID_HEADING_BG,
            foreground=self.GRID_TEXT,
            relief='raised',
            borderwidth=1,
            bordercolor=self.GRID_LINE
        )
        style.map(
            'Gantt.Treeview',
            background=[('selected', self.GRID_SELECT_BG)],
            foreground=[('selected', self.GRID_TEXT)]
        )
        style.map(
            'Gantt.Treeview.Heading',
            background=[('active', self.GRID_LINE)]
        )

        self.tree.configure(style='Gantt.Treeview')


    def __init__(self, master, project: Project, 
                 on_task_select: Callable[[Task], None] = None,
                 on_task_edit: Callable[[Task], None] = None,
                 on_project_changed: Callable[[], None] = None,
                 project_tracker: ProjectStateTracker = None,
                 clipboard_manager=None):
        super().__init__(master)
        
        self.master = master
        self.project = project
        self.on_task_select = on_task_select
        self.on_task_edit = on_task_edit
        self.on_project_changed = on_project_changed
        self.project_tracker = project_tracker
        self.clipboard_manager = clipboard_manager
        
        # Track dragged task
        self.dragged_task_id = None
        self.drag_item = None

        # Where the press started, whether it has become a drag, the row the
        # drop would land at, and which of its edges the line sits on
        self._drag_origin = None
        self._dragging = False
        self._drop_target = None
        self._drop_above = True
        self._drop_line_widget = None

        # Create UI
        self._create_ui()
        
        # Update task list
        self.update_task_list()
    
    def _create_ui(self):
        """Create the user interface."""
        # Title
        title_label = ctk.CTkLabel(self, text="Task List", font=ctk.CTkFont(weight="bold"))
        title_label.pack(fill=tk.X, padx=10, pady=5)
        
        # Treeview frame
        tree_frame = ctk.CTkFrame(self)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 'tree headings' rather than 'headings': column #0 is what carries
        # the expander, so hiding it left a task with sub-tasks looking
        # exactly like one without, and gave nothing to click to fold a
        # branch away. The names used to be prefixed with '|--' to stand in
        # for the indentation this column draws properly.
        self.tree = ttk.Treeview(tree_frame, columns=(
            'ID', 'Name', 'Type', 'Duration', 'Start', 'End', 'Progress', 'Dependencies', 'Milestone'
        ), show='tree headings')

        # Configure columns
        self.tree.heading('#0', text='', anchor=tk.W)
        self.tree.heading('ID', text='ID', anchor=tk.W)
        self.tree.heading('Name', text='Name', anchor=tk.W)
        self.tree.heading('Type', text='Type', anchor=tk.W)
        self.tree.heading('Duration', text='Duration (Days)', anchor=tk.W)
        self.tree.heading('Start', text='Start Date', anchor=tk.W)
        self.tree.heading('End', text='End Date', anchor=tk.W)
        self.tree.heading('Progress', text='Progress', anchor=tk.W)
        self.tree.heading('Dependencies', text='Dependencies', anchor=tk.W)
        self.tree.heading('Milestone', text='Milestone', anchor=tk.W)
        
        # Column widths. #0 holds only the expander, so it stays narrow.
        #
        # Nothing stretches. Name used to, which is what made it impossible
        # to widen: a stretchable column absorbs whatever width is left over,
        # so ttk re-stretched it the moment the drag ended and it sprang back.
        # The same rule squeezed it to a sliver whenever the pane was narrower
        # than the other columns needed, because a stretchable column is also
        # the one ttk takes space away from.
        #
        # With fixed widths the columns are exactly what they are set to, a
        # drag sticks, and the horizontal scrollbar reaches anything that no
        # longer fits. minwidth keeps a column from being dragged shut.
        self.tree.column('#0', width=34, minwidth=34, stretch=False)
        self.tree.column('ID', width=60, minwidth=40, stretch=False)
        self.tree.column('Name', width=260, minwidth=80, stretch=False)
        self.tree.column('Type', width=90, minwidth=60, stretch=False)
        self.tree.column('Duration', width=110, minwidth=60, stretch=False)
        self.tree.column('Start', width=100, minwidth=80, stretch=False)
        self.tree.column('End', width=100, minwidth=80, stretch=False)
        self.tree.column('Progress', width=80, minwidth=60, stretch=False)
        self.tree.column('Dependencies', width=150, minwidth=80, stretch=False)
        self.tree.column('Milestone', width=80, minwidth=60, stretch=False)
        
        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)

        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        # Grid layout
        self.tree.grid(row=0, column=0, sticky=tk.NSEW)
        vsb.grid(row=0, column=1, sticky=tk.NS)
        hsb.grid(row=1, column=0, sticky=tk.EW)
        
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        # Store reference to tree_frame for DnD
        self.tree_frame = tree_frame

        self._apply_grid_style()

        # Configure tags for subtask styling
        # Sub-tasks are ordinary work and read in the same colour as tasks;
        # the indent and the Type column already mark them as nested
        self.tree.tag_configure('subtask', foreground=self.GRID_TEXT)

        # Alternating row shading, which is what makes the rows read as a grid
        self.tree.tag_configure('oddrow', background=self.GRID_ROW_ALT)
        self.tree.tag_configure('evenrow', background=self.GRID_ROW_BASE)

        # A row that has been cut and is waiting to be pasted somewhere.
        # A Treeview row cannot be made half transparent the way a web page
        # would fade one, so it is greyed instead - the same thing said in
        # the way this widget can say it.
        self.tree.tag_configure('cut', foreground=self.CUT_ROW_TEXT)
        
        # Bind events
        self.tree.bind('<Double-1>', self.on_double_click)
        self.tree.bind('<ButtonPress-1>', self.on_press)
        self.tree.bind('<ButtonRelease-1>', self.on_release)
        self.tree.bind('<B1-Motion>', self.on_drag)
        self.tree.bind('<<TreeviewSelect>>', self.on_select)

        # Right-click menu, which offers the same moves as dragging
        self.context_menu = TaskContextMenu(
            self.tree,
            project_getter=lambda: self.project,
            on_move=self.move_task,
            on_indent=self.indent_task,
            on_outdent=self.outdent_task,
            on_edit=self.edit_task,
            on_delete=self.delete_task,
            on_create=self.create_task,
            on_undo=self.undo,
            on_redo=self.redo,
            can_undo=self.can_undo,
            can_redo=self.can_redo,
            on_copy=self.copy_tasks,
            on_cut=self.cut_tasks,
            on_paste=self.paste_tasks,
            can_copy_or_cut=self.can_copy_or_cut,
            can_paste=self.can_paste,
        )

    def on_double_click(self, event):
        """
        Fold a task's sub-tasks away, or open them up again.

        DEVELOPMENT NOTES:
        ------------------
        Double-click used to open the edit dialog. Editing is on the context
        menu now, and the gesture does what it does in every other tree:
        expands and collapses.

        'break' stops ttk's own double-click handler running afterwards,
        which would toggle the row a second time and undo this.
        """
        item = self.tree.identify_row(event.y)
        if not item:
            return None

        if self.tree.get_children(item):
            self.tree.item(item, open=not self.tree.item(item, 'open'))

        return 'break'

    def edit_task(self, task_id: str):
        """
        Open the edit window for a task.

        PARAMETERS:
        -----------
        task_id : str
            The task to edit.

        DEVELOPMENT NOTES:
        ------------------
        Shared by the double-click and the context menu's Edit entry. The
        dialog is opened inside a try/except so a failure while building it
        is reported rather than leaving an empty window on screen with
        nothing in the log.
        """
        task = self.project.get_task_by_id(task_id)
        if not task or not self.on_task_edit:
            return

        logger.info("Editing task %s %r", task.id, task.name)
        try:
            self.on_task_edit(task)
        except Exception:
            logger.exception("Could not open the edit dialog for task %s", task.id)
            messagebox.showerror(
                "Edit Task Failed",
                "The task could not be opened for editing.\n\n"
                "See the Log window for details."
            )

    def delete_task(self, task_id: str):
        """
        Delete a task, after confirming, and refresh the list.

        PARAMETERS:
        -----------
        task_id : str
            The task to delete.

        DEVELOPMENT NOTES:
        ------------------
        Deleting a task takes its sub-tasks with it, so the confirmation says
        how many will go. A right-click and a menu entry is a short path to
        losing a branch of the plan, and the count is the part a user cannot
        see from the row itself.

        The delete is undoable, which the prompt says so that confirming
        feels less final than it looks.
        """
        task = self.project.get_task_by_id(task_id)
        if task is None:
            return

        subtasks = self.project.get_subtasks(task_id)
        if subtasks:
            detail = (f"\n\nIts {len(subtasks)} sub-task(s) will be deleted "
                      f"as well.")
        else:
            detail = ""

        if not messagebox.askyesno(
            "Delete Task",
            f"Delete '{task.name}'?{detail}\n\nThis can be undone.",
            icon=messagebox.WARNING,
        ):
            return

        logger.info("Deleting task %s %r", task.id, task.name)
        self.remove_task(task_id)

    def _cut_task_ids(self) -> set:
        """
        The rows waiting to be pasted somewhere, so they can be greyed.

        Empty when there is no clipboard, which is how the task list is
        built in the tests and wherever it is used without one.
        """
        if self.clipboard_manager is None:
            return set()
        try:
            return set(self.clipboard_manager.cut_item_ids)
        except AttributeError:
            return set()

    def get_selected_task_ids(self) -> List[str]:
        """
        The tasks the user has picked out, in the order they are shown.

        RETURNS:
        --------
        List[str]
            Task IDs, empty when nothing is selected.

        DEVELOPMENT NOTES:
        ------------------
        The toolbar and the menu bar reach for this by name, behind a
        hasattr, to decide what Copy, Cut and Paste act on. Nothing answered
        to it, so the test was false every time and every one of those
        actions quietly did nothing at all.

        Rows carry their task's ID as their tree item ID, so the selection is
        the answer; a row for a task that has since gone is left out rather
        than handed on to be looked up and not found.
        """
        try:
            selection = self.tree.selection()
        except tk.TclError:
            return []
        return [task_id for task_id in selection
                if self.project.get_task_by_id(task_id) is not None]

    def copy_tasks(self, selected_ids: List[str]):
        """
        Copy selected tasks to clipboard.
        
        PARAMETERS:
        -----------
        selected_ids : List[str]
            List of task IDs to copy
        """
        if self.clipboard_manager:
            self.clipboard_manager.copy(selected_ids)
            self.update_task_list()

    def cut_tasks(self, selected_ids: List[str]):
        """
        Cut selected tasks to clipboard.
        
        PARAMETERS:
        -----------
        selected_ids : List[str]
            List of task IDs to cut
        """
        if self.clipboard_manager:
            self.clipboard_manager.cut(selected_ids)
            self.update_task_list()

    def paste_tasks(self, target_container_id: Optional[str],
                    anchor_id: Optional[str] = None):
        """
        Paste tasks from the clipboard into a container.

        PARAMETERS:
        -----------
        target_container_id : Optional[str]
            ID of the target container (parent task ID), or None for root
            level.
        anchor_id : Optional[str]
            The row the paste was asked for from. Rows that land beside it
            are placed directly after it rather than at the end of the
            branch. None - from the toolbar, or a shortcut over empty space
            - leaves them where they land.
        """
        if not self.clipboard_manager:
            return

        pasted = self.clipboard_manager.paste(target_container_id, anchor_id)
        self.update_task_list()

        # What has just arrived is what the user is about to move, rename or
        # drag somewhere else, so it is what is left selected
        if pasted:
            try:
                self.tree.selection_set(*pasted)
                self.tree.focus(pasted[0])
                self.tree.see(pasted[0])
            except tk.TclError:
                logger.debug("Pasted rows %s are not on show to select",
                             pasted)

        if self.on_project_changed:
            self.on_project_changed()

    def can_copy_or_cut(self, selected_ids: List[str]) -> bool:
        """
        Check if copy or cut operations are possible.
        
        PARAMETERS:
        -----------
        selected_ids : List[str]
            List of task IDs to check
            
        RETURNS:
        --------
        bool
            True if copy/cut is possible
        """
        return len(selected_ids) > 0

    def can_paste(self, target_container_id: Optional[str]) -> bool:
        """
        Check if paste operation is possible for the target container.
        
        PARAMETERS:
        -----------
        target_container_id : Optional[str]
            ID of the target container
            
        RETURNS:
        --------
        bool
            True if paste is possible
        """
        if not self.clipboard_manager:
            return False
        return self.clipboard_manager.can_paste(target_container_id)


    def on_select(self, event):
        """
        Handle task selection.

        DEVELOPMENT NOTES:
        ------------------
        The row's iid is the task ID. This used to read it out of the item's
        'text' instead, which only worked while column #0 was hidden and
        being used to stash the ID.
        """
        item = self.tree.selection()[0] if self.tree.selection() else None
        if item:
            task = self.project.get_task_by_id(item)
            if task and self.on_task_select:
                self.on_task_select(task)
    
    def on_press(self, event):
        """
        Begin a possible drag.

        DEVELOPMENT NOTES:
        ------------------
        Only the row is recorded here. Whether this becomes a drag is decided
        in on_drag once the pointer has actually travelled, so an ordinary
        click to select, and the double-click that opens the edit dialog, are
        not mistaken for very small drags.
        """
        item = self.tree.identify_row(event.y)
        if not item:
            # The heading, or empty space below the last row
            return

        self.dragged_task_id = item
        self.drag_item = item
        self._drag_origin = (event.x, event.y)
        self._dragging = False

    def on_drag(self, event):
        """
        Track a drag in progress and mark the row it would drop onto.

        DEVELOPMENT NOTES:
        ------------------
        This was a no-op whose comment said tkinterdnd2 was needed for real
        drag-and-drop. It is not: tkinterdnd2 exists to exchange drops with
        other applications, while moving a row inside a single Treeview only
        needs the pointer position. The tkinterdnd2 path was unreachable in
        any case - the guard deciding whether the library was usable tested
        for TkinterDnD.Treeview and TkinterDnD.Scrollbar, neither of which
        that library defines - so between the two nothing responded to a drag
        at all.

        Rows that are not valid drops are deliberately left unmarked, so the
        line only appears where releasing would actually do something.
        """
        if self.dragged_task_id is None or self._drag_origin is None:
            return

        if not self._dragging:
            if abs(event.y - self._drag_origin[1]) < self.DRAG_THRESHOLD_PX:
                return
            self._dragging = True
            try:
                self.tree.configure(cursor=self.DRAG_CURSOR)
            except tk.TclError:
                pass

        self._mark_drop_target(self.tree.identify_row(event.y), event.y)

    def _mark_drop_target(self, item, pointer_y=None):
        """
        Show where the dragged row would land.

        PARAMETERS:
        -----------
        item : str
            The row under the pointer, or '' for none.
        pointer_y : int, optional
            Pointer position, used to decide which edge of the row the line
            sits on.

        DEVELOPMENT NOTES:
        ------------------
        A drop lands *at* the target's position, so the line is drawn on the
        edge the row will be inserted against: above the target when the
        pointer is in its top half, below it otherwise. Shading the whole row
        instead, as this first did, said which row was involved but not where
        the dragged one would end up.
        """
        if item and not self._is_valid_drop(item):
            item = None

        self._drop_target = item or None

        if self._drop_target is None:
            self._hide_drop_line()
            return

        self._show_drop_line(self._drop_target, pointer_y)

    def _drop_line(self):
        """The line widget, created on first use."""
        if self._drop_line_widget is None:
            self._drop_line_widget = tk.Frame(
                self.tree, height=self.DROP_LINE_THICKNESS,
                background=self.DROP_LINE_COLOR,
                borderwidth=0, highlightthickness=0,
            )
        return self._drop_line_widget

    def _show_drop_line(self, item, pointer_y=None):
        """
        Put the indicator on the edge of a row the drop would insert against.

        DEVELOPMENT NOTES:
        ------------------
        place() rather than a canvas overlay: a Treeview will host a placed
        child directly, which keeps the line inside the scrolling viewport
        without a second widget to keep in step.
        """
        try:
            box = self.tree.bbox(item)
        except tk.TclError:
            box = None

        if not box:
            # The row is scrolled out of view
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

    def _hide_drop_line(self):
        """Take the indicator off screen."""
        if self._drop_line_widget is not None:
            self._drop_line_widget.place_forget()

    def _is_valid_drop(self, item):
        """
        Whether the dragged task can be dropped onto this row.

        DEVELOPMENT NOTES:
        ------------------
        A move stays inside one set of siblings, so a sub-task cannot be
        dropped onto a root task and quietly change parent. Refusing here,
        where the highlight is decided, means an invalid drop looks inert
        while the pointer is still over it.
        """
        if not item or item == self.dragged_task_id:
            return False
        source = self.project.get_task_by_id(self.dragged_task_id)
        target = self.project.get_task_by_id(item)
        if source is None or target is None:
            return False
        return source.parent_task_id == target.parent_task_id

    def _end_drag(self):
        """Clear every trace of a drag, whether it completed or not."""
        self._hide_drop_line()
        self._drop_target = None
        self._drop_above = True
        self.dragged_task_id = None
        self.drag_item = None
        self._drag_origin = None
        self._dragging = False
        try:
            self.tree.configure(cursor='')
        except tk.TclError:
            pass

    def on_release(self, event):
        """
        Finish a drag by moving the dragged task to the drop position.

        DEVELOPMENT NOTES:
        ------------------
        A release that never became a drag falls straight through, leaving
        click-to-select and double-click-to-edit untouched.
        """
        if self.dragged_task_id is None:
            return

        if not self._dragging:
            self._end_drag()
            return

        source_id = self.dragged_task_id
        target_id = self._drop_target
        self._end_drag()

        if target_id:
            self.move_task_before(source_id, target_id)

    def move_task(self, task_id: str, where: str):
        """
        Move a task within its siblings and refresh everything.

        PARAMETERS:
        -----------
        task_id : str
            The task to move.
        where : str
            'top', 'up', 'down' or 'bottom'.

        DEVELOPMENT NOTES:
        ------------------
        This is what the context menu calls. Ordering belongs to the project
        rather than to the widget, so the reordering itself lives on Project
        and this deals only with undo, redrawing and keeping the moved row
        selected.
        """
        self._apply_reorder(lambda: self.project.move_task(task_id, where),
                            task_id)

    def move_task_before(self, task_id: str, target_id: str):
        """Move a task to the position its sibling target_id occupies."""
        self._apply_reorder(
            lambda: self.project.move_task_before(task_id, target_id), task_id
        )

    def _manager(self):
        """The undo/redo manager, or None when there is no tracker."""
        tracker = self.project_tracker
        return getattr(tracker, 'manager', None) if tracker else None

    def can_undo(self) -> bool:
        """Whether there is anything to undo."""
        manager = self._manager()
        return bool(manager and manager.can_undo())

    def can_redo(self) -> bool:
        """Whether there is anything to redo."""
        manager = self._manager()
        return bool(manager and manager.can_redo())

    def undo(self):
        """Undo the last change and refresh."""
        manager = self._manager()
        if manager and manager.can_undo() and manager.undo():
            logger.info("Undo from the context menu")
            self._after_history_change()

    def redo(self):
        """Redo the last undone change and refresh."""
        manager = self._manager()
        if manager and manager.can_redo() and manager.redo():
            logger.info("Redo from the context menu")
            self._after_history_change()

    def _after_history_change(self):
        """
        Refresh once an undo or redo has been applied.

        DEVELOPMENT NOTES:
        ------------------
        on_project_changed reaches the chart and the toolbar's Undo and Redo
        entries, so the two routes to the history - this menu and the
        toolbar's Edit menu - leave the window in the same state.
        """
        self.update_task_list()
        if self.on_project_changed:
            self.on_project_changed()

    def create_task(self, task_type: str, anchor_id: str):
        """
        Open the create dialog for a new task placed at a row.

        PARAMETERS:
        -----------
        task_type : str
            'Task', 'Sub-Task' or 'Milestone'.
        anchor_id : Optional[str]
            The row the context menu was opened on, or None when it was
            opened over the empty space below the rows.

        DEVELOPMENT NOTES:
        ------------------
        A sub-task is created under the clicked row, which is what makes it
        a sub-task. A task or milestone is created beside it and dropped in
        directly below, rather than at the end of the plan: the menu was
        opened on a particular row, so that is where the new one belongs.

        With no row behind the menu the new task goes at the end of the plan
        at the top level, which is what right-clicking the empty space below
        the last row asks for. A sub-task has nothing to go under there, and
        the menu greys it out.
        """
        if anchor_id is None:
            anchor = None
        else:
            anchor = self.project.get_task_by_id(anchor_id)
            if anchor is None:
                # A row naming a task that has since gone. Not the same as
                # no row at all, so it creates nothing rather than quietly
                # adding one at the end of the plan
                logger.warning("Cannot create at unknown task %s", anchor_id)
                return

        if anchor is None:
            if task_type == "Subtask":
                return
            parent_id = None
        elif task_type == "Subtask":
            # A sub-task goes inside the clicked row; a task or milestone
            # goes beside it, which is what "under this row" means for those
            parent_id = anchor.id
        else:
            parent_id = anchor.parent_task_id

        parent = self.project.get_task_by_id(parent_id) if parent_id else None

        logger.info("Creating a %s at %s", task_type, anchor_id)

        dialog = CreateTaskDialog(
            self.winfo_toplevel(), self.project,
            task_type=task_type,
            parent_task=parent,
            on_save=lambda task: self._save_created(task, anchor_id, parent_id),
            project_tracker=self.project_tracker,
        )
        dialog.wait_window()

    def _save_created(self, task: Task, anchor_id: str, parent_id):
        """
        Add a newly created task and put it where the menu was opened.

        DEVELOPMENT NOTES:
        ------------------
        The level is set here rather than left to the dialog, which only
        honours a parent when it is building a sub-task. Choosing Task from
        a sub-task's menu should give another task beside it, not one that
        jumps out to the top of the plan.

        add_task appends, so a sibling is then moved up behind the row it
        was created from. A sub-task needs no move: rebuilding from the
        hierarchy already places it under its parent.
        """
        before = self.project.structure_snapshot()

        task.parent_task_id = parent_id
        # Only set task_type to Subtask if it's not already set to a specific type and has a parent
        if parent_id and task.task_type not in ("Phase", "Deliverable", "Milestone"):
            task.task_type = "Subtask"

        self.project.add_task(task)
        anchor = self.project.get_task_by_id(anchor_id)

        if anchor is not None and task.parent_task_id == anchor.parent_task_id:
            # A sibling: slot it in directly after the row it came from
            self.project.move_task_before(task.id, anchor_id)
            self.project.move_task(task.id, 'down')

        if self.project_tracker:
            self.project_tracker.restructure_tasks(
                before, self.project.structure_snapshot(), "Create Task"
            )

        self.update_task_list()
        try:
            self.tree.selection_set(task.id)
            self.tree.see(task.id)
        except tk.TclError:
            pass

        if self.on_project_changed:
            self.on_project_changed()

    def _report_dropped_links(self, dropped):
        """
        Tell the user about links a move made impossible.

        DEVELOPMENT NOTES:
        ------------------
        Indenting a task under its own predecessor is the ordinary way a
        phase gets built, and the link has to go: a task cannot wait for
        something it is part of. Dropping it quietly would leave the plan
        different from what the user thinks it is, so it is named. The
        dialog only appears when something actually went, which is rare.
        """
        if not dropped:
            return

        described = []
        for successor_id, predecessor_id in dropped:
            successor = self.project.get_task_by_id(successor_id)
            predecessor = self.project.get_task_by_id(predecessor_id)
            described.append(
                f"  {successor.name if successor else successor_id}"
                f"  ->  {predecessor.name if predecessor else predecessor_id}"
            )

        logger.info("Dropped %d link(s) made impossible by the move: %s",
                    len(dropped), dropped)
        messagebox.showinfo(
            "Dependency Removed",
            "A task cannot wait for something it is now part of, so "
            f"{'this link was' if len(dropped) == 1 else 'these links were'} "
            "removed:\n\n" + "\n".join(described)
            + "\n\nUndo puts everything back.",
            parent=self.winfo_toplevel(),
        )

    def indent_task(self, task_id: str):
        """Make a task a sub-task of the row above it."""
        self._apply_restructure(lambda: self.project.indent_task(task_id),
                                task_id, "Indent Task")

    def outdent_task(self, task_id: str):
        """Move a task out to sit beside its parent."""
        self._apply_restructure(lambda: self.project.outdent_task(task_id),
                                task_id, "Outdent Task")

    def _apply_restructure(self, change, task_id: str, label: str):
        """
        Run a change to the hierarchy, record it for undo and redraw.

        PARAMETERS:
        -----------
        change : callable
            Performs the change, returning True when anything moved.
        task_id : str
            The task being moved, so it can be reselected afterwards.
        label : str
            What to call the change in the undo history.

        DEVELOPMENT NOTES:
        ------------------
        The undo entry records the hierarchy as well as the order. Indenting
        rewrites parent_task_id and task_type on the tasks themselves, which
        the reorder entry cannot express - both of its orderings hold the
        same objects, so restoring one puts the list back and leaves every
        parent where the indent left it.

        The row is reopened after the redraw: a task indented under a
        collapsed parent would otherwise vanish from view, looking for all
        the world as if it had been deleted.
        """
        before = self.project.structure_snapshot()

        if not change():
            return

        after = self.project.structure_snapshot()

        if self.project_tracker:
            self.project_tracker.restructure_tasks(before, after, label)

        self.update_task_list()

        self._report_dropped_links(self.project.dropped_links(before, after))

        try:
            parent = self.tree.parent(task_id)
            while parent:
                self.tree.item(parent, open=True)
                parent = self.tree.parent(parent)
            self.tree.selection_set(task_id)
            self.tree.focus(task_id)
            self.tree.see(task_id)
        except tk.TclError:
            pass

        if self.on_project_changed:
            self.on_project_changed()

    def _apply_reorder(self, reorder, task_id: str):
        """
        Run a reordering, record it for undo and redraw.

        PARAMETERS:
        -----------
        reorder : callable
            Performs the move, returning True when anything changed.
        task_id : str
            The task being moved, so it can be reselected afterwards.

        DEVELOPMENT NOTES:
        ------------------
        Order is a property of Project.tasks as a whole rather than of any
        single task, so the undo entry records the list. update_task, which
        every other edit goes through, rewrites one task and cannot express
        a move.
        """
        before = list(self.project.tasks)

        if not reorder():
            return

        if self.project_tracker:
            self.project_tracker.reorder_tasks(before, list(self.project.tasks))

        self.update_task_list()

        try:
            self.tree.selection_set(task_id)
            self.tree.focus(task_id)
            self.tree.see(task_id)
        except tk.TclError:
            pass

        if self.on_project_changed:
            self.on_project_changed()


    def _would_create_circle(self, source_id: str, target_id: str) -> bool:
        """
        Check if adding a dependency would create a circular reference.
        
        This prevents:
        1. Direct circular dependencies (A -> B -> A)
        2. Indirect circular dependencies (A -> B -> C -> A)
        3. A task depending on itself
        4. A task depending on its own subtask (parent-child circular dependency)
        
        PARAMETERS:
        -----------
        source_id : str
            The task that would have target_id added as a dependency
        target_id : str
            The dependency to be added
        
        RETURNS:
        --------
        bool
            True if adding this dependency would create a circle
        """
        # Cannot depend on self
        if source_id == target_id:
            return True
        
        # Cannot depend on own subtask (directly or indirectly)
        if self.project.is_descendant(target_id, source_id):
            return True
        
        # Check for circular dependencies through the dependency graph
        def check_circle(task_id: str, visited: set) -> bool:
            if task_id in visited:
                return True
            
            task = self.project.get_task_by_id(task_id)
            if not task:
                return False
            
            visited.add(task_id)
            
            for dep_id in task.dependency_ids:
                if dep_id == source_id:
                    return True
                if check_circle(dep_id, visited.copy()):
                    return True
            
            return False
        
        # Check if target depends on source (directly or indirectly)
        return check_circle(target_id, set())
    
    def update_task_list(self):
        """
        Update the task list display with all task information.
        
        DEVELOPMENT NOTES:
        ------------------
        Displays tasks in a hierarchical structure where subtasks are indented
        under their parent tasks. Uses tags to apply visual indentation.
        """
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)

        self._populate_tree_hierarchical()
    
    def _populate_tree_hierarchical(self):
        """
        Populate the treeview with tasks in a hierarchical structure.
        
        DEVELOPMENT NOTES:
        ------------------
        This method first adds all root tasks, then adds subtasks under their
        parent tasks. It uses the treeview's parent-child relationships to
        create the visual hierarchy.

        Rows follow the order of Project.tasks. They used to be sorted by
        start date on every refresh, which left no way to arrange a plan by
        hand: a moved row sprang straight back to its date-order position, so
        reordering could not be seen even when it had worked. It also meant
        the visible order disagreed with the sequential IDs, which are handed
        out by list position.

        Sorting is left to the Gantt chart, which is where a reader looks for
        the plan in date order.
        """
        # Restart the row banding for each repopulation
        self._row_counter = 0

        # Map task IDs to tree items for parent-child relationships
        tree_items = {}

        # First pass: add all root tasks
        for task in self.project.get_root_tasks():
            item_id = self._add_task_to_tree(task, indent_level=0)
            tree_items[task.id] = item_id

        # Further passes: add subtasks once their parent is in the tree.
        # Imported files (notably GanttProject) can nest tasks several levels
        # deep, so keep sweeping until a pass places nothing new - a single
        # pass would silently drop anything below the second level.
        remaining = [t for t in self.project.tasks if t.parent_task_id]

        while remaining:
            placed = []
            for task in remaining:
                parent_item = tree_items.get(task.parent_task_id)
                if parent_item is None:
                    continue
                item_id = self._add_task_to_tree(task, parent_item=parent_item,
                                                 indent_level=1)
                tree_items[task.id] = item_id
                placed.append(task)

            if not placed:
                # Orphaned subtasks (parent missing or a cycle) - show at root
                for task in remaining:
                    tree_items[task.id] = self._add_task_to_tree(task, indent_level=0)
                break

            remaining = [t for t in remaining if t not in placed]
    
    def _add_task_to_tree(self, task: Task, parent_item: str = '', indent_level: int = 0):
        """
        Add a single task to the treeview.
        
        PARAMETERS:
        -----------
        task : Task
            The task to add
        parent_item : str
            The parent tree item ID (for subtasks)
        indent_level : int
            Indentation level for visual hierarchy
        
        RETURNS:
        --------
        str
            The tree item ID created
        """
        # Format dependencies
        dep_names = []
        for dep_id in task.dependencies:
            dep_task = self.project.get_task_by_id(dep_id)
            if dep_task:
                dep_names.append(dep_task.name)
        deps_str = ', '.join(dep_names) if dep_names else 'None'
        
        # Format dates
        start_str = task.start_date.strftime('%Y-%m-%d')
        end_str = task.end_date.strftime('%Y-%m-%d') if task.end_date else 'N/A'
        
        # Format milestone indicator
        milestone_str = 'Yes' if task.is_milestone else 'No'
        
        # Format duration
        duration = task.duration_days
        duration_str = str(duration) if duration is not None else 'N/A'
        
        # Format task type
        type_str = task.task_type
        
        # Column #0 draws the indentation and the expander, so the name is
        # no longer prefixed with '|--' to fake it
        # Insert into tree
        item_id = self.tree.insert(parent_item, tk.END,
                                 iid=task.id,
                                 text='',
                                 open=True,
                                 values=(
                                     task.id,  # IDs are short sequential numbers
                                     task.name,
                                     type_str,
                                     duration_str,
                                     start_str,
                                     end_str,
                                     f"{task.progress}%",
                                     deps_str,
                                     milestone_str
                                 ))
        
        # Alternating background, counted over rows actually drawn so the
        # banding stays continuous through nested sub-tasks
        self._row_counter = getattr(self, '_row_counter', 0)
        band = 'oddrow' if self._row_counter % 2 else 'evenrow'
        self._row_counter += 1

        tags = [band]
        if task.task_type == 'Subtask':
            tags.append('subtask')
        if task.id in self._cut_task_ids():
            tags.append('cut')
        self.tree.item(item_id, tags=tuple(tags))

        return item_id
    
    def add_task(self, task: Task):
        """Add a task to the project and update the list."""
        self.project.add_task(task)
        self.update_task_list()
        if self.on_project_changed:
            self.on_project_changed()
    
    def remove_task(self, task_id: str):
        """Remove a task from the project and update the list with undo support."""
        if self.project_tracker:
            if self.project_tracker.remove_task(task_id):
                self.update_task_list()
                if self.on_project_changed:
                    self.on_project_changed()
        else:
            # Fallback to direct removal
            self.project.remove_task(task_id)
            self.update_task_list()
            if self.on_project_changed:
                self.on_project_changed()
    
    def update_task(self, task: Task):
        """Update a task and refresh the list."""
        self.update_task_list()
        if self.on_project_changed:
            self.on_project_changed()
    
    def select_task(self, task_id: str):
        """
        Select a task in the list.

        DEVELOPMENT NOTES:
        ------------------
        The row's iid is the task ID, so this is a direct lookup. Scanning
        get_children() compared against the item's 'text' and only looked at
        the top level, so selecting a sub-task silently did nothing.
        """
        if not self.tree.exists(task_id):
            return
        self.tree.selection_set(task_id)
        self.tree.see(task_id)
