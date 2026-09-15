"""
The task form's Deliverables tab: which deliverables this task feeds.

WHY THIS MODULE EXISTS:
======================
A task can count toward several deliverables and a deliverable collects
several tasks - the link is many-to-many and is stored on the deliverable
side (Deliverable.task_ids). This tab is the task's view of it: every
deliverable in the plan, as one indented checklist, with a tick wherever
this task is a member. Ticking writes nothing itself - the dialog's Save
reads selected_ids() and applies the set through
Project.set_task_deliverables, which is also where the undo entry is made.

A deliverable's progress counts its assigned tasks into the roll-up, so
what is ticked here moves the percentage the Deliverables tab shows.

DEVELOPMENT NOTES:
------------------
The list is a ScrollFrame of plain checkboxes rather than a Treeview: the
gesture wanted is tick/untick, not row selection, and a checkbox says so
directly. Indentation is drawn with padding, the way the deliverables
board's outline reads.
"""

import tkinter as tk
from typing import Optional, Set

import customtkinter as ctk

from gantt_app.core.models import Project
from gantt_app.views.scrollframe import ScrollFrame
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


class TaskDeliverablesTab(ctk.CTkFrame):
    """
    The checklist of deliverables a task can be assigned to.

    PARAMETERS:
    -----------
    parent : widget
        The tab page this fills.
    project : Project
        The plan, whose deliverables are listed.
    task_id : str, optional
        The task being edited - its current memberships arrive pre-ticked.
        A task being created has no id yet and starts with nothing ticked.
    """

    #: Pixels of indent per outline level, so a sub-deliverable reads as
    #: sitting under its parent the way it does on the board.
    INDENT_PX = 22

    def __init__(self, parent, project: Project,
                 task_id: Optional[str] = None) -> None:
        super().__init__(parent, fg_color='transparent')
        self.project = project
        self._vars = {}

        ctk.CTkLabel(
            self, text='DELIVERABLES THIS TASK FEEDS',
            font=('Arial', 12, 'bold'), anchor=tk.W,
        ).pack(fill=tk.X, padx=10, pady=(10, 4))

        member_of = {d.id for d in project.deliverables_for_task(task_id)} \
            if task_id else set()

        deliverables = project.deliverable_display_order()
        if not deliverables:
            ctk.CTkLabel(
                self,
                text='No deliverables yet - add them on the '
                     'Deliverables tab.',
                anchor=tk.W, justify=tk.LEFT,
            ).pack(fill=tk.X, padx=10, pady=10)
            return

        scroller = ScrollFrame(self)
        scroller.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        numbers = project.deliverable_display_ids()
        for deliverable in deliverables:
            depth = max(0, project.deliverable_outline_level(
                deliverable.id) - 1)
            var = tk.BooleanVar(value=deliverable.id in member_of)
            self._vars[deliverable.id] = var
            number = str(numbers.get(deliverable.id, '')).zfill(
                project.ID_WIDTH)
            ctk.CTkCheckBox(
                scroller.content,
                text=f"{number}  {deliverable.name or '(unnamed)'}",
                variable=var,
            ).pack(fill=tk.X, padx=(10 + depth * self.INDENT_PX, 8),
                   pady=2)

        if member_of:
            logger.debug("Task %s is a member of %d deliverable(s)",
                         task_id, len(member_of))

    def selected_ids(self) -> Set[str]:
        """The deliverable ids ticked on the form."""
        return {deliverable_id for deliverable_id, var in self._vars.items()
                if var.get()}
