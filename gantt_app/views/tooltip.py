"""
Hover text: what a button does, said when somebody looks at it.

WHY THIS MODULE EXISTS:
======================
A row of icons is only readable to whoever drew it. The captions were already
written - every entry in IconToolbar.ICON_ACTIONS carries one - but they were
stored on the button as an attribute and never shown, so the row said nothing
to anyone who had not learnt it. This is the part that puts them on screen.

DEVELOPMENT NOTES:
------------------
A borderless Toplevel rather than anything CustomTkinter offers, because
CustomTkinter has no tooltip and a frame inside the window cannot hang past
the edge of the toolbar it belongs to.

The pointer is never over a CTkButton itself: it is a frame holding a canvas
and a label, and one of those is what the mouse is on. Binding the button
still works, because CTkButton.bind forwards to exactly those children rather
than binding the frame - which is worth knowing before adding a walk over
winfo_children() here, as that binds the canvas a second time and runs every
handler twice.
"""

import tkinter as tk
import weakref
from typing import Optional

from gantt_app import theme
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


#: How long the pointer rests before the text appears, in milliseconds.
#:
#: Long enough that crossing the row on the way somewhere else stays quiet,
#: short enough that stopping on a button feels answered rather than delayed.
DELAY_MS = 450

#: How far below the widget the text sits, in pixels.
OFFSET_Y = 6

#: Padding inside the tooltip.
PAD_X, PAD_Y = 8, 4


#: How many things are currently asking for hover text to be held back.
#:
#: A count rather than a flag: a submenu is open while its parent is, and
#: both ask, so the first one to close must not let tooltips through again
#: while the other is still showing.
_HELD_BACK = 0

#: Every tooltip that exists, weakly, so held_back can take down whichever
#: of them happens to be on screen. Weak, because a tooltip belongs to the
#: widget it decorates and must not be kept alive by this.
_LIVE = weakref.WeakSet()


def hold_back() -> None:
    """
    Stop hover text appearing, and take down anything already showing.

    DEVELOPMENT NOTES:
    ------------------
    Menus ask for this while they are open. Hover text is scheduled on a
    delay and shown by a timer, so a tooltip started by the pointer passing
    over a toolbar button on its way to a menu arrived after the menu had
    opened - and drew itself over the menu, being an always-on-top window
    like the menu is. What the reader saw was "Bold  (CmdB)" written across
    the entries of the Actions menu.

    Holding them back rather than destroying them, because the pointer is
    still over whatever it was over; the tooltip should come back when the
    menu goes, if the pointer is still resting there.
    """
    global _HELD_BACK
    _HELD_BACK += 1
    for tip in list(_LIVE):
        try:
            tip.hide_for_now()
        except Exception:
            logger.debug("Could not take down a tooltip")


def let_through() -> None:
    """Allow hover text again, once nothing is asking otherwise."""
    global _HELD_BACK
    _HELD_BACK = max(0, _HELD_BACK - 1)


def held_back() -> bool:
    """Whether hover text is currently being kept off the screen."""
    return _HELD_BACK > 0


class Tooltip:
    """
    One line of hover text attached to one widget.

    PARAMETERS:
    -----------
    widget : tkinter widget
        What the pointer has to rest on.
    text : str
        What to say. An empty string attaches nothing, so a caller may pass
        whatever a table gave it without checking first.

    DEVELOPMENT NOTES:
    ------------------
    The window is built when it is first needed and destroyed when it hides,
    rather than being kept hidden between times. A kept window has to be
    followed through every appearance change and every move of the parent,
    and there is no saving worth that: building it takes a few milliseconds
    once every time somebody pauses on a button.
    """

    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = str(text or '')
        self.window: Optional[tk.Toplevel] = None
        self._after_id = None
        _LIVE.add(self)

        if not self.text:
            return

        self._bind(widget)

    def _bind(self, widget):
        """
        Listen for the pointer arriving at and leaving the widget.

        DEVELOPMENT NOTES:
        ------------------
        Bound on the widget alone; see the note on the module for why that
        reaches the canvas the pointer is actually over.

        <ButtonPress> takes the caption away as well. A button that opens
        something - the day/night control, the Log window - would otherwise
        leave its hover text sitting over whatever it just opened.
        """
        widget.bind('<Enter>', self._on_enter, add='+')
        widget.bind('<Leave>', self._on_leave, add='+')
        widget.bind('<ButtonPress>', self._on_leave, add='+')
        widget.bind('<Destroy>', self._on_leave, add='+')

    def set_text(self, text: str) -> None:
        """
        Change what the hover text says.

        DEVELOPMENT NOTES:
        ------------------
        Here so that a button whose caption changes - the day/night control,
        which says whichever mode it is in - can be kept up to date without
        a second Tooltip being attached to it. Attaching again would bind
        <Enter> a second time with add='+', and the button would gain another
        binding every time the mode was toggled.
        """
        self.text = str(text or '')
        if not self.text:
            self._on_leave()

    def hide_for_now(self) -> None:
        """Take the text off screen and forget any that was on its way."""
        self._cancel()
        self._hide()

    def _on_enter(self, _event=None):
        """Start the clock; the text appears if the pointer stays."""
        self._cancel()
        if held_back():
            return
        try:
            self._after_id = self.widget.after(DELAY_MS, self._show)
        except tk.TclError:
            self._after_id = None

    def _on_leave(self, _event=None):
        """Take it away, whether it had appeared yet or not."""
        self._cancel()
        self._hide()

    def _cancel(self):
        """Stop a tooltip that has been scheduled but not yet shown."""
        if self._after_id is None:
            return
        try:
            self.widget.after_cancel(self._after_id)
        except tk.TclError:
            pass
        self._after_id = None

    def _show(self):
        """Put the text on screen just below the widget."""
        self._after_id = None
        if self.window is not None or not self.text:
            return
        # Asked again here as well as when the clock started: a menu can
        # open during the delay, which is exactly the case that put hover
        # text across an open menu
        if held_back():
            return

        try:
            if not self.widget.winfo_exists():
                return
            x = self.widget.winfo_rootx()
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + OFFSET_Y
        except tk.TclError:
            return

        appearance = theme.current_appearance()
        try:
            window = tk.Toplevel(self.widget)
            # No title bar, no border, and above the window it belongs to
            window.wm_overrideredirect(True)
            window.attributes('-topmost', True)
            window.configure(
                background=theme.resolve(theme.SEPARATOR, appearance))

            label = tk.Label(
                window, text=self.text,
                background=theme.resolve(theme.DROPDOWN_BG, appearance),
                foreground=theme.resolve(theme.TEXT, appearance),
                justify=tk.LEFT, padx=PAD_X, pady=PAD_Y,
            )
            # The one pixel of background showing round the label is the
            # border: a tooltip with no edge dissolves into whatever is
            # behind it, and Toplevel borders are not drawn without a frame
            label.pack(padx=1, pady=1)

            window.wm_geometry(f"+{x}+{y}")
            self.window = window
        except tk.TclError:
            # A window torn down mid-hover, which happens when a dialog
            # closes under the pointer. Nothing to show and nothing wrong.
            self._destroy_window()

    def _hide(self):
        """Take the text off screen."""
        self._destroy_window()

    def _destroy_window(self):
        """Destroy the tooltip window, if there is one."""
        window, self.window = self.window, None
        if window is None:
            return
        try:
            window.destroy()
        except tk.TclError:
            pass


def attach(widget, text: str) -> Optional[Tooltip]:
    """
    Give a widget hover text.

    PARAMETERS:
    -----------
    widget : tkinter widget
        What to attach it to.
    text : str
        What to say. Nothing is attached for an empty string.

    RETURNS:
    --------
    Optional[Tooltip]
        The tooltip, kept by the caller so it is not collected, or None when
        there was no text to show.

    DEVELOPMENT NOTES:
    ------------------
    A failure here must not cost the button it was decorating. Hover text is
    the least important thing on a toolbar, and a row that will not build
    because a tooltip raised would be a poor trade.
    """
    existing = getattr(widget, 'tooltip_widget', None)
    if isinstance(existing, Tooltip):
        # Attaching a second time would bind <Enter> again, and a button
        # whose caption is rebuilt on every change would gain a binding each
        # time; see Tooltip.set_text
        existing.set_text(text)
        return existing

    if not text:
        return None
    try:
        return Tooltip(widget, text)
    except Exception:
        logger.exception("Could not attach the hover text %r", text)
        return None
