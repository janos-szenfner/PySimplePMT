"""
Tests for the Deliverables board - the #100-#109 package.

WHY THIS MODULE EXISTS:
======================
The deliverable issues covered a lot of small ground on the one widget: the
way a row is numbered and coloured, the words on its columns and menus, the
clipboard the task list already had, the editor a double-click opens and the
health flags the whole list is judged by. These tests pin the parts that
were asked for, so the next change to the board cannot quietly take one
back.

The board is built over a real CTk root the same way test_statusbar_bdd's
application fixture builds it; conftest's one_tk_root_at_a_time fixture
takes each root down again.
"""

import unittest
from datetime import datetime, timedelta

import customtkinter as ctk

from gantt_app.core.deliverable import Deliverable
from gantt_app.core.models import Project, Task
from gantt_app.utils.undoredo import ProjectStateTracker, UndoRedoManager
from gantt_app.views.deliverables_board import DeliverablesBoard


YESTERDAY = datetime.now() - timedelta(days=1)
TOMORROW = datetime.now() + timedelta(days=1)
NEXT_WEEK = datetime.now() + timedelta(days=7)


def _deliverable(deliverable_id, name='D', **kwargs):
    return Deliverable.create(name=name, deliverable_id=deliverable_id,
                              **kwargs)


class BoardTestCase(unittest.TestCase):
    """A board over a small plan; every test gets a fresh one."""

    def setUp(self):
        self.root = ctk.CTk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.project = Project(name='P')
        self.tracker = ProjectStateTracker(
            self.project, UndoRedoManager())
        self.board = DeliverablesBoard(
            self.root, self.project, project_tracker=self.tracker)

    def _add(self, deliverable_id, name='D', **kwargs):
        row = _deliverable(deliverable_id, name, **kwargs)
        self.project.deliverables.append(row)
        self.board.refresh()
        return row


class TestTheColumns(BoardTestCase):
    """What the rows are called and how they read - #105, #106, #107."""

    def test_the_owner_column_is_called_responsible(self):
        self.assertIn('Responsible', self.board.COLUMNS)
        self.assertNotIn('Assignee', self.board.COLUMNS)

    def test_the_gutter_numbers_deliverables_with_a_d(self):
        self._add('001', 'First')
        self._add('002', 'Second')
        labels = [self.board.id_tree.item(i, 'text')
                  for i in self.board.id_tree.get_children('')]
        self.assertTrue(labels[0].startswith('D-001'),
                        labels)
        self.assertTrue(labels[1].startswith('D-002'),
                        labels)

    def test_a_task_row_keeps_the_plan_number(self):
        self.project.tasks = [
            Task(id='001', name='Work', start_date=datetime(2026, 1, 5),
                 end_date=datetime(2026, 1, 6))]
        self._add('001', 'D', task_ids=['001'])
        task_iid = DeliverablesBoard._task_row_id('001', '001')
        self.assertEqual(
            self.board.id_tree.item(task_iid, 'text'), '001')

    def test_a_task_row_wears_the_muted_tag(self):
        self.project.tasks = [
            Task(id='001', name='Work', start_date=datetime(2026, 1, 5),
                 end_date=datetime(2026, 1, 6))]
        self._add('001', 'D', task_ids=['001'])
        task_iid = DeliverablesBoard._task_row_id('001', '001')
        self.assertIn('task_row', self.board.tree.item(task_iid, 'tags'))

    def test_a_row_wears_its_health_colour(self):
        self._add('001', 'Late', due_date=YESTERDAY, progress=40)
        self.assertIn('health_overdue',
                      self.board.tree.item('001', 'tags'))


class TestTheClipboard(BoardTestCase):
    """Copy, cut and paste for deliverable branches - issue #109."""

    def test_copy_then_paste_places_a_sibling_copy_after_the_anchor(self):
        parent = self._add('001', 'Parent')
        self._add('002', 'Child', parent_id='001')
        other = self._add('003', 'Other')

        self.board.copy_deliverables(['001'])
        self.assertEqual(len(self.board._clipboard_items), 1)
        self.assertEqual(len(self.board._clipboard_items[0]['children']), 1)

        self.board.tree.focus('003')
        self.board.tree.selection_set('003')
        self.board.paste_deliverables()

        order = self.project.deliverable_display_order()
        # The copy, with its child, sits right after the anchor row.
        self.assertEqual(order[3].name, 'Parent')
        self.assertIsNone(order[3].parent_id)
        self.assertEqual(order[4].name, 'Child')
        self.assertEqual(order[4].parent_id, order[3].id)
        self.assertNotEqual(order[3].id, '001')

    def test_paste_as_sub_deliverable_nests_under_the_anchor(self):
        self._add('001', 'Source')
        self._add('002', 'Target')
        self.board.copy_deliverables(['001'])
        self.board.tree.focus('002')
        self.board.tree.selection_set('002')
        self.board.paste_deliverables(inside=True)

        target = self.project.get_deliverable_by_id('002')
        children = self.project.get_sub_deliverables('002')
        self.assertEqual([c.name for c in children], ['Source'])

    def test_cut_removes_and_paste_brings_the_branch_back(self):
        self._add('001', 'Parent')
        self._add('002', 'Child', parent_id='001')
        self._add('003', 'Other')

        self.board.cut_deliverables(['001'])
        self.assertIsNone(self.project.get_deliverable_by_id('001'))
        self.assertIsNone(self.project.get_deliverable_by_id('002'))

        self.board.tree.focus('003')
        self.board.tree.selection_set('003')
        self.board.paste_deliverables()

        names = [d.name for d in self.project.deliverable_display_order()]
        self.assertIn('Parent', names)
        self.assertIn('Child', names)

    def test_a_cut_and_paste_is_one_undo_step_each(self):
        self._add('001', 'Parent')
        self._add('002', 'Child', parent_id='001')

        self.board.cut_deliverables(['001'])
        self.assertIsNone(self.project.get_deliverable_by_id('001'))
        self.assertTrue(self.tracker.manager.undo())
        self.assertIsNotNone(self.project.get_deliverable_by_id('002'))


class TestTheDoubleClick(BoardTestCase):
    """What a double-click reaches - issues #101 and #103."""

    def test_a_deliverable_row_opens_the_editor(self):
        self._add('001', 'First', details='accept me')
        self.board._open_editor('001')
        windows = [w for w in self.root.winfo_children()
                   if isinstance(w, ctk.CTkToplevel)]
        self.assertEqual(len(windows), 1)
        self.assertIn('Edit Deliverable', windows[0].title())
        windows[0].destroy()

    def test_a_task_row_opens_the_task_editor(self):
        self.project.tasks = [
            Task(id='001', name='Work', start_date=datetime(2026, 1, 5),
                 end_date=datetime(2026, 1, 6))]
        self._add('001', 'D', task_ids=['001'])

        opened = []
        self.board.on_task_edit = opened.append
        task_iid = DeliverablesBoard._task_row_id('001', '001')
        self.board._open_task_editor(task_iid)
        self.assertEqual([t.id for t in opened], ['001'])


class TestTheMenu(BoardTestCase):
    """The right-click menu's order, the task list's own - issue #109."""

    def test_the_moves_come_first_and_flat(self):
        self._add('001', 'First')
        # Build the menu the click would post and read its entries off.
        captured = {}

        class MenuSpy:
            def __init__(self, *a, **k):
                self.entries = []
            def add_command(self, label='', **kw):
                self.entries.append(label)
            def add_cascade(self, label='', **kw):
                self.entries.append(label)
            def add_separator(self):
                self.entries.append('---')
            def tk_popup(self, *a):
                captured['menu'] = self
            def grab_release(self):
                pass

        import gantt_app.views.deliverables_board as board_module
        real_menu = board_module.tk.Menu
        board_module.tk.Menu = MenuSpy
        try:
            self.board._open_context_menu('001', 0, 0)
        finally:
            board_module.tk.Menu = real_menu

        labels = captured['menu'].entries
        self.assertEqual(labels[:4],
                         ['Move to Top', 'Move Up', 'Move Down',
                          'Move to Bottom'])
        self.assertIn('Indent', labels)
        self.assertIn('Outdent', labels)
        self.assertIn('Copy', labels)
        self.assertIn('Cut', labels)
        self.assertIn('Paste', labels)
        self.assertIn('Paste as Sub-deliverable', labels)
        self.assertIn('Undo', labels)
        self.assertIn('Redo', labels)
        # The clipboard block sits between the pick lists and Undo/Redo.
        self.assertLess(labels.index('Copy'), labels.index('Undo'))


if __name__ == '__main__':
    unittest.main()
