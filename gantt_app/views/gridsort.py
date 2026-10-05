"""
Sorting the task grid, and the dialogs that ask for it.

WHY THIS MODULE EXISTS:
======================
Two requests meet here: every column heading should sort the list when it
is clicked (issue #46), and a menu entry should offer MS Project's "Sort
By" dialog with up to three levels - "Duration descending, then Start
Date ascending, then Progress ascending" (issue #45).

Both are the same mechanism underneath: the list holds a row of sort
keys - (column, 'asc' | 'desc') - applied to each level of the outline,
so siblings are rearranged but a task never leaves its parent. The plan's
own order is untouched; clearing the sort puts the original order back.

The helpers are pure so the ordering can be tested without a display;
the dialog at the bottom only collects the keys.
"""

from datetime import date, datetime
from typing import Dict, List, Tuple

import customtkinter as ctk

from gantt_app.views import theme
from gantt_app.views.modal import grab_when_visible
from gantt_app.views.buttonstyle import secondary_button
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)

ASC = 'asc'
DESC = 'desc'

#: The most keys a sort carries - the dialog's Sort by, Then by, Then by.
MAX_SORT_KEYS = 3

#: The arrow a sorted column's heading wears, by direction.
SORT_ARROWS = {ASC: '▲', DESC: '▼'}

#: What the sort field menu offers a row that sorts by nothing. The first
#: Sort By row takes it as "leave the list in plan order"; the Then By
#: rows take it as "no further level".
NO_FIELD = '(none)'


def next_column_sort(keys: List[Tuple[str, str]], column: str
                     ) -> List[Tuple[str, str]]:
    """
    The sort state after a plain heading click.

    A click on an unsorted column makes it the one sort key, ascending -
    a plain click asks a single-column question, so any multi-level sort
    is replaced rather than quietly amended. A second click on the sorted
    column reverses it, and a third lifts the sort entirely, putting the
    rows back in plan order: the cycle a spreadsheet column runs.
    """
    if keys == [(column, ASC)]:
        return [(column, DESC)]
    if keys == [(column, DESC)]:
        return []
    return [(column, ASC)]


def _comparable(value):
    """
    The value a sort compares, normalised so a column never mixes kinds.

    Dates and datetimes land on the same ordinal scale (a datetime keeps
    its time as the fraction of a day), numbers compare as floats, and
    text compares case-folded - "design" beside "Design" rather than
    after "zebra".
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, datetime):
        return (value.toordinal()
                + (value.hour * 3600 + value.minute * 60 + value.second)
                / 86400.0)
    if isinstance(value, date):
        return float(value.toordinal())
    return str(value).casefold()


def sort_tasks(tasks, keys, project, context: Dict = None) -> list:
    """
    The given rows in sort order, blanks last whichever way the sort runs.

    PARAMETERS:
    -----------
    tasks : iterable
        The sibling group or root set being arranged.
    keys : list of (column, 'asc' | 'desc')
        At most MAX_SORT_KEYS; applied in order, so the first wins ties
        nowhere but breaks them everywhere else.
    project : Project
        The plan, for the values a task cannot answer alone.
    context : Dict, optional
        gridfilter.column_value's shared cache - variances, display
        numbers, the conflict set - worked out once by the caller.

    DEVELOPMENT NOTES:
    ------------------
    Each level is a stable sort over the result of the last, applied from
    the final key back to the first - the way every spreadsheet layers
    sorts. Rows whose cell is empty are parted out and re-appended, so a
    blank finish lands at the bottom for ascending and descending alike,
    the way MS Project and Excel both leave blanks.
    """
    from gantt_app.views.gridfilter import column_value

    context = context or {}
    ordered = list(tasks)
    for column, direction in reversed(list(keys or ())[:MAX_SORT_KEYS]):
        present, blank = [], []
        for task in ordered:
            value = _comparable(column_value(task, column, project, context))
            (blank if value is None else present).append((value, task))
        present.sort(key=lambda pair: pair[0],
                     reverse=(direction == DESC))
        ordered = [task for _v, task in present] \
            + [task for _v, task in blank]
    return ordered


def sort_indicator(column: str, keys) -> str:
    """
    The marker a column's heading wears, or ''.

    A single-level sort is just the arrow; a multi-level sort numbers the
    arrow so Duration ▼1 and Start ▲2 read as "Duration first, then
    Start", the order the dialog asked for them in.
    """
    for index, (key_column, direction) in enumerate(keys or ()):
        if key_column == column:
            marker = SORT_ARROWS.get(direction, '')
            return f'{marker}{index + 1}' if len(keys) > 1 else marker
    return ''


class SortDialog(ctk.CTkToplevel):
    """
    The "Sort By" window: up to three levels, each a field and a way round.

    PARAMETERS:
    -----------
    master : widget
        The application window.
    columns : list
        The sortable column names, Task Name first.
    current : list
        The (column, direction) keys already in force, so reopening shows
        the sort that is on rather than a blank form.
    on_apply : callable
        Given the collected keys - a list of (column, 'asc' | 'desc'),
        empty when every row is left at "(none)".
    """

    def __init__(self, master, columns, current=None, on_apply=None):
        super().__init__(master)
        self.title("Sort Tasks")
        self.transient(master)
        self._on_apply = on_apply

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=12, pady=(12, 4))
        ctk.CTkLabel(
            head,
            text="Rows sort inside their level of the outline - a "
                 "sub-task is ordered among its siblings, never moved "
                 "out from under its summary.",
            anchor="w", wraplength=460, justify="left",
            text_color=theme.MUTED_TEXT,
            font=ctk.CTkFont(size=12),
        ).pack(fill="x")

        #: The two controls of each level: a field pick and a direction.
        self._rows = []
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="x", padx=12, pady=4)
        choices = [NO_FIELD] + list(columns)
        for index, caption in enumerate(
                ("Sort by", "Then by", "Then by")):
            row = ctk.CTkFrame(body, fg_color="transparent")
            row.pack(fill="x", pady=4)
            ctk.CTkLabel(row, text=caption, width=64,
                         anchor="w").pack(side="left")
            field = ctk.CTkOptionMenu(row, values=choices, width=180)
            field.pack(side="left", padx=(4, 8))
            direction = ctk.CTkSegmentedButton(
                row, values=["Ascending", "Descending"])
            direction.set("Ascending")
            direction.pack(side="left")
            self._rows.append((field, direction))

        for (column, direction), (field, picker) in zip(
                current or (), self._rows):
            if column in columns:
                field.set(column)
                picker.set("Ascending" if direction == ASC
                           else "Descending")

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", padx=12, pady=(8, 12))
        ctk.CTkButton(buttons, text="Sort", width=80,
                      command=self._apply).pack(side="right", padx=(6, 0))
        secondary_button(buttons, "Close", self.destroy,
                         width=70).pack(side="right")
        secondary_button(buttons, "Reset", self._reset,
                         width=70).pack(side="left")

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        grab_when_visible(self)

    def _keys(self) -> list:
        """The levels the form currently asks for, (none) rows dropped."""
        keys = []
        for field, picker in self._rows:
            column = field.get()
            if column == NO_FIELD:
                continue
            keys.append((column,
                         ASC if picker.get() == "Ascending" else DESC))
        return keys

    def _apply(self):
        """Hand the keys over; the window stays open for another try."""
        if self._on_apply is not None:
            try:
                self._on_apply(self._keys())
            except Exception:
                logger.exception("Applying the sort failed")

    def _reset(self):
        """Every row back to (none), and the plan order applied."""
        for field, picker in self._rows:
            field.set(NO_FIELD)
            picker.set("Ascending")
        self._apply()
