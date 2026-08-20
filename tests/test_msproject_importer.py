"""
Tests for the Microsoft Project import: reading an MSPDI file into a plan.

WHY THIS MODULE EXISTS:
======================
This replaced an import that called a function which did not exist, in a
library that had nothing to do with Microsoft Project, behind a check for
whether that library was installed - so it reported "install tasklib" and
returned nothing whether or not tasklib was there. Nothing caught it because
nothing tested the reading of an actual file.

So the centre of this module is a round trip against the exporter: write the
plan out, read it back, and compare every field that decides a date. The rest
covers what a file written by Project itself carries and this application's
own exporter does not - the newer <Exceptions> calendar block, a project
summary row at outline level 0, and an outline that skips a level.

Nothing here needs a display, and nothing here needs Microsoft Project.
"""

import os
import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

from gantt_app.models import Project, Task
from gantt_app.utils.msproject_exporter import export_project_to_msproject
from gantt_app.utils.msproject_importer import (
    import_msproject_file, parse_msproject,
)
from gantt_app.workdaycalendar import WorkingCalendar


def sample_project() -> Project:
    """A plan with a phase, nested work, a lagged link and a milestone."""
    project = Project(name="Tosca Implementation")
    base = datetime(2026, 7, 6)          # a Monday

    project.add_task(Task(id="P1", name="Procurement", task_type="Phase",
                          start_date=base, end_date=base + timedelta(days=16)))
    project.add_task(Task(id="T1", name="Business case", task_type="Task",
                          parent_task_id="P1", start_date=base,
                          end_date=base + timedelta(days=4), progress=50,
                          priority="High",
                          details="Signed off by the steering group"))
    project.add_task(Task(id="T2", name="Tender", task_type="Task",
                          parent_task_id="P1",
                          start_date=base + timedelta(days=7),
                          end_date=base + timedelta(days=16),
                          dependencies=[{'task_id': "T1", 'dep_type': 'SS',
                                         'hardness': 'Hard', 'lag': 2}]))
    project.add_task(Task(id="M1", name="Contract signed",
                          task_type="Milestone",
                          start_date=base + timedelta(days=21),
                          dependencies=["T2"]))

    project.calendar.holidays.add(datetime(2026, 7, 8).date())
    return project


def parse(xml_text: str) -> Project:
    """Read a plan out of an MSPDI document held as text."""
    return parse_msproject(ET.fromstring(xml_text))


class RoundTripTestCase(unittest.TestCase):
    """What comes back when the exporter's own file is read in again."""

    def setUp(self):
        """Export the sample plan to a temporary file and import it back."""
        self.project = sample_project()
        handle, self.path = tempfile.mkstemp(suffix=".xml")
        os.close(handle)
        self.assertTrue(export_project_to_msproject(self.project, self.path))
        self.imported = import_msproject_file(self.path)
        self.assertIsNotNone(self.imported)
        self.by_name = {task.name: task for task in self.imported.tasks}

    def tearDown(self):
        """Remove the file."""
        if os.path.exists(self.path):
            os.unlink(self.path)

    def test_the_plan_keeps_its_name(self):
        """The title travels, without the file name's extension."""
        self.assertEqual(self.imported.name, "Tosca Implementation")

    def test_every_task_survives_in_order(self):
        """Nothing is lost and the outline order is kept."""
        self.assertEqual([task.name for task in self.imported.tasks],
                         [task.name for task in self.project.tasks])

    def test_the_dates_are_the_dates(self):
        """
        The point of the whole exercise.

        A finish is a moment in this format and an inclusive day here, so
        this is the test that says the conversion between them is right in
        both directions.
        """
        for original in self.project.tasks:
            returned = self.by_name[original.name]
            self.assertEqual(returned.start_date.date(),
                             original.start_date.date(), original.name)
            if original.end_date is None:
                self.assertIsNone(returned.end_date, original.name)
            else:
                self.assertEqual(returned.end_date.date(),
                                 original.end_date.date(), original.name)

    def test_hierarchy_survives(self):
        """The outline levels come back as parents."""
        phase = self.by_name["Procurement"]

        self.assertIsNone(phase.parent_task_id)
        self.assertEqual(self.by_name["Business case"].parent_task_id, phase.id)
        self.assertEqual(self.by_name["Tender"].parent_task_id, phase.id)

    def test_the_summary_row_comes_back_as_a_container(self):
        """A Project summary at the top of the outline is a Phase here."""
        self.assertEqual(self.by_name["Procurement"].task_type, 'Phase')
        self.assertEqual(self.by_name["Business case"].task_type, 'Task')

    def test_a_milestone_comes_back_as_a_milestone(self):
        """Zero duration, and no end date to speak of."""
        milestone = self.by_name["Contract signed"]

        self.assertEqual(milestone.task_type, 'Milestone')
        self.assertTrue(milestone.effective_milestone)
        self.assertIsNone(milestone.end_date)

    def test_the_link_keeps_its_type_and_its_lag(self):
        """A Start-Start link with two days of lag is still one."""
        tender = self.by_name["Tender"]
        self.assertEqual(len(tender.dependencies), 1)
        link = tender.dependencies[0]

        self.assertEqual(link.task_id, self.by_name["Business case"].id)
        self.assertEqual(link.dep_type, 'SS')
        self.assertEqual(link.lag, 2)

    def test_progress_notes_and_priority_travel(self):
        """The fields that are not dates come back too."""
        task = self.by_name["Business case"]

        self.assertEqual(task.progress, 50)
        self.assertEqual(task.details, "Signed off by the steering group")
        self.assertEqual(task.priority, "High")

    def test_the_calendar_survives(self):
        """The working week and the holiday both come back."""
        calendar = self.imported.calendar

        self.assertEqual(calendar.non_working_days, {5, 6})
        self.assertIn(datetime(2026, 7, 8).date(), calendar.holidays)

    def test_a_pin_on_the_task_s_own_start_is_not_read_back(self):
        """
        Every piece of work is exported with a Start No Earlier Than on its
        own start date, which says only "stay where you are". Reading that
        back as an Earliest begin would put a floor on every task in a plan
        that had none.
        """
        for task in self.imported.tasks:
            self.assertIsNone(task.earliest_begin, task.name)

    def test_a_real_floor_does_come_back(self):
        """One naming a date other than the start is carrying information."""
        project = sample_project()
        project.get_task_by_id("T2").earliest_begin = datetime(2026, 7, 10)

        handle, path = tempfile.mkstemp(suffix=".xml")
        os.close(handle)
        try:
            export_project_to_msproject(project, path)
            imported = import_msproject_file(path)
        finally:
            os.unlink(path)

        tender = [t for t in imported.tasks if t.name == "Tender"][0]
        self.assertEqual(tender.earliest_begin.date(), datetime(2026, 7, 10).date())


class PerTaskCalendarTestCase(unittest.TestCase):
    """The calendars, which are the reason this format is worth reading."""

    def setUp(self):
        """A plan where one task is worked at the weekend and nothing else is."""
        self.project = sample_project()
        weekend = self.project.calendars.create(
            "Weekend window", WorkingCalendar(non_working_days={0, 1, 2, 3, 4}))
        self.project.get_task_by_id("T2").calendar_id = weekend.id

        handle, self.path = tempfile.mkstemp(suffix=".xml")
        os.close(handle)
        export_project_to_msproject(self.project, self.path)
        self.imported = import_msproject_file(self.path)

    def tearDown(self):
        """Remove the file."""
        if os.path.exists(self.path):
            os.unlink(self.path)

    def test_the_named_calendar_comes_back(self):
        """It lands in the registry under the name it went out with."""
        names = [named.name for named in self.imported.calendars]

        self.assertEqual(names, ["Weekend window"])

    def test_the_task_still_follows_it(self):
        """And the week it describes is the week that went out."""
        tender = [t for t in self.imported.tasks if t.name == "Tender"][0]
        calendar = self.imported.calendar_for(tender)

        self.assertIsNotNone(tender.calendar_id)
        self.assertEqual(calendar.non_working_days, {0, 1, 2, 3, 4})

    def test_a_task_on_the_plan_calendar_names_nothing(self):
        """The base calendar is the plan's own, not a named one."""
        business_case = [t for t in self.imported.tasks
                         if t.name == "Business case"][0]

        self.assertIsNone(business_case.calendar_id)


class FilesProjectItselfWritesTestCase(unittest.TestCase):
    """Shapes this application's own exporter never produces."""

    #: The header every one of these documents needs, and nothing more.
    HEADER = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
              '<Project xmlns="http://schemas.microsoft.com/project">'
              '<Title>Imported</Title><CalendarUID>1</CalendarUID>')

    def document(self, calendars: str, tasks: str) -> str:
        """One MSPDI document from its two interesting halves."""
        return (f"{self.HEADER}<Calendars>{calendars}</Calendars>"
                f"<Tasks>{tasks}</Tasks></Project>")

    def task(self, uid, name, level, start, finish, extra=''):
        """One <Task> element with the fields every task needs."""
        return (f"<Task><UID>{uid}</UID><Name>{name}</Name>"
                f"<OutlineLevel>{level}</OutlineLevel>"
                f"<Start>{start}T08:00:00</Start>"
                f"<Finish>{finish}T17:00:00</Finish>{extra}</Task>")

    def standard_calendar(self, body=''):
        """A Monday-to-Friday calendar, with whatever is passed appended."""
        days = ''.join(
            f"<WeekDay><DayType>{code}</DayType>"
            f"<DayWorking>{'0' if code in (1, 7) else '1'}</DayWorking>"
            "</WeekDay>" for code in range(1, 8))
        return (f"<Calendar><UID>1</UID><Name>Standard</Name>"
                f"<WeekDays>{days}</WeekDays>{body}</Calendar>")

    def test_the_newer_exceptions_block_is_read(self):
        """
        Project itself writes calendar exceptions in an <Exceptions> block.

        This application's exporter writes the older WeekDay form, so nothing
        in the round trip exercises this - and a reader that ignored it would
        import every plan Project wrote with its holidays silently missing.
        """
        exceptions = ("<Exceptions><Exception><DayWorking>0</DayWorking>"
                      "<Name>Company shutdown</Name><TimePeriod>"
                      "<FromDate>2026-12-24T00:00:00</FromDate>"
                      "<ToDate>2026-12-26T23:59:00</ToDate>"
                      "</TimePeriod></Exception></Exceptions>")
        project = parse(self.document(
            self.standard_calendar(exceptions),
            self.task(1, "Work", 1, "2026-07-06", "2026-07-10")))

        for day in (24, 25, 26):
            self.assertIn(datetime(2026, 12, day).date(),
                          project.calendar.holidays)

    def test_a_project_summary_row_is_not_imported_as_work(self):
        """
        Project writes the plan itself as a task at outline level 0.

        Imported as work it would appear as a task spanning everything, at
        the top of a plan that already has that information.
        """
        project = parse(self.document(
            self.standard_calendar(),
            self.task(0, "Tosca Implementation", 0, "2026-07-06", "2026-07-24")
            + self.task(1, "Work", 1, "2026-07-06", "2026-07-10")))

        self.assertEqual([task.name for task in project.tasks], ["Work"])

    def test_a_null_task_is_skipped(self):
        """A row marked IsNull is a gap in the numbering, not a task."""
        project = parse(self.document(
            self.standard_calendar(),
            "<Task><UID>1</UID><IsNull>1</IsNull></Task>"
            + self.task(2, "Work", 1, "2026-07-06", "2026-07-10")))

        self.assertEqual([task.name for task in project.tasks], ["Work"])

    def test_an_outline_that_skips_a_level_still_attaches(self):
        """
        Project does not write one, but tools that generate MSPDI do.

        The task attaches to the deepest row above it rather than being
        dropped, because losing work is the worse of the two answers.
        """
        project = parse(self.document(
            self.standard_calendar(),
            self.task(1, "Phase", 1, "2026-07-06", "2026-07-24",
                      "<Summary>1</Summary>")
            + self.task(2, "Deep", 3, "2026-07-06", "2026-07-10")))

        deep = [task for task in project.tasks if task.name == "Deep"][0]
        phase = [task for task in project.tasks if task.name == "Phase"][0]
        self.assertEqual(deep.parent_task_id, phase.id)

    def test_a_finish_at_midnight_means_the_day_before(self):
        """
        Some writers state a finish as the start of the day after the last.

        Taking its date would add a day of work the plan does not hold.
        """
        project = parse(self.document(
            self.standard_calendar(),
            "<Task><UID>1</UID><Name>Work</Name><OutlineLevel>1</OutlineLevel>"
            "<Start>2026-07-06T08:00:00</Start>"
            "<Finish>2026-07-11T00:00:00</Finish></Task>"))

        self.assertEqual(project.tasks[0].end_date.date(),
                         datetime(2026, 7, 10).date())

    def test_a_file_with_no_calendar_keeps_the_standard_week(self):
        """
        A calendar that never describes its week is not a week with no days.

        Read as one, every day of the plan would count as working and every
        duration would come out short.
        """
        project = parse(self.document(
            "<Calendar><UID>1</UID><Name>Standard</Name></Calendar>",
            self.task(1, "Work", 1, "2026-07-06", "2026-07-10")))

        self.assertEqual(project.calendar.non_working_days, {5, 6})

    def test_a_namespaceless_document_parses(self):
        """Some tools omit the namespace; both forms take one code path."""
        project = parse(
            '<Project><Title>Bare</Title><CalendarUID>1</CalendarUID>'
            f'<Calendars>{self.standard_calendar()}</Calendars>'
            f'<Tasks>{self.task(1, "Work", 1, "2026-07-06", "2026-07-10")}'
            '</Tasks></Project>')

        self.assertEqual(project.name, "Bare")
        self.assertEqual([task.name for task in project.tasks], ["Work"])

    def test_a_link_to_a_task_that_is_not_there_is_dropped(self):
        """A dangling link is dropped rather than left pointing at nothing."""
        project = parse(self.document(
            self.standard_calendar(),
            self.task(1, "Work", 1, "2026-07-06", "2026-07-10",
                      "<PredecessorLink><PredecessorUID>99</PredecessorUID>"
                      "<Type>1</Type></PredecessorLink>")))

        self.assertEqual(list(project.tasks[0].dependencies), [])


class FailureTestCase(unittest.TestCase):
    """What happens when the file is not what it claims to be."""

    def test_a_missing_file_returns_nothing(self):
        """No exception escapes to the caller."""
        self.assertIsNone(import_msproject_file('/nonexistent/plan.xml'))

    def test_malformed_xml_returns_nothing(self):
        """A truncated document is reported rather than raising."""
        handle, path = tempfile.mkstemp(suffix=".xml")
        with os.fdopen(handle, 'w') as broken:
            broken.write('<Project><Tasks><Task>')

        try:
            self.assertIsNone(import_msproject_file(path))
        finally:
            os.unlink(path)


if __name__ == '__main__':
    unittest.main()
