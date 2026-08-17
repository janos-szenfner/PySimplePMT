"""
A color picker with a full palette popup, for the task dialogs.

WHY THIS MODULE EXISTS:
======================
Color selection was a grid of swatches directly in the form. This module
provides a button-based approach where clicking "Choose" opens a popup
window with a comprehensive color palette, similar to how the date picker
works. This makes the interface cleaner and more user-friendly.

DEVELOPMENT NOTES:
------------------
Built the way the calendar in datepicker.py is, and the Dependency tab's
editor: the form carries a swatch and two buttons, and the seventy-six
swatches of the palette are built the first time Choose is pressed. Most
edits are a name or a date and never open it, so building it with every task
dialog would charge all of them for something few of them use - see
ColorEntry.open_picker.
"""

import tkinter as tk
from tkinter import ttk

import customtkinter as ctk

from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


#: Default color for tasks
DEFAULT_COLOR = '#1f6aa5'

#: The full color palette as (hex, name) tuples
FULL_PALETTE = (
    ('#ffffff', 'White'),
    ('#f8f9fa', 'Light Gray'),
    ('#e9ecef', 'Medium Light Gray'),
    ('#dee2e6', 'Silver'),
    ('#ced4da', 'Dark Silver'),
    ('#adb5bd', 'Gray'),
    ('#6c757d', 'Dark Gray'),
    ('#495057', 'Charcoal'),
    ('#343a40', 'Dark Charcoal'),
    ('#212529', 'Black'),
    
    ('#1f6aa5', 'Blue'),
    ('#007bff', 'Bright Blue'),
    ('#0069d9', 'Deep Blue'),
    ('#0056b3', 'Navy Blue'),
    ('#004085', 'Dark Navy'),
    ('#003061', 'Midnight Blue'),
    ('#002040', 'Deep Midnight'),
    
    ('#3498db', 'Light Blue'),
    ('#2980b9', 'Sky Blue'),
    ('#1abc9c', 'Teal'),
    ('#17a2b8', 'Cyan'),
    ('#00bcd4', 'Light Cyan'),
    ('#0097a7', 'Dark Cyan'),
    
    ('#2ecc71', 'Green'),
    ('#28a745', 'Success Green'),
    ('#20c997', 'Emerald'),
    ('#155724', 'Dark Green'),
    ('#006400', 'Forest Green'),
    ('#228b22', 'Sea Green'),
    
    ('#f1c40f', 'Yellow'),
    ('#ffc107', 'Amber'),
    ('#ffca28', 'Light Yellow'),
    ('#ffcd38', 'Golden Yellow'),
    ('#ffd54f', 'Pale Yellow'),
    ('#ffeb3b', 'Lemon'),
    
    ('#f39c12', 'Orange'),
    ('#fd7e14', 'Burnt Orange'),
    ('#ff9800', 'Bright Orange'),
    ('#ffa726', 'Light Orange'),
    ('#ffb74d', 'Pale Orange'),
    ('#ffcc80', 'Peach'),
    
    ('#e74c3c', 'Red'),
    ('#dc3545', 'Bright Red'),
    ('#c82333', 'Dark Red'),
    ('#bd2130', 'Deep Red'),
    ('#ff1744', 'Pink Red'),
    ('#ff5252', 'Light Red'),
    
    ('#9b59b6', 'Purple'),
    ('#8e44ad', 'Deep Purple'),
    ('#673ab7', 'Indigo'),
    ('#7b1fa2', 'Dark Indigo'),
    ('#5e35b1', 'Deep Indigo'),
    ('#4527a0', 'Dark Purple'),
    
    ('#f06292', 'Pink'),
    ('#e91e63', 'Hot Pink'),
    ('#d81b60', 'Deep Pink'),
    ('#c2185b', 'Dark Pink'),
    ('#ad1457', 'Magenta'),
    ('#880e4f', 'Dark Magenta'),
    
    ('#795548', 'Brown'),
    ('#6d4c41', 'Dark Brown'),
    ('#5d4037', 'Deep Brown'),
    ('#4e342e', 'Darker Brown'),
    ('#3e2723', 'Darkest Brown'),
    
    ('#34495e', 'Slate'),
    ('#2c3e50', 'Charcoal Blue'),
    ('#7f8c8d', 'Grey'),
    ('#95a5a6', 'Light Grey'),
    ('#dfe6e9', 'Pale Grey'),
    
    ('#f5f5f5', 'Off White'),
    ('#e0e0e0', 'Very Light Gray'),
    ('#bdbdbd', 'Light Gray'),
    ('#9e9e9e', 'Medium Gray'),
    ('#757575', 'Dark Gray'),
    ('#616161', 'Darker Gray'),
    ('#424242', 'Almost Black'),
)

#: Swatches per row in the popup
COLUMNS = 12

#: How far the palette is allowed to grow before it starts scrolling.
MAX_POPUP_WIDTH = 900
MAX_POPUP_HEIGHT = 600


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
    This follows the same pattern as DateEntry in datepicker.py, providing
    a compact representation in the form with a popup for the full selection.
    """

    #: Size of the color preview swatch
    SWATCH_SIZE = 24
    BUTTON_WIDTH = 80

    def __init__(self, master, color: str = DEFAULT_COLOR, on_change=None, **kwargs):
        super().__init__(master, fg_color='transparent', **kwargs)
        
        self.on_change = on_change
        self._value = normalise(color or DEFAULT_COLOR)
        self._popup = None
        
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
        Open the palette, building it the first time it is asked for.

        DEVELOPMENT NOTES:
        ------------------
        The seventy-six swatches are built here rather than with the form,
        the way the Dependency tab builds its editor on first sight of it.
        Most edits are a name or a date and never open the palette, and
        building it with every task dialog would charge all of them for it.
        """
        if self._popup is not None and self._popup.winfo_exists():
            self._popup.lift()
            return self._popup

        logger.debug("Building the colour palette, opening on %s", self._value)
        self._popup = ColorPickerPopup(
            self, self._value, on_pick=self._picked
        )
        return self._popup

    def _picked(self, color: str):
        """Take a color chosen from the picker."""
        self.set(color)
        logger.debug("Picked color %s from the color picker", color)


class ColorPickerPopup(ctk.CTkToplevel):
    """
    A popup window with a full color palette for selection.
    
    PARAMETERS:
    -----------
    master : widget
        The ColorEntry that opened it.
    color : str
        The color to start with (selected).
    on_pick : callable
        Called with the chosen color hex string.
    
    DEVELOPMENT NOTES:
    ------------------
    The swatches are built in a grid. A very large palette means many rows,
    so the popup is made scrollable if needed. For now, the FULL_PALETTE
    produces about 20 rows with COLUMNS=12, which is manageable.
    """

    #: Size of each color swatch
    SWATCH = 28
    SELECTED_BORDER = 3
    SELECTED_BORDER_COLOR = '#1a1a1a'
    UNSELECTED_BORDER_COLOR = '#d0d0d0'

    def __init__(self, master, color: str, on_pick):
        super().__init__(master)
        
        self.on_pick = on_pick
        self._value = normalise(color)
        self._buttons = {}
        
        self.title("Choose Color")
        self.resizable(False, False)
        self.transient(master.winfo_toplevel())
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind('<Escape>', lambda _e: self.close())
        
        self._build()
        self._show_selection()
        self._place_near(master)

    def _build(self):
        """
        Lay the palette out, and give the canvas room to show it.

        DEVELOPMENT NOTES:
        ------------------
        The canvas is sized from the palette rather than left at the size a
        tk.Canvas defaults to. Left alone it opened at 284x199 around a grid
        wanting 432x252, so the picker came up showing about half its colours
        with the rest behind a scrollbar - on a palette of seventy-six
        swatches that fits on any screen with room to spare.

        The cap is there so that a palette someone extends to hundreds of
        colours scrolls instead of opening taller than the desktop.
        """
        main_frame = ctk.CTkFrame(self, fg_color='transparent')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # A canvas with no scroll increment moves a tenth of itself per
        # notch, which on a palette this size is most of it
        self._canvas = tk.Canvas(main_frame, highlightthickness=0,
                                 borderwidth=0, yscrollincrement=20)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL,
                                        command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._scrollbar.set)

        self._grid_frame = ctk.CTkFrame(self._canvas, fg_color='transparent')
        self._window = self._canvas.create_window(
            (0, 0), window=self._grid_frame, anchor='nw')

        self._build_grid()
        self._fit_to_palette()
        self._bind_wheel()

        close_frame = ctk.CTkFrame(self, fg_color='transparent')
        close_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        ctk.CTkButton(close_frame, text="Close", width=80,
                      command=self.close).pack(side=tk.RIGHT)

    def _fit_to_palette(self):
        """Open at the size of the palette, up to what a screen will take."""
        self._grid_frame.update_idletasks()
        wanted_width = self._grid_frame.winfo_reqwidth()
        wanted_height = self._grid_frame.winfo_reqheight()

        width = min(wanted_width, MAX_POPUP_WIDTH)
        height = min(wanted_height, MAX_POPUP_HEIGHT)
        self._canvas.configure(width=width, height=height,
                               scrollregion=(0, 0, wanted_width, wanted_height))

        if wanted_height > height:
            # Only then is there anything to scroll past
            self._scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _bind_wheel(self):
        """
        Let the wheel scroll a palette too tall to show at once.

        Bound to the swatches as well as to the canvas: the pointer spends
        its time over them, and an event goes to the widget under it, so a
        wheel bound to the canvas alone did nothing anywhere the user's
        pointer actually was.
        """
        def on_wheel(event):
            """Scroll by a notch, the way the chart reads one."""
            if event.delta:
                steps = -1 if event.delta > 0 else 1
                if abs(event.delta) >= 120:
                    steps = int(-event.delta / 120)
            else:
                steps = -1 if getattr(event, 'num', 5) == 4 else 1
            self._canvas.yview_scroll(steps, 'units')
            return 'break'

        for widget in [self._canvas, self._grid_frame,
                       *self._buttons.values()]:
            for sequence in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
                widget.bind(sequence, on_wheel, add='+')

    def _build_grid(self):
        """Lay the color swatches out in a grid."""
        for index, (value, name) in enumerate(FULL_PALETTE):
            row, column = divmod(index, COLUMNS)
            button = tk.Frame(
                self._grid_frame, width=self.SWATCH, height=self.SWATCH,
                background=value, cursor='hand2',
                highlightthickness=self.SELECTED_BORDER,
                highlightbackground=self.UNSELECTED_BORDER_COLOR,
            )
            button.grid(row=row, column=column, padx=4, pady=4)
            button.grid_propagate(False)
            button.bind('<Button-1>', lambda _e, v=value: self.pick(v))
            self._buttons[value] = button
            
            # Tooltip-like debug info
            button.bind('<Enter>',
                        lambda _e, n=name: logger.debug("Color %s", n))

    def _show_selection(self):
        """Outline the selected swatch and clear the others."""
        for value, button in self._buttons.items():
            selected = value.lower() == self._value.lower()
            try:
                button.configure(
                    highlightbackground=(self.SELECTED_BORDER_COLOR if selected
                                         else self.UNSELECTED_BORDER_COLOR),
                    highlightcolor=(self.SELECTED_BORDER_COLOR if selected
                                    else self.UNSELECTED_BORDER_COLOR),
                )
            except tk.TclError:
                pass

    def _place_near(self, widget):
        """
        Open just below the widget that asked for it.
        
        DEVELOPMENT NOTES:
        ------------------
        Only the widget's own position is needed, and it already has one.
        This follows the same pattern as datepicker.py.
        """
        try:
            x = widget.winfo_rootx()
            y = widget.winfo_rooty() + widget.winfo_height() + 4
            # Adjust for screen boundaries
            screen_width = widget.winfo_screenwidth()
            screen_height = widget.winfo_screenheight()
            
            # Make sure we don't go off-screen
            popup_width = 600  # Approximate width
            popup_height = 500  # Approximate height
            
            if x + popup_width > screen_width:
                x = screen_width - popup_width - 20
            if y + popup_height > screen_height:
                y = screen_height - popup_height - 20
                
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except tk.TclError:
            pass

    def pick(self, color: str):
        """Choose a color and close."""
        self._value = normalise(color)
        if self.on_pick:
            self.on_pick(self._value)
        self.close()

    def close(self):
        """Close the picker."""
        try:
            self.destroy()
        except tk.TclError:
            pass


class ColorPickerDialog:
    """
    Kept for the name alone.

    It never was a dialog - it held one static copy of normalise, which two
    other classes held copies of as well. The function is the module's now;
    this stays so that anything reaching for the old name still finds it.
    """

    _normalise = staticmethod(normalise)