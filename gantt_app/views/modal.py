"""
Making a dialog modal without breaking it.

WHY THIS MODULE EXISTS:
======================
Calling grab_set() on a Toplevel that has not been mapped yet fails on X11
with "grab failed: window not viewable". Every dialog in this application
called it directly in __init__, so on Linux the exception aborted the
constructor before the form was built and the user was left looking at an
empty window with no explanation.

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
