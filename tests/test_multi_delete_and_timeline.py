"""
Multi-row Delete and Add-to-Timeline in the task list (issues #17, #34).

Deleting a multi-row selection now removes every selected row as one
undoable step, and the right-click Add to Timeline turns Show-in-timeline on
for the whole selection. Both drive the real widget, so the tests are
display-gated like the other task-list suites.
"""

import unittest
from datetime import datetime, timedelta

from gantt_app.models import Project, Task
from gantt_app.views import dialogs as messagebox

BASE = datetime(2026, 9, 10)


def _display_available() -> bool:
    try:
        import tkinter
        root = tkinter.Tk()
    except Exception:
        return False
    root.destroy()
    return True


HAVE_DISPLAY = _display_available()


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class TaskListCase(unittest.TestCase):
    def setUp(self):
        import customtkinter as ctk
        from gantt_app.utils.undoredo import ProjectStateTracker, UndoRedoManager
        from gantt_app.views.task_list import DragDropTaskList

        self.root = ctk.CTk()
        self.root.withdraw()

        self.project = Project(name="Plan")
        for n in range(1, 5):
            self.project.add_task(Task(
                id=f"t{n}", name=f"Task {n}", task_type="Task",
                start_date=BASE, end_date=BASE + timedelta(days=2)))

        self.manager = UndoRedoManager()
        self.task_list = DragDropTaskList(
            self.root, self.project,
            project_tracker=ProjectStateTracker(self.project, self.manager))
        self.root.update_idletasks()

        # Confirmations answer Yes without a real dialog.
        self._orig_askyesno = messagebox.askyesno
        messagebox.askyesno = lambda *a, **k: True

    def tearDown(self):
        messagebox.askyesno = self._orig_askyesno
        try:
            self.root.destroy()
        except Exception:
            pass

    def _ids(self):
        return [t.id for t in self.project.tasks]


class TestMultiDelete(TaskListCase):
    def test_deleting_a_selection_removes_every_row(self):
        self.task_list.delete_tasks(["t1", "t2", "t3"])
        self.assertEqual(self._ids(), ["t4"])

    def test_a_multi_delete_is_one_undo_step(self):
        self.task_list.delete_tasks(["t1", "t2", "t3"])
        self.assertTrue(self.manager.can_undo())
        self.manager.undo()
        self.assertEqual(set(self._ids()), {"t1", "t2", "t3", "t4"})

    def test_deleting_a_single_row_still_works(self):
        self.task_list.delete_tasks("t2")
        self.assertEqual(self._ids(), ["t1", "t3", "t4"])

    def test_cancelling_the_prompt_keeps_every_row(self):
        messagebox.askyesno = lambda *a, **k: False
        self.task_list.delete_tasks(["t1", "t2"])
        self.assertEqual(len(self.project.tasks), 4)


class TestAddToTimeline(TaskListCase):
    def setUp(self):
        super().setUp()
        for t in self.project.tasks:
            t.show_in_timeline = False

    def test_it_turns_the_flag_on_for_the_selection(self):
        self.task_list.add_to_timeline(["t1", "t3"])
        flags = {t.id: t.show_in_timeline for t in self.project.tasks}
        self.assertTrue(flags["t1"])
        self.assertTrue(flags["t3"])
        self.assertFalse(flags["t2"])
        self.assertFalse(flags["t4"])

    def test_it_is_one_undo_step(self):
        self.task_list.add_to_timeline(["t1", "t2"])
        self.assertTrue(self.manager.can_undo())
        self.manager.undo()
        self.assertFalse(
            any(t.show_in_timeline for t in self.project.tasks))

    def test_rows_already_on_the_timeline_need_no_undo_step(self):
        self.project.get_task_by_id("t1").show_in_timeline = True
        self.task_list.add_to_timeline(["t1"])
        self.assertFalse(self.manager.can_undo())

    def test_added_rows_become_visible_on_the_gantt(self):
        from gantt_app.utils.chart_render import _get_visible_tasks

        self.assertEqual(_get_visible_tasks(self.project), [])  # all off
        self.task_list.add_to_timeline(["t1", "t2"])
        visible = {t.id for t in _get_visible_tasks(self.project)}
        self.assertEqual(visible, {"t1", "t2"})

    def test_the_flag_the_editor_reads_is_set(self):
        # The task editor's checkbox reads task.show_in_timeline directly, so
        # a flag turned on here shows ticked when the row is next opened.
        self.task_list.add_to_timeline(["t3"])
        self.assertTrue(self.project.get_task_by_id("t3").show_in_timeline)


if __name__ == "__main__":
    unittest.main()
