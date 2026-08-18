"""
How a secondary button is drawn, so it is drawn the same everywhere.

WHY THIS MODULE EXISTS:
======================
A dialog with two buttons wants them to look different: Apply and Cancel side
by side in the same filled blue is an invitation to press the wrong one. The
obvious way to say "this is the quieter one" in CustomTkinter is
`fg_color='transparent'`, and it is a trap - the theme's button text colour is
white, chosen to sit on the filled blue, so a transparent button is white text
on the window's own background. On macOS that is white on white: the Cancel in
the holiday picker and the Recalculate in the critical path window were both
invisible, and looked like empty space where a button should be.

So a secondary button is drawn here, once, with a colour of its own and a text
colour to go with it. Both are given as (light, dark) pairs, which is how
CustomTkinter is told what to use in either appearance mode - a single colour
would be legible in one and not the other, which is the same bug with an extra
step.
"""

from typing import Any, Dict

import customtkinter as ctk


#: Fill, hover and text for a button that is not the primary action, as
#: (light mode, dark mode) pairs.
SECONDARY_FILL = ('#e5e7eb', '#4a4d50')
SECONDARY_HOVER = ('#d1d5db', '#5c6063')
SECONDARY_TEXT = ('#1f2937', '#f2f2f2')
SECONDARY_BORDER = ('#c8ccd0', '#5c6063')


def secondary_button(master, text: str, command, width: int = 110, **kwargs):
    """
    A button for the action that is not the main one.

    PARAMETERS:
    -----------
    master : widget
        Where to put it.
    text : str
        Its label.
    command : callable
        What it does.
    width : int
        Its width, matching the primary button beside it.
    **kwargs
        Anything else CTkButton takes.

    RETURNS:
    --------
    ctk.CTkButton
        Visible in both appearance modes, and clearly the quieter of the two.
    """
    options: Dict[str, Any] = dict(
        fg_color=SECONDARY_FILL,
        hover_color=SECONDARY_HOVER,
        text_color=SECONDARY_TEXT,
        border_color=SECONDARY_BORDER,
        border_width=1,
    )
    options.update(kwargs)
    return ctk.CTkButton(master, text=text, width=width, command=command,
                         **options)
