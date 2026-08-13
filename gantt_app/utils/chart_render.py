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
BAR_HEIGHT = 20
MARGIN_LEFT = 220
MARGIN_RIGHT = 60
MARGIN_TOP = 70
MARGIN_BOTTOM = 70
MIN_WIDTH = 900
MILESTONE_RADIUS = 9
LABEL_CHARS = 28


@dataclass
class ChartLayout:
    """Geometry for one rendered chart, in pixels."""

    width: int
    height: int
    settings: Dict[str, Any]
    bars: List[Dict[str, Any]] = field(default_factory=list)
    milestones: List[Dict[str, Any]] = field(default_factory=list)
    dependencies: List[Tuple[float, float, float, float]] = field(default_factory=list)
    row_labels: List[Tuple[float, str]] = field(default_factory=list)
    date_ticks: List[Tuple[float, str]] = field(default_factory=list)
    title: str = ""
    empty_message: Optional[str] = None


def _shorten(text: str, limit: int = LABEL_CHARS) -> str:
    """Trim a label to fit the left margin."""
    return text if len(text) <= limit else text[:limit - 1] + '...'


def _tick_step(days: int) -> int:
    """Choose a sensible gap between date labels for the given span."""
    for step in (1, 2, 7, 14, 30, 60, 90, 180, 365):
        if days / step <= 12:
            return step
    return max(1, days // 12)


#: Horizontal space each day should get before the chart starts scrolling.
MIN_PIXELS_PER_DAY = 6

#: Upper bound on the rendered width, so a multi-year plan cannot produce an
#: image large enough to exhaust memory.
MAX_WIDTH = 6000


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

    if project.tasks:
        low, high = calculate_date_range(
            sorted(project.tasks, key=lambda t: t.start_date)
        )
        days = max((high - low).days, 1)
        needed = MARGIN_LEFT + MARGIN_RIGHT + days * MIN_PIXELS_PER_DAY
        width = max(width, needed)

    return min(width, MAX_WIDTH)


def layout_chart(project: Project, settings: Optional[Dict[str, Any]] = None,
                 width: int = 1400) -> ChartLayout:
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

    RETURNS:
    --------
    ChartLayout
        Positions for every bar, milestone, dependency line and label.
    """
    resolved = _merged_settings(settings)
    width = max(int(width), MIN_WIDTH)

    tasks = sorted(project.tasks, key=lambda t: t.start_date)
    title = f"Gantt Chart: {project.name or 'New Project'}"

    if not tasks:
        return ChartLayout(width=width, height=320, settings=resolved,
                           title=title,
                           empty_message="Add tasks to see the Gantt chart")

    height = MARGIN_TOP + len(tasks) * ROW_HEIGHT + MARGIN_BOTTOM
    plot_left = MARGIN_LEFT
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
        return MARGIN_TOP + index * ROW_HEIGHT + ROW_HEIGHT / 2

    layout = ChartLayout(width=width, height=height, settings=resolved,
                         title=title)

    positions = {task.id: index for index, task in enumerate(tasks)}
    critical = {t.id for t in project.get_critical_path()}

    for index, task in enumerate(tasks):
        centre = y_for(index)
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

        layout.bars.append({
            'x0': start_x,
            'x1': end_x,
            'y0': centre - BAR_HEIGHT / 2,
            'y1': centre + BAR_HEIGHT / 2,
            'color': (resolved['critical_path_color'] if task.id in critical
                      else task.color),
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

    step = _tick_step(total_days)
    tick = min_date
    while tick <= max_date:
        layout.date_ticks.append((x_for(tick), tick.strftime('%Y-%m-%d')))
        tick += timedelta(days=step)

    return layout


# ---------------------------------------------------------------------------
# SVG emitter
# ---------------------------------------------------------------------------

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
        f'<text x="{layout.width / 2}" y="34" text-anchor="middle" '
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

    for x, label in layout.date_ticks:
        parts.append(
            f'<line x1="{x:.1f}" y1="{MARGIN_TOP - 10}" x2="{x:.1f}" '
            f'y2="{layout.height - MARGIN_BOTTOM}" stroke="{s["grid_color"]}" '
            f'stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{x:.1f}" y="{layout.height - MARGIN_BOTTOM + 20}" '
            f'text-anchor="middle" font-family="sans-serif" '
            f'font-size="{font_size - 2}" fill="{s["text_color"]}" '
            f'transform="rotate(-35 {x:.1f} {layout.height - MARGIN_BOTTOM + 20})"'
            f'>{escape(label)}</text>'
        )

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
    # macOS
    '/System/Library/Fonts/Supplemental/Arial.ttf',
    '/Library/Fonts/Arial.ttf',
    '/System/Library/Fonts/Helvetica.ttc',
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


def render_image(project: Project, settings: Optional[Dict[str, Any]] = None,
                 width: int = 1400, scale: float = 2.0) -> Image.Image:
    """
    Render the chart into a PIL image.

    PARAMETERS:
    -----------
    scale : float
        Supersampling factor. The chart is drawn large and reduced with a
        high quality filter, which is what keeps text and bar edges smooth
        without needing an anti-aliasing capable drawing backend.

    RETURNS:
    --------
    Image.Image
        The finished RGB image.
    """
    layout = layout_chart(project, settings, width)
    s = layout.settings
    scale = max(1.0, float(scale))

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

    draw.text((size[0] / 2, sx(24)), layout.title, font=title_font,
              fill=s['text_color'], anchor='mm')

    if layout.empty_message:
        draw.text((size[0] / 2, size[1] / 2), layout.empty_message,
                  font=label_font, fill='#7f8c8d', anchor='mm')
        return image.resize((layout.width, layout.height), Image.LANCZOS)

    for x, label in layout.date_ticks:
        draw.line([(sx(x), sx(MARGIN_TOP - 10)),
                   (sx(x), sx(layout.height - MARGIN_BOTTOM))],
                  fill=s['grid_color'], width=max(1, int(scale)))
        draw.text((sx(x), sx(layout.height - MARGIN_BOTTOM + 16)), label,
                  font=small_font, fill=s['text_color'], anchor='ma')

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
