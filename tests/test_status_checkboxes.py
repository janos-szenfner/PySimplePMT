"""
Status as two checkboxes: Estimated and Inactive (issue #36).

The Status dropdown became an Estimated checkbox and an Inactive checkbox.
The single status field still drives the grid, the chart and the KPIs, and
is derived from the two boxes - both ticked reads as Inactive, while the
Estimated tick is remembered so clearing Inactive returns to Estimated.
"""

import json
import unittest
from datetime import datetime, timedelta

from gantt_app.models import Project, Task


BASE = datetime(2026, 1, 1)


def _task(**kwargs):
    kwargs.setdefault("id", "001")
    kwargs.setdefault("name", "A")
    kwargs.setdefault("start_date", BASE)
    return Task(**kwargs)


class TestModelEstimatedFlag(unittest.TestCase):
    def test_default_is_active_and_not_estimated(self):
        task = _task()
        self.assertEqual(task.status, "Active")
        self.assertFalse(task.estimated)

    def test_estimated_status_implies_the_flag(self):
        self.assertTrue(_task(status="Estimated").estimated)

    def test_inactive_can_remember_estimated(self):
        task = _task(status="Inactive", estimated=True)
        self.assertEqual(task.status, "Inactive")
        self.assertTrue(task.estimated)

    def test_the_flag_survives_save_and_load(self):
        task = _task(status="Inactive", estimated=True)
        reread = Task.from_dict(json.loads(json.dumps(task.to_dict())))
        self.assertEqual(reread.status, "Inactive")
        self.assertTrue(reread.estimated)

    def test_an_old_estimated_file_backfills_the_flag(self):
        data = _task(status="Estimated").to_dict()
        data.pop("estimated", None)
        self.assertTrue(Task.from_dict(data).estimated)


def _display_available() -> bool:
    try:
        import tkinter
        root = tkinter.Tk()
    except Exception:
        return False
    root.destroy()
    return True


HAVE_DISPLAY = _display_available()


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestEditorStatusCheckboxes(unittest.TestCase):
    def setUp(self):
        import customtkinter as ctk
        self.root = ctk.CTk()
        self.root.withdraw()
        self.project = Project(name="P")

    def tearDown(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def _dialog(self, task):
        from gantt_app.views.taskdialogs import EditTaskDialog
        self.project.add_task(task)
        dialog = EditTaskDialog(self.root, task, self.project,
                                on_save=lambda t: None,
                                on_delete=lambda i: None)
        dialog.update_idletasks()
        return dialog

    def test_active_task_opens_with_both_boxes_clear(self):
        d = self._dialog(_task())
        self.assertFalse(d.estimated_var.get())
        self.assertFalse(d.inactive_var.get())
        self.assertEqual(d.status_value(), "Active")

    def test_estimated_task_opens_with_estimated_ticked(self):
        d = self._dialog(_task(id="002", status="Estimated"))
        self.assertTrue(d.estimated_var.get())
        self.assertFalse(d.inactive_var.get())
        self.assertEqual(d.status_value(), "Estimated")

    def test_both_ticked_reads_as_inactive(self):
        d = self._dialog(_task(id="003", status="Inactive", estimated=True))
        self.assertTrue(d.estimated_var.get())   # remembered
        self.assertTrue(d.inactive_var.get())
        self.assertEqual(d.status_value(), "Inactive")

    def test_clearing_inactive_returns_to_estimated(self):
        d = self._dialog(_task(id="004", status="Inactive", estimated=True))
        d.inactive_var.set(False)
        self.assertEqual(d.status_value(), "Estimated")
        self.assertTrue(d.estimated_flag())

    def test_clearing_both_is_active(self):
        d = self._dialog(_task(id="005", status="Inactive", estimated=True))
        d.inactive_var.set(False)
        d.estimated_var.set(False)
        self.assertEqual(d.status_value(), "Active")


if __name__ == "__main__":
    unittest.main()
