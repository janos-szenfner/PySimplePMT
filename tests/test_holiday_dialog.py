"""
Tests for the EU holiday country picker.

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
from gantt_app.workdaycalendar import EU_COUNTRIES


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
        from gantt_app.views.holidaydialog import EUHolidayDialog

        window = EUHolidayDialog(self.root, selected, self.applied.append)
        window.update_idletasks()
        return window


class TestWhatTheDialogOffers(HolidayDialogTestCase):
    """The list of countries itself."""

    def test_every_member_state_is_listed(self):
        """All 27, and nothing else."""
        window = self.dialog()

        self.assertEqual(set(window.checkboxes), set(EU_COUNTRIES))
        self.assertEqual(len(window.checkboxes), 27)

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

    def test_all_ticks_everything(self):
        """One press instead of 27."""
        window = self.dialog()

        window.select_all()

        self.assertEqual(len(window.selection()), 27)

    def test_clear_unticks_everything(self):
        """Back to weekends alone."""
        window = self.dialog(['HU', 'DE'])

        window.clear_all()

        self.assertEqual(window.selection(), [])

    def test_the_summary_says_what_is_chosen(self):
        """
        The line under the header explains the union rule.

        A dialog listing 27 countries has to say what ticking several of them
        means, or the reader is left to guess between "any of these" and "all
        of these".
        """
        window = self.dialog()
        self.assertIn("weekends only", window.summary_label.cget('text'))

        window.select_all()

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
