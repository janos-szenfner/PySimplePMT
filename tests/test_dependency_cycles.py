"""
Circular links through the roll-up, and links obeyed when they are typed
(issue #47).

WHY THIS MODULE EXISTS:
======================
Two faults were reported on the same plan:

  * A link typed into the Dependencies column as "7SS" - or "7FF", "7SF" -
    changed nothing: the pass that settles the plan only ever moves a task
    later, so a link whose required date was earlier than where the task
    sat was silently not applied. A link just typed is meant to be obeyed,
    so the column edit now settles the plan without the forward-only rule.

  * A link added in the task dialog sent a summary row's duration past two
    thousand days and wrecked the chart. The link closed a loop the cycle
    check could not see: the check walked dependency edges only, but a row
    that holds work takes its dates from the rows inside it, so waiting on
    anything that waits on one of those - or on the parent itself - is
    circular all the same. Each pass moved the task past the end the
    summary had just rolled up, the summary followed, and the loop never
    settled.
"""

import unittest
from datetime import datetime, timedelta

from gantt_app.core.models import Dependency, Project, Task


BASE = datetime(2026, 9, 14)  # a Monday


def _task(id, name, start, end, dur=None, parent=None, deps=None):
    """A subtask-shaped row, the shape the report's plan was built from."""
    return Task(id=id, name=name, start_date=start, end_date=end,
                task_type="Subtask", parent_task_id=parent, duration=dur,
                dependencies=[Dependency(x, dep_type, "Hard")
                              for x, dep_type in (deps or [])])


def _plan():
    """
    The report's plan, simplified.

    A phase holds a summary, the summary holds the linked leaf, and a chain
    hangs off the phase - so a link from the leaf to anywhere on the chain
    runs in a circle through the roll-up, whatever the type.
    """
    p = Project(name="P", start_date=datetime(2026, 9, 7))
    p.add_task(Task(id="P1", name="Phase", task_type="Phase",
                    start_date=datetime(2026, 9, 7),
                    end_date=datetime(2026, 11, 27)))
    p.add_task(_task("M", "Mockups", datetime(2026, 9, 11),
                     datetime(2026, 9, 11), dur=1, parent="P1"))
    p.add_task(_task("UX", "UX planning", BASE, datetime(2026, 11, 27),
                     parent="P1", deps=[("M", "FS")]))
    p.add_task(_task("F1", "feature1", BASE, datetime(2026, 10, 23),
                     dur=30, parent="UX"))
    p.add_task(_task("F3", "feature3", BASE, datetime(2026, 10, 23),
                     dur=30, parent="UX"))
    p.add_task(_task("F2", "feature2", datetime(2026, 10, 26),
                     datetime(2026, 11, 23), dur=21, parent="UX",
                     deps=[("F3", "FS")]))
    start = datetime(2026, 11, 30)
    for tid, dep in (("I", "P1"), ("DR", "I"), ("T3", "DR"),
                     ("TE", "T3"), ("DE", "TE")):
        end = start + timedelta(days=13)
        p.add_task(Task(id=tid, name=tid, start_date=start, end_date=end,
                        duration=10,
                        dependencies=[Dependency(dep, "FS", "Hard")]))
        start = end + timedelta(days=3)
    return p


class TestALoopThroughTheRollUpIsSeen(unittest.TestCase):
    """The cycle check follows containment, not only the links."""

    def test_a_child_depending_on_its_parent_is_circular(self):
        """
        The parent's dates are the children's; a child that waits on it
        waits on itself.
        """
        p = _plan()
        self.assertTrue(p.would_create_dependency_cycle("F2", "UX"))

    def test_a_child_depending_on_a_higher_ancestor_is_circular(self):
        p = _plan()
        self.assertTrue(p.would_create_dependency_cycle("F2", "P1"))

    def test_a_link_to_a_task_that_waits_on_the_branch_is_circular(self):
        """
        The reported case: an SF link from the leaf to a task downstream of
        the phase, which waits on the phase, which takes its dates from the
        leaf. Every reschedule grew the summary by another span.
        """
        p = _plan()
        self.assertTrue(p.would_create_dependency_cycle("F2", "T3"))

    def test_a_summary_depending_on_its_descendant_is_circular(self):
        """The other way round, caught before this change and still."""
        p = _plan()
        self.assertTrue(p.would_create_dependency_cycle("UX", "F2"))

    def test_a_leaf_depending_on_a_summary_that_waits_on_it(self):
        """
        A link to a summary one of whose children waits on the leaf: the
        summary's dates are the child's, which are the leaf's.
        """
        p = Project(name="Loop", start_date=BASE)
        p.add_task(Task(id="L", name="Leaf", start_date=BASE,
                        end_date=datetime(2026, 9, 16)))
        p.add_task(Task(id="S", name="Summary", task_type="Phase",
                        start_date=BASE, end_date=datetime(2026, 9, 25)))
        p.add_task(_task("C", "Child", BASE, datetime(2026, 9, 16),
                         parent="S", deps=[("L", "FS")]))
        self.assertTrue(p.would_create_dependency_cycle("L", "S"))

    def test_an_ordinary_link_is_still_allowed(self):
        """A sibling waits on nothing the leaf feeds."""
        p = _plan()
        self.assertFalse(p.would_create_dependency_cycle("F1", "F3"))

    def test_a_link_to_a_summary_outside_the_branch_is_allowed(self):
        """
        Linking to a summary is legitimate when the summary does not hold
        the task - the rule is circles, not summary rows.
        """
        p = _plan()
        self.assertFalse(p.would_create_dependency_cycle("T3", "P1"))


class TestTheColumnRefusesTheLoop(unittest.TestCase):
    """parse_dependencies says why, in the column's own words."""

    def test_a_parents_number_is_refused(self):
        p = _plan()
        number = p.display_ids()["UX"]

        links, errors = p.parse_dependencies("F2", str(number))

        self.assertEqual(links, [])
        self.assertIn("holds this task inside it", errors[0])

    def test_a_descendants_number_is_refused(self):
        p = _plan()
        number = p.display_ids()["F2"]

        links, errors = p.parse_dependencies("UX", str(number))

        self.assertEqual(links, [])
        self.assertIn("holds task", errors[0])

    def test_a_downstream_number_is_refused(self):
        p = _plan()
        number = p.display_ids()["T3"]

        links, errors = p.parse_dependencies("F2", f"{number}SF")

        self.assertEqual(links, [])
        self.assertIn("circle", errors[0])

    def test_the_summary_stays_its_own_size(self):
        """
        The refused link is the one that sent the collector's duration past
        two thousand days: with it refused, the plan still settles.
        """
        p = _plan()
        p.reschedule()
        ux = p.get_task_by_id("UX")
        self.assertLess(
            p.calendar.working_days_between(ux.start_date, ux.end_date),
            500)
        self.assertFalse(p.reschedule())


class TestATypedLinkIsObeyed(unittest.TestCase):
    """A link just stated moves the task, even when that means earlier."""

    def setUp(self):
        """feature2 sits after feature3, waiting on it Finish-to-Start."""
        self.p = _plan()
        self.p.reschedule()
        self.f2 = self.p.get_task_by_id("F2")
        self.f3 = self.p.get_task_by_id("F3")

    def _set(self, dep_type):
        """What set_dependencies does with a cell that was just typed."""
        self.f2.dependencies = [Dependency("F3", dep_type, "Hard")]
        self.p.apply_schedule(forward_only=False)

    def test_start_start_pulls_the_task_to_the_predecessors_start(self):
        self._set("SS")
        self.assertEqual(self.f2.start_date.date(), self.f3.start_date.date())

    def test_finish_finish_holds_the_tasks_end(self):
        self._set("FF")
        self.assertEqual(self.f2.end_date.date(), self.f3.end_date.date())

    def test_start_finish_holds_the_tasks_end_at_the_start(self):
        self._set("SF")
        self.assertEqual(self.f2.end_date.date(), self.f3.start_date.date())

    def test_the_automatic_pass_still_keeps_deliberate_slack(self):
        """
        The forward-only rule is untouched for the pass nobody asked for:
        re-settling the plan does not close a gap a planner left.
        """
        self._set("SS")
        self.f2.start_date = datetime(2026, 10, 26)
        self.f2.end_date = datetime(2026, 11, 23)
        self.f2.dependencies = [Dependency("F3", "SS", "Rubber")]

        self.p.reschedule()

        self.assertEqual(self.f2.start_date, datetime(2026, 10, 26))


if __name__ == "__main__":
    unittest.main()
