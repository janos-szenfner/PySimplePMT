"""
Tests for which completion control the task editor offers.

WHY THIS FILE EXISTS:
=====================
It was reported as "the progress bar is not viewable on a different Mac",
with two screenshots: one editor showing "Progress (%): 30" and another
showing a "Completed:" tick and no percentage at all.

Nothing about it depends on the machine. The two screenshots were of two
different rows - a Task and a Subtask - and the editor offers a different
control for each on purpose: a sub-task is a tick on a checklist, done or
not, and the task above it reads how many of its sub-tasks are ticked.
Offering a percentage box for a sub-task invites a 60% that would then count
as not done, with nothing on the form saying so.

These tests say that out loud, so the next person who sees the two forms
side by side can tell design from fault.
"""

import unittest
from datetime import datetime

import customtkinter as ctk

from gantt_app.models import Project, Task
from gantt_app.views.taskdialogs import EditTaskDialog


BASE = datetime(2026, 1, 13)


class ProgressFieldTestCase(unittest.TestCase):
    """One plan holding a row of every type."""

    def setUp(self):
        """A phase, a deliverable, a task, a sub-task and a milestone."""
        self.root = ctk.CTk()
        self.root.withdraw()

        self.project = Project(name="Plan")
        rows = (
            ("001", "Preparation", "Phase", None),
            ("002", "Handover", "Deliverable", "001"),
            ("003", "Implementation", "Task", "001"),
            ("004", "Defining goals", "Subtask", "003"),
            ("005", "Sign-off", "Milestone", None),
        )
        for task_id, name, task_type, parent in rows:
            self.project.add_task(Task(
                id=task_id, name=name, start_date=BASE, end_date=BASE,
                task_type=task_type, parent_task_id=parent))

    def tearDown(self):
        """Tear the root window down."""
        try:
            self.root.destroy()
        except Exception:
            pass

    def editor_for(self, task_id):
        """The edit dialog for one row, built but never shown."""
        def nothing(*_args, **_kwargs):
            """A callback the dialog needs and this test does not."""

        task = self.project.get_task_by_id(task_id)
        dialog = EditTaskDialog(self.root, task, self.project, nothing, nothing)
        # Never shown: this asks what the form offers, not how it looks.
        # Not registered for cleanup either - tearDown destroys the root,
        # which takes its dialogs with it, and a cleanup runs after that
        dialog.withdraw()
        return dialog


class TestWhichControlEachTypeGets(ProgressFieldTestCase):
    """A tick for a sub-task, a percentage for everything else."""

    def test_a_task_is_offered_a_percentage(self):
        """Which is the form in the second screenshot."""
        editor = self.editor_for("003")

        self.assertIsNotNone(editor.progress_entry)
        self.assertIsNone(editor.progress_done_var)

    def test_a_subtask_is_offered_a_tick(self):
        """
        Which is the form in the first screenshot, and is not a fault.

        A sub-task is done or not; the task above it counts how many of its
        sub-tasks are ticked.
        """
        editor = self.editor_for("004")

        self.assertIsNone(editor.progress_entry)
        self.assertIsNotNone(editor.progress_done_var)

    def test_a_phase_and_a_deliverable_are_offered_a_percentage(self):
        """
        Shown but not editable: they read theirs from what is under them.
        """
        for task_id in ("001", "002"):
            editor = self.editor_for(task_id)

            self.assertIsNotNone(editor.progress_entry,
                                 f"{task_id} has no progress box")
            self.assertIsNone(editor.progress_done_var)

    def test_a_milestone_is_offered_a_percentage(self):
        """It is not a sub-task, so it gets what everything else gets."""
        editor = self.editor_for("005")

        self.assertIsNotNone(editor.progress_entry)

    def test_the_choice_is_made_from_the_type_and_nothing_else(self):
        """
        No part of it asks the machine, the platform or the window.

        Which is the whole answer to "it is not viewable on a different
        Mac": the two forms compared were a Task and a Subtask.
        """
        import inspect

        from gantt_app.views import taskform

        source = inspect.getsource(taskform.TaskFormDialog._build_progress)

        self.assertIn("task_type == 'Subtask'", source)
        for machine_dependent in ('platform', 'sys.', 'darwin', 'winfo_screen'):
            self.assertNotIn(machine_dependent, source)


if __name__ == '__main__':
    unittest.main()
