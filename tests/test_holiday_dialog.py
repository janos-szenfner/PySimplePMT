"""
Tests for the calendar settings dialog: countries, and dates ruled by hand.

WHY THIS MODULE EXISTS:
======================
The dialog's whole job is to hand back a list of country codes and a list of
date rulings, and everything downstream - which dates are holidays, which
tasks move - follows from those lists being right. Building the window is what
proves it: a checkbox wired to the wrong variable, a delete button that closes
over the wrong date, or a Cancel that applies anyway, is invisible to a test
that only imports the module.

DEVELOPMENT NOTES:
------------------
The module skips without a display; CI provides one through xvfb. The dialog
is exercised through its own methods rather than by clicking, which needs no
event loop and tests the same code the buttons call.
"""

import unittest
from datetime import date, datetime
from unittest import mock

from gantt_app.models import Project, Task
from gantt_app.workdaycalendar import (
    DateOverride, EU_COUNTRIES, supported_countries,
)


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
        self.applied_overrides = []
        self.applied_weeks = []
        self.applied_calendars = []
        self.finished = []

    def tearDown(self):
        """Tear the root window down."""
        try:
            self.root.destroy()
        except Exception:
            pass

    def dialog(self, selected=(), overrides=(), non_working_days=None,
               registry=None):
        """The dialog, opened on a given selection, rulings, week and set."""
        from gantt_app.views.holidaydialog import CalendarSettingsDialog

        window = CalendarSettingsDialog(
            self.root, selected, self.applied.append,
            overrides, self.applied_overrides.append,
            non_working_days, self.applied_weeks.append,
            lambda: self.finished.append(True),
            registry, self.applied_calendars.append)
        window.update_idletasks()
        return window

    def fill_override(self, window, day, kind=None, reason=""):
        """Type one ruling into the add form, as a user would."""
        window.override_date_entry.entry.delete(0, 'end')
        window.override_date_entry.entry.insert(0, day)
        window.override_type_var.set(kind or window.WORKING_LABEL)
        window.override_reason_entry.delete(0, 'end')
        window.override_reason_entry.insert(0, reason)


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
        """The codes currently laid out in the list, regions included."""
        return [code for code, _haystack, box, _indent in window._all_rows()
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

        countries = [code for code in self.shown(window) if '-' not in code]
        self.assertEqual(len(countries), len(supported_countries()))

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


class TestRegionsAndStates(HolidayDialogTestCase):
    """
    Holidays below the national level.

    WHY THESE EXIST:
    ================
    Bavaria keeps three public holidays the rest of Germany works through, so
    a plan scheduled against Germany as a whole quietly puts work on days half
    the team is off - which is the entire reason this application observes
    holidays at all.

    There are around a thousand regions across the seventy countries that
    have them, so they are not all on show: a thousand check boxes is a
    dialog that takes seconds to open. They appear when they are searched for
    and when they are already selected.
    """

    def shown(self, window):
        """The codes currently laid out, regions included."""
        return [code for code, _haystack, box, _indent in window._all_rows()
                if box.winfo_manager()]

    def test_regions_are_not_on_show_by_default(self):
        """The list opens as a list of countries."""
        window = self.dialog()

        self.assertEqual([c for c in self.shown(window) if '-' in c], [])

    def test_searching_a_country_brings_out_its_regions(self):
        """Which is what makes them findable without a page of expanders."""
        window = self.dialog()

        window.search_var.set("germany")
        window.update_idletasks()

        shown = self.shown(window)
        self.assertIn("DE", shown)
        self.assertIn("DE-BY", shown)

    def test_a_region_can_be_found_by_its_own_name(self):
        """Someone who wants Bavaria should be able to type Bavaria."""
        window = self.dialog()

        window.search_var.set("bayern")
        window.update_idletasks()

        self.assertEqual(self.shown(window), ["DE-BY"])

    def test_a_selected_region_is_shown_without_searching(self):
        """
        A selection is never hidden from the person who made it.

        A plan observing Bavaria that opened on an unticked Germany would
        look as though the setting had been lost.
        """
        window = self.dialog(['DE-BY'])

        self.assertIn("DE-BY", self.shown(window))
        self.assertEqual(window.selection(), ["DE-BY"])

    def test_a_region_survives_being_applied(self):
        """It reaches the project in the form the calendar reads."""
        window = self.dialog()
        window.search_var.set("bayern")
        window.update_idletasks()
        window.checkboxes["DE-BY"].set(True)

        window.apply()

        self.assertEqual(self.applied, [["DE-BY"]])

    def test_the_eu_button_selects_countries_not_regions(self):
        """The union is 27 national calendars."""
        window = self.dialog(['DE-BY'])

        window.select_eu()

        self.assertNotIn("DE-BY", window.selection())
        self.assertIn("DE", window.selection())


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


class TestTheTabs(HolidayDialogTestCase):
    """Both halves of the calendar are reachable from one window."""

    def test_both_tabs_are_offered(self):
        """The countries, and the dates ruled on by hand."""
        window = self.dialog()

        self.assertIsNotNone(window.tabview.tab(window.TAB_HOLIDAYS))
        self.assertIsNotNone(window.tabview.tab(window.TAB_OVERRIDES))

    def test_it_opens_on_the_countries(self):
        """The commoner of the two, and the one the menu entry used to be."""
        window = self.dialog()

        self.assertEqual(window.tabview.get(), window.TAB_HOLIDAYS)

    def test_the_country_list_still_works_beside_the_new_tab(self):
        """Moving it into a tab must not have unwired it."""
        window = self.dialog(['HU'])

        self.assertTrue(window.checkboxes['HU'].get())
        self.assertEqual(window.selection(), ['HU'])


class TestAddingAnOverride(HolidayDialogTestCase):
    """Turning a filled-in form into a ruling."""

    def test_a_saturday_can_be_named_a_working_day(self):
        """The case the tab exists for."""
        window = self.dialog()
        self.fill_override(window, '2026-09-12', window.WORKING_LABEL,
                           'Make-up day')

        self.assertTrue(window.add_override())

        self.assertEqual(window.override_selection(),
                         [DateOverride(date(2026, 9, 12), True, 'Make-up day')])

    def test_a_weekday_can_be_named_a_non_working_day(self):
        """And the other direction, which the type selector chooses."""
        window = self.dialog()
        self.fill_override(window, '2026-09-15', window.NON_WORKING_LABEL,
                           'Team building')

        window.add_override()

        self.assertEqual(window.override_selection(),
                         [DateOverride(date(2026, 9, 15), False,
                                       'Team building')])

    def test_the_reason_is_optional(self):
        """Most rulings do not need explaining to the person making them."""
        window = self.dialog()
        self.fill_override(window, '2026-09-12')

        window.add_override()

        self.assertEqual(window.override_selection()[0].reason, '')

    def test_an_unreadable_date_is_refused_and_said_so(self):
        """
        In the dialog, not a second window.

        A message box over a modal dialog is two things to dismiss for a typo,
        and the second one lands behind the first often enough to look like a
        freeze.
        """
        window = self.dialog()
        self.fill_override(window, 'next Saturday')

        self.assertFalse(window.add_override())

        self.assertEqual(window.override_selection(), [])
        self.assertTrue(window.override_error_label.cget('text'))

    def test_an_empty_date_is_refused(self):
        """Pressing Add on a cleared form should not add anything."""
        window = self.dialog()
        self.fill_override(window, '')

        self.assertFalse(window.add_override())

        self.assertEqual(window.override_selection(), [])

    def test_ruling_on_a_date_twice_replaces_the_first(self):
        """
        Which is how a ruling gets edited.

        The calendar can only hold one per date, so a list that showed two
        would be showing something it could not apply.
        """
        window = self.dialog()
        self.fill_override(window, '2026-09-12', window.WORKING_LABEL, 'First')
        window.add_override()
        self.fill_override(window, '2026-09-12', window.NON_WORKING_LABEL,
                           'Second')
        window.add_override()

        self.assertEqual(window.override_selection(),
                         [DateOverride(date(2026, 9, 12), False, 'Second')])

    def test_the_reason_box_clears_for_the_next_one(self):
        """Or the second ruling silently inherits the first one's note."""
        window = self.dialog()
        self.fill_override(window, '2026-09-12', reason='Make-up day')
        window.add_override()

        self.assertEqual(window.override_reason_entry.get(), '')

    def test_the_rulings_are_listed_in_date_order(self):
        """However they were typed in."""
        window = self.dialog()
        for day in ('2026-09-15', '2026-01-03', '2026-12-25'):
            self.fill_override(window, day)
            window.add_override()

        self.assertEqual([o.override_date.isoformat()
                          for o in window.override_selection()],
                         ['2026-01-03', '2026-09-15', '2026-12-25'])


class TestTheOverrideList(HolidayDialogTestCase):
    """What the table shows, and what its delete button removes."""

    def test_existing_rulings_open_listed(self):
        """A plan carrying rulings shows them, rather than an empty tab."""
        window = self.dialog(overrides=[
            DateOverride(date(2026, 9, 12), True, 'Make-up day')])

        self.assertEqual(window.override_selection(),
                         [DateOverride(date(2026, 9, 12), True, 'Make-up day')])
        self.assertIn(date(2026, 9, 12), window.override_rows)

    def test_a_row_is_drawn_for_each_ruling(self):
        """And torn down again when one goes."""
        window = self.dialog(overrides=[
            DateOverride(date(2026, 9, 12), True),
            DateOverride(date(2026, 9, 15), False),
        ])

        self.assertEqual(len(window.override_rows), 2)

    def test_delete_removes_one_ruling_and_leaves_the_rest(self):
        """
        The lambda in the row closes over its own date.

        A loop variable captured by reference gives every delete button the
        last date in the list, which deletes the wrong row every time but the
        last - and looks right in a one-row list.
        """
        window = self.dialog(overrides=[
            DateOverride(date(2026, 9, 12), True),
            DateOverride(date(2026, 9, 15), False),
            DateOverride(date(2026, 12, 25), True),
        ])

        self.assertTrue(window.remove_override(date(2026, 9, 15)))

        self.assertEqual([o.override_date for o in window.override_selection()],
                         [date(2026, 9, 12), date(2026, 12, 25)])

    def test_deleting_what_is_not_there_is_a_no_op(self):
        """Two presses on the same button must not raise."""
        window = self.dialog()

        self.assertFalse(window.remove_override(date(2026, 9, 12)))

    def test_an_empty_list_says_so(self):
        """Rather than showing an empty box that reads as a broken tab."""
        window = self.dialog()

        self.assertEqual(window.override_rows, {})
        labels = [child.cget('text')
                  for child in window.override_list.winfo_children()
                  if hasattr(child, 'cget')]
        self.assertTrue(any('No overrides' in str(text) for text in labels))


class TestApplyingTheOverrides(HolidayDialogTestCase):
    """What reaches the project, and what does not."""

    def test_apply_hands_back_both_halves(self):
        """The countries and the rulings, from the one press."""
        window = self.dialog()
        window.checkboxes['HU'].set(True)
        self.fill_override(window, '2026-09-12', window.WORKING_LABEL, 'Cover')

        window.add_override()
        window.apply()

        self.assertEqual(self.applied, [['HU']])
        self.assertEqual(self.applied_overrides,
                         [[DateOverride(date(2026, 9, 12), True, 'Cover')]])

    def test_apply_hands_back_the_whole_list_not_the_changes(self):
        """
        A deletion has to reach the project as an absence.

        Handing back only what was added would make a deleted ruling come
        straight back the next time the plan was rescheduled.
        """
        window = self.dialog(overrides=[
            DateOverride(date(2026, 9, 12), True),
            DateOverride(date(2026, 9, 15), False),
        ])
        window.remove_override(date(2026, 9, 12))

        window.apply()

        self.assertEqual(self.applied_overrides,
                         [[DateOverride(date(2026, 9, 15), False)]])

    def test_cancel_hands_back_no_rulings(self):
        """A cancelled dialog leaves the plan's overrides alone."""
        window = self.dialog(overrides=[DateOverride(date(2026, 9, 12), True)])
        window.remove_override(date(2026, 9, 12))

        window.cancel()

        self.assertEqual(self.applied_overrides, [])

    def test_clearing_every_ruling_is_a_choice(self):
        """
        Emptying the list has to reach the project.

        Treating "none left" as "nothing to do" would make the last deletion
        impossible to apply.
        """
        window = self.dialog(overrides=[DateOverride(date(2026, 9, 12), True)])
        window.remove_override(date(2026, 9, 12))

        window.apply()

        self.assertEqual(self.applied_overrides, [[]])


class TestTheProjectFollowsAnOverride(HolidayDialogTestCase):
    """The rulings, once applied, move the plan."""

    def test_a_named_saturday_pulls_a_finish_in(self):
        """
        End to end: name the Saturday, and the task ends a day earlier.

        Two days of work from Friday 11 September end on the Monday. With the
        Saturday named as worked they end on it instead.
        """
        project = Project(name="Make-up")
        project.add_task(Task(id="A", name="A",
                              start_date=datetime(2026, 9, 11),
                              end_date=datetime(2026, 9, 14)))
        project.reschedule()

        window = self.dialog(sorted(project.calendar.countries))
        self.fill_override(window, '2026-09-12', window.WORKING_LABEL,
                           'Make-up day')
        window.add_override()
        window.apply()

        project.set_date_overrides(self.applied_overrides[0])

        task = project.get_task_by_id("A")
        self.assertEqual(task.end_date.date(), date(2026, 9, 12))
        self.assertEqual(project.working_duration(task), 2)


class TestTheWorkingWeekTab(HolidayDialogTestCase):
    """Which weekdays are worked, which used to need a file import."""

    def test_the_boxes_show_the_days_that_are_worked(self):
        """
        Ticked means worked, which is the opposite of what is stored.

        Asking somebody to tick the days they are *off* is the double
        negative that gets set backwards once and disbelieved forever.
        """
        window = self.dialog()

        worked = [index for index, _name in window.WEEKDAYS
                  if window.weekday_boxes[index].get()]

        self.assertEqual(worked, [0, 1, 2, 3, 4])

    def test_it_opens_on_the_plan_s_own_week(self):
        """A plan already on a six-day week shows one."""
        window = self.dialog(non_working_days={6})

        self.assertTrue(window.weekday_boxes[5].get())
        self.assertFalse(window.weekday_boxes[6].get())

    def test_the_selection_is_handed_back_as_non_working_days(self):
        """Inverted on the way out, once, here."""
        window = self.dialog()
        window.weekday_boxes[5].set(True)

        window.apply()

        self.assertEqual(self.applied_weeks, [{6}])

    def test_the_standard_week_button_restores_monday_to_friday(self):
        """However far the boxes had been moved."""
        window = self.dialog(non_working_days={0, 1, 6})

        window.select_standard_week()

        self.assertEqual(window.working_week_selection(), {5, 6})

    def test_the_summary_names_the_standard_week(self):
        """The commonest case is worth saying in words, not five names."""
        window = self.dialog()

        self.assertIn("Monday to Friday",
                      window.week_summary_label.cget('text'))

    def test_the_summary_counts_an_unusual_week(self):
        """And spells the days out where there is no name for it."""
        window = self.dialog()
        window.weekday_boxes[5].set(True)

        text = window.week_summary_label.cget('text')

        self.assertIn("6 days worked", text)
        self.assertIn("Saturday", text)


class TestAnEmptyWeekIsRefused(HolidayDialogTestCase):
    """
    The one thing the dialog will not apply.

    DEVELOPMENT NOTES:
    ------------------
    WorkingCalendar tolerates a week with no working day - it treats every
    day as worked, so a corrupt file cannot hang the day-by-day walks. That
    is damage limitation for bad data. Applying it to a deliberate choice
    would answer "no days" with seven of them, and say so only in the log.
    """

    def test_apply_refuses_and_keeps_the_window_open(self):
        """Closing on a refusal would look like it had been accepted."""
        window = self.dialog()
        for index in range(7):
            window.weekday_boxes[index].set(False)

        self.assertFalse(window.apply())

        self.assertTrue(window.winfo_exists())

    def test_nothing_at_all_is_applied(self):
        """Not the week, and not the other two tabs either."""
        window = self.dialog()
        window.checkboxes['HU'].set(True)
        for index in range(7):
            window.weekday_boxes[index].set(False)

        window.apply()

        self.assertEqual(self.applied, [])
        self.assertEqual(self.applied_overrides, [])
        self.assertEqual(self.applied_weeks, [])
        self.assertEqual(self.finished, [])

    def test_the_week_tab_is_brought_forward(self):
        """The refusal has to be visible beside the boxes that caused it."""
        window = self.dialog()
        window.tabview.set(window.TAB_HOLIDAYS)
        for index in range(7):
            window.weekday_boxes[index].set(False)

        window.apply()

        self.assertEqual(window.tabview.get(), window.TAB_WEEK)

    def test_the_summary_says_why_as_the_last_box_is_unticked(self):
        """Said as it happens, not held back until Apply."""
        window = self.dialog()
        for index in range(7):
            window.weekday_boxes[index].set(False)

        self.assertIn("At least one",
                      window.week_summary_label.cget('text'))

    def test_it_applies_once_a_day_is_put_back(self):
        """The refusal is recoverable without reopening the dialog."""
        window = self.dialog()
        for index in range(7):
            window.weekday_boxes[index].set(False)
        window.apply()

        window.select_standard_week()

        self.assertTrue(window.apply())
        self.assertEqual(self.applied_weeks, [{5, 6}])


class TestEverythingIsAppliedTogether(HolidayDialogTestCase):
    """Three tabs, one Apply, one redraw."""

    def test_all_three_reach_the_caller(self):
        """From the one press."""
        window = self.dialog()
        window.checkboxes['HU'].set(True)
        window.weekday_boxes[5].set(True)
        self.fill_override(window, '2026-09-20', window.NON_WORKING_LABEL)
        window.add_override()

        window.apply()

        self.assertEqual(self.applied, [['HU']])
        self.assertEqual(self.applied_weeks, [{6}])
        self.assertEqual(len(self.applied_overrides[0]), 1)

    def test_the_finish_hook_fires_once_after_them(self):
        """
        Which is where a caller redraws.

        Redrawing inside each callback would draw the chart three times on
        one press, twice of them against a half-applied calendar.
        """
        window = self.dialog()
        window.checkboxes['HU'].set(True)

        window.apply()

        self.assertEqual(self.finished, [True])

    def test_cancel_fires_nothing(self):
        """Including the finish hook."""
        window = self.dialog()
        window.weekday_boxes[5].set(True)

        window.cancel()

        self.assertEqual(self.applied_weeks, [])
        self.assertEqual(self.finished, [])


class TestManagingTheCalendars(HolidayDialogTestCase):
    """Adding, renaming and removing the calendars a task can follow."""

    def setUp(self):
        """A dialog over the three presets."""
        super().setUp()
        from gantt_app.calendarregistry import default_registry

        self.registry = default_registry()

    def named(self, name):
        """Patch the name prompt to answer with a given name."""
        return mock.patch('tkinter.simpledialog.askstring', return_value=name)

    def confirmed(self, answer=True):
        """Patch the delete confirmation."""
        return mock.patch('gantt_app.views.dialogs.askyesno',
                          return_value=answer)

    def test_the_selector_lists_the_default_and_every_calendar(self):
        """The plan's own leads, because it is what most tasks follow."""
        window = self.dialog(registry=self.registry)

        self.assertEqual(list(window.calendar_selector.cget('values')),
                         ['Project Default', 'Standard Week',
                          'Weekend-Only Shift', '24/7 Continuous Run'])

    def test_a_new_calendar_copies_the_one_on_screen(self):
        """
        So "New..." doubles as "duplicate this one".

        Building a second weekend shift differing by one holiday is the case
        that matters, and starting from a bare week means rebuilding it.
        """
        window = self.dialog(registry=self.registry)
        window._on_calendar_selected('Weekend-Only Shift')

        with self.named('Night Shift'):
            created = window.new_calendar()

        self.assertEqual(created, 'night-shift')
        self.assertEqual(
            window.registry.get('night-shift').calendar.non_working_days,
            {0, 1, 2, 3, 4})

    def test_a_cancelled_prompt_adds_nothing(self):
        """Closing the name box is not a calendar."""
        window = self.dialog(registry=self.registry)

        with self.named(None):
            self.assertIsNone(window.new_calendar())

        self.assertEqual(len(window.registry), 3)

    def test_an_empty_name_is_refused(self):
        """A calendar nobody could pick again is not worth making."""
        window = self.dialog(registry=self.registry)

        with self.named('   '):
            self.assertIsNone(window.new_calendar())

        self.assertEqual(len(window.registry), 3)

    def test_renaming_keeps_the_id(self):
        """Every task following it names it by id, not by name."""
        window = self.dialog(registry=self.registry)
        window._on_calendar_selected('Weekend-Only Shift')

        with self.named('Weekend Cover'):
            self.assertTrue(window.rename_calendar())

        self.assertIn('weekend-shift', window.registry)
        self.assertEqual(window.registry.get('weekend-shift').name,
                         'Weekend Cover')
        self.assertIn('Weekend Cover',
                      list(window.calendar_selector.cget('values')))

    def test_deleting_asks_first(self):
        """And does nothing when the answer is no."""
        window = self.dialog(registry=self.registry)
        window._on_calendar_selected('Weekend-Only Shift')

        with self.confirmed(False):
            self.assertFalse(window.delete_calendar())

        self.assertIn('weekend-shift', window.registry)

    def test_deleting_returns_to_the_project_default(self):
        """There is nothing else the tabs could sensibly show."""
        window = self.dialog(registry=self.registry)
        window._on_calendar_selected('Weekend-Only Shift')

        with self.confirmed():
            self.assertTrue(window.delete_calendar())

        self.assertIsNone(window.current_calendar_id)
        self.assertNotIn('weekend-shift', window.registry)

    def test_the_project_default_cannot_be_renamed_or_deleted(self):
        """It is the fallback every task depends on."""
        window = self.dialog(registry=self.registry)

        self.assertEqual(str(window.button_rename.cget('state')), 'disabled')
        self.assertEqual(str(window.button_delete.cget('state')), 'disabled')
        self.assertFalse(window.rename_calendar())
        self.assertFalse(window.delete_calendar())


class TestAnEmptiedRegistryIsNotADeadEnd(HolidayDialogTestCase):
    """
    A plan with no named calendars can still get one.

    DEVELOPMENT NOTES:
    ------------------
    The selector used not to be built at all without calendars to select,
    which meant a plan whose calendars had been deleted - and any plan
    written before they existed - had no way back to the feature at all.
    """

    def test_the_selector_is_built_even_with_nothing_in_it(self):
        """It is what New... hangs off."""
        from gantt_app.calendarregistry import CalendarRegistry

        window = self.dialog(registry=CalendarRegistry())

        self.assertIsNotNone(window.calendar_selector)
        self.assertEqual(list(window.calendar_selector.cget('values')),
                         ['Project Default'])

    def test_a_calendar_can_be_added_from_empty(self):
        """Which is the whole point of it still being there."""
        from gantt_app.calendarregistry import CalendarRegistry

        window = self.dialog(registry=CalendarRegistry())

        with mock.patch('tkinter.simpledialog.askstring',
                        return_value='Night Shift'):
            window.new_calendar()

        self.assertEqual(window.registry.ids(), ['night-shift'])

    def test_the_calendars_reach_the_caller_on_apply(self):
        """Along with everything else, from the one press."""
        from gantt_app.calendarregistry import CalendarRegistry

        window = self.dialog(registry=CalendarRegistry())
        with mock.patch('tkinter.simpledialog.askstring',
                        return_value='Night Shift'):
            window.new_calendar()

        window.apply()

        self.assertEqual([named.id for named in self.applied_calendars[0]],
                         ['night-shift'])


if __name__ == '__main__':
    unittest.main()
