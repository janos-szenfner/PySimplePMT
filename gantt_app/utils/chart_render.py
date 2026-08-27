"""
Browser-free static rendering of the Gantt chart.

WHY THIS MODULE EXISTS:
======================
Plotly draws the interactive chart in the window, but turning a Plotly figure
into a PNG or PDF means Kaleido, and Kaleido works by driving a real Chrome or
Chromium over the DevTools protocol. When no browser is installed it downloads
one - a few hundred megabytes, at runtime, over the network.

That is unacceptable for an application that must work entirely from what it
ships with, so static export is drawn here instead. Nothing is downloaded and
no browser, no system library and no font file is required.

DEVELOPMENT NOTES:
------------------
Layout is computed once into a list of primitives, then handed to one of two
emitters:

  * render_svg   - plain text, true vector, zero dependencies
  * render_image - a PIL image, used for PNG and PDF

Splitting it this way keeps a single source of truth for the geometry. The
alternative, drawing the chart twice, is exactly how the view and the two old
exporters drifted apart.

Pillow is the only dependency and it is already required by customtkinter.
Text uses ImageFont.load_default(size=...), which returns a scalable font
built into Pillow, so no font file has to be found or shipped.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont

from gantt_app.models import Project, Task
from gantt_app.utils.chart_figure import _merged_settings, calculate_date_range
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


#: Layout metrics, in pixels.
ROW_HEIGHT = 34
MIN_ROW_HEIGHT = 8
BAR_HEIGHT = 20
MARGIN_LEFT = 220
MARGIN_RIGHT = 60
#: Room above the first row, for the title and the calendar strip.
#:
#: The strip is two tiers - a month band and a row of day cells - and it
#: sits at the top now rather than under the chart, where a reader had to
#: look away from the bars to read a date. gantt_chart floors its
#: row alignment at this, so the panes go slightly out of line rather than
#: drawing bars over the dates; see GanttChart._first_row_offset.
MARGIN_TOP = 70

#: Room below the last row. Small now: the dates used to live down here.
MARGIN_BOTTOM = 30

#: Where the chart's title sits, as the centre of its line. Above the
#: calendar strip and clear of it; see HEADER_MONTH_HEIGHT for the budget.
TITLE_BASELINE = 16

#: The two tiers of the strip, in pixels, measured up from the plot top.
#:
#: Sized so the title and both tiers fit inside MARGIN_TOP, which is what
#: keeps the chart's rows level with the task list's. The list reserves
#: about 70px above its first row - a heading label and the column titles -
#: and the chart floors its row alignment at MARGIN_TOP, so a strip needing
#: more than that does not make the chart taller: it pushes every bar down
#: and out of line with the list beside it, which is what a first attempt
#: at 24 and 28 did.
HEADER_MONTH_HEIGHT = 18
HEADER_CELL_HEIGHT = 22
MIN_WIDTH = 900
MILESTONE_RADIUS = 9

#: How far the tapered ends of a summary bracket reach back along the span.
SUMMARY_FOOT = 7

#: How far back along the span a Phase's arrow head reaches, as a fraction of
#: the bar's height. A head about three quarters as long as the bar is tall
#: reads as a point rather than as a bar somebody has nicked the corner off.
PHASE_HEAD_RATIO = 0.75

LABEL_CHARS = 28

#: Outline shapes a summary row can be drawn in; see _summary_outline.
SHAPE_BRACKET = 'bracket'
SHAPE_PHASE = 'phase'


@dataclass
class RowPlan:
    """
    The rows to draw, and the geometry that lines them up with a task list.

    WHY THIS EXISTS:
    ================
    On its own the chart chooses its own rows, in its own order, at its own
    height, and prints the task's name down the left of it. Beside the task
    list that is three ways of disagreeing with the grid the reader is
    looking at: a row folded away in the list still had a bar, a row height
    of 34 against the list's 26 drifted a whole row out of step every four
    tasks, and the names appeared twice.

    Handed one of these, the chart draws exactly the rows it is given, in the
    order given, at the height given - so a bar sits on the same line as the
    task it belongs to, which is how a plan is read.

    ATTRIBUTES:
    -----------
    tasks : List[Task]
        The rows, top to bottom. Whatever the list is showing.
    row_height : int
        Pixels per row, matching the grid's.
    top_margin : int
        Pixels above the first row, so row one starts level with the grid's.
    label_width : int
        Room down the left for the chart's own task names. Zero beside a
        task list, which is already showing them.
    """

    tasks: List[Task]
    row_height: int
    top_margin: int = MARGIN_TOP
    label_width: int = 0


@dataclass
class ChartLayout:
    """Geometry for one rendered chart, in pixels."""

    width: int
    height: int
    settings: Dict[str, Any]
    bars: List[Dict[str, Any]] = field(default_factory=list)
    #: Tasks that have sub-tasks, drawn as a spanning bracket
    summaries: List[Dict[str, Any]] = field(default_factory=list)
    milestones: List[Dict[str, Any]] = field(default_factory=list)
    dependencies: List[Tuple[float, float, float, float]] = field(default_factory=list)
    row_labels: List[Tuple[float, str]] = field(default_factory=list)
    date_ticks: List[Tuple[float, str]] = field(default_factory=list)
    #: The month band across the top: (x0, x1, "DECEMBER 2020").
    month_bands: List[Tuple[float, float, str]] = field(default_factory=list)
    #: The cells under it: (x0, x1, label, is_today, is_working, starts_week).
    #:
    #: One per day where the days are wide enough to label, one per week
    #: below that, and none at all when even a week is too narrow - see
    #: _header_mode. The label is the day of the month; the month and the
    #: year are in the band above, which is what lets a cell be 22px wide
    #: rather than the 82px a full date needed.
    day_cells: List[Tuple[float, float, str, bool, bool, bool]] = field(
        default_factory=list)
    #: Which of the three the header is in: 'day', 'week' or 'month'.
    header_mode: str = 'month'
    #: The left and right edges of the plotting area, which the header's
    #: closing rules run between.
    plot_left: float = 0.0
    plot_right: float = 0.0
    title: str = ""
    empty_message: Optional[str] = None


def _shorten(text: str, limit: int = LABEL_CHARS) -> str:
    """Trim a label to fit the left margin."""
    return text if len(text) <= limit else text[:limit - 1] + '...'


def _get_visible_tasks(project: Project) -> List[Task]:
    """
    Get tasks that should be visible in the Gantt chart.
    
    Only returns tasks where show_in_timeline is True (default).
    
    PARAMETERS:
    -----------
    project : Project
        The project containing tasks.
        
    RETURNS:
    --------
    List[Task]
        List of tasks with show_in_timeline set to True.
    """
    return [task for task in project.tasks if task.show_in_timeline]


def _summary_outline(summary: Dict[str, Any]) -> List[Tuple[float, float]]:
    """
    Corner points of the shape drawn for a task that has sub-tasks.

    PARAMETERS:
    -----------
    summary : Dict[str, Any]
        A `ChartLayout.summaries` entry. Its 'shape' decides which outline is
        returned; anything without one gets the bracket.

    RETURNS:
    --------
    List[Tuple[float, float]]
        A closed polygon. For a Phase, a full-height bar drawn to a point at
        its right-hand end. For anything else, a thin spine across the span
        with a tapered foot dropping below each end.

    DEVELOPMENT NOTES:
    ------------------
    Two shapes, because a plan has two kinds of parent and they are read
    differently. A Phase is the top of the plan - the reader wants to see
    where it runs to, so it is drawn as a solid bar ending in an arrow head
    pointing at its finish. A Phase, or a plain Task that happens to
    have sub-tasks, brackets the work beneath it, which is the thin spine with
    feet that every Gantt tool uses.

    Both emitters share this so the on-screen chart and the exports cannot
    drift apart.

    Each is clamped for a short span: a bracket spanning a day or two collapses
    to a wedge, and a phase to a plain triangle, rather than folding through
    itself.
    """
    x0, x1 = summary['x0'], summary['x1']
    y0, y1 = summary['y0'], summary['y1']
    height = y1 - y0

    if summary.get('shape') == SHAPE_PHASE:
        head = min(height * PHASE_HEAD_RATIO, max(x1 - x0, 1))
        return [
            (x0, y0),
            (x1 - head, y0),
            (x1, y0 + height / 2),
            (x1 - head, y1),
            (x0, y1),
        ]

    spine = y0 + height * 0.45          # the bar itself stays thin
    foot = min(SUMMARY_FOOT, max((x1 - x0) / 2, 1))

    return [
        (x0, y0),
        (x1, y0),
        (x1, y1),
        (x1 - foot, spine),
        (x0 + foot, spine),
        (x0, y1),
    ]


#: Clear space to leave between two date labels, in pixels.
#:
#: The labels themselves are measured - see _tick_label_px - so this is only
#: the gap, and it is what stops "2026-08-17" and "2026-08-19" reading as one
#: long number.
TICK_LABEL_GAP_PX = 28


#: What one day cell needs, in pixels: the widest day number plus padding.
#:
#: A cell is delimited by rules on either side, so it needs padding rather
#: than the wide gap free-floating text needs to read as separate. That is
#: why a day cell fits in about 22px where "2026-08-17" needed 82 - the
#: month and the year moved up into the band.
HEADER_CELL_PAD_PX = 10

#: Below this, a week cell is not worth labelling either and the strip drops
#: to the month band alone.
MIN_WEEK_CELL_PX = 26


def _day_cell_px(font_size: int) -> float:
    """How much room one day cell needs, at a given font size."""
    font = _font(max(6, int(font_size) - 2))
    try:
        width = font.getbbox('22')[2]
    except AttributeError:                  # very old Pillow
        width = font.getsize('22')[0]
    return width + HEADER_CELL_PAD_PX


def _header_mode(days: int, plot_span: float, font_size: int) -> str:
    """
    Which of the three headers the available room allows.

    RETURNS:
    --------
    str
        'day' when every day can carry its own number, 'week' when only a
        week can, and 'month' when neither will fit and the band is left to
        say where in the calendar the chart is.
    """
    if days <= 0 or plot_span <= 0:
        return 'month'

    per_day = plot_span / days
    if per_day >= _day_cell_px(font_size):
        return 'day'
    if per_day * 7 >= MIN_WEEK_CELL_PX:
        return 'week'
    return 'month'


def _tick_label_px(font_size: int) -> float:
    """
    How much room one date label needs, at a given font size.

    Measured from the font rather than assumed, because the tick size
    follows the chart's font_size setting - which the user can raise in
    View > Settings. A fixed number was safe at the default and overlapped
    the moment anybody made the type bigger.
    """
    font = _font(max(6, int(font_size) - 2))
    sample = '2026-08-17'
    try:
        width = font.getbbox(sample)[2]
    except AttributeError:                  # very old Pillow
        width = font.getsize(sample)[0]
    return width + TICK_LABEL_GAP_PX

#: The gaps a date axis is allowed to step by, in days.
#:
#: Three, four and five are in here for the middle sizes. Without them the
#: list jumped straight from 2 to 7, so a month-long plan on a wide window
#: was labelled once a week however much room there was - which is what a
#: chart showing four dates across its whole width was.
TICK_STEPS = (1, 2, 3, 4, 5, 7, 10, 14, 21, 30, 60, 90, 180, 365)


def _tick_step(days: int, plot_span: float = 0, font_size: int = 12) -> int:
    """
    Choose the gap between date labels.

    PARAMETERS:
    -----------
    days : int
        How many days the axis covers.
    plot_span : float
        How many pixels it covers. Zero falls back to a fixed dozen labels,
        for a caller that has no width to offer.
    font_size : int
        The chart's font size, which the tick labels are sized from.

    RETURNS:
    --------
    int
        Days between labels: the smallest step in TICK_STEPS whose labels
        still fit.

    DEVELOPMENT NOTES:
    ------------------
    Worked out from the room available rather than from a fixed count. A
    dozen labels is right for a narrow window and wrong for a wide one, and
    it was the same dozen either way - so widening the window, or zooming
    in, added blank space between the same four dates rather than
    more dates.

    The pixel budget is what decides it now, so a wider chart or a deeper
    zoom shows more of the calendar, and a narrow one thins the labels out
    rather than overlapping them.
    """
    if plot_span > 0:
        fits = max(2, int(plot_span // _tick_label_px(font_size)))
    else:
        fits = 12

    for step in TICK_STEPS:
        if days / step <= fits:
            return step
    return max(1, int(days // fits))


#: Horizontal space each day should get before the chart starts scrolling.
MIN_PIXELS_PER_DAY = 6

#: Upper bound on the rendered width, so a multi-year plan cannot produce an
#: image large enough to exhaust memory.
MAX_WIDTH = 6000

#: Upper bound on the total pixels in a rendered chart. Width alone is not
#: enough of a guard: a long plan with hundreds of tasks is tall as well as
#: wide, and the product is what decides how much memory the image and the
#: Tk copy of it take. Repeated redraws of an unbounded image while dragging
#: the pane divider were enough to lock a machine up.
MAX_PIXELS = 24_000_000


def preferred_width(project: Project, available: int = 0) -> int:
    """
    Choose how wide to draw the chart.

    PARAMETERS:
    -----------
    project : Project
        The project being drawn.
    available : int
        Width of the space the chart is displayed in, in pixels.

    RETURNS:
    --------
    int
        The width to render at: at least the available space, and enough for
        every day to get a few pixels so a long plan stays readable.

    DEVELOPMENT NOTES:
    ------------------
    Fitting a multi-month plan into a narrow pane squeezed the bars down to
    slivers. Rendering wider than the viewport and letting the canvas scroll
    keeps the bars legible, which is the point of scrolling sideways at all.
    """
    width = max(int(available), MIN_WIDTH)

    visible_tasks = _get_visible_tasks(project)
    if visible_tasks:
        low, high = calculate_date_range(
            sorted(visible_tasks, key=lambda t: t.start_date)
        )
        days = max((high - low).days, 1)
        needed = MARGIN_LEFT + MARGIN_RIGHT + days * MIN_PIXELS_PER_DAY
        width = max(width, needed)

    return min(width, MAX_WIDTH)


def layout_chart(project: Project, settings: Optional[Dict[str, Any]] = None,
                 width: int = 1400,
                 min_width: int = MIN_WIDTH,
                 rows: Optional['RowPlan'] = None) -> ChartLayout:
    """
    Compute the geometry of the chart.

    PARAMETERS:
    -----------
    project : Project
        The project to lay out.
    settings : Optional[Dict[str, Any]]
        Appearance overrides, matching chart_figure.DEFAULT_SETTINGS.
    width : int
        Target image width in pixels.
    min_width : int
        Floor for that width. The default keeps a chart readable; the
        on-screen view lowers it when the user has deliberately zoomed out,
        which would otherwise stop having any effect at the default floor.
    rows : Optional[RowPlan]
        The rows to draw and how tall to draw them, when the chart is being
        lined up with a task list beside it. Left out - as the PNG, PDF and
        SVG exports leave it out - the chart chooses its own rows and prints
        its own labels, having no grid beside it to borrow either from.

    RETURNS:
    --------
    ChartLayout
        Positions for every bar, milestone, dependency line and label.
    """
    resolved = _merged_settings(settings)
    width = max(int(width), int(min_width))

    # Rows follow the task list rather than the dates. Sorting here meant a
    # row moved by hand in the list did not move in the chart, so the two
    # panes disagreed and a reorder looked like it had done nothing. The task
    # list is already in hierarchy order, which keeps a parent beside its
    # sub-tasks here too.
    # Only include tasks that should be visible in the timeline
    tasks = rows.tasks if rows is not None else _get_visible_tasks(project)
    top_margin = rows.top_margin if rows is not None else MARGIN_TOP
    label_width = rows.label_width if rows is not None else MARGIN_LEFT
    title = f"Gantt Chart: {project.name or 'New Project'}"

    if not tasks:
        return ChartLayout(width=width, height=320, settings=resolved,
                           title=title,
                           empty_message="Add tasks to see the Gantt chart")

    # Keep the whole chart within a bounded number of pixels. Rows are
    # squeezed before anything is dropped, so every task stays visible: a
    # plan with hundreds of tasks would otherwise be tens of thousands of
    # pixels tall, and rendering that repeatedly while dragging the pane
    # divider was enough to exhaust memory.
    row_height = rows.row_height if rows is not None else ROW_HEIGHT
    height = top_margin + len(tasks) * row_height + MARGIN_BOTTOM
    if width * height > MAX_PIXELS and rows is None:
        # Rows are squeezed only when the chart is free to choose them. Given
        # a row height by the list beside it, changing it is what puts the
        # two out of step, so the width gives way instead.
        budget = max(MAX_PIXELS // max(width, 1) - top_margin - MARGIN_BOTTOM,
                     len(tasks) * MIN_ROW_HEIGHT)
        row_height = max(MIN_ROW_HEIGHT, budget // max(len(tasks), 1))
        height = top_margin + len(tasks) * row_height + MARGIN_BOTTOM

        # Rows have a floor, so a very long task list stays tall no matter
        # what. Give back the remaining pixels by narrowing the chart, which
        # the horizontal scrollbar already copes with.
        if width * height > MAX_PIXELS:
            width = max(int(min_width), MAX_PIXELS // max(height, 1))

        logger.info("Compressed chart to %dx%d (rows %dpx) for %d tasks to "
                    "stay within the pixel budget",
                    width, height, row_height, len(tasks))

    if width * height > MAX_PIXELS:
        width = max(int(min_width), MAX_PIXELS // max(height, 1))

    bar_height = max(6, int(row_height * BAR_HEIGHT / ROW_HEIGHT))
    plot_left = label_width or MARGIN_RIGHT
    plot_right = width - MARGIN_RIGHT
    plot_span = max(plot_right - plot_left, 1)

    min_date, max_date = calculate_date_range(tasks)
    total_days = max((max_date - min_date).days, 1)

    def x_for(moment: datetime) -> float:
        """Map a date onto the horizontal axis."""
        offset = (moment - min_date).days + (moment - min_date).seconds / 86400
        return plot_left + (offset / total_days) * plot_span

    def y_for(index: int) -> float:
        """Centre of the row at the given index."""
        return top_margin + index * row_height + row_height / 2

    layout = ChartLayout(width=width, height=height, settings=resolved,
                         title=title)

    positions = {task.id: index for index, task in enumerate(tasks)}
    critical = {t.id for t in project.get_critical_path()}
    # A task with sub-tasks spans the work beneath it rather than being work
    # of its own, so it is drawn as a bracket instead of a solid bar
    summary_ids = project.get_summary_task_ids()

    for index, task in enumerate(tasks):
        centre = y_for(index)
        if label_width:
            layout.row_labels.append((centre, _shorten(task.name)))

        if task.is_milestone:
            layout.milestones.append({
                'x': x_for(task.start_date),
                'y': centre,
                'color': (resolved['critical_path_color'] if task.id in critical
                          else task.color),
                'label': _shorten(task.name, 24),
            })
            continue

        end = task.end_date or task.start_date
        start_x = x_for(task.start_date)
        # A task is inclusive of its end date, so the bar covers that whole day
        end_x = max(x_for(end + timedelta(days=1)), start_x + 2)
        colour = (resolved['critical_path_color'] if task.id in critical
                  else task.color)

        # A Phase is drawn to a point whether or not anything hangs off it
        # yet. It is the top of the plan either way, and one that changed
        # shape the moment its first task was added looked like two
        # different kinds of row.
        is_phase = task.task_type == 'Phase'
        if is_phase or task.id in summary_ids:
            layout.summaries.append({
                'x0': start_x,
                'x1': end_x,
                'y0': centre - bar_height / 2,
                'y1': centre + bar_height / 2,
                'color': colour,
                'label': task.name,
                'shape': SHAPE_PHASE if is_phase else SHAPE_BRACKET,
            })
            continue

        layout.bars.append({
            'x0': start_x,
            'x1': end_x,
            'y0': centre - bar_height / 2,
            'y1': centre + bar_height / 2,
            'color': colour,
            'progress': max(0, min(100, task.progress)),
            'label': task.name,
        })

    for task in tasks:
        for dep_id in task.dependency_ids:
            dep = project.get_task_by_id(dep_id)
            if dep is None or dep.id not in positions:
                continue
            dep_end = dep.start_date if dep.is_milestone else \
                (dep.end_date or dep.start_date) + timedelta(days=1)
            layout.dependencies.append((
                x_for(dep_end), y_for(positions[dep.id]),
                x_for(task.start_date), y_for(positions[task.id])
            ))

    layout.plot_left = plot_left
    layout.plot_right = plot_right
    _build_date_header(layout, project, min_date, max_date, x_for,
                       total_days, plot_span)

    return layout


def _build_date_header(layout: 'ChartLayout', project: Project,
                       min_date: datetime, max_date: datetime,
                       x_for, total_days: int, plot_span: float) -> None:
    """
    Build the calendar strip across the top: a month band and day cells.

    PARAMETERS:
    -----------
    x_for : callable
        Maps a date to its x position, from layout_chart.

    DEVELOPMENT NOTES:
    ------------------
    The axis stays linear in calendar days - every day gets the same width,
    worked or not. Dropping the non-working columns would be denser and is
    what most calendar strips do, but it cannot be done here: a task may
    follow a calendar of its own, so a 24/7 task genuinely works Saturdays
    and would have nowhere to be drawn, and the whole point of a manual
    override is to make one particular Saturday a working day. Non-working
    days are shaded instead, which says the same thing and costs a fill
    rather than a semantic argument.

    Which days are shaded comes from the *project's* calendar, for the same
    reason the float axis does: it is the one frame every task is drawn
    against, and a strip that tried to honour several would have to shade a
    column two ways at once.
    """
    font_size = layout.settings.get('font_size', 12)
    layout.header_mode = _header_mode(total_days, plot_span, font_size)

    calendar = project.calendar
    today = datetime.now().date()
    day = datetime(min_date.year, min_date.month, min_date.day)
    last = max_date

    # ---- the month band -------------------------------------------------
    band_start, band_key = day, (day.year, day.month)
    walk = day
    while walk <= last:
        key = (walk.year, walk.month)
        if key != band_key:
            layout.month_bands.append(
                (x_for(band_start), x_for(walk),
                 band_start.strftime('%B %Y').upper()))
            band_start, band_key = walk, key
        walk += timedelta(days=1)
    layout.month_bands.append(
        (x_for(band_start), x_for(walk), band_start.strftime('%B %Y').upper()))

    # ---- the cells under it ---------------------------------------------
    if layout.header_mode == 'month':
        # Nothing fits; the band alone says where in the calendar this is,
        # and the gridlines fall back to the stepped dates.
        step = _tick_step(total_days, plot_span, font_size)
        tick = min_date
        while tick <= max_date:
            layout.date_ticks.append((x_for(tick), tick.strftime('%Y-%m-%d')))
            tick += timedelta(days=step)
        return

    span = 1 if layout.header_mode == 'day' else 7
    walk = day
    if span == 7:
        # Weeks are read from Monday, so the first cell starts on one
        walk -= timedelta(days=walk.weekday())

    while walk <= last:
        finish = walk + timedelta(days=span)
        starts_week = walk.weekday() == 0
        layout.day_cells.append((
            x_for(walk), x_for(finish), str(walk.day),
            walk.date() == today,
            calendar.is_working_day(walk),
            starts_week,
        ))
        # A rule down the chart at the start of each week, which is what
        # gives the strip its rhythm now that the weekday letters are gone
        if starts_week:
            layout.date_ticks.append((x_for(walk), walk.strftime('%Y-%m-%d')))
        walk = finish


# ---------------------------------------------------------------------------
# SVG emitter
# ---------------------------------------------------------------------------

def _svg_date_header(layout: 'ChartLayout', s: Dict[str, Any],
                     font_size: int) -> List[str]:
    """
    The calendar strip and its day shading, as SVG elements.

    The same drawing as _draw_date_header does with Pillow. Two emitters
    rather than one because the two output formats share the *layout* - the
    bands and cells worked out in _build_date_header - and nothing else;
    that is the same split every other part of this chart already uses.
    """
    plot_top = MARGIN_TOP - HEADER_MONTH_HEIGHT - HEADER_CELL_HEIGHT
    band_bottom = plot_top + HEADER_MONTH_HEIGHT
    cell_bottom = band_bottom + HEADER_CELL_HEIGHT
    chart_bottom = layout.height - MARGIN_BOTTOM
    parts: List[str] = []

    for x0, x1, _label, is_today, is_working, _week in layout.day_cells:
        if is_today:
            colour = s['header_today_bg']
        elif not is_working:
            colour = s['header_non_working']
        else:
            continue
        parts.append(
            f'<rect x="{x0:.1f}" y="{cell_bottom}" width="{x1 - x0:.1f}" '
            f'height="{chart_bottom - cell_bottom}" fill="{colour}"/>')

    for x, _label in layout.date_ticks:
        parts.append(
            f'<line x1="{x:.1f}" y1="{cell_bottom}" x2="{x:.1f}" '
            f'y2="{chart_bottom}" stroke="{s["grid_color"]}" '
            f'stroke-width="1"/>')

    for x0, x1, label in layout.month_bands:
        parts.append(
            f'<rect x="{x0:.1f}" y="{plot_top}" width="{x1 - x0:.1f}" '
            f'height="{HEADER_MONTH_HEIGHT}" fill="{s["header_month_bg"]}"/>')
        parts.append(
            f'<line x1="{x0:.1f}" y1="{plot_top}" x2="{x0:.1f}" '
            f'y2="{band_bottom}" stroke="{s["header_week_rule"]}" '
            f'stroke-width="1"/>')
        parts.append(
            f'<text x="{(x0 + x1) / 2:.1f}" '
            f'y="{(plot_top + band_bottom) / 2:.1f}" text-anchor="middle" '
            f'dominant-baseline="central" font-family="sans-serif" '
            f'font-size="{font_size - 2}" fill="{s["header_month_text"]}"'
            f'>{escape(label)}</text>')

    for x0, x1, label, is_today, is_working, starts_week in layout.day_cells:
        if is_today:
            fill, ink = s['header_today_bg'], s['header_today_text']
        elif not is_working:
            fill, ink = s['header_non_working'], s['header_day_text']
        else:
            fill, ink = s['header_cell_bg'], s['header_day_text']
        parts.append(
            f'<rect x="{x0:.1f}" y="{band_bottom}" width="{x1 - x0:.1f}" '
            f'height="{HEADER_CELL_HEIGHT}" fill="{fill}"/>')
        parts.append(
            f'<line x1="{x0:.1f}" y1="{band_bottom}" x2="{x0:.1f}" '
            f'y2="{cell_bottom}" '
            f'stroke="{s["header_week_rule"] if starts_week else s["header_rule"]}" '
            f'stroke-width="1"/>')
        parts.append(
            f'<text x="{(x0 + x1) / 2:.1f}" '
            f'y="{(band_bottom + cell_bottom) / 2:.1f}" text-anchor="middle" '
            f'dominant-baseline="central" font-family="sans-serif" '
            f'font-size="{font_size - 2}" fill="{ink}">{escape(label)}</text>')

    if layout.day_cells:
        parts.append(
            f'<line x1="{layout.plot_right:.1f}" y1="{plot_top}" '
            f'x2="{layout.plot_right:.1f}" y2="{cell_bottom}" '
            f'stroke="{s["header_week_rule"]}" stroke-width="1"/>')

    for y in (plot_top, band_bottom, cell_bottom):
        parts.append(
            f'<line x1="{layout.plot_left:.1f}" y1="{y}" '
            f'x2="{layout.plot_right:.1f}" y2="{y}" '
            f'stroke="{s["header_week_rule"]}" stroke-width="1"/>')

    return parts


def render_svg(project: Project, settings: Optional[Dict[str, Any]] = None,
               width: int = 1400) -> str:
    """
    Render the chart as an SVG document.

    RETURNS:
    --------
    str
        A complete standalone SVG. True vector output, produced with no
        dependency beyond the standard library.
    """
    layout = layout_chart(project, settings, width)
    s = layout.settings
    font_size = s['font_size']

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{layout.width}" '
        f'height="{layout.height}" viewBox="0 0 {layout.width} {layout.height}">',
        f'<rect width="100%" height="100%" fill="{s["bg_color"]}"/>',
        f'<text x="{layout.width / 2}" y="{TITLE_BASELINE + 6}" '
        f'text-anchor="middle" '
        f'font-family="sans-serif" font-size="18" font-weight="bold" '
        f'fill="{s["text_color"]}">{escape(layout.title)}</text>',
    ]

    if layout.empty_message:
        parts.append(
            f'<text x="{layout.width / 2}" y="{layout.height / 2}" '
            f'text-anchor="middle" font-family="sans-serif" font-size="16" '
            f'fill="#7f8c8d">{escape(layout.empty_message)}</text></svg>'
        )
        return '\n'.join(parts)

    parts.extend(_svg_date_header(layout, s, font_size))

    for y, label in layout.row_labels:
        parts.append(
            f'<text x="{MARGIN_LEFT - 12}" y="{y + font_size / 3:.1f}" '
            f'text-anchor="end" font-family="sans-serif" font-size="{font_size}" '
            f'fill="{s["text_color"]}">{escape(label)}</text>'
        )

    for x0, y0, x1, y1 in layout.dependencies:
        parts.append(
            f'<path d="M {x0:.1f} {y0:.1f} L {x1:.1f} {y1:.1f}" fill="none" '
            f'stroke="{s["dependency_color"]}" stroke-width="1.5" '
            f'stroke-dasharray="4,3" opacity="0.75"/>'
        )

    for bar in layout.bars:
        w = bar['x1'] - bar['x0']
        h = bar['y1'] - bar['y0']
        parts.append(
            f'<rect x="{bar["x0"]:.1f}" y="{bar["y0"]:.1f}" width="{w:.1f}" '
            f'height="{h:.1f}" fill="{bar["color"]}" stroke="#000000" '
            f'stroke-width="1" rx="2"/>'
        )
        if bar['progress']:
            parts.append(
                f'<rect x="{bar["x0"]:.1f}" y="{bar["y0"]:.1f}" '
                f'width="{w * bar["progress"] / 100:.1f}" height="{h:.1f}" '
                f'fill="#000000" opacity="0.25" rx="2"/>'
            )
        parts.append(
            f'<text x="{bar["x1"] + 6:.1f}" y="{(bar["y0"] + h / 2 + font_size / 3):.1f}" '
            f'font-family="sans-serif" font-size="{font_size - 2}" '
            f'fill="{s["text_color"]}">{escape(_shorten(bar["label"], 40))}</text>'
        )

    for summary in layout.summaries:
        points = _summary_outline(summary)
        coords = ' '.join(f'{px:.1f},{py:.1f}' for px, py in points)
        parts.append(
            f'<polygon points="{coords}" fill="{summary["color"]}" '
            f'stroke="#000000" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{summary["x1"] + 6:.1f}" '
            f'y="{(summary["y0"] + (summary["y1"] - summary["y0"]) / 2 + font_size / 3):.1f}" '
            f'font-family="sans-serif" font-size="{font_size - 2}" '
            f'font-weight="bold" fill="{s["text_color"]}"'
            f'>{escape(_shorten(summary["label"], 40))}</text>'
        )

    for milestone in layout.milestones:
        x, y = milestone['x'], milestone['y']
        r = MILESTONE_RADIUS
        parts.append(
            f'<polygon points="{x:.1f},{y - r:.1f} {x + r:.1f},{y:.1f} '
            f'{x:.1f},{y + r:.1f} {x - r:.1f},{y:.1f}" '
            f'fill="{milestone["color"]}" stroke="#000000" stroke-width="1.5"/>'
        )
        parts.append(
            f'<text x="{x + r + 6:.1f}" y="{y + font_size / 3:.1f}" '
            f'font-family="sans-serif" font-size="{font_size - 2}" '
            f'fill="{s["text_color"]}">{escape(milestone["label"])}</text>'
        )

    parts.append('</svg>')
    return '\n'.join(parts)


# ---------------------------------------------------------------------------
# Raster emitter
# ---------------------------------------------------------------------------

#: Fonts to look for, best coverage first. All are ordinary system fonts;
#: nothing is downloaded and nothing is installed.
FONT_CANDIDATES = (
    # Linux, which is what the .deb targets
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
    '/usr/share/fonts/TTF/DejaVuSans.ttf',
    '/usr/share/fonts/dejavu/DejaVuSans.ttf',
    '/usr/share/fonts/liberation-sans/LiberationSans-Regular.ttf',
    # macOS. Helvetica leads Arial deliberately: the two are metric
    # compatible - the same string measures the same to the pixel - and
    # Helvetica rasterises in about half the time. Text is some 95% of the
    # cost of drawing a chart, so which face is picked is a performance
    # decision as much as a typographic one.
    '/System/Library/Fonts/Helvetica.ttc',
    '/System/Library/Fonts/Supplemental/Arial.ttf',
    '/Library/Fonts/Arial.ttf',
    # Windows
    r'C:\Windows\Fonts\arial.ttf',
    r'C:\Windows\Fonts\segoeui.ttf',
)

#: Resolved once; None means nothing suitable was found.
_font_file: Optional[str] = None
_font_file_resolved = False


def find_font_file() -> Optional[str]:
    """
    Locate a system font with accented Latin coverage.

    RETURNS:
    --------
    Optional[str]
        Path to a usable TrueType font, or None to fall back to Pillow's
        built-in face.

    DEVELOPMENT NOTES:
    ------------------
    Pillow's built-in font covers little more than ASCII: every accented
    character renders as the same empty box, which turned Hungarian task
    names such as "SDLC kialakitasa" into a row of tofu. Only files already
    present on the machine are considered - nothing is fetched.
    """
    global _font_file, _font_file_resolved

    if _font_file_resolved:
        return _font_file

    _font_file_resolved = True
    for candidate in FONT_CANDIDATES:
        path = Path(candidate)
        if not path.exists():
            continue
        try:
            # Prove it loads before committing to it
            ImageFont.truetype(str(path), 12)
        except Exception:
            continue
        _font_file = str(path)
        logger.debug("Chart text will use %s", _font_file)
        return _font_file

    logger.warning(
        "No system font with accented Latin coverage was found; exported "
        "charts fall back to Pillow's built-in face and may show accented "
        "characters as empty boxes"
    )
    _font_file = None
    return None


def _font(size: int):
    """
    Get a scalable font at the requested size.

    Prefers a system TrueType face so accented characters render, and falls
    back to Pillow's built-in font when none is available.
    """
    path = find_font_file()
    if path:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            logger.exception("Could not load %s; falling back", path)

    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _safe_scale(layout: 'ChartLayout', scale: float) -> float:
    """
    Reduce the supersampling factor if the image would be too large.

    RETURNS:
    --------
    float
        A scale that keeps the intermediate image within MAX_PIXELS.
    """
    scale = max(1.0, float(scale))
    pixels = layout.width * layout.height * scale * scale
    if pixels <= MAX_PIXELS:
        return scale

    reduced = max(1.0, (MAX_PIXELS / (layout.width * layout.height)) ** 0.5)
    logger.info("Reducing chart supersampling from %.2f to %.2f: %dx%d would "
                "need %.0f megapixels", scale, reduced,
                layout.width, layout.height, pixels / 1e6)
    return reduced


def _draw_date_header(draw, layout: 'ChartLayout', s: Dict[str, Any],
                      sx, scale: float, font) -> None:
    """
    Paint the calendar strip, and the day shading that goes with it.

    PARAMETERS:
    -----------
    sx : callable
        Scales a layout coordinate to the supersampled image.

    DEVELOPMENT NOTES:
    ------------------
    The shading is drawn down the whole chart before the bars, so it sits
    behind them; the strip itself is drawn at the top. Non-working days and
    today are fills rather than text, which is what keeps a denser header
    from costing anything - the labels went from one full date every 82px to
    one number every 22px, and the number of *text* draws barely moved.
    """
    plot_top = MARGIN_TOP - HEADER_MONTH_HEIGHT - HEADER_CELL_HEIGHT
    band_bottom = plot_top + HEADER_MONTH_HEIGHT
    cell_bottom = band_bottom + HEADER_CELL_HEIGHT
    chart_bottom = layout.height - MARGIN_BOTTOM
    line_width = max(1, int(scale))

    # ---- shading down the chart, behind everything ----------------------
    for x0, x1, _label, is_today, is_working, _week in layout.day_cells:
        if is_today:
            colour = s['header_today_bg']
        elif not is_working:
            colour = s['header_non_working']
        else:
            continue
        draw.rectangle([(sx(x0), sx(cell_bottom)), (sx(x1), sx(chart_bottom))],
                       fill=colour)

    # ---- the week rules -------------------------------------------------
    for x, _label in layout.date_ticks:
        draw.line([(sx(x), sx(cell_bottom)), (sx(x), sx(chart_bottom))],
                  fill=s['grid_color'], width=line_width)

    # ---- the month band -------------------------------------------------
    for x0, x1, label in layout.month_bands:
        draw.rectangle([(sx(x0), sx(plot_top)), (sx(x1), sx(band_bottom))],
                       fill=s['header_month_bg'])
        draw.line([(sx(x0), sx(plot_top)), (sx(x0), sx(band_bottom))],
                  fill=s['header_week_rule'], width=line_width)
        # Centred in whatever of the band is on the chart, so a month running
        # off either edge still shows its name rather than losing it
        draw.text((sx((x0 + x1) / 2), sx((plot_top + band_bottom) / 2)), label,
                  font=font, fill=s['header_month_text'], anchor='mm')

    # ---- the day cells --------------------------------------------------
    for x0, x1, label, is_today, is_working, starts_week in layout.day_cells:
        if is_today:
            fill, ink = s['header_today_bg'], s['header_today_text']
        elif not is_working:
            fill, ink = s['header_non_working'], s['header_day_text']
        else:
            fill, ink = s['header_cell_bg'], s['header_day_text']

        draw.rectangle([(sx(x0), sx(band_bottom)), (sx(x1), sx(cell_bottom))],
                       fill=fill)
        draw.line([(sx(x0), sx(band_bottom)), (sx(x0), sx(cell_bottom))],
                  fill=s['header_week_rule'] if starts_week else s['header_rule'],
                  width=line_width)
        draw.text((sx((x0 + x1) / 2), sx((band_bottom + cell_bottom) / 2)),
                  label, font=font, fill=ink, anchor='mm')

    # ---- the rules closing the strip off --------------------------------
    # The cells draw a rule on their left edge only, so the last one needs
    # its right edge drawn or the strip ends in mid-air.
    if layout.day_cells:
        draw.line([(sx(layout.plot_right), sx(plot_top)),
                   (sx(layout.plot_right), sx(cell_bottom))],
                  fill=s['header_week_rule'], width=line_width)

    for y in (plot_top, band_bottom, cell_bottom):
        draw.line([(sx(layout.plot_left), sx(y)),
                   (sx(layout.plot_right), sx(y))],
                  fill=s['header_week_rule'], width=line_width)


def render_image(project: Project, settings: Optional[Dict[str, Any]] = None,
                 width: int = 1400, scale: float = 2.0,
                 min_width: int = MIN_WIDTH,
                 rows: Optional['RowPlan'] = None) -> Image.Image:
    """
    Render the chart into a PIL image.

    PARAMETERS:
    -----------
    scale : float
        Supersampling factor. The chart is drawn large and reduced with a
        high quality filter, which is what keeps text and bar edges smooth
        without needing an anti-aliasing capable drawing backend.
    min_width : int
        Floor for the rendered width; see layout_chart.
    rows : Optional[RowPlan]
        The rows to draw, when the chart is lined up with a task list; see
        layout_chart.

    RETURNS:
    --------
    Image.Image
        The finished RGB image.
    """
    layout = layout_chart(project, settings, width, min_width=min_width,
                          rows=rows)
    s = layout.settings
    scale = _safe_scale(layout, scale)

    size = (int(layout.width * scale), int(layout.height * scale))
    image = Image.new('RGB', size, s['bg_color'])
    draw = ImageDraw.Draw(image, 'RGBA')

    font_size = s['font_size']
    title_font = _font(int(18 * scale))
    label_font = _font(int(font_size * scale))
    small_font = _font(int((font_size - 2) * scale))

    def sx(value: float) -> float:
        """Scale a coordinate."""
        return value * scale

    draw.text((size[0] / 2, sx(TITLE_BASELINE)), layout.title,
              font=title_font, fill=s['text_color'], anchor='mm')

    if layout.empty_message:
        draw.text((size[0] / 2, size[1] / 2), layout.empty_message,
                  font=label_font, fill='#7f8c8d', anchor='mm')
        return image.resize((layout.width, layout.height), Image.LANCZOS)

    _draw_date_header(draw, layout, s, sx, scale, small_font)

    for y, label in layout.row_labels:
        draw.text((sx(MARGIN_LEFT - 12), sx(y)), label, font=label_font,
                  fill=s['text_color'], anchor='rm')

    for x0, y0, x1, y1 in layout.dependencies:
        _dashed_line(draw, sx(x0), sx(y0), sx(x1), sx(y1),
                     s['dependency_color'], max(1, int(1.5 * scale)))

    for bar in layout.bars:
        box = [sx(bar['x0']), sx(bar['y0']), sx(bar['x1']), sx(bar['y1'])]
        draw.rectangle(box, fill=bar['color'], outline='#000000',
                       width=max(1, int(scale)))
        if bar['progress']:
            filled = box[0] + (box[2] - box[0]) * bar['progress'] / 100
            draw.rectangle([box[0], box[1], filled, box[3]],
                           fill=(0, 0, 0, 64))
        draw.text((box[2] + sx(6), (box[1] + box[3]) / 2),
                  _shorten(bar['label'], 40), font=small_font,
                  fill=s['text_color'], anchor='lm')

    for summary in layout.summaries:
        draw.polygon([(sx(px), sx(py)) for px, py in _summary_outline(summary)],
                     fill=summary['color'], outline='#000000')
        draw.text((sx(summary['x1']) + sx(6),
                   (sx(summary['y0']) + sx(summary['y1'])) / 2),
                  _shorten(summary['label'], 40), font=small_font,
                  fill=s['text_color'], anchor='lm')

    for milestone in layout.milestones:
        x, y, r = sx(milestone['x']), sx(milestone['y']), sx(MILESTONE_RADIUS)
        draw.polygon([(x, y - r), (x + r, y), (x, y + r), (x - r, y)],
                     fill=milestone['color'], outline='#000000')
        draw.text((x + r + sx(6), y), milestone['label'], font=small_font,
                  fill=s['text_color'], anchor='lm')

    # Supersampled down for smooth edges
    return image.resize((layout.width, layout.height), Image.LANCZOS)


def _dashed_line(draw: ImageDraw.ImageDraw, x0: float, y0: float,
                 x1: float, y1: float, colour: str, width: int,
                 dash: int = 8, gap: int = 6) -> None:
    """Draw a dashed straight line, which ImageDraw has no primitive for."""
    length = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
    if length <= 0:
        return

    step_x = (x1 - x0) / length
    step_y = (y1 - y0) / length
    position = 0.0

    while position < length:
        end = min(position + dash, length)
        draw.line([(x0 + step_x * position, y0 + step_y * position),
                   (x0 + step_x * end, y0 + step_y * end)],
                  fill=colour, width=width)
        position = end + gap
