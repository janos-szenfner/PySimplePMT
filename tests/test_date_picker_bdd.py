"""
pytest-bdd tests for the calendar behind the date boxes.

Run with:
    python3 -m pytest tests/test_date_picker_bdd.py -q

The scenarios drive the real popup, so they skip without a display.
Converted from test_date_picker.py - every case carried over.
"""
import calendar
from datetime import datetime
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

pytestmark = [
    pytest.mark.date_picker,
]

scenarios("features/date_picker.feature")

#: A month that starts on a Sunday, so a wrong column shows up at once.
YEAR, MONTH = 2026, 3


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


def _shut_down(root) -> None:
    """
    Take a root down, children first, without raising.

    Destroying a root while a Toplevel is still on it leaves Tk running
    ttk::ThemeChanged against an interpreter that has already gone, which
    floods stderr with "can't invoke event" tracebacks.
    """
    try:
        for child in list(root.children.values()):
            try:
                child.destroy()
            except Exception:
                pass
        root.destroy()
    except Exception:
        pass


def _placed(popup):
    """Every cell of the calendar grid, as {(row, column): text}."""
    cells = {}
    for widget in popup._grid.winfo_children():
        info = widget.grid_info()
        cells[(int(info['row']), int(info['column']))] = str(
            widget.cget('text'))
    return cells


def _column_of(popup, text):
    """The column a given cell was placed in."""
    for (_row, column), value in _placed(popup).items():
        if value == text:
            return column
    raise AssertionError(f"no cell reading {text!r}")


# ------------------------------------------------------------------
# GIVEN - needs a display
# ------------------------------------------------------------------

@given("the calendar open on March 2026", target_fixture="ctx")
def the_calendar_open_on_march_2026():
    if not HAVE_DISPLAY:
        pytest.skip("needs a display")
    import customtkinter as ctk
    from gantt_app.views.datepicker import DateEntry

    root = ctk.CTk()
    root.withdraw()

    entry = DateEntry(root, date=datetime(YEAR, MONTH, 15))
    entry.pack()
    root.update_idletasks()

    popup = entry.open_calendar()
    popup.update_idletasks()

    yield SimpleNamespace(root=root, entry=entry, popup=popup)

    _shut_down(root)


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------

@when("the calendar steps to the next month")
def the_calendar_steps_to_the_next_month(ctx):
    ctx.popup.next_month()
    ctx.popup.update_idletasks()


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@then("the top row holds every weekday heading")
def the_top_row_holds_every_weekday_heading(ctx):
    from gantt_app.views.datepicker import WEEKDAYS

    headings = [text for (row, _column), text in _placed(ctx.popup).items()
                if row == 0]
    assert sorted(headings) == sorted(WEEKDAYS)


@then("every weekday heading sits in its own column")
def every_weekday_heading_sits_in_its_own_column(ctx):
    from gantt_app.views.datepicker import WEEKDAYS

    for column, name in enumerate(WEEKDAYS):
        assert _column_of(ctx.popup, name) == column


@then("every day of March 2026 sits under its weekday")
def every_day_sits_under_its_weekday(ctx):
    for day in range(1, calendar.monthrange(YEAR, MONTH)[1] + 1):
        weekday = datetime(YEAR, MONTH, day).weekday()
        assert _column_of(ctx.popup, str(day)) == weekday


@then(parsers.parse("day {day:d} sits in the Sunday column"))
def the_first_sits_in_the_sunday_column(ctx, day):
    from gantt_app.views.datepicker import WEEKDAYS

    assert _column_of(ctx.popup, str(day)) == WEEKDAYS.index('Su')


@then("no day cell shares the headings' row")
def no_day_cell_shares_the_headings_row(ctx):
    days = [text for (row, _column), text in _placed(ctx.popup).items()
            if row > 0]
    top = [text for (row, _c), text in _placed(ctx.popup).items()
           if row == 0]
    assert '1' in days
    assert '1' not in top


@then("every column is uniform and floored at one cell")
def every_column_is_uniform_and_floored(ctx):
    from gantt_app.views.datepicker import WEEKDAYS, CalendarPopup

    for column in range(len(WEEKDAYS)):
        options = ctx.popup._grid.grid_columnconfigure(column)
        assert options.get('uniform') == 'day'
        assert int(options.get('minsize')) == CalendarPopup.CELL


@then("the sampled April days sit under their weekdays")
def the_sampled_april_days_sit_under_their_weekdays(ctx):
    for day in (1, 15, 30):
        weekday = datetime(2026, 4, day).weekday()
        assert _column_of(ctx.popup, str(day)) == weekday
