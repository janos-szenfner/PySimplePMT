"""
The Dependency tab shared by the task creation and editing dialogs.

WHY THIS MODULE EXISTS:
======================
Dependencies used to be a column of checkboxes: one row per candidate task,
with nothing to say how the link behaves. A link carries a type, a lag and a
hardness, so it needs a grid with a row per dependency and a control per
setting, and both dialogs need exactly the same thing.

DEVELOPMENT NOTES:
------------------
The editor owns a working copy of the links and hands it back on request, so
a cancelled dialog leaves the task untouched.

It carries no explanatory text of its own. What was here could only afford a
line or two per setting while taking room the grid wanted, and still had
nowhere to say what lead time is or when Finish - Finish is the right choice.
The Help button opens help/dependencyhelp.py instead, which has the space to
explain all of it properly.

Choosing a predecessor also moves the dependent task. The dialog asks this
widget for the resulting start date rather than computing it itself; the rule
lives in Project.constrained_dates, so the same logic serves the UI, the
importers and the scheduler.
"""

import tkinter as tk
from tkinter import ttk
# See gantt_app/views/dialogs.py: native on macOS and Windows, drawn
# to match the application on X11
from gantt_app.views import dialogs as messagebox
from typing import Callable, List, Optional

import customtkinter as ctk

from gantt_app.models import (
    Dependency, Project, Task,
    DEPENDENCY_TYPES, DEPENDENCY_TYPE_LABELS, DEPENDENCY_HARDNESS,
)
# Imported at module scope rather than inside show_help: a module reached
# only from a button is exactly what goes missing from a frozen build
# without anyone noticing until someone clicks it
from gantt_app.help.dependencyhelp import DependencyHelpWindow
from gantt_app import theme
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


#: Reverse lookup from the label shown in the UI to the stored code.
TYPE_CODE_BY_LABEL = {label: code for code, label in DEPENDENCY_TYPE_LABELS.items()}


class DependencyEditor(ctk.CTkFrame):
    """
    A grid of dependency links with per-row Type and Link Hardness.

    PARAMETERS:
    -----------
    master : widget
        Parent widget, normally a tab.
    project : Project
        Used to list candidate predecessors and resolve their names.
    task : Task
        The task being edited. Used to exclude itself and its descendants.
    on_changed : Optional[Callable]
        Called after any change, so the dialog can refresh the start date.
    """

    COLUMNS = ('task', 'type', 'lag', 'hardness')

    def __init__(self, master, project: Project, task: Task,
                 on_changed: Optional[Callable] = None):
        super().__init__(master)

        self.project = project
        self.task = task
        self.on_changed = on_changed

        # Work on a copy so cancelling the dialog changes nothing
        self.links: List[Dependency] = [
            Dependency(d.task_id, d.dep_type, d.hardness, d.lag)
            for d in task.dependencies
        ]

        self._build_ui()
        # Do not notify on the initial draw: the dialog is still being
        # constructed, so the attribute holding this editor is not assigned
        # yet, and opening a dialog must not reschedule the task by itself.
        self.refresh(notify=False)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        """
        Lay out the add row, the grid and the help text.

        DEVELOPMENT NOTES:
        ------------------
        The add controls are stacked over two rows rather than strung along
        one. On a single row the fixed widths came to roughly 700px inside a
        500px dialog, so the Add button sat outside the window and there was
        no way to add a dependency at all until the dialog was dragged wider.

        Only the predecessor menu is given weight; the rest keep their natural
        size, so narrowing the dialog shrinks the long control rather than
        pushing the button off the edge.
        """
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        add_row = ctk.CTkFrame(self)
        add_row.grid(row=0, column=0, sticky=tk.EW, padx=5, pady=(5, 8))
        add_row.grid_columnconfigure(1, weight=1)

        # First row: the predecessor, which needs the most room
        ctk.CTkLabel(add_row, text="Task:").grid(
            row=0, column=0, sticky=tk.W, padx=(8, 4), pady=(8, 4))
        self.candidate_var = ctk.StringVar()
        self.candidate_menu = ctk.CTkOptionMenu(
            add_row, variable=self.candidate_var, values=["(none available)"]
        )
        self.candidate_menu.grid(row=0, column=1, columnspan=5, sticky=tk.EW,
                                 padx=(4, 8), pady=(8, 4))

        # Second row: the link settings and the button
        ctk.CTkLabel(add_row, text="Type:").grid(
            row=1, column=0, sticky=tk.W, padx=(8, 4), pady=(4, 8))
        self.type_var = ctk.StringVar(value=DEPENDENCY_TYPE_LABELS['FS'])
        ctk.CTkOptionMenu(
            add_row, variable=self.type_var,
            values=list(DEPENDENCY_TYPE_LABELS.values()), width=150
        ).grid(row=1, column=1, sticky=tk.W, padx=4, pady=(4, 8))

        ctk.CTkLabel(add_row, text="Lag:").grid(
            row=1, column=2, sticky=tk.W, padx=(12, 4), pady=(4, 8))
        self.lag_var = ctk.StringVar(value='0')
        ctk.CTkEntry(add_row, textvariable=self.lag_var, width=56).grid(
            row=1, column=3, sticky=tk.W, padx=4, pady=(4, 8))

        # Said on the form rather than left to be discovered. A plan whose
        # tasks follow calendars of their own gives "2" three different
        # meanings unless it is spelt out which week counts it.
        ctk.CTkLabel(add_row, text="project working days",
                     text_color=theme.MUTED_TEXT).grid(
            row=1, column=4, columnspan=2, sticky=tk.W, padx=(4, 8),
            pady=(4, 8))

        ctk.CTkLabel(add_row, text="Hardness:").grid(
            row=2, column=0, sticky=tk.W, padx=(8, 4), pady=(0, 8))
        self.hardness_var = ctk.StringVar(value='Hard')
        ctk.CTkOptionMenu(
            add_row, variable=self.hardness_var,
            values=list(DEPENDENCY_HARDNESS), width=90
        ).grid(row=2, column=1, sticky=tk.W, padx=4, pady=(0, 8))

        ctk.CTkButton(add_row, text="Add", width=70,
                      command=self.add_selected).grid(
            row=2, column=5, sticky=tk.E, padx=(12, 8), pady=(0, 8))

        # The grid of existing links
        table_frame = ctk.CTkFrame(self)
        table_frame.grid(row=1, column=0, sticky=tk.NSEW, padx=5, pady=5)
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(table_frame, columns=self.COLUMNS,
                                 show='headings', selectmode='browse',
                                 style='Gantt.Treeview')
        self.tree.heading('task', text='Depends on', anchor=tk.W)
        self.tree.heading('type', text='Type', anchor=tk.W)
        self.tree.heading('lag', text='Lag', anchor=tk.W)
        self.tree.heading('hardness', text='Link Hardness', anchor=tk.W)
        self.tree.column('task', width=260, stretch=True)
        self.tree.column('type', width=130, stretch=False)
        self.tree.column('lag', width=60, stretch=False)
        self.tree.column('hardness', width=120, stretch=False)

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL,
                                  command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=0, column=0, sticky=tk.NSEW)
        scrollbar.grid(row=0, column=1, sticky=tk.NS)

        self.tree.bind('<Double-1>', lambda _e: self.edit_selected())

        # Row actions. Help sits with them rather than as a block of text
        # under the grid: the explanation needs far more room than a couple
        # of lines could give it, and it was taking space the grid wanted
        actions = ctk.CTkFrame(self)
        actions.grid(row=2, column=0, sticky=tk.EW, padx=5, pady=(0, 5))
        ctk.CTkButton(actions, text="Change Type", width=120,
                      command=self.cycle_type).pack(side=tk.LEFT, padx=5, pady=6)
        ctk.CTkButton(actions, text="Change Hardness", width=150,
                      command=self.cycle_hardness).pack(side=tk.LEFT, padx=5, pady=6)
        ctk.CTkButton(actions, text="Remove", width=90,
                      command=self.remove_selected).pack(side=tk.RIGHT, padx=5, pady=6)
        ctk.CTkButton(actions, text="Help", width=70,
                      command=self.show_help).pack(side=tk.RIGHT, padx=5, pady=6)

    def show_help(self):
        """Open the dependency reference."""
        logger.info("Opening the dependency help window")
        DependencyHelpWindow.show(self.winfo_toplevel())

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def candidate_tasks(self) -> List[Task]:
        """
        Get the tasks that may be chosen as a predecessor.

        RETURNS:
        --------
        List[Task]
            Every task except this one, its descendants, and any already
            linked - a task cannot depend on itself or on its own sub-tasks.
        """
        taken = {link.task_id for link in self.links}
        candidates = []
        for other in self.project.tasks:
            if other.id == self.task.id or other.id in taken:
                continue
            if self.project.is_descendant(other.id, self.task.id):
                continue
            candidates.append(other)
        return sorted(candidates, key=lambda t: t.start_date)

    def _label_for(self, task: Task) -> str:
        """
        Format a task for the chooser.

        The number the list shows it as, not its identity: the reader is
        picking a row they can see, and the two stopped being the same thing
        when the number became a position - see Project.display_ids.
        """
        return f"{self.project.display_id(task.id)} - {task.name}"

    def refresh(self, notify: bool = True):
        """
        Redraw the grid and the list of candidates.

        PARAMETERS:
        -----------
        notify : bool
            Whether to tell the dialog the links changed. False during
            construction, when there is nothing to react to yet and the
            dialog is not finished building.
        """
        for item in self.tree.get_children():
            self.tree.delete(item)

        for index, link in enumerate(self.links):
            predecessor = self.project.get_task_by_id(link.task_id)
            name = self._label_for(predecessor) if predecessor else link.task_id
            self.tree.insert(
                '', tk.END, iid=str(index),
                values=(name, link.type_label, link.lag, link.hardness),
                tags=('oddrow' if index % 2 else 'evenrow',)
            )

        # The style comes from the task list's 'Gantt.Treeview', which
        # follows the theme; the banding is a tag colour and does not, so it
        # is resolved here every time the rows are rebuilt.
        self.tree.tag_configure('oddrow', background=theme.now(theme.GRID_ROW_ALT))
        self.tree.tag_configure('evenrow', background=theme.now(theme.GRID_ROW_BG))

        candidates = self.candidate_tasks()
        if candidates:
            values = [self._label_for(t) for t in candidates]
            self.candidate_menu.configure(values=values, state=tk.NORMAL)
            if self.candidate_var.get() not in values:
                self.candidate_var.set(values[0])
        else:
            self.candidate_menu.configure(values=["(none available)"],
                                          state=tk.DISABLED)
            self.candidate_var.set("(none available)")

        if notify and self.on_changed:
            self.on_changed()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def add_selected(self):
        """Add a link to the task chosen in the add row."""
        label = self.candidate_var.get()
        match = next((t for t in self.candidate_tasks()
                      if self._label_for(t) == label), None)
        if match is None:
            messagebox.showinfo("No Task Selected",
                                "Choose a task to depend on first.",
                                parent=self.winfo_toplevel())
            return

        dep_type = TYPE_CODE_BY_LABEL.get(self.type_var.get(), 'FS')
        self.links.append(Dependency(match.id, dep_type,
                                     self.hardness_var.get(), self._lag()))
        logger.info("Added dependency on %s (%s, %s, lag %s) to task %s",
                    match.id, dep_type, self.hardness_var.get(),
                    self._lag(), self.task.id)
        self.refresh()

    def _lag(self) -> int:
        """
        Read the lag box, treating anything unparseable as no lag.

        A half-typed '-' or an empty box should not stop a link being added,
        so it falls back to zero rather than refusing.
        """
        try:
            return int(str(self.lag_var.get()).strip() or 0)
        except (TypeError, ValueError):
            return 0

    def _selected_index(self) -> Optional[int]:
        """Get the index of the highlighted row."""
        selection = self.tree.selection()
        if not selection:
            return None
        try:
            return int(selection[0])
        except ValueError:
            return None

    def remove_selected(self):
        """Remove the highlighted link."""
        index = self._selected_index()
        if index is None:
            return
        removed = self.links.pop(index)
        logger.info("Removed dependency on %s from task %s",
                    removed.task_id, self.task.id)
        self.refresh()

    def cycle_type(self):
        """Step the highlighted link on to the next type, wrapping round."""
        index = self._selected_index()
        if index is None:
            return
        link = self.links[index]
        position = DEPENDENCY_TYPES.index(link.dep_type)
        link.dep_type = DEPENDENCY_TYPES[(position + 1) % len(DEPENDENCY_TYPES)]
        self.refresh()
        self.tree.selection_set(str(index))

    def cycle_hardness(self):
        """Switch the highlighted link between Hard and Rubber."""
        index = self._selected_index()
        if index is None:
            return
        link = self.links[index]
        link.hardness = 'Rubber' if link.hardness == 'Hard' else 'Hard'
        self.refresh()
        self.tree.selection_set(str(index))

    def edit_selected(self):
        """Double-click cycles the type, the setting people change most."""
        self.cycle_type()

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------

    def get_links(self) -> List[Dependency]:
        """Get the edited links, for the dialog to store on the task."""
        return [Dependency(d.task_id, d.dep_type, d.hardness, d.lag)
                for d in self.links]

    def required_start_date(self, start_date):
        """
        Get the start date the current links imply.

        PARAMETERS:
        -----------
        start_date : datetime
            The task's start date as currently entered in the General tab.

        RETURNS:
        --------
        Optional[datetime]
            The date the task should start, or None when nothing constrains
            it. Lets the dialog fill in the start date as soon as a
            dependency is chosen.
        """
        probe = Task(
            id=self.task.id, name=self.task.name or 'probe',
            start_date=start_date,
            end_date=self.task.end_date,
            is_milestone=self.task.is_milestone,
        )
        probe.dependencies = self.get_links()
        return self.project.constrained_start_date(probe)
