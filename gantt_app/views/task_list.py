"""
Task list view for the Gantt Project Management Tool.

Rows are reordered by dragging them, or through the right-click menu in
contextmenu.py.

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
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
from typing import Optional, Callable, List, Dict, Any
import copy

import customtkinter as ctk

from gantt_app.models import Task, Project
from gantt_app.utils.undoredo import ProjectStateTracker
from gantt_app.views.modal import grab_when_visible
from gantt_app.views.contextmenu import TaskContextMenu
from gantt_app.views.dependency_editor import DependencyEditor
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


class EditTaskDialog(ctk.CTkToplevel):
    """
    Dialog for editing task properties.
    """
    
    def __init__(self, master, task: Task, project: Project, 
                 on_save: Callable[[Task], None], on_delete: Callable[[str], None],
                 project_tracker: ProjectStateTracker = None):
        super().__init__(master)
        
        self.task = task
        self.project = project
        self.on_save = on_save
        self.on_delete = on_delete
        self.project_tracker = project_tracker
        
        self.title(f"Edit Task: {task.name}")
        self.geometry("620x640")
        # The Dependency tab needs this much to keep its Add button on screen
        self.minsize(560, 480)
        self.transient(master)
        # Deferred: grabbing before the window is mapped fails on X11
        grab_when_visible(self)
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        
        # Create form
        self._create_form()
        
        # Center window
        self.center_window()
    
    def _create_form(self):
        """
        Create the edit form widgets.

        DEVELOPMENT NOTES:
        ------------------
        The form is split across a General tab and a Dependency tab. Links
        now carry a type and a hardness, which needs a grid rather than the
        single column of checkboxes the fields used to share space with.
        """
        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(fill=tk.BOTH, expand=True, padx=15, pady=(15, 5))
        self.tabs.add("General")
        self.tabs.add("Dependency")

        # Main frame
        main_frame = ctk.CTkScrollableFrame(self.tabs.tab("General"))
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Configure grid columns
        main_frame.columnconfigure(1, weight=1)
        
        # Name
        ctk.CTkLabel(main_frame, text="Task Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_entry = ctk.CTkEntry(main_frame)
        self.name_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)
        self.name_entry.insert(0, self.task.name)
        
        # ID
        ctk.CTkLabel(main_frame, text="ID:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.id_label = ctk.CTkLabel(main_frame, text=self.task.id)
        self.id_label.grid(row=1, column=1, sticky=tk.W, pady=5)
        
        # Task Type
        ctk.CTkLabel(main_frame, text="Type:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.task_type_var = ctk.StringVar(value=self.task.task_type)
        self.task_type_menu = ctk.CTkOptionMenu(
            main_frame, variable=self.task_type_var,
            values=["Task", "Sub-Task"], state=tk.DISABLED if self.task.parent_task_id else tk.NORMAL
        )
        self.task_type_menu.grid(row=2, column=1, sticky=tk.EW, pady=5)
        
        # Parent Task (for subtasks)
        if self.task.task_type == "Sub-Task" and self.task.parent_task_id:
            ctk.CTkLabel(main_frame, text="Parent Task:").grid(row=3, column=0, sticky=tk.W, pady=5)
            parent_task = self.project.get_task_by_id(self.task.parent_task_id)
            parent_name = parent_task.name if parent_task else "Unknown"
            self.parent_label = ctk.CTkLabel(main_frame, text=parent_name)
            self.parent_label.grid(row=3, column=1, sticky=tk.W, pady=5)
        
        # Duration (Days) - calculated field, displayed but not editable
        duration = self.task.duration_days
        duration_str = str(duration) if duration is not None else "N/A"
        ctk.CTkLabel(main_frame, text="Duration (Days):").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.duration_label = ctk.CTkLabel(main_frame, text=duration_str)
        self.duration_label.grid(row=4, column=1, sticky=tk.W, pady=5)
        
        # Start Date
        ctk.CTkLabel(main_frame, text="Start Date:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.start_date_entry = ctk.CTkEntry(main_frame)
        self.start_date_entry.grid(row=5, column=1, sticky=tk.EW, pady=5)
        self.start_date_entry.insert(0, self.task.start_date.strftime('%Y-%m-%d'))
        
        # End Date
        ctk.CTkLabel(main_frame, text="End Date:").grid(row=6, column=0, sticky=tk.W, pady=5)
        self.end_date_entry = ctk.CTkEntry(main_frame)
        self.end_date_entry.grid(row=6, column=1, sticky=tk.EW, pady=5)
        if self.task.end_date:
            self.end_date_entry.insert(0, self.task.end_date.strftime('%Y-%m-%d'))
        # Disable end date for milestones
        if self.task.is_milestone:
            self.end_date_entry.configure(state=tk.DISABLED)
        
        # Is Milestone
        self.is_milestone_var = ctk.BooleanVar(value=self.task.is_milestone)
        self.milestone_check = ctk.CTkCheckBox(
            main_frame, text="Is Milestone", 
            variable=self.is_milestone_var, command=self.toggle_milestone
        )
        self.milestone_check.grid(row=7, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        # Progress
        ctk.CTkLabel(main_frame, text="Progress (%):").grid(row=8, column=0, sticky=tk.W, pady=5)
        self.progress_slider = ctk.CTkSlider(main_frame, from_=0, to=100)
        self.progress_slider.grid(row=8, column=1, sticky=tk.EW, pady=5)
        self.progress_slider.set(self.task.progress)
        
        self.progress_label = ctk.CTkLabel(main_frame, text=f"{self.task.progress}%")
        self.progress_label.grid(row=8, column=2, padx=10, pady=5)
        
        self.progress_slider.bind("<B1-Motion>", self.update_progress_label)
        self.progress_slider.bind("<ButtonRelease-1>", self.update_progress_label)
        
        # Color
        ctk.CTkLabel(main_frame, text="Color:").grid(row=9, column=0, sticky=tk.W, pady=5)
        self.color_entry = ctk.CTkEntry(main_frame)
        self.color_entry.grid(row=9, column=1, sticky=tk.EW, pady=5)
        self.color_entry.insert(0, self.task.color)
        
        # Dependencies live on their own tab
        self.dependency_editor = DependencyEditor(
            self.tabs.tab("Dependency"), self.project, self.task,
            on_changed=self._on_dependencies_changed
        )
        self.dependency_editor.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Buttons
        button_frame = ctk.CTkFrame(self)
        button_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ctk.CTkButton(button_frame, text="Save", command=self.save).pack(side=tk.RIGHT, padx=5)
        ctk.CTkButton(button_frame, text="Delete", fg_color="#e74c3c", hover_color="#c0392b", command=self.delete).pack(side=tk.RIGHT, padx=5)
        ctk.CTkButton(button_frame, text="Cancel", command=self.cancel).pack(side=tk.RIGHT, padx=5)
    
    def _on_dependencies_changed(self):
        """
        Update the start date to match the current dependency links.

        DEVELOPMENT NOTES:
        ------------------
        This is what makes choosing a predecessor fill in the start date. A
        Hard link pins it; a Rubber link only moves it when the current date
        would start too early.
        """
        editor = getattr(self, 'dependency_editor', None)
        if editor is None or not hasattr(self, 'start_date_entry'):
            # Called while the dialog is still being built
            return
        try:
            current = datetime.strptime(self.start_date_entry.get(), '%Y-%m-%d')
        except (ValueError, tk.TclError):
            return

        required = editor.required_start_date(current)
        if required is None or required == current:
            return

        duration = None
        if self.task.end_date and self.task.start_date:
            duration = self.task.end_date - self.task.start_date

        self.start_date_entry.delete(0, tk.END)
        self.start_date_entry.insert(0, required.strftime('%Y-%m-%d'))

        # Keep the length of the task, shifting the end with the start
        if duration is not None and not self.is_milestone_var.get():
            self.end_date_entry.configure(state=tk.NORMAL)
            self.end_date_entry.delete(0, tk.END)
            self.end_date_entry.insert(0, (required + duration).strftime('%Y-%m-%d'))

        logger.debug("Start date moved to %s by a dependency",
                     required.strftime('%Y-%m-%d'))

    def toggle_milestone(self):
        """Toggle milestone mode."""
        is_milestone = self.is_milestone_var.get()
        
        if is_milestone:
            # Disable end date for milestones
            if self.end_date_entry:
                self.end_date_entry.configure(state=tk.DISABLED)
        else:
            # Enable end date for regular tasks
            if self.end_date_entry:
                self.end_date_entry.configure(state=tk.NORMAL)
    
    def update_progress_label(self, event=None):
        """Update progress label when slider moves."""
        value = int(self.progress_slider.get())
        self.progress_label.configure(text=f"{value}%")
    
    def save(self):
        """Save the edited task with undo support."""
        try:
            # Store old task for undo
            old_task = copy.copy(self.task)
            
            # Update task properties
            self.task.name = self.name_entry.get()
            
            # Update task type (only if not a subtask with a parent)
            # Subtasks cannot change their type or parent
            if not self.task.parent_task_id:
                self.task.task_type = self.task_type_var.get()
            
            # Parse dates
            start_date_str = self.start_date_entry.get()
            self.task.start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            
            if not self.is_milestone_var.get():
                if self.end_date_entry and self.end_date_entry.get():
                    end_date_str = self.end_date_entry.get()
                    self.task.end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                else:
                    self.task.end_date = None
            else:
                self.task.end_date = None
            
            self.task.is_milestone = self.is_milestone_var.get()
            self.task.progress = int(self.progress_slider.get())
            self.task.color = self.color_entry.get()
            
            # Update dependencies from the Dependency tab
            self.task.dependencies = self.dependency_editor.get_links()
            
            # Use undo/redo if available
            if self.project_tracker:
                new_task = copy.copy(self.task)
                if self.project_tracker.update_task(old_task.id, 
                    name=new_task.name,
                    task_type=new_task.task_type,
                    start_date=new_task.start_date,
                    end_date=new_task.end_date,
                    progress=new_task.progress,
                    dependencies=new_task.dependencies,
                    color=new_task.color,
                    is_milestone=new_task.is_milestone,
                    parent_task_id=new_task.parent_task_id
                ):
                    # Call save callback
                    if self.on_save:
                        self.on_save(new_task)
                    self.destroy()
                    return
            
            # Call save callback (fallback)
            if self.on_save:
                self.on_save(self.task)
            
            self.destroy()
            
        except ValueError as e:
            # Show error for invalid date format
            ctk.CTkLabel(self, text=f"Error: {e}", text_color="red").pack(pady=10)
    
    def delete(self):
        """Delete the task with undo support."""
        if self.project_tracker:
            if self.project_tracker.remove_task(self.task.id):
                # Call delete callback
                if self.on_delete:
                    self.on_delete(self.task.id)
        else:
            # Fallback to direct deletion
            if self.on_delete:
                self.on_delete(self.task.id)
        self.destroy()
    
    def cancel(self):
        """Cancel editing."""
        self.destroy()
    
    def _is_descendant(self, task_id: str, potential_ancestor_id: str, project: Project) -> bool:
        """
        Check if a task is a descendant of another task (through parent-child relationships).
        
        This is used to prevent circular dependencies when setting dependencies.
        A task cannot depend on itself or any of its subtasks.
        
        PARAMETERS:
        -----------
        task_id : str
            The task ID to check
        potential_ancestor_id : str
            The potential ancestor task ID
        project : Project
            The project containing the tasks
        
        RETURNS:
        --------
        bool
            True if task_id is a descendant of potential_ancestor_id
        
        DEVELOPMENT NOTES:
        ------------------
        This recursively checks the parent hierarchy to see if task_id
        is a subtask (directly or indirectly) of potential_ancestor_id.
        """
        if task_id == potential_ancestor_id:
            return True
        
        # Check if task_id is a direct or indirect subtask of potential_ancestor_id
        current_id = task_id
        while current_id:
            parent_task = project.get_task_by_id(current_id)
            if not parent_task or not parent_task.parent_task_id:
                break
            current_id = parent_task.parent_task_id
            if current_id == potential_ancestor_id:
                return True
        
        return False
    
    def center_window(self):
        """Center the window on the screen."""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")


class CreateTaskDialog(ctk.CTkToplevel):
    """
    Dialog for creating a new task, sub-task, or milestone with all fields visible at once.
    """
    
    def __init__(self, master, project: Project,
                 task_type: str = "Task", parent_task: Task = None,
                 on_save: Callable[[Task], None] = None,
                 project_tracker: ProjectStateTracker = None):
        super().__init__(master)
        
        self.project = project
        self.task_type = task_type
        self.parent_task = parent_task
        self.on_save = on_save
        self.project_tracker = project_tracker
        
        # Determine if creating a milestone
        self.is_milestone = (task_type == "Milestone")
        
        # Set window title based on type
        if self.is_milestone:
            self.title("Create New Milestone")
        elif task_type == "Sub-Task":
            self.title("Create New Sub-Task")
        else:
            self.title("Create New Task")
        
        self.geometry("620x720")
        self.minsize(560, 480)
        self.transient(master)
        # Deferred: grabbing before the window is mapped fails on X11
        grab_when_visible(self)
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        
        # Create form
        self._create_form()
        
        # Center window
        self.center_window()
    
    def _create_form(self):
        """Create the task creation form widgets."""
        # Main frame
        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(fill=tk.BOTH, expand=True, padx=15, pady=(15, 5))
        self.tabs.add("General")
        self.tabs.add("Dependency")

        main_frame = ctk.CTkScrollableFrame(self.tabs.tab("General"))
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Configure grid columns
        main_frame.columnconfigure(1, weight=1)
        
        # Task Name
        ctk.CTkLabel(main_frame, text="Task Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_entry = ctk.CTkEntry(main_frame)
        self.name_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)
        
        # Task Type (only for non-milestone)
        if not self.is_milestone:
            ctk.CTkLabel(main_frame, text="Type:").grid(row=1, column=0, sticky=tk.W, pady=5)
            self.task_type_var = ctk.StringVar(value=self.task_type)
            self.task_type_menu = ctk.CTkOptionMenu(
                main_frame, variable=self.task_type_var,
                values=["Task", "Sub-Task"],
                state=tk.DISABLED if self.parent_task else tk.NORMAL
            )
            self.task_type_menu.grid(row=1, column=1, sticky=tk.EW, pady=5)
        
        # Parent Task (for subtasks)
        if self.parent_task:
            ctk.CTkLabel(main_frame, text="Parent Task:").grid(row=2, column=0, sticky=tk.W, pady=5)
            self.parent_label = ctk.CTkLabel(main_frame, text=self.parent_task.name)
            self.parent_label.grid(row=2, column=1, sticky=tk.W, pady=5)
        elif self.task_type == "Sub-Task":
            # Need to select parent
            ctk.CTkLabel(main_frame, text="Parent Task:").grid(row=2, column=0, sticky=tk.W, pady=5)
            parent_names = [t.name for t in self.project.get_root_tasks()]
            if parent_names:
                self.parent_var = ctk.StringVar()
                self.parent_menu = ctk.CTkOptionMenu(
                    main_frame, variable=self.parent_var,
                    values=parent_names
                )
                self.parent_menu.grid(row=2, column=1, sticky=tk.EW, pady=5)
            else:
                self.parent_label = ctk.CTkLabel(main_frame, text="No parent tasks available")
                self.parent_label.grid(row=2, column=1, sticky=tk.W, pady=5)
        
        # Start Date
        row_offset = 3 if self.parent_task or self.task_type == "Sub-Task" or not self.is_milestone else 2
        if self.parent_task and not self.is_milestone:
            # For subtasks, default to parent's start date
            start_date_str = self.parent_task.start_date.strftime('%Y-%m-%d')
        else:
            start_date_str = datetime.now().strftime('%Y-%m-%d')
        
        ctk.CTkLabel(main_frame, text="Start Date:").grid(row=row_offset, column=0, sticky=tk.W, pady=5)
        self.start_date_entry = ctk.CTkEntry(main_frame)
        self.start_date_entry.grid(row=row_offset, column=1, sticky=tk.EW, pady=5)
        self.start_date_entry.insert(0, start_date_str)
        
        # End Date (not for milestones)
        if not self.is_milestone:
            ctk.CTkLabel(main_frame, text="End Date:").grid(row=row_offset+1, column=0, sticky=tk.W, pady=5)
            self.end_date_entry = ctk.CTkEntry(main_frame)
            self.end_date_entry.grid(row=row_offset+1, column=1, sticky=tk.EW, pady=5)
            # Default end date: start + 7 days for tasks, start + 1 day for subtasks
            if self.parent_task:
                default_end = self.parent_task.start_date + timedelta(days=1)
            else:
                default_end = datetime.now() + timedelta(days=7)
            self.end_date_entry.insert(0, default_end.strftime('%Y-%m-%d'))
        else:
            self.end_date_entry = None
        
        # Is Milestone checkbox
        ctk.CTkLabel(main_frame, text="Is Milestone:").grid(row=row_offset+2, column=0, sticky=tk.W, pady=5)
        self.is_milestone_var = ctk.BooleanVar(value=self.is_milestone)
        self.milestone_check = ctk.CTkCheckBox(
            main_frame, text="",
            variable=self.is_milestone_var, command=self.toggle_milestone
        )
        self.milestone_check.grid(row=row_offset+2, column=1, sticky=tk.W, pady=5)
        
        # Progress
        ctk.CTkLabel(main_frame, text="Progress (%):").grid(row=row_offset+3, column=0, sticky=tk.W, pady=5)
        self.progress_slider = ctk.CTkSlider(main_frame, from_=0, to=100)
        self.progress_slider.grid(row=row_offset+3, column=1, sticky=tk.EW, pady=5)
        self.progress_slider.set(0)
        
        self.progress_label = ctk.CTkLabel(main_frame, text="0%")
        self.progress_label.grid(row=row_offset+3, column=2, padx=10, pady=5)
        
        self.progress_slider.bind("<B1-Motion>", self.update_progress_label)
        self.progress_slider.bind("<ButtonRelease-1>", self.update_progress_label)
        
        # Color
        ctk.CTkLabel(main_frame, text="Color:").grid(row=row_offset+4, column=0, sticky=tk.W, pady=5)
        self.color_entry = ctk.CTkEntry(main_frame)
        self.color_entry.grid(row=row_offset+4, column=1, sticky=tk.EW, pady=5)
        
        # Default colors based on type
        if self.is_milestone:
            self.color_entry.insert(0, "#e74c3c")
        elif self.task_type == "Sub-Task":
            self.color_entry.insert(0, "#9b59b6")
        else:
            self.color_entry.insert(0, "#3498db")
        
        # Dependencies live on their own tab. A task being created has no
        # ID yet, so a stand-in carries the parent link used to exclude
        # invalid candidates.
        probe = Task(
            id='__new__',
            name=self.task_type,
            start_date=datetime.now(),
            task_type=self.task_type,
            parent_task_id=self.parent_task.id if self.parent_task else None,
            is_milestone=self.is_milestone,
        )
        self.dependency_editor = DependencyEditor(
            self.tabs.tab("Dependency"), self.project, probe,
            on_changed=self._on_dependencies_changed
        )
        self.dependency_editor.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Buttons
        button_frame = ctk.CTkFrame(self)
        button_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ctk.CTkButton(button_frame, text="Save", command=self.save).pack(side=tk.RIGHT, padx=5)
        ctk.CTkButton(button_frame, text="Cancel", command=self.cancel).pack(side=tk.RIGHT, padx=5)
    
    def toggle_milestone(self):
        """Toggle milestone mode."""
        is_milestone = self.is_milestone_var.get()
        
        if is_milestone:
            # Disable end date for milestones
            if self.end_date_entry:
                self.end_date_entry.configure(state=tk.DISABLED)
        else:
            # Enable end date for regular tasks
            if self.end_date_entry:
                self.end_date_entry.configure(state=tk.NORMAL)
    
    def update_progress_label(self, event=None):
        """Update progress label when slider moves."""
        value = int(self.progress_slider.get())
        self.progress_label.configure(text=f"{value}%")
    
    def _on_dependencies_changed(self):
        """
        Move the start date to satisfy the chosen dependency links.

        DEVELOPMENT NOTES:
        ------------------
        Selecting a predecessor fills the start date in straight away, so a
        new task lands where its links require without the user working the
        date out.
        """
        editor = getattr(self, 'dependency_editor', None)
        if editor is None or not hasattr(self, 'start_date_entry'):
            # Called while the dialog is still being built
            return
        try:
            current = datetime.strptime(self.start_date_entry.get(), '%Y-%m-%d')
        except (ValueError, tk.TclError):
            return

        required = editor.required_start_date(current)
        if required is None or required == current:
            return

        duration = None
        try:
            end_text = self.end_date_entry.get()
            if end_text:
                duration = datetime.strptime(end_text, '%Y-%m-%d') - current
        except (ValueError, AttributeError, tk.TclError):
            duration = None

        self.start_date_entry.delete(0, tk.END)
        self.start_date_entry.insert(0, required.strftime('%Y-%m-%d'))

        if duration is not None and not self.is_milestone:
            self.end_date_entry.delete(0, tk.END)
            self.end_date_entry.insert(0, (required + duration).strftime('%Y-%m-%d'))

        logger.debug("New task start moved to %s by a dependency",
                     required.strftime('%Y-%m-%d'))

    def save(self):
        """Save the new task."""
        try:
            # Determine final task type
            if self.is_milestone_var.get():
                final_task_type = "Task"  # Milestones are type "Task" with is_milestone=True
                is_milestone = True
            else:
                final_task_type = self.task_type_var.get() if not self.is_milestone else self.task_type
                is_milestone = False
            
            # Get name
            name = self.name_entry.get()
            if not name:
                raise ValueError("Task name cannot be empty")
            
            # Parse start date
            start_date_str = self.start_date_entry.get()
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            
            # Get end date if not milestone
            end_date = None
            if not is_milestone and self.end_date_entry:
                end_date_str = self.end_date_entry.get()
                if end_date_str:
                    end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            
            # Get progress
            progress = int(self.progress_slider.get())
            
            # Get color
            color = self.color_entry.get()
            
            # Get dependencies from the Dependency tab
            dependencies = self.dependency_editor.get_links()
            
            # Determine parent task ID
            parent_task_id = None
            if self.parent_task:
                parent_task_id = self.parent_task.id
            elif hasattr(self, 'parent_var') and self.parent_var.get():
                # Find parent task by name
                parent_name = self.parent_var.get()
                parent = self.project.get_task_by_id(parent_name)
                if parent:
                    parent_task_id = parent.id
                else:
                    # Try to find by name
                    for t in self.project.tasks:
                        if t.name == parent_name:
                            parent_task_id = t.id
                            break
            
            # Update task type if parent is set
            if parent_task_id and final_task_type != "Sub-Task":
                final_task_type = "Sub-Task"
            
            # Create the task
            task = Task(
                id=self.project.next_task_id(),
                name=name,
                start_date=start_date,
                end_date=end_date,
                progress=progress,
                dependencies=dependencies,
                color=color,
                is_milestone=is_milestone,
                task_type=final_task_type,
                parent_task_id=parent_task_id
            )
            
            # Validate
            task.__post_init__()
            
            # Call save callback
            if self.on_save:
                self.on_save(task)
            
            self.destroy()
            
        except ValueError as e:
            # Show error
            ctk.CTkLabel(self, text=f"Error: {e}", text_color="red").pack(pady=10)
    
    def cancel(self):
        """Cancel task creation."""
        self.destroy()
    
    def _is_descendant(self, task_id: str, potential_ancestor_id: str, project: Project) -> bool:
        """Check if a task is a descendant of another task."""
        if task_id == potential_ancestor_id:
            return True
        
        current_id = task_id
        while current_id:
            parent_task = project.get_task_by_id(current_id)
            if not parent_task or not parent_task.parent_task_id:
                break
            current_id = parent_task.parent_task_id
            if current_id == potential_ancestor_id:
                return True
        
        return False
    
    def center_window(self):
        """Center the window on the screen."""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")


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
                 project_tracker: ProjectStateTracker = None):
        super().__init__(master)
        
        self.master = master
        self.project = project
        self.on_task_select = on_task_select
        self.on_task_edit = on_task_edit
        self.on_project_changed = on_project_changed
        self.project_tracker = project_tracker
        
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
        
        # Column widths. #0 holds only the expander, so it stays narrow
        self.tree.column('#0', width=34, minwidth=34, stretch=False)
        self.tree.column('ID', width=80, stretch=False)
        self.tree.column('Name', width=200, stretch=True)
        self.tree.column('Type', width=80, stretch=False)
        self.tree.column('Duration', width=100, stretch=False)
        self.tree.column('Start', width=100, stretch=False)
        self.tree.column('End', width=100, stretch=False)
        self.tree.column('Progress', width=80, stretch=False)
        self.tree.column('Dependencies', width=150, stretch=False)
        self.tree.column('Milestone', width=80, stretch=False)
        
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
        anchor_id : str
            The row the context menu was opened on.

        DEVELOPMENT NOTES:
        ------------------
        A sub-task is created under the clicked row, which is what makes it
        a sub-task. A task or milestone is created beside it and dropped in
        directly below, rather than at the end of the plan: the menu was
        opened on a particular row, so that is where the new one belongs.
        """
        anchor = self.project.get_task_by_id(anchor_id)
        if anchor is None:
            return

        # A sub-task goes inside the clicked row; a task or milestone goes
        # beside it, which is what "under this row" means for those
        if task_type == "Sub-Task":
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
        task.task_type = "Sub-Task" if parent_id else "Task"

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


    def _is_descendant(self, task_id: str, potential_ancestor_id: str, project: Project) -> bool:
        """
        Check if a task is a descendant of another task (through parent-child relationships).
        
        This is used to prevent circular dependencies when setting dependencies.
        A task cannot depend on itself or any of its subtasks.
        
        PARAMETERS:
        -----------
        task_id : str
            The task ID to check
        potential_ancestor_id : str
            The potential ancestor task ID
        project : Project
            The project containing the tasks
        
        RETURNS:
        --------
        bool
            True if task_id is a descendant of potential_ancestor_id
        
        DEVELOPMENT NOTES:
        ------------------
        This recursively checks the parent hierarchy to see if task_id
        is a subtask (directly or indirectly) of potential_ancestor_id.
        """
        if task_id == potential_ancestor_id:
            return True
        
        # Check if task_id is a direct or indirect subtask of potential_ancestor_id
        current_id = task_id
        while current_id:
            parent_task = project.get_task_by_id(current_id)
            if not parent_task or not parent_task.parent_task_id:
                break
            current_id = parent_task.parent_task_id
            if current_id == potential_ancestor_id:
                return True
        
        return False
    
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
        if self._is_descendant(target_id, source_id, self.project):
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
        if task.task_type == 'Sub-Task':
            tags.append('subtask')
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
