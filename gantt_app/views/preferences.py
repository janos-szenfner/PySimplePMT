"""
The application's own settings: what is kept between runs, not per file.

WHY THIS MODULE EXISTS:
======================
Two kinds of settings used to live only inside a project file - the named
calendars and the baseline slots' names and colours - which meant they were
rebuilt for every project and lost the moment the program closed without a
save (issues #92, #93). They are preferences rather than plan data, so they
now live in the application's own settings.json beside the theme mode and
the style presets, and are merged back over whatever a file carries.

The file is shared: theme.save_mode and presets both read-modify-write it.
So do these functions - read the whole object, change one key, write it
back - so no one key's save erases the others.

DEVELOPMENT NOTES:
------------------
Everything here shrugs off a missing or damaged file: a preference is not
worth failing to start over, and the defaults - the calendar presets, the
factory baseline names - are what a missing answer always meant.
"""
import json
from typing import Dict, Optional

from gantt_app.core.baselines import BaselineManager, MAX_BASELINES
from gantt_app.core.calendarregistry import (
    CalendarRegistry, default_registry,
)
from gantt_app.utils.log import get_logger
from gantt_app.views import theme

logger = get_logger(__name__)

#: The settings.json keys this module owns.
CALENDARS_KEY = 'calendars'
BASELINE_SLOTS_KEY = 'baseline_slots'


def _read_settings() -> Dict:
    """The whole settings object, or an empty one when it cannot be read."""
    path = theme.settings_directory() / theme.SETTINGS_FILE
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            loaded = json.load(handle)
            return loaded if isinstance(loaded, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_key(key: str, value) -> bool:
    """Set one key in settings.json, leaving every other key alone."""
    path = theme.settings_directory() / theme.SETTINGS_FILE
    existing = _read_settings()
    existing[key] = value
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as handle:
            json.dump(existing, handle, indent=2)
        return True
    except OSError:
        logger.warning("Could not save %s to %s", key, path)
        return False


# ---------------------------------------------------------------------------
# The named-calendar library
# ---------------------------------------------------------------------------

def load_calendar_library() -> CalendarRegistry:
    """
    The calendars every plan is offered: the saved library, or the presets.

    A settings file with no calendars key means this run predates the
    library, which is exactly what the presets were written for - it is
    seeded from them, so somebody's Standard Week is never empty.
    """
    data = _read_settings()
    if CALENDARS_KEY not in data:
        # No key means this run predates the library, which is exactly what
        # the presets were written for - it is seeded from them, so
        # somebody's Standard Week is never empty. A key holding an empty
        # list is honoured instead: deleting every calendar is a choice.
        return default_registry()
    try:
        return CalendarRegistry.from_dict(data[CALENDARS_KEY])
    except (TypeError, ValueError, KeyError, AttributeError):
        logger.warning("Ignoring the malformed calendars in settings.json")
        return default_registry()


def save_calendar_library(registry: CalendarRegistry) -> bool:
    """Remember the named calendars for every project, past and next."""
    return _write_key(CALENDARS_KEY, registry.to_dict())


# ---------------------------------------------------------------------------
# The baseline slots' names and colours
# ---------------------------------------------------------------------------

def load_baseline_slot_preferences() -> Dict[int, Dict[str, str]]:
    """
    The slot labels and colours kept between runs, keyed by slot number.

    Shape in the file: {"baseline_slots": {"1": {"name": ..., "color": ...}}}.
    Numbers that do not read as slot numbers are dropped rather than carried.
    """
    raw = _read_settings().get(BASELINE_SLOTS_KEY)
    if not isinstance(raw, dict):
        return {}

    prefs: Dict[int, Dict[str, str]] = {}
    for key, entry in raw.items():
        try:
            number = int(key)
        except (TypeError, ValueError):
            continue
        if not (1 <= number <= MAX_BASELINES) or not isinstance(entry, dict):
            continue
        prefs[number] = {
            "name": str(entry.get("name") or ""),
            "color": str(entry.get("color") or ""),
        }
    return prefs


def save_baseline_slot_preferences(prefs: Dict[int, Dict[str, str]]) -> bool:
    """Remember the slot names and colours for every project, past and next."""
    return _write_key(
        BASELINE_SLOTS_KEY,
        {str(number): {"name": str(entry.get("name") or ""),
                       "color": str(entry.get("color") or "")}
         for number, entry in prefs.items()})


def apply_baseline_slot_preferences(
        manager: Optional[BaselineManager],
        prefs: Optional[Dict[int, Dict[str, str]]] = None) -> bool:
    """
    Overlay the stored names and colours onto a manager's slots.

    The file a project loads still carries its own labels - this overlay is
    what makes the centrally-kept choice win over them, so a slot's name and
    colour read the same whichever plan is open (issue #92). Slots with no
    stored preference keep what the file gave them.

    RETURNS:
    --------
    bool
        True when anything was applied.
    """
    if manager is None:
        return False
    if prefs is None:
        prefs = load_baseline_slot_preferences()

    applied = False
    for number, entry in prefs.items():
        slot = manager.get_slot(number)
        if slot is None:
            continue
        if entry.get("name"):
            slot.display_name = entry["name"]
            applied = True
        if entry.get("color"):
            slot.color = entry["color"]
            applied = True
    return applied
