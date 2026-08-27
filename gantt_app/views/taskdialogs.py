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
from datetime import datetime
from typing import Optional, Callable
import copy

import customtkinter as ctk

from gantt_app.models import Task, Project, TASK_TYPES, child_type_for
from gantt_app.utils.undoredo import ProjectStateTracker
from gantt_app.views.taskform import TaskFormDialog
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


class EditTaskDialog(TaskFormDialog):
    """
    Dialog for editing an existing task.

    It opens at TaskFormDialog's size. Both dialogs used to narrow it, from
    when the form was one column; a 620-wide window then squeezed the tab
    strip, and it holds three tabs now.
    """

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
        """
        Never. The type is the user's to set, wherever the row sits.

        A row with a parent used to have the menu greyed out, on the
        grounds that a sub-task could not be anything else without being
        moved first. That made the type a property of the tree rather than
        of the row, and left a nested row with no way to say what it was:
        the editor refused, and indenting - the other way it could change -
        only ever went the wrong way.
        """
        return False

    # ---- the two rows only an existing task has -----------------------

    def _build_identity(self, frame):
        """
        Show the task's number, which is assigned and not editable.

        DEVELOPMENT NOTES:
        ------------------
        The number the list shows, not Task.id. The two used to be the same
        thing; they are not any more, and the identity is a key rather than
        something a reader has any use for - see Project.display_ids. Showing
        it here would put a number in front of somebody that matches nothing
        in the ID column they were just looking at.
        """
        self.id_label = ctk.CTkLabel(frame,
                                     text=self.project.display_id(self.task.id))
        self._field(frame, "ID:", self.id_label, sticky=tk.W,
                    where=self.RIGHT)

    def _build_parent(self, frame):
        """Name the parent, when there is one."""
        parent = self.seed_parent()
        name = parent.name if parent else "Unknown"
        if self.task.task_type == "Subtask" and self.task.parent_task_id:
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

            is_milestone = self.is_milestone_var.get()
            start, end, duration = self._read_schedule()
            progress = self._typed_progress()

            earliest_begin = None
            if self.earliest_begin_var.get():
                earliest_begin = self._typed_date(self.earliest_begin_entry,
                                                  "earliest begin date")

            details = self.details_text.get("1.0", tk.END).strip()

            old_task = copy.copy(self.task)

            self.task.name = name
            # Whatever the menu says, wherever the row sits; see
            # seed_type_locked
            self.task.task_type = self.task_type_var.get()
            self.task.start_date = start
            self.task.end_date = end
            self.task.is_milestone = is_milestone
            self.task.progress = progress
            # A row with children takes its length from the work inside
            # it, so nothing is written here for one. The form derives the
            # number from the two dates even where its own rules have greyed
            # the box out, and storing that froze a container at whatever its
            # children happened to span on the day it was last edited.
            if not self.task.is_container:
                self.task.duration = duration
            self.task.priority = self.priority_var.get()
            self.task.shape = self.shape_var.get()
            self.task.show_in_timeline = self.show_in_timeline_var.get()
            self.task.earliest_begin = earliest_begin
            self.task.scheduling_options = self.scheduling_options_var.get()
            self.task.calendar_id = self.chosen_calendar_id()
            self.task.details = details
            self.task.color = self.color_entry.get()
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
                    calendar_id=new_task.calendar_id,
                    details=new_task.details,
                ):
                    logger.info("Edited task %s %r", new_task.id,
                                new_task.name)
                    if self.on_save:
                        self.on_save(new_task)
                    return True

            logger.info("Edited task %s %r", self.task.id, self.task.name)
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
            'Subtask': "Create New Subtask",
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
        starts today and runs seven days.

        The lengths are working days and go through the project's calendar, so
        a form opened on a Friday offers a task ending the following Thursday
        rather than one two days of which fall over the weekend. A start on a
        weekend is moved to the Monday for the same reason.
        """
        calendar = self.project.calendar

        if self.parent_task and not self.is_milestone:
            start = calendar.get_next_working_day(self.parent_task.start_date)
            end = calendar.add_working_days(start, self.SUBTASK_LENGTH)
        else:
            start = calendar.get_next_working_day(datetime.now())
            end = calendar.add_working_days(start, self.DEFAULT_LENGTH)

        return Task(
            id='__new__',
            name=self.task_type,
            start_date=start,
            end_date=None if self.is_milestone else end,
            color=self.DEFAULT_COLORS.get(self.task_type,
                                          self.DEFAULT_COLORS['Task']),
            is_milestone=self.is_milestone,
            task_type=self.task_type,
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
            frame, variable=self.task_type_var, values=list(TASK_TYPES),
            state=tk.DISABLED if self.seed_type_locked() else tk.NORMAL,
        )
        self._field(frame, "Type:", self.task_type_menu, where=self.LEFT)

    def _build_parent(self, frame):
        """Name the parent, or offer the tasks that could be one."""
        if self.parent_task:
            super()._build_parent(frame)
            return

        if self.task_type != "Subtask":
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

            is_milestone = self.is_milestone_var.get()
            start, end, duration = self._read_schedule()
            progress = self._typed_progress()

            parent_task_id = self._resolve_parent_id()
            task_type = "Milestone" if is_milestone else self.task_type_var.get()
            if parent_task_id:
                # The level the chosen parent can hold, which is the task's
                # own type wherever the parent can hold it - a Task created
                # under a Phase stays a Task. Creating and indenting
                # settle this the same way; see models.child_type_for.
                parent = self.project.get_task_by_id(parent_task_id)
                stand_in = Task(id='__type__', name=task_type,
                                start_date=start, task_type=task_type)
                task_type = child_type_for(parent, stand_in)

            earliest_begin = None
            if self.earliest_begin_var.get():
                earliest_begin = self._typed_date(self.earliest_begin_entry,
                                                  "earliest begin date")

            details = self.details_text.get("1.0", tk.END).strip()

            task = Task(
                id=self.project.next_task_id(),
                name=name,
                start_date=start,
                end_date=end,
                progress=progress,
                dependencies=(self._dependency_editor.get_links()
                              if self._dependency_editor else []),
                color=self.color_entry.get(),
                is_milestone=is_milestone,
                task_type=task_type,
                parent_task_id=parent_task_id,
                duration=duration,
                priority=self.priority_var.get(),
                shape=self.shape_var.get(),
                show_in_timeline=self.show_in_timeline_var.get(),
                earliest_begin=earliest_begin,
                scheduling_options=self.scheduling_options_var.get(),
                calendar_id=self.chosen_calendar_id(),
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
