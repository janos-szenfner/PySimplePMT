"""
Which days the plan works: whose public holidays, and which dates by hand.

WHY THIS MODULE EXISTS:
======================
A project scheduled across several countries is not scheduled against one
calendar. A task worked in Hungary and Germany at once cannot run on either
country's national day, and which days those are is not something anybody should be
typing into a holiday list by hand - about half of them move with Easter.

So the first half of this is the country picker. The rule it applies is the
union: a date that is a public holiday in *any* selected country is a
non-working day for the whole plan.

That is the conservative reading and the one a plan spanning several countries
needs - work does not happen on a day half the team is off.

Every country the `holidays` package knows is offered - around 250 of them -
with a search box to find one, and the 27 EU member states behind a single
button for the case this was first written for.

The second half is the part no country list can answer. Real plans work
Saturdays to make a deadline, and close for a week in August that no public
holiday knows about. Those are decisions about one named date, not rules, and
the only place they can come from is the person running the plan. The
overrides tab is where they say so: a date, worked or not worked, and why.

The two live in one window under two tabs because they answer the same
question - is this day worked - and a reader who found the wrong answer should
not have to guess which of two menu entries holds the fix.

DEVELOPMENT NOTES:
------------------
The dialog chooses country codes and date rulings. What either means, and
every piece of arithmetic that follows, belongs to gantt_app.workdaycalendar -
see the note on WorkingCalendar about why there is one calendar rather than
one per source of non-working day. Applying sets codes and overrides on the
project's calendar and reschedules; nothing here knows what a holiday is, or
that an override outranks one.

Both tabs are applied together, by Apply, and neither touches the project
before then. Recalculating an override the moment it was added - and leaving
the countries to wait for Apply - would make one Cancel button mean two
different things, and the one it did not undo would be the one nobody expected.

The `holidays` package that resolves the codes is an optional dependency, like
openpyxl for the spreadsheets. Without it the dialog still opens and still
saves the selection - so a plan carrying one is not silently emptied - but it
says on the face of it that the choice will not take effect until the package
is installed. The overrides tab is unaffected: a date named by hand needs
nothing installed to be honoured.
"""

import tkinter as tk
from tkinter import simpledialog
from datetime import date, datetime
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Set

import customtkinter as ctk

from gantt_app.views.buttonstyle import secondary_button
from gantt_app.views.datepicker import DateEntry
from gantt_app.views.modal import grab_when_visible
from gantt_app.calendarregistry import (
    CalendarRegistry, NamedCalendar, PROJECT_DEFAULT_LABEL, describe_week,
)
from gantt_app.views import dialogs as messagebox
from gantt_app.workdaycalendar import (
    DEFAULT_NON_WORKING_DAYS, REGION_ORDER, DateOverride, EU_COUNTRIES,
    WorkingCalendar, holidays_available, region_of, split_country,
    subdivisions, supported_countries,
)
from gantt_app import theme
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


class CalendarSettingsDialog(ctk.CTkToplevel):
    """
    The country picker and the manual date overrides, under two tabs.

    PARAMETERS:
    -----------
    master : widget
        Window to open over.
    selected : Sequence[str]
        The country codes currently observed, which open ticked.
    on_apply : Callable[[List[str]], None]
        Called with the chosen codes when Apply is pressed. Not called at all
        when the dialog is cancelled.
    overrides : Sequence[DateOverride]
        The date rulings currently in force, which open listed. The dialog
        edits a copy of these, so a cancelled dialog leaves them alone.
    on_apply_overrides : Optional[Callable[[List[DateOverride]], None]]
        Called with the full list of rulings when Apply is pressed, after the
        countries. The full list rather than the changes, because a deletion
        here has to become a deletion there - see Project.set_date_overrides.
        Omitted by a caller that only wants the countries.

    DEVELOPMENT NOTES:
    ------------------
    Laid out in three bands - a header, the tabs, the buttons - with the tabs
    the only one that grows. Packing the buttons before the tabs is what keeps
    them on screen when the window is made short: pack gives space to what it
    placed first, so a list packed first squeezes the buttons off the bottom
    edge and the dialog cannot be applied at all. The same holds inside each
    tab, where the scrolling part is packed last for the same reason.
    """

    GEOMETRY = "620x660"
    #: Wide enough for the selector row: the calendar menu plus New, Rename
    #: and Delete come to a little under 500, and a narrower window clipped
    #: Delete off the right edge.
    MINSIZE = (580, 420)

    #: What the tabs are called. Named here because both the builders and
    #: the tests reach for them, and a tab looked up by a mistyped string
    #: fails as a KeyError deep inside customtkinter.
    TAB_HOLIDAYS = "National Holidays"
    TAB_OVERRIDES = "Manual Overrides"
    TAB_WEEK = "Working Week"

    #: The two things an override can say, as the type selector spells them.
    WORKING_LABEL = "Working Day"
    NON_WORKING_LABEL = "Non-Working Day"

    #: Green for a day worked, red for one not, in (light, dark) pairs as
    #: customtkinter takes them - a single value is legible in one appearance
    #: mode and not the other.
    WORKING_COLOR = ('#15803d', '#4ade80')
    NON_WORKING_COLOR = ('#b91c1c', '#f87171')

    #: Two columns of countries, so the list does not need a longer scroll
    #: than it has to.
    COLUMNS = 2

    #: The weekdays, in the order a week is read and by the index
    #: date.weekday() gives each. Monday first, which is what the calendar
    #: counts from - a list starting on Sunday would put the two out of step
    #: everywhere the index is used.
    WEEKDAYS = (
        (0, "Monday"), (1, "Tuesday"), (2, "Wednesday"), (3, "Thursday"),
        (4, "Friday"), (5, "Saturday"), (6, "Sunday"),
    )

    #: How much has to be typed before the search reaches the regions.
    #:
    #: A single letter matches most of the thousand of them, and building
    #: that many check boxes takes half a second - a stutter on the first
    #: keystroke of every search. Two letters is not a restriction anybody
    #: notices and cuts the worst case to a handful.
    REGION_SEARCH_MINIMUM = 2

    def __init__(self, master, selected: Sequence[str],
                 on_apply: Callable[[List[str]], None],
                 overrides: Sequence[DateOverride] = (),
                 on_apply_overrides: Optional[
                     Callable[[List[DateOverride]], None]] = None,
                 non_working_days: Optional[Iterable[int]] = None,
                 on_apply_working_week: Optional[
                     Callable[[Set[int]], None]] = None,
                 on_applied: Optional[Callable[[], None]] = None,
                 registry: Optional[CalendarRegistry] = None,
                 on_apply_calendars: Optional[
                     Callable[[List[NamedCalendar]], None]] = None):
        super().__init__(master)

        self.on_apply = on_apply
        self.on_apply_overrides = on_apply_overrides
        self.on_apply_working_week = on_apply_working_week
        self.on_applied = on_applied
        self.on_apply_calendars = on_apply_calendars
        self.checkboxes = {}

        #: The named calendars, edited as copies. The dialog never writes to
        #: the project's own objects, so Cancel needs to do nothing but close
        #: - the same reason the overrides are copied below.
        self.registry = CalendarRegistry(
            NamedCalendar(id=named.id, name=named.name,
                          calendar=WorkingCalendar.from_dict(
                              named.calendar.to_dict()))
            for named in (registry or ())
        )

        #: Which calendar the three tabs are currently showing. None is the
        #: project's own, which is what the dialog opens on and what it shows
        #: when a plan holds no named calendars at all.
        self.current_calendar_id: Optional[str] = None

        #: The project's own calendar, as an editable copy. Assembled from
        #: the three pieces the caller passes rather than taken whole,
        #: because those three are what the callbacks hand back and what the
        #: dialog has always been given.
        self._default_working = WorkingCalendar(
            non_working_days=(DEFAULT_NON_WORKING_DAYS
                              if non_working_days is None
                              else {int(day) for day in non_working_days}),
            countries=[str(code).strip().upper() for code in selected],
            overrides=list(overrides or ()),
        )

        #: The rulings as the dialog currently has them, keyed by date. A
        #: working copy: the project keeps its own until Apply, so Cancel
        #: needs to do nothing more than close.
        self.overrides: Dict[date, DateOverride] = {
            override.override_date: override for override in (overrides or ())
        }

        #: The week the dialog opens on, as non-working weekday indices.
        week = (set(DEFAULT_NON_WORKING_DAYS) if non_working_days is None
                else {int(day) for day in non_working_days})

        self.title("Calendar Settings")
        self.geometry(self.GEOMETRY)
        self.minsize(*self.MINSIZE)
        self.transient(master)
        # Deferred: grabbing before the window is mapped fails on X11
        grab_when_visible(self)
        self.protocol("WM_DELETE_WINDOW", self.cancel)

        chosen = {str(code).strip().upper() for code in selected}

        # Buttons first, then the tabs they must not be pushed off the bottom
        # by; see the note on the class.
        self._build_buttons()
        self._build_calendar_selector()
        self._build_tabs()

        self._build_header()
        self._build_countries(chosen)
        self._update_count()

        self._build_overrides_tab()
        self._refresh_override_list()

        self._build_working_week_tab(week)
        self._update_week_summary()

        self.center_window()

    def _build_tabs(self):
        """The two tabs, and the frames the rest of the dialog builds into."""
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill=tk.BOTH, expand=True, padx=15, pady=(15, 0))

        self.tab_holidays = self.tabview.add(self.TAB_HOLIDAYS)
        self.tab_overrides = self.tabview.add(self.TAB_OVERRIDES)
        self.tab_week = self.tabview.add(self.TAB_WEEK)

        # Opened on the countries, not on the week. The week is set once for
        # a plan and then left alone, while the other two are what the dialog
        # is reopened for; a rarely-touched tab in front of them would be a
        # click on every visit.
        self.tabview.set(self.TAB_HOLIDAYS)

    # ---- the parts of the dialog ---------------------------------------

    def _build_header(self):
        """The title line, the batch buttons, and what the rule is."""
        header = ctk.CTkFrame(self.tab_holidays, fg_color='transparent')
        header.pack(fill=tk.X, padx=5, pady=(5, 0))

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
        search = ctk.CTkEntry(self.tab_holidays, textvariable=self.search_var,
                              placeholder_text="Search by country or code...")
        search.pack(fill=tk.X, padx=5, pady=(10, 0))

        # Two fonts, because the label says two different kinds of thing.
        # "No countries selected" is a statement about the plan that the
        # reader has to notice - it means the calendar is weekends only - so
        # it is set apart from the ordinary running count beside it.
        self.summary_font = ctk.CTkFont(size=12)
        self.summary_warning_font = ctk.CTkFont(
            size=12, weight="bold", slant="italic", underline=True)

        self.summary_label = ctk.CTkLabel(
            self.tab_holidays, anchor=tk.W, justify=tk.LEFT, text="",
            text_color=theme.MUTED_TEXT, font=self.summary_font,
        )
        self.summary_label.pack(fill=tk.X, padx=5, pady=(6, 0))

        if not holidays_available():
            # Said plainly and up front. Ticking a page of boxes and finding
            # out afterwards that nothing moved is the worst version of this.
            ctk.CTkLabel(
                self.tab_holidays, anchor=tk.W, justify=tk.LEFT,
                wraplength=440,
                text=("The 'holidays' package is not installed, so these "
                      "dates cannot be worked out. Your selection is saved "
                      "with the project and takes effect once you run: "
                      "pip install holidays"),
                text_color=theme.WARNING_TEXT,
            ).pack(fill=tk.X, padx=5, pady=(6, 0))

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
        self.scroller = ctk.CTkScrollableFrame(self.tab_holidays)
        self.scroller.pack(fill=tk.BOTH, expand=True, padx=5, pady=(6, 5))

        for column in range(self.COLUMNS):
            self.scroller.grid_columnconfigure(column, weight=1, uniform='cty')

        #: Every country, in display order, so filtering can re-grid them
        self.rows = []

        for code, name in supported_countries().items():
            self.rows.append(self._row(code, f"{name} ({code})",
                                       f"{name} {code}".lower(), chosen))

        #: One heading per region, built once and shown or hidden as the
        #: search empties a region out; see _apply_filter.
        self.region_headings = {
            region: self._region_heading(region) for region in REGION_ORDER
        }

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

    def _region_heading(self, region: str):
        """
        The caption over one region's countries, with its rule beneath it.

        DEVELOPMENT NOTES:
        ------------------
        A frame rather than a bare label, because the rule under the caption
        is what separates one region from the next in a list two columns wide
        - a caption alone reads as another entry in the column it happens to
        start in.

        Built for every region whether or not it has anything to show. A
        search that empties a region hides the heading rather than destroying
        it, so the next keystroke has it back without rebuilding anything.
        """
        frame = ctk.CTkFrame(self.scroller, fg_color='transparent')
        ctk.CTkLabel(frame, text=region, anchor=tk.W, justify=tk.LEFT,
                     font=ctk.CTkFont(size=13, weight="bold"),
                     ).pack(fill=tk.X, anchor=tk.W)
        ctk.CTkFrame(frame, height=1, fg_color=theme.MUTED_TEXT
                     ).pack(fill=tk.X, pady=(2, 0))
        return frame

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

        self.shown_count = self._lay_out_by_region(self._visible_rows(needle))
        self._update_count()

    def _lay_out_by_region(self, rows) -> int:
        """
        Grid the visible rows under their region headings.

        PARAMETERS:
        -----------
        rows : Iterable
            The rows to show, in display order, as _visible_rows yields them.

        RETURNS:
        --------
        int
            How many countries and regions ended up on screen, which is what
            the summary line reports.

        DEVELOPMENT NOTES:
        ------------------
        Bucketing is stable, so a country's subdivisions stay directly under
        it: _visible_rows yields them adjacently and they share a region,
        their country's - see workdaycalendar.region_of, which reads the
        country out of a "DE-BY".

        A region with nothing to show has its heading hidden rather than
        left over an empty stretch of grid, which is what a search for one
        country would otherwise leave behind in the other four.
        """
        by_region = {}
        for row in rows:
            by_region.setdefault(region_of(row[0]), []).append(row)

        shown = 0
        grid_row = 0
        for region in REGION_ORDER:
            found = by_region.get(region)
            heading = self.region_headings[region]

            if not found:
                heading.grid_remove()
                continue

            heading.grid(row=grid_row, column=0, columnspan=self.COLUMNS,
                         sticky=tk.EW, padx=6,
                         pady=(12 if grid_row else 2, 4))
            grid_row += 1

            for offset, (_code, _haystack, box, indent) in enumerate(found):
                box.grid(row=grid_row + offset // self.COLUMNS,
                         column=offset % self.COLUMNS,
                         sticky=tk.W, padx=6 + indent * 18, pady=4)

            grid_row += -(-len(found) // self.COLUMNS)
            shown += len(found)

        return shown

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

    # ---- the overrides tab ---------------------------------------------

    def _build_overrides_tab(self):
        """
        The form for adding a ruling, and the list of the ones in force.

        DEVELOPMENT NOTES:
        ------------------
        The form is gridded rather than packed: three labelled controls that
        have to line up down the left edge, which is the one thing grid does
        and pack does not.
        """
        form = ctk.CTkFrame(self.tab_overrides, fg_color='transparent')
        form.pack(fill=tk.X, padx=5, pady=(5, 0))
        form.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(form, text="Override a single date:",
                     font=ctk.CTkFont(size=14, weight="bold")
                     ).grid(row=0, column=0, columnspan=3, sticky=tk.W,
                            pady=(0, 8))

        ctk.CTkLabel(form, text="Date:", anchor=tk.W).grid(
            row=1, column=0, sticky=tk.W, padx=(0, 8), pady=4)
        self.override_date_entry = DateEntry(form, date=datetime.now())
        self.override_date_entry.grid(row=1, column=1, sticky=tk.EW, pady=4)

        self.override_type_var = ctk.StringVar(value=self.WORKING_LABEL)
        self.override_type_menu = ctk.CTkOptionMenu(
            form, width=150, variable=self.override_type_var,
            values=[self.WORKING_LABEL, self.NON_WORKING_LABEL],
        )
        self.override_type_menu.grid(row=1, column=2, sticky=tk.W, padx=(8, 0),
                                     pady=4)

        ctk.CTkLabel(form, text="Reason:", anchor=tk.W).grid(
            row=2, column=0, sticky=tk.W, padx=(0, 8), pady=4)
        self.override_reason_entry = ctk.CTkEntry(
            form, placeholder_text="e.g. Saturday make-up day (optional)")
        self.override_reason_entry.grid(row=2, column=1, sticky=tk.EW, pady=4)

        ctk.CTkButton(form, text="Add Override", width=150,
                      command=self.add_override).grid(
            row=2, column=2, sticky=tk.W, padx=(8, 0), pady=4)

        # Enter in either box adds the override, so the form can be filled in
        # and committed without the mouse ever coming back.
        self.override_date_entry.entry.bind(
            '<Return>', lambda _event: self.add_override())
        self.override_reason_entry.bind(
            '<Return>', lambda _event: self.add_override())

        self.override_error_label = ctk.CTkLabel(
            self.tab_overrides, anchor=tk.W, justify=tk.LEFT, text="",
            wraplength=520, text_color=theme.WARNING_TEXT,
        )
        self.override_error_label.pack(fill=tk.X, padx=5, pady=(4, 0))

        ctk.CTkLabel(self.tab_overrides, text="Active date overrides:",
                     anchor=tk.W, font=ctk.CTkFont(size=12, weight="bold")
                     ).pack(fill=tk.X, padx=5, pady=(10, 2))

        self._build_override_headings()

        self.override_list = ctk.CTkScrollableFrame(self.tab_overrides)
        self.override_list.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

    def _build_override_headings(self):
        """
        The column titles, outside the scrolling area so they stay put.

        Inside it they would scroll away with the first few rows, which is
        exactly when a reader needs to be told which column is which.
        """
        headings = ctk.CTkFrame(self.tab_overrides, fg_color='transparent')
        headings.pack(fill=tk.X, padx=5)

        for text, width, expand in (("Date", 100, False),
                                    ("Type", 120, False),
                                    ("Reason", 0, True),
                                    ("", 40, False)):
            label = ctk.CTkLabel(headings, text=text, anchor=tk.W,
                                 text_color=theme.MUTED_TEXT,
                                 font=ctk.CTkFont(size=11, weight="bold"))
            if expand:
                label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
            else:
                label.configure(width=width)
                label.pack(side=tk.LEFT, padx=6)

    def _refresh_override_list(self):
        """
        Draw the rulings currently held, in date order.

        DEVELOPMENT NOTES:
        ------------------
        The rows are torn down and rebuilt rather than updated in place. There
        are rarely more than a couple of dozen of them and they are only
        redrawn when one is added or removed, so the simple version costs
        nothing and cannot leave a stale row behind - which the update-in-place
        version did, on the last row of the list, every time one was deleted.
        """
        for widget in self.override_list.winfo_children():
            widget.destroy()

        #: The delete buttons, by the date each removes. Kept so a test can
        #: press one without hunting through the widget tree.
        self.override_rows: Dict[date, ctk.CTkFrame] = {}

        if not self.overrides:
            ctk.CTkLabel(
                self.override_list, anchor=tk.W, justify=tk.LEFT,
                wraplength=500, text_color=theme.MUTED_TEXT,
                text=("No overrides. Weekends and the public holidays chosen "
                      "on the other tab apply as they stand."),
            ).pack(fill=tk.X, padx=6, pady=8)
            return

        for day in sorted(self.overrides):
            self._build_override_row(self.overrides[day])

    def _build_override_row(self, override: DateOverride):
        """One ruling: its date, what it says, why, and a way to drop it."""
        row = ctk.CTkFrame(self.override_list)
        row.pack(fill=tk.X, pady=2, padx=2)
        self.override_rows[override.override_date] = row

        ctk.CTkLabel(row, text=override.override_date.isoformat(), width=100,
                     anchor=tk.W, font=ctk.CTkFont(size=12, weight="bold")
                     ).pack(side=tk.LEFT, padx=6, pady=4)

        worked = override.is_working_day
        ctk.CTkLabel(row, width=120, anchor=tk.W,
                     text=(self.WORKING_LABEL if worked
                           else self.NON_WORKING_LABEL),
                     text_color=(self.WORKING_COLOR if worked
                                 else self.NON_WORKING_COLOR),
                     font=ctk.CTkFont(size=12, weight="bold")
                     ).pack(side=tk.LEFT, padx=6, pady=4)

        delete = ctk.CTkButton(
            row, text="\U0001F5D1", width=36, height=26,
            command=lambda day=override.override_date: self.remove_override(day),
        )
        delete.pack(side=tk.RIGHT, padx=6, pady=4)

        # Packed after the button so the reason yields the space rather than
        # pushing the delete button off the right edge on a long note.
        ctk.CTkLabel(row, text=override.reason, anchor=tk.W,
                     text_color=theme.MUTED_TEXT
                     ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6,
                            pady=4)

    # ---- what the overrides tab does -----------------------------------

    def add_override(self):
        """
        Take the form's ruling into the list.

        RETURNS:
        --------
        bool
            True when one was added. False when the date could not be read,
            which is said above the list rather than in a second window - a
            message box over a modal dialog is a stack of two things to
            dismiss for a typo.

        DEVELOPMENT NOTES:
        ------------------
        A date already ruled on is replaced, matching the calendar, which can
        only hold one ruling per date. Re-adding a date to change its type or
        its reason is the obvious way to try to edit one, and it works.
        """
        chosen = self.override_date_entry.get_date()
        if chosen is None:
            self.override_error_label.configure(
                text=("Enter a date as YYYY-MM-DD, or pick one from the "
                      "calendar button."))
            return False

        day = chosen.date()
        worked = self.override_type_var.get() == self.WORKING_LABEL
        replaced = day in self.overrides

        self.overrides[day] = DateOverride(
            override_date=day, is_working_day=worked,
            reason=self.override_reason_entry.get().strip(),
        )

        self.override_error_label.configure(
            text=(f"{day.isoformat()} was already overridden; it now reads "
                  f"as the new one." if replaced else ""))
        self.override_reason_entry.delete(0, tk.END)
        self._refresh_override_list()

        logger.info("Override: %s is %s", day,
                    "a working day" if worked else "not a working day")
        return True

    def remove_override(self, day: date) -> bool:
        """
        Drop one ruling, putting the date back under the ordinary rules.

        RETURNS:
        --------
        bool
            True when there was one to drop.
        """
        if self.overrides.pop(day, None) is None:
            return False

        self.override_error_label.configure(text="")
        self._refresh_override_list()
        logger.info("Override on %s removed", day)
        return True

    def override_selection(self) -> List[DateOverride]:
        """Every ruling the dialog holds, in date order."""
        return [self.overrides[day] for day in sorted(self.overrides)]

    # ---- the working week tab -------------------------------------------

    def _build_working_week_tab(self, week: Set[int]):
        """
        A tick box per weekday, ticked for the days that are worked.

        PARAMETERS:
        -----------
        week : Set[int]
            The weekday indices *not* worked, which open unticked.

        DEVELOPMENT NOTES:
        ------------------
        The boxes read as "worked", the calendar stores "not worked", and the
        inversion happens here rather than anywhere else. Asking somebody to
        tick the days they are off is the kind of double negative that gets
        set backwards once and then disbelieved forever.
        """
        ctk.CTkLabel(self.tab_week, text="Days of the week that are worked:",
                     anchor=tk.W, font=ctk.CTkFont(size=14, weight="bold")
                     ).pack(fill=tk.X, padx=5, pady=(5, 2))

        ctk.CTkLabel(
            self.tab_week, anchor=tk.W, justify=tk.LEFT, wraplength=520,
            text_color=theme.MUTED_TEXT,
            text=("The base rule the whole plan is scheduled on. Public "
                  "holidays and manual overrides are read on top of it."),
        ).pack(fill=tk.X, padx=5, pady=(0, 8))

        boxes = ctk.CTkFrame(self.tab_week, fg_color='transparent')
        boxes.pack(fill=tk.X, padx=5)

        #: One tick box per weekday, by index. True means the day is worked,
        #: which is the opposite of what the calendar stores.
        self.weekday_boxes: Dict[int, ctk.BooleanVar] = {}
        for index, name in self.WEEKDAYS:
            variable = ctk.BooleanVar(value=index not in week)
            variable.trace_add('write',
                               lambda *_args: self._update_week_summary())
            self.weekday_boxes[index] = variable
            ctk.CTkCheckBox(boxes, text=name, variable=variable).pack(
                anchor=tk.W, padx=6, pady=3)

        batch = ctk.CTkFrame(self.tab_week, fg_color='transparent')
        batch.pack(fill=tk.X, padx=5, pady=(10, 0))
        secondary_button(batch, "Standard week (Mon-Fri)",
                         self.select_standard_week, width=200).pack(side=tk.LEFT)

        self.week_summary_label = ctk.CTkLabel(
            self.tab_week, anchor=tk.W, justify=tk.LEFT, wraplength=520,
            text="", text_color=theme.MUTED_TEXT,
        )
        self.week_summary_label.pack(fill=tk.X, padx=5, pady=(10, 0))

    def select_standard_week(self):
        """Put the week back to Monday-to-Friday."""
        for index, variable in self.weekday_boxes.items():
            variable.set(index not in DEFAULT_NON_WORKING_DAYS)

    def working_week_selection(self) -> Set[int]:
        """
        The weekday indices that are *not* worked, as the calendar wants them.

        The inverse of what the boxes show; see _build_working_week_tab.
        """
        return {index for index, variable in self.weekday_boxes.items()
                if not variable.get()}

    def _update_week_summary(self):
        """
        Say what the current ticks amount to, and when they amount to nothing.

        The empty week is called out as it happens rather than only on Apply,
        so the last box untick explains itself where the eye already is.
        """
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return

        worked = sorted(index for index, variable in self.weekday_boxes.items()
                        if variable.get())

        if not worked:
            self.week_summary_label.configure(
                text=("No days are worked. At least one has to be, or there "
                      "is no calendar to schedule against."),
                text_color=theme.WARNING_TEXT)
            return

        names = dict(self.WEEKDAYS)
        if worked == [0, 1, 2, 3, 4]:
            text = "The standard week: Monday to Friday."
        elif len(worked) == 7:
            text = "Every day is worked; nothing is ever skipped."
        else:
            text = (f"{len(worked)} days worked: "
                    f"{', '.join(names[index] for index in worked)}.")

        self.week_summary_label.configure(text=text, text_color=theme.MUTED_TEXT)

    # ---- choosing which calendar the tabs edit --------------------------

    def _build_calendar_selector(self):
        """
        The row that says which calendar the three tabs are showing.

        DEVELOPMENT NOTES:
        ------------------
        Not built at all when the plan holds no named calendars: a selector
        whose only entry is the project's own is a control that cannot be
        used, and it would put a row of chrome above every tab for the plans
        - most of them - that never name a second calendar.

        The menu holds labels and the ids are kept beside it, because two
        calendars may be called the same thing while their ids cannot be.
        """
        row = ctk.CTkFrame(self, fg_color='transparent')
        row.pack(fill=tk.X, padx=15, pady=(15, 0))

        ctk.CTkLabel(row, text="Editing:",
                     font=ctk.CTkFont(size=12, weight="bold")
                     ).pack(side=tk.LEFT, padx=(0, 8))

        #: Label to calendar id, for reading the menu back.
        self._selector_ids: Dict[str, Optional[str]] = {}

        self.selector_var = ctk.StringVar()
        self.calendar_selector = ctk.CTkOptionMenu(
            row, variable=self.selector_var, values=[PROJECT_DEFAULT_LABEL],
            width=200, command=self._on_calendar_selected)
        self.calendar_selector.pack(side=tk.LEFT)

        self.button_new = ctk.CTkButton(row, text="New...", width=64,
                                        command=self.new_calendar)
        self.button_new.pack(side=tk.LEFT, padx=(6, 0))

        self.button_rename = secondary_button(row, "Rename...",
                                              self.rename_calendar, width=84)
        self.button_rename.pack(side=tk.LEFT, padx=(6, 0))

        self.button_delete = secondary_button(row, "Delete",
                                              self.delete_calendar, width=64)
        self.button_delete.pack(side=tk.LEFT, padx=(6, 0))

        self.selector_note = ctk.CTkLabel(self, text="", anchor=tk.W,
                                          justify=tk.LEFT, wraplength=560,
                                          text_color=theme.MUTED_TEXT)
        self.selector_note.pack(fill=tk.X, padx=15, pady=(4, 0))

        self._rebuild_selector()

    def _rebuild_selector(self):
        """
        Put the menu back in step with the registry, and keep the selection.

        Called after anything that adds, renames or removes a calendar. The
        selection is restored by id rather than by label, because a rename
        changes the label under it.
        """
        self._selector_ids = {}
        labels = []
        for calendar_id, name in self.registry.options():
            self._selector_ids[name] = calendar_id
            labels.append(name)

        self.calendar_selector.configure(values=labels)

        wanted = self.current_calendar_id
        if wanted is not None and wanted not in self.registry:
            wanted = None
        self.current_calendar_id = wanted

        for label, calendar_id in self._selector_ids.items():
            if calendar_id == wanted:
                self.selector_var.set(label)
                break

        editable = self.current_calendar_id is not None
        state = tk.NORMAL if editable else tk.DISABLED
        self.button_rename.configure(state=state)
        self.button_delete.configure(state=state)

    # ---- adding, renaming and removing calendars ------------------------

    def new_calendar(self):
        """
        Add a calendar, starting from the one currently shown.

        RETURNS:
        --------
        Optional[str]
            The new calendar's id, or None when the prompt was cancelled.

        DEVELOPMENT NOTES:
        ------------------
        A copy of what is on screen rather than a bare Monday-to-Friday week,
        so "New..." doubles as "duplicate this one" - which is what building
        a second weekend shift with one different holiday actually needs, and
        the alternative was rebuilding it from nothing every time.

        The dialog is raised again afterwards. A modal prompt opened over a
        modal dialog comes back behind it on some window managers, and a
        settings window that has apparently frozen is the worst version of
        this.
        """
        name = self._ask_name("New calendar", "Name for the new calendar:",
                              "Weekend Shift")
        if not name:
            return None

        self._capture_current_calendar()
        source = self._working_calendar(self.current_calendar_id)
        named = self.registry.create(
            name, WorkingCalendar.from_dict(source.to_dict()))

        self.current_calendar_id = named.id
        self._rebuild_selector()
        self._load_current_calendar()
        logger.info("Added the calendar %r", named.id)
        return named.id

    def rename_calendar(self):
        """Change what the selected calendar is called, keeping its id."""
        if self.current_calendar_id is None:
            return False

        named = self.registry.get(self.current_calendar_id)
        name = self._ask_name("Rename calendar", "New name:", named.name)
        if not name:
            return False

        self.registry.rename(named.id, name)
        self._rebuild_selector()
        return True

    def delete_calendar(self):
        """
        Remove the selected calendar, after saying what that does to tasks.

        Tasks following it are not touched and are not listed: they fall back
        to the project's own calendar the moment it is gone - see
        CalendarRegistry.resolve - so there is nothing for the reader to
        repair and nothing they need to be shown before deciding.
        """
        if self.current_calendar_id is None:
            return False

        named = self.registry.get(self.current_calendar_id)
        if not messagebox.askyesno(
                "Delete calendar",
                f"Delete the calendar {named.name!r}?\n\n"
                f"Any task following it goes back to the project's own "
                f"calendar.", parent=self):
            return False

        self.registry.remove(named.id)
        self.current_calendar_id = None
        self._rebuild_selector()
        self._load_current_calendar()
        logger.info("Removed the calendar %r", named.id)
        return True

    def _ask_name(self, title: str, prompt: str,
                  initial: str = "") -> Optional[str]:
        """
        Ask for a calendar name, over this dialog rather than behind it.

        RETURNS:
        --------
        Optional[str]
            The name typed, stripped, or None when it was cancelled or left
            empty - an unnamed calendar is one nobody could pick again.
        """
        answer = simpledialog.askstring(title, prompt, parent=self,
                                        initialvalue=initial)
        try:
            self.lift()
            self.focus_force()
        except tk.TclError:
            pass

        answer = (answer or '').strip()
        return answer or None

    def _on_calendar_selected(self, label: str):
        """
        Swap the tabs over to another calendar, keeping what was typed.

        The tabs are the same widgets throughout; only what they show changes.
        Whatever the reader had set on the calendar they are leaving is
        captured first, so switching away and back does not lose it - the
        alternative, applying on every switch, would make Cancel meaningless.
        """
        self._capture_current_calendar()
        self.current_calendar_id = self._selector_ids.get(label)
        self._load_current_calendar()

    def _working_calendar(self, calendar_id: Optional[str]) -> WorkingCalendar:
        """The editable calendar behind an id; the project's own for None."""
        if calendar_id is None:
            return self._default_working
        named = self.registry.get(calendar_id)
        return named.calendar if named is not None else self._default_working

    def _capture_current_calendar(self):
        """Write what the three tabs show onto the calendar they show it for."""
        calendar = self._working_calendar(self.current_calendar_id)
        calendar.set_countries(self.selection())
        calendar.overrides = {
            override.override_date: override
            for override in self.override_selection()
        }
        calendar.non_working_days = self.working_week_selection()

    def _load_current_calendar(self):
        """Point the three tabs at the calendar now selected."""
        calendar = self._working_calendar(self.current_calendar_id)

        # The countries, including any region whose boxes have not been built
        chosen = set(calendar.countries)
        for country in self._countries_with_regions(chosen):
            self._build_regions(country, chosen)
        for code, variable in self.checkboxes.items():
            variable.set(code in chosen)
        self._apply_filter()

        self.overrides = dict(calendar.overrides)
        self._refresh_override_list()

        for index, variable in self.weekday_boxes.items():
            variable.set(index not in calendar.non_working_days)
        self._update_week_summary()

        if getattr(self, 'selector_note', None) is not None:
            self.selector_note.configure(text=describe_week(calendar))

    def _first_empty_calendar(self):
        """
        The first calendar left with no working day, or None when all are fine.

        RETURNS:
        --------
        Optional[str]
            A calendar id, or None for the project's own - which is why the
            caller has to check against a sentinel rather than for None; see
            _show_calendar, which takes the same value back.
        """
        candidates = [(None, self._default_working)]
        candidates += [(named.id, named.calendar) for named in self.registry]

        for calendar_id, calendar in candidates:
            if not set(range(7)) - calendar.non_working_days:
                return (calendar_id, )
        return None

    def _show_calendar(self, found):
        """Bring a calendar and its week tab forward, for a refusal."""
        calendar_id = found[0]
        if calendar_id != self.current_calendar_id:
            self.current_calendar_id = calendar_id
            self._load_current_calendar()
            if getattr(self, 'selector_var', None) is not None:
                for label, identifier in self._selector_ids.items():
                    if identifier == calendar_id:
                        self.selector_var.set(label)
                        break
        self.tabview.set(self.TAB_WEEK)
        self._update_week_summary()

    def _build_buttons(self):
        """Apply and Cancel, along the bottom."""
        footer = ctk.CTkFrame(self, fg_color='transparent')
        footer.pack(fill=tk.X, side=tk.BOTTOM, padx=15, pady=15)

        ctk.CTkButton(footer, text="Apply", width=110,
                      command=self.apply).pack(side=tk.RIGHT, padx=5)
        secondary_button(footer, "Cancel", self.cancel).pack(side=tk.RIGHT)

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

        # The empty selection is the one worth looking at twice; see the
        # fonts built in _build_header
        self.summary_label.configure(
            text=text,
            font=self.summary_warning_font if not chosen else self.summary_font,
        )

    def apply(self):
        """
        Hand every tab's choices back and close.

        RETURNS:
        --------
        bool
            False when the dialog refused to apply and stayed open; True
            otherwise. Only the empty week refuses - see below.

        DEVELOPMENT NOTES:
        ------------------
        The week goes first, then the countries, then the overrides, and all
        three go through even when only one of them changed. Each is applied
        by rebuilding the project's calendar from the others' current state -
        see Project.set_date_overrides - so the order does not matter to where
        they land; doing all three unconditionally just saves the dialog from
        having to work out which the user touched. on_applied is called once
        at the end, which is where a caller redraws.

        A week with no day worked is refused here, before anything is applied
        and before the window closes. The calendar would take it - it treats
        such a week as working every day, so a corrupt file cannot hang the
        scheduler - but that fallback is for bad data, and applying it to a
        deliberate choice would answer "no days" with seven of them and say so
        only in the log. The tab is brought forward so the refusal is visible
        next to the boxes that caused it.
        """
        week = self.working_week_selection()
        if not set(range(7)) - week:
            self.tabview.set(self.TAB_WEEK)
            self._update_week_summary()
            logger.info("Refused a working week with no working day in it")
            return False

        # What the tabs currently show belongs to the calendar they show it
        # for, and has to be written back before any of them is read.
        self._capture_current_calendar()

        # Every *other* calendar is checked too. Only the one on screen can
        # have just been emptied, but one emptied earlier and switched away
        # from would otherwise be applied unnoticed.
        empty = self._first_empty_calendar()
        if empty is not None:
            self._show_calendar(empty)
            logger.info("Refused a working week with no working day in it")
            return False

        chosen = sorted(self._default_working.countries)
        overrides = self._default_working.sorted_overrides()
        week = set(self._default_working.non_working_days)

        logger.info("Observing public holidays for %s, with %d date "
                    "override(s), on a %d-day week",
                    ', '.join(chosen) if chosen else 'no countries',
                    len(overrides), 7 - len(week))

        self.destroy()

        if self.on_apply_working_week:
            self.on_apply_working_week(week)
        if self.on_apply:
            self.on_apply(chosen)
        if self.on_apply_overrides:
            self.on_apply_overrides(overrides)
        if self.on_apply_calendars:
            self.on_apply_calendars(list(self.registry))
        if self.on_applied:
            self.on_applied()
        return True

    def cancel(self):
        """
        Close without changing anything.

        Nothing here has touched the project, on either tab, so closing is the
        whole of it - see the note on the module about why both tabs wait.
        """
        self.destroy()


#: What this dialog was before it grew a second tab. Kept because the country
#: picker is what most callers still mean by it, and renaming a class is not a
#: reason to break an import.
HolidayDialog = CalendarSettingsDialog


def choose_holidays(master, selected: Sequence[str],
                    on_apply: Callable[[List[str]], None],
                    overrides: Sequence[DateOverride] = (),
                    on_apply_overrides: Optional[
                        Callable[[List[DateOverride]], None]] = None,
                    non_working_days: Optional[Iterable[int]] = None,
                    on_apply_working_week: Optional[
                        Callable[[Set[int]], None]] = None,
                    on_applied: Optional[Callable[[], None]] = None,
                    registry: Optional[CalendarRegistry] = None,
                    on_apply_calendars: Optional[
                        Callable[[List[NamedCalendar]], None]] = None
                    ) -> Optional[CalendarSettingsDialog]:
    """
    Open the calendar settings.

    PARAMETERS:
    -----------
    See CalendarSettingsDialog, whose arguments these are.

    RETURNS:
    --------
    Optional[CalendarSettingsDialog]
        The dialog, or None when it could not be built. A dialog that fails to
        open should not take the menu that opened it down with it.
    """
    try:
        return CalendarSettingsDialog(master, selected, on_apply,
                                      overrides, on_apply_overrides,
                                      non_working_days, on_apply_working_week,
                                      on_applied, registry, on_apply_calendars)
    except Exception:
        logger.exception("Could not open the calendar settings dialog")
        return None
