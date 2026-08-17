"""
The working-day calendar every date in a plan is measured against.

WHY THIS MODULE EXISTS:
======================
A plan has two different notions of "days" and conflating them is what makes
a schedule wrong over a weekend:

  * Working days (effort)  - how much work a task actually holds. Five days
                             of effort is five days of effort whether or not
                             a Saturday happens to fall in the middle of it.
  * Calendar days (elapsed) - how far apart the two ends of it sit on a wall
                             calendar. That is the span the chart draws.

Task durations are stated in the first and drawn in the second. Adding a
duration to a start date with plain timedelta arithmetic silently spends
effort on Saturdays and Sundays, so a five day task starting on a Thursday
finished on the Monday - two days of it having been "worked" over a weekend
nobody was in.

Everything that turns a duration into a date, or a pair of dates back into a
duration, goes through a WorkingCalendar here. Three copies of weekend
skipping had grown up independently - one in the GanttProject importer, one in
the spreadsheet importer, and none at all in the editor - which is exactly how
the same plan came out with different dates depending on where it came from.

DEVELOPMENT NOTES:
------------------
The rules, in full:

  1. A calendar names which weekdays are non-working (Saturday and Sunday by
     default) and which individual dates are holidays.
  2. A task's duration is its working effort. Its finish is found by walking
     the calendar day by day from its start and spending one day of duration
     only on a working day.
  3. Crossing a weekend therefore pushes the finish further out in calendar
     time without lengthening the duration: the task pauses on the Saturday
     and resumes on the Monday.
  4. A task asked to start on a non-working day starts on the next working
     day instead.

Both `date` and `datetime` are accepted, and whichever was passed in is what
comes back - the models hold datetimes, while the standalone form below and
most callers reason in plain dates. Any time-of-day component is carried
through untouched; only the calendar date decides whether a day is worked.

This sits beside models.py rather than under utils/ because models imports it:
everything in utils imports models, so reaching back into that package from
here would run gantt_app.utils.__init__ mid-import and deadlock on a circular
import. Same reason as gantt_app.priority, and the same reason the logger
below comes from the standard library directly.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, Optional, Set, Tuple, Union
import logging

logger = logging.getLogger(__name__)

#: Either kind of date the application deals in.
DateLike = Union[date, datetime]

#: Weekday indices, Monday first, as date.weekday() numbers them.
MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY, SATURDAY, SUNDAY = range(7)

#: The standard week: Monday to Friday worked, the weekend not.
DEFAULT_NON_WORKING_DAYS: Set[int] = {SATURDAY, SUNDAY}

#: Ceiling on any day-by-day walk. A duration arriving from a corrupted file
#: as several million days would otherwise spin here rather than being drawn
#: wrong and noticed.
MAX_STEPS = 200_000


def as_date(value: DateLike) -> date:
    """
    The calendar date of either a date or a datetime.

    RETURNS:
    --------
    date
        The day `value` falls on, with any time of day discarded. Used for
        holiday comparison, so a holiday listed as a date matches a task
        whose start carries a time.
    """
    return value.date() if isinstance(value, datetime) else value


class WorkingCalendar:
    """
    Which days a project works, and the arithmetic that follows from it.

    ATTRIBUTES:
    -----------
    non_working_days : Set[int]
        Weekday indices that are never worked, as date.weekday() numbers
        them (Monday 0 ... Sunday 6). Saturday and Sunday by default.
    holidays : Set[date]
        Individual dates that are not worked, whatever weekday they land on.
    recurring_holidays : Set[Tuple[int, int]]
        (month, day) pairs not worked in any year - the fixed-date national
        holidays a plan spanning several years would otherwise have to list
        once per year.

    DEVELOPMENT NOTES:
    ------------------
    A calendar that works no weekday at all cannot answer "when does this
    finish", and every loop here would run to MAX_STEPS looking for a working
    day that does not exist. Rather than hang or raise deep inside a redraw,
    such a calendar is treated as working every day and says so in the log:
    an unusable calendar should degrade to plain calendar-day arithmetic, not
    take the window down with it.
    """

    def __init__(self,
                 non_working_days: Optional[Iterable[int]] = None,
                 holidays: Optional[Iterable[DateLike]] = None,
                 recurring_holidays: Optional[Iterable[Tuple[int, int]]] = None):
        self.non_working_days: Set[int] = (
            set(non_working_days) if non_working_days is not None
            else set(DEFAULT_NON_WORKING_DAYS)
        )
        self.holidays: Set[date] = {as_date(d) for d in (holidays or ())}
        self.recurring_holidays: Set[Tuple[int, int]] = {
            (int(month), int(day)) for month, day in (recurring_holidays or ())
        }
        #: Whether the "no weekday is worked" warning has already been given.
        #: It is answered on every date the calendar is asked about, and a
        #: single redraw asks about thousands.
        self._empty_week_reported = False

    # ---- what the calendar is ------------------------------------------

    @property
    def works_any_weekday(self) -> bool:
        """Whether at least one weekday is worked."""
        return bool(set(range(7)) - self.non_working_days)

    def is_working_day(self, check_date: DateLike) -> bool:
        """
        Whether work happens on the given date.

        RETURNS:
        --------
        bool
            False for a non-working weekday, a listed holiday or a recurring
            holiday; True otherwise.
        """
        if not self.works_any_weekday:
            # See the note on the class: an empty week is no calendar at all
            if not self._empty_week_reported:
                self._empty_week_reported = True
                logger.warning(
                    "Working calendar marks every weekday non-working; "
                    "treating every day as a working day instead"
                )
            return True

        if check_date.weekday() in self.non_working_days:
            return False

        day = as_date(check_date)
        if (day.month, day.day) in self.recurring_holidays:
            return False
        if day in self.holidays:
            return False
        return True

    # ---- moving to a working day ---------------------------------------

    def get_next_working_day(self, current_date: DateLike) -> DateLike:
        """
        The first working day on or after the given date.

        This is the start-date enforcement rule: a task moved onto a Saturday
        starts on the Monday instead. A date that is already a working day is
        returned unchanged.
        """
        return self._seek(current_date, step=1)

    def get_previous_working_day(self, current_date: DateLike) -> DateLike:
        """
        The last working day on or before the given date.

        The mirror of get_next_working_day, used when a link fixes a task's
        finish rather than its start.
        """
        return self._seek(current_date, step=-1)

    def _seek(self, current_date: DateLike, step: int) -> DateLike:
        """Walk one day at a time until a working day is reached."""
        moved = current_date
        for _ in range(MAX_STEPS):
            if self.is_working_day(moved):
                return moved
            moved += timedelta(days=step)

        logger.warning(
            "No working day found within %d days of %s; leaving it where it "
            "is", MAX_STEPS, current_date
        )
        return current_date

    # ---- durations and dates -------------------------------------------

    def add_working_days(self, start_date: DateLike,
                         duration_days: int) -> DateLike:
        """
        The inclusive finish date of a task, given its working duration.

        PARAMETERS:
        -----------
        start_date : DateLike
            Requested start. Pushed to the next working day first, so the
            answer never counts from a Saturday.
        duration_days : int
            Working days of effort, the start day included.

        RETURNS:
        --------
        DateLike
            The last day worked. A duration of one day finishes on the day it
            starts, matching Task.end_date, which is inclusive.

        DEVELOPMENT NOTES:
        ------------------
        Duration is spent only on working days, so the walk passes over a
        weekend without consuming any of it - the task pauses on the Saturday
        and resumes on the Monday, finishing further out in calendar time
        while still holding the same effort.
        """
        if duration_days <= 0:
            return start_date

        current = self.get_next_working_day(start_date)
        remaining = duration_days

        for _ in range(MAX_STEPS):
            if remaining <= 1:
                return current
            current += timedelta(days=1)
            if self.is_working_day(current):
                remaining -= 1

        logger.warning("Duration of %s days from %s did not resolve within "
                       "%d steps", duration_days, start_date, MAX_STEPS)
        return current

    def subtract_working_days(self, end_date: DateLike,
                              duration_days: int) -> DateLike:
        """
        The inclusive start date of a task, given its finish and duration.

        The mirror of add_working_days, for a plan that states when work has
        to be finished and works backwards from it.
        """
        if duration_days <= 0:
            return end_date

        current = self.get_previous_working_day(end_date)
        remaining = duration_days

        for _ in range(MAX_STEPS):
            if remaining <= 1:
                return current
            current -= timedelta(days=1)
            if self.is_working_day(current):
                remaining -= 1

        logger.warning("Duration of %s days back from %s did not resolve "
                       "within %d steps", duration_days, end_date, MAX_STEPS)
        return current

    def working_days_between(self, start_date: DateLike,
                             end_date: DateLike) -> int:
        """
        How many working days a pair of inclusive dates covers.

        RETURNS:
        --------
        int
            The working effort the span holds. Zero when the span runs
            backwards, or when it falls entirely on non-working days - a
            "task" occupying only a Saturday and a Sunday holds no work.

        DEVELOPMENT NOTES:
        ------------------
        This is add_working_days read the other way round, and the two agree:
        add_working_days(start, working_days_between(start, end)) lands back
        on the last working day of the span.
        """
        if as_date(end_date) < as_date(start_date):
            return 0

        worked = 0
        current = as_date(start_date)
        last = as_date(end_date)
        for _ in range(MAX_STEPS):
            if current > last:
                break
            if self.is_working_day(current):
                worked += 1
            current += timedelta(days=1)
        return worked

    @staticmethod
    def elapsed_days(start_date: DateLike, end_date: DateLike) -> int:
        """
        How many calendar days a pair of inclusive dates spans.

        The weekends are in this number and not in working_days_between; the
        difference between the two is what the chart draws.
        """
        span = (as_date(end_date) - as_date(start_date)).days + 1
        return max(span, 0)

    # ---- storage --------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Convert the calendar to a JSON-safe dictionary."""
        return {
            'non_working_days': sorted(self.non_working_days),
            'holidays': sorted(day.isoformat() for day in self.holidays),
            'recurring_holidays': sorted(
                [month, day] for month, day in self.recurring_holidays
            ),
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> 'WorkingCalendar':
        """
        Rebuild a calendar from a saved dictionary.

        Anything missing or unreadable falls back to the standard week, so a
        file saved before projects carried a calendar - or one whose calendar
        block is damaged - still opens on Monday to Friday.
        """
        if not data:
            return cls()

        non_working = data.get('non_working_days')
        try:
            non_working = ({int(day) for day in non_working}
                           if non_working is not None else None)
        except (TypeError, ValueError):
            logger.warning("Unreadable non-working days %r; using the "
                           "standard week", data.get('non_working_days'))
            non_working = None

        holidays = set()
        for entry in data.get('holidays') or ():
            try:
                holidays.add(date.fromisoformat(str(entry)[:10]))
            except ValueError:
                logger.warning("Ignoring unreadable holiday %r", entry)

        recurring = set()
        for entry in data.get('recurring_holidays') or ():
            try:
                month, day = entry
                recurring.add((int(month), int(day)))
            except (TypeError, ValueError):
                logger.warning("Ignoring unreadable recurring holiday %r",
                               entry)

        return cls(non_working_days=non_working, holidays=holidays,
                   recurring_holidays=recurring)

    def __eq__(self, other: object) -> bool:
        """Two calendars are the same when they name the same days."""
        if not isinstance(other, WorkingCalendar):
            return NotImplemented
        return (self.non_working_days == other.non_working_days
                and self.holidays == other.holidays
                and self.recurring_holidays == other.recurring_holidays)

    def __repr__(self) -> str:
        return (f"WorkingCalendar(non_working_days={sorted(self.non_working_days)}, "
                f"holidays={len(self.holidays)}, "
                f"recurring_holidays={len(self.recurring_holidays)})")


#: The calendar used when nothing else has been said: Monday to Friday, no
#: holidays. Held as a module-level instance so a Task measuring its own
#: duration agrees with a Project scheduling it. A project carrying its own
#: calendar - one imported from a file that declared holidays - passes that
#: one in explicitly rather than mutating this.
DEFAULT_CALENDAR = WorkingCalendar()


def default_calendar() -> WorkingCalendar:
    """The standard Monday-to-Friday calendar."""
    return DEFAULT_CALENDAR


@dataclass
class CalendarTask:
    """
    A task reduced to the calendar arithmetic, with nothing else attached.

    WHY THIS EXISTS:
    ================
    models.Task carries a plan's worth of state - links, progress, colour,
    hierarchy - and the scheduling rules above are hard to see through it.
    This is the same rules with only the three things they depend on, which
    makes them straightforward to reason about and to test:

        >>> task = CalendarTask(id="T1", name="Backend API", duration_days=5,
        ...                     start_date=date(2026, 9, 10))   # a Thursday
        >>> task.end_date                       # Thu, Fri, [weekend], Mon-Wed
        datetime.date(2026, 9, 16)
        >>> task.duration_days, task.total_elapsed_days
        (5, 7)

    ATTRIBUTES:
    -----------
    id, name : str
        Identity, so a set of these can stand in for a plan.
    duration_days : int
        Working days of effort.
    start_date : date
        Requested start; a weekend one is pushed to the Monday.
    calendar : WorkingCalendar
        Which days are worked. The standard week unless given one.
    """

    id: str
    name: str
    duration_days: int
    start_date: date
    calendar: WorkingCalendar = field(default_factory=WorkingCalendar)

    @property
    def effective_start_date(self) -> date:
        """The day work actually begins, a weekend start having been pushed."""
        return self.calendar.get_next_working_day(self.start_date)

    @property
    def end_date(self) -> date:
        """The last day worked, weekends crossed without spending duration."""
        return self.calendar.add_working_days(self.effective_start_date,
                                              self.duration_days)

    @property
    def total_elapsed_days(self) -> int:
        """Calendar days spanned, weekends included."""
        return self.calendar.elapsed_days(self.effective_start_date,
                                          self.end_date)
