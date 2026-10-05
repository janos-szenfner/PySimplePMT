"""
The theme: who decides light or dark, and the colours that follow.

The scenarios live in features/theme.feature. They pin down the
controller - toggle, sync, the poll that follows the desktop, the
listeners, and the saved preference - plus the palette invariants and
the drawn icons.

The toolbar control and the panes need a display and stay in
tests/test_theme.py.

detect_system_appearance is faked throughout: the desktop this runs on
has a setting of its own and the tests must not depend on which. A
controller's save_mode is faked for the same reason - a stand-in must
not write to the user's real file. The scenarios about the preference
itself write to a temporary settings directory instead.
"""

import gc
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.views import theme
from tests.pixels import flat_pixels


scenarios('features/theme.feature')


MODES = {'system': theme.MODE_SYSTEM, 'light': theme.MODE_LIGHT,
         'dark': theme.MODE_DARK}
APPEARANCES = {'light': theme.LIGHT, 'dark': theme.DARK}


@pytest.fixture
def ctx(monkeypatch):
    ctx = SimpleNamespace(desktop='light', applied=[], heard=[], saved=[])
    # A test that reads the real desktop reports where it ran.
    monkeypatch.setattr(theme, 'detect_system_appearance',
                        lambda: ctx.desktop)
    return ctx


class _FakeWidget:
    """A widget that records what was scheduled on it."""

    def __init__(self):
        self.scheduled = []
        self.cancelled = []
        self._next = 0

    def after(self, _ms, callback):
        self._next += 1
        self.scheduled.append((self._next, callback))
        return self._next

    def after_cancel(self, identifier):
        self.cancelled.append(identifier)


class _Owner:
    """Something that can be destroyed, standing in for a widget."""

    def __init__(self):
        self.alive = True
        self.heard = []

    def winfo_exists(self):
        return self.alive

    def hear(self, mode, appearance):
        self.heard.append((mode, appearance))


def _controller(ctx, desktop='light', mode=theme.MODE_SYSTEM,
                persist=False):
    """A controller over a named desktop, recording what it applies."""
    ctx.desktop = desktop
    ctx.controller = theme.ThemeController(mode=mode,
                                           apply=ctx.applied.append,
                                           persist=persist)


def _watch_saving(ctx, monkeypatch):
    """Recording save_mode: what a controller writes, and when."""
    monkeypatch.setattr(theme, 'save_mode',
                        lambda mode: ctx.saved.append(mode) or True)


# ---- the controller ---------------------------------------------------------------

@given(parsers.parse('a controller over a "{desktop}" desktop'))
def a_controller(ctx, monkeypatch, desktop):
    _watch_saving(ctx, monkeypatch)
    _controller(ctx, desktop)


@given(parsers.parse('a controller over a "{desktop}" desktop in "{mode}" '
                     'mode'))
def a_controller_in_a_mode(ctx, monkeypatch, desktop, mode):
    _watch_saving(ctx, monkeypatch)
    _controller(ctx, desktop, mode=MODES[mode])


@given(parsers.parse('a controller over a "{desktop}" desktop with saving '
                     'watched'))
def a_stand_in_controller(ctx, monkeypatch, desktop):
    """The stand-in a toolbar makes: persist=False, never writes."""
    _watch_saving(ctx, monkeypatch)
    _controller(ctx, desktop, persist=False)


@given(parsers.parse('an owned controller over a "{desktop}" desktop with '
                     'saving watched'))
def an_owned_controller(ctx, monkeypatch, desktop):
    _watch_saving(ctx, monkeypatch)
    _controller(ctx, desktop, persist=True)


@when('it is toggled')
@given('it is toggled')
def it_is_toggled(ctx):
    ctx.answer = ctx.controller.toggle()


@when('it syncs with the system')
def it_syncs(ctx):
    ctx.answer = ctx.controller.sync_with_system()


@when(parsers.parse('"{mode}" mode is asked for'))
def a_mode_is_asked(ctx, mode):
    ctx.answer = ctx.controller.set_mode(mode)


@then('the request is refused')
def the_request_is_refused(ctx):
    assert ctx.answer is False


@then('it follows the system')
def it_follows(ctx):
    assert ctx.controller.following_system


@then('it does not follow the system')
def it_does_not_follow(ctx):
    assert not ctx.controller.following_system


@then(parsers.parse('its appearance is "{appearance}"'))
def its_appearance_is(ctx, appearance):
    assert ctx.controller.appearance == APPEARANCES[appearance]


@then(parsers.parse('its mode is "{mode}"'))
def its_mode_is(ctx, mode):
    assert ctx.controller.mode == MODES[mode]


@then('it applied nothing')
def it_applied_nothing(ctx):
    assert ctx.applied == []


@then(parsers.parse('it applied "{appearance}"'))
def it_applied(ctx, appearance):
    assert ctx.applied == [appearance]


# ---- the caption, the icon, and the status line ---------------------------------------

@then(parsers.parse('a "{desktop}" desktop says "{text}"'))
def a_desktop_says(ctx, monkeypatch, desktop, text):
    _watch_saving(ctx, monkeypatch)
    _controller(ctx, desktop)
    assert ctx.controller.button_text() == text


@then(parsers.parse('a "{desktop}" desktop carries the "{icon}" icon'))
def a_desktop_carries(ctx, monkeypatch, desktop, icon):
    _watch_saving(ctx, monkeypatch)
    _controller(ctx, desktop)
    assert ctx.controller.icon_name() == icon


@then('its status line is empty')
def its_status_line_is_empty(ctx):
    assert ctx.controller.status_text() == ""


@then(parsers.parse('its status line mentions "{text}"'))
def its_status_line_mentions(ctx, text):
    assert text in ctx.controller.status_text()


# ---- the poll -------------------------------------------------------------------------

@when('it starts watching')
@given('it is watching')
def it_starts_watching(ctx):
    ctx.widget = _FakeWidget()
    ctx.controller.start_watching(ctx.widget)


@when(parsers.parse('the desktop turns "{appearance}" and the poll fires'))
def the_desktop_turns(ctx, appearance):
    ctx.desktop = appearance
    ctx.widget.scheduled[0][1]()


@when('the poll fires')
def the_poll_fires(ctx):
    ctx.widget.scheduled[0][1]()


@then(parsers.parse('{count:d} poll is scheduled'))
@then(parsers.parse('{count:d} polls have been scheduled'))
def polls_scheduled(ctx, count):
    assert len(ctx.widget.scheduled) == count


@then('no polls are scheduled')
def no_polls(ctx):
    assert ctx.widget.scheduled == []


@then('the poll is cancelled')
def the_poll_is_cancelled(ctx):
    assert ctx.widget.cancelled == [1]


# ---- listeners ---------------------------------------------------------------------------

@given('a listener')
def a_listener(ctx):
    ctx.controller.subscribe(
        lambda mode, appearance: ctx.heard.append((mode, appearance)))


@given('a failing listener')
def a_failing_listener(ctx):
    def boom(_mode, _appearance):
        raise RuntimeError("dead widget")
    ctx.controller.subscribe(boom)


@then(parsers.parse('the listeners saw "{pairs}"'))
def the_listeners_saw(ctx, pairs):
    heard = []
    for pair in pairs.split(','):
        mode, appearance = pair.strip().split(':')
        heard.append((MODES[mode], APPEARANCES[appearance]))
    assert ctx.heard == heard


@then('the listener heard')
def the_listener_heard(ctx):
    assert ctx.heard


@then('the listener heard nothing')
def the_listener_heard_nothing(ctx):
    assert ctx.heard == []


# ---- the preference: the real save/load, against a temporary directory ---------------

@when(parsers.parse('"{mode}" mode is saved'))
def a_mode_is_saved(ctx, monkeypatch, tmp_path, mode):
    monkeypatch.setattr(theme, 'settings_directory', lambda: tmp_path)
    ctx.saved_ok = theme.save_mode(MODES[mode])


@then('it is saved')
def it_is_saved(ctx):
    assert ctx.saved_ok is True


@given('an empty settings directory')
def an_empty_settings_directory(monkeypatch, tmp_path):
    monkeypatch.setattr(theme, 'settings_directory',
                        lambda: tmp_path / 'nothing-here')


@given(parsers.parse('a preference file holding "{content}"'))
def a_preference_file_holding(monkeypatch, tmp_path, content):
    (tmp_path / theme.SETTINGS_FILE).write_text(content)
    monkeypatch.setattr(theme, 'settings_directory', lambda: tmp_path)


@given(parsers.parse('a preference file naming "{mode}"'))
def a_preference_file_naming(monkeypatch, tmp_path, mode):
    (tmp_path / theme.SETTINGS_FILE).write_text(
        json.dumps({'theme_mode': mode}))
    monkeypatch.setattr(theme, 'settings_directory', lambda: tmp_path)


@given('a settings directory that cannot be written')
def an_unwritable_settings_directory(monkeypatch):
    monkeypatch.setattr(theme, 'settings_directory',
                        lambda: Path('/proc/nowhere/PySimplePMT'))


@then(parsers.parse('the mode read back is "{mode}"'))
def the_mode_read_back_is(ctx, mode):
    assert theme.load_mode() == MODES[mode]


@then('nothing was saved')
def nothing_was_saved(ctx):
    assert ctx.saved == []


@then(parsers.parse('"{mode}" was saved once'))
def a_mode_was_saved_once(ctx, mode):
    assert ctx.saved == [MODES[mode]]


@then(parsers.parse('saving "{mode}" returns False'))
def saving_returns_false(ctx, mode):
    assert theme.save_mode(MODES[mode]) is False


# ---- the palette ------------------------------------------------------------------------

_PALETTE = (
    'TEXT', 'MUTED_TEXT', 'WARNING_TEXT', 'FIELD_BG', 'FIELD_TEXT',
    'FIELD_BG_DISABLED', 'FIELD_TEXT_DISABLED', 'SEPARATOR', 'ROW_BG',
    'POSITIVE_TEXT', 'NEGATIVE_TEXT', 'MENU_BG', 'MENU_HOVER',
    'MENU_TEXT', 'DROPDOWN_BG', 'ICON_SEPARATOR',
    'GRID_ROW_BG', 'GRID_ROW_ALT', 'GRID_HEADING_BG', 'GRID_TEXT',
    'GRID_LINE', 'GRID_SELECT_BG', 'GRID_CUT_TEXT', 'GRID_INACTIVE_TEXT',
    'GRID_CRITICAL_BG', 'GRID_HIGHLIGHT_BG',
    'GRID_TIGHT_BG', 'SCROLL_TROUGH', 'SCROLL_THUMB',
    'SCROLL_THUMB_ACTIVE', 'SASH_BG', 'SASH_LIGHT', 'SASH_DARK',
    'CHART_BG', 'CHART_TEXT', 'CHART_GRID',
    'HEADER_MONTH_BG', 'HEADER_CELL_BG', 'HEADER_RULE',
    'HEADER_WEEK_RULE', 'HEADER_MONTH_TEXT', 'HEADER_DAY_TEXT',
    'HEADER_NON_WORKING', 'HEADER_TODAY_BG', 'HEADER_TODAY_TEXT',
    'DASH_PLOT_BG', 'DASH_BOARD_BG', 'DASH_TITLE_TEXT', 'DASH_TICK_TEXT',
    'DASH_AXIS', 'DASH_GRID', 'DASH_PROGRESS_BAR', 'DASH_DURATION_BAR',
    'DASH_SERIES_1', 'DASH_SERIES_2', 'DASH_SERIES_3', 'DASH_SERIES_4',
    'DASH_KPI_BG', 'DASH_KPI_BORDER',
    'TL_BAND_BG', 'TL_BAND_TEXT', 'TL_HEADER_BG', 'TL_LANE_BG',
    'TL_SPINE', 'TL_TODAY', 'TL_PROGRESS_UNDER',
)


@then('the palette lists every pair the module declares')
def the_palette_is_complete():
    declared = {
        name for name in dir(theme)
        if name.isupper() and isinstance(getattr(theme, name), tuple)
        and len(getattr(theme, name)) == 2
        and all(isinstance(half, str) for half in getattr(theme, name))
    }
    assert declared - set(_PALETTE) == set()


@then('every palette entry is a pair')
def every_entry_is_a_pair():
    for name in _PALETTE:
        colour = getattr(theme, name)
        assert isinstance(colour, tuple), name
        assert len(colour) == 2, name


@then('no palette entry repeats itself')
def no_entry_repeats_itself():
    for name in _PALETTE:
        light, dark = getattr(theme, name)
        assert light != dark, name


@then('every palette half is a six-figure hex colour')
def every_half_is_a_colour():
    import re
    colour = re.compile(r'^#[0-9a-fA-F]{6}$')
    for name in _PALETTE:
        for half in getattr(theme, name):
            assert colour.match(half), name


@then(parsers.parse('pairing "{colour}" raises'))
def pairing_refuses(colour):
    with pytest.raises(TypeError):
        theme.pair(colour)


@then(parsers.parse('"{name}" resolves light to its first half and dark to '
                    'its second'))
def resolve_picks_the_right_half(name):
    pair = getattr(theme, name)
    assert theme.resolve(pair, theme.LIGHT) == pair[0]
    assert theme.resolve(pair, theme.DARK) == pair[1]


def _contrast(first, second):
    """The WCAG contrast ratio between two hex colours."""
    def luminance(value):
        value = value.lstrip('#')
        channels = [int(value[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        adjusted = [c / 12.92 if c <= 0.03928
                    else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return (0.2126 * adjusted[0] + 0.7152 * adjusted[1]
                + 0.0722 * adjusted[2])

    high, low = sorted((luminance(first), luminance(second)),
                       reverse=True)
    return (high + 0.05) / (low + 0.05)


_READABLE = (
    ('GRID_TEXT', 'GRID_ROW_BG', 4.5),
    ('GRID_TEXT', 'GRID_ROW_ALT', 4.5),
    ('GRID_TEXT', 'GRID_HEADING_BG', 4.5),
    ('GRID_TEXT', 'GRID_SELECT_BG', 4.5),
    ('GRID_TEXT', 'GRID_CRITICAL_BG', 4.5),
    ('GRID_TEXT', 'GRID_HIGHLIGHT_BG', 4.5),
    ('GRID_TEXT', 'GRID_TIGHT_BG', 4.5),
    ('CHART_TEXT', 'CHART_BG', 4.5),
    ('HEADER_DAY_TEXT', 'HEADER_CELL_BG', 4.5),
    ('HEADER_DAY_TEXT', 'HEADER_NON_WORKING', 4.5),
    ('HEADER_MONTH_TEXT', 'HEADER_MONTH_BG', 4.5),
    ('HEADER_TODAY_TEXT', 'HEADER_TODAY_BG', 4.5),
    ('FIELD_TEXT', 'FIELD_BG', 4.5),
    ('FIELD_TEXT', 'DROPDOWN_BG', 4.5),
    ('MUTED_TEXT', 'DROPDOWN_BG', 4.5),
    ('WARNING_TEXT', 'DROPDOWN_BG', 4.5),
    ('MENU_TEXT', 'MENU_BG', 4.5),
    ('POSITIVE_TEXT', 'ROW_BG', 4.5),
    ('NEGATIVE_TEXT', 'ROW_BG', 4.5),
)


@then('both appearances are readable')
def both_appearances_are_readable():
    failures = []
    for index, appearance in ((0, 'light'), (1, 'dark')):
        for text_name, background_name, wanted in _READABLE:
            text = getattr(theme, text_name)[index]
            background = getattr(theme, background_name)[index]
            ratio = _contrast(text, background)
            if ratio < wanted:
                failures.append(
                    f"{appearance}: {text_name} on {background_name} "
                    f"is {ratio:.2f}, wanted {wanted}")

    assert failures == []


@then('the disabled field is quieter than a live one in both appearances')
def the_disabled_field_is_quieter():
    for index, appearance in ((0, 'light'), (1, 'dark')):
        ratio = _contrast(theme.FIELD_TEXT_DISABLED[index],
                          theme.FIELD_BG_DISABLED[index])
        live = _contrast(theme.FIELD_TEXT[index],
                         theme.FIELD_BG[index])
        assert ratio < live, appearance
        assert ratio > 2.0, appearance


# ---- the drawn icons ------------------------------------------------------------------------

@then(parsers.parse('the "{first}" and "{second}" icons are drawn at '
                    '{size:d}px'))
def the_icons_are_drawn(first, second, size):
    from gantt_app.resources.icons import draw_icon

    for name in (first, second):
        icon = draw_icon(name, size=size)
        assert icon is not None, name
        assert icon.size == (size, size), name


@then(parsers.parse('the "{name}" drawn in light ink differs from dark ink'))
def the_icon_follows_the_ink(name):
    from gantt_app.resources.icons import draw_icon

    light = draw_icon(name, size=20, color=theme.ICON_INK_LIGHT)
    dark = draw_icon(name, size=20, color=theme.ICON_INK_DARK)

    assert flat_pixels(light) != flat_pixels(dark)


@then(parsers.parse('the "{name}" covers less than its disc but is not '
                    'empty'))
def the_moon_is_a_crescent(name):
    from gantt_app.resources.icons import draw_icon

    moon = draw_icon(name, size=40, color=(0, 0, 0))
    disc = draw_icon('sun', size=40, color=(0, 0, 0))

    def opaque(image):
        return sum(1 for pixel in flat_pixels(image) if pixel[3] > 128)

    assert opaque(moon) > 0
    assert opaque(moon) < 40 * 40 * 0.5
    assert opaque(moon) > opaque(disc) * 0.3


# ---- subscriptions do not pile up ---------------------------------------------------------------

@given('a listener owned by a widget')
def a_listener_owned_by_a_widget(ctx):
    ctx.owner = _Owner()
    ctx.controller.subscribe(
        lambda mode, appearance: ctx.heard.append((mode, appearance)),
        owner=ctx.owner)


@given('an ownerless listener')
def an_ownerless_listener(ctx):
    ctx.orphan = lambda mode, appearance: ctx.heard.append(
        (mode, appearance))
    ctx.controller.subscribe(ctx.orphan)


@given("a widget's bound method owned by something else")
def a_bound_method_owned_by_something_else(ctx):
    ctx.widget_being_heard = _Owner()
    ctx.owner = _Owner()
    ctx.controller.subscribe(ctx.widget_being_heard.hear,
                             owner=ctx.owner)


@when('the owner dies')
def the_owner_dies(ctx):
    ctx.owner.alive = False


@when('the widget dies')
def the_widget_dies(ctx):
    ctx.widget_being_heard.alive = False


@when('the owner is collected')
def the_owner_is_collected(ctx):
    del ctx.owner
    gc.collect()


@given(parsers.parse('{count:d} subscriptions whose owners have died'))
def dead_subscriptions(ctx, count):
    for _ in range(count):
        owner = _Owner()
        ctx.controller.subscribe(lambda *_a: None, owner=owner)
        owner.alive = False


@when('a fresh listener subscribes')
def a_fresh_listener_subscribes(ctx):
    ctx.controller.subscribe(lambda *_a: None, owner=_Owner())


@when('it is unsubscribed by hand')
def it_is_unsubscribed(ctx):
    ctx.answer = ctx.controller.unsubscribe(ctx.orphan)


@then('the unsubscribe said so')
def the_unsubscribe_said_so(ctx):
    assert ctx.answer is True


@then('unsubscribing it again says there was none')
def unsubscribing_again_says_none(ctx):
    assert ctx.controller.unsubscribe(ctx.orphan) is False


@then(parsers.parse('{count:d} listener is held'))
def listeners_held(ctx, count):
    assert len(ctx.controller._listeners) == count


@then('no listeners are held')
def no_listeners_held(ctx):
    assert ctx.controller._listeners == []
