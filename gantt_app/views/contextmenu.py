"""
Right-click context menu for the task list.

WHY THIS MODULE EXISTS:
======================
The task list is already a large widget, and the context menu is a
self-contained concern: it decides what a right-click offers, works out
whether each entry applies to the row that was clicked, and calls back into
the list to carry the choice out. Keeping it here lets the menu grow new
entries without the task list growing with it.

DEVELOPMENT NOTES:
------------------
Which button opens a context menu differs by platform. X11 and Windows use
the right button, which Tk reports as Button-3. On macOS the right button -
and a two-finger click on a trackpad - arrives as Button-2, and Control with
the left button is the long-standing convention there as well. Binding
Button-2 everywhere would fire the menu on a middle-click paste under X11,
so the bindings are chosen from the windowing system rather than applied
blindly.
"""

import tkinter as tk

from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


#: The move entries, as (label, Project.move_task target).
MOVE_ACTIONS = (
    ("Move to top", 'top'),
    ("Move up", 'up'),
    ("Move down", 'down'),
    ("Move to bottom", 'bottom'),
)

#: The hierarchy entries, as (label, DragDropTaskList method name).
LEVEL_ACTIONS = (
    ("Indent", 'indent'),
    ("Outdent", 'outdent'),
)

#: What the Create submenu offers, as the task_type each entry builds.
CREATE_TYPES = ("Phase", "Deliverable", "Task", "Subtask", "Milestone")

#: Entries following the moves, after a separator.
TASK_ACTIONS = ("Edit", "Delete")


class TaskContextMenu:
    """
    A right-click menu offering the move actions for a task row.

    PARAMETERS:
    -----------
    tree : ttk.Treeview
        The task list's tree. Its item IDs are task IDs.
    project_getter : callable
        Returns the current Project. A callable rather than the project
        itself, because opening a file replaces the project object while
        this menu goes on living.
    on_move : callable
        Called with (task_id, target) when a move is chosen, where target is
        one of 'top', 'up', 'down' or 'bottom'.
    on_indent : callable, optional
        Called with the task ID when Indent is chosen. Omitted, the entry is
        greyed out.
    on_outdent : callable, optional
        Called with the task ID when Outdent is chosen. Omitted, the entry is
        greyed out.
    on_edit : callable, optional
        Called with the task ID when Edit is chosen. Omitted, the entry is
        greyed out.
    on_delete : callable, optional
        Called with the task ID when Delete is chosen. Omitted, the entry is
        greyed out.
    on_copy : callable, optional
        Called with selected task IDs when Copy is chosen. Omitted, the entry is
        greyed out.
    on_cut : callable, optional
        Called with selected task IDs when Cut is chosen. Omitted, the entry is
        greyed out.
    on_paste : callable, optional
        Called with (target container ID, clicked row ID) when Paste is
        chosen. Omitted, the entry is greyed out.
    can_copy_or_cut : callable, optional
        Returns True if copy/cut operations are possible. Used to enable/disable menu items.
    can_paste : callable, optional
        Returns True if paste operation is possible. Used to enable/disable menu items.

    DEVELOPMENT NOTES:
    ------------------
    The menu is rebuilt on every click rather than built once and reused, so
    entries that cannot apply to the clicked row - moving the top row up, for
    instance - are shown greyed out rather than silently doing nothing.
    """

    def __init__(self, tree, project_getter, on_move,
                 on_indent=None, on_outdent=None,
                 on_edit=None, on_delete=None,
                 on_create=None, on_undo=None, on_redo=None,
                 can_undo=None, can_redo=None,
                 on_copy=None, on_cut=None, on_paste=None,
                 can_copy_or_cut=None, can_paste=None):
        self.tree = tree
        self._project_getter = project_getter
        self._on_move = on_move
        self._on_indent = on_indent
        self._on_outdent = on_outdent
        self._on_edit = on_edit
        self._on_delete = on_delete
        self._on_create = on_create
        self._on_undo = on_undo
        self._on_redo = on_redo
        self._can_undo = can_undo
        self._can_redo = can_redo
        self._on_copy = on_copy
        self._on_cut = on_cut
        self._on_paste = on_paste
        self._can_copy_or_cut = can_copy_or_cut
        self._can_paste = can_paste
        self._menu = None
        self._windowing = 'x11'

        self._bind()

    def _bind(self):
        """Bind the platform's context-menu gesture to the tree."""
        try:
            windowing = self.tree.tk.call('tk', 'windowingsystem')
        except tk.TclError:
            windowing = 'x11'

        self._windowing = windowing

        if windowing == 'aqua':
            # macOS: the right button and a two-finger trackpad click both
            # arrive as Button-2; Control with the left button is the older
            # convention and still widely used.
            sequences = ('<Button-2>', '<Control-Button-1>')
        else:
            sequences = ('<Button-3>',)

        for sequence in sequences:
            self.tree.bind(sequence, self.show, add='+')

    def _task_id_at(self, event):
        """The task ID of the row under the pointer, or None."""
        row = self.tree.identify_row(event.y)
        return row or None

    def show(self, event):
        """
        Open the menu, over a row or over the empty space below the rows.

        DEVELOPMENT NOTES:
        ------------------
        The clicked row is selected first, unless it is already one of
        several that are. Right-clicking a row that is not the selected one
        would otherwise act on whatever happened to be selected already,
        which is a reliable way to move the wrong task - while collapsing the
        selection onto the clicked row regardless meant Copy and Cut could
        never see more than one, however many the user had picked out.

        Clicking below the last row opens the menu with no row behind it.
        That used to do nothing at all, which left the empty space - the
        obvious place to right-click to add a task to a plan - inert.
        Everything that needs a task is greyed out there; Create, Undo and
        Redo do not, and Create builds at the end of the plan.
        """
        project = self._project_getter()
        if project is None:
            return None

        task_id = self._task_id_at(event)
        if task_id is not None and project.get_task_by_id(task_id) is None:
            # A row for a task that has since gone
            task_id = None

        if task_id is not None:
            if task_id not in self.tree.selection():
                self.tree.selection_set(task_id)
            self.tree.focus(task_id)
        else:
            self.tree.selection_remove(*self.tree.selection())

        self._close()
        self._menu = self._build(project, task_id)

        # Clicking away, or pressing Escape, takes the menu down. Losing
        # focus is what a click elsewhere produces, and unposting on it is
        # what makes the menu dismissable without choosing something.
        self._menu.bind('<FocusOut>', lambda _e: self._unpost(), add='+')
        self._menu.bind('<Escape>', lambda _e: self._unpost(), add='+')

        try:
            self._menu.tk_popup(event.x_root, event.y_root)
        finally:
            # Only X11 and Windows need the grab dropped by hand. On macOS
            # the menu is a native one that manages its own grab, and
            # releasing it here took away the grab it uses to notice a click
            # outside itself - so the menu stayed on screen until an entry
            # was chosen, which is exactly what it must not do.
            if self._windowing != 'aqua':
                self._menu.grab_release()

        return 'break'

    def _unpost(self):
        """Take the menu down without running anything."""
        if self._menu is None:
            return
        try:
            self._menu.unpost()
        except tk.TclError:
            pass

    def _build(self, project, task_id):
        """
        Build the menu for one task, or for the empty space below the rows.

        PARAMETERS:
        -----------
        project : Project
            The project the rows belong to.
        task_id : Optional[str]
            The row the menu was opened on, or None for the empty space.

        RETURNS:
        --------
        tk.Menu
            A menu whose entries are disabled where the action would not do
            anything, so the row's position is readable from the menu itself.

        DEVELOPMENT NOTES:
        ------------------
        Edit and Delete come last, separated from the moves. Rearranging is
        harmless and repeatable while deleting is neither, so the destructive
        entry sits at the far end of the menu rather than next to something a
        user clicks repeatedly.

        With no row behind it every entry that needs a task is greyed out.
        Create, Undo and Redo are not: adding a task is the obvious reason to
        right-click empty space, and it builds at the end of the plan.
        """
        menu = tk.Menu(self.tree, tearoff=0)
        has_task = task_id is not None

        if has_task:
            siblings = project.get_siblings(task_id)
            position = next(
                (i for i, task in enumerate(siblings) if task.id == task_id),
                None,
            )
            last = len(siblings) - 1
            can_move_up = position is not None and position > 0
            can_move_down = position is not None and position < last
        else:
            can_move_up = can_move_down = False

        allowed = {
            'top': can_move_up,
            'up': can_move_up,
            'down': can_move_down,
            'bottom': can_move_down,
        }

        for label, target in MOVE_ACTIONS:
            menu.add_command(
                label=label,
                state=tk.NORMAL if allowed[target] else tk.DISABLED,
                command=lambda t=target: self._invoke_move(task_id, t),
            )

        menu.add_separator()

        # Indent needs a row above to go under, and outdent needs a parent to
        # come out of, so both are greyed out where they would do nothing
        level_allowed = {
            'indent': has_task and self._on_indent is not None
            and project.can_indent(task_id),
            'outdent': has_task and self._on_outdent is not None
            and project.can_outdent(task_id),
        }
        for label, action in LEVEL_ACTIONS:
            menu.add_command(
                label=label,
                state=tk.NORMAL if level_allowed[action] else tk.DISABLED,
                command=lambda a=action: self._invoke_level(task_id, a),
            )

        menu.add_separator()

        create = tk.Menu(menu, tearoff=0)
        for task_type in CREATE_TYPES:
            # A sub-task needs a row to go under; the rest do not, and over
            # empty space they are added at the end of the plan.
            #
            # The type is spelt as the model spells it. Against the old
            # hyphenated "Sub-Task" this test was true of every entry, so
            # Subtask was offered over empty space with no parent to hang it
            # on.
            can_create = self._on_create is not None and (
                has_task or task_type != "Subtask"
            )
            create.add_command(
                label=task_type,
                state=tk.NORMAL if can_create else tk.DISABLED,
                command=lambda t=task_type: self._after_menu(
                    self._invoke_create, task_id, t),
            )
        menu.add_cascade(label="Create", menu=create)
        # Held on the menu: a submenu that only the local name refers to is
        # collected once this method returns, and the entry stops working
        menu._create_submenu = create

        menu.add_command(
            label="Edit",
            state=tk.NORMAL if (has_task and self._on_edit) else tk.DISABLED,
            command=lambda: self._after_menu(self._invoke_edit, task_id),
        )
        menu.add_command(
            label="Delete",
            state=tk.NORMAL if (has_task and self._on_delete) else tk.DISABLED,
            command=lambda: self._after_menu(self._invoke_delete, task_id),
        )

        menu.add_separator()

        # Add Copy, Cut, Paste menu items
        # Get selected IDs from the tree
        selected_ids = self.tree.selection()
        can_copy_cut = (self._can_copy_or_cut and self._can_copy_or_cut(selected_ids)) if has_task else False
        
        menu.add_command(
            label="Copy",
            state=tk.NORMAL if (can_copy_cut and self._on_copy) else tk.DISABLED,
            command=lambda: self._invoke_copy(selected_ids),
        )
        menu.add_command(
            label="Cut",
            state=tk.NORMAL if (can_copy_cut and self._on_cut) else tk.DISABLED,
            command=lambda: self._invoke_cut(selected_ids),
        )
        
        # For paste, check if we can paste into the clicked task (as container) or root
        target_container_id = task_id if (has_task and self._can_accept_paste(task_id)) else None
        can_paste = (self._can_paste and self._can_paste(target_container_id)) if self._can_paste else False
        
        menu.add_command(
            label="Paste",
            state=tk.NORMAL if (can_paste and self._on_paste) else tk.DISABLED,
            command=lambda: self._invoke_paste(target_container_id, task_id),
        )

        menu.add_separator()

        menu.add_command(
            label="Undo",
            state=tk.NORMAL if (self._can_undo and self._can_undo())
            else tk.DISABLED,
            command=self._invoke_undo,
        )
        menu.add_command(
            label="Redo",
            state=tk.NORMAL if (self._can_redo and self._can_redo())
            else tk.DISABLED,
            command=self._invoke_redo,
        )

        return menu

    def _after_menu(self, action, *args):
        """
        Run a menu action once the menu itself has gone.

        PARAMETERS:
        -----------
        action : Callable
            The handler to run.
        *args
            What to hand it.

        DEVELOPMENT NOTES:
        ------------------
        A menu entry's command runs inside the menu's own event loop, and on
        macOS that loop belongs to the system: tk_popup does not return until
        the native menu has finished tracking. Anything that opens a window
        from in there - the create form, the edit form, the delete prompt -
        builds it underneath a menu that is still up, and it does not come
        forward until the loop unwinds. What the user sees is a first click
        that appears to do nothing and a second one that works.

        Scheduling on the idle queue puts the window after the menu rather
        than inside it. Only the entries that open one are deferred; a move or
        an indent changes the tree and can happen where it stands.

        Callers that have no event loop to schedule on - a torn-down window -
        fall through and run it directly, since not doing the thing at all is
        worse than doing it a moment early.
        """
        try:
            self.tree.after_idle(action, *args)
        except tk.TclError:
            logger.debug("No event loop to defer %s on; running it now",
                         getattr(action, '__name__', action))
            action(*args)

    def _invoke_move(self, task_id, target):
        """Run a chosen move, reporting a failure rather than swallowing it."""
        logger.info("Context menu: move task %s to %s", task_id, target)
        try:
            self._on_move(task_id, target)
        except Exception:
            logger.exception("Could not move task %s to %s", task_id, target)

    def _invoke_level(self, task_id, action):
        """Indent or outdent the clicked task."""
        handler = (self._on_indent if action == 'indent'
                   else self._on_outdent)
        if not handler:
            return
        logger.info("Context menu: %s task %s", action, task_id)
        try:
            handler(task_id)
        except Exception:
            logger.exception("Could not %s task %s", action, task_id)

    def _invoke_create(self, task_id, task_type):
        """Create a new task of the chosen type at the clicked row."""
        if not self._on_create:
            return
        logger.info("Context menu: create a %s at %s", task_type, task_id)
        try:
            self._on_create(task_type, task_id)
        except Exception:
            logger.exception("Could not create a %s at %s", task_type, task_id)

    def _invoke_undo(self):
        """Undo the last change."""
        if not self._on_undo:
            return
        try:
            self._on_undo()
        except Exception:
            logger.exception("Could not undo")

    def _invoke_redo(self):
        """Redo the last undone change."""
        if not self._on_redo:
            return
        try:
            self._on_redo()
        except Exception:
            logger.exception("Could not redo")

    def _invoke_edit(self, task_id):
        """Open the edit window for the clicked task."""
        if not self._on_edit:
            return
        logger.info("Context menu: edit task %s", task_id)
        try:
            self._on_edit(task_id)
        except Exception:
            logger.exception("Could not edit task %s", task_id)

    def _invoke_delete(self, task_id):
        """Delete the clicked task."""
        if not self._on_delete:
            return
        logger.info("Context menu: delete task %s", task_id)
        try:
            self._on_delete(task_id)
        except Exception:
            logger.exception("Could not delete task %s", task_id)

    def _invoke_copy(self, selected_ids):
        """Copy selected tasks to clipboard."""
        if not self._on_copy:
            return
        logger.info("Context menu: copy tasks %s", selected_ids)
        try:
            self._on_copy(selected_ids)
        except Exception:
            logger.exception("Could not copy tasks %s", selected_ids)

    def _invoke_cut(self, selected_ids):
        """Cut selected tasks to clipboard."""
        if not self._on_cut:
            return
        logger.info("Context menu: cut tasks %s", selected_ids)
        try:
            self._on_cut(selected_ids)
        except Exception:
            logger.exception("Could not cut tasks %s", selected_ids)

    def _invoke_paste(self, target_container_id, anchor_id=None):
        """
        Paste from the clipboard into the target container.

        PARAMETERS:
        -----------
        target_container_id : Optional[str]
            The row the pasted items go under, or None for the top level.
        anchor_id : Optional[str]
            The row the menu was opened over. Rows that land beside it are
            placed after it rather than at the end of the branch, which is
            what Create already does from this menu.
        """
        if not self._on_paste:
            return
        logger.info("Context menu: paste to container %s, after %s",
                    target_container_id, anchor_id)
        try:
            self._on_paste(target_container_id, anchor_id)
        except Exception:
            logger.exception("Could not paste to container %s", target_container_id)

    def _can_accept_paste(self, task_id: str) -> bool:
        """
        Check if a task can accept pasted items (i.e., it's a container type).
        
        PARAMETERS:
        -----------
        task_id : str
            The task ID to check
            
        RETURNS:
        --------
        bool
            True if the task can have children (and thus accept paste)
        """
        project = self._project_getter()
        if not project or not task_id:
            return False
        task = project.get_task_by_id(task_id)
        if not task:
            return False
        return task.can_have_children

    def _close(self):
        """Tear down the previous menu, if one is still around."""
        if self._menu is None:
            return
        try:
            self._menu.destroy()
        except tk.TclError:
            pass
        self._menu = None
