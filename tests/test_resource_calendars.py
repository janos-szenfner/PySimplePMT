"""
Tests for the resource-calendar hierarchy (issue #38).

A task is scheduled where its own calendar and the calendars of the
resources on it agree; "Scheduling ignores resource calendars" on the
Advanced tab is the escape, and it is off by default.
"""
import tkinter as tk
import unittest
from datetime import date, datetime, timedelta

from gantt_app.core.models import Project, Task
from gantt_app.core.resource_model import (
    DaysOffRange, Resource, ResourceType, SchedulePattern,
)

BASE = datetime(2026, 1, 5)          # a Monday


def _display_available() -> bool:
    try:
        root = tk.Tk()
    except Exception:
        return False
    root.destroy()
    return True


HAVE_DISPLAY = _display_available()


def make_resource(**overrides):
    """A standard Monday-Friday resource, tweaked as asked."""
    fields = dict(id="r1", name="Ann", resource_type=ResourceType.NAMED,
                  role_type="Dev")
    fields.update(overrides)
    return Resource(**fields)


class TestResourceWorksOn(unittest.TestCase):
    """Resource.works_on: the resource's own calendar for one date."""

    def test_a_working_weekday_is_worked(self):
        resource = make_resource()
        self.assertTrue(resource.works_on(date(2026, 1, 5)))   # Monday

    def test_an_empty_weekday_is_not(self):
        resource = make_resource()
        self.assertFalse(resource.works_on(date(2026, 1, 10)))  # Saturday

    def test_a_days_off_range_wins_over_the_weekday(self):
        resource = make_resource(
            days_off=[DaysOffRange(date(2026, 1, 7), date(2026, 1, 8))])
        self.assertFalse(resource.works_on(date(2026, 1, 7)))
        self.assertFalse(resource.works_on(date(2026, 1, 8)))
        self.assertTrue(resource.works_on(date(2026, 1, 9)))

    def test_a_datetime_is_taken_by_its_date(self):
        resource = make_resource(
            days_off=[DaysOffRange(date(2026, 1, 7), date(2026, 1, 7))])
        self.assertFalse(resource.works_on(datetime(2026, 1, 7, 15, 30)))


class TestCalendarIntersection(unittest.TestCase):
    """calendar_for crosses the task's calendar with its resources'."""

    def setUp(self):
        self.project = Project(name="T")
        self.task = Task.create_task("A", BASE, BASE + timedelta(days=4))
        self.task.duration = 5
        self.project.add_task(self.task)

    def assign(self, resource):
        self.project.resource_repository.add_resource(resource)
        self.task.resource_assignments = [{"resource_id": resource.id}]

    def test_no_assignments_keeps_the_task_calendar(self):
        calendar = self.project.calendar_for(self.task)
        self.assertTrue(calendar.is_working_day(datetime(2026, 1, 7)))
        self.assertFalse(calendar.is_working_day(datetime(2026, 1, 10)))

    def test_resource_days_off_are_not_worked(self):
        self.assign(make_resource(
            days_off=[DaysOffRange(date(2026, 1, 7), date(2026, 1, 8))]))
        calendar = self.project.calendar_for(self.task)
        self.assertFalse(calendar.is_working_day(datetime(2026, 1, 7)))
        self.assertFalse(calendar.is_working_day(datetime(2026, 1, 8)))
        self.assertTrue(calendar.is_working_day(datetime(2026, 1, 9)))

    def test_the_task_calendar_still_rules(self):
        """Intersection: the project closing a day closes it for everyone."""
        self.assign(make_resource(
            schedule_pattern=SchedulePattern.FULL_WEEK))
        calendar = self.project.calendar_for(self.task)
        # Bob works Saturdays; the project does not.
        self.assertFalse(calendar.is_working_day(datetime(2026, 1, 10)))
        self.assertTrue(calendar.is_working_day(datetime(2026, 1, 6)))

    def test_several_resources_work_in_parallel(self):
        """A day counts when at least one assigned resource can work it."""
        off = make_resource(
            days_off=[DaysOffRange(date(2026, 1, 7), date(2026, 1, 7))])
        other = make_resource(id="r2", name="Bob")
        self.project.resource_repository.add_resource(off)
        self.project.resource_repository.add_resource(other)
        self.task.resource_assignments = [{"resource_id": "r1"},
                                          {"resource_id": "r2"}]
        self.assertTrue(self.project.calendar_for(self.task)
                        .is_working_day(datetime(2026, 1, 7)))

    def test_an_assignment_nobody_has_is_skipped(self):
        self.task.resource_assignments = [{"resource_id": "ghost"}]
        calendar = self.project.calendar_for(self.task)
        self.assertTrue(calendar.is_working_day(datetime(2026, 1, 7)))

    def test_a_resource_that_never_works_is_left_out(self):
        resource = make_resource()
        resource.daily_capacity_hours = {
            day: 0.0 for day in resource.daily_capacity_hours}
        self.assign(resource)
        self.assertTrue(self.project.calendar_for(self.task)
                        .is_working_day(datetime(2026, 1, 7)))

    def test_the_flag_leaves_the_task_calendar_alone(self):
        self.assign(make_resource(
            days_off=[DaysOffRange(date(2026, 1, 7), date(2026, 1, 7))]))
        self.task.ignores_resource_calendars = True
        self.assertTrue(self.project.calendar_for(self.task)
                        .is_working_day(datetime(2026, 1, 7)))


class TestSchedulingAgainstResources(unittest.TestCase):
    """The stretch the issue describes: finish moves when work cannot."""

    def setUp(self):
        self.project = Project(name="T")
        self.project.resource_repository.add_resource(make_resource(
            days_off=[DaysOffRange(date(2026, 1, 7), date(2026, 1, 8))]))

    def test_a_task_stretches_over_the_resource_days_off(self):
        task = Task.create_task("A", BASE, BASE + timedelta(days=4))
        task.duration = 5
        task.resource_assignments = [{"resource_id": "r1"}]
        self.project.add_task(task)
        self.project.apply_schedule()
        # Mon, Tue, [off, off], Fri, [weekend], Mon, Tue
        self.assertEqual(task.start_date, BASE)
        self.assertEqual(task.end_date, datetime(2026, 1, 13))

    def test_the_flag_keeps_the_finish_where_it_was(self):
        task = Task.create_task("A", BASE, BASE + timedelta(days=4))
        task.duration = 5
        task.resource_assignments = [{"resource_id": "r1"}]
        task.ignores_resource_calendars = True
        self.project.add_task(task)
        self.project.apply_schedule()
        self.assertEqual(task.end_date, datetime(2026, 1, 9))

    def test_a_milestone_moves_off_a_day_the_resource_has_off(self):
        milestone = Task.create_milestone("M", datetime(2026, 1, 7))
        milestone.resource_assignments = [{"resource_id": "r1"}]
        self.project.add_task(milestone)
        self.project.apply_schedule()
        self.assertEqual(milestone.start_date, datetime(2026, 1, 9))


class TestTheFieldItself(unittest.TestCase):
    """The flag's default and its place in the saved file."""

    def test_it_is_off_by_default(self):
        task = Task.create_task("A", BASE, BASE + timedelta(days=2))
        self.assertFalse(task.ignores_resource_calendars)

    def test_it_survives_a_round_trip(self):
        task = Task.create_task("A", BASE, BASE + timedelta(days=2))
        task.ignores_resource_calendars = True
        loaded = Task.from_dict(task.to_dict())
        self.assertTrue(loaded.ignores_resource_calendars)


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestTheAdvancedTabCheckbox(unittest.TestCase):
    """The checkbox on the Advanced tab itself."""

    def _tab(self, task):
        import customtkinter as ctk
        from gantt_app.views.advanced_tab import AdvancedTab
        self.root = ctk.CTk()
        self.root.withdraw()
        return AdvancedTab(self.root, task)

    def tearDown(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def test_it_opens_unticked(self):
        task = Task(id="1", name="X", start_date=BASE,
                    end_date=BASE + timedelta(days=3))
        tab = self._tab(task)
        self.assertFalse(tab.ignores_calendars_var.get())

    def test_it_is_disabled_without_a_task_calendar(self):
        task = Task(id="1", name="X", start_date=BASE,
                    end_date=BASE + timedelta(days=3))
        tab = self._tab(task)
        self.assertEqual(
            str(tab.ignores_calendars_check.cget("state")), "disabled")

    def test_it_is_enabled_with_a_task_calendar(self):
        task = Task(id="1", name="X", start_date=BASE,
                    end_date=BASE + timedelta(days=3),
                    calendar_id="cal_x")
        tab = self._tab(task)
        self.assertEqual(
            str(tab.ignores_calendars_check.cget("state")), "normal")

    def test_it_reads_into_the_saved_values(self):
        task = Task(id="1", name="X", start_date=BASE,
                    end_date=BASE + timedelta(days=3),
                    calendar_id="cal_x")
        tab = self._tab(task)
        tab.ignores_calendars_var.set(True)
        self.assertTrue(
            tab.read_values()["ignores_resource_calendars"])

    def test_disabling_it_clears_the_tick(self):
        task = Task(id="1", name="X", start_date=BASE,
                    end_date=BASE + timedelta(days=3),
                    calendar_id="cal_x",
                    ignores_resource_calendars=True)
        tab = self._tab(task)
        self.assertTrue(tab.ignores_calendars_var.get())
        tab.set_ignores_calendars_enabled(False)
        self.assertFalse(tab.ignores_calendars_var.get())


if __name__ == "__main__":
    unittest.main()
