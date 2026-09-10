"""
Start/Finish No Later Than conflict detection and resolution (issue #28).

A No-Later-Than constraint was only weighed against a task's own direct
dependency links, so a task held past its date by its parent summary - or
sitting past it for any other reason - reported no conflict at all and the
Save-time dialog never appeared ("nothing happens"). Detection now reads
where the task actually lands, and the Remove Predecessors resolution drops
the links and pulls the task to the date it was given.
"""

import unittest
from datetime import datetime

from gantt_app.models import Project, Task, Dependency


class TestNoLaterThanDetection(unittest.TestCase):
    def _plan(self):
        return Project(name="P", start_date=datetime(2026, 10, 1))

    def test_a_task_sitting_past_its_snlt_conflicts_without_links(self):
        # The screenshot case: a task placed at 10-20 with no predecessors of
        # its own, told to start no later than 10-05.
        p = self._plan()
        t = Task(id="T", name="T", start_date=datetime(2026, 10, 20),
                 end_date=datetime(2026, 10, 21),
                 constraint_type="SNLT", constraint_date=datetime(2026, 10, 5))
        p.add_task(t)
        self.assertIsNotNone(p.constraint_conflict(t))
        self.assertIn("T", p.tasks_in_conflict())

    def test_a_child_held_by_its_summary_conflicts(self):
        p = self._plan()
        parent = Task(id="P1", name="Phase", start_date=datetime(2026, 10, 20),
                      end_date=datetime(2026, 10, 24), task_type="Phase")
        child = Task(id="C", name="Child", start_date=datetime(2026, 10, 20),
                     end_date=datetime(2026, 10, 21), parent_task_id="P1",
                     constraint_type="SNLT",
                     constraint_date=datetime(2026, 10, 5))
        p.add_task(parent)
        p.add_task(child)
        self.assertIsNotNone(p.constraint_conflict(child))

    def test_a_meetable_snlt_is_no_conflict(self):
        p = self._plan()
        t = Task(id="T", name="T", start_date=datetime(2026, 10, 5),
                 end_date=datetime(2026, 10, 6),
                 constraint_type="SNLT", constraint_date=datetime(2026, 10, 20))
        p.add_task(t)
        self.assertIsNone(p.constraint_conflict(t))

    def test_a_task_finishing_past_its_fnlt_conflicts(self):
        p = self._plan()
        t = Task(id="T", name="T", start_date=datetime(2026, 10, 19),
                 end_date=datetime(2026, 10, 23),
                 constraint_type="FNLT", constraint_date=datetime(2026, 10, 5))
        p.add_task(t)
        self.assertIsNotNone(p.constraint_conflict(t))

    def test_a_snet_floor_is_never_a_conflict(self):
        # The change must not touch the flexible floors.
        p = self._plan()
        t = Task(id="T", name="T", start_date=datetime(2026, 10, 20),
                 end_date=datetime(2026, 10, 21),
                 constraint_type="SNET", constraint_date=datetime(2026, 10, 5))
        p.add_task(t)
        self.assertIsNone(p.constraint_conflict(t))


class TestDatesMeetingConstraint(unittest.TestCase):
    def _plan(self):
        return Project(name="P", start_date=datetime(2026, 10, 1))

    def test_snlt_meeting_dates_are_on_or_before_the_date(self):
        p = self._plan()
        t = Task(id="T", name="T", start_date=datetime(2026, 10, 20),
                 end_date=datetime(2026, 10, 21),
                 constraint_type="SNLT", constraint_date=datetime(2026, 10, 5))
        p.add_task(t)
        start, end = p.dates_meeting_constraint(t)
        self.assertEqual(start, datetime(2026, 10, 5))   # a Monday
        self.assertLessEqual(start, datetime(2026, 10, 5))

    def test_a_weekend_snlt_lands_on_the_working_day_before_it(self):
        # 2026-10-04 is a Sunday: starting "no later than" it means the Friday.
        p = self._plan()
        t = Task(id="T", name="T", start_date=datetime(2026, 10, 20),
                 end_date=datetime(2026, 10, 21),
                 constraint_type="SNLT", constraint_date=datetime(2026, 10, 4))
        p.add_task(t)
        start, _end = p.dates_meeting_constraint(t)
        self.assertEqual(start, datetime(2026, 10, 2))   # the Friday before

    def test_fnlt_meeting_dates_fix_the_finish(self):
        p = self._plan()
        t = Task(id="T", name="T", start_date=datetime(2026, 10, 19),
                 end_date=datetime(2026, 10, 23),
                 constraint_type="FNLT", constraint_date=datetime(2026, 10, 6))
        p.add_task(t)
        _start, end = p.dates_meeting_constraint(t)
        self.assertEqual(end, datetime(2026, 10, 6))

    def test_other_constraints_have_no_meeting_dates(self):
        p = self._plan()
        t = Task(id="T", name="T", start_date=datetime(2026, 10, 20),
                 constraint_type="MSO", constraint_date=datetime(2026, 10, 5))
        p.add_task(t)
        self.assertEqual(p.dates_meeting_constraint(t), (None, None))


class TestRemovePredecessorsResolves(unittest.TestCase):
    def _linked_plan(self, ctype, cd):
        p = Project(name="P", start_date=datetime(2026, 10, 1))
        a = Task(id="A", name="A", start_date=datetime(2026, 10, 1),
                 end_date=datetime(2026, 10, 7))
        b = Task(id="B", name="B", start_date=datetime(2026, 10, 8),
                 end_date=datetime(2026, 10, 9),
                 dependencies=[Dependency(task_id="A", dep_type="FS",
                                          hardness="Hard")])
        p.add_task(a)
        p.add_task(b)
        p.reschedule()
        b.constraint_type = ctype
        b.constraint_date = cd
        return p, b

    def _remove(self, project, task):
        start, end = project.dates_meeting_constraint(task)
        task.dependencies = []
        if start is not None:
            task.start_date, task.end_date = start, end
        project.apply_schedule()

    def test_snlt_conflict_clears_after_removing_predecessors(self):
        p, b = self._linked_plan("SNLT", datetime(2026, 10, 2))
        self.assertIsNotNone(p.constraint_conflict(b))
        self._remove(p, b)
        self.assertIsNone(p.constraint_conflict(b))
        self.assertEqual(b.dependencies, [])
        self.assertEqual(b.start_date, datetime(2026, 10, 2))

    def test_fnlt_conflict_clears_after_removing_predecessors(self):
        p, b = self._linked_plan("FNLT", datetime(2026, 10, 5))
        self.assertIsNotNone(p.constraint_conflict(b))
        self._remove(p, b)
        self.assertIsNone(p.constraint_conflict(b))
        self.assertEqual(b.end_date, datetime(2026, 10, 5))


if __name__ == "__main__":
    unittest.main()
