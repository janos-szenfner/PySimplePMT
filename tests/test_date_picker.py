"""
Tests for the calendar behind the date boxes.

WHY THIS MODULE EXISTS:
======================
The weekday headings and the day cells sat in two frames, each with a grid of
its own, and were sized in different units besides - the headings 34 pixels
wide, the cells three characters. Two grids cannot line their columns up with
one another, so Monday stood over no particular column and nor did any other
day: the calendar read as a row of headings above an unrelated block of
numbers.

DEVELOPMENT NOTES:
------------------
What is checked is which column each widget was placed in, which is what
decides where it is drawn. Whether the pixels line up on a particular desktop
is a matter of what the window manager made of the popup, and no test here
can see that - but a day in the same column as its heading cannot be drawn
anywhere else.

The module skips without a display; CI provides one through xvfb.
"""

import unittest
import calendar
from datetime import datetime


def _display_available() -> bool:
    """Whether a usable Tk display is present."""
    try:
        import tkinter
        root = tkinter.Tk()
    except Exception:
        return False
    root.destroy()
    return True


HAVE_DISPLAY = _display_available()


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class CalendarTestCase(unittest.TestCase):
    """A date box with its calendar open."""

    #: A month that starts on a Sunday, so a wrong column shows up at once.
    YEAR, MONTH = 2026, 3

    def setUp(self):
        """Open the calendar on March 2026."""
        import customtkinter as ctk
        from gantt_app.views.datepicker import DateEntry

        self.root = ctk.CTk()
        self.root.withdraw()

        self.entry = DateEntry(self.root, date=datetime(self.YEAR, self.MONTH, 15))
        self.entry.pack()
        self.root.update_idletasks()

        self.popup = self.entry.open_calendar()
        self.popup.update_idletasks()

    def tearDown(self):
        """Tear the root window down."""
        try:
            self.root.destroy()
        except Exception:
            pass

    def placed(self):
        """Every cell of the calendar grid, as {(row, column): text}."""
        cells = {}
        for widget in self.popup._grid.winfo_children():
            info = widget.grid_info()
            cells[(int(info['row']), int(info['column']))] = str(
                widget.cget('text'))
        return cells

    def column_of(self, text):
        """The column a given cell was placed in."""
        for (_row, column), value in self.placed().items():
            if value == text:
                return column
        raise AssertionError(f"no cell reading {text!r}")


class TestTheDaysSitUnderTheirHeadings(CalendarTestCase):
    """Which is the whole job of a calendar's columns."""

    def test_the_headings_are_in_the_same_grid_as_the_days(self):
        """
        One grid, so one set of columns.

        Two frames cannot line their columns up with one another however
        they are sized.
        """
        from gantt_app.views.datepicker import WEEKDAYS

        headings = [text for (row, _column), text in self.placed().items()
                    if row == 0]

        self.assertEqual(sorted(headings), sorted(WEEKDAYS))

    def test_each_heading_is_in_its_own_column(self):
        """Monday leftmost, Sunday last, one column each."""
        from gantt_app.views.datepicker import WEEKDAYS

        for column, name in enumerate(WEEKDAYS):
            self.assertEqual(self.column_of(name), column)

    def test_every_day_sits_under_the_weekday_it_falls_on(self):
        """Checked against the calendar module, for the whole month."""
        from gantt_app.views.datepicker import WEEKDAYS

        for day in range(1, calendar.monthrange(self.YEAR, self.MONTH)[1] + 1):
            weekday = datetime(self.YEAR, self.MONTH, day).weekday()

            self.assertEqual(
                self.column_of(str(day)), weekday,
                f"{day} March falls on {WEEKDAYS[weekday]}",
            )

    def test_the_first_of_the_month_lands_on_its_weekday(self):
        """
        March 2026 opens on a Sunday, the last column.

        A month starting at the right-hand edge is where a grid that has
        lost its leading blanks shows itself.
        """
        from gantt_app.views.datepicker import WEEKDAYS

        self.assertEqual(self.column_of('1'), WEEKDAYS.index('Su'))

    def test_the_days_start_below_the_headings(self):
        """Row 0 is the headings, so no day may be in it."""
        days = [text for (row, _column), text in self.placed().items()
                if row > 0]

        self.assertIn('1', days)
        self.assertNotIn('1', [text for (row, _c), text in self.placed().items()
                               if row == 0])


class TestTheColumnsAreEqual(CalendarTestCase):
    """A column is the same width whatever happens to be in it."""

    def test_every_column_is_held_to_the_same_width(self):
        """
        uniform ties them together and minsize gives them a floor.

        Without it a column of single digits comes out narrower than one
        holding a two-digit day, and the headings drift off their days as
        the month goes down the grid.
        """
        from gantt_app.views.datepicker import WEEKDAYS, CalendarPopup

        for column in range(len(WEEKDAYS)):
            options = self.popup._grid.grid_columnconfigure(column)

            self.assertEqual(options.get('uniform'), 'day')
            self.assertEqual(int(options.get('minsize')), CalendarPopup.CELL)


class TestSteppingThroughTheMonths(CalendarTestCase):
    """The headings survive a redraw, being drawn with the days."""

    def test_the_headings_are_still_there_after_a_month_change(self):
        """_draw_month clears the grid, so it puts them back."""
        from gantt_app.views.datepicker import WEEKDAYS

        self.popup.next_month()
        self.popup.update_idletasks()

        headings = [text for (row, _column), text in self.placed().items()
                    if row == 0]

        self.assertEqual(sorted(headings), sorted(WEEKDAYS))

    def test_the_days_of_the_next_month_line_up_too(self):
        """April 2026 starts on a Wednesday."""
        self.popup.next_month()
        self.popup.update_idletasks()

        for day in (1, 15, 30):
            weekday = datetime(2026, 4, day).weekday()

            self.assertEqual(self.column_of(str(day)), weekday)


if __name__ == '__main__':
    unittest.main()
