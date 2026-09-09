"""
Tests for the About > Changelog window.

The parsing is pure and checked without a display; the window build and
single-instance behaviour are display-gated, like the other help windows.
"""

import unittest

from gantt_app.help.changelog import (
    CHANGELOG_SECTIONS,
    parse_changelog,
    show_changelog,
)


def _display_available() -> bool:
    try:
        import tkinter
        root = tkinter.Tk()
    except Exception:
        return False
    root.destroy()
    return True


HAVE_DISPLAY = _display_available()

SAMPLE = """# Changelog

## 2.0.0 - 2026-09-09

- A **bold** change with a `code` bit.
- A bullet wrapped
  over two lines.

## 1.0.0 - 2026-01-01

- The first release.
"""


class TestParsing(unittest.TestCase):
    def test_each_version_becomes_a_section(self):
        sections = parse_changelog(SAMPLE)
        headings = [h for h, _ in sections]
        self.assertEqual(headings, ['2.0.0 - 2026-09-09', '1.0.0 - 2026-01-01'])

    def test_the_top_title_is_dropped(self):
        sections = parse_changelog(SAMPLE)
        self.assertNotIn('Changelog', [h for h, _ in sections])

    def test_bold_and_code_marks_are_stripped(self):
        first = parse_changelog(SAMPLE)[0][1]
        self.assertIn("• A bold change with a code bit.", first)

    def test_a_wrapped_bullet_is_rejoined(self):
        first = parse_changelog(SAMPLE)[0][1]
        self.assertIn("• A bullet wrapped over two lines.", first)

    def test_an_empty_changelog_still_yields_a_section(self):
        sections = parse_changelog("# Changelog\n")
        self.assertTrue(sections)


class TestLoadedSections(unittest.TestCase):
    def test_the_real_changelog_loads_with_the_latest_first(self):
        self.assertTrue(CHANGELOG_SECTIONS)
        # The newest entry heads the file, so it heads the sections.
        self.assertTrue(CHANGELOG_SECTIONS[0][0].startswith("1.68.1"))


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class TestWindow(unittest.TestCase):
    def setUp(self):
        import customtkinter as ctk
        self.root = ctk.CTk()
        self.root.withdraw()

    def tearDown(self):
        from gantt_app.help.changelog import ChangelogWindow
        if ChangelogWindow._open_window is not None:
            try:
                ChangelogWindow._open_window.destroy()
            except Exception:
                pass
            ChangelogWindow._open_window = None
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_it_opens_titled_changelog(self):
        window = show_changelog(self.root)
        self.root.update_idletasks()
        self.assertEqual(window.title(), "Changelog")

    def test_opening_twice_raises_the_same_window(self):
        first = show_changelog(self.root)
        second = show_changelog(self.root)
        self.assertIs(first, second)


if __name__ == '__main__':
    unittest.main()
