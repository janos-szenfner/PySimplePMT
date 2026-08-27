"""
Tests for the completion a row carries and the one it takes from below.

WHY THIS FILE EXISTS:
=====================
It began as "the progress bar is not viewable on a different Mac", with two
editors side by side: one showing "Progress (%): 30" and one showing a
"Completed:" tick and no percentage. Nothing about it depended on the
machine - they were a Task and a Sub-task, and the editor deliberately
offered a different control for each.

The reason it did was the roll-up: a Task counted how many of its sub-tasks
were ticked, so a sub-task at 60% would have counted for nothing, and a
percentage box would have been a number the form took and the plan ignored.

Asked for, and now the case: a sub-task carries a percentage like every
other row, and the Task above it averages those percentages instead of
counting ticks. Evenly, which is what counting ticks was all along - a
checklist holds nothing but 0 and 100, and the average of those is the
proportion ticked, so every plan that existed before this reads exactly as
it did.
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
        """A phase, a task, a sub-task and a milestone."""
        self.root = ctk.CTk()
        self.root.withdraw()

        self.project = Project(name="Plan")
        rows = (
            ("001", "Preparation", "Phase", None),
            ("002", "Handover", "Task", "001"),
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


class TestEveryTypeIsOfferedAPercentage(ProgressFieldTestCase):
    """Including a sub-task, which used to be offered a tick instead."""

    def test_a_task_is_offered_a_percentage(self):
        """As it always was."""
        self.assertIsNotNone(self.editor_for("003").progress_entry)

    def test_a_subtask_is_offered_a_percentage(self):
        """
        The change asked for.

        It was a tick, because a Task counted how many of its sub-tasks
        were ticked and a 60% would have counted for nothing. The Task
        averages percentages now, so 60% counts for 60%.
        """
        self.assertIsNotNone(self.editor_for("004").progress_entry)

    def test_a_phase_and_a_summary_task_are_offered_a_percentage(self):
        """Shown but not editable: they read theirs from what is under."""
        for task_id in ("001", "003"):
            self.assertIsNotNone(self.editor_for(task_id).progress_entry,
                                 f"{task_id} has no progress box")

    def test_a_milestone_is_offered_a_percentage(self):
        """Like everything else."""
        self.assertIsNotNone(self.editor_for("005").progress_entry)

    def test_no_row_is_offered_a_tick_any_more(self):
        """One control, so there is one thing for the form to read back."""
        for task_id in ("001", "002", "003", "004", "005"):
            editor = self.editor_for(task_id)
            self.assertFalse(hasattr(editor, 'progress_done_var'),
                             f"{task_id} still has a tick")

    def test_nothing_about_the_form_asks_the_machine(self):
        """
        Which was the whole answer to "it is not viewable on a different
        Mac": the two forms compared were a Task and a Sub-task.
        """
        import inspect

        from gantt_app.views import taskform

        source = inspect.getsource(taskform.TaskFormDialog._build_progress)

        for machine_dependent in ('platform', 'sys.', 'darwin',
                                  'winfo_screen'):
            self.assertNotIn(machine_dependent, source)


class TestATaskAveragesItsSubtasks(unittest.TestCase):
    """
    And every plan that existed before this reads exactly as it did.

    WHY THESE EXIST:
    ================
    A Task used to count how many of its sub-tasks were ticked. It averages
    their percentages now, which is the same arithmetic on a checklist: a
    tick is 100 and an empty box is 0, and the average of those is the
    proportion ticked.
    """

    @staticmethod
    def subtask(progress):
        """A sub-task at a given percentage."""
        return Task(id=f"s{progress}", name="s", start_date=BASE,
                    end_date=BASE, task_type="Subtask", progress=progress)

    def rolled(self, percentages):
        """What a Task holding those sub-tasks reads."""
        from gantt_app.models import rolled_up_progress

        parent = Task(id="T", name="t", start_date=BASE, end_date=BASE,
                      task_type="Task")
        return rolled_up_progress(parent, [self.subtask(p)
                                           for p in percentages])

    def test_a_checklist_reads_as_it_always_did(self):
        """Nothing but ticks and empty boxes, and the same answers."""
        for percentages in ([0, 0, 0, 0], [100, 0], [100, 100, 0, 0],
                            [100, 100], [100, 0, 0]):
            ticked = round(sum(1 for p in percentages if p >= 100)
                           / len(percentages) * 100)
            self.assertEqual(self.rolled(percentages), ticked,
                             f"{percentages} used to read {ticked}%")

    def test_a_part_finished_subtask_now_counts_for_its_part(self):
        """Which is the point of the change."""
        self.assertEqual(self.rolled([60, 0]), 30)
        self.assertEqual(self.rolled([25, 50, 75]), 50)

    def test_it_is_still_counted_rather_than_weighted(self):
        """
        A checklist is a checklist. Four sub-tasks of an hour each are four
        entries like any other four; length is the Phase's business, one
        level up.
        """
        from gantt_app.models import rolled_up_progress
        from datetime import timedelta

        short = Task(id="a", name="a", start_date=BASE,
                     end_date=BASE + timedelta(days=1),
                     task_type="Subtask", progress=100)
        long = Task(id="b", name="b", start_date=BASE,
                    end_date=BASE + timedelta(days=20),
                    task_type="Subtask", progress=0)
        parent = Task(id="T", name="t", start_date=BASE, end_date=BASE,
                      task_type="Task")

        self.assertEqual(rolled_up_progress(parent, [short, long]), 50)

    def test_it_carries_all_the_way_up_a_plan(self):
        """A sub-task at 60% reaches the phase above it."""
        project = Project(name="Plan")
        rows = (("001", "Preparation", "Phase", None, 0),
                ("003", "Implementation", "Task", "001", 0),
                ("004", "Goals", "Subtask", "003", 60),
                ("005", "Criteria", "Subtask", "003", 0),
                ("006", "Scope", "Subtask", "003", 100))
        for task_id, name, task_type, parent, progress in rows:
            project.add_task(Task(id=task_id, name=name, start_date=BASE,
                                  end_date=BASE, task_type=task_type,
                                  parent_task_id=parent, progress=progress))

        project.roll_up_summaries()

        for task_id in ("001", "003"):
            self.assertEqual(project.get_task_by_id(task_id).progress, 53)


if __name__ == '__main__':
    unittest.main()
