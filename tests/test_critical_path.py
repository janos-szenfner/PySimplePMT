"""
Tests for the critical path analysis.

WHY THIS MODULE EXISTS:
======================
The old implementation returned one chain: the longest run of dependent tasks
ending at whatever finished last. That is *a* critical path rather than *the*
critical path, and a plan whose risk sits in two parallel strands had half of
it hidden - the chart coloured one and left the other looking like ordinary
work with room to spare.

Criticality is defined as zero total float, and that needs both passes of the
critical path method. What is pinned down here is the arithmetic: that the
float is right, that every zero-float task is found rather than one chain
through them, and that the link types are honoured on the way back.

DEVELOPMENT NOTES:
------------------
Everything is counted in working days, so the fixtures run Monday to Friday
and the expected numbers are working days rather than calendar ones. Nothing
here needs a display.
"""

import unittest
from datetime import date, datetime

from gantt_app.models import Project, Task


class CriticalPathTestCase(unittest.TestCase):
    """Helpers for building a small network and reading it back."""

    def plan(self, rows):
        """
        A project from (id, start, end, [(predecessor, type, lag)]) rows.

        Dates are (year, month, day) tuples; an end of None is a milestone.
        """
        project = Project(name="Analysis")
        for task_id, start, end, links in rows:
            task = Task(
                id=task_id, name=task_id,
                start_date=datetime(*start),
                end_date=datetime(*end) if end else None,
                is_milestone=end is None,
            )
            for predecessor, dep_type, lag in links:
                task.add_dependency(predecessor, dep_type, 'Hard', lag)
            project.add_task(task)
        return project

    def floats(self, project):
        """Total float per task ID."""
        return {task_id: found.total_float
                for task_id, found in project.schedule_analysis().items()}

    def critical(self, project):
        """The IDs the analysis calls critical, sorted."""
        return sorted(t.id for t in project.get_critical_path())


class TestFloatAndCriticality(CriticalPathTestCase):
    """The numbers the two passes produce."""

    def setUp(self):
        """
        Two strands between a start and a finish, one of them slack.

        A: 5 days, then B (10 days) and C (2 days) in parallel, then D.
        B drives the finish; C has eight days of air behind it.
        """
        self.project = self.plan([
            ("A", (2026, 1, 5), (2026, 1, 9), []),
            ("B", (2026, 1, 12), (2026, 1, 23), [("A", 'FS', 0)]),
            ("C", (2026, 1, 12), (2026, 1, 13), [("A", 'FS', 0)]),
            ("D", (2026, 1, 26), (2026, 1, 30), [("B", 'FS', 0),
                                                 ("C", 'FS', 0)]),
        ])
        self.project.reschedule()

    def test_the_driving_chain_has_no_float(self):
        """A, B and D cannot slip by a day."""
        floats = self.floats(self.project)

        self.assertEqual(floats["A"], 0)
        self.assertEqual(floats["B"], 0)
        self.assertEqual(floats["D"], 0)

    def test_the_slack_strand_has_its_slack_measured(self):
        """
        C runs two days inside a ten day window, so it has eight.

        Working days: the weekend inside the window is not slack anybody can
        spend, and counting it would overstate the number by four.
        """
        self.assertEqual(self.floats(self.project)["C"], 8)

    def test_the_critical_path_is_every_zero_float_task(self):
        """Not one chain through them."""
        self.assertEqual(self.critical(self.project), ["A", "B", "D"])

    def test_late_dates_are_the_early_ones_where_there_is_no_float(self):
        """A critical task has nowhere to be but where it is."""
        analysis = self.project.schedule_analysis()

        for task_id in ("A", "B", "D"):
            with self.subTest(task=task_id):
                found = analysis[task_id]
                self.assertEqual(found.late_start, found.early_start)
                self.assertEqual(found.late_finish, found.early_finish)

    def test_a_slack_task_may_finish_later_than_it_does(self):
        """Its latest finish is where the work behind it needs it."""
        found = self.project.schedule_analysis()["C"]

        self.assertEqual(found.late_finish, found.early_finish + 8)


class TestTwoStrandsBothCritical(CriticalPathTestCase):
    """
    The case a single chain could not express.

    Two strands of equal length between the same two tasks are both critical:
    either one slipping moves the finish. The old implementation walked back
    through one predecessor and reported that strand alone.
    """

    def test_both_equal_strands_are_critical(self):
        """Neither has any float, so both are on the path."""
        project = self.plan([
            ("start", (2026, 1, 5), (2026, 1, 9), []),
            ("left", (2026, 1, 12), (2026, 1, 23), [("start", 'FS', 0)]),
            ("right", (2026, 1, 12), (2026, 1, 23), [("start", 'FS', 0)]),
            ("end", (2026, 1, 26), (2026, 1, 30), [("left", 'FS', 0),
                                                   ("right", 'FS', 0)]),
        ])
        project.reschedule()

        self.assertEqual(self.critical(project),
                         ["end", "left", "right", "start"])


class TestTheLinkTypesOnTheWayBack(CriticalPathTestCase):
    """What a predecessor has to clear depends on which end the link holds."""

    def test_a_start_start_link_lets_the_predecessor_run_on(self):
        """
        Only the start has to clear, so the first task may still be running
        when the second begins.

        Its latest finish falls after the second task's earliest start, which
        is the whole difference between this link and a Finish-Start one -
        and getting it wrong would report float that cannot be taken, or deny
        float that can.
        """
        project = self.plan([
            ("first", (2026, 1, 5), (2026, 1, 9), []),
            ("second", (2026, 1, 5), (2026, 1, 16), [("first", 'SS', 0)]),
        ])
        project.reschedule()

        analysis = project.schedule_analysis()

        self.assertGreaterEqual(analysis["first"].late_finish,
                                analysis["second"].early_start)

    def test_a_finish_start_link_does_not(self):
        """The same pair, under the link that says finish first."""
        project = self.plan([
            ("first", (2026, 1, 5), (2026, 1, 9), []),
            ("second", (2026, 1, 12), (2026, 1, 23), [("first", 'FS', 0)]),
        ])
        project.reschedule()

        analysis = project.schedule_analysis()

        self.assertLess(analysis["first"].late_finish,
                        analysis["second"].early_start)

    def test_a_finish_finish_link_ties_the_two_finishes(self):
        """
        The predecessor may run right up to the successor's finish.

        A short task tied Finish-Finish to a long one has all the room the
        difference between them gives it.
        """
        project = self.plan([
            ("short", (2026, 1, 5), (2026, 1, 6), []),
            ("long", (2026, 1, 5), (2026, 1, 16), [("short", 'FF', 0)]),
        ])
        project.reschedule()

        analysis = project.schedule_analysis()

        self.assertEqual(analysis["short"].late_finish,
                         analysis["long"].late_finish)
        self.assertGreater(analysis["short"].total_float, 0)

    def test_a_lag_is_slack_the_predecessor_does_not_get(self):
        """
        The wait is part of the plan, not float.

        A three day lag between two tasks does not mean the first has three
        days to spare: the wait still has to happen after it.
        """
        project = self.plan([
            ("first", (2026, 1, 5), (2026, 1, 9), []),
            ("second", (2026, 1, 15), (2026, 1, 21), [("first", 'FS', 3)]),
        ])
        project.reschedule()

        self.assertEqual(self.floats(project)["first"], 0)


class TestWhatIsLeftOut(CriticalPathTestCase):
    """Not everything in a plan is work."""

    def test_a_summary_is_not_analysed(self):
        """
        It brackets its children rather than being work of its own.

        Left in, a group bar spanning a fortnight would outrank the work
        inside it and come out critical on its own account.
        """
        project = Project(name="Nested")
        project.add_task(Task(id="P", name="Phase", task_type="Phase",
                              start_date=datetime(2026, 1, 5),
                              end_date=datetime(2026, 1, 9)))
        project.add_task(Task(id="T", name="Work", task_type="Subtask",
                              parent_task_id="P",
                              start_date=datetime(2026, 1, 5),
                              end_date=datetime(2026, 1, 9)))
        project.reschedule()

        analysis = project.schedule_analysis()

        self.assertNotIn("P", analysis)
        self.assertIn("T", analysis)

    def test_a_milestone_takes_no_time_and_can_still_be_critical(self):
        """It marks a moment, and the moment can be the one that matters."""
        project = self.plan([
            ("work", (2026, 1, 5), (2026, 1, 9), []),
            ("gate", (2026, 1, 12), None, [("work", 'FS', 0)]),
        ])
        project.reschedule()

        analysis = project.schedule_analysis()
        self.assertEqual(analysis["gate"].early_start,
                         analysis["gate"].early_finish)
        self.assertIn("gate", self.critical(project))

    def test_an_empty_plan_analyses_to_nothing(self):
        """And says so rather than raising."""
        self.assertEqual(Project(name="Empty").schedule_analysis(), {})
        self.assertEqual(Project(name="Empty").get_critical_path(), [])


class TestItDoesNotHang(CriticalPathTestCase):
    """A plan can contain links that do not resolve."""

    def test_a_dependency_cycle_returns_rather_than_looping(self):
        """
        The backward pass walks successors, which a cycle never exhausts.

        An edge it cannot measure contributes nothing rather than the whole
        analysis failing on a plan that has one - and it is logged, so the
        cycle is not silently treated as a schedule.
        """
        project = self.plan([
            ("X", (2026, 1, 5), (2026, 1, 9), [("Y", 'FS', 0)]),
            ("Y", (2026, 1, 12), (2026, 1, 16), [("X", 'FS', 0)]),
        ])

        analysis = project.schedule_analysis()

        self.assertEqual(set(analysis), {"X", "Y"})

    def test_a_link_to_a_task_that_is_gone_is_ignored(self):
        """A file can name a predecessor that is not in the plan."""
        project = self.plan([
            ("only", (2026, 1, 5), (2026, 1, 9), [("missing", 'FS', 0)]),
        ])

        self.assertEqual(set(project.schedule_analysis()), {"only"})


class TestTheReportedNumbers(CriticalPathTestCase):
    """The shape of what comes back."""

    def test_every_task_gets_a_full_set(self):
        """Early, late, float and the verdict, for each."""
        project = self.plan([
            ("A", (2026, 1, 5), (2026, 1, 9), []),
            ("B", (2026, 1, 12), (2026, 1, 16), [("A", 'FS', 0)]),
        ])
        project.reschedule()

        for task_id, found in project.schedule_analysis().items():
            with self.subTest(task=task_id):
                self.assertEqual(found.task_id, task_id)
                self.assertEqual(found.early_finish - found.early_start,
                                 found.late_finish - found.late_start)
                self.assertEqual(found.total_float,
                                 found.late_finish - found.early_finish)
                self.assertIs(found.is_critical, found.total_float <= 0)

    def test_the_first_task_starts_at_offset_zero(self):
        """Offsets are working days from the plan's first day."""
        project = self.plan([
            ("A", (2026, 1, 5), (2026, 1, 9), []),
            ("B", (2026, 1, 12), (2026, 1, 16), [("A", 'FS', 0)]),
        ])
        project.reschedule()

        analysis = project.schedule_analysis()
        self.assertEqual(analysis["A"].early_start, 0)
        # Five working days of A, so B starts on the sixth
        self.assertEqual(analysis["B"].early_start, 5)


def _display_available() -> bool:
    """Whether a usable Tk display is present."""
    try:
        import tkinter
        root = tkinter.Tk()
    except Exception:
        return False
    root.destroy()
    return True


HAVE_DISPLAY = _display_available()


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestTheWindowItOpens(CriticalPathTestCase):
    """
    What the reader is shown.

    A colour on the chart says which tasks are critical and nothing else.
    The question a plan raises is the next one - how much slack has
    everything else got - and one day of float is the thing worth knowing
    about before it is spent.
    """

    def setUp(self):
        """A root window and the two-strand plan."""
        import customtkinter as ctk

        self.root = ctk.CTk()
        self.root.withdraw()
        self.project = self.plan([
            ("A", (2026, 1, 5), (2026, 1, 9), []),
            ("B", (2026, 1, 12), (2026, 1, 23), [("A", 'FS', 0)]),
            ("C", (2026, 1, 12), (2026, 1, 13), [("A", 'FS', 0)]),
            ("D", (2026, 1, 26), (2026, 1, 30), [("B", 'FS', 0),
                                                 ("C", 'FS', 0)]),
        ])
        self.project.reschedule()

    def tearDown(self):
        """Tear the root window down."""
        try:
            self.root.destroy()
        except Exception:
            pass

    def window(self):
        """The analysis window over the fixture."""
        from gantt_app.views.criticalpath import CriticalPathWindow

        found = CriticalPathWindow(self.root, self.project)
        found.update_idletasks()
        return found

    def rows(self, window):
        """Each row as a dict of column to value."""
        keys = [key for key, *_rest in window.COLUMNS]
        return {
            iid: dict(zip(keys, window.tree.item(iid, 'values')))
            for iid in window.tree.get_children()
        }

    def test_every_task_that_holds_work_gets_a_row(self):
        """Summaries are left out; everything else is listed."""
        self.assertEqual(set(self.rows(self.window())), {"A", "B", "C", "D"})

    def test_the_float_is_shown_per_task(self):
        """Which is the number a colour on the chart cannot give."""
        rows = self.rows(self.window())

        self.assertEqual(rows["C"]['float'], '8')
        self.assertEqual(rows["B"]['float'], '0')

    def test_the_critical_rows_are_marked_and_shaded(self):
        """Both in the column and in the row's colour."""
        window = self.window()
        rows = self.rows(window)

        self.assertEqual(rows["B"]['critical'], 'Yes')
        self.assertEqual(rows["C"]['critical'], '')
        self.assertIn('critical', window.tree.item("B", 'tags'))

    def test_the_latest_dates_are_dates(self):
        """
        The analysis counts in working days; the reader wants a calendar.

        "Day 14 of the plan" is honest and useless.
        """
        rows = self.rows(self.window())

        self.assertEqual(rows["C"]['late_finish'], '2026-01-23')

    def test_the_summary_counts_the_critical_tasks(self):
        """The headline above the table."""
        text = self.window().summary_label.cget('text')

        self.assertIn("3 of 4 tasks are critical", text)

    def test_it_opens_on_an_empty_plan(self):
        """A report with nothing to report says so rather than raising."""
        from gantt_app.views.criticalpath import CriticalPathWindow

        window = CriticalPathWindow(self.root, Project(name="Empty"))
        window.update_idletasks()

        self.assertEqual(window.tree.get_children(), ())
        self.assertIn("no work", window.summary_label.cget('text'))


class TestTheToolbarOffersIt(unittest.TestCase):
    """Where the analysis is reached from."""

    def test_the_icon_stands_on_its_own_between_the_groups(self):
        """
        With a divider on each side.

        It neither edits a row nor moves anything about, so it belongs to
        neither of the groups it sits between - which is why it is pinned to
        the dividers rather than to whichever icon currently happens to be
        its neighbour.
        """
        from gantt_app.views.toolbar import IconToolbar

        row = [name for name, _tip, _action in IconToolbar.ICON_ACTIONS]
        index = row.index('critical_path')

        self.assertEqual(row[index - 1], IconToolbar.SEPARATOR)
        self.assertEqual(row[index + 1], IconToolbar.SEPARATOR)
        # The group before it ends with the linking pair; the one after it
        # starts with the clipboard
        self.assertEqual(row[index - 2], 'unlink')
        self.assertEqual(row[index + 2], 'cut')

    def test_the_icon_has_a_drawing_and_a_handler(self):
        """An icon with neither is a blank button that does nothing."""
        from gantt_app.resources.icons import ICON_STROKES
        from gantt_app.views.toolbar import Toolbar

        self.assertIn('critical_path', ICON_STROKES)
        self.assertTrue(callable(getattr(Toolbar, 'show_critical_path', None)))

    def test_it_is_on_the_actions_menu_too(self):
        """Reachable without knowing which icon it is."""
        from tests.test_toolbar_menus import menu_tree, find, labels

        items = find(menu_tree(), 'Actions')['items']

        self.assertIn('Critical Path...', labels(items))


class TestTasksOnCalendarsOfTheirOwn(CriticalPathTestCase):
    """
    Float has to mean the same thing for every task compared on it.

    DEVELOPMENT NOTES:
    ------------------
    A task's duration is counted on the calendar that task follows; the axis
    every task is placed on counts the plan's. For a plan on one calendar the
    two agree exactly. For a task on a calendar of its own they do not, and
    adding one to the other put the task's finish past where it actually was.
    """

    def mixed_plan(self):
        """A 24/7 task, then an ordinary one hard-linked after it."""
        project = Project(name="Mixed")
        start = datetime(2026, 9, 10)           # a Thursday
        project.add_task(Task(id="A", name="A", start_date=start,
                              end_date=start, duration=5,
                              calendar_id="continuous"))
        follower = Task(id="B", name="B", start_date=start, end_date=start,
                        duration=2)
        follower.add_dependency("A", "FS", "Hard")
        project.add_task(follower)
        project.reschedule()
        return project

    def test_a_continuous_task_is_not_given_negative_float(self):
        """
        It was, and it had not slipped by so much as a day.

        Five days of a 24/7 run cover three of the plan's working days.
        Counting the five onto an axis measuring the plan's put the finish
        two days beyond the real one, which came back as two days of
        negative float - a task reported as undeliverable that was on time.
        """
        project = self.mixed_plan()

        self.assertEqual(self.floats(project)["A"], 0)

    def test_the_axis_agrees_with_the_dates(self):
        """Both ends of a task measured with the one ruler."""
        project = self.mixed_plan()
        analysis = project.schedule_analysis()

        # A runs Thu 10 to Mon 14, which is three of the plan's working days
        self.assertEqual(analysis["A"].early_start, 0)
        self.assertEqual(analysis["A"].early_finish, 2)
        # B follows it on the Tuesday and Wednesday
        self.assertEqual(analysis["B"].early_start, 3)
        self.assertEqual(analysis["B"].early_finish, 4)

    def test_a_weekend_task_is_placed_where_it_runs(self):
        """The other direction: a task whose week is narrower than the plan's."""
        project = Project(name="Weekend")
        start = datetime(2026, 9, 10)
        project.add_task(Task(id="A", name="A", start_date=start,
                              end_date=start, duration=2,
                              calendar_id="weekend-shift"))
        project.reschedule()
        task = project.get_task_by_id("A")
        self.assertEqual(task.start_date.date().isoformat(), '2026-09-12')

        analysis = project.schedule_analysis()

        # It runs Sat 12 to Sun 13, neither of which the plan works, so it
        # covers none of the axis at all - and still has no float, being the
        # only task in the plan.
        self.assertEqual(analysis["A"].early_start, analysis["A"].early_finish)
        self.assertEqual(analysis["A"].total_float, 0)

    def test_a_single_calendar_plan_is_unchanged(self):
        """
        The fix must not move the numbers everybody already has.

        Where every task follows the plan's calendar, reading the finish off
        the axis and adding the duration to the start give the same answer.
        """
        project = self.plan([
            ("A", (2026, 3, 2), (2026, 3, 6), []),
            ("B", (2026, 3, 9), (2026, 3, 13), [("A", "FS", 0)]),
            ("C", (2026, 3, 9), (2026, 3, 11), [("A", "FS", 0)]),
        ])
        project.reschedule()

        analysis = project.schedule_analysis()

        self.assertEqual(analysis["A"].early_start, 0)
        self.assertEqual(analysis["A"].early_finish, 4)
        self.assertEqual(analysis["B"].early_start, 5)
        self.assertEqual(analysis["B"].early_finish, 9)
        self.assertEqual(self.floats(project)["C"], 2)


class TestTheAnalysisIsCached(CriticalPathTestCase):
    """
    The chart asks for this on every redraw, only to colour bars.

    DEVELOPMENT NOTES:
    ------------------
    layout_chart calls get_critical_path unconditionally, so a resize, a
    zoom, a theme change or a scroll-triggered redraw paid for the whole
    forward-and-backward pass again - about 230ms on a thousand-task plan.

    Cached against a signature of the plan rather than cleared by hand:
    tasks are mutated directly all over the dialogs, so a cache cleared from
    a dozen places would go stale the first time somebody added a
    thirteenth. Every test below is really asking "can it go stale".
    """

    def plan_of_three(self):
        """A short chain, rescheduled."""
        project = self.plan([
            ("A", (2026, 3, 2), (2026, 3, 6), []),
            ("B", (2026, 3, 9), (2026, 3, 13), [("A", "FS", 0)]),
            ("C", (2026, 3, 9), (2026, 3, 11), [("A", "FS", 0)]),
        ])
        project.reschedule()
        return project

    def test_an_unchanged_plan_is_not_analysed_twice(self):
        """The whole point: a redraw that changed nothing pays nothing."""
        project = self.plan_of_three()

        first = project.schedule_analysis()
        second = project.schedule_analysis()

        self.assertIs(first, second)

    def test_moving_a_task_is_noticed(self):
        """A date is the most obvious thing that changes the answer."""
        project = self.plan_of_three()
        before = project.schedule_analysis()

        project.get_task_by_id("C").end_date = datetime(2026, 3, 13)

        self.assertIsNot(project.schedule_analysis(), before)
        self.assertEqual(self.floats(project)["C"], 0)

    def test_changing_a_link_is_noticed(self):
        """Links are read straight off the tasks, not through a method."""
        project = self.plan_of_three()
        project.schedule_analysis()

        project.get_task_by_id("C").dependencies = []

        self.assertNotEqual(project._analysis_signature(),
                            project._analysis_signature_seen)

    def test_adding_a_task_is_noticed(self):
        """The signature covers the list, not only what is in each row."""
        project = self.plan_of_three()
        before = project.schedule_analysis()

        project.add_task(Task(id="D", name="D",
                              start_date=datetime(2026, 3, 16),
                              end_date=datetime(2026, 3, 18)))

        self.assertIsNot(project.schedule_analysis(), before)

    def test_a_calendar_change_is_noticed(self):
        """
        Even one that moves no dates.

        Float is counted in working days, so a holiday inside the plan
        changes the answer without any task's dates changing.
        """
        project = self.plan_of_three()
        project.schedule_analysis()
        signature = project._analysis_signature_seen

        project.calendar.add_override(date(2026, 3, 10), False, "shutdown")

        self.assertNotEqual(project._analysis_signature(), signature)

    def test_a_named_calendar_change_is_noticed(self):
        """A task may follow one, so its week is part of the answer."""
        project = self.plan_of_three()
        project.schedule_analysis()
        signature = project._analysis_signature_seen

        project.calendars.get('weekend-shift').calendar.add_override(
            date(2026, 3, 10), False, "shutdown")

        self.assertNotEqual(project._analysis_signature(), signature)

    def test_the_cached_answer_is_the_right_one(self):
        """
        Caching is only worth having while it agrees with the slow path.

        This is what stops the memoisation quietly returning yesterday's
        answer for the rest of the session.
        """
        project = self.plan_of_three()

        cached = project.schedule_analysis()
        fresh = project._compute_schedule_analysis()

        self.assertEqual({k: v for k, v in cached.items()},
                         {k: v for k, v in fresh.items()})

    def test_it_can_be_dropped_by_hand(self):
        """For a caller that did something the signature cannot see."""
        project = self.plan_of_three()
        first = project.schedule_analysis()

        project.invalidate_schedule_analysis()

        self.assertIsNot(project.schedule_analysis(), first)

    def test_a_copied_project_still_answers(self):
        """
        The undo history copies projects, and a copy skips __post_init__.

        Restored from copy, deepcopy or a pickle, the cache attributes are
        whatever the original's __dict__ held - or absent entirely.
        """
        import copy as copy_module

        project = self.plan_of_three()
        project.schedule_analysis()

        for made in (copy_module.copy(project),
                     copy_module.deepcopy(project)):
            self.assertTrue(made.schedule_analysis())

        bare = Project.__new__(Project)
        bare.__dict__.update(project.__dict__)
        self.assertTrue(bare.schedule_analysis())


class TestTheFloatAxisIsBuiltOnce(CriticalPathTestCase):
    """
    The axis every task's float is measured on.

    DEVELOPMENT NOTES:
    ------------------
    Each offset used to be counted from the plan's first day, so two lookups
    per task each walked the whole calendar - 211,703 calls to is_working_day
    on a thousand-task plan, and O(tasks x span) overall. The span is walked
    once now and remembered.
    """

    def mixed_plan(self):
        """Tasks over a span with weekends and a holiday in it."""
        project = self.plan([
            ("A", (2026, 3, 2), (2026, 3, 6), []),
            ("B", (2026, 3, 9), (2026, 3, 20), [("A", "FS", 0)]),
            ("C", (2026, 3, 9), (2026, 3, 11), [("A", "FS", 0)]),
            ("D", (2026, 3, 23), (2026, 3, 27), [("B", "FS", 0)]),
        ])
        project.calendar.add_override(date(2026, 3, 17), False, "shutdown")
        project.reschedule()
        return project

    def counted(self, project):
        """The analysis with the axis taken away, so offsets are counted."""
        original = Project._working_day_axis
        Project._working_day_axis = lambda self, origin, tasks: {}
        try:
            return project._compute_schedule_analysis()
        finally:
            Project._working_day_axis = original

    def test_the_indexed_answers_match_the_counted_ones(self):
        """
        Which is the whole requirement.

        A faster axis that disagreed with the old one would move every
        float in the plan and nobody would know which was right.
        """
        project = self.mixed_plan()

        indexed = project._compute_schedule_analysis()
        counted = self.counted(project)

        self.assertEqual(set(indexed), set(counted))
        for task_id, found in indexed.items():
            self.assertEqual(found, counted[task_id], task_id)

    def test_it_covers_every_date_the_plan_touches(self):
        """A gap would send that lookup down the slow path silently."""
        project = self.mixed_plan()
        tasks = [t for t in project.tasks]
        origin = min(t.start_date for t in tasks)

        axis = project._working_day_axis(origin, tasks)

        for task in tasks:
            self.assertIn(task.start_date.date(), axis, task.id)
            if task.end_date is not None:
                self.assertIn(task.end_date.date(), axis, task.id)

    def test_it_counts_the_same_as_the_calendar(self):
        """The table is only worth having while it agrees with the walk."""
        project = self.mixed_plan()
        tasks = list(project.tasks)
        origin = min(t.start_date for t in tasks)

        axis = project._working_day_axis(origin, tasks)

        for day, offset in axis.items():
            walked = max(
                project.calendar.working_days_between(origin, day) - 1, 0)
            self.assertEqual(offset, walked, day)

    def test_a_date_outside_the_table_still_answers(self):
        """Slow rather than wrong, for anything unexpected."""
        project = self.mixed_plan()
        analysis = project._compute_schedule_analysis()

        self.assertTrue(analysis)       # the fallback path is exercised by
                                        # the counted comparison above


if __name__ == '__main__':
    unittest.main()
