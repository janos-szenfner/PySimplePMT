"""
Tests for the completion a parent takes from the work under it.

WHY THIS MODULE EXISTS:
======================
Each level of the plan counts what is under it differently - a Task counts
its sub-tasks' percentages, a Deliverable weights its tasks by how long they run, a
Phase averages its deliverables evenly - and which rule is applied to what is
the sort of thing that is quietly wrong for a long time. The rules are set
out in models.rolled_up_progress; these are the same rules, written as
arithmetic somebody can check.

DEVELOPMENT NOTES:
------------------
No display is needed: this is the model, and none of it draws anything.
"""

import unittest
from datetime import datetime, timedelta

from gantt_app.models import Project, Task, rolled_up_progress


def task(task_id, task_type, progress=0, days=1, parent=None,
         start=datetime(2026, 1, 1)):
    """A task of a given type, length and progress."""
    return Task(
        id=task_id, name=task_id, task_type=task_type, progress=progress,
        start_date=start, end_date=start + timedelta(days=days - 1),
        parent_task_id=parent,
    )


class TestASubtaskIsATick(unittest.TestCase):
    """A sub-task is done or it is not."""

    def test_a_full_subtask_counts_as_done(self):
        """100% is the ticked state."""
        self.assertTrue(task("S", "Subtask", progress=100).is_completed)

    def test_an_empty_subtask_does_not(self):
        """0% is the unticked one."""
        self.assertFalse(task("S", "Subtask", progress=0).is_completed)

    def test_a_part_finished_subtask_does_not_count_as_done(self):
        """
        Anything short of 100 is unfinished.

        Nothing on the form can produce this - a sub-task is entered with a
        tick box - but an imported file can carry it, and a job half done is
        not a job done.
        """
        self.assertFalse(task("S", "Subtask", progress=60).is_completed)


class TestATaskCountsItsSubtasks(unittest.TestCase):
    """
    A Task with sub-tasks averages their percentages.

    Which is what counting ticks was: these all hold 0 or 100, and the
    average of those is the proportion ticked. They read the same answers
    now as they did then, which is the point of them.
    """

    def test_none_done(self):
        """Nothing ticked is nothing done."""
        parent = task("T", "Task")
        children = [task("S1", "Subtask"), task("S2", "Subtask")]

        self.assertEqual(rolled_up_progress(parent, children), 0)

    def test_half_done(self):
        """One of two ticked is half."""
        parent = task("T", "Task")
        children = [task("S1", "Subtask", progress=100),
                    task("S2", "Subtask")]

        self.assertEqual(rolled_up_progress(parent, children), 50)

    def test_all_done(self):
        """Every box ticked is finished."""
        parent = task("T", "Task")
        children = [task("S1", "Subtask", progress=100),
                    task("S2", "Subtask", progress=100)]

        self.assertEqual(rolled_up_progress(parent, children), 100)

    def test_length_does_not_come_into_it(self):
        """
        A checklist is counted, not weighted.

        Four sub-tasks of an hour each are four boxes like any other four,
        so a ticked short one counts the same as a ticked long one.
        """
        parent = task("T", "Task")
        children = [task("S1", "Subtask", progress=100, days=1),
                    task("S2", "Subtask", progress=0, days=99)]

        self.assertEqual(rolled_up_progress(parent, children), 50)

    def test_a_third_rounds_to_a_whole_percent(self):
        """One of three is 33, not 33.3."""
        parent = task("T", "Task")
        children = [task("S1", "Subtask", progress=100),
                    task("S2", "Subtask"), task("S3", "Subtask")]

        self.assertEqual(rolled_up_progress(parent, children), 33)


class TestADeliverableWeightsByDuration(unittest.TestCase):
    """A long task counts for more of its deliverable than a short one."""

    def test_it_weights_by_days(self):
        """Ten finished days of thirty is a third of the way through."""
        parent = task("D", "Deliverable")
        children = [task("T1", "Task", progress=100, days=10),
                    task("T2", "Task", progress=0, days=20)]

        self.assertEqual(rolled_up_progress(parent, children), 33)

    def test_part_finished_tasks_count_for_their_part(self):
        """Half of a fortnight is a week's worth."""
        parent = task("D", "Deliverable")
        children = [task("T1", "Task", progress=50, days=14),
                    task("T2", "Task", progress=0, days=14)]

        self.assertEqual(rolled_up_progress(parent, children), 25)

    def test_zero_length_children_are_averaged_instead(self):
        """
        With nothing to weight by, the tasks are averaged.

        A deliverable holding only milestones has no days in it, and
        dividing by that total would be dividing by nothing.
        """
        parent = task("D", "Deliverable")
        children = [task("M1", "Milestone", progress=100),
                    task("M2", "Milestone", progress=0)]

        self.assertEqual(rolled_up_progress(parent, children), 50)


class TestAPhaseAveragesItsDeliverables(unittest.TestCase):
    """Deliverables count evenly towards the phase holding them."""

    def test_it_averages_them(self):
        """Two deliverables, one done, is half the phase."""
        parent = task("P", "Phase")
        children = [task("D1", "Deliverable", progress=100, days=1),
                    task("D2", "Deliverable", progress=0, days=1)]

        self.assertEqual(rolled_up_progress(parent, children), 50)

    def test_length_does_not_come_into_it(self):
        """
        A longer deliverable is not a larger share of the phase.

        Deliverables are the units a phase is scoped in; the same two at
        100% and 0% make half a phase however long either runs.
        """
        parent = task("P", "Phase")
        children = [task("D1", "Deliverable", progress=100, days=2),
                    task("D2", "Deliverable", progress=0, days=200)]

        self.assertEqual(rolled_up_progress(parent, children), 50)


class TestEmptyAndOutOfRange(unittest.TestCase):
    """What the rules do with nothing, and with nonsense."""

    def test_a_container_with_nothing_in_it_is_nothing_done(self):
        """No work under it, none of it done."""
        self.assertEqual(rolled_up_progress(task("P", "Phase"), []), 0)
        self.assertEqual(rolled_up_progress(task("D", "Deliverable"), []), 0)

    def test_a_percentage_over_a_hundred_is_clamped(self):
        """
        A child outside 0 to 100 does not carry its parent outside it.

        Task rejects such a value on the way in, so this is set past it -
        which is the only way one arrives, an imported file having been read
        into a task that was already built.
        """
        parent = task("D", "Deliverable")
        child = task("T1", "Task", days=1)
        child.progress = 400

        self.assertEqual(rolled_up_progress(parent, [child]), 100)

    def test_a_negative_percentage_is_clamped(self):
        """Nor below it."""
        parent = task("D", "Deliverable")
        child = task("T1", "Task", days=1)
        child.progress = -50

        self.assertEqual(rolled_up_progress(parent, [child]), 0)


class TestTheWholeCascade(unittest.TestCase):
    """A tick on a sub-task reaches the phase above it in one pass."""

    def setUp(self):
        """A phase over two deliverables, over tasks, over sub-tasks."""
        self.project = Project(name="Test Project")
        base = datetime(2026, 1, 1)

        self.project.add_task(task("P", "Phase", start=base))
        self.project.add_task(task("D1", "Deliverable", parent="P", start=base))
        self.project.add_task(task("D2", "Deliverable", parent="P", start=base))

        # D1 holds one task of ten days, itself holding two sub-tasks
        self.project.add_task(task("T1", "Task", parent="D1", days=10,
                                   start=base))
        self.project.add_task(task("S1", "Subtask", parent="T1", start=base))
        self.project.add_task(task("S2", "Subtask", parent="T1", start=base))

        # D2 holds one task of ten days with no sub-tasks, half done
        self.project.add_task(task("T2", "Task", parent="D2", days=10,
                                   progress=40, start=base))

    def of(self, task_id):
        """The progress of one task after a reschedule."""
        return self.project.get_task_by_id(task_id).progress

    def test_a_ticked_subtask_reaches_the_phase(self):
        """One of two sub-tasks ticked carries all the way up."""
        self.project.get_task_by_id("S1").progress = 100

        self.project.reschedule()

        self.assertEqual(self.of("T1"), 50)     # one of two boxes ticked
        self.assertEqual(self.of("D1"), 50)     # its only task, so all of it
        self.assertEqual(self.of("D2"), 40)     # T2's own percentage
        self.assertEqual(self.of("P"), 45)      # the two averaged evenly

    def test_untucking_it_again_carries_back_up(self):
        """The cascade runs on the way down as well as up."""
        self.project.get_task_by_id("S1").progress = 100
        self.project.reschedule()

        self.project.get_task_by_id("S1").progress = 0
        self.project.reschedule()

        self.assertEqual(self.of("T1"), 0)
        self.assertEqual(self.of("D1"), 0)
        self.assertEqual(self.of("P"), 20)      # 0 and 40, averaged

    def test_a_task_without_subtasks_keeps_what_was_typed_on_it(self):
        """Nothing underneath it means nothing to overrule it."""
        self.project.reschedule()

        self.assertEqual(self.of("T2"), 40)


if __name__ == '__main__':
    unittest.main()
