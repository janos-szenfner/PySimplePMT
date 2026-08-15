"""
Help window for the task editor dialog.

Provides information about the task editor functionality.
"""

import tkinter as tk
from tkinter import ttk

import customtkinter as ctk

from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


#: The editor help text, as (heading, [paragraph, ...]).
HELP_SECTIONS = (
    (
        "Task Types:",
        [
            "Tasks: Tasks are the core work items of your project. Each task has a name, a start date, a duration, and appears as a horizontal bar on the chart. The length of the bar is proportional to its duration. Tasks can run sequentially or in parallel, and their bars may overlap on the timeline when independent work streams happen simultaneously.",
        ],
    ),
    (
        "Milestones",
        [
            "Milestones mark significant checkpoints in a project — moments of achievement rather than spans of work. They have zero duration and are typically shown as a diamond or marker on the timeline. Common milestones include \"Design approved,\" \"MVP released,\" or \"Client sign-off.\" They are essential for tracking project health and communicating progress to stakeholders.",
        ],
    ),
    (
        "Timeline / Time Scale",
        [
            "The horizontal axis of a Gantt chart is the timeline. It can be scaled daily, weekly, or monthly depending on project length. A zoom level lets you drill into detail or pull back for a high-level overview. Most tools also display a \"today marker\" — a vertical line showing the current date — making it easy to see how actual progress compares to the plan.",
        ],
    ),
    (
        "% Completion",
        [
            "Progress tracking is built into Gantt charts through percentage completion (0%–100%). A partially completed bar is visually shaded or filled to show how much work is done. At a glance, you can see which tasks are on track, ahead, or behind schedule relative to the today marker. Aggregate completion across all tasks gives a quick project-health snapshot.",
        ],
    ),
)


class EditorHelpWindow(ctk.CTkToplevel):
    """
    A scrollable reference window with task editor help.

    PARAMETERS:
    -----------
    master : widget
        The window to open over.

    DEVELOPMENT NOTES:
    ------------------
    Deliberately not modal so it can be read while using the editor.

    Only one is kept open at a time - see `show` - to avoid stacking
    identical windows.

    The body is a tk.Text rather than a label so it scrolls, wraps and can be
    selected and copied. It is disabled after filling, which leaves it
    readable and selectable but not editable.
    """

    #: The window currently open, if any.
    _open_window = None

    #: Colours, kept close to the application's palette.
    HEADING_COLOR = '#1f6aa5'
    BODY_COLOR = '#1a1a1a'
    BACKGROUND = '#ffffff'

    def __init__(self, master=None):
        super().__init__(master)

        self.title("Editor Help - Gantt Project Manager")
        self.geometry("640x480")
        self.minsize(480, 360)
        if master is not None:
            self.transient(master)
        self.protocol("WM_DELETE_WINDOW", self.close)

        self._build_ui()
        self._fill()

    @classmethod
    def show(cls, master):
        """
        Open the editor help window, or bring the existing one to the front.

        PARAMETERS:
        -----------
        master : widget
            The window to open over.
        """
        if cls._open_window is not None and cls._open_window.winfo_exists():
            # Bring existing window to front
            try:
                cls._open_window.lift()
                cls._open_window.focus_force()
            except tk.TclError:
                cls._open_window = None
            return

        try:
            window = cls(master)
            cls._open_window = window
            window.lift()
            logger.info("Opened editor help window")
        except Exception:
            logger.exception("Could not open the editor help window")

    def close(self):
        """Close this help window."""
        if EditorHelpWindow._open_window is self:
            EditorHelpWindow._open_window = None
        try:
            self.destroy()
        except tk.TclError:
            pass

    def _build_ui(self):
        """Build the user interface."""
        # Main frame
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Text widget for help content
        self.text_widget = tk.Text(
            main_frame,
            wrap=tk.WORD,
            background=self.BACKGROUND,
            padx=10,
            pady=10,
            state=tk.DISABLED
        )
        self.text_widget.pack(fill=tk.BOTH, expand=True)

        # Scrollbar
        scrollbar = ttk.Scrollbar(main_frame, command=self.text_widget.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_widget.configure(yscrollcommand=scrollbar.set)

        # Close button
        close_frame = ctk.CTkFrame(self)
        close_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        ctk.CTkButton(
            close_frame, text="Close", width=80,
            command=self.close
        ).pack(side=tk.RIGHT, padx=5, pady=5)

    def _fill(self):
        """Fill the text widget with the help content."""
        self.text_widget.configure(state=tk.NORMAL)
        self.text_widget.delete(1.0, tk.END)

        for heading, paragraphs in HELP_SECTIONS:
            # Add heading
            self.text_widget.insert(tk.END, heading + "\n", 'heading')
            self.text_widget.insert(tk.END, "\n")

            # Add paragraphs
            for para in paragraphs:
                self.text_widget.insert(tk.END, para + "\n\n")

        # Configure text tags
        self.text_widget.tag_configure('heading', 
                                      foreground=self.HEADING_COLOR,
                                      font=('Arial', 12, 'bold'))
        self.text_widget.configure(state=tk.DISABLED)