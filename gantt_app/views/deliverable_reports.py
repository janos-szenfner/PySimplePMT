"""
Deliverable reports - the summary the Deliverables ribbon's button opens.

WHY THIS MODULE EXISTS:
======================
The board is the editing surface; this is the reading surface. A project
manager who wants "how are the deliverables doing" should not have to
count rows by eye - the panel answers it in three pieces the issue's list
calls the core of the suite: the RAG summary cards up top, the status
distribution bar, and the status report table under them.

DEVELOPMENT NOTES:
------------------
Everything draws from the same health helpers the grid colours by
(deliverable_health / overall_deliverable_health in core.deliverable), so
a row that is red in the grid is red in the report - the two surfaces
cannot disagree about what "late" means. The chart is a plain Canvas:
matplotlib was removed from the dependencies, and a stacked bar is a
dozen rectangles either way.
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict

import customtkinter as ctk

from gantt_app.views import theme
from gantt_app.views.modal import grab_when_visible
from gantt_app.core.deliverable import (
    deliverable_health, overall_deliverable_health)
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


#: The health states, in the order the report counts them - worst last so
#: the stacked bar's tail is the good news.
HEALTH_ORDER = ('not_started', 'on_track', 'at_risk', 'overdue', 'done')

HEALTH_LABELS = {
    'done': 'Done',
    'on_track': 'On Track',
    'not_started': 'Not Started',
    'at_risk': 'At Risk',
    'overdue': 'Overdue',
}

HEALTH_COLORS = {
    'done': theme.POSITIVE_TEXT,
    'on_track': ('#1565c0', '#7cb3f5'),
    'not_started': theme.MUTED_TEXT,
    'at_risk': theme.WARNING_TEXT,
    'overdue': theme.NEGATIVE_TEXT,
}


class DeliverableReportsDialog(ctk.CTkToplevel):
    """
    The reports window: summary cards, a distribution bar, a status table.

    PARAMETERS:
    -----------
    master : widget
        The board's toplevel, so the panel sits over the app it belongs to.
    project : Project
        The plan whose deliverables are reported on.
    """

    def __init__(self, master, project) -> None:
        super().__init__(master)
        self.project = project
        self.title('Deliverable Reports')
        self.geometry('720x560')
        self.transient(master)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_cards()
        self._build_chart()
        self._build_table()

        grab_when_visible(self)

    # ------------------------------------------------------------------
    # The cards
    # ------------------------------------------------------------------

    def _build_cards(self) -> None:
        """The RAG strip: one card per health state, plus the totals."""
        strip = ctk.CTkFrame(self, fg_color='transparent')
        strip.grid(row=0, column=0, sticky=tk.EW, padx=12, pady=(12, 4))

        deliverables = self.project.deliverables
        counts = self._health_counts(deliverables)
        total = len(deliverables)
        done = counts.get('done', 0)
        percent = int(round(100 * done / total)) if total else 0
        overall = overall_deliverable_health(deliverables)

        specs = (
            ('Overall', HEALTH_LABELS[overall], HEALTH_COLORS[overall]),
            ('Total', str(total), theme.TEXT),
            ('Complete', f'{percent}%', theme.TEXT),
        ) + tuple(
            (HEALTH_LABELS[h], str(counts.get(h, 0)), HEALTH_COLORS[h])
            for h in ('done', 'on_track', 'at_risk', 'overdue',
                      'not_started')
        )

        for caption, value, colour in specs:
            card = ctk.CTkFrame(strip)
            card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True,
                      padx=(0, 4))
            ctk.CTkLabel(
                card, text=value,
                font=ctk.CTkFont(size=18, weight='bold'),
                text_color=theme.now(colour)).pack(
                    fill=tk.X, padx=8, pady=(8, 0))
            ctk.CTkLabel(
                card, text=caption,
                font=ctk.CTkFont(size=11),
                text_color=theme.now(theme.MUTED_TEXT)).pack(
                    fill=tk.X, padx=8, pady=(0, 8))

    @staticmethod
    def _health_counts(deliverables) -> Dict[str, int]:
        """Rows by health state, for the cards and the chart."""
        counts: Dict[str, int] = {}
        for deliverable in deliverables:
            health = deliverable_health(deliverable)
            counts[health] = counts.get(health, 0) + 1
        return counts

    # ------------------------------------------------------------------
    # The chart
    # ------------------------------------------------------------------

    def _build_chart(self) -> None:
        """The status distribution: one stacked bar, every row's health."""
        frame = ctk.CTkFrame(self)
        frame.grid(row=1, column=0, sticky=tk.EW, padx=12, pady=4)
        ctk.CTkLabel(
            frame, text='Status distribution',
            font=ctk.CTkFont(weight='bold'), anchor=tk.W).pack(
                fill=tk.X, padx=10, pady=(8, 0))

        counts = self._health_counts(self.project.deliverables)
        total = sum(counts.values())

        canvas = tk.Canvas(frame, height=40, highlightthickness=0,
                           borderwidth=0)
        canvas.pack(fill=tk.X, padx=10, pady=(4, 0))
        legend = ctk.CTkFrame(frame, fg_color='transparent')
        legend.pack(fill=tk.X, padx=10, pady=(0, 8))

        def paint(_event=None) -> None:
            canvas.delete('all')
            width = max(1, canvas.winfo_width())
            height = 28
            top = 4
            if total == 0:
                canvas.create_text(
                    width // 2, top + height // 2,
                    text='No deliverables yet',
                    fill=theme.now(theme.MUTED_TEXT))
                return
            x = 0.0
            for health in HEALTH_ORDER:
                share = counts.get(health, 0)
                if not share:
                    continue
                x2 = x + width * share / total
                canvas.create_rectangle(
                    x, top, x2, top + height,
                    fill=theme.now(HEALTH_COLORS[health]), outline='')
                if x2 - x > 20:
                    canvas.create_text(
                        (x + x2) / 2, top + height // 2, text=str(share),
                        fill='#ffffff', font=('Arial', 10, 'bold'))
                x = x2

        canvas.bind('<Configure>', paint)
        self.after_idle(paint)

        for health in HEALTH_ORDER:
            if counts.get(health, 0) == 0:
                continue
            item = ctk.CTkFrame(legend, fg_color='transparent')
            item.pack(side=tk.LEFT, padx=(0, 10))
            ctk.CTkLabel(
                item, text='■',
                text_color=theme.now(HEALTH_COLORS[health])).pack(
                    side=tk.LEFT)
            ctk.CTkLabel(
                item,
                text=f" {HEALTH_LABELS[health]} ({counts[health]})",
                font=ctk.CTkFont(size=11)).pack(side=tk.LEFT)

    # ------------------------------------------------------------------
    # The table
    # ------------------------------------------------------------------

    def _build_table(self) -> None:
        """The status report: every deliverable, its flag and its owner."""
        frame = ctk.CTkFrame(self)
        frame.grid(row=2, column=0, sticky=tk.NSEW, padx=12, pady=(4, 12))
        frame.grid_rowconfigure(1, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            frame, text='Deliverable Status Report',
            font=ctk.CTkFont(weight='bold'), anchor=tk.W).grid(
                row=0, column=0, columnspan=2, sticky=tk.W,
                padx=10, pady=(8, 2))

        columns = ('No', 'Responsible', 'Status', 'Progress',
                   'Due Date', 'Health')
        tree = ttk.Treeview(frame, columns=columns,
                            show='tree headings', selectmode='browse')
        theme.style_treeview('Deliverables.Treeview')
        tree.configure(style='Deliverables.Treeview')
        tree.heading('#0', text='Name', anchor=tk.W)
        tree.column('#0', width=220, minwidth=120)
        for name in columns:
            anchor = tk.CENTER if name in ('Status', 'Progress',
                                           'Due Date', 'Health') else tk.W
            tree.heading(name, text=name, anchor=tk.W)
            tree.column(name, width=80 if name != 'Responsible' else 110,
                        minwidth=50, stretch=False, anchor=anchor)

        numbers = self.project.deliverable_display_ids()
        for health, colour in HEALTH_COLORS.items():
            tree.tag_configure(f'health_{health}',
                               foreground=theme.now(colour))
        # The bands carry the striping's background only; the health tag
        # owns the foreground, so the two never fight for an option.
        tree.tag_configure('evenrow',
                           background=theme.now(theme.GRID_ROW_BG))
        tree.tag_configure('oddrow',
                           background=theme.now(theme.GRID_ROW_ALT))

        for index, deliverable in enumerate(
                self.project.deliverable_display_order()):
            health = deliverable_health(deliverable)
            band = 'evenrow' if index % 2 == 0 else 'oddrow'
            number = numbers.get(deliverable.id)
            parent = deliverable.parent_id
            tree.insert(
                parent if parent and tree.exists(parent) else '',
                tk.END, iid=deliverable.id, open=True,
                text=deliverable.name or '(unnamed)',
                tags=(f'health_{health}', band),
                values=(
                    f"D-{str(number).zfill(3)}" if number else '',
                    ', '.join(deliverable.assignees),
                    deliverable.status,
                    f'{deliverable.progress}%',
                    (deliverable.due_date.strftime('%Y-%m-%d')
                     if deliverable.due_date else ''),
                    HEALTH_LABELS[health],
                ))

        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL,
                                  command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.grid(row=1, column=0, sticky=tk.NSEW, padx=(10, 0),
                  pady=(0, 10))
        scrollbar.grid(row=1, column=1, sticky=tk.NS, pady=(0, 10))


def show_deliverable_reports(master, project) -> DeliverableReportsDialog:
    """Open the reports panel over the board's window."""
    logger.info("Deliverable reports opened")
    return DeliverableReportsDialog(master, project)
