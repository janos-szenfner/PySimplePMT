"""
The progress group on the icon bar: the five presets, and Mark on Track.

WHY THIS MODULE EXISTS:
======================
Reporting on a plan is a weekly job done against a list of forty rows, and
almost none of it involves choosing a number. A task is not started, it is
underway, or it is done, and the rest of the time what is wanted is "this is
where it should be by now". Typing a percentage into a task editor, one row at
a time, is the slowest possible way to say any of that.

So the five thresholds anybody actually uses are one press each, and Mark on
Track works the rest out from the dates.

WHAT MARK ON TRACK MEANS:
=========================
The completion a task would have if it were running exactly to plan, measured
against today. Work whose finish has passed is done, work that has not started
is at nothing, and work in the middle is at the share of its working days that
have gone by; see Project.progress_on_track, which does the arithmetic.

It is a statement about the schedule rather than about the work, so it is
offered rather than applied: it fills in the reporting for the rows nobody has
had to think about, leaving the ones that are actually ahead or behind to be
typed in.

DEVELOPMENT NOTES:
------------------
Like the formatting group beside it, this holds no state about the plan and
changes nothing. It reports which control was pressed; what that means for a
selection is the toolbar's business.
"""

import tkinter as tk
from typing import Callable, Optional

import customtkinter as ctk

from gantt_app import theme
from gantt_app.utils.log import get_logger
from gantt_app.views.tooltip import attach as attach_tooltip

logger = get_logger(__name__)


#: The thresholds on the strip, in the order they appear.
#:
#: Held here rather than being typed into the layout, so the row and the
#: captions cannot drift apart - which is what happened to the icon bar's own
#: tooltips before they were driven from one table.
PRESETS = (0, 25, 50, 75, 100)

#: What each preset says on hover. The percentage is on the button; what a
#: reader wants from the hover is what that percentage means for the plan.
PRESET_CAPTIONS = {
    0: "Not started - set the selected tasks to 0%",
    25: "A quarter done - set the selected tasks to 25%",
    50: "Half done - set the selected tasks to 50%",
    75: "Three quarters done - set the selected tasks to 75%",
    100: "Complete - set the selected tasks to 100%",
}

#: The two scopes Mark on Track can be asked for.
SCOPE_SELECTED = 'selected'
SCOPE_PROJECT = 'project'

SCOPE_LABELS = (
    ("Selected Tasks Only", SCOPE_SELECTED),
    ("Entire Project", SCOPE_PROJECT),
)


class ProgressGroup(ctk.CTkFrame):
    """
    Five percentages and a way to work the sixth out from the dates.

    PARAMETERS:
    -----------
    master : widget
        The icon toolbar this sits in.
    on_preset : Callable[[int], None]
        Given the percentage pressed.
    on_mark_on_track : Callable[[str], None]
        Given the scope: SCOPE_SELECTED or SCOPE_PROJECT.
    button_size : int
        Matched to the icons either side so the row stays one height.
    icon_image : Callable[[str], object]
        How to get a drawing, from the row's own cache.
    """

    #: How wide a percentage button is. Enough for "100%" and no wider: five
    #: of these sit in a row that already has a good deal in it.
    PRESET_WIDTH = 42

    #: The chevron that opens the scope menu, beside the main button.
    CHEVRON_WIDTH = 18

    def __init__(self, master, on_preset: Callable, on_mark_on_track: Callable,
                 button_size: int = 32, icon_image: Optional[Callable] = None,
                 **kwargs):
        super().__init__(master, fg_color='transparent', **kwargs)

        self.on_preset = on_preset
        self.on_mark_on_track = on_mark_on_track
        self.button_size = button_size
        self._icon_image = icon_image or (lambda _name: None)

        #: Every control that needs a selection to act on.
        self.buttons = {}
        #: Whether anything is selected; see set_state.
        self.enabled = False

        self._build()
        self.set_state(False)

    # ---- building -------------------------------------------------------

    def _build(self):
        """The five thresholds, then the schedule alignment beside them."""
        for percent in PRESETS:
            self._preset_button(percent)

        self._separator()
        self._mark_on_track_buttons()

    def _separator(self):
        """A hairline between the presets and Mark on Track."""
        line = ctk.CTkFrame(self, width=1, height=self.button_size - 10,
                            fg_color=theme.ICON_SEPARATOR)
        line.pack(side='left', padx=4, pady=2)

    def _preset_button(self, percent: int):
        """One threshold, captioned with the number it sets."""
        button = ctk.CTkButton(
            self, text=f"{percent}%", width=self.PRESET_WIDTH,
            height=self.button_size, fg_color='transparent',
            hover_color=theme.MENU_HOVER, text_color=theme.MENU_TEXT,
            corner_radius=4, font=ctk.CTkFont(size=12),
            command=lambda value=percent: self._preset(value))
        button.pack(side='left', padx=1, pady=2)
        button.tooltip_widget = attach_tooltip(button, PRESET_CAPTIONS[percent])
        self.buttons[f"preset_{percent}"] = button

    def _mark_on_track_buttons(self):
        """
        The main press, and the chevron that offers the other scope.

        DEVELOPMENT NOTES:
        ------------------
        Two buttons rather than one that does both. A single button opening
        a menu would put a menu between the reader and the thing they press
        every week; a single button that only acted would leave no way to
        reach the whole plan at once.

        The chevron stays live with nothing selected, because Entire Project
        does not need a selection - greying it out would hide the one scope
        that still applies.
        """
        image = self._icon_image('mark_on_track')
        main = ctk.CTkButton(
            self, text='' if image is not None else 'Track',
            image=image, width=self.button_size, height=self.button_size,
            fg_color='transparent', hover_color=theme.MENU_HOVER,
            text_color=theme.MENU_TEXT, corner_radius=4,
            command=lambda: self._mark(SCOPE_SELECTED))
        main.pack(side='left', padx=(1, 0), pady=2)
        main.icon_image = image
        main.tooltip_widget = attach_tooltip(
            main, "Mark on Track - set the selected tasks to where today's "
                  "date says they should be")
        self.buttons['mark_on_track'] = main

        self.scope_button = ctk.CTkButton(
            self, text="▾", width=self.CHEVRON_WIDTH,
            height=self.button_size, fg_color='transparent',
            hover_color=theme.MENU_HOVER, text_color=theme.MENU_TEXT,
            corner_radius=4, font=ctk.CTkFont(size=11),
            command=self._open_scope_menu)
        self.scope_button.pack(side='left', padx=(0, 1), pady=2)
        self.scope_button.tooltip_widget = attach_tooltip(
            self.scope_button, "Mark on Track - choose what to apply it to")

    # ---- what the controls do ------------------------------------------

    def _preset(self, percent: int):
        """Report a threshold, and never let a handler take the row down."""
        if not self.enabled:
            return
        try:
            self.on_preset(percent)
        except Exception:
            logger.exception("Could not set the progress to %d%%", percent)

    def _mark(self, scope: str):
        """Report a Mark on Track, for one scope or the other."""
        if scope == SCOPE_SELECTED and not self.enabled:
            return
        try:
            self.on_mark_on_track(scope)
        except Exception:
            logger.exception("Could not mark %s on track", scope)

    def _open_scope_menu(self):
        """Offer the two scopes under the chevron."""
        from gantt_app.views.toolbar import CTkDropdownMenu

        items = [{"text": label,
                  "command": (lambda value=scope: self._mark(value))}
                 for label, scope in SCOPE_LABELS]

        menu = CTkDropdownMenu(self, items=items)
        menu.geometry(
            f"+{self.scope_button.winfo_rootx()}"
            f"+{self.scope_button.winfo_rooty() + self.scope_button.winfo_height() + 2}")

    # ---- what the controls show ----------------------------------------

    def set_state(self, enabled: bool):
        """
        Grey the group out when there is nothing selected to act on.

        DEVELOPMENT NOTES:
        ------------------
        The chevron is deliberately left alone; see _mark_on_track_buttons.
        """
        self.enabled = bool(enabled)
        state = tk.NORMAL if self.enabled else tk.DISABLED

        for name, button in self.buttons.items():
            try:
                button.configure(state=state)
            except tk.TclError:
                continue
