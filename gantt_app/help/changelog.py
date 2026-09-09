"""
The Changelog window: the project's CHANGELOG.md, read like the Help guide.

WHY THIS MODULE EXISTS:
======================
About > Changelog opens the same scrolling, searchable reference the Help
guide uses, so a reader sees what changed release by release without leaving
the application or opening a file. The single source of truth is the
repository's CHANGELOG.md; this module reads it and turns each `## version`
heading and its bullets into the (heading, paragraphs) sections a
ReferenceWindow renders.

The file is bundled into the packaged build (see packaging/pysimplepmt.spec),
and the reader tries a handful of locations so it is found both from a source
checkout and from a frozen app.
"""

import re
import sys
from pathlib import Path

from gantt_app.help.reference import ReferenceWindow
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


def _changelog_path_candidates():
    """Where CHANGELOG.md might be, source checkout or frozen app first."""
    here = Path(__file__).resolve()
    candidates = [here.parents[2] / 'CHANGELOG.md']      # repo root in dev
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        candidates.append(Path(meipass) / 'CHANGELOG.md')
        candidates.append(Path(meipass) / 'gantt_app' / 'CHANGELOG.md')
    candidates.append(here.parent.parent / 'CHANGELOG.md')
    return candidates


def _read_changelog_text() -> str:
    """The changelog markdown, or a short note when it cannot be found."""
    for path in _changelog_path_candidates():
        try:
            if path.is_file():
                return path.read_text(encoding='utf-8')
        except OSError:
            continue
    logger.info("CHANGELOG.md not found in any known location")
    return ("# Changelog\n\n## Unavailable\n"
            "- The changelog file could not be found.")


def _clean(text: str) -> str:
    """Plain text from a line of markdown: no bold marks, no code ticks."""
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = text.replace('`', '')
    return re.sub(r'\s+', ' ', text).strip()


def parse_changelog(text: str) -> tuple:
    """
    Turn CHANGELOG.md into (heading, [paragraph, ...]) sections.

    Each ``## `` line starts a section; its bullets become paragraphs, each
    prefixed with a bullet dot, and a bullet wrapped over several lines is
    rejoined. The top ``# Changelog`` title is dropped.
    """
    sections = []
    heading = None
    paragraphs = []
    current = None

    def flush_paragraph():
        nonlocal current
        if current is not None:
            cleaned = _clean(' '.join(current))
            if cleaned:
                paragraphs.append(f"• {cleaned}")
            current = None

    def flush_section():
        nonlocal heading, paragraphs
        flush_paragraph()
        if heading is not None:
            sections.append((heading, paragraphs))
        paragraphs = []

    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if line.startswith('## '):
            flush_section()
            heading = line[3:].strip()
        elif line.startswith('# '):
            continue
        elif not stripped:
            flush_paragraph()
        elif stripped.startswith('- '):
            flush_paragraph()
            current = [stripped[2:].strip()]
        else:
            if current is None:
                current = [stripped]
            else:
                current.append(stripped)

    flush_section()
    if not sections:
        sections = [("Changelog", ["The changelog is empty."])]
    return tuple(sections)


#: Parsed once at import, the way the Help guide's sections are module-level.
CHANGELOG_SECTIONS = parse_changelog(_read_changelog_text())


class ChangelogWindow(ReferenceWindow):
    """The changelog, opened from About > Changelog and read like the guide."""

    TITLE = "Changelog"
    GEOMETRY = "820x720"
    MINSIZE = (560, 400)
    SECTIONS = CHANGELOG_SECTIONS
    SEARCHABLE = True

    #: Its own instance, so the changelog and the guide can be open together.
    _open_window = None


def show_changelog(master=None):
    """Open the Changelog window, or raise the copy already open."""
    logger.info("Showing the Changelog (%d entries)", len(CHANGELOG_SECTIONS))
    return ChangelogWindow.show(master)
