"""
pytest-bdd tests for which modifier key a shortcut uses, and what it
is called.

Run with:
    python3 -m pytest tests/test_shortcuts_bdd.py -q

Nothing here needs a display. Converted from test_shortcuts.py -
every case carried over.
"""
from types import SimpleNamespace
from unittest import mock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.utils import shortcuts

pytestmark = [
    pytest.mark.shortcuts,
]

scenarios("features/shortcuts.feature")


class FakeEvent:
    """Only the attributes is_key reads."""

    def __init__(self, keysym='', char='', keycode=None, state=0):
        self.keysym = keysym
        self.char = char
        self.keycode = keycode
        self.state = state


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------

@when("the platform is a Mac", target_fixture="ctx")
def the_platform_is_a_mac():
    ctx = SimpleNamespace()
    ctx.patch = mock.patch.object(shortcuts, 'IS_MACOS', True)
    ctx.label_patch = mock.patch.object(shortcuts, 'MODIFIER_LABEL', '⌘')
    ctx.patch.start()
    ctx.label_patch.start()
    return ctx


@when("the platform is not a Mac", target_fixture="ctx")
def the_platform_is_not_a_mac():
    ctx = SimpleNamespace()
    ctx.patch = mock.patch.object(shortcuts, 'IS_MACOS', False)
    ctx.label_patch = mock.patch.object(shortcuts, 'MODIFIER_LABEL',
                                        'Ctrl')
    ctx.patch.start()
    ctx.label_patch.start()
    return ctx


@when(parsers.parse('an event carries keysym "{keysym}"'),
      target_fixture="ctx")
def an_event_carries_a_keysym(keysym):
    return SimpleNamespace(event=FakeEvent(keysym=keysym))


@when("a Mac event carries the i keycode packed over a circumflex",
      target_fixture="ctx")
def a_mac_event_with_a_packed_keycode():
    circumflex = ord('ˆ')
    packed = (shortcuts.MAC_KEYCODES['i'] << 16) | circumflex
    return SimpleNamespace(
        event=FakeEvent(keysym='dead_circumflex', char='ˆ',
                        keycode=packed),
        macos=True)


@when("a Mac event carries the bare i keycode", target_fixture="ctx")
def a_mac_event_with_a_bare_keycode():
    return SimpleNamespace(
        event=FakeEvent(keysym='dead_circumflex',
                        keycode=shortcuts.MAC_KEYCODES['i']),
        macos=True)


@when("a Mac event carries the b keycode packed over a b",
      target_fixture="ctx")
def a_mac_event_with_another_packed_keycode():
    packed = (shortcuts.MAC_KEYCODES['b'] << 16) | ord('b')
    return SimpleNamespace(
        event=FakeEvent(keysym='dead_circumflex', keycode=packed),
        macos=True)


def _held(ctx, state, macos):
    ctx.event = FakeEvent(keysym='i', state=state)
    ctx.macos = macos
    return ctx


@when("a Mac event holds Command and Option", target_fixture="ctx")
def a_mac_event_holds_command_and_option():
    return _held(SimpleNamespace(),
                 shortcuts.COMMAND_BIT | shortcuts.OPTION_BIT, True)


@when("a Mac event holds Command alone", target_fixture="ctx")
def a_mac_event_holds_command_alone():
    return _held(SimpleNamespace(), shortcuts.COMMAND_BIT, True)


@when("a Mac event holds Command, Option and Shift",
      target_fixture="ctx")
def a_mac_event_holds_command_option_shift():
    state = shortcuts.COMMAND_BIT | shortcuts.OPTION_BIT | 0x01
    return _held(SimpleNamespace(), state, True)


@when("a non-Mac event holds Command and Option", target_fixture="ctx")
def a_non_mac_event_holds_command_and_option():
    return _held(SimpleNamespace(),
                 shortcuts.COMMAND_BIT | shortcuts.OPTION_BIT, False)


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@then("the modifier is Command on macOS and Control elsewhere")
def the_modifier_matches_the_platform():
    expected = 'Command' if shortcuts.IS_MACOS else 'Control'
    assert shortcuts.MODIFIER == expected


@then("the label is the ⌘ symbol on macOS and Ctrl elsewhere")
def the_label_matches_the_modifier():
    expected = '⌘' if shortcuts.IS_MACOS else 'Ctrl'
    assert shortcuts.MODIFIER_LABEL == expected


@then(parsers.parse('"{key}" binds two sequences, for "{lower}" and '
                    '"{upper}"'))
def a_letter_is_bound_in_both_cases(key, lower, upper):
    found = shortcuts.sequences(key)
    assert len(found) == 2
    assert f'<{shortcuts.MODIFIER}-{lower}>' in found
    assert f'<{shortcuts.MODIFIER}-{upper}>' in found


@then(parsers.parse('"{first}" binds the same sequences as "{second}"'))
def the_case_does_not_matter(first, second):
    assert set(shortcuts.sequences(first)) == set(shortcuts.sequences(second))


@then(parsers.parse('"{key}" binds one sequence for "{named}"'))
def a_named_key_is_bound_once(key, named):
    assert shortcuts.sequences(key) == (f'<{shortcuts.MODIFIER}-{named}>',)


@then(parsers.parse('every sequence for "{first}", "{second}" and '
                    '"{third}" is well formed'))
def every_sequence_is_well_formed(first, second, third):
    for key in (first, second, third):
        for sequence in shortcuts.sequences(key):
            assert sequence.startswith('<'), sequence
            assert sequence.endswith('>'), sequence
            assert shortcuts.MODIFIER in sequence


@then(parsers.parse('the accelerator for "{key}" reads "{expected}"'))
def the_accelerator_reads(ctx, key, expected):
    try:
        assert shortcuts.accelerator(key) == expected
    finally:
        ctx.patch.stop()
        ctx.label_patch.stop()


@then(parsers.parse('the accelerator for "{key}" says Enter and not '
                    'Return'))
def return_is_written_as_enter(key):
    assert 'Enter' in shortcuts.accelerator(key)
    assert 'Return' not in shortcuts.accelerator(key)


@then(parsers.parse('the accelerator for "{key}" matches the platform\'s '
                    'modifier'))
def it_names_the_key_actually_bound(key):
    label = shortcuts.accelerator(key)
    if shortcuts.IS_MACOS:
        assert '⌘' in label
        assert 'Ctrl' not in label
    else:
        assert 'Ctrl' in label
        assert '⌘' not in label


@then(parsers.parse('it is the key "{key}"'))
def it_is_the_key(ctx, key):
    if getattr(ctx, 'macos', False):
        with mock.patch.object(shortcuts, 'IS_MACOS', True):
            assert shortcuts.is_key(ctx.event, key)
    else:
        assert shortcuts.is_key(ctx.event, key)


@then(parsers.parse('it is not the key "{key}"'))
def it_is_not_the_key(ctx, key):
    if getattr(ctx, 'macos', False):
        with mock.patch.object(shortcuts, 'IS_MACOS', True):
            assert not shortcuts.is_key(ctx.event, key)
    else:
        assert not shortcuts.is_key(ctx.event, key)


@then("the modifier pair is held")
def the_modifier_pair_is_held(ctx):
    with mock.patch.object(shortcuts, 'IS_MACOS', ctx.macos):
        assert shortcuts.modifiers_held(ctx.event, alt=True)


@then("the modifier pair is not held")
def the_modifier_pair_is_not_held(ctx):
    with mock.patch.object(shortcuts, 'IS_MACOS', ctx.macos):
        assert not shortcuts.modifiers_held(ctx.event, alt=True)
