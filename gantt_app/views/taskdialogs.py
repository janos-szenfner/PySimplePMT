"""
The two dialogs that show the task form: creating a task and editing one.

WHY THIS MODULE EXISTS:
======================
Both are the same form - TaskFormDialog in taskform.py - differing in what
they seed the fields from and what they do with them afterwards. One writes
back onto a task that already exists and can delete it; the other builds a
new one, works out where in the plan it belongs, and can be left open to
enter the next.

DEVELOPMENT NOTES:
------------------
Subclasses set their seed attributes and then call _create_form() and
center_window() themselves, rather than the base calling them. A Tk widget is
only half-built until its own __init__ has run, so a base class that built
the form would be reading attributes the subclass had not set yet.
"""

import tkinter as tk
from datetime import datetime, timedelta
from typing import Optional, Callable
import copy

import customtkinter as ctk

from gantt_app.models import Task, Project
from gantt_app.utils.undoredo import ProjectStateTracker
from gantt_app.views.taskform import TaskFormDialog
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


class EditTaskDialog(TaskFormDialog):
    """Dialog for editing an existing task."""

    GEOMETRY = "620x640"

    def __init__(self, master, task: Task, project: Project,
                 on_save: Callable[[Task], None], on_delete: Callable[[str], None],
                 project_tracker: ProjectStateTracker = None,
                 on_new: Callable[[], None] = None):
        self.task = task
        self.on_delete = on_delete
        # Called by Save & New once the edit is saved; without it that
        # button just saves and closes
        self.on_new = on_new

        super().__init__(master, project, f"Edit Task: {task.name}",
                         on_save=on_save, project_tracker=project_tracker)

        self._create_form()
        self.center_window()

    # ---- what the fields start on -------------------------------------

    def form_template(self):
        """The task itself: the form opens on its current values."""
        return self.task

    def seed_name(self):
        """Its current name."""
        return self.task.name

    def seed_type_locked(self):
        """A sub-task cannot change type without changing parent."""
        return bool(self.task.parent_task_id)

    # ---- the two rows only an existing task has -----------------------

    def _build_identity(self, frame):
        """Show the task's ID, which is assigned and not editable."""
        self.id_label = ctk.CTkLabel(frame, text=self.task.id)
        self._field(frame, "ID:", self.id_label, sticky=tk.W)

    def _build_parent(self, frame):
        """Name the parent, when there is one."""
        parent = self.seed_parent()
        name = parent.name if parent else "Unknown"
        if self.task.task_type == "Sub-Task" and self.task.parent_task_id:
            self.parent_label = ctk.CTkLabel(frame, text=name)
            self._field(frame, "Parent Task:", self.parent_label,
                        sticky=tk.W)

    def _build_leading_buttons(self, frame):
        """Delete and Help, set apart on the left."""
        super()._build_leading_buttons(frame)
        ctk.CTkButton(frame, text="Delete", width=self.DELETE_WIDTH,
                      fg_color="#e74c3c", hover_color="#c0392b",
                      command=self.delete).pack(side=tk.LEFT, padx=5)

    # ---- saving --------------------------------------------------------

    def _apply(self) -> bool:
        """
        Write the form back onto the task.

        DEVELOPMENT NOTES:
        ------------------
        The whole form is read before any of it is written. A rejected date
        used to leave behind whatever had already been assigned above it, so
        a task whose save was refused for its end date had its name and type
        changed anyway - and the dialog stayed open saying nothing had been
        saved.
        """
        try:
            name = self.name_entry.get().strip()
            if not name:
                raise ValueError("Enter a name for the task.")

            start = self._typed_date(self.start_date_entry, "start date")
            if start is None:
                raise ValueError("Enter a start date.")

            is_milestone = self.is_milestone_var.get()
            end = (None if is_milestone
                   else self._typed_date(self.end_date_entry, "end date"))
            if end is not None and end < start:
                raise ValueError("The end date falls before the start date.")

            # Get duration value
            duration_text = self.duration_entry.get().strip()
            duration = int(duration_text) if duration_text else None

            # Get progress value
            progress_text = self.progress_entry.get().strip()
            progress = int(progress_text) if progress_text else 0
            if progress < 0 or progress > 100:
                raise ValueError("Progress must be between 0 and 100")

            # Get earliest begin date
            earliest_begin = None
            if self.earliest_begin_var.get():
                earliest_begin = self._typed_date(self.earliest_begin_entry, "earliest begin date")

            # Get details
            details = self.details_text.get("1.0", tk.END).strip()

            old_task = copy.copy(self.task)

            self.task.name = name
            # A sub-task cannot change its type or parent from here
            if not self.task.parent_task_id:
                self.task.task_type = self.task_type_var.get()
            self.task.start_date = start
            self.task.end_date = end
            self.task.is_milestone = is_milestone
            self.task.progress = progress
            self.task.duration = duration
            self.task.priority = self.priority_var.get()
            self.task.shape = self.shape_var.get()
            self.task.show_in_timeline = self.show_in_timeline_var.get()
            self.task.earliest_begin = earliest_begin
            self.task.scheduling_options = self.scheduling_options_var.get()
            self.task.details = details
            self.task.color = self.color_palette.get()
            if self._dependency_editor is not None:
                # Untouched tab means untouched links
                self.task.dependencies = self._dependency_editor.get_links()

            if self.project_tracker:
                new_task = copy.copy(self.task)
                if self.project_tracker.update_task(
                    old_task.id,
                    name=new_task.name,
                    task_type=new_task.task_type,
                    start_date=new_task.start_date,
                    end_date=new_task.end_date,
                    progress=new_task.progress,
                    dependencies=new_task.dependencies,
                    color=new_task.color,
                    is_milestone=new_task.is_milestone,
                    parent_task_id=new_task.parent_task_id,
                    duration=new_task.duration,
                    priority=new_task.priority,
                    shape=new_task.shape,
                    show_in_timeline=new_task.show_in_timeline,
                    earliest_begin=new_task.earliest_begin,
                    scheduling_options=new_task.scheduling_options,
                    details=new_task.details,
                ):
                    if self.on_save:
                        self.on_save(new_task)
                    return True

            if self.on_save:
                self.on_save(self.task)
            return True

        except ValueError as error:
            self._report_invalid(error)
            return False

    def _start_another(self):
        """
        Close, then ask for a fresh form.

        DEVELOPMENT NOTES:
        ------------------
        Opened by whoever opened this dialog, through on_new, rather than
        built here. Adding a task means placing it in the plan and recording
        it for undo, which is the task list's job; this dialog only knows how
        to edit the one task it was given.
        """
        self.destroy()
        if self.on_new:
            self.on_new()

    def delete(self):
        """Delete the task, with undo support."""
        if self.project_tracker:
            if self.project_tracker.remove_task(self.task.id):
                if self.on_delete:
                    self.on_delete(self.task.id)
        elif self.on_delete:
            self.on_delete(self.task.id)
        self.destroy()


class CreateTaskDialog(TaskFormDialog):
    """Dialog for creating a task, sub-task or milestone."""

    GEOMETRY = "620x720"

    #: How long a new task runs by default, in days.
    DEFAULT_LENGTH = 7
    SUBTASK_LENGTH = 1

    def __init__(self, master, project: Project,
                 task_type: str = "Task", parent_task: Task = None,
                 on_save: Callable[[Task], None] = None,
                 project_tracker: ProjectStateTracker = None):
        self.task_type = task_type
        self.parent_task = parent_task
        self.is_milestone = (task_type == "Milestone")

        titles = {
            'Milestone': "Create New Milestone",
            'Sub-Task': "Create New Sub-Task",
        }
        super().__init__(master, project,
                         titles.get(task_type, "Create New Task"),
                         on_save=on_save, project_tracker=project_tracker)

        self._create_form()
        self.center_window()

    # ---- what the fields start on -------------------------------------

    def form_template(self):
        """
        A stand-in carrying the defaults for what is being created.

        DEVELOPMENT NOTES:
        ------------------
        It also serves as the Dependency tab's subject. A task being created
        has no ID yet, and that tab needs something with a parent link to
        leave invalid candidates out of the list; this is that object, so the
        defaults on the form and the ones the tab reasons about cannot drift
        apart.

        A sub-task starts with its parent and runs a day; anything else
        starts today and runs a week.
        """
        if self.parent_task and not self.is_milestone:
            start = self.parent_task.start_date
            end = start + timedelta(days=self.SUBTASK_LENGTH)
        else:
            start = datetime.now()
            end = start + timedelta(days=self.DEFAULT_LENGTH)

        return Task(
            id='__new__',
            name=self.task_type,
            start_date=start,
            end_date=None if self.is_milestone else end,
            color=self.DEFAULT_COLORS.get(self.task_type,
                                          self.DEFAULT_COLORS['Task']),
            is_milestone=self.is_milestone,
            task_type="Task" if self.is_milestone else self.task_type,
            parent_task_id=self.parent_task.id if self.parent_task else None,
        )

    def seed_type_locked(self):
        """A parent chosen up front fixes the type."""
        return bool(self.parent_task)

    def seed_has_end(self):
        """A milestone has no end date at all."""
        return not self.is_milestone

    # ---- choosing a parent when none was given ------------------------

    def _build_type(self, frame):
        """The type menu, which a milestone does not offer."""
        self.task_type_var = ctk.StringVar(value=self.template.task_type)
        if self.is_milestone:
            return
        self.task_type_menu = ctk.CTkOptionMenu(
            frame, variable=self.task_type_var, values=["Task", "Sub-Task"],
            state=tk.DISABLED if self.seed_type_locked() else tk.NORMAL,
        )
        self._field(frame, "Type:", self.task_type_menu)

    def _build_parent(self, frame):
        """Name the parent, or offer the tasks that could be one."""
        if self.parent_task:
            super()._build_parent(frame)
            return

        if self.task_type != "Sub-Task":
            return

        names = [t.name for t in self.project.get_root_tasks()]
        if names:
            self.parent_var = ctk.StringVar()
            self.parent_menu = ctk.CTkOptionMenu(
                frame, variable=self.parent_var, values=names)
            self._field(frame, "Parent Task:", self.parent_menu)
        else:
            self.parent_label = ctk.CTkLabel(
                frame, text="No parent tasks available")
            self._field(frame, "Parent Task:", self.parent_label, sticky=tk.W)

    def _resolve_parent_id(self) -> Optional[str]:
        """The ID of the parent to hang the new task off, if any."""
        if self.parent_task:
            return self.parent_task.id

        chosen = getattr(self, 'parent_var', None)
        name = chosen.get() if chosen else ''
        if not name:
            return None

        match = self.project.get_task_by_id(name)
        if match:
            return match.id
        return next((t.id for t in self.project.tasks if t.name == name), None)

    # ---- saving --------------------------------------------------------

    def _apply(self) -> bool:
        """Build the task from the form and hand it to the save callback."""
        try:
            name = self.name_entry.get().strip()
            if not name:
                raise ValueError("Enter a name for the task.")

            start = self._typed_date(self.start_date_entry, "start date")
            if start is None:
                raise ValueError("Enter a start date.")

            is_milestone = self.is_milestone_var.get()
            end = (None if is_milestone
                   else self._typed_date(self.end_date_entry, "end date"))
            if end is not None and end < start:
                raise ValueError("The end date falls before the start date.")

            parent_task_id = self._resolve_parent_id()
            if is_milestone:
                task_type = "Task"
            else:
                task_type = self.task_type_var.get()
            if parent_task_id:
                task_type = "Sub-Task"

            # Get duration value
            duration_text = self.duration_entry.get().strip()
            duration = int(duration_text) if duration_text else None

            # Get progress value
            progress_text = self.progress_entry.get().strip()
            progress = int(progress_text) if progress_text else 0
            if progress < 0 or progress > 100:
                raise ValueError("Progress must be between 0 and 100")

            # Get earliest begin date
            earliest_begin = None
            if self.earliest_begin_var.get():
                earliest_begin = self._typed_date(self.earliest_begin_entry, "earliest begin date")

            # Get details
            details = self.details_text.get("1.0", tk.END).strip()

            task = Task(
                id=self.project.next_task_id(),
                name=name,
                start_date=start,
                end_date=end,
                progress=progress,
                dependencies=(self._dependency_editor.get_links()
                              if self._dependency_editor else []),
                color=self.color_palette.get(),
                is_milestone=is_milestone,
                task_type=task_type,
                parent_task_id=parent_task_id,
                duration=duration,
                priority=self.priority_var.get(),
                shape=self.shape_var.get(),
                show_in_timeline=self.show_in_timeline_var.get(),
                earliest_begin=earliest_begin,
                scheduling_options=self.scheduling_options_var.get(),
                details=details,
            )
            task.__post_init__()

            if self.on_save:
                self.on_save(task)
            return True

        except ValueError as error:
            self._report_invalid(error)
            return False

    def _start_another(self):
        """
        Clear the form for the next task, keeping the window open.

        DEVELOPMENT NOTES:
        ------------------
        Entering a run of tasks is the point of the button, and a window that
        blinks away and back loses its position and the field the user was
        about to type in.

        The dates are kept: a run of tasks almost always sits in the same part
        of the plan, so carrying them over saves setting them again. The name
        is what changes every time, and it takes the focus.
        """
        self._reset_form()

    def _reset_form(self):
        """
        Empty the form ready for the next task.

        The name goes back to being one the user has not typed in yet, so the
        emptied box is not outlined in red for the task they are about to
        name.
        """
        self.name_entry.delete(0, tk.END)
        self.progress_entry.delete(0, tk.END)
        self.progress_entry.insert(0, "0")
        self.duration_entry.delete(0, tk.END)
        self.details_text.delete("1.0", tk.END)
        self._touched.discard('name')
        self._check_fields()

        if self._dependency_editor is not None:
            self._dependency_editor.links = []
            self._dependency_editor.refresh(notify=False)

        try:
            self.name_entry.focus_set()
        except tk.TclError:
            pass
