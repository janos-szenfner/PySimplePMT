"""
The Update Project window: reschedule uncompleted work to start after a date.

WHY THIS MODULE EXISTS:
=======================
A plan ages between the day it was drawn and the day it is looked at, and
the status date in Project Settings is only a marker - nothing moves for
it on its own. Microsoft Project's answer is the Update Project window,
whose 'Reschedule uncompleted work to start after' line is the one worth
having here: everything nobody has started yet stops pretending it began
last month and starts on the status date instead.

The window's other half - 'Update work as complete through' - is
deliberately absent: marking work complete is Mark on Track's job, and
one button doing both would surprise everybody. Microsoft's Scope choice
is absent too; the run covers the whole plan, the way baselines do (issue
#89, following #84).

DEVELOPMENT NOTES:
------------------
The window asks one question - the date - and hands it back through
on_update; the moving itself is Project.reschedule_uncompleted_work,
called by the toolbar inside a single undoable command.
"""
import tkinter as tk
from datetime import datetime
from typing import Callable, Optional

import customtkinter as ctk

from gantt_app.core.models import Project
from gantt_app.utils.log import get_logger
from gantt_app.views import dialogs as messagebox
from gantt_app.views.datepicker import DateEntry
from gantt_app.views.modal import grab_when_visible

logger = get_logger(__name__)


class UpdateProjectDialog(ctk.CTkToplevel):
    """
    Modal dialog asking which date uncompleted work resumes on.

    PARAMETERS:
    -----------
    master : widget
        The main window.
    project : Project
        The plan - read for the status date the box defaults to.
    on_update : Callable[[datetime], None]
        Given the date OK was pressed with.
    """

    def __init__(self, master, project: Project,
                 on_update: Callable[[datetime], None] = None):
        super().__init__(master)
        self.title("Update Project")
        self.geometry("460x220")
        self.resizable(False, False)
        self.transient(master.winfo_toplevel())
        self.project = project
        self.on_update = on_update
        self._build()
        grab_when_visible(self)

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=0, column=0, sticky=tk.NSEW, padx=20, pady=20)
        body.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            body, text="Reschedule uncompleted work to start after:",
            anchor=tk.W).grid(row=0, column=0, sticky=tk.W)

        # The line the plan is reported against is the sane default; a
        # different catch-up day is a date like any other.
        default = self.project.status_date or datetime.now()
        self._date_entry = DateEntry(body, date=default)
        self._date_entry.grid(row=1, column=0, sticky=tk.EW, pady=(6, 10))

        ctk.CTkLabel(
            body, anchor=tk.W, justify=tk.LEFT, wraplength=400,
            text="Tasks not yet started move to begin on or after the "
                 "date. Tasks underway whose finish is already behind it "
                 "keep their start and their remaining work resumes on "
                 "it. Completed and inactive tasks are left alone."
        ).grid(row=2, column=0, sticky=tk.W)

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=1, column=0, sticky=tk.EW, padx=20, pady=(0, 15))
        buttons.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(buttons, text="OK", width=80,
                      command=self._on_ok).grid(row=0, column=0, sticky=tk.E,
                                                padx=(0, 5))
        ctk.CTkButton(buttons, text="Cancel", width=80,
                      command=self.destroy).grid(row=0, column=1,
                                                 sticky=tk.E)

    def _on_ok(self):
        date = self._date_entry.get_date()
        if date is None:
            messagebox.showwarning(
                "Update Project",
                "Enter the date uncompleted work should resume on.")
            return
        logger.info("Update Project: rescheduling uncompleted work to "
                    "start after %s", date.date())
        if self.on_update:
            self.on_update(date)
        self.destroy()
