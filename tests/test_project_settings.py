"""
Tests for the settings panel - the parts that need a display.

WHY THIS MODULE EXISTS:
======================
The settings themselves, the start-date shift and scheduling backward
are all model arithmetic - they live in
tests/features/project_settings.feature with their steps in
tests/test_project_settings_bdd.py.

What is kept here is the panel over them: the boxes it lays out, what
typing in them does, and how it sizes itself.
"""

import unittest
from datetime import datetime, timedelta

from gantt_app.core.models import (
    SCHEDULE_FROM_FINISH, Project, Task,
)

#: Monday 17 August 2026, so every weekday below is known.
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
            _shut_down(self.root)
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
        # A rename here is the user deliberately naming the plan, so a
        # Save As file name is no longer adopted over it (issue #91).
        self.assertTrue(self.project.name_was_set)
        self.assertEqual(self.project.priority, 750)
        self.assertEqual(self.project.status_date.date(),
                         datetime(2026, 9, 1).date())
        self.assertEqual(self.applied, [True])

    def test_applying_an_untouched_name_does_not_count_as_naming(self):
        """Apply on the name it already had leaves the flag alone (#91)."""
        panel = self.panel()
        self.assertFalse(self.project.name_was_set)

        self.assertTrue(panel.apply())

        self.assertFalse(self.project.name_was_set)

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
            _shut_down(self.root)
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
