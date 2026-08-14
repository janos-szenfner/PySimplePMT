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
CREATE_TYPES = ("Task", "Sub-Task", "Milestone")

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
                 can_undo=None, can_redo=None):
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
        Open the menu over the row that was clicked.

        DEVELOPMENT NOTES:
        ------------------
        The clicked row is selected first. Right-clicking a row that is not
        the selected one would otherwise act on whatever happened to be
        selected already, which is a reliable way to move the wrong task.
        """
        task_id = self._task_id_at(event)
        if task_id is None:
            return None

        project = self._project_getter()
        if project is None or project.get_task_by_id(task_id) is None:
            return None

        self.tree.selection_set(task_id)
        self.tree.focus(task_id)

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
        Build the menu for one task.

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
        """
        menu = tk.Menu(self.tree, tearoff=0)

        siblings = project.get_siblings(task_id)
        position = next(
            (i for i, task in enumerate(siblings) if task.id == task_id), None
        )
        last = len(siblings) - 1

        can_move_up = position is not None and position > 0
        can_move_down = position is not None and position < last

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
            'indent': self._on_indent is not None
            and project.can_indent(task_id),
            'outdent': self._on_outdent is not None
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
            create.add_command(
                label=task_type,
                state=tk.NORMAL if self._on_create else tk.DISABLED,
                command=lambda t=task_type: self._invoke_create(task_id, t),
            )
        menu.add_cascade(label="Create", menu=create)
        # Held on the menu: a submenu that only the local name refers to is
        # collected once this method returns, and the entry stops working
        menu._create_submenu = create

        menu.add_command(
            label="Edit",
            state=tk.NORMAL if self._on_edit else tk.DISABLED,
            command=lambda: self._invoke_edit(task_id),
        )
        menu.add_command(
            label="Delete",
            state=tk.NORMAL if self._on_delete else tk.DISABLED,
            command=lambda: self._invoke_delete(task_id),
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

    def _close(self):
        """Tear down the previous menu, if one is still around."""
        if self._menu is None:
            return
        try:
            self._menu.destroy()
        except tk.TclError:
            pass
        self._menu = None
