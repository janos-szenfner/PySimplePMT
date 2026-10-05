"""
Issue #89: Update Project - reschedule uncompleted work behind a line.

The status date is only a marker; this is the action that catches the
plan up to it, the way Microsoft Project's Update Project window does.
Only its 'Reschedule uncompleted work' half exists - marking work
complete is Mark on Track's job - and it runs over the whole plan.
"""
import unittest
from datetime import datetime, timedelta

from gantt_app.core.models import Dependency, Project, Task


def _task(task_id, name, start, end, progress=0, **kwargs):
    return Task(id=task_id, name=name, task_type="Task",
                start_date=start, end_date=end, progress=progress,
                **kwargs)


class TestRescheduleUncompletedWork(unittest.TestCase):
    """
    The three answers: unstarted rows move onto the line, underway rows
    already behind it push their remaining work past it, and everything
    else stays.
    """

    def setUp(self):
        self.line = datetime(2026, 1, 15)          # a Thursday
        self.project = Project(name="Plan")

    def _add(self, *args, **kwargs):
        task = _task(*args, **kwargs)
        self.project.add_task(task)
        return task

    def test_an_unstarted_task_begins_on_the_line(self):
        task = self._add("A", "Planned", datetime(2026, 1, 5),
                         datetime(2026, 1, 9))
        self.assertEqual(
            self.project.reschedule_uncompleted_work(self.line), 1)
        self.assertEqual(task.start_date.date(), datetime(2026, 1, 15).date())

    def test_the_task_keeps_its_working_duration(self):
        """Five working days from Thursday is next Wednesday."""
        task = self._add("A", "Planned", datetime(2026, 1, 5),
                         datetime(2026, 1, 9))
        self.project.reschedule_uncompleted_work(self.line)
        self.assertEqual(task.end_date.date(), datetime(2026, 1, 21).date())

    def test_a_task_already_past_the_line_stays(self):
        task = self._add("A", "Later", datetime(2026, 2, 2),
                         datetime(2026, 2, 6))
        self.assertEqual(
            self.project.reschedule_uncompleted_work(self.line), 0)
        self.assertEqual(task.start_date.date(), datetime(2026, 2, 2).date())

    def test_the_line_on_a_weekend_resumes_on_monday(self):
        """The row begins on the next working day, not on a Saturday."""
        task = self._add("A", "Planned", datetime(2026, 1, 5),
                         datetime(2026, 1, 9))
        self.project.reschedule_uncompleted_work(datetime(2026, 1, 17))
        self.assertEqual(task.start_date.date(), datetime(2026, 1, 19).date())

    def test_an_unstarted_milestone_moves_to_the_line(self):
        milestone = Task.create_milestone("Kick", datetime(2026, 1, 8),
                                          task_id="M")
        self.project.add_task(milestone)
        self.assertEqual(
            self.project.reschedule_uncompleted_work(self.line), 1)
        self.assertEqual(milestone.start_date.date(),
                         datetime(2026, 1, 15).date())

    def test_an_overdue_underway_task_pushes_its_remainder(self):
        """
        Half of a five-day task is still to do, so two working days of it
        resume on the line - the worked part keeps its dates in the past.
        """
        task = self._add("A", "Late", datetime(2026, 1, 5),
                         datetime(2026, 1, 9), progress=50)
        self.assertEqual(
            self.project.reschedule_uncompleted_work(self.line), 1)
        self.assertEqual(task.start_date.date(), datetime(2026, 1, 5).date())
        self.assertEqual(task.end_date.date(), datetime(2026, 1, 16).date())

    def test_an_underway_task_running_through_the_line_stays(self):
        task = self._add("A", "Running", datetime(2026, 1, 12),
                         datetime(2026, 1, 30), progress=50)
        self.assertEqual(
            self.project.reschedule_uncompleted_work(self.line), 0)
        self.assertEqual(task.end_date.date(), datetime(2026, 1, 30).date())

    def test_done_inactive_and_pinned_rows_stay(self):
        done = self._add("D", "Done", datetime(2026, 1, 5),
                         datetime(2026, 1, 9), progress=100)
        shelved = self._add("F", "Shelved", datetime(2026, 1, 5),
                            datetime(2026, 1, 9), status='Inactive')
        pinned = self._add("G", "Pinned", datetime(2026, 1, 5),
                           datetime(2026, 1, 9), constraint_type='MSO',
                           constraint_date=datetime(2026, 1, 5))
        self.assertEqual(
            self.project.reschedule_uncompleted_work(self.line), 0)
        for task in (done, shelved, pinned):
            self.assertEqual(task.start_date.date(),
                             datetime(2026, 1, 5).date())

    def test_summaries_follow_their_children(self):
        """A container is never moved directly - its dates are its
        children's, rolled up after they move."""
        phase = Task.create_phase("Phase", datetime(2026, 1, 5),
                                  datetime(2026, 1, 30), task_id="P")
        self.project.add_task(phase)
        child = self._add("A", "Inside", datetime(2026, 1, 5),
                          datetime(2026, 1, 9), parent_task_id="P")
        self.project.reschedule_uncompleted_work(self.line)
        self.assertEqual(phase.start_date.date(),
                         child.start_date.date())

    def test_successors_settle_after_the_move(self):
        """A task pushed past the line drags the links waiting on it."""
        first = self._add("A", "First", datetime(2026, 1, 5),
                          datetime(2026, 1, 9))
        second = self._add("B", "Second", datetime(2026, 1, 12),
                           datetime(2026, 1, 14),
                           dependencies=[Dependency(task_id="A")])
        self.project.reschedule_uncompleted_work(self.line)
        self.assertGreater(second.start_date, first.end_date)

    def test_nothing_to_move_returns_zero(self):
        self._add("A", "Later", datetime(2026, 2, 2), datetime(2026, 2, 6))
        self.assertEqual(
            self.project.reschedule_uncompleted_work(self.line), 0)


if __name__ == '__main__':
    unittest.main()
