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

#: Toolbar palette. A single standard blue with white text, rather than the
#: pure #0000FF buttons and dark green menu rows used previously - saturated
#: primaries read as unfinished and gave poor contrast against the dark menu
#: background.
ACCENT = "#1f6aa5"          # buttons and menu rows
ACCENT_HOVER = "#17537f"    # hover / pressed
ACCENT_TEXT = "#ffffff"
MENU_BG = "#1f2937"         # menu panel behind the rows
MENU_BORDER = "#3b4759"
LOG_ACCENT = "#b8860b"      # the Log button stays distinct
LOG_ACCENT_HOVER = "#966d09"


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
        self._dismiss_binding = None
    
    #: The dropdown currently showing its menu, if any. Only one opens at a
    #: time, so clicking a second button dismisses the first.
    _open_menu_owner = None

    ITEM_HEIGHT = 34
    MENU_WIDTH = 220
    MENU_PADDING = 8

    def _show_menu(self):
        """
        Show the dropdown menu, or close it if it is already open.

        DEVELOPMENT NOTES:
        ------------------
        The whole build runs inside a try/except that tears the popup down on
        failure. An earlier version passed an unsupported argument to
        CTkButton; the exception escaped part-way through, leaving an empty,
        undecorated, always-on-top window with no bindings and no way to
        dismiss it. Every click on a menu button added another one.
        """
        # A second click on the same button closes the menu
        if self.menu_window is not None and self._menu_is_alive():
            self.close_menu()
            return

        DropdownButton.close_open_menu()

        try:
            self._build_menu()
        except Exception:
            logger.exception("Could not build the %r menu", self.cget("text"))
            self.close_menu()

    def _menu_is_alive(self) -> bool:
        """Check whether the popup window still exists."""
        try:
            return bool(self.menu_window and self.menu_window.winfo_exists())
        except tk.TclError:
            return False

    def _build_menu(self):
        """Create and populate the popup window."""
        self.menu_window = ctk.CTkToplevel(self.master)
        DropdownButton._open_menu_owner = self

        self.menu_window.title("")
        self.menu_window.overrideredirect(True)
        self.menu_window.attributes("-topmost", True)

        # Position directly below the button
        button_x = self.winfo_rootx()
        button_y = self.winfo_rooty()
        button_height = self.winfo_height()

        height = len(self.menu_items) * self.ITEM_HEIGHT + self.MENU_PADDING * 2
        self.menu_window.geometry(
            f"{self.MENU_WIDTH}x{height}+{button_x}+{button_y + button_height}"
        )

        menu_frame = ctk.CTkFrame(
            self.menu_window, fg_color=MENU_BG,
            corner_radius=0, border_width=1, border_color=MENU_BORDER
        )
        menu_frame.pack(fill=tk.BOTH, expand=True)

        for item in self.menu_items:
            btn = ctk.CTkButton(
                menu_frame,
                text=item['text'],
                command=lambda cmd=item.get('command'): self._on_menu_select(cmd),
                height=self.ITEM_HEIGHT - 4,
                fg_color=ACCENT,
                hover_color=ACCENT_HOVER,
                text_color=ACCENT_TEXT,
                anchor="w",
                corner_radius=0
            )
            btn.pack(fill=tk.X, padx=self.MENU_PADDING, pady=2)

        # Dismiss on Escape, on losing focus, or on a click anywhere else
        self.menu_window.bind("<Escape>", lambda _e: self.close_menu())
        self.menu_window.bind("<FocusOut>", lambda _e: self.close_menu())

        toplevel = self.winfo_toplevel()
        self._dismiss_binding = toplevel.bind(
            "<Button-1>", self._on_click_elsewhere, add="+"
        )

        self.menu_window.focus_set()

    def _on_click_elsewhere(self, event):
        """Close the menu when the click lands outside it."""
        if not self._menu_is_alive():
            return

        # A click on this button is handled by _show_menu's toggle
        if event.widget is self:
            return

        self.close_menu()

    def close_menu(self):
        """
        Dismiss the menu and release everything it registered.

        DEVELOPMENT NOTES:
        ------------------
        Safe to call when no menu is open, and never raises: it runs from
        window teardown, where a half-destroyed widget tree is normal.
        """
        binding = getattr(self, '_dismiss_binding', None)
        if binding is not None:
            try:
                self.winfo_toplevel().unbind("<Button-1>", binding)
            except tk.TclError:
                pass
            self._dismiss_binding = None

        if self.menu_window is not None:
            try:
                self.menu_window.destroy()
            except tk.TclError:
                pass
            self.menu_window = None

        if DropdownButton._open_menu_owner is self:
            DropdownButton._open_menu_owner = None

    @classmethod
    def close_open_menu(cls):
        """Close whichever dropdown is currently showing a menu."""
        owner = cls._open_menu_owner
        if owner is not None:
            owner.close_menu()

    def _on_menu_select(self, command):
        """Handle menu item selection."""
        self.close_menu()

        if command:
            try:
                command()
            except Exception:
                logger.exception("Menu action failed")
                messagebox.showerror(
                    "Action Failed",
                    "That action could not be completed. "
                    "See the Log window for details."
                )


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
        # Create dropdown button
        self._create_create_buttons()
        
        # Project dropdown button
        self._create_project_buttons()
        
        # Import/Export buttons (now with dropdowns)
        self._create_import_export_buttons()
        
        # Edit dropdown button
        self._create_edit_buttons()
        
        # View dropdown button
        self._create_view_buttons()
        
        # Theme toggle and Log buttons
        self._create_theme_log_buttons()
    
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
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color="white"
        )
        create_btn.pack(side=tk.LEFT, padx=5, pady=5)
    
    def _create_edit_buttons(self):
        """Create the Edit dropdown button for undo/redo operations."""
        edit_frame = ctk.CTkFrame(self)
        edit_frame.pack(side=tk.LEFT, padx=5, pady=5)
        
        # Edit dropdown button for Undo, Redo
        edit_menu_items = [
            {"text": "Undo", "command": self.undo},
            {"text": "Redo", "command": self.redo}
        ]
        
        edit_btn = DropdownButton(
            edit_frame,
            text="Edit",
            menu_items=edit_menu_items,
            width=100,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color="white"
        )
        edit_btn.pack(side=tk.LEFT, padx=5, pady=5)
    
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
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color="white"
        )
        project_btn.pack(side=tk.LEFT, padx=5, pady=5)
    
    def _create_view_buttons(self):
        """Create the View dropdown button for Project Info, Toggle Theme, and Gantt Chart settings."""
        view_frame = ctk.CTkFrame(self)
        view_frame.pack(side=tk.LEFT, padx=5, pady=5)
        
        # View dropdown button for Project Info, Toggle Theme, Gantt Chart settings
        view_menu_items = [
            {"text": "Project Info", "command": self.edit_project_info},
            {"text": "Toggle Theme", "command": self.toggle_theme},
            {"text": "Gantt Chart Settings", "command": self.open_gantt_chart_settings}
        ]
        
        view_btn = DropdownButton(
            view_frame,
            text="View",
            menu_items=view_menu_items,
            width=100,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color="white"
        )
        view_btn.pack(side=tk.LEFT, padx=5, pady=5)
    

    
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
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color="white"
        )
        import_btn.pack(side=tk.LEFT, padx=5, pady=5)
        
        # Export dropdown button
        export_menu_items = [
            {"text": "Mermaid...", "command": self.export_mermaid},
            {"text": "HTML...", "command": self.export_html},
            {"text": "PNG...", "command": self.export_png},
            {"text": "PDF...", "command": self.export_pdf},
            {"text": "XLSX...", "command": self.export_xlsx}
        ]
        
        export_btn = DropdownButton(
            import_frame,
            text="Export",
            menu_items=export_menu_items,
            width=100,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color="white"
        )
        export_btn.pack(side=tk.LEFT, padx=5, pady=5)
    
    def _create_theme_log_buttons(self):
        """Create the log button."""
        theme_frame = ctk.CTkFrame(self)
        theme_frame.pack(side=tk.RIGHT, padx=5, pady=5)

        # Log viewer
        self.log_button = ctk.CTkButton(
            theme_frame, text="Log",
            command=self.show_log, width=70,
            fg_color=LOG_ACCENT,
            hover_color=LOG_ACCENT_HOVER,
            text_color="white"
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
        from gantt_app.views.task_list import CreateTaskDialog
        
        # Open create task dialog
        dialog = CreateTaskDialog(
            self.master, self.project,
            task_type="Task",
            on_save=self._save_new_task
        )
        dialog.wait_window()
    
    def _save_new_task(self, task: Task):
        """Handle saving a newly created task with undo support."""
        # Use undo/redo if available
        if self.undo_redo_manager:
            from gantt_app.utils.undoredo import create_add_task_command
            command = create_add_task_command(self.project, task)
            logger.info("Created %s %s %r starting %s",
                        "milestone" if task.is_milestone else task.task_type.lower(),
                        task.id, task.name, task.start_date.date())
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
        from gantt_app.views.task_list import CreateTaskDialog
        
        # Open create milestone dialog
        dialog = CreateTaskDialog(
            self.master, self.project,
            task_type="Milestone",
            on_save=self._save_new_task
        )
        dialog.wait_window()
    
    def add_subtask(self):
        """Add a new subtask to the project with undo support."""
        from gantt_app.models import Task
        from gantt_app.views.task_list import CreateTaskDialog
        
        # Any task can be a parent, including an existing sub-task, so that
        # hierarchies deeper than two levels can be built
        candidate_parents = self._candidate_parent_tasks()
        if not candidate_parents:
            messagebox.showwarning("No Parent Task", "You need at least one task to create a subtask.")
            return
        
        # If only one parent, use it directly
        if len(candidate_parents) == 1:
            parent_task = candidate_parents[0]
            dialog = CreateTaskDialog(
                self.master, self.project,
                task_type="Sub-Task",
                parent_task=parent_task,
                on_save=self._save_new_task
            )
            dialog.wait_window()
        else:
            # Let user select parent first, then open full dialog
            parent_task = self._select_parent_task(candidate_parents)
            if parent_task:
                dialog = CreateTaskDialog(
                    self.master, self.project,
                    task_type="Sub-Task",
                    parent_task=parent_task,
                    on_save=self._save_new_task
                )
                dialog.wait_window()
    
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
        logger.info("Saving project %r to %s", self.project.name, file_path)
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
        logger.info("Loading project from %s", file_path)
        project = load_project(file_path)
        if project:
            # Replace current project
            self.project.name = project.name
            project.renumber_task_ids()
            logger.info("Imported %d task(s) from %s", len(project.tasks), file_path)
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
            project.renumber_task_ids()
            logger.info("Imported %d task(s) from %s", len(project.tasks), file_path)
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
            project.renumber_task_ids()
            logger.info("Imported %d task(s) from %s", len(project.tasks), file_path)
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
            project.renumber_task_ids()
            logger.info("Imported %d task(s) from %s", len(project.tasks), file_path)
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
            project.renumber_task_ids()
            logger.info("Imported %d task(s) from %s", len(project.tasks), file_path)
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
        
        logger.info("Exporting the Gantt chart to PNG: %s", file_path)
        if self.gantt_chart.export_to_png(file_path):
            messagebox.showinfo("Success", "Gantt chart exported to PNG successfully!")
        else:
            self._report_static_export_failure("PNG")
    
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
        
        logger.info("Exporting the Gantt chart to PDF: %s", file_path)
        if self.gantt_chart.export_to_pdf(file_path):
            messagebox.showinfo("Success", "Gantt chart exported to PDF successfully!")
        else:
            self._report_static_export_failure("PDF")

    def _report_static_export_failure(self, image_format: str):
        """
        Explain why a PNG or PDF export did not produce a file.

        DEVELOPMENT NOTES:
        ------------------
        Kaleido rasterises the Plotly figure by driving a Chrome or Chromium
        browser. Missing that browser is by far the most likely cause, and a
        bare "export failed" leaves the user with nowhere to go, so the
        message names the fix and points at HTML export as the alternative.
        """
        from gantt_app.utils.image_export import (
            static_export_available, NO_BROWSER_MESSAGE
        )

        if not static_export_available():
            logger.warning("%s export unavailable: no browser for Kaleido",
                           image_format)
            messagebox.showwarning(
                f"{image_format} Export Unavailable", NO_BROWSER_MESSAGE
            )
            return

        messagebox.showerror(
            "Error",
            f"Failed to export the Gantt chart to {image_format}.\n\n"
            "See the Log window for details."
        )

    def export_html(self):
        """Export the Gantt chart to a standalone interactive HTML file."""
        if self.gantt_chart is None:
            messagebox.showerror("Error", "Gantt chart not available for export")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".html",
            filetypes=[("HTML Files", "*.html"), ("All Files", "*.*")],
            title="Export Gantt Chart to HTML"
        )

        if not file_path:
            return

        from gantt_app.utils.image_export import export_gantt_to_html

        logger.info("Exporting the Gantt chart to HTML: %s", file_path)
        if export_gantt_to_html(self.project, file_path,
                                settings=self.gantt_chart._figure_settings()):
            messagebox.showinfo(
                "Success",
                "Gantt chart exported to HTML.\n\n"
                "The file is self-contained and stays interactive offline."
            )
        else:
            messagebox.showerror(
                "Error",
                "Failed to export the Gantt chart to HTML.\n\n"
                "See the Log window for details."
            )
    
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
            # Update button states if they exist (they may be in dropdown menus now)
            if hasattr(self, 'undo_btn') and self.undo_btn:
                self.undo_btn.configure(state=tk.NORMAL if self.undo_redo_manager.can_undo() else tk.DISABLED)
            if hasattr(self, 'redo_btn') and self.redo_btn:
                self.redo_btn.configure(state=tk.NORMAL if self.undo_redo_manager.can_redo() else tk.DISABLED)
    
    def undo(self):
        """Undo the last action."""
        if self.undo_redo_manager and self.undo_redo_manager.can_undo():
            if self.undo_redo_manager.undo():
                logger.info("Undo")
                self.update_undo_redo_buttons()
                if self.on_project_changed:
                    self.on_project_changed()
    
    def redo(self):
        """Redo the last undone action."""
        if self.undo_redo_manager and self.undo_redo_manager.can_redo():
            if self.undo_redo_manager.redo():
                logger.info("Redo")
                self.update_undo_redo_buttons()
                if self.on_project_changed:
                    self.on_project_changed()
    
    def toggle_theme(self):
        """Toggle between light and dark themes."""
        current_theme = ctk.get_appearance_mode()
        new_theme = "dark" if current_theme == "light" else "light"
        ctk.set_appearance_mode(new_theme)
        logger.info("Switched appearance to %s mode", new_theme)
    
    def open_gantt_chart_settings(self):
        """Open the Gantt chart settings dialog."""
        if self.gantt_chart:
            from gantt_app.views.ganttsettingsw import GanttChartSettingsDialog
            
            try:
                dialog = GanttChartSettingsDialog(
                    self.master, 
                    self.gantt_chart,
                    on_settings_changed=self._on_gantt_settings_changed
                )
                dialog.wait_window()
            except Exception as e:
                logger.exception("Could not open Gantt chart settings")
                messagebox.showerror(
                    "Settings Error",
                    f"Could not open Gantt chart settings:\n{e}"
                )
        else:
            messagebox.showerror(
                "Error",
                "Gantt chart is not available. Cannot open settings."
            )
    
    def _on_gantt_settings_changed(self, settings: Dict):
        """Handle Gantt chart settings changes."""
        logger.debug("Gantt chart settings changed: %s", settings)
        # The chart will be redrawn automatically by the settings dialog
    
    def set_project(self, project: Project):
        """Set a new project for the toolbar."""
        self.project = project
