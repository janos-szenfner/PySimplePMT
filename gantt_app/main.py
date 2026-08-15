"""
Main application entry point for the Gantt Project Management Tool.

Creates the main window and manages the application components.
"""

import sys
import os
from datetime import datetime
from typing import Optional

import customtkinter as ctk

from gantt_app.models import Project, Task
from gantt_app.views.task_list import DragDropTaskList
from gantt_app.views.taskdialogs import EditTaskDialog
from gantt_app.views.gantt_chart import GanttChart
from gantt_app.views.toolbar import Toolbar
from gantt_app.utils.file_io import JSONFileIO, save_project, load_project
from gantt_app.utils.undoredo import UndoRedoManager, ProjectStateTracker
from gantt_app.utils.log import (
    setup_logging, get_logger, install_exception_hook, get_log_file_path
)

logger = get_logger(__name__)


def set_appearance_from_system() -> str:
    """
    Match the desktop's light or dark setting, once.

    RETURNS:
    --------
    str
        The mode chosen, 'light' or 'dark'.

    DEVELOPMENT NOTES:
    ------------------
    The obvious call here is set_appearance_mode("system"), and that is what
    this used to be. It is a trap. Left in that mode CustomTkinter starts a
    tracker that re-reads the system setting every thirty milliseconds - over
    thirty times a second, for the lifetime of the application.

    On macOS each read is a library call and merely wasteful. On Linux
    darkdetect answers by running `gsettings` through subprocess, and falls
    back to a second call when the first comes back empty: thirty to sixty
    processes spawned every second, for a setting that changes about twice a
    day. It made the whole window sluggish, worst wherever there was most to
    redraw, and it is why typing in a dialog felt heavy.

    Reading it once at startup costs one call. The theme can still be changed
    from View > Toggle Theme, which sets an explicit mode and leaves the
    tracker asleep.
    """
    mode = 'light'
    try:
        import darkdetect
        if str(darkdetect.theme() or '').lower() == 'dark':
            mode = 'dark'
    except Exception:
        # No detector, or it refused to answer - light is the safe default
        logger.debug("Could not detect the system theme; using light")

    ctk.set_appearance_mode(mode)
    logger.info("Appearance set to %s from the system setting", mode)
    return mode


class GanttApp(ctk.CTk):
    """
    Main application class for the Gantt Project Management Tool.
    
    Manages the project, task list, Gantt chart, and toolbar components.
    """
    
    def __init__(self):
        super().__init__()
        
        # Configure main window
        self.title("Gantt Project Manager")
        self.geometry("1400x900")
        self.minsize(1200, 800)
        
        # Set appearance
        set_appearance_from_system()
        ctk.set_default_color_theme("blue")
        
        # Create project
        self.project = Project(name="New Project")
        
        # Create undo/redo manager
        self.undo_redo_manager = UndoRedoManager(max_history=100)
        self.undo_redo_manager.set_project(self.project)
        
        # Create project state tracker for easier undo/redo integration
        self.project_tracker = ProjectStateTracker(self.project, self.undo_redo_manager)
        
        # Create sample data
        self._create_sample_data()
        
        # Create UI components
        self._create_ui()
        
        # Bind events
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Tk sends callback exceptions to stderr, which a packaged build has
        # no console for, so a failing dialog just appeared empty with no
        # explanation anywhere. Route them into the log instead.
        self.report_callback_exception = self._on_callback_error
    
    def _create_sample_data(self):
        """Create sample tasks for demonstration."""
        today = datetime.now()
        
        # Add sample tasks
        task1 = Task.create_task(
            name="Project Planning",
            start_date=today,
            end_date=today + timedelta(days=3),
            color="#3498db"
        )
        
        # Add a subtask under Project Planning
        subtask1 = Task.create_subtask(
            name="Requirements Gathering",
            parent_task=task1,
            end_date=today + timedelta(days=1),
            color="#9b59b6"
        )
        
        task2 = Task.create_task(
            name="Design Phase",
            start_date=today + timedelta(days=4),
            end_date=today + timedelta(days=10),
            dependencies=[task1.id],
            color="#2ecc71"
        )
        
        # Add a subtask under Design Phase
        subtask2 = Task.create_subtask(
            name="UI Mockups",
            parent_task=task2,
            end_date=today + timedelta(days=6),
            color="#8e44ad"
        )
        
        task3 = Task.create_task(
            name="Implementation",
            start_date=today + timedelta(days=11),
            end_date=today + timedelta(days=20),
            dependencies=[task2.id],
            color="#f39c12",
            progress=30
        )
        
        # Add milestone
        milestone = Task.create_milestone(
            name="Design Review",
            date=today + timedelta(days=10),
            dependencies=[task2.id],
            color="#e74c3c"
        )
        
        # Add more tasks
        task4 = Task.create_task(
            name="Testing",
            start_date=today + timedelta(days=21),
            end_date=today + timedelta(days=25),
            dependencies=[task3.id, milestone.id],
            color="#9b59b6"
        )
        
        task5 = Task.create_task(
            name="Deployment",
            start_date=today + timedelta(days=26),
            end_date=today + timedelta(days=28),
            dependencies=[task4.id],
            color="#1abc9c"
        )
        
        # Add tasks to project (in order: root tasks first, then subtasks)
        self.project.add_task(task1)
        self.project.add_task(subtask1)
        self.project.add_task(task2)
        self.project.add_task(subtask2)
        self.project.add_task(task3)
        self.project.add_task(milestone)
        self.project.add_task(task4)
        self.project.add_task(task5)

        # The factories generate UUIDs, which read as noise in the ID column.
        # Renumbering here gives the sample project the same 001, 002, ...
        # sequence that new tasks and imported plans use.
        self.project.renumber_task_ids()
    
    def _create_ui(self):
        """Create the user interface."""
        # Main layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Create toolbar (gantt_chart will be set after it's created)
        self.toolbar = Toolbar(
            self, self.project,
            on_project_changed=self.update_all,
            undo_redo_manager=self.undo_redo_manager
        )
        self.toolbar.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=10)
        
        # Create main content frame
        content_frame = ctk.CTkFrame(self)
        content_frame.grid(row=1, column=0, sticky=tk.NSEW, padx=10, pady=10)
        
        content_frame.grid_columnconfigure(0, weight=1)
        content_frame.grid_rowconfigure(0, weight=1)

        # A paned window rather than two grid columns, so the divider between
        # the task list and the chart can be dragged to give either side more
        # room. ttk provides the sash; CTk has no equivalent widget.
        self._configure_sash_style()
        self.content_panes = ttk.PanedWindow(
            content_frame, orient=tk.HORIZONTAL, style='Gantt.TPanedwindow'
        )
        self.content_panes.grid(row=0, column=0, sticky=tk.NSEW, padx=5, pady=5)

        # Create task list
        self.task_list = DragDropTaskList(
            self.content_panes, self.project,
            on_task_select=self.on_task_select,
            on_task_edit=self.edit_task,
            on_project_changed=self.update_all,
            project_tracker=self.project_tracker
        )
        self.content_panes.add(self.task_list, weight=2)

        # Create Gantt chart
        self.gantt_chart = GanttChart(
            self.content_panes, self.project,
            width=12, height=8
        )
        self.content_panes.add(self.gantt_chart, weight=3)

        # Place the divider once the window has its real size
        self.after(120, self._set_initial_sash)
        
        # Set Gantt chart reference in toolbar for export functionality
        self.toolbar.set_gantt_chart(self.gantt_chart)
        
        # Create status bar
        self.status_bar = ctk.CTkLabel(
            self, text="Ready", anchor=tk.W,
            height=25, padx=10
        )
        self.status_bar.grid(row=2, column=0, sticky=tk.EW, padx=10, pady=(0, 10))
    
    def _configure_sash_style(self):
        """
        Give the divider a visible grip in the application's grey palette.

        DEVELOPMENT NOTES:
        ------------------
        The default sash is a couple of pixels wide and easy to miss. The
        'clam' theme, which the task list already selects for its grid lines,
        honours sash thickness and colour.
        """
        style = ttk.Style()
        try:
            style.configure('Gantt.TPanedwindow', background='#d0d0d0')
            style.configure('Gantt.Sash', sashthickness=7, gripcount=0,
                            background='#d0d0d0', bordercolor='#b0b0b0',
                            lightcolor='#e8e8e8', darkcolor='#b0b0b0')
        except tk.TclError:
            logger.debug("Could not style the pane divider on this platform")

    def _set_initial_sash(self):
        """Put the divider at a sensible starting position."""
        try:
            if not self.content_panes.winfo_exists():
                return
            width = self.content_panes.winfo_width()
            if width > 200:
                # Roughly 40 percent for the task list, the rest for the chart
                self.content_panes.sashpos(0, int(width * 0.4))
        except tk.TclError:
            pass

    def on_task_select(self, task: Task):
        """Handle task selection in the task list."""
        # Update status bar
        if task.is_milestone:
            self.status_bar.configure(
                text=f"Milestone: {task.name} ({task.start_date.strftime('%Y-%m-%d')}) | "
                     f"Dependencies: {len(task.dependencies)}"
            )
        else:
            # duration_days is a property, not a method
            duration = task.duration_days or 0
            self.status_bar.configure(
                text=f"Task: {task.name} | {task.start_date.strftime('%Y-%m-%d')} - "
                     f"{task.end_date.strftime('%Y-%m-%d') if task.end_date else 'N/A'} "
                     f"({duration} days) | Progress: {task.progress}% | "
                     f"Dependencies: {len(task.dependencies)}"
            )
        
        # Highlight task in Gantt chart (could be implemented)
        self.gantt_chart.update_chart()
    
    def edit_task(self, task: Task):
        """Open the task edit dialog."""
        dialog = EditTaskDialog(
            self, task, self.project,
            on_save=self.on_task_saved,
            on_delete=self.on_task_deleted,
            project_tracker=self.project_tracker,
            # Save & New continues from the task just edited, so the new one
            # lands beside it rather than at the end of the plan
            on_new=lambda anchor=task.id: self.task_list.create_task(
                "Task", anchor
            ),
        )
        dialog.wait_window()
    
    def on_task_saved(self, task: Task):
        """Handle task save from edit dialog."""
        self.update_all()
        self.status_bar.configure(text=f"Task '{task.name}' updated successfully")
    
    def on_task_deleted(self, task_id: str):
        """Handle task deletion."""
        # The deletion is already handled by EditTaskDialog with undo support
        # Just update the UI
        self.update_all()
        self.status_bar.configure(text="Task deleted successfully")
    
    def update_all(self):
        """
        Settle the schedule, then update every component.

        DEVELOPMENT NOTES:
        ------------------
        Rescheduling happens here because this is what every mutation path
        already calls - the toolbar, the dialogs, the task list and the
        importers all end up in update_all. Links used to be applied only at
        the moment one was created, so moving a predecessor afterwards left
        everything downstream of it where it was.

        reschedule returns whether anything moved and is a no-op on a settled
        plan, so calling it on every refresh costs a single pass.
        """
        if self.project.reschedule():
            logger.debug("Rescheduled %r after a change", self.project.name)

        self.task_list.update_task_list()
        self.gantt_chart.update_chart()
        
        # Update window title with project name
        if self.project.name:
            self.title(f"Gantt Project Manager - {self.project.name}")
        
        # Update status bar
        if self.project.tasks:
            milestone_count = sum(1 for t in self.project.tasks if t.is_milestone)
            task_count = len(self.project.tasks) - milestone_count
            self.status_bar.configure(
                text=f"Project: {self.project.name} | "
                     f"Tasks: {task_count} | Milestones: {milestone_count}"
            )
        else:
            self.status_bar.configure(text=f"Project: {self.project.name} | No tasks")
    
    def _on_callback_error(self, exc_type, exc_value, exc_traceback):
        """
        Log an exception raised inside a Tk callback and tell the user.

        PARAMETERS:
        -----------
        exc_type, exc_value, exc_traceback
            The exception, as Tkinter passes it to report_callback_exception.

        DEVELOPMENT NOTES:
        ------------------
        Without this, an error while building a dialog left an empty window
        on screen and nothing in the log; the traceback went to a stderr that
        nobody sees. Every UI failure is now recorded with its stack and
        named in the status bar.
        """
        logger.error("Unhandled error in a UI callback",
                     exc_info=(exc_type, exc_value, exc_traceback))
        try:
            self.status_bar.configure(
                text=f"Error: {exc_value} - see the Log window for details"
            )
        except Exception:
            pass

    def on_close(self):
        """
        Handle application close.

        DEVELOPMENT NOTES:
        ------------------
        Everything before the final teardown is best effort. This runs from
        the window manager's close button, and anything that raises here
        leaves the user with a window they cannot shut: an earlier version
        called ctk.messagebox, which does not exist, so the AttributeError
        escaped and destroy() was never reached.

        Teardown also closes any remaining Toplevel windows. A stray popup
        keeps the Tk main loop alive, so the process would linger after the
        main window disappeared.
        """
        try:
            if self.project.tasks:
                result = messagebox.askyesnocancel(
                    "Exit", "Do you want to save your project before exiting?"
                )
                if result is None:  # Cancel - stay open
                    return
                if result:  # Yes, save
                    self._save_on_exit()
        except Exception:
            logger.exception("Error while preparing to exit; closing anyway")

        self._shutdown()

    def _shutdown(self):
        """Destroy every window and stop the main loop."""
        try:
            from gantt_app.views.toolbar import DropdownButton
            DropdownButton.close_open_menu()
        except Exception:
            logger.exception("Could not close an open dropdown menu")

        # Any surviving Toplevel keeps the main loop running
        for child in list(self.winfo_children()):
            if isinstance(child, tk.Toplevel):
                try:
                    child.destroy()
                except tk.TclError:
                    pass

        logger.info("Application closing")

        try:
            self.quit()
        except tk.TclError:
            pass
        try:
            self.destroy()
        except tk.TclError:
            pass
    
    def _save_on_exit(self):
        """Save project when exiting."""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            title="Save Project Before Exit"
        )
        
        if file_path:
            save_project(self.project, file_path)


# Import tkinter modules
import tkinter as tk
from tkinter import ttk
# Message boxes and file choosers that stay native on every desktop:
# Tk's own are native on macOS and Windows but drawn by Tk on X11.
# Aliased so the call sites below read exactly as they always have.
from gantt_app.views import dialogs as messagebox
from gantt_app.views import dialogs as filedialog
from datetime import timedelta


def main():
    """Run the main application."""
    # Set logging up before anything else, so a failure during construction
    # is recorded rather than lost - a packaged build has no console
    setup_logging()
    install_exception_hook()

    logger.info("Starting PySimplePMT")
    log_path = get_log_file_path()
    if log_path:
        logger.info("Logging to %s", log_path)

    try:
        app = GanttApp()
        app.mainloop()
        logger.info("Application closed")
    except Exception as e:
        logger.exception("Failed to start application")
        # Show error message
        root = ctk.CTk()
        root.withdraw()
        messagebox.showerror("Error", f"Failed to start application: {e}")
        root.destroy()
        sys.exit(1)


if __name__ == "__main__":
    main()
