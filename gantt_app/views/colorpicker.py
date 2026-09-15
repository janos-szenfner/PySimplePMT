"""
A color entry for the task dialogs, backed by the platform's chooser.

WHY THIS MODULE EXISTS:
======================
The form needs a compact color field - a swatch showing the current value
with a Choose button beside it - rather than a palette sitting inside the
dialog itself.

DEVELOPMENT NOTES:
------------------
Choose opens tkinter's own colorchooser, the same dialog the baseline
settings use, so every colour in the application is picked the same way
and the full system wheel is on offer instead of a fixed swatch list.
"""

import tkinter as tk
from tkinter import colorchooser

import customtkinter as ctk

from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


#: Default color for tasks
DEFAULT_COLOR = '#1f6aa5'


def normalise(color: str) -> str:
    """
    Tidy a stored colour into a comparable string.

    RETURNS:
    --------
    str
        A lowercased hex string with its '#', or a colour name as given.
        An empty value becomes DEFAULT_COLOR.

    DEVELOPMENT NOTES:
    ------------------
    Six hex digits with no '#' are what a file written elsewhere tends to
    carry, so they gain one. A name does not: Tk accepts 'red', and putting
    a '#' in front of it made '#red', which Tk accepts from nobody.
    """
    text = str(color or '').strip().lower()
    if not text:
        return DEFAULT_COLOR
    if text.startswith('#'):
        return text
    if all(character in '0123456789abcdef' for character in text):
        return f'#{text}'
    return text


class ColorEntry(ctk.CTkFrame):
    """
    A color preview with Choose and Default buttons.

    PARAMETERS:
    -----------
    master : widget
        Parent widget.
    color : str
        The color to start on. Defaults to DEFAULT_COLOR.
    on_change : Optional[Callable]
        Called with the new hex string whenever the color changes.

    DEVELOPMENT NOTES:
    ------------------
    Choose opens the platform's colour chooser - tk's colorchooser, the
    one the baseline settings use - seeded with the colour shown, so the
    user picks from the full system wheel rather than a swatch list.
    """

    #: Size of the color preview swatch
    SWATCH_SIZE = 24
    BUTTON_WIDTH = 80

    def __init__(self, master, color: str = DEFAULT_COLOR, on_change=None, **kwargs):
        super().__init__(master, fg_color='transparent', **kwargs)

        self.on_change = on_change
        self._value = normalise(color or DEFAULT_COLOR)

        # Build the layout: preview swatch + Choose button + Default button
        self._build()
        self._show_color()

    def _build(self):
        """Build the color preview and buttons."""
        # Color preview swatch
        self.preview_frame = tk.Frame(
            self, width=self.SWATCH_SIZE, height=self.SWATCH_SIZE,
            borderwidth=1, relief=tk.SOLID, cursor='hand2'
        )
        self.preview_frame.grid(row=0, column=0, padx=(0, 8), pady=2)
        self.preview_frame.grid_propagate(False)
        self.preview_frame.bind('<Button-1>', lambda _e: self.open_picker())

        # Choose button
        self.choose_btn = ctk.CTkButton(
            self, text="Choose", width=self.BUTTON_WIDTH,
            command=self.open_picker
        )
        self.choose_btn.grid(row=0, column=1, padx=(0, 8))

        # Default button
        self.default_btn = ctk.CTkButton(
            self, text="Default", width=self.BUTTON_WIDTH,
            command=self.set_default
        )
        self.default_btn.grid(row=0, column=2, padx=(0, 0))

    def _show_color(self):
        """
        Paint the preview swatch with the colour now selected.

        A colour Tk will not take is logged and the swatch left as it was,
        rather than passed over in silence: it means a task is carrying
        something no chart can draw either, and the Log window is where
        somebody would go to find out why the plan looks wrong.
        """
        try:
            self.preview_frame.configure(background=self._value)
        except tk.TclError:
            logger.warning("Cannot show colour %r; it is not one Tk accepts",
                           self._value)

    def get(self) -> str:
        """The selected color, as a hex string."""
        return self._value

    def set(self, color: str):
        """
        Set the color programmatically.

        PARAMETERS:
        -----------
        color : str
            The hex color string to set.
        """
        value = normalise(color)
        if value == self._value:
            return

        self._value = value
        self._show_color()

        if self.on_change:
            self.on_change(value)

    def set_default(self):
        """Reset to the default blue color."""
        self.set(DEFAULT_COLOR)

    def open_picker(self):
        """
        Open the platform's colour chooser and take its answer.

        The same dialog the baseline settings offer - tk's own
        colorchooser - opened on the colour shown. Cancelling leaves the
        entry untouched.

        RETURNS:
        --------
        str or None
            The hex string chosen, or None when the chooser was cancelled.
        """
        result = colorchooser.askcolor(
            color=self._value, title="Choose color")
        if result is None or result[1] is None:
            return None
        self.set(result[1])
        logger.debug("Picked color %s from the color chooser", result[1])
        return result[1]
