"""
Tests for the holiday country picker.

WHY THIS MODULE EXISTS:
======================
The dialog's whole job is to hand back a list of country codes, and everything
downstream - which dates are holidays, which tasks move - follows from that
list being right. Building the window is what proves it: a checkbox wired to
the wrong variable, or a Cancel that applies anyway, is invisible to a test
that only imports the module.

DEVELOPMENT NOTES:
------------------
The module skips without a display; CI provides one through xvfb. The dialog
is exercised through its own methods rather than by clicking, which needs no
event loop and tests the same code the buttons call.
"""

import unittest
from datetime import datetime

from gantt_app.models import Project, Task
from gantt_app.workdaycalendar import EU_COUNTRIES, supported_countries


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
class HolidayDialogTestCase(unittest.TestCase):
    """A root window and a way to open the picker over it."""

    def setUp(self):
        """Build the window and collect any error Tk would otherwise eat."""
        import customtkinter as ctk

        self.root = ctk.CTk()
        self.root.withdraw()

        self.callback_errors = []
        self.root.report_callback_exception = (
            lambda *info: self.callback_errors.append(info)
        )

        self.applied = []

    def tearDown(self):
        """Tear the root window down."""
        try:
            self.root.destroy()
        except Exception:
            pass

    def dialog(self, selected=()):
        """The picker, opened on a given selection."""
        from gantt_app.views.holidaydialog import HolidayDialog

        window = HolidayDialog(self.root, selected, self.applied.append)
        window.update_idletasks()
        return window


class TestSearchingTheList(HolidayDialogTestCase):
    """
    Finding one country among a couple of hundred.

    DEVELOPMENT NOTES:
    ------------------
    The boxes are built once and hidden as the search narrows, rather than
    rebuilt: rebuilding would throw away the variables and with them every
    tick made outside the current search.
    """

    def shown(self, window):
        """The codes currently laid out in the list."""
        return [code for code, _name, box in window.rows
                if box.winfo_manager()]

    def test_a_search_narrows_the_list(self):
        """By name."""
        window = self.dialog()

        window.search_var.set("hungar")
        window.update_idletasks()

        self.assertEqual(self.shown(window), ["HU"])

    def test_a_search_matches_the_code_too(self):
        """A reader who knows the code should not have to guess the spelling."""
        window = self.dialog()

        window.search_var.set("hu")
        window.update_idletasks()

        self.assertIn("HU", self.shown(window))

    def test_clearing_the_search_brings_them_all_back(self):
        """Nothing is lost by having searched."""
        window = self.dialog()
        window.search_var.set("hungary")
        window.update_idletasks()

        window.search_var.set("")
        window.update_idletasks()

        self.assertEqual(len(self.shown(window)), len(window.checkboxes))

    def test_a_search_keeps_ticks_made_outside_it(self):
        """
        The selection is not the visible list.

        Rebuilding the boxes on each keystroke would have quietly cleared
        every country the search was not showing.
        """
        window = self.dialog(['US'])

        window.search_var.set("hungary")
        window.update_idletasks()
        window.checkboxes['HU'].set(True)
        window.search_var.set("")
        window.update_idletasks()

        self.assertEqual(set(window.selection()), {"US", "HU"})

    def test_a_search_matching_nothing_shows_nothing(self):
        """And says so in the count rather than looking broken."""
        window = self.dialog()

        window.search_var.set("zzzzz")
        window.update_idletasks()

        self.assertEqual(self.shown(window), [])
        self.assertIn("Showing 0", window.summary_label.cget('text'))


class TestWhatTheDialogOffers(HolidayDialogTestCase):
    """The list of countries itself."""

    def test_every_supported_country_is_listed(self):
        """
        Not just the EU: any country the holidays package knows.

        A plan is not always worked inside the union, and the calendar took
        any ISO code from the day it was written - it was only the picker
        that stopped at 27.
        """
        window = self.dialog()

        self.assertEqual(set(window.checkboxes), set(supported_countries()))
        self.assertGreaterEqual(len(window.checkboxes), 27)

    def test_the_member_states_are_still_among_them(self):
        """Widening the list did not lose the one it started as."""
        window = self.dialog()

        for code in EU_COUNTRIES:
            self.assertIn(code, window.checkboxes)

    def test_the_current_selection_opens_ticked(self):
        """The dialog opens on what the project already observes."""
        window = self.dialog(['HU', 'DE'])

        self.assertEqual(window.selection(), ['DE', 'HU'])

    def test_a_lower_case_code_is_still_recognised(self):
        """A hand-edited project file need not shout."""
        window = self.dialog(['hu'])

        self.assertEqual(window.selection(), ['HU'])

    def test_an_unknown_code_does_not_break_the_dialog(self):
        """A code from a newer file leaves the rest of the list usable."""
        window = self.dialog(['HU', 'ZZ'])

        self.assertEqual(window.selection(), ['HU'])
        self.assertEqual(self.callback_errors, [])


class TestTheBatchButtons(HolidayDialogTestCase):
    """Select All and Clear All."""

    def test_all_ticks_everything_on_show(self):
        """One press instead of a page of them."""
        window = self.dialog()

        window.select_all()

        self.assertEqual(len(window.selection()), len(window.checkboxes))

    def test_all_respects_the_search(self):
        """
        Against a search, All means the countries the search found.

        With a couple of hundred on offer, All against the whole list is a
        press nobody means; against a search for one country it is exactly
        what they mean.
        """
        window = self.dialog()
        window.search_var.set("hungary")
        window.update_idletasks()

        window.select_all()

        self.assertEqual(window.selection(), ["HU"])

    def test_eu_ticks_the_member_states_and_nothing_else(self):
        """The list this dialog used to be, kept as one press."""
        window = self.dialog(['US', 'JP'])

        window.select_eu()

        self.assertEqual(set(window.selection()), set(EU_COUNTRIES))

    def test_clear_unticks_everything(self):
        """Back to weekends alone."""
        window = self.dialog(['HU', 'DE'])

        window.clear_all()

        self.assertEqual(window.selection(), [])

    def test_the_summary_says_what_is_chosen(self):
        """
        The line under the header explains the union rule.

        A dialog listing hundreds of countries has to say what ticking
        several of them means, or the reader is left to guess between "any of
        these" and "all of these".
        """
        window = self.dialog()
        self.assertIn("weekends only", window.summary_label.cget('text'))

        window.select_eu()

        self.assertIn("27", window.summary_label.cget('text'))
        self.assertIn("any of them", window.summary_label.cget('text'))


class TestApplyingAndCancelling(HolidayDialogTestCase):
    """What reaches the project, and what does not."""

    def test_apply_hands_back_the_selection(self):
        """Sorted, so the order does not depend on the click order."""
        window = self.dialog()
        window.checkboxes['IT'].set(True)
        window.checkboxes['FR'].set(True)

        window.apply()

        self.assertEqual(self.applied, [['FR', 'IT']])

    def test_cancel_hands_back_nothing(self):
        """A cancelled dialog changes nothing, ticked boxes included."""
        window = self.dialog(['HU'])
        window.select_all()

        window.cancel()

        self.assertEqual(self.applied, [])

    def test_applying_an_empty_selection_is_a_choice(self):
        """
        Clearing every country has to reach the project.

        Treating "nothing selected" as "nothing to do" would make the Clear
        button impossible to apply - the one case where the user most clearly
        means it.
        """
        window = self.dialog(['HU', 'DE'])
        window.clear_all()

        window.apply()

        self.assertEqual(self.applied, [[]])


class TestTheProjectFollows(HolidayDialogTestCase):
    """The selection, once applied, moves the plan."""

    def test_the_plan_reschedules_onto_the_new_calendar(self):
        """
        End to end: tick a country, and a task spanning Easter moves.

        Ten days of work from Monday 30 March end on the Friday of the second
        week. Good Friday and Easter Monday are not worked in Germany, so the
        same ten days now reach the Tuesday after.
        """
        project = Project(name="EU")
        project.add_task(Task(id="A", name="A",
                              start_date=datetime(2026, 3, 30),
                              end_date=datetime(2026, 4, 10)))
        project.reschedule()

        window = self.dialog(sorted(project.calendar.countries))
        window.checkboxes['DE'].set(True)
        window.apply()

        project.set_holiday_countries(self.applied[0])

        self.assertEqual(project.calendar.countries, {'DE'})
        self.assertEqual(project.working_duration(project.get_task_by_id("A")),
                         10)


if __name__ == '__main__':
    unittest.main()
