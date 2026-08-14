"""
The colour swatches shared by the task creation and editing dialogs.

WHY THIS MODULE EXISTS:
======================
Colour was a text box holding a hex code. Picking one meant knowing that
#9b59b6 is purple, a typo produced a task Tk refused to draw, and there was
nothing to keep a plan looking consistent - every task was a fresh guess at
a colour. A fixed set of swatches removes all three problems, and both
dialogs need exactly the same one.

DEVELOPMENT NOTES:
------------------
The palette is the set the application already used: the defaults for tasks,
sub-tasks and milestones are in it, so an existing plan keeps its colours and
the swatch for a task already shows as selected when a dialog opens.

A colour from outside the palette - an imported file, or a project saved
before this existed - is kept and shown as an extra swatch rather than being
snapped to the nearest one, which would quietly repaint someone's plan.
"""

import tkinter as tk

import customtkinter as ctk

from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


#: The choices, as (hex, name). Names are what the tooltip and the log say.
PALETTE = (
    ('#1f6aa5', 'Blue'),
    ('#3498db', 'Light blue'),
    ('#1abc9c', 'Teal'),
    ('#2ecc71', 'Green'),
    ('#f1c40f', 'Yellow'),
    ('#f39c12', 'Orange'),
    ('#e74c3c', 'Red'),
    ('#9b59b6', 'Purple'),
    ('#8e44ad', 'Deep purple'),
    ('#34495e', 'Slate'),
    ('#7f8c8d', 'Grey'),
    ('#2c3e50', 'Charcoal'),
)

#: Swatches per row.
COLUMNS = 6


class ColorPalette(ctk.CTkFrame):
    """
    A grid of colour swatches with one selected.

    PARAMETERS:
    -----------
    master : widget
        Parent widget.
    color : str
        The colour to start on. One outside the palette is added to it.
    on_change : Optional[Callable]
        Called with the new hex string whenever the selection changes.

    DEVELOPMENT NOTES:
    ------------------
    Selection is shown by a border rather than a tick, so the swatch's own
    colour stays fully visible - which is the thing being chosen.
    """

    SWATCH = 26
    SELECTED_BORDER = 3
    SELECTED_BORDER_COLOR = '#1a1a1a'
    #: Border on the swatches that are not selected. A literal colour rather
    #: than the frame's own fg_color, which CustomTkinter reports as
    #: 'transparent' - a value it understands and Tk does not.
    UNSELECTED_BORDER_COLOR = '#d0d0d0'

    def __init__(self, master, color: str = '#1f6aa5', on_change=None):
        super().__init__(master, fg_color='transparent')

        self.on_change = on_change
        self._value = self._normalise(color)
        self._buttons = {}

        self._build(self._choices())
        self._show_selection()

    @staticmethod
    def _normalise(color: str) -> str:
        """Tidy a stored colour into a comparable hex string."""
        text = str(color or '').strip().lower()
        return text if text.startswith('#') else f'#{text}' if text else '#1f6aa5'

    def _choices(self):
        """
        The swatches to draw.

        A colour that is not in the palette is appended, so opening a task
        that came from an imported file shows its real colour as selected
        instead of silently offering to change it.
        """
        choices = list(PALETTE)
        if self._value not in {value for value, _name in choices}:
            choices.append((self._value, 'Current'))
        return choices

    def _build(self, choices):
        """Lay the swatches out in a grid."""
        for index, (value, name) in enumerate(choices):
            row, column = divmod(index, COLUMNS)
            button = tk.Frame(
                self, width=self.SWATCH, height=self.SWATCH,
                background=value, cursor='hand2',
                highlightthickness=self.SELECTED_BORDER,
                highlightbackground=self.UNSELECTED_BORDER_COLOR,
            )
            button.grid(row=row, column=column, padx=3, pady=3)
            button.grid_propagate(False)
            button.bind('<Button-1>', lambda _e, v=value: self.set(v))
            self._buttons[value] = button

            # Tk has no tooltip; the name is at least reachable by hovering
            # in any environment that surfaces it
            button.bind('<Enter>',
                        lambda _e, n=name: logger.debug("Colour %s", n))

    def _show_selection(self):
        """Outline the selected swatch and clear the others."""
        for value, button in self._buttons.items():
            selected = value == self._value
            try:
                button.configure(
                    highlightbackground=(self.SELECTED_BORDER_COLOR if selected
                                         else self.UNSELECTED_BORDER_COLOR),
                    highlightcolor=(self.SELECTED_BORDER_COLOR if selected
                                    else self.UNSELECTED_BORDER_COLOR),
                )
            except tk.TclError:
                pass

    def get(self) -> str:
        """The selected colour, as a hex string."""
        return self._value

    def set(self, color: str):
        """
        Select a colour.

        A value outside the palette is accepted and gets a swatch of its own,
        so setting one programmatically cannot lose it.
        """
        value = self._normalise(color)
        if value == self._value:
            return

        self._value = value
        if value not in self._buttons:
            self._rebuild()
        self._show_selection()

        if self.on_change:
            self.on_change(value)

    def _rebuild(self):
        """Redraw the swatches, for a colour that was not there before."""
        for button in self._buttons.values():
            button.destroy()
        self._buttons = {}
        self._build(self._choices())
