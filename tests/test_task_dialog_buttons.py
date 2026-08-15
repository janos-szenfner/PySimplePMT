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
        from gantt_app.views.task_list import EditTaskDialog

        dialog = EditTaskDialog(self.root, self.task, self.project,
                                on_save=lambda t: None,
                                on_delete=lambda i: None, **kwargs)
        dialog.update_idletasks()
        return dialog

    def test_the_buttons_read_in_order(self):
        """Delete sits apart, then Close, Save & Close, Save & New."""
        self.assertEqual(self.button_row(self.dialog()),
                         ["Delete", "Close", "Save & Close", "Save & New"])

    def test_there_is_no_cancel(self):
        """Close replaced it; nothing is written until a Save is pressed."""
        self.assertNotIn("Cancel", self.button_row(self.dialog()))

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

        with mock.patch('gantt_app.views.task_list.messagebox.showerror'):
            dialog.save_and_new()

        self.assertEqual(opened, [])
        self.assertTrue(dialog.winfo_exists())

    def test_a_bad_date_is_reported(self):
        """The dialog says why it will not save."""
        dialog = self.dialog()
        dialog.start_date_entry.delete(0, 'end')
        dialog.start_date_entry.insert(0, "nonsense")

        with mock.patch('gantt_app.views.task_list.messagebox.showerror') as err:
            dialog.save()

        self.assertTrue(err.called)
        self.assertTrue(dialog.winfo_exists())


class TestCreateDialogButtons(DialogTestCase):
    """The create dialog's button row and its Save & New."""

    def dialog(self, on_save=None):
        """A create dialog collecting saved tasks."""
        from gantt_app.views.task_list import CreateTaskDialog

        dialog = CreateTaskDialog(self.root, self.project,
                                  on_save=on_save or (lambda t: None))
        dialog.update_idletasks()
        return dialog

    def test_the_buttons_read_in_order(self):
        """No Delete here - the task does not exist yet."""
        self.assertEqual(self.button_row(self.dialog()),
                         ["Close", "Save & Close", "Save & New"])

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

        with mock.patch('gantt_app.views.task_list.messagebox.showerror'):
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
        from gantt_app.views.task_list import EditTaskDialog

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


if __name__ == '__main__':
    unittest.main()
