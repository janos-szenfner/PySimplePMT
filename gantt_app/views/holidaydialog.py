"""
Choosing whose public holidays the plan observes.

WHY THIS MODULE EXISTS:
======================
A project scheduled across several countries is not scheduled against one
calendar. A task worked in Hungary and Germany at once cannot run on either
country's national day, and which days those are is not something anybody should be
typing into a holiday list by hand - about half of them move with Easter.

This is the dialog for picking the countries. The rule it applies is the
union: a date that is a public holiday in *any* selected country is a
non-working day for the whole plan.

That is the conservative reading and the one a plan spanning several countries
needs - work does not happen on a day half the team is off.

Every country the `holidays` package knows is offered - around 250 of them -
with a search box to find one, and the 27 EU member states behind a single
button for the case this was first written for.

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
from gantt_app.workdaycalendar import (
    EU_COUNTRIES, holidays_available, split_country, subdivisions,
    supported_countries,
)
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


class HolidayDialog(ctk.CTkToplevel):
    """
    The country picker.

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

    GEOMETRY = "520x620"
    MINSIZE = (420, 360)

    #: Two columns of countries, so the list does not need a longer scroll
    #: than it has to.
    COLUMNS = 2

    #: How much has to be typed before the search reaches the regions.
    #:
    #: A single letter matches most of the thousand of them, and building
    #: that many check boxes takes half a second - a stutter on the first
    #: keystroke of every search. Two letters is not a restriction anybody
    #: notices and cuts the worst case to a handful.
    REGION_SEARCH_MINIMUM = 2

    def __init__(self, master, selected: Sequence[str],
                 on_apply: Callable[[List[str]], None]):
        super().__init__(master)

        self.on_apply = on_apply
        self.checkboxes = {}

        self.title("Public Holiday Calendar")
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

        ctk.CTkLabel(header, text="Observe public holidays in:",
                     font=ctk.CTkFont(size=14, weight="bold")
                     ).pack(side=tk.LEFT)

        batch = ctk.CTkFrame(header, fg_color='transparent')
        batch.pack(side=tk.RIGHT)
        ctk.CTkButton(batch, text="EU", width=44, height=24,
                      command=self.select_eu).pack(side=tk.LEFT, padx=2)
        ctk.CTkButton(batch, text="All", width=44, height=24,
                      command=self.select_all).pack(side=tk.LEFT, padx=2)
        ctk.CTkButton(batch, text="Clear", width=52, height=24,
                      command=self.clear_all).pack(side=tk.LEFT, padx=2)

        self.search_var = ctk.StringVar()
        self.search_var.trace_add('write', self._apply_filter)
        search = ctk.CTkEntry(self, textvariable=self.search_var,
                              placeholder_text="Search by country or code...")
        search.pack(fill=tk.X, padx=15, pady=(10, 0))

        self.summary_label = ctk.CTkLabel(
            self, anchor=tk.W, justify=tk.LEFT, text="",
            text_color="#6b7280",
        )
        self.summary_label.pack(fill=tk.X, padx=15, pady=(6, 0))

        if not holidays_available():
            # Said plainly and up front. Ticking a page of boxes and finding
            # out afterwards that nothing moved is the worst version of this.
            ctk.CTkLabel(
                self, anchor=tk.W, justify=tk.LEFT, wraplength=380,
                text=("The 'holidays' package is not installed, so these "
                      "dates cannot be worked out. Your selection is saved "
                      "with the project and takes effect once you run: "
                      "pip install holidays"),
                text_color="#b45309",
            ).pack(fill=tk.X, padx=15, pady=(6, 0))

    def _build_countries(self, chosen):
        """
        A tick box per country, in two columns.

        DEVELOPMENT NOTES:
        ------------------
        Every box is built once and then shown or hidden as the search
        narrows the list, rather than the list being rebuilt on each
        keystroke. Rebuilding would throw away the variables, and with them
        every tick the user had made outside the current search - so
        searching for one country would silently clear the rest.
        """
        self.scroller = ctk.CTkScrollableFrame(self)
        self.scroller.pack(fill=tk.BOTH, expand=True, padx=15, pady=(6, 10))

        for column in range(self.COLUMNS):
            self.scroller.grid_columnconfigure(column, weight=1, uniform='cty')

        #: Every country, in display order, so filtering can re-grid them
        self.rows = []

        for code, name in supported_countries().items():
            self.rows.append(self._row(code, f"{name} ({code})",
                                       f"{name} {code}".lower(), chosen))

        # The regions, which only appear when they are searched for or
        # already selected; see _apply_filter.
        #
        # Their *names* are indexed up front - a thousand of them takes a
        # thirtieth of a second - so the search can find one without its
        # country being on screen. Their *boxes* are built a country at a
        # time, because a thousand check boxes is a dialog that takes
        # seconds to open.
        self.region_rows = {}
        self.region_index = self._index_regions()
        for code in self._countries_with_regions(chosen):
            self._build_regions(code, chosen)

        self._apply_filter()

    def _index_regions(self):
        """
        Every region's searchable text, without building anything.

        RETURNS:
        --------
        Dict[str, str]
            Country code to the text of all its regions, lower case. Enough
            to answer "does this search touch this country's regions", which
            is what decides whether its boxes are worth building.
        """
        index = {}
        for country, name in supported_countries().items():
            regions = subdivisions(country)
            if not regions:
                continue
            index[country] = ' '.join(
                f"{name} {region} {code} {country}-{code}"
                for code, region in regions.items()
            ).lower()
        return index

    def _row(self, code, label, haystack, chosen, indent=0):
        """One tick box, and the strings the search matches it on."""
        variable = ctk.BooleanVar(value=code in chosen)
        variable.trace_add('write', lambda *_args: self._update_count())
        box = ctk.CTkCheckBox(self.scroller, text=label, variable=variable)
        self.checkboxes[code] = variable
        return (code, haystack, box, indent)

    def _countries_with_regions(self, chosen):
        """
        Which countries' regions are worth building up front.

        Everything already selected, so a plan that observes Bavaria opens
        showing Bavaria rather than an unticked Germany. The rest are built
        when the search first asks for them.
        """
        return sorted({split_country(entry)[0] for entry in chosen})

    def _build_regions(self, country, chosen=()):
        """
        The regions of one country, built once and kept.

        DEVELOPMENT NOTES:
        ------------------
        Lazy, because there are around a thousand of these across the seventy
        countries that have them, and a thousand check boxes is a dialog that
        takes seconds to open. Only the countries a reader actually looks at
        are built.
        """
        if country in self.region_rows:
            return self.region_rows[country]

        names = supported_countries()
        rows = []
        for code, name in subdivisions(country).items():
            entry = f"{country}-{code}"
            label = f"    {name} ({entry})"
            haystack = f"{names.get(country, '')} {name} {entry}".lower()
            rows.append(self._row(entry, label, haystack, chosen, indent=1))

        self.region_rows[country] = rows
        return rows

    def _apply_filter(self, *_args):
        """
        Show the countries matching the search, and lay them out again.

        Matched on the name and on the code, so both "germany" and "de"
        find Germany - a reader who knows the code should not have to
        remember how the country is spelt here.
        """
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return

        needle = self.search_var.get().strip().lower()

        # A search reaches the regions as well, which is what makes them
        # findable without a page of expanders: typing a country's name
        # brings its regions out under it, and typing a region's name finds
        # it on its own. The boxes for a country are built the first time a
        # search asks for them and kept from then on.
        if len(needle) >= self.REGION_SEARCH_MINIMUM:
            for country, haystack in self.region_index.items():
                if country in self.region_rows:
                    continue
                if needle in haystack:
                    self._build_regions(country)

        shown = 0
        for code, haystack, box, indent in self._visible_rows(needle):
            box.grid(row=shown // self.COLUMNS, column=shown % self.COLUMNS,
                     sticky=tk.W, padx=6 + indent * 18, pady=4)
            shown += 1

        self.shown_count = shown
        self._update_count()

    def _all_rows(self):
        """Every row built so far, countries and regions together."""
        for row in self.rows:
            yield row
            for region in self.region_rows.get(row[0], ()):
                yield region

    def _visible_rows(self, needle):
        """
        The rows the current search should show, in order.

        A region shows when the search matches it, when it matches its
        country - so the country's regions come out beneath it - or when it
        is already ticked, so a selection is never hidden from the person who
        made it.
        """
        for row in self._all_rows():
            code, haystack, box, _indent = row
            matched = not needle or needle in haystack
            is_region = split_country(code)[1] is not None

            if is_region and not needle and not self.checkboxes[code].get():
                box.grid_remove()
                continue
            if matched or (is_region and self.checkboxes[code].get()):
                yield row
            else:
                box.grid_remove()

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

    def select_eu(self):
        """
        Tick the 27 EU member states, and nothing else.

        The list this dialog used to be, kept as one press because a plan
        worked across the union is the case it was written for.
        """
        for code, variable in self.checkboxes.items():
            variable.set(code in EU_COUNTRIES)

    def select_all(self):
        """
        Tick everything the search is showing.

        The search rather than the whole list: with a couple of hundred
        countries on offer, "All" against an unfiltered list is a press
        nobody means, and against a search for "united" it is exactly what
        they mean.
        """
        shown = {code for code, _haystack, box, _indent in self._all_rows()
                 if box.winfo_manager()}
        for code, variable in self.checkboxes.items():
            if code in shown:
                variable.set(True)

    def clear_all(self):
        """Untick every country, wherever it is in the list."""
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
        available = len(self.checkboxes)
        shown = getattr(self, 'shown_count', available)

        if not chosen:
            text = ("No countries selected: weekends only, and no public "
                    "holidays.")
        else:
            text = (f"{len(chosen)} selected. A date that is a holiday in any "
                    f"of them is a non-working day.")

        if shown < available:
            text += f"  Showing {shown} of {available}."
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


def choose_holidays(master, selected: Sequence[str],
                    on_apply: Callable[[List[str]], None]
                    ) -> Optional[HolidayDialog]:
    """
    Open the country picker.

    RETURNS:
    --------
    Optional[HolidayDialog]
        The dialog, or None when it could not be built. A dialog that fails to
        open should not take the menu that opened it down with it.
    """
    try:
        return HolidayDialog(master, selected, on_apply)
    except Exception:
        logger.exception("Could not open the holiday dialog")
        return None
