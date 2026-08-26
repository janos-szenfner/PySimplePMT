"""
Generated icon definitions for the Gantt Project Management Tool.

This module contains icon definitions and utilities for the icon toolbar.
All icons are open source and generated programmatically.

Every icon is a short list of strokes in a unit square - see ICON_STROKES -
painted with Pillow at whatever size and ink the row asks for.

Available icons:
- open, new_project, save, edit
- task, subtask, milestone, phase, deliverable
- cut, copy, paste, delete
- undo, redo
- sun, moon (the light and dark appearances)

Everything here is drawn from coordinates in this file with Pillow. There is
no bundled artwork and nothing is fetched, so the icons carry no licence of
their own beyond this project's.
"""

from typing import Dict, List


# =============================================================================
# ICON GROUPS
# =============================================================================

# Icons that should always be active (enabled)
ALWAYS_ACTIVE: List[str] = ['open']

# Icons that should be active only when there's an open/new project
ACTIVE_WHEN_PROJECT_OPEN: List[str] = [
    'new_project', 'save', 'save_as', 'edit',
    'task', 'subtask', 'milestone', 'phase', 'deliverable',
    'indent', 'outdent',
    'link', 'unlink',
    'bold', 'italic', 'underline',
    'text_color', 'fill_color', 'style_preset', 'clear_style',
    'mark_on_track',
    'critical_path',
    'cut', 'copy', 'paste', 'delete',
    'undo', 'redo'
]

# Work item creation icons
WORK_ITEM_CREATION_ICONS: List[str] = ['task', 'subtask', 'milestone', 'phase', 'deliverable']

# =============================================================================
# DRAWN ICONS
# =============================================================================
#
# WHY THESE EXIST:
# ----------------
# The toolbar set its buttons in "Segoe UI Emoji" and put an emoji character
# on each one. That font ships with Windows and with nothing else, and a
# stock Linux desktop has no emoji font at all, so every button on the row
# came out blank - which is what the icon toolbar looked like on Linux.
#
# datepicker.py met the same thing and answered it the same way: the glyph is
# drawn, so it depends on no font being installed. Pillow is already required
# for the chart exports, so this costs no new dependency.
#
# Each icon is a few strokes in a square running 0 to 1, so the drawing is
# independent of the size it ends up at. They are painted at four times the
# size and reduced, which keeps the edges clean on a HiDPI screen.

from typing import Optional, Tuple

from PIL import Image, ImageDraw

#: The strokes each icon is made of, in a unit square.
#:
#: 'line' is a polyline through the points given, 'shape' a closed outline,
#: 'ellipse' the oval within the two corners, and 'fill' a solid rectangle.
ICON_STROKES: Dict[str, List[tuple]] = {
    'open': [
        ('shape', [(0.08, 0.28), (0.42, 0.28), (0.50, 0.40),
                   (0.92, 0.40), (0.92, 0.84), (0.08, 0.84)]),
    ],
    'new_project': [
        ('shape', [(0.22, 0.10), (0.62, 0.10), (0.78, 0.28),
                   (0.78, 0.90), (0.22, 0.90)]),
        ('line', [(0.50, 0.46), (0.50, 0.72)]),
        ('line', [(0.37, 0.59), (0.63, 0.59)]),
    ],
    'save': [
        ('shape', [(0.12, 0.12), (0.74, 0.12), (0.88, 0.26),
                   (0.88, 0.88), (0.12, 0.88)]),
        ('shape', [(0.30, 0.12), (0.66, 0.12), (0.66, 0.40), (0.30, 0.40)]),
        ('shape', [(0.28, 0.56), (0.72, 0.56), (0.72, 0.88), (0.28, 0.88)]),
    ],
    'edit': [
        ('line', [(0.16, 0.84), (0.24, 0.62), (0.68, 0.18),
                  (0.84, 0.34), (0.40, 0.78), (0.16, 0.84)]),
        ('line', [(0.60, 0.26), (0.76, 0.42)]),
    ],
    # Saving under a new name: the same floppy, drawn smaller to leave the
    # corner for the plus that says it becomes a second file rather than
    # overwriting the one already open.
    'save_as': [
        ('shape', [(0.06, 0.08), (0.54, 0.08), (0.66, 0.20),
                   (0.66, 0.68), (0.06, 0.68)]),
        ('shape', [(0.20, 0.08), (0.46, 0.08), (0.46, 0.28), (0.20, 0.28)]),
        ('line', [(0.76, 0.64), (0.76, 0.94)]),
        ('line', [(0.61, 0.79), (0.91, 0.79)]),
    ],
    # The row's background: a highlighter nib over the stripe it lays
    # down. A paint bucket was tried first and read as a triangle at 20
    # pixels, which is the size that matters.
    'fill_color': [
        ('line', [(0.20, 0.56), (0.56, 0.16), (0.76, 0.36),
                  (0.40, 0.74), (0.20, 0.74), (0.20, 0.56)]),
        ('fill', [(0.12, 0.84), (0.88, 0.94)]),
    ],
    # A whole look in one press, drawn as the tag it puts on a row.
    'style_preset': [
        ('shape', [(0.10, 0.10), (0.52, 0.10), (0.90, 0.48),
                   (0.52, 0.86), (0.10, 0.86)]),
        ('ellipse', [(0.22, 0.36), (0.36, 0.50)]),
    ],
    # Back to the grid's own. A cross rather than the bin used for Delete:
    # this removes formatting, not the row, and the two must not look alike.
    'clear_style': [
        ('line', [(0.22, 0.22), (0.78, 0.78)]),
        ('line', [(0.78, 0.22), (0.22, 0.78)]),
    ],
    # Caught up with today: an arrow running into the status date, which is
    # the line everything to the left of it has already passed.
    'mark_on_track': [
        ('line', [(0.08, 0.50), (0.62, 0.50)]),
        ('line', [(0.44, 0.32), (0.62, 0.50), (0.44, 0.68)]),
        ('line', [(0.80, 0.14), (0.80, 0.86)]),
    ],
    # Indent and outdent: the plan as four rows with the middle two moved,
    # and an arrow saying which way. Mirror images of each other, because
    # that is the only thing that tells them apart at 20 pixels.
    'indent': [
        ('line', [(0.10, 0.14), (0.90, 0.14)]),
        ('line', [(0.42, 0.38), (0.90, 0.38)]),
        ('line', [(0.42, 0.62), (0.90, 0.62)]),
        ('line', [(0.10, 0.86), (0.90, 0.86)]),
        ('line', [(0.10, 0.36), (0.28, 0.50), (0.10, 0.64)]),
    ],
    'outdent': [
        ('line', [(0.10, 0.14), (0.90, 0.14)]),
        ('line', [(0.42, 0.38), (0.90, 0.38)]),
        ('line', [(0.42, 0.62), (0.90, 0.62)]),
        ('line', [(0.10, 0.86), (0.90, 0.86)]),
        ('line', [(0.28, 0.36), (0.10, 0.50), (0.28, 0.64)]),
    ],
    # Link and unlink: two rings of a chain, joined or pulled apart. Rings
    # rather than the interlocking ovals the emoji uses, because at 20
    # pixels two overlapping outlines become one grey blob - the bar between
    # them, and its absence, is what carries the difference.
    'link': [
        ('ellipse', [(0.06, 0.34), (0.44, 0.66)]),
        ('ellipse', [(0.56, 0.34), (0.94, 0.66)]),
        ('line', [(0.40, 0.50), (0.60, 0.50)]),
    ],
    'unlink': [
        ('ellipse', [(0.02, 0.34), (0.38, 0.66)]),
        ('ellipse', [(0.62, 0.34), (0.98, 0.66)]),
        ('line', [(0.36, 0.50), (0.44, 0.50)]),
        ('line', [(0.56, 0.50), (0.64, 0.50)]),
        # The snap: a mark above the gap and one below it
        ('line', [(0.50, 0.14), (0.50, 0.28)]),
        ('line', [(0.50, 0.72), (0.50, 0.86)]),
    ],
    # Following the desktop again: two arrows chasing each other
    # round a circle. Arcs are polylines here because the drawing
    # primitives have no curve - twelve segments over 150 degrees
    # is smooth at the size a toolbar draws.
    'sync': [
        ('line', [(0.65, 0.24), (0.59, 0.214), (0.526, 0.201), (0.461, 0.203), (0.397, 0.218), (0.339, 0.247), (0.288, 0.288), (0.247, 0.339), (0.218, 0.397), (0.203, 0.461), (0.201, 0.526), (0.214, 0.59), (0.24, 0.65)]),
        ('line', [(0.091, 0.591), (0.24, 0.65), (0.299, 0.501)]),
        ('line', [(0.35, 0.76), (0.41, 0.786), (0.474, 0.799), (0.539, 0.797), (0.603, 0.782), (0.661, 0.753), (0.712, 0.712), (0.753, 0.661), (0.782, 0.603), (0.797, 0.539), (0.799, 0.474), (0.786, 0.41), (0.76, 0.35)]),
        ('line', [(0.909, 0.409), (0.76, 0.35), (0.701, 0.499)]),
    ],
    'task': [
        ('shape', [(0.12, 0.34), (0.88, 0.34), (0.88, 0.66), (0.12, 0.66)]),
        ('fill', [(0.12, 0.34), (0.46, 0.66)]),
    ],
    'subtask': [
        ('line', [(0.14, 0.18), (0.14, 0.62), (0.34, 0.62)]),
        ('shape', [(0.34, 0.44), (0.90, 0.44), (0.90, 0.78), (0.34, 0.78)]),
    ],
    'milestone': [
        ('shape', [(0.50, 0.12), (0.88, 0.50), (0.50, 0.88), (0.12, 0.50)]),
    ],
    # A phase brackets the deliverables under it, so it is drawn as the
    # stack of layers it is - the outermost thing in the plan.
    'phase': [
        ('shape', [(0.50, 0.08), (0.92, 0.30), (0.50, 0.52), (0.08, 0.30)]),
        ('line', [(0.08, 0.50), (0.50, 0.72), (0.92, 0.50)]),
        ('line', [(0.08, 0.68), (0.50, 0.90), (0.92, 0.68)]),
    ],
    # A deliverable is the thing handed over when its tasks are done: a box
    # with a tick on it, told apart from the plain rectangles by both.
    'deliverable': [
        ('shape', [(0.10, 0.26), (0.90, 0.26), (0.90, 0.88), (0.10, 0.88)]),
        ('line', [(0.10, 0.44), (0.90, 0.44)]),
        ('line', [(0.30, 0.64), (0.44, 0.78), (0.72, 0.54)]),
    ],
    # The critical path: three bars of a chart, the longest of them carrying
    # the chain forward. Drawn as the plan it measures rather than as a
    # warning triangle, which would say "something is wrong" instead of
    # "here is what cannot slip".
    'critical_path': [
        ('line', [(0.10, 0.20), (0.44, 0.20)]),
        ('line', [(0.10, 0.50), (0.64, 0.50)]),
        ('line', [(0.10, 0.80), (0.38, 0.80)]),
        ('line', [(0.66, 0.32), (0.88, 0.50), (0.66, 0.68)]),
    ],
    'cut': [
        ('line', [(0.24, 0.14), (0.72, 0.72)]),
        ('line', [(0.76, 0.14), (0.28, 0.72)]),
        ('ellipse', [(0.14, 0.68), (0.36, 0.90)]),
        ('ellipse', [(0.64, 0.68), (0.86, 0.90)]),
    ],
    'copy': [
        ('shape', [(0.12, 0.12), (0.62, 0.12), (0.62, 0.62), (0.12, 0.62)]),
        ('shape', [(0.38, 0.38), (0.88, 0.38), (0.88, 0.88), (0.38, 0.88)]),
    ],
    'paste': [
        ('shape', [(0.18, 0.18), (0.82, 0.18), (0.82, 0.90), (0.18, 0.90)]),
        ('shape', [(0.36, 0.08), (0.64, 0.08), (0.64, 0.26), (0.36, 0.26)]),
        ('line', [(0.34, 0.50), (0.66, 0.50)]),
        ('line', [(0.34, 0.68), (0.66, 0.68)]),
    ],
    'delete': [
        ('line', [(0.14, 0.26), (0.86, 0.26)]),
        ('shape', [(0.24, 0.26), (0.76, 0.26), (0.70, 0.90), (0.30, 0.90)]),
        ('line', [(0.40, 0.14), (0.60, 0.14)]),
        ('line', [(0.44, 0.44), (0.44, 0.74)]),
        ('line', [(0.56, 0.44), (0.56, 0.74)]),
    ],
    # Help: a question mark. Drawn as a hook, a stem and a dot rather than
    # set as the character '?', so it keeps the weight of the rest of the row
    # and does not depend on which font Tk picks for a button.
    'help': [
        ('line', [(0.30, 0.34), (0.33, 0.23), (0.42, 0.16), (0.55, 0.15),
                  (0.66, 0.21), (0.71, 0.32), (0.68, 0.43), (0.58, 0.50),
                  (0.50, 0.57), (0.50, 0.66)]),
        ('disc', [(0.43, 0.76), (0.57, 0.90)]),
    ],
    # Day: a disc with eight rays. Drawn rather than set as an emoji so it
    # matches the weight of every other icon on the bar, and so it renders
    # the same on a machine with no colour emoji font - which is most Linux
    # desktops, where the emoji comes out as a dotted box.
    'sun': [
        ('disc', [(0.34, 0.34), (0.66, 0.66)]),
        ('line', [(0.50, 0.06), (0.50, 0.18)]),
        ('line', [(0.50, 0.82), (0.50, 0.94)]),
        ('line', [(0.06, 0.50), (0.18, 0.50)]),
        ('line', [(0.82, 0.50), (0.94, 0.50)]),
        ('line', [(0.19, 0.19), (0.28, 0.28)]),
        ('line', [(0.72, 0.72), (0.81, 0.81)]),
        ('line', [(0.81, 0.19), (0.72, 0.28)]),
        ('line', [(0.28, 0.72), (0.19, 0.81)]),
    ],
    # Night: a disc with a second one taken out of it, which is the only way
    # to get a crescent with a filled shape and no arc primitive. The bite is
    # offset up and right so the crescent opens down and left, the way a
    # waxing moon is drawn everywhere.
    'moon': [
        ('disc', [(0.12, 0.12), (0.88, 0.88)]),
        ('erase', [(0.34, 0.00), (1.10, 0.76)]),
    ],
    'undo': [
        ('line', [(0.14, 0.38), (0.60, 0.38), (0.74, 0.50),
                  (0.74, 0.64), (0.60, 0.76), (0.30, 0.76)]),
        ('line', [(0.32, 0.20), (0.14, 0.38), (0.32, 0.56)]),
    ],
    'redo': [
        ('line', [(0.86, 0.38), (0.40, 0.38), (0.26, 0.50),
                  (0.26, 0.64), (0.40, 0.76), (0.70, 0.76)]),
        ('line', [(0.68, 0.20), (0.86, 0.38), (0.68, 0.56)]),
    ],
}

#: Drawings already made, by (icon, size, colour).
#: Every icon this module can draw.
#:
#: Taken from the drawings rather than kept as a list of its own, because
#: the drawings are what the toolbar paints: a name in here that nothing can
#: draw would be a button showing a letter, which is the failure this is
#: worth checking for. There were two further registries - an emoji per icon
#: and an SVG path per icon, both complete, both carefully kept in step, and
#: neither reachable from the application. Adding an icon meant editing
#: three dictionaries and only one of them changed anything on screen.
ICON_NAMES: List[str] = list(ICON_STROKES.keys())


_DRAWN: Dict[tuple, Image.Image] = {}


def draw_icon(name: str, size: int = 20,
              color: Tuple[int, int, int] = (28, 29, 31)) -> Optional[Image.Image]:
    """
    Paint one toolbar icon.

    PARAMETERS:
    -----------
    name : str
        One of ICON_STROKES.
    size : int
        The width and height to paint it at, in pixels.
    color : tuple
        The stroke colour, as RGB.

    RETURNS:
    --------
    Optional[Image.Image]
        The icon on a transparent square, or None for a name with no
        strokes defined - the caller falls back to a letter.
    """
    strokes = ICON_STROKES.get(name)
    if not strokes:
        return None

    key = (name, size, color)
    if key in _DRAWN:
        return _DRAWN[key]

    scale = 4
    edge = size * scale
    image = Image.new('RGBA', (edge, edge), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    width = max(1, round(size * scale / 12))
    ink = (*color, 255)

    def points(pairs):
        """Unit-square points at the size being drawn."""
        return [(x * edge, y * edge) for x, y in pairs]

    for kind, pairs in strokes:
        placed = points(pairs)
        if kind == 'line':
            draw.line(placed, fill=ink, width=width, joint='curve')
        elif kind == 'shape':
            draw.line(placed + [placed[0]], fill=ink, width=width,
                      joint='curve')
        elif kind == 'ellipse':
            draw.ellipse([placed[0], placed[1]], outline=ink, width=width)
        elif kind == 'fill':
            draw.rectangle([placed[0], placed[1]], fill=ink)
        elif kind == 'disc':
            draw.ellipse([placed[0], placed[1]], fill=ink)
        elif kind == 'erase':
            # Written, not composited: ImageDraw sets the pixels it covers,
            # so a fully transparent fill takes a bite out of what is already
            # there. That is what turns a disc into a crescent.
            draw.ellipse([placed[0], placed[1]], fill=(0, 0, 0, 0))

    icon = image.resize((size, size), Image.LANCZOS)
    _DRAWN[key] = icon
    return icon
