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
                 on_edit=None, on_delete=None):
        self.tree = tree
        self._project_getter = project_getter
        self._on_move = on_move
        self._on_edit = on_edit
        self._on_delete = on_delete
        self._menu = None

        self._bind()

    def _bind(self):
        """Bind the platform's context-menu gesture to the tree."""
        try:
            windowing = self.tree.tk.call('tk', 'windowingsystem')
        except tk.TclError:
            windowing = 'x11'

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

        try:
            self._menu.tk_popup(event.x_root, event.y_root)
        finally:
            # Without this the pointer stays grabbed by the menu on X11 and
            # the rest of the window stops responding to clicks
            self._menu.grab_release()

        return 'break'

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

        return menu

    def _invoke_move(self, task_id, target):
        """Run a chosen move, reporting a failure rather than swallowing it."""
        logger.info("Context menu: move task %s to %s", task_id, target)
        try:
            self._on_move(task_id, target)
        except Exception:
            logger.exception("Could not move task %s to %s", task_id, target)

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
