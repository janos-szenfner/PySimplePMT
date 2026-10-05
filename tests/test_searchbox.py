"""
Tests for finding a work item by anything written on it.

WHY THIS MODULE EXISTS:
======================
A search that quietly misses a field is worse than no search: somebody types
a ticket number, sees nothing, and concludes the number is not in the plan.
So most of what is pinned here is coverage - every field a work item carries
has a test saying it can be found by.

The other half is what a search must *not* do. It hides rows; it must not
change the plan. Roll-up, the schedule and the critical path are measured on
every task whether or not the list is showing it.

DEVELOPMENT NOTES:
------------------
The matching itself is pure and lives in tests/features/searchbox.feature
with its steps in tests/test_searchbox_bdd.py. What is kept here is the
widget and the list it filters - they need a display and skip without one.
"""

import unittest


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
class TestTheBoxOnTheToolbar(unittest.TestCase):
    """The widget, and what it reports."""

    def setUp(self):
        """A search box over a recording callback."""
        import customtkinter as ctk
        from gantt_app.views.searchbox import TaskSearchBox

        self.root = ctk.CTk()
        self.root.withdraw()
        self.searched = []
        self.box = TaskSearchBox(self.root, on_search=self.searched.append)
        self.box.update_idletasks()

    def tearDown(self):
        """Tear the window down."""
        try:
            _shut_down(self.root)
        except Exception:
            pass

    def test_typing_is_handed_over(self):
        """Fired at once here rather than waiting out the settle delay."""
        self.box.search_var.set("mockup")
        self.box._fire_now()

        self.assertEqual(self.searched[-1], "mockup")

    def test_it_reports_how_much_is_left(self):
        """
        The safeguard, not decoration.

        A filtered list looks exactly like a short plan to somebody who has
        forgotten the box has text in it.
        """
        self.box.search_var.set("mockup")
        self.box.report(2, 40)

        self.assertEqual(self.box.count_label.cget('text'), "2 of 40")

    def test_an_empty_box_says_nothing_and_offers_nothing(self):
        """No count, and no Clear button to explain away."""
        self.box.report(40, 40)

        self.assertEqual(self.box.count_label.cget('text'), "")
        self.assertFalse(self.box.clear_button.winfo_manager())

    def test_clear_appears_only_while_searching(self):
        """Beside the thing that needs explaining."""
        self.box.search_var.set("mockup")
        self.box.report(2, 40)

        self.assertTrue(self.box.clear_button.winfo_manager())

    def test_destroying_the_box_cancels_a_pending_search(self):
        """
        A settle timer must not outlive the box that scheduled it.

        Typing arms the debounce; tearing the box down before it fires would
        otherwise leave the timer to run _fire_now on a dead widget.
        """
        self.box.search_var.set("mock")
        self.assertIsNotNone(self.box._settle_job)

        self.box.destroy()

        self.assertIsNone(self.box._settle_job)

    def test_clearing_empties_the_box_and_says_so(self):
        """Which puts every row back."""
        self.box.search_var.set("mockup")
        self.box._fire_now()

        self.box.clear()

        self.assertEqual(self.box.needle, "")
        self.assertEqual(self.searched[-1], "")

    def test_typing_is_not_acted_on_per_keystroke(self):
        """
        Each one would rebuild the tree and redraw the chart with it.

        Nine renders while somebody types "milestone" is eight nobody sees.
        """
        for text in ("m", "mi", "mil", "mile"):
            self.box.search_var.set(text)

        self.assertEqual(self.searched, [])


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestTheListAndChartFollow(unittest.TestCase):
    """End to end: what the reader actually sees."""

    def setUp(self):
        """The whole application, over a fake settings file."""
        from unittest import mock
        from gantt_app.views import theme

        saver = mock.patch.object(theme, 'save_mode', return_value=True)
        saver.start()
        self.addCleanup(saver.stop)

        from gantt_app.main import GanttApp
        self.app = GanttApp()
        self.app.update_idletasks()
        self.addCleanup(self._destroy)

    def _destroy(self):
        """Tear the window down."""
        try:
            self.app.destroy()
        except Exception:
            pass

    def test_the_list_narrows_to_the_matches_and_their_ancestors(self):
        """The rows on screen, not the ids in a set."""
        task_list = self.app.task_list
        everything = len(task_list.visible_rows())

        task_list.apply_search("mockup")

        self.assertLess(len(task_list.visible_rows()), everything)

    def test_clearing_puts_every_row_back(self):
        """A search that could not be undone would be a trap."""
        task_list = self.app.task_list
        everything = len(task_list.visible_rows())

        task_list.apply_search("mockup")
        task_list.apply_search("")

        self.assertEqual(len(task_list.visible_rows()), everything)

    def test_the_chart_follows_without_being_told(self):
        """
        It draws from visible_rows, which reads the tree.

        This is why the search touches nothing in the chart at all.
        """
        task_list = self.app.task_list
        task_list.apply_search("mockup")
        self.app.gantt_chart.draw_chart()
        self.app.update_idletasks()

        self.assertEqual(len(self.app.gantt_chart._drawn_rows),
                         len(task_list.visible_rows()))

    def test_the_plan_is_not_touched(self):
        """Hiding a row is not deleting it."""
        before = len(self.app.project.tasks)

        self.app.task_list.apply_search("mockup")

        self.assertEqual(len(self.app.project.tasks), before)


if __name__ == '__main__':
    unittest.main()
