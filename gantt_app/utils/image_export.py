"""
Static export of the Gantt chart: PNG, PDF, SVG and interactive HTML.

WHY THIS MODULE EXISTS:
======================
Nothing here reaches the network or shells out to another program. The
application must work from exactly what it ships with, so every format is
produced by code and libraries already inside the bundle:

  * PNG and PDF - drawn by chart_render.py with Pillow
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

from gantt_app.models import Project
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
    Export a project's Gantt chart to a PDF file.

    RETURNS:
    --------
    bool
        True on success, False if writing failed.

    DEVELOPMENT NOTES:
    ------------------
    Pillow writes the PDF, embedding the rendered page at 150 dpi. A true
    vector PDF would mean another rendering library; the SVG export already
    covers the case where scalable output matters.
    """
    try:
        path = _prepare(filepath)
        image = render_image(project, settings=settings, width=width, scale=2.0)
        image.save(path, 'PDF', resolution=150.0)
        logger.info("Exported PDF to %s", path)
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
