"""
Tests for the user guide - the parts that need a display.

WHY THIS MODULE EXISTS:
======================
The guide's coverage, its worked examples re-derived from the scheduler,
the chart's default framing and the calendar strip's layout are all
arithmetic over the document and the model - they live in
tests/features/user_guide.feature with their steps in
tests/test_user_guide_bdd.py.

What is kept here needs a window: the guide window itself, the menu and
buttons that reach it, and help opening over a modal dialog.
"""

import unittest
from unittest import mock


def _shut_down(root) -> None:
    """
    Take a root down, children first, without raising.

    Destroying a root while a Toplevel is still on it leaves Tk running
    ttk::ThemeChanged against an interpreter that has already gone, which
    floods stderr with "can't invoke event" tracebacks.
    """
    try:
        for child in list(root.children.values()):
            try:
                child.destroy()
            except Exception:
                pass
        root.destroy()
    except Exception:
        pass


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
class TestTheGuideWindow(unittest.TestCase):
    """Opening it, and finding things in it."""

    def setUp(self):
        """A root window and a guide over it."""
        import customtkinter as ctk
        from gantt_app.help.userguide import UserGuideWindow

        self.root = ctk.CTk()
        self.root.withdraw()
        self.window = UserGuideWindow(self.root)
        self.window.update_idletasks()

    def tearDown(self):
        """Tear the windows down."""
        from gantt_app.help.userguide import UserGuideWindow

        UserGuideWindow._open_window = None
        try:
            _shut_down(self.root)
        except Exception:
            pass

    def test_the_guide_is_written_into_the_body(self):
        """All of it, not the first section."""
        body = self.window.text.get('1.0', 'end')

        self.assertGreater(len(body), 8000)
        self.assertIn("Milestone", body)

    def test_the_body_cannot_be_typed_in(self):
        """Readable and selectable, but not editable."""
        import tkinter as tk

        self.assertEqual(str(self.window.text.cget('state')), tk.DISABLED)

    def test_searching_finds_and_counts(self):
        """The count is what tells a reader whether to keep pressing Next."""
        found = self.window.search('float')

        self.assertGreater(found, 0)
        self.assertEqual(self.window.search_status.cget('text'),
                         f"1 of {found}")

    def test_searching_ignores_case(self):
        """Nobody types a heading's capitals to find it."""
        self.assertEqual(self.window.search('MILESTONE'),
                         self.window.search('milestone'))

    def test_a_number_can_be_searched_for(self):
        """'any typed text or number' - a duration, a count, a year."""
        self.assertGreater(self.window.search('24/7'), 0)
        self.assertGreater(self.window.search('2026'), 0)

    def test_a_search_is_taken_literally(self):
        """
        So a date or a duration finds itself.

        Read as a pattern, '24/7' and '100%' are not what the reader typed.
        """
        self.assertEqual(self.window.search('nothing.matches.this'), 0)
        self.assertEqual(self.window.search_status.cget('text'), "No matches")

    def test_every_hit_is_highlighted(self):
        """Not only the one being looked at."""
        found = self.window.search('calendar')
        ranges = self.window.text.tag_ranges('match')

        # Two indices - a start and an end - per hit
        self.assertEqual(len(ranges), found * 2)

    def test_next_and_previous_walk_the_hits(self):
        """And wrap, rather than stopping at either end."""
        found = self.window.search('calendar')
        self.assertGreater(found, 2)

        self.window.next_match()
        self.assertEqual(self.window.search_status.cget('text'),
                         f"2 of {found}")

        self.window.previous_match()
        self.window.previous_match()
        self.assertEqual(self.window.search_status.cget('text'),
                         f"{found} of {found}")

    def test_clearing_takes_the_highlighting_off(self):
        """A stale highlight is worse than none."""
        self.window.search('calendar')

        self.window.clear_search()

        self.assertEqual(self.window.text.tag_ranges('match'), ())
        self.assertEqual(self.window.search_status.cget('text'), "")

    def test_only_one_guide_is_ever_open(self):
        """Pressing ? twice raises the one that is up."""
        from gantt_app.help.userguide import UserGuideWindow

        first = UserGuideWindow.show(self.root)
        second = UserGuideWindow.show(self.root)

        self.assertIs(first, second)

    def test_search_is_opt_in_per_window(self):
        """
        A short reference is faster read than searched; a long one is not.

        The dependency reference is a handful of sections and keeps none.
        The guide and the task editor's reference are both long enough to be
        looked things up in, and have it.
        """
        from gantt_app.help.dependencyhelp import DependencyHelpWindow
        from gantt_app.help.editorhelp import EditorHelpWindow
        from gantt_app.help.userguide import UserGuideWindow

        self.assertFalse(DependencyHelpWindow.SEARCHABLE)
        self.assertTrue(EditorHelpWindow.SEARCHABLE)
        self.assertTrue(UserGuideWindow.SEARCHABLE)


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestReachingTheGuide(unittest.TestCase):
    """The two ways in, which have to be the same window."""

    def setUp(self):
        """A toolbar over an empty project."""
        import customtkinter as ctk
        from gantt_app.core.models import Project
        from gantt_app.views.toolbar import Toolbar

        self.root = ctk.CTk()
        self.root.withdraw()
        self.toolbar = Toolbar(self.root, Project(name="P"))
        self.toolbar.update_idletasks()

    def tearDown(self):
        """Tear the windows down."""
        from gantt_app.help.userguide import UserGuideWindow

        if UserGuideWindow._open_window is not None:
            UserGuideWindow._open_window = None
        try:
            _shut_down(self.root)
        except Exception:
            pass

    def test_the_icon_bar_carries_a_question_mark(self):
        """Which is what a reader looks for."""
        self.assertIsNotNone(self.toolbar.icon_toolbar.help_button)
        self.assertEqual(self.toolbar.icon_toolbar.help_button.tooltip, "Help")

    def test_it_is_live_with_no_project_open(self):
        """
        Help withheld until you have a plan is withheld from whoever needs it.

        Everything in ICON_ACTIONS is greyed out without a project, which is
        why the ? is built outside that list.
        """
        self.assertEqual(str(self.toolbar.icon_toolbar.help_button.cget('state')),
                         'normal')

    def test_pressing_it_opens_the_guide(self):
        """The window, by name."""
        from gantt_app.help.userguide import UserGuideWindow

        self.toolbar.icon_toolbar.help_button.invoke()
        self.toolbar.update_idletasks()

        self.assertIsNotNone(UserGuideWindow._open_window)

    def test_the_menu_opens_the_same_window(self):
        """Not a second copy of it."""
        from gantt_app.help.userguide import UserGuideWindow

        self.toolbar.icon_toolbar.help_button.invoke()
        opened = UserGuideWindow._open_window

        self.toolbar.show_help()

        self.assertIs(UserGuideWindow._open_window, opened)


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestTheHelpButtonSitsUnderLog(unittest.TestCase):
    """
    Where the ? is on the icon row.

    Both rows fill the toolbar's width, so lining the two up is a matter of
    matching what each keeps clear of the right edge.
    """

    def test_the_two_are_measured_from_the_same_edge(self):
        """The arithmetic the alignment rests on, without needing a window."""
        from gantt_app.views.toolbar import IconToolbar

        centre_of_help = (IconToolbar.HELP_RIGHT_PAD
                          + IconToolbar.BUTTON_SIZE / 2)

        self.assertEqual(centre_of_help, IconToolbar.LOG_CENTRE_FROM_RIGHT)

    def test_the_question_mark_is_packed_to_the_right(self):
        """Rather than after the day/night control, where it used to be."""
        import customtkinter as ctk
        from gantt_app.core.models import Project
        from gantt_app.views.toolbar import Toolbar

        root = ctk.CTk()
        root.withdraw()
        try:
            toolbar = Toolbar(root, Project(name="P"))
            toolbar.update_idletasks()

            info = toolbar.icon_toolbar.help_button.pack_info()

            self.assertEqual(info['side'], 'right')
        finally:
            root.destroy()


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestHelpOpensOverAModalDialog(unittest.TestCase):
    """
    A help window opened from the task editor has to be usable.

    DEVELOPMENT NOTES:
    ------------------
    A grab is exclusive. The task editor is modal, so it receives every click
    in the application, and a window opened from it is a separate Toplevel
    rather than one of its children - so it got nothing. It drew correctly,
    scrolled nowhere, and no button in it responded. Both Help buttons on the
    editor had been dead since they were added.

    The decision is tested rather than the Tk state, because take_grab defers
    until the window manager has mapped the window - so asserting on
    grab_current() is a race, and a test that sleeps to avoid one is a test
    that fails on a slow machine.
    """

    def setUp(self):
        """A root window to open references over."""
        import customtkinter as ctk

        self.root = ctk.CTk()
        self.root.withdraw()

    def tearDown(self):
        """Tear it down, and forget any window left open."""
        from gantt_app.help.editorhelp import EditorHelpWindow
        from gantt_app.help.userguide import UserGuideWindow

        for cls in (EditorHelpWindow, UserGuideWindow):
            cls._open_window = None
        try:
            _shut_down(self.root)
        except Exception:
            pass

    def open_with_grab_held_by(self, holder):
        """
        Build a reference window, reporting whether it claimed the grab.

        `holder` stands in for whatever grab_current() would return: None
        when nothing is modal, or an object when something is.
        """
        from gantt_app.help.editorhelp import EditorHelpWindow

        with mock.patch('gantt_app.views.modal.take_grab') as claimed, \
             mock.patch.object(EditorHelpWindow, 'grab_current',
                               return_value=holder):
            window = EditorHelpWindow(self.root)
            self.addCleanup(window.close)

        return claimed.called

    def test_it_takes_the_grab_when_something_else_holds_one(self):
        """Or the window opens and nothing in it can be clicked."""
        modal_window = object()

        self.assertTrue(self.open_with_grab_held_by(modal_window))

    def test_it_leaves_the_grab_alone_when_nothing_is_modal(self):
        """
        The guide is meant to be read beside the window it describes.

        Taking the grab whenever a reference opened would lock the whole
        application behind the guide - which is the same bug, pointed the
        other way.
        """
        self.assertFalse(self.open_with_grab_held_by(None))

    def test_it_does_not_take_the_grab_from_itself(self):
        """A window already holding it has nothing to claim."""
        from gantt_app.help.editorhelp import EditorHelpWindow

        with mock.patch('gantt_app.views.modal.take_grab') as claimed:
            window = EditorHelpWindow(self.root)
            self.addCleanup(window.close)
            claimed.reset_mock()

            with mock.patch.object(window, 'grab_current',
                                   return_value=window):
                window._claim_grab_if_needed()

        self.assertFalse(claimed.called)

    def test_every_reference_window_does_this(self):
        """
        All three share the base class, so all three are fixed at once.

        The dependency reference is opened from the same modal editor and had
        the same bug.
        """
        from gantt_app.help.dependencyhelp import DependencyHelpWindow
        from gantt_app.help.editorhelp import EditorHelpWindow
        from gantt_app.help.reference import ReferenceWindow
        from gantt_app.help.userguide import UserGuideWindow

        for cls in (EditorHelpWindow, DependencyHelpWindow, UserGuideWindow):
            self.assertTrue(issubclass(cls, ReferenceWindow), cls.__name__)
            self.assertTrue(hasattr(cls, '_claim_grab_if_needed'),
                            cls.__name__)



if __name__ == '__main__':
    unittest.main()
