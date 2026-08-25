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
  1a. A date the user has overridden by hand beats both. An override says
     "this specific date is worked" or "this specific date is not", and it is
     the first thing consulted - a Saturday named as a make-up day is worked,
     and a working Tuesday named as a shutdown is not. Nothing else in the
     calendar can overturn it, which is the point of it: the reason a plan
     needs an override at all is that the general rules got this one date
     wrong.
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
import importlib
import importlib.util
import logging
import re

logger = logging.getLogger(__name__)

#: Either kind of date the application deals in.
DateLike = Union[date, datetime]

#: Weekday indices, Monday first, as date.weekday() numbers them.
MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY, SATURDAY, SUNDAY = range(7)

#: The standard week: Monday to Friday worked, the weekend not.
DEFAULT_NON_WORKING_DAYS: Set[int] = {SATURDAY, SUNDAY}

#: Every weekday, built once. works_any_weekday subtracts the non-working
#: days from this, and it was rebuilding `set(range(7))` on every call - of
#: which one chart redraw makes over two hundred thousand.
_ALL_WEEKDAYS: frozenset = frozenset(range(7))

#: Ceiling on any day-by-day walk. A duration arriving from a corrupted file
#: as several million days would otherwise spin here rather than being drawn
#: wrong and noticed.
MAX_STEPS = 200_000

#: The 27 EU member states, by ISO 3166-1 alpha-2 code.
#:
#: Held here rather than in the dialog that lists them: which countries a
#: calendar can observe is a property of the calendar, and the dialog is one
#: way of choosing among them.
EU_COUNTRIES: Dict[str, str] = {
    "AT": "Austria", "BE": "Belgium", "BG": "Bulgaria", "HR": "Croatia",
    "CY": "Cyprus", "CZ": "Czechia", "DK": "Denmark", "EE": "Estonia",
    "FI": "Finland", "FR": "France", "DE": "Germany", "GR": "Greece",
    "HU": "Hungary", "IE": "Ireland", "IT": "Italy", "LV": "Latvia",
    "LT": "Lithuania", "LU": "Luxembourg", "MT": "Malta", "NL": "Netherlands",
    "PL": "Poland", "PT": "Portugal", "RO": "Romania", "SK": "Slovakia",
    "SI": "Slovenia", "ES": "Spain", "SE": "Sweden",
}

#: What each region of the world is called in the country picker, in the
#: order the picker shows them.
#:
#: Held here beside EU_COUNTRIES and for the same reason: which countries a
#: calendar can observe, and how they group, is a property of the calendar
#: rather than of the dialog that happens to list them.
REGION_AFRICA_MIDDLE_EAST = "Africa & Middle East Region"
REGION_AMERICA = "America Region"
REGION_ASIA_PACIFIC = "Asia Pacific Region"
REGION_EUROPE = "Europe Region"
REGION_OTHER = "Other Territories"

#: The regions in the order the picker lists them: alphabetical, with the
#: territories that belong to no region last.
REGION_ORDER: Tuple[str, ...] = (
    REGION_AFRICA_MIDDLE_EAST,
    REGION_AMERICA,
    REGION_ASIA_PACIFIC,
    REGION_EUROPE,
    REGION_OTHER,
)

#: Which region each country sits in, by ISO 3166-1 alpha-2 code.
#:
#: DEVELOPMENT NOTES:
#: ------------------
#: A country that straddles two continents is placed where somebody looking
#: for it in a picker would look, not where the UN geoscheme puts it. Turkey,
#: Russia, Armenia, Azerbaijan, Georgia and Cyprus are all listed under
#: Europe on that basis; the geoscheme has the first five in Asia.
#:
#: The sub-Antarctic and uninhabited territories go to Other Territories
#: rather than being forced into a continent, because any continent would be
#: a guess and none of them has a public holiday to observe anyway.
#:
#: Anything absent falls to Other Territories rather than being dropped - see
#: region_of. The holidays package gains countries between releases, and one
#: arriving in an odd group is a great deal better than one vanishing from a
#: list somebody is choosing from.
#:
#: That is not a substitute for keeping this list current, and there is a test
#: that fails when the package knows a country this does not. It found Kosovo
#: that way: the package added XK in a release after the one this was written
#: against, and on a machine with the newer version it was quietly filed under
#: Other Territories at the bottom of the picker. Checked against 0.103, which
#: is the newest release as of August 2026, and complete to there.
COUNTRY_REGIONS: Dict[str, str] = {}

COUNTRY_REGIONS.update(dict.fromkeys((
    # Africa
    "AO", "BF", "BI", "BJ", "BW", "CD", "CF", "CG", "CI", "CM", "CV", "DJ",
    "DZ", "EG", "EH", "ER", "ET", "GA", "GH", "GM", "GN", "GQ", "GW", "KE",
    "KM", "LR", "LS", "LY", "MA", "MG", "ML", "MR", "MU", "MW", "MZ", "NA",
    "NE", "NG", "RE", "RW", "SC", "SD", "SH", "SL", "SN", "SO", "SS", "ST",
    "SZ", "TD", "TG", "TN", "TZ", "UG", "YT", "ZA", "ZM", "ZW",
    # Middle East
    "AE", "BH", "IL", "IQ", "IR", "JO", "KW", "LB", "OM", "PS", "QA", "SA",
    "SY", "YE",
), REGION_AFRICA_MIDDLE_EAST))

COUNTRY_REGIONS.update(dict.fromkeys((
    "AG", "AI", "AR", "AW", "BB", "BL", "BM", "BO", "BQ", "BR", "BS", "BZ",
    "CA", "CL", "CO", "CR", "CU", "CW", "DM", "DO", "EC", "FK", "GD", "GF",
    "GL", "GP", "GT", "GY", "HN", "HT", "JM", "KN", "KY", "LC", "MF", "MQ",
    "MS", "MX", "NI", "PA", "PE", "PM", "PR", "PY", "SR", "SV", "SX", "TC",
    "TT", "US", "UY", "VC", "VE", "VG", "VI",
), REGION_AMERICA))

COUNTRY_REGIONS.update(dict.fromkeys((
    "AF", "AS", "AU", "BD", "BN", "BT", "CC", "CK", "CN", "CX", "FJ", "FM",
    "GU", "HK", "ID", "IN", "IO", "JP", "KH", "KG", "KI", "KP", "KR", "KZ",
    "LA", "LK", "MH", "MM", "MN", "MO", "MP", "MV", "MY", "NC", "NF", "NP",
    "NR", "NU", "NZ", "PF", "PG", "PH", "PK", "PN", "PW", "SB", "SG", "TH",
    "TJ", "TK", "TL", "TM", "TO", "TV", "TW", "UM", "UZ", "VN", "VU", "WF",
    "WS",
), REGION_ASIA_PACIFIC))

COUNTRY_REGIONS.update(dict.fromkeys((
    "AD", "AL", "AM", "AT", "AX", "AZ", "BA", "BE", "BG", "BY", "CH", "CY",
    "CZ", "DE", "DK", "EE", "ES", "FI", "FO", "FR", "GB", "GE", "GG", "GI",
    "GR", "HR", "HU", "IE", "IM", "IS", "IT", "JE", "LI", "LT", "LU", "LV",
    "MC", "MD", "ME", "MK", "MT", "NL", "NO", "PL", "PT", "RO", "RS", "RU",
    "SE", "SI", "SJ", "SK", "SM", "TR", "UA", "VA", "XK",
), REGION_EUROPE))

COUNTRY_REGIONS.update(dict.fromkeys((
    "AQ", "BV", "GS", "HM", "TF",
), REGION_OTHER))


def region_of(code: str) -> str:
    """
    Which region a country is listed under.

    PARAMETERS:
    -----------
    code : str
        An ISO 3166-1 alpha-2 country code, or a country and subdivision -
        "DE-BY" - in which case the country decides.

    RETURNS:
    --------
    str
        One of REGION_ORDER. A country the table does not name falls to
        Other Territories rather than being dropped from the picker.
    """
    country = str(code or '').strip().upper().split(SUBDIVISION_SEPARATOR)[0]
    return COUNTRY_REGIONS.get(country, REGION_OTHER)


#: Every country the holidays package knows, worked out once. None until it
#: has been asked for; see supported_countries.
_country_names: Optional[Dict[str, str]] = None

#: Splits a CamelCase class name into words, leaving an acronym intact:
#: "UnitedStates" becomes "United States" and "HolidaysUK" keeps its UK.
_CAMEL_BOUNDARY = re.compile(r'(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])')


def supported_countries() -> Dict[str, str]:
    """
    Every country whose public holidays can be observed, code to name.

    RETURNS:
    --------
    Dict[str, str]
        ISO 3166-1 alpha-2 codes mapped to a readable name, sorted by name.
        The 27 EU member states alone when the `holidays` package is missing,
        so the picker still has something to show and a selection made before
        it was uninstalled still reads back.

    DEVELOPMENT NOTES:
    ------------------
    Read from the package's own registry rather than kept as a table here.
    There are around 250 of them, they change as the package adds support,
    and a copy would be wrong the first time one was added - which is the
    whole reason the dates are not kept here either.

    The registry gives a class name rather than a country name, so the
    CamelCase is split back into words. It is not a substitute for a proper
    ISO name table, but "Bosnia And Herzegovina" is recognisable and needs no
    second dependency to produce.

    Worked out once: the registry is stable for the life of the process, and
    the picker asks for it every time it opens.
    """
    global _country_names

    if _country_names is not None:
        return _country_names

    try:
        from holidays.registry import COUNTRIES
    except ImportError:
        logger.debug("The holidays package is absent; offering the EU only")
        _country_names = dict(EU_COUNTRIES)
        return _country_names

    found = {}
    for entry in COUNTRIES.values():
        try:
            class_name, code = entry[0], entry[1]
        except (IndexError, TypeError):
            continue
        found[str(code)] = _CAMEL_BOUNDARY.sub(' ', str(class_name))

    # The EU names are spelt here deliberately - "Czechia" reads better than
    # whatever the class happens to be called - so they win where they differ
    found.update(EU_COUNTRIES)

    _country_names = dict(sorted(found.items(), key=lambda item: item[1]))
    logger.debug("Holiday calendars available for %d countries",
                 len(_country_names))
    return _country_names


#: Subdivisions per country, worked out on demand and kept. Building one
#: country's list means importing its module, which is not free across 250 of
#: them - and most callers ask about a handful.
_subdivision_names: Dict[str, Dict[str, str]] = {}

#: How a subdivision is written in a saved calendar and in the picker:
#: the country, this, then the subdivision - "DE-BY" for Bavaria. It is the
#: ISO 3166-2 form, and it keeps a selection a plain list of strings, so a
#: calendar saved before subdivisions existed still reads back.
SUBDIVISION_SEPARATOR = '-'


def split_country(entry: str) -> Tuple[str, Optional[str]]:
    """
    Separate a selection entry into its country and its subdivision.

    PARAMETERS:
    -----------
    entry : str
        Either a country code - "DE" - or a country and a subdivision -
        "DE-BY".

    RETURNS:
    --------
    Tuple[str, Optional[str]]
        The country code, and the subdivision or None for the country as a
        whole.
    """
    country, separator, subdivision = str(entry).strip().upper().partition(
        SUBDIVISION_SEPARATOR
    )
    return country, (subdivision or None) if separator else None


def subdivisions(country: str) -> Dict[str, str]:
    """
    The regions of a country that keep holidays of their own.

    PARAMETERS:
    -----------
    country : str
        An ISO 3166-1 alpha-2 country code.

    RETURNS:
    --------
    Dict[str, str]
        Subdivision code to name, sorted by name. Empty for a country whose
        holidays are all national, and for every country when the `holidays`
        package is missing.

    DEVELOPMENT NOTES:
    ------------------
    Roughly seventy of the countries have these, and they matter: Bavaria
    keeps three public holidays the rest of Germany works through, so a plan
    scheduled against Germany as a whole quietly puts work on days half the
    team is off - which is the entire reason this application observes
    holidays at all.

    The package holds the names as an alias table pointing the other way,
    name to code, so it is inverted here. A subdivision with no name in the
    table keeps its code, which is still better than dropping it.
    """
    country = str(country).strip().upper()
    if country in _subdivision_names:
        return _subdivision_names[country]

    try:
        import holidays as holidays_package
    except ImportError:
        _subdivision_names[country] = {}
        return {}

    try:
        codes = holidays_package.list_supported_countries().get(country) or []
    except Exception:
        logger.exception("Could not list the subdivisions of %r", country)
        codes = []

    names = {code: code for code in codes}
    try:
        registry = holidays_package.registry.COUNTRIES
        entry = next((value for value in registry.values()
                      if len(value) > 1 and value[1] == country), None)
        if entry is not None:
            module = importlib.import_module(
                f"holidays.countries.{_module_for(registry, country)}"
            )
            found = getattr(getattr(module, entry[0]),
                            'subdivisions_aliases', {}) or {}
            for name, code in found.items():
                if code in names:
                    names[code] = str(name)
    except Exception:
        logger.debug("No subdivision names for %r; using the codes", country)

    _subdivision_names[country] = dict(
        sorted(names.items(), key=lambda item: item[1])
    )
    return _subdivision_names[country]


def _module_for(registry, country: str) -> str:
    """The holidays submodule holding a country, by its code."""
    for key, value in registry.items():
        if len(value) > 1 and value[1] == country:
            return key
    return country.lower()


#: Whether the missing-package warning has already been given. Resolving a
#: year of holidays is attempted on every redraw of a plan whose calendar
#: names a country, and a log line per attempt would bury everything else.
_holidays_package_reported = False


def holidays_available() -> bool:
    """
    Whether public holidays can be looked up at all.

    RETURNS:
    --------
    bool
        True when the optional `holidays` package is installed. The dialog
        asks so it can say why the countries it is offering will not take
        effect, rather than letting the user tick 27 boxes for nothing.

    DEVELOPMENT NOTES:
    ------------------
    Asks the import system rather than importing, which is both cheaper and
    honest about what is being tested: whether the package is there, not
    whether it works. A package that is present but broken raises where it is
    actually used, in country_holidays, which already copes.
    """
    try:
        return importlib.util.find_spec('holidays') is not None
    except (ImportError, ValueError):
        return False


def country_holidays(codes: Iterable[str], year: int) -> Set[date]:
    """
    Every public holiday in the given countries for one year.

    PARAMETERS:
    -----------
    codes : Iterable[str]
        ISO 3166-1 alpha-2 country codes.
    year : int
        The calendar year to resolve.

    RETURNS:
    --------
    Set[date]
        The union across the countries: a date that is a holiday in any of
        them is in the set. Empty when the `holidays` package is missing.

    DEVELOPMENT NOTES:
    ------------------
    The package is asked rather than a table being kept here, because roughly
    half of these are Easter-dependent - Good Friday, Easter Monday, Whit
    Monday - and computing the paschal full moon per country per year is not
    something to reimplement badly. It also tracks the one-off substitutions
    that several member states make when a holiday falls on a weekend.

    `country_holidays()` is the package's documented entry point. The obvious
    `getattr(holidays, code)` works too but reaches into whatever the module
    happens to expose, and a code that is not a country - or one that collides
    with something else in the namespace - fails in a way that is hard to read.

    A code the package does not know is skipped with a warning rather than
    raising. The calendar is loaded from a project file, and one unknown code
    in it should cost that country's holidays, not the plan.
    """
    global _holidays_package_reported

    try:
        import holidays as holidays_package
    except ImportError:
        if not _holidays_package_reported:
            _holidays_package_reported = True
            logger.warning(
                "The 'holidays' package is not installed, so public holidays "
                "are not applied and plans are scheduled on weekends alone. "
                "Install it with: pip install holidays"
            )
        return set()

    merged: Set[date] = set()
    for entry in codes:
        country, subdivision = split_country(entry)
        try:
            found = holidays_package.country_holidays(
                country, subdiv=subdivision, years=year
            )
        except (NotImplementedError, KeyError, AttributeError, ValueError):
            if subdivision is not None:
                # A region the package does not know, or no longer knows.
                # Falling back to the country keeps the national holidays
                # rather than losing the entry altogether, which would be a
                # plan quietly scheduled through them.
                logger.warning(
                    "No holiday calendar for %r; observing %r as a whole",
                    entry, country
                )
                try:
                    found = holidays_package.country_holidays(country,
                                                              years=year)
                except Exception:
                    logger.warning("No holiday calendar for country %r either;"
                                   " ignoring it", country)
                    continue
            else:
                logger.warning("No holiday calendar for country %r; ignoring "
                               "it", country)
                continue
        merged.update(found.keys())

    return merged


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


@dataclass(frozen=True)
class DateOverride:
    """
    One date the user has ruled on by hand, and why.

    ATTRIBUTES:
    -----------
    override_date : date
        The single date this rules on. One date, not a range: a shutdown week
        is five of these, which keeps the rule for any given day answerable by
        a dictionary lookup rather than a scan.
    is_working_day : bool
        True to work a day the calendar would otherwise have taken off - a
        Saturday make-up day - and False to take a day off that the calendar
        would otherwise have worked.
    reason : str
        Why, in the user's words. Carried for the person reading the list back
        in six months, and shown in the overrides table; it takes no part in
        the arithmetic.

    DEVELOPMENT NOTES:
    ------------------
    Frozen, because these are kept in a dict keyed by their own date. A
    mutable override whose date was reassigned would sit under the wrong key
    and answer for a day it no longer names; changing one means replacing it,
    which is what add_override does.
    """

    override_date: date
    is_working_day: bool
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert the override to a JSON-safe dictionary."""
        return {
            'date': self.override_date.isoformat(),
            'is_working_day': bool(self.is_working_day),
            'reason': self.reason,
        }

    @classmethod
    def from_dict(cls, data: Any) -> Optional['DateOverride']:
        """
        Rebuild one override from a saved dictionary.

        RETURNS:
        --------
        Optional[DateOverride]
            None when the entry cannot be read, so one damaged row is dropped
            with a line in the log rather than costing the reader the rest of
            the list - and, through it, the project file.
        """
        if not isinstance(data, dict):
            logger.warning("Ignoring unreadable date override %r", data)
            return None
        try:
            day = date.fromisoformat(str(data.get('date'))[:10])
        except (TypeError, ValueError):
            logger.warning("Ignoring date override with an unreadable date %r",
                           data.get('date'))
            return None
        return cls(
            override_date=day,
            is_working_day=bool(data.get('is_working_day', True)),
            reason=str(data.get('reason') or ''),
        )


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
    countries : Set[str]
        What is observed, as ISO codes: a country - "DE" - or a country and
        one of its regions - "DE-BY" for Bavaria, which keeps three public
        holidays the rest of Germany works through. The union applies: a date
        that is a holiday in any of them is a holiday here. Resolved a year at
        a time through the `holidays` package - see country_holidays - which
        is what gets Easter Monday and the rest of the movable feasts right
        without any of them being listed.
    overrides : Dict[date, DateOverride]
        Dates the user has ruled on by hand, keyed by the date each names.
        These beat everything else here - see is_working_day - which is what
        makes a Saturday make-up day worked and a company shutdown on a
        Wednesday not.

    DEVELOPMENT NOTES:
    ------------------
    A calendar that works no weekday at all cannot answer "when does this
    finish", and every loop here would run to MAX_STEPS looking for a working
    day that does not exist. Rather than hang or raise deep inside a redraw,
    such a calendar is treated as working every day and says so in the log:
    an unusable calendar should degrade to plain calendar-day arithmetic, not
    take the window down with it.

    The four sources of a non-working day are deliberately all in one class.
    Country holidays could have been a calendar of their own - the obvious
    shape, and the wrong one: everything that schedules would then have to know
    which kind of calendar it had, and the arithmetic would exist twice. A
    calendar answers is_working_day; where the answer came from is its own
    business.

    The four general sources disagree with each other only by accident; an
    override disagrees on purpose, so it is consulted first and nothing gets
    to argue with it. The order is: an override, then a public holiday in an
    observed country, then a listed or recurring holiday, then the weekend.
    A date named as worked is worked even where it is Christmas Day - the
    person who typed it in could see that, and meant it anyway.
    """

    def __init__(self,
                 non_working_days: Optional[Iterable[int]] = None,
                 holidays: Optional[Iterable[DateLike]] = None,
                 recurring_holidays: Optional[Iterable[Tuple[int, int]]] = None,
                 countries: Optional[Iterable[str]] = None,
                 overrides: Optional[Iterable['DateOverride']] = None):
        #: Set through the property below, which keeps the cached answer to
        #: works_any_weekday in step with it.
        self._works_any_weekday: Optional[bool] = None
        self._cached_week_size: int = -1
        self.non_working_days = (
            set(non_working_days) if non_working_days is not None
            else set(DEFAULT_NON_WORKING_DAYS)
        )
        self.holidays: Set[date] = {as_date(d) for d in (holidays or ())}
        self.recurring_holidays: Set[Tuple[int, int]] = {
            (int(month), int(day)) for month, day in (recurring_holidays or ())
        }
        self.countries: Set[str] = {
            str(code).strip().upper() for code in (countries or ())
            if str(code).strip()
        }
        #: Manual rulings, by the date each names. A dict rather than a list
        #: because is_working_day asks "is this date overridden" for every day
        #: of every task on every redraw, and because a date can only be ruled
        #: on one way - a second ruling for a date replaces the first rather
        #: than leaving the calendar to choose between them.
        self.overrides: Dict[date, DateOverride] = {}
        for override in (overrides or ()):
            self.overrides[as_date(override.override_date)] = override
        #: Whether the "no weekday is worked" warning has already been given.
        #: It is answered on every date the calendar is asked about, and a
        #: single redraw asks about thousands.
        self._empty_week_reported = False
        #: Public holidays already worked out, by year; see _country_holidays.
        self._country_cache: Dict[int, Set[date]] = {}

    # ---- public holidays by country ------------------------------------

    def set_countries(self, codes: Iterable[str]) -> None:
        """
        Choose whose public holidays this calendar observes.

        PARAMETERS:
        -----------
        codes : Iterable[str]
            ISO codes: a country - "DE" - or a country and one of its regions
            - "DE-BY". An empty list observes none.
        """
        self.countries = {
            str(code).strip().upper() for code in codes if str(code).strip()
        }
        self._country_cache.clear()

    def _country_holidays(self, year: int) -> Set[date]:
        """
        Every public holiday in the selected countries for one year.

        RETURNS:
        --------
        Set[date]
            The union across the selected countries. Empty when none are
            selected, or when the `holidays` package is not installed.

        DEVELOPMENT NOTES:
        ------------------
        Worked out a year at a time and kept, because is_working_day is called
        for every day of every task on every redraw and building a country's
        year is not free.

        The `holidays` package is an optional dependency, like openpyxl for the
        spreadsheets. Missing, the countries are simply not observed and the
        plan is scheduled on weekends alone - a wrong holiday list is worth
        less than a plan that will not open. It is said once, not once per
        date.
        """
        if not self.countries:
            return frozenset()

        if year not in self._country_cache:
            self._country_cache[year] = country_holidays(self.countries, year)
        return self._country_cache[year]

    # ---- manual overrides ----------------------------------------------

    def add_override(self, override_date: DateLike, is_working_day: bool,
                     reason: str = "") -> 'DateOverride':
        """
        Rule on one date by hand, overturning every other rule for it.

        PARAMETERS:
        -----------
        override_date : DateLike
            The date being ruled on. Any time of day is discarded; an override
            names a day, not a moment.
        is_working_day : bool
            True to work a day the calendar would otherwise take off, False to
            take off a day it would otherwise work.
        reason : str
            Why, for the person reading the list back later.

        RETURNS:
        --------
        DateOverride
            The stored ruling. A date already overridden is replaced rather
            than duplicated - see the note on the attribute.
        """
        day = as_date(override_date)
        override = DateOverride(override_date=day,
                                is_working_day=bool(is_working_day),
                                reason=str(reason or ''))
        self.overrides[day] = override
        return override

    def remove_override(self, override_date: DateLike) -> bool:
        """
        Drop the ruling for one date, restoring the ordinary rules for it.

        RETURNS:
        --------
        bool
            True when there was one to drop, so a caller can tell a removal
            from a no-op without looking first.
        """
        return self.overrides.pop(as_date(override_date), None) is not None

    def override_for(self, check_date: DateLike) -> Optional['DateOverride']:
        """
        The ruling covering a date, or None when it is not overridden.

        What the overrides table and the chart's tooltip read to say *why* a
        given day is drawn the way it is - is_working_day answers only whether.
        """
        return self.overrides.get(as_date(check_date))

    def clear_overrides(self) -> None:
        """Drop every manual ruling."""
        self.overrides.clear()

    def sorted_overrides(self):
        """
        Every ruling in date order.

        The order the overrides table lists them in, and the order they are
        saved in - a stable one, so a file does not churn between saves that
        changed nothing.
        """
        return [self.overrides[day] for day in sorted(self.overrides)]

    # ---- what the calendar is ------------------------------------------

    @property
    def non_working_days(self) -> Set[int]:
        """
        Weekday indices that are never worked, as date.weekday() numbers them.

        A property so that assigning to it can drop the cached answer to
        works_any_weekday; see that property for why there is one.
        """
        return self._non_working_days

    @non_working_days.setter
    def non_working_days(self, days: Iterable[int]) -> None:
        """Take a new week, and forget what the old one worked out to."""
        self._non_working_days = set(days)
        self._works_any_weekday = None

    @property
    def works_any_weekday(self) -> bool:
        """
        Whether at least one weekday is worked.

        DEVELOPMENT NOTES:
        ------------------
        Cached, because is_working_day asks this before anything else and a
        single chart redraw calls that over two hundred thousand times on a
        large plan. It used to build `set(range(7))` and subtract from it on
        every one of them, which came to some 40ms of a redraw spent
        constructing the same seven-element set.

        Assigning a new week clears the cache through the setter above. The
        length is checked as well, which catches the other way the week
        could move - add, discard, remove or clear on the set itself. That
        costs about a third of what the cache saves and is worth it: nothing
        in the application mutates the set in place today, and a cache that
        silently answers for last week's calendar is a bad way to find out
        that something started.
        """
        if (self._works_any_weekday is None
                or self._cached_week_size != len(self._non_working_days)):
            self._cached_week_size = len(self._non_working_days)
            self._works_any_weekday = bool(
                _ALL_WEEKDAYS - self._non_working_days)
        return self._works_any_weekday

    def is_working_day(self, check_date: DateLike) -> bool:
        """
        Whether work happens on the given date.

        RETURNS:
        --------
        bool
            Whatever a manual override for the date says, if there is one.
            Otherwise False for a non-working weekday, a listed holiday, a
            recurring holiday, or a public holiday in any country the calendar
            observes; True otherwise.

        DEVELOPMENT NOTES:
        ------------------
        The override is read before anything else, including the empty-week
        guard below. A calendar that works no weekday is a broken calendar and
        is treated as working every day rather than hanging every loop here -
        but a date the user has explicitly named as not worked is not part of
        that breakage, and honouring it costs nothing.
        """
        override = self.overrides.get(as_date(check_date))
        if override is not None:
            return override.is_working_day

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
        if day in self._country_holidays(day.year):
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
        """
        Convert the calendar to a JSON-safe dictionary.

        The countries are saved, not the dates they resolve to. A plan reopened
        in a later year needs that year's holidays, and a list of dates worked
        out today would run out; the codes go on answering for any year.

        The overrides are saved as the dates they are, which is the opposite
        and right for the same reason: an override is a statement about one
        particular day, and there is no rule behind it to re-resolve.
        """
        return {
            'non_working_days': sorted(self.non_working_days),
            'holidays': sorted(day.isoformat() for day in self.holidays),
            'recurring_holidays': sorted(
                [month, day] for month, day in self.recurring_holidays
            ),
            'countries': sorted(self.countries),
            'overrides': [override.to_dict()
                          for override in self.sorted_overrides()],
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

        countries = []
        for entry in data.get('countries') or ():
            code = str(entry).strip().upper()
            if code:
                countries.append(code)

        overrides = []
        for entry in data.get('overrides') or ():
            override = DateOverride.from_dict(entry)
            if override is not None:
                overrides.append(override)

        return cls(non_working_days=non_working, holidays=holidays,
                   recurring_holidays=recurring, countries=countries,
                   overrides=overrides)

    def __eq__(self, other: object) -> bool:
        """Two calendars are the same when they name the same days."""
        if not isinstance(other, WorkingCalendar):
            return NotImplemented
        return (self.non_working_days == other.non_working_days
                and self.holidays == other.holidays
                and self.recurring_holidays == other.recurring_holidays
                and self.countries == other.countries
                and self.overrides == other.overrides)

    def __repr__(self) -> str:
        return (f"WorkingCalendar(non_working_days={sorted(self.non_working_days)}, "
                f"holidays={len(self.holidays)}, "
                f"recurring_holidays={len(self.recurring_holidays)}, "
                f"countries={sorted(self.countries)}, "
                f"overrides={len(self.overrides)})")


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
