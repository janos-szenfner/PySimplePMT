"""
Log viewer window for the Gantt Project Management Tool.

Shows the records collected by utils/log.py so problems can be inspected
without a console, which a packaged desktop build does not have.

DEVELOPMENT NOTES:
------------------
The logging itself lives in gantt_app/utils/log.py; this module is only the
window that displays it.
"""

import logging
import tkinter as tk
# Message boxes and file choosers that stay native on every desktop:
# Tk's own are native on macOS and Windows but drawn by Tk on X11.
# Aliased so the call sites below read exactly as they always have.
from gantt_app.views import dialogs as messagebox
from gantt_app.views import dialogs as filedialog
from datetime import datetime

import customtkinter as ctk

from gantt_app.utils.log import (
    get_log_text, get_log_file_path, clear_log, save_log_to, count_records
)


#: Filter choices offered in the window, in display order.
LEVEL_CHOICES = [
    ("All", logging.NOTSET),
    ("Debug", logging.DEBUG),
    ("Info", logging.INFO),
    ("Warning", logging.WARNING),
    ("Error", logging.ERROR),
]

#: How often the view refreshes itself, in milliseconds.
REFRESH_INTERVAL_MS = 2000


class LogWindow(ctk.CTkToplevel):
    """
    A window showing the application log.

    DEVELOPMENT NOTES:
    ------------------
    Only one instance should exist at a time; use LogWindow.show() rather than
    constructing directly, so repeated clicks on the Log button raise the
    existing window instead of opening duplicates.
    """

    _instance = None

    def __init__(self, master=None):
        super().__init__(master)

        self.title("Application Log")
        self.geometry("900x520")
        self.minsize(500, 300)

        self._auto_refresh = True
        self._refresh_job = None
        self._level = logging.NOTSET

        self._build_ui()
        self.refresh()
        self._schedule_refresh()

        self.protocol("WM_DELETE_WINDOW", self.close)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        """Lay out the controls, the text area and the status bar."""
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        controls = ctk.CTkFrame(self)
        controls.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=(10, 5))

        ctk.CTkLabel(controls, text="Level:").pack(side=tk.LEFT, padx=(10, 5), pady=8)

        self.level_var = ctk.StringVar(value=LEVEL_CHOICES[0][0])
        self.level_menu = ctk.CTkOptionMenu(
            controls,
            variable=self.level_var,
            values=[name for name, _ in LEVEL_CHOICES],
            command=self._on_level_changed,
            width=110
        )
        self.level_menu.pack(side=tk.LEFT, padx=5, pady=8)

        self.auto_var = ctk.BooleanVar(value=True)
        self.auto_check = ctk.CTkCheckBox(
            controls, text="Auto-refresh", variable=self.auto_var,
            command=self._on_auto_toggled
        )
        self.auto_check.pack(side=tk.LEFT, padx=15, pady=8)

        ctk.CTkButton(controls, text="Refresh", width=90,
                      command=self.refresh).pack(side=tk.LEFT, padx=5, pady=8)
        ctk.CTkButton(controls, text="Copy", width=80,
                      command=self.copy_to_clipboard).pack(side=tk.LEFT, padx=5, pady=8)
        ctk.CTkButton(controls, text="Save As...", width=100,
                      command=self.save_as).pack(side=tk.LEFT, padx=5, pady=8)
        ctk.CTkButton(controls, text="Clear", width=80,
                      command=self.clear).pack(side=tk.LEFT, padx=5, pady=8)
        ctk.CTkButton(controls, text="Close", width=80,
                      command=self.close).pack(side=tk.RIGHT, padx=10, pady=8)

        # Monospace so timestamps and levels line up into columns
        self.textbox = ctk.CTkTextbox(self, wrap=tk.NONE,
                                      font=("Courier New", 11))
        self.textbox.grid(row=1, column=0, sticky=tk.NSEW, padx=10, pady=5)

        self.status_label = ctk.CTkLabel(self, text="", anchor=tk.W)
        self.status_label.grid(row=2, column=0, sticky=tk.EW, padx=15, pady=(0, 10))

    # ------------------------------------------------------------------
    # Behaviour
    # ------------------------------------------------------------------

    def _on_level_changed(self, choice: str):
        """Apply a new minimum level and redraw."""
        for name, level in LEVEL_CHOICES:
            if name == choice:
                self._level = level
                break
        self.refresh()

    def _on_auto_toggled(self):
        """Start or stop periodic refreshing."""
        self._auto_refresh = bool(self.auto_var.get())
        if self._auto_refresh:
            self._schedule_refresh()
        else:
            self._cancel_refresh()

    def _cancel_refresh(self):
        """Cancel any queued refresh callback."""
        if self._refresh_job is None:
            return
        try:
            self.after_cancel(self._refresh_job)
        except (tk.TclError, ValueError):
            pass
        self._refresh_job = None

    def _schedule_refresh(self):
        """
        Queue the next automatic refresh.

        DEVELOPMENT NOTES:
        ------------------
        Any pending callback is cancelled first. Without that, toggling
        auto-refresh off and on again while one was still queued left the old
        callback running alongside the new one, and every toggle doubled the
        number of refresh chains for the life of the window.
        """
        self._cancel_refresh()

        if not self._auto_refresh:
            return
        try:
            self._refresh_job = self.after(REFRESH_INTERVAL_MS, self._tick)
        except tk.TclError:
            # Window is being destroyed
            self._refresh_job = None

    def _tick(self):
        """Refresh and queue the next tick."""
        self._refresh_job = None
        if not self.winfo_exists():
            return
        self.refresh()
        self._schedule_refresh()

    def refresh(self):
        """Reload the log text, keeping the view pinned to the newest entries."""
        if not self.winfo_exists():
            return

        text = get_log_text(self._level)

        # Only redraw when something changed, so the user's selection and
        # scroll position survive an auto-refresh tick
        current = self.textbox.get("1.0", tk.END).rstrip("\n")
        if current == text:
            self._update_status()
            return

        at_bottom = self._is_scrolled_to_bottom()

        self.textbox.configure(state=tk.NORMAL)
        self.textbox.delete("1.0", tk.END)
        self.textbox.insert("1.0", text)

        if at_bottom:
            self.textbox.see(tk.END)

        self._update_status()

    def _is_scrolled_to_bottom(self) -> bool:
        """Check whether the view is currently at the end of the log."""
        try:
            _, last = self.textbox.yview()
            return last >= 0.999
        except (tk.TclError, ValueError):
            return True

    def _update_status(self):
        """Show entry counts and where the log file lives."""
        errors = count_records(logging.ERROR)
        warnings = count_records(logging.WARNING) - errors
        total = count_records()

        path = get_log_file_path()
        location = str(path) if path else "not writing to a file"

        self.status_label.configure(
            text=(f"{total} entries  |  {warnings} warnings  |  {errors} errors"
                  f"  |  Log file: {location}")
        )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def copy_to_clipboard(self):
        """Put the visible log text on the clipboard."""
        try:
            self.clipboard_clear()
            self.clipboard_append(get_log_text(self._level))
            self.status_label.configure(text="Log copied to clipboard")
        except tk.TclError as e:
            messagebox.showerror("Copy Failed", f"Could not copy the log:\n{e}",
                                 parent=self)

    def save_as(self):
        """Write the visible log to a file chosen by the user."""
        default_name = f"pysimplepmt-log-{datetime.now():%Y%m%d-%H%M%S}.txt"
        filepath = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".txt",
            initialfile=default_name,
            filetypes=[("Text Files", "*.txt"), ("Log Files", "*.log"),
                       ("All Files", "*.*")],
            title="Save Log"
        )
        if not filepath:
            return

        if save_log_to(filepath, self._level):
            messagebox.showinfo("Log Saved", f"Log written to:\n{filepath}",
                                parent=self)
        else:
            messagebox.showerror("Save Failed",
                                 "Could not write the log file.", parent=self)

    def clear(self):
        """Discard the buffered entries after confirming."""
        if not messagebox.askyesno(
            "Clear Log",
            "Discard the entries shown here?\n\n"
            "The log file on disk is not affected.",
            parent=self
        ):
            return
        clear_log()
        self.refresh()

    def close(self):
        """Cancel the refresh timer and destroy the window."""
        self._auto_refresh = False
        self._cancel_refresh()

        LogWindow._instance = None
        self.destroy()

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    @classmethod
    def show(cls, master=None) -> 'LogWindow':
        """
        Open the log window, or raise the existing one.

        RETURNS:
        --------
        LogWindow
            The visible window instance.
        """
        existing = cls._instance
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.refresh()
                    existing.deiconify()
                    existing.lift()
                    existing.focus_force()
                    return existing
            except tk.TclError:
                pass

        window = cls(master)
        cls._instance = window
        window.lift()
        window.focus_force()
        return window
