"""
What the critical path analysis found, shown as a table.

WHY THIS MODULE EXISTS:
======================
The chart colours the critical tasks, which answers "what is critical" and
nothing else. The question a plan actually raises is the next one: *how much*
slack has everything else got, and which task is closest to having none. A
colour cannot say "this has one day of float and that has thirty", and one day
of float is the thing worth knowing about before it is spent.

So this lists every task with its early and late dates, its float, and whether
it is critical - the output of the critical path method rather than a summary
of it. Project.schedule_analysis does the arithmetic; nothing here computes a
date.

DEVELOPMENT NOTES:
------------------
Float is shown in working days, which is the only unit it means anything in:
the weekend between two tasks is not slack anybody can spend, so counting it
would overstate every number on the page.

The dates are the task's own, drawn from the plan, while the float comes from
the analysis. Showing the analysis's own offsets instead would be honest and
useless - "day 14 of the plan" is not a date anybody can act on.
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional

import customtkinter as ctk

from gantt_app.models import Project
from gantt_app.views.buttonstyle import secondary_button
from gantt_app.views.modal import grab_when_visible
from gantt_app import theme
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


class CriticalPathWindow(ctk.CTkToplevel):
    """
    The analysis, one row per task.

    PARAMETERS:
    -----------
    master : widget
        Window to open over.
    project : Project
        The plan to analyse. Read, never written: this reports on a schedule
        rather than changing one.
    """

    GEOMETRY = "980x620"
    MINSIZE = (720, 400)

    #: The columns, as (key, heading, width, anchor).
    COLUMNS = (
        ('name', 'Task', 300, tk.W),
        ('type', 'Type', 90, tk.W),
        ('start', 'Start', 100, tk.W),
        ('end', 'Finish', 100, tk.W),
        ('duration', 'Duration (wd)', 100, tk.CENTER),
        ('float', 'Float (wd)', 90, tk.CENTER),
        ('late_start', 'Latest start', 100, tk.W),
        ('late_finish', 'Latest finish', 100, tk.W),
        ('critical', 'Critical', 80, tk.CENTER),
    )

    #: Row shading: the critical ones, and the ones nearly there.
    #: (light, dark) pairs; see gantt_app.theme. Resolved when the rows are
    #: built, because a Treeview tag holds one colour and knows nothing about
    #: appearance modes - so this table stayed white on a dark desktop.
    CRITICAL_BG = theme.GRID_CRITICAL_BG
    TIGHT_BG = theme.GRID_TIGHT_BG
    ROW_BG = theme.GRID_ROW_BG
    ROW_ALT = theme.GRID_ROW_ALT

    #: The ttk style this table uses. Its own rather than the task list's,
    #: because the two are different widths and the task list sets a row
    #: height to match its chart.
    STYLE_NAME = 'CriticalPath.Treeview'

    #: Float at or below this, without being zero, counts as tight.
    TIGHT_FLOAT = 2

    def __init__(self, master, project: Project):
        super().__init__(master)

        self.project = project

        self.title(f"Critical Path Analysis - {project.name or 'Project'}")
        self.geometry(self.GEOMETRY)
        self.minsize(*self.MINSIZE)
        self.transient(master)
        grab_when_visible(self)

        self._build_summary()
        self._build_table()
        self._build_buttons()
        self.refresh()

    # ---- the parts of the window ---------------------------------------

    def _build_summary(self):
        """The headline: how long the plan is and what drives it."""
        self.summary_label = ctk.CTkLabel(
            self, anchor=tk.W, justify=tk.LEFT, text="",
            font=ctk.CTkFont(size=13),
        )
        self.summary_label.pack(fill=tk.X, padx=15, pady=(15, 0))

        self.explain_label = ctk.CTkLabel(
            self, anchor=tk.W, justify=tk.LEFT, wraplength=900,
            text=("Float is how many working days a task can slip before the "
                  "project finishes later. A task with none of it is on the "
                  "critical path - and every such task is listed, not one "
                  "chain through them, so parallel work that is equally "
                  "critical shows up as such. Counted in the project "
                  "calendar's working days, including for tasks that follow "
                  "a calendar of their own, so every task is measured "
                  "against the same ruler."),
            text_color=theme.MUTED_TEXT,
        )
        self.explain_label.pack(fill=tk.X, padx=15, pady=(4, 8))

    def _build_table(self):
        """The rows themselves."""
        frame = ctk.CTkFrame(self)
        frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 10))

        theme.style_treeview(self.STYLE_NAME)
        self.tree = ttk.Treeview(
            frame, columns=[key for key, *_rest in self.COLUMNS],
            show='headings', style=self.STYLE_NAME,
        )
        for key, heading, width, anchor in self.COLUMNS:
            self.tree.heading(key, text=heading, anchor=tk.W)
            self.tree.column(key, width=width, anchor=anchor,
                             stretch=(key == 'name'))

        vertical = ttk.Scrollbar(frame, orient=tk.VERTICAL,
                                 command=self.tree.yview)
        self.tree.configure(yscrollcommand=vertical.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vertical.pack(side=tk.RIGHT, fill=tk.Y)

        self._apply_row_colours()

    def _apply_row_colours(self):
        """Colour the row tags for the appearance in force."""
        self.tree.tag_configure('critical', background=theme.now(self.CRITICAL_BG))
        self.tree.tag_configure('tight', background=theme.now(self.TIGHT_BG))
        self.tree.tag_configure('plain', background=theme.now(self.ROW_BG))
        self.tree.tag_configure('alt', background=theme.now(self.ROW_ALT))

    def _build_buttons(self):
        """Refresh, and a way out."""
        footer = ctk.CTkFrame(self, fg_color='transparent')
        footer.pack(fill=tk.X, side=tk.BOTTOM, padx=15, pady=(0, 15))

        ctk.CTkButton(footer, text="Close", width=110,
                      command=self.destroy).pack(side=tk.RIGHT, padx=5)
        secondary_button(footer, "Recalculate", self.refresh).pack(
            side=tk.RIGHT)

    # ---- filling it in --------------------------------------------------

    def refresh(self):
        """
        Run the analysis and redraw the table.

        Rows are drawn in the plan's own order rather than sorted by float.
        The reader is looking for a task they know by name, and a table that
        rearranged itself every time it was recalculated would make that
        harder than reading down the plan they already have in their head.
        """
        for row in self.tree.get_children():
            self.tree.delete(row)

        analysis = self.project.schedule_analysis()
        critical = 0

        for index, task in enumerate(self.project.tasks):
            found = analysis.get(task.id)
            if found is None:
                continue        # a summary: it brackets work rather than being it

            if found.is_critical:
                tag = 'critical'
                critical += 1
            elif found.total_float <= self.TIGHT_FLOAT:
                tag = 'tight'
            else:
                tag = 'alt' if index % 2 else 'plain'

            self.tree.insert('', tk.END, iid=task.id, tags=(tag,), values=(
                task.name,
                task.task_type,
                task.start_date.strftime('%Y-%m-%d'),
                task.end_date.strftime('%Y-%m-%d') if task.end_date else '—',
                self.project.working_duration(task),
                found.total_float,
                self._date_for(found.late_start),
                self._date_for(found.late_finish),
                'Yes' if found.is_critical else '',
            ))

        self._write_summary(analysis, critical)

    def _date_for(self, offset: int) -> str:
        """
        A working-day offset from the plan's start, as a date.

        The analysis counts in working days from the first day of the plan,
        which is the only unit float means anything in. A reader wants a
        date, so the offset is walked back out over the same calendar.

        The plan's calendar, deliberately, even for a task following one of
        its own: the axis is what every task's float is compared on, and a
        task measured against its own week would sit at a different number
        for the same day - so slack between two tasks on different calendars
        would come out as whatever the difference between their weeks was.
        Both ends of every task are read off this one ruler; see
        Project.schedule_analysis.
        """
        if self.project.start_date is None:
            return '—'
        try:
            moment = self.project.calendar.add_working_days(
                self.project.start_date, offset + 1
            )
        except Exception:
            logger.exception("Could not turn offset %s into a date", offset)
            return '—'
        return moment.strftime('%Y-%m-%d')

    def _write_summary(self, analysis, critical: int) -> None:
        """The line above the table: the length of the plan and its risk."""
        if not analysis:
            self.summary_label.configure(
                text="Nothing to analyse: the plan holds no work yet."
            )
            return

        span = max(found.early_finish for found in analysis.values()) + 1
        slack = [found.total_float for found in analysis.values()
                 if not found.is_critical]
        tightest = min(slack) if slack else 0

        text = (f"{span} working days from start to finish.  "
                f"{critical} of {len(analysis)} tasks are critical.")
        if slack:
            text += f"  Tightest task with any slack: {tightest} day(s)."
        if any(found.total_float < 0 for found in analysis.values()):
            text += ("  Some tasks have negative float: the links require a "
                     "finish the plan cannot reach.")
        self.summary_label.configure(text=text)


def show_critical_path(master, project: Project) -> Optional[CriticalPathWindow]:
    """
    Open the analysis window.

    RETURNS:
    --------
    Optional[CriticalPathWindow]
        The window, or None when it could not be built - a report that fails
        to open should not take the toolbar that opened it down with it.
    """
    try:
        return CriticalPathWindow(master, project)
    except Exception:
        logger.exception("Could not open the critical path window")
        return None
