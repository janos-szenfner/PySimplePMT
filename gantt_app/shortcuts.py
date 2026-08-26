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

#: The other modifier some shortcuts add, spelled both ways.
#:
#: A Mac writes the modifiers as symbols with nothing between them and in a
#: fixed order - Shift before Command, so Cmd+Shift+F2 is written the other
#: way round from how it is said. Everywhere else they are words joined by
#: plus signs, in the order they are pressed.
SHIFT = 'Shift'
SHIFT_LABEL = '⇧' if IS_MACOS else 'Shift'


def accelerator(key: str, shift: bool = False) -> str:
    """
    How a shortcut is written for the reader.

    PARAMETERS:
    -----------
    key : str
        The key itself - 'B', 'F2', 'Enter', 'Return'.
    shift : bool
        True when the shortcut also holds Shift.

    RETURNS:
    --------
    str
        Cmd notation on a Mac and Ctrl notation elsewhere, so a caption says
        what the machine it is running on actually responds to.

    EXAMPLE:
    --------
    >>> accelerator('B')          # on Windows or Linux
    'Ctrl+B'
    >>> accelerator('F2', shift=True)   # on Windows or Linux
    'Ctrl+Shift+F2'
    """
    name = 'Enter' if key in ('Return', 'KP_Enter') else key
    if IS_MACOS:
        return f"{SHIFT_LABEL if shift else ''}{MODIFIER_LABEL}{name}"
    parts = [MODIFIER_LABEL] + ([SHIFT_LABEL] if shift else []) + [name]
    return '+'.join(parts)


def sequences(key: str, shift: bool = False) -> tuple:
    """
    Every Tk sequence one shortcut has to be bound to.

    PARAMETERS:
    -----------
    key : str
        A single letter, or a key name such as 'Return' or 'F2'.
    shift : bool
        True when the shortcut also holds Shift.

    RETURNS:
    --------
    tuple
        The sequences to bind. A letter is bound in both cases; see the note
        on the module about caps lock.

    EXAMPLE:
    --------
    >>> sequences('b')            # on macOS
    ('<Command-b>', '<Command-B>')
    >>> sequences('F2', shift=True)     # on macOS
    ('<Command-Shift-F2>',)

    DEVELOPMENT NOTES:
    ------------------
    Tk spells Shift out in the sequence whichever platform it is on, and
    puts it before the other modifier. A held Shift is not the same thing as
    the upper-case letter the two forms above bind: Shift+B reports keysym
    'B' with the Shift bit set, so a shortcut that means to include Shift
    has to say so.
    """
    held = f"{MODIFIER}-{SHIFT}" if shift else MODIFIER
    if len(key) == 1 and key.isalpha():
        return (f"<{held}-{key.lower()}>", f"<{held}-{key.upper()}>")
    return (f"<{held}-{key}>",)


def bind_all(widget, key: str, handler, shift: bool = False) -> None:
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
    shift : bool
        True when the shortcut also holds Shift.

    DEVELOPMENT NOTES:
    ------------------
    add='+' throughout: these go onto windows that already have bindings of
    their own, and replacing them would take the dialog's own keys with it.
    """
    for sequence in sequences(key, shift):
        widget.bind(sequence, handler, add='+')
