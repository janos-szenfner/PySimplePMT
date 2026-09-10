"""
As Late As Possible actually moves a task now (issue #26).

The constraint used to be recorded and drawn but never scheduled - "nothing
happens". A leaf set As Late As Possible is now pushed to the latest finish
its collection and its successors allow: a child with nothing waiting on it
ends level with its summary, and one that a sibling waits for ends the working
day before that sibling starts.
"""

import unittest
from datetime import datetime, timedelta

from gantt_app.models import Project, Task, Dependency


def _sub(id, name, parent, start, end, dur=None, ctype='NA', deps=None):
    return Task(id=id, name=name, start_date=start, end_date=end,
                task_type="Subtask", parent_task_id=parent, duration=dur,
                constraint_type=ctype,
                dependencies=[Dependency(task_id=x, dep_type="FS",
                                         hardness="Hard") for x in (deps or [])])


class TestAlapUnderASummary(unittest.TestCase):
    def _plan(self):
        # A summary with an early ALAP child (A, no successor), a later chain
        # B -> C where B is ALAP and C waits for it. The summary is driven by
        # C, the latest.
        p = Project(name="P", start_date=datetime(2026, 9, 7))
        p.add_task(Task(id="S", name="Phase", start_date=datetime(2026, 9, 14),
                        end_date=datetime(2026, 9, 28), task_type="Subtask"))
        p.add_task(_sub("A", "feature1", "S", datetime(2026, 9, 14),
                        datetime(2026, 9, 16), dur=3, ctype='ALAP'))
        p.add_task(_sub("B", "feature3", "S", datetime(2026, 9, 21),
                        datetime(2026, 9, 25), dur=5, ctype='ALAP'))
        p.add_task(_sub("C", "feature2", "S", datetime(2026, 9, 28),
                        datetime(2026, 9, 28), dur=1, deps=["B"]))
        p.reschedule()
        return p

    def test_a_child_with_no_successor_ends_level_with_the_summary(self):
        p = self._plan()
        a = p.get_task_by_id("A")
        summary = p.get_task_by_id("S")
        self.assertEqual(a.end_date, summary.end_date)

    def test_a_child_a_sibling_waits_for_ends_before_that_sibling(self):
        p = self._plan()
        b = p.get_task_by_id("B")
        c = p.get_task_by_id("C")
        self.assertLess(b.end_date, c.start_date)
        # As late as it can be: the working day before C starts.
        self.assertEqual(b.end_date, p.calendar.get_previous_working_day(
            c.start_date - timedelta(days=1)))

    def test_the_alap_child_keeps_its_length(self):
        p = self._plan()
        a = p.get_task_by_id("A")
        self.assertEqual(p.working_duration(a), 3)

    def test_the_plan_settles(self):
        p = self._plan()
        self.assertFalse(p.reschedule())

    def test_alap_is_not_pulled_to_the_collection_start(self):
        # The summary has a predecessor, so a link-less child would normally
        # be aligned to the collection start (issue #25). ALAP overrides that.
        p = Project(name="P", start_date=datetime(2026, 9, 7))
        p.add_task(Task(id="M", name="Mock", start_date=datetime(2026, 9, 11),
                        end_date=datetime(2026, 9, 11)))
        p.add_task(Task(id="S", name="Phase", start_date=datetime(2026, 9, 14),
                        end_date=datetime(2026, 9, 28), task_type="Subtask",
                        dependencies=[Dependency(task_id="M", dep_type="FS",
                                                 hardness="Hard")]))
        p.add_task(_sub("A", "feature1", "S", datetime(2026, 9, 14),
                        datetime(2026, 9, 16), dur=3, ctype='ALAP'))
        p.add_task(_sub("C", "feature2", "S", datetime(2026, 9, 28),
                        datetime(2026, 9, 28), dur=1))
        p.reschedule()
        a = p.get_task_by_id("A")
        # Pulled to the summary end, not the collection start (09-14).
        self.assertEqual(a.end_date, p.get_task_by_id("S").end_date)
        self.assertGreater(a.start_date, datetime(2026, 9, 14))


class TestAlapEdges(unittest.TestCase):
    def test_the_latest_child_is_left_where_it_is(self):
        # An ALAP child that is already the last has nothing to slide against.
        p = Project(name="P", start_date=datetime(2026, 9, 7))
        p.add_task(Task(id="S", name="Phase", start_date=datetime(2026, 9, 14),
                        end_date=datetime(2026, 9, 25), task_type="Subtask"))
        p.add_task(_sub("A", "early", "S", datetime(2026, 9, 14),
                        datetime(2026, 9, 16), dur=3))
        last = _sub("B", "late", "S", datetime(2026, 9, 21),
                    datetime(2026, 9, 25), dur=5, ctype='ALAP')
        p.add_task(last)
        p.reschedule()
        self.assertEqual(p.get_task_by_id("B").end_date, datetime(2026, 9, 25))

    def test_a_top_level_alap_without_a_successor_stays_put(self):
        p = Project(name="P", start_date=datetime(2026, 9, 7))
        t = Task(id="T", name="T", start_date=datetime(2026, 9, 14),
                 end_date=datetime(2026, 9, 16), duration=3,
                 constraint_type='ALAP')
        p.add_task(t)
        p.reschedule()
        self.assertEqual(p.get_task_by_id("T").start_date, datetime(2026, 9, 14))

    def test_an_alap_milestone_is_pushed_later(self):
        p = Project(name="P", start_date=datetime(2026, 9, 7))
        p.add_task(Task(id="S", name="Phase", start_date=datetime(2026, 9, 14),
                        end_date=datetime(2026, 9, 25), task_type="Subtask"))
        p.add_task(_sub("A", "work", "S", datetime(2026, 9, 14),
                        datetime(2026, 9, 25), dur=9))
        p.add_task(Task(id="MS", name="gate", start_date=datetime(2026, 9, 14),
                        task_type="Milestone", parent_task_id="S",
                        constraint_type='ALAP'))
        p.reschedule()
        # It no longer sits at the front; it slides to the end of the work.
        moved = p.get_task_by_id("MS").start_date
        self.assertGreater(moved, datetime(2026, 9, 14))
        self.assertEqual(moved, p.get_task_by_id("S").end_date)


if __name__ == "__main__":
    unittest.main()
