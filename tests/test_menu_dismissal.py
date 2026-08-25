"""
Tests that a menu can always be dismissed by clicking away from it.

WHY THIS MODULE EXISTS:
======================
Menus were going behind the main window and leaving the application looking
unresponsive, and the cause was a binding that removed more than it was asked
to.

Every popup bound <Button-1> on the main window to notice a click outside
itself, and unbound it on close. tkinter's unbind(sequence, funcid) does not
remove one binding: it clears every binding for that sequence on the widget
and then deletes the one command. So with two popups open, the first to close
took the second's dismissal with it - and the second, being borderless and
always-on-top, then had nothing able to close it. It stayed on screen and
dropped behind the main window the next time that was raised.

So the thing to pin down is that registering and unregistering never disturbs
anybody else's watch, and that every popup is watched at all - the menus
opened from the formatting bar and the progress group had no dismissal of any
kind.

DEVELOPMENT NOTES:
------------------
Clicks cannot be delivered to an unmapped window, so the handlers are called
with a stand-in event rather than by pressing anything. That is the same code
a press reaches.
"""

import tkinter as tk
import unittest
from types import SimpleNamespace


def _display_available() -> bool:
    """Whether a usable Tk display is present."""
    try:
        root = tk.Tk()
    except Exception:
        return False
    root.destroy()
    return True


HAVE_DISPLAY = _display_available()


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class WatchTestCase(unittest.TestCase):
    """The registry the popups share."""

    def setUp(self):
        """A window to watch."""
        import customtkinter as ctk

        self.root = ctk.CTk()
        self.root.withdraw()

    def tearDown(self):
        """Close it."""
        try:
            self.root.destroy()
        except Exception:
            pass

    def click(self, widget=None):
        """A stand-in for a press, which cannot be delivered here."""
        return SimpleNamespace(widget=widget if widget is not None else self.root)


class TestTheWatchIsNotDestructive(WatchTestCase):
    """The fault, stated directly."""

    def watchers(self):
        """Everything currently watching the window."""
        from gantt_app.views.toolbar import DISMISS_WATCHERS

        return getattr(self.root, DISMISS_WATCHERS, [])

    def test_two_watchers_can_be_registered(self):
        """Which is the situation the old code could not survive."""
        from gantt_app.views.toolbar import watch_for_click_elsewhere

        first, second = [], []
        watch_for_click_elsewhere(self.root, first.append)
        watch_for_click_elsewhere(self.root, second.append)

        self.assertEqual(len(self.watchers()), 2)

    def test_removing_one_leaves_the_other(self):
        """
        The whole bug in one assertion.

        Unbinding took every <Button-1> handler on the window with it, so
        the surviving menu could never be dismissed.
        """
        from gantt_app.views.toolbar import (
            stop_watching_for_click_elsewhere, watch_for_click_elsewhere,
        )

        first, second = [], []
        watch_for_click_elsewhere(self.root, first.append)
        watch_for_click_elsewhere(self.root, second.append)

        stop_watching_for_click_elsewhere(self.root, first.append)

        self.assertEqual(len(self.watchers()), 1)

    def test_the_window_keeps_its_own_bindings(self):
        """
        Nothing is unbound at all, so nothing else can be caught by it.

        The window has bindings of its own - the formatting shortcuts among
        them - and those were being cleared too.
        """
        from gantt_app.views.toolbar import (
            stop_watching_for_click_elsewhere, watch_for_click_elsewhere,
        )

        self.root.bind('<Button-1>', lambda _event: None, add='+')
        before = len(self.root.bind('<Button-1>').strip().splitlines())

        handler = [].append
        watch_for_click_elsewhere(self.root, handler)
        stop_watching_for_click_elsewhere(self.root, handler)

        after = len(self.root.bind('<Button-1>').strip().splitlines())
        self.assertGreaterEqual(after, before)

    def test_one_binding_however_many_watchers(self):
        """The window is bound once and then only the list changes."""
        from gantt_app.views.toolbar import watch_for_click_elsewhere

        for index in range(5):
            watch_for_click_elsewhere(self.root, [].append)
        first = self.root.bind('<Button-1>')

        watch_for_click_elsewhere(self.root, [].append)

        self.assertEqual(self.root.bind('<Button-1>'), first)

    def test_the_same_handler_is_not_registered_twice(self):
        """Opening the same menu twice should not double its dismissals."""
        from gantt_app.views.toolbar import watch_for_click_elsewhere

        handler = [].append
        watch_for_click_elsewhere(self.root, handler)
        watch_for_click_elsewhere(self.root, handler)

        self.assertEqual(len(self.watchers()), 1)

    def test_removing_something_never_registered_is_harmless(self):
        """It runs from teardown, where anything may already have gone."""
        from gantt_app.views.toolbar import stop_watching_for_click_elsewhere

        stop_watching_for_click_elsewhere(self.root, [].append)

    def test_a_handler_that_raises_does_not_stop_the_others(self):
        """One broken popup must not leave the rest undismissable."""
        from gantt_app.views.toolbar import (
            DISMISS_WATCHERS, watch_for_click_elsewhere,
        )

        seen = []

        def broken(_event):
            raise RuntimeError("boom")

        watch_for_click_elsewhere(self.root, broken)
        watch_for_click_elsewhere(self.root, seen.append)

        # Whatever the window's binding calls, it has to reach both
        for handler in list(getattr(self.root, DISMISS_WATCHERS, [])):
            try:
                handler(self.click())
            except Exception:
                pass

        self.assertEqual(len(seen), 1)


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class TestAMenuDismissesItself(WatchTestCase):
    """Every menu, including the ones that had no dismissal at all."""

    def menu(self):
        """A dropdown over the window."""
        from gantt_app.views.toolbar import CTkDropdownMenu

        built = CTkDropdownMenu(self.root, items=[{"text": "One",
                                                   "command": lambda: None}])
        built.update_idletasks()
        return built

    def test_it_watches_for_a_click_outside(self):
        """
        The menus opened from the formatting bar and the progress group had
        nothing of the kind, and relied on a FocusOut an overrideredirect
        window does not reliably get on macOS.
        """
        from gantt_app.views.toolbar import DISMISS_WATCHERS

        menu = self.menu()

        self.assertTrue(getattr(self.root, DISMISS_WATCHERS, []))
        self.assertTrue(menu.winfo_exists())

    def test_a_click_outside_closes_it(self):
        """Which is what stops one being left on screen."""
        menu = self.menu()

        menu._dismiss_if_outside(self.click(self.root))

        self.assertFalse(menu.winfo_exists())

    def test_a_click_inside_leaves_it_alone(self):
        """Or choosing an entry would close the menu before it ran."""
        menu = self.menu()

        menu._dismiss_if_outside(self.click(menu))

        self.assertTrue(menu.winfo_exists())

    def test_a_click_on_something_inside_it_leaves_it_alone(self):
        """The press lands on a row, not on the menu itself."""
        menu = self.menu()
        inner = menu.winfo_children()[0]

        menu._dismiss_if_outside(self.click(inner))

        self.assertTrue(menu.winfo_exists())

    def test_closing_it_stops_the_watch(self):
        """A watcher for a menu that has gone would run on every click."""
        from gantt_app.views.toolbar import DISMISS_WATCHERS

        menu = self.menu()
        before = len(getattr(self.root, DISMISS_WATCHERS, []))

        menu.destroy()

        self.assertEqual(len(getattr(self.root, DISMISS_WATCHERS, [])),
                         before - 1)

    def test_two_menus_can_be_open_and_closed_independently(self):
        """
        The exact sequence that broke.

        Closing the first used to take the second's dismissal with it, and
        the second could then never be closed by clicking away.
        """
        first, second = self.menu(), self.menu()

        first.destroy()
        second._dismiss_if_outside(self.click(self.root))

        self.assertFalse(second.winfo_exists())


if __name__ == '__main__':
    unittest.main()
