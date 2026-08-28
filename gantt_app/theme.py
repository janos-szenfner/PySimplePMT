"""
Light or dark, who decides it, and the colours that follow.

WHY THIS MODULE EXISTS:
======================
The application read the desktop's light/dark setting once at startup and then
never looked again. A machine that switched to dark at sunset left the window
in whatever it had been at launch, and there was no way to say "I want dark
anyway" - only a Toggle Theme entry that flipped the current mode and was
forgotten the next time the application opened.

Two things were missing and this is both of them:

  * **Following the system, continuously.** The desktop's setting is watched
    while the application is in system mode, so the window follows it.
  * **Overriding it, deliberately and durably.** A choice of light or dark is
    remembered between runs, and stops the system being followed until the
    user asks for it back.

The colours live here too, and that is the other half of the problem. A colour
written as a single string - `text_color="#1a1a1a"` - is used in *both*
appearances by CustomTkinter, so a form full of them read perfectly in light
and turned into near-black labels on a near-black panel in dark. Every colour
here is a (light, dark) pair, which is the only shape that cannot have that
bug, and the light half of every pair is exactly what the application used
before so nothing about the light appearance moves.

DEVELOPMENT NOTES:
------------------
The system setting is polled rather than subscribed to, because there is no
portable way to subscribe: darkdetect offers a listener thread on macOS only.
The poll is deliberately slow - see POLL_SECONDS. CustomTkinter's own
`set_appearance_mode("system")` does the same job at thirty times a second and
is why this application stopped using it: on Linux each read runs `gsettings`
through subprocess, so it spawned tens of processes a second to watch a
setting that changes about twice a day. Once every few seconds is
indistinguishable to a person and free to the machine.

Polling only runs while the mode is `system`. An explicit light or dark choice
stops it, because there is then nothing for it to discover.

This sits at the top of the package, beside models.py and workdaycalendar.py,
because both the views and main.py need it and nothing here needs either.
"""

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
import json
import logging
import os
import sys

logger = logging.getLogger(__name__)

#: The three things the mode can be. `system` follows the desktop; the other
#: two are the user overriding it.
MODE_SYSTEM = 'system'
MODE_LIGHT = 'light'
MODE_DARK = 'dark'

#: Every valid mode, for reading a saved preference back safely.
MODES: Tuple[str, ...] = (MODE_SYSTEM, MODE_LIGHT, MODE_DARK)

#: The two appearances a mode resolves to.
LIGHT = 'light'
DARK = 'dark'


# ---------------------------------------------------------------------------
# The palette
# ---------------------------------------------------------------------------
#
# Every entry is (light, dark), which is the pair CustomTkinter takes. The
# light half of each is the colour the application already used, so the light
# appearance is unchanged to the pixel; the dark half is chosen to hold the
# same *contrast* against its own background rather than to be the same hue.

#: Ordinary body text on a panel.
TEXT: Tuple[str, str] = ('#1a1a1a', '#e8eaed')

#: Secondary text - captions, counts, the grey note under a control.
MUTED_TEXT: Tuple[str, str] = ('#6b7280', '#9aa3ad')

#: A warning that is not an error: a missing optional package, a value that
#: was replaced. Amber both ways, lightened for dark so it is not mud.
WARNING_TEXT: Tuple[str, str] = ('#b45309', '#f0b429')

#: A field the user may type in, and the text in it.
FIELD_BG: Tuple[str, str] = ('#ffffff', '#2b2d31')
FIELD_TEXT: Tuple[str, str] = ('#1a1a1a', '#e8eaed')

#: A field being filled in for the user, and its text. Shaded rather than
#: merely paler, in both appearances, so "not yours to fill in" reads at a
#: glance - see TaskFormDialog._paint_field.
FIELD_BG_DISABLED: Tuple[str, str] = ('#ebecee', '#232529')
FIELD_TEXT_DISABLED: Tuple[str, str] = ('#8a8f96', '#7d838b')

#: A hairline between things: menu separators, toolbar dividers.
SEPARATOR: Tuple[str, str] = ('#6C757D', '#4a4d52')

#: A row in a list, and the same row when it is the alternate stripe.
ROW_BG: Tuple[str, str] = ('#F8F9FA', '#2b2d31')

#: Something that succeeded, or a day that is worked.
POSITIVE_TEXT: Tuple[str, str] = ('#15803d', '#4ade80')

#: Something that failed, or a day that is not worked.
NEGATIVE_TEXT: Tuple[str, str] = ('#b91c1c', '#f87171')

#: The menu bar and icon row across the top.
MENU_BG: Tuple[str, str] = ('#F1F3F5', '#232529')
MENU_HOVER: Tuple[str, str] = ('#E9ECEF', '#34373d')
MENU_TEXT: Tuple[str, str] = ('#1C1D1F', '#e8eaed')

#: The panel a dropdown menu is drawn on.
DROPDOWN_BG: Tuple[str, str] = ('#F8F9FA', '#2b2d31')

#: The hairline between groups of icons.
ICON_SEPARATOR: Tuple[str, str] = ('#C8CDD2', '#43464c')

# ---- the grids -------------------------------------------------------------
#
# The task list, the critical path table and the dependency table are ttk
# Treeviews. ttk knows nothing about appearance modes and takes one colour per
# thing, so each of these is resolved to a single colour when the grid is
# styled and re-resolved when the theme changes; see style_treeview.

#: A row, and every other row, giving the banded look.
GRID_ROW_BG: Tuple[str, str] = ('#ffffff', '#26282c')
GRID_ROW_ALT: Tuple[str, str] = ('#f4f4f4', '#2b2d31')

#: The column headings above them.
GRID_HEADING_BG: Tuple[str, str] = ('#e4e4e4', '#34373d')

#: Text in a row, and the hairline between cells.
GRID_TEXT: Tuple[str, str] = ('#1a1a1a', '#e8eaed')
GRID_LINE: Tuple[str, str] = ('#d0d0d0', '#3a3d42')

#: A selected row.
GRID_SELECT_BG: Tuple[str, str] = ('#cfe2f3', '#2f5d86')

#: A row that has been cut and is waiting to be pasted.
GRID_CUT_TEXT: Tuple[str, str] = ('#9aa0a6', '#71767c')

#: The window's own furniture: the scrollbars and the divider between the
#: two panes.
#:
#: These are ttk widgets with no colour of their own, so they took whatever
#: the 'clam' theme ships - a light grey - in both appearances. On a dark
#: window that left a pale scrollbar down each pane and a pale bar between
#: them, which is the one part of the window a theme change never reached.
SCROLL_TROUGH: Tuple[str, str] = ('#f0f0f0', '#2b2d31')
SCROLL_THUMB: Tuple[str, str] = ('#c8c8c8', '#4a4e54')
SCROLL_THUMB_ACTIVE: Tuple[str, str] = ('#a8a8a8', '#5a5f66')

#: The draggable divider between the task list and the chart.
SASH_BG: Tuple[str, str] = ('#d0d0d0', '#3a3d42')
SASH_LIGHT: Tuple[str, str] = ('#e8e8e8', '#4a4e54')
SASH_DARK: Tuple[str, str] = ('#b0b0b0', '#2a2c30')

#: Rows the critical path analysis calls out: no float, and nearly none.
GRID_CRITICAL_BG: Tuple[str, str] = ('#fde2e1', '#5a2b2a')
GRID_TIGHT_BG: Tuple[str, str] = ('#fdf4d8', '#544a24')

# ---- the chart -------------------------------------------------------------
#
# The on-screen chart only. What is *exported* stays light whatever the window
# is set to: a PNG or a PDF is shared and printed, and a dark chart on paper
# is a page of ink. See GanttChartView.screen_settings.

#: The paper the chart is drawn on, the axis labels, and the gridlines.
CHART_BG: Tuple[str, str] = ('#ffffff', '#232529')
CHART_TEXT: Tuple[str, str] = ('#000000', '#e8eaed')
CHART_GRID: Tuple[str, str] = ('#ecf0f1', '#3a3d42')

# ---- the date header -------------------------------------------------------
#
# The calendar strip across the top: a month band, and a cell per day under
# it. Screen and export alike - unlike the three above, these are not
# swapped for the appearance by screen_settings, because the header is drawn
# from the same settings dict and the export keeps the light half anyway.

#: The month band, and the day cells beneath it.
HEADER_MONTH_BG: Tuple[str, str] = ('#f7f8f9', '#2b2d31')
HEADER_CELL_BG: Tuple[str, str] = ('#ffffff', '#26282c')

#: The hairlines: between one day cell and the next, and the heavier one at
#: the start of a week, which is what gives the strip its rhythm now that
#: the weekday letters are gone.
HEADER_RULE: Tuple[str, str] = ('#e3e6e8', '#3a3d42')
HEADER_WEEK_RULE: Tuple[str, str] = ('#c8ccd0', '#4a4d52')

#: The month name, and the day numbers under it.
HEADER_MONTH_TEXT: Tuple[str, str] = ('#5b6167', '#9aa3ad')
HEADER_DAY_TEXT: Tuple[str, str] = ('#1a1a1a', '#e8eaed')

#: A day nobody works, shaded down the whole chart. This is what carries
#: "not a working day" now that there is no weekday letter to read it from.
HEADER_NON_WORKING: Tuple[str, str] = ('#f2f4f6', '#1b1d21')

#: Today: its cell in the strip, and the tint down the chart behind it.
HEADER_TODAY_BG: Tuple[str, str] = ('#dbeafe', '#1e3a5f')
HEADER_TODAY_TEXT: Tuple[str, str] = ('#1e40af', '#bfdbfe')

# ---- the dashboard ---------------------------------------------------------
#
# The dashboard is drawn on a Tk canvas in plain Python. A canvas takes one
# colour per thing and knows nothing about appearance modes, so every one of
# these is resolved when it is drawn and resolved again on a theme change;
# see ProjectDashboardFrame.apply_theme.

#: The panel behind a chart, and the board the four of them sit on.
DASH_PLOT_BG: Tuple[str, str] = ('#ffffff', '#232529')
DASH_BOARD_BG: Tuple[str, str] = ('#f7f8fa', '#1b1d21')

#: A panel title, a tick label, and the axis box and gridlines.
DASH_TITLE_TEXT: Tuple[str, str] = ('#1a1a1a', '#e8eaed')
DASH_TICK_TEXT: Tuple[str, str] = ('#5f6368', '#9aa0a6')
DASH_AXIS: Tuple[str, str] = ('#c8cdd2', '#43464c')
DASH_GRID: Tuple[str, str] = ('#ecf0f1', '#33363b')

#: The bars: progress across the top, duration along the bottom.
DASH_PROGRESS_BAR: Tuple[str, str] = ('#2b8fd4', '#38bdf8')
DASH_DURATION_BAR: Tuple[str, str] = ('#5b62d6', '#818cf8')

#: The donut, one colour per task type, in the order the types are declared.
DASH_SERIES_1: Tuple[str, str] = ('#4f46e5', '#6366f1')
DASH_SERIES_2: Tuple[str, str] = ('#059669', '#10b981')
DASH_SERIES_3: Tuple[str, str] = ('#d97706', '#f59e0b')
DASH_SERIES_4: Tuple[str, str] = ('#dc2626', '#ef4444')

#: The summary box in the fourth quarter.
DASH_KPI_BG: Tuple[str, str] = ('#eef1f5', '#2d3748')
DASH_KPI_BORDER: Tuple[str, str] = ('#c8cdd2', '#4a5568')


#: What a toolbar icon is drawn in, as RGB rather than hex - Pillow draws
#: the strokes and knows nothing about appearance modes, so each appearance
#: gets its own drawing and CTkImage picks between them. Near-black on the
#: light bar; near-white on the dark one, where the light drawing was
#: invisible.
ICON_INK_LIGHT: Tuple[int, int, int] = (28, 29, 31)
ICON_INK_DARK: Tuple[int, int, int] = (232, 234, 237)


def pair(colour: Tuple[str, str]) -> Tuple[str, str]:
    """
    A palette entry, as the tuple CustomTkinter wants.

    Exists so a caller reads `pair(TEXT)` rather than indexing the constant,
    and so a single-string colour slipping into the palette is caught here
    rather than by somebody's eyes in dark mode.
    """
    if isinstance(colour, str):
        raise TypeError(
            f"{colour!r} is one colour, not a (light, dark) pair; a single "
            f"string is used in both appearances and will be unreadable in "
            f"one of them"
        )
    light, dark = colour
    return (light, dark)


def current_appearance() -> str:
    """
    The appearance CustomTkinter is currently in: LIGHT or DARK.

    Imported locally so this module stays importable with no display and no
    CustomTkinter - the palette and the controller are both wanted by tests
    that build no widgets.
    """
    try:
        import customtkinter
        mode = str(customtkinter.get_appearance_mode()).lower()
    except Exception:
        return LIGHT
    return DARK if mode == 'dark' else LIGHT


def now(colour: Tuple[str, str]) -> str:
    """
    The half of a pair the window is currently showing.

    For the plain Tk and ttk widgets - a Treeview, a Canvas, a tk.Text -
    which take one colour and have to be told again when the theme changes.
    """
    if isinstance(colour, str):
        return colour
    return resolve(colour, current_appearance())


def style_chrome() -> None:
    """
    Colour the scrollbars and the pane divider for the appearance in force.

    DEVELOPMENT NOTES:
    ------------------
    Neither follows a theme on its own. A ttk.Scrollbar with no style takes
    whatever the active ttk theme ships, and the sash was configured once at
    startup with a light grey written into the source - so both stayed pale
    on a dark window, in every mode, including after a restart.

    Called at startup and again on every theme change; see
    GanttApp._theme_changed.

    Every scrollbar in the application is styled, not a named one: they are
    plain ttk.Scrollbars built in three different modules, and a named style
    would mean remembering to ask for it in each. The base name and both
    orientations are configured because ttk resolves an unstyled vertical
    scrollbar as 'Vertical.TScrollbar', which inherits from 'TScrollbar' but
    can be overridden by a theme that sets it directly.
    """
    from tkinter import ttk

    style = ttk.Style()
    trough = now(SCROLL_TROUGH)
    thumb = now(SCROLL_THUMB)
    active = now(SCROLL_THUMB_ACTIVE)

    for name in ('TScrollbar', 'Vertical.TScrollbar',
                 'Horizontal.TScrollbar'):
        try:
            style.configure(name, background=thumb, troughcolor=trough,
                            bordercolor=trough, arrowcolor=active,
                            lightcolor=thumb, darkcolor=thumb)
            style.map(name, background=[('active', active)])
        except Exception:
            logger.debug("Could not colour %s on this platform", name)

    sash = now(SASH_BG)
    try:
        style.configure('Gantt.TPanedwindow', background=sash)
        style.configure('Gantt.Sash', sashthickness=7, gripcount=0,
                        background=sash, bordercolor=now(SASH_DARK),
                        lightcolor=now(SASH_LIGHT), darkcolor=now(SASH_DARK))
    except Exception:
        logger.debug("Could not colour the pane divider on this platform")


def style_treeview(style_name: str, row_height: Optional[int] = None,
                   font=None, heading_font=None) -> None:
    """
    Colour a ttk Treeview style for the appearance in force.

    PARAMETERS:
    -----------
    style_name : str
        The style the grid uses - 'Gantt.Treeview' and so on. Its heading
        style is derived from it, as ttk names them.
    row_height, font, heading_font :
        Passed through when given, so a caller that also sets these does not
        have to configure the style twice.

    DEVELOPMENT NOTES:
    ------------------
    Here rather than in each of the three grids that need it. ttk styles are
    global and the colours are the same everywhere, so three copies of this
    would be three chances for one of them to be missed the next time the
    palette moves - which is exactly how the whole application came to be
    half light and half dark.

    ttk takes one colour per thing and has no notion of appearance modes, so
    every one of these is resolved now and has to be resolved again when the
    theme changes. That is what the apply_theme methods on the grids do.
    """
    from tkinter import ttk

    style = ttk.Style()

    options = {
        'background': now(GRID_ROW_BG),
        'fieldbackground': now(GRID_ROW_BG),
        'foreground': now(GRID_TEXT),
    }
    if row_height is not None:
        options['rowheight'] = row_height
    if font is not None:
        options['font'] = font
    style.configure(style_name, **options)

    heading_options = {
        'background': now(GRID_HEADING_BG),
        'foreground': now(GRID_TEXT),
    }
    if heading_font is not None:
        heading_options['font'] = heading_font
    style.configure(f'{style_name}.Heading', **heading_options)

    style.map(style_name,
              background=[('selected', now(GRID_SELECT_BG))],
              foreground=[('selected', now(GRID_TEXT))])
    style.map(f'{style_name}.Heading',
              background=[('active', now(GRID_LINE))])


def resolve(colour: Tuple[str, str], appearance: str) -> str:
    """
    The half of a pair that a given appearance uses.

    For the places that need an actual colour rather than a pair - drawing an
    icon with PIL, say, which knows nothing about appearance modes.
    """
    light, dark = colour
    return dark if appearance == DARK else light


# ---------------------------------------------------------------------------
# What the desktop says
# ---------------------------------------------------------------------------

def detect_system_appearance() -> str:
    """
    Whether the desktop is set to light or dark, right now.

    RETURNS:
    --------
    str
        LIGHT or DARK. LIGHT when there is no detector installed or it
        refuses to answer - a light window on a dark desktop is a cosmetic
        mismatch, and guessing dark on a light desktop is an unreadable one.
    """
    try:
        import darkdetect
        if str(darkdetect.theme() or '').lower() == 'dark':
            return DARK
    except Exception:
        logger.debug("Could not detect the system theme; assuming light")
    return LIGHT


# ---------------------------------------------------------------------------
# Where the preference is kept
# ---------------------------------------------------------------------------

def settings_directory() -> Path:
    """
    A per-user, per-platform place for the preference.

    %LOCALAPPDATA% on Windows, ~/Library/Application Support on macOS, and
    $XDG_CONFIG_HOME (or ~/.config) elsewhere - the same shape as the log
    directory, which is why it is spelt the same way.
    """
    if sys.platform.startswith('win'):
        base = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
        return Path(base) / 'PySimplePMT'

    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / 'PySimplePMT'

    config_home = os.environ.get('XDG_CONFIG_HOME')
    base = Path(config_home) if config_home else Path.home() / '.config'
    return base / 'PySimplePMT'


#: The file the preference lives in. One small JSON object rather than a
#: whole settings system, because there is exactly one preference so far.
SETTINGS_FILE = 'settings.json'


def load_mode() -> str:
    """
    The saved theme mode, or MODE_SYSTEM when there is not one.

    Anything unreadable - no file, bad JSON, a mode this version does not
    know - comes back as MODE_SYSTEM. A preference is not worth failing to
    start over, and following the desktop is the right default to fall to.
    """
    path = settings_directory() / SETTINGS_FILE
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            saved = json.load(handle).get('theme_mode')
    except (OSError, ValueError, AttributeError):
        return MODE_SYSTEM

    if saved in MODES:
        return saved

    if saved is not None:
        logger.debug("Ignoring unknown saved theme mode %r", saved)
    return MODE_SYSTEM


def save_mode(mode: str) -> bool:
    """
    Remember the theme mode for next time.

    RETURNS:
    --------
    bool
        Whether it was written. A read-only or missing settings directory is
        logged and shrugged off: the theme still works for this run, and
        refusing to change it because it could not be *saved* would be a
        strange thing to do to somebody who just pressed the button.
    """
    path = settings_directory() / SETTINGS_FILE

    existing: Dict = {}
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            loaded = json.load(handle)
            if isinstance(loaded, dict):
                existing = loaded
    except (OSError, ValueError):
        pass

    existing['theme_mode'] = mode

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as handle:
            json.dump(existing, handle, indent=2)
        return True
    except OSError:
        logger.warning("Could not save the theme preference to %s", path)
        return False


# ---------------------------------------------------------------------------
# The controller
# ---------------------------------------------------------------------------

class ThemeController:
    """
    Which appearance the application is in, and who decided it.

    PARAMETERS:
    -----------
    mode : Optional[str]
        The mode to start in. Read from the saved preference when not given.
    apply : Optional[Callable[[str], None]]
        Called with LIGHT or DARK whenever the appearance changes, and once
        when the controller starts. CustomTkinter's set_appearance_mode by
        default; taking it as an argument is what lets the tests drive the
        whole controller without a display.
    persist : bool
        Whether choosing a mode writes it to the user's settings file. False
        for a stand-in controller - see the note on the attribute.

    DEVELOPMENT NOTES:
    ------------------
    The mode and the appearance are two different things and keeping them
    apart is most of what this class is for. The *mode* is what the user
    asked for - follow the system, or be light, or be dark. The *appearance*
    is what that resolves to today. Only `system` mode can have the two
    disagree over time, and it is the only one that polls.
    """

    #: How often the desktop setting is re-read, in seconds, while the mode
    #: is `system`.
    #:
    #: Slow on purpose. The setting changes about twice a day; a person
    #: notices nothing at four seconds, and on Linux each read runs
    #: `gsettings` in a subprocess. CustomTkinter's own system mode does this
    #: thirty times a second, which is why this application does not use it.
    POLL_SECONDS = 4

    def __init__(self, mode: Optional[str] = None,
                 apply: Optional[Callable[[str], None]] = None,
                 persist: bool = True):
        self._mode = mode if mode in MODES else load_mode()
        self._apply = apply or self._apply_to_customtkinter
        #: Whether a mode change is written to the user's settings file.
        #:
        #: False for a controller nobody owns - the stand-in a toolbar builds
        #: when it is constructed without one, which is what the tests do.
        #: Such a controller writing to the settings file means running the
        #: suite changes the preference of whoever ran it, which it did.
        self._persist = persist
        self._appearance = self._resolve_appearance()
        #: (listener, owner reference) pairs; see subscribe.
        self._listeners: List[Tuple[Callable[[str, str], None], Any]] = []

        #: The widget the poll is scheduled on, and the pending `after` id,
        #: so watching can be stopped and never scheduled twice.
        self._widget = None
        self._poll_id = None

    # ---- what it currently is -------------------------------------------

    @property
    def mode(self) -> str:
        """What the user asked for: MODE_SYSTEM, MODE_LIGHT or MODE_DARK."""
        return self._mode

    @property
    def appearance(self) -> str:
        """What that resolves to now: LIGHT or DARK."""
        return self._appearance

    @property
    def following_system(self) -> bool:
        """Whether the desktop is deciding, rather than the user."""
        return self._mode == MODE_SYSTEM

    @property
    def is_dark(self) -> bool:
        """Whether the current appearance is the dark one."""
        return self._appearance == DARK

    def _resolve_appearance(self) -> str:
        """The appearance the current mode means."""
        if self._mode == MODE_LIGHT:
            return LIGHT
        if self._mode == MODE_DARK:
            return DARK
        return detect_system_appearance()

    @staticmethod
    def _apply_to_customtkinter(appearance: str) -> None:
        """
        Hand the appearance to CustomTkinter.

        An explicit 'light' or 'dark', never 'system': see the note on the
        module about the tracker that mode starts.
        """
        import customtkinter as ctk
        ctk.set_appearance_mode(appearance)

    # ---- the labels the UI shows ----------------------------------------

    def button_text(self) -> str:
        """
        What the toggle button says: the appearance it is *in*.

        Day while light and Night while dark, rather than naming what a press
        would do. A button captioned with its own effect and a button
        captioned with the current state are both defensible, and the sun
        beside it settles it: a sun labelled Night would be nonsense.
        """
        return "Night" if self.is_dark else "Day"

    def icon_name(self) -> str:
        """Which drawn icon goes on the toggle button."""
        return 'moon' if self.is_dark else 'sun'

    def status_text(self) -> str:
        """
        The subtle line saying who is deciding.

        Empty while following the system: that is the default and the quiet
        case, and a permanent "Following system" badge is chrome nobody reads
        after the first day. It appears only once the user has overridden it,
        which is when it is telling them something they might have forgotten.
        """
        if self.following_system:
            return ""
        return f"Manual ({self._appearance})"

    # ---- changing it -----------------------------------------------------

    def set_mode(self, mode: str, remember: bool = True) -> bool:
        """
        Ask for a mode, and settle the appearance that follows from it.

        PARAMETERS:
        -----------
        mode : str
            One of MODES. Anything else is refused rather than guessed at.
        remember : bool
            Whether to save it as the preference for next time.

        RETURNS:
        --------
        bool
            True when anything changed - the mode, the appearance, or both.
        """
        if mode not in MODES:
            logger.warning("Ignoring unknown theme mode %r", mode)
            return False

        was_mode, was_appearance = self._mode, self._appearance
        self._mode = mode
        self._appearance = self._resolve_appearance()

        if remember and self._persist:
            save_mode(mode)

        if self._appearance != was_appearance:
            self._apply(self._appearance)

        changed = (self._mode != was_mode
                   or self._appearance != was_appearance)
        if changed:
            logger.info("Theme mode %s, appearance %s",
                        self._mode, self._appearance)
            self._announce()

        # Following the system again means the poll has to be running; an
        # explicit choice means it does not.
        self._reschedule()
        return changed

    def toggle(self) -> str:
        """
        Flip between light and dark, and take manual control.

        RETURNS:
        --------
        str
            The appearance now in force.

        DEVELOPMENT NOTES:
        ------------------
        Flipping *the appearance*, not the mode. Pressing the button while
        following a dark desktop asks for light - which is a manual light,
        not a manual dark - so the flip is read off what is on screen rather
        than off a mode that was not naming an appearance at all.
        """
        wanted = MODE_LIGHT if self.is_dark else MODE_DARK
        self.set_mode(wanted)
        return self._appearance

    def sync_with_system(self) -> bool:
        """
        Give the decision back to the desktop.

        RETURNS:
        --------
        bool
            True when anything changed. Already following it, this does
            nothing and says so.
        """
        return self.set_mode(MODE_SYSTEM)

    # ---- telling the rest of the application -----------------------------

    def subscribe(self, listener: Callable[[str, str], None],
                  owner=None) -> None:
        """
        Be told when the theme changes.

        PARAMETERS:
        -----------
        listener : Callable[[str, str], None]
            Called with (mode, appearance) after every change. Used by the
            toggle button to redraw its icon and by the View menu to show
            which mode is ticked.
        owner : Optional[widget]
            The widget the listener belongs to. Given one, the subscription
            is dropped as soon as that widget is destroyed.

        DEVELOPMENT NOTES:
        ------------------
        The owner is what keeps this from being a leak. A listener is
        normally a closure over a toolbar, so the controller holding it
        holds the whole widget tree behind it - and the controller outlives
        any number of toolbars, because it belongs to the application. Five
        toolbars built and destroyed left five dead listeners, and five
        widget trees that could never be collected.

        Held weakly as well, so an owner that is garbage collected without
        Tk ever being told - which is what happens in a test - does not keep
        its listener alive either.
        """
        # Dropped here as well as in _announce, so a toolbar being rebuilt
        # clears the one it is replacing. Waiting for the next theme change
        # would let them pile up in an application whose theme never moves,
        # which is most of them.
        self._drop_dead_listeners()
        self._listeners.append((listener, self._owner_ref(owner)))

    def _drop_dead_listeners(self) -> None:
        """Forget every subscription whose owner has gone."""
        self._listeners = [
            (listener, owner) for listener, owner in self._listeners
            if not self._owner_is_gone(owner)
        ]

    @staticmethod
    def _owner_ref(owner):
        """
        A weak reference to a listener's owner, or None when it has none.

        Not every object can be weakly referenced, and a listener whose
        owner cannot be is simply kept for the life of the controller - the
        old behaviour, for the callers that do not name one.
        """
        if owner is None:
            return None
        try:
            import weakref
            return weakref.ref(owner)
        except TypeError:
            return None

    @staticmethod
    def _owner_is_gone(reference) -> bool:
        """Whether a subscription's owner has been destroyed or collected."""
        if reference is None:
            return False

        owner = reference()
        if owner is None:
            return True

        # A Tk widget that has been destroyed is still a live Python object;
        # winfo_exists is what actually answers the question.
        exists = getattr(owner, 'winfo_exists', None)
        if exists is None:
            return False
        try:
            return not exists()
        except Exception:
            return True

    def unsubscribe(self, listener: Callable[[str, str], None]) -> bool:
        """
        Stop telling a listener about theme changes.

        RETURNS:
        --------
        bool
            True when there was one to remove. Callers that named an owner
            do not need this; it is for anything that has to detach earlier
            than its owner goes.
        """
        for index, (existing, _owner) in enumerate(self._listeners):
            if existing is listener:
                del self._listeners[index]
                return True
        return False

    def _announce(self) -> None:
        """
        Tell every listener, and let none of them stop the others.

        A listener is a widget, and a widget that has been destroyed raises
        when it is written to. One dead toolbar must not stop the theme
        reaching the rest of the window.

        Subscriptions whose owner has gone are dropped here rather than
        called. That is what keeps the list from growing for the life of the
        application - see subscribe.
        """
        alive = []
        for listener, owner in self._listeners:
            if self._owner_is_gone(owner):
                continue
            alive.append((listener, owner))
            try:
                listener(self._mode, self._appearance)
            except Exception:
                logger.exception("A theme listener failed")

        self._listeners = alive

    # ---- following the desktop -------------------------------------------

    def start_watching(self, widget) -> None:
        """
        Begin re-reading the desktop setting, if the mode calls for it.

        PARAMETERS:
        -----------
        widget : widget
            Any Tk widget; its `after` is what schedules the poll. Held so
            the poll can be cancelled and rescheduled as the mode changes.
        """
        self._widget = widget
        self._reschedule()

    def stop_watching(self) -> None:
        """Cancel the poll, if one is pending."""
        if self._poll_id is not None and self._widget is not None:
            try:
                self._widget.after_cancel(self._poll_id)
            except Exception:
                logger.debug("Could not cancel the theme poll")
        self._poll_id = None

    def _reschedule(self) -> None:
        """Put the poll in step with the mode: running only under `system`."""
        self.stop_watching()
        if self._widget is None or not self.following_system:
            return
        try:
            self._poll_id = self._widget.after(
                int(self.POLL_SECONDS * 1000), self._poll)
        except Exception:
            logger.debug("Could not schedule the theme poll")

    def _poll(self) -> None:
        """
        Re-read the desktop setting and follow it if it moved.

        Reschedules itself whatever it finds, so the window goes on following
        the desktop for as long as the mode says to.
        """
        self._poll_id = None

        if not self.following_system:
            return

        found = detect_system_appearance()
        if found != self._appearance:
            logger.info("The desktop switched to %s; following it", found)
            self._appearance = found
            self._apply(found)
            self._announce()

        self._reschedule()

    def refresh_from_system(self) -> bool:
        """
        Re-read the desktop setting once, now.

        RETURNS:
        --------
        bool
            True when the appearance moved. For the case a poll would
            eventually catch but a person is waiting on - reopening a window,
            or a test that does not want to wait POLL_SECONDS.
        """
        if not self.following_system:
            return False

        found = detect_system_appearance()
        if found == self._appearance:
            return False

        self._appearance = found
        self._apply(found)
        self._announce()
        return True
