"""
Project Settings: the dates and rules a whole plan is built from.

WHY THIS WINDOW EXISTS:
======================
Everything here used to be either unreachable or spread across three places. A
plan's title was behind a one-line prompt on the Actions menu, its calendar
behind a different dialog, and the date it starts on was not settable at all -
it was whatever the earliest task happened to say, so moving a plan meant
editing every task in it.

The one that matters is the start date. A plan slips by a month far more often
than any single task in it does, and the answer to that should be one date box
rather than forty edits.

WHAT IS A SETTING AND WHAT IS A COMMAND:
========================================
Not everything on this panel is stored. The start date is not a field on a
project - it is derived from the tasks - so that box is a command: typing a
date into it moves the whole plan to begin there, preserving every duration
and every gap. See Project.shift_to_start.

The finish date is the same when the plan is scheduled forward, where it is an
answer rather than a question, and it is shown but not editable. Switch
Schedule From to the finish date and it becomes the deadline, which is stored
and which the plan is then packed backwards against.

DEVELOPMENT NOTES:
------------------
Nothing is applied until Apply. A settings panel that acted on every keystroke
would reschedule a plan of a thousand tasks while somebody was still typing
the year.
"""

import tkinter as tk
from datetime import datetime
from typing import Callable, Optional

import customtkinter as ctk

from gantt_app import theme
from gantt_app.models import (
    DEFAULT_PROJECT_PRIORITY, MAX_PROJECT_PRIORITY, MIN_PROJECT_PRIORITY,
    SCHEDULE_FROM_FINISH, SCHEDULE_FROM_START, Project,
)
from gantt_app.utils.log import get_logger
from gantt_app.views import dialogs as messagebox
from gantt_app.views.datepicker import DateEntry
from gantt_app.views.modal import grab_when_visible

logger = get_logger(__name__)

#: What the Schedule From menu says, and what each answer means.
DIRECTION_LABELS = {
    "Project Start Date": SCHEDULE_FROM_START,
    "Project Finish Date": SCHEDULE_FROM_FINISH,
}
DIRECTION_NAMES = {value: label for label, value in DIRECTION_LABELS.items()}

#: What the calendar menu calls the plan's own, which has no name of its own.
PLAN_CALENDAR_LABEL = "Project calendar"


class ProjectSettingsDialog(ctk.CTkToplevel):
    """
    The panel behind Actions > Project Settings.

    PARAMETERS:
    -----------
    master : widget
        Window to open over.
    project : Project
        The plan being configured. Nothing on it is touched until Apply.
    on_apply : Callable[[], None]
        Called once the settings have been written, so the application can
        redraw. Given nothing: everything it needs is on the project.
    """

    GEOMETRY = "520x560"
    LABEL_WIDTH = 130

    def __init__(self, master, project: Project,
                 on_apply: Optional[Callable] = None, **kwargs):
        super().__init__(master, **kwargs)

        self.project = project
        self.on_apply = on_apply

        self.title("Project Settings")
        self.geometry(self.GEOMETRY)
        self.resizable(False, False)
        self.transient(master.winfo_toplevel())
        self.bind('<Escape>', lambda _event: self.destroy())
        grab_when_visible(self)

        self._build()
        self._show_direction()

    # ---- building -------------------------------------------------------

    def _row(self, parent, label: str, widget, note: str = ""):
        """One labelled row, with an optional line of explanation under it."""
        frame = ctk.CTkFrame(parent, fg_color='transparent')
        frame.pack(fill=tk.X, padx=16, pady=(8, 0))

        ctk.CTkLabel(frame, text=label, width=self.LABEL_WIDTH, anchor=tk.W
                     ).pack(side=tk.LEFT)
        widget.pack(side=tk.LEFT, fill=tk.X, expand=True)

        if note:
            ctk.CTkLabel(parent, text=note, anchor=tk.W, justify=tk.LEFT,
                         text_color=theme.MUTED_TEXT,
                         font=ctk.CTkFont(size=11),
                         ).pack(fill=tk.X, padx=(16 + self.LABEL_WIDTH, 16))
        return widget

    def _build(self):
        """Lay the panel out: what the plan is, then when, then how."""
        ctk.CTkLabel(self, text="Project Settings",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     ).pack(anchor=tk.W, padx=16, pady=(14, 0))

        self.name_entry = ctk.CTkEntry(self)
        self.name_entry.insert(0, self.project.name or '')
        self._row(self, "Title:", self.name_entry)

        self._separator()

        self.direction_menu = ctk.CTkOptionMenu(
            self, values=list(DIRECTION_LABELS),
            command=lambda _value: self._show_direction())
        self.direction_menu.set(
            DIRECTION_NAMES.get(self.project.schedule_from,
                                "Project Start Date"))
        self._row(self, "Schedule from:", self.direction_menu,
                  "Forward: work starts as soon as its links allow.\n"
                  "Backward: work is fitted in before the finish date.")

        self.start_entry = DateEntry(self, date=self.project.start_date)
        self._row(self, "Start date:", self.start_entry,
                  "Changing this moves the whole plan, keeping every\n"
                  "duration and every gap between tasks.")

        self.finish_entry = DateEntry(
            self, date=self.project.deadline or self.project.end_date)
        self._row(self, "Finish date:", self.finish_entry)
        self.finish_note = ctk.CTkLabel(
            self, text="", anchor=tk.W, justify=tk.LEFT,
            text_color=theme.MUTED_TEXT, font=ctk.CTkFont(size=11))
        self.finish_note.pack(fill=tk.X, padx=(16 + self.LABEL_WIDTH, 16))

        self._separator()

        self.calendar_menu = ctk.CTkOptionMenu(self, values=self._calendars())
        self.calendar_menu.set(PLAN_CALENDAR_LABEL)
        self._row(self, "Calendar:", self.calendar_menu,
                  "Which days the plan works. Edit them in\n"
                  "Actions > Calendar Settings.")

        today = ctk.CTkLabel(self, anchor=tk.W,
                             text=datetime.now().strftime('%Y-%m-%d'))
        self._row(self, "Current date:", today)

        self.status_entry = DateEntry(self, date=self.project.status_date)
        self._row(self, "Status date:", self.status_entry,
                  "What Mark on Track reports against. Empty means today.")

        self.priority_entry = ctk.CTkEntry(self, width=90)
        self.priority_entry.insert(0, str(self.project.priority))
        self._row(self, "Priority:", self.priority_entry,
                  f"{MIN_PROJECT_PRIORITY} to {MAX_PROJECT_PRIORITY}, "
                  f"{DEFAULT_PROJECT_PRIORITY} by default.")

        self._build_buttons()

    def _separator(self):
        """A hairline between two groups of settings."""
        ctk.CTkFrame(self, height=1, fg_color=theme.SEPARATOR
                     ).pack(fill=tk.X, padx=16, pady=(12, 2))

    def _calendars(self):
        """What the calendar menu offers: the plan's own, then the named."""
        return [PLAN_CALENDAR_LABEL] + [named.name
                                        for named in self.project.calendars]

    def _build_buttons(self):
        """Apply and Cancel, with Apply as the primary action."""
        frame = ctk.CTkFrame(self, fg_color='transparent')
        frame.pack(fill=tk.X, side=tk.BOTTOM, padx=16, pady=14)

        ctk.CTkButton(frame, text="Cancel", width=100,
                      fg_color='transparent', border_width=1,
                      border_color=theme.SEPARATOR, text_color=theme.TEXT,
                      hover_color=theme.MENU_HOVER,
                      command=self.destroy).pack(side=tk.RIGHT, padx=(6, 0))
        ctk.CTkButton(frame, text="Apply", width=100,
                      command=self.apply).pack(side=tk.RIGHT)

    # ---- what the panel shows -------------------------------------------

    def direction(self) -> str:
        """Which end the panel currently says the plan is scheduled from."""
        return DIRECTION_LABELS.get(self.direction_menu.get(),
                                    SCHEDULE_FROM_START)

    def _show_direction(self):
        """
        Let the finish date be typed into only when it is a question.

        DEVELOPMENT NOTES:
        ------------------
        Scheduled forward, the finish is an answer: it is whatever the work
        adds up to, and a box that accepted a date and then ignored it would
        be worse than one that refused. Scheduled backward it is the
        deadline, and the only date on the panel the plan is built around.
        """
        backward = self.direction() == SCHEDULE_FROM_FINISH
        self._set_enabled(self.finish_entry, backward)

        self.finish_note.configure(
            text=("The plan is packed backwards to end on this date."
                  if backward else
                  "Worked out from the plan; set Schedule from to the\n"
                  "finish date to make it a deadline."))

    @staticmethod
    def _set_enabled(date_entry, enabled: bool) -> None:
        """
        Turn a date box on or off, box and calendar button together.

        DEVELOPMENT NOTES:
        ------------------
        The state goes on the parts rather than on the DateEntry. It is a
        CTkFrame holding an entry and a button, and a frame has no state
        option at all - configuring one raises ValueError rather than doing
        nothing, so a disabled box was an exception rather than a grey box.

        The button matters as much as the entry. Leaving it live would put a
        calendar in front of somebody for a date the panel is not going to
        read.
        """
        state = tk.NORMAL if enabled else tk.DISABLED
        for part in (getattr(date_entry, 'entry', None),
                     getattr(date_entry, 'button', None)):
            if part is None:
                continue
            try:
                part.configure(state=state)
            except (ValueError, tk.TclError):
                continue

    # ---- applying it ----------------------------------------------------

    def _read_priority(self) -> Optional[int]:
        """The priority box, or None when it does not hold a usable number."""
        text = str(self.priority_entry.get()).strip()
        if not text:
            return DEFAULT_PROJECT_PRIORITY
        try:
            number = int(float(text))
        except (TypeError, ValueError):
            return None
        if not MIN_PROJECT_PRIORITY <= number <= MAX_PROJECT_PRIORITY:
            return None
        return number

    def apply(self) -> bool:
        """
        Write every setting, move the plan if it has to move, and close.

        RETURNS:
        --------
        bool
            True when the settings were applied. False leaves the panel open
            with the reason, which is what a refused number does.

        DEVELOPMENT NOTES:
        ------------------
        The order matters. The direction and the deadline are set before the
        plan is moved, because moving it settles the schedule and settling it
        has to know which end it is being settled from.
        """
        priority = self._read_priority()
        if priority is None:
            messagebox.showerror(
                "Project Settings",
                f"The priority has to be a whole number between "
                f"{MIN_PROJECT_PRIORITY} and {MAX_PROJECT_PRIORITY}.")
            return False

        backward = self.direction() == SCHEDULE_FROM_FINISH
        deadline = self.finish_entry.get_date() if backward else None
        if backward and deadline is None:
            messagebox.showerror(
                "Project Settings",
                "Scheduling backwards needs a finish date to work back from.")
            return False

        name = str(self.name_entry.get()).strip()
        if name:
            self.project.name = name

        self.project.priority = priority
        self.project.status_date = self.status_entry.get_date()
        self.project.schedule_from = (SCHEDULE_FROM_FINISH if backward
                                      else SCHEDULE_FROM_START)
        self.project.deadline = deadline

        start = self.start_entry.get_date()
        if start is not None:
            self.project.shift_to_start(start)

        self.project.apply_schedule()
        logger.info("Applied settings to %r: scheduled from the %s",
                    self.project.name, self.project.schedule_from)

        if self.on_apply:
            self.on_apply()

        self.destroy()
        return True


def edit_project_settings(master, project: Project,
                          on_apply: Optional[Callable] = None):
    """
    Open the settings panel over a window.

    RETURNS:
    --------
    Optional[ProjectSettingsDialog]
        The panel, or None when it could not be built - which is reported
        rather than left to take the window down with it.
    """
    try:
        return ProjectSettingsDialog(master, project, on_apply)
    except Exception:
        logger.exception("Could not open the project settings")
        messagebox.showerror(
            "Project Settings",
            "Could not open the project settings.\n\n"
            "See the Log window for details.")
        return None
