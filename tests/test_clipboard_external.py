"""
Copy puts a readable table on the desktop clipboard, and internal paste
never reads it (issue #16).

Copying selected rows should let other programs (a spreadsheet, a note) paste
the task rows - at least the names - while copy/cut/paste inside the
application keep working from the in-memory clipboard, not the desktop one.
"""

import unittest
from datetime import datetime

from gantt_app.core.models import Project, Task
from gantt_app.utils.copypastecut import CLIPBOARD_COLUMNS, ClipboardService


class _FakeClipboard:
    """Records what the service writes to the desktop clipboard."""

    def __init__(self, holds=""):
        self.written = None
        self._holds = holds

    def clipboard_clear(self):
        self.written = None

    def clipboard_append(self, text):
        self.written = text

    def clipboard_get(self):
        return self._holds


def _project():
    base = datetime(2026, 9, 14)
    project = Project(name="Plan")
    project.add_task(Task(id="001", name="Design Phase", task_type="Task",
                          start_date=base, end_date=datetime(2026, 9, 18)))
    project.add_task(Task(id="002", name="UI Mockups", task_type="Subtask",
                          parent_task_id="001", start_date=base,
                          end_date=base))
    project.add_task(Task(id="003", name="Design Review",
                          task_type="Milestone", start_date=base))
    return project


class TestReadableClipboardText(unittest.TestCase):
    def setUp(self):
        self.project = _project()
        self.service = ClipboardService(self.project)

    def test_the_first_line_is_the_header(self):
        self.service.copy(["001", "002", "003"])
        first = self.service._clipboard_text().splitlines()[0]
        self.assertEqual(first, "\t".join(CLIPBOARD_COLUMNS))

    def test_every_task_name_is_present(self):
        self.service.copy(["001", "002", "003"])
        text = self.service._clipboard_text()
        for name in ("Design Phase", "UI Mockups", "Design Review"):
            self.assertIn(name, text)

    def test_rows_are_tab_separated_with_the_type(self):
        self.service.copy(["001"])
        row = self.service._clipboard_text().splitlines()[1]
        cells = row.split("\t")
        self.assertEqual(cells[0].strip(), "Design Phase")
        self.assertEqual(cells[1], "Task")

    def test_a_subtask_name_is_indented(self):
        self.service.copy(["001", "002"])
        lines = self.service._clipboard_text().splitlines()
        subtask_line = next(l for l in lines if "UI Mockups" in l)
        self.assertTrue(subtask_line.startswith(" "))

    def test_a_milestone_shows_zero_days(self):
        self.service.copy(["003"])
        row = self.service._clipboard_text().splitlines()[1]
        self.assertIn("0 days", row)

    def test_no_internal_json_leaks_to_the_clipboard(self):
        self.service.copy(["001", "002", "003"])
        text = self.service._clipboard_text()
        for leak in ("payload", "operation", "PySimplePMT tasks",
                     "source_container_id"):
            self.assertNotIn(leak, text)

    def test_the_table_is_what_reaches_the_desktop_clipboard(self):
        self.service.clipboard_widget = _FakeClipboard()
        self.service.copy(["001", "002"])
        written = self.service.clipboard_widget.written
        self.assertEqual(written, self.service._clipboard_text())
        self.assertIn("Design Phase", written)


class TestInternalPasteIgnoresTheDesktopClipboard(unittest.TestCase):
    def setUp(self):
        self.project = _project()
        self.service = ClipboardService(self.project)

    def test_paste_reads_only_the_in_memory_copy(self):
        # Nothing copied inside the app, but the desktop clipboard holds text.
        self.service.clipboard_widget = _FakeClipboard(
            holds="Design Phase\tTask\t...\n")
        self.assertIsNone(self.service._resolve_payload())
        self.assertFalse(self.service.can_paste(None))

    def test_an_internal_copy_still_pastes(self):
        self.service.copy(["001"])
        pasted = self.service.paste_at("001")
        self.assertTrue(pasted)


if __name__ == "__main__":
    unittest.main()
