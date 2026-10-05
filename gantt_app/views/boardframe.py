"""
The redraw-and-resize skeleton the canvas boards share.

WHY THIS MODULE EXISTS:
=======================
The dashboard and the timeline both need the same four things from Tk: a
canvas that asks its real size only after layout, a Configure that debounces
rather than redrawing on every stray pixel, a refresh() that repaints on
demand, and a redraw that skips a torn-down or too-small canvas. They each
carried a copy that could drift - the timeline's was written from the
dashboard's. Both call into BoardRedrawMixin now; each only supplies the
one thing that differs, which is what to draw into the cleared canvas.

A subclass provides:

  * ``self.canvas``     - the tk.Canvas (or a widget answering the same)
  * ``MIN_USEFUL_PX``   - the size under which a draw is skipped
  * ``_draw_content(width, height)`` - the content itself. (Not "_draw":
    CTkFrame already owns that name for its own paint engine.)
"""

import tkinter as tk

from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


class BoardRedrawMixin:
    """Resize debounce, refresh and size fallbacks for a canvas board."""

    def _on_configure(self, event=None):
        """A resize redraws - debounced, and not for a stray pixel."""
        if event is not None:
            if (abs(event.width - self._last_size[0]) < 4
                    and abs(event.height - self._last_size[1]) < 4):
                return
            self._last_size = (event.width, event.height)
        if self._redraw_pending:
            return
        self._redraw_pending = True
        self.after_idle(self._redraw_now)

    def refresh(self):
        """Repaint now - the plan changed, or the board's own state did."""
        self._redraw_pending = False
        self._redraw_now()

    def _size(self):
        """
        How big the canvas is to draw into.

        winfo_width answers 1 until Tk has laid the widget out, so two
        things stand in for it: the size the last Configure reported, and
        then the size the canvas was asked for. In the application the
        first of those is the real answer, and the second is what lets
        the drawing be checked without putting a window on somebody's
        screen, since Tk delivers no Configure to a widget that was
        never mapped.
        """
        width, height = (self.canvas.winfo_width(),
                         self.canvas.winfo_height())
        if width > 1 and height > 1:
            return width, height
        if self._last_size[0] > 1 and self._last_size[1] > 1:
            return self._last_size
        return (self.canvas.winfo_reqwidth(),
                self.canvas.winfo_reqheight())

    def _redraw_now(self):
        """Clear, measure and hand the pen over - unless the board is gone."""
        self._redraw_pending = False
        canvas = self.canvas
        try:
            if not canvas.winfo_exists():
                return
        except tk.TclError:
            return
        canvas.delete('all')
        width, height = self._size()
        if width < self.MIN_USEFUL_PX or height < self.MIN_USEFUL_PX:
            logger.debug("%s not drawn at %sx%s; too small",
                         type(self).__name__, width, height)
            self._on_too_small()
            return
        try:
            self._draw_content(width, height)
        except Exception:
            logger.exception("Could not draw the %s", type(self).__name__)

    def _on_too_small(self):
        """What to tidy when a draw is skipped for size; boards may override."""
