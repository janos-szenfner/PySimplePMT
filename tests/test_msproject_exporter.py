"""
Tests for the Microsoft Project export: the plan as an MSPDI file.

WHY THIS MODULE EXISTS:
======================
MSPDI hands Project a plan and lets it re-solve the schedule, so an export
that writes only durations and links opens showing dates nobody planned -
every task without a predecessor collapsed onto the project start. The export
therefore pins each piece of work with a Start No Earlier Than constraint, and
most of what is checked here is that pinning: that it is there, that it is on
the date the plan says, and that summary rows are left alone so Project can
compute them.

The rest is the parts of the format that are easy to write plausibly and
wrongly - the schema's element order, lag counted in tenths of a minute, the
weekday numbering that starts at Sunday, and the per-task calendars that are
the one thing MSPDI holds and the GanttProject export cannot.

Nothing here needs a display, and nothing here needs Microsoft Project.
"""

import os
import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

from gantt_app.models import Project, Task
from gantt_app.utils.msproject_exporter import (
    MSPDI_NAMESPACE, export_project_to_msproject, generate_msproject_content,
)
from gantt_app.workdaycalendar import WorkingCalendar

#: Every element in the document sits in the MSPDI namespace, so every find
#: has to say so. Bound once rather than at each call site.
NS = {'ms': MSPDI_NAMESPACE}


def sample_project() -> Project:
    """A plan with a phase, nested work, a lagged link and a milestone."""
    project = Project(name="Tosca Implementation")
    base = datetime(2026, 7, 6)          # a Monday

    project.add_task(Task(id="P1", name="Procurement", task_type="Phase",
                          start_date=base, end_date=base + timedelta(days=16)))
    project.add_task(Task(id="T1", name="Business case", task_type="Task",
                          parent_task_id="P1", start_date=base,
                          end_date=base + timedelta(days=4), progress=50,
                          details="Signed off by the steering group"))
    project.add_task(Task(id="T2", name="Tender", task_type="Task",
                          parent_task_id="P1",
                          start_date=base + timedelta(days=7),
                          end_date=base + timedelta(days=16),
                          dependencies=[{'task_id': "T1", 'dep_type': 'FS',
                                         'hardness': 'Hard', 'lag': 2}]))
    project.add_task(Task(id="M1", name="Contract signed",
                          task_type="Milestone",
                          start_date=base + timedelta(days=21),
                          dependencies=["T2"]))

    project.calendar.holidays.add(datetime(2026, 7, 8).date())
    return project


class MSProjectDocumentTestCase(unittest.TestCase):
    """The shape of the document the exporter writes."""

    def setUp(self):
        """Export the sample plan and parse it back as XML."""
        self.project = sample_project()
        self.root = ET.fromstring(generate_msproject_content(self.project))
        self.tasks = self.root.findall('ms:Tasks/ms:Task', NS)

    def task_by_name(self, name):
        """Find one <Task> element by the name it carries."""
        for element in self.tasks:
            if element.find('ms:Name', NS).text == name:
                return element
        self.fail(f"No task named {name!r} in the exported file")

    def value(self, element, tag):
        """The text of one child element, or None when it is absent."""
        child = element.find(f'ms:{tag}', NS)
        return None if child is None else child.text

    def test_root_is_an_mspdi_project(self):
        """The document is a <Project> in Microsoft's namespace."""
        self.assertEqual(self.root.tag, f'{{{MSPDI_NAMESPACE}}}Project')
        self.assertEqual(self.value(self.root, 'Title'), "Tosca Implementation")

    def test_hierarchy_is_an_outline_rather_than_nesting(self):
        """
        MSPDI keeps every task in one flat list and states the level.

        This is the opposite of the .gan file, where the same hierarchy is
        expressed by nesting the elements.
        """
        levels = [(self.value(task, 'Name'), self.value(task, 'OutlineLevel'),
                   self.value(task, 'WBS')) for task in self.tasks]

        self.assertEqual(levels, [
            ("Procurement", '1', '1'),
            ("Business case", '2', '1.1'),
            ("Tender", '2', '1.2'),
            ("Contract signed", '1', '2'),
        ])

    def test_work_is_pinned_to_the_date_the_plan_says(self):
        """Start No Earlier Than, on the task's own start."""
        task = self.task_by_name("Tender")

        self.assertEqual(self.value(task, 'ConstraintType'), '4')
        self.assertEqual(self.value(task, 'ConstraintDate'),
                         '2026-07-13T08:00:00')

    def test_a_summary_row_carries_no_constraint(self):
        """
        Project computes a summary from its children and refuses one that
        disagrees, so the phase is left As Soon As Possible.
        """
        phase = self.task_by_name("Procurement")

        self.assertEqual(self.value(phase, 'Summary'), '1')
        self.assertEqual(self.value(phase, 'ConstraintType'), '0')
        self.assertIsNone(self.value(phase, 'ConstraintDate'))

    def test_an_earliest_begin_date_wins_over_the_inferred_pin(self):
        """A floor the user typed beats one this export worked out."""
        project = sample_project()
        project.get_task_by_id("T2").earliest_begin = datetime(2026, 7, 10)

        root = ET.fromstring(generate_msproject_content(project))
        tender = [task for task in root.findall('ms:Tasks/ms:Task', NS)
                  if task.find('ms:Name', NS).text == "Tender"][0]

        self.assertEqual(tender.find('ms:ConstraintDate', NS).text,
                         '2026-07-10T08:00:00')

    def test_duration_is_working_hours(self):
        """
        Four working days of eight hours each.

        The task runs Monday to Friday and the Wednesday is a holiday, so it
        holds four days of work rather than five.
        """
        self.assertEqual(self.value(self.task_by_name("Business case"),
                                    'Duration'), 'PT32H0M0S')

    def test_a_milestone_takes_no_time(self):
        """It is a marker: zero duration, and it starts where it finishes."""
        milestone = self.task_by_name("Contract signed")

        self.assertEqual(self.value(milestone, 'Milestone'), '1')
        self.assertEqual(self.value(milestone, 'Duration'), 'PT0H0M0S')
        self.assertEqual(self.value(milestone, 'Start'),
                         self.value(milestone, 'Finish'))

    def test_a_finish_lands_at_the_end_of_its_last_day(self):
        """An end date is inclusive here, so the task runs to 17:00 on it."""
        self.assertEqual(self.value(self.task_by_name("Business case"),
                                    'Finish'), '2026-07-10T17:00:00')

    def test_links_are_held_by_the_successor(self):
        """
        MSPDI stores a link the way Task.dependencies does.

        Unlike the .gan export, nothing is reversed on the way out - the
        successor names what it waits for.
        """
        tender = self.task_by_name("Tender")
        business_case = self.task_by_name("Business case")

        links = tender.findall('ms:PredecessorLink', NS)
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].find('ms:PredecessorUID', NS).text,
                         self.value(business_case, 'UID'))
        self.assertEqual(links[0].find('ms:Type', NS).text, '1')  # Finish-Start

    def test_lag_is_written_in_tenths_of_a_minute(self):
        """
        Two days of lag is 9600 tenths.

        MSPDI counts every span in tenths of a minute whatever LagFormat says
        it should be displayed as, and a file that writes the number of days
        into that field opens showing a lag of two minutes.
        """
        link = self.task_by_name("Tender").find('ms:PredecessorLink', NS)

        self.assertEqual(link.find('ms:LinkLag', NS).text, '9600')
        self.assertEqual(link.find('ms:LagFormat', NS).text, '7')

    def test_element_order_follows_the_schema(self):
        """
        Project rejects a file whose elements are out of sequence.

        CalendarUID really does belong between the constraint's type and its
        date, and the links really do come after every scalar field. Both look
        like mistakes, so both are pinned down here.
        """
        project = sample_project()
        tender = project.get_task_by_id("T2")
        tender.details = "Three bidders shortlisted"
        tender.calendar_id = project.calendars.create("Weekend window").id

        root = ET.fromstring(generate_msproject_content(project))
        element = [task for task in root.findall('ms:Tasks/ms:Task', NS)
                   if task.find('ms:Name', NS).text == "Tender"][0]
        tags = [child.tag.split('}')[1] for child in element]

        self.assertEqual(tags[tags.index('ConstraintType'):
                              tags.index('ConstraintDate') + 1],
                         ['ConstraintType', 'CalendarUID', 'ConstraintDate'])
        self.assertLess(tags.index('Notes'), tags.index('PredecessorLink'))
        self.assertEqual(tags[-1], 'PredecessorLink')

    def test_progress_and_notes_travel(self):
        """Completion and the task's details both have fields of their own."""
        task = self.task_by_name("Business case")

        self.assertEqual(self.value(task, 'PercentComplete'), '50')
        self.assertEqual(self.value(task, 'Notes'),
                         "Signed off by the steering group")

    def test_the_working_week_is_declared_from_sunday(self):
        """
        MSPDI numbers Sunday 1 and Saturday 7, where Python starts at Monday.

        Getting the offset wrong writes a week that works Sunday and rests on
        Monday, which no reader would question and every date would follow.
        """
        weekdays = self.root.findall(
            'ms:Calendars/ms:Calendar/ms:WeekDays/ms:WeekDay', NS)
        week = {day.find('ms:DayType', NS).text:
                day.find('ms:DayWorking', NS).text
                for day in weekdays if day.find('ms:DayType', NS).text != '0'}

        self.assertEqual(week['1'], '0')      # Sunday
        self.assertEqual(week['2'], '1')      # Monday
        self.assertEqual(week['6'], '1')      # Friday
        self.assertEqual(week['7'], '0')      # Saturday

    def test_a_holiday_becomes_a_dated_exception(self):
        """The one-off holiday is a day the calendar does not work."""
        exceptions = [day for day in self.root.findall(
            'ms:Calendars/ms:Calendar/ms:WeekDays/ms:WeekDay', NS)
            if day.find('ms:DayType', NS).text == '0']
        dates = {day.find('ms:TimePeriod/ms:FromDate', NS).text:
                 day.find('ms:DayWorking', NS).text for day in exceptions}

        self.assertEqual(dates.get('2026-07-08T00:00:00'), '0')


class MSProjectCalendarTestCase(unittest.TestCase):
    """The per-task calendars, which are the reason to prefer this format."""

    def setUp(self):
        """A plan where one task is worked at the weekend and nothing else is."""
        self.project = sample_project()
        weekend = self.project.calendars.create(
            "Weekend window", WorkingCalendar(non_working_days={0, 1, 2, 3, 4}))
        self.project.get_task_by_id("T2").calendar_id = weekend.id
        self.root = ET.fromstring(generate_msproject_content(self.project))

    def test_both_calendars_are_written(self):
        """The plan's own, then the named one a task follows."""
        names = [element.find('ms:Name', NS).text for element
                 in self.root.findall('ms:Calendars/ms:Calendar', NS)]

        self.assertEqual(names, ['Standard', 'Weekend window'])

    def test_the_task_points_at_its_own_calendar(self):
        """The task carries the UID of the calendar it is scheduled against."""
        tender = [task for task in self.root.findall('ms:Tasks/ms:Task', NS)
                  if task.find('ms:Name', NS).text == "Tender"][0]
        weekend = [element for element
                   in self.root.findall('ms:Calendars/ms:Calendar', NS)
                   if element.find('ms:Name', NS).text == "Weekend window"][0]

        self.assertEqual(tender.find('ms:CalendarUID', NS).text,
                         weekend.find('ms:UID', NS).text)

    def test_a_task_on_the_plan_calendar_names_nothing(self):
        """Saying nothing is how a task follows the plan's own calendar."""
        business_case = [task for task in self.root.findall('ms:Tasks/ms:Task', NS)
                         if task.find('ms:Name', NS).text == "Business case"][0]

        self.assertIsNone(business_case.find('ms:CalendarUID', NS))

    def test_an_unused_calendar_is_not_written(self):
        """A Calendar nothing points at is noise rather than information."""
        self.project.calendars.create("Nobody uses this")
        root = ET.fromstring(generate_msproject_content(self.project))
        names = [element.find('ms:Name', NS).text for element
                 in root.findall('ms:Calendars/ms:Calendar', NS)]

        self.assertNotIn("Nobody uses this", names)


class MSProjectEdgeCaseTestCase(unittest.TestCase):
    """Plans that are empty, broken, or ask for something the format lacks."""

    def test_an_empty_plan_still_writes_a_file(self):
        """A project with no tasks exports rather than failing."""
        root = ET.fromstring(generate_msproject_content(Project(name="Empty")))

        self.assertEqual(root.findall('ms:Tasks/ms:Task', NS), [])
        self.assertEqual(len(root.findall('ms:Calendars/ms:Calendar', NS)), 1)

    def test_a_link_to_a_missing_task_is_dropped(self):
        """A link naming an id no reader can resolve is not written."""
        project = Project(name="Dangling")
        base = datetime(2026, 7, 6)
        project.add_task(Task(id="T1", name="Work", start_date=base,
                              end_date=base, dependencies=["nowhere"]))

        root = ET.fromstring(generate_msproject_content(project))
        self.assertEqual(root.findall('.//ms:PredecessorLink', NS), [])

    def test_a_six_day_week_states_its_own_length(self):
        """
        A plan working Saturdays has a 2880-minute week.

        Left at Project's usual 2400, every duration a reader converts into
        weeks comes out wrong.
        """
        project = Project(name="Six days",
                          calendar=WorkingCalendar(non_working_days={6}))
        project.add_task(Task(id="T1", name="Work",
                              start_date=datetime(2026, 7, 6),
                              end_date=datetime(2026, 7, 11)))

        root = ET.fromstring(generate_msproject_content(project))
        self.assertEqual(root.find('ms:MinutesPerWeek', NS).text, '2880')

    def test_a_worked_weekend_is_written_as_an_exception(self):
        """
        A Saturday the plan works is a day the calendar gives back.

        This is the one the .gan export cannot say at all, and it is written
        with the working times that make it a real day rather than an empty
        one.
        """
        project = Project(name="Make-up day")
        project.calendar.add_override(datetime(2026, 7, 11).date(),
                                      is_working_day=True, reason="Catch-up")
        project.add_task(Task(id="T1", name="Work",
                              start_date=datetime(2026, 7, 6),
                              end_date=datetime(2026, 7, 11)))

        root = ET.fromstring(generate_msproject_content(project))
        worked = [day for day in root.findall(
            'ms:Calendars/ms:Calendar/ms:WeekDays/ms:WeekDay', NS)
            if day.find('ms:DayType', NS).text == '0'
            and day.find('ms:DayWorking', NS).text == '1']

        self.assertEqual(len(worked), 1)
        self.assertEqual(worked[0].find('ms:TimePeriod/ms:FromDate', NS).text,
                         '2026-07-11T00:00:00')
        self.assertTrue(worked[0].findall('ms:WorkingTimes/ms:WorkingTime', NS))

    def test_export_writes_a_file(self):
        """The file lands on disk and parses."""
        handle, path = tempfile.mkstemp(suffix=".xml")
        os.close(handle)
        try:
            self.assertTrue(export_project_to_msproject(sample_project(), path))
            self.assertEqual(ET.parse(path).getroot().tag,
                             f'{{{MSPDI_NAMESPACE}}}Project')
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_export_reports_failure_rather_than_raising(self):
        """A path that cannot be written returns False."""
        self.assertFalse(export_project_to_msproject(
            sample_project(),
            os.path.join(tempfile.gettempdir(), "no-such\0path.xml")))


if __name__ == '__main__':
    unittest.main()
