"""
The application's own icon, drawn rather than stored.

WHY THIS MODULE EXISTS:
======================
The icon is drawn from code so it stays reviewable in version control, so it
rebuilds identically on any machine, and so the window, the desktop entry and
the packaged build cannot drift apart - they all come from here. A committed
PNG would be a binary blob nobody can diff, and three of them would be three
things to remember to update.

Nothing is loaded from disk and no font file is needed: every stroke is a
geometric primitive, so the same script produces the same image everywhere.
That matters more than it sounds - text drawn through a system font would give
a different icon on every machine that built the package.

WHAT IS IN IT:
--------------
  * Python's own two blues and two yellows, in the diagonal split the
    language's logo is built on.
  * A Gantt chart: three staggered bars, a dependency link dropping from the
    first to the second, and a milestone diamond closing the last - which is
    the whole vocabulary of a project plan in four marks.
  * SZJ, the author's initials, set in the same bar language as the chart so
    the letters read as part of it rather than as a caption stuck underneath.

All of it is original geometry. Nothing is traced from another icon set, and
the palette is the Python Software Foundation's published logo colours, which
are free to use for work about Python.
"""

from PIL import Image, ImageDraw

#: Python's published logo colours.
BLUE_DARK = (48, 105, 152, 255)     # #306998
BLUE_LIGHT = (75, 139, 190, 255)    # #4B8BBE
YELLOW = (255, 212, 59, 255)        # #FFD43B
YELLOW_LIGHT = (255, 232, 115, 255)  # #FFE873
WHITE = (255, 255, 255, 255)
LINK = (255, 255, 255, 170)         # the dependency line, deliberately quiet

#: How much of the tile the artwork keeps clear of the edge.
MARGIN = 0.12

#: The three bars, as (left, right, top) in fractions of the tile.
#:
#: The second starts exactly where the first finishes, so the link between
#: them drops straight down - which is what a Finish-Start link looks like on
#: a real chart. The third overlaps them both, because a plan with no
#: parallel work in it is not a plan anybody recognises.
BARS = (
    (0.00, 0.44, 0.00),
    (0.44, 0.86, 0.20),
    (0.16, 0.60, 0.40),
)
BAR_HEIGHT = 0.14
BAR_COLOURS = (YELLOW, YELLOW_LIGHT, WHITE)

#: Where the letters sit, how big they are, and how thick their strokes are.
LETTER_TOP = 0.66
LETTER_HEIGHT = 0.34
LETTER_WIDTH = 0.21
LETTER_GAP = 0.065
LETTER_STROKE = 0.068


def _rounded(draw, box, radius, fill):
    """A rounded rectangle, clamped so a tiny bar cannot invert its corners."""
    left, top, right, bottom = box
    radius = max(0, min(radius, (right - left) / 2, (bottom - top) / 2))
    draw.rounded_rectangle([(left, top), (right, bottom)], radius=radius,
                           fill=fill)


def _background(draw, size):
    """
    The tile: dark Python blue, with the lighter blue cut across it.

    The diagonal is the one gesture that says Python without borrowing the
    logo itself - two tones meeting on a slant, the way the two snakes do.

    Drawn square. The corners are rounded once at the end, by masking the
    finished artwork, which is both simpler than rounding each layer and the
    only way the wedge can reach the edge without overhanging it.
    """
    draw.rectangle([(0, 0), (size, size)], fill=BLUE_DARK)
    draw.polygon([(0, 0), (size, 0), (0, size)], fill=BLUE_LIGHT)


def _chart(draw, size):
    """
    Three staggered bars, one dependency link, one milestone.

    Drawn in the order a plan is read: the bars first, then the line that
    says the second waits for the first, then the diamond that closes the
    last one out.
    """
    span = size * (1 - MARGIN * 2)
    left_edge = size * MARGIN
    top_edge = size * MARGIN
    height = span * BAR_HEIGHT
    radius = height / 2

    placed = []
    for (start, end, top), colour in zip(BARS, BAR_COLOURS):
        box = (left_edge + span * start, top_edge + span * top,
               left_edge + span * end, top_edge + span * top + height)
        _rounded(draw, box, radius, colour)
        placed.append(box)

    # The link: straight down from where the first bar finishes to where the
    # second one starts. They meet at the same x, so it is one clean drop -
    # which is exactly how a Finish-Start link is drawn on a real chart.
    first, second = placed[0], placed[1]
    draw.line([(first[2] - radius, first[3] + height * 0.1),
               (first[2] - radius, second[1] + height / 2)],
              fill=LINK, width=max(1, int(size * 0.020)))

    # The milestone, closing the last bar
    third = placed[2]
    centre_x = third[2] + span * 0.10
    centre_y = (third[1] + third[3]) / 2
    reach = height * 0.78
    draw.polygon([(centre_x, centre_y - reach), (centre_x + reach, centre_y),
                  (centre_x, centre_y + reach), (centre_x - reach, centre_y)],
                 fill=YELLOW)


def _letters(draw, size):
    """
    SZJ, in the same rounded-bar language as the chart above it.

    Built from strokes rather than from a font: a font would make the icon
    depend on what happens to be installed, and the whole point of drawing it
    is that it comes out the same everywhere.
    """
    span = size * (1 - MARGIN * 2)
    top = size * MARGIN + span * LETTER_TOP
    height = span * LETTER_HEIGHT
    width = span * LETTER_WIDTH
    gap = span * LETTER_GAP
    stroke = max(2, int(span * LETTER_STROKE))

    # Centred as a group, so the three read as a wordmark rather than as
    # three marks that happen to be in a row
    block = width * 3 + gap * 2
    left = size * MARGIN + (span - block) / 2
    inset = stroke / 2

    def stem(index):
        """The left edge of the nth letter."""
        return left + index * (width + gap)

    line = dict(fill=WHITE, width=stroke, joint='curve')

    # S - across the top, down the left, across the middle, down the right,
    # across the bottom: the letter as five runs of a single path
    x = stem(0)
    draw.line([(x + width - inset, top + inset),
               (x + inset, top + inset),
               (x + inset, top + height / 2),
               (x + width - inset, top + height / 2),
               (x + width - inset, top + height - inset),
               (x + inset, top + height - inset)], **line)

    # Z - across, down the diagonal, across again
    x = stem(1)
    draw.line([(x + inset, top + inset),
               (x + width - inset, top + inset),
               (x + inset, top + height - inset),
               (x + width - inset, top + height - inset)], **line)

    # J - down the stem, then the hook turning left at the foot
    x = stem(2)
    draw.line([(x + width - inset, top + inset),
               (x + width - inset, top + height - stroke),
               (x + width - stroke * 1.5, top + height - inset),
               (x + inset, top + height - inset)], **line)


def draw_icon(size: int = 256) -> Image.Image:
    """
    Draw the application icon.

    PARAMETERS:
    -----------
    size : int
        Width and height of the square icon in pixels.

    RETURNS:
    --------
    Image.Image
        The rendered RGBA image.

    DEVELOPMENT NOTES:
    ------------------
    Drawn four times larger and reduced with a high quality filter. Every
    edge here is a diagonal or a curve, and at 32 pixels - which is what a
    title bar asks for - drawing them directly gives stair-steps rather than
    an icon.
    """
    scale = 4
    canvas = size * scale

    tile = Image.new('RGBA', (canvas, canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(tile)
    _background(draw, canvas)
    _chart(draw, canvas)
    _letters(draw, canvas)

    # The corners, cut once through the finished artwork
    mask = Image.new('L', (canvas, canvas), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [(0, 0), (canvas - 1, canvas - 1)], radius=int(canvas * 0.22), fill=255
    )
    image = Image.new('RGBA', (canvas, canvas), (0, 0, 0, 0))
    image.paste(tile, (0, 0), mask)

    return image.resize((size, size), Image.LANCZOS)


def icon_photo(master, size: int = 64):
    """
    The icon as a Tk image, for a window to wear.

    PARAMETERS:
    -----------
    master : tkinter widget
        The window the image belongs to. A Tk image outlives nothing: it has
        to be created against a live interpreter and kept referenced.
    size : int
        Pixel size to draw at.

    RETURNS:
    --------
    Optional[tkinter.PhotoImage]
        The image, or None when it could not be built - an icon is a nicety
        and losing it must not stop the application starting.

    DEVELOPMENT NOTES:
    ------------------
    Encoded in memory and handed to Tk, rather than converted pixel by pixel
    into a PhotoImage - that takes over a second for a 64 pixel icon, on every
    start.

    PNG first, GIF second. Tk reads PNG from 8.6, which is what the packaged
    build and every current desktop ship; 8.5 does not, and the system Tk on
    some macOS installs is still 8.5. GIF has been readable since long before
    either, at the cost of a palette and a one-bit edge - a fair trade for an
    icon that would otherwise not appear at all.

    Tk wants binary image data base64 encoded, not raw.
    """
    import base64
    import io
    import tkinter as tk

    image = None
    try:
        image = draw_icon(size)
    except Exception:
        return None

    for image_format, options in (('PNG', {}), ('GIF', {'transparency': 0})):
        try:
            buffer = io.BytesIO()
            image.save(buffer, image_format, **options)
            encoded = base64.b64encode(buffer.getvalue()).decode('ascii')
            return tk.PhotoImage(master=master, data=encoded)
        except Exception:
            continue

    return None
