"""
Tests for the progress controls: the five presets, and Mark on Track.

WHY THIS MODULE EXISTS:
======================
Two things here are worth pinning down and neither is the button.

The first is what "on track" means. It is a share of *working* days, not of
calendar days, and the difference shows up every weekend: a five-day task
starting on a Friday is 20% through by Sunday, because one of its five days
has been worked, not 40% because two nights have passed.

The second is what happens to a summary row. Its completion is rolled up from
its children and would be overwritten by the next reschedule, so writing a
percentage onto one does nothing that lasts - and pressing 100% on a phase has
an obvious meaning that has to land somewhere.

DEVELOPMENT NOTES:
------------------
The arithmetic is tested without a display; the toolbar half skips without
one, and CI provides it through xvfb.
"""

import unittest
from datetime import datetime, timedelta

from gantt_app.models import Project, Task

#: Monday 17 August 2026, so the weekday of every date below is known.
MONDAY = datetime(2026, 8, 17)


class OnTrackTestCase(unittest.TestCase):
    """What a task's completion would be if it ran exactly to plan."""

    def setUp(self):
        """A five-working-day task, Monday to Friday."""
        self.project = Project(name="Plan")
        self.task = Task(id="T1", name="Work", task_type="Task",
                         start_date=MONDAY,
                         end_date=MONDAY + timedelta(days=4))
        self.project.add_task(self.task)

    def on(self, offset: int) -> int:
        """The completion this task would have that many days in."""
        return self.project.progress_on_track(
            self.task, MONDAY + timedelta(days=offset))

    def test_work_that_has_not_started_is_at_nothing(self):
        """A future task keeps its zero."""
        self.assertEqual(self.on(-1), 0)

    def test_work_whose_finish_has_passed_is_done(self):
        """The past is complete, whatever it says now."""
        self.assertEqual(self.on(7), 100)

    def test_the_finish_day_itself_counts_as_done(self):
        """The boundary is "finish on or before the status date"."""
        self.assertEqual(self.on(4), 100)

    def test_the_first_day_is_one_day_of_five(self):
        """A day worked is a day counted, not a day elapsed."""
        self.assertEqual(self.on(0), 20)

    def test_it_climbs_a_day_at_a_time(self):
        """Monday to Thursday, one fifth each."""
        self.assertEqual([self.on(day) for day in range(4)],
                         [20, 40, 60, 80])

    def test_a_weekend_adds_nothing(self):
        """
        The reason this counts working days.

        Saturday and Sunday are not worked, so a task sitting across them is
        no further on by Monday morning than it was on Friday evening.
        """
        friday = self.on(4)
        self.assertEqual(self.on(5), friday)
        self.assertEqual(self.on(6), friday)

    def test_a_task_over_a_weekend_is_not_ahead_of_itself(self):
        """A Friday start is a fifth done by Sunday, not two fifths."""
        task = Task(id="T2", name="Weekend", task_type="Task",
                    start_date=MONDAY + timedelta(days=4),
                    end_date=MONDAY + timedelta(days=10))
        self.project.add_task(task)

        sunday = MONDAY + timedelta(days=6)
        self.assertEqual(self.project.progress_on_track(task, sunday), 20)

    def test_a_milestone_is_done_or_it_is_not(self):
        """There is no proportion of a moment."""
        milestone = Task(id="M1", name="Signed", task_type="Milestone",
                         start_date=MONDAY + timedelta(days=2))
        self.project.add_task(milestone)

        self.assertEqual(
            self.project.progress_on_track(milestone, MONDAY), 0)
        self.assertEqual(
            self.project.progress_on_track(milestone,
                                           MONDAY + timedelta(days=2)), 100)

    def test_a_holiday_shortens_both_halves_of_the_sum(self):
        """
        The task's own calendar decides which days were worked.

        A Tuesday holiday takes a day off the elapsed count and off the
        total alike: the span Monday to Friday now holds four working days,
        so Monday alone is a quarter of the task rather than a fifth. Both
        halves have to use the same calendar or the percentage drifts.
        """
        self.project.calendar.holidays.add((MONDAY + timedelta(days=1)).date())

        self.assertEqual(self.on(0), 25)
        self.assertEqual(self.on(1), 25)     # the holiday adds nothing
        self.assertEqual(self.on(2), 50)     # Wednesday is the second day

    def test_a_task_with_no_end_date_is_a_single_day(self):
        """It cannot be part done, so it is not started or it is finished."""
        task = Task(id="T3", name="Open", task_type="Task",
                    start_date=MONDAY, end_date=None)
        self.project.add_task(task)

        self.assertEqual(self.project.progress_on_track(task, MONDAY), 100)
        self.assertEqual(self.project.progress_on_track(
            task, MONDAY - timedelta(days=1)), 0)

    def test_the_answer_is_always_a_percentage(self):
        """Never below zero, never above a hundred, always whole."""
        for offset in range(-10, 20):
            value = self.on(offset)
            self.assertIsInstance(value, int)
            self.assertGreaterEqual(value, 0)
            self.assertLessEqual(value, 100)


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


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class ProgressGroupTestCase(unittest.TestCase):
    """The controls, over a plan with a past, a present and a future task."""

    def setUp(self):
        """Build the toolbar and the list, wired as the application is."""
        import customtkinter as ctk

        from gantt_app.utils.undoredo import (
            ProjectStateTracker, UndoRedoManager,
        )
        from gantt_app.views.task_list import DragDropTaskList
        from gantt_app.views.toolbar import Toolbar

        self.root = ctk.CTk()
        self.root.withdraw()

        today = datetime.now()
        self.project = Project(name="Plan")
        self.project.add_task(Task(
            id="P", name="Phase", task_type="Phase",
            start_date=today - timedelta(days=20),
            end_date=today + timedelta(days=20)))
        self.project.add_task(Task(
            id="past", name="Finished", task_type="Task", parent_task_id="P",
            start_date=today - timedelta(days=20),
            end_date=today - timedelta(days=10)))
        self.project.add_task(Task(
            id="future", name="To come", task_type="Task", parent_task_id="P",
            start_date=today + timedelta(days=10),
            end_date=today + timedelta(days=15)))

        self.manager = UndoRedoManager()
        self.toolbar = Toolbar(self.root, self.project,
                               undo_redo_manager=self.manager)
        self.task_list = DragDropTaskList(
            self.root, self.project,
            project_tracker=ProjectStateTracker(self.project, self.manager))
        self.toolbar.set_task_list(self.task_list)
        self.toolbar.on_project_changed = self.task_list.update_task_list
        self.root.update()

        self.group = self.toolbar.icon_toolbar.progress_group

    def tearDown(self):
        """Close the window."""
        try:
            self.root.destroy()
        except Exception:
            pass

    def select(self, *task_ids):
        """Select rows, and let the toolbar hear about it."""
        self.task_list.tree.selection_set(task_ids)
        self.root.update()

    def progress(self, task_id: str) -> int:
        """What one task now reports."""
        return self.project.get_task_by_id(task_id).progress


class TestTheGroupIsSetApart(ProgressGroupTestCase):
    """It is its own kind of control, and says what each button does."""

    def test_it_offers_the_five_thresholds(self):
        """The ones a status report actually uses."""
        from gantt_app.views.progressgroup import PRESETS

        self.assertEqual(PRESETS, (0, 25, 50, 75, 100))
        for percent in PRESETS:
            self.assertIn(f"preset_{percent}", self.group.buttons)

    def test_every_control_says_what_it_is(self):
        """Five bare percentages need the hover more than most."""
        from gantt_app.views.tooltip import Tooltip

        for name, button in self.group.buttons.items():
            attached = getattr(button, 'tooltip_widget', None)
            self.assertIsInstance(attached, Tooltip, name)
            self.assertTrue(attached.text.strip(), name)

        self.assertIsInstance(
            getattr(self.group.scope_button, 'tooltip_widget', None), Tooltip)

    def test_it_sits_between_two_dividers(self):
        """Like the formatting group it stands beside."""
        icons = self.toolbar.icon_toolbar
        children = icons.winfo_children()
        position = children.index(self.group)

        self.assertIn(children[position - 1], icons.separators)
        self.assertIn(children[position + 1], icons.separators)


class TestTheThresholds(ProgressGroupTestCase):
    """One press, one value, however many rows."""

    def test_a_press_sets_the_selected_rows(self):
        """Which is the whole of the feature."""
        self.select('past')

        self.toolbar.set_task_progress(75)

        self.assertEqual(self.progress('past'), 75)

    def test_it_reaches_every_selected_row(self):
        """Status reporting is done to a list, not to a row."""
        self.select('past', 'future')

        self.toolbar.set_task_progress(25)

        self.assertEqual(self.progress('past'), 25)
        self.assertEqual(self.progress('future'), 25)

    def test_the_whole_press_is_one_undo_step(self):
        """
        Marking six rows and pressing undo once puts all six back.

        This is the fault the formatting bar shipped with: update_task in a
        loop executes a command per call, so undo gave the rows back one at
        a time.
        """
        self.select('past', 'future')
        depth = len(self.manager.undo_stack)

        self.toolbar.set_task_progress(50)
        self.assertEqual(len(self.manager.undo_stack), depth + 1)

        self.manager.undo()

        self.assertEqual(self.progress('past'), 0)
        self.assertEqual(self.progress('future'), 0)

    def test_a_row_already_there_costs_no_undo_step(self):
        """Pressing the same button twice should not need two undos."""
        self.select('past')
        self.toolbar.set_task_progress(50)
        depth = len(self.manager.undo_stack)

        self.toolbar.set_task_progress(50)

        self.assertEqual(len(self.manager.undo_stack), depth)

    def test_nothing_selected_changes_nothing(self):
        """And the group is greyed out to say so."""
        self.select()

        self.assertFalse(self.group.enabled)
        self.group._preset(100)

        self.assertEqual(self.progress('past'), 0)

    def test_pressing_it_on_a_phase_marks_the_work_under_it(self):
        """
        A summary's own percentage is rolled up and would not survive.

        Ignoring the press would be worse: selecting a phase and pressing
        100% has one obvious meaning.
        """
        self.select('P')

        self.toolbar.set_task_progress(100)

        self.assertEqual(self.progress('past'), 100)
        self.assertEqual(self.progress('future'), 100)


class TestMarkOnTrack(ProgressGroupTestCase):
    """Where the dates say the work should have got to."""

    def test_past_work_is_marked_done(self):
        """Its finish has gone by."""
        self.select('past')

        self.toolbar.mark_on_track('selected')

        self.assertEqual(self.progress('past'), 100)

    def test_future_work_is_left_at_nothing(self):
        """It has not started, so there is nothing to report."""
        self.select('future')
        self.project.get_task_by_id('future').progress = 40

        self.toolbar.mark_on_track('selected')

        self.assertEqual(self.progress('future'), 0)

    def test_the_whole_project_can_be_marked_at_once(self):
        """Which is the scope behind the arrow, and needs no selection."""
        self.select()

        self.toolbar.mark_on_track('project')

        self.assertEqual(self.progress('past'), 100)
        self.assertEqual(self.progress('future'), 0)

    def test_the_scope_control_stays_live_with_nothing_selected(self):
        """Entire Project does not need a selection to mean something."""
        self.select()

        self.assertEqual(str(self.group.scope_button.cget('state')), 'normal')

    def test_it_is_one_undo_step_too(self):
        """However much of the plan it reached."""
        depth = len(self.manager.undo_stack)

        self.toolbar.mark_on_track('project')

        self.assertEqual(len(self.manager.undo_stack), depth + 1)

    def test_a_summary_is_not_written_to_directly(self):
        """Its completion comes from its children."""
        self.toolbar.mark_on_track('project')

        self.assertEqual(self.progress('P'), 0)


if __name__ == '__main__':
    unittest.main()
