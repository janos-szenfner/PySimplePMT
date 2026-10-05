"""
Drawing the dashboard and the timeline, for the screen and for export.

WHY THIS MODULE EXISTS:
======================
Both boards draw their contents twice - onto the Tk canvas in the window
and into a Pillow image for PNG/PDF export - and a drawing written twice
is a drawing that drifts apart. The panels and timeline styles here draw
against a drawpen pen instead, so the same code produces both: the view
hands over a CanvasPen, the exporter an ImagePen (issues #66, #83).

WHAT IS IN HERE:
================
dashboard_rows and friends  - the plan as flat rows, the arithmetic the
                              charts read (kept importable from
                              views.project_dashboard for the tests).
DASHBOARD_PANELS            - the toggleable panel registry: id, title,
                              draw function.
TIMELINE_STYLES             - the timeline's clickable styles: lanes,
                              roadmap, callouts, chevrons, phases.
render_dashboard            - lays out the enabled panels in the 2-wide
                              grid and draws them.
render_timeline             - draws the flagged rows in the picked style.

DEVELOPMENT NOTES:
------------------
Nothing here touches Tk or knows which theme is in force: a palette
dictionary comes in with the call (views.theme builds it for the screen;
the exporter passes the same one), so tests can draw the boards without
a display. Rows and items are plain dictionaries for the same reason.

The timeline draws the rows the planner flagged - a task's Show in
timeline switch is finally what its name says (issues #72, #83).
"""

import math
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

from gantt_app.core.baselines import rolled_task_costs
from gantt_app.core.models import Project, TASK_TYPES
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)

Rect = Tuple[float, float, float, float]

#: The palette keys every draw here reads. views.theme.view_palette
#: builds the dictionary for the appearance in force; exports use the
#: same, so a file looks like the screen did.
PALETTE_KEYS = (
    'bg', 'panel_bg', 'title', 'tick', 'axis', 'grid',
    'progress_bar', 'progress_under', 'duration_bar',
    'kpi_bg', 'kpi_border',
    'header_bg', 'header_text', 'band_bg', 'band_text',
    'lane_bg', 'lane_text', 'spine', 'today',
)


def _clip(text: str, longest: int) -> str:
    """A name cut to fit, with an ellipsis to say it was cut."""
    text = str(text or '')
    return text if len(text) <= longest else text[:longest - 1] + '…'


def clip_to_width(pen, text: str, size: int, max_px: float,
                  bold=False) -> str:
    """As much of the label as fits in the pixels it is given."""
    text = str(text or '')
    if pen.text_width(text, size, bold=bold) <= max_px:
        return text
    clipped = text
    while clipped and pen.text_width(clipped + '…', size,
                                     bold=bold) > max_px:
        clipped = clipped[:-1]
    return clipped + '…' if clipped else ''


def _plural(word: str, count) -> str:
    """The word, with an s on it unless there is exactly one."""
    return word if count == 1 else word + 's'


# ---------------------------------------------------------------------------
# The plan as rows - the dashboard's arithmetic
# ---------------------------------------------------------------------------

def dashboard_rows(project: Optional[Project]) -> List[Dict[str, Any]]:
    """
    The plan as flat rows, with everything the charts need on each one.

    An empty plan gives no rows, and the dashboard says so. It used to
    hand back eight invented tasks - a reader who opened the dashboard
    before typing anything was shown a stranger's plan with their own
    project's name over it, and every number in the summary was fiction
    presented as measurement.
    """
    if project is None:
        return []

    rows = []
    costs = rolled_task_costs(project)
    for task in project.tasks:
        rows.append({
            'ID': task.id,
            'Name': task.name,
            'Type': task.task_type,
            'Milestone': task.effective_milestone,
            'Status': getattr(task, 'status', 'Active') or 'Active',
            'Duration': task.duration_days or 0,
            'Progress': task.progress or 0,
            'Level': _level_of(task, project),
            'Cost': costs.get(task.id, 0.0),
        })
    return rows


def _level_of(task, project: Project) -> int:
    """
    How deep a row sits, counting the top level as one.

    Walked with a loop and a seen-set rather than by recursion. A plan
    whose parent links form a ring is not supposed to exist, but a
    dashboard is not the place to find out: recursion answers that with
    a blown stack and a window that will not open.
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

    SUM(duration * progress) / SUM(duration) over the top-level rows,
    and 0.0 when they hold no duration between them. Weighted by
    duration and taken over the top level only, so a plan is not
    reported as half done because half of its one-day rows are finished
    while the eight-day one has not started.
    """
    top = [row for row in rows if row['Level'] == 1]
    total = sum(row['Duration'] for row in top)
    if not total:
        return 0.0
    return sum(row['Duration'] * row['Progress'] for row in top) / total


def duration_by_type(rows: List[Dict[str, Any]]) -> List[Tuple[str, int]]:
    """
    Total duration per task type, for the donut.

    (type, days) for every type present, in the order the model declares
    them so the colours do not move between two readings of the same plan.
    """
    totals: Dict[str, int] = {}
    for row in rows:
        # Milestone stopped being a type in issue #73 - the flag column
        # is what still gives the donut its (zero-day) slice.
        kind = 'Milestone' if row.get('Milestone') else row['Type']
        totals[kind] = totals.get(kind, 0) + row['Duration']

    ordered = [kind for kind in TASK_TYPES if kind in totals]
    ordered += sorted(kind for kind in totals if kind not in TASK_TYPES)
    return [(kind, totals[kind]) for kind in ordered]


def kpi_metrics(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    The eight numbers in the summary box.

    Completion is the plan's overall completion, weighted by how long
    each row is - not the average of the percentages on them. The three
    shares are the Status field a row carries - the letters the task
    list's own Status column uses, an empty cell for Active and the E
    and I for Estimated and Inactive - counted on their own so they
    come to a hundred even when rounding does not.
    """
    top = [row for row in rows if row['Level'] == 1]

    def share(status: str) -> float:
        if not rows:
            return 0.0
        n = len([row for row in rows if row.get('Status', 'Active') == status])
        return n / len(rows) * 100

    estimated_share = share('Estimated')
    inactive_share = share('Inactive')
    # Active is the default the column leaves blank, so every row that is
    # not explicitly Estimated or Inactive counts towards it - which is
    # what the blank cell means and how the coercion above already
    # treats 'Draft'.
    active_share = (100.0 - estimated_share - inactive_share) if rows else 0.0
    return {
        'total_scope': sum(row['Duration'] for row in top),
        'total_items': len(rows),
        'milestones': len([row for row in rows if row['Milestone']]),
        # Rolled up, so the top-level rows' costs are the plan's whole
        # spend with nothing counted twice
        'total_cost': sum(row.get('Cost', 0.0) for row in top),
        'completion': weighted_progress(rows),
        'active_share': active_share,
        'estimated_share': estimated_share,
        'inactive_share': inactive_share,
    }


# ---------------------------------------------------------------------------
# The dashboard's panel registry (issue #66)
# ---------------------------------------------------------------------------

#: How much of a panel the border and its title leave the chart.
PANEL_PAD = 18
PANEL_TITLE_H = 26
LEFT_LABEL_W = 130
BOTTOM_LABEL_H = 62

#: How thick the donut's ring is drawn, as a share of its radius.
RING_SHARE = 0.42


def _panel(pen, palette, x, y, width, height, title: str) -> Rect:
    """The paper one chart is drawn on, and its title; the inside rect."""
    left, top = x + PANEL_PAD // 2, y + PANEL_PAD // 2
    right = x + width - PANEL_PAD // 2
    bottom = y + height - PANEL_PAD // 2
    pen.rect(left, top, right, bottom, fill=palette['panel_bg'])
    pen.text((left + right) // 2, top + PANEL_TITLE_H // 2, title,
             fill=palette['title'], size=12, bold=True)
    return left + PANEL_PAD, top + PANEL_TITLE_H, right - PANEL_PAD, bottom


def _say(pen, palette, left, top, right, bottom, text):
    """A sentence in the middle of a panel that has nothing to draw."""
    pen.text((left + right) / 2, (top + bottom) / 2, text,
             fill=palette['tick'], size=10)


def draw_progress(pen, rows, palette, x, y, width, height):
    """Panel 1: one horizontal bar per top-level row, 0 to 100 per cent."""
    left, top, right, bottom = _panel(
        pen, palette, x, y, width, height, "Task Progress (%)")

    top_rows = [row for row in rows if row['Level'] == 1]
    if not top_rows:
        _say(pen, palette, left, top, right, bottom, "No top-level rows")
        return

    plot_left = left + LEFT_LABEL_W
    plot_bottom = bottom - 28
    if plot_left >= right - 40 or plot_bottom <= top + 10:
        return

    pen.rect(plot_left, top, right, plot_bottom,
             outline=palette['axis'], width=1)

    # The scale, every twenty per cent
    for percent in range(0, 101, 20):
        at = plot_left + (right - plot_left) * percent / 100
        if percent:
            pen.line((at, top, at, plot_bottom), fill=palette['grid'],
                     dash=(2, 3))
        pen.text(at, plot_bottom + 10, f"{percent}%",
                 fill=palette['tick'], size=9)

    band = (plot_bottom - top) / len(top_rows)
    thickness = max(4, min(22, band * 0.55))
    for index, row in enumerate(top_rows):
        middle = top + band * (index + 0.5)
        pen.text(plot_left - 8, middle, _clip(row['Name'], 20),
                 anchor='e', fill=palette['tick'], size=10)

        share = max(0.0, min(100.0, float(row['Progress']))) / 100
        end = plot_left + (right - plot_left) * share
        if end > plot_left + 1:
            pen.rect(plot_left + 1, middle - thickness / 2,
                     end, middle + thickness / 2,
                     fill=palette['progress_bar'])
        pen.text(end + 6, middle, f"{int(row['Progress'])}%", anchor='w',
                 fill=palette['tick'], size=9)


def draw_donut(pen, rows, palette, x, y, width, height):
    """Panel 2: total duration split by task type, a ring with a legend."""
    left, top, right, bottom = _panel(
        pen, palette, x, y, width, height,
        "Duration Allocation by Task Type (Days)")

    shares = duration_by_type(rows)
    total = sum(days for _kind, days in shares)
    colours = palette['series']

    legend_h = min(len(shares) * 18 + 6, max(0, (bottom - top) // 2))
    ring_bottom = bottom - legend_h
    size = min(right - left, ring_bottom - top) - 10

    if total <= 0:
        _say(pen, palette, left, top, right, bottom,
             "No duration to divide up yet")
    elif size > 40:
        radius = size / 2
        cx = (left + right) / 2
        cy = (top + ring_bottom) / 2
        thickness = radius * RING_SHARE
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
            pen.arc(*box, start=start, extent=extent,
                    outline=colours[index % len(colours)],
                    width=int(max(2, thickness)))
            start += extent

    # The legend carries the numbers, including the types holding none
    row_y = bottom - legend_h + 10
    for index, (kind, days) in enumerate(shares):
        if row_y > bottom - 4:
            break
        share = (days / total * 100) if total else 0.0
        pen.rect(left, row_y - 5, left + 10, row_y + 5,
                 fill=colours[index % len(colours)])
        pen.text(left + 18, row_y, anchor='w',
                 content=f"{kind}  {days}d  ({share:.1f}%)",
                 fill=palette['tick'], size=10)
        row_y += 18


def draw_workload(pen, rows, palette, x, y, width, height):
    """Panel 3: one vertical bar per row, its own duration in days."""
    left, top, right, bottom = _panel(
        pen, palette, x, y, width, height, "Duration per Item (Days)")

    longest = max((row['Duration'] for row in rows), default=0)
    if longest <= 0:
        _say(pen, palette, left, top, right, bottom,
             "Every row is zero days long")
        return

    plot_left = left + 30
    plot_bottom = bottom - BOTTOM_LABEL_H
    if plot_left >= right - 20 or plot_bottom <= top + 20:
        return

    pen.rect(plot_left, top, right, plot_bottom,
             outline=palette['axis'], width=1)

    # A gridline every step days, at a step that keeps the count small
    step = max(1, -(-longest // 5))
    value = step
    while value <= longest:
        at = plot_bottom - (plot_bottom - top) * value / longest
        pen.line((plot_left, at, right, at), fill=palette['grid'],
                 dash=(2, 3))
        pen.text(plot_left - 6, at, str(value), anchor='e', size=9,
                 fill=palette['tick'])
        value += step

    band = (right - plot_left) / len(rows)
    thickness = max(3, min(34, band * 0.6))
    for index, row in enumerate(rows):
        middle = plot_left + band * (index + 0.5)
        if row['Duration'] > 0:
            bar_top = plot_bottom - ((plot_bottom - top)
                                     * row['Duration'] / longest)
            pen.rect(middle - thickness / 2, bar_top,
                     middle + thickness / 2, plot_bottom - 1,
                     fill=palette['duration_bar'])
            pen.text(middle, bar_top - 7, f"{row['Duration']}d",
                     fill=palette['tick'], size=8)
        pen.text(middle, plot_bottom + 6, _clip(row['Name'], 18),
                 anchor='ne', angle=35, fill=palette['tick'], size=9)


def draw_summary(pen, rows, palette, x, y, width, height):
    """
    Panel 4: the eight figures, in a box of their own.

    The three status lines are the Status field the task list's own
    column shows: Active, which that column leaves blank, and Estimated
    and Inactive, which it marks E and I. They are written as a set that
    comes to a hundred, so the reader can weigh how much of the plan is
    firm against how much is still an estimate or set aside.
    """
    left, top, right, bottom = _panel(
        pen, palette, x, y, width, height, "Summary")

    metrics = kpi_metrics(rows)
    lines = (
        ("Total Project Scope",
         f"{metrics['total_scope']} "
         f"{_plural('Day', metrics['total_scope'])}"),
        ("Total Items Tracked",
         f"{metrics['total_items']} "
         f"{_plural('Item', metrics['total_items'])}"),
        ("Milestones Count",
         f"{metrics['milestones']} "
         f"{_plural('Milestone', metrics['milestones'])}"),
        ("Total Committed Cost", f"${metrics['total_cost']:g}"),
        ("Overall Completion", f"{metrics['completion']:.2f}%"),
        ("Active Status", f"{metrics['active_share']:.0f}% Active"),
        ("Estimated Status",
         f"{metrics['estimated_share']:.0f}% Estimated (E)"),
        ("Inactive Status",
         f"{metrics['inactive_share']:.0f}% Inactive (I)"),
    )

    box_h = min(len(lines) * 24 + 28, bottom - top)
    box_top = top + max(0, (bottom - top - box_h) // 2)
    pen.rect(left, box_top, right, box_top + box_h,
             fill=palette['kpi_bg'], outline=palette['kpi_border'],
             width=1)

    row_y = box_top + 22
    for caption, value in lines:
        if row_y > box_top + box_h - 6:
            break
        pen.text(left + 16, row_y, caption, anchor='w',
                 fill=palette['tick'], size=10)
        pen.text(right - 16, row_y, value, anchor='e',
                 fill=palette['title'], size=11, bold=True)
        row_y += 24


#: The panels the dashboard can show, in the order the Panels menu lists
#: them. Each is (id, title, draw): the id is what settings.json keeps,
#: the title heads the panel, and draw paints inside the pen rect it is
#: given. Built-ins only for now (issue #66); adding one is a row here.
DASHBOARD_PANELS: List[Tuple[str, str, Callable]] = [
    ('progress', "Task Progress (%)", draw_progress),
    ('donut', "Duration Allocation by Task Type (Days)", draw_donut),
    ('workload', "Duration per Item (Days)", draw_workload),
    ('summary', "Summary", draw_summary),
]

#: A dashboard holds four panels at most, two to a row (issue #66).
MAX_PANELS = 4
PANELS_PER_ROW = 2


def all_panel_ids() -> List[str]:
    """Every panel the dashboard knows, in registry order."""
    return [panel_id for panel_id, _t, _d in DASHBOARD_PANELS]


def sanitize_panel_ids(ids) -> List[str]:
    """
    The panel ids from a settings file, filtered to ones that exist.

    A name the registry does not carry - written by hand, or by a
    version that had a panel this one does not - is dropped rather than
    drawn as an empty quarter, and the four-panel cap is applied here so
    a settings file holding more simply stops at the fourth.
    """
    known = all_panel_ids()
    unknown = [pid for pid in (ids or []) if pid not in known]
    if unknown:
        logger.warning("Ignoring unknown dashboard panel(s) %s", unknown)
    if ids and len([pid for pid in ids if pid in known]) > MAX_PANELS:
        logger.warning("More than %d panels saved; keeping the first %d",
                       MAX_PANELS, MAX_PANELS)
    return [pid for pid in (ids or []) if pid in known][:MAX_PANELS]


def dashboard_layout(count: int, width: float,
                     height: float) -> List[Rect]:
    """
    The cell each enabled panel draws in: two across, top to bottom.

    One panel gets the whole board; two split it side by side; three and
    four form the grid the cap allows (issue #66).
    """
    if count <= 0:
        return []
    cols = 1 if count == 1 else PANELS_PER_ROW
    rows = math.ceil(count / cols)
    cell_w, cell_h = width / cols, height / rows
    return [
        (cell_w * (i % cols), cell_h * (i // cols), cell_w, cell_h)
        for i in range(count)
    ]


def render_dashboard(pen, rows: List[Dict[str, Any]], palette,
                     enabled_ids, maximized_id=None,
                     width=0, height=0) -> List[Dict]:
    """
    Draw the enabled panels and report where each one landed.

    RETURNS:
    --------
    List[Dict]
        {id, rect, inner} per panel drawn - the view uses the rects for
        its maximize hit-testing and to draw the per-panel glyph; the
        exporter ignores them.
    """
    enabled = sanitize_panel_ids(enabled_ids)
    if maximized_id in enabled:
        enabled = [maximized_id]
    if not rows:
        # An empty plan gets a sentence rather than four empty charts;
        # see the old dashboard's _draw_empty and the test that pins it.
        pen.text(width / 2, height / 2,
                 "Nothing to summarise yet.\n"
                 "Add a task to the plan and it will appear here.",
                 fill=palette['tick'], size=13)
        return []
    panels = {pid: (title, draw)
              for pid, title, draw in DASHBOARD_PANELS}
    landed = []
    for (x, y, w, h), pid in zip(dashboard_layout(len(enabled),
                                                width, height),
                                 enabled):
        title, draw = panels[pid]
        draw(pen, rows, palette, x, y, w, h)
        pad = PANEL_PAD // 2
        landed.append({'id': pid,
                       'rect': (x + pad, y + pad,
                                x + w - pad, y + h - pad),
                       'title': title})
    return landed


# ---------------------------------------------------------------------------
# The timeline's rows and its time axis (issue #83)
# ---------------------------------------------------------------------------

def timeline_items(project: Optional[Project]) -> List[Dict[str, Any]]:
    """
    The rows the planner put on the timeline, in plan order.

    A task's Show in timeline flag decides (issue #83) - the checkbox
    finally means what it says. Each item carries its top-level
    ancestor's name and colour: the styles that group into lanes read
    them off the item rather than walking the plan again, and a row with
    no parent lanes under itself.
    """
    if project is None:
        return []

    def top_ancestor(task):
        seen = {task.id}
        top = task
        while top.parent_task_id and top.parent_task_id not in seen:
            parent = project.get_task_by_id(top.parent_task_id)
            if parent is None:
                break
            top = parent
            seen.add(top.id)
        return top

    items = []
    for task in project.display_order():
        if not getattr(task, 'show_in_timeline', False):
            continue
        if task.start_date is None:
            continue
        ancestor = top_ancestor(task)
        items.append({
            'task': task,
            'name': task.name,
            'start': task.start_date,
            'finish': task.end_date or task.start_date,
            'milestone': task.effective_milestone,
            'progress': task.progress or 0,
            'color': task.color or '#1f6aa5',
            'lane': ancestor.name if ancestor is not task else None,
            'lane_id': ancestor.id,
        })
    return items


def _item_lanes(items: List[Dict]) -> List[Tuple[str, str, List[Dict]]]:
    """
    The items grouped under their top-level row, in plan order.

    (lane_id, lane_label, items) - the label is the ancestor's name, or
    the project's own row when the flagged task sits at the top.
    """
    lanes: List[Tuple[str, str, List[Dict]]] = []
    for item in items:
        lane_id = item['lane_id']
        label = item['lane'] or item['name']
        lane = next((lane for lane in lanes if lane[0] == lane_id), None)
        if lane is None:
            lane = (lane_id, label, [])
            lanes.append(lane)
        lane[2].append(item)
    return lanes


def timeline_span(items) -> Tuple[datetime, datetime]:
    """The dates the axis covers, padded a touch at both ends."""
    first = min(item['start'] for item in items)
    last = max(item['finish'] for item in items)
    pad = max(1, (last - first).days // 40 + 1)
    return first - timedelta(days=pad), last + timedelta(days=pad)


def _add_months(d: datetime, months: int) -> datetime:
    """The first of the month, n months on."""
    m = d.month - 1 + months
    return d.replace(year=d.year + m // 12, month=m % 12 + 1, day=1)


def axis_columns(start: datetime, end: datetime,
                 width: float) -> Tuple[List[Dict], int]:
    """
    The columns a timeline's date band is drawn in.

    RETURNS:
    --------
    (columns, month_step)
        columns: {'x0', 'x1', 'label'} dicts covering the span; the step
        is months-per-column (1 month, 3 for quarters, 12 for years) so
        callers that want a finer row underneath can ask for one.

    DEVELOPMENT NOTES:
    ------------------
    The step is the largest that still leaves a column at least ~96
    pixels wide: a fortnight of columns labels months, a plan of years
    labels years. Columns land on calendar boundaries - a quarter starts
    January/April/July/October - rather than wherever the plan happens
    to begin.
    """
    days = max(1, (end - start).days or 1)
    for step in (1, 3, 12, 36):
        if width / (days / (step * 30.44)) >= 96:
            break
    else:
        step = 36

    # Align the first column to the step boundary the start sits in:
    # month 1 is quarters-aligned when step is 3, year-aligned at 12.
    if step == 1:
        boundary = start.replace(day=1)
    elif step == 3:
        month = ((start.month - 1) // 3) * 3 + 1
        boundary = start.replace(month=month, day=1)
    else:
        per_year = max(1, step // 12)
        year = (start.year // per_year) * per_year
        boundary = start.replace(year=year, month=1, day=1)
    if boundary > start:
        boundary = _add_months(boundary, -step)

    days_total = (end - start).days or 1

    def x_of(d):
        return (d - start).days / days_total * width

    columns = []
    cursor = boundary
    while cursor < end:
        nxt = _add_months(cursor, step)
        x0, x1 = x_of(cursor), x_of(nxt)
        if x1 <= 0:
            cursor = nxt
            continue
        if x0 >= width:
            break
        if step == 1:
            label = cursor.strftime('%b %Y')
        elif step == 3:
            label = f"Q{(cursor.month - 1) // 3 + 1} {cursor.year}"
        else:
            per_year = max(1, step // 12)
            if per_year == 1:
                label = str(cursor.year)
            else:
                label = f"{cursor.year}–{cursor.year + per_year - 1}"
        columns.append({'x0': x0, 'x1': x1, 'label': label})
        cursor = nxt
    return columns, step


def _month_columns(start, end, width) -> List[Dict]:
    """The finer month row under a quarter/year band (img4's look)."""
    columns, _step = axis_columns(start, end, width)
    # Recompute at month granularity regardless of the coarse step.
    days_total = (end - start).days or 1
    months = []
    cursor = start.replace(day=1)
    while cursor < end:
        nxt = _add_months(cursor, 1)
        x0 = (cursor - start).days / days_total * width
        x1 = (nxt - start).days / days_total * width
        if x1 > 0 and x0 < width:
            months.append({'x0': x0, 'x1': x1,
                           'label': cursor.strftime('%b')})
        cursor = nxt
    return months


def _draw_date_band(pen, palette, start, end, x0, x1, y0, height,
                    month_row=True):
    """
    The column header the swimlane styles share: labelled period cells
    over a lighter month row, both boxed and ruled.
    """
    width = x1 - x0
    columns, step = axis_columns(start, end, width)
    band_h = height * (0.55 if month_row else 1.0)

    pen.rect(x0, y0, x1, y0 + band_h, fill=palette['band_bg'])
    for col in columns:
        cx0, cx1 = x0 + col['x0'], x0 + col['x1']
        pen.line((cx0, y0, cx0, y0 + band_h), fill=palette['band_text'],
                 width=1)
        pen.text((cx0 + cx1) / 2, y0 + band_h / 2,
                 clip_to_width(pen, col['label'], 11, cx1 - cx0 - 8,
                               bold=True),
                 fill=palette['band_text'], size=11, bold=True)
    pen.line((x1, y0, x1, y0 + band_h), fill=palette['band_text'],
             width=1)

    if month_row:
        my0 = y0 + band_h
        pen.rect(x0, my0, x1, y0 + height, fill=palette['header_bg'])
        for col in _month_columns(start, end, width):
            cx0, cx1 = x0 + col['x0'], x0 + col['x1']
            pen.line((cx0, my0, cx0, y0 + height),
                     fill=palette['axis'], width=1)
            pen.text((cx0 + cx1) / 2, (my0 + y0 + height) / 2,
                     clip_to_width(pen, col['label'], 9, cx1 - cx0 - 4),
                     fill=palette['header_text'], size=9)
        pen.rect(x0, y0, x1, y0 + height, outline=palette['axis'],
                 width=1)


def _draw_today(pen, palette, start, end, x0, x1, y0, y1):
    """The status/today marker the lanes styles share."""
    days_total = (end - start).days or 1
    today = datetime.now()
    if not (start <= today <= end):
        return
    at = x0 + (today - start).days / days_total * (x1 - x0)
    pen.line((at, y0, at, y1), fill=palette['today'], width=2)


def _diamond(pen, x, y, radius, fill):
    """A milestone marker - a square turned onto its corner."""
    pen.polygon((x, y - radius, x + radius, y,
                 x, y + radius, x - radius, y), fill=fill)


def _item_bar(pen, item, bx0, bx1, y, height, palette, radius=None):
    """A task's span as a filled bar, progress as a darker lower band."""
    colour = item['color']
    if radius is None:
        pen.rect(bx0, y, bx1, y + height, fill=colour)
    else:
        pen.round_rect(bx0, y, bx1, y + height, radius=radius,
                       fill=colour)
    share = max(0.0, min(100.0, item['progress'])) / 100
    if share > 0 and bx1 > bx0:
        mark = bx0 + (bx1 - bx0) * share
        band_top = y + height - max(3, height * 0.3)
        if radius is None:
            pen.rect(bx0, band_top, mark, y + height,
                     fill=palette['progress_under'])
        else:
            pen.round_rect(bx0, band_top, mark, y + height,
                           radius=radius, fill=palette['progress_under'])


def _fmt_date(d: datetime) -> str:
    """2/5/2024 - the shape the example timelines write dates in."""
    return f"{d.month}/{d.day}/{d.year}"


def draw_timeline_lanes(pen, items, palette, rect):
    """
    The swimlane roadmap (the issue's third example): a lane per
    top-level row, its flagged children as segment bars that end in a
    ring, labels above them, milestones as diamonds, months over the top.
    """
    x0, y0, x1, y1 = rect
    start, end = timeline_span(items)
    lanes = _item_lanes(items)

    label_w = 120
    header_h = 46
    lane_h = max(52, min(90, (y1 - y0 - header_h) / max(1, len(lanes))))

    _draw_date_band(pen, palette, start, end, x0 + label_w, x1, y0,
                    header_h, month_row=True)

    days_total = (end - start).days or 1

    def x_at(d):
        return (x0 + label_w
                + (d - start).days / days_total * (x1 - x0 - label_w))

    # The month grid runs down through the lanes, faint.
    for col in _month_columns(start, end, x1 - x0 - label_w):
        pen.line((x0 + label_w + col['x0'], y0 + header_h,
                  x0 + label_w + col['x0'], y1),
                 fill=palette['grid'], width=1)

    row_y = y0 + header_h
    for lane_id, label, lane_items in lanes:
        cy = row_y + lane_h / 2
        pen.rect(x0, row_y, x0 + label_w, min(row_y + lane_h, y1),
                 fill=palette['lane_bg'], outline=palette['axis'],
                 width=1)
        pen.text(x0 + label_w / 2, cy,
                 clip_to_width(pen, label, 10, label_w - 12, bold=True),
                 fill=palette['lane_text'], size=10, bold=True)
        pen.line((x0, row_y, x1, row_y), fill=palette['axis'], width=1)

        # Sub-pack the lane's overlapping bars so two dated-together
        # rows do not sit on top of each other.
        ends: List[float] = []
        for item in sorted(lane_items, key=lambda it: it['start']):
            bx0, bx1 = x_at(item['start']), x_at(item['finish'])
            if item['milestone']:
                bx1 = bx0
            sub = 0
            while sub < len(ends) and ends[sub] > bx0:
                sub += 1
            sub = min(sub, 1)
            while len(ends) <= sub:
                ends.append(float('-inf'))

            band_top = row_y + 12
            sub_h = (lane_h - 20) / 2 if sub else lane_h - 20
            by = band_top + sub * ((lane_h - 20) / 2)
            if item['milestone']:
                _diamond(pen, bx0, by + sub_h / 2, 6, item['color'])
                pen.text(bx0, by - 6,
                         clip_to_width(pen, item['name'], 9, 140),
                         fill=palette['tick'], size=9)
            else:
                # The segment with the ring node at its end (img3).
                pen.line((bx0, by + sub_h / 2, bx1, by + sub_h / 2),
                         fill=item['color'], width=max(5, sub_h / 3))
                pen.oval(bx1 - 7, by + sub_h / 2 - 7, bx1 + 7,
                         by + sub_h / 2 + 7, fill=item['color'],
                         outline=palette['panel_bg'], width=2)
                pen.text(bx0, by - 2, anchor='sw',
                         content=clip_to_width(
                             pen, item['name'], 9,
                             max(40, bx1 - bx0)),
                         fill=palette['title'], size=9)
            ends[sub] = bx1
        row_y += lane_h
        if row_y > y1:
            break

    _draw_today(pen, palette, start, end, x0 + label_w, x1,
                y0 + header_h, y1)


def draw_timeline_roadmap(pen, items, palette, rect):
    """
    The grouped pill roadmap (the issue's sixth example): dark period
    header, a coloured pill of a lane label per top-level row, rounded
    bars with their names above, milestones as diamonds.
    """
    x0, y0, x1, y1 = rect
    start, end = timeline_span(items)
    lanes = _item_lanes(items)

    label_w = 130
    header_h = 34
    lane_h = max(46, min(84, (y1 - y0 - header_h) / max(1, len(lanes))))

    _draw_date_band(pen, palette, start, end, x0 + label_w, x1, y0,
                    header_h, month_row=False)

    days_total = (end - start).days or 1

    def x_at(d):
        return (x0 + label_w
                + (d - start).days / days_total * (x1 - x0 - label_w))

    series = palette['series']
    row_y = y0 + header_h
    for index, (lane_id, label, lane_items) in enumerate(lanes):
        pen.rect(x0, row_y, x1, row_y + lane_h,
                 fill=palette['panel_bg'] if index % 2
                 else palette['bg'])
        # The lane's label is a colour-blocked pill (img6's look).
        colour = series[index % len(series)]
        pen.round_rect(x0 + 6, row_y + lane_h / 2 - 12, x0 + label_w - 6,
                       row_y + lane_h / 2 + 12, radius=4, fill=colour)
        pen.text(x0 + label_w / 2, row_y + lane_h / 2,
                 clip_to_width(pen, label.upper(), 9, label_w - 18,
                               bold=True),
                 fill='#ffffff', size=9, bold=True)

        for item in sorted(lane_items, key=lambda it: it['start']):
            bx0, bx1 = x_at(item['start']), x_at(item['finish'])
            cy = row_y + lane_h / 2 + 4
            if item['milestone']:
                _diamond(pen, bx0, cy, 7, item['color'])
                pen.text(bx0, cy - 18,
                         clip_to_width(pen, item['name'], 9, 150),
                         fill=palette['tick'], size=9)
            else:
                _item_bar(pen, item, bx0, max(bx1, bx0 + 14),
                          cy - 7, 14, palette, radius=7)
                pen.text(bx0, cy - 12, anchor='sw',
                         content=clip_to_width(pen, item['name'], 9,
                                               max(50, bx1 - bx0)),
                         fill=palette['title'], size=9)
        row_y += lane_h
        if row_y > y1:
            break

    _draw_today(pen, palette, start, end, x0 + label_w, x1,
                y0 + header_h, y1)


def draw_timeline_callouts(pen, items, palette, rect):
    """
    The spine with alternating callouts (the issue's second example):
    a bold line across the middle, a period dot at each column, and each
    row hanging off a stem above or below it - title over the dates.
    """
    x0, y0, x1, y1 = rect
    start, end = timeline_span(items)
    spine_y = (y0 + y1) / 2

    # The spine and the period dots that walk it (img2's quarters).
    pen.line((x0 + 10, spine_y, x1 - 10, spine_y),
             fill=palette['spine'], width=6)
    columns, _step = axis_columns(start, end, x1 - x0)
    for col in columns:
        cx = x0 + (col['x0'] + col['x1']) / 2
        if x0 + 10 <= cx <= x1 - 10:
            pen.oval(cx - 9, spine_y - 9, cx + 9, spine_y + 9,
                     fill=palette['spine'],
                     outline=palette['bg'], width=2)
            pen.text(cx, spine_y, col['label'].split()[0],
                     fill='#ffffff', size=8, bold=True)
            pen.text(cx, spine_y + 22, col['label'],
                     fill=palette['tick'], size=9)

    days_total = (end - start).days or 1

    def x_at(d):
        return x0 + 24 + (d - start).days / days_total * (x1 - x0 - 48)

    # Alternating stems, spread to keep neighbouring callouts apart.
    top_used: List[float] = []
    bottom_used: List[float] = []
    ordered = sorted(items, key=lambda it: it['start'])
    for index, item in enumerate(ordered):
        cx = x_at(item['start'])
        above = index % 2 == 0
        used = top_used if above else bottom_used

        # Push overlapping callouts sideways, the way hand-drawn ones
        # are slid apart; the dot stays on the date.
        for other in used:
            if abs(cx - other) < 120:
                cx = other + 120
        used.append(cx)
        cx = min(cx, x1 - 110)

        stem_to = spine_y - 14 if above else spine_y + 14
        text_y = spine_y - 40 if above else spine_y + 40
        colour = item['color']

        pen.line((cx, spine_y, cx, stem_to), fill=colour, width=2)
        pen.oval(cx - 4, spine_y - 4, cx + 4, spine_y + 4, fill=colour,
                 outline=palette['bg'], width=1)
        anchor_y = text_y
        if item['milestone']:
            _diamond(pen, cx, stem_to, 5, colour)
        pen.text(cx, anchor_y, item['name'], fill=palette['title'],
                 size=11, bold=True, italic=True)
        when = _fmt_date(item['start'])
        if not item['milestone']:
            when = f"{when} – {_fmt_date(item['finish'])}"
        pen.text(cx, anchor_y + 16, when,
                 fill=palette['tick'], size=9)
        if item['progress']:
            pen.text(cx, anchor_y + 30,
                     f"{int(item['progress'])}% done",
                     fill=palette['tick'], size=9)


def _chevron(pen, x0, y0, x1, y1, tip, fill, outline=None):
    """An arrow-ended bar - the shape the chevron styles are built of."""
    x1 = max(x1, x0 + tip + 4)
    pen.polygon((x0, y0, x1 - tip, y0, x1, (y0 + y1) / 2,
                 x1 - tip, y1, x0, y1, x0 + tip, (y0 + y1) / 2),
                fill=fill, outline=outline)


def draw_timeline_chevrons(pen, items, palette, rect):
    """
    One staggered arrow bar per row (the issue's fifth example): a
    period band on top, then each flagged row as a chevron carrying its
    name, milestones as diamonds on their rows.
    """
    x0, y0, x1, y1 = rect
    start, end = timeline_span(items)
    header_h = 40
    row_h = max(34, min(56,
                        (y1 - y0 - header_h) / max(1, len(items))))

    _draw_date_band(pen, palette, start, end, x0, x1, y0, header_h,
                    month_row=False)

    days_total = (end - start).days or 1

    def x_at(d):
        return x0 + 16 + (d - start).days / days_total * (x1 - x0 - 32)

    row_y = y0 + header_h
    for index, item in enumerate(items):
        cy = row_y + row_h / 2
        pen.line((x0, row_y, x1, row_y), fill=palette['grid'], width=1,
                 dash=(2, 4))
        if item['milestone']:
            _diamond(pen, x_at(item['start']), cy, 7, item['color'])
            pen.text(x_at(item['start']) + 12, cy, anchor='w',
                     content=clip_to_width(pen, item['name'], 10, 220),
                     fill=palette['title'], size=10, bold=True)
        else:
            bx0 = x_at(item['start'])
            bx1 = x_at(item['finish'])
            if bx1 - bx0 < 90:
                # A chevron has a name inside; too narrow and it is a
                # sliver with text hanging off it - floor the length.
                spare = min(x1 - bx1 - 20, 90 - (bx1 - bx0))
                bx1 += max(0, spare)
            _chevron(pen, bx0, cy - 11, bx1, cy + 11, tip=14,
                     fill=item['color'])
            pen.text(bx0 + (bx1 - bx0) / 2, cy,
                     clip_to_width(pen, item['name'], 10,
                                   bx1 - bx0 - 30, bold=True),
                     fill='#ffffff', size=10, bold=True)
        row_y += row_h
        if row_y > y1:
            break

    _draw_today(pen, palette, start, end, x0, x1, y0 + header_h, y1)


def draw_timeline_phases(pen, items, palette, rect):
    """
    Phase banding over lane arrows (the issue's fourth example): the
    top-level rows' own spans head the chart as dark super-periods,
    months run underneath, and each lane's flagged rows are arrow bars
    with grey milestone dots between them.
    """
    x0, y0, x1, y1 = rect
    start, end = timeline_span(items)
    lanes = _item_lanes(items)

    label_w = 96
    header_h = 52
    lane_h = max(44, min(76,
                         (y1 - y0 - header_h) / max(1, len(lanes))))

    days_total = (end - start).days or 1

    def x_at(d):
        return (x0 + label_w
                + (d - start).days / days_total * (x1 - x0 - label_w))

    # The super-period band: one dark cell per lane (the phase), its
    # span and its name; months in the lighter row underneath.
    sup_h = header_h * 0.52
    pen.rect(x0 + label_w, y0, x1, y0 + sup_h, fill=palette['band_bg'])
    lane_first: Dict[str, datetime] = {}
    lane_last: Dict[str, datetime] = {}
    for item in items:
        lane_first[item['lane_id']] = min(
            lane_first.get(item['lane_id'], item['start']), item['start'])
        lane_last[item['lane_id']] = max(
            lane_last.get(item['lane_id'], item['finish']), item['finish'])
    for lane_id, label, _items in lanes:
        px0 = x_at(lane_first.get(lane_id, start))
        px1 = x_at(lane_last.get(lane_id, end))
        pen.line((px0, y0, px0, y0 + sup_h), fill=palette['band_text'],
                 width=1)
        pen.text((px0 + px1) / 2, y0 + sup_h / 2,
                 clip_to_width(pen, label, 11,
                               max(30, px1 - px0 - 8), bold=True),
                 fill=palette['band_text'], size=11, bold=True)

    my0 = y0 + sup_h
    pen.rect(x0 + label_w, my0, x1, y0 + header_h,
             fill=palette['header_bg'])
    for col in _month_columns(start, end, x1 - x0 - label_w):
        cx0, cx1 = x0 + label_w + col['x0'], x0 + label_w + col['x1']
        pen.line((cx0, my0, cx0, y0 + header_h),
                 fill=palette['axis'], width=1)
        pen.text((cx0 + cx1) / 2, (my0 + y0 + header_h) / 2,
                 clip_to_width(pen, col['label'], 9, cx1 - cx0 - 4),
                 fill=palette['header_text'], size=9)

    row_y = y0 + header_h
    for index, (lane_id, label, lane_items) in enumerate(lanes):
        pen.rect(x0, row_y, x0 + label_w, row_y + lane_h,
                 fill=palette['band_bg'])
        pen.text(x0 + label_w / 2, row_y + lane_h / 2,
                 clip_to_width(pen, label, 9, label_w - 10, bold=True),
                 fill=palette['band_text'], size=9, bold=True)
        pen.line((x0, row_y, x1, row_y), fill=palette['axis'], width=1)

        for item in sorted(lane_items, key=lambda it: it['start']):
            cy = row_y + lane_h / 2
            bx0 = x_at(item['start'])
            if item['milestone']:
                # The grey dot between a lane's arrows.
                pen.oval(bx0 - 6, cy - 6, bx0 + 6, cy + 6,
                         fill=palette['tick'],
                         outline=palette['panel_bg'], width=1)
                pen.text(bx0, cy - 16,
                         clip_to_width(pen, item['name'], 8, 120),
                         fill=palette['tick'], size=8)
            else:
                bx1 = x_at(item['finish'])
                if bx1 - bx0 < 70:
                    bx1 = bx0 + 70
                _chevron(pen, bx0, cy - 9, bx1, cy + 9, tip=12,
                         fill=item['color'])
                pen.text(bx0 + (bx1 - bx0) / 2, cy,
                         clip_to_width(pen, item['name'], 9,
                                       bx1 - bx0 - 24, bold=True),
                         fill='#ffffff', size=9, bold=True)
        row_y += lane_h
        if row_y > y1:
            break

    _draw_today(pen, palette, start, end, x0 + label_w, x1,
                y0 + header_h, y1)


#: The styles the timeline can draw, in the order its style picker lists
#: them. Each is (id, label, draw): the id is what settings.json keeps,
#: and draw paints the flagged rows inside the pen rect it is given.
#: Every one is a layout from the issue's examples - the MS Project look
#: it called useless is deliberately not among them.
TIMELINE_STYLES: List[Tuple[str, str, Callable]] = [
    ('lanes', 'Lanes', draw_timeline_lanes),
    ('roadmap', 'Roadmap', draw_timeline_roadmap),
    ('callouts', 'Callouts', draw_timeline_callouts),
    ('chevrons', 'Chevrons', draw_timeline_chevrons),
    ('phases', 'Phases', draw_timeline_phases),
]

#: The style a first run shows - the grouped lanes are the most literal
#: of the examples.
DEFAULT_TIMELINE_STYLE = 'lanes'


def timeline_style_ids() -> List[str]:
    """Every style the timeline knows, in picker order."""
    return [style_id for style_id, _l, _d in TIMELINE_STYLES]


def render_timeline(pen, project, style_id: str, palette,
                    width: float, height: float) -> None:
    """Draw the flagged rows in the picked style, or the empty hint."""
    items = timeline_items(project)
    pen.rect(0, 0, width, height, fill=palette['bg'])
    if not items:
        pen.text(width / 2, height / 2,
                 "Nothing on the timeline yet.\n"
                 "Tick \"Show in timeline\" on a row's Display section "
                 "and it will appear here.",
                 fill=palette['tick'], size=12)
        return
    style = next((draw for sid, _l, draw in TIMELINE_STYLES
                  if sid == style_id), None)
    if style is None:
        logger.warning("Unknown timeline style %r; drawing the lanes "
                       "style instead", style_id)
        style = draw_timeline_lanes
    pad = 14
    style(pen, items, palette, (pad, pad, width - pad, height - pad))
