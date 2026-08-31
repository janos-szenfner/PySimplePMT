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

from gantt_app import theme
from gantt_app.models import TASK_TYPES, Task, Project
from gantt_app.dependencysyntax import format_links
from gantt_app.taskstyle import resolve as resolve_style
from gantt_app.utils.undoredo import ProjectStateTracker
from gantt_app.views.contextmenu import TaskContextMenu
from gantt_app.views.taskdialogs import CreateTaskDialog
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


#: What paste_tasks is given by a caller with no row in mind, meaning "use
#: whichever row the cursor is on".
#:
#: None cannot say that, because None already means something else and had to
#: keep meaning it: no row at all, which is the end of the plan. That is the
#: right-click menu opened over the empty space below the last row - the same
#: gesture that creates a task there. Overloading None onto both left the menu
#: pasting beside whatever happened to be selected halfway up the plan when
#: the user had pointed at the bottom of it.
FROM_CURSOR = object()


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

    #: The grid palette, as (light, dark) pairs from gantt_app.theme.
    #:
    #: Resolved to single colours in _apply_grid_style, because ttk takes one
    #: colour per thing and knows nothing about appearance modes - which is
    #: why the whole task list stayed white on a dark desktop. They have to
    #: be resolved again when the theme changes; see apply_theme.
    GRID_LINE = theme.GRID_LINE
    GRID_ROW_BASE = theme.GRID_ROW_BG
    GRID_ROW_ALT = theme.GRID_ROW_ALT
    GRID_HEADING_BG = theme.GRID_HEADING_BG
    GRID_TEXT = theme.GRID_TEXT
    GRID_SELECT_BG = theme.GRID_SELECT_BG
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
    CUT_ROW_TEXT = theme.GRID_CUT_TEXT

    #: Fill of a row on the critical path, while the icon has it turned on.
    #: The same light red the critical path window uses for those rows, so
    #: the report and the list agree about what a critical row looks like.
    CRITICAL_ROW_BG = theme.GRID_CRITICAL_BG

    def _apply_grid_style(self):
        """
        Re-colour the task table's global ttk style for the current theme.

        DEVELOPMENT NOTES:
        ------------------
        ``ttk.Style().theme_use('clam')`` is no longer called here; it is
        process-global and is done once at startup by
        :func:`gantt_app.theme.initialise_ttk_styles`. This method only
        re-resolves the named 'Gantt.Treeview' colours when the application
        appearance changes.
        """
        theme.style_treeview('Gantt.Treeview', row_height=self.GRID_ROW_HEIGHT)
        self.tree.configure(style='Gantt.Treeview')

    def _is_search_context(self, task) -> bool:
        """
        Whether a row is on screen only to say where a match sits.

        An ancestor kept for context is not itself a hit, and reads as one
        unless it is drawn differently.
        """
        matches = getattr(self, '_search_matches', None)
        if not matches:
            return False
        return task.id not in matches

    def is_summary_row(self, task) -> bool:
        """
        Whether a row brackets other rows.

        RETURNS:
        --------
        bool
            True for a Phase, and for any task that has
            work nested under it.

        DEVELOPMENT NOTES:
        ------------------
        Having children is what decides it, not the Type column - a Task
        with sub-tasks under it is a summary of them whatever its type says,
        and the hierarchy has to read the same whether that column is on
        screen or not. The container types are included as well so a Phase
        with nothing in it yet still reads as the bracket it is.
        """
        if task.is_container:
            return True
        return any(other.parent_task_id == task.id
                   for other in self.project.tasks)

    def _base_font(self):
        """
        The family and size the grid draws in, read from the desktop's own.

        RETURNS:
        --------
        Tuple[str, int]
            TkDefaultFont's family and size, asked of this widget's own Tk
            interpreter and kept.

        DEVELOPMENT NOTES:
        ------------------
        Read rather than named here, so the rows follow whatever the desktop
        uses - naming a family produced a task list in a different typeface
        from the rest of the window on every platform but the one it was
        written on.

        Asked through self.tree rather than through tkinter.font.nametofont,
        which resolves against the default root. A test suite builds and
        destroys a root per test, so nametofont can end up asking an
        interpreter that has already been torn down.
        """
        if self._base_font_spec is None:
            actual = self.tree.tk.call('font', 'actual', 'TkDefaultFont')
            values = dict(zip(actual[::2], actual[1::2]))
            family = str(values.get('-family', 'TkDefaultFont'))
            try:
                size = int(values.get('-size', 10))
            except (TypeError, ValueError):
                size = 10
            self._base_font_spec = (family, size or 10)
        return self._base_font_spec

    def _row_font(self, bold: bool, italic: bool, underline: bool):
        """
        The grid's own font, with the emphasis a row asked for.

        RETURNS:
        --------
        Tuple[str, int, str]
            A Tk font specification - family, size, and the modifiers.

        DEVELOPMENT NOTES:
        ------------------
        A specification rather than a tkinter.font.Font, and that is not a
        detail. A Font is an object in the Tk interpreter with a lifetime:
        one built here outlives the root that made it, and deleting it later
        reaches into an interpreter that may already be gone. A tuple is
        just a description - Tk reads it when the tag is configured and
        nothing owns anything afterwards.
        """
        family, size = self._base_font()
        modifiers = ' '.join(name for name, wanted in (
            ('bold', bold), ('italic', italic), ('underline', underline),
        ) if wanted)
        return (family, size, modifiers) if modifiers else (family, size)

    def _row_tag(self, task, band: str) -> str:
        """
        One tag carrying everything about how a row is painted.

        PARAMETERS:
        -----------
        task : Task
            The row being drawn.
        band : str
            'oddrow' or 'evenrow', which decides the background where the
            row carries no fill of its own.

        RETURNS:
        --------
        str
            The name of a tag configured with the row's ink, fill and font.

        DEVELOPMENT NOTES:
        ------------------
        One tag rather than several, and every visual option set on it,
        because a Treeview row carrying two tags that both set a background
        leaves which one wins up to Tk. Resolving the whole appearance here
        makes the precedence something this file states and a test can check,
        rather than something the platform decides.

        The order is: what the row is doing now beats what it was given.
        A row waiting to be pasted, or on screen only to say where a match
        sits, is greyed whatever ink it carries - those say "this row is not
        what you are looking at", which outranks decoration.

        Tags are shared by every row that resolves the same way, so a plan
        where forty rows are marked as financial milestones configures one
        tag rather than forty.
        """
        resolved = resolve_style(task.style, self.is_summary_row(task))

        if task.id in self._critical_task_ids:
            # Beats the row's own fill for the same reason the greying beats
            # its ink: it says what the row is doing now, and the reader
            # turned it on to see exactly that
            background = theme.now(self.CRITICAL_ROW_BG)
        else:
            background = resolved.fill_color or theme.now(
                self.GRID_ROW_ALT if band == 'oddrow' else self.GRID_ROW_BASE)

        if task.id in self._cut_task_ids() or self._is_search_context(task):
            foreground = theme.now(self.CUT_ROW_TEXT)
        else:
            foreground = resolved.text_color or theme.now(self.GRID_TEXT)

        name = (f"row_{background}_{foreground}"
                f"_{int(resolved.bold)}{int(resolved.italic)}"
                f"{int(resolved.underline)}").replace('#', '')

        if name not in self._row_tags:
            self.tree.tag_configure(
                name, background=background, foreground=foreground,
                font=self._row_font(resolved.bold, resolved.italic,
                                    resolved.underline))
            self._row_tags.add(name)

        return name

    def _apply_row_tag_colours(self):
        """
        Forget the row tags built for the appearance that has just changed.

        DEVELOPMENT NOTES:
        ------------------
        The banding, the greying and the formatting a row was given all
        arrive together on one tag per row - see _row_tag - so there is no
        longer a fixed set of tags here to re-colour. What there is to do is
        drop the ones already built, since every one of them names colours
        that have just stopped being right; they are rebuilt as the rows are
        drawn.

        This used to configure 'oddrow', 'evenrow', 'cut' and
        'search_context' directly, and left out, the banding stayed white on
        a dark grid and every other row glowed. Those tags are still put on
        the rows, as markers of what a row is, but they carry no colours:
        two tags both setting a background leaves Tk to decide which wins,
        which is the thing _row_tag exists to avoid.
        """
        self._row_tags.clear()

    def apply_theme(self):
        """
        Re-colour the grid for the appearance now in force.

        DEVELOPMENT NOTES:
        ------------------
        ttk resolves a style's colours when it is configured and keeps them,
        so a Treeview does not follow a theme change on its own - it has to
        be told, which is what this is for. The row tags are re-applied with
        it, because the banding and the cut-row shading are tag colours and
        those are held per row rather than on the style.

        The rows are then painted again, and that is the half that was
        missing: a row tag is named after the colours it carries, so the new
        appearance does not reconfigure the old tags - it needs new ones,
        under new names. Forgetting the old names only arranges for the new
        ones to be built the next time a row is drawn, and a theme change
        draws no rows. Every row on screen went on wearing the tag it was
        given, which is still configured in the widget and still holds the
        colours of the appearance the reader has just left - so the grid
        stayed white on a dark desktop while the heading and the empty space
        below the rows, which are the style rather than the tags, went dark
        around it.

        _paint_rows rather than update_task_list: the rows themselves have
        not changed, only their colours, and rebuilding them would throw
        away the selection and the folding for a repaint.
        """
        try:
            if not self.tree.winfo_exists():
                return
        except tk.TclError:
            return

        self._apply_grid_style()
        self._apply_row_tag_colours()
        self._paint_rows()


    def __init__(self, master, project: Project, 
                 on_task_select: Callable[[Task], None] = None,
                 on_task_edit: Callable[[Task], None] = None,
                 on_project_changed: Callable[[], None] = None,
                 project_tracker: ProjectStateTracker = None,
                 clipboard_manager=None,
                 on_status: Callable[[str], None] = None):
        super().__init__(master)
        
        self.master = master
        self.project = project
        self.on_task_select = on_task_select
        self.on_task_edit = on_task_edit
        self.on_project_changed = on_project_changed
        self.project_tracker = project_tracker
        self.clipboard_manager = clipboard_manager
        #: Where to put a line of text for the reader - the status bar, when
        #: the application supplies one. A refused paste is the reason this
        #: exists: from the keyboard it did nothing and said nothing, which
        #: reads as the shortcut being broken rather than as an answer
        self.on_status = on_status
        #: The message waiting on the idle queue, so it can be called off.
        #: See _say, and _cancel_pending_say for why it has to be.
        self._pending_say = None
        
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

        #: Called when the rows on show change or scroll; see on_rows_changed
        self._row_watchers = []

        #: The row tags configured so far. Shared by every row that
        #: resolves the same way, so a plan with forty rows marked the same
        #: way configures one tag. Cleared when the appearance changes; see
        #: _apply_row_tag_colours.
        self._row_tags = set()
        #: The grid's family and size, asked of Tk once; see _base_font.
        self._base_font_spec = None

        #: Rows painted as critical while the icon has the highlight on.
        #: Empty means the highlight is off; see show_critical_path_rows.
        self._critical_task_ids = set()

        #: The box open over a cell, and the row it belongs to. Set here so
        #: everything that asks can ask plainly; see _open_cell_editor.
        self._cell_editor = None
        self._cell_editor_task = None

        #: A rename waiting to see whether a second click is coming, and the
        #: row it would rename. See on_release and RENAME_DELAY_MS.
        self._rename_pending = None
        self._rename_row = None
        #: Whether the row pressed was already the one selected. A click on a
        #: row that was already picked out is the second of a slow pair.
        self._pressed_selected = False

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
            'ID', 'Type', 'Status', 'Duration', 'Start', 'End', 'Progress',
            'Dependencies', 'Milestone', 'Outline'
        ), show='tree headings')

        # Configure columns.
        #
        # The name lives in the tree column rather than in one of its own,
        # which is what makes the outline readable. Column #0 is the only
        # one that draws the indentation and the expander, so a name in any
        # other column sits flush left however deep the task is - the plan
        # was nested and looked flat, with the whole hierarchy expressed in
        # 34 pixels of empty space nobody could see.
        self.tree.heading('#0', text='Task Name', anchor=tk.W)
        self.tree.heading('ID', text='ID', anchor=tk.W)
        self.tree.heading('Type', text='Type', anchor=tk.W)
        self.tree.heading('Status', text='Status', anchor=tk.W)
        self.tree.heading('Duration', text='Duration (Days)', anchor=tk.W)
        self.tree.heading('Start', text='Start Date', anchor=tk.W)
        self.tree.heading('End', text='End Date', anchor=tk.W)
        self.tree.heading('Progress', text='Progress', anchor=tk.W)
        self.tree.heading('Dependencies', text='Dependencies', anchor=tk.W)
        self.tree.heading('Milestone', text='Milestone', anchor=tk.W)
        self.tree.heading('Outline', text='Outline Level', anchor=tk.W)
        
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
        # Wide, because it now holds the names as well as the indentation
        self.tree.column('#0', width=300, minwidth=120, stretch=False)
        self.tree.column('ID', width=60, minwidth=40, stretch=False)
        self.tree.column('Type', width=90, minwidth=60, stretch=False)
        self.tree.column('Status', width=64, minwidth=48, stretch=False)
        self.tree.column('Duration', width=110, minwidth=60, stretch=False)
        self.tree.column('Start', width=100, minwidth=80, stretch=False)
        self.tree.column('End', width=100, minwidth=80, stretch=False)
        self.tree.column('Progress', width=80, minwidth=60, stretch=False)
        self.tree.column('Dependencies', width=150, minwidth=80, stretch=False)
        self.tree.column('Milestone', width=80, minwidth=60, stretch=False)
        self.tree.column('Outline', width=95, minwidth=60, stretch=False)
        
        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)

        self.tree.configure(yscrollcommand=self._rows_scrolled,
                            xscrollcommand=hsb.set)
        self._vertical_scrollbar = vsb
        
        # Grid layout
        self.tree.grid(row=0, column=0, sticky=tk.NSEW)
        vsb.grid(row=0, column=1, sticky=tk.NS)
        hsb.grid(row=1, column=0, sticky=tk.EW)
        
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        # Store reference to tree_frame for DnD
        self.tree_frame = tree_frame

        self.tree.configure(style='Gantt.Treeview')

        self._apply_row_tag_colours()
        
        # Folding a branch away changes which rows are on show, which the
        # chart beside the list draws from
        self.tree.bind('<<TreeviewOpen>>', self._tell_row_watchers, add='+')
        self.tree.bind('<<TreeviewClose>>', self._tell_row_watchers, add='+')

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

    #: How long a rename waits before it opens, in milliseconds.
    #:
    #: Long enough for a second click to arrive and cancel it, so a quick
    #: double-click opens the editor rather than the name box. macOS calls a
    #: pair within about half a second a double-click, so this sits past it.
    RENAME_DELAY_MS = 600

    def on_double_click(self, event):
        """
        Open the row's editor, or the cell that has one of its own.

        DEVELOPMENT NOTES:
        ------------------
        Two clicks in quick succession open the editor window - the whole
        row at once, which is what a double-click means in a task list and
        what it means nearly everywhere else. Two clicks with a pause
        between them type over the name in place, which is the same gesture
        a file manager renames with; see on_release.

        A double-click used to open the name box, so there was no gesture
        that reached the editor at all and no way to rename in place without
        the dialog appearing instead half the time.

        Two columns keep their own cell editor. Typing "3FS+2d" over a
        Dependencies cell is not something the form does better, and the
        Type cell offers its four answers in a dropdown, which is faster
        than the form for the one field most often changed after a row is
        made. The form is one click away on any other column.

        Any rename this click has already set going is called off first: the
        first of these two clicks landed on a row that was probably already
        selected, which is exactly what starts one.

        'break' stops ttk's own double-click handler running afterwards,
        which would toggle the row underneath whatever has just been opened
        over it.
        """
        self._cancel_rename()

        item = self.tree.identify_row(event.y)
        if not item:
            return None

        cell = self._column_name(event.x)
        if cell == 'Dependencies':
            self.edit_dependencies_cell(item)
        elif cell == 'Type':
            self.edit_type_cell(item)
        else:
            self.edit_task(item)

        return 'break'

    def _cancel_rename(self):
        """Call off a rename that has not opened yet."""
        pending, self._rename_pending = self._rename_pending, None
        self._rename_row = None
        if pending is None:
            return
        try:
            self.after_cancel(pending)
        except (tk.TclError, ValueError):
            pass

    def _rename_if_still_wanted(self, item):
        """
        Open the name box, if nothing has happened since to say otherwise.

        DEVELOPMENT NOTES:
        ------------------
        Asked again here rather than trusted from when it was scheduled. The
        wait is long enough for the row to have gone, the selection to have
        moved, or a dialog to have opened over the list.
        """
        self._rename_pending = None
        self._rename_row = None

        try:
            if not self.tree.exists(item):
                return
            if self.tree.selection() != (item,):
                return
        except tk.TclError:
            return

        self.edit_name_cell(item)

    def _column_name(self, x: int):
        """
        Which column an x position falls in, by name rather than by number.

        RETURNS:
        --------
        Optional[str]
            The column's name, '#0' for the tree column, or None when the
            position is not over a column at all.

        DEVELOPMENT NOTES:
        ------------------
        identify_column answers '#4', counting the data columns from one and
        calling the tree column '#0'. A number is the wrong thing to compare
        against: adding a column shifts every one after it, and the code
        that cared would go on working and mean something else.
        """
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

        columns = self.tree.cget('columns')
        return columns[index] if 0 <= index < len(columns) else None

    def _open_cell_editor(self, task_id: str, column: str, current: str,
                          commit):
        """
        Put a typing box over one cell of one row.

        PARAMETERS:
        -----------
        task_id : str
            The row being edited.
        column : str
            Which cell to cover - a column name, or '#0' for the name.
        current : str
            What the cell holds now, selected so typing replaces it.
        commit : callable
            Called with no arguments by Enter and by the focus leaving. It
            reads the box itself; see _editor_text.

        DEVELOPMENT NOTES:
        ------------------
        An entry placed over the cell rather than a dialog opened beside it.
        The point of editing in the grid is that a column can be worked down
        without leaving it, and a window in the way defeats that as
        thoroughly as the dialog it replaces.

        The entry is a plain tkinter one. A CTkEntry is a frame holding an
        entry and draws its own border and corners, which at the height of a
        grid row leaves the text clipped and the cell it is covering showing
        round the edges.
        """
        if not self.tree.exists(task_id):
            return
        self._close_cell_editor()

        box = self._cell_box(task_id, column)
        if box is None:
            return

        x, y, width, height = box
        editor = tk.Entry(self.tree, borderwidth=1, relief='solid',
                          highlightthickness=0)
        editor.insert(0, current)
        editor.select_range(0, tk.END)
        editor.place(x=x, y=y, width=width, height=height)
        editor.focus_set()

        self._cell_editor = editor
        self._cell_editor_task = task_id

        editor.bind('<Return>', lambda _event: commit())
        editor.bind('<KP_Enter>', lambda _event: commit())
        editor.bind('<Escape>', lambda _event: self._close_cell_editor())
        editor.bind('<FocusOut>', lambda _event: commit())

    def _cell_box(self, task_id: str, column: str):
        """
        Where one cell is on screen, bringing the row into view if it is not.

        RETURNS:
        --------
        Optional[tuple]
            x, y, width and height, or None when the cell cannot be placed -
            which happens while the widget is being torn down.
        """
        for attempt in (0, 1):
            try:
                box = self.tree.bbox(task_id, column)
                if box:
                    return box
                if attempt == 0:
                    # Scrolled out of sight; bring it back and ask again
                    self.tree.see(task_id)
                    self.tree.update_idletasks()
            except tk.TclError:
                # A row that has gone, or a widget being torn down. Both
                # happen: this runs from a double-click and from a focus
                # change, and neither waits for the plan to hold still.
                return None
        return None

    def _editor_text(self):
        """
        What is in the open editor, and which row it belongs to.

        RETURNS:
        --------
        tuple
            The text and the task ID, or (None, None) when there is no
            editor open or the row has gone from under it.

        DEVELOPMENT NOTES:
        ------------------
        The editor is taken away here, before the caller stores anything.
        Storing redraws the list, which destroys the row the entry is
        sitting on - and an entry left over a row that no longer exists is a
        box floating over the wrong task.
        """
        editor = getattr(self, '_cell_editor', None)
        task_id = getattr(self, '_cell_editor_task', None)
        if editor is None or task_id is None:
            return None, None

        try:
            text = editor.get()
        except tk.TclError:
            text = None
        self._close_cell_editor()

        if text is None or self.project.get_task_by_id(task_id) is None:
            return None, None
        return text, task_id

    def edit_name_cell(self, task_id: str):
        """
        Type over a task's name in the grid.

        DEVELOPMENT NOTES:
        ------------------
        The box covers the whole of the tree column, the expander included.
        The alternative is working out where the text starts from the row's
        depth and the theme's indent, which is a number the theme is free to
        change - and a box that starts a few pixels off the text it is
        replacing looks broken in a way that covering the arrow does not.
        The arrow comes back the moment the edit ends.
        """
        task = self.project.get_task_by_id(task_id)
        if task is None:
            return
        self._open_cell_editor(task_id, '#0', task.name or '',
                               self._commit_name)

    def _commit_name(self):
        """
        Store what was typed over a task's name.

        DEVELOPMENT NOTES:
        ------------------
        An empty name puts the old one back rather than saying anything. A
        row has to be called something, and a dialog thrown up because
        somebody clicked away from a box they had cleared would be a
        reprimand for a slip - the cell simply reverts, which says the same
        thing and gets out of the way.
        """
        text, task_id = self._editor_text()
        if task_id is None:
            return

        name = text.strip()
        if not name:
            logger.debug("Empty name typed over task %s; keeping the old one",
                         task_id)
            return

        self.set_task_name(task_id, name)

    def set_task_name(self, task_id: str, name: str):
        """
        Rename a task as one undoable step, and redraw.

        PARAMETERS:
        -----------
        task_id : str
            The task being renamed.
        name : str
            What to call it.

        DEVELOPMENT NOTES:
        ------------------
        Through the tracker, so a rename typed into the grid is in the undo
        history like one typed into the editor - and so the editor, which
        reads the task, shows what the grid stored.
        """
        task = self.project.get_task_by_id(task_id)
        if task is None or task.name == name:
            return

        if self.project_tracker:
            self.project_tracker.update_task(task_id, name=name)
        else:
            task.name = name

        logger.info("Renamed task %s to %r", task_id, name)
        self.update_task_list()
        if self.on_project_changed:
            self.on_project_changed()

    # ------------------------------------------------------------------
    # The Type column
    # ------------------------------------------------------------------

    def edit_type_cell(self, task_id: str):
        """
        Choose a task's type from a dropdown over the Type cell.

        DEVELOPMENT NOTES:
        ------------------
        A list rather than a typing box, because the answer is one of four
        and typing one is a chance to misspell it. Choosing stores it: there
        is nothing to confirm about picking from a list of the only valid
        answers, and a second gesture to commit a one-click choice is a
        gesture that gets forgotten.

        Changing a type used to mean opening the editor - and for a nested
        row, not even that: the editor's menu was greyed out for anything
        with a parent. This is the fast way, and it is undoable like every
        other edit.
        """
        task = self.project.get_task_by_id(task_id)
        if task is None:
            return
        self._open_cell_chooser(
            task_id, 'Type', task.task_type, list(TASK_TYPES),
            lambda chosen: self.set_task_type(task_id, chosen))

    def set_task_type(self, task_id: str, task_type: str):
        """
        Retype a task as one undoable step, and redraw.

        PARAMETERS:
        -----------
        task_id : str
            The task being retyped.
        task_type : str
            One of TASK_TYPES.

        DEVELOPMENT NOTES:
        ------------------
        The milestone flag is written with the type, in both directions.
        The two say the same thing - Task.effective_milestone is true for
        either - so a row typed Milestone here and opened in the editor has
        to show the milestone switch on, and one typed back to a Task has to
        show it off. Setting only the type left the flag behind, and a Task
        still carrying it drew as a diamond and lost its end date.

        Through the tracker, so it is one step in the undo history and the
        editor reads what the column stored.
        """
        task = self.project.get_task_by_id(task_id)
        if task is None or task_type not in TASK_TYPES:
            return
        if task.task_type == task_type:
            return

        milestone = task_type == 'Milestone'
        if self.project_tracker:
            self.project_tracker.update_task(task_id, task_type=task_type,
                                             is_milestone=milestone)
        else:
            task.task_type = task_type
            task.is_milestone = milestone

        logger.info("Task %s is now a %s", task_id, task_type)
        self.project.reschedule()
        self.update_task_list()
        if self.on_project_changed:
            self.on_project_changed()

    def _open_cell_chooser(self, task_id: str, column: str, current: str,
                           choices, commit):
        """
        Put a dropdown over one cell, and store what is picked from it.

        PARAMETERS:
        -----------
        task_id : str
            The row being edited.
        column : str
            Which cell to cover.
        current : str
            What the cell holds now, shown as the selection.
        choices : list
            Everything the cell may be set to.
        commit : callable
            Called with the chosen value.

        DEVELOPMENT NOTES:
        ------------------
        A read-only ttk.Combobox: a plain one is an entry with a list
        attached, and typing into a cell whose only valid answers are in the
        list is a way to store an invalid one.

        It opens its own list straight away. The double-click that got here
        has already been spent asking for the choice, and a dropdown that
        then has to be clicked a third time to show what it offers reads as
        not having opened.
        """
        if not self.tree.exists(task_id):
            return
        self._close_cell_editor()

        box = self._cell_box(task_id, column)
        if box is None:
            return

        x, y, width, height = box
        chooser = ttk.Combobox(self.tree, values=list(choices),
                               state='readonly')
        chooser.set(current)
        chooser.place(x=x, y=y, width=width, height=height)
        chooser.focus_set()

        self._cell_editor = chooser
        self._cell_editor_task = task_id

        def chosen(_event=None):
            """Store the pick and take the dropdown away."""
            value = chooser.get()
            self._close_cell_editor()
            commit(value)

        chooser.bind('<<ComboboxSelected>>', chosen)
        chooser.bind('<Return>', chosen)
        chooser.bind('<KP_Enter>', chosen)
        chooser.bind('<Escape>', lambda _event: self._close_cell_editor())
        # Not <FocusOut>: opening the list moves the focus to it, so
        # committing on focus leaving would store the value and close the
        # dropdown the instant it was opened
        self.after_idle(lambda: self._drop_the_list(chooser))

    def _drop_the_list(self, chooser):
        """Open a combobox's list, if it is still there to open."""
        try:
            if chooser.winfo_exists():
                chooser.event_generate('<Button-1>')
        except tk.TclError:
            pass

    def edit_dependencies_cell(self, task_id: str):
        """
        Type into the Dependencies cell of one row.

        DEVELOPMENT NOTES:
        ------------------
        The grammar the cell takes is gantt_app.dependencysyntax's; what is
        shown is what can be typed straight back in.
        """
        task = self.project.get_task_by_id(task_id)
        if task is None:
            return
        current = format_links(task.dependencies, self.project.display_ids())
        self._open_cell_editor(task_id, 'Dependencies', current,
                               self._commit_dependencies)

    def _close_cell_editor(self):
        """Take the entry away, if one is open."""
        editor = getattr(self, '_cell_editor', None)
        self._cell_editor = None
        self._cell_editor_task = None
        if editor is None:
            return
        try:
            editor.destroy()
        except tk.TclError:
            pass

    def _commit_dependencies(self):
        """
        Read the cell, store what it said, and say what it could not.

        DEVELOPMENT NOTES:
        ------------------
        The entry is taken away first. Storing the links redraws the list,
        which destroys the row the entry is sitting on - and an entry left
        over a row that no longer exists is a box floating over the wrong
        task.

        A cell that could not be read entirely is not stored at all. Storing
        the half of it that parsed would silently drop the rest, and the
        reader would have to compare what they typed against what came back
        to notice.
        """
        text, task_id = self._editor_text()
        if task_id is None:
            return

        links, errors = self.project.parse_dependencies(task_id, text)

        if errors:
            messagebox.showerror("Dependencies", "\n\n".join(errors))
            return

        self.set_dependencies(task_id, links)

    def set_dependencies(self, task_id: str, links):
        """
        Put a task's links where the cell said, as one undoable step.

        PARAMETERS:
        -----------
        task_id : str
            The task being linked.
        links : List[Dependency]
            What it should now wait for. An empty list clears the cell.

        DEVELOPMENT NOTES:
        ------------------
        Through the tracker, so typing a cell is one entry in the undo
        history like every other change to a task.

        The plan is rescheduled afterwards rather than the dates being left
        as they were: a link that has just been stated is one the dates are
        supposed to obey, and a column that accepted a link and moved
        nothing would look like it had not worked.
        """
        task = self.project.get_task_by_id(task_id)
        if task is None:
            return

        if list(task.dependencies) == list(links):
            return

        if self.project_tracker:
            self.project_tracker.update_task(task_id, dependencies=links)
        else:
            task.dependencies = links

        self.project.apply_schedule()
        logger.info("Set %d dependency(ies) on task %s", len(links), task_id)

        self.update_task_list()
        if self.on_project_changed:
            self.on_project_changed()

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

    def on_rows_changed(self, callback):
        """
        Be told when the rows on show change, or scroll.

        PARAMETERS:
        -----------
        callback : callable
            Called with no arguments. The Gantt chart beside the list uses
            this to draw the same rows the list is drawing - folding a
            branch away takes its bars with it - and to scroll with it.
        """
        self._row_watchers.append(callback)

    def _rows_scrolled(self, first, last):
        """
        Move the scrollbar, and tell anything following the rows.

        This is the tree's yscrollcommand, so it runs whenever what is on
        show changes - a scroll, a branch folded away, a row added.
        """
        self._vertical_scrollbar.set(first, last)
        self._tell_row_watchers()

    def _tell_row_watchers(self, _event=None):
        """Let the chart know the rows have moved or changed."""
        for callback in self._row_watchers:
            try:
                callback()
            except Exception:
                logger.exception("A row watcher failed")

    def rows_scrolled_to(self) -> float:
        """
        How far down the rows the list has scrolled, from 0 to 1.

        The chart beside it scrolls to match, so the two panes show the same
        rows rather than only starting at the same one.
        """
        try:
            return float(self.tree.yview()[0])
        except (tk.TclError, ValueError, IndexError):
            return 0.0

    def visible_rows(self) -> List[str]:
        """
        The task IDs the grid is showing, top to bottom.

        RETURNS:
        --------
        List[str]
            In the order they are drawn, with the contents of folded-away
            branches left out - what the reader can actually see.

        DEVELOPMENT NOTES:
        ------------------
        This is what the Gantt chart draws its rows from, so that a bar sits
        on the line of the task it belongs to. Asking the tree rather than
        the project is the point: the project knows nothing about which
        branches are folded away, and a chart drawn from it put bars beside
        rows that were not on screen.
        """
        rows: List[str] = []

        def walk(item: str):
            """Add a row, then its children when it is open."""
            for child in self.tree.get_children(item):
                rows.append(child)
                if self.tree.item(child, 'open'):
                    walk(child)

        try:
            walk('')
        except tk.TclError:
            return []
        return rows

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
            self._say(f"Copied {self._count(selected_ids)}.")

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
            self._say(f"Cut {self._count(selected_ids)}. "
                      f"Select where they go and paste.")

    def focused_task_id(self) -> Optional[str]:
        """
        The row the cursor is on, or None when the list has no cursor.

        RETURNS:
        --------
        Optional[str]
            The focused row's task ID, falling back to the first selected
            row, and None when nothing is selected at all.

        DEVELOPMENT NOTES:
        ------------------
        Focus and selection are not the same thing in a Treeview: clicking
        sets both, but extending a selection with shift moves the focus to
        the end of the range while the first row stays selected. A paste
        goes where the cursor is, so focus is asked first.
        """
        try:
            focused = self.tree.focus()
        except tk.TclError:
            return None

        if focused and self.project.get_task_by_id(focused) is not None:
            return focused

        selected = self.get_selected_task_ids()
        return selected[0] if selected else None

    def paste_tasks(self, focused_id=FROM_CURSOR, inside: bool = False):
        """
        Paste from the clipboard at the row the cursor is on.

        PARAMETERS:
        -----------
        focused_id : str, None or FROM_CURSOR
            The row to paste at. None is no row at all - the end of the
            plan, which is what the right-click menu passes when it was
            opened over the empty space below the last row. FROM_CURSOR, the
            default, asks the list which row has the cursor, which is what
            the toolbar and the keyboard do.
        inside : bool
            True for "Paste as Sub-Task", which puts the rows underneath the
            focused row. False - every other route - puts them beside it, in
            its place, pushing it down.

        DEVELOPMENT NOTES:
        ------------------
        Every route into a paste ends up here: the keyboard, the toolbar,
        the menu bar and the right-click menu. They differ only in which row
        they name, and none of them decides any more where the rows land -
        see ClipboardService.resolve_target.

        The whole paste is one entry in the undo history. It has to be: it
        adds rows, positions them, rewrites their links and renumbers the
        plan, and a user who presses undo means all of that. Before this it
        was recorded as nothing at all, and undo reached past the paste to
        whatever the user had done before it - deleting a row they had made
        earlier and leaving the pasted one in place.
        """
        if not self.clipboard_manager:
            return

        if focused_id is FROM_CURSOR:
            focused_id = self.focused_task_id()
            if focused_id is None:
                # Nothing selected and no row pointed at: which row was
                # meant is not something to guess at
                self._say("Select the row to paste at first.")
                return

        pasted = []

        def apply() -> bool:
            """The paste itself, run inside the undo command."""
            pasted.extend(
                self.clipboard_manager.paste_at(focused_id, inside))
            return bool(pasted)

        if self.project_tracker:
            self.project_tracker.run_as_command(apply, "Paste Tasks")
        else:
            apply()

        if not pasted:
            self._say(self._why_not_pasted(focused_id, inside))
            return

        self._say(f"Pasted {self._count(pasted)}.")

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
        Whether Copy and Cut should be offered for these rows.

        PARAMETERS:
        -----------
        selected_ids : List[str]
            The rows the menu was opened over.

        RETURNS:
        --------
        bool
            True when there is something to put on the clipboard.

        DEVELOPMENT NOTES:
        ------------------
        The only one of these left. The same question was answered in three
        places - here, on ClipboardService and on ClipboardManager - and the
        two on the clipboard side were reachable from nothing but their own
        tests. Neither of them consulted the clipboard to answer it either,
        because the clipboard is not what decides: copying needs a
        selection, and the selection is this list's to report.
        """
        return len(selected_ids) > 0

    @staticmethod
    def _count(rows) -> str:
        """How many rows, said in a way that reads in a sentence."""
        total = len(rows)
        return f"{total} row" if total == 1 else f"{total} rows"

    def _say(self, message: str) -> None:
        """
        Put a line of text where the reader will see it.

        DEVELOPMENT NOTES:
        ------------------
        After the pending events rather than straight away. Selecting rows
        makes Tk queue a <<TreeviewSelect>>, and the window answers that one
        by writing what the selected task is into the same status bar - so a
        message written first was overwritten a moment later by the very
        selection the action had just made. Everything that reports on an
        action here ends by selecting its rows, so all of them were losing
        the message they had just written.
        """
        if not message:
            return
        logger.info("%s", message)
        if not self.on_status:
            return

        # Only the last one matters: they are written to the same one line,
        # so an earlier one would be overwritten before it could be read
        self._cancel_pending_say()

        try:
            self._pending_say = self.after_idle(self._now_say, message)
        except tk.TclError:
            # No event loop to wait for - say it now
            self.on_status(message)

    def _now_say(self, message: str) -> None:
        """Write the message, once the queued events have been through."""
        self._pending_say = None
        self.on_status(message)

    def _cancel_pending_say(self) -> None:
        """
        Call off a message that has not been written yet.

        DEVELOPMENT NOTES:
        ------------------
        Tk deletes a widget's callback commands when the widget is
        destroyed, but leaves anything already on the after queue pointing
        at them. Closing the window with a message still waiting therefore
        printed

            invalid command name "4386744064_now_say"
                while executing
            "4386744064_now_say" ("after" script)

        to the terminal on the way out - harmless, since Tk reports it and
        carries on, but it is an error message for something nobody did
        wrong, and it lands in whatever log the user is watching.
        """
        pending, self._pending_say = self._pending_say, None
        if pending is None:
            return
        try:
            self.after_cancel(pending)
        except (tk.TclError, ValueError):
            pass

    def destroy(self):
        """Take anything still waiting off the queue before going away."""
        self._cancel_pending_say()
        self._cancel_rename()
        super().destroy()

    def _why_not_pasted(self, focused_id: Optional[str],
                        inside: bool) -> str:
        """
        Why a paste did nothing, in a line the reader can act on.

        PARAMETERS:
        -----------
        focused_id : Optional[str]
            The row the paste was aimed at.
        inside : bool
            True for "Paste as Sub-Task".

        RETURNS:
        --------
        str
            What to tell the reader.

        DEVELOPMENT NOTES:
        ------------------
        Every one of these used to be silence. The clipboard logged its
        reason and returned an empty list, the shortcut did nothing visible,
        and the reader was left to work out whether they had copied
        anything, aimed at the wrong row, or found a bug.
        """
        if not self.clipboard_manager or self.clipboard_manager.is_empty():
            return "Nothing to paste: copy or cut some rows first."

        if focused_id is None:
            return "Those rows cannot go at the end of the plan."

        target = self.project.get_task_by_id(focused_id)
        if target is None:
            return "Select the row to paste at first."

        if inside:
            return (f"Those rows cannot go inside '{target.name}'.")

        return (f"Those rows cannot go beside '{target.name}'.")

    def can_paste(self, focused_id=FROM_CURSOR, inside: bool = False) -> bool:
        """
        Whether a paste would be accepted where it is aimed.

        PARAMETERS:
        -----------
        focused_id : str, None or FROM_CURSOR
            The row to paste at, as paste_tasks takes it: None is the end of
            the plan, FROM_CURSOR is wherever the cursor is.
        inside : bool
            True for "Paste as Sub-Task".

        RETURNS:
        --------
        bool
            True when the menu entry should be live.
        """
        if not self.clipboard_manager:
            return False
        if focused_id is FROM_CURSOR:
            focused_id = self.focused_task_id()
            if focused_id is None:
                return False
        return self.clipboard_manager.can_paste_at(focused_id, inside)


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
            self._cancel_rename()
            self._pressed_selected = False
            return

        # Asked before the click changes it: a press on a row that was
        # already the one selected is the second of a slow pair, which is
        # what renames. Asked after, every first click would look like one.
        try:
            self._pressed_selected = self.tree.selection() == (item,)
        except tk.TclError:
            self._pressed_selected = False

        self._cancel_rename()
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
        A release that never became a drag is where a rename starts, if the
        row it landed on was already the one selected - the second of two
        clicks with a pause between them, which is how a file manager is
        renamed and now how a task is. It waits RENAME_DELAY_MS first, so a
        second click arriving quickly cancels it and opens the editor window
        instead; see on_double_click.
        """
        if self.dragged_task_id is None:
            return

        if not self._dragging:
            item = self.dragged_task_id
            rename = (self._pressed_selected
                      and self._column_name(event.x) == '#0'
                      and self._cell_editor is None)
            self._end_drag()
            if rename:
                self._rename_row = item
                try:
                    self._rename_pending = self.after(
                        self.RENAME_DELAY_MS, self._rename_if_still_wanted,
                        item)
                except tk.TclError:
                    self._rename_pending = None
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

        # Not waited on; see GanttApp.edit_task for what waiting on a dialog
        # opened from the right-click menu did on macOS
        CreateTaskDialog(
            self.winfo_toplevel(), self.project,
            task_type=task_type,
            parent_task=parent,
            on_save=lambda task: self._save_created(task, anchor_id, parent_id),
            project_tracker=self.project_tracker,
        )

    def create_task_at_cursor(self):
        """
        Make a task where the cursor is, and open its editor.

        DEVELOPMENT NOTES:
        ------------------
        What the keyboard shortcut does; see Toolbar._bind_style_hotkeys.
        Creating a row was a menu or a right-click away, which for the
        commonest thing anybody does to a plan is two gestures too many -
        and the right-click needs a row to open on, so the first row of a
        plan could only be made from the menu.

        It goes beside the focused row and drops in below it, as the
        right-click Create does; with no cursor - a list nobody has clicked
        in yet - it goes at the end of the plan at the top level, which is
        where a row made without pointing at anything belongs.
        """
        self.create_task('Task', self.focused_task_id())

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
        def apply() -> bool:
            """Place the new row, then renew the numbering it changed."""
            task.parent_task_id = parent_id
            # Only set task_type to Subtask if it's not already set to a
            # specific type and has a parent
            if parent_id and task.task_type not in ("Phase", "Milestone"):
                task.task_type = "Subtask"

            self.project.add_task(task)
            anchor = self.project.get_task_by_id(anchor_id)

            if anchor is not None and task.parent_task_id == anchor.parent_task_id:
                # A sibling: slot it in directly after the row it came from
                self.project.move_task_before(task.id, anchor_id)
                self.project.move_task(task.id, 'down')

            return True

        if self.project_tracker:
            self.project_tracker.run_as_command(apply, "Create Task")
        else:
            apply()

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

    def indent_task(self, task_ids):
        """
        Make the chosen tasks sub-tasks of the row above them.

        PARAMETERS:
        -----------
        task_ids : str or Sequence[str]
            One row, or every row the menu was opened over. A bare string is
            still accepted: plenty of callers pass one row.
        """
        chosen = self._as_ids(task_ids)
        label = "Indent Tasks" if len(chosen) > 1 else "Indent Task"
        self._apply_restructure(lambda: self.project.indent_tasks(chosen),
                                chosen, label)

    def outdent_task(self, task_ids):
        """Move the chosen tasks out to sit beside their parent."""
        chosen = self._as_ids(task_ids)
        label = "Outdent Tasks" if len(chosen) > 1 else "Outdent Task"
        self._apply_restructure(lambda: self.project.outdent_tasks(chosen),
                                chosen, label)

    def link_tasks(self, task_ids):
        """
        Chain the chosen rows Finish-to-Start, down the list.

        PARAMETERS:
        -----------
        task_ids : str or Sequence[str]
            The rows to link. One row is nothing to chain.

        DEVELOPMENT NOTES:
        ------------------
        The plan is rescheduled afterwards rather than the dates being left
        as they were: a link that has just been stated is one the dates are
        supposed to obey, and a button that accepted a link and moved
        nothing would look like it had not worked. See set_dependencies,
        which does the same for a link typed into the column.

        One entry in the undo history however many pairs were joined: the
        user pressed Link once.
        """
        chosen = self._as_ids(task_ids)
        if len(chosen) < 2:
            self._say("Select two or more rows to link, "
                      "in the order they run.")
            return

        linked = []

        def apply() -> bool:
            """The links, and the dates they move, inside the undo command."""
            linked.extend(self.project.link_tasks(chosen))
            if not linked:
                return False
            # Inside, not after: the dates the link moves are part of what
            # the link did, and undo has to put those back too
            self.project.apply_schedule()
            return True

        if self.project_tracker:
            self.project_tracker.run_as_command(apply, "Link Tasks")
        else:
            apply()

        if not linked:
            self._say("Those rows are already linked.")
            return

        self._say(f"Linked {self._count(chosen)} Finish-to-Start.")
        self._after_links_changed(chosen)

    def unlink_tasks(self, task_ids):
        """
        Break the links between the chosen rows.

        PARAMETERS:
        -----------
        task_ids : str or Sequence[str]
            The rows to unlink. A single row loses every link it is part
            of; see Project.unlink_tasks.
        """
        chosen = self._as_ids(task_ids)
        if not chosen:
            self._say("Select the rows to unlink first.")
            return

        removed = []

        def apply() -> bool:
            """The removals, and the dates they move, inside the command."""
            removed.extend(self.project.unlink_tasks(chosen))
            if not removed:
                return False
            self.project.apply_schedule()
            return True

        if self.project_tracker:
            self.project_tracker.run_as_command(apply, "Unlink Tasks")
        else:
            apply()

        if not removed:
            self._say("There were no links between those rows.")
            return

        self._say(f"Removed {len(removed)} link"
                  f"{'' if len(removed) == 1 else 's'}.")
        self._after_links_changed(chosen)

    def _after_links_changed(self, chosen):
        """Redraw, keep the rows selected, and tell the rest of the window."""
        self.update_task_list()
        try:
            live = [task_id for task_id in chosen
                    if self.project.get_task_by_id(task_id) is not None]
            if live:
                self.tree.selection_set(*live)
                self.tree.focus(live[0])
                self.tree.see(live[0])
        except tk.TclError:
            pass

        if self.on_project_changed:
            self.on_project_changed()

    @staticmethod
    def _as_ids(task_ids) -> List[str]:
        """One row or several, always as a list."""
        if task_ids is None:
            return []
        if isinstance(task_ids, str):
            return [task_ids]
        return [str(task_id) for task_id in task_ids]

    def _apply_restructure(self, change, task_ids, label: str):
        """
        Run a change to the hierarchy, record it for undo and redraw.

        PARAMETERS:
        -----------
        change : callable
            Performs the change, returning True when anything moved.
        task_ids : str or Sequence[str]
            The tasks being moved, so they can be reselected afterwards.
        label : str
            What to call the change in the undo history. One entry however
            many rows moved: the user pressed Indent once, so Undo has to put
            all of it back once.

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

        logger.info("%s: %d row(s)", label, len(self._as_ids(task_ids)))

        self.update_task_list()

        self._report_dropped_links(self.project.dropped_links(before, after))

        # Every row that moved stays selected, so the group can be indented
        # again without picking it out a second time
        chosen = [task_id for task_id in self._as_ids(task_ids)
                  if self.project.get_task_by_id(task_id) is not None]
        try:
            for task_id in chosen:
                parent = self.tree.parent(task_id)
                while parent:
                    self.tree.item(parent, open=True)
                    parent = self.tree.parent(parent)
            if chosen:
                self.tree.selection_set(*chosen)
                self.tree.focus(chosen[0])
                self.tree.see(chosen[0])
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

        logger.info("Moved task %s", task_id)

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

        DEVELOPMENT NOTES:
        ------------------
        The walk itself lives on the plan now. It is a fact about the plan
        rather than about this list, and the Dependencies column needed the
        same answer - so rather than have two of it, with the two free to
        disagree, this asks.
        """
        return self.project.would_create_dependency_cycle(source_id, target_id)

    def apply_search(self, needle: str):
        """
        Show only the rows carrying a piece of text, and their ancestors.

        PARAMETERS:
        -----------
        needle : str
            What was typed. Empty puts every row back.

        RETURNS:
        --------
        Tuple[int, int]
            How many rows matched in their own right, and how many work
            items the plan holds - what the box beside the search reports.

        DEVELOPMENT NOTES:
        ------------------
        The tree is rebuilt with the filter in force rather than rows being
        detached and put back. Rebuilding reuses the one populate path that
        is already right about indentation, banding and ordering; detaching
        would need a second implementation of where a row goes, and the two
        would drift.

        The chart follows without being told: it draws from visible_rows,
        which reads the tree. Nothing here touches the project, so the
        schedule, the roll-up and the critical path are all measured on the
        whole plan whatever is on screen.
        """
        from gantt_app.views.searchbox import matching_task_ids, visible_task_ids

        self._search_visible = visible_task_ids(self.project, needle)
        self._search_matches = matching_task_ids(self.project, needle)
        self.update_task_list()
        return len(self._search_matches), len(self.project.tasks)

    def _hidden_by_search(self, task) -> bool:
        """Whether the current search leaves a row off the list."""
        visible = getattr(self, '_search_visible', None)
        if visible is None:
            return False
        return task.id not in visible

    def update_task_list(self):
        """
        Update the task list display with all task information.

        DEVELOPMENT NOTES:
        ------------------
        Displays tasks in a hierarchical structure where subtasks are indented
        under their parent tasks.

        Every row is destroyed and rebuilt, so what the reader had done to
        the list has to be carried across it - which row was selected, which
        branches were folded away, and where the list was scrolled to.
        Without that, every action that changed anything at all threw the
        selection away: pressing Bold cleared it, and the formatting bar,
        which is only live while something is selected, greyed itself out.
        The row had to be clicked again between every single change.
        
        Folding had the same fault from the other side. Every rebuilt row is
        inserted open, so a branch folded away sprang back open on the next
        change anywhere in the plan.
        """
        state = self._capture_view_state()

        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)

        self._populate_tree_hierarchical()
        self._paint_rows()
        self._restore_view_state(state)

        # The rows are all new, so anything drawing from them - the Gantt
        # chart beside the list - is told once they are all in place. The
        # tree's own scroll callback fires part way through the rebuild,
        # when the answer to what is on show is still half of it.
        self._tell_row_watchers()

    def _capture_view_state(self) -> dict:
        """
        What the reader has done to the list, before it is torn down.

        RETURNS:
        --------
        dict
            The selected rows, the focused one, which branches are folded,
            and where the list is scrolled to. Empty when the tree cannot be
            read, which happens while the widget is being destroyed.
        """
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
        """
        Put the reader's selection, folds and scroll position back.

        DEVELOPMENT NOTES:
        ------------------
        Rows that are gone are skipped rather than restored: a selection
        that included a deleted task would otherwise raise, and the caller
        of this is every refresh in the application.

        The folds go back before the selection, so a selected row inside a
        branch that is folded again is still selected - it is simply not on
        screen, which is what folding means. The scroll position is restored
        last for the same reason: reselecting can scroll the list, and where
        the reader had it is the answer that should win.
        """
        if not state:
            return

        try:
            for item in state.get('closed', ()):
                if self.tree.exists(item):
                    self.tree.item(item, open=False)

            alive = [item for item in state.get('selection', ())
                     if self.tree.exists(item)]
            if alive:
                self.tree.selection_set(*alive)

            focused = state.get('focus')
            if focused and self.tree.exists(focused):
                self.tree.focus(focused)

            scroll = state.get('scroll')
            if scroll is not None:
                self.tree.yview_moveto(scroll)
        except tk.TclError:
            logger.debug("Could not restore the task list view state")
    
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
        # The number beside each row, worked out once for the whole plan
        # rather than per row: display_ids walks the hierarchy, and asking it
        # per row would walk it once per row. See Project.display_ids.
        self._display_ids = self.project.display_ids()

        # Map task IDs to tree items for parent-child relationships
        tree_items = {}

        # First pass: add all root tasks
        for task in self.project.get_root_tasks():
            if self._hidden_by_search(task):
                continue
            item_id = self._add_task_to_tree(task, indent_level=0)
            tree_items[task.id] = item_id

        # Further passes: add subtasks once their parent is in the tree.
        # Imported files (notably GanttProject) can nest tasks several levels
        # deep, so keep sweeping until a pass places nothing new - a single
        # pass would silently drop anything below the second level.
        remaining = [t for t in self.project.tasks
                     if t.parent_task_id and not self._hidden_by_search(t)]

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
                # Orphaned subtasks (parent missing or a cycle) - show at
                # root. A search reaches here too: a match whose parent is
                # filtered out has nowhere to hang, and the alternative to
                # showing it at the top is not showing the match at all.
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
        # Predecessors in the grammar the cell itself takes back - '001',
        # '003SS+1d' - so what is shown is what can be typed. By the numbers
        # shown beside them rather than by name: the number is what the
        # reader is looking at in the ID column, and it follows a reorder
        # without anything being rewritten. See dependencysyntax.format_links.
        numbers = getattr(self, '_display_ids', None) or self.project.display_ids()
        deps_str = format_links(task.dependencies, numbers) or 'None'
        
        # Format dates
        start_str = task.start_date.strftime('%Y-%m-%d')
        end_str = task.end_date.strftime('%Y-%m-%d') if task.end_date else 'N/A'
        
        # Format milestone indicator
        milestone_str = 'Yes' if task.is_milestone else 'No'
        
        # Format duration
        #
        # A row with children answers 0 from duration_days: it holds no
        # work of its own, only the work beneath it. Printing that 0 beside a
        # row whose two dates are a fortnight apart said the phase took
        # no time, which is the one thing it does not mean. The working days
        # it spans is what the row is showing dates for, so that is the
        # number in the column.
        #
        # It is a span, not a total. Children that overlap - two sub-tasks
        # linked Start-Start run together - span less than their efforts add
        # up to, and that is the point of a summary bracketing them.
        if task.is_container:
            duration = self.project.working_duration(task)
        else:
            duration = task.duration_days
        duration_str = str(duration) if duration is not None else 'N/A'
        
        # Format task type
        type_str = task.task_type
        
        # Format status - D for Draft, A for Active
        status_str = 'D' if task.status == 'Draft' else 'A'
        
        # The name goes in column #0, which is the one that draws the
        # indentation and the expander beside it
        item_id = self.tree.insert(parent_item, tk.END,
                                 iid=task.id,
                                 text=task.name,
                                 open=True,
                                 values=(
                                     # What the row shows is its position,
                                     # not its identity; see display_ids
                                     self._display_label(task),
                                     type_str,
                                     status_str,
                                     duration_str,
                                     start_str,
                                     end_str,
                                     f"{task.progress}%",
                                     deps_str,
                                     milestone_str,
                                     str(self.project.outline_level(task.id)),
                                 ))
        
        # What the row is. How it is painted is decided afterwards, once
        # every row is in place and the order they are drawn in is known -
        # see _paint_rows.
        tags = []
        if task.task_type == 'Subtask':
            tags.append('subtask')
        if task.id in self._cut_task_ids():
            tags.append('cut')
        if self._is_search_context(task):
            # On screen to say where a match sits, not because it is one
            tags.append('search_context')
        self.tree.item(item_id, tags=tuple(tags))

        return item_id

    def _display_label(self, task) -> str:
        """
        The number shown in the ID column, zero-padded as the list writes it.

        DEVELOPMENT NOTES:
        ------------------
        The identity is never shown, whatever happens. It is a key, not a
        number a reader has any use for, and one appearing in the column
        where every other row shows its position would be read as a
        position - so a row drawn outside a repopulation asks the plan
        rather than falling back to task.id.
        """
        numbers = getattr(self, '_display_ids', None) or self.project.display_ids()
        number = numbers.get(task.id)
        return '' if number is None else str(number).zfill(self.project.ID_WIDTH)

    def _paint_rows(self):
        """
        Give every row its banding and its formatting, in the order shown.

        DEVELOPMENT NOTES:
        ------------------
        A second pass, and it has to be. The banding alternates over the
        rows as they are drawn, and the rows are not inserted in that order:
        the roots go in first and their children follow in later passes, so
        a plan of a phase, its one task and a second root had the phase and
        the nested task both counted even - two touching rows in the same
        shade, with the banding restarting underneath them.

        Walking the tree afterwards asks the widget what the order actually
        is, which is the only thing that knows.
        """
        for index, item in enumerate(self._rows_in_display_order()):
            task = self.project.get_task_by_id(item)
            if task is None:
                continue
            band = 'oddrow' if index % 2 else 'evenrow'
            markers = [tag for tag in self.tree.item(item, 'tags')
                       if not tag.startswith('row_')]
            self.tree.item(item, tags=tuple(
                markers + [band, self._row_tag(task, band)]))

    # ------------------------------------------------------------------
    # The critical path, painted onto the list
    # ------------------------------------------------------------------

    def show_critical_path_rows(self, task_ids) -> int:
        """
        Paint the given rows as critical, and clear any painted before.

        PARAMETERS:
        -----------
        task_ids : Iterable[str]
            The tasks with no float. An empty one turns the highlight off,
            which is what clear_critical_path_rows does.

        RETURNS:
        --------
        int
            How many rows are painted now.

        DEVELOPMENT NOTES:
        ------------------
        Held as ids rather than as rows, so the highlight survives the list
        being rebuilt - which every edit does. The rows are looked up again
        each time they are painted; see _row_tag.

        The tags built for the old answer name colours that have stopped
        being right, so they go the same way a theme change sends them.
        """
        self._critical_task_ids = set(task_ids)
        self._apply_row_tag_colours()
        self._paint_rows()
        return len(self._critical_task_ids)

    def clear_critical_path_rows(self):
        """Take the highlight off, leaving every row as it was drawn."""
        self.show_critical_path_rows(())

    def critical_path_rows_shown(self) -> bool:
        """Whether the highlight is on."""
        return bool(self._critical_task_ids)

    def _rows_in_display_order(self):
        """Every row in the tree, parents before their children."""
        def walk(parent):
            """One level, then everything under it."""
            for item in self.tree.get_children(parent):
                yield item
                yield from walk(item)

        return list(walk(''))
    
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
