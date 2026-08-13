"""
Toolbar for the Gantt Project Management Tool.

Contains action buttons for managing the project.
"""

import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
from datetime import datetime, timedelta
from typing import Optional, Callable, List, Dict

import customtkinter as ctk

from gantt_app.models import Task, Project
from gantt_app.utils.file_io import JSONFileIO, save_project, load_project
from gantt_app.utils.gan_importer import import_gan_file
from gantt_app.utils.mpp_importer import import_mpp_file
from gantt_app.utils.mermaid_importer import import_mermaid_file
from gantt_app.utils.xlsx_importer import import_xlsx_file
from gantt_app.utils.mermaid_exporter import export_project_to_mermaid
from gantt_app.utils.xlsx_exporter import export_project_to_xlsx
from gantt_app.utils.undoredo import UndoRedoManager
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


class DropdownButton(ctk.CTkButton):
    """Custom dropdown button that shows a menu when clicked."""
    
    def __init__(self, master, text: str, menu_items: List[Dict], 
                 width: int = 100, fg_color: str = None, hover_color: str = None,
                 **kwargs):
        """
        Create a dropdown button.
        
        PARAMETERS:
        -----------
        master : widget
            Parent widget
        text : str
            Button text
        menu_items : List[Dict]
            List of menu item dictionaries with 'text' and 'command' keys
        width : int
            Button width
        fg_color : str
            Button foreground color
        hover_color : str
            Button hover color
        **kwargs : dict
            Additional keyword arguments for CTkButton
        """
        # Set the command before calling super().__init__
        kwargs['command'] = self._show_menu
        
        super().__init__(master, text=text, width=width, 
                        fg_color=fg_color, hover_color=hover_color, **kwargs)
        
        self.menu_items = menu_items
        self.menu_window = None
    
    def _show_menu(self):
        """Show the dropdown menu."""
        # Close existing menu if any
        if self.menu_window and self.menu_window.winfo_exists():
            self.menu_window.destroy()
        
        # Create a popup menu window
        self.menu_window = ctk.CTkToplevel(self.master)
        self.menu_window.title("")
        self.menu_window.geometry("200x50")  # Will be adjusted based on content
        
        # Remove window decorations
        self.menu_window.overrideredirect(True)
        self.menu_window.attributes("-topmost", True)
        
        # Position the menu below the button
        button_x = self.winfo_rootx()
        button_y = self.winfo_rooty()
        button_width = self.winfo_width()
        button_height = self.winfo_height()
        
        self.menu_window.geometry(f"220x{min(len(self.menu_items) * 40 + 10, 400)}")
        self.menu_window.geometry(f"+{button_x}+{button_y + button_height}")
        
        # Create menu frame
        menu_frame = ctk.CTkFrame(self.menu_window, fg_color="#2b2b2b", 
                                  corner_radius=0, border_width=1, border_color="#444444")
        menu_frame.pack(fill=tk.BOTH, expand=True)
        
        # Add menu items
        for i, item in enumerate(self.menu_items):
            btn = ctk.CTkButton(
                menu_frame, 
                text=item['text'],
                command=lambda cmd=item['command']: self._on_menu_select(cmd),
                width=200,
                height=35,
                fg_color="#3b3b3b",
                hover_color="#4a4a4a",
                anchor="w",
                corner_radius=0,
                padding_x=15
            )
            btn.pack(fill=tk.X, pady=(5 if i == 0 else 0, 5 if i == len(self.menu_items) - 1 else 0))
            
            # Bind mouse enter/leave for better UX
            btn.bind("<Enter>", lambda e, b=btn: b.configure(fg_color="#4a4a4a"))
            btn.bind("<Leave>", lambda e, b=btn: b.configure(fg_color="#3b3b3b"))
        
        # Handle click outside to close menu
        self.menu_window.bind("<Button-1>", self._on_click_outside)
        self.menu_window.bind("<FocusOut>", self._on_focus_out)
        
        # Make it transient to the main window
        self.menu_window.transient(self.master)
        self.menu_window.grab_set()
    
    def _on_menu_select(self, command):
        """Handle menu item selection."""
        if self.menu_window:
            self.menu_window.destroy()
            self.menu_window = None
        
        if command:
            command()
    
    def _on_click_outside(self, event):
        """Close menu if clicked outside."""
        # Check if click is inside the menu
        if self.menu_window:
            menu_x = self.menu_window.winfo_rootx()
            menu_y = self.menu_window.winfo_rooty()
            menu_width = self.menu_window.winfo_width()
            menu_height = self.menu_window.winfo_height()
            
            if (event.x_root < menu_x or event.x_root >= menu_x + menu_width or
                event.y_root < menu_y or event.y_root >= menu_y + menu_height):
                self.menu_window.destroy()
                self.menu_window = None
    
    def _on_focus_out(self, event):
        """Close menu when focus is lost."""
        if self.menu_window:
            self.menu_window.destroy()
            self.menu_window = None


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
        
        # Create dropdown button
        self._create_create_buttons()
        
        # Project dropdown button
        self._create_project_buttons()
        
        # Import/Export buttons (now with dropdowns)
        self._create_import_export_buttons()
        
        # Theme toggle
        self._create_theme_toggle()
    
    def _create_create_buttons(self):
        """Create the Create dropdown button for task creation."""
        create_frame = ctk.CTkFrame(self)
        create_frame.pack(side=tk.LEFT, padx=5, pady=5)
        
        # Create dropdown button for Task, Sub-Task, Milestone
        create_menu_items = [
            {"text": "Task...", "command": self.add_task},
            {"text": "Sub-Task...", "command": self.add_subtask},
            {"text": "Milestone...", "command": self.add_milestone}
        ]
        
        create_btn = DropdownButton(
            create_frame, 
            text="Create", 
            menu_items=create_menu_items,
            width=100,
            fg_color="#2ecc71",
            hover_color="#27ae60"
        )
        create_btn.pack(side=tk.LEFT, padx=5, pady=5)
    
    def _create_project_buttons(self):
        """Create dropdown button for project file operations."""
        project_frame = ctk.CTkFrame(self)
        project_frame.pack(side=tk.LEFT, padx=5, pady=5)
        
        # Project dropdown button for New, Load, Save
        project_menu_items = [
            {"text": "New Project...", "command": self.new_project},
            {"text": "Load Project...", "command": self.load_project},
            {"text": "Save Project...", "command": self.save_project}
        ]
        
        project_btn = DropdownButton(
            project_frame,
            text="Project",
            menu_items=project_menu_items,
            width=100,
            fg_color="#f39c12",
            hover_color="#d35400"
        )
        project_btn.pack(side=tk.LEFT, padx=5, pady=5)
        
        # Project Info button
        project_info_btn = ctk.CTkButton(
            project_frame, text="Project Info",
            command=self.edit_project_info, width=100
        )
        project_info_btn.pack(side=tk.LEFT, padx=5, pady=5)
    

    
    def _create_import_export_buttons(self):
        """Create dropdown buttons for importing and exporting files."""
        import_frame = ctk.CTkFrame(self)
        import_frame.pack(side=tk.LEFT, padx=5, pady=5)
        
        # Import dropdown button
        import_menu_items = [
            {"text": "MPP...", "command": self.import_mpp},
            {"text": "GAN...", "command": self.import_gan},
            {"text": "Mermaid...", "command": self.import_mermaid},
            {"text": "XLSX...", "command": self.import_xlsx}
        ]
        
        import_btn = DropdownButton(
            import_frame,
            text="Import",
            menu_items=import_menu_items,
            width=100,
            fg_color="#3498db",
            hover_color="#2980b9"
        )
        import_btn.pack(side=tk.LEFT, padx=5, pady=5)
        
        # Export dropdown button
        export_menu_items = [
            {"text": "Mermaid...", "command": self.export_mermaid},
            {"text": "PNG...", "command": self.export_png},
            {"text": "PDF...", "command": self.export_pdf},
            {"text": "XLSX...", "command": self.export_xlsx}
        ]
        
        export_btn = DropdownButton(
            import_frame,
            text="Export",
            menu_items=export_menu_items,
            width=100,
            fg_color="#9b59b6",
            hover_color="#8e44ad"
        )
        export_btn.pack(side=tk.LEFT, padx=5, pady=5)
    
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
        """Create the theme toggle and log buttons."""
        theme_frame = ctk.CTkFrame(self)
        theme_frame.pack(side=tk.RIGHT, padx=5, pady=5)

        # Theme toggle
        self.theme_toggle = ctk.CTkButton(
            theme_frame, text="Toggle Theme",
            command=self.toggle_theme, width=100
        )
        self.theme_toggle.pack(side=tk.LEFT, padx=5, pady=5)

        # Log viewer
        self.log_button = ctk.CTkButton(
            theme_frame, text="Log",
            command=self.show_log, width=70
        )
        self.log_button.pack(side=tk.LEFT, padx=5, pady=5)

    def show_log(self):
        """Open the application log window."""
        try:
            from gantt_app.views.log_window import LogWindow
            LogWindow.show(self.winfo_toplevel())
            logger.debug("Log window opened")
        except Exception as e:
            logger.exception("Could not open the log window")
            messagebox.showerror(
                "Log Unavailable",
                f"Could not open the log window:\n{e}"
            )

    def add_task(self):
        """Add a new task to the project with undo support."""
        # Create a default task
        default_start = datetime.now()
        duration_days = simpledialog.askinteger(
            "Task Duration", "Enter duration in days:", parent=self.master, minvalue=1, maxvalue=365, initialvalue=7
        )
        
        if duration_days is None:  # User cancelled
            return
        
        # Durations are inclusive: a 1 day task starts and ends on the same
        # day, matching Task.duration_days and every importer
        default_end = default_start + timedelta(days=duration_days - 1)
        
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
        
        # Any task can be a parent, including an existing sub-task, so that
        # hierarchies deeper than two levels can be built
        candidate_parents = self._candidate_parent_tasks()
        if not candidate_parents:
            messagebox.showwarning("No Parent Task", "You need at least one task to create a subtask.")
            return

        # Get subtask name
        subtask_name = simpledialog.askstring(
            "New Sub-Task", "Enter subtask name:", parent=self.master
        )

        if not subtask_name:
            return

        # Let user select parent task
        parent_task = self._select_parent_task(candidate_parents)
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
        # Inclusive duration, as in add_task
        subtask_end = parent_start + timedelta(days=duration_days - 1)
        
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
    
    def _candidate_parent_tasks(self) -> List[Task]:
        """
        Get the tasks that may act as a parent, in hierarchy order.

        RETURNS:
        --------
        List[Task]
            Every non-milestone task, each parent immediately followed by its
            own descendants, so the selection list reads as a tree.

        DEVELOPMENT NOTES:
        ------------------
        Sub-tasks are included, which is what allows hierarchies deeper than
        two levels to be built from the UI. Imported files (GanttProject in
        particular) already nest several levels deep, so restricting this to
        root tasks made the UI unable to express what the importers produce.
        Milestones are excluded because they are single-date markers with no
        span for a child to sit inside.
        """
        by_parent = {}
        for task in self.project.tasks:
            by_parent.setdefault(task.parent_task_id, []).append(task)

        for group in by_parent.values():
            group.sort(key=lambda t: t.start_date)

        ordered: List[Task] = []
        visited = set()

        def walk(parent_id):
            for task in by_parent.get(parent_id, []):
                if task.id in visited:
                    continue
                visited.add(task.id)
                if not task.is_milestone:
                    ordered.append(task)
                walk(task.id)

        walk(None)

        # Include anything unreachable from the root (orphaned parent reference)
        for task in self.project.tasks:
            if task.id not in visited and not task.is_milestone:
                ordered.append(task)

        return ordered

    def _task_depth(self, task: Task) -> int:
        """Get how many levels down a task sits, 0 for a root task."""
        depth = 0
        current = task
        seen = {current.id}
        while current.parent_task_id:
            parent = self.project.get_task_by_id(current.parent_task_id)
            if parent is None or parent.id in seen:
                break
            seen.add(parent.id)
            current = parent
            depth += 1
        return depth

    def _select_parent_task(self, candidate_tasks: List[Task]) -> Optional[Task]:
        """
        Show a dialog to select a parent task for a subtask.

        PARAMETERS:
        -----------
        candidate_tasks : List[Task]
            Tasks that can be parents, in hierarchy order

        RETURNS:
        --------
        Optional[Task]
            The selected parent task, or None if cancelled

        DEVELOPMENT NOTES:
        ------------------
        Uses a dictionary to map listbox indices to task objects.
        This provides a clean way to retrieve the selected task.
        Entries are indented by depth so nesting is visible when picking a
        sub-task as the parent.
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
        
        # Add tasks to listbox, indented by how deep they sit
        for i, task in enumerate(candidate_tasks):
            indent = "    " * self._task_depth(task)
            display_name = f"{indent}{task.name} ({task.start_date.strftime('%Y-%m-%d')})"
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
            messagebox.showerror(
                "Error",
                "Failed to import MPP file.\n\n"
                "MS Project import needs the optional Tasklib reader:\n"
                "    pip install tasklib"
            )
    
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
    
    def import_xlsx(self):
        """Import an Excel (.xlsx) project plan."""
        # Ask for file path
        file_path = filedialog.askopenfilename(
            filetypes=[("Excel Files", "*.xlsx;*.xlsm"), ("All Files", "*.*")],
            title="Import XLSX File"
        )

        if not file_path:
            return

        # Import XLSX file
        project = import_xlsx_file(file_path)
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

            messagebox.showinfo("Success", f"Imported {len(project.tasks)} tasks from XLSX file")
        else:
            messagebox.showerror(
                "Error",
                "Failed to import XLSX file.\n\n"
                "Check that openpyxl is installed and that the sheet has a "
                "header row naming a task column plus a start date or duration."
            )

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
    
    def export_xlsx(self):
        """Export the project to an Excel XLSX file."""
        # Ask for file path
        file_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel Files", "*.xlsx"), ("All Files", "*.*")],
            title="Export Project to XLSX"
        )
        
        if not file_path:
            return
        
        # Export project to XLSX
        if export_project_to_xlsx(self.project, file_path):
            messagebox.showinfo("Success", "Project exported to XLSX successfully!")
        else:
            messagebox.showerror(
                "Error",
                "Failed to export project to XLSX.\n\n"
                "Check that openpyxl is installed."
            )
    
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
