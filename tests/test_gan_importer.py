"""
Unit tests for GAN file importer.

DEVELOPMENT NOTES:
------------------
Fixtures here mirror what GanttProject 3.x actually writes: no XML namespace,
schedules given as a start attribute plus a working-day duration, milestones
flagged with meeting="true", sub-tasks nested inside their parent, and
<depend> elements naming a *successor*. A namespaced fixture is kept to cover
files written by older versions.
"""

import unittest
import os
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import shutil

from gantt_app.utils.gan_importer import (
    GANImporter, GanttProjectCalendar, import_gan_file, strip_namespaces
)


#: A plan exercising nesting, milestones, dependencies and a holiday.
SAMPLE_GAN = '''<?xml version="1.0" encoding="UTF-8"?>
<project name="Sample Project" company="" version="3.2.3247">
    <calendars base-id="Hungary">
        <day-types>
            <day-type id="0"/>
            <day-type id="1"/>
            <default-week id="1" name="default" sun="1" mon="0" tue="0" wed="0" thu="0" fri="0" sat="1"/>
            <only-show-weekends value="false"/>
        </day-types>
        <date year="" month="3" date="15" type="HOLIDAY"/>
        <date year="2024" month="5" date="1" type="HOLIDAY"/>
    </calendars>
    <tasks empty-milestones="true">
        <taskproperties>
            <taskproperty id="tpd3" name="name" type="default" valuetype="text"/>
        </taskproperties>
        <task id="1" name="Kick-Off" color="#8cb6ce" meeting="false" start="2024-01-01" duration="5" complete="25" expand="true">
            <depend id="2" type="2" difference="0" hardness="Strong"/>
        </task>
        <task id="2" name="Approval" color="#8cb6ce" meeting="true" start="2024-01-08" duration="0" complete="0" expand="true">
            <depend id="3" type="2" difference="0" hardness="Strong"/>
        </task>
        <task id="3" name="Delivery" color="#000000" meeting="false" start="2024-01-08" duration="10" complete="0" expand="true">
            <task id="4" name="Build" color="#8cb6ce" meeting="false" start="2024-01-08" duration="5" complete="0" expand="true">
                <task id="5" name="Sub-build" color="#8cb6ce" meeting="false" start="2024-01-08" duration="2" complete="0" expand="true"/>
            </task>
            <task id="6" name="Ship" meeting="false" start="2024-01-15" duration="5" complete="100" expand="true"/>
        </task>
    </tasks>
    <resources/>
    <allocations/>
</project>
'''


class TestGanttProjectCalendar(unittest.TestCase):
    """Tests for the working-day calendar."""

    def setUp(self):
        """Set up test fixtures."""
        root = ET.fromstring(SAMPLE_GAN)
        self.calendar = GanttProjectCalendar.from_element(root.find('calendars'))

    def test_weekend_days_parsed(self):
        """Saturday and Sunday are read as non-working from default-week."""
        self.assertEqual(self.calendar.non_working_weekdays, {5, 6})

    def test_recurring_holiday(self):
        """A holiday with no year recurs every year."""
        self.assertIn((3, 15), self.calendar.recurring_holidays)
        self.assertFalse(self.calendar.is_working_day(datetime(2024, 3, 15)))
        self.assertFalse(self.calendar.is_working_day(datetime(2030, 3, 15)))

    def test_year_specific_holiday(self):
        """A holiday pinned to a year applies only to that year."""
        self.assertFalse(self.calendar.is_working_day(datetime(2024, 5, 1)))
        # 2025-05-01 is a Thursday and was not declared for that year
        self.assertTrue(self.calendar.is_working_day(datetime(2025, 5, 1)))

    def test_weekends_are_not_working_days(self):
        """Saturdays and Sundays do not count as working days."""
        self.assertFalse(self.calendar.is_working_day(datetime(2024, 1, 6)))
        self.assertFalse(self.calendar.is_working_day(datetime(2024, 1, 7)))
        self.assertTrue(self.calendar.is_working_day(datetime(2024, 1, 8)))

    def test_add_working_days_skips_weekends(self):
        """Advancing by working days steps over the weekend."""
        monday = datetime(2024, 1, 1)
        self.assertEqual(self.calendar.add_working_days(monday, 4),
                         datetime(2024, 1, 5))
        self.assertEqual(self.calendar.add_working_days(monday, 5),
                         datetime(2024, 1, 8))
        self.assertEqual(self.calendar.add_working_days(monday, 0), monday)

    def test_add_working_days_skips_holidays(self):
        """Advancing by working days steps over declared holidays."""
        # 2024-03-14 is a Thursday; the 15th is a holiday, the 16th a Saturday
        thursday = datetime(2024, 3, 14)
        self.assertEqual(self.calendar.add_working_days(thursday, 1),
                         datetime(2024, 3, 18))

    def test_end_date_is_inclusive(self):
        """A duration of N working days covers N days including the start."""
        monday = datetime(2024, 1, 1)
        self.assertEqual(self.calendar.end_date_for(monday, 1), monday)
        self.assertEqual(self.calendar.end_date_for(monday, 5),
                         datetime(2024, 1, 5))

    def test_default_calendar_without_element(self):
        """With no <calendars> block, weekends still default to non-working."""
        calendar = GanttProjectCalendar.from_element(None)
        self.assertEqual(calendar.non_working_weekdays, {5, 6})


class TestGANImporter(unittest.TestCase):
    """Test cases for GAN file import."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.importer = GANImporter()

    def tearDown(self):
        """Clean up test files."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_gan_file(self, content: str) -> str:
        """Create a temporary GAN file with the given XML content."""
        filepath = os.path.join(self.test_dir, "test.gan")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return filepath

    # ------------------------------------------------------------------
    # Date parsing
    # ------------------------------------------------------------------

    def test_parse_date_plain(self):
        """GanttProject 3.x writes plain YYYY-MM-DD dates."""
        result = self.importer.parse_date("2024-01-22")
        self.assertEqual(result, datetime(2024, 1, 22))

    def test_parse_date_iso_with_milliseconds(self):
        """Test parsing ISO date with milliseconds."""
        result = self.importer.parse_date("2024-01-01T10:30:45.123Z")

        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2024)
        self.assertEqual(result.hour, 10)
        self.assertEqual(result.second, 45)

    def test_parse_date_iso_without_milliseconds(self):
        """Test parsing ISO date without milliseconds."""
        result = self.importer.parse_date("2024-01-01T10:30:45Z")

        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2024)
        self.assertEqual(result.minute, 30)

    def test_parse_date_none(self):
        """Test parsing None date."""
        self.assertIsNone(self.importer.parse_date(None))

    def test_parse_date_empty_string(self):
        """Test parsing empty string date."""
        self.assertIsNone(self.importer.parse_date(""))

    def test_parse_date_invalid(self):
        """Test parsing invalid date string."""
        self.assertIsNone(self.importer.parse_date("invalid-date"))

    # ------------------------------------------------------------------
    # Structure
    # ------------------------------------------------------------------

    def test_import_reads_every_task(self):
        """Nested tasks are imported alongside top-level ones."""
        project = self.importer.import_gan(self._create_gan_file(SAMPLE_GAN))

        self.assertIsNotNone(project)
        self.assertEqual(project.name, "Sample Project")
        self.assertEqual(len(project.tasks), 6)

    def test_nested_tasks_become_subtasks(self):
        """A <task> inside a <task> becomes a Subtask of it."""
        project = self.importer.import_gan(self._create_gan_file(SAMPLE_GAN))

        build = project.get_task_by_id("4")
        self.assertEqual(build.parent_task_id, "3")
        self.assertEqual(build.task_type, "Subtask")

        top_level = {t.id for t in project.get_root_tasks()}
        self.assertEqual(top_level, {"1", "2", "3"})

    def test_deep_nesting_is_preserved(self):
        """Nesting deeper than one level keeps its real parent."""
        project = self.importer.import_gan(self._create_gan_file(SAMPLE_GAN))

        sub_build = project.get_task_by_id("5")
        self.assertEqual(sub_build.parent_task_id, "4")
        self.assertEqual(sub_build.task_type, "Subtask")

    def test_dependencies_are_reversed(self):
        """<depend> names a successor, so the edge lands on the successor."""
        project = self.importer.import_gan(self._create_gan_file(SAMPLE_GAN))

        # Task 1 declares <depend id="2"/>, meaning 2 comes after 1
        self.assertEqual(project.get_task_by_id("1").dependency_ids, [])
        self.assertEqual(project.get_task_by_id("2").dependency_ids, ["1"])
        self.assertEqual(project.get_task_by_id("3").dependency_ids, ["2"])

    def test_milestone_from_meeting_attribute(self):
        """meeting="true" marks a milestone with no end date."""
        project = self.importer.import_gan(self._create_gan_file(SAMPLE_GAN))

        approval = project.get_task_by_id("2")
        self.assertTrue(approval.is_milestone)
        self.assertIsNone(approval.end_date)
        self.assertEqual(approval.start_date, datetime(2024, 1, 8))

    def test_regular_task_is_not_a_milestone(self):
        """A task with a duration is not treated as a milestone."""
        project = self.importer.import_gan(self._create_gan_file(SAMPLE_GAN))

        self.assertFalse(project.get_task_by_id("1").is_milestone)

    def test_summary_task_is_not_a_milestone(self):
        """A parent task is never a milestone, whatever its duration reads."""
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
<project name="Summary">
    <tasks>
        <task id="1" name="Parent" start="2024-01-01" duration="0">
            <task id="2" name="Child" start="2024-01-01" duration="3"/>
        </task>
    </tasks>
</project>
'''
        project = self.importer.import_gan(self._create_gan_file(xml))
        self.assertFalse(project.get_task_by_id("1").is_milestone)

    # ------------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------------

    def test_end_date_from_working_day_duration(self):
        """Durations expand into end dates across the project calendar."""
        project = self.importer.import_gan(self._create_gan_file(SAMPLE_GAN))

        kickoff = project.get_task_by_id("1")
        self.assertEqual(kickoff.start_date, datetime(2024, 1, 1))
        # 5 working days from Monday the 1st ends Friday the 5th
        self.assertEqual(kickoff.end_date, datetime(2024, 1, 5))

    def test_end_date_spans_weekend(self):
        """A duration longer than a week runs past the weekend."""
        project = self.importer.import_gan(self._create_gan_file(SAMPLE_GAN))

        delivery = project.get_task_by_id("3")
        self.assertEqual(delivery.start_date, datetime(2024, 1, 8))
        # 10 working days from Monday the 8th ends Friday the 19th
        self.assertEqual(delivery.end_date, datetime(2024, 1, 19))

    def test_calendar_can_be_ignored(self):
        """respect_calendar=False treats durations as calendar days."""
        importer = GANImporter(respect_calendar=False)
        project = importer.import_gan(self._create_gan_file(SAMPLE_GAN))

        delivery = project.get_task_by_id("3")
        self.assertEqual(delivery.end_date, datetime(2024, 1, 17))

    def test_progress_from_complete_attribute(self):
        """The complete attribute becomes the task's progress."""
        project = self.importer.import_gan(self._create_gan_file(SAMPLE_GAN))

        self.assertEqual(project.get_task_by_id("1").progress, 25)
        self.assertEqual(project.get_task_by_id("6").progress, 100)
        self.assertEqual(project.get_task_by_id("3").progress, 0)

    def test_color_from_attribute(self):
        """The color attribute is used directly."""
        project = self.importer.import_gan(self._create_gan_file(SAMPLE_GAN))

        self.assertEqual(project.get_task_by_id("1").color, "#8cb6ce")
        self.assertEqual(project.get_task_by_id("3").color, "#000000")

    def test_default_color_when_absent(self):
        """A task with no color attribute falls back to the default."""
        project = self.importer.import_gan(self._create_gan_file(SAMPLE_GAN))

        self.assertEqual(project.get_task_by_id("6").color, "#1f6aa5")

    def test_project_dates_cover_all_tasks(self):
        """Project start and end are derived from the imported tasks."""
        project = self.importer.import_gan(self._create_gan_file(SAMPLE_GAN))

        self.assertEqual(project.start_date, datetime(2024, 1, 1))
        self.assertEqual(project.end_date, datetime(2024, 1, 19))

    # ------------------------------------------------------------------
    # Compatibility and error handling
    # ------------------------------------------------------------------

    def test_namespaced_file_is_supported(self):
        """Older namespaced files parse through the same path."""
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
<project name="Namespaced" xmlns="http://ganttproject.sf.net/">
    <tasks>
        <task id="1" name="Task One" start="2024-01-01" duration="3">
            <depend id="2" type="2" difference="0" hardness="Strong"/>
        </task>
        <task id="2" name="Task Two" start="2024-01-04" duration="2"/>
    </tasks>
</project>
'''
        project = self.importer.import_gan(self._create_gan_file(xml))

        self.assertIsNotNone(project)
        self.assertEqual(len(project.tasks), 2)
        self.assertEqual(project.get_task_by_id("2").dependency_ids, ["1"])

    def test_legacy_depends_on_form(self):
        """The legacy <depends-on><dependency idref=""/> form still works."""
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
<project name="Legacy">
    <tasks>
        <task id="1" name="First" start="2024-01-01" duration="3"/>
        <task id="2" name="Second" start="2024-01-04" duration="2">
            <depends-on>
                <dependency idref="1"/>
            </depends-on>
        </task>
    </tasks>
</project>
'''
        project = self.importer.import_gan(self._create_gan_file(xml))

        self.assertEqual(project.get_task_by_id("2").dependency_ids, ["1"])

    def test_dependency_to_missing_task_is_dropped(self):
        """An edge naming a task not in the file does not dangle."""
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
<project name="Dangling">
    <tasks>
        <task id="1" name="Only" start="2024-01-01" duration="3">
            <depend id="99" type="2" difference="0" hardness="Strong"/>
        </task>
    </tasks>
</project>
'''
        project = self.importer.import_gan(self._create_gan_file(xml))

        self.assertEqual(len(project.tasks), 1)
        self.assertEqual(project.get_task_by_id("1").dependency_ids, [])

    def test_empty_project(self):
        """A file with no tasks imports as an empty project."""
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
<project name="Empty Project">
    <tasks></tasks>
</project>
'''
        project = self.importer.import_gan(self._create_gan_file(xml))

        self.assertIsNotNone(project)
        self.assertEqual(project.name, "Empty Project")
        self.assertEqual(len(project.tasks), 0)

    def test_project_without_name(self):
        """A project with no name attribute gets a placeholder."""
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
<project>
    <tasks>
        <task id="1" name="Task" start="2024-01-01" duration="1"/>
    </tasks>
</project>
'''
        project = self.importer.import_gan(self._create_gan_file(xml))

        self.assertEqual(project.name, "Imported Project")

    def test_task_without_start_date(self):
        """A task with no start date still imports."""
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
<project name="No Dates">
    <tasks>
        <task id="1" name="Undated" duration="3"/>
    </tasks>
</project>
'''
        project = self.importer.import_gan(self._create_gan_file(xml))

        self.assertEqual(len(project.tasks), 1)
        self.assertIsNotNone(project.tasks[0].start_date)

    def test_import_nonexistent_file(self):
        """Importing a missing file returns None."""
        missing = os.path.join(self.test_dir, "nonexistent.gan")
        self.assertIsNone(self.importer.import_gan(missing))

    def test_import_malformed_xml(self):
        """Malformed XML returns None rather than raising."""
        filepath = self._create_gan_file("<project><tasks></project>")
        self.assertIsNone(self.importer.import_gan(filepath))

    def test_convenience_function(self):
        """import_gan_file works without constructing the importer."""
        project = import_gan_file(self._create_gan_file(SAMPLE_GAN))

        self.assertIsNotNone(project)
        self.assertEqual(len(project.tasks), 6)


class TestGANColors(unittest.TestCase):
    """Tests for the optional <colors> lookup table."""

    def setUp(self):
        """Set up test fixtures."""
        self.importer = GANImporter()

    def test_parse_colors_empty(self):
        """Test parsing colors from empty XML."""
        root = ET.Element('project')
        colors = self.importer.parse_colors(root)

        self.assertIn('default', colors)
        self.assertIn('milestone', colors)
        self.assertEqual(colors['default'], '#1f6aa5')
        self.assertEqual(colors['milestone'], '#e74c3c')

    def test_parse_colors_from_xml(self):
        """RGB colour definitions convert to hex."""
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
<project name="Color Project">
    <colors>
        <color id="custom" r="255" g="128" b="0"/>
    </colors>
    <tasks></tasks>
</project>
'''
        root = strip_namespaces(ET.fromstring(xml))
        colors = self.importer.parse_colors(root)

        self.assertEqual(colors['custom'], '#ff8000')


class TestStripNamespaces(unittest.TestCase):
    """Tests for the namespace-stripping helper."""

    def test_namespaces_removed(self):
        """Namespaced tags are reduced to their local names."""
        xml = '<project xmlns="http://ganttproject.sf.net/"><tasks/></project>'
        root = strip_namespaces(ET.fromstring(xml))

        self.assertEqual(root.tag, 'project')
        self.assertIsNotNone(root.find('tasks'))

    def test_plain_tags_untouched(self):
        """Documents without namespaces are left alone."""
        root = strip_namespaces(ET.fromstring('<project><tasks/></project>'))

        self.assertEqual(root.tag, 'project')
        self.assertIsNotNone(root.find('tasks'))


if __name__ == '__main__':
    unittest.main()
