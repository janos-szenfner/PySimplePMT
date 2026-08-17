"""
Tests that the duration entered when creating a task is the duration created.

DEVELOPMENT NOTES:
------------------
The dialogs ask for a duration in days and turn it into an end date. That
arithmetic has to agree with Task.duration_days, which counts inclusive
working days, and with the importers, which all treat a stated duration the
same way. It previously did not, so a task created in the UI was a day longer
than one imported from a file with the same stated duration.

A duration is working effort, so both sides of that agreement now go through
the working calendar - see gantt_app.workdaycalendar. Adding days with plain
timedelta arithmetic is what these tests exist to catch: it spends part of a
task over the weekend, and the task comes out shorter than it was asked for.

The end-date expression is duplicated here rather than driven through the
form, which would need a display to construct.
"""

import unittest
from datetime import datetime, timedelta

from gantt_app.models import Task
from gantt_app.utils.mermaid_importer import MermaidImporter
from gantt_app.workdaycalendar import WorkingCalendar


def end_date_for(start: datetime, duration_days: int) -> datetime:
    """The expression the create dialog and the importers both use."""
    return WorkingCalendar().add_working_days(start, duration_days)


class TestCreatedTaskDuration(unittest.TestCase):
    """Tests for the duration of a task created from the toolbar."""

    def setUp(self):
        """Set up test fixtures."""
        self.start = datetime(2024, 1, 1)

    def test_created_duration_matches_the_request(self):
        """A task created for N days spans exactly N days."""
        for requested in (1, 2, 7, 30, 365):
            task = Task.create_task(
                "T", self.start, end_date_for(self.start, requested)
            )
            self.assertEqual(task.duration_days, requested,
                             f"asked for {requested} days")

    def test_single_day_task_starts_and_ends_together(self):
        """A one day task does not spill onto a second day."""
        task = Task.create_task("T", self.start, end_date_for(self.start, 1))

        self.assertEqual(task.start_date, task.end_date)
        self.assertEqual(task.duration_days, 1)

    def test_agrees_with_the_mermaid_importer(self):
        """A hand-created task matches an imported one of the same duration."""
        importer = MermaidImporter()

        for requested in (1, 5, 14):
            created = Task.create_task(
                "T", self.start, end_date_for(self.start, requested)
            )
            imported = Task.create_task(
                "T", self.start,
                importer._parse_duration(f"{requested}d", self.start)
            )
            self.assertEqual(created.end_date, imported.end_date,
                             f"{requested}d disagrees between UI and import")
            self.assertEqual(created.duration_days, imported.duration_days)

    def test_subtask_duration_matches_the_request(self):
        """A sub-task created for N days spans exactly N days."""
        parent = Task.create_task("Parent", self.start,
                                  self.start + timedelta(days=30))

        for requested in (1, 4, 10):
            subtask = Task.create_subtask(
                "Child", parent_task=parent,
                end_date=end_date_for(parent.start_date, requested)
            )
            self.assertEqual(subtask.duration_days, requested,
                             f"asked for {requested} days")


if __name__ == '__main__':
    unittest.main()
