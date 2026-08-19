"""
Tests for the GAN export: the plan as a GanttProject file.

WHY THIS MODULE EXISTS:
======================
GanttProject never stores an end date. It stores a start and a duration in
working days, and replays the calendar in the file to work out where a task
finishes - so an export can be entirely well-formed, open without complaint,
and show a plan finishing on the wrong day. The dates are what a reader acts
on, so most of what is checked here is a round trip: export the plan, read it
back through the importer that replays the calendar, and compare the dates
against the plan that went in.

The rest is the two things the format is easy to get backwards - which end of
a dependency the <depend> element hangs off, and that sub-tasks nest inside
their parent rather than naming it.

Nothing here needs a display.
"""

import os
import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

from gantt_app.models import Project, Task
from gantt_app.utils.gan_exporter import (
    export_project_to_gan, generate_gan_content,
)
from gantt_app.utils.gan_importer import import_gan_file
from gantt_app.workdaycalendar import WorkingCalendar


def sample_project() -> Project:
    """A plan with a phase, nested work, a link, a milestone and a holiday."""
    project = Project(name="Tosca Implementation")
    base = datetime(2026, 7, 6)          # a Monday

    phase = Task(id="P1", name="Procurement", task_type="Phase",
                 start_date=base, end_date=base + timedelta(days=16))
    project.add_task(phase)

    project.add_task(Task(id="T1", name="Business case", task_type="Task",
                          parent_task_id="P1", start_date=base,
                          end_date=base + timedelta(days=4), progress=50,
                          details="Signed off by the steering group"))
    project.add_task(Task(id="T2", name="Tender", task_type="Task",
                          parent_task_id="P1",
                          start_date=base + timedelta(days=7),
                          end_date=base + timedelta(days=16),
                          dependencies=["T1"]))
    project.add_task(Task(id="M1", name="Contract signed",
                          task_type="Milestone",
                          start_date=base + timedelta(days=21),
                          dependencies=["T2"]))

    project.calendar.holidays.add(datetime(2026, 7, 8).date())
    project.calendar.recurring_holidays.add((12, 25))
    return project


class GanDocumentTestCase(unittest.TestCase):
    """The shape of the document the exporter writes."""

    def setUp(self):
        """Export the sample plan and parse it back as XML."""
        self.project = sample_project()
        self.root = ET.fromstring(generate_gan_content(self.project))

    def task_by_name(self, name):
        """Find one <task> element anywhere in the outline."""
        for element in self.root.iter('task'):
            if element.get('name') == name:
                return element
        self.fail(f"No task named {name!r} in the exported file")

    def test_root_is_a_gantt_project(self):
        """The document is a <project> carrying the plan's name."""
        self.assertEqual(self.root.tag, 'project')
        self.assertEqual(self.root.get('name'), "Tosca Implementation")

    def test_subtasks_nest_inside_their_parent(self):
        """Hierarchy is nesting in this format, not a parent reference."""
        phase = self.task_by_name("Procurement")
        nested = [child.get('name') for child in phase.findall('task')]

        self.assertEqual(nested, ["Business case", "Tender"])
        self.assertIsNone(phase.get('parent'))

    def test_dependency_hangs_off_the_predecessor(self):
        """
        <depend> is written on the task that comes first.

        The element names the successor, which is the reverse of the way
        Task.dependencies holds the same edge.
        """
        first = self.task_by_name("Business case")
        second = self.task_by_name("Tender")

        depends = first.findall('depend')
        self.assertEqual(len(depends), 1)
        self.assertEqual(depends[0].get('id'), second.get('id'))
        self.assertEqual(depends[0].get('type'), '2')       # Finish-Start
        self.assertEqual(depends[0].get('hardness'), 'Strong')

        # And the successor carries nothing about the link it is the far end
        # of: the milestone at the end of the chain has no <depend> at all
        self.assertEqual(self.task_by_name("Contract signed").findall('depend'),
                         [])

    def test_milestone_is_written_both_ways(self):
        """A milestone is a meeting of zero duration."""
        milestone = self.task_by_name("Contract signed")

        self.assertEqual(milestone.get('meeting'), 'true')
        self.assertEqual(milestone.get('duration'), '0')

    def test_duration_is_counted_in_working_days(self):
        """
        Five calendar days over a holiday are four working days.

        The task runs Monday to Friday and the Wednesday is a holiday, so a
        reader replaying the duration has to be told four rather than five or
        it will finish the task on the Thursday.
        """
        self.assertEqual(self.task_by_name("Business case").get('duration'), '4')

    def test_progress_and_notes_travel(self):
        """Completion is an attribute; the details are a <notes> child."""
        task = self.task_by_name("Business case")

        self.assertEqual(task.get('complete'), '50')
        self.assertEqual(task.find('notes').text,
                         "Signed off by the steering group")

    def test_working_week_is_declared(self):
        """<default-week> marks the weekend off and the rest worked."""
        week = self.root.find('.//default-week')

        self.assertEqual(week.get('mon'), '0')
        self.assertEqual(week.get('sat'), '1')
        self.assertEqual(week.get('sun'), '1')

    def test_recurring_holiday_keeps_its_empty_year(self):
        """A holiday with no year means every year, which is what it is."""
        entries = [element for element in self.root.findall('calendars/date')
                   if element.get('month') == '12' and element.get('date') == '25']

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].get('year'), '')

    def test_dated_holiday_is_written_with_its_year(self):
        """A one-off holiday is pinned to the year it falls in."""
        entries = [element for element in self.root.findall('calendars/date')
                   if element.get('year') == '2026'
                   and element.get('month') == '7'
                   and element.get('date') == '8']

        self.assertEqual(len(entries), 1)

    def test_ids_are_integers(self):
        """
        The format identifies a task by a number, and this application by a
        string, so every task is written as its outline position.
        """
        ids = [element.get('id') for element in self.root.iter('task')]

        self.assertEqual(ids, ['1', '2', '3', '4'])


class GanRoundTripTestCase(unittest.TestCase):
    """What comes back when the exported file is read in again."""

    def setUp(self):
        """Export the sample plan to a temporary file and import it back."""
        self.project = sample_project()
        handle, self.path = tempfile.mkstemp(suffix=".gan")
        os.close(handle)
        self.assertTrue(export_project_to_gan(self.project, self.path))
        self.imported = import_gan_file(self.path)

    def tearDown(self):
        """Remove the file."""
        if os.path.exists(self.path):
            os.unlink(self.path)

    def test_every_task_survives(self):
        """Nothing is lost, and the outline order is kept."""
        self.assertEqual([task.name for task in self.imported.tasks],
                         [task.name for task in self.project.tasks])

    def test_the_dates_are_the_dates(self):
        """
        The point of the whole exercise.

        The file holds durations rather than end dates, so this is the test
        that says the duration written and the calendar written agree with
        each other and with the plan they came from.
        """
        by_name = {task.name: task for task in self.imported.tasks}

        for original in self.project.tasks:
            returned = by_name[original.name]
            self.assertEqual(returned.start_date.date(),
                             original.start_date.date(), original.name)
            if original.end_date is None:
                self.assertIsNone(returned.end_date, original.name)
            else:
                self.assertEqual(returned.end_date.date(),
                                 original.end_date.date(), original.name)

    def test_the_calendar_survives(self):
        """The weekend and both kinds of holiday come back."""
        calendar = self.imported.calendar

        self.assertEqual(calendar.non_working_days, {5, 6})
        self.assertIn(datetime(2026, 7, 8).date(), calendar.holidays)
        self.assertIn((12, 25), calendar.recurring_holidays)

    def test_links_come_back_the_right_way_round(self):
        """A round trip through the reversal leaves the edge as it started."""
        by_name = {task.name: task for task in self.imported.tasks}
        numbers = {task.id: name for name, task in by_name.items()}

        tender = by_name["Tender"]
        self.assertEqual([numbers[d.task_id] for d in tender.dependencies],
                         ["Business case"])
        self.assertEqual([d.dep_type for d in tender.dependencies], ["FS"])

    def test_hierarchy_survives(self):
        """The work still sits under the phase it was written inside."""
        by_name = {task.name: task for task in self.imported.tasks}
        phase = by_name["Procurement"]

        self.assertEqual(by_name["Business case"].parent_task_id, phase.id)
        self.assertEqual(by_name["Tender"].parent_task_id, phase.id)
        self.assertIsNone(phase.parent_task_id)


class GanEdgeCaseTestCase(unittest.TestCase):
    """Plans that are empty, broken, or ask for something the format lacks."""

    def test_an_empty_plan_still_writes_a_file(self):
        """A project with no tasks exports rather than failing."""
        root = ET.fromstring(generate_gan_content(Project(name="Nothing yet")))

        self.assertEqual(root.get('name'), "Nothing yet")
        self.assertEqual(list(root.find('tasks').iter('task')), [])

    def test_a_link_to_a_missing_task_is_dropped(self):
        """
        A <depend> naming an id no reader can resolve costs the whole file.

        GanttProject refuses to open one, so the edge is dropped and logged
        rather than written.
        """
        project = Project(name="Dangling")
        base = datetime(2026, 7, 6)
        project.add_task(Task(id="T1", name="Work", start_date=base,
                              end_date=base, dependencies=["nowhere"]))

        root = ET.fromstring(generate_gan_content(project))
        self.assertEqual(list(root.iter('depend')), [])

    def test_a_six_day_week_is_written_as_one(self):
        """A plan that works Saturdays says so, and its durations follow."""
        project = Project(name="Six days",
                          calendar=WorkingCalendar(non_working_days={6}))
        base = datetime(2026, 7, 6)
        project.add_task(Task(id="T1", name="Work", start_date=base,
                              end_date=base + timedelta(days=6)))

        root = ET.fromstring(generate_gan_content(project))
        week = root.find('.//default-week')

        self.assertEqual(week.get('sat'), '0')
        self.assertEqual(week.get('sun'), '1')
        # Monday to the following Sunday is seven days, six of them worked
        self.assertEqual(root.find('.//task').get('duration'), '6')

    def test_a_task_with_no_end_date_lasts_a_day(self):
        """A day is the shortest anything that is not a milestone can be."""
        project = Project(name="Open ended")
        project.add_task(Task(id="T1", name="Work",
                              start_date=datetime(2026, 7, 6), end_date=None))

        root = ET.fromstring(generate_gan_content(project))
        self.assertEqual(root.find('.//task').get('duration'), '1')

    def test_export_reports_failure_rather_than_raising(self):
        """A path that cannot be written returns False."""
        project = sample_project()

        self.assertFalse(export_project_to_gan(
            project, os.path.join(tempfile.gettempdir(), "no-such\0path.gan")))


if __name__ == '__main__':
    unittest.main()
