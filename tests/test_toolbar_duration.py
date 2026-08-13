"""
Tests that the duration entered when creating a task is the duration created.

DEVELOPMENT NOTES:
------------------
The toolbar asks for a duration in days and turns it into an end date. That
arithmetic has to agree with Task.duration_days, which is inclusive, and with
the importers, which all treat a stated duration as inclusive too. It
previously did not, so a task created in the UI was a day longer than one
imported from a file with the same stated duration.

The end-date expressions are duplicated here rather than driven through the
toolbar, which would need a display to construct.
"""

import unittest
from datetime import datetime, timedelta

from gantt_app.models import Task
from gantt_app.utils.mermaid_importer import MermaidImporter


def end_date_for(start: datetime, duration_days: int) -> datetime:
    """The expression used by Toolbar.add_task and Toolbar.add_subtask."""
    return start + timedelta(days=duration_days - 1)


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
