"""
Choosing whose public holidays the plan observes.

WHY THIS MODULE EXISTS:
======================
A project scheduled across the EU is not scheduled against one calendar. A
task worked in Hungary and Germany at once cannot run on either country's
national day, and which days those are is not something anybody should be
typing into a holiday list by hand - about half of them move with Easter.

This is the dialog for picking the countries. The rule it applies is the
union: a date that is a public holiday in *any* selected country is a
non-working day for the whole plan. That is the conservative reading and the
one a plan spanning several countries needs - work does not happen on a day
half the team is off.

DEVELOPMENT NOTES:
------------------
The dialog only chooses country codes. What a code means, and every piece of
arithmetic that follows from it, belongs to gantt_app.workdaycalendar - see the
note on WorkingCalendar about why there is one calendar rather than one per
source of non-working day. Applying the choice therefore sets a list of codes
on the project's calendar and reschedules; nothing here knows what a holiday
is.

The `holidays` package that resolves the codes is an optional dependency, like
openpyxl for the spreadsheets. Without it the dialog still opens and still
saves the selection - so a plan carrying one is not silently emptied - but it
says on the face of it that the choice will not take effect until the package
is installed.
"""

import tkinter as tk
from typing import Callable, List, Optional, Sequence

import customtkinter as ctk

from gantt_app.views.modal import grab_when_visible
from gantt_app.workdaycalendar import EU_COUNTRIES, holidays_available
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


class EUHolidayDialog(ctk.CTkToplevel):
    """
    The EU country picker.

    PARAMETERS:
    -----------
    master : widget
        Window to open over.
    selected : Sequence[str]
        The country codes currently observed, which open ticked.
    on_apply : Callable[[List[str]], None]
        Called with the chosen codes when Apply is pressed. Not called at all
        when the dialog is cancelled.

    DEVELOPMENT NOTES:
    ------------------
    Laid out in three bands - a header, the scrolling list, the buttons - with
    the list the only one that grows. Packing the buttons before the list is
    what keeps them on screen when the window is made short: pack gives space
    to what it placed first, so a list packed first squeezes the buttons off
    the bottom edge and the dialog cannot be applied at all.
    """

    GEOMETRY = "420x560"
    MINSIZE = (360, 320)

    #: Two columns of countries, so 27 of them do not need a long scroll.
    COLUMNS = 2

    def __init__(self, master, selected: Sequence[str],
                 on_apply: Callable[[List[str]], None]):
        super().__init__(master)

        self.on_apply = on_apply
        self.checkboxes = {}

        self.title("EU Holiday Calendar Selection")
        self.geometry(self.GEOMETRY)
        self.minsize(*self.MINSIZE)
        self.transient(master)
        # Deferred: grabbing before the window is mapped fails on X11
        grab_when_visible(self)
        self.protocol("WM_DELETE_WINDOW", self.cancel)

        chosen = {str(code).strip().upper() for code in selected}

        self._build_header()
        self._build_buttons()
        self._build_countries(chosen)
        self._update_count()

        self.center_window()

    # ---- the parts of the dialog ---------------------------------------

    def _build_header(self):
        """The title line, the batch buttons, and what the rule is."""
        header = ctk.CTkFrame(self, fg_color='transparent')
        header.pack(fill=tk.X, padx=15, pady=(15, 0))

        ctk.CTkLabel(header, text="Select EU countries:",
                     font=ctk.CTkFont(size=14, weight="bold")
                     ).pack(side=tk.LEFT)

        batch = ctk.CTkFrame(header, fg_color='transparent')
        batch.pack(side=tk.RIGHT)
        ctk.CTkButton(batch, text="All", width=52, height=24,
                      command=self.select_all).pack(side=tk.LEFT, padx=2)
        ctk.CTkButton(batch, text="Clear", width=52, height=24,
                      command=self.clear_all).pack(side=tk.LEFT, padx=2)

        self.summary_label = ctk.CTkLabel(
            self, anchor=tk.W, justify=tk.LEFT, text="",
            text_color="#6b7280",
        )
        self.summary_label.pack(fill=tk.X, padx=15, pady=(6, 0))

        if not holidays_available():
            # Said plainly and up front. Ticking 27 boxes and finding out
            # afterwards that nothing moved is the worst version of this.
            ctk.CTkLabel(
                self, anchor=tk.W, justify=tk.LEFT, wraplength=380,
                text=("The 'holidays' package is not installed, so these "
                      "dates cannot be worked out. Your selection is saved "
                      "with the project and takes effect once you run: "
                      "pip install holidays"),
                text_color="#b45309",
            ).pack(fill=tk.X, padx=15, pady=(6, 0))

    def _build_countries(self, chosen):
        """A tick box per member state, in two columns."""
        self.scroller = ctk.CTkScrollableFrame(self)
        self.scroller.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)

        for column in range(self.COLUMNS):
            self.scroller.grid_columnconfigure(column, weight=1, uniform='cty')

        for index, (code, name) in enumerate(sorted(EU_COUNTRIES.items(),
                                                    key=lambda item: item[1])):
            variable = ctk.BooleanVar(value=code in chosen)
            variable.trace_add('write', lambda *_args: self._update_count())
            box = ctk.CTkCheckBox(self.scroller, text=f"{name} ({code})",
                                  variable=variable)
            box.grid(row=index // self.COLUMNS, column=index % self.COLUMNS,
                     sticky=tk.W, padx=6, pady=5)
            self.checkboxes[code] = variable

    def _build_buttons(self):
        """Apply and Cancel, along the bottom."""
        footer = ctk.CTkFrame(self, fg_color='transparent')
        footer.pack(fill=tk.X, side=tk.BOTTOM, padx=15, pady=15)

        ctk.CTkButton(footer, text="Apply", width=110,
                      command=self.apply).pack(side=tk.RIGHT, padx=5)
        ctk.CTkButton(footer, text="Cancel", width=110, fg_color='transparent',
                      border_width=1, command=self.cancel).pack(side=tk.RIGHT)

    def center_window(self):
        """Place the dialog over the middle of the screen."""
        self.update_idletasks()
        width, _, height = self.GEOMETRY.partition('x')
        try:
            width, height = int(width), int(height)
        except ValueError:
            return
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    # ---- what the buttons do -------------------------------------------

    def selection(self) -> List[str]:
        """The country codes currently ticked, in a stable order."""
        return sorted(code for code, variable in self.checkboxes.items()
                      if variable.get())

    def select_all(self):
        """Tick every member state."""
        for variable in self.checkboxes.values():
            variable.set(True)

    def clear_all(self):
        """Untick every member state, leaving weekends alone."""
        for variable in self.checkboxes.values():
            variable.set(False)

    def _update_count(self):
        """Say how many are ticked, and what none of them means."""
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return

        chosen = self.selection()
        if not chosen:
            text = ("No countries selected: weekends only, and no public "
                    "holidays.")
        else:
            text = (f"{len(chosen)} selected. A date that is a holiday in any "
                    f"of them is a non-working day.")
        self.summary_label.configure(text=text)

    def apply(self):
        """Hand the selection back and close."""
        chosen = self.selection()
        logger.info("Observing public holidays for %s",
                    ', '.join(chosen) if chosen else 'no countries')
        self.destroy()
        if self.on_apply:
            self.on_apply(chosen)

    def cancel(self):
        """Close without changing anything."""
        self.destroy()


def choose_eu_holidays(master, selected: Sequence[str],
                       on_apply: Callable[[List[str]], None]
                       ) -> Optional[EUHolidayDialog]:
    """
    Open the country picker.

    RETURNS:
    --------
    Optional[EUHolidayDialog]
        The dialog, or None when it could not be built. A dialog that fails to
        open should not take the menu that opened it down with it.
    """
    try:
        return EUHolidayDialog(master, selected, on_apply)
    except Exception:
        logger.exception("Could not open the EU holiday dialog")
        return None
