"""
Making a dialog modal without breaking it.

WHY THIS MODULE EXISTS:
======================
Calling grab_set() on a Toplevel that has not been mapped yet fails on X11
with "grab failed: window not viewable". Every dialog in this application
called it directly in __init__, so on Linux the exception aborted the
constructor before the form was built and the user was left looking at an
empty window with no explanation.

A second problem lives here too. A grab is *exclusive*: while a dialog holds
one, every click goes to it and to the widgets inside it, and a popup opened
on top - a colour palette, a calendar - is a separate window rather than a
child, so it receives nothing at all. Its buttons look normal and do nothing.
take_grab is the fix: the popup takes the grab for as long as it is up and
hands it back to whatever held it before.

DEVELOPMENT NOTES:
------------------
The window has to be visible before it can take a grab, and how long that
takes is up to the window manager. So the grab is retried on the event loop
until it succeeds or the attempts run out, and a dialog that never manages it
simply stays non-modal rather than failing to open.
"""

import tkinter as tk

from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


#: How many times to retry, and how long to wait between attempts (ms).
MAX_ATTEMPTS = 25
RETRY_DELAY_MS = 40


def grab_when_visible(window: tk.Misc, attempt: int = 0) -> None:
    """
    Make a dialog modal as soon as the window manager has mapped it.

    PARAMETERS:
    -----------
    window : tk.Misc
        The Toplevel to grab input for.
    attempt : int
        Retry counter; callers leave this at its default.

    DEVELOPMENT NOTES:
    ------------------
    Never raises. Modality is a nicety - losing it is far better than losing
    the dialog, which is what happened when grab_set() was called too early.
    """
    try:
        if not window.winfo_exists():
            return
    except tk.TclError:
        return

    try:
        if window.winfo_viewable():
            window.grab_set()
            return
    except tk.TclError as error:
        # Still not viewable, or the window manager refused for now
        logger.debug("Deferring grab for %s: %s", window, error)

    if attempt >= MAX_ATTEMPTS:
        logger.info("Dialog stayed non-modal; the window never became grabbable")
        return

    try:
        window.after(RETRY_DELAY_MS, grab_when_visible, window, attempt + 1)
    except tk.TclError:
        pass


def take_grab(window: tk.Misc) -> None:
    """
    Give a popup the input grab, and hand it back when the popup closes.

    PARAMETERS:
    -----------
    window : tk.Misc
        The Toplevel being opened over a dialog that already holds a grab.

    DEVELOPMENT NOTES:
    ------------------
    A grab is exclusive. A dialog that has one receives every click in the
    application, and a popup opened on top of it is a separate window rather
    than one of its children - so the popup gets nothing. Its buttons draw
    normally, its swatches highlight on hover, and not one of them responds.
    That is what a colour palette opened from the task form was doing: no
    colour could be picked and Close did not close.

    So the popup takes the grab, and the window that had it gets it back when
    the popup goes - otherwise the dialog underneath is left non-modal, which
    is the same bug one level up.

    <Destroy> fires for every widget inside the window as well as for the
    window itself, so the handler checks which it was given. Restoring on a
    child's teardown would hand the grab back while the popup was still up.
    """
    try:
        previous = window.grab_current()
    except tk.TclError:
        previous = None

    grab_when_visible(window)

    def restore(event=None):
        """Release this window's grab and give the previous one its back."""
        if event is not None and event.widget is not window:
            return                      # a child of the popup, not the popup

        try:
            window.grab_release()
        except tk.TclError:
            pass

        if previous is None:
            return
        try:
            if previous.winfo_exists():
                grab_when_visible(previous)
        except tk.TclError:
            logger.debug("The window that held the grab has gone")

    window.bind('<Destroy>', restore, add='+')
