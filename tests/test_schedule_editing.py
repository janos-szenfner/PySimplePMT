"""
Editing the start, end and duration (issues #23 and #31).

The scheduling-options mode is gone: all three fields are editable, and
Project.reconcile_schedule settles the other two when one changes -
    * a new Duration moves the End, the Start held;
    * a new End moves the Start, the Duration held;
    * a new Start sets a Start No Earlier Than and the Duration follows, the
      End held.
The grid edits the same three cells in place through the same rules.
"""

import unittest
from datetime import datetime

from gantt_app.core.models import Project, Task


def _project():
    # A plain Monday-to-Friday plan; the fixture task runs Mon 5 - Fri 9 Oct
    # 2026, five working days.
    p = Project(name="P", start_date=datetime(2026, 10, 1))
    task = Task(id="T", name="T", start_date=datetime(2026, 10, 5),
                end_date=datetime(2026, 10, 9), duration=5)
    p.add_task(task)
    return p, task


def _shut_down(root) -> None:
    """
    Take a root down, children first, without raising.

    Destroying a root while a Toplevel is still on it leaves Tk running
    ttk::ThemeChanged against an interpreter that has already gone, which
    floods stderr with "can't invoke event" tracebacks.
    """
    try:
        for child in list(root.children.values()):
            try:
                child.destroy()
            except Exception:
                pass
        root.destroy()
    except Exception:
        pass


class TestReconcileSchedule(unittest.TestCase):
    def test_a_new_duration_moves_the_end_and_holds_the_start(self):
        p, t = _project()
        start, end, duration, snet = p.reconcile_schedule(
            t, t.start_date, t.end_date, 8)
        self.assertEqual(start, datetime(2026, 10, 5))
        self.assertEqual(duration, 8)
        self.assertEqual(end, datetime(2026, 10, 14))  # 8 working days
        self.assertIsNone(snet)

    def test_a_new_end_moves_the_start_and_holds_the_duration(self):
        p, t = _project()
        start, end, duration, snet = p.reconcile_schedule(
            t, t.start_date, datetime(2026, 10, 16), t.duration)
        self.assertEqual(end, datetime(2026, 10, 16))
        self.assertEqual(duration, 5)                  # held
        self.assertEqual(start, datetime(2026, 10, 12))  # 5 wd back from the 16th
        self.assertIsNone(snet)

    def test_a_new_start_sets_a_floor_and_recomputes_the_duration(self):
        p, t = _project()
        start, end, duration, snet = p.reconcile_schedule(
            t, datetime(2026, 10, 7), t.end_date, t.duration)
        self.assertEqual(start, datetime(2026, 10, 7))
        self.assertEqual(end, datetime(2026, 10, 9))   # held
        self.assertEqual(duration, 3)                  # Wed-Fri
        self.assertEqual(snet, datetime(2026, 10, 7))  # Start No Earlier Than

    def test_a_start_past_the_end_keeps_at_least_a_day(self):
        p, t = _project()
        start, end, duration, snet = p.reconcile_schedule(
            t, datetime(2026, 10, 19), t.end_date, t.duration)
        self.assertEqual(start, datetime(2026, 10, 19))
        self.assertEqual(duration, 1)
        self.assertEqual(end, datetime(2026, 10, 19))
        self.assertEqual(snet, datetime(2026, 10, 19))

    def test_no_change_returns_the_task_as_it_was(self):
        p, t = _project()
        start, end, duration, snet = p.reconcile_schedule(
            t, t.start_date, t.end_date, 5)
        self.assertEqual((start, end, duration), (t.start_date, t.end_date, 5))
        self.assertIsNone(snet)

    def test_start_takes_precedence_when_more_than_one_changed(self):
        # Both start and end retyped: the start rule wins, holding the new end.
        p, t = _project()
        start, end, duration, snet = p.reconcile_schedule(
            t, datetime(2026, 10, 6), datetime(2026, 10, 15), 5)
        self.assertEqual(start, datetime(2026, 10, 6))
        self.assertEqual(end, datetime(2026, 10, 15))
        self.assertEqual(snet, datetime(2026, 10, 6))

    def test_a_milestone_start_sets_a_floor_and_no_length(self):
        p = Project(name="P", start_date=datetime(2026, 10, 1))
        m = Task(id="M", name="M", start_date=datetime(2026, 10, 5),
                 task_type="Milestone")
        p.add_task(m)
        start, end, duration, snet = p.reconcile_schedule(
            m, datetime(2026, 10, 9), None, None)
        self.assertEqual(start, datetime(2026, 10, 9))
        self.assertIsNone(end)
        self.assertEqual(duration, 0)
        self.assertEqual(snet, datetime(2026, 10, 9))


def _display() -> bool:
    try:
        import tkinter
        root = tkinter.Tk()
    except Exception:
        return False
    root.destroy()
    return True


HAVE_DISPLAY = _display()


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestGridScheduleEditing(unittest.TestCase):
    def setUp(self):
        import customtkinter as ctk
        from gantt_app.views.task_list import DragDropTaskList
        from gantt_app.utils.undoredo import (ProjectStateTracker,
                                              UndoRedoManager)

        self.root = ctk.CTk()
        self.root.withdraw()
        self.project, self.task = _project()
        self.tracker = ProjectStateTracker(self.project, UndoRedoManager())
        self.view = DragDropTaskList(self.root, self.project,
                                     project_tracker=self.tracker)
        self.view.update_task_list()

    def tearDown(self):
        try:
            _shut_down(self.root)
        except Exception:
            pass

    def test_setting_the_duration_moves_the_end(self):
        self.view.set_schedule("T", self.task.start_date,
                               datetime(2026, 10, 14), 8, None)
        # update_task rebuilds the task, so read it back from the project.
        task = self.project.get_task_by_id("T")
        self.assertEqual(task.duration, 8)
        self.assertEqual(task.end_date, datetime(2026, 10, 14))
        self.assertEqual(task.start_date, datetime(2026, 10, 5))

    def test_setting_the_start_pins_a_start_no_earlier_than(self):
        self.view.set_schedule("T", datetime(2026, 10, 7), self.task.end_date,
                               3, datetime(2026, 10, 7))
        task = self.project.get_task_by_id("T")
        self.assertEqual(task.constraint_type, "SNET")
        self.assertEqual(task.constraint_date, datetime(2026, 10, 7))

    def test_a_grid_schedule_edit_is_one_undo_step(self):
        self.view.set_schedule("T", self.task.start_date,
                               datetime(2026, 10, 14), 8, None)
        self.assertEqual(self.project.get_task_by_id("T").duration, 8)
        self.tracker.manager.undo()
        self.assertEqual(self.project.get_task_by_id("T").duration, 5)

    def test_a_container_cell_is_not_typed_in_place(self):
        parent = Task(id="P1", name="Phase", task_type="Phase",
                      start_date=datetime(2026, 10, 5),
                      end_date=datetime(2026, 10, 9))
        self.project.add_task(parent)
        self.task.parent_task_id = "P1"
        self.assertFalse(self.view._schedule_cell_editable("P1", "Start"))
        self.assertTrue(self.view._schedule_cell_editable("T", "Duration"))


if __name__ == "__main__":
    unittest.main()
