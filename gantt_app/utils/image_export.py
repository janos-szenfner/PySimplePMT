"""
Static export of the Gantt chart, rendered by Plotly.

WHY THIS MODULE EXISTS:
======================
matplotlib used to render the PNG and PDF exports while Plotly drew the
on-screen chart, which meant two renderers and two different-looking outputs.
Everything now goes through the Plotly figure built in chart_figure.py.

DEVELOPMENT NOTES:
------------------
Plotly turns a figure into a raster or PDF through Kaleido, and Kaleido 1.x
does that by driving a real Chrome or Chromium over the DevTools protocol. If
no browser is installed it tries to download one - a silent, multi-hundred
megabyte fetch that hangs a desktop app with no explanation.

So a browser check runs first and the export fails fast with a message naming
the fix. HTML export needs none of this: Plotly writes the page itself, with
plotly.js inlined so the result works offline.
"""

import shutil
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from gantt_app.models import Project
from gantt_app.utils.chart_figure import build_gantt_figure
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


#: Executables Kaleido can drive, in the order they are looked for.
CHROME_EXECUTABLES = (
    'chromium', 'chromium-browser', 'chrome', 'google-chrome',
    'google-chrome-stable', 'microsoft-edge',
)

#: Fixed locations to check when nothing is on PATH.
CHROME_PATHS = (
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
    '/usr/bin/google-chrome',
    '/snap/bin/chromium',
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
)

#: Shown when static export is attempted without a browser present.
NO_BROWSER_MESSAGE = (
    "Static image export needs a Chrome or Chromium browser, which Plotly's "
    "Kaleido renderer drives behind the scenes, and none was found.\n\n"
    "Install one:\n"
    "    sudo apt install chromium        (Debian/Ubuntu)\n"
    "    brew install --cask chromium     (macOS)\n\n"
    "Exporting to HTML works without a browser and keeps the chart "
    "interactive."
)


def find_browser() -> Optional[str]:
    """
    Locate a Chrome or Chromium executable for Kaleido.

    RETURNS:
    --------
    Optional[str]
        Path to a usable browser, or None when none is installed.

    DEVELOPMENT NOTES:
    ------------------
    Checked before every static export. Without it Kaleido would try to
    download a browser, which blocks for minutes with no feedback.
    """
    for name in CHROME_EXECUTABLES:
        found = shutil.which(name)
        if found:
            return found

    for path in CHROME_PATHS:
        if Path(path).exists():
            return path

    # Kaleido may already have fetched its own copy on a previous run
    try:
        from kaleido import get_chrome_sync  # noqa: F401
        cache = Path.home() / '.cache' / 'kaleido'
        if sys.platform == 'darwin':
            cache = Path.home() / 'Library' / 'Caches' / 'kaleido'
        if cache.exists() and any(cache.iterdir()):
            return str(cache)
    except Exception:
        pass

    return None


def static_export_available() -> bool:
    """Check whether PNG and PDF export can run on this machine."""
    try:
        import kaleido  # noqa: F401
    except ImportError:
        logger.info("Kaleido is not installed; static image export disabled")
        return False

    if find_browser() is None:
        logger.info("No Chrome or Chromium found; static image export disabled")
        return False

    return True


def _write_image(project: Project, filepath: str, image_format: str,
                 width: int, height: Optional[int],
                 scale: float, settings: Optional[Dict[str, Any]]) -> bool:
    """Render a project to an image file through Kaleido."""
    try:
        if not static_export_available():
            logger.error("Cannot export %s: no browser available for Kaleido",
                         image_format.upper())
            return False

        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        figure = build_gantt_figure(project, settings=settings,
                                    width=width, height=height)
        figure.write_image(str(path), format=image_format, scale=scale)

        logger.info("Exported %s to %s", image_format.upper(), path)
        return True

    except Exception:
        logger.exception("Error exporting the chart to %s", image_format.upper())
        return False


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
        Image width in pixels before scaling.
    height : Optional[int]
        Image height in pixels; derived from the task count when omitted.
    scale : float
        Resolution multiplier; 2.0 gives a sharp image for printing.
    settings : Optional[Dict[str, Any]]
        Appearance overrides passed to the figure builder.

    RETURNS:
    --------
    bool
        True on success, False if rendering failed or no browser is present.
    """
    return _write_image(project, filepath, 'png', width, height, scale, settings)


def export_gantt_to_pdf(project: Project, filepath: str,
                        width: int = 1400, height: Optional[int] = None,
                        settings: Optional[Dict[str, Any]] = None) -> bool:
    """
    Export a project's Gantt chart to a PDF file.

    RETURNS:
    --------
    bool
        True on success, False if rendering failed or no browser is present.
    """
    return _write_image(project, filepath, 'pdf', width, height, 1.0, settings)


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
    file opens without an internet connection. It costs a few megabytes and
    is the only export that needs no browser installed to produce.
    """
    try:
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        figure = build_gantt_figure(project, settings=settings,
                                    width=width, height=height)
        figure.write_html(str(path), include_plotlyjs=True, full_html=True)

        logger.info("Exported HTML to %s", path)
        return True

    except Exception:
        logger.exception("Error exporting the chart to HTML")
        return False
