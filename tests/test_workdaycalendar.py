"""
Tests for the working-day calendar and the scheduling rules built on it.

DEVELOPMENT NOTES:
------------------
Two things are being pinned down here, and they are easy to confuse:

  * Working days  - the effort a task holds. Unchanged by a weekend.
  * Calendar days - how far apart its two ends sit. Stretched by one.

Everything below is a statement about one or the other. Nothing here needs a
display. Dates are chosen so the weekday matters and is named in the comment,
because "2026-01-03" tells a later reader nothing on its own.
"""

import unittest
from datetime import date, datetime, timedelta

from unittest import mock

from gantt_app.models import Project, Task
from gantt_app.workdaycalendar import (
    CalendarTask, EU_COUNTRIES, WorkingCalendar, country_holidays,
    default_calendar, holidays_available,
)

HAVE_HOLIDAYS = holidays_available()


class TestWorkingDays(unittest.TestCase):
    """Which days the standard calendar works."""

    def setUp(self):
        """The standard Monday-to-Friday week."""
        self.calendar = WorkingCalendar()

    def test_weekdays_are_worked(self):
        """Monday to Friday are working days."""
        monday = date(2026, 1, 5)
        for offset in range(5):
            self.assertTrue(self.calendar.is_working_day(monday + timedelta(days=offset)))

    def test_the_weekend_is_not(self):
        """Saturday and Sunday are not."""
        saturday = date(2026, 1, 3)
        self.assertFalse(self.calendar.is_working_day(saturday))
        self.assertFalse(self.calendar.is_working_day(saturday + timedelta(days=1)))

    def test_a_datetime_is_read_the_same_way(self):
        """The models hold datetimes, so those have to answer too."""
        self.assertFalse(self.calendar.is_working_day(datetime(2026, 1, 3, 14, 30)))
        self.assertTrue(self.calendar.is_working_day(datetime(2026, 1, 5, 14, 30)))

    def test_a_holiday_is_not_worked(self):
        """A listed date is not a working day whatever weekday it is."""
        calendar = WorkingCalendar(holidays={date(2026, 1, 6)})

        self.assertFalse(calendar.is_working_day(date(2026, 1, 6)))   # a Tuesday
        self.assertTrue(calendar.is_working_day(date(2026, 1, 7)))

    def test_a_recurring_holiday_applies_every_year(self):
        """A fixed-date national holiday need not be listed per year."""
        calendar = WorkingCalendar(recurring_holidays={(3, 15)})

        self.assertFalse(calendar.is_working_day(date(2026, 3, 15)))
        self.assertFalse(calendar.is_working_day(date(2031, 3, 15)))

    def test_a_different_week_can_be_declared(self):
        """A plan working Sunday to Thursday is a plan the calendar allows."""
        calendar = WorkingCalendar(non_working_days={4, 5})   # Fri and Sat off

        self.assertFalse(calendar.is_working_day(date(2026, 1, 2)))   # Friday
        self.assertTrue(calendar.is_working_day(date(2026, 1, 4)))    # Sunday

    def test_a_week_with_no_working_day_does_not_hang(self):
        """
        A calendar working nothing degrades to plain calendar days.

        Every loop in the module looks for the next working day, so a week with
        none would run to the step limit on every date in a redraw. Answering
        "every day" instead is wrong but finite, and it is logged.
        """
        calendar = WorkingCalendar(non_working_days=set(range(7)))

        self.assertTrue(calendar.is_working_day(date(2026, 1, 3)))
        self.assertEqual(calendar.add_working_days(date(2026, 1, 1), 3),
                         date(2026, 1, 3))


class TestStartDateEnforcement(unittest.TestCase):
    """A task cannot start on a day nobody works."""

    def setUp(self):
        """The standard week."""
        self.calendar = WorkingCalendar()

    def test_a_weekend_start_moves_to_the_monday(self):
        """Saturday and Sunday both push forward to the Monday."""
        monday = date(2026, 1, 5)

        self.assertEqual(self.calendar.get_next_working_day(date(2026, 1, 3)), monday)
        self.assertEqual(self.calendar.get_next_working_day(date(2026, 1, 4)), monday)

    def test_a_working_start_is_left_alone(self):
        """Nothing moves a task that already starts on a working day."""
        tuesday = date(2026, 1, 6)

        self.assertEqual(self.calendar.get_next_working_day(tuesday), tuesday)

    def test_it_steps_over_a_holiday_too(self):
        """A Monday holiday pushes the start to the Tuesday."""
        calendar = WorkingCalendar(holidays={date(2026, 1, 5)})

        self.assertEqual(calendar.get_next_working_day(date(2026, 1, 3)),
                         date(2026, 1, 6))

    def test_the_previous_working_day_is_the_mirror(self):
        """Backwards, for a plan that works from its finish date."""
        friday = date(2026, 1, 2)

        self.assertEqual(self.calendar.get_previous_working_day(date(2026, 1, 4)),
                         friday)

    def test_a_datetime_keeps_its_time_of_day(self):
        """Only the date decides; the time is carried through untouched."""
        moved = self.calendar.get_next_working_day(datetime(2026, 1, 3, 9, 15))

        self.assertEqual(moved, datetime(2026, 1, 5, 9, 15))


class TestDurationToDates(unittest.TestCase):
    """Turning a working duration into an inclusive finish date."""

    def setUp(self):
        """The standard week."""
        self.calendar = WorkingCalendar()

    def test_a_span_inside_one_week(self):
        """Five days from a Monday ends on the Friday."""
        self.assertEqual(self.calendar.add_working_days(date(2026, 1, 5), 5),
                         date(2026, 1, 9))

    def test_one_day_ends_where_it_starts(self):
        """A day-long task does not spill onto a second day."""
        monday = date(2026, 1, 5)

        self.assertEqual(self.calendar.add_working_days(monday, 1), monday)

    def test_a_weekend_is_crossed_without_spending_duration(self):
        """
        The task pauses over the weekend and resumes on the Monday.

        This is the rule the whole module exists for: five days from a Thursday
        runs Thursday, Friday, Monday, Tuesday, Wednesday. Adding four calendar
        days instead finished on the Monday, having spent two days of the task
        on a Saturday and a Sunday.
        """
        thursday = date(2026, 1, 1)

        self.assertEqual(self.calendar.add_working_days(thursday, 5),
                         date(2026, 1, 7))          # the following Wednesday

    def test_a_long_task_crosses_several_weekends(self):
        """Twenty days of work from a Monday is four weeks of calendar."""
        self.assertEqual(self.calendar.add_working_days(date(2026, 1, 5), 20),
                         date(2026, 1, 30))

    def test_a_weekend_start_is_pushed_before_counting(self):
        """Three days from a Saturday runs Monday to Wednesday."""
        self.assertEqual(self.calendar.add_working_days(date(2026, 1, 3), 3),
                         date(2026, 1, 7))

    def test_a_holiday_extends_the_finish(self):
        """A holiday inside the span is not worked and not counted."""
        calendar = WorkingCalendar(holidays={date(2026, 1, 7)})

        self.assertEqual(calendar.add_working_days(date(2026, 1, 5), 3),
                         date(2026, 1, 8))

    def test_no_duration_leaves_the_date_alone(self):
        """A milestone takes no time, so it finishes where it starts."""
        monday = date(2026, 1, 5)

        self.assertEqual(self.calendar.add_working_days(monday, 0), monday)

    def test_working_backwards_is_the_mirror(self):
        """The start a finish and a duration imply."""
        self.assertEqual(
            self.calendar.subtract_working_days(date(2026, 1, 7), 5),
            date(2026, 1, 1)
        )


class TestMeasuringASpan(unittest.TestCase):
    """Reading a pair of dates back as effort and as elapsed time."""

    def setUp(self):
        """The standard week."""
        self.calendar = WorkingCalendar()

    def test_working_days_ignore_the_weekend(self):
        """Thursday to the following Wednesday holds five days of work."""
        self.assertEqual(
            self.calendar.working_days_between(date(2026, 1, 1), date(2026, 1, 7)),
            5
        )

    def test_elapsed_days_do_not(self):
        """The same span is seven days of calendar, which is what is drawn."""
        self.assertEqual(
            self.calendar.elapsed_days(date(2026, 1, 1), date(2026, 1, 7)),
            7
        )

    def test_a_span_of_one_day(self):
        """Both measures agree on a single working day."""
        monday = date(2026, 1, 5)

        self.assertEqual(self.calendar.working_days_between(monday, monday), 1)
        self.assertEqual(self.calendar.elapsed_days(monday, monday), 1)

    def test_a_weekend_only_span_holds_no_work(self):
        """A "task" occupying only a Saturday and a Sunday is not work."""
        self.assertEqual(
            self.calendar.working_days_between(date(2026, 1, 3), date(2026, 1, 4)),
            0
        )

    def test_a_backwards_span_holds_no_work(self):
        """An end before the start counts nothing rather than going negative."""
        self.assertEqual(
            self.calendar.working_days_between(date(2026, 1, 7), date(2026, 1, 1)),
            0
        )

    def test_measuring_and_adding_agree(self):
        """
        The two directions are consistent, which is what makes rescheduling
        stable: measuring a span and adding it back lands on the same day, so
        a task settled once does not creep every time the plan is rescheduled.
        """
        start = date(2026, 1, 1)
        for end in (start + timedelta(days=offset) for offset in range(0, 40)):
            worked = self.calendar.working_days_between(start, end)
            if worked == 0:
                continue
            self.assertEqual(
                self.calendar.working_days_between(
                    start, self.calendar.add_working_days(start, worked)),
                worked
            )


class TestCalendarStorage(unittest.TestCase):
    """A calendar survives being saved and loaded."""

    def test_a_round_trip_keeps_every_day(self):
        """The week, the holidays and the recurring ones all come back."""
        calendar = WorkingCalendar(non_working_days={4, 5},
                                   holidays={date(2026, 1, 6)},
                                   recurring_holidays={(3, 15), (8, 20)})

        self.assertEqual(WorkingCalendar.from_dict(calendar.to_dict()), calendar)

    def test_a_missing_calendar_is_the_standard_week(self):
        """A file saved before projects carried one opens Monday to Friday."""
        self.assertEqual(WorkingCalendar.from_dict(None), WorkingCalendar())
        self.assertEqual(WorkingCalendar.from_dict({}), WorkingCalendar())

    def test_a_damaged_calendar_falls_back_rather_than_raising(self):
        """Junk in the file loads as the standard week; opening it matters more."""
        calendar = WorkingCalendar.from_dict({
            'non_working_days': 'weekends',
            'holidays': ['not a date', '2026-01-06'],
            'recurring_holidays': [['March', 15], [8, 20]],
        })

        self.assertEqual(calendar.non_working_days, {5, 6})
        self.assertEqual(calendar.holidays, {date(2026, 1, 6)})
        self.assertEqual(calendar.recurring_holidays, {(8, 20)})

    def test_a_project_carries_its_calendar_through_a_save(self):
        """The plan's own week is part of the plan."""
        project = Project(name="Imported",
                          calendar=WorkingCalendar(holidays={date(2026, 1, 6)}))

        reloaded = Project.from_dict(project.to_dict())

        self.assertEqual(reloaded.calendar, project.calendar)

    def test_a_project_saved_without_one_opens_on_the_standard_week(self):
        """Older files have no calendar block at all."""
        data = Project(name="Old").to_dict()
        del data['calendar']

        self.assertEqual(Project.from_dict(data).calendar, WorkingCalendar())


class TestStandaloneCalendarTask(unittest.TestCase):
    """
    The rules with nothing else attached.

    These are the worked examples from the specification, kept as tests so the
    documented behaviour and the code cannot part company.
    """

    def test_a_task_crossing_a_weekend(self):
        """Five days from Thursday 10 September 2026 ends on the Wednesday."""
        task = CalendarTask(id="T1", name="Backend API", duration_days=5,
                            start_date=date(2026, 9, 10))

        self.assertEqual(task.effective_start_date, date(2026, 9, 10))
        self.assertEqual(task.end_date, date(2026, 9, 16))
        self.assertEqual(task.duration_days, 5)
        self.assertEqual(task.total_elapsed_days, 7)

    def test_a_task_starting_on_a_saturday(self):
        """It begins on the Monday and its three days run to the Wednesday."""
        task = CalendarTask(id="T2", name="Database Migration", duration_days=3,
                            start_date=date(2026, 9, 12))

        self.assertEqual(task.effective_start_date, date(2026, 9, 14))
        self.assertEqual(task.end_date, date(2026, 9, 16))

    def test_it_uses_the_standard_week_unless_given_one(self):
        """A task built without a calendar still knows about weekends."""
        task = CalendarTask(id="T3", name="Anything", duration_days=1,
                            start_date=date(2026, 9, 12))

        self.assertEqual(task.calendar, default_calendar())


class TestTaskDuration(unittest.TestCase):
    """What a Task answers about its own length."""

    def test_a_task_inside_one_week(self):
        """Monday to Friday is five days of work in five days of calendar."""
        task = Task(id="T", name="T", start_date=datetime(2026, 1, 5),
                    end_date=datetime(2026, 1, 9))

        self.assertEqual(task.duration_days, 5)
        self.assertEqual(task.total_elapsed_days, 5)

    def test_a_task_crossing_a_weekend(self):
        """The two measures part company, which is the point of having both."""
        task = Task(id="T", name="T", start_date=datetime(2026, 1, 1),
                    end_date=datetime(2026, 1, 7))

        self.assertEqual(task.duration_days, 5)
        self.assertEqual(task.total_elapsed_days, 7)

    def test_a_task_on_a_weekend_is_still_a_day_long(self):
        """
        A span holding no work reads as one day rather than none.

        Nothing in the application can show a task of nought days sensibly, and
        a start date on a Saturday is what puts a task there.
        Project.enforce_working_calendar moves it off.
        """
        task = Task(id="T", name="T", start_date=datetime(2026, 1, 3),
                    end_date=datetime(2026, 1, 4))

        self.assertEqual(task.duration_days, 1)

    def test_a_milestone_has_no_length(self):
        """A milestone marks a moment."""
        task = Task(id="T", name="T", start_date=datetime(2026, 1, 5),
                    is_milestone=True)

        self.assertEqual(task.duration_days, 0)
        self.assertEqual(task.total_elapsed_days, 0)

    def test_an_effective_start_skips_the_weekend(self):
        """A task placed on a Saturday works from the Monday."""
        task = Task(id="T", name="T", start_date=datetime(2026, 1, 3),
                    end_date=datetime(2026, 1, 9))

        self.assertEqual(task.effective_start_date, datetime(2026, 1, 5))


class TestEnforcingTheCalendar(unittest.TestCase):
    """Project.enforce_working_calendar, on a plan that needs it."""

    def setUp(self):
        """An empty project on the standard week."""
        self.project = Project(name="Enforcement")

    def add(self, task_id, start, end, **kwargs):
        """Add a task and return it."""
        task = Task(id=task_id, name=task_id, start_date=start, end_date=end,
                    **kwargs)
        self.project.add_task(task)
        return task

    def test_a_weekend_start_is_moved_to_the_monday(self):
        """Rule four: a task cannot start on a day nobody works."""
        task = self.add("A", datetime(2026, 1, 3), datetime(2026, 1, 8))

        self.assertTrue(self.project.enforce_working_calendar())
        self.assertEqual(task.start_date, datetime(2026, 1, 5))

    def test_the_working_duration_is_kept_when_the_start_moves(self):
        """
        Moving the start does not cost the task any of its work.

        Saturday to Thursday holds four days of work - Monday to Thursday - so
        starting on the Monday it still holds four, ending on the Thursday.
        """
        task = self.add("A", datetime(2026, 1, 3), datetime(2026, 1, 8))

        self.project.enforce_working_calendar()

        self.assertEqual(task.start_date, datetime(2026, 1, 5))
        self.assertEqual(task.end_date, datetime(2026, 1, 8))
        self.assertEqual(self.project.working_duration(task), 4)

    def test_a_finish_on_a_weekend_is_pulled_back(self):
        """Monday to Sunday holds five days of work, so it ends on the Friday."""
        task = self.add("A", datetime(2026, 1, 5), datetime(2026, 1, 11))

        self.project.enforce_working_calendar()

        self.assertEqual(task.end_date, datetime(2026, 1, 9))
        self.assertEqual(task.duration_days, 5)

    def test_a_stated_duration_is_honoured(self):
        """A task carrying its own duration is stretched to match it."""
        task = self.add("A", datetime(2026, 1, 1), datetime(2026, 1, 2),
                        duration=5)

        self.project.enforce_working_calendar()

        self.assertEqual(task.end_date, datetime(2026, 1, 7))

    def test_a_task_already_on_working_days_is_left_alone(self):
        """Nothing moves, and it says so."""
        self.add("A", datetime(2026, 1, 5), datetime(2026, 1, 9))

        self.assertFalse(self.project.enforce_working_calendar())

    def test_running_it_twice_changes_nothing(self):
        """
        It has to be idempotent: it runs inside the reschedule loop, which
        repeats until nothing moves. A pass that moved a task every time would
        never settle.
        """
        self.add("A", datetime(2026, 1, 3), datetime(2026, 1, 11))

        self.project.enforce_working_calendar()

        self.assertFalse(self.project.enforce_working_calendar())

    def test_a_milestone_moves_off_the_weekend_and_keeps_no_end(self):
        """A milestone is a date, and it has to be a date somebody works."""
        milestone = self.add("M", datetime(2026, 1, 4), None,
                             is_milestone=True)

        self.project.enforce_working_calendar()

        self.assertEqual(milestone.start_date, datetime(2026, 1, 5))
        self.assertIsNone(milestone.end_date)

    def test_a_container_takes_its_dates_from_its_children(self):
        """
        A Phase is not moved directly.

        Its dates are rolled up from the work inside it - which this has
        already put on working days - so touching it here would only fight
        roll_up_summaries.
        """
        phase = self.add("P", datetime(2026, 1, 3), datetime(2026, 1, 11),
                         task_type="Phase")
        self.add("C", datetime(2026, 1, 3), datetime(2026, 1, 9),
                 task_type="Subtask", parent_task_id="P")

        self.project.enforce_working_calendar()

        self.assertEqual(phase.start_date, datetime(2026, 1, 3))

        self.project.reschedule()

        self.assertEqual(phase.start_date, datetime(2026, 1, 5))
        self.assertEqual(phase.end_date, datetime(2026, 1, 9))

    def test_a_holiday_calendar_is_respected(self):
        """The project's own calendar is the one enforced, not the standard week."""
        self.project.calendar = WorkingCalendar(holidays={datetime(2026, 1, 6)})
        task = self.add("A", datetime(2026, 1, 5), datetime(2026, 1, 7),
                        duration=3)

        self.project.enforce_working_calendar()

        self.assertEqual(task.end_date, datetime(2026, 1, 8))


@unittest.skipUnless(HAVE_HOLIDAYS, "needs the holidays package")
class TestCountryHolidays(unittest.TestCase):
    """
    Public holidays, taken from whichever countries the plan observes.

    DEVELOPMENT NOTES:
    ------------------
    The dates asserted here are real national holidays, chosen because they
    exercise the three things a hand-written list gets wrong: one country
    having a holiday another does not, a movable Easter feast, and the union
    across several countries.
    """

    def test_a_fixed_national_holiday_is_not_worked(self):
        """23 October is Hungary's national day, and a Friday in 2026."""
        calendar = WorkingCalendar(countries=["HU"])

        self.assertFalse(calendar.is_working_day(date(2026, 10, 23)))
        # The Thursday before it is an ordinary working day
        self.assertTrue(calendar.is_working_day(date(2026, 10, 22)))

    def test_a_movable_easter_holiday_is_not_worked(self):
        """
        Easter Monday moves every year and is never listed anywhere.

        This is the reason the holidays package is asked rather than a table
        being kept: computing the paschal full moon per country per year is
        not something to reimplement.
        """
        calendar = WorkingCalendar(countries=["DE"])

        self.assertFalse(calendar.is_working_day(date(2026, 4, 6)))
        self.assertFalse(calendar.is_working_day(date(2027, 3, 29)))

    def test_countries_are_merged_as_a_union(self):
        """
        A holiday in any selected country is a holiday for the plan.

        Epiphany is a public holiday in Austria and an ordinary working day in
        Hungary, so a plan worked in both cannot count on it.
        """
        hungary = WorkingCalendar(countries=["HU"])
        both = WorkingCalendar(countries=["HU", "AT"])
        epiphany = date(2026, 1, 6)

        self.assertTrue(hungary.is_working_day(epiphany))
        self.assertFalse(both.is_working_day(epiphany))

    def test_a_holiday_lengthens_a_task_without_lengthening_its_duration(self):
        """
        The rule weekends already follow, applied to holidays.

        Ten days of work from Monday 30 March run to the Friday of the second
        week. In Hungary they reach the Tuesday after it instead: Good Friday
        and Easter Monday fall inside the span and neither is worked.
        """
        plain = WorkingCalendar()
        hungary = WorkingCalendar(countries=["HU"])
        monday = date(2026, 3, 30)

        self.assertEqual(plain.add_working_days(monday, 10), date(2026, 4, 10))
        self.assertEqual(hungary.add_working_days(monday, 10),
                         date(2026, 4, 14))

    def test_a_start_on_a_holiday_moves_to_the_next_working_day(self):
        """
        Start-date enforcement does not care why a day is not worked.

        New Year's Day 2026 is a Thursday, Hungary takes the Friday with it,
        and the weekend follows - so work begins on the Monday.
        """
        calendar = WorkingCalendar(countries=["HU"])

        self.assertEqual(calendar.get_next_working_day(date(2026, 1, 1)),
                         date(2026, 1, 5))

    def test_selecting_no_countries_leaves_weekends_alone(self):
        """Clearing the list is a plan on weekends only."""
        calendar = WorkingCalendar(countries=[])

        self.assertTrue(calendar.is_working_day(date(2026, 10, 23)))
        self.assertEqual(calendar.working_days_between(date(2026, 3, 30),
                                                       date(2026, 4, 10)), 10)

    def test_the_countries_can_be_changed_afterwards(self):
        """Applying a new selection takes effect at once."""
        calendar = WorkingCalendar()
        epiphany = date(2026, 1, 6)
        self.assertTrue(calendar.is_working_day(epiphany))

        calendar.set_countries(["AT"])

        self.assertFalse(calendar.is_working_day(epiphany))

    def test_changing_the_countries_clears_what_was_worked_out(self):
        """
        The cached year is dropped, not reused.

        Holidays are resolved a year at a time and kept, because is_working_day
        runs for every day of every task on every redraw. A cache that survived
        a change of country would answer for the old selection forever.
        """
        calendar = WorkingCalendar(countries=["AT"])
        epiphany = date(2026, 1, 6)
        self.assertFalse(calendar.is_working_day(epiphany))

        calendar.set_countries(["HU"])

        self.assertTrue(calendar.is_working_day(epiphany))

    def test_every_eu_country_resolves(self):
        """All 27 are known to the package; none of them is a typo here."""
        for code in EU_COUNTRIES:
            with self.subTest(country=code):
                self.assertTrue(country_holidays([code], 2026))

    def test_the_selection_survives_a_save(self):
        """The codes are saved, so a plan reopened next year still knows."""
        project = Project(name="EU",
                          calendar=WorkingCalendar(countries=["HU", "DE"]))

        reloaded = Project.from_dict(project.to_dict())

        self.assertEqual(reloaded.calendar.countries, {"HU", "DE"})
        self.assertFalse(reloaded.calendar.is_working_day(date(2026, 4, 6)))

    def test_a_holiday_pushes_a_scheduled_task_out(self):
        """
        The whole point: the plan moves when the calendar does.

        Ten days of work keep being ten days of work. Good Friday and Easter
        Monday appearing inside the task push its finish from the Friday to
        the Tuesday rather than costing it two days of what it holds.
        """
        project = Project(name="EU")
        project.add_task(Task(id="A", name="A",
                              start_date=datetime(2026, 3, 30),
                              end_date=datetime(2026, 4, 10)))

        project.reschedule()
        self.assertEqual(project.get_task_by_id("A").end_date,
                         datetime(2026, 4, 10))

        project.set_holiday_countries(["HU"])

        self.assertEqual(project.get_task_by_id("A").end_date,
                         datetime(2026, 4, 14))
        self.assertEqual(project.working_duration(project.get_task_by_id("A")),
                         10)

    def test_dropping_a_country_pulls_the_plan_back_in(self):
        """The change is undoable by making the opposite change."""
        project = Project(name="EU", calendar=WorkingCalendar(countries=["HU"]))
        project.add_task(Task(id="A", name="A",
                              start_date=datetime(2026, 3, 30),
                              end_date=datetime(2026, 4, 14)))
        project.reschedule()

        project.set_holiday_countries([])

        self.assertEqual(project.get_task_by_id("A").end_date,
                         datetime(2026, 4, 10))
        self.assertEqual(project.working_duration(project.get_task_by_id("A")),
                         10)

    def test_a_milestone_moves_off_a_holiday(self):
        """A date nobody works is not a date to mark something on."""
        project = Project(name="EU")
        project.add_task(Task(id="M", name="M",
                              start_date=datetime(2026, 4, 6),
                              is_milestone=True))

        project.set_holiday_countries(["DE"])

        self.assertEqual(project.get_task_by_id("M").start_date,
                         datetime(2026, 4, 7))
        self.assertIsNone(project.get_task_by_id("M").end_date)


class TestWithoutTheHolidaysPackage(unittest.TestCase):
    """
    The optional dependency being absent costs holidays, not the plan.

    A wrong holiday list is worth less than a project that will not open, so a
    missing package is logged once and the calendar carries on with weekends.
    """

    def test_an_unresolvable_country_is_simply_not_observed(self):
        """Nothing raises, and the weekend rule still applies."""
        calendar = WorkingCalendar(countries=["HU"])

        with mock.patch('gantt_app.workdaycalendar.country_holidays',
                        return_value=set()):
            self.assertTrue(calendar.is_working_day(date(2026, 3, 16)))
            self.assertFalse(calendar.is_working_day(date(2026, 3, 14)))
            self.assertEqual(calendar.add_working_days(date(2026, 3, 9), 10),
                             date(2026, 3, 20))

    def test_an_unknown_country_code_is_skipped(self):
        """One bad code in a saved file costs that country, not the plan."""
        self.assertEqual(country_holidays(["ZZ"], 2026), set())

    def test_the_selection_is_still_saved(self):
        """A plan carrying countries is not silently emptied without them."""
        calendar = WorkingCalendar(countries=["HU", "DE"])

        self.assertEqual(WorkingCalendar.from_dict(calendar.to_dict()).countries,
                         {"HU", "DE"})


if __name__ == '__main__':
    unittest.main()
