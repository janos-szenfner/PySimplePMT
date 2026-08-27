"""
Tests for the task dialogs' buttons and their date pickers.

DEVELOPMENT NOTES:
------------------
Both need real widgets, so the module skips without a display; CI provides
one through xvfb.
"""

import unittest
from datetime import datetime, timedelta
from unittest import mock

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
class DialogTestCase(unittest.TestCase):
    """Shared fixture: a root window and a project with one task."""

    def setUp(self):
        """Build the window and the project."""
        import customtkinter as ctk

        self.root = ctk.CTk()
        self.root.withdraw()

        self.project = Project(name="Test Project")
        base = datetime(2026, 1, 1)
        self.task = Task(id="001", name="Alpha", start_date=base,
                         end_date=base + timedelta(days=2))
        self.project.add_task(self.task)
        self.project.add_task(Task(id="002", name="Beta", start_date=base,
                                   end_date=base + timedelta(days=2)))

    def tearDown(self):
        """Tear the root window down."""
        try:
            self.root.destroy()
        except Exception:
            pass

    def button_row(self, dialog):
        """
        The dialog's own buttons, left to right.

        Only the bottom row: the Dependency tab has buttons of its own, and
        the date pickers each carry a calendar button.

        DEVELOPMENT NOTES:
        ------------------
        Worked out from how each button is packed rather than from where it
        ended up. Sorting on winfo_x needs the row laid out at its final
        width, which it is not until the window has been mapped and sized -
        under xvfb the positions came back meaningless and the order looked
        wrong when it was not.

        pack puts LEFT children on in creation order, and RIGHT children on
        from the right edge inwards, so reversing the RIGHT ones gives what
        a reader sees.
        """
        import customtkinter as ctk
        import tkinter as tk

        frame = dialog.winfo_children()[-1]
        buttons = [w for w in frame.winfo_children()
                   if isinstance(w, ctk.CTkButton)]

        left, right = [], []
        for button in buttons:
            side = str(button.pack_info().get('side', tk.LEFT))
            (right if side == tk.RIGHT else left).append(
                str(button.cget('text'))
            )

        return left + right[::-1]


class TestEditDialogButtons(DialogTestCase):
    """The edit dialog's button row."""

    def dialog(self, **kwargs):
        """An edit dialog over the fixture task."""
        from gantt_app.views.taskdialogs import EditTaskDialog

        dialog = EditTaskDialog(self.root, self.task, self.project,
                                on_save=lambda t: None,
                                on_delete=lambda i: None, **kwargs)
        dialog.update_idletasks()
        return dialog

    def test_the_buttons_read_in_order(self):
        """Help, Delete sit apart, then Cancel, Save & Close, Save & New."""
        self.assertEqual(self.button_row(self.dialog()),
                         ["Help", "Delete", "Cancel", "Save & Close",
                          "Save & New"])

    def test_the_way_out_is_called_cancel(self):
        """
        It was called Close, on the grounds that nothing is written until a
        Save is pressed, so there was nothing to cancel.

        That is still true of the behaviour and it is the wrong name anyway:
        the key that does it is Escape, every dialog in every application
        calls that Cancel, and a button whose shortcut and label disagree is
        one the reader has to think about.
        """
        self.assertIn("Cancel", self.button_row(self.dialog()))

    def test_save_and_close_saves(self):
        """The renamed task is stored."""
        dialog = self.dialog()
        dialog.name_entry.delete(0, 'end')
        dialog.name_entry.insert(0, "Renamed")

        dialog.save()

        self.assertEqual(self.task.name, "Renamed")

    def test_save_and_close_closes(self):
        """The window goes away."""
        dialog = self.dialog()

        dialog.save()

        self.assertFalse(dialog.winfo_exists())

    def test_close_discards(self):
        """Closing without saving leaves the task alone."""
        dialog = self.dialog()
        dialog.name_entry.delete(0, 'end')
        dialog.name_entry.insert(0, "Not saved")

        dialog.cancel()

        self.assertEqual(self.task.name, "Alpha")

    def test_save_and_new_saves_then_opens_a_new_form(self):
        """The edit is kept and a fresh form is asked for."""
        opened = []
        dialog = self.dialog(on_new=lambda: opened.append(True))
        dialog.name_entry.delete(0, 'end')
        dialog.name_entry.insert(0, "Renamed")

        dialog.save_and_new()

        self.assertEqual(self.task.name, "Renamed")
        self.assertFalse(dialog.winfo_exists())
        self.assertEqual(opened, [True])

    def test_save_and_new_opens_nothing_when_the_save_fails(self):
        """
        A bad date leaves the form up rather than replacing it.

        Losing what was typed because the date was wrong would be a poor
        trade for a button press.
        """
        opened = []
        dialog = self.dialog(on_new=lambda: opened.append(True))
        dialog.start_date_entry.delete(0, 'end')
        dialog.start_date_entry.insert(0, "nonsense")

        with mock.patch('gantt_app.views.taskform.messagebox.showerror'):
            dialog.save_and_new()

        self.assertEqual(opened, [])
        self.assertTrue(dialog.winfo_exists())

    def test_a_bad_date_is_reported(self):
        """The dialog says why it will not save."""
        dialog = self.dialog()
        dialog.start_date_entry.delete(0, 'end')
        dialog.start_date_entry.insert(0, "nonsense")

        with mock.patch('gantt_app.views.taskform.messagebox.showerror') as err:
            dialog.save()

        self.assertTrue(err.called)
        self.assertTrue(dialog.winfo_exists())


class TestCreateDialogButtons(DialogTestCase):
    """The create dialog's button row and its Save & New."""

    def dialog(self, on_save=None):
        """A create dialog collecting saved tasks."""
        from gantt_app.views.taskdialogs import CreateTaskDialog

        dialog = CreateTaskDialog(self.root, self.project,
                                  on_save=on_save or (lambda t: None))
        dialog.update_idletasks()
        return dialog

    def test_the_buttons_read_in_order(self):
        """Help, no Delete here - the task does not exist yet."""
        self.assertEqual(self.button_row(self.dialog()),
                         ["Help", "Cancel", "Save & Close", "Save & New"])

    def test_save_and_new_keeps_the_dialog_open(self):
        """
        Entering a run of tasks is the point of the button.

        A window that blinks away and back loses its position and the field
        the user was about to type in.
        """
        dialog = self.dialog()
        dialog.name_entry.insert(0, "First")

        dialog.save_and_new()

        self.assertTrue(dialog.winfo_exists())

    def test_save_and_new_creates_each_task(self):
        """Pressing it twice yields two tasks."""
        saved = []
        dialog = self.dialog(on_save=saved.append)

        dialog.name_entry.insert(0, "First")
        dialog.save_and_new()
        dialog.name_entry.insert(0, "Second")
        dialog.save_and_new()

        self.assertEqual([t.name for t in saved], ["First", "Second"])

    def test_the_name_is_cleared_for_the_next_one(self):
        """The field that changes every time starts empty."""
        dialog = self.dialog()
        dialog.name_entry.insert(0, "First")

        dialog.save_and_new()

        self.assertEqual(dialog.name_entry.get(), "")

    def test_the_dates_are_carried_over(self):
        """
        A run of tasks usually sits in the same part of the plan.

        Clearing the dates would mean setting them again for every one.
        """
        dialog = self.dialog()
        start = dialog.start_date_entry.get()
        dialog.name_entry.insert(0, "First")

        dialog.save_and_new()

        self.assertEqual(dialog.start_date_entry.get(), start)

    def test_nothing_is_cleared_when_the_save_fails(self):
        """A rejected form is left as it was for correcting."""
        dialog = self.dialog()
        dialog.name_entry.insert(0, "Kept")
        dialog.start_date_entry.delete(0, 'end')
        dialog.start_date_entry.insert(0, "nonsense")

        with mock.patch('gantt_app.views.taskform.messagebox.showerror'):
            dialog.save_and_new()

        self.assertEqual(dialog.name_entry.get(), "Kept")


class TestDateEntry(DialogTestCase):
    """The date box and the calendar behind it."""

    def entry(self, date=None):
        """A date box over the root window."""
        from gantt_app.views.datepicker import DateEntry

        widget = DateEntry(self.root, date=date)
        widget.update_idletasks()
        return widget

    def test_it_shows_the_date_given(self):
        """The box opens on the task's own date."""
        widget = self.entry(datetime(2026, 3, 9))

        self.assertEqual(widget.get(), "2026-03-09")

    def test_it_starts_empty_without_one(self):
        """A task with no end date gets an empty box."""
        self.assertEqual(self.entry().get(), "")

    def test_it_parses_what_it_holds(self):
        """get_date reads the text back."""
        widget = self.entry(datetime(2026, 3, 9))

        self.assertEqual(widget.get_date(), datetime(2026, 3, 9))

    def test_unparseable_text_reads_as_nothing(self):
        """Typing something odd does not raise."""
        widget = self.entry()
        widget.insert(0, "nonsense")

        self.assertIsNone(widget.get_date())

    def test_it_can_still_be_typed_into(self):
        """The calendar is a way in, not a replacement for the keyboard."""
        widget = self.entry()
        widget.insert(0, "2026-12-25")

        self.assertEqual(widget.get_date(), datetime(2026, 12, 25))

    def test_picking_fills_the_box(self):
        """A date chosen from the calendar lands in the entry."""
        widget = self.entry(datetime(2026, 3, 1))
        calendar_popup = widget.open_calendar()

        calendar_popup.pick(datetime(2027, 5, 4))

        self.assertEqual(widget.get(), "2027-05-04")

    def test_the_calendar_opens_on_the_current_value(self):
        """It starts on the month the box already holds."""
        widget = self.entry(datetime(2026, 3, 9))

        calendar_popup = widget.open_calendar()

        self.assertEqual(calendar_popup._title.cget('text'), "March 2026")

    def test_the_months_step(self):
        """Both arrows move a month and roll over the year."""
        widget = self.entry(datetime(2026, 12, 1))
        calendar_popup = widget.open_calendar()

        calendar_popup.next_month()

        self.assertEqual(calendar_popup._title.cget('text'), "January 2027")

    def test_it_steps_back_over_a_year_boundary(self):
        """The other direction too."""
        widget = self.entry(datetime(2026, 1, 1))
        calendar_popup = widget.open_calendar()

        calendar_popup.previous_month()

        self.assertEqual(calendar_popup._title.cget('text'), "December 2025")

    def test_every_day_of_the_month_is_offered(self):
        """A 31-day month draws 31 buttons."""
        widget = self.entry(datetime(2026, 1, 15))
        calendar_popup = widget.open_calendar()

        self.assertEqual(len(calendar_popup.day_buttons), 31)

    def test_february_in_a_leap_year(self):
        """The calendar module handles the awkward month."""
        widget = self.entry(datetime(2028, 2, 1))
        calendar_popup = widget.open_calendar()

        self.assertEqual(len(calendar_popup.day_buttons), 29)

    def test_disabling_it_disables_the_calendar_too(self):
        """
        A milestone's end date is switched off, button and all.

        Leaving the button live would let the box be filled from behind a
        disabled entry.
        """
        widget = self.entry(datetime(2026, 3, 9))

        widget.configure(state='disabled')

        self.assertEqual(str(widget.button.cget('state')), 'disabled')
        self.assertIsNone(widget.open_calendar())

    def test_setting_a_date_works_while_disabled(self):
        """
        Rescheduling still writes through a disabled box.

        Choosing a predecessor moves the dates, and a milestone's end box is
        disabled - the value still has to get in.
        """
        widget = self.entry(datetime(2026, 3, 9))
        widget.configure(state='disabled')

        widget.set_date(datetime(2026, 4, 1))

        self.assertEqual(widget.get(), "2026-04-01")
        self.assertEqual(str(widget.entry.cget('state')), 'disabled')


class TestCalendarIcon(unittest.TestCase):
    """The glyph on the button that opens the month view."""

    def test_it_is_drawn_not_a_font_glyph(self):
        """
        The icon is painted, so it needs no emoji font.

        It used to be the '\U0001f4c5' character. A stock Linux desktop often
        has no font carrying it, and the button came out blank - a plain blue
        rectangle with nothing on it.
        """
        from gantt_app.views.datepicker import _draw_calendar

        image = _draw_calendar(16)

        self.assertEqual(image.size, (16, 16))
        self.assertEqual(image.mode, 'RGBA')

    def test_it_actually_has_something_on_it(self):
        """A blank icon would pass a size check but show nothing."""
        from gantt_app.views.datepicker import _draw_calendar

        image = _draw_calendar(16)
        inked = sum(1 for pixel in image.getdata() if pixel[3] > 60)

        self.assertGreater(inked, 40)
        self.assertLess(inked, 16 * 16)

    def test_the_drawing_is_reused(self):
        """Painting happens once, however many boxes ask for it."""
        from gantt_app.views import datepicker

        datepicker._ICON_IMAGE = None
        datepicker.calendar_icon()
        first = datepicker._ICON_IMAGE
        datepicker.calendar_icon()

        self.assertIs(datepicker._ICON_IMAGE, first)


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestIconWrapping(DialogTestCase):
    """
    A fresh wrapper is made per box, over the one cached drawing.

    DEVELOPMENT NOTES:
    ------------------
    A Tk image belongs to the interpreter that made it and stops existing
    when that window goes. Caching the CTkImage rather than the picture made
    every dialog after the first fail with 'image "pyimage1" doesn\'t exist'.
    """

    def test_the_button_carries_the_icon(self):
        """The box shows a picture, not a character."""
        from gantt_app.views.datepicker import DateEntry

        entry = DateEntry(self.root)

        self.assertEqual(entry.button.cget('text'), '')
        self.assertIsNotNone(entry.button.cget('image'))

    def test_a_second_window_still_gets_one(self):
        """The cached drawing outlives the window that first asked for it."""
        import customtkinter as ctk
        from gantt_app.views.datepicker import DateEntry

        DateEntry(self.root)
        self.root.destroy()

        self.root = ctk.CTk()
        self.root.withdraw()
        entry = DateEntry(self.root)

        self.assertIsNotNone(entry.button.cget('image'))


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestDependencyTabIsLazy(DialogTestCase):
    """
    The Dependency tab is filled in when it is first opened.

    DEVELOPMENT NOTES:
    ------------------
    It cost about ten of the twenty-six milliseconds a dialog took to open,
    and most edits are a name or a date and never go near it.
    """

    def dialog(self):
        """An edit dialog over the fixture task."""
        from gantt_app.views.taskdialogs import EditTaskDialog

        return EditTaskDialog(self.root, self.task, self.project,
                              on_save=lambda t: None,
                              on_delete=lambda i: None)

    def test_it_is_not_built_on_open(self):
        """Opening the dialog does not pay for it."""
        self.assertIsNone(self.dialog()._dependency_editor)

    def test_opening_the_tab_builds_it(self):
        """Looking at the tab is what brings it into being."""
        dialog = self.dialog()

        dialog.tabs.set("Dependency")
        dialog._on_tab_changed()

        self.assertIsNotNone(dialog._dependency_editor)

    def test_asking_for_it_builds_it(self):
        """Reaching for the links is asking for the editor."""
        dialog = self.dialog()

        editor = dialog.dependency_editor

        self.assertIsNotNone(editor)
        self.assertIs(dialog._dependency_editor, editor)

    def test_saving_without_opening_leaves_the_links_alone(self):
        """
        An untouched tab means untouched links.

        Reading an editor that was never built would have replaced the task's
        real links with whatever an empty one returned.
        """
        self.task.add_dependency("002", 'FS', 'Hard')
        dialog = self.dialog()

        dialog.save()

        self.assertEqual(self.task.dependency_ids, ["002"])

    def test_changes_made_on_the_tab_are_saved(self):
        """Once opened, it behaves as it always did."""
        self.task.add_dependency("002", 'FS', 'Hard')
        dialog = self.dialog()
        dialog.dependency_editor.links = []

        dialog.save()

        self.assertEqual(self.task.dependency_ids, [])


class TestButtonWidths(DialogTestCase):
    """
    The bottom row is evenly sized and fits the smallest window.

    DEVELOPMENT NOTES:
    ------------------
    CTkButton defaults to 140 and only the two longest labels had a width
    set, so Close came out wider than Save & Close and the row's widths ran
    backwards against the length of what was written on them.
    """

    def widths(self, dialog):
        """Each bottom button's requested width, by label."""
        import customtkinter as ctk

        dialog.update_idletasks()
        frame = dialog.winfo_children()[-1]
        return {str(w.cget('text')): w.winfo_reqwidth()
                for w in frame.winfo_children()
                if isinstance(w, ctk.CTkButton)}

    def edit_dialog(self):
        """An edit dialog over the fixture task."""
        from gantt_app.views.taskdialogs import EditTaskDialog

        return EditTaskDialog(self.root, self.task, self.project,
                              on_save=lambda t: None,
                              on_delete=lambda i: None)

    def create_dialog(self):
        """A create dialog."""
        from gantt_app.views.taskdialogs import CreateTaskDialog

        return CreateTaskDialog(self.root, self.project,
                                on_save=lambda t: None)

    def test_the_save_buttons_match(self):
        """The three actions on the right are one width."""
        widths = self.widths(self.edit_dialog())

        self.assertEqual(widths["Cancel"], widths["Save & Close"])
        self.assertEqual(widths["Cancel"], widths["Save & New"])

    def test_cancel_is_not_the_widest(self):
        """
        The shortest label had the widest button.

        Close was left at the CTkButton default of 140 while Save & Close,
        which is twice the text, was set to 120.
        """
        widths = self.widths(self.edit_dialog())

        self.assertLessEqual(widths["Cancel"], widths["Save & Close"])

    def test_the_create_dialog_matches_too(self):
        """Both dialogs use the same widths."""
        edit = self.widths(self.edit_dialog())
        create = self.widths(self.create_dialog())

        self.assertEqual(create["Cancel"], edit["Cancel"])
        self.assertEqual(create["Save & Close"], edit["Save & Close"])

    def test_the_row_fits_the_minimum_window(self):
        """
        Nothing is clipped when the dialog is squeezed as far as it goes.

        Widening the buttons to match is only an improvement if they all
        still fit.
        """
        dialog = self.edit_dialog()
        widths = self.widths(dialog)

        # each button carries padx=5 either side, the frame padx=20
        needed = sum(widths.values()) + 10 * len(widths) + 40

        self.assertLessEqual(needed, dialog.MINSIZE[0])


class TestAppearanceIsPinned(unittest.TestCase):
    """
    The system theme is read once, not polled.

    DEVELOPMENT NOTES:
    ------------------
    set_appearance_mode("system") leaves CustomTkinter re-reading the setting
    every 30ms. On Linux darkdetect answers that by running gsettings through
    subprocess, so it was spawning thirty-odd processes a second, each one
    blocking the event loop it was called from.
    """

    def test_it_sets_an_explicit_mode(self):
        """Never 'system', which is the mode that polls."""
        from unittest import mock
        from gantt_app.main import set_appearance_from_system

        with mock.patch('customtkinter.set_appearance_mode') as setter:
            set_appearance_from_system()

        self.assertIn(setter.call_args[0][0], ('light', 'dark'))

    def test_it_follows_a_dark_desktop(self):
        """A dark system setting gives a dark window."""
        from unittest import mock
        from gantt_app.main import set_appearance_from_system

        with mock.patch('darkdetect.theme', return_value='Dark'), \
                mock.patch('customtkinter.set_appearance_mode') as setter:
            set_appearance_from_system()

        self.assertEqual(setter.call_args[0][0], 'dark')

    def test_a_detector_that_fails_falls_back_to_light(self):
        """A missing or broken detector must not stop the app starting."""
        from unittest import mock
        from gantt_app.main import set_appearance_from_system

        with mock.patch('darkdetect.theme', side_effect=OSError("no")), \
                mock.patch('customtkinter.set_appearance_mode') as setter:
            mode = set_appearance_from_system()

        self.assertEqual(mode, 'light')
        self.assertEqual(setter.call_args[0][0], 'light')


if __name__ == '__main__':
    unittest.main()


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestTheKeyboardExits(DialogTestCase):
    """
    Enter saves and closes, Escape cancels.

    WHY THESE LOOK LIKE THIS:
    =========================
    A run of edits down a task list is a keyboard job, and reaching for the
    mouse to confirm each one is the friction the shortcuts exist to remove.

    The interesting case is the notes box. Enter means a newline in there,
    so the handler has to leave it alone - and it can, because Tk runs the
    text widget's own binding first and the newline is already typed by the
    time the window's handler is reached.

    The keys cannot be pressed here: Tk does not deliver a synthetic key
    event to a window that has never been mapped, and every window in a test
    run is withdrawn. So the handlers are called directly, which is the same
    code the key reaches.
    """

    def dialog(self):
        """An edit dialog over the fixture task."""
        from gantt_app.views.taskdialogs import EditTaskDialog

        dialog = EditTaskDialog(self.root, self.task, self.project,
                                on_save=lambda t: None,
                                on_delete=lambda i: None)
        dialog.update_idletasks()
        return dialog

    def test_enter_saves_and_closes(self):
        """The default action, from anywhere that is not a text area."""
        dialog = self.dialog()
        dialog.name_entry.delete(0, 'end')
        dialog.name_entry.insert(0, "Renamed by Enter")

        dialog._return_pressed()

        self.assertEqual(self.task.name, "Renamed by Enter")
        self.assertFalse(dialog.winfo_exists())

    def test_enter_stops_there(self):
        """
        It reports that it handled the key.

        Without that the same press reaches whatever else is listening,
        which for a form inside a window with its own bindings means the
        action running twice.
        """
        dialog = self.dialog()

        self.assertEqual(dialog._return_pressed(), 'break')

    def test_enter_in_the_notes_box_types_a_newline(self):
        """
        And does not save.

        The newline is already in the box by the time the window's handler
        runs, so all it has to do is keep out of the way.

        The focus is reported rather than set. focus_set does nothing on a
        window that has never been mapped, so the real widget is handed to
        the handler the way Tk would hand it over - which is what the branch
        actually reads.
        """
        dialog = self.dialog()
        inner = dialog.details_text.winfo_children()[0]

        with mock.patch.object(dialog, 'focus_get', return_value=inner):
            result = dialog._return_pressed()

        self.assertIsNone(result, "it should not claim the key")
        self.assertTrue(dialog.winfo_exists(), "it should not have closed")

    def test_the_wrapper_counts_as_the_box_too(self):
        """
        Which of the two Tk names as the focus depends on the version.

        A check against only the inner text widget passes on one release of
        CustomTkinter and saves the form on the next.
        """
        dialog = self.dialog()

        with mock.patch.object(dialog, 'focus_get',
                               return_value=dialog.details_text):
            self.assertTrue(dialog._focus_is_multiline())

    def test_a_single_line_field_is_not_a_text_area(self):
        """Enter in the name box saves, which is the whole point."""
        dialog = self.dialog()

        with mock.patch.object(dialog, 'focus_get',
                               return_value=dialog.name_entry):
            self.assertFalse(dialog._focus_is_multiline())

    def test_the_modifier_saves_from_the_notes_box(self):
        """The way out of a multi-line field, as everywhere else."""
        dialog = self.dialog()

        dialog.save()

        self.assertFalse(dialog.winfo_exists())

    def test_escape_closes_without_saving(self):
        """What was typed is discarded, which is what Cancel means."""
        dialog = self.dialog()
        dialog.name_entry.delete(0, 'end')
        dialog.name_entry.insert(0, "Not saved")

        dialog.cancel()

        self.assertEqual(self.task.name, "Alpha")
        self.assertFalse(dialog.winfo_exists())

    def test_all_the_exit_keys_are_bound(self):
        """
        Enter, the keypad's Enter, Escape, and the modifier form of each.

        Matched on the key rather than the modifier: Tk stores a binding
        under a spelling of its own - <Command-Return> comes back as
        <Mod1-Key-Return> - and which modifier goes in is pinned in
        test_shortcuts.py.
        """
        bound = self.dialog().bind()

        self.assertIn('<Key-Return>', bound)
        self.assertIn('<Key-Escape>', bound)
        self.assertTrue(
            any(sequence.endswith('-Key-Return>') and sequence != '<Key-Return>'
                for sequence in bound),
            "the modifier form of Enter is not bound")

    def test_the_primary_action_looks_like_one(self):
        """
        Save & Close is the call to action; Cancel is the quiet way out.

        A row of three identical buttons says nothing about which one Enter
        performs.
        """
        dialog = self.dialog()

        primary = dialog.action_buttons["Save & Close"]
        secondary = dialog.action_buttons["Cancel"]

        self.assertNotEqual(str(primary.cget('fg_color')), 'transparent')
        self.assertEqual(str(secondary.cget('fg_color')), 'transparent')
        self.assertGreater(int(secondary.cget('border_width')), 0)


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestWhereTheFieldsSit(DialogTestCase):
    """
    The order of the General tab, and what the notes have to themselves.

    Both are about reading order rather than behaviour, so both are checked
    against the grid the form was actually built into: a field moved in the
    source and not in the layout would pass a test that only read the code.
    """

    def dialog(self):
        """An edit dialog over the fixture task."""
        from gantt_app.views.taskdialogs import EditTaskDialog

        dialog = EditTaskDialog(self.root, self.task, self.project,
                                on_save=lambda t: None,
                                on_delete=lambda i: None)
        dialog.update_idletasks()
        return dialog

    def labels(self, dialog):
        """
        Every label on the General tab, in reading order.

        Sorted by row and then by column: the grid is four columns wide and
        two fields share a row, so a sort on the row alone leaves the two
        halves of a row in whatever order Tk happens to list them.
        """
        import customtkinter as ctk

        grid = dialog.name_entry.master
        cells = []
        for child in grid.grid_slaves():
            if not isinstance(child, ctk.CTkLabel):
                continue
            where = child.grid_info()
            cells.append((int(where['row']), int(where['column']),
                          child.cget('text')))
        return [text for _row, _column, text in sorted(cells)]

    def sections(self, dialog):
        """The section titles, in order."""
        return [text for text in self.labels(dialog)
                if text in ("Basic Information", "Schedule", "Calendar",
                            "Display")]

    def test_the_scheduling_menu_comes_before_the_dates(self):
        """
        It says which of the three boxes under it the form fills in.

        Read after them it explained a greyed-out box the user had already
        tried to type in.
        """
        labels = self.labels(self.dialog())

        self.assertLess(labels.index("Scheduling options:"),
                        labels.index("Start Date:"))

    def test_it_sits_immediately_above_the_start_date(self):
        """Nothing in between, or it is explaining something else."""
        labels = self.labels(self.dialog())

        self.assertEqual(labels[labels.index("Scheduling options:") + 1],
                         "Start Date:")

    def test_it_is_the_first_thing_under_the_schedule_heading(self):
        """Which is the other half of putting it above the dates."""
        labels = self.labels(self.dialog())

        self.assertEqual(labels[labels.index("Schedule") + 1],
                         "Scheduling options:")

    def test_the_calculated_box_is_greyed_from_the_moment_it_opens(self):
        """
        The menu is built before the boxes it greys out now.

        It used to grey them from inside its own builder, which ran last;
        moved first, that call reaches nothing and the form has to make it
        again once all three exist.
        """
        dialog = self.dialog()

        self.assertEqual(dialog.scheduling_options_var.get(),
                         "End date is calculated")
        self.assertFalse(dialog._field_is_live(dialog.end_date_entry))
        self.assertTrue(dialog._field_is_live(dialog.start_date_entry))

    def test_the_sections_read_in_order(self):
        """What the row is, when it happens, which week, how it is drawn."""
        self.assertEqual(self.sections(self.dialog()),
                         ["Basic Information", "Schedule", "Calendar",
                          "Display"])

    def test_a_title_has_its_row_to_itself(self):
        """
        Above its section rather than beside the first field of it.

        A heading sharing a row with a field reads as that field's label.
        """
        import customtkinter as ctk

        dialog = self.dialog()
        grid = dialog.name_entry.master

        titled = {}
        for child in grid.grid_slaves():
            where = child.grid_info()
            titled.setdefault(int(where['row']), []).append(
                child.cget('text') if isinstance(child, ctk.CTkLabel) else None)

        for row, texts in titled.items():
            for text in texts:
                if text in ("Basic Information", "Schedule", "Calendar",
                            "Display"):
                    self.assertEqual(len(texts), 1,
                                     f"{text} shares row {row}")

    def test_the_last_two_sections_are_ruled_off(self):
        """
        Calendar and Display each open under a separator.

        Basic Information opens the tab and Schedule follows it directly, so
        a line between those two would divide nothing the headings do not.
        """
        import customtkinter as ctk
        from tkinter import ttk

        dialog = self.dialog()
        grid = dialog.name_entry.master

        rules = {int(child.grid_info()['row'])
                 for child in grid.grid_slaves()
                 if isinstance(child, ttk.Separator)}
        titles = {child.cget('text'): int(child.grid_info()['row'])
                  for child in grid.grid_slaves()
                  if isinstance(child, ctk.CTkLabel)}

        self.assertIn(titles["Calendar"] - 1, rules)
        self.assertIn(titles["Display"] - 1, rules)
        self.assertNotIn(titles["Schedule"] - 1, rules)

    def test_short_fields_sit_two_to_a_row(self):
        """
        A start beside a finish, a percentage beside a priority.

        One column of a dozen rows made the form taller than most screens.
        """
        import customtkinter as ctk

        dialog = self.dialog()
        grid = dialog.name_entry.master

        placed = {}
        for child in grid.grid_slaves():
            if isinstance(child, ctk.CTkLabel):
                where = child.grid_info()
                placed[child.cget('text')] = (int(where['row']),
                                              int(where['column']))

        for left, right in (("Type:", "ID:"),
                            ("Progress (%):", "Priority:"),
                            ("Start Date:", "End Date:"),
                            ("Duration:", "Is Milestone:")):
            self.assertEqual(placed[left][0], placed[right][0],
                             f"{left} and {right} are not on one row")
            self.assertLess(placed[left][1], placed[right][1],
                            f"{left} should be the left of the pair")

    def test_a_field_with_nothing_beside_it_keeps_the_left(self):
        """
        And is not pulled across into the half of a row above it.

        A milestone has no end date, so the start has the row to itself -
        which has to leave the half beside it empty rather than letting the
        duration below climb into it.
        """
        from gantt_app.views.taskdialogs import CreateTaskDialog
        import customtkinter as ctk

        dialog = CreateTaskDialog(self.root, self.project,
                                  task_type="Milestone")
        dialog.update_idletasks()
        grid = dialog.name_entry.master

        placed = {}
        for child in grid.grid_slaves():
            if isinstance(child, ctk.CTkLabel):
                where = child.grid_info()
                placed[child.cget('text')] = (int(where['row']),
                                              int(where['column']))

        self.assertNotIn("End Date:", placed)
        self.assertEqual(placed["Start Date:"][1], 0)
        self.assertGreater(placed["Duration:"][0], placed["Start Date:"][0])

    def test_the_calendar_section_is_left_out_with_its_menu(self):
        """
        A heading over nothing is worse than no heading.

        The menu is not built at all in a plan with no named calendars to
        choose between, so the title it sits under cannot be either.
        """
        dialog = self.dialog()
        if dialog.calendar_var is not None:
            self.assertIn("Calendar", self.sections(dialog))
            return

        self.assertNotIn("Calendar", self.sections(dialog))

    def test_the_notes_have_a_tab_of_their_own(self):
        """Between the fields and the links, which is where they belong."""
        dialog = self.dialog()

        self.assertEqual(
            list(dialog.tabs._segmented_button._buttons_dict.keys()),
            ["General", "Notes", "Dependency"])

    def test_the_notes_box_is_on_that_tab(self):
        """
        And not beside the fields, where it took half the width of the
        form on every edit whether or not the task had any notes.
        """
        dialog = self.dialog()

        self.assertTrue(str(dialog.details_text).startswith(
            str(dialog.tabs.tab("Notes"))))

    def test_the_notes_still_open_holding_what_the_task_says(self):
        """A tab is where it is drawn; it is still the same field."""
        self.task.details = "Waiting on the signed contract"

        dialog = self.dialog()

        self.assertEqual(dialog.details_text.get("1.0", "end").strip(),
                         "Waiting on the signed contract")

    def test_the_notes_are_saved_from_their_tab(self):
        """The one thing moving a field can quietly break."""
        dialog = self.dialog()
        dialog.details_text.insert("1.0", "Rewritten")

        dialog.save()

        self.assertEqual(self.task.details, "Rewritten")

    def test_the_form_opens_on_the_general_tab(self):
        """The notes are a tab away, not the first thing you land on."""
        self.assertEqual(self.dialog().tabs.get(), "General")
