"""
A scrolling container for the task form.

WHY THIS MODULE EXISTS:
======================
CustomTkinter has CTkScrollableFrame, and the task form used it. Its
scrollbar ends every draw with

    self._canvas.update_idletasks()

which forces a full layout pass of the whole window, and its scrollbar is
drawn again on every step of the scroll. Turning the wheel over the form cost
3.2ms a notch against 0.11ms here - thirty times the work, on the one gesture
that arrives dozens at a time from a trackpad, and it is what made the form
feel heavy to move through.

Building one is not free either: a milestone dialog opens in 18ms against the
30ms it took, the difference being the flushes its scrollbar performs while
the window around it is still being built. The task and sub-task dialogs open
in about the same time as before - a CTkOptionMenu costs some 10ms on its own
here and is what their time now goes on.

A canvas with a frame inside it and a ttk scrollbar beside it is what a
scrolling frame is, and ttk's scrollbar is the platform's own: it draws
without flushing anything.

DEVELOPMENT NOTES:
------------------
This is the same trade the calendar popup makes in datepicker.py, where
thirty-one CTkButtons became thirty-one tk.Labels. Little of CustomTkinter's
appearance is lost either way: the scrollbar is the only part on show, and a
native one is what the rest of the application's scrolled areas already use.

The scrollbar is only gridded when there is something to scroll, so a form
that fits its window shows none - which is what a form that fits should look
like.
"""

import tkinter as tk
from tkinter import ttk

import customtkinter as ctk

from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


class ScrollFrame(ctk.CTkFrame):
    """
    A frame that scrolls vertically.

    PARAMETERS:
    -----------
    master : widget
        Parent widget.

    ATTRIBUTES:
    -----------
    content : ctk.CTkFrame
        What to put the widgets in. The ScrollFrame itself holds the canvas
        and the scrollbar, so gridding into it directly would land beside the
        scrolling area rather than inside it.

    DEVELOPMENT NOTES:
    ------------------
    The canvas scrolls in steps of SCROLL_STEP pixels. Left at Tk's default
    of 0 a wheel notch jumps a tenth of the window, which on a form this size
    is most of a field.
    """

    #: How far one notch of the wheel moves the form, in pixels.
    SCROLL_STEP = 20

    #: The wheel, as each platform reports it. X11 sends button presses;
    #: Windows and macOS send a delta.
    WHEEL_EVENTS = ('<MouseWheel>', '<Button-4>', '<Button-5>')

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color='transparent', **kwargs)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            self, highlightthickness=0, borderwidth=0,
            yscrollincrement=self.SCROLL_STEP,
            background=self._background_of(master),
        )
        self.canvas.grid(row=0, column=0, sticky=tk.NSEW)

        self.scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL,
                                       command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self._scrolled)

        self.content = ctk.CTkFrame(self.canvas, fg_color='transparent')
        self._window = self.canvas.create_window(
            (0, 0), window=self.content, anchor=tk.NW)
        self._scrollregion_pending = False

        self.content.bind('<Configure>', self._content_resized)
        self.canvas.bind('<Configure>', self._canvas_resized)
        self.bind('<Enter>', self._take_the_wheel)
        self.bind('<Leave>', self._let_go_of_the_wheel)

    def _background_of(self, master) -> str:
        """
        The colour to paint the canvas, so it disappears into its parent.

        A canvas has no notion of CustomTkinter's light and dark themes, so
        it is told what its parent is wearing; left alone it would show as a
        white rectangle behind the form on a dark desktop.
        """
        color = None
        try:
            color = master.cget('fg_color')
        except (AttributeError, ValueError, tk.TclError):
            pass
        if color is None or color == 'transparent':
            color = ctk.ThemeManager.theme['CTkFrame']['fg_color']
        return self._apply_appearance_mode(color)

    # ------------------------------------------------------------------
    # Keeping the canvas and its contents in step
    # ------------------------------------------------------------------

    def _content_resized(self, _event=None):
        """
        Let the canvas scroll over however tall the form has become.

        DEVELOPMENT NOTES:
        ------------------
        The work is put off to the idle moment after the burst of resizes
        that a form being built sets off, and only one is ever outstanding.
        Measuring the region means canvas.bbox, which settles the geometry of
        everything inside it, and doing that once per field added cost about
        three milliseconds of the time to open the editor for an answer that
        was wrong again by the next line.
        """
        if self._scrollregion_pending:
            return
        self._scrollregion_pending = True
        self.after_idle(self._update_scrollregion)

    def _update_scrollregion(self):
        """Measure the form and let the canvas scroll over all of it."""
        self._scrollregion_pending = False
        try:
            self.canvas.configure(scrollregion=self.canvas.bbox('all'))
        except tk.TclError:
            pass                        # torn down before the idle moment

    def _canvas_resized(self, event):
        """
        Keep the form as wide as the canvas.

        Without this the frame inside the canvas sits at its requested width,
        so a field set to stretch has nothing to stretch into.
        """
        self.canvas.itemconfigure(self._window, width=event.width)

    def _scrolled(self, first, last):
        """
        Move the scrollbar, and put it away when it has nothing to do.

        Called by the canvas rather than by us: this is its yscrollcommand,
        so it runs whenever what is on show changes, including when the form
        grows a row or the window is resized around it.
        """
        if float(first) <= 0.0 and float(last) >= 1.0:
            self.scrollbar.grid_remove()
        else:
            self.scrollbar.grid(row=0, column=1, sticky=tk.NS, padx=(4, 0))
        self.scrollbar.set(first, last)

    # ------------------------------------------------------------------
    # The wheel
    # ------------------------------------------------------------------

    def _take_the_wheel(self, _event=None):
        """
        Claim the wheel while the pointer is over the form.

        DEVELOPMENT NOTES:
        ------------------
        bind_all, because the pointer spends its time over the fields rather
        than over the canvas behind them, and an event goes to the widget
        under it. Claiming it only while the pointer is inside leaves the
        wheel to whatever else wants it - the chart has its own handling -
        the moment the pointer leaves.
        """
        for sequence in self.WHEEL_EVENTS:
            self.canvas.bind_all(sequence, self._wheel, add='+')

    def _let_go_of_the_wheel(self, _event=None):
        """
        Give the wheel back, unless the pointer only moved onto a field.

        Tk reports leaving for a child as leaving, so the pointer crossing
        onto a box inside the form arrives here as though it had left the
        form altogether. Where it actually is settles it.
        """
        if self._pointer_is_inside():
            return
        for sequence in self.WHEEL_EVENTS:
            try:
                self.canvas.unbind_all(sequence)
            except tk.TclError:
                pass

    def _pointer_is_inside(self) -> bool:
        """Whether the pointer is over this frame or anything inside it."""
        try:
            under = self.winfo_containing(*self.winfo_pointerxy())
        except tk.TclError:
            return False
        return under is not None and str(under).startswith(str(self))

    def _wheel(self, event):
        """
        Scroll the form by one notch.

        Deltas are read the way the chart reads them - see
        gantt_chart._bind_scrolling: X11 sends Button-4 and Button-5 with no
        delta, Windows sends multiples of 120, macOS sends small numbers.
        """
        if not self._scrollable():
            return None

        if event.delta:
            steps = -1 if event.delta > 0 else 1
            if abs(event.delta) >= 120:
                steps = int(-event.delta / 120)
        else:
            steps = -1 if event.num == 4 else 1

        self.canvas.yview_scroll(steps, 'units')
        return 'break'

    def _scrollable(self) -> bool:
        """Whether the form is taller than the window showing it."""
        try:
            return self.content.winfo_reqheight() > self.canvas.winfo_height()
        except tk.TclError:
            return False

    def destroy(self):
        """Give up the wheel on the way out."""
        for sequence in self.WHEEL_EVENTS:
            try:
                self.canvas.unbind_all(sequence)
            except tk.TclError:
                pass
        super().destroy()
