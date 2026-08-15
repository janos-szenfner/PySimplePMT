"""
Tests for the task editor's checking of the form as it is filled in.

WHY THIS MODULE EXISTS:
======================
The checks run on every keystroke and touch live widgets, so nothing short of
building the dialog and typing into it exercises them. The first version of
them reconfigured a CustomTkinter entry with border_color=None, which raises
part way through configure() and left the box a widget whose Tk command no
longer existed: the name of every task opened for editing became untypeable
and unreadable, and Save raised rather than saving. Every test here passed
against it, because none of them touched a widget.

DEVELOPMENT NOTES:
------------------
The module skips without a display; CI provides one through xvfb.

Typing is done by writing into the box, which is what the checks watch - see
type_into.
"""

import unittest
from unittest import mock
import tkinter as tk
from datetime import datetime, timedelta

from gantt_app.models import Project, Task


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
class EditorTestCase(unittest.TestCase):
    """A root window, a small project, and a way to type into a form."""

    def setUp(self):
        """Build the window and the project, and watch for stray errors."""
        import customtkinter as ctk

        self.root = ctk.CTk()
        self.root.withdraw()

        # Tk swallows an exception raised inside a callback, so a broken
        # binding shows up as a misbehaving widget rather than a failure.
        # Collect them and let the tests assert there were none.
        self.callback_errors = []
        self.root.report_callback_exception = (
            lambda *info: self.callback_errors.append(info)
        )

        base = datetime(2026, 1, 1)
        self.project = Project(name="Test Project")
        self.task = Task(id="001", name="Alpha", start_date=base,
                         end_date=base + timedelta(days=2))
        self.project.add_task(self.task)

    def tearDown(self):
        """Tear the root window down."""
        try:
            self.root.destroy()
        except Exception:
            pass

    def edit_dialog(self, **kwargs):
        """An edit dialog over the fixture task."""
        from gantt_app.views.taskdialogs import EditTaskDialog

        dialog = EditTaskDialog(self.root, self.task, self.project,
                                on_save=kwargs.pop('on_save', lambda t: None),
                                on_delete=lambda i: None, **kwargs)
        dialog.update_idletasks()
        return dialog

    def create_dialog(self, task_type="Task", **kwargs):
        """A create dialog for a new task."""
        from gantt_app.views.taskdialogs import CreateTaskDialog

        dialog = CreateTaskDialog(self.root, self.project,
                                  task_type=task_type, **kwargs)
        dialog.update_idletasks()
        return dialog

    def type_into(self, widget, text):
        """
        Replace what is in a box, as though it had been typed.

        DEVELOPMENT NOTES:
        ------------------
        Writing to the box is enough: the checks watch each field through a
        variable rather than a keyboard binding, so they see a change however
        it arrived - typed, picked from the calendar, or written by a
        dependency. Firing <KeyRelease> here would prove less than this does.
        """
        from gantt_app.views.datepicker import DateEntry

        entry = widget.entry if isinstance(widget, DateEntry) else widget
        entry.delete(0, tk.END)
        entry.insert(0, text)

    def marked(self, dialog, key):
        """Whether a field is currently outlined as wrong."""
        return bool(dialog._marked.get(key))

    def problem(self, dialog):
        """What the line under the form says."""
        return str(dialog.problem_label.cget('text'))


class TestTheFormStaysUsable(EditorTestCase):
    """
    The boxes survive being checked.

    A check that damages the widget it is checking is worse than no check at
    all, and this is what the first version of it did.
    """

    def test_the_name_can_still_be_read_after_opening(self):
        """Opening an edit dialog leaves the name box readable."""
        dialog = self.edit_dialog()

        self.assertEqual(dialog.name_entry.get(), "Alpha")

    def test_the_name_can_still_be_typed_into(self):
        """The name box takes text after the form has been checked."""
        dialog = self.edit_dialog()

        self.type_into(dialog.name_entry, "Renamed")

        self.assertEqual(dialog.name_entry.get(), "Renamed")

    def test_typing_raises_nothing(self):
        """No keystroke leaves an exception behind in a Tk callback."""
        dialog = self.edit_dialog()

        self.type_into(dialog.name_entry, "Renamed")
        self.type_into(dialog.start_date_entry, "2026-02-01")
        self.type_into(dialog.end_date_entry, "nonsense")
        self.type_into(dialog.end_date_entry, "2026-02-05")

        self.assertEqual(self.callback_errors, [])

    def test_opening_raises_nothing(self):
        """Neither dialog leaves an exception behind while it opens."""
        self.edit_dialog()
        self.create_dialog()
        self.create_dialog(task_type="Milestone")

        self.assertEqual(self.callback_errors, [])

    def test_a_saved_edit_keeps_the_typed_name(self):
        """The name reaches the task, which needs a working box to read."""
        saved = []
        dialog = self.edit_dialog(on_save=saved.append)

        self.type_into(dialog.name_entry, "Renamed")
        dialog.save()

        self.assertEqual(self.task.name, "Renamed")
        self.assertEqual(len(saved), 1)


class TestWhatTheFormComplainsAbout(EditorTestCase):
    """Which fields are marked, and what is said under the form."""

    def test_an_untouched_empty_name_is_left_alone(self):
        """A create dialog does not open with its empty name in red."""
        dialog = self.create_dialog()

        self.assertFalse(self.marked(dialog, 'name'))
        self.assertEqual(self.problem(dialog), "")

    def test_a_name_emptied_by_the_user_is_marked(self):
        """Clearing a name you have typed in is worth pointing out."""
        dialog = self.edit_dialog()

        self.type_into(dialog.name_entry, "")

        self.assertTrue(self.marked(dialog, 'name'))
        self.assertIn("name", self.problem(dialog))

    def test_a_date_that_will_not_parse_is_marked(self):
        """A misread date is pointed at as it is typed."""
        dialog = self.edit_dialog()

        self.type_into(dialog.start_date_entry, "15/08/2026")

        self.assertTrue(self.marked(dialog, 'start_date'))
        self.assertIn("YYYY-MM-DD", self.problem(dialog))

    def test_correcting_a_date_clears_the_mark(self):
        """The complaint goes away when the date is written properly."""
        dialog = self.edit_dialog()

        self.type_into(dialog.start_date_entry, "15/08/2026")
        self.type_into(dialog.start_date_entry, "2026-01-02")

        self.assertFalse(self.marked(dialog, 'start_date'))
        self.assertEqual(self.problem(dialog), "")

    def test_an_end_before_the_start_is_marked(self):
        """A task cannot finish before it begins."""
        dialog = self.edit_dialog()

        self.type_into(dialog.start_date_entry, "2026-03-10")
        self.type_into(dialog.end_date_entry, "2026-03-01")

        self.assertTrue(self.marked(dialog, 'end_date'))
        self.assertIn("before", self.problem(dialog))

    def test_a_milestone_is_not_asked_for_an_end_date(self):
        """Ticking Is Milestone withdraws the complaint about the end date."""
        dialog = self.edit_dialog()

        self.type_into(dialog.end_date_entry, "")
        self.assertTrue(self.marked(dialog, 'end_date'))

        dialog.is_milestone_var.set(True)
        dialog.toggle_milestone()

        self.assertFalse(self.marked(dialog, 'end_date'))

    def test_unticking_milestone_asks_for_the_end_date(self):
        """A task that is no longer a milestone needs one again."""
        dialog = self.edit_dialog()

        self.type_into(dialog.end_date_entry, "")
        dialog.is_milestone_var.set(True)
        dialog.toggle_milestone()

        dialog.is_milestone_var.set(False)
        dialog.toggle_milestone()

        self.assertTrue(self.marked(dialog, 'end_date'))

    def test_the_milestone_dialog_has_no_end_date_to_check(self):
        """Creating a milestone leaves the box out, and nothing looks for it."""
        dialog = self.create_dialog(task_type="Milestone")

        self.assertIsNone(dialog.end_date_entry)
        self.assertEqual(self.problem(dialog), "")

    def test_the_line_keeps_its_place_when_it_is_empty(self):
        """
        The message has a row whether or not it says anything.

        A line that appeared and disappeared would shift the form under the
        pointer on the keystroke that fixed a date.
        """
        dialog = self.edit_dialog()
        before = dialog.problem_label.winfo_manager()

        self.type_into(dialog.start_date_entry, "nonsense")

        self.assertEqual(dialog.problem_label.winfo_manager(), before)
        self.assertNotEqual(before, "")


class TestRefusingToSave(EditorTestCase):
    """What a save does with a form it will not accept."""

    def test_a_misread_end_date_does_not_wipe_the_one_it_had(self):
        """
        A date typed the wrong way round is refused, not read as nothing.

        It used to parse as None, which cleared the end date of the task
        being edited and reported nothing.
        """
        from gantt_app.views import dialogs

        dialog = self.edit_dialog()
        original_end = self.task.end_date

        self.type_into(dialog.end_date_entry, "01/02/2026")
        with mock.patch.object(dialogs, 'showerror') as reported:
            saved = dialog._apply()

        self.assertFalse(saved)
        self.assertEqual(self.task.end_date, original_end)
        self.assertTrue(reported.called)

    def test_a_refused_save_leaves_the_rest_of_the_task_alone(self):
        """Nothing is written until the whole form has been read."""
        from gantt_app.views import dialogs

        dialog = self.edit_dialog()

        self.type_into(dialog.name_entry, "Renamed")
        self.type_into(dialog.end_date_entry, "01/02/2026")
        with mock.patch.object(dialogs, 'showerror'):
            dialog._apply()

        self.assertEqual(self.task.name, "Alpha")

    def test_a_refused_save_marks_the_field_it_refused(self):
        """The offending box is outlined behind the message."""
        from gantt_app.views import dialogs

        dialog = self.create_dialog()

        with mock.patch.object(dialogs, 'showerror'):
            dialog._apply()

        self.assertTrue(self.marked(dialog, 'name'))

    def test_a_good_form_saves(self):
        """Nothing above stops an ordinary edit going through."""
        dialog = self.edit_dialog()

        self.type_into(dialog.name_entry, "Renamed")
        self.type_into(dialog.start_date_entry, "2026-04-01")
        self.type_into(dialog.end_date_entry, "2026-04-10")

        self.assertTrue(dialog._apply())
        self.assertEqual(self.task.name, "Renamed")
        self.assertEqual(self.task.start_date, datetime(2026, 4, 1))
        self.assertEqual(self.task.end_date, datetime(2026, 4, 10))


class TestCheckingIsCheap(EditorTestCase):
    """
    Typing does not redraw what it has not changed.

    Every configure() on a CustomTkinter widget redraws its canvas, and the
    scrolling frame around the form flushes a full layout pass when one of
    its children is touched. Reasserting a field's border on each keystroke
    was what made the editor feel heavy to type in.
    """

    def test_typing_in_a_good_field_touches_no_widget(self):
        """A keystroke that changes no verdict reconfigures nothing."""
        dialog = self.edit_dialog()
        touched = []
        original = dialog._mark

        def watch(key, widget, message):
            if dialog._marked.get(key, '') != message:
                touched.append(key)
            original(key, widget, message)

        dialog._mark = watch
        for character in "bcdef":
            dialog.name_entry.insert(tk.END, character)

        self.assertEqual(touched, [])

    def test_a_field_is_reconfigured_only_when_its_verdict_changes(self):
        """Going wrong marks it once; staying wrong does not mark it again."""
        dialog = self.edit_dialog()
        touched = []
        original = dialog._mark

        def watch(key, widget, message):
            if dialog._marked.get(key, '') != message:
                touched.append(key)
            original(key, widget, message)

        dialog._mark = watch
        for character in "xyz":
            dialog.start_date_entry.entry.insert(tk.END, character)

        self.assertEqual(touched, ['start_date'])


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestTheHelpButton(EditorTestCase):
    """The Help button beside Delete."""

    def tearDown(self):
        """Close the help window before tearing the root down."""
        from gantt_app.help.editorhelp import EditorHelpWindow

        if EditorHelpWindow._open_window is not None:
            EditorHelpWindow._open_window.close()
        super().tearDown()

    def test_it_opens_the_reference(self):
        """Pressing Help puts the reference on screen."""
        from gantt_app.help.editorhelp import EditorHelpWindow

        dialog = self.edit_dialog()
        dialog._show_editor_help()

        self.assertIsNotNone(EditorHelpWindow._open_window)
        self.assertTrue(EditorHelpWindow._open_window.winfo_exists())

    def test_the_reference_holds_every_section(self):
        """All the content reaches the body."""
        from gantt_app.help.editorhelp import EditorHelpWindow, HELP_SECTIONS

        window = EditorHelpWindow.show(self.root)
        body = window.text.get('1.0', tk.END)

        for heading, _paragraphs in HELP_SECTIONS:
            self.assertIn(heading, body)

    def test_pressing_help_twice_reuses_the_window(self):
        """The second press raises the first window rather than stacking one."""
        from gantt_app.help.editorhelp import EditorHelpWindow

        dialog = self.edit_dialog()
        dialog._show_editor_help()
        first = EditorHelpWindow._open_window
        dialog._show_editor_help()

        self.assertIs(EditorHelpWindow._open_window, first)

    def test_it_is_separate_from_the_dependency_reference(self):
        """
        The two Help buttons keep their own window.

        They share everything but their text, and a shared record of which
        one is open would have the editor's Help raise the dependency window.
        """
        from gantt_app.help.dependencyhelp import DependencyHelpWindow
        from gantt_app.help.editorhelp import EditorHelpWindow

        editor = EditorHelpWindow.show(self.root)
        dependency = DependencyHelpWindow.show(self.root)

        self.assertIsNot(editor, dependency)
        self.assertIs(EditorHelpWindow._open_window, editor)
        self.assertIs(DependencyHelpWindow._open_window, dependency)
        dependency.close()

    def test_the_body_scrolls(self):
        """
        The scrollbar is beside the text rather than squeezed to nothing.

        Packed after a body that already filled the frame, it came out zero
        pixels wide and a reference longer than the window could not be read
        past its first screen.
        """
        from gantt_app.help.editorhelp import EditorHelpWindow

        window = EditorHelpWindow.show(self.root)
        window.update_idletasks()
        scrollbars = [child
                      for child in window.text.master.winfo_children()
                      if child is not window.text]

        self.assertEqual(len(scrollbars), 1)
        self.assertEqual(int(scrollbars[0].grid_info().get('column')), 1)


if __name__ == '__main__':
    unittest.main()
