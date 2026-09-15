"""
What resource levelling would change, shown before anything changes.

WHY THIS MODULE EXISTS:
======================
Levelling rewrites the plan's dates, and a tool that silently moves a
fortnight of work on a button press is not a tool anybody trusts. So the
ribbon's Level button opens this first: the same engine run on a scratch
copy, its answers laid out as a table - which tasks move, for which
resource, how far, and what it could not fix. Apply replays the run on
the real plan as a single undoable command; Cancel throws the copy away.

DEVELOPMENT NOTES:
------------------
The shape is the critical path window's: a summary line, a styled table,
a button row. The difference is Apply - the one window in the report
family that is allowed to write, and only when the button is pressed.
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

import customtkinter as ctk

from gantt_app.core.leveling import LevelingOptions, LevelingPlan, preview
from gantt_app.core.models import Project
from gantt_app.views.buttonstyle import secondary_button
from gantt_app.views.modal import grab_when_visible
from gantt_app.views import theme
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


class LevelingPreviewWindow(ctk.CTkToplevel):
    """
    The levelling run's answers, one row per task it would move.

    PARAMETERS:
    -----------
    master : widget
        Window to open over.
    project : Project
        The plan to level - read for the preview, written only by Apply.
    apply_callback : Callable[[LevelingPlan], None]
        What the Apply button hands the run to; the toolbar supplies it so
        the change lands inside one undoable command and refreshes the
        views. None leaves the window read-only.
    options : LevelingOptions
        The run's knobs; defaults to the safe set (free float only,
        deadlines respected).
    """

    GEOMETRY = "940x560"
    MINSIZE = (700, 380)

    #: The columns, as (key, heading, width, anchor).
    COLUMNS = (
        ('name', 'Task', 260, tk.W),
        ('start', 'Was', 100, tk.W),
        ('becomes', 'Becomes', 100, tk.W),
        ('delay', 'Delay (wd)', 80, tk.CENTER),
        ('finish', 'Finish', 100, tk.W),
    )

    UNRESOLVED_COLUMNS = (
        ('resource', 'Resource', 160, tk.W),
        ('day', 'Day', 100, tk.W),
        ('over', 'Still over', 90, tk.CENTER),
        ('advice', 'Advice', 400, tk.W),
    )

    ROW_BG = theme.GRID_ROW_BG
    ROW_ALT = theme.GRID_ROW_ALT
    TIGHT_BG = theme.GRID_TIGHT_BG

    STYLE_NAME = 'LevelingPreview.Treeview'

    def __init__(self, master, project: Project,
                 apply_callback: Optional[Callable[[LevelingPlan],
                                                 None]] = None,
                 options: Optional[LevelingOptions] = None):
        super().__init__(master)

        self.project = project
        self._apply_callback = apply_callback
        self._options = options or LevelingOptions()
        #: The scratch run's answers, kept so Apply reports what it did.
        self._plan = None

        self.title(f"Resource Levelling - {project.name or 'Project'}")
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
        """The headline: what the run found and what it would do."""
        self.summary_label = ctk.CTkLabel(
            self, anchor=tk.W, justify=tk.LEFT, text="",
            font=ctk.CTkFont(size=13),
        )
        self.summary_label.pack(fill=tk.X, padx=15, pady=(15, 0))

        float_note = (
            "free float, so no successor's dates move"
            if self._options.within_free_float else
            "total float, so the project's finish stays put but "
            "successors may move with it")
        self.explain_label = ctk.CTkLabel(
            self, anchor=tk.W, justify=tk.LEFT, wraplength=880,
            text=("Levelling delays tasks to clear the days a resource is "
                  "booked past its capacity. A task only moves inside its "
                  f"{float_note}; whatever no delay can clear is listed "
                  "below the moves rather than hidden."),
            text_color=theme.MUTED_TEXT,
        )
        self.explain_label.pack(fill=tk.X, padx=15, pady=(4, 8))

    def _build_table(self):
        """The moves, then the unresolved days under them."""
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

        self.unresolved_tree = ttk.Treeview(
            frame, columns=[key for key, *_rest in self.UNRESOLVED_COLUMNS],
            show='headings', style=self.STYLE_NAME, height=5,
        )
        for key, heading, width, anchor in self.UNRESOLVED_COLUMNS:
            self.unresolved_tree.heading(key, text=heading, anchor=tk.W)
            self.unresolved_tree.column(key, width=width, anchor=anchor,
                                        stretch=(key == 'advice'))

        self.tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.unresolved_tree.pack(side=tk.TOP, fill=tk.X, pady=(8, 0))
        self._apply_row_colours()

    def _apply_row_colours(self):
        """Colour the row tags for the appearance in force."""
        self.tree.tag_configure('plain', background=theme.now(self.ROW_BG))
        self.tree.tag_configure('alt', background=theme.now(self.ROW_ALT))
        self.unresolved_tree.tag_configure(
            'tight', background=theme.now(self.TIGHT_BG))

    def _build_buttons(self):
        """Apply what was previewed, or walk away."""
        footer = ctk.CTkFrame(self, fg_color='transparent')
        footer.pack(fill=tk.X, side=tk.BOTTOM, padx=15, pady=(0, 15))

        ctk.CTkButton(footer, text="Cancel", width=110,
                      command=self.destroy).pack(side=tk.RIGHT, padx=5)
        if self._apply_callback is not None:
            ctk.CTkButton(footer, text="Apply", width=110,
                          command=self._apply).pack(side=tk.RIGHT)

    # ---- filling it in --------------------------------------------------

    def refresh(self):
        """Run the engine on a scratch copy and draw its answers."""
        for row in self.tree.get_children():
            self.tree.delete(row)
        for row in self.unresolved_tree.get_children():
            self.unresolved_tree.delete(row)

        self._plan = preview(self.project, self._options)

        for index, move in enumerate(self._plan.moves):
            tag = 'alt' if index % 2 else 'plain'
            self.tree.insert('', tk.END, tags=(tag,), values=(
                move.task_name,
                move.old_start.strftime('%Y-%m-%d') if move.old_start else '—',
                move.new_start.strftime('%Y-%m-%d') if move.new_start else '—',
                move.delay_days,
                move.new_finish.strftime('%Y-%m-%d') if move.new_finish else '—',
            ))

        for issue in self._plan.unresolved:
            self.unresolved_tree.insert('', tk.END, tags=('tight',), values=(
                issue.resource_name,
                issue.day.strftime('%Y-%m-%d'),
                f"+{issue.over_by:.1f}h",
                issue.detail,
            ))

        self._write_summary()

    def _write_summary(self) -> None:
        """The line above the table: found, moved, left over, slipped."""
        plan = self._plan
        if plan is None:
            return
        if not plan.overallocations_found:
            self.summary_label.configure(
                text="No resource is overallocated - nothing to level.")
            return

        text = (f"{plan.overallocations_found} overloaded day(s) found - "
                f"{len(plan.moves)} task(s) would move, "
                f"{len(plan.unresolved)} day(s) would stay over.")
        if plan.finish_slipped:
            text += "  The project's finish would slip."
        else:
            text += "  The project's finish is unchanged."
        if plan.skipped:
            text += (f"  {len(plan.skipped)} task(s) were skipped for "
                     "hard constraints.")
        if plan.gave_up:
            text += "  The run hit its pass cap - the links may cycle."
        self.summary_label.configure(text=text)

    # ---- Apply ----------------------------------------------------------

    def _apply(self) -> None:
        """
        Hand the run to whoever opened the window.

        The callback re-runs the engine on the real plan inside one undo
        command - deterministic, so it lands on exactly what the table
        showed - and this window has served its purpose once it does.
        """
        if self._apply_callback is None:
            return
        logger.info("Levelling preview applied: %s move(s), %s unresolved",
                    len(self._plan.moves), len(self._plan.unresolved))
        self._apply_callback(self._plan)
        self.destroy()


def show_leveling_preview(master, project: Project,
                          apply_callback: Optional[Callable] = None,
                          options: Optional[LevelingOptions] = None
                          ) -> Optional[LevelingPreviewWindow]:
    """
    Open the levelling preview window.

    RETURNS:
    --------
    Optional[LevelingPreviewWindow]
        The window, or None when it could not be built - a report that
        fails to open should not take the toolbar that opened it down
        with it.
    """
    try:
        return LevelingPreviewWindow(master, project,
                                     apply_callback=apply_callback,
                                     options=options)
    except Exception:
        logger.exception("Could not open the levelling preview")
        return None
