"""
Tests for which modifier key a shortcut uses, and what it is called.

WHY THIS MODULE EXISTS:
======================
Every shortcut in the application was written out as Control. On a Mac that
is not the key anybody reaches for, and it is not the key macOS reports when
they press Cmd - so the shortcuts did nothing there while their captions
promised otherwise.

The sequence and the caption are worked out from the same place because they
have to agree. A caption naming a key that is not bound is worse than no
caption at all, and the two drift the moment they are written separately.

DEVELOPMENT NOTES:
------------------
This is where the platform branch is pinned exactly. The tests that bind
these cannot check the spelling: Tk stores a binding under a name of its own
choosing - <Command-b> comes back as <Mod1-Key-b> - so those check only that
something arrived for each key.

Nothing here needs a display.
"""

import unittest
from unittest import mock

from gantt_app import shortcuts


class ModifierTestCase(unittest.TestCase):
    """Which key this platform uses, and how it is spelt."""

    def test_the_modifier_matches_the_platform(self):
        """Command on a Mac, Control everywhere else."""
        expected = 'Command' if shortcuts.IS_MACOS else 'Control'

        self.assertEqual(shortcuts.MODIFIER, expected)

    def test_the_label_matches_the_modifier(self):
        """What is shown and what is bound describe the same key."""
        expected = '⌘' if shortcuts.IS_MACOS else 'Ctrl'

        self.assertEqual(shortcuts.MODIFIER_LABEL, expected)


class SequenceTestCase(unittest.TestCase):
    """What gets handed to Tk."""

    def test_a_letter_is_bound_in_both_cases(self):
        """
        Tk reports the upper case one when caps lock is on.

        A shortcut that stops working with caps lock is the kind of fault
        nobody reports and everybody notices.
        """
        found = shortcuts.sequences('b')

        self.assertEqual(len(found), 2)
        self.assertIn(f'<{shortcuts.MODIFIER}-b>', found)
        self.assertIn(f'<{shortcuts.MODIFIER}-B>', found)

    def test_the_case_it_is_given_does_not_matter(self):
        """A caller may pass either; both forms come back regardless."""
        self.assertEqual(set(shortcuts.sequences('B')),
                         set(shortcuts.sequences('b')))

    def test_a_named_key_is_bound_once(self):
        """Return has no case to worry about."""
        self.assertEqual(shortcuts.sequences('Return'),
                         (f'<{shortcuts.MODIFIER}-Return>',))

    def test_every_sequence_is_shaped_like_one(self):
        """A malformed sequence is a binding Tk refuses at run time."""
        for key in ('b', 'Return', 'KP_Enter'):
            for sequence in shortcuts.sequences(key):
                self.assertTrue(sequence.startswith('<'), sequence)
                self.assertTrue(sequence.endswith('>'), sequence)
                self.assertIn(shortcuts.MODIFIER, sequence)


class AcceleratorTestCase(unittest.TestCase):
    """How a shortcut is written for the reader."""

    def test_a_mac_gets_the_symbol_and_no_plus(self):
        """⌘B, which is how a Mac writes it."""
        with mock.patch.object(shortcuts, 'IS_MACOS', True), \
                mock.patch.object(shortcuts, 'MODIFIER_LABEL', '⌘'):
            self.assertEqual(shortcuts.accelerator('B'), '⌘B')

    def test_everywhere_else_gets_ctrl_and_a_plus(self):
        """Ctrl+B, which is how everywhere else writes it."""
        with mock.patch.object(shortcuts, 'IS_MACOS', False), \
                mock.patch.object(shortcuts, 'MODIFIER_LABEL', 'Ctrl'):
            self.assertEqual(shortcuts.accelerator('B'), 'Ctrl+B')

    def test_return_is_written_as_enter(self):
        """Nobody calls the key Return on a keyboard."""
        self.assertIn('Enter', shortcuts.accelerator('Return'))
        self.assertNotIn('Return', shortcuts.accelerator('Return'))

    def test_it_names_the_key_that_is_actually_bound(self):
        """
        The caption and the binding come from the same branch.

        Written separately they drift, and a caption promising a key that
        does nothing is the fault this module exists to prevent.
        """
        label = shortcuts.accelerator('B')

        if shortcuts.IS_MACOS:
            self.assertIn('⌘', label)
            self.assertNotIn('Ctrl', label)
        else:
            self.assertIn('Ctrl', label)
            self.assertNotIn('⌘', label)


class KeyIdentityTestCase(unittest.TestCase):
    """
    Which key an event is, when Option has taken the character away.

    WHY THESE EXIST:
    ----------------
    Option is a compose key on macOS: Option+I is the dead key for a
    circumflex, so the event carries no 'i' anywhere a binding could match.
    All that is left of the key pressed is where it sits on the keyboard,
    which is what the keycode names - and reading it wrongly is silent, as
    a shortcut that does nothing at all.
    """

    class FakeEvent:
        """Only the attributes is_key reads."""

        def __init__(self, keysym='', char='', keycode=None, state=0):
            self.keysym = keysym
            self.char = char
            self.keycode = keycode
            self.state = state

    def test_the_keysym_is_enough(self):
        """The ordinary case, on every platform."""
        self.assertTrue(shortcuts.is_key(self.FakeEvent(keysym='i'), 'I'))

    def test_another_key_is_not_it(self):
        """A near miss is still a miss."""
        self.assertFalse(shortcuts.is_key(self.FakeEvent(keysym='o'), 'I'))

    def test_a_packed_keycode_still_names_the_key(self):
        """
        The character underneath the keycode does not hide the key.

        Tk packs the virtual keycode into the high bytes and leaves the
        character below it, so the whole number is never equal to the
        keycode on its own - which is what the comparison used to ask for.
        """
        circumflex = ord('ˆ')
        packed = (shortcuts.MAC_KEYCODES['i'] << 16) | circumflex

        with mock.patch.object(shortcuts, 'IS_MACOS', True):
            event = self.FakeEvent(keysym='dead_circumflex', char='ˆ',
                                   keycode=packed)

            self.assertTrue(shortcuts.is_key(event, 'I'))

    def test_a_bare_keycode_still_names_the_key(self):
        """The other spelling Tk has used for the same thing."""
        with mock.patch.object(shortcuts, 'IS_MACOS', True):
            event = self.FakeEvent(keysym='dead_circumflex',
                                   keycode=shortcuts.MAC_KEYCODES['i'])

            self.assertTrue(shortcuts.is_key(event, 'I'))

    def test_another_packed_keycode_is_not_it(self):
        """A different physical key, packed the same way, is not I."""
        packed = (shortcuts.MAC_KEYCODES['b'] << 16) | ord('b')

        with mock.patch.object(shortcuts, 'IS_MACOS', True):
            event = self.FakeEvent(keysym='dead_circumflex', keycode=packed)

            self.assertFalse(shortcuts.is_key(event, 'I'))


class ModifiersHeldTestCase(unittest.TestCase):
    """
    Reading the modifiers out of the event, where Tk would not match them.

    WHY THESE EXIST:
    ----------------
    This is the last net under the new-task shortcut. It has to catch
    Cmd+Option+I, and it must not catch plain Cmd+I - which is italic, and
    would start creating tasks instead.
    """

    def held(self, state):
        """An event carrying nothing but these modifier bits."""
        return KeyIdentityTestCase.FakeEvent(keysym='i', state=state)

    def test_both_modifiers_are_held(self):
        """The combination the shortcut is on."""
        state = shortcuts.COMMAND_BIT | shortcuts.OPTION_BIT

        with mock.patch.object(shortcuts, 'IS_MACOS', True):
            self.assertTrue(shortcuts.modifiers_held(self.held(state),
                                                     alt=True))

    def test_the_modifier_alone_is_not_the_pair(self):
        """Cmd+I is italic and has to stay italic."""
        with mock.patch.object(shortcuts, 'IS_MACOS', True):
            self.assertFalse(
                shortcuts.modifiers_held(self.held(shortcuts.COMMAND_BIT),
                                         alt=True))

    def test_a_shift_alongside_does_not_matter(self):
        """Other modifiers are not asked about."""
        state = shortcuts.COMMAND_BIT | shortcuts.OPTION_BIT | 0x01

        with mock.patch.object(shortcuts, 'IS_MACOS', True):
            self.assertTrue(shortcuts.modifiers_held(self.held(state),
                                                     alt=True))

    def test_nothing_is_read_off_a_mac(self):
        """
        Everywhere else Tk matches the sequence, and the bit Alt sets is
        not the same on Windows as on X11 - so this answers no rather than
        guessing.
        """
        state = shortcuts.COMMAND_BIT | shortcuts.OPTION_BIT

        with mock.patch.object(shortcuts, 'IS_MACOS', False):
            self.assertFalse(shortcuts.modifiers_held(self.held(state),
                                                      alt=True))


if __name__ == '__main__':
    unittest.main()
