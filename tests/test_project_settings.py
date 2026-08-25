"""
Tests for the settings a whole plan is built from, and the panel over them.

WHY THIS MODULE EXISTS:
======================
Two of these settings are not settings at all in the ordinary sense.

The start date is not a field on a project - it is derived from the tasks - so
the box is a command: typing a date moves the whole plan. What has to be true
afterwards is that every duration and every gap survived it, because the
alternative implementation, rescheduling from the new date, would collapse
every gap somebody had put there on purpose.

The direction is the other. Scheduled backward, the plan is packed as late as
it can go against a deadline - which is a different thing from sliding it, and
the difference only shows on a task with float: a slide keeps it early, and
As Late As Possible does not.

DEVELOPMENT NOTES:
------------------
The model half needs no display. The panel half does, and skips without one.
"""

import unittest
from datetime import datetime, timedelta

from gantt_app.models import (
    DEFAULT_PROJECT_PRIORITY, MAX_PROJECT_PRIORITY, MIN_PROJECT_PRIORITY,
    SCHEDULE_FROM_FINISH, SCHEDULE_FROM_START, Project, Task,
)

#: Monday 17 August 2026, so every weekday below is known.
MONDAY = datetime(2026, 8, 17)


class PlanTestCase(unittest.TestCase):
    """A chain of three, plus one task with float hanging off the first."""

    def plan(self) -> Project:
        """The fixture, settled forward."""
        project = Project(name="Plan")
        for task_id in ('a', 'b', 'c'):
            project.add_task(Task(id=task_id, name=task_id.upper(),
                                  task_type="Task", start_date=MONDAY,
                                  end_date=MONDAY + timedelta(days=4)))
        project.add_task(Task(id='slack', name="Slack", task_type="Task",
                              start_date=MONDAY,
                              end_date=MONDAY + timedelta(days=1)))
        project.get_task_by_id('b').add_dependency('a')
        project.get_task_by_id('c').add_dependency('b')
        project.get_task_by_id('slack').add_dependency('a')
        project.reschedule()
        return project

    def spans(self, project):
        """Each task's working duration, by id."""
        return {task.id: project.working_duration(task)
                for task in project.tasks}


class TestTheSettingsAreCarried(unittest.TestCase):
    """What a project holds, and what an older file gets."""

    def test_a_new_plan_is_scheduled_forward(self):
        """Which is what every plan did before there was a choice."""
        self.assertEqual(Project(name="P").schedule_from, SCHEDULE_FROM_START)

    def test_a_direction_it_does_not_know_falls_back(self):
        """A damaged file opens forward rather than not at all."""
        self.assertEqual(Project(name="P", schedule_from="sideways").schedule_from,
                         SCHEDULE_FROM_START)

    def test_the_priority_is_clamped_rather_than_refused(self):
        """
        It arrives from a text box and from saved files.

        A plan that will not open because somebody typed 2000 would be a
        poor trade for a number nothing acts on yet.
        """
        self.assertEqual(Project(name="P", priority=2000).priority,
                         MAX_PROJECT_PRIORITY)
        self.assertEqual(Project(name="P", priority=0).priority,
                         MIN_PROJECT_PRIORITY)
        self.assertEqual(Project(name="P", priority="nonsense").priority,
                         DEFAULT_PROJECT_PRIORITY)

    def test_the_settings_survive_a_saved_file(self):
        """All four of them."""
        project = Project(name="P", schedule_from=SCHEDULE_FROM_FINISH,
                          deadline=datetime(2026, 12, 1),
                          status_date=datetime(2026, 11, 1), priority=750)

        back = Project.from_dict(project.to_dict())

        self.assertEqual(back.schedule_from, SCHEDULE_FROM_FINISH)
        self.assertEqual(back.deadline, datetime(2026, 12, 1))
        self.assertEqual(back.status_date, datetime(2026, 11, 1))
        self.assertEqual(back.priority, 750)

    def test_a_plan_saved_before_the_settings_existed_opens(self):
        """With the defaults, which are what those plans meant."""
        data = Project(name="P").to_dict()
        for key in ('schedule_from', 'deadline', 'status_date', 'priority'):
            del data[key]

        back = Project.from_dict(data)

        self.assertEqual(back.schedule_from, SCHEDULE_FROM_START)
        self.assertIsNone(back.deadline)
        self.assertIsNone(back.status_date)
        self.assertEqual(back.priority, DEFAULT_PROJECT_PRIORITY)

    def test_an_unreadable_date_does_not_stop_the_file_opening(self):
        """A setting comes back empty rather than the plan failing to load."""
        data = Project(name="P").to_dict()
        data['deadline'] = 'the third of never'

        self.assertIsNone(Project.from_dict(data).deadline)


class TestMovingTheWholePlan(PlanTestCase):
    """The start date box, which is a command rather than a setting."""

    def test_it_begins_on_the_date_given(self):
        """Which is the whole of what the box promises."""
        project = self.plan()

        project.shift_to_start(datetime(2026, 9, 14))

        self.assertEqual(project.start_date.date(),
                         datetime(2026, 9, 14).date())

    def test_every_duration_survives(self):
        """A plan is moved, not rebuilt."""
        project = self.plan()
        before = self.spans(project)

        project.shift_to_start(datetime(2026, 9, 14))

        self.assertEqual(self.spans(project), before)

    def test_the_gaps_between_tasks_survive(self):
        """
        The reason this is a shift rather than a reschedule.

        Rescheduling from the new date would pull everything up against its
        links and collapse every gap somebody had put there on purpose.
        """
        project = self.plan()
        gap = (project.get_task_by_id('c').start_date
               - project.get_task_by_id('a').start_date)

        project.shift_to_start(datetime(2026, 9, 14))

        self.assertEqual(project.get_task_by_id('c').start_date
                         - project.get_task_by_id('a').start_date, gap)

    def test_an_earliest_begin_moves_with_it(self):
        """
        A floor set relative to the plan around it moves with that plan.

        Left behind, a plan shifted six months later is full of constraints
        nobody wrote.
        """
        project = self.plan()
        project.get_task_by_id('c').earliest_begin = MONDAY + timedelta(days=7)
        floor = project.get_task_by_id('c').earliest_begin

        project.shift_to_start(datetime(2026, 9, 14))

        self.assertGreater(project.get_task_by_id('c').earliest_begin, floor)

    def test_moving_it_where_it_already_is_changes_nothing(self):
        """And says so, so a caller can skip the redraw."""
        project = self.plan()

        self.assertFalse(project.shift_to_start(project.start_date))

    def test_an_empty_plan_is_not_moved(self):
        """There is nothing to move and nothing to fail on."""
        self.assertFalse(Project(name="P").shift_to_start(MONDAY))


class TestSchedulingBackwards(PlanTestCase):
    """As Late As Possible, against a deadline."""

    def backward(self, deadline=datetime(2026, 10, 30)):
        """The fixture, scheduled backward to a Friday deadline."""
        project = self.plan()
        project.schedule_from = SCHEDULE_FROM_FINISH
        project.deadline = deadline
        project.apply_schedule()
        return project

    def test_the_plan_ends_on_the_deadline(self):
        """Which is the point of scheduling from a finish date."""
        project = self.backward()

        self.assertEqual(project.end_date.date(),
                         datetime(2026, 10, 30).date())

    def test_durations_survive(self):
        """The work is moved, not compressed."""
        before = self.spans(self.plan())

        self.assertEqual(self.spans(self.backward()), before)

    def test_the_links_are_still_satisfied(self):
        """
        Nothing is rescheduled afterwards, so this is what says the late
        dates were right - they satisfy every link by construction, which
        is what the backward pass computes.
        """
        project = self.backward()

        for task_id, predecessor in (('b', 'a'), ('c', 'b')):
            follower = project.get_task_by_id(task_id)
            leader = project.get_task_by_id(predecessor)
            self.assertGreater(follower.start_date, leader.end_date,
                               f"{predecessor} -> {task_id}")

    def test_a_task_with_float_is_moved_late(self):
        """
        The behaviour that tells this apart from sliding the plan.

        A slide keeps a task with float where it was relative to everything
        else - early. As Late As Possible pushes it up against the finish,
        because nothing starts earlier than it has to.
        """
        forward = self.plan()
        early = (forward.get_task_by_id('slack').end_date
                 - forward.start_date).days

        project = self.backward()
        late = (project.get_task_by_id('slack').end_date
                - project.start_date).days

        self.assertGreater(late, early)

    def test_a_deadline_in_the_past_still_moves_the_plan(self):
        """
        A deadline that cannot be met from today is what a reader needs to
        be shown, and refusing to move would hide it.
        """
        project = self.backward(deadline=datetime(2020, 1, 31))

        self.assertEqual(project.end_date.date(),
                         datetime(2020, 1, 31).date())

    def test_a_forward_plan_is_settled_exactly_as_before(self):
        """
        The whole of the existing behaviour, unchanged.

        apply_schedule dispatches on the direction, and a plan scheduled
        forward has to get reschedule and nothing else.
        """
        one, other = self.plan(), self.plan()

        one.apply_schedule()
        other.reschedule()

        self.assertEqual([(t.id, t.start_date, t.end_date) for t in one.tasks],
                         [(t.id, t.start_date, t.end_date) for t in other.tasks])


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
class TestThePanel(PlanTestCase):
    """The window itself."""

    def setUp(self):
        """A plan and a panel over it."""
        import customtkinter as ctk

        self.root = ctk.CTk()
        self.root.withdraw()
        self.project = self.plan()
        self.applied = []

    def tearDown(self):
        """Close the window."""
        try:
            self.root.destroy()
        except Exception:
            pass

    def panel(self):
        """The settings panel, built over the fixture."""
        from gantt_app.views.projectsettings import ProjectSettingsDialog

        dialog = ProjectSettingsDialog(self.root, self.project,
                                       on_apply=lambda: self.applied.append(True))
        dialog.update_idletasks()
        return dialog

    def test_it_offers_every_setting(self):
        """All six, plus the title that used to be the whole dialog."""
        panel = self.panel()

        for field in ('name_entry', 'start_entry', 'finish_entry',
                      'direction_menu', 'calendar_menu', 'status_entry',
                      'priority_entry'):
            self.assertTrue(hasattr(panel, field), field)

    def test_the_finish_date_is_shut_while_the_plan_runs_forward(self):
        """
        Forward, the finish is an answer rather than a question.

        A box that accepted a date and then ignored it would be worse than
        one that refused.
        """
        panel = self.panel()

        self.assertEqual(str(panel.finish_entry.entry.cget('state')),
                         'disabled')

    def test_choosing_to_schedule_backwards_opens_it(self):
        """It becomes the deadline, and the only date the plan is built on."""
        panel = self.panel()

        panel.direction_menu.set("Project Finish Date")
        panel._show_direction()

        self.assertEqual(str(panel.finish_entry.entry.cget('state')), 'normal')

    def test_the_calendar_button_is_shut_too(self):
        """Leaving it live offers a calendar for a date nothing will read."""
        panel = self.panel()

        self.assertEqual(str(panel.finish_entry.button.cget('state')),
                         'disabled')

    def test_applying_writes_the_settings(self):
        """And tells the application to redraw."""
        panel = self.panel()
        panel.name_entry.delete(0, 'end')
        panel.name_entry.insert(0, "Renamed")
        panel.priority_entry.delete(0, 'end')
        panel.priority_entry.insert(0, "750")
        panel.status_entry.set_date(datetime(2026, 9, 1))

        self.assertTrue(panel.apply())

        self.assertEqual(self.project.name, "Renamed")
        self.assertEqual(self.project.priority, 750)
        self.assertEqual(self.project.status_date.date(),
                         datetime(2026, 9, 1).date())
        self.assertEqual(self.applied, [True])

    def test_applying_a_backward_schedule_packs_the_plan(self):
        """The panel's end of what apply_backward_schedule does."""
        panel = self.panel()
        panel.direction_menu.set("Project Finish Date")
        panel._show_direction()
        panel.finish_entry.set_date(datetime(2026, 10, 30))

        panel.apply()

        self.assertEqual(self.project.schedule_from, SCHEDULE_FROM_FINISH)
        self.assertEqual(self.project.end_date.date(),
                         datetime(2026, 10, 30).date())

    def test_backwards_with_no_finish_date_is_refused(self):
        """There is nothing to work back from."""
        from unittest import mock

        panel = self.panel()
        panel.direction_menu.set("Project Finish Date")
        panel._show_direction()
        panel.finish_entry.entry.delete(0, 'end')

        with mock.patch(
                'gantt_app.views.projectsettings.messagebox.showerror') as told:
            refused = panel.apply()

        self.assertFalse(refused)
        self.assertTrue(told.called)
        self.assertTrue(panel.winfo_exists(), "it should stay open")

    def test_a_priority_out_of_range_is_refused(self):
        """And the panel stays open with what was typed still in it."""
        from unittest import mock

        panel = self.panel()
        panel.priority_entry.delete(0, 'end')
        panel.priority_entry.insert(0, "5000")

        with mock.patch(
                'gantt_app.views.projectsettings.messagebox.showerror') as told:
            refused = panel.apply()

        self.assertFalse(refused)
        self.assertTrue(told.called)
        self.assertTrue(panel.winfo_exists())

    def test_changing_the_start_date_moves_the_plan(self):
        """The box is a command; this is the command running."""
        panel = self.panel()
        before = self.spans(self.project)
        panel.start_entry.set_date(datetime(2026, 9, 14))

        panel.apply()

        self.assertEqual(self.project.start_date.date(),
                         datetime(2026, 9, 14).date())
        self.assertEqual(self.spans(self.project), before)



@unittest.skipUnless(HAVE_DISPLAY, "no display")
class TestThePanelIsLaidOut(PlanTestCase):
    """
    That the form is a form.

    WHY THIS EXISTS:
    ================
    The first version built every control with the window as its master and
    then packed it into a per-row frame. Tk permits that - the frame shares
    the controls' master ancestry - and then lays them out against the
    toplevel rather than against the frame. The labels came out cascading
    down the top left, the controls stacked at the bottom of the window, and
    half the text ran off the right-hand edge.

    Nothing about it raised, and the tests of the time all passed: they asked
    what the panel did, and it did all of it. So this asks about the shape.
    """

    def setUp(self):
        """A panel over the fixture."""
        import customtkinter as ctk

        from gantt_app.views.projectsettings import ProjectSettingsDialog

        self.root = ctk.CTk()
        self.root.withdraw()
        self.project = self.plan()
        self.panel = ProjectSettingsDialog(self.root, self.project)
        self.panel.update_idletasks()

    def tearDown(self):
        """Close the window."""
        try:
            self.root.destroy()
        except Exception:
            pass

    def controls(self):
        """Every control on the panel, by the attribute it is kept under."""
        return {name: getattr(self.panel, name) for name in
                ('name_entry', 'direction_menu', 'start_entry',
                 'finish_entry', 'calendar_menu', 'status_entry',
                 'priority_entry')}

    def test_every_control_belongs_to_the_frame_it_sits_in(self):
        """
        The fault, stated directly.

        A control whose master is the window lays out against the window,
        wherever it was told to sit.
        """
        for name, widget in self.controls().items():
            self.assertIs(widget.master, self.panel.content, name)

    def test_every_control_is_actually_placed(self):
        """One built and never gridded is one that is simply not there."""
        for name, widget in self.controls().items():
            self.assertTrue(widget.grid_info(), name)

    def test_the_labels_and_the_controls_are_in_their_own_columns(self):
        """Which is what makes it read as a form rather than a cascade."""
        for widget in self.controls().values():
            self.assertEqual(int(widget.grid_info()['column']), 1)

    def test_the_controls_take_the_slack(self):
        """Or a wide window leaves them all bunched against the labels."""
        self.assertEqual(
            self.panel.content.grid_columnconfigure(1).get('weight'), 1)

    def test_two_columns_and_a_row_for_everything(self):
        """
        grid_size answers columns first, then rows.

        Worth stating: read the other way round this looks like a panel of
        two rows and sixteen columns, which is what the layout used to be
        accused of being.
        """
        columns, rows = self.panel.content.grid_size()

        self.assertEqual(columns, 2)
        self.assertGreaterEqual(rows, len(self.controls()))

    def test_no_explanation_runs_off_the_edge(self):
        """
        Every note wraps.

        Unwrapped, they ran past the right-hand edge of the window and were
        cut off mid-word - "Forward: worl" and the like.
        """
        import customtkinter as ctk

        notes = [child for child in self.panel.content.winfo_children()
                 if isinstance(child, ctk.CTkLabel) and child.cget('wraplength')]

        self.assertTrue(notes, "the panel should explain some of its fields")
        for note in notes:
            self.assertLessEqual(int(note.cget('wraplength')),
                                 self.panel.NOTE_WRAP)

    def test_the_window_is_big_enough_for_what_is_in_it(self):
        """It cannot be resized, so it has to be right at the size it opens."""
        wanted = self.panel.content.winfo_reqheight()
        width, _, height = self.panel.GEOMETRY.partition('x')

        self.assertGreaterEqual(int(height), wanted)
        self.assertGreaterEqual(int(width),
                                self.panel.content.winfo_reqwidth())

if __name__ == '__main__':
    unittest.main()
