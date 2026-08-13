#!/usr/bin/env python3
"""
Generate the application icon used by the desktop entry.

The icon is drawn rather than committed as a binary blob, so it stays
reviewable in version control and rebuilds identically. Pillow is already a
dependency of matplotlib, so this adds nothing to the requirements.

Usage:
    python3 packaging/make_icon.py <output.png> [size]
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw

#: Palette matching the application's default task colours.
BACKGROUND = (31, 106, 165, 255)   # #1f6aa5, the default task colour
BAR_COLORS = [
    (236, 240, 241, 255),          # light bar
    (241, 196, 15, 255),           # critical path amber
    (236, 240, 241, 255),
    (231, 76, 60, 255),            # milestone red
]


def draw_icon(size: int = 256) -> Image.Image:
    """
    Draw a Gantt-like icon at the requested size.

    PARAMETERS:
    -----------
    size : int
        Width and height of the square icon in pixels.

    RETURNS:
    --------
    Image.Image
        The rendered RGBA image.
    """
    image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # Rounded background tile
    radius = int(size * 0.18)
    draw.rounded_rectangle([(0, 0), (size - 1, size - 1)],
                           radius=radius, fill=BACKGROUND)

    # Four staggered bars suggesting a Gantt chart
    margin = int(size * 0.16)
    usable = size - (margin * 2)
    bar_height = int(usable * 0.15)
    gap = int((usable - bar_height * len(BAR_COLORS)) / (len(BAR_COLORS) - 1))
    bar_radius = max(2, bar_height // 3)

    offsets = [0.00, 0.18, 0.36, 0.54]
    widths = [0.55, 0.62, 0.46, 0.16]

    for index, colour in enumerate(BAR_COLORS):
        top = margin + index * (bar_height + gap)
        left = margin + int(usable * offsets[index])
        right = min(left + int(usable * widths[index]), size - margin)
        draw.rounded_rectangle([(left, top), (right, top + bar_height)],
                               radius=bar_radius, fill=colour)

    return image


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
