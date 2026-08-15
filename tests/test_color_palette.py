"""
Tests for the colour swatches and the task list's column sizing.

DEVELOPMENT NOTES:
------------------
Both need a real widget, so the module skips without a display; CI provides
one through xvfb.
"""

import unittest
from datetime import datetime, timedelta

from gantt_app.models import Project, Task
from gantt_app.views.colorpalette import PALETTE


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
        for value, _name in PALETTE:
            self.assertRegex(value, r'^#[0-9a-f]{6}$')

    def test_every_entry_is_named(self):
        """Each colour has a readable name."""
        for _value, name in PALETTE:
            self.assertTrue(name.strip())

    def test_there_are_no_duplicates(self):
        """The same colour is not offered twice."""
        values = [value for value, _name in PALETTE]

        self.assertEqual(len(values), len(set(values)))

    def test_the_application_defaults_are_included(self):
        """
        The colours existing plans already use are on the palette.

        Otherwise opening any task made before this existed would show an
        extra swatch rather than a selected one.
        """
        values = {value for value, _name in PALETTE}

        for default in ('#3498db', '#9b59b6', '#e74c3c', '#1f6aa5'):
            self.assertIn(default, values)


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestColorPalette(unittest.TestCase):
    """The swatch widget."""

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

    def palette(self, color='#1f6aa5', on_change=None):
        """A palette over the root window."""
        from gantt_app.views.colorpalette import ColorPalette

        return ColorPalette(self.root, color=color, on_change=on_change)

    def test_it_draws_a_swatch_per_colour(self):
        """Every palette entry gets one."""
        widget = self.palette()

        self.assertEqual(len(widget._buttons), len(PALETTE))

    def test_it_starts_on_the_given_colour(self):
        """The task's own colour is what shows as selected."""
        widget = self.palette('#2ecc71')

        self.assertEqual(widget.get(), '#2ecc71')

    def test_picking_changes_the_value(self):
        """Clicking a swatch selects it."""
        widget = self.palette()

        widget.set('#f39c12')

        self.assertEqual(widget.get(), '#f39c12')

    def test_the_selected_swatch_is_outlined(self):
        """Selection is shown by the border, not by hiding the colour."""
        widget = self.palette('#2ecc71')

        outline = widget._buttons['#2ecc71'].cget('highlightbackground')

        self.assertEqual(str(outline), widget.SELECTED_BORDER_COLOR)

    def test_the_others_are_not_outlined(self):
        """Only one swatch reads as chosen."""
        widget = self.palette('#2ecc71')

        outline = widget._buttons['#e74c3c'].cget('highlightbackground')

        self.assertEqual(str(outline), widget.UNSELECTED_BORDER_COLOR)

    def test_a_colour_outside_the_palette_is_kept(self):
        """
        An imported colour is offered rather than snapped to a neighbour.

        Replacing it with the closest palette entry would repaint someone's
        plan without asking.
        """
        widget = self.palette('#123456')

        self.assertEqual(widget.get(), '#123456')
        self.assertEqual(len(widget._buttons), len(PALETTE) + 1)

    def test_it_reports_a_change(self):
        """The callback fires with the new colour."""
        seen = []
        widget = self.palette(on_change=seen.append)

        widget.set('#1abc9c')

        self.assertEqual(seen, ['#1abc9c'])

    def test_reselecting_reports_nothing(self):
        """Choosing the colour already selected is not a change."""
        seen = []
        widget = self.palette('#1abc9c', on_change=seen.append)

        widget.set('#1abc9c')

        self.assertEqual(seen, [])

    def test_a_missing_colour_falls_back(self):
        """An empty value does not leave the widget blank."""
        widget = self.palette('')

        self.assertTrue(widget.get().startswith('#'))


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestDialogColourPicking(unittest.TestCase):
    """The dialogs use the palette rather than a hex box."""

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
        """The palette opens on whatever the task already is."""
        from gantt_app.views.taskdialogs import EditTaskDialog

        dialog = EditTaskDialog(self.root, self.task, self.project,
                                on_save=lambda t: None,
                                on_delete=lambda i: None)

        self.assertEqual(dialog.color_palette.get(), '#2ecc71')

    def test_saving_stores_the_picked_colour(self):
        """What the palette shows is what the task gets."""
        from gantt_app.views.taskdialogs import EditTaskDialog

        dialog = EditTaskDialog(self.root, self.task, self.project,
                                on_save=lambda t: None,
                                on_delete=lambda i: None)
        dialog.color_palette.set('#f39c12')

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

            self.assertEqual(dialog.color_palette.get(), colour, task_type)
            dialog.destroy()

    def test_no_hex_entry_is_left(self):
        """The text box the palette replaced is gone."""
        from gantt_app.views.taskdialogs import EditTaskDialog

        dialog = EditTaskDialog(self.root, self.task, self.project,
                                on_save=lambda t: None,
                                on_delete=lambda i: None)

        self.assertFalse(hasattr(dialog, 'color_entry'))


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
