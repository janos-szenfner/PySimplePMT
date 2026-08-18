"""
The named calendars a plan can hold, and which one a given task follows.

WHY THIS MODULE EXISTS:
======================
A plan does not always run on one week. A migration that can only touch
production at the weekend, a load test that runs unattended around the clock,
and the ordinary Monday-to-Friday work that surrounds them are three different
answers to "is this day worked", inside one project. Scheduling all three
against the project's calendar puts the migration on a Tuesday and stretches
the load test over two weekends it was actually running through.

So a calendar stops being a property of the plan alone and becomes something a
task can name. This module holds the naming: a registry of calendars, each
with an id and a readable name, and the resolution rule that turns a task's
`calendar_id` into the calendar it is actually scheduled on.

The rule is deliberately one line long:

    a task with a calendar_id naming a registered calendar follows it;
    every other task follows the project's own.

That covers the task that names nothing, the task written before the registry
existed, and - the case worth being careful about - the task naming a calendar
that has since been deleted. All three fall back to the project default, which
is the only answer that cannot leave a task with no calendar at all.

DEVELOPMENT NOTES:
------------------
There is no calendar class here. The calendars are gantt_app.workdaycalendar's
WorkingCalendar, the same one the project has always used, and everything they
can express - non-working weekdays, listed and recurring holidays, observed
countries, manual date overrides and the priority between them - they express
here unchanged. A second calendar type with its own arithmetic was the obvious
shape and the wrong one: the scheduler would then have to know which kind it
had been handed, and the day-by-day walks would exist twice, which is exactly
the duplication workdaycalendar was written to end.

What a registry adds is a *name* and an *id*, and those are all it adds.

The project's own calendar is not held here. It stays on Project, where it has
always been, and is passed in to resolve() as the fallback. Moving it in would
have given the default two homes and a way for them to disagree; leaving it
out means a project with no registry at all behaves exactly as it did before.

This sits beside models.py rather than under utils/ for the same reason
workdaycalendar does: models imports it, and everything in utils imports
models, so reaching back into that package from here would run
gantt_app.utils.__init__ mid-import and deadlock.
"""

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple
import logging
import re

from gantt_app.workdaycalendar import WorkingCalendar

logger = logging.getLogger(__name__)

#: What a task's calendar_id holds when it follows the plan's own calendar.
#: None rather than an id for the default, so a plan that never touches this
#: feature carries no calendar ids at all and reads back exactly as it did.
PROJECT_DEFAULT: Optional[str] = None

#: How the project's own calendar is labelled wherever calendars are listed.
#: Held here rather than in the dialogs, because three of them say it and a
#: fourth would have spelt it differently.
PROJECT_DEFAULT_LABEL = "Project Default"

#: Ids are generated from the name, so a calendar called "Weekend Shift"
#: becomes "weekend-shift" and a file stays readable.
_NON_SLUG = re.compile(r'[^a-z0-9]+')


def slugify(name: str) -> str:
    """
    An id built from a readable name.

    RETURNS:
    --------
    str
        Lower case, with runs of anything else collapsed to a single dash.
        'calendar' when the name has nothing usable in it, so an id is always
        a non-empty string - make_id below is what keeps it unique.
    """
    slug = _NON_SLUG.sub('-', str(name).strip().lower()).strip('-')
    return slug or 'calendar'


@dataclass
class NamedCalendar:
    """
    One calendar in the registry, with the name a reader chooses it by.

    ATTRIBUTES:
    -----------
    id : str
        What a task's calendar_id points at. Stable for the life of the
        calendar: renaming changes the name and leaves this alone, or every
        task following it would come loose - see CalendarRegistry.rename.
    name : str
        What the dropdowns show.
    calendar : WorkingCalendar
        The week, the holidays and the overrides. An ordinary calendar; see
        the note on the module about why there is no second calendar type.
    """

    id: str
    name: str
    calendar: WorkingCalendar

    def to_dict(self) -> Dict[str, Any]:
        """Convert the calendar to a JSON-safe dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'calendar': self.calendar.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Any) -> Optional['NamedCalendar']:
        """
        Rebuild one named calendar from a saved dictionary.

        RETURNS:
        --------
        Optional[NamedCalendar]
            None when the entry cannot be read, so one damaged calendar is
            dropped with a line in the log rather than costing the reader the
            rest of the registry - and, through it, the project file. A task
            pointing at the dropped one falls back to the project default,
            which is what resolve() does for an unknown id anyway.
        """
        if not isinstance(data, dict):
            logger.warning("Ignoring unreadable calendar %r", data)
            return None

        identifier = str(data.get('id') or '').strip()
        if not identifier:
            logger.warning("Ignoring a calendar with no id: %r", data)
            return None

        return cls(
            id=identifier,
            name=str(data.get('name') or identifier),
            calendar=WorkingCalendar.from_dict(data.get('calendar')),
        )


class CalendarRegistry:
    """
    Every named calendar a plan holds, and the rule for choosing one.

    PARAMETERS:
    -----------
    calendars : Iterable[NamedCalendar]
        The calendars to start with, in the order they should be listed.

    DEVELOPMENT NOTES:
    ------------------
    Ordered, and deliberately. A dictionary keyed by id would be the obvious
    store and would list the calendars in whatever order they were added,
    which is the order the dropdown would show them in and the order the file
    would save them in - so adding one would reshuffle a saved plan's list.
    Insertion order is kept and the id lookup is a dict built beside it.
    """

    def __init__(self, calendars: Iterable[NamedCalendar] = ()):
        #: The calendars in display order.
        self._calendars: List[NamedCalendar] = []
        #: The same objects by id, for resolve(), which is called for every
        #: task on every reschedule.
        self._by_id: Dict[str, NamedCalendar] = {}

        for named in calendars:
            self.add(named)

    # ---- what is in it -------------------------------------------------

    def __len__(self) -> int:
        return len(self._calendars)

    def __iter__(self):
        return iter(self._calendars)

    def __bool__(self) -> bool:
        return bool(self._calendars)

    def __contains__(self, calendar_id: object) -> bool:
        return calendar_id in self._by_id

    def __eq__(self, other: object) -> bool:
        """Two registries are the same when they hold the same list."""
        if not isinstance(other, CalendarRegistry):
            return NotImplemented
        return self._calendars == other._calendars

    def __repr__(self) -> str:
        return (f"CalendarRegistry({[named.id for named in self._calendars]!r})")

    def get(self, calendar_id: Optional[str]) -> Optional[NamedCalendar]:
        """The named calendar with this id, or None when there is not one."""
        if not calendar_id:
            return None
        return self._by_id.get(calendar_id)

    def ids(self) -> List[str]:
        """Every id held, in display order."""
        return [named.id for named in self._calendars]

    def options(self) -> List[Tuple[Optional[str], str]]:
        """
        Every choice a calendar dropdown should offer, in order.

        RETURNS:
        --------
        List[Tuple[Optional[str], str]]
            (id, label) pairs, the project's own calendar first as
            (None, PROJECT_DEFAULT_LABEL). The default leads because it is
            what most tasks follow and what a reader is putting a task back
            to when they change this.
        """
        return ([(PROJECT_DEFAULT, PROJECT_DEFAULT_LABEL)]
                + [(named.id, named.name) for named in self._calendars])

    # ---- the rule ------------------------------------------------------

    def resolve(self, calendar_id: Optional[str],
                default: WorkingCalendar) -> WorkingCalendar:
        """
        The calendar a task actually follows.

        PARAMETERS:
        -----------
        calendar_id : Optional[str]
            What the task names, which may be None, or may name a calendar
            that no longer exists.
        default : WorkingCalendar
            The project's own calendar, used whenever the id does not lead
            anywhere.

        RETURNS:
        --------
        WorkingCalendar
            The named calendar, or `default`.

        DEVELOPMENT NOTES:
        ------------------
        The unknown id falls back rather than raising, and that is the whole
        reason this is a method and not a dictionary lookup at the call site.
        A calendar can be deleted while tasks still point at it, and a plan
        that will not open - or a task with no calendar at all, which would
        hang the day-by-day walks - is a far worse answer than a task
        quietly back on the standard week. It is said once per id, at debug,
        because resolve is called for every task on every reschedule.
        """
        if not calendar_id:
            return default

        named = self._by_id.get(calendar_id)
        if named is None:
            logger.debug("No calendar %r; falling back to the project's own",
                         calendar_id)
            return default
        return named.calendar

    # ---- changing it ---------------------------------------------------

    def add(self, named: NamedCalendar) -> NamedCalendar:
        """
        Put a calendar in the registry, replacing any with the same id.

        RETURNS:
        --------
        NamedCalendar
            The calendar stored. Replacing keeps its position in the list, so
            editing one does not move it to the bottom of every dropdown.
        """
        existing = self._by_id.get(named.id)
        if existing is not None:
            self._calendars[self._calendars.index(existing)] = named
        else:
            self._calendars.append(named)

        self._by_id[named.id] = named
        return named

    def create(self, name: str,
               calendar: Optional[WorkingCalendar] = None) -> NamedCalendar:
        """
        Build a calendar from a name and add it, giving it a unique id.

        RETURNS:
        --------
        NamedCalendar
            The calendar added. Its id comes from the name; see make_id for
            what happens when that name is already taken.
        """
        named = NamedCalendar(id=self.make_id(name), name=str(name),
                              calendar=calendar or WorkingCalendar())
        return self.add(named)

    def make_id(self, name: str) -> str:
        """
        An id from a name that nothing in the registry is using yet.

        A second "Weekend Shift" becomes `weekend-shift-2` rather than taking
        the first one's id, which would silently move every task following the
        first onto the second.
        """
        base = slugify(name)
        if base not in self._by_id:
            return base

        for suffix in range(2, len(self._by_id) + 3):
            candidate = f"{base}-{suffix}"
            if candidate not in self._by_id:
                return candidate

        # Unreachable while the loop runs past the number of ids held, but a
        # generated id must never collide, so this does not rely on that.
        return f"{base}-{len(self._by_id) + 1}"

    def rename(self, calendar_id: str, name: str) -> bool:
        """
        Change what a calendar is called, leaving its id alone.

        RETURNS:
        --------
        bool
            True when there was one to rename. The id is deliberately not
            rebuilt from the new name: every task following this calendar
            names it by id, and changing that would come loose from all of
            them at once.
        """
        named = self._by_id.get(calendar_id)
        if named is None:
            return False
        named.name = str(name)
        return True

    def remove(self, calendar_id: str) -> bool:
        """
        Drop a calendar from the registry.

        RETURNS:
        --------
        bool
            True when there was one to drop. Tasks still naming it are not
            touched here - they fall back to the project's own calendar
            through resolve, which is what makes deleting one safe without
            walking the whole plan.
        """
        named = self._by_id.pop(calendar_id, None)
        if named is None:
            return False
        self._calendars.remove(named)
        return True

    # ---- storage --------------------------------------------------------

    def to_dict(self) -> List[Dict[str, Any]]:
        """
        Convert the registry to a JSON-safe list, in display order.

        A list rather than a dictionary keyed by id, so the order a reader
        put them in is the order they come back in - see the note on the
        class.
        """
        return [named.to_dict() for named in self._calendars]

    @classmethod
    def from_dict(cls, data: Any) -> 'CalendarRegistry':
        """
        Rebuild a registry from a saved list.

        Anything missing gives an empty registry, so a plan saved before
        calendars could be named - or one whose registry is damaged - opens
        with every task on the project's own calendar, which is what those
        plans meant anyway.
        """
        if not data:
            return cls()

        # A dictionary keyed by id is accepted as well as a list. That is the
        # shape the feature was specified in, and a hand-written file is
        # likelier to arrive that way than to be rejected for it.
        entries = data.values() if isinstance(data, dict) else data

        calendars = []
        try:
            for entry in entries:
                named = NamedCalendar.from_dict(entry)
                if named is not None:
                    calendars.append(named)
        except TypeError:
            logger.warning("Unreadable calendar registry %r; using none", data)
            return cls()

        return cls(calendars)


# ---------------------------------------------------------------------------
# The calendars a plan is offered before anyone has built one
# ---------------------------------------------------------------------------

#: The presets, as (id, name, worked weekday indices). Monday is 0, as
#: date.weekday() numbers them and as WorkingCalendar stores the inverse of.
#:
#: These three are the cases that come up often enough to be worth not making
#: anybody build by hand: work that can only happen at the weekend, work that
#: runs unattended through it, and the standard week itself for a task being
#: put back to it explicitly rather than by clearing its calendar.
PRESETS: Tuple[Tuple[str, str, Tuple[int, ...]], ...] = (
    ('standard-week', 'Standard Week', (0, 1, 2, 3, 4)),
    ('weekend-shift', 'Weekend-Only Shift', (5, 6)),
    ('continuous', '24/7 Continuous Run', (0, 1, 2, 3, 4, 5, 6)),
)


def preset_calendar(identifier: str, name: str,
                    worked: Iterable[int]) -> NamedCalendar:
    """
    One preset, as a named calendar.

    PARAMETERS:
    -----------
    worked : Iterable[int]
        The weekday indices that *are* worked. Inverted here, once, because
        WorkingCalendar stores the days that are not - see PRESETS.
    """
    worked = {int(day) for day in worked}
    return NamedCalendar(
        id=identifier, name=name,
        calendar=WorkingCalendar(non_working_days=set(range(7)) - worked),
    )


def default_registry() -> CalendarRegistry:
    """
    The registry a new plan starts with: the three presets.

    DEVELOPMENT NOTES:
    ------------------
    Offered rather than imposed. Every task still follows the project's own
    calendar until one is chosen for it, so a plan that never opens the
    dropdown is scheduled exactly as it was before any of this existed - the
    presets only mean nobody has to build a weekend calendar from scratch to
    find out what the feature does.
    """
    return CalendarRegistry(
        preset_calendar(identifier, name, worked)
        for identifier, name, worked in PRESETS
    )


def describe_week(calendar: WorkingCalendar) -> str:
    """
    A short readable summary of which days a calendar works.

    Used beside a calendar's name where a reader is choosing one, because the
    name alone does not say what picking it will do to a task's dates.
    """
    names = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')
    worked = [index for index in range(7)
              if index not in calendar.non_working_days]

    if not worked:
        return "no days worked"
    if len(worked) == 7:
        return "every day"
    if worked == [0, 1, 2, 3, 4]:
        return "Mon-Fri"
    if worked == [5, 6]:
        return "Sat-Sun"
    return ', '.join(names[index] for index in worked)
