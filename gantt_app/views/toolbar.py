"""
Toolbar for the Gantt Project Management Tool.

Contains action buttons for managing the project.
"""

import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
from datetime import datetime, timedelta
from typing import Optional, Callable, List

import customtkinter as ctk

from gantt_app.models import Task, Project
from gantt_app.utils.file_io import JSONFileIO, save_project, load_project
from gantt_app.utils.gan_importer import import_gan_file
from gantt_app.utils.mpp_importer import import_mpp_file
from gantt_app.utils.mermaid_importer import import_mermaid_file
from gantt_app.utils.mermaid_exporter import export_project_to_mermaid
from gantt_app.utils.undoredo import UndoRedoManager


class Toolbar(ctk.CTkFrame):
    """
    Toolbar with action buttons for the Gantt application.
    """
    
    def __init__(self, master, project: Project,
                 on_project_changed: Callable[[], None] = None,
                 gantt_chart=None,
                 undo_redo_manager: UndoRedoManager = None):
        super().__init__(master)
        
        self.master = master
        self.project = project
        self.on_project_changed = on_project_changed
        self.gantt_chart = gantt_chart
        self.undo_redo_manager = undo_redo_manager
        
        # Create UI
        self._create_ui()
    
    def _create_ui(self):
        """Create the toolbar user interface."""
        # Undo/Redo buttons
        self._create_undo_redo_buttons()
        
        # Project buttons
        self._create_project_buttons()
        
        # File buttons
        self._create_file_buttons()
        
        # Import buttons
        self._create_import_buttons()
        
        # Export buttons
        self._create_export_buttons()
        
        # Theme toggle
        self._create_theme_toggle()
    
    def _create_project_buttons(self):
        """Create buttons for project management."""
        project_frame = ctk.CTkFrame(self)
        project_frame.pack(side=tk.LEFT, padx=5, pady=5)
        
        # Add Task button
        add_task_btn = ctk.CTkButton(
            project_frame, text="Add Task",
            command=self.add_task, width=100
        )
        add_task_btn.pack(side=tk.LEFT, padx=5, pady=5)
        
        # Add Sub-Task button
        add_subtask_btn = ctk.CTkButton(
            project_frame, text="Add Sub-Task",
            command=self.add_subtask, width=100,
            fg_color="#9b59b6", hover_color="#8e44ad"
        )
        add_subtask_btn.pack(side=tk.LEFT, padx=5, pady=5)
        
        # Add Milestone button
        add_milestone_btn = ctk.CTkButton(
            project_frame, text="Add Milestone",
            command=self.add_milestone, width=100
        )
        add_milestone_btn.pack(side=tk.LEFT, padx=5, pady=5)
        
        # Project Info button
        project_info_btn = ctk.CTkButton(
            project_frame, text="Project Info",
            command=self.edit_project_info, width=100
        )
        project_info_btn.pack(side=tk.LEFT, padx=5, pady=5)
    
    def _create_file_buttons(self):
        """Create buttons for file operations."""
        file_frame = ctk.CTkFrame(self)
        file_frame.pack(side=tk.LEFT, padx=5, pady=5)
        
        # Save Project button
        save_btn = ctk.CTkButton(
            file_frame, text="Save Project",
            command=self.save_project, width=100
        )
        save_btn.pack(side=tk.LEFT, padx=5, pady=5)
        
        # Load Project button
        load_btn = ctk.CTkButton(
            file_frame, text="Load Project",
            command=self.load_project, width=100
        )
        load_btn.pack(side=tk.LEFT, padx=5, pady=5)
        
        # New Project button
        new_btn = ctk.CTkButton(
            file_frame, text="New Project",
            command=self.new_project, width=100, fg_color="#3498db"
        )
        new_btn.pack(side=tk.LEFT, padx=5, pady=5)
    
    def _create_import_buttons(self):
        """Create buttons for importing files."""
        import_frame = ctk.CTkFrame(self)
        import_frame.pack(side=tk.LEFT, padx=5, pady=5)
        
        # Import GAN button
        import_gan_btn = ctk.CTkButton(
            import_frame, text="Import GAN",
            command=self.import_gan, width=100
        )
        import_gan_btn.pack(side=tk.LEFT, padx=5, pady=5)
        
        # Import MPP button
        import_mpp_btn = ctk.CTkButton(
            import_frame, text="Import MPP",
            command=self.import_mpp, width=100
        )
        import_mpp_btn.pack(side=tk.LEFT, padx=5, pady=5)
        
        # Import Mermaid button
        import_mermaid_btn = ctk.CTkButton(
            import_frame, text="Import Mermaid",
            command=self.import_mermaid, width=100
        )
        import_mermaid_btn.pack(side=tk.LEFT, padx=5, pady=5)
        
    def _create_export_buttons(self):
        """Create buttons for exporting files."""
        export_frame = ctk.CTkFrame(self)
        export_frame.pack(side=tk.LEFT, padx=5, pady=5)
        
        # Export Mermaid button
        export_mermaid_btn = ctk.CTkButton(
            export_frame, text="Export Mermaid",
            command=self.export_mermaid, width=100
        )
        export_mermaid_btn.pack(side=tk.LEFT, padx=5, pady=5)
        
        # Export PNG button
        export_png_btn = ctk.CTkButton(
            export_frame, text="Export PNG",
            command=self.export_png, width=100
        )
        export_png_btn.pack(side=tk.LEFT, padx=5, pady=5)
        
        # Export PDF button
        export_pdf_btn = ctk.CTkButton(
            export_frame, text="Export PDF",
            command=self.export_pdf, width=100
        )
        export_pdf_btn.pack(side=tk.LEFT, padx=5, pady=5)
    
    def _create_undo_redo_buttons(self):
        """Create undo and redo buttons."""
        undo_frame = ctk.CTkFrame(self)
        undo_frame.pack(side=tk.LEFT, padx=5, pady=5)
        
        # Undo button
        self.undo_btn = ctk.CTkButton(
            undo_frame, text="Undo",
            command=self.undo, width=80,
            fg_color="#3498db", hover_color="#2980b9"
        )
        self.undo_btn.pack(side=tk.LEFT, padx=2, pady=5)
        
        # Redo button
        self.redo_btn = ctk.CTkButton(
            undo_frame, text="Redo",
            command=self.redo, width=80,
            fg_color="#2ecc71", hover_color="#27ae60"
        )
        self.redo_btn.pack(side=tk.LEFT, padx=2, pady=5)
        
        # Update button states
        self.update_undo_redo_buttons()
    
    def _create_theme_toggle(self):
        """Create theme toggle button."""
        theme_frame = ctk.CTkFrame(self)
        theme_frame.pack(side=tk.RIGHT, padx=5, pady=5)
        
        # Theme toggle
        self.theme_toggle = ctk.CTkButton(
            theme_frame, text="Toggle Theme",
            command=self.toggle_theme, width=100
        )
        self.theme_toggle.pack(side=tk.LEFT, padx=5, pady=5)
    
    def add_task(self):
        """Add a new task to the project with undo support."""
        # Create a default task
        default_start = datetime.now()
        duration_days = simpledialog.askinteger(
            "Task Duration", "Enter duration in days:", parent=self.master, minvalue=1, maxvalue=365, initialvalue=7
        )
        
        if duration_days is None:  # User cancelled
            return
        
        default_end = default_start + timedelta(days=duration_days)
        
        # Get task name
        task_name = simpledialog.askstring(
            "New Task", "Enter task name:", parent=self.master
        )
        
        if not task_name:
            return
        
        # Create and add task
        task = Task.create_task(
            name=task_name,
            start_date=default_start,
            end_date=default_end
        )
        
        # Use undo/redo if available
        if self.undo_redo_manager:
            from gantt_app.utils.undoredo import create_add_task_command
            command = create_add_task_command(self.project, task)
            if self.undo_redo_manager.execute(command):
                self.update_undo_redo_buttons()
                if self.on_project_changed:
                    self.on_project_changed()
        else:
            # Fallback to direct addition
            self.project.add_task(task)
            if self.on_project_changed:
                self.on_project_changed()
    
    def add_milestone(self):
        """Add a new milestone to the project with undo support."""
        # Get milestone name
        milestone_name = simpledialog.askstring(
            "New Milestone", "Enter milestone name:", parent=self.master
        )
        
        if not milestone_name:
            return
        
        # Get milestone date
        date_str = simpledialog.askstring(
            "Milestone Date", "Enter date (YYYY-MM-DD):", 
            parent=self.master, initialvalue=datetime.now().strftime('%Y-%m-%d')
        )
        
        if not date_str:
            return
        
        try:
            milestone_date = datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            messagebox.showerror("Invalid Date", "Please use YYYY-MM-DD format")
            return
        
        # Create and add milestone
        milestone = Task.create_milestone(
            name=milestone_name,
            date=milestone_date
        )
        
        # Use undo/redo if available
        if self.undo_redo_manager:
            from gantt_app.utils.undoredo import create_add_task_command
            command = create_add_task_command(self.project, milestone)
            if self.undo_redo_manager.execute(command):
                self.update_undo_redo_buttons()
                if self.on_project_changed:
                    self.on_project_changed()
        else:
            # Fallback to direct addition
            self.project.add_task(milestone)
            if self.on_project_changed:
                self.on_project_changed()
    
    def add_subtask(self):
        """Add a new subtask to the project with undo support."""
        from gantt_app.models import Task
        
        # Check if there are any tasks to be a parent
        root_tasks = self.project.get_root_tasks()
        if not root_tasks:
            messagebox.showwarning("No Parent Task", "You need at least one task to create a subtask.")
            return
        
        # Get subtask name
        subtask_name = simpledialog.askstring(
            "New Sub-Task", "Enter subtask name:", parent=self.master
        )
        
        if not subtask_name:
            return
        
        # Let user select parent task
        parent_task = self._select_parent_task(root_tasks)
        if not parent_task:
            return
        
        # Get duration in days
        duration_days = simpledialog.askinteger(
            "Sub-Task Duration", "Enter duration in days:", 
            parent=self.master, minvalue=1, maxvalue=365, initialvalue=1
        )
        
        if duration_days is None:  # User cancelled
            return
        
        # Calculate end date based on parent start date
        parent_start = parent_task.start_date
        subtask_end = parent_start + timedelta(days=duration_days)
        
        # Create subtask
        subtask = Task.create_subtask(
            name=subtask_name,
            parent_task=parent_task,
            end_date=subtask_end
        )
        
        # Use undo/redo if available
        if self.undo_redo_manager:
            from gantt_app.utils.undoredo import create_add_task_command
            command = create_add_task_command(self.project, subtask)
            if self.undo_redo_manager.execute(command):
                self.update_undo_redo_buttons()
                if self.on_project_changed:
                    self.on_project_changed()
        else:
            # Fallback to direct addition
            self.project.add_task(subtask)
            if self.on_project_changed:
                self.on_project_changed()
    
    def _select_parent_task(self, root_tasks: List[Task]) -> Optional[Task]:
        """
        Show a dialog to select a parent task for a subtask.
        
        PARAMETERS:
        -----------
        root_tasks : List[Task]
            List of root tasks that can be parents
        
        RETURNS:
        --------
        Optional[Task]
            The selected parent task, or None if cancelled
        
        DEVELOPMENT NOTES:
        ------------------
        Uses a dictionary to map listbox indices to task objects.
        This provides a clean way to retrieve the selected task.
        """
        # Create a simple dialog with a listbox
        dialog = tk.Toplevel(self.master)
        dialog.title("Select Parent Task")
        dialog.geometry("400x300")
        dialog.transient(self.master)
        dialog.grab_set()
        
        # Add label
        label = tk.Label(dialog, text="Select a parent task for the subtask:")
        label.pack(pady=10)
        
        # Create listbox
        listbox = tk.Listbox(dialog, width=50, height=10)
        listbox.pack(padx=20, pady=10)
        
        # Store mapping from index to task
        task_map = {}
        
        # Add tasks to listbox
        for i, task in enumerate(root_tasks):
            display_name = f"{task.name} ({task.start_date.strftime('%Y-%m-%d')})"
            listbox.insert(tk.END, display_name)
            task_map[i] = task
        
        # Add buttons
        button_frame = tk.Frame(dialog)
        button_frame.pack(pady=10)
        
        selected_task = [None]  # Use list to allow modification in nested function
        
        def on_ok():
            selection = listbox.curselection()
            if selection:
                idx = selection[0]
                selected_task[0] = task_map.get(idx)
            dialog.destroy()
        
        def on_cancel():
            dialog.destroy()
        
        ok_btn = tk.Button(button_frame, text="OK", command=on_ok)
        ok_btn.pack(side=tk.LEFT, padx=10)
        
        cancel_btn = tk.Button(button_frame, text="Cancel", command=on_cancel)
        cancel_btn.pack(side=tk.LEFT, padx=10)
        
        # Wait for dialog to close
        dialog.wait_window()
        
        return selected_task[0]
    
    def edit_project_info(self):
        """Edit project information with undo support."""
        new_name = simpledialog.askstring(
            "Project Info", "Enter project name:", 
            parent=self.master, initialvalue=self.project.name
        )
        
        if new_name and new_name != self.project.name:
            if self.undo_redo_manager:
                from gantt_app.utils.undoredo import create_update_project_name_command
                command = create_update_project_name_command(self.project, self.project.name, new_name)
                if self.undo_redo_manager.execute(command):
                    self.update_undo_redo_buttons()
                    if self.on_project_changed:
                        self.on_project_changed()
            else:
                # Fallback to direct update
                self.project.name = new_name
                if self.on_project_changed:
                    self.on_project_changed()
    
    def save_project(self):
        """Save the current project to a JSON file."""
        # Ask for file path
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            title="Save Project"
        )
        
        if not file_path:
            return
        
        # Save project
        if save_project(self.project, file_path):
            messagebox.showinfo("Success", "Project saved successfully!")
        else:
            messagebox.showerror("Error", "Failed to save project")
    
    def load_project(self):
        """Load a project from a JSON file."""
        # Ask for file path
        file_path = filedialog.askopenfilename(
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            title="Load Project"
        )
        
        if not file_path:
            return
        
        # Load project
        project = load_project(file_path)
        if project:
            # Replace current project
            self.project.name = project.name
            self.project.tasks = project.tasks
            self.project.start_date = project.start_date
            self.project.end_date = project.end_date
            
            # Clear undo/redo history when loading a new project
            if self.undo_redo_manager:
                self.undo_redo_manager.clear()
                self.update_undo_redo_buttons()
            
            if self.on_project_changed:
                self.on_project_changed()
        else:
            messagebox.showerror("Error", "Failed to load project")
    
    def new_project(self):
        """Create a new empty project."""
        new_name = tk.simpledialog.askstring(
            "New Project", "Enter project name:", 
            parent=self.master, initialvalue="New Project"
        )
        
        if new_name:
            # Clear current project
            self.project.name = new_name
            self.project.tasks = []
            self.project.start_date = None
            self.project.end_date = None
            
            # Clear undo/redo history for new project
            if self.undo_redo_manager:
                self.undo_redo_manager.clear()
                self.update_undo_redo_buttons()
            
            if self.on_project_changed:
                self.on_project_changed()
    
    def import_gan(self):
        """Import a GanttProject (.gan) file."""
        # Ask for file path
        file_path = filedialog.askopenfilename(
            filetypes=[("GanttProject Files", "*.gan"), ("All Files", "*.*")],
            title="Import GAN File"
        )
        
        if not file_path:
            return
        
        # Import GAN file
        project = import_gan_file(file_path)
        if project:
            # Replace current project
            self.project.name = project.name
            self.project.tasks = project.tasks
            self.project.start_date = project.start_date
            self.project.end_date = project.end_date
            
            # Clear undo/redo history when importing
            if self.undo_redo_manager:
                self.undo_redo_manager.clear()
                self.update_undo_redo_buttons()
            
            if self.on_project_changed:
                self.on_project_changed()
            
            messagebox.showinfo("Success", f"Imported {len(project.tasks)} tasks from GAN file")
        else:
            messagebox.showerror("Error", "Failed to import GAN file")
    
    def import_mpp(self):
        """Import a Microsoft Project (.mpp) file."""
        # Ask for file path
        file_path = filedialog.askopenfilename(
            filetypes=[("Microsoft Project Files", "*.mpp"), ("All Files", "*.*")],
            title="Import MPP File"
        )
        
        if not file_path:
            return
        
        # Import MPP file
        project = import_mpp_file(file_path)
        if project:
            # Replace current project
            self.project.name = project.name
            self.project.tasks = project.tasks
            self.project.start_date = project.start_date
            self.project.end_date = project.end_date
            
            # Clear undo/redo history when importing
            if self.undo_redo_manager:
                self.undo_redo_manager.clear()
                self.update_undo_redo_buttons()
            
            if self.on_project_changed:
                self.on_project_changed()
            
            tk.messagebox.showinfo("Success", f"Imported {len(project.tasks)} tasks from MPP file")
        else:
            messagebox.showerror("Error", "Failed to import MPP file (Tasklib or JPype + mpxj required)")
    
    def import_mermaid(self):
        """Import a Mermaid (.mmd or .mermaid) file."""
        # Ask for file path
        file_path = filedialog.askopenfilename(
            filetypes=[("Mermaid Files", "*.mmd;*.mermaid"), ("All Files", "*.*")],
            title="Import Mermaid File"
        )
        
        if not file_path:
            return
        
        # Import Mermaid file
        project = import_mermaid_file(file_path)
        if project:
            # Replace current project
            self.project.name = project.name
            self.project.tasks = project.tasks
            self.project.start_date = project.start_date
            self.project.end_date = project.end_date
            
            # Clear undo/redo history when importing
            if self.undo_redo_manager:
                self.undo_redo_manager.clear()
                self.update_undo_redo_buttons()
            
            if self.on_project_changed:
                self.on_project_changed()
            
            messagebox.showinfo("Success", f"Imported {len(project.tasks)} tasks from Mermaid file")
        else:
            messagebox.showerror("Error", "Failed to import Mermaid file")
    
    def export_mermaid(self):
        """Export the current project to a Mermaid (.mmd) file."""
        # Ask for file path
        file_path = filedialog.asksaveasfilename(
            defaultextension=".mmd",
            filetypes=[("Mermaid Files", "*.mmd"), ("All Files", "*.*")],
            title="Export Mermaid File"
        )
        
        if not file_path:
            return
        
        # Export project to Mermaid
        if export_project_to_mermaid(self.project, file_path):
            messagebox.showinfo("Success", "Project exported to Mermaid successfully!")
        else:
            messagebox.showerror("Error", "Failed to export project to Mermaid")
    
    def export_png(self):
        """Export the Gantt chart to a PNG file."""
        if self.gantt_chart is None:
            messagebox.showerror("Error", "Gantt chart not available for export")
            return
        
        # Ask for file path
        file_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG Files", "*.png"), ("All Files", "*.*")],
            title="Export Gantt Chart to PNG"
        )
        
        if not file_path:
            return
        
        # Export Gantt chart to PNG
        if self.gantt_chart.export_to_png(file_path):
            messagebox.showinfo("Success", "Gantt chart exported to PNG successfully!")
        else:
            messagebox.showerror("Error", "Failed to export Gantt chart to PNG")
    
    def export_pdf(self):
        """Export the Gantt chart to a PDF file."""
        if self.gantt_chart is None:
            messagebox.showerror("Error", "Gantt chart not available for export")
            return
        
        # Ask for file path
        file_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")],
            title="Export Gantt Chart to PDF"
        )
        
        if not file_path:
            return
        
        # Export Gantt chart to PDF
        if self.gantt_chart.export_to_pdf(file_path):
            messagebox.showinfo("Success", "Gantt chart exported to PDF successfully!")
        else:
            messagebox.showerror("Error", "Failed to export Gantt chart to PDF")
    
    def set_gantt_chart(self, gantt_chart):
        """Set the Gantt chart reference for export functionality."""
        self.gantt_chart = gantt_chart
    
    def set_undo_redo_manager(self, manager: UndoRedoManager):
        """Set the undo/redo manager."""
        self.undo_redo_manager = manager
        self.update_undo_redo_buttons()
    
    def update_undo_redo_buttons(self):
        """Update the state of undo and redo buttons."""
        if self.undo_redo_manager:
            self.undo_btn.configure(state=tk.NORMAL if self.undo_redo_manager.can_undo() else tk.DISABLED)
            self.redo_btn.configure(state=tk.NORMAL if self.undo_redo_manager.can_redo() else tk.DISABLED)
    
    def undo(self):
        """Undo the last action."""
        if self.undo_redo_manager and self.undo_redo_manager.can_undo():
            if self.undo_redo_manager.undo():
                self.update_undo_redo_buttons()
                if self.on_project_changed:
                    self.on_project_changed()
    
    def redo(self):
        """Redo the last undone action."""
        if self.undo_redo_manager and self.undo_redo_manager.can_redo():
            if self.undo_redo_manager.redo():
                self.update_undo_redo_buttons()
                if self.on_project_changed:
                    self.on_project_changed()
    
    def toggle_theme(self):
        """Toggle between light and dark themes."""
        current_theme = ctk.get_appearance_mode()
        new_theme = "dark" if current_theme == "light" else "light"
        ctk.set_appearance_mode(new_theme)
    
    def set_project(self, project: Project):
        """Set a new project for the toolbar."""
        self.project = project
