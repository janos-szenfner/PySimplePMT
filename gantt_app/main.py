"""
Main application entry point for the Gantt Project Management Tool.

Creates the main window and manages the application components.
"""

import sys
import os
from datetime import datetime
from typing import Optional
import tkinter as tk

import customtkinter as ctk

from gantt_app import theme
from gantt_app.models import Project, Task
from gantt_app.views.task_list import DragDropTaskList
from gantt_app.views.taskdialogs import EditTaskDialog
from gantt_app.views.gantt_chart import GanttChart
from gantt_app.views.toolbar import Toolbar
from gantt_app.utils.file_io import JSONFileIO, save_project, load_project
from gantt_app.utils.undoredo import UndoRedoManager, ProjectStateTracker
from gantt_app.utils.copypastecut import ClipboardManager, setup_keyboard_bindings
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
        The appearance chosen, 'light' or 'dark'.

    DEVELOPMENT NOTES:
    ------------------
    The *desktop's* setting, deliberately, and not the user's saved
    preference - the name says system and it means it. The application's own
    startup goes through ThemeController instead, which honours a saved
    override; this is for a caller that wants the desktop's answer and
    nothing else. The detection itself is gantt_app.theme's.

    The obvious call here is set_appearance_mode("system"), and that is what
    this used to be. It is a trap. Left in that mode CustomTkinter starts a
    tracker that re-reads the system setting every thirty milliseconds - over
    thirty times a second, for the lifetime of the application. On Linux
    darkdetect answers by running `gsettings` through subprocess, so it spawns
    tens of processes a second for a setting that changes about twice a day.
    ThemeController watches it once every few seconds instead; see
    ThemeController.POLL_SECONDS.
    """
    appearance = theme.detect_system_appearance()
    ctk.set_appearance_mode(appearance)
    logger.info("Appearance set to %s from the system setting", appearance)
    return appearance


class GanttApp(ctk.CTk):
    """
    Main application class for the Gantt Project Management Tool.
    
    Manages the project, task list, Gantt chart, and toolbar components.
    """
    
    #: The X11 window class the desktop matches this application by.
    #:
    #: It has to be the StartupWMClass in packaging/pysimplepmt.desktop, and
    #: Tk capitalises what it is given - so the desktop entry names the
    #: capitalised form. Without it the class is Tk, which is what every
    #: other Tk application on the machine is called: the desktop cannot tell
    #: which .desktop file the window belongs to, so it shows a generic icon
    #: in the dock and the switcher however good the one in the menu is.
    WM_CLASS_NAME = 'pysimplepmt'

    def __init__(self):
        # className is what Tk builds WM_CLASS from, and it can only be given
        # at construction - there is no way to set it on a window that already
        # exists. CustomTkinter forwards it to Tk untouched.
        super().__init__(className=self.WM_CLASS_NAME)

        # Configure main window
        self.title("Gantt Project Manager")
        self.geometry("1400x900")
        self.minsize(1200, 800)
        self._set_window_icon()
        
        # Who decides light or dark, and the watch on the desktop setting.
        # Held on the application because the toolbar's day/night control and
        # the View menu both drive it - see gantt_app.theme.
        self.theme_controller = theme.ThemeController()
        ctk.set_appearance_mode(self.theme_controller.appearance)
        self.theme_controller.start_watching(self)
        self.theme_controller.subscribe(self._theme_changed, owner=self)
        logger.info("Appearance %s (%s mode)",
                    self.theme_controller.appearance,
                    self.theme_controller.mode)
        ctk.set_default_color_theme("blue")
        
        # Create project
        self.project = Project(name="New Project")
        
        # Create undo/redo manager
        self.undo_redo_manager = UndoRedoManager(max_history=100)
        self.undo_redo_manager.set_project(self.project)
        
        # Create project state tracker for easier undo/redo integration
        self.project_tracker = ProjectStateTracker(self.project, self.undo_redo_manager)
        
        # Create clipboard manager
        self.clipboard_manager = ClipboardManager(self.project)
        
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
    
    def _set_window_icon(self):
        """
        Give the window the application's own icon.

        DEVELOPMENT NOTES:
        ------------------
        Drawn rather than loaded - see gantt_app.resources.appicon - so the
        window, the desktop entry and the packaged build all wear the same
        mark and there is no file to ship or to find at runtime.

        The image is kept on the instance. A Tk image is only alive while
        something references it from Python, and one dropped here left the
        window wearing a blank square.

        `default=True` passes it to every window the application opens, so
        the dialogs get it too. Losing the icon is not worth losing the
        application over, so a failure is logged and stepped over: some
        window managers refuse iconphoto outright.
        """
        try:
            from gantt_app.resources.appicon import icon_photo

            self._icon = icon_photo(self, 64)
            if self._icon is not None:
                self.iconphoto(True, self._icon)
        except Exception:
            logger.exception("Could not set the window icon")

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
    
    def _theme_changed(self, _mode, appearance):
        """
        Repaint the panes that do not follow the theme on their own.

        DEVELOPMENT NOTES:
        ------------------
        CustomTkinter widgets are given (light, dark) pairs and swap over by
        themselves. The two big panes are not CustomTkinter: the task list is
        a ttk Treeview, whose style resolves its colours once and keeps them,
        and the chart is a picture drawn with Pillow, which has the old
        colours baked into it. Neither notices a theme change without being
        told, so a flip left a white grid and a white chart inside a dark
        window.

        Guarded per pane. This runs from the desktop poll as well as from the
        button, so it can fire while the window is being torn down, and one
        pane that has already gone must not stop the other being repainted.
        """
        for name in ('task_list', 'gantt_chart'):
            pane = getattr(self, name, None)
            if pane is None:
                continue
            try:
                pane.apply_theme()
            except Exception:
                logger.debug("Could not repaint %s for the %s appearance",
                             name, appearance, exc_info=True)

    def _create_ui(self):
        """Create the user interface."""
        # Main layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Create toolbar (gantt_chart will be set after it's created)
        self.toolbar = Toolbar(
            self, self.project,
            on_project_changed=self.update_all,
            undo_redo_manager=self.undo_redo_manager,
            clipboard_manager=self.clipboard_manager,
            theme_controller=self.theme_controller,
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
            project_tracker=self.project_tracker,
            clipboard_manager=self.clipboard_manager
        )
        self.content_panes.add(self.task_list, weight=2)
        
        # Set task list reference in toolbar for copy/paste functionality
        self.toolbar.set_task_list(self.task_list)

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

        # The chart draws the rows the task list is showing, so the two line
        # up. Both have to exist first: this went in beside the toolbar's
        # set_task_list above, three lines before the chart was built, and
        # the application would not start at all.
        self.gantt_chart.set_task_list(self.task_list)
        
        # Create status bar
        self.status_bar = ctk.CTkLabel(
            self, text="Ready", anchor=tk.W,
            height=25, padx=10
        )
        self.status_bar.grid(row=2, column=0, sticky=tk.EW, padx=10, pady=(0, 10))
        
        # The clipboard needs a widget to reach the desktop's own
        self.clipboard_manager.set_clipboard_widget(self)

        # Set up clipboard keyboard bindings
        # These will be properly initialized after task_list is created
        self._setup_clipboard_bindings()
    
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

    def _setup_clipboard_bindings(self):
        """
        Set up keyboard bindings for copy, cut, and paste operations.
        
        DEVELOPMENT NOTES:
        ------------------
        This sets up Ctrl/Cmd+C, Ctrl/Cmd+X, and Ctrl/Cmd+V keyboard shortcuts
        for copy, cut, and paste operations on tasks.
        """
        def get_selected_ids():
            """Get currently selected task IDs from the task list."""
            if hasattr(self, 'task_list') and self.task_list:
                selection = self.task_list.tree.selection()
                return list(selection) if selection else []
            return []
        
        def get_target_container():
            """
            Get the target container ID for paste operations.
            
            For now, this returns None (root level) as the default.
            In a more sophisticated implementation, this could determine
            the container based on the current focus or selection context.
            """
            # Check if there's a selected task that can be a container
            selected_ids = get_selected_ids()
            if selected_ids:
                first_task = self.project.get_task_by_id(selected_ids[0])
                if first_task and first_task.can_have_children:
                    return first_task.id
            return None
        
        def on_clipboard_change():
            """Callback when clipboard state changes."""
            # Update the UI to reflect clipboard state changes
            self.update_all()
        
        # Set up the keyboard bindings
        setup_keyboard_bindings(
            self, self.clipboard_manager,
            get_selected_ids, get_target_container, on_clipboard_change
        )

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
