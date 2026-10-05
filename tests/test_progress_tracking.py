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

from gantt_app.core.models import Project, Task

#: Monday 17 August 2026, so the weekday of every date below is known.
MONDAY = datetime(2026, 8, 17)


def _shut_down(root) -> None:
    """
    Take a root down, children first, without raising.

    Destroying a root while a Toplevel is still on it leaves Tk running
    ttk::ThemeChanged against an interpreter that has already gone, which
    floods stderr with "can't invoke event" tracebacks.
    """
    try:
        for child in list(root.children.values()):
            try:
                child.destroy()
            except Exception:
                pass
        root.destroy()
    except Exception:
        pass


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
            _shut_down(self.root)
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
            getattr(self.group.project_button, 'tooltip_widget', None),
            Tooltip)

    def test_each_mark_press_names_the_rows_it_reaches(self):
        """
        The complaint that split the button.

        The press used to be an unmarked icon with a chevron beside it that
        opened a scope menu - so nobody could tell which rows a press was
        about to move, or whether the chevron set a default the button then
        used. Each press now names its scope on its face.
        """
        self.assertEqual(self.group.buttons['mark_on_track'].cget('text'),
                         'Selected')
        self.assertEqual(self.group.project_button.cget('text'), 'Project')

    def test_the_scope_a_press_names_is_the_scope_it_applies(self):
        """No remembered default: the button does exactly what it says."""
        self.select('past')

        self.group.buttons['mark_on_track'].invoke()

        self.assertEqual(self.progress('past'), 100)
        self.assertEqual(self.progress('future'), 0)

    def test_the_project_press_marks_the_whole_plan(self):
        """The second press, which used to hide in a menu."""
        self.select()

        self.group.project_button.invoke()

        self.assertEqual(self.progress('past'), 100)

    def test_it_sits_between_two_dividers(self):
        """Like the formatting group it stands beside - its own group."""
        from gantt_app.views.ribbon import RibbonGroup

        parent = self.group.master
        while parent is not None and not isinstance(parent, RibbonGroup):
            parent = getattr(parent, 'master', None)

        self.assertIsNotNone(parent)
        self.assertEqual(parent.caption, 'Progress')


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

    def test_future_work_with_nothing_reported_stays_at_nothing(self):
        """It has not started, so there is nothing to bring forward."""
        from unittest import mock

        self.select('future')

        with mock.patch('gantt_app.views.toolbar.messagebox.showinfo'):
            self.toolbar.mark_on_track('selected')

        self.assertEqual(self.progress('future'), 0)

    def test_what_was_reported_on_future_work_is_not_wiped(self):
        """
        The fault this replaced.

        A project manager reported a morning's progress against work whose
        dates were still ahead, pressed Mark on Track over the whole
        project, and watched 25% and 75% become 0% - because the calendar
        expects nothing of work that has not started, and this wrote that
        expectation over the report.

            before   004 25%   005 75%
            after    004  0%   005  0%

        A figure on a row is something somebody reported; the on-track
        figure is what the calendar expects. Where they disagree and the
        report is higher, the report is the one that knows something.
        """
        from unittest import mock

        self.select('future')
        self.project.get_task_by_id('future').progress = 75

        with mock.patch('gantt_app.views.toolbar.messagebox.showinfo'):
            self.toolbar.mark_on_track('selected')

        self.assertEqual(self.progress('future'), 75)

    def test_work_reported_ahead_of_its_dates_is_left_alone(self):
        """Being ahead of schedule is not a fault to correct."""
        from unittest import mock

        self.select('past')
        self.project.get_task_by_id('past').progress = 100

        with mock.patch('gantt_app.views.toolbar.messagebox.showinfo') as told:
            self.toolbar.mark_on_track('selected')

        self.assertEqual(self.progress('past'), 100)
        self.assertTrue(told.called, "nothing to do, so it should say so")

    def test_work_that_is_behind_is_still_brought_forward(self):
        """Which is what the button is for."""
        self.select('past')
        self.project.get_task_by_id('past').progress = 10

        self.toolbar.mark_on_track('selected')

        self.assertEqual(self.progress('past'), 100)

    def test_a_run_over_the_whole_project_raises_and_never_lowers(self):
        """The scope the report was destroyed from."""
        from unittest import mock

        self.project.get_task_by_id('future').progress = 75
        self.project.get_task_by_id('past').progress = 10

        with mock.patch('gantt_app.views.toolbar.messagebox.showinfo'):
            self.toolbar.mark_on_track('project')

        self.assertEqual(self.progress('future'), 75)
        self.assertEqual(self.progress('past'), 100)

    def test_the_whole_project_can_be_marked_at_once(self):
        """Which is the scope behind the arrow, and needs no selection."""
        self.select()

        self.toolbar.mark_on_track('project')  # noqa: nothing reported yet

        self.assertEqual(self.progress('past'), 100)
        self.assertEqual(self.progress('future'), 0)

    def test_the_scope_control_stays_live_with_nothing_selected(self):
        """Marking the project does not need a selection to mean something."""
        self.select()

        self.assertEqual(str(self.group.project_button.cget('state')),
                         'normal')

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
