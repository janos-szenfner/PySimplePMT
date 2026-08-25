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


if __name__ == '__main__':
    unittest.main()
