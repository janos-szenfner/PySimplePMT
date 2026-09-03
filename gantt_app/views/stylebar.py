"""
The formatting group on the icon bar: ink, fill and emphasis for a row.

WHY THIS MODULE EXISTS:
======================
The task list is the operational workspace, and a plan of any size is scanned
rather than read. The rows worth finding again - the payment milestones, the
phase gates, the things that are finished - have to be findable at a glance,
and a Type column does not do that, because scanning is exactly the activity
that skips columns.

So the formatting lives on the main toolbar rather than behind the task
editor. Marking a row up has to cost one press from where the reader already
is; a dialog two clicks away is how a feature ends up unused.

WHAT IT DOES NOT DO:
====================
It holds no state about the plan and changes nothing. It reports which control
was pressed and shows what it is told to show - see StyleBar.set_state. What a
press means for the selected rows, and how that reaches the undo history, is
the toolbar's business.

That split is deliberate: the same bar has to answer for one selected row and
for forty, and "what is bold when three of five rows are" is a question about
a selection rather than about a button.
"""

import tkinter as tk
from typing import Callable, Optional

import customtkinter as ctk

from gantt_app import theme
from gantt_app.shortcuts import accelerator
from gantt_app.taskstyle import (
    DEFAULT_BADGE, FILL_COLOURS, PRESETS, TEXT_COLOURS, ResolvedStyle,
    preset_badge,
)
from gantt_app.utils.log import get_logger
from gantt_app.views.modal import take_grab
from gantt_app.views.tooltip import attach as attach_tooltip

logger = get_logger(__name__)


#: How the swatches in a colour popup are laid out.
SWATCH_SIZE = 22
SWATCH_PAD = 3
SWATCH_COLUMNS = 6

#: The height of the colour bar under the A and the highlighter.
INDICATOR_HEIGHT = 3

#: What a colour bar shows when the row carries no colour of its own.
INDICATOR_DEFAULT = ('#9aa0a6', '#71767c')

#: Where the full picker starts when it is opened from a swatch grid.
DEFAULT_CUSTOM_COLOUR = '#1f6aa5'


class SwatchPopup(ctk.CTkToplevel):
    """
    A small grid of colours, opened from the button that asked for it.

    PARAMETERS:
    -----------
    master : widget
        The button this hangs from; also what it is placed under.
    colours : Sequence[Tuple[str, Optional[str]]]
        Name and value per swatch. A value of None is the "no colour" entry -
        the grid's own ink, or no fill - and is drawn as an outlined square
        rather than a filled one, because a swatch of the background colour
        on a background is invisible.
    on_pick : Callable[[Optional[str]], None]
        Given the chosen colour, or None for the "no colour" entry.
    allow_custom : bool
        Whether to offer the full picker underneath.

    DEVELOPMENT NOTES:
    ------------------
    This is shaped like ColorPickerPopup, which is the colour window this
    application already had and which works. The first version was not, and
    was broken in three separate ways:

      * It was an overrideredirect, always-on-top window. On macOS an
        update() with one of those open does not return, and mainloop is
        update() in a loop - so opening the palette wedged the window.
      * It watched for a click elsewhere by binding <Button-1> on
        winfo_toplevel(), which for a Toplevel is itself. The binding went
        on the palette rather than on the window behind it, so clicking
        outside never closed it.
      * Closing unbound that <Button-1> from the *main* window instead.
        Tkinter's unbind(sequence, funcid) does not remove one binding: it
        clears every binding for that sequence on the widget it is called
        on. So using the palette once silently removed every <Button-1>
        handler the main window had, taking the menu dismissal with it.

    None of that is worth rebuilding carefully. A window with a title bar
    that takes the input grab is what the rest of the application uses, and
    take_grab hands the grab back to whatever held it when this closes.
    """

    def __init__(self, master, colours, on_pick: Callable,
                 allow_custom: bool = True, **kwargs):
        super().__init__(master, **kwargs)
        self.on_pick = on_pick

        self.title("Choose Colour")
        self.resizable(False, False)
        self.transient(master.winfo_toplevel())
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind('<Escape>', lambda _event: self.close())

        # The toolbar's own menus can hold a grab, and a grab is exclusive:
        # without taking it this window would receive no clicks at all
        take_grab(self)

        body = ctk.CTkFrame(self, fg_color='transparent')
        body.pack(padx=10, pady=(10, 4))

        for index, (name, value) in enumerate(colours):
            self._swatch(body, name, value,
                         index // SWATCH_COLUMNS, index % SWATCH_COLUMNS)

        if allow_custom:
            ctk.CTkButton(
                self, text="Custom colour...", height=28,
                command=self._open_picker,
            ).pack(fill=tk.X, padx=10, pady=(4, 4))

        ctk.CTkButton(
            self, text="Cancel", height=28, fg_color='transparent',
            border_width=1, border_color=theme.SEPARATOR,
            text_color=theme.TEXT, hover_color=theme.MENU_HOVER,
            command=self.close,
        ).pack(fill=tk.X, padx=10, pady=(0, 10))

        self._place_near(master)

    def _swatch(self, parent, name: str, value: Optional[str],
                row: int, column: int):
        """One colour, as a square that says what it is on hover."""
        if value is None:
            button = ctk.CTkButton(
                parent, text="/", width=SWATCH_SIZE, height=SWATCH_SIZE,
                fg_color='transparent', border_width=1,
                border_color=theme.SEPARATOR, text_color=theme.MUTED_TEXT,
                hover_color=theme.MENU_HOVER,
                command=lambda: self._picked(None))
        else:
            button = ctk.CTkButton(
                parent, text="", width=SWATCH_SIZE, height=SWATCH_SIZE,
                fg_color=value, border_width=1,
                border_color=theme.SEPARATOR, hover_color=value,
                command=lambda colour=value: self._picked(colour))

        button.grid(row=row, column=column, padx=SWATCH_PAD, pady=SWATCH_PAD)
        button.tooltip_widget = attach_tooltip(button, name)

    def _open_picker(self):
        """
        Hand over to the full colour picker.

        DEVELOPMENT NOTES:
        ------------------
        The parent is read before this window closes, because self.master is
        gone once it has. The picker is opened after the close so the grab
        this window holds is released first - opening it underneath a live
        grab is precisely the fault take_grab exists to describe, and the
        picker would have come up unable to receive a click.
        """
        from gantt_app.views.colorpicker import ColorPickerPopup

        parent = self.master
        self.close()
        try:
            ColorPickerPopup(parent, DEFAULT_CUSTOM_COLOUR, self.on_pick)
        except Exception:
            logger.exception("Could not open the colour picker")

    def _picked(self, colour: Optional[str]):
        """Report the choice and go away."""
        self.close()
        try:
            self.on_pick(colour)
        except Exception:
            logger.exception("Could not apply the colour %r", colour)

    def _place_near(self, widget):
        """Sit under the button that opened this, and on screen."""
        try:
            self.update_idletasks()
            x = widget.winfo_rootx()
            y = widget.winfo_rooty() + widget.winfo_height() + 4
            # Not off the bottom or the right of the display
            x = min(x, max(0, self.winfo_screenwidth() - self.winfo_width()))
            y = min(y, max(0, self.winfo_screenheight() - self.winfo_height()))
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except tk.TclError:
            pass

    def close(self, *_args):
        """Take the palette off screen once, whatever state it is in."""
        try:
            self.destroy()
        except tk.TclError:
            pass


class StyleBar(ctk.CTkFrame):
    """
    Bold, italic, underline, ink, fill, the presets, and the way back.

    PARAMETERS:
    -----------
    master : widget
        The icon toolbar this sits in.
    on_apply : Callable[[str, object], None]
        Called with what was pressed and what it means: ('bold', True),
        ('text_color', '#c0392b'), ('preset', TaskStyle), ('reset', None).
    button_size : int
        Matched to the icons either side so the row stays one height.
    icon_image : Callable[[str], object]
        How to get a drawing, which the toolbar already caches per
        appearance. Passed in rather than imported so this does not build a
        second cache of the same pictures.

    DEVELOPMENT NOTES:
    ------------------
    Every control is disabled until something is selected. A formatting bar
    that looks live with nothing to format invites a press that silently does
    nothing, and the user learns the bar is unreliable rather than that they
    forgot to select a row.
    """

    #: What each control is called, and what it says on hover.
    CAPTIONS = {
        # The modifier is the platform's, and the caption says whichever it
        # is: a hover promising Ctrl+B on a Mac names a key that does
        # nothing. See gantt_app.shortcuts.
        'bold': f"Bold  ({accelerator('B')})",
        'italic': f"Italic  ({accelerator('I')})",
        'underline': f"Underline  ({accelerator('U')})",
        'text_color': "Text colour",
        'fill_color': "Background fill",
        'style_preset': "Style presets",
        'clear_style': "Clear formatting",
    }

    def __init__(self, master, on_apply: Callable, button_size: int = 32,
                 icon_image: Optional[Callable] = None, **kwargs):
        super().__init__(master, fg_color='transparent', **kwargs)

        self.on_apply = on_apply
        self.button_size = button_size
        self._icon_image = icon_image or (lambda _name: None)

        #: Every control, by name, so state can be set in one sweep.
        self.buttons = {}
        #: The colour bars under the ink and fill buttons.
        self.indicators = {}
        #: Whether anything is selected; see set_state.
        self.enabled = False

        self._build()
        self.set_state(False, None)

    # ---- building -------------------------------------------------------

    def _build(self):
        """Lay the group out: emphasis, then colour, then the presets."""
        for name, caption in (('bold', 'B'), ('italic', 'I'),
                              ('underline', 'U')):
            self._emphasis_button(name, caption)

        self._colour_button('text_color', 'A')
        self._colour_button('fill_color', None)
        self._icon_button('style_preset', self._open_presets)
        self._icon_button('clear_style', lambda: self._apply('reset', None))

    def _new_button(self, name: str, **options) -> ctk.CTkButton:
        """One button in the group, captioned and remembered."""
        button = ctk.CTkButton(
            self, width=self.button_size, height=self.button_size,
            fg_color='transparent', hover_color=theme.MENU_HOVER,
            text_color=theme.MENU_TEXT, corner_radius=4, **options)
        button.tooltip_widget = attach_tooltip(button, self.CAPTIONS[name])
        self.buttons[name] = button
        return button

    def _emphasis_button(self, name: str, caption: str):
        """
        A toggle, captioned with the letter it stands for.

        DEVELOPMENT NOTES:
        ------------------
        A letter rather than a drawing, and set in the style it applies: a
        bold B, an italic I, an underlined U. Every word processor ever
        written does this, so it needs no learning - and a drawn glyph at 20
        pixels would be less legible than the letter itself.
        """
        font = ctk.CTkFont(
            size=14,
            weight='bold' if name == 'bold' else 'normal',
            slant='italic' if name == 'italic' else 'roman',
            underline=name == 'underline')

        button = self._new_button(
            name, text=caption, font=font,
            command=lambda: self._toggle(name))
        button.pack(side='left', padx=1, pady=2)

    def _colour_button(self, name: str, caption: Optional[str]):
        """
        A colour chooser, with the colour it last applied shown beneath it.

        DEVELOPMENT NOTES:
        ------------------
        The bar under the button is the whole point of the control: it says
        what pressing it again would apply, which is what makes the second
        row and the fortieth one press each rather than a trip through the
        palette every time.
        """
        holder = ctk.CTkFrame(self, fg_color='transparent')
        holder.pack(side='left', padx=1, pady=2)

        options = {'command': lambda: self._open_colours(name)}
        if caption is not None:
            options['text'] = caption
            options['font'] = ctk.CTkFont(size=14, weight='bold')
        else:
            options['text'] = ''
            image = self._icon_image(name)
            if image is not None:
                options['image'] = image

        button = ctk.CTkButton(
            holder, width=self.button_size, height=self.button_size - 6,
            fg_color='transparent', hover_color=theme.MENU_HOVER,
            text_color=theme.MENU_TEXT, corner_radius=4, **options)
        button.pack()
        # Kept from the garbage collector, as everywhere else a CTkImage is
        # put on a button
        button.icon_image = options.get('image')
        button.tooltip_widget = attach_tooltip(button, self.CAPTIONS[name])
        self.buttons[name] = button

        indicator = ctk.CTkFrame(holder, height=INDICATOR_HEIGHT,
                                 width=self.button_size - 8,
                                 fg_color=INDICATOR_DEFAULT)
        indicator.pack(pady=(1, 0))
        self.indicators[name] = indicator

    def _icon_button(self, name: str, command: Callable):
        """One of the two that carry a drawing rather than a letter."""
        image = self._icon_image(name)
        button = self._new_button(
            name, text='' if image is not None else '?', image=image,
            command=command)
        button.icon_image = image
        button.pack(side='left', padx=1, pady=2)

    # ---- what the controls do ------------------------------------------

    def _apply(self, kind: str, value):
        """Report a press, and never let a handler take the toolbar down."""
        if not self.enabled:
            return
        try:
            self.on_apply(kind, value)
        except Exception:
            logger.exception("Could not apply the %s change", kind)

    def _toggle(self, name: str):
        """
        Turn an emphasis on, or off if it is already on.

        DEVELOPMENT NOTES:
        ------------------
        The button shows what the selection currently is - see set_state - so
        pressing it means "make it the other thing". With a mixed selection
        the button reads as off, and pressing it turns the emphasis on for
        every selected row, which is what a reader means by pressing it.
        """
        self._apply(name, not self._active(name))

    def _active(self, name: str) -> bool:
        """Whether a toggle is currently showing as on."""
        return bool(getattr(self, f"_{name}_on", False))

    def _open_colours(self, name: str):
        """Open the palette for the ink or for the fill."""
        if not self.enabled:
            return
        colours = TEXT_COLOURS if name == 'text_color' else FILL_COLOURS
        SwatchPopup(self.buttons[name], colours,
                    lambda colour: self._apply(name, colour))

    def _open_presets(self):
        """
        Offer the combined styles, each shown as it will look.

        DEVELOPMENT NOTES:
        ------------------
        Every preset is a preview row - a badge, its name, and a chip drawn
        in the preset's own colours and emphasis - so a reader picks by sight
        rather than applying one to find out what it is; see issue #9. The
        chip is built from the same TaskStyle the click applies, so the two
        cannot disagree.

        A Default entry heads the list, and clearing formatting is what it
        does. Trying a preset and putting it back was a trip out to the
        Clear button beside the menu, which is several clicks from where the
        eye already is; one at the top of the same list is where it is looked
        for. See issue #10.
        """
        if not self.enabled:
            return
        from gantt_app.views.toolbar import CTkDropdownMenu

        button = self.buttons['style_preset']

        default_glyph, default_colour = DEFAULT_BADGE
        items = [{
            "type": "preview",
            "text": "Default (no style)",
            "badge": default_glyph,
            "badge_color": default_colour,
            "preview": {"sample": "Sample"},
            "command": (lambda: self._apply('reset', None)),
        }, {"type": "separator"}]

        for name, style in PRESETS:
            glyph, colour = preset_badge(name)
            items.append({
                "type": "preview",
                "text": name,
                "badge": glyph,
                "badge_color": colour,
                "preview": {
                    "sample": "Sample",
                    "fill": style.fill_color,
                    "text_color": style.text_color,
                    "bold": bool(style.bold),
                    "italic": bool(style.italic),
                    "underline": bool(style.underline),
                },
                "command": (lambda s=style: self._apply('preset', s)),
            })

        menu = CTkDropdownMenu(self, items=items)
        menu.geometry(f"+{button.winfo_rootx()}"
                      f"+{button.winfo_rooty() + button.winfo_height() + 2}")

    # ---- what the controls show ----------------------------------------

    def set_state(self, enabled: bool, resolved: Optional[ResolvedStyle]):
        """
        Show what the selection is, and whether there is one at all.

        PARAMETERS:
        -----------
        enabled : bool
            Whether anything is selected in the task list.
        resolved : Optional[ResolvedStyle]
            What the selection looks like now, or None when nothing is
            selected. Where selected rows disagree, the toolbar passes the
            common ground - see Toolbar._selected_style.
        """
        self.enabled = bool(enabled)
        state = tk.NORMAL if self.enabled else tk.DISABLED

        for name, button in self.buttons.items():
            try:
                button.configure(state=state)
            except tk.TclError:
                continue

        for name in ('bold', 'italic', 'underline'):
            on = bool(resolved and getattr(resolved, name))
            setattr(self, f"_{name}_on", on)
            self._show_toggle(name, on)

        self._show_indicator('text_color', resolved.text_color if resolved else None)
        self._show_indicator('fill_color', resolved.fill_color if resolved else None)

    def _show_toggle(self, name: str, on: bool):
        """
        Give an active toggle a frame, so it reads as pressed.

        A button that applies a style it is already showing has to look
        different from one that would apply it, or the row's state is only
        discoverable by pressing.
        """
        button = self.buttons.get(name)
        if button is None:
            return
        try:
            button.configure(
                fg_color=theme.MENU_HOVER if on else 'transparent')
        except tk.TclError:
            pass

    def _show_indicator(self, name: str, colour: Optional[str]):
        """Paint the bar under a colour button with what it would apply."""
        indicator = self.indicators.get(name)
        if indicator is None:
            return
        try:
            indicator.configure(fg_color=colour or INDICATOR_DEFAULT)
        except tk.TclError:
            pass
