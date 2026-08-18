"""
Tests for the named calendars a plan holds, and which one a task follows.

WHY THIS MODULE EXISTS:
======================
The registry's whole job is to answer "which calendar is this task scheduled
on", and everything downstream - where the task starts, how long its bar is,
what the critical path measures - follows from that answer being right. Most
of what is worth pinning down is therefore the resolution rule and its edges:
the task that names nothing, and the task naming a calendar that has since
been deleted.

DEVELOPMENT NOTES:
------------------
Nothing here needs a display. Dates are chosen so the weekday matters and is
named in the comment, because "2026-09-12" tells a later reader nothing on
its own.
"""

import unittest
from datetime import date, datetime

from gantt_app.calendarregistry import (
    CalendarRegistry, NamedCalendar, PROJECT_DEFAULT_LABEL, default_registry,
    describe_week, preset_calendar, slugify,
)
from gantt_app.models import Project, Task
from gantt_app.workdaycalendar import WorkingCalendar


class TestSlugs(unittest.TestCase):
    """Ids are built from names, and have to stay usable."""

    def test_a_name_becomes_a_readable_id(self):
        """So a saved file can be read by a person."""
        self.assertEqual(slugify("Weekend Shift"), "weekend-shift")

    def test_punctuation_collapses(self):
        """Rather than surviving into the id."""
        self.assertEqual(slugify("24/7  Continuous!! Run"),
                         "24-7-continuous-run")

    def test_a_name_with_nothing_usable_still_gives_an_id(self):
        """An empty id would be a calendar nothing could point at."""
        self.assertEqual(slugify("!!!"), "calendar")
        self.assertEqual(slugify(""), "calendar")


class TestTheRegistry(unittest.TestCase):
    """Holding calendars, and handing them back in the order they went in."""

    def setUp(self):
        """A registry with the three presets."""
        self.registry = default_registry()

    def test_the_presets_are_offered(self):
        """A plan that has never opened the dialog still has something."""
        self.assertEqual(self.registry.ids(),
                         ['standard-week', 'weekend-shift', 'continuous'])

    def test_the_default_leads_the_options(self):
        """It is what most tasks follow and what one is put back to."""
        options = self.registry.options()

        self.assertEqual(options[0], (None, PROJECT_DEFAULT_LABEL))
        self.assertEqual(len(options), len(self.registry) + 1)

    def test_order_is_the_order_they_were_added(self):
        """Not whatever a dictionary happened to give back."""
        self.registry.create("Aardvark")

        self.assertEqual(self.registry.ids()[-1], 'aardvark')

    def test_replacing_keeps_its_place(self):
        """Editing one must not move it to the bottom of every dropdown."""
        replacement = NamedCalendar(id='weekend-shift', name='Changed',
                                    calendar=WorkingCalendar())
        self.registry.add(replacement)

        self.assertEqual(self.registry.ids(),
                         ['standard-week', 'weekend-shift', 'continuous'])
        self.assertEqual(self.registry.get('weekend-shift').name, 'Changed')

    def test_two_calendars_of_the_same_name_get_different_ids(self):
        """
        Or the second silently takes every task following the first.

        The name is the user's to repeat; the id is what the tasks point at.
        """
        first = self.registry.create("Site Visit")
        second = self.registry.create("Site Visit")

        self.assertNotEqual(first.id, second.id)
        self.assertEqual(len(self.registry), 5)

    def test_renaming_leaves_the_id_alone(self):
        """Every task following it names it by id."""
        self.assertTrue(self.registry.rename('weekend-shift', "Weekend Cover"))

        self.assertEqual(self.registry.get('weekend-shift').name,
                         "Weekend Cover")

    def test_removing_reports_whether_there_was_one(self):
        """So a caller can tell a deletion from a no-op."""
        self.assertTrue(self.registry.remove('continuous'))
        self.assertFalse(self.registry.remove('continuous'))


class TestResolution(unittest.TestCase):
    """The one rule the whole feature rests on."""

    def setUp(self):
        """The presets, and the standard week as the plan's own."""
        self.registry = default_registry()
        self.default = WorkingCalendar()
        self.saturday = date(2026, 9, 12)

    def test_a_named_calendar_is_followed(self):
        """A weekend calendar works the Saturday the plan does not."""
        resolved = self.registry.resolve('weekend-shift', self.default)

        self.assertTrue(resolved.is_working_day(self.saturday))

    def test_naming_nothing_follows_the_plan(self):
        """Which is what almost every task does."""
        resolved = self.registry.resolve(None, self.default)

        self.assertIs(resolved, self.default)
        self.assertFalse(resolved.is_working_day(self.saturday))

    def test_naming_a_deleted_calendar_falls_back(self):
        """
        Rather than raising, which is the point of this being a method.

        A calendar can be deleted while tasks still point at it. A plan that
        will not open - or a task with no calendar at all, which would hang
        the day-by-day walks - is a far worse answer than a task quietly back
        on the plan's own week.
        """
        self.registry.remove('weekend-shift')

        resolved = self.registry.resolve('weekend-shift', self.default)

        self.assertIs(resolved, self.default)

    def test_an_empty_registry_resolves_everything_to_the_plan(self):
        """A plan that never named a calendar behaves exactly as before."""
        empty = CalendarRegistry()

        self.assertIs(empty.resolve('anything', self.default), self.default)
        self.assertIs(empty.resolve(None, self.default), self.default)


class TestDescribingAWeek(unittest.TestCase):
    """The summary shown beside a calendar's name."""

    def test_the_standard_week(self):
        """Named, because five day names is not a summary."""
        self.assertEqual(describe_week(WorkingCalendar()), "Mon-Fri")

    def test_the_weekend(self):
        self.assertEqual(
            describe_week(preset_calendar('w', 'W', (5, 6)).calendar),
            "Sat-Sun")

    def test_every_day(self):
        self.assertEqual(
            describe_week(preset_calendar('c', 'C', range(7)).calendar),
            "every day")

    def test_an_unusual_week_is_spelt_out(self):
        """There is no name for it, so the days are named."""
        self.assertEqual(
            describe_week(preset_calendar('x', 'X', (0, 2, 4)).calendar),
            "Mon, Wed, Fri")

    def test_a_week_with_nothing_in_it(self):
        """It should not be reachable, and should still read."""
        self.assertEqual(
            describe_week(WorkingCalendar(non_working_days=range(7))),
            "no days worked")


class TestStorage(unittest.TestCase):
    """A registry has to survive being saved and reopened."""

    def test_a_registry_round_trips(self):
        """Ids, names, order and each calendar's own contents."""
        registry = default_registry()
        registry.get('weekend-shift').calendar.add_override(
            date(2026, 12, 25), False, "Christmas off even here")

        reopened = CalendarRegistry.from_dict(registry.to_dict())

        self.assertEqual(reopened, registry)
        self.assertEqual(reopened.ids(), registry.ids())
        self.assertEqual(
            reopened.get('weekend-shift').calendar.override_for(
                date(2026, 12, 25)).reason,
            "Christmas off even here")

    def test_the_shape_the_feature_was_specified_in_is_accepted(self):
        """
        A dictionary keyed by id, as well as a list.

        A hand-written file is likelier to arrive that way than to be
        rejected for it.
        """
        registry = CalendarRegistry.from_dict({
            'a': {'id': 'a', 'name': 'A', 'calendar': {}},
            'b': {'id': 'b', 'name': 'B', 'calendar': {}},
        })

        self.assertEqual(sorted(registry.ids()), ['a', 'b'])

    def test_one_damaged_calendar_does_not_cost_the_rest(self):
        """A bad entry is dropped with a line in the log, not raised."""
        registry = CalendarRegistry.from_dict([
            {'id': 'kept', 'name': 'Kept', 'calendar': {}},
            'not a dictionary',
            {'name': 'no id at all'},
        ])

        self.assertEqual(registry.ids(), ['kept'])

    def test_nothing_saved_gives_an_empty_registry(self):
        """Rather than raising on a plan that predates the feature."""
        self.assertEqual(len(CalendarRegistry.from_dict(None)), 0)


class TestATaskFollowsItsOwnCalendar(unittest.TestCase):
    """The point of all of it: one strand of work on a different week."""

    def build(self):
        """Three tasks starting on the same Thursday, on three calendars."""
        project = Project(name="Mixed")
        start = datetime(2026, 9, 10)           # a Thursday
        for identifier, name, calendar_id in (
                ("t1", "Frontend Work", None),
                ("t2", "Server Migration", "weekend-shift"),
                ("t3", "Load Test", "continuous")):
            project.add_task(Task(id=identifier, name=name, start_date=start,
                                  end_date=start, duration=2,
                                  calendar_id=calendar_id))
        project.reschedule()
        return project

    def test_the_plan_s_own_calendar_skips_the_weekend(self):
        """Two days from a Thursday reach the Friday."""
        project = self.build()
        task = project.get_task_by_id("t1")

        self.assertEqual(task.start_date.date(), date(2026, 9, 10))
        self.assertEqual(task.end_date.date(), date(2026, 9, 11))

    def test_a_weekend_task_starts_on_the_saturday(self):
        """
        Its start rolls forward to a day it can actually begin on.

        A Thursday is not a working day on a weekend-only calendar, so the
        task cannot start there - the same rule that moves an ordinary task
        off a Saturday, read on a different week.
        """
        project = self.build()
        task = project.get_task_by_id("t2")

        self.assertEqual(task.start_date.date(), date(2026, 9, 12))
        self.assertEqual(task.end_date.date(), date(2026, 9, 13))

    def test_a_continuous_task_runs_straight_through(self):
        """Nothing is skipped, so two days are two days."""
        project = self.build()
        task = project.get_task_by_id("t3")

        self.assertEqual(task.start_date.date(), date(2026, 9, 10))
        self.assertEqual(task.end_date.date(), date(2026, 9, 11))

    def test_each_task_keeps_the_work_it_holds(self):
        """Three calendars, three sets of dates, the same two days each."""
        project = self.build()

        for task in project.tasks:
            self.assertEqual(project.working_duration(task), 2, task.name)

    def test_a_task_naming_a_deleted_calendar_is_scheduled_anyway(self):
        """
        Back on the plan's own week, rather than not at all.

        It lands on the Monday, not back on the Thursday it was first given:
        rescheduling rolls a start forward off a day nobody works and never
        pulls one backwards, which is the same rule an ordinary task follows.
        """
        project = self.build()
        task = project.get_task_by_id("t2")
        self.assertEqual(task.start_date.date(), date(2026, 9, 12))

        project.calendars.remove('weekend-shift')
        project.reschedule()

        self.assertEqual(task.start_date.date(), date(2026, 9, 14))
        self.assertEqual(task.end_date.date(), date(2026, 9, 15))

    def test_the_calendar_a_task_follows_survives_saving(self):
        """Both the id on the task and the calendar it names."""
        project = self.build()

        reopened = Project.from_dict(project.to_dict())

        self.assertEqual(reopened.get_task_by_id("t2").calendar_id,
                         "weekend-shift")
        self.assertEqual([task.end_date for task in reopened.tasks],
                         [task.end_date for task in project.tasks])


class TestEditingANamedCalendar(unittest.TestCase):
    """Changing a calendar moves the tasks that follow it, and only those."""

    def test_the_work_is_held_and_the_finish_moves(self):
        """
        The reason set_calendars goes through apply_calendar.

        Adding Friday to a weekend calendar should pull its task in by a day,
        not hand it a third day of effort.
        """
        project = Project(name="Edit")
        start = datetime(2026, 9, 10)
        project.add_task(Task(id="t1", name="Migration", start_date=start,
                              end_date=start, duration=3,
                              calendar_id="weekend-shift"))
        project.reschedule()
        task = project.get_task_by_id("t1")
        self.assertEqual(task.end_date.date(), date(2026, 9, 19))

        widened = default_registry()
        widened.add(preset_calendar('weekend-shift', 'Weekend + Friday',
                                    (4, 5, 6)))
        project.set_calendars(widened)

        # The start stays where it is - a Saturday is still worked - and the
        # third day is now the Friday rather than the Saturday a week later.
        self.assertEqual(project.working_duration(task), 3)
        self.assertEqual(task.start_date.date(), date(2026, 9, 12))
        self.assertEqual(task.end_date.date(), date(2026, 9, 18))

    def test_tasks_on_other_calendars_are_left_alone(self):
        """Editing one calendar is not editing the plan."""
        project = Project(name="Edit")
        start = datetime(2026, 9, 10)
        project.add_task(Task(id="t1", name="Ordinary", start_date=start,
                              end_date=start, duration=3))
        project.reschedule()
        before = project.get_task_by_id("t1").end_date

        widened = default_registry()
        widened.add(preset_calendar('weekend-shift', 'Weekend + Friday',
                                    (4, 5, 6)))
        project.set_calendars(widened)

        self.assertEqual(project.get_task_by_id("t1").end_date, before)

    def test_changing_the_plan_s_week_leaves_a_named_task_alone(self):
        """
        A task on its own calendar does not follow the plan's.

        apply_calendar rebuilt every task on whatever calendar it was handed,
        which put the weekend task back on the plan's week the first time
        anybody touched the holiday settings.
        """
        project = Project(name="Edit")
        start = datetime(2026, 9, 10)
        project.add_task(Task(id="t1", name="Migration", start_date=start,
                              end_date=start, duration=2,
                              calendar_id="weekend-shift"))
        project.reschedule()
        before = project.get_task_by_id("t1")
        self.assertEqual(before.start_date.date(), date(2026, 9, 12))

        project.set_working_week({6})           # the plan goes six-day

        self.assertEqual(project.get_task_by_id("t1").start_date.date(),
                         date(2026, 9, 12))

    def test_an_override_on_a_named_calendar_is_honoured(self):
        """The whole of WorkingCalendar comes along, not just the week."""
        project = Project(name="Edit")
        registry = default_registry()
        registry.get('weekend-shift').calendar.add_override(
            date(2026, 9, 12), False, "Site closed")
        project.calendars = registry

        start = datetime(2026, 9, 10)
        project.add_task(Task(id="t1", name="Migration", start_date=start,
                              end_date=start, duration=1,
                              calendar_id="weekend-shift"))
        project.reschedule()

        self.assertEqual(project.get_task_by_id("t1").start_date.date(),
                         date(2026, 9, 13))


class TestWhichPlansGetThePresets(unittest.TestCase):
    """
    Seeded, but never invented for a file that did not have them.

    DEVELOPMENT NOTES:
    ------------------
    The presets used to be forced onto every plan including old ones, because
    without them the dropdown never appeared and there was no way to make a
    calendar. Calendar Settings can now add one, so an old file is left
    exactly as its author saved it.
    """

    def legacy(self, **extra):
        """A project dictionary, by default without a calendars key at all."""
        data = {'name': 'Old', 'tasks': [], 'start_date': None,
                'end_date': None}
        data.update(extra)
        return data

    def test_a_new_project_is_seeded(self):
        """So the feature is there to be found."""
        self.assertEqual(Project(name="New").calendars.ids(),
                         ['standard-week', 'weekend-shift', 'continuous'])

    def test_a_plan_written_before_calendars_gets_none(self):
        """Three calendars in a file nobody added them to is worse."""
        self.assertEqual(Project.from_dict(self.legacy()).calendars.ids(), [])

    def test_a_deliberately_emptied_registry_stays_empty(self):
        """Deleting them all has to survive a save."""
        self.assertEqual(
            Project.from_dict(self.legacy(calendars=[])).calendars.ids(), [])

    def test_a_seeded_project_round_trips_unchanged(self):
        """The seeding happens once, not on every open."""
        project = Project(name="New")
        project.calendars.remove('continuous')

        reopened = Project.from_dict(project.to_dict())

        self.assertEqual(reopened.calendars.ids(),
                         ['standard-week', 'weekend-shift'])


class TestLagIsCountedOnThePlansCalendar(unittest.TestCase):
    """
    One number, one meaning, wherever it is typed.

    DEVELOPMENT NOTES:
    ------------------
    Counted on the successor's week, the same lag of 2 was two days for an
    ordinary task, two for a 24/7 run, and eight calendar days for a
    weekend-only shift - which is not a wait anybody asked for.
    """

    def plan_with_lag(self, calendar_id):
        """A Friday finish, a lag of two, and a successor on some calendar."""
        project = Project(name="Lag")
        project.add_task(Task(id="a", name="A",
                              start_date=datetime(2026, 9, 9),
                              end_date=datetime(2026, 9, 11)))   # to a Friday
        follower = Task(id="b", name="B", start_date=datetime(2026, 9, 14),
                        end_date=datetime(2026, 9, 14), duration=1,
                        calendar_id=calendar_id)
        follower.add_dependency("a", "FS", "Hard", lag=2)
        project.add_task(follower)
        project.reschedule()
        return project.get_task_by_id("b")

    def test_the_wait_is_the_same_length_on_every_calendar(self):
        """The Wednesday, twice; only the third can it not work."""
        self.assertEqual(self.plan_with_lag(None).start_date.date(),
                         date(2026, 9, 16))
        self.assertEqual(self.plan_with_lag("continuous").start_date.date(),
                         date(2026, 9, 16))

    def test_the_successor_still_starts_where_it_can_work(self):
        """
        The wait is held steady; where it lands is the successor's own.

        A weekend crew cannot begin on the Wednesday the lag reaches, so it
        starts on the Saturday after it - the calendar placing the task, not
        lengthening the wait.
        """
        self.assertEqual(self.plan_with_lag("weekend-shift").start_date.date(),
                         date(2026, 9, 19))


if __name__ == '__main__':
    unittest.main()
