"""
Which task-grid columns are on show, and the Settings tab that edits it.

The setting lives on the project - hidden_grid_columns - so it travels
with the file, and the grid reads it through displaycolumns. The Task
Grid tab in Settings edits it with a dropdown per column, like the grid
edits its own cells.
"""

import unittest
from datetime import datetime, timedelta

from gantt_app.core.models import Project, Task


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
        from gantt_app.views import theme
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
        _shut_down(self.root)


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

    def test_the_baseline_block_trails_the_layout(self):
        """
        Ten columns materialising mid-grid splits the arrangement in two
        and pushes whatever stood right of them off the screen; they stand
        as a block at the end instead.
        """
        self.task_list.set_active_baseline(None, 1)
        shown = self.shown()

        baseline_start = shown.index('Baseline Start')
        self.assertEqual(
            shown[baseline_start:],
            ('Baseline Start', 'Start Variance', 'Baseline Finish',
             'Finish Variance', 'Baseline Duration', 'Duration Variance',
             'Baseline Work', 'Work Variance', 'Baseline Cost',
             'Cost Variance'))
        self.assertLess(shown.index('Task Calendar'), baseline_start)

    def test_the_layout_is_untouched_by_a_compare(self):
        """
        What was on screen before the compare is exactly what the compare
        puts back - the reader's own columns never move.
        """
        before = self.shown()

        self.task_list.set_active_baseline(None, 1)
        self.assertEqual(self.shown()[:len(before)], before)

        self.task_list.set_active_baseline(None, None)
        self.assertEqual(self.shown(), before)


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

        # The tab lists the columns where they stand: viewable first in
        # layout order, then the hidden ones trailing - Label among them.
        expected = [c for c in self.task_list.DATA_COLUMNS
                    if c != 'Label'] + ['Label']
        self.assertEqual(list(rows), expected)
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

    def test_hiding_a_column_sends_it_to_the_back(self):
        """A hidden column trails the layout, not the spot it vacated."""
        tree = self.window._grid_columns_tree
        tree.item('Type', values=('Hidden',))

        self.window._save_grid_columns()

        # Label already trailed the layout; Type joins it ahead of it.
        self.assertEqual(self.project.grid_column_order[-2:],
                         ['Type', 'Label'])

    def test_reset_puts_the_factory_layout_back(self):
        """The tab's other button: the order the grid was built with."""
        self.task_list.move_column('End', 'Type')
        marked = []
        self.root.mark_dirty = lambda: marked.append(True)

        self.window._reset_grid_layout()

        self.assertEqual(
            self.project.grid_column_order,
            [c for c in self.task_list.DATA_COLUMNS
             if c != 'Label'] + ['Label'])
        self.assertEqual(marked, [True])

    def test_reset_visibility_restores_the_default(self):
        """The tab's third button: Label hidden, the rest shown again."""
        tree = self.window._grid_columns_tree
        tree.item('Status', values=('Hidden',))
        tree.item('Type', values=('Hidden',))
        tree.item('Label', values=('Viewable',))
        self.window._save_grid_columns()
        marked = []
        self.root.mark_dirty = lambda: marked.append(True)

        self.window._reset_grid_visibility()

        self.assertEqual(self.project.hidden_grid_columns, ['Label'])
        for row in tree.get_children():
            expected = 'Hidden' if row == 'Label' else 'Viewable'
            self.assertEqual(tree.item(row, 'values'), (expected,))
        self.assertIn('Status',
                      self.task_list.tree.cget('displaycolumns'))
        self.assertNotIn('Label',
                         self.task_list.tree.cget('displaycolumns'))
        self.assertEqual(marked, [True])


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestMovingColumns(GridColumnCase):
    """Dragging a column's heading to where it should stand."""

    def shown(self):
        """The column names the tree is currently drawing."""
        return list(self.task_list.tree.cget('displaycolumns'))

    def _heading_x(self, name, fraction=0.5):
        """A widget x inside the named column's heading."""
        edges = {n: (a, b) for n, a, b in self.task_list._heading_edges()}
        x0, x1 = edges[name]
        return int(x0 + (x1 - x0) * fraction)

    def _drag_heading(self, source, target, fraction=0.4):
        """
        Press a column's title, carry it over another's, release.

        The handlers are driven directly rather than through
        event_generate: a synthetic event at an unmapped widget is what
        segfaults Tk 8.5. The gesture logic is what is under test, and it
        identifies regions and columns from these same coordinates.
        """
        from types import SimpleNamespace

        start_x = self._heading_x(source)
        target_x = self._heading_x(target, fraction)
        self.task_list.on_press(SimpleNamespace(x=start_x, y=10, state=0))
        self.task_list.on_drag(SimpleNamespace(x=target_x, y=10))
        self.task_list.on_release(SimpleNamespace(x=target_x, y=10))

    def test_the_move_is_written_to_the_plan(self):
        """move_column is what a released heading drag calls."""
        self.task_list.move_column('End', 'Type')

        order = self.project.grid_column_order
        self.assertEqual(order[:3], ['Alert', 'End', 'Type'])
        self.assertEqual(self.shown()[:3], ['Alert', 'End', 'Type'])

    def test_a_hidden_column_keeps_its_place_in_the_tail(self):
        """Moves happen among the viewable; the hidden stay last."""
        self.task_list.move_column('Start', 'Type')

        self.assertEqual(self.project.grid_column_order[-1], 'Label')

    def test_an_unhidden_column_comes_back_at_the_end(self):
        """Hidden columns trail the order, so Label returns at the back."""
        self.project.hidden_grid_columns = []
        self.task_list.apply_column_visibility()

        self.assertEqual(self.shown()[-1], 'Label')

    def test_reset_restores_the_factory_layout(self):
        """The settings tab's reset, at the grid end of it."""
        self.task_list.move_column('End', 'Type')
        self.task_list.reset_column_order()

        self.assertEqual(self.shown()[:2], ['Alert', 'Type'])

    def test_column_positions_follow_the_shown_set(self):
        """_column_name counts displayed columns, not the full list."""
        x = self._heading_x('Type')

        self.assertEqual(self.task_list._column_name(x), 'Type')

    def test_a_heading_drag_reorders_the_grid(self):
        """The gesture itself: press a title, carry it, let go."""
        self._drag_heading('Type', 'Duration')

        order = self.project.grid_column_order
        self.assertLess(order.index('Type'), order.index('Duration'))
        self.assertLess(self.shown().index('Type'),
                        self.shown().index('Duration'))


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestTheAlertColumn(GridColumnCase):
    """
    The warning flag's own column, pinned beside the name.

    Issue #39: the flag used to ride in front of the Status letter; it
    now has a column of its own, standing where Microsoft Project puts
    Indicators - first, immovable, hideable.
    """

    def shown(self):
        """The column names the tree is currently drawing."""
        return list(self.task_list.tree.cget('displaycolumns'))

    def cell(self, task_id, column):
        """What a named column says for a row."""
        columns = list(self.task_list.tree.cget('columns'))
        return self.task_list.tree.item(task_id, 'values')[
            columns.index(column)]

    def test_it_stands_first_by_default(self):
        """Right of the name, before every other column."""
        self.assertEqual(self.shown()[0], 'Alert')

    def test_it_is_viewable_until_hidden(self):
        """The default keeps it on show; the settings can hide it."""
        self.assertNotIn('Alert', self.project.hidden_grid_columns)

        self.project.hidden_grid_columns = ['Alert']
        self.task_list.apply_column_visibility()

        self.assertNotIn('Alert', self.shown())

    def test_it_comes_back_first_whatever_the_layout(self):
        """Hidden then shown again, it re-pins itself to the front."""
        self.project.grid_column_order = [
            'Type', 'Status', 'Alert', 'Duration', 'Start', 'End']
        self.project.hidden_grid_columns = ['Alert']
        self.task_list.apply_column_visibility()

        self.project.hidden_grid_columns = []
        self.task_list.apply_column_visibility()

        self.assertEqual(self.shown()[0], 'Alert')

    def test_it_cannot_be_dragged(self):
        """A press on its title never becomes a move."""
        from types import SimpleNamespace

        before = list(self.project.grid_column_order)
        x = int(self.task_list.tree.column('#0')['width']) + 10
        self.task_list.on_press(SimpleNamespace(x=x, y=10, state=0))
        self.task_list.on_drag(SimpleNamespace(x=x + 300, y=10))
        self.task_list.on_release(SimpleNamespace(x=x + 300, y=10))

        self.assertIsNone(self.task_list._pressed_heading)
        self.assertEqual(list(self.project.grid_column_order), before)

    def test_nothing_can_stand_before_it(self):
        """A move asking for its place is refused at both ends."""
        self.task_list.move_column('Type', 'Alert')
        self.assertEqual(self.project.grid_column_order[0], 'Alert')

        self.task_list.move_column('Alert', 'Type')
        self.assertEqual(self.project.grid_column_order[0], 'Alert')

    def test_a_past_deadline_task_wears_the_flag(self):
        """The warning lives here now, not ahead of the Status letter."""
        task = self.project.get_task_by_id('001')
        task.deadline = task.start_date
        self.task_list.update_task_list()

        self.assertEqual(self.cell('001', 'Alert'), '⚠')
        self.assertNotIn('⚠', self.cell('001', 'Status'))

    def test_a_task_inside_its_deadline_shows_nothing(self):
        """The flag answers a finish past the deadline, not the deadline."""
        task = self.project.get_task_by_id('001')
        task.deadline = task.end_date + timedelta(days=30)
        self.task_list.update_task_list()

        self.assertEqual(self.cell('001', 'Alert'), '')


if __name__ == '__main__':
    unittest.main()
