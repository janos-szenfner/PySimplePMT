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

    def edit_dialog_for(self, task, **kwargs):
        """An edit dialog over a given task."""
        from gantt_app.views.taskdialogs import EditTaskDialog

        dialog = EditTaskDialog(self.root, task, self.project,
                                on_save=lambda t: None,
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

    def let_the_end_date_be_typed(self, dialog):
        """
        Put the form in the mode where the end date is the user's to set.

        DEVELOPMENT NOTES:
        ------------------
        A task form opens on "End date is calculated", which greys the end
        date box out and works it out from the start date and the duration.
        Typing an end date means saying so first, which is what this does -
        the same two clicks a user makes.
        """
        dialog.scheduling_options_var.set("Duration is calculated")

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
        self.let_the_end_date_be_typed(dialog)
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

    def test_a_name_emptied_by_the_user_is_not_marked(self):
        """
        A blank name is allowed now, so clearing one says nothing. See #3.

        Nothing else on an untouched form complains either, so the problem
        line stays empty rather than moving on to the next field.
        """
        dialog = self.edit_dialog()

        self.type_into(dialog.name_entry, "")

        self.assertFalse(self.marked(dialog, 'name'))
        self.assertEqual(self.problem(dialog), "")

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
        self.let_the_end_date_be_typed(dialog)

        self.type_into(dialog.start_date_entry, "2026-03-10")
        self.type_into(dialog.end_date_entry, "2026-03-01")

        self.assertTrue(self.marked(dialog, 'end_date'))
        self.assertIn("before", self.problem(dialog))

    def test_a_milestone_is_not_asked_for_an_end_date(self):
        """Ticking Is Milestone withdraws the complaint about the end date."""
        dialog = self.edit_dialog()
        self.let_the_end_date_be_typed(dialog)

        self.type_into(dialog.end_date_entry, "")
        self.assertTrue(self.marked(dialog, 'end_date'))

        dialog.is_milestone_var.set(True)
        dialog.toggle_milestone()

        self.assertFalse(self.marked(dialog, 'end_date'))

    def test_unticking_milestone_asks_for_the_end_date(self):
        """A task that is no longer a milestone needs one again."""
        dialog = self.edit_dialog()
        self.let_the_end_date_be_typed(dialog)

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
        self.let_the_end_date_be_typed(dialog)
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
        self.let_the_end_date_be_typed(dialog)

        self.type_into(dialog.name_entry, "Renamed")
        self.type_into(dialog.end_date_entry, "01/02/2026")
        with mock.patch.object(dialogs, 'showerror'):
            dialog._apply()

        self.assertEqual(self.task.name, "Alpha")

    def test_a_refused_save_marks_the_field_it_refused(self):
        """
        The offending box is outlined behind the message.

        Refused for a malformed date rather than an empty name: an empty
        name is no longer a reason to refuse a save. See issue #3.
        """
        from gantt_app.views import dialogs

        dialog = self.edit_dialog()
        self.let_the_end_date_be_typed(dialog)
        self.type_into(dialog.start_date_entry, "15/08/2026")

        with mock.patch.object(dialogs, 'showerror'):
            dialog._apply()

        self.assertTrue(self.marked(dialog, 'start_date'))

    def test_a_good_form_saves(self):
        """Nothing above stops an ordinary edit going through."""
        dialog = self.edit_dialog()
        self.let_the_end_date_be_typed(dialog)

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


class TestFieldsTheFormFillsInItself(EditorTestCase):
    """
    A box the user cannot type in looks like one.

    WHY THESE EXIST:
    ================
    A disabled CustomTkinter box is only very slightly paler than a live
    one, so the end date - greyed out because the scheduling mode is
    deriving it - looked exactly like the start date you are meant to fill
    in. There was nothing on the form to say which was which.
    """

    def state_of(self, dialog, widget):
        """A field's state, background and caption colour."""
        entry = dialog._entry_of(widget)
        caption = dialog._field_labels.get(widget)
        return (str(entry.cget('state')),
                entry.cget('fg_color'),
                caption.cget('text_color') if caption else None)

    def test_the_calculated_date_is_greyed(self):
        """It is the form's to fill in, not the user's."""
        from gantt_app.views.taskform import TaskFormDialog

        dialog = self.edit_dialog()
        state, background, caption = self.state_of(dialog,
                                                   dialog.end_date_entry)

        self.assertEqual(state, 'disabled')
        self.assertEqual(background, TaskFormDialog.FIELD_BG_DISABLED)
        self.assertEqual(caption, TaskFormDialog.FIELD_TEXT_DISABLED)

    def test_the_boxes_the_user_fills_in_are_not(self):
        """The start date and the duration stay live and plain."""
        from gantt_app.views.taskform import TaskFormDialog

        dialog = self.edit_dialog()

        for widget in (dialog.start_date_entry, dialog.duration_entry):
            state, background, caption = self.state_of(dialog, widget)

            self.assertEqual(state, 'normal')
            self.assertEqual(background, TaskFormDialog.FIELD_BG)
            self.assertEqual(caption, TaskFormDialog.FIELD_TEXT)

    def test_the_greying_follows_the_scheduling_mode(self):
        """Whichever box the mode names is the one that greys."""
        from gantt_app.views.taskform import TaskFormDialog

        dialog = self.edit_dialog()
        dialog.scheduling_options_var.set("Duration is calculated")

        duration = self.state_of(dialog, dialog.duration_entry)
        end = self.state_of(dialog, dialog.end_date_entry)

        self.assertEqual(duration[0], 'disabled')
        self.assertEqual(duration[1], TaskFormDialog.FIELD_BG_DISABLED)
        self.assertEqual(end[0], 'normal')
        self.assertEqual(end[1], TaskFormDialog.FIELD_BG)

    def test_a_container_greys_everything_it_rolls_up(self):
        """A phase takes its dates and its length from the work inside it."""
        from gantt_app.models import Task
        from gantt_app.views.taskform import TaskFormDialog

        phase = Task(id="P1", name="Planning", task_type="Phase",
                     start_date=datetime(2026, 1, 1),
                     end_date=datetime(2026, 1, 8))
        self.project.add_task(phase)
        dialog = self.edit_dialog_for(phase)

        for widget in (dialog.start_date_entry, dialog.end_date_entry,
                       dialog.duration_entry):
            state, background, _caption = self.state_of(dialog, widget)

            self.assertEqual(state, 'disabled')
            self.assertEqual(background, TaskFormDialog.FIELD_BG_DISABLED)

    def test_every_box_on_the_form_is_painted_by_the_same_rule(self):
        """
        None left on the toolkit's own theme colours.

        Painting only the boxes something greys out left the rest on
        CustomTkinter's defaults, so two live boxes on one form could be
        different shades of white.
        """
        from gantt_app.views.taskform import TaskFormDialog

        dialog = self.edit_dialog()
        ours = (TaskFormDialog.FIELD_BG, TaskFormDialog.FIELD_BG_DISABLED)

        boxes = {
            'name': dialog.name_entry,
            'start date': dialog.start_date_entry,
            'end date': dialog.end_date_entry,
            'duration': dialog.duration_entry,
            'progress': dialog.progress_entry,
            'notes': dialog.details_text,
            'earliest begin': dialog.earliest_begin_entry,
        }
        for label, widget in boxes.items():
            background = dialog._entry_of(widget).cget('fg_color')

            self.assertIn(background, ours,
                          f"the {label} box is on a theme colour")

    def test_painting_a_field_does_not_wake_it_up(self):
        """
        The colour is read off the widget, not decided again.

        A field painted with its own state cannot quietly re-enable one
        that was built disabled.
        """
        from gantt_app.views.taskform import TaskFormDialog

        dialog = self.edit_dialog()
        dialog._paint_field(dialog.end_date_entry)

        entry = dialog._entry_of(dialog.end_date_entry)

        self.assertEqual(str(entry.cget('state')), 'disabled')
        self.assertEqual(entry.cget('fg_color'),
                         TaskFormDialog.FIELD_BG_DISABLED)

    def test_the_earliest_begin_date_waits_for_its_tick_box(self):
        """
        It means nothing until it is asked for, so it is greyed until then.

        Which is what the reference this form follows does with it.
        """
        from gantt_app.views.taskform import TaskFormDialog

        dialog = self.edit_dialog()
        entry = dialog._entry_of(dialog.earliest_begin_entry)

        self.assertEqual(str(entry.cget('state')), 'disabled')
        self.assertEqual(entry.cget('fg_color'),
                         TaskFormDialog.FIELD_BG_DISABLED)

        dialog.earliest_begin_var.set(True)

        self.assertEqual(str(entry.cget('state')), 'normal')
        self.assertEqual(entry.cget('fg_color'), TaskFormDialog.FIELD_BG)

    def test_a_caption_goes_back_to_black_when_its_box_comes_back(self):
        """Greying is undone, not only applied."""
        from gantt_app.views.taskform import TaskFormDialog

        dialog = self.edit_dialog()
        dialog.scheduling_options_var.set("Duration is calculated")
        dialog.scheduling_options_var.set("End date is calculated")

        _state, _background, caption = self.state_of(dialog,
                                                     dialog.duration_entry)

        self.assertEqual(caption, TaskFormDialog.FIELD_TEXT)

class TestTheCalculatedBoxKeepsUp(EditorTestCase):
    """
    The box the mode is deriving updates as the form is filled in.

    WHY THESE EXIST:
    ================
    The three date fields were watched through a variable and the duration box
    was not, so on the setting every task opens with - End date is calculated -
    typing a duration changed nothing on screen. The end date caught up only
    when Save read the form back, which meant the number in front of the user
    and the date beside it disagreed right up until the task was saved.

    Dates here are read against a Monday-to-Friday calendar: the fixture task
    starts on Monday 5 January 2026.
    """

    def setUp(self):
        """Move the fixture onto a Monday so the weekends are predictable."""
        super().setUp()
        self.task.start_date = datetime(2026, 1, 5)
        self.task.end_date = datetime(2026, 1, 7)

    def shown(self, widget):
        """What a box currently shows."""
        from gantt_app.views.datepicker import DateEntry

        entry = widget.entry if isinstance(widget, DateEntry) else widget
        return entry.get()

    def test_typing_a_duration_moves_the_end_date(self):
        """Ten days from the Monday reaches the Friday of the second week."""
        dialog = self.edit_dialog()

        self.type_into(dialog.duration_entry, "10")

        self.assertEqual(self.shown(dialog.end_date_entry), "2026-01-16")
        self.assertEqual(self.callback_errors, [])

    def test_typing_a_duration_moves_the_start_date(self):
        """The mirror, for a plan working back from a finish date."""
        dialog = self.edit_dialog()
        dialog.scheduling_options_var.set("Start date is calculated")

        self.type_into(dialog.duration_entry, "3")

        self.assertEqual(self.shown(dialog.start_date_entry), "2026-01-05")

    def test_typing_a_date_moves_the_duration(self):
        """The other direction was already watched, and stays watched."""
        dialog = self.edit_dialog()
        dialog.scheduling_options_var.set("Duration is calculated")

        self.type_into(dialog.end_date_entry, "2026-01-09")

        self.assertEqual(self.shown(dialog.duration_entry), "5")

    def test_the_end_date_follows_the_start_date_too(self):
        """Moving the start with a duration typed moves the finish with it."""
        dialog = self.edit_dialog()

        self.type_into(dialog.duration_entry, "5")
        self.type_into(dialog.start_date_entry, "2026-01-12")

        self.assertEqual(self.shown(dialog.end_date_entry), "2026-01-16")

    def test_a_weekend_is_crossed_as_the_duration_is_typed(self):
        """
        What the box shows is what the scheduler would settle on.

        Five days from a Thursday ends on the following Wednesday. A form
        working in calendar days would have shown the Monday, and saving it
        would then have moved the task - the form disagreeing with the plan
        the moment it was saved.
        """
        dialog = self.edit_dialog()

        self.type_into(dialog.start_date_entry, "2026-01-01")
        self.type_into(dialog.duration_entry, "5")

        self.assertEqual(self.shown(dialog.end_date_entry), "2026-01-07")

    def test_an_unreadable_duration_leaves_the_date_alone(self):
        """
        Half-typed input is what typing looks like.

        The box is written to on every keystroke, so a duration that is not a
        number yet cannot be allowed to raise or to blank the date beside it.
        """
        dialog = self.edit_dialog()
        before = self.shown(dialog.end_date_entry)

        self.type_into(dialog.duration_entry, "")
        self.type_into(dialog.duration_entry, "nonsense")

        self.assertEqual(self.shown(dialog.end_date_entry), before)
        self.assertEqual(self.callback_errors, [])

    def test_un_ticking_milestone_fills_the_end_date_in(self):
        """
        A milestone becoming a task again gets its finish worked out.

        The end date box was enabled directly rather than through the form's
        own rules, so it came back empty and typable even though the mode was
        deriving it.
        """
        dialog = self.edit_dialog()
        dialog.is_milestone_var.set(True)
        dialog.toggle_milestone()
        dialog.is_milestone_var.set(False)
        dialog.toggle_milestone()

        self.assertEqual(self.shown(dialog.end_date_entry), "2026-01-07")
        self.assertEqual(self.callback_errors, [])

    def test_choosing_a_container_type_greys_what_it_rolls_up(self):
        """A Phase takes its dates and its length from the work inside it."""
        import tkinter as tk

        dialog = self.edit_dialog()
        dialog.task_type_var.set("Phase")

        for widget in (dialog.start_date_entry, dialog.end_date_entry,
                       dialog.duration_entry):
            entry = dialog._entry_of(widget)
            self.assertEqual(str(entry.cget('state')), tk.DISABLED)


if __name__ == '__main__':
    unittest.main()
