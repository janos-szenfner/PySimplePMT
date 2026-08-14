"""
Tests for the dependency reference window and the Help button that opens it.

DEVELOPMENT NOTES:
------------------
The content is checked as data - HELP_SECTIONS - so the coverage assertions
do not depend on a display. Only the window and the button need one, and
those tests skip without it; CI provides one through xvfb.
"""

import unittest
from datetime import datetime, timedelta

from gantt_app.models import Project, Task, DEPENDENCY_TYPE_LABELS
from gantt_app.help.dependencyhelp import HELP_SECTIONS


def all_text():
    """Every heading and paragraph run together."""
    parts = []
    for heading, paragraphs in HELP_SECTIONS:
        parts.append(heading)
        parts.extend(paragraphs)
    return '\n'.join(parts)


class TestHelpContent(unittest.TestCase):
    """The reference covers what the Dependency tab offers."""

    def test_every_type_is_explained(self):
        """
        Each of the four types has a section of its own.

        The tab's Type menu offers all four, so a reader who meets an
        unfamiliar one has somewhere to look it up.
        """
        headings = [heading for heading, _paragraphs in HELP_SECTIONS]

        for label in DEPENDENCY_TYPE_LABELS.values():
            self.assertTrue(
                any(label in heading for heading in headings),
                f"no section explains {label}",
            )

    def test_lag_and_lead_are_explained(self):
        """Lead time is the half of the lag field that needs explaining."""
        text = all_text().lower()

        self.assertIn("lead time", text)
        self.assertIn("negative", text)

    def test_hardness_is_explained(self):
        """Both hardness settings are described."""
        text = all_text()

        self.assertIn("Hard", text)
        self.assertIn("Rubber", text)

    def test_the_scheduling_behaviour_is_explained(self):
        """
        The forward-only rule is described.

        It is the behaviour most likely to look wrong without an
        explanation: gaps survive rescheduling on purpose.
        """
        text = all_text().lower()

        self.assertIn("later", text)
        self.assertIn("gap", text)

    def test_no_external_links_are_shown(self):
        """
        The reference stands on its own.

        It described standard scheduling concepts in this application's own
        terms, so pointing readers at someone else's page added nothing.
        """
        text = all_text()

        self.assertNotIn("http", text)

    def test_every_section_has_content(self):
        """No heading is left with nothing under it."""
        for heading, paragraphs in HELP_SECTIONS:
            self.assertTrue(paragraphs, f"{heading} has no text")
            for paragraph in paragraphs:
                self.assertTrue(paragraph.strip())


def _display_available() -> bool:
    """Whether a usable Tk display is present."""
    try:
        import tkinter
        root = tkinter.Tk()
    except Exception:
        return False
    root.destroy()
    return True


HAVE_DISPLAY = _display_available()


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestHelpWindow(unittest.TestCase):
    """The window itself."""

    def setUp(self):
        """Build a root window."""
        import customtkinter as ctk

        self.root = ctk.CTk()
        self.root.withdraw()

    def tearDown(self):
        """Close any help window, then the root."""
        from gantt_app.help.dependencyhelp import DependencyHelpWindow

        if DependencyHelpWindow._open_window is not None:
            DependencyHelpWindow._open_window.close()
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_it_opens(self):
        """The window builds and shows the reference."""
        from gantt_app.help.dependencyhelp import DependencyHelpWindow

        window = DependencyHelpWindow.show(self.root)

        self.assertTrue(window.winfo_exists())

    def test_it_holds_every_section(self):
        """All the content reaches the body."""
        import tkinter as tk
        from gantt_app.help.dependencyhelp import DependencyHelpWindow

        window = DependencyHelpWindow.show(self.root)
        body = window.text.get('1.0', tk.END)

        for heading, _paragraphs in HELP_SECTIONS:
            self.assertIn(heading, body)

    def test_the_body_is_read_only(self):
        """
        Readable and selectable, but not editable.

        Leaving it editable would let a reader type into the reference.
        """
        import tkinter as tk
        from gantt_app.help.dependencyhelp import DependencyHelpWindow

        window = DependencyHelpWindow.show(self.root)

        self.assertEqual(str(window.text.cget('state')), tk.DISABLED)

    def test_opening_twice_reuses_the_window(self):
        """
        A second click raises the open window rather than stacking another.

        The button sits beside controls people click repeatedly.
        """
        from gantt_app.help.dependencyhelp import DependencyHelpWindow

        first = DependencyHelpWindow.show(self.root)
        second = DependencyHelpWindow.show(self.root)

        self.assertIs(first, second)

    def test_closing_forgets_it(self):
        """A closed window is not handed out again."""
        from gantt_app.help.dependencyhelp import DependencyHelpWindow

        window = DependencyHelpWindow.show(self.root)
        window.close()

        self.assertIsNone(DependencyHelpWindow._open_window)

    def test_it_reopens_after_closing(self):
        """Closing and clicking again gives a fresh window."""
        from gantt_app.help.dependencyhelp import DependencyHelpWindow

        first = DependencyHelpWindow.show(self.root)
        first.close()

        second = DependencyHelpWindow.show(self.root)

        self.assertTrue(second.winfo_exists())
        self.assertIsNot(first, second)


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestDependencyTabHasNoProse(unittest.TestCase):
    """
    The Dependency tab carries controls only.

    DEVELOPMENT NOTES:
    ------------------
    The block of explanatory text that used to sit under the grid took room
    the grid wanted and could still only afford a line per setting.
    """

    def setUp(self):
        """Open an edit dialog over a small project."""
        import customtkinter as ctk
        from gantt_app.views.task_list import EditTaskDialog

        self.root = ctk.CTk()
        self.root.withdraw()

        self.project = Project(name="Test Project")
        base = datetime(2026, 1, 1)
        for index in (1, 2):
            self.project.add_task(Task(
                id=f"00{index}", name=f"Task {index}",
                start_date=base, end_date=base + timedelta(days=3),
            ))

        self.dialog = EditTaskDialog(
            self.root, self.project.tasks[0], self.project,
            on_save=lambda task: None, on_delete=lambda task_id: None,
        )
        self.editor = self.dialog.dependency_editor

    def tearDown(self):
        """Close any help window, then the root."""
        from gantt_app.help.dependencyhelp import DependencyHelpWindow

        if DependencyHelpWindow._open_window is not None:
            DependencyHelpWindow._open_window.close()
        try:
            self.root.destroy()
        except Exception:
            pass

    def _labels(self, widget, found=None):
        """Every label's text, recursively."""
        import customtkinter as ctk

        found = [] if found is None else found
        for child in widget.winfo_children():
            if isinstance(child, ctk.CTkLabel):
                found.append(str(child.cget('text')))
            self._labels(child, found)
        return found

    def _buttons(self, widget, found=None):
        """Every button's text, recursively."""
        import customtkinter as ctk

        found = [] if found is None else found
        for child in widget.winfo_children():
            if isinstance(child, ctk.CTkButton):
                found.append(str(child.cget('text')))
            self._buttons(child, found)
        return found

    def test_only_field_labels_remain(self):
        """Nothing on the tab is a paragraph of explanation."""
        labels = self._labels(self.editor)

        self.assertTrue(labels)
        for text in labels:
            self.assertLess(len(text), 30, f"{text!r} reads like prose")

    def test_the_help_button_is_offered(self):
        """The explanation is a click away."""
        self.assertIn("Help", self._buttons(self.editor))

    def test_the_button_opens_the_window(self):
        """Clicking Help shows the reference."""
        from gantt_app.help.dependencyhelp import DependencyHelpWindow

        self.editor.show_help()

        self.assertIsNotNone(DependencyHelpWindow._open_window)


if __name__ == '__main__':
    unittest.main()
