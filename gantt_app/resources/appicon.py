"""
The application's own icon and logo, loaded from a single image on disk.

WHY THIS MODULE EXISTS:
======================
The mark is now a designed image - the hexagonal "P / IT-Space" logo shipped
as ``logo_source.png`` beside this module - rather than geometry drawn in
code. One file feeds every place the brand appears: the window icon, the
macOS ``.icns``, the Linux desktop entry and ``.deb`` pixmaps, and the About
box. Because they all read the same source there is no way for the packaged
icon and the running one to drift apart.

The source is a landscape image on a white ground. Two shapes come out of it:

  * :func:`draw_icon` - a *square* tile for use as an application icon,
    centre-cropped to the logo, resized, and given rounded corners so it sits
    like an icon rather than a photograph in a title bar or a Dock.
  * :func:`logo_image` - the *full* logo at its natural aspect ratio, for the
    About window where the whole mark should read.

Losing the image must never stop the application: every entry point here
fails soft, returning ``None`` (or a blank tile) rather than raising, because
an icon is a nicety and a missing one is not worth an aborted launch.
"""

from pathlib import Path

from PIL import Image, ImageDraw

#: The designed logo, shipped beside this module and bundled into the package
#: (see packaging/pysimplepmt.spec, which adds it to the frozen build's
#: gantt_app/resources so Path(__file__) still finds it when frozen).
LOGO_PATH = Path(__file__).resolve().parent / 'logo_source.png'

#: How much of the icon tile's shorter side its corners are rounded by. The
#: white ground then reads as a rounded plate rather than a hard square.
CORNER_RADIUS = 0.18


def load_logo() -> Image.Image:
    """
    The source logo as an RGBA image.

    RETURNS:
    --------
    Image.Image
        The logo, converted to RGBA so callers can composite and mask it.

    RAISES:
    -------
    FileNotFoundError, OSError
        If the image is missing or unreadable. Callers that must not fail -
        window icon, About box - guard the call; the packaging scripts let it
        raise so a broken build fails loudly rather than shipping no icon.
    """
    return Image.open(LOGO_PATH).convert('RGBA')


def logo_image(width: int = None) -> Image.Image:
    """
    The full logo at its natural aspect ratio, optionally scaled to a width.

    PARAMETERS:
    -----------
    width : int, optional
        Target width in pixels. The height follows to preserve the aspect
        ratio. Left at None, the image comes back at its native size.

    RETURNS:
    --------
    Image.Image
        The RGBA logo. Used by the About window, which wants the whole mark
        rather than the cropped icon tile.
    """
    image = load_logo()
    if width and width != image.width:
        height = max(1, round(image.height * width / image.width))
        image = image.resize((width, height), Image.LANCZOS)
    return image


def _square_crop(image: Image.Image) -> Image.Image:
    """Centre-crop to a square on the shorter side, keeping the logo centred."""
    side = min(image.width, image.height)
    left = (image.width - side) // 2
    top = (image.height - side) // 2
    return image.crop((left, top, left + side, top + side))


def draw_icon(size: int = 256) -> Image.Image:
    """
    The application icon: a square, rounded tile cut from the logo.

    PARAMETERS:
    -----------
    size : int
        Width and height of the square icon in pixels.

    RETURNS:
    --------
    Image.Image
        The rendered RGBA image. On any failure to read the source a blank
        transparent tile of the requested size is returned, so a caller that
        saves or displays it still has a valid image to work with.

    DEVELOPMENT NOTES:
    ------------------
    Built four times larger and reduced with a high-quality filter: the corner
    rounding is a curve, and at the 16-32 pixels a title bar asks for, cutting
    it directly gives stair-steps rather than a clean edge.
    """
    scale = 4
    canvas = size * scale

    try:
        source = _square_crop(load_logo())
    except Exception:
        return Image.new('RGBA', (size, size), (0, 0, 0, 0))

    tile = source.resize((canvas, canvas), Image.LANCZOS)

    # The corners, cut once through the finished tile.
    mask = Image.new('L', (canvas, canvas), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [(0, 0), (canvas - 1, canvas - 1)],
        radius=int(canvas * CORNER_RADIUS), fill=255,
    )
    rounded = Image.new('RGBA', (canvas, canvas), (0, 0, 0, 0))
    rounded.paste(tile, (0, 0), mask)

    return rounded.resize((size, size), Image.LANCZOS)


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
