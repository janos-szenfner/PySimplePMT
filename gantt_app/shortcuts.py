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

#: The Option key on a Mac, the Alt key everywhere else.
#:
#: Tk spells it Option on macOS - an alias for Alt, which it also accepts -
#: and Alt elsewhere. Written the way each platform's own documentation
#: writes it, so a binding read here matches what a reader would look up.
ALT = 'Option' if IS_MACOS else 'Alt'
ALT_LABEL = '⌥' if IS_MACOS else 'Alt'


def _held(shift: bool, alt: bool) -> list:
    """
    The modifiers a shortcut holds besides the key itself.

    The platform's own modifier first, then the extras. Tk does not mind
    the order within a sequence, so this is only a convention - but it is
    the one the sequences already bound were written in, and respelling a
    working binding to tidy it is a change with a risk and no gain.

    Note that this is not the order they are *written* in for the reader:
    see accelerator, where a Mac's fixed ⌥⌘ order applies.
    """
    parts = [MODIFIER]
    if shift:
        parts.append(SHIFT)
    if alt:
        parts.append(ALT)
    return parts


def accelerator(key: str, shift: bool = False, alt: bool = False) -> str:
    """
    How a shortcut is written for the reader.

    PARAMETERS:
    -----------
    key : str
        The key itself - 'B', 'F2', 'Enter', 'Return'.
    shift : bool
        True when the shortcut also holds Shift.
    alt : bool
        True when it also holds Option on a Mac, Alt elsewhere.

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
    >>> accelerator('.', alt=True)      # on Windows or Linux
    'Ctrl+Alt+.'

    DEVELOPMENT NOTES:
    ------------------
    A Mac writes the modifiers as symbols with nothing between them and in
    a fixed order - ⌥ before ⌘, so Option+Command+. is written ⌥⌘. however
    it is said out loud.
    """
    name = 'Enter' if key in ('Return', 'KP_Enter') else key
    if IS_MACOS:
        return (f"{SHIFT_LABEL if shift else ''}"
                f"{ALT_LABEL if alt else ''}{MODIFIER_LABEL}{name}")
    parts = ([MODIFIER_LABEL] + ([SHIFT_LABEL] if shift else [])
             + ([ALT_LABEL] if alt else []) + [name])
    return '+'.join(parts)


def sequences(key: str, shift: bool = False, alt: bool = False) -> tuple:
    """
    Every Tk sequence one shortcut has to be bound to.

    PARAMETERS:
    -----------
    key : str
        A single letter, or a key name such as 'Return' or 'F2'.
    shift : bool
        True when the shortcut also holds Shift.
    alt : bool
        True when it also holds Option on a Mac, Alt elsewhere.

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
    >>> sequences('.', alt=True)        # on macOS
    ('<Command-Option-period>',)

    DEVELOPMENT NOTES:
    ------------------
    Tk spells Shift out in the sequence whichever platform it is on, and
    puts it before the other modifier. A held Shift is not the same thing as
    the upper-case letter the two forms above bind: Shift+B reports keysym
    'B' with the Shift bit set, so a shortcut that means to include Shift
    has to say so.
    """
    held = '-'.join(_held(shift, alt))
    if len(key) == 1 and key.isalpha():
        return (f"<{held}-{key.lower()}>", f"<{held}-{key.upper()}>")
    return (f"<{held}-{key}>",)


#: Where each letter sits on a Mac keyboard, by macOS virtual keycode.
#:
#: Only the letters this application binds. macOS virtual keycodes name a
#: physical position rather than a character, so they are the same whatever
#: the keyboard layout produces - which is the point of having them here.
MAC_KEYCODES = {'b': 11, 'i': 34, 'u': 32, '.': 47}

#: The bits Tk sets in an event's state for the modifiers a shortcut holds.
#:
#: Tk uses the X11 modifier masks on every platform, and its macOS port puts
#: the Command key on Mod1 and the Option key on Mod2 - the same two bits its
#: binding table answers to the names 'Command' and 'Option'. So a state read
#: here and a sequence bound above are talking about the same thing.
#:
#: Read directly only by the last-resort net under a shortcut that holds
#: Option; see modifiers_held and Toolbar._any_key_pressed. Everywhere else
#: Tk matches the modifiers itself, which is better done by the library.
COMMAND_BIT = 0x08                      # Mod1
OPTION_BIT = 0x10                       # Mod2


def modifiers_held(event, alt: bool = False) -> bool:
    """
    Whether a key event carries this platform's shortcut modifiers.

    PARAMETERS:
    -----------
    event : tkinter.Event
        A KeyPress.
    alt : bool
        True to require Option as well as the platform's own modifier.

    RETURNS:
    --------
    bool
        True when every modifier asked for is held. Others may be held too;
        this says nothing about them.

    DEVELOPMENT NOTES:
    ------------------
    macOS only. Everywhere else Alt leaves a keystroke alone, so the bound
    sequences match and nothing needs to read the state by hand - and the
    bit Alt sets is not the same on Windows as it is on X11, so guessing at
    one here would be a wrong answer rather than a missing one.
    """
    if not IS_MACOS:
        return False
    state = getattr(event, 'state', 0)
    if not isinstance(state, int):
        return False
    wanted = COMMAND_BIT | (OPTION_BIT if alt else 0)
    return state & wanted == wanted


def any_key_with(shift: bool = False, alt: bool = False) -> str:
    """
    The sequence matching any key pressed while these modifiers are held.

    RETURNS:
    --------
    str
        A Tk sequence such as '<Command-Option-KeyPress>'.

    DEVELOPMENT NOTES:
    ------------------
    For shortcuts that hold Option. Tk matches the modifiers itself here,
    which is the half that works; identifying the key is left to is_key,
    which is the half that does not - see there.
    """
    return f"<{'-'.join(_held(shift, alt))}-KeyPress>"


def is_key(event, key: str) -> bool:
    """
    Whether a key event is the given key, however it reached us.

    PARAMETERS:
    -----------
    event : tkinter.Event
        A KeyPress.
    key : str
        The key meant, as a single letter.

    RETURNS:
    --------
    bool
        True when the event is that key.

    DEVELOPMENT NOTES:
    ------------------
    Option is a compose key on macOS: it does not modify a keystroke so much
    as replace it. Option+. on a US layout produces an ellipsis, so the event
    can arrive carrying keysym 'ellipsis' and a char of '…' - and a binding
    written <Command-Option-period> may not match, because by the time Tk
    looks there is no period in the event to match against.

    Which of those a given Tk hands over differs by version, so all three
    are accepted: the keysym, the character, and - on a Mac - the physical
    key the keycode names, which is the one thing Option cannot change.
    """
    wanted = key.lower()
    for reported in (getattr(event, 'keysym', ''), getattr(event, 'char', '')):
        if isinstance(reported, str) and reported.lower() == wanted:
            return True

    if IS_MACOS and wanted in MAC_KEYCODES:
        keycode = getattr(event, 'keycode', None)
        if isinstance(keycode, int):
            # Tk has reported this as the bare virtual keycode and, in other
            # versions, packed into the high bytes with the character
            # underneath it. The low bits are shifted away rather than
            # compared: an equality against the packed forms only matched
            # when the character underneath happened to be zero, which for
            # Option+. - an ellipsis on a US layout, and something else again
            # on others - it is not.
            virtual = MAC_KEYCODES[wanted]
            return virtual in (keycode,
                               (keycode >> 16) & 0xFFFF,
                               (keycode >> 24) & 0xFF)
    return False


def bind_all(widget, key: str, handler, shift: bool = False,
             alt: bool = False) -> None:
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
    alt : bool
        True when it also holds Option on a Mac, Alt elsewhere.

    DEVELOPMENT NOTES:
    ------------------
    add='+' throughout: these go onto windows that already have bindings of
    their own, and replacing them would take the dialog's own keys with it.
    """
    for sequence in sequences(key, shift, alt):
        widget.bind(sequence, handler, add='+')
