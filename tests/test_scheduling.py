"""
Tests for the dependency types, lead/lag and automatic scheduling.

DEVELOPMENT NOTES:
------------------
Everything here goes against Project directly, so none of it needs a display.
The four types split into two groups - FS and SS place a task's start, FF and
SF its finish - which is why constrained_dates returns a pair rather than the
single start date the model used to work with.
"""

import unittest
from datetime import datetime, timedelta

from gantt_app.models import (
    Dependency, Project, Task,
    DEPENDENCY_TYPES, DEPENDENCY_TYPE_LABELS,
)


class DependencyTestCase(unittest.TestCase):
    """Shared fixture: a predecessor running 1-5 January and a successor."""

    def setUp(self):
        """Two tasks, unlinked."""
        self.project = Project(name="Test Project")
        self.first = Task(id="A", name="First",
                          start_date=datetime(2026, 1, 1),
                          end_date=datetime(2026, 1, 5))
        self.second = Task(id="B", name="Second",
                           start_date=datetime(2026, 1, 1),
                           end_date=datetime(2026, 1, 3))
        self.project.add_task(self.first)
        self.project.add_task(self.second)

    def link(self, dep_type, hardness='Hard', lag=0):
        """Link the successor to the predecessor and apply the constraint."""
        self.second.dependencies = []
        self.second.add_dependency("A", dep_type, hardness, lag)
        self.project.apply_dependency_constraints(self.second)


class TestDependencyTypes(DependencyTestCase):
    """Each of the four types places the successor where it should."""

    def test_finish_to_start_follows_the_predecessor(self):
        """FS starts the day after the predecessor's inclusive end."""
        self.link('FS')

        self.assertEqual(self.second.start_date, datetime(2026, 1, 6))

    def test_start_to_start_aligns_the_starts(self):
        """SS starts with the predecessor."""
        self.link('SS')

        self.assertEqual(self.second.start_date, datetime(2026, 1, 1))

    def test_finish_to_finish_aligns_the_finishes(self):
        """FF finishes with the predecessor."""
        self.link('FF')

        self.assertEqual(self.second.end_date, datetime(2026, 1, 5))

    def test_start_to_finish_ends_at_the_predecessor_start(self):
        """SF finishes once the predecessor has started."""
        self.link('SF')

        self.assertEqual(self.second.end_date, datetime(2026, 1, 1))

    def test_duration_is_preserved(self):
        """Moving a task keeps its length."""
        original = self.second.end_date - self.second.start_date

        self.link('FS')

        self.assertEqual(self.second.end_date - self.second.start_date,
                         original)

    def test_every_type_is_supported(self):
        """All four codes round-trip through a Dependency."""
        for dep_type in DEPENDENCY_TYPES:
            self.assertEqual(Dependency("A", dep_type).dep_type, dep_type)

    def test_an_unknown_type_falls_back_to_finish_start(self):
        """A code from a newer file does not break the link."""
        self.assertEqual(Dependency("A", 'ZZ').dep_type, 'FS')

    def test_the_labels_cover_every_type(self):
        """Each type has a label for the dialog."""
        self.assertEqual(set(DEPENDENCY_TYPE_LABELS), set(DEPENDENCY_TYPES))

    def test_only_the_finish_types_constrain_the_finish(self):
        """FF and SF hold the finish; FS and SS hold the start."""
        holds = {t: Dependency("A", t).constrains_finish
                 for t in DEPENDENCY_TYPES}

        self.assertEqual(holds, {'FS': False, 'SS': False,
                                 'FF': True, 'SF': True})


class TestLagAndLead(DependencyTestCase):
    """Lag delays the successor; a negative lag lets it overlap."""

    def test_lag_delays_the_successor(self):
        """A positive lag pushes the start out."""
        self.link('FS', lag=3)

        self.assertEqual(self.second.start_date, datetime(2026, 1, 9))

    def test_lead_pulls_the_successor_in(self):
        """A negative lag is lead time, compressing the schedule."""
        self.link('FS', lag=-2)

        self.assertEqual(self.second.start_date, datetime(2026, 1, 4))

    def test_lag_applies_to_a_finish_link(self):
        """FF with lag finishes that many days after the predecessor."""
        self.link('FF', lag=4)

        self.assertEqual(self.second.end_date, datetime(2026, 1, 9))

    def test_lag_defaults_to_none(self):
        """A link with no lag stated has none."""
        self.assertEqual(Dependency("A").lag, 0)

    def test_a_bad_lag_is_treated_as_zero(self):
        """Junk from a file does not break loading."""
        self.assertEqual(Dependency("A", 'FS', 'Hard', 'nonsense').lag, 0)

    def test_lag_survives_serialisation(self):
        """Saving and loading keeps the lag."""
        link = Dependency("A", 'FS', 'Hard', 5)

        self.assertEqual(Dependency.from_any(link.to_dict()).lag, 5)


class TestHardness(DependencyTestCase):
    """Hard pins the date; Rubber is only a floor."""

    def test_hard_pulls_a_late_task_back(self):
        """A hard link fixes the date exactly, earlier or later."""
        self.second.start_date = datetime(2026, 3, 1)
        self.second.end_date = datetime(2026, 3, 3)

        self.link('FS', hardness='Hard')

        self.assertEqual(self.second.start_date, datetime(2026, 1, 6))

    def test_rubber_leaves_a_later_task_alone(self):
        """A rubber link only forbids being earlier."""
        self.second.start_date = datetime(2026, 3, 1)
        self.second.end_date = datetime(2026, 3, 3)

        self.link('FS', hardness='Rubber')

        self.assertEqual(self.second.start_date, datetime(2026, 3, 1))

    def test_rubber_still_pushes_an_early_task_out(self):
        """A rubber link is a floor, so it moves a task that starts too soon."""
        self.link('FS', hardness='Rubber')

        self.assertEqual(self.second.start_date, datetime(2026, 1, 6))


class TestMilestonePredecessor(DependencyTestCase):
    """A milestone marks a moment rather than occupying a day."""

    def setUp(self):
        """Replace the predecessor with a milestone."""
        super().setUp()
        self.first.is_milestone = True
        self.first.end_date = None
        self.first.start_date = datetime(2026, 1, 15)

    def test_finish_start_lands_on_the_milestone_date(self):
        """
        A task after a milestone starts on the milestone's own day.

        The inclusive-end rule adds a day to a real task's finish, because it
        occupies that whole day. A milestone takes no time, so adding a day
        would leave a gap that is not there.
        """
        self.link('FS')

        self.assertEqual(self.second.start_date, datetime(2026, 1, 15))

    def test_start_start_lands_on_the_milestone_date(self):
        """SS behaves the same for a zero-duration predecessor."""
        self.link('SS')

        self.assertEqual(self.second.start_date, datetime(2026, 1, 15))


class TestAutoScheduling(unittest.TestCase):
    """Moving a predecessor drags everything that follows it."""

    def setUp(self):
        """A chain of three tasks linked Finish-Start."""
        self.project = Project(name="Test Project")
        previous = None
        for name in ("A", "B", "C"):
            task = Task(id=name, name=name,
                        start_date=datetime(2026, 1, 1),
                        end_date=datetime(2026, 1, 3))
            if previous:
                task.add_dependency(previous, 'FS', 'Hard')
            self.project.add_task(task)
            previous = name
        self.project.reschedule()

    def starts(self):
        """Start date of each task by ID."""
        return {t.id: t.start_date for t in self.project.tasks}

    def test_the_chain_settles(self):
        """Each task follows the one before it."""
        self.assertEqual(self.starts(), {
            "A": datetime(2026, 1, 1),
            "B": datetime(2026, 1, 4),
            "C": datetime(2026, 1, 7),
        })

    def test_moving_the_head_moves_everything(self):
        """
        The whole chain shifts when its first task does.

        Links used to be applied only when one was created, so moving a
        predecessor afterwards left everything downstream where it was.
        """
        head = self.project.get_task_by_id("A")
        head.start_date = datetime(2026, 2, 1)
        head.end_date = datetime(2026, 2, 3)

        self.project.reschedule()

        self.assertEqual(self.starts(), {
            "A": datetime(2026, 2, 1),
            "B": datetime(2026, 2, 4),
            "C": datetime(2026, 2, 7),
        })

    def test_a_settled_plan_does_not_move(self):
        """Rescheduling twice changes nothing the second time."""
        self.assertFalse(self.project.reschedule())

    def test_a_cycle_does_not_hang(self):
        """
        Mutually dependent tasks stop rather than looping.

        The pass repeats until nothing moves, so a cycle would never settle
        without the iteration cap.
        """
        project = Project(name="Cyclic")
        first = Task(id="X", name="X", start_date=datetime(2026, 1, 1),
                     end_date=datetime(2026, 1, 2))
        second = Task(id="Y", name="Y", start_date=datetime(2026, 1, 1),
                      end_date=datetime(2026, 1, 2))
        first.add_dependency("Y", 'FS', 'Hard')
        second.add_dependency("X", 'FS', 'Hard')
        project.add_task(first)
        project.add_task(second)

        project.reschedule()          # must return

        self.assertEqual(len(project.tasks), 2)

    def test_a_missing_predecessor_is_ignored(self):
        """A link to a deleted task does not stop the rest scheduling."""
        self.project.get_task_by_id("B").add_dependency("gone", 'FS', 'Hard')

        self.project.reschedule()

        self.assertEqual(self.starts()["C"], datetime(2026, 1, 7))


class TestAutomaticPassOnlyMovesForward(unittest.TestCase):
    """
    Rescheduling repairs violations without closing deliberate gaps.

    DEVELOPMENT NOTES:
    ------------------
    A hard link pins a date exactly, which is right when the user has just
    chosen a predecessor and wrong to apply unasked to a whole plan. An
    imported GanttProject file is the clearest case: its dates come from
    replaying the file's working-day calendar, so a task sits after a
    weekend, and pinning it to the day after its predecessor put the plan on
    dates GanttProject never showed.
    """

    def setUp(self):
        """A predecessor and a successor with slack between them."""
        self.project = Project(name="Test Project")
        self.first = Task(id="A", name="First",
                          start_date=datetime(2026, 1, 1),
                          end_date=datetime(2026, 1, 5))
        self.second = Task(id="B", name="Second",
                           start_date=datetime(2026, 1, 12),
                           end_date=datetime(2026, 1, 15))
        self.second.add_dependency("A", 'FS', 'Hard')
        self.project.add_task(self.first)
        self.project.add_task(self.second)

    def test_slack_is_left_alone(self):
        """A gap the user or a file put there survives."""
        self.project.reschedule()

        self.assertEqual(self.second.start_date, datetime(2026, 1, 12))

    def test_a_violation_is_repaired(self):
        """A successor starting too early is still pushed out."""
        self.second.start_date = datetime(2026, 1, 2)
        self.second.end_date = datetime(2026, 1, 4)

        self.project.reschedule()

        self.assertEqual(self.second.start_date, datetime(2026, 1, 6))

    def test_moving_a_predecessor_later_drags_the_successor(self):
        """The point of auto-scheduling still holds."""
        self.first.start_date = datetime(2026, 3, 1)
        self.first.end_date = datetime(2026, 3, 5)

        self.project.reschedule()

        self.assertEqual(self.second.start_date, datetime(2026, 3, 6))

    def test_choosing_a_predecessor_still_pins_exactly(self):
        """
        The dialog's own call is unaffected.

        Picking a predecessor should place the task on the link's date, which
        is what fills the start date in without the user typing it.
        """
        self.project.apply_dependency_constraints(self.second)

        self.assertEqual(self.second.start_date, datetime(2026, 1, 6))


class TestSummaryRollUp(unittest.TestCase):
    """A task with sub-tasks derives its dates from them."""

    def setUp(self):
        """A parent with two children of differing spans and progress."""
        self.project = Project(name="Test Project")
        self.project.add_task(Task(
            id="P1", name="Phase",
            start_date=datetime(2026, 6, 1), end_date=datetime(2026, 6, 2),
        ))
        self.project.add_task(Task(
            id="C1", name="One", start_date=datetime(2026, 1, 1),
            end_date=datetime(2026, 1, 10), progress=100,
            task_type="Sub-Task", parent_task_id="P1",
        ))
        self.project.add_task(Task(
            id="C2", name="Two", start_date=datetime(2026, 1, 5),
            end_date=datetime(2026, 1, 24), progress=0,
            task_type="Sub-Task", parent_task_id="P1",
        ))

    def parent(self):
        """The summary task."""
        return self.project.get_task_by_id("P1")

    def test_it_spans_its_children(self):
        """The parent runs from the earliest child to the latest."""
        self.project.reschedule()

        self.assertEqual(self.parent().start_date, datetime(2026, 1, 1))
        self.assertEqual(self.parent().end_date, datetime(2026, 1, 24))

    def test_progress_is_weighted_by_duration(self):
        """
        A long child counts for more than a short one.

        Ten of thirty days are complete, so the parent reads 33%.
        """
        self.project.reschedule()

        self.assertEqual(self.parent().progress, 33)

    def test_a_child_moving_out_stretches_the_parent(self):
        """The parent grows rather than the child being clipped."""
        self.project.reschedule()
        self.project.get_task_by_id("C2").end_date = datetime(2026, 3, 15)

        self.project.reschedule()

        self.assertEqual(self.parent().end_date, datetime(2026, 3, 15))

    def test_nested_summaries_total_upwards(self):
        """A summary of summaries takes what its children settled on."""
        project = Project(name="Nested")
        project.add_task(Task(id="TOP", name="Top",
                              start_date=datetime(2026, 1, 1),
                              end_date=datetime(2026, 1, 2)))
        project.add_task(Task(id="MID", name="Mid",
                              start_date=datetime(2026, 1, 1),
                              end_date=datetime(2026, 1, 2),
                              task_type="Sub-Task", parent_task_id="TOP"))
        project.add_task(Task(id="LEAF", name="Leaf",
                              start_date=datetime(2026, 4, 1),
                              end_date=datetime(2026, 4, 30),
                              task_type="Sub-Task", parent_task_id="MID"))

        project.reschedule()

        self.assertEqual(project.get_task_by_id("TOP").start_date,
                         datetime(2026, 4, 1))
        self.assertEqual(project.get_task_by_id("TOP").end_date,
                         datetime(2026, 4, 30))

    def test_a_childless_task_keeps_its_own_dates(self):
        """Roll-up only touches tasks that have sub-tasks."""
        self.project.reschedule()

        self.assertEqual(self.project.get_task_by_id("C1").start_date,
                         datetime(2026, 1, 1))

    def test_a_link_does_not_move_a_summary(self):
        """
        A summary's dates come from its children, not from its links.

        Letting a link move one would put it out of step with the sub-tasks
        it is supposed to bracket.
        """
        other = Task(id="Z", name="Z", start_date=datetime(2026, 9, 1),
                     end_date=datetime(2026, 9, 5))
        self.project.add_task(other)
        self.parent().add_dependency("Z", 'FS', 'Hard')

        self.project.reschedule()

        self.assertEqual(self.parent().start_date, datetime(2026, 1, 1))


class TestMilestoneRules(unittest.TestCase):
    """Milestones stay zero-duration markers."""

    def setUp(self):
        """A milestone with a stray end date and a stray child."""
        self.project = Project(name="Test Project")
        self.project.add_task(Task(id="M", name="Sign-off",
                                   start_date=datetime(2026, 1, 1),
                                   is_milestone=True))
        self.project.add_task(Task(id="S", name="Child",
                                   start_date=datetime(2026, 1, 1),
                                   end_date=datetime(2026, 1, 3),
                                   task_type="Sub-Task", parent_task_id="M"))

    def test_an_end_date_is_cleared(self):
        """A milestone carries no end date."""
        self.project.get_task_by_id("M").end_date = datetime(2026, 2, 2)

        self.project.reschedule()

        self.assertIsNone(self.project.get_task_by_id("M").end_date)

    def test_a_child_is_promoted_off_a_milestone(self):
        """
        A milestone cannot have sub-tasks.

        It would have to span them, which contradicts taking no time. The
        child is promoted rather than dropped, so no work is lost.
        """
        self.project.reschedule()
        child = self.project.get_task_by_id("S")

        self.assertIsNone(child.parent_task_id)
        self.assertEqual(child.task_type, "Task")

    def test_a_milestone_has_no_duration(self):
        """Duration stays zero however it is set up."""
        self.project.reschedule()

        self.assertEqual(self.project.get_task_by_id("M").duration_days, 0)

    def test_a_milestone_is_not_a_summary(self):
        """Once its child is promoted, nothing hangs off it."""
        self.project.reschedule()

        self.assertNotIn("M", self.project.get_summary_task_ids())


class TestConstrainedDates(DependencyTestCase):
    """The raw constraint calculation."""

    def test_no_links_constrain_nothing(self):
        """A task with no predecessors is left alone."""
        self.assertEqual(self.project.constrained_dates(self.second),
                         (None, None))

    def test_a_start_link_returns_only_a_start(self):
        """FS says when to start and nothing about the finish."""
        self.second.add_dependency("A", 'FS', 'Hard')

        start, end = self.project.constrained_dates(self.second)

        self.assertEqual(start, datetime(2026, 1, 6))
        self.assertIsNone(end)

    def test_a_finish_link_returns_only_a_finish(self):
        """FF says when to finish and nothing about the start."""
        self.second.add_dependency("A", 'FF', 'Hard')

        start, end = self.project.constrained_dates(self.second)

        self.assertIsNone(start)
        self.assertEqual(end, datetime(2026, 1, 5))

    def test_the_latest_hard_link_wins(self):
        """With several hard links the latest applies."""
        third = Task(id="C", name="Third", start_date=datetime(2026, 2, 1),
                     end_date=datetime(2026, 2, 10))
        self.project.add_task(third)
        self.second.add_dependency("A", 'FS', 'Hard')
        self.second.add_dependency("C", 'FS', 'Hard')

        start, _end = self.project.constrained_dates(self.second)

        self.assertEqual(start, datetime(2026, 2, 11))

    def test_a_start_link_wins_over_a_finish_link(self):
        """
        FS and SS place a task; FF and SF only hold its finish.

        Honouring the finish first would drag a task away from the
        predecessor it is meant to follow.
        """
        self.second.add_dependency("A", 'FS', 'Hard')
        self.second.add_dependency("A", 'FS', 'Hard')  # same link, updated

        self.project.apply_dependency_constraints(self.second)

        self.assertEqual(self.second.start_date, datetime(2026, 1, 6))


if __name__ == '__main__':
    unittest.main()
