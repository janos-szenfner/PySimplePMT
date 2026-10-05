"""
A drawing surface a Tk canvas and a Pillow image can both stand behind.

WHY THIS MODULE EXISTS:
======================
The dashboard and the timeline are drawn twice over: once onto the Tk
canvas that shows them, and once into a Pillow image when they are
exported to PNG or PDF. Writing each panel's drawing twice would mean
two implementations that drift apart the day one of them is edited, so
the panels draw against a pen instead - a small set of primitives both
backends honour. What a panel looks like on screen is exactly what the
exported file shows, because the same lines of code drew both.

DEVELOPMENT NOTES:
------------------
The pen speaks in canvas terms - coordinates in points, Tk's compass
anchors, angles the way Tk's arc takes them (degrees, counterclockwise
from 3 o'clock). ImagePen translates: Pillow's arc angles run clockwise
from 3 o'clock, its text anchors are two-letter codes, and it has no
dashed line at all, so dashes are split into segments here.

ImagePen renders at a supersampling scale and the caller downsizes the
result once - thin lines and small text come out antialiased rather
than stepped, the same trick chart_render.render_image uses.
"""

import math
from typing import List, Tuple

from gantt_app.utils.log import get_logger

logger = get_logger(__name__)

#: Canvas compass anchor -> Pillow two-letter anchor.
_PIL_ANCHORS = {
    'center': 'mm', 'c': 'mm',
    'n': 'mt', 's': 'mb', 'w': 'lm', 'e': 'rm',
    'nw': 'lt', 'ne': 'rt', 'sw': 'lb', 'se': 'rb',
}


def _points(coords) -> List[Tuple[float, float]]:
    """Flatten (x0, y0, x1, y1, ...) into [(x0, y0), ...]."""
    it = iter(coords)
    return list(zip(it, it))


class BasePen:
    """
    What a drawing gets: the primitives both backends honour.

    All measurements are in logical pixels - ImagePen scales them
    internally, so a panel never knows it is being exported.
    """

    # -- the drawing calls --------------------------------------------------

    def rect(self, x0, y0, x1, y1, fill=None, outline=None,
             width=1, dash=None):
        raise NotImplementedError

    def round_rect(self, x0, y0, x1, y1, radius=8, fill=None,
                   outline=None, width=1):
        raise NotImplementedError

    def line(self, coords, fill, width=1, dash=None):
        """A polyline; coords is a flat (x0, y0, x1, y1, ...) sequence."""
        raise NotImplementedError

    def oval(self, x0, y0, x1, y1, fill=None, outline=None, width=1):
        raise NotImplementedError

    def arc(self, x0, y0, x1, y1, start, extent, outline, width=1):
        """An unfilled arc: Tk's angles - degrees CCW from 3 o'clock."""
        raise NotImplementedError

    def wedge(self, x0, y0, x1, y1, start, extent, fill, outline=None):
        """A filled pie slice; angles as arc()."""
        raise NotImplementedError

    def polygon(self, coords, fill=None, outline=None, width=1):
        raise NotImplementedError

    def text(self, x, y, content, fill, size=10, bold=False,
             italic=False, anchor='center', angle=0):
        raise NotImplementedError

    # -- measuring ----------------------------------------------------------

    def text_width(self, content, size=10, bold=False,
                   italic=False) -> float:
        """How wide a string draws at that size - for clipping to fit."""
        raise NotImplementedError


class CanvasPen(BasePen):
    """The pen that puts the drawing on the screen."""

    def __init__(self, canvas):
        self.canvas = canvas
        self._tk_fonts = {}

    def rect(self, x0, y0, x1, y1, fill=None, outline=None,
             width=1, dash=None):
        self.canvas.create_rectangle(
            x0, y0, x1, y1, fill=fill or '', outline=outline or '',
            width=width, dash=dash)

    def round_rect(self, x0, y0, x1, y1, radius=8, fill=None,
                   outline=None, width=1):
        # Tk has no rounded rectangle; a smoothed polygon tracing the
        # rounded outline is how it is drawn. Corner samples land a
        # little inside the radius so the smoothing has room.
        radius = min(radius, (x1 - x0) / 2, (y1 - y0) / 2)
        if radius <= 0:
            self.rect(x0, y0, x1, y1, fill=fill, outline=outline,
                      width=width)
            return
        pts = []
        for cx, cy, start in (
                (x1 - radius, y0 + radius, 0),
                (x1 - radius, y1 - radius, 270),
                (x0 + radius, y1 - radius, 180),
                (x0 + radius, y0 + radius, 90)):
            for step in range(5):
                angle = math.radians(start - step * 90 / 4)
                pts.extend((cx + radius * math.cos(angle),
                            cy - radius * math.sin(angle)))
        self.canvas.create_polygon(
            pts, fill=fill or '', outline=outline or '',
            width=width, smooth=True, splinesteps=24)

    def line(self, coords, fill, width=1, dash=None):
        self.canvas.create_line(*coords, fill=fill, width=width,
                                dash=dash)

    def oval(self, x0, y0, x1, y1, fill=None, outline=None, width=1):
        self.canvas.create_oval(x0, y0, x1, y1, fill=fill or '',
                                outline=outline or '', width=width)

    def arc(self, x0, y0, x1, y1, start, extent, outline, width=1):
        import tkinter as tk
        self.canvas.create_arc(x0, y0, x1, y1, start=start,
                               extent=extent, style=tk.ARC,
                               outline=outline, width=max(1, int(width)))

    def wedge(self, x0, y0, x1, y1, start, extent, fill, outline=None):
        import tkinter as tk
        self.canvas.create_arc(x0, y0, x1, y1, start=start,
                               extent=extent, style=tk.PIESLICE,
                               fill=fill or '', outline=outline or '')

    def polygon(self, coords, fill=None, outline=None, width=1):
        self.canvas.create_polygon(coords, fill=fill or '',
                                   outline=outline or '', width=width)

    def _font(self, size, bold, italic):
        weight = 'bold' if bold else 'normal'
        slant = 'italic' if italic else 'roman'
        return ('TkDefaultFont', int(size), weight, slant)

    def text(self, x, y, content, fill, size=10, bold=False,
             italic=False, anchor='center', angle=0):
        import tkinter as tk
        kwargs = dict(text=content, fill=fill, anchor=anchor,
                      font=self._font(size, bold, italic))
        if angle:
            # angle= is Tk 8.6; the Tk that ships with older macOS is
            # 8.5 and raises TclError - the flat label is what it gets,
            # which is what the dashboard's angled labels already did.
            try:
                self.canvas.create_text(x, y, angle=angle, **kwargs)
                return
            except tk.TclError:
                pass
        self.canvas.create_text(x, y, **kwargs)

    def text_width(self, content, size=10, bold=False,
                   italic=False) -> float:
        try:
            import tkinter.font as tkfont
            key = (int(size), bool(bold), bool(italic))
            font = self._tk_fonts.get(key)
            if font is None:
                font = tkfont.Font(font=self._font(size, bold, italic))
                self._tk_fonts[key] = font
            return font.measure(str(content))
        except Exception:
            # No interpreter or no font - an estimate is better than a
            # failure for something that is only used to clip labels.
            logger.debug("Could not measure %r at size %s; estimating its "
                         "width", content, size)
            return len(str(content)) * size * 0.6


class ImagePen(BasePen):
    """
    The pen that draws into a Pillow image, for PNG and PDF export.

    PARAMETERS:
    -----------
    image : PIL.Image.Image
        The image the pen draws into - kept as well as its drawing
        context, because rotated text pastes a prepared patch onto it.
    scale : float
        The supersampling factor the image was created at. Every
        coordinate and size is multiplied by it, so callers work in the
        pixels the exported image will be shown at, not the bigger
        intermediate ones.
    """

    def __init__(self, image, scale: float = 1.0):
        from PIL import ImageDraw

        self.image = image
        self.draw = ImageDraw.Draw(image, 'RGBA')
        self.scale = scale
        self._fonts = {}

    def _s(self, value) -> float:
        return value * self.scale

    def _font(self, size, bold=False, italic=False):
        from gantt_app.utils.chart_render import _font as load_font

        scaled = max(1, int(round(size * self.scale)))
        key = scaled
        font = self._fonts.get(key)
        if font is None:
            font = load_font(scaled)
            self._fonts[key] = font
        return font

    def rect(self, x0, y0, x1, y1, fill=None, outline=None,
             width=1, dash=None):
        s = self._s
        if dash and (outline or fill):
            # A dashed fill has no meaning; the outline gets the dash.
            if fill:
                self.draw.rectangle([s(x0), s(y0), s(x1), s(y1)],
                                    fill=fill)
            self._dashed_border(x0, y0, x1, y1, outline, width, dash)
            return
        self.draw.rectangle([s(x0), s(y0), s(x1), s(y1)], fill=fill,
                            outline=outline,
                            width=max(1, int(s(width))))

    def _dashed_border(self, x0, y0, x1, y1, colour, width, dash):
        for x0_, y0_, x1_, y1_ in (
                (x0, y0, x1, y0), (x1, y0, x1, y1),
                (x1, y1, x0, y1), (x0, y1, x0, y0)):
            self._dashed_line([(x0_, y0_), (x1_, y1_)], colour, width,
                              dash)

    def round_rect(self, x0, y0, x1, y1, radius=8, fill=None,
                   outline=None, width=1):
        s = self._s
        self.draw.rounded_rectangle(
            [s(x0), s(y0), s(x1), s(y1)], radius=s(radius), fill=fill,
            outline=outline, width=max(1, int(s(width))))

    def line(self, coords, fill, width=1, dash=None):
        points = _points(coords)
        if dash:
            self._dashed_line(points, fill, width, dash)
            return
        self.draw.line([(self._s(x), self._s(y)) for x, y in points],
                       fill=fill, width=max(1, int(self._s(width))))

    def _dashed_line(self, points, colour, width, dash):
        """
        A dashed polyline, drawn as the on-segments only.

        Pillow's line takes no dash, so the pattern - a (on, off) pair in
        logical pixels - is walked along each segment and the gaps are
        simply not drawn.
        """
        on, off = dash[0], dash[1] if len(dash) > 1 else dash[0]
        step = (on + off) or 1
        thick = max(1, int(self._s(width)))
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            length = math.hypot(x1 - x0, y1 - y0)
            if length <= 0:
                continue
            ux, uy = (x1 - x0) / length, (y1 - y0) / length
            mark = 0.0
            while mark < length:
                end = min(mark + on, length)
                self.draw.line(
                    [self._s(x0 + ux * mark), self._s(y0 + uy * mark),
                     self._s(x0 + ux * end), self._s(y0 + uy * end)],
                    fill=colour, width=thick)
                mark += step

    def oval(self, x0, y0, x1, y1, fill=None, outline=None, width=1):
        s = self._s
        self.draw.ellipse([s(x0), s(y0), s(x1), s(y1)], fill=fill,
                          outline=outline, width=max(1, int(s(width))))

    @staticmethod
    def _pil_angles(start, extent) -> Tuple[float, float]:
        """
        Tk's (start, extent) - degrees CCW from 3 o'clock - as Pillow's
        clockwise (start, end) pair.
        """
        if extent >= 0:
            a, b = -(start + extent), -start
        else:
            a, b = -start, -(start + extent)
        a, b = a % 360, b % 360
        if b <= a:
            b += 360
        return a, b

    def arc(self, x0, y0, x1, y1, start, extent, outline, width=1):
        s = self._s
        a, b = self._pil_angles(start, extent)
        self.draw.arc([s(x0), s(y0), s(x1), s(y1)], a, b, fill=outline,
                      width=max(1, int(s(width))))

    def wedge(self, x0, y0, x1, y1, start, extent, fill, outline=None):
        s = self._s
        a, b = self._pil_angles(start, extent)
        self.draw.pieslice([s(x0), s(y0), s(x1), s(y1)], a, b, fill=fill,
                           outline=outline)

    def polygon(self, coords, fill=None, outline=None, width=1):
        s = self._s
        self.draw.polygon([(s(x), s(y)) for x, y in _points(coords)],
                          fill=fill)
        if outline:
            pts = [(s(x), s(y)) for x, y in _points(coords)]
            self.draw.line(pts + [pts[0]], fill=outline,
                           width=max(1, int(s(width))))

    def text(self, x, y, content, fill, size=10, bold=False,
             italic=False, anchor='center', angle=0):
        font = self._font(size, bold)
        pil_anchor = _PIL_ANCHORS.get(anchor, 'mm')
        if angle:
            self._angled_text(x, y, content, font, fill, pil_anchor,
                              angle)
            return
        self.draw.text((self._s(x), self._s(y)), str(content),
                       font=font, fill=fill, anchor=pil_anchor)
        if bold:
            # The system face has no separate bold file loaded, so bold
            # is drawn twice with a one-pixel offset - heavier where it
            # matters, honest everywhere.
            self.draw.text((self._s(x) + 1, self._s(y)), str(content),
                           font=font, fill=fill, anchor=pil_anchor)

    def _angled_text(self, x, y, content, font, fill, anchor, angle):
        """
        Rotated text: drawn flat on a clear patch, turned, pasted.

        The rotation is about the patch's centre, which lands the text
        close enough to the anchor point for the labels it is used for
        (angled axis labels anchor near their corner).
        """
        from PIL import Image, ImageDraw

        content = str(content)
        width = max(4, int(math.ceil(
            font.getlength(content) if hasattr(font, 'getlength')
            else len(content) * 10)))
        height = max(4, int(math.ceil(
            getattr(font, 'size', 12) * 1.4)))
        patch = Image.new('RGBA', (width + 8, height + 8), (0, 0, 0, 0))
        ImageDraw.Draw(patch).text((4, 4), content, font=font,
                                   fill=fill)
        # Pillow rotates counterclockwise too, matching Tk's angle.
        turned = patch.rotate(angle, expand=True,
                              resample=Image.BICUBIC)
        px = int(self._s(x) - turned.width / 2)
        py = int(self._s(y) - turned.height / 2)
        self.image.paste(turned, (px, py), turned)

    def text_width(self, content, size=10, bold=False,
                   italic=False) -> float:
        font = self._font(size, bold)
        try:
            return font.getlength(str(content)) / self.scale
        except AttributeError:
            logger.debug("Could not measure %r at size %s; estimating its "
                         "width", content, size)
            return len(str(content)) * size * 0.6
