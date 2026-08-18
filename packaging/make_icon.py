#!/usr/bin/env python3
"""
Write the application icon out for the desktop entry and the package.

The icon itself is drawn in gantt_app/resources/appicon.py, which is part of
the application: the window wears the same mark at runtime, so there is one
drawing and no way for the packaged icon and the running one to drift apart.
This script only decides where it is written and at what size.

Usage:
    python3 packaging/make_icon.py <output.png> [size]
"""

import sys
from pathlib import Path

# Run from the repository root, where the package sits beside this script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gantt_app.resources.appicon import draw_icon


def main() -> int:
    """Write the icon to the path given on the command line."""
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    output = Path(sys.argv[1])
    size = int(sys.argv[2]) if len(sys.argv) > 2 else 256

    output.parent.mkdir(parents=True, exist_ok=True)
    draw_icon(size).save(output, 'PNG')
    print(f"Wrote {output} ({size}x{size})")
    return 0


if __name__ == '__main__':
    sys.exit(main())
