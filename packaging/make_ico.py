#!/usr/bin/env python3
"""
Write the application icon out as a Windows .ico.

The icon comes from gantt_app/resources/appicon.py, which loads the one logo
image the application ships, so the Windows executable wears the same mark as
the macOS .app, the Linux desktop entry and the running window.

A .ico is a container of several sizes; Windows picks the one it needs for the
taskbar, the title bar, the Alt-Tab switcher and the Explorer tile. Pillow
writes them all from a single high-resolution source.

Usage:
    python3 packaging/make_ico.py <output.ico>
"""

import sys
from pathlib import Path

# Run from the repository root, where the package sits beside this script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gantt_app.resources.appicon import draw_icon

#: The sizes Windows reads from an .ico, largest first.
ICO_SIZES = (256, 128, 64, 48, 32, 16)


def main() -> int:
    """Write the .ico to the path given on the command line."""
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    output = Path(sys.argv[1])
    output.parent.mkdir(parents=True, exist_ok=True)

    # Draw at the largest size and let Pillow embed the smaller members.
    largest = draw_icon(max(ICO_SIZES))
    largest.save(output, 'ICO', sizes=[(s, s) for s in ICO_SIZES])

    print(f"Wrote {output} ({output.stat().st_size} bytes)")
    return 0


if __name__ == '__main__':
    sys.exit(main())
