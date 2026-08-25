"""
Which modifier key a shortcut uses, and what to call it on screen.

WHY THIS MODULE EXISTS:
======================
Ctrl+B is Cmd+B on a Mac, and a Mac user pressing Ctrl+B gets nothing. The
application had its shortcuts written out as Control everywhere, which meant
every one of them was wrong on one of the three platforms it ships for.

Held in one place because the answer is needed twice for every shortcut and
the two must agree: the sequence Tk binds, and the text a menu or a tooltip
shows. Written separately they drift, and a caption promising a key that is
not bound is worse than no caption.

DEVELOPMENT NOTES:
------------------
Tk spells the Command key 'Command' and the Control key 'Control', and on
macOS it reports them separately - Control-B on a Mac really is Control, not
Command. So this is a genuine branch rather than an alias.

Both letter cases are bound for every shortcut. Tk reports the upper case one
when caps lock is on, and a shortcut that stops working with caps lock is the
kind of fault nobody reports and everybody notices.
"""

import sys

#: Whether this is a Mac. Read once; it cannot change while running.
IS_MACOS = sys.platform == 'darwin'

#: How Tk spells the modifier this platform uses for application shortcuts.
MODIFIER = 'Command' if IS_MACOS else 'Control'

#: How a person writing it down spells it.
MODIFIER_LABEL = '⌘' if IS_MACOS else 'Ctrl'


def accelerator(key: str) -> str:
    """
    How a shortcut is written for the reader.

    PARAMETERS:
    -----------
    key : str
        The key itself - 'B', 'Enter', 'Return'.

    RETURNS:
    --------
    str
        Cmd notation on a Mac and Ctrl notation elsewhere, so a caption says
        what the machine it is running on actually responds to.

    EXAMPLE:
    --------
    >>> accelerator('B')          # on Windows or Linux
    'Ctrl+B'
    """
    name = 'Enter' if key in ('Return', 'KP_Enter') else key
    return f"{MODIFIER_LABEL}{name}" if IS_MACOS else f"{MODIFIER_LABEL}+{name}"


def sequences(key: str) -> tuple:
    """
    Every Tk sequence one shortcut has to be bound to.

    PARAMETERS:
    -----------
    key : str
        A single letter, or a key name such as 'Return'.

    RETURNS:
    --------
    tuple
        The sequences to bind. A letter is bound in both cases; see the note
        on the module about caps lock.

    EXAMPLE:
    --------
    >>> sequences('b')            # on macOS
    ('<Command-b>', '<Command-B>')
    """
    if len(key) == 1 and key.isalpha():
        return (f"<{MODIFIER}-{key.lower()}>", f"<{MODIFIER}-{key.upper()}>")
    return (f"<{MODIFIER}-{key}>",)


def bind_all(widget, key: str, handler) -> None:
    """
    Bind one shortcut, in every form this platform needs.

    PARAMETERS:
    -----------
    widget : tkinter widget
        Usually the window, so the shortcut works wherever the focus is.
    key : str
        The key, as sequences() takes it.
    handler : callable
        Given the event, as any Tk binding is.

    DEVELOPMENT NOTES:
    ------------------
    add='+' throughout: these go onto windows that already have bindings of
    their own, and replacing them would take the dialog's own keys with it.
    """
    for sequence in sequences(key):
        widget.bind(sequence, handler, add='+')
