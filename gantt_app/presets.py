"""
The style presets a plan can be marked up with, built-in and custom.

WHY THIS MODULE EXISTS:
======================
Four presets ship with the application - Financial Milestone, Work Complete,
Phase Gate / Approval, Summary Phase - and they are the four things a plan is
most often marked up for. They are read-only: a plan opened on another machine
has to mean the same thing by "Phase Gate", so the built-ins cannot be edited
or deleted, only used. See REQ-UI-020.

A reader also wants their own. A custom preset is defined once in Settings and
is then offered in the toolbar's preset menu beside the built-in four, without
restarting - so this holds both kinds in one place, persists the custom ones,
and tells whoever is showing them when the set has changed.

WHY A SINGLE MANAGER:
====================
The menu that shows presets and the Settings tab that edits them are far apart
in the widget tree, and both have to see the same set the moment it changes.
Rather than thread one object down to each, the manager is a module singleton
- default_manager() - the way the theme is, which is the other piece of state
every corner of the application shares. A test builds its own with an explicit
settings file instead.

DEVELOPMENT NOTES:
------------------
A preset carries the TaskStyle it applies, not a second description of what it
looks like. The toolbar's chip and the Settings preview are both drawn from
that one style, so neither can promise a look the click does not deliver - the
same rule the preview menu already followed for the built-ins.
"""

import json
import re
from pathlib import Path
from dataclasses import dataclass, field, replace
from typing import Callable, Dict, List, Optional

from gantt_app import theme
from gantt_app.taskstyle import PRESETS, TaskStyle, preset_badge
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


#: A stable id for each built-in, so a saved plan and the menu name the same
#: preset however the display name is later worded. Custom ids are minted at
#: add time; see PresetManager.add_custom.
BUILTIN_IDS: Dict[str, str] = {
    'Financial Milestone': 'financial',
    'Work Complete': 'complete',
    'Phase Gate / Approval': 'gate',
    'Summary Phase': 'summary',
}

#: The badge a custom preset gets when it names none of its own.
DEFAULT_CUSTOM_BADGE = ('★', '#8e44ad')


@dataclass(frozen=True)
class StylePreset:
    """
    One preset: what it is called, what it applies, and how it is badged.

    ATTRIBUTES:
    -----------
    id : str
        Stable across renames; how a preset is referred to.
    name : str
        What the menu and the Settings grid show.
    style : TaskStyle
        The formatting a click applies, and what the preview is drawn from.
    badge : str
        A glyph to recognise the preset by.
    badge_color : str
        The badge's colour, as '#rrggbb'.
    is_builtin : bool
        True for the four that ship; those cannot be edited or deleted.
    """

    id: str
    name: str
    style: TaskStyle
    badge: str
    badge_color: str
    is_builtin: bool = False

    def to_dict(self) -> Dict:
        """A custom preset as JSON. Built-ins are never written."""
        return {
            'id': self.id,
            'name': self.name,
            'badge': self.badge,
            'badge_color': self.badge_color,
            'style': self.style.to_dict() or {},
        }

    @classmethod
    def from_dict(cls, data: Dict) -> Optional['StylePreset']:
        """
        A custom preset read back from JSON, or None when it will not read.

        A damaged entry is dropped rather than raising: one bad custom preset
        must not stop the others loading, nor the application starting.
        """
        try:
            return cls(
                id=str(data['id']),
                name=str(data.get('name', '')),
                style=TaskStyle.from_any(data.get('style')),
                badge=str(data.get('badge') or DEFAULT_CUSTOM_BADGE[0]),
                badge_color=str(data.get('badge_color')
                                or DEFAULT_CUSTOM_BADGE[1]),
                is_builtin=False,
            )
        except (KeyError, TypeError, ValueError):
            logger.warning("Dropping an unreadable custom preset: %r", data)
            return None


def _builtin_presets() -> List[StylePreset]:
    """The four that ship, from taskstyle and its badges."""
    presets = []
    for name, style in PRESETS:
        glyph, colour = preset_badge(name)
        presets.append(StylePreset(
            id=BUILTIN_IDS.get(name, _slug(name)),
            name=name, style=style, badge=glyph, badge_color=colour,
            is_builtin=True,
        ))
    return presets


def _slug(text: str) -> str:
    """A lower-case id from a name, for anything not in BUILTIN_IDS."""
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-') or 'preset'


class PresetManager:
    """
    The built-in and custom presets, and who to tell when they change.

    PARAMETERS:
    -----------
    settings_path : Optional[str]
        Where the custom presets are read and written. Defaults to the
        application's own settings.json; a test passes its own.

    DEVELOPMENT NOTES:
    ------------------
    The built-ins are rebuilt on every read rather than stored, so there is
    no copy of them that a caller could reach in and change - the read-only
    guarantee is that they simply are not mutable state. Only the customs are
    held and persisted.
    """

    #: The key the custom presets live under in settings.json, beside
    #: theme_mode - read-modified-written so the two do not clobber each other.
    SETTINGS_KEY = 'custom_presets'

    def __init__(self, settings_path: Optional[str] = None):
        self._settings_path = settings_path
        self._custom: List[StylePreset] = []
        self._listeners: List[Callable[[], None]] = []
        self._load()

    # -- reading ---------------------------------------------------------

    def builtin(self) -> List[StylePreset]:
        """The four read-only presets that ship."""
        return _builtin_presets()

    def custom(self) -> List[StylePreset]:
        """The presets the reader has added, in the order they were added."""
        return list(self._custom)

    def all(self) -> List[StylePreset]:
        """Every preset, built-ins first, then customs."""
        return self.builtin() + self.custom()

    def get(self, preset_id: str) -> Optional[StylePreset]:
        """One preset by id, of either kind, or None."""
        return next((p for p in self.all() if p.id == preset_id), None)

    # -- writing ---------------------------------------------------------

    def add_custom(self, name: str, style: TaskStyle,
                   badge: str = DEFAULT_CUSTOM_BADGE[0],
                   badge_color: str = DEFAULT_CUSTOM_BADGE[1]) -> StylePreset:
        """
        Add a custom preset, save it, and tell the listeners.

        RETURNS:
        --------
        StylePreset
            The preset as stored, carrying the id it was given.
        """
        preset = StylePreset(
            id=self._fresh_id(), name=name, style=style,
            badge=badge, badge_color=badge_color, is_builtin=False,
        )
        self._custom.append(preset)
        logger.info("Added custom preset %r (%s)", name, preset.id)
        self._save()
        self._notify()
        return preset

    def update_custom(self, preset_id: str, **changes) -> bool:
        """
        Change a custom preset's fields; refuse a built-in.

        PARAMETERS:
        -----------
        preset_id : str
            Which preset to change.
        **changes
            name, style, badge and/or badge_color.

        RETURNS:
        --------
        bool
            True when a custom preset was changed. A built-in, or an unknown
            id, changes nothing and answers False - the read-only guardrail.
        """
        for index, preset in enumerate(self._custom):
            if preset.id == preset_id:
                allowed = {k: v for k, v in changes.items()
                           if k in ('name', 'style', 'badge', 'badge_color')}
                self._custom[index] = replace(preset, **allowed)
                logger.info("Updated custom preset %s", preset_id)
                self._save()
                self._notify()
                return True
        logger.debug("Refused to update preset %s: not a custom one",
                     preset_id)
        return False

    def delete_custom(self, preset_id: str) -> bool:
        """
        Remove a custom preset; refuse a built-in.

        RETURNS:
        --------
        bool
            True when a custom preset was removed. A built-in id, or an
            unknown one, removes nothing and answers False.
        """
        remaining = [p for p in self._custom if p.id != preset_id]
        if len(remaining) == len(self._custom):
            logger.debug("Refused to delete preset %s: not a custom one",
                         preset_id)
            return False
        self._custom = remaining
        logger.info("Deleted custom preset %s", preset_id)
        self._save()
        self._notify()
        return True

    def is_builtin(self, preset_id: str) -> bool:
        """Whether an id names one of the read-only presets."""
        return preset_id in {p.id for p in self.builtin()}

    # -- the broadcast ---------------------------------------------------

    def subscribe(self, listener: Callable[[], None]) -> None:
        """
        Be told, with no argument, whenever the custom set changes.

        The listener reads all() again itself; the call is only the nudge.
        Registered once - a listener added twice is still called once - so a
        widget rebuilt on a theme change does not stack up callbacks.
        """
        if listener not in self._listeners:
            self._listeners.append(listener)

    def unsubscribe(self, listener: Callable[[], None]) -> None:
        """Stop telling this listener; harmless if it was never subscribed."""
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _notify(self) -> None:
        """
        Tell every listener the set has changed.

        One that raises is logged and the rest are still told: a menu that
        failed to refresh must not stop the Settings grid being told too.
        """
        for listener in list(self._listeners):
            try:
                listener()
            except Exception:
                logger.exception("A preset listener failed")

    # -- persistence -----------------------------------------------------

    def _path(self):
        """The settings file, defaulting to the application's own."""
        if self._settings_path is not None:
            return Path(self._settings_path)
        return theme.settings_directory() / theme.SETTINGS_FILE

    def _load(self) -> None:
        """
        Read the custom presets, dropping any that will not read.

        Anything wrong - no file, bad JSON, a list that is not one - leaves
        no custom presets rather than raising. The built-ins are always
        there, so the menu still works.
        """
        try:
            with open(self._path(), 'r', encoding='utf-8') as handle:
                loaded = json.load(handle)
        except (OSError, ValueError):
            self._custom = []
            return

        raw = (loaded.get(self.SETTINGS_KEY)
               if isinstance(loaded, dict) else None)
        if not isinstance(raw, list):
            self._custom = []
            return

        presets = [StylePreset.from_dict(entry) for entry in raw
                   if isinstance(entry, dict)]
        self._custom = [p for p in presets if p is not None]

    def _save(self) -> bool:
        """
        Write the custom presets back, keeping the rest of settings.json.

        Read-modify-write, so theme_mode and anything else in the file
        survives. A read-only or missing directory is logged and shrugged
        off: the presets still work for this run.
        """
        path = self._path()

        existing: Dict = {}
        try:
            with open(path, 'r', encoding='utf-8') as handle:
                loaded = json.load(handle)
                if isinstance(loaded, dict):
                    existing = loaded
        except (OSError, ValueError):
            pass

        existing[self.SETTINGS_KEY] = [p.to_dict() for p in self._custom]

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as handle:
                json.dump(existing, handle, indent=2)
            return True
        except OSError:
            logger.warning("Could not save custom presets to %s", path)
            return False

    def _fresh_id(self) -> str:
        """
        A custom id nothing else uses.

        Numbered rather than slugged from the name, because two customs may
        share a name and an id may not - and a name can be changed later
        while the id has to stay put.
        """
        used = {p.id for p in self.all()}
        index = len(self._custom) + 1
        while f"custom_{index}" in used:
            index += 1
        return f"custom_{index}"


#: The one manager the application shares; see the module note.
_DEFAULT: Optional[PresetManager] = None


def default_manager() -> PresetManager:
    """The application-wide manager, built on first use."""
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = PresetManager()
    return _DEFAULT
