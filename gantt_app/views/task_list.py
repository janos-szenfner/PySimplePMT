"""
Drag-and-drop task list view for the Gantt Project Management Tool.

Uses tkinterdnd2 for drag-and-drop functionality with ttk.Treeview.
"""

import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta
from typing import Optional, Callable, List, Dict, Any
import copy

import customtkinter as ctk

from gantt_app.models import Task, Project
from gantt_app.utils.undoredo import ProjectStateTracker

# Try to import tkinterdnd2 for enhanced drag and drop
try:
    import tkinterdnd2
    # Check if Treeview and Scrollbar are available in the expected location
    if (hasattr(tkinterdnd2, 'TkinterDnD') and 
        hasattr(tkinterdnd2.TkinterDnD, 'Treeview') and
        hasattr(tkinterdnd2.TkinterDnD, 'Scrollbar')):
        TKINTERDND2_AVAILABLE = True
    else:
        TKINTERDND2_AVAILABLE = False
except ImportError:
    TKINTERDND2_AVAILABLE = False


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
        self.geometry("500x600")
        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        
        # Create form
        self._create_form()
        
        # Center window
        self.center_window()
    
    def _create_form(self):
        """Create the edit form widgets."""
        # Main frame
        main_frame = ctk.CTkScrollableFrame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
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
        
        # Dependencies
        ctk.CTkLabel(main_frame, text="Dependencies:").grid(row=10, column=0, sticky=tk.W, pady=5)
        
        # Available tasks for dependencies
        self.dep_vars = []
        self.dep_frame = ctk.CTkScrollableFrame(main_frame)
        self.dep_frame.grid(row=11, column=0, columnspan=2, sticky=tk.EW, pady=5)
        self.dep_frame.configure(height=150)
        
        # Filter out current task and its descendants from available dependencies
        # (a task cannot depend on itself or its own subtasks - that would create a circle)
        available_tasks = []
        for t in self.project.tasks:
            if t.id != self.task.id:
                # Check if this task is a descendant of the current task
                if not self._is_descendant(t.id, self.task.id, self.project):
                    available_tasks.append(t)
        
        # Sort tasks by start date for consistent display
        available_tasks.sort(key=lambda t: t.start_date)
        
        # Create checkboxes for each available task with hierarchical grouping
        # Display tasks and subtasks in a structured way
        if available_tasks:
            # Group tasks by parent (root tasks have no parent)
            root_tasks = [t for t in available_tasks if t.parent_task_id is None]
            subtasks = [t for t in available_tasks if t.parent_task_id is not None]
            
            # Sort by start date
            root_tasks.sort(key=lambda t: t.start_date)
            subtasks.sort(key=lambda t: t.start_date)
            
            # Create a frame for each root task and its subtasks
            for root_task in root_tasks:
                # Root task checkbox
                var = ctk.BooleanVar(value=root_task.id in self.task.dependencies)
                self.dep_vars.append((root_task.id, var))
                
                check = ctk.CTkCheckBox(
                    self.dep_frame, 
                    text=f"{root_task.name} ({root_task.start_date.strftime('%Y-%m-%d')})",
                    variable=var
                )
                check.pack(fill=tk.X, padx=5, pady=2, anchor=tk.W)
                
                # Find subtasks that belong to this root task
                root_subtasks = [st for st in subtasks if st.parent_task_id == root_task.id]
                
                # Add subtasks under the root task with indentation
                for subtask in root_subtasks:
                    var = ctk.BooleanVar(value=subtask.id in self.task.dependencies)
                    self.dep_vars.append((subtask.id, var))
                    
                    check = ctk.CTkCheckBox(
                        self.dep_frame, 
                        text=f"  ├── {subtask.name} (Sub-Task) ({subtask.start_date.strftime('%Y-%m-%d')})",
                        variable=var
                    )
                    check.pack(fill=tk.X, padx=15, pady=2, anchor=tk.W)
            
            # Add any remaining subtasks that don't have a parent in available tasks
            # (this can happen if the parent was filtered out due to circular dependency)
            remaining_subtasks = [st for st in subtasks if st.parent_task_id not in [t.id for t in root_tasks]]
            for subtask in remaining_subtasks:
                var = ctk.BooleanVar(value=subtask.id in self.task.dependencies)
                self.dep_vars.append((subtask.id, var))
                
                parent_name = self.project.get_task_by_id(subtask.parent_task_id).name if self.project.get_task_by_id(subtask.parent_task_id) else "Unknown"
                check = ctk.CTkCheckBox(
                    self.dep_frame, 
                    text=f"  └─ {subtask.name} (Sub-Task of {parent_name}) ({subtask.start_date.strftime('%Y-%m-%d')})",
                    variable=var
                )
                check.pack(fill=tk.X, padx=5, pady=2, anchor=tk.W)
        
        # Add a note about multiple selection
        if available_tasks:
            note_label = ctk.CTkLabel(
                self.dep_frame, 
                text="Check multiple boxes to select tasks and subtasks as dependencies",
                text_color="#7f8c8d",
                font=ctk.CTkFont(size=10, slant="italic")
            )
            note_label.pack(fill=tk.X, padx=5, pady=(5, 0), anchor=tk.W)
        
        # Buttons
        button_frame = ctk.CTkFrame(self)
        button_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ctk.CTkButton(button_frame, text="Save", command=self.save).pack(side=tk.RIGHT, padx=5)
        ctk.CTkButton(button_frame, text="Delete", fg_color="#e74c3c", hover_color="#c0392b", command=self.delete).pack(side=tk.RIGHT, padx=5)
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
            
            # Update dependencies
            self.task.dependencies = [
                task_id for task_id, var in self.dep_vars if var.get()
            ]
            
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
        
        self.geometry("500x700")
        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        
        # Create form
        self._create_form()
        
        # Center window
        self.center_window()
    
    def _create_form(self):
        """Create the task creation form widgets."""
        # Main frame
        main_frame = ctk.CTkScrollableFrame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
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
        
        # Dependencies
        ctk.CTkLabel(main_frame, text="Dependencies:").grid(row=row_offset+5, column=0, sticky=tk.W, pady=5)
        
        # Available tasks for dependencies
        self.dep_vars = []
        self.dep_frame = ctk.CTkScrollableFrame(main_frame)
        self.dep_frame.grid(row=row_offset+6, column=0, columnspan=2, sticky=tk.EW, pady=5)
        self.dep_frame.configure(height=150)
        
        # Get available tasks (exclude self if editing, but for new task just show all)
        available_tasks = []
        for t in self.project.tasks:
            # Check if this task is a descendant of the parent (for subtasks)
            if self.parent_task:
                if not self._is_descendant(t.id, self.parent_task.id, self.project):
                    available_tasks.append(t)
            else:
                available_tasks.append(t)
        
        # Sort tasks by start date for consistent display
        available_tasks.sort(key=lambda t: t.start_date)
        
        # Create checkboxes for each available task
        if available_tasks:
            for task in available_tasks:
                var = ctk.BooleanVar(value=False)
                self.dep_vars.append((task.id, var))
                
                check = ctk.CTkCheckBox(
                    self.dep_frame,
                    text=f"{task.name} ({task.start_date.strftime('%Y-%m-%d')})",
                    variable=var
                )
                check.pack(fill=tk.X, padx=5, pady=2, anchor=tk.W)
        
        # Note about dependencies
        if available_tasks:
            note_label = ctk.CTkLabel(
                self.dep_frame,
                text="Check multiple boxes to select dependencies",
                text_color="#7f8c8d",
                font=ctk.CTkFont(size=10, slant="italic")
            )
            note_label.pack(fill=tk.X, padx=5, pady=(5, 0), anchor=tk.W)
        
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
            
            # Get dependencies
            dependencies = [task_id for task_id, var in self.dep_vars if var.get()]
            
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
    Task list with drag-and-drop functionality for setting dependencies.
    Uses tkinterdnd2 for enhanced drag and drop when available.
    """
    
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
        
        # Track drag and drop state for tkinterdnd2
        self.dnd_enabled = TKINTERDND2_AVAILABLE
        
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
        
        # Create Treeview - use tkinterdnd2.TkinterDnD.Treeview if available
        if TKINTERDND2_AVAILABLE:
            TreeviewDnD = tkinterdnd2.TkinterDnD.Treeview
            self.tree = TreeviewDnD(tree_frame, columns=(
                'ID', 'Name', 'Type', 'Duration', 'Start', 'End', 'Progress', 'Dependencies', 'Milestone'
            ), show='headings')
            # Store reference for dnd operations
            self.tree_dnd = self.tree
        else:
            self.tree = ttk.Treeview(tree_frame, columns=(
                'ID', 'Name', 'Type', 'Duration', 'Start', 'End', 'Progress', 'Dependencies', 'Milestone'
            ), show='headings')
            self.tree_dnd = None
        
        # Configure columns
        self.tree.heading('ID', text='ID', anchor=tk.W)
        self.tree.heading('Name', text='Name', anchor=tk.W)
        self.tree.heading('Type', text='Type', anchor=tk.W)
        self.tree.heading('Duration', text='Duration (Days)', anchor=tk.W)
        self.tree.heading('Start', text='Start Date', anchor=tk.W)
        self.tree.heading('End', text='End Date', anchor=tk.W)
        self.tree.heading('Progress', text='Progress', anchor=tk.W)
        self.tree.heading('Dependencies', text='Dependencies', anchor=tk.W)
        self.tree.heading('Milestone', text='Milestone', anchor=tk.W)
        
        # Column widths
        self.tree.column('ID', width=80, stretch=False)
        self.tree.column('Name', width=200, stretch=True)
        self.tree.column('Type', width=80, stretch=False)
        self.tree.column('Duration', width=100, stretch=False)
        self.tree.column('Start', width=100, stretch=False)
        self.tree.column('End', width=100, stretch=False)
        self.tree.column('Progress', width=80, stretch=False)
        self.tree.column('Dependencies', width=150, stretch=False)
        self.tree.column('Milestone', width=80, stretch=False)
        
        # Scrollbars - use tkinterdnd2 versions if available
        if TKINTERDND2_AVAILABLE:
            vsb = tkinterdnd2.TkinterDnD.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
            hsb = tkinterdnd2.TkinterDnD.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        else:
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
        
        # Configure tags for subtask styling
        self.tree.tag_configure('subtask', foreground='#7f8c8d')
        
        # Bind events
        self.tree.bind('<Double-1>', self.on_double_click)
        self.tree.bind('<ButtonPress-1>', self.on_press)
        self.tree.bind('<ButtonRelease-1>', self.on_release)
        self.tree.bind('<B1-Motion>', self.on_drag)
        self.tree.bind('<<TreeviewSelect>>', self.on_select)
        
        # Enable drag and drop
        self._enable_dnd()
    
    def _enable_dnd(self):
        """Enable drag and drop for the treeview."""
        if TKINTERDND2_AVAILABLE:
            # Register the treeview as a drop target
            self.tree.drop_target_register(tkinterdnd2.DND_FILES)
            self.tree.drop_target_register(tkinterdnd2.DND_TEXT)
            
            # Bind DnD events
            self.tree.bind('<<DropEnter>>', self.on_dnd_enter)
            self.tree.bind('<<DropLeave>>', self.on_dnd_leave)
            self.tree.bind('<<DropPosition>>', self.on_dnd_position)
            self.tree.bind('<<Drop>>', self.on_dnd_drop)
            self.tree.bind('<<DragInit>>', self.on_dnd_init)
            
            # For the frame itself
            self.tree_frame.drop_target_register(tkinterdnd2.DND_FILES)
            self.tree_frame.drop_target_register(tkinterdnd2.DND_TEXT)
            self.tree_frame.bind('<<Drop>>', self.on_dnd_drop)
    
    def on_dnd_init(self, event):
        """Handle drag initiation for tkinterdnd2."""
        # Get the item under the cursor
        item = self.tree.identify_row(event.y)
        if item:
            self.dragged_task_id = self.tree.item(item, 'text')
            self.tree.selection_set(item)
            # Store the item for drag feedback
            self.drag_item = item
            # Set drag data
            event.widget.dnd_start(event, 'text/plain', self.dragged_task_id)
    
    def on_dnd_enter(self, event):
        """Handle drag enter for visual feedback."""
        # Highlight the treeview during drag
        self.tree.config(bg='#f0f0f0')
        
    def on_dnd_leave(self, event):
        """Handle drag leave for visual feedback."""
        self.tree.config(bg='')
        
    def on_dnd_position(self, event):
        """Handle drag position for visual feedback."""
        # Get the item under the cursor
        item = self.tree.identify_row(event.y)
        if item and item != self.drag_item:
            # Highlight the potential drop target
            self.tree.selection_set(item)
    
    def on_dnd_drop(self, event):
        """Handle drop event for setting dependencies with tkinterdnd2."""
        if self.dragged_task_id is None:
            return
            
        # Get the target item
        target_item = self.tree.identify_row(event.y)
        if target_item:
            target_task_id = self.tree.item(target_item, 'text')
            
            # Don't allow circular dependencies
            source_task = self.project.get_task_by_id(self.dragged_task_id)
            target_task = self.project.get_task_by_id(target_task_id)
            
            if source_task and target_task:
                # Check if adding this dependency would create a circular reference
                if not self._would_create_circle(self.dragged_task_id, target_task_id):
                    # Add dependency with undo support
                    if target_task_id not in source_task.dependencies:
                        # Store old dependencies for undo
                        old_dependencies = copy.copy(source_task.dependencies)
                        
                        # Add the new dependency
                        source_task.dependencies.append(target_task_id)
                        
                        # Use undo/redo if available
                        if self.project_tracker:
                            new_dependencies = copy.copy(source_task.dependencies)
                            if self.project_tracker.update_task(
                                source_task.id,
                                dependencies=new_dependencies
                            ):
                                self.update_task_list()
                                if self.on_project_changed:
                                    self.on_project_changed()
                        else:
                            # Fallback
                            self.update_task_list()
                            if self.on_project_changed:
                                self.on_project_changed()
        
        # Reset drag state
        self.dragged_task_id = None
        self.tree.config(bg='')
        if hasattr(self, 'drag_item'):
            self.drag_item = None
    
    def on_double_click(self, event):
        """Handle double click to edit task."""
        item = self.tree.selection()[0] if self.tree.selection() else None
        if item:
            task_id = self.tree.item(item, 'text')
            task = self.project.get_task_by_id(task_id)
            if task and self.on_task_edit:
                self.on_task_edit(task)
    
    def on_select(self, event):
        """Handle task selection."""
        item = self.tree.selection()[0] if self.tree.selection() else None
        if item:
            task_id = self.tree.item(item, 'text')
            task = self.project.get_task_by_id(task_id)
            if task and self.on_task_select:
                self.on_task_select(task)
    
    def on_press(self, event):
        """Handle mouse press for drag start."""
        item = self.tree.identify_row(event.y)
        if item:
            self.dragged_task_id = self.tree.item(item, 'text')
            self.tree.selection_set(item)
    
    def on_drag(self, event):
        """Handle drag motion."""
        # This is a simplified drag implementation
        # For full drag-and-drop, tkinterdnd2 would be needed
        pass
    
    def on_release(self, event):
        """Handle mouse release for drop with undo support."""
        if self.dragged_task_id is None:
            return
        
        # Get the target item
        target_item = self.tree.identify_row(event.y)
        if target_item and target_item != self.tree.selection()[0]:
            target_task_id = self.tree.item(target_item, 'text')
            
            # Don't allow circular dependencies
            source_task = self.project.get_task_by_id(self.dragged_task_id)
            target_task = self.project.get_task_by_id(target_task_id)
            
            if source_task and target_task:
                # Check if adding this dependency would create a circular reference
                if not self._would_create_circle(self.dragged_task_id, target_task_id):
                    # Add dependency with undo support
                    if target_task_id not in source_task.dependencies:
                        # Store old dependencies for undo
                        old_dependencies = copy.copy(source_task.dependencies)
                        
                        # Add the new dependency
                        source_task.dependencies.append(target_task_id)
                        
                        # Use undo/redo if available
                        if self.project_tracker:
                            new_dependencies = copy.copy(source_task.dependencies)
                            if self.project_tracker.update_task(
                                source_task.id,
                                dependencies=new_dependencies
                            ):
                                self.update_task_list()
                                if self.on_project_changed:
                                    self.on_project_changed()
                        else:
                            # Fallback
                            self.update_task_list()
                            if self.on_project_changed:
                                self.on_project_changed()
        
        self.dragged_task_id = None
    
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
            
            for dep_id in task.dependencies:
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
        
        # First, add root tasks (non-subtasks)
        root_tasks = self.project.get_root_tasks()
        root_tasks_sorted = sorted(root_tasks, key=lambda t: t.start_date)
        
        for task in root_tasks_sorted:
            self._add_task_to_tree(task, indent_level=0)
        
        # Then add subtasks under their parent tasks
        for task in self.project.tasks:
            if task.parent_task_id:
                # Find the parent task's tree item
                parent = self.project.get_task_by_id(task.parent_task_id)
                if parent:
                    # Find all root tasks and their subtasks to maintain order
                    pass
        
        # Re-sort all items to maintain proper order
        # Actually, let's use a better approach - add all tasks with proper indentation
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Build a proper hierarchy
        self._populate_tree_hierarchical()
    
    def _populate_tree_hierarchical(self):
        """
        Populate the treeview with tasks in a hierarchical structure.
        
        DEVELOPMENT NOTES:
        ------------------
        This method first adds all root tasks, then adds subtasks under their
        parent tasks. It uses the treeview's parent-child relationships to
        create the visual hierarchy.
        """
        # Map task IDs to tree items for parent-child relationships
        tree_items = {}
        
        # First pass: add all root tasks
        root_tasks = self.project.get_root_tasks()
        root_tasks_sorted = sorted(root_tasks, key=lambda t: t.start_date)

        for task in root_tasks_sorted:
            item_id = self._add_task_to_tree(task, indent_level=0)
            tree_items[task.id] = item_id

        # Further passes: add subtasks once their parent is in the tree.
        # Imported files (notably GanttProject) can nest tasks several levels
        # deep, so keep sweeping until a pass places nothing new - a single
        # pass would silently drop anything below the second level.
        remaining = [t for t in sorted(self.project.tasks, key=lambda t: t.start_date)
                     if t.parent_task_id]

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
        
        # Format name with indentation for subtasks
        display_name = task.name
        if indent_level > 0:
            display_name = ('  ' * indent_level) + '├── ' + display_name
        
        # Insert into tree
        item_id = self.tree.insert(parent_item, tk.END, 
                                 iid=task.id,
                                 text=task.id,
                                 values=(
                                     task.id,  # IDs are short sequential numbers
                                     display_name,
                                     type_str,
                                     duration_str,
                                     start_str,
                                     end_str,
                                     f"{task.progress}%",
                                     deps_str,
                                     milestone_str
                                 ))
        
        # Apply tag for subtask styling
        if task.task_type == 'Sub-Task':
            self.tree.item(item_id, tags=('subtask',))
        
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
        """Select a task in the list."""
        for item in self.tree.get_children():
            if self.tree.item(item, 'text') == task_id:
                self.tree.selection_set(item)
                self.tree.see(item)
                break
