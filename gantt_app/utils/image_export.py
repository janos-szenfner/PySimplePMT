"""
Static export of the Gantt chart: PNG, PDF, SVG and interactive HTML.

WHY THIS MODULE EXISTS:
======================
Nothing here reaches the network or shells out to another program. The
application must work from exactly what it ships with, so every format is
produced by code and libraries already inside the bundle:

  * PNG       - drawn by chart_render.py with Pillow
  * PDF       - a three page document, laid out by page_render.py
  * SVG         - written as text by chart_render.py, no dependency at all
  * HTML        - Plotly's own writer, with plotly.js inlined

DEVELOPMENT NOTES:
------------------
Kaleido used to render PNG and PDF. It works by driving a real Chrome or
Chromium over the DevTools protocol and downloads a browser when none is
present - hundreds of megabytes fetched at runtime, which defeats the point of
a self-contained package. It has been removed entirely.
"""

from pathlib import Path
from typing import Any, Dict, Optional

from gantt_app.core.models import Project
from gantt_app.utils.chart_figure import build_gantt_figure
from gantt_app.utils.chart_render import render_image, render_svg
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


def static_export_available() -> bool:
    """
    Check whether PNG and PDF export can run.

    RETURNS:
    --------
    bool
        True whenever Pillow is importable, which it always is in a packaged
        build. Kept so callers need not care how rendering is done.
    """
    try:
        import PIL  # noqa: F401
        return True
    except ImportError:
        logger.error("Pillow is missing; static image export is unavailable")
        return False


def _prepare(filepath: str) -> Path:
    """Resolve a destination path, creating parent directories."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def export_gantt_to_png(project: Project, filepath: str,
                        width: int = 1400, height: Optional[int] = None,
                        scale: float = 2.0,
                        settings: Optional[Dict[str, Any]] = None) -> bool:
    """
    Export a project's Gantt chart to a PNG file.

    PARAMETERS:
    -----------
    project : Project
        The project to render.
    filepath : str
        Destination path. Parent directories are created.
    width : int
        Image width in pixels.
    height : Optional[int]
        Accepted for call compatibility; the height follows the task count.
    scale : float
        Supersampling factor for smoother text and edges.
    settings : Optional[Dict[str, Any]]
        Appearance overrides passed through to the renderer.

    RETURNS:
    --------
    bool
        True on success, False if writing failed.
    """
    try:
        path = _prepare(filepath)
        image = render_image(project, settings=settings, width=width,
                             scale=scale)
        image.save(path, 'PNG')
        logger.info("Exported PNG to %s (%dx%d)", path, *image.size)
        return True
    except Exception:
        logger.exception("Error exporting the chart to PNG")
        return False


def export_gantt_to_pdf(project: Project, filepath: str,
                        width: int = 1400, height: Optional[int] = None,
                        settings: Optional[Dict[str, Any]] = None) -> bool:
    """
    Export a project to a three page PDF document.

    PARAMETERS:
    -----------
    project : Project
        The plan to print.
    filepath : str
        Destination path. Parent directories are created.
    width, height : int, Optional[int]
        Accepted for call compatibility. The pages are a fixed physical size
        - see page_render.PAGE_INCHES - because a printed document is, and
        the width of a window has nothing to say about it.
    settings : Optional[Dict[str, Any]]
        Appearance overrides passed through to the chart.

    RETURNS:
    --------
    bool
        True on success, False if writing failed.

    DEVELOPMENT NOTES:
    ------------------
    Three pages, each answering a different question - the list beside the
    chart, the chart alone, and the list as a full table; see page_render.
    A PDF of the chart on its own was half a plan: the bars say when work
    happens and nothing else, so printed and handed round it was a picture
    rather than a document.

    The resolution matters as much as the drawing. A PDF page is pixels plus
    a number saying how many of them go in an inch, and this used to save a
    2800 pixel image at 150 - a page eighteen inches wide that every printer
    then shrank by an amount of its own choosing. The pages are now drawn at
    exactly the size they are declared to be, so A4 comes out A4.

    Pillow writes it. A true vector PDF would mean another rendering library;
    the SVG export already covers the case where scalable output matters.
    """
    try:
        from gantt_app.utils.page_render import PAGE_DPI, render_pages

        path = _prepare(filepath)
        pages = render_pages(project, settings=settings)
        if not pages:
            logger.error("Nothing to export: no pages were drawn")
            return False

        first, rest = pages[0], pages[1:]
        first.save(path, 'PDF', save_all=True, append_images=rest,
                   resolution=float(PAGE_DPI))
        logger.info("Exported a %d page PDF to %s at %d dpi",
                    len(pages), path, PAGE_DPI)
        return True
    except Exception:
        logger.exception("Error exporting the chart to PDF")
        return False


def export_gantt_to_svg(project: Project, filepath: str,
                        width: int = 1400,
                        settings: Optional[Dict[str, Any]] = None) -> bool:
    """
    Export a project's Gantt chart to a scalable SVG file.

    RETURNS:
    --------
    bool
        True on success, False if writing failed.
    """
    try:
        path = _prepare(filepath)
        path.write_text(render_svg(project, settings=settings, width=width),
                        encoding='utf-8')
        logger.info("Exported SVG to %s", path)
        return True
    except Exception:
        logger.exception("Error exporting the chart to SVG")
        return False


def export_gantt_to_html(project: Project, filepath: str,
                         width: int = 1400, height: Optional[int] = None,
                         settings: Optional[Dict[str, Any]] = None) -> bool:
    """
    Export a project's Gantt chart to a standalone interactive HTML page.

    RETURNS:
    --------
    bool
        True on success, False otherwise.

    DEVELOPMENT NOTES:
    ------------------
    plotly.js is written into the page rather than linked from a CDN, so the
    file opens and stays interactive with no internet connection. That costs a
    few megabytes per file and is the whole point: nothing the application
    produces may depend on fetching something later.
    """
    try:
        path = _prepare(filepath)
        figure = build_gantt_figure(project, settings=settings,
                                    width=width, height=height)
        figure.write_html(str(path), include_plotlyjs=True, full_html=True)
        logger.info("Exported HTML to %s", path)
        return True
    except Exception:
        logger.exception("Error exporting the chart to HTML")
        return False


# ---------------------------------------------------------------------------
# The dashboard and the timeline (issues #66, #83)
# ---------------------------------------------------------------------------

#: How big the board exports draw, in logical pixels; the file carries
#: them at `scale` times that and is downsampled once on the way out,
#: the same antialiasing trick render_image uses.
BOARD_EXPORT_SIZE = (1600, 1000)
TIMELINE_EXPORT_SIZE = (1600, 900)

#: The pixels-per-inch a board page is written at, so a PDF comes out a
#: printable size rather than however many inches the pixels happened to
#: stretch to.
BOARD_EXPORT_DPI = 150


def _fallback_palette() -> Dict[str, Any]:
    """
    The light appearance, as literals.

    The drawing is theme-aware but this module sits under the views - a
    palette is handed in by the caller that has one, and this is what a
    caller without one gets so an export never fails for want of colours.
    """
    return {
        'bg': '#f5f6f8', 'panel_bg': '#ffffff', 'title': '#1f2328',
        'tick': '#4a5568', 'axis': '#8a9199', 'grid': '#e2e5e9',
        'progress_bar': '#3b82f6', 'progress_under': '#1c2b3a',
        'duration_bar': '#10b981',
        'series': ['#4f46e5', '#059669', '#d97706', '#dc2626'],
        'kpi_bg': '#eef1f5', 'kpi_border': '#c8cdd2',
        'header_bg': '#eef1f5', 'header_text': '#4a5568',
        'band_bg': '#3f4753', 'band_text': '#ffffff',
        'lane_bg': '#f4f5f7', 'lane_text': '#1f2328',
        'spine': '#2f3552', 'today': '#2e7d32',
    }


def _board_image(draw_fn, width: int, height: int, scale: float):
    """The image a board export is made of - drawn big, shrunk once."""
    from PIL import Image
    from gantt_app.utils.drawpen import ImagePen

    image = Image.new('RGB', (int(width * scale), int(height * scale)),
                      'white')
    draw_fn(ImagePen(image, scale), width, height)
    if scale != 1.0:
        image = image.resize((width, height), Image.LANCZOS)
    return image


def export_dashboard_to_png(project: Project, filepath: str,
                            enabled_ids=None, maximized_id=None,
                            palette=None, scale: float = 2.0) -> bool:
    """
    The dashboard as it stands - the panels it shows, and one alone when
    it is maximized - as a PNG file (issue #66).
    """
    from gantt_app.utils import boardrender

    try:
        path = _prepare(filepath)
        width, height = BOARD_EXPORT_SIZE
        palette = palette or _fallback_palette()
        rows = boardrender.dashboard_rows(project)

        def draw(pen, w, h):
            pen.rect(0, 0, w, h, fill=palette['bg'])
            boardrender.render_dashboard(
                pen, rows, palette, enabled_ids, maximized_id,
                width=w, height=h)

        image = _board_image(draw, width, height, scale)
        image.save(path, 'PNG')
        logger.info("Exported the dashboard to PNG %s", path)
        return True
    except Exception:
        logger.exception("Error exporting the dashboard to PNG")
        return False


def export_timeline_to_png(project: Project, filepath: str,
                           style_id: str = 'lanes', palette=None,
                           scale: float = 2.0) -> bool:
    """The timeline in the style the user picked, as a PNG (issue #83)."""
    from gantt_app.utils import boardrender

    try:
        path = _prepare(filepath)
        width, height = TIMELINE_EXPORT_SIZE
        palette = palette or _fallback_palette()

        def draw(pen, w, h):
            boardrender.render_timeline(pen, project, style_id,
                                        palette, w, h)

        image = _board_image(draw, width, height, scale)
        image.save(path, 'PNG')
        logger.info("Exported the '%s' timeline to PNG %s",
                    style_id, path)
        return True
    except Exception:
        logger.exception("Error exporting the timeline to PNG")
        return False


def export_dashboard_to_pdf(project: Project, filepath: str,
                            enabled_ids=None, maximized_id=None,
                            palette=None, scale: float = 2.0) -> bool:
    """The dashboard as a one page landscape PDF (issue #66)."""
    from gantt_app.utils import boardrender

    try:
        path = _prepare(filepath)
        width, height = BOARD_EXPORT_SIZE
        palette = palette or _fallback_palette()
        rows = boardrender.dashboard_rows(project)

        def draw(pen, w, h):
            pen.rect(0, 0, w, h, fill=palette['bg'])
            boardrender.render_dashboard(
                pen, rows, palette, enabled_ids, maximized_id,
                width=w, height=h)

        image = _board_image(draw, width, height, scale)
        image.save(path, 'PDF', resolution=float(BOARD_EXPORT_DPI))
        logger.info("Exported the dashboard to PDF %s", path)
        return True
    except Exception:
        logger.exception("Error exporting the dashboard to PDF")
        return False


def export_timeline_to_pdf(project: Project, filepath: str,
                           style_id: str = 'lanes', palette=None,
                           scale: float = 2.0) -> bool:
    """The timeline in the picked style as a one page PDF (issue #83)."""
    from gantt_app.utils import boardrender

    try:
        path = _prepare(filepath)
        width, height = TIMELINE_EXPORT_SIZE
        palette = palette or _fallback_palette()

        def draw(pen, w, h):
            boardrender.render_timeline(pen, project, style_id,
                                        palette, w, h)

        image = _board_image(draw, width, height, scale)
        image.save(path, 'PDF', resolution=float(BOARD_EXPORT_DPI))
        logger.info("Exported the '%s' timeline to PDF %s",
                    style_id, path)
        return True
    except Exception:
        logger.exception("Error exporting the timeline to PDF")
        return False
