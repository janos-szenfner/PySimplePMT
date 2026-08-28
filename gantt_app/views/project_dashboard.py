"""
The project dashboard: what the plan adds up to, in four charts.

WHY THIS MODULE EXISTS:
======================
A Gantt chart says when everything happens and almost nothing about how the
plan is doing. How far along is it, where is the work concentrated, how much
of the plan is milestones rather than effort - those are read off a plan by
counting, and nobody counts. The dashboard answers them in one panel, beside
the same task list, and View > Charts switches between the two.

WHY IT IS DRAWN BY HAND:
=======================
Every mark here is put on a Tk canvas in plain Python. That is not a stylistic
preference, it is the only thing that works: the first version of this
dashboard built Plotly figures and loaded them into a tkinterweb HtmlFrame,
which renders no JavaScript, so it drew four charts' worth of nothing. The
Gantt view learned the same lesson before it - see GanttChartView.draw_chart -
and there is no reason to learn it twice.

Drawing it here also means it needs nothing fetched at runtime. A Plotly page
either carries a megabyte of plotly.js or links one from a CDN, and an
application that goes to the network to draw its own window is an application
that shows a blank panel on a train.

WHAT THE FOUR CHARTS SAY:
========================
Task Progress
    One bar per top-level row, the percentage it reports. What is moving.

Duration Allocation
    A donut of total duration split by task type. Where the effort sits, and
    how much of the plan is milestones - which hold none.

Duration per Item
    One bar per row, its own length. Which pieces are big.

Summary
    The five numbers underneath all of it; see kpi_metrics.

DEVELOPMENT NOTES:
------------------
The arithmetic is four module-level functions taking plain lists of
dictionaries, so what the dashboard claims can be tested without opening a
window. The widget draws; it does not calculate.

Durations are the ones the task list shows - working days, from
Task.duration_days - rather than the calendar span between the two dates. The
dashboard sits beside the grid, and a panel disagreeing with the column next
to it about how long a task is would be read as a fault in one of them.
"""

import tkinter as tk
from typing import Any, Dict, List, Optional, Tuple

import customtkinter as ctk

from gantt_app import theme
from gantt_app.models import Project, TASK_TYPES
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# What the plan adds up to
# ---------------------------------------------------------------------------

def dashboard_rows(project: Optional[Project]) -> List[Dict[str, Any]]:
    """
    The plan as flat rows, with everything the charts need on each one.

    PARAMETERS:
    -----------
    project : Optional[Project]
        The plan. None, or one with no tasks, gives an empty list.

    RETURNS:
    --------
    List[Dict[str, Any]]
        One dictionary per task: id, name, type, duration, progress, level.

    DEVELOPMENT NOTES:
    ------------------
    An empty plan gives no rows, and the dashboard says so. It used to hand
    back eight invented tasks - Project Planning, Design Phase, Implementation
    at 30% - so a reader who opened the dashboard before typing anything was
    shown a stranger's plan with their own project's name over it, and every
    number in the summary was fiction presented as measurement.
    """
    if project is None:
        return []

    rows = []
    for task in project.tasks:
        rows.append({
            'ID': task.id,
            'Name': task.name,
            'Type': task.task_type,
            'Duration': task.duration_days or 0,
            'Progress': task.progress or 0,
            'Level': _level_of(task, project),
        })
    return rows


def _level_of(task, project: Project) -> int:
    """
    How deep a row sits, counting the top level as one.

    DEVELOPMENT NOTES:
    ------------------
    Walked with a loop and a seen-set rather than by recursion. A plan whose
    parent links form a ring is not supposed to exist, but a dashboard is
    not the place to find out: recursion answers that with a blown stack and
    a window that will not open.
    """
    level = 1
    seen = {task.id}
    parent_id = task.parent_task_id
    while parent_id is not None and parent_id not in seen:
        parent = project.get_task_by_id(parent_id)
        if parent is None:
            break
        seen.add(parent_id)
        level += 1
        parent_id = parent.parent_task_id
    return level


def weighted_progress(rows: List[Dict[str, Any]]) -> float:
    """
    How far the plan has got, as one percentage.

    RETURNS:
    --------
    float
        SUM(duration * progress) / SUM(duration) over the top-level rows,
        and 0.0 when they hold no duration between them.

    DEVELOPMENT NOTES:
    ------------------
    Weighted by duration and taken over the top level only, so a plan is not
    reported as half done because half of its one-day rows are finished
    while the eight-day one has not started. Sub-tasks are left out because
    their work is already counted inside the row that brackets them.
    """
    top = [row for row in rows if row['Level'] == 1]
    total = sum(row['Duration'] for row in top)
    if not total:
        return 0.0
    return sum(row['Duration'] * row['Progress'] for row in top) / total


def duration_by_type(rows: List[Dict[str, Any]]) -> List[Tuple[str, int]]:
    """
    Total duration per task type, for the donut.

    RETURNS:
    --------
    List[Tuple[str, int]]
        (type, days) for every type present, in the order the model
        declares them so the colours do not move between two readings of
        the same plan.
    """
    totals: Dict[str, int] = {}
    for row in rows:
        totals[row['Type']] = totals.get(row['Type'], 0) + row['Duration']

    ordered = [kind for kind in TASK_TYPES if kind in totals]
    ordered += sorted(kind for kind in totals if kind not in TASK_TYPES)
    return [(kind, totals[kind]) for kind in ordered]


def kpi_metrics(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    The five numbers in the summary box.

    RETURNS:
    --------
    Dict[str, Any]
        total_scope   - days held by the top-level rows
        total_items   - how many rows there are
        milestones    - how many of them are milestones
        progress      - weighted_progress over the same rows
        active_share  - percentage of rows that have started
    """
    top = [row for row in rows if row['Level'] == 1]
    started = [row for row in rows if row['Progress'] > 0]
    return {
        'total_scope': sum(row['Duration'] for row in top),
        'total_items': len(rows),
        'milestones': len([row for row in rows
                           if row['Type'] == 'Milestone']),
        'progress': weighted_progress(rows),
        'active_share': (len(started) / len(rows) * 100) if rows else 0.0,
    }


# ---------------------------------------------------------------------------
# The panel
# ---------------------------------------------------------------------------

class ProjectDashboardFrame(ctk.CTkFrame):
    """
    The four charts, on one canvas, beside the task list.

    PARAMETERS:
    -----------
    master : widget
        Usually the paned window the Gantt chart also lives in.
    project : Optional[Project]
        The plan to summarise. refresh() re-reads it.

    DEVELOPMENT NOTES:
    ------------------
    One canvas rather than four, because the four quarters are drawn from
    one set of numbers and resized by one event. Everything is redrawn from
    scratch on every change; there is no incremental update to get wrong,
    and a dashboard redraw is a few hundred canvas items.
    """

    #: How much of the canvas the axis box leaves for the labels around it.
    PAD = 18
    TITLE_H = 26
    LEFT_LABEL_W = 130
    BOTTOM_LABEL_H = 62

    #: A redraw is skipped until the canvas is at least this big, which it
    #: is not while the pane is still being laid out.
    MIN_USEFUL_PX = 240

    #: How thick the donut's ring is drawn, as a share of its radius.
    RING_SHARE = 0.42

    def __init__(self, master, project: Optional[Project] = None, **kwargs):
        super().__init__(master, **kwargs)

        self.project = project
        self._last_size = (0, 0)

        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind('<Configure>', self._on_resize)

        self._redraw()

    # -- what the outside calls ------------------------------------------

    def refresh(self):
        """Read the plan again and redraw. Called when anything changes."""
        self._redraw()

    def apply_theme(self):
        """
        Redraw for the appearance now in force.

        Every colour on a canvas is written into the item that carries it,
        so nothing here follows a theme change until it is drawn again -
        the same reason the chart and the task grid have this method.
        """
        self._redraw()

    def set_project(self, project: Optional[Project]):
        """Point the dashboard at a different plan."""
        self.project = project
        self._redraw()

    # -- drawing ----------------------------------------------------------

    def _on_resize(self, event):
        """Redraw when the pane changes size, and not for a stray pixel."""
        if (abs(event.width - self._last_size[0]) < 4
                and abs(event.height - self._last_size[1]) < 4):
            return
        self._last_size = (event.width, event.height)
        self._redraw()

    def _size(self) -> Tuple[int, int]:
        """
        How big the canvas is to draw into.

        DEVELOPMENT NOTES:
        ------------------
        winfo_width answers 1 until Tk has laid the widget out, so two
        things stand in for it: the size the last Configure reported, and
        then the size the canvas was asked for. In the application the
        first of those is the real answer - Configure is where a pane's
        size arrives - and the second is what lets the drawing be checked
        without putting a window on somebody's screen, since Tk delivers no
        Configure to a widget that was never mapped.
        """
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        if width > 1 and height > 1:
            return width, height
        if self._last_size[0] > 1 and self._last_size[1] > 1:
            return self._last_size
        return self.canvas.winfo_reqwidth(), self.canvas.winfo_reqheight()

    def _redraw(self):
        """Put the whole dashboard on the canvas again."""
        try:
            if not self.canvas.winfo_exists():
                return
        except tk.TclError:
            return

        self.canvas.delete('all')
        width, height = self._size()
        self.canvas.configure(background=theme.now(theme.DASH_BOARD_BG))

        if width < self.MIN_USEFUL_PX or height < self.MIN_USEFUL_PX:
            # Still being laid out, or dragged too narrow to say anything.
            # The Configure that follows draws it; logged because a blank
            # dashboard is otherwise indistinguishable from a broken one
            logger.debug("Dashboard not drawn at %sx%s; too small to read",
                         width, height)
            return

        rows = dashboard_rows(self.project)
        if not rows:
            self._draw_empty(width, height)
            return

        half_w = width // 2
        half_h = height // 2
        self._draw_progress(rows, 0, 0, half_w, half_h)
        self._draw_donut(rows, half_w, 0, width - half_w, half_h)
        self._draw_workload(rows, 0, half_h, half_w, height - half_h)
        self._draw_summary(rows, half_w, half_h,
                           width - half_w, height - half_h)

    def _draw_empty(self, width: int, height: int):
        """
        What an empty plan gets: a sentence, not invented tasks.
        """
        self.canvas.create_text(
            width // 2, height // 2,
            text="Nothing to summarise yet.\n"
                 "Add a task to the plan and it will appear here.",
            fill=theme.now(theme.DASH_TICK_TEXT), justify=tk.CENTER,
            font=self._font(13))

    def _panel(self, x: int, y: int, width: int, height: int, title: str):
        """
        The paper one chart is drawn on, and its title.

        RETURNS:
        --------
        tuple[int, int, int, int]
            The area left inside it: left, top, right, bottom.
        """
        left, top = x + self.PAD // 2, y + self.PAD // 2
        right, bottom = x + width - self.PAD // 2, y + height - self.PAD // 2
        self.canvas.create_rectangle(
            left, top, right, bottom, width=0,
            fill=theme.now(theme.DASH_PLOT_BG))
        self.canvas.create_text(
            (left + right) // 2, top + self.TITLE_H // 2, text=title,
            fill=theme.now(theme.DASH_TITLE_TEXT), font=self._font(12, True))
        return left + self.PAD, top + self.TITLE_H, right - self.PAD, bottom

    def _font(self, size: int, bold: bool = False):
        """A canvas font, in the family Tk has everywhere."""
        return ('TkDefaultFont', size, 'bold') if bold \
            else ('TkDefaultFont', size)

    # -- 1: progress across the top-level rows ----------------------------

    def _draw_progress(self, rows, x, y, width, height):
        """One horizontal bar per top-level row, 0 to 100 per cent."""
        left, top, right, bottom = self._panel(
            x, y, width, height, "Task Progress (%)")

        top_rows = [row for row in rows if row['Level'] == 1]
        if not top_rows:
            self._say(left, top, right, bottom, "No top-level rows")
            return

        plot_left = left + self.LEFT_LABEL_W
        plot_bottom = bottom - 28
        if plot_left >= right - 40 or plot_bottom <= top + 10:
            return

        axis = theme.now(theme.DASH_AXIS)
        self.canvas.create_rectangle(plot_left, top, right, plot_bottom,
                                     outline=axis, width=1)

        # The scale, every twenty per cent
        for percent in range(0, 101, 20):
            at = plot_left + (right - plot_left) * percent / 100
            if percent:
                self.canvas.create_line(at, top, at, plot_bottom,
                                        fill=theme.now(theme.DASH_GRID),
                                        dash=(2, 3))
            self.canvas.create_text(at, plot_bottom + 10, text=f"{percent}%",
                                    fill=theme.now(theme.DASH_TICK_TEXT),
                                    font=self._font(9))

        band = (plot_bottom - top) / len(top_rows)
        thickness = max(4, min(22, band * 0.55))
        for index, row in enumerate(top_rows):
            middle = top + band * (index + 0.5)
            self.canvas.create_text(
                plot_left - 8, middle, text=self._clip(row['Name'], 20),
                anchor=tk.E, fill=theme.now(theme.DASH_TICK_TEXT),
                font=self._font(10))

            share = max(0.0, min(100.0, float(row['Progress']))) / 100
            end = plot_left + (right - plot_left) * share
            if end > plot_left + 1:
                self.canvas.create_rectangle(
                    plot_left + 1, middle - thickness / 2,
                    end, middle + thickness / 2,
                    fill=theme.now(theme.DASH_PROGRESS_BAR), width=0)
            self.canvas.create_text(
                end + 6, middle, text=f"{int(row['Progress'])}%", anchor=tk.W,
                fill=theme.now(theme.DASH_TICK_TEXT), font=self._font(9))

    # -- 2: where the duration sits ---------------------------------------

    def _draw_donut(self, rows, x, y, width, height):
        """Total duration split by task type, as a ring with a legend."""
        left, top, right, bottom = self._panel(
            x, y, width, height, "Duration Allocation by Task Type (Days)")

        shares = duration_by_type(rows)
        total = sum(days for _kind, days in shares)
        colours = self._series_colours()

        legend_h = min(len(shares) * 18 + 6, max(0, (bottom - top) // 2))
        ring_bottom = bottom - legend_h
        size = min(right - left, ring_bottom - top) - 10

        if total <= 0:
            self._say(left, top, right, bottom,
                      "No duration to divide up yet")
        elif size > 40:
            radius = size / 2
            cx = (left + right) / 2
            cy = (top + ring_bottom) / 2
            thickness = radius * self.RING_SHARE
            inset = thickness / 2
            box = (cx - radius + inset, cy - radius + inset,
                   cx + radius - inset, cy + radius - inset)

            start = 90.0
            for index, (_kind, days) in enumerate(shares):
                if not days:
                    continue
                extent = -360.0 * days / total
                if extent > -0.05:
                    continue
                self.canvas.create_arc(
                    *box, start=start, extent=extent, style=tk.ARC,
                    outline=colours[index % len(colours)],
                    width=int(max(2, thickness)))
                start += extent

        # The legend carries the numbers, including the types holding none
        row_y = bottom - legend_h + 10
        for index, (kind, days) in enumerate(shares):
            if row_y > bottom - 4:
                break
            share = (days / total * 100) if total else 0.0
            self.canvas.create_rectangle(
                left, row_y - 5, left + 10, row_y + 5, width=0,
                fill=colours[index % len(colours)])
            self.canvas.create_text(
                left + 18, row_y, anchor=tk.W,
                text=f"{kind}  {days}d  ({share:.1f}%)",
                fill=theme.now(theme.DASH_TICK_TEXT), font=self._font(10))
            row_y += 18

    def _series_colours(self) -> List[str]:
        """The donut's colours, resolved for the appearance in force."""
        return [theme.now(pair) for pair in (
            theme.DASH_SERIES_1, theme.DASH_SERIES_2,
            theme.DASH_SERIES_3, theme.DASH_SERIES_4)]

    # -- 3: how long each row is ------------------------------------------

    def _draw_workload(self, rows, x, y, width, height):
        """One vertical bar per row, its own duration in days."""
        left, top, right, bottom = self._panel(
            x, y, width, height, "Duration per Item (Days)")

        longest = max((row['Duration'] for row in rows), default=0)
        if longest <= 0:
            self._say(left, top, right, bottom, "Every row is zero days long")
            return

        plot_left = left + 30
        plot_bottom = bottom - self.BOTTOM_LABEL_H
        if plot_left >= right - 20 or plot_bottom <= top + 20:
            return

        axis = theme.now(theme.DASH_AXIS)
        self.canvas.create_rectangle(plot_left, top, right, plot_bottom,
                                     outline=axis, width=1)

        # A gridline every step days, at a step that keeps the count small
        step = max(1, -(-longest // 5))
        value = step
        while value <= longest:
            at = plot_bottom - (plot_bottom - top) * value / longest
            self.canvas.create_line(plot_left, at, right, at,
                                    fill=theme.now(theme.DASH_GRID),
                                    dash=(2, 3))
            self.canvas.create_text(plot_left - 6, at, text=str(value),
                                    anchor=tk.E, font=self._font(9),
                                    fill=theme.now(theme.DASH_TICK_TEXT))
            value += step

        band = (right - plot_left) / len(rows)
        thickness = max(3, min(34, band * 0.6))
        for index, row in enumerate(rows):
            middle = plot_left + band * (index + 0.5)
            if row['Duration'] > 0:
                bar_top = plot_bottom - ((plot_bottom - top)
                                         * row['Duration'] / longest)
                self.canvas.create_rectangle(
                    middle - thickness / 2, bar_top,
                    middle + thickness / 2, plot_bottom - 1,
                    fill=theme.now(theme.DASH_DURATION_BAR), width=0)
                self.canvas.create_text(
                    middle, bar_top - 7, text=f"{row['Duration']}d",
                    fill=theme.now(theme.DASH_TICK_TEXT), font=self._font(8))
            self._angled(middle, plot_bottom + 6, row['Name'])

    def _angled(self, x: float, y: float, text: str):
        """
        A label under a bar, turned out of the way of its neighbours.

        DEVELOPMENT NOTES:
        ------------------
        Tk grew the angle option for canvas text in 8.6, and the Tk that
        ships with macOS is 8.5. So the turn is attempted and the flat
        label is what a Tk without it gets - shorter, because a flat label
        has a bar's width to fit in rather than a diagonal.
        """
        try:
            self.canvas.create_text(
                x, y, text=self._clip(text, 18), angle=35, anchor=tk.NE,
                fill=theme.now(theme.DASH_TICK_TEXT), font=self._font(9))
        except tk.TclError:
            self.canvas.create_text(
                x, y, text=self._clip(text, 8), anchor=tk.N,
                fill=theme.now(theme.DASH_TICK_TEXT), font=self._font(8))

    # -- 4: the numbers underneath ----------------------------------------

    def _draw_summary(self, rows, x, y, width, height):
        """The five figures, in a box of their own."""
        left, top, right, bottom = self._panel(
            x, y, width, height, "Summary")

        metrics = kpi_metrics(rows)
        lines = (
            ("Total project scope", f"{metrics['total_scope']} days"),
            ("Total items tracked", f"{metrics['total_items']} items"),
            ("Milestones", f"{metrics['milestones']}"),
            ("Overall completion", f"{metrics['progress']:.2f}%"),
            ("Rows started", f"{metrics['active_share']:.0f}%"),
        )

        box_h = min(len(lines) * 24 + 28, bottom - top)
        box_top = top + max(0, (bottom - top - box_h) // 2)
        self.canvas.create_rectangle(
            left, box_top, right, box_top + box_h,
            fill=theme.now(theme.DASH_KPI_BG),
            outline=theme.now(theme.DASH_KPI_BORDER), width=1)

        row_y = box_top + 22
        for caption, value in lines:
            if row_y > box_top + box_h - 6:
                break
            self.canvas.create_text(
                left + 16, row_y, text=caption, anchor=tk.W,
                fill=theme.now(theme.DASH_TICK_TEXT), font=self._font(10))
            self.canvas.create_text(
                right - 16, row_y, text=value, anchor=tk.E,
                fill=theme.now(theme.DASH_TITLE_TEXT),
                font=self._font(11, True))
            row_y += 24

    # -- odds and ends -----------------------------------------------------

    def _say(self, left, top, right, bottom, text: str):
        """A sentence in the middle of a panel that has nothing to draw."""
        self.canvas.create_text(
            (left + right) // 2, (top + bottom) // 2, text=text,
            fill=theme.now(theme.DASH_TICK_TEXT), font=self._font(10))

    @staticmethod
    def _clip(text: str, longest: int) -> str:
        """A name cut to fit, with an ellipsis to say it was cut."""
        text = str(text or '')
        return text if len(text) <= longest else text[:longest - 1] + '…'
