"""
A date box with a calendar behind it, for the task dialogs.

WHY THIS MODULE EXISTS:
======================
Start and end dates were plain text boxes wanting YYYY-MM-DD. That asks the
user to know what day of the week the 14th falls on, and to get the format
exactly right or have the dialog reject the whole task. A calendar answers
both: the date is picked from a month, and what lands in the box is always
well formed.

DEVELOPMENT NOTES:
------------------
Written against the standard library's calendar module rather than adding a
dependency. tkcalendar is the usual choice, but it would be the only package
in the build that exists solely for one widget, and the packaged .deb goes to
some trouble to stay self-contained.

The box is still typeable. Anyone who would rather key a date in can, and the
dialogs keep the validation they already had, so this only adds a way in
rather than replacing one.

DateEntry stands in for the CTkEntry it replaced, so get, insert, delete and
configure(state=...) all behave as the dialogs already expect.
"""

import calendar
import tkinter as tk
from datetime import datetime
from typing import Optional

import customtkinter as ctk
from PIL import Image, ImageDraw

from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


#: How a date is written in the box, and what the dialogs parse.
DATE_FORMAT = '%Y-%m-%d'

#: Day-of-week headings, starting on Monday.
WEEKDAYS = ('Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su')

#: The drawn glyph, kept so it is only painted once.
#:
#: The picture is cached, not the CTkImage wrapping it: a Tk image belongs to
#: the interpreter that made it and stops existing when that window is torn
#: down, so a shared one would go stale. Painting is the part worth keeping;
#: wrapping it again costs almost nothing.
_ICON_IMAGE = None


def _draw_calendar(size: int):
    """
    Paint a calendar glyph.

    RETURNS:
    --------
    Image.Image
        The glyph in white on transparent, ready to sit on a coloured button.

    DEVELOPMENT NOTES:
    ------------------
    Drawn rather than set as the emoji this used to be. An emoji needs a font
    that has it, and a stock Linux desktop often has none - the button came
    out blank, a plain blue rectangle with nothing on it. Drawing depends on
    no font at all.

    Pillow is already required for the chart exports, so this costs no new
    dependency. It is painted at four times the size and reduced, which keeps
    the edges clean on a HiDPI screen.
    """
    scale = 4
    edge = size * scale
    image = Image.new('RGBA', (edge, edge), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    white = (255, 255, 255, 255)
    line = max(1, scale)

    # The body, with the header bar filled in
    top = int(edge * 0.18)
    draw.rounded_rectangle([line, top, edge - line - 1, edge - line - 1],
                           radius=scale * 2, outline=white, width=line)
    draw.rounded_rectangle([line, top, edge - line - 1, top + int(edge * 0.20)],
                           radius=scale * 2, fill=white)

    # The two rings above it
    for x in (int(edge * 0.30), int(edge * 0.68)):
        draw.line([(x, int(edge * 0.06)), (x, int(edge * 0.24))],
                  fill=white, width=line)

    # A couple of rows of days. Positions are whole multiples of the scale
    # so each mark lands on one pixel of the reduced image rather than
    # straddling two and coming out a different weight from its neighbours.
    for row in range(2):
        y = (8 + row * 3) * scale
        for column in range(3):
            x = (4 + column * 3) * scale
            draw.rectangle([x, y, x + line - 1, y + line - 1], fill=white)

    return image.resize((size, size), Image.LANCZOS)


def calendar_icon(size: int = 16):
    """
    The calendar glyph for the button that opens the month view.

    RETURNS:
    --------
    ctk.CTkImage
        A fresh wrapper around the cached drawing.
    """
    global _ICON_IMAGE
    if _ICON_IMAGE is None:
        _ICON_IMAGE = _draw_calendar(size)
    return ctk.CTkImage(light_image=_ICON_IMAGE, size=(size, size))


class DateEntry(ctk.CTkFrame):
    """
    A text box holding a date, with a button that opens a calendar.

    PARAMETERS:
    -----------
    master : widget
        Parent widget.
    date : Optional[datetime]
        The date to start on. None leaves the box empty.

    DEVELOPMENT NOTES:
    ------------------
    The entry is the source of truth, not a stored date object. The dialogs
    read the text and parse it themselves, and a user may type something the
    calendar never produced, so keeping a parallel value would only give the
    two a chance to disagree.
    """

    def __init__(self, master, date: Optional[datetime] = None, **kwargs):
        super().__init__(master, fg_color='transparent', **kwargs)

        self.grid_columnconfigure(0, weight=1)

        self.entry = ctk.CTkEntry(self)
        self.entry.grid(row=0, column=0, sticky=tk.EW)

        self.button = ctk.CTkButton(self, text='', image=calendar_icon(),
                                    width=36, command=self.open_calendar)
        self.button.grid(row=0, column=1, padx=(6, 0))

        if date is not None:
            self.entry.insert(0, date.strftime(DATE_FORMAT))

        self._popup = None

    # ------------------------------------------------------------------
    # Standing in for a CTkEntry
    # ------------------------------------------------------------------

    def get(self) -> str:
        """The text in the box."""
        return self.entry.get()

    def insert(self, index, text):
        """Insert text, as CTkEntry does."""
        self.entry.insert(index, text)

    def delete(self, first, last=None):
        """Delete text, as CTkEntry does."""
        self.entry.delete(first, last)

    def configure(self, **kwargs):
        """
        Configure the widget.

        DEVELOPMENT NOTES:
        ------------------
        'state' is taken off and applied to the entry and the button instead
        of the frame, which has no such option. The dialogs disable the end
        date for a milestone, and the calendar has to go with it or the box
        could still be filled in from behind.
        """
        state = kwargs.pop('state', None)
        if state is not None:
            self.entry.configure(state=state)
            self.button.configure(state=state)
        if kwargs:
            super().configure(**kwargs)

    # ------------------------------------------------------------------
    # Dates
    # ------------------------------------------------------------------

    def get_date(self) -> Optional[datetime]:
        """The date in the box, or None when it is empty or unparseable."""
        text = self.entry.get().strip()
        if not text:
            return None
        try:
            return datetime.strptime(text, DATE_FORMAT)
        except ValueError:
            return None

    def set_date(self, date: datetime):
        """Put a date in the box, replacing whatever was there."""
        was_disabled = str(self.entry.cget('state')) == tk.DISABLED
        if was_disabled:
            self.entry.configure(state=tk.NORMAL)

        self.entry.delete(0, tk.END)
        self.entry.insert(0, date.strftime(DATE_FORMAT))

        if was_disabled:
            self.entry.configure(state=tk.DISABLED)

    def open_calendar(self):
        """Open the month view, starting on whatever the box holds."""
        if str(self.entry.cget('state')) == tk.DISABLED:
            return None

        if self._popup is not None and self._popup.winfo_exists():
            self._popup.lift()
            return self._popup

        self._popup = CalendarPopup(self, self.get_date() or datetime.now(),
                                    on_pick=self._picked)
        return self._popup

    def _picked(self, date: datetime):
        """Take a date chosen from the calendar."""
        self.set_date(date)
        logger.debug("Picked %s from the calendar", date.date())


class CalendarPopup(ctk.CTkToplevel):
    """
    A one-month calendar, opened by a DateEntry.

    PARAMETERS:
    -----------
    master : widget
        The DateEntry that opened it.
    date : datetime
        The month to show, and the day to mark as selected.
    on_pick : callable
        Called with the chosen datetime.

    DEVELOPMENT NOTES:
    ------------------
    The day grid is rebuilt on every month change rather than the labels
    being rewritten. A month has four to six weeks, so the number of rows
    changes, and rebuilding is simpler than tracking which cells to blank.
    """

    #: How wide a column is, in pixels, and how wide a cell asks to be, in
    #: characters. Both are given: the characters size the label to its text
    #: and the pixels hold every column to the same width whatever is in it.
    CELL = 34
    CELL_CHARS = 3
    SELECTED_COLOR = '#1f6aa5'
    TODAY_BORDER = '#e74c3c'
    CELL_BG = '#ffffff'
    HOVER_BG = '#cfe2f3'
    HEADING_COLOR = '#6b7280'

    def __init__(self, master, date: datetime, on_pick):
        super().__init__(master)

        self.on_pick = on_pick
        self._selected = date
        self._year, self._month = date.year, date.month

        self.title("Pick a date")
        self.resizable(False, False)
        self.transient(master.winfo_toplevel())
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind('<Escape>', lambda _e: self.close())

        self._build()
        self._draw_month()
        self._place_near(master)

    def _build(self):
        """Build the month header, the day grid's container and the footer."""
        header = ctk.CTkFrame(self, fg_color='transparent')
        header.pack(fill=tk.X, padx=10, pady=(10, 4))

        ctk.CTkButton(header, text='‹', width=32,
                      command=self.previous_month).pack(side=tk.LEFT)
        self._title = ctk.CTkLabel(header, text='', width=150,
                                   font=ctk.CTkFont(weight='bold'))
        self._title.pack(side=tk.LEFT, expand=True)
        ctk.CTkButton(header, text='›', width=32,
                      command=self.next_month).pack(side=tk.RIGHT)

        # The weekday headings and the day cells share one grid, so they
        # share its columns. They used to sit in two frames, each with a
        # grid of its own, and be sized in different units besides - the
        # headings 34 pixels wide, the cells three characters - so Monday
        # stood over no particular column and nor did any other day.
        self._grid = ctk.CTkFrame(self, fg_color='transparent')
        self._grid.pack(padx=10, pady=(2, 4))
        for column in range(len(WEEKDAYS)):
            self._grid.grid_columnconfigure(column, uniform='day',
                                            minsize=self.CELL)

        footer = ctk.CTkFrame(self, fg_color='transparent')
        footer.pack(fill=tk.X, padx=10, pady=(0, 10))
        ctk.CTkButton(footer, text="Today", width=70,
                      command=self.pick_today).pack(side=tk.LEFT)
        ctk.CTkButton(footer, text="Close", width=70,
                      command=self.close).pack(side=tk.RIGHT)

    def _draw_month(self):
        """
        Redraw the day cells for the month on show.

        DEVELOPMENT NOTES:
        ------------------
        The cells are tk.Labels with their own bindings rather than
        CTkButtons. Thirty-one CTkButtons cost about 4.3ms to build against
        0.3ms for the same number of labels, and this runs again on every
        press of the month arrows - the popup took 18ms to open and each step
        through the months another 4.6ms, which is what made it feel sticky.

        Nothing is lost by it: every colour here is set explicitly anyway, so
        there was no CustomTkinter styling being relied on, and hover is two
        bindings.
        """
        for child in self._grid.winfo_children():
            child.destroy()

        self._title.configure(
            text=f"{calendar.month_name[self._month]} {self._year}"
        )

        # The headings go in with the days, being cleared with them. Same
        # widget and same width as a day cell, so a column is the same
        # width whichever of the two is measuring it.
        for column, name in enumerate(WEEKDAYS):
            tk.Label(self._grid, text=name, width=self.CELL_CHARS,
                     background=self.CELL_BG, foreground=self.HEADING_COLOR,
                     padx=2, pady=3).grid(row=0, column=column,
                                          padx=1, pady=(1, 3))

        today = datetime.now().date()
        weeks = calendar.Calendar(firstweekday=0).monthdayscalendar(
            self._year, self._month
        )

        self.day_buttons = {}
        # Row 0 is the headings, so the weeks start at row 1
        for row, week in enumerate(weeks, start=1):
            for column, day in enumerate(week):
                if day == 0:
                    continue                # a day belonging to another month

                date = datetime(self._year, self._month, day)
                selected = date.date() == self._selected.date()
                is_today = date.date() == today

                cell = tk.Label(
                    self._grid, text=str(day), width=self.CELL_CHARS,
                    background=(self.SELECTED_COLOR if selected
                                else self.CELL_BG),
                    foreground='#ffffff' if selected else '#1a1a1a',
                    relief=tk.SOLID if is_today else tk.FLAT,
                    borderwidth=1 if is_today else 0,
                    cursor='hand2', padx=2, pady=3,
                )
                cell.grid(row=row, column=column, padx=1, pady=1)
                cell.bind('<Button-1>', lambda _e, d=date: self.pick(d))
                if not selected:
                    cell.bind('<Enter>',
                              lambda _e, c=cell: c.configure(
                                  background=self.HOVER_BG))
                    cell.bind('<Leave>',
                              lambda _e, c=cell: c.configure(
                                  background=self.CELL_BG))
                self.day_buttons[day] = cell

    def _place_near(self, widget):
        """
        Open just below the box that asked for it.

        DEVELOPMENT NOTES:
        ------------------
        Only the widget's own position is needed, and it already has one.
        This used to call update_idletasks first, which forces a full layout
        pass of the popup being built purely to learn a size nothing here
        reads - most of the time it took to open.
        """
        try:
            x = widget.winfo_rootx()
            y = widget.winfo_rooty() + widget.winfo_height() + 4
            self.geometry(f"+{x}+{y}")
        except tk.TclError:
            pass

    def previous_month(self):
        """Step back one month."""
        self._month -= 1
        if self._month < 1:
            self._month, self._year = 12, self._year - 1
        self._draw_month()

    def next_month(self):
        """Step forward one month."""
        self._month += 1
        if self._month > 12:
            self._month, self._year = 1, self._year + 1
        self._draw_month()

    def pick_today(self):
        """Choose today, whichever month is on show."""
        self.pick(datetime.now().replace(hour=0, minute=0, second=0,
                                         microsecond=0))

    def pick(self, date: datetime):
        """Choose a date and close."""
        self._selected = date
        if self.on_pick:
            self.on_pick(date)
        self.close()

    def close(self):
        """Close the calendar."""
        try:
            self.destroy()
        except tk.TclError:
            pass
