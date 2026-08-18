#!/usr/bin/env python3
"""
Write the application icon out as a macOS .icns.

The icon itself is drawn in gantt_app/resources/appicon.py, which is part of
the application, so the window, the desktop entry, the .deb and the .app all
wear the same mark.

macOS wants an icon family rather than a single image: an .iconset directory
holding each size at both normal and Retina scale, compiled by iconutil. That
is the documented route and the only one that produces a file the Finder,
the Dock and the app switcher all read.

Usage:
    python3 packaging/make_icns.py <output.icns>
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Run from the repository root, where the package sits beside this script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gantt_app.resources.appicon import draw_icon

#: The sizes an .iconset carries, as (points, scale). macOS names them
#: icon_<points>x<points>.png and icon_<points>x<points>@2x.png, and the @2x
#: file is drawn at twice the points.
ICONSET = (
    (16, 1), (16, 2),
    (32, 1), (32, 2),
    (128, 1), (128, 2),
    (256, 1), (256, 2),
    (512, 1), (512, 2),
)


def build_iconset(directory: Path) -> None:
    """Draw every member of the icon family into an .iconset directory."""
    directory.mkdir(parents=True, exist_ok=True)
    for points, scale in ICONSET:
        suffix = '@2x' if scale == 2 else ''
        name = f"icon_{points}x{points}{suffix}.png"
        draw_icon(points * scale).save(directory / name, 'PNG')


def main() -> int:
    """Write the .icns to the path given on the command line."""
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    output = Path(sys.argv[1])
    output.parent.mkdir(parents=True, exist_ok=True)

    if not shutil.which('iconutil'):
        print("iconutil is not available; this only runs on macOS",
              file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as workspace:
        iconset = Path(workspace) / 'pysimplepmt.iconset'
        build_iconset(iconset)
        subprocess.run(
            ['iconutil', '--convert', 'icns', str(iconset),
             '--output', str(output)],
            check=True,
        )

    print(f"Wrote {output} ({output.stat().st_size} bytes)")
    return 0


if __name__ == '__main__':
    sys.exit(main())
