"""
Which task-grid columns are on show, and the Settings tab that edits it.

The setting lives on the project - hidden_grid_columns - so it travels
with the file, and the grid reads it through displaycolumns. The Task
Grid tab in Settings edits it with a dropdown per column, like the grid
edits its own cells.
"""

import unittest
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


class TestTheSettingItself(unittest.TestCase):
    """The model side: the default, and the file round-trip."""

    def test_label_is_hidden_by_default(self):
        """The column a plan only needs once it has labels."""
        self.assertEqual(Project(name="P").hidden_grid_columns, ['Label'])

    def test_it_survives_a_save_round_trip(self):
        """The point of putting it on the project is that it is saved."""
        project = Project(name="P")
        project.hidden_grid_columns = ['Label', 'Outline']

        loaded = Project.from_dict(project.to_dict())

        self.assertEqual(loaded.hidden_grid_columns, ['Label', 'Outline'])

    def test_an_old_plan_reads_the_default(self):
        """A file from before the setting still hides the Label column."""
        data = Project(name="P").to_dict()
        del data['hidden_grid_columns']

        self.assertEqual(Project.from_dict(data).hidden_grid_columns,
                         ['Label'])


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class GridColumnCase(unittest.TestCase):
    """Shared fixture: a withdrawn root with a bare task list."""

    def setUp(self):
        """Build the grid the way the main window does."""
        import customtkinter as ctk
        from gantt_app import theme
        from gantt_app.views.task_list import DragDropTaskList

        self.root = ctk.CTk()
        self.root.withdraw()
        theme.initialise_ttk_styles()

        self.project = Project(name="Test Project")
        base = datetime(2026, 1, 1)
        self.project.add_task(Task(
            id="001", name="Alpha", start_date=base,
            end_date=base + timedelta(days=2)))

        self.task_list = DragDropTaskList(self.root, self.project)
        self.root.update_idletasks()

    def tearDown(self):
        """Tear the window down."""
        self.root.destroy()


class TestTheGridReadsIt(GridColumnCase):
    """What displaycolumns does with the setting."""

    def shown(self):
        """The column names the tree is currently drawing."""
        return tuple(self.task_list.tree.cget('displaycolumns'))

    def test_label_is_not_shown_until_asked_for(self):
        """The default flows through to the grid, not just the model."""
        self.assertNotIn('Label', self.shown())

    def test_everything_else_is(self):
        """Only what the plan hides is hidden."""
        self.assertIn('Start', self.shown())
        self.assertIn('Task Calendar', self.shown())

    def test_unhiding_a_column_brings_it_back(self):
        """The settings tab's save path, end to end."""
        self.project.hidden_grid_columns = []
        self.task_list.apply_column_visibility()

        self.assertIn('Label', self.shown())

    def test_baseline_columns_still_follow_the_baseline(self):
        """Hidden or not, they only exist while a baseline is compared."""
        self.project.hidden_grid_columns = []

        self.task_list.apply_column_visibility()
        self.assertNotIn('Baseline Start', self.shown())

        self.task_list.set_active_baseline(None, 1)
        self.assertIn('Baseline Start', self.shown())

    def test_a_hidden_baseline_column_stays_hidden(self):
        """The two rules compose rather than either winning."""
        self.project.hidden_grid_columns = ['Baseline Start']

        self.task_list.set_active_baseline(None, 1)

        self.assertNotIn('Baseline Start', self.shown())


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestTheSettingsTab(GridColumnCase):
    """The Task Grid tab itself."""

    def setUp(self):
        """Open Settings on the new tab."""
        super().setUp()
        from gantt_app.views.settingswindow import SettingsWindow

        self.window = SettingsWindow(
            self.root, self.project,
            open_project=lambda: None,
            open_resource=lambda: None,
            open_calendar=lambda: None,
            task_list=self.task_list)
        self.root.update_idletasks()

    def tearDown(self):
        """Close the window, then the root."""
        self.window.destroy()
        super().tearDown()

    def test_the_tab_lists_every_column(self):
        """One row per hideable column, Task Name excepted."""
        rows = self.window._grid_columns_tree.get_children()

        self.assertEqual(list(rows), list(self.task_list.DATA_COLUMNS))
        self.assertNotIn('Task Name', rows)

    def test_label_row_starts_hidden(self):
        """The dropdown's starting state mirrors the plan."""
        values = self.window._grid_columns_tree.item('Label', 'values')

        self.assertEqual(values, ('Hidden',))

    def test_save_writes_the_plan_and_repaints(self):
        """Mark a column Hidden, save, and it is gone from the grid."""
        tree = self.window._grid_columns_tree
        tree.item('Status', values=('Hidden',))

        self.window._save_grid_columns()

        self.assertIn('Status', self.project.hidden_grid_columns)
        self.assertNotIn('Status',
                         self.task_list.tree.cget('displaycolumns'))

    def test_save_tells_the_window_the_plan_changed(self):
        """It edits the file's contents, so the unsaved-work guard hears."""
        marked = []
        self.root.mark_dirty = lambda: marked.append(True)

        self.window._save_grid_columns()

        self.assertEqual(marked, [True])


if __name__ == '__main__':
    unittest.main()
