"""
The fixed "No" gutter down the left of the task list.

The row number was a data column inside the tree, second after Task Name. It
is now a grey, read-only gutter in its own column to the left of the list
(like MS Project), mirroring the visible rows. The number stays flush for
every row whatever its type or depth, and folding a branch away drops the
hidden rows without renumbering the rest.
"""

import unittest
from datetime import datetime

from gantt_app.models import Project, Task


def _display_available() -> bool:
    try:
        import tkinter
        root = tkinter.Tk()
    except Exception:
        return False
    root.destroy()
    return True


HAVE_DISPLAY = _display_available()


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestTheNoGutter(unittest.TestCase):
    def setUp(self):
        import customtkinter as ctk
        from gantt_app.views.task_list import DragDropTaskList

        self.root = ctk.CTk()
        self.root.withdraw()
        self.project = Project(name="P", start_date=datetime(2026, 1, 1))
        # A phase with a child, a milestone, and a plain task - a mix of types
        # and depths, so the numbering can be shown to be uniform.
        self.project.add_task(Task(
            id="a", name="Phase", start_date=datetime(2026, 1, 1),
            end_date=datetime(2026, 1, 8), task_type="Phase"))
        self.project.add_task(Task(
            id="b", name="Child", start_date=datetime(2026, 1, 1),
            end_date=datetime(2026, 1, 3), task_type="Subtask",
            parent_task_id="a"))
        self.project.add_task(Task(
            id="m", name="Gate", start_date=datetime(2026, 1, 9),
            task_type="Milestone"))
        self.project.add_task(Task(
            id="c", name="Task2", start_date=datetime(2026, 1, 12),
            end_date=datetime(2026, 1, 14)))
        self.view = DragDropTaskList(self.root, self.project)
        self.view.update_task_list()

    def tearDown(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def _gutter(self):
        tree = self.view.id_tree
        return [tree.item(i, 'text') for i in tree.get_children('')]

    def test_the_row_number_is_no_longer_a_main_tree_column(self):
        self.assertNotIn('ID', self.view.tree.cget('columns'))

    def test_the_gutter_header_is_no(self):
        self.assertEqual(self.view.id_tree.heading('#0', 'text'), 'No')

    def test_it_numbers_every_visible_row_flush_and_uniform(self):
        # One number per visible row, in order, zero-padded, whatever the
        # row's type or depth - no indentation between them.
        self.assertEqual(self._gutter(), ['001', '002', '003', '004'])

    def test_it_mirrors_exactly_the_visible_rows(self):
        self.assertEqual(len(self._gutter()), len(self.view.visible_rows()))

    def test_folding_drops_the_hidden_row_without_renumbering(self):
        self.view.tree.item('a', open=False)
        self.view._refresh_id_gutter()
        # The child (002) is gone; the rest keep the numbers they had.
        self.assertEqual(self.view.visible_rows(), ['a', 'm', 'c'])
        self.assertEqual(self._gutter(), ['001', '003', '004'])

    def test_the_gutter_is_read_only(self):
        # No selection can be made in it - it is a fixed key, not a control.
        self.assertEqual(str(self.view.id_tree.cget('selectmode')), 'none')


if __name__ == "__main__":
    unittest.main()
