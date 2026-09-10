"""
A dependency on a collection row drives the work inside it (issue #25).

Two faults were reported on the same plan:

  * A Task- or Subtask-typed row that had grown children never settled: the
    working-calendar pass rebuilt it from its stored duration while the
    roll-up rebuilt it from its children, and the two took turns for every
    pass of the reschedule loop.
  * A child with no link of its own sat wherever it had been placed, ignoring
    the predecessor set on the collection above it. The reporter expected the
    child to begin when the collection could.
"""

import logging
import unittest
from datetime import datetime

from gantt_app.models import Project, Task, Dependency


BASE = datetime(2026, 9, 14)  # a Monday


def _child(id, name, parent, start, end, dur=None, deps=None):
    return Task(id=id, name=name, start_date=start, end_date=end,
                task_type="Subtask", parent_task_id=parent, duration=dur,
                dependencies=[Dependency(task_id=x, dep_type="FS",
                                         hardness="Hard") for x in (deps or [])])


class TestATaskWithChildrenSettles(unittest.TestCase):
    """The convergence fault: a non-Phase summary and the calendar pass."""

    def _plan(self):
        p = Project(name="Conv", start_date=datetime(2026, 9, 7))
        # A "Task" (not a Phase) that has grown children, and carries a
        # stored duration of its own - the shape that used to oscillate.
        parent = Task(id="P", name="Phase", start_date=BASE,
                      end_date=datetime(2026, 9, 25), task_type="Task",
                      duration=10)
        p.add_task(parent)
        p.add_task(_child("A", "A", "P", BASE, datetime(2026, 9, 16), dur=3))
        p.add_task(_child("B", "B", "P", datetime(2026, 9, 21),
                          datetime(2026, 9, 25), dur=5))
        return p

    def test_it_settles_without_a_cycle_warning(self):
        p = self._plan()
        with self.assertLogs('gantt_app.models', level='WARNING') as caught:
            p.reschedule()
            logging.getLogger('gantt_app.models').warning("sentinel")
        self.assertEqual(
            [r for r in caught.output if 'did not settle' in r], [])

    def test_rescheduling_again_moves_nothing(self):
        p = self._plan()
        p.reschedule()
        self.assertFalse(p.reschedule())


class TestCollectionDependencyDrivesChildren(unittest.TestCase):
    """A predecessor on the collection reaches the work inside it."""

    def _plan(self):
        p = Project(name="Coll", start_date=datetime(2026, 9, 7))
        # UI Mockups ends Friday 09-11; the collection waits for it.
        p.add_task(Task(id="M", name="UI Mockups",
                        start_date=datetime(2026, 9, 11),
                        end_date=datetime(2026, 9, 11)))
        p.add_task(Task(id="UX", name="UX planning", start_date=BASE,
                        end_date=datetime(2026, 9, 28), task_type="Subtask",
                        dependencies=[Dependency(task_id="M", dep_type="FS",
                                                 hardness="Hard")]))
        # feature1 sits at the collection start; feature3 later with no link;
        # feature2 waits for feature3.
        p.add_task(_child("F1", "feature1", "UX", BASE,
                          datetime(2026, 9, 16), dur=3))
        p.add_task(_child("F3", "feature3", "UX", datetime(2026, 9, 21),
                          datetime(2026, 9, 25), dur=5))
        p.add_task(_child("F2", "feature2", "UX", datetime(2026, 9, 28),
                          datetime(2026, 9, 28), dur=1, deps=["F3"]))
        return p

    def test_a_link_less_child_starts_when_the_collection_can(self):
        p = self._plan()
        p.reschedule()
        ux = p.get_task_by_id("UX")
        f3 = p.get_task_by_id("F3")
        self.assertEqual(f3.start_date, ux.start_date)
        self.assertEqual(f3.start_date, datetime(2026, 9, 14))

    def test_the_collection_still_spans_its_children(self):
        p = self._plan()
        p.reschedule()
        ux = p.get_task_by_id("UX")
        kids = [p.get_task_by_id(i) for i in ("F1", "F3", "F2")]
        self.assertEqual(ux.start_date, min(k.start_date for k in kids))
        self.assertEqual(ux.end_date, max(k.end_date for k in kids))

    def test_a_child_with_its_own_link_is_not_pulled_to_the_start(self):
        p = self._plan()
        p.reschedule()
        f2 = p.get_task_by_id("F2")      # waits for F3
        self.assertNotEqual(f2.start_date, p.get_task_by_id("UX").start_date)

    def test_the_plan_is_stable(self):
        p = self._plan()
        p.reschedule()
        self.assertFalse(p.reschedule())


class TestScoping(unittest.TestCase):
    """The alignment reaches only the right rows."""

    def test_a_collection_without_a_predecessor_leaves_children_alone(self):
        p = Project(name="Free", start_date=datetime(2026, 9, 7))
        p.add_task(Task(id="G", name="Group", start_date=BASE,
                        end_date=datetime(2026, 9, 25), task_type="Subtask"))
        p.add_task(_child("X", "X", "G", BASE, datetime(2026, 9, 16), dur=3))
        late = _child("Y", "Y", "G", datetime(2026, 9, 21),
                      datetime(2026, 9, 25), dur=5)
        p.add_task(late)
        p.reschedule()
        # No predecessor on the collection, so nothing pulls Y forward.
        self.assertEqual(p.get_task_by_id("Y").start_date,
                         datetime(2026, 9, 21))

    def test_a_top_level_task_is_untouched(self):
        p = Project(name="Top", start_date=datetime(2026, 9, 7))
        p.add_task(Task(id="T", name="T", start_date=datetime(2026, 9, 21),
                        end_date=datetime(2026, 9, 25)))
        p.reschedule()
        self.assertEqual(p.get_task_by_id("T").start_date,
                         datetime(2026, 9, 21))

    def test_a_child_follows_the_nearest_constrained_ancestor(self):
        # Outer phase waits for M (ends 09-11 -> 09-14); an inner sub-phase
        # waits for a later task, so its link-less child follows the inner one.
        p = Project(name="Nested", start_date=datetime(2026, 9, 7))
        p.add_task(Task(id="M", name="M", start_date=datetime(2026, 9, 11),
                        end_date=datetime(2026, 9, 11)))
        p.add_task(Task(id="G", name="Gate", start_date=datetime(2026, 9, 18),
                        end_date=datetime(2026, 9, 18)))
        p.add_task(Task(id="OUT", name="Outer", start_date=BASE,
                        end_date=datetime(2026, 9, 28), task_type="Subtask",
                        dependencies=[Dependency(task_id="M", dep_type="FS",
                                                 hardness="Hard")]))
        p.add_task(Task(id="IN", name="Inner", start_date=datetime(2026, 9, 21),
                        end_date=datetime(2026, 9, 28), task_type="Subtask",
                        parent_task_id="OUT",
                        dependencies=[Dependency(task_id="G", dep_type="FS",
                                                 hardness="Hard")]))
        p.add_task(_child("K", "K", "IN", datetime(2026, 9, 25),
                          datetime(2026, 9, 28), dur=2))
        p.reschedule()
        # K follows Inner (its nearest constrained ancestor), which waits for
        # G ending 09-18 -> starts 09-21, not the outer phase's 09-14.
        self.assertEqual(p.get_task_by_id("K").start_date,
                         p.get_task_by_id("IN").start_date)
        self.assertEqual(p.get_task_by_id("K").start_date,
                         datetime(2026, 9, 21))


if __name__ == "__main__":
    unittest.main()
