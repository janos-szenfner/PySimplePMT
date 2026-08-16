"""
Tests for the colour picker and the task list's column sizing.

DEVELOPMENT NOTES:
------------------
Both need a real widget, so the module skips without a display; CI provides
one through xvfb.
"""

import unittest
from datetime import datetime, timedelta

from gantt_app.models import Project, Task
from gantt_app.views.colorpicker import ColorEntry, FULL_PALETTE, DEFAULT_COLOR


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


class TestPaletteContents(unittest.TestCase):
    """The set of colours on offer, checked without a display."""

    def test_every_entry_is_a_hex_colour(self):
        """Each swatch is something Tk can paint."""
        for value, _name in FULL_PALETTE:
            self.assertRegex(value, r'^#[0-9a-f]{6}$')

    def test_every_entry_is_named(self):
        """Each colour has a readable name."""
        for _value, name in FULL_PALETTE:
            self.assertTrue(name.strip())

    def test_there_are_no_duplicates(self):
        """The same colour is not offered twice."""
        values = [value for value, _name in FULL_PALETTE]

        self.assertEqual(len(values), len(set(values)))

    def test_the_application_defaults_are_included(self):
        """
        The colours existing plans already use are on the palette.

        Otherwise opening any task made before this existed would show an
        extra swatch rather than a selected one.
        """
        values = {value for value, _name in FULL_PALETTE}

        for default in ('#3498db', '#9b59b6', '#e74c3c', '#1f6aa5'):
            self.assertIn(default, values)


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestColorEntry(unittest.TestCase):
    """The color picker entry widget."""

    def setUp(self):
        """Build a root window."""
        import customtkinter as ctk

        self.root = ctk.CTk()
        self.root.withdraw()

    def tearDown(self):
        """Tear the root window down."""
        try:
            self.root.destroy()
        except Exception:
            pass

    def entry(self, color=DEFAULT_COLOR, on_change=None):
        """A color entry over the root window."""
        return ColorEntry(self.root, color=color, on_change=on_change)

    def test_it_starts_on_the_given_colour(self):
        """The task's own colour is what shows as selected."""
        widget = self.entry('#2ecc71')

        self.assertEqual(widget.get(), '#2ecc71')

    def test_setting_a_new_colour(self):
        """Setting a color programmatically changes the value."""
        widget = self.entry()

        widget.set('#f39c12')

        self.assertEqual(widget.get(), '#f39c12')

    def test_default_button_resets_to_blue(self):
        """Clicking Default resets to the default blue color."""
        widget = self.entry('#2ecc71')

        widget.set_default()

        self.assertEqual(widget.get(), DEFAULT_COLOR)
        self.assertEqual(widget.get(), '#1f6aa5')

    def test_it_reports_a_change(self):
        """The callback fires with the new colour."""
        seen = []
        widget = self.entry(on_change=seen.append)

        widget.set('#1abc9c')

        self.assertEqual(seen, ['#1abc9c'])

    def test_reselecting_reports_nothing(self):
        """Choosing the colour already selected is not a change."""
        seen = []
        widget = self.entry('#1abc9c', on_change=seen.append)

        widget.set('#1abc9c')

        self.assertEqual(seen, [])

    def test_a_missing_colour_falls_back(self):
        """An empty value does not leave the widget blank."""
        widget = self.entry('')

        self.assertTrue(widget.get().startswith('#'))


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestDialogColourPicking(unittest.TestCase):
    """The dialogs use the color picker rather than a hex box."""

    def setUp(self):
        """A root window and a small project."""
        import customtkinter as ctk

        self.root = ctk.CTk()
        self.root.withdraw()

        self.project = Project(name="Test Project")
        base = datetime(2026, 1, 1)
        self.task = Task(id="001", name="Alpha", start_date=base,
                         end_date=base + timedelta(days=2), color='#2ecc71')
        self.project.add_task(self.task)

    def tearDown(self):
        """Tear the root window down."""
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_the_edit_dialog_shows_the_tasks_colour(self):
        """The color entry opens on whatever the task already is."""
        from gantt_app.views.taskdialogs import EditTaskDialog

        dialog = EditTaskDialog(self.root, self.task, self.project,
                                on_save=lambda t: None,
                                on_delete=lambda i: None)

        self.assertEqual(dialog.color_entry.get(), '#2ecc71')

    def test_saving_stores_the_picked_colour(self):
        """What the color entry shows is what the task gets."""
        from gantt_app.views.taskdialogs import EditTaskDialog

        dialog = EditTaskDialog(self.root, self.task, self.project,
                                on_save=lambda t: None,
                                on_delete=lambda i: None)
        dialog.color_entry.set('#f39c12')

        dialog.save()

        self.assertEqual(self.task.color, '#f39c12')

    def test_the_create_dialog_defaults_by_type(self):
        """Each kind of task starts on its own colour."""
        from gantt_app.views.taskdialogs import CreateTaskDialog

        expected = {"Task": '#3498db', "Milestone": '#e74c3c'}
        for task_type, colour in expected.items():
            dialog = CreateTaskDialog(self.root, self.project,
                                      task_type=task_type,
                                      on_save=lambda t: None)

            self.assertEqual(dialog.color_entry.get(), colour, task_type)
            dialog.destroy()


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestColumnSizing(unittest.TestCase):
    """
    Columns keep the width they are dragged to.

    DEVELOPMENT NOTES:
    ------------------
    Name was the one stretchable column, so ttk gave it whatever width was
    left over. Dragging its edge was undone the moment the drag ended, and a
    narrow pane squeezed it to a sliver, because a stretchable column is also
    the one ttk takes space away from.
    """

    def setUp(self):
        """A task list over a small project."""
        import customtkinter as ctk
        from gantt_app.views.task_list import DragDropTaskList

        self.root = ctk.CTk()
        self.root.withdraw()

        self.project = Project(name="Test Project")
        base = datetime(2026, 1, 1)
        self.project.add_task(Task(id="001", name="Alpha", start_date=base,
                                   end_date=base + timedelta(days=2)))

        self.task_list = DragDropTaskList(self.root, self.project)

    def tearDown(self):
        """Tear the root window down."""
        try:
            self.root.destroy()
        except Exception:
            pass

    def columns(self):
        """Every column identifier, including the tree column."""
        return ('#0',) + self.task_list.tree.cget('columns')

    def test_no_column_stretches(self):
        """Nothing absorbs leftover width, so a drag is not undone."""
        for column in self.columns():
            self.assertFalse(
                self.task_list.tree.column(column, 'stretch'),
                f"{column} still stretches",
            )

    def test_every_column_has_a_floor(self):
        """A column cannot be dragged shut."""
        for column in self.columns():
            self.assertGreater(self.task_list.tree.column(column, 'minwidth'),
                               0, column)

    def test_a_width_survives_a_refresh(self):
        """Repopulating the rows leaves the columns alone."""
        self.task_list.tree.column('Name', width=420)

        self.task_list.update_task_list()

        self.assertEqual(self.task_list.tree.column('Name', 'width'), 420)

    def test_the_name_column_is_the_widest_by_default(self):
        """Names are the longest thing in the table."""
        widths = {c: self.task_list.tree.column(c, 'width')
                  for c in self.columns()}

        self.assertEqual(max(widths, key=widths.get), 'Name')


if __name__ == '__main__':
    unittest.main()
