"""
Tests for the gestures that reorder rows: dragging, and the context menu.

DEVELOPMENT NOTES:
------------------
The rules a move obeys are tested against Project in test_task_ordering.py.
What is left, and what is covered here, is the part that only exists once a
widget does: that a press followed by movement is recognised as a drag at
all, that a plain click is not, and that the menu offers the right entries
for the row it was opened on.

That distinction matters because the drag handling was broken in exactly this
layer - the tkinterdnd2 branch was unreachable and the fallback's motion
handler did nothing - while the ordering logic beneath it did not yet exist.

CI runs the suite under xvfb; the module skips when no display is available.
"""

import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace

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
class TaskListTestCase(unittest.TestCase):
    """Shared fixture: a task list over three roots and two sub-tasks."""

    def setUp(self):
        """Build a withdrawn root window holding a populated task list."""
        import customtkinter as ctk
        from gantt_app.views.task_list import DragDropTaskList

        self.root = ctk.CTk()
        self.root.withdraw()

        self.project = Project(name="Test Project")
        base = datetime(2026, 1, 1)
        for task_id, name in [("001", "Alpha"), ("002", "Beta"),
                              ("003", "Gamma")]:
            self.project.add_task(Task(
                id=task_id, name=name, start_date=base,
                end_date=base + timedelta(days=2),
            ))
        for task_id, name in [("004", "Beta one"), ("005", "Beta two")]:
            self.project.add_task(Task(
                id=task_id, name=name, start_date=base,
                task_type="Sub-Task", parent_task_id="002",
            ))

        self.task_list = DragDropTaskList(self.root, self.project)

    def tearDown(self):
        """Tear the root window down."""
        try:
            self.root.destroy()
        except Exception:
            pass

    def rows(self):
        """Every visible row, parents before their children."""
        found = []

        def walk(parent=''):
            """Collect a row and then its children."""
            for item in self.task_list.tree.get_children(parent):
                found.append(item)
                walk(item)

        walk()
        return found

    def at(self, mapping):
        """Make identify_row resolve y coordinates to given rows."""
        self.task_list.tree.identify_row = lambda y: mapping.get(y, '')

    def rows_at(self, boxes):
        """
        Give named rows a geometry, as (x, y, width, height).

        A withdrawn window has no laid-out rows, so Treeview.bbox returns
        empty and the drop line has nowhere to go. Supplying the rectangles
        keeps the placement arithmetic under test without needing a mapped,
        on-screen window.
        """
        self.task_list.tree.bbox = lambda item, column=None: boxes.get(item, '')


class TestRowOrder(TaskListTestCase):
    """Rows follow the project's order rather than the task dates."""

    def test_rows_are_not_sorted_by_date(self):
        """
        A later-starting task keeps its place in the list.

        Rows were sorted by start date on every refresh, so a task moved by
        hand snapped back and reordering could never be seen.
        """
        self.project.get_task_by_id("001").start_date = datetime(2026, 6, 1)
        self.task_list.update_task_list()

        self.assertEqual(self.rows()[0], "001")

    def test_moving_a_row_changes_what_is_displayed(self):
        """A move is visible in the tree, not only in the model."""
        self.task_list.move_task("003", 'top')

        self.assertEqual(self.rows()[0], "003")

    def test_a_moved_row_stays_selected(self):
        """The moved task keeps the selection so it can be moved again."""
        self.task_list.move_task("003", 'top')

        self.assertEqual(self.task_list.tree.selection(), ("003",))


class TestHierarchyDisplay(TaskListTestCase):
    """
    A task with sub-tasks is visibly different from one without.

    DEVELOPMENT NOTES:
    ------------------
    The tree was built show='headings', which hides column #0 - the column
    that draws the expander. A parent looked exactly like a leaf and there
    was nothing to click to fold a branch away, so the names were prefixed
    with '|--' to stand in for the indentation.
    """

    def test_the_tree_column_is_shown(self):
        """Column #0 is displayed, which is what draws the expander."""
        self.assertIn('tree', str(self.task_list.tree.cget('show')))

    def test_the_tree_column_is_narrow(self):
        """It carries only the expander, so it does not eat the row."""
        self.assertLessEqual(self.task_list.tree.column('#0', 'width'), 60)

    def test_a_parent_reports_children(self):
        """The sub-tasks hang off their parent, so ttk draws an expander."""
        self.assertEqual(list(self.task_list.tree.get_children("002")),
                         ["004", "005"])

    def test_a_leaf_reports_none(self):
        """A task without sub-tasks gets no expander."""
        self.assertEqual(list(self.task_list.tree.get_children("001")), [])

    def test_names_are_not_prefixed(self):
        """The name column holds the name, with no drawn-in tree characters."""
        values = self.task_list.tree.item("004", 'values')

        self.assertEqual(values[1], "Beta one")

    def test_selecting_a_subtask_works(self):
        """
        select_task reaches a nested row.

        It used to scan only the top level and compare against the item's
        'text', so selecting a sub-task quietly did nothing.
        """
        self.task_list.select_task("005")

        self.assertEqual(self.task_list.tree.selection(), ("005",))


class TestDoubleClick(TaskListTestCase):
    """Double-click folds a branch instead of opening the edit dialog."""

    def double_click(self, item):
        """Double-click the given row."""
        self.task_list.tree.identify_row = lambda y: item
        return self.task_list.on_double_click(SimpleNamespace(x=5, y=0))

    def test_double_click_collapses_a_parent(self):
        """An open parent closes."""
        self.assertTrue(self.task_list.tree.item("002", 'open'))

        self.double_click("002")

        self.assertFalse(self.task_list.tree.item("002", 'open'))

    def test_double_click_expands_a_closed_parent(self):
        """A closed parent opens again."""
        self.task_list.tree.item("002", open=False)

        self.double_click("002")

        self.assertTrue(self.task_list.tree.item("002", 'open'))

    def test_double_click_does_not_open_the_edit_dialog(self):
        """Editing moved to the context menu."""
        opened = []
        self.task_list.on_task_edit = opened.append

        self.double_click("002")
        self.double_click("001")

        self.assertEqual(opened, [])

    def test_double_click_on_a_leaf_does_nothing(self):
        """A task without sub-tasks has nothing to fold."""
        before = self.rows()

        self.double_click("001")

        self.assertEqual(self.rows(), before)

    def test_the_default_handler_is_suppressed(self):
        """
        'break' stops ttk's own double-click running afterwards.

        Without it the built-in handler toggles the row a second time and
        the branch snaps straight back.
        """
        self.assertEqual(self.double_click("002"), 'break')

    def test_double_click_off_the_rows_is_ignored(self):
        """Below the last row there is nothing to toggle."""
        self.task_list.tree.identify_row = lambda y: ''

        result = self.task_list.on_double_click(SimpleNamespace(x=5, y=900))

        self.assertIsNone(result)


class TestDragGesture(TaskListTestCase):
    """Pressing, moving and releasing over the rows."""

    def press(self, y):
        """Press the left button at a y coordinate."""
        self.task_list.on_press(SimpleNamespace(x=5, y=y))

    def drag(self, y):
        """Move the pointer with the button held."""
        self.task_list.on_drag(SimpleNamespace(x=5, y=y))

    def release(self, y):
        """Release the left button."""
        self.task_list.on_release(SimpleNamespace(x=5, y=y))

    def test_a_click_is_not_a_drag(self):
        """Press and release without movement leaves the order alone."""
        self.at({0: "003"})
        before = self.rows()

        self.press(0)
        self.release(0)

        self.assertEqual(self.rows(), before)
        self.assertFalse(self.task_list._dragging)

    def test_a_tiny_movement_is_not_a_drag(self):
        """A wobble below the threshold still counts as a click."""
        self.at({0: "003"})

        self.press(0)
        self.drag(1)

        self.assertFalse(self.task_list._dragging)

    def test_movement_past_the_threshold_starts_a_drag(self):
        """Travelling far enough turns the press into a drag."""
        self.at({0: "003", 100: "001"})

        self.press(0)
        self.drag(100)

        self.assertTrue(self.task_list._dragging)
        self.assertEqual(self.task_list._drop_target, "001")

    def test_a_line_marks_where_the_row_would_land(self):
        """A visible indicator is placed while dragging over a valid row."""
        self.at({0: "003", 100: "001"})
        self.rows_at({"001": (0, 100, 300, 26)})

        self.press(0)
        self.drag(100)

        line = self.task_list._drop_line_widget
        self.assertIsNotNone(line)
        self.assertTrue(line.winfo_manager())

    def test_the_line_is_thin_and_blue(self):
        """The indicator is a thin blue rule, not a shaded row."""
        self.at({0: "003", 100: "001"})
        self.rows_at({"001": (0, 100, 300, 26)})

        self.press(0)
        self.drag(100)

        line = self.task_list._drop_line_widget
        self.assertEqual(line.cget('background'),
                         self.task_list.DROP_LINE_COLOR)
        self.assertEqual(int(line.cget('height')),
                         self.task_list.DROP_LINE_THICKNESS)

    def test_the_line_sits_above_a_row_approached_from_its_top(self):
        """Pointing at the upper half puts the line on the row's top edge."""
        self.at({0: "003", 104: "001"})
        self.rows_at({"001": (0, 100, 300, 26)})

        self.press(0)
        self.drag(104)          # 4px into a 26px row

        self.assertTrue(self.task_list._drop_above)

    def test_the_line_sits_below_a_row_approached_from_its_bottom(self):
        """Pointing at the lower half puts the line on the row's bottom edge."""
        self.at({0: "003", 120: "001"})
        self.rows_at({"001": (0, 100, 300, 26)})

        self.press(0)
        self.drag(120)          # 20px into a 26px row

        self.assertFalse(self.task_list._drop_above)

    def test_the_line_spans_the_row(self):
        """The rule is as wide as the row it marks."""
        self.at({0: "003", 100: "001"})
        self.rows_at({"001": (7, 100, 280, 26)})

        self.press(0)
        self.drag(100)

        line = self.task_list._drop_line_widget
        self.assertEqual(line.place_info()['x'], '7')
        self.assertEqual(line.place_info()['width'], '280')

    def test_an_invalid_drop_row_gets_no_line(self):
        """Dragging a sub-task over a root task offers no drop."""
        self.at({0: "004", 100: "001"})
        self.rows_at({"001": (0, 100, 300, 26)})

        self.press(0)
        self.drag(100)

        self.assertIsNone(self.task_list._drop_target)
        line = self.task_list._drop_line_widget
        self.assertTrue(line is None or not line.winfo_manager())

    def test_dropping_reorders_the_rows(self):
        """A completed drag moves the row to the drop position."""
        self.at({0: "003", 100: "001"})

        self.press(0)
        self.drag(100)
        self.release(100)

        self.assertEqual(self.rows()[0], "003")

    def test_the_drag_state_is_cleared_after_a_drop(self):
        """Nothing is left marked or half-dragged once the button is up."""
        self.at({0: "003", 100: "001"})

        self.press(0)
        self.drag(100)
        self.release(100)

        self.assertIsNone(self.task_list.dragged_task_id)
        self.assertIsNone(self.task_list._drop_target)
        self.assertFalse(self.task_list._dragging)
        line = self.task_list._drop_line_widget
        self.assertTrue(line is None or not line.winfo_manager())

    def test_releasing_away_from_any_row_moves_nothing(self):
        """Dropping on empty space leaves the order alone."""
        self.at({0: "003"})
        before = self.rows()

        self.press(0)
        self.drag(500)
        self.release(500)

        self.assertEqual(self.rows(), before)

    def test_pressing_off_the_rows_starts_nothing(self):
        """A press on the heading or empty space is ignored."""
        self.at({})

        self.press(0)

        self.assertIsNone(self.task_list.dragged_task_id)


class TestContextMenu(TaskListTestCase):
    """The right-click menu and the moves it offers."""

    def menu_for(self, task_id):
        """
        Build the menu for a task and return its (label, state) entries.

        Separators carry no label, so they are skipped rather than read.
        """
        menu = self.task_list.context_menu._build(self.project, task_id)
        entries = []
        for index in range(menu.index('end') + 1):
            if menu.type(index) == 'separator':
                continue
            entries.append((menu.entrycget(index, 'label'),
                            str(menu.entrycget(index, 'state'))))
        return entries

    def test_the_entries_are_offered_in_order(self):
        """The four moves come first, then Edit and Delete."""
        labels = [label for label, _ in self.menu_for("002")]

        self.assertEqual(labels, ["Move to top", "Move up",
                                  "Move down", "Move to bottom",
                                  "Edit", "Delete"])

    def test_edit_and_delete_come_last(self):
        """The two task actions are the final entries in the menu."""
        labels = [label for label, _ in self.menu_for("002")]

        self.assertEqual(labels[-2:], ["Edit", "Delete"])

    def test_a_separator_divides_the_groups(self):
        """The moves are separated from Edit and Delete."""
        menu = self.task_list.context_menu._build(self.project, "002")

        kinds = [menu.type(i) for i in range(menu.index('end') + 1)]

        self.assertEqual(kinds.count('separator'), 1)
        self.assertEqual(kinds.index('separator'), 4)

    def test_a_middle_row_can_move_either_way(self):
        """Everything is available to a task with siblings on both sides."""
        states = {label: state for label, state in self.menu_for("002")}

        self.assertTrue(all(state == 'normal' for state in states.values()))

    def test_the_first_row_cannot_move_up(self):
        """Upward moves are greyed out at the top of a group."""
        states = {label: state for label, state in self.menu_for("001")}

        self.assertEqual(states["Move to top"], 'disabled')
        self.assertEqual(states["Move up"], 'disabled')
        self.assertEqual(states["Move down"], 'normal')
        self.assertEqual(states["Move to bottom"], 'normal')

    def test_the_last_row_cannot_move_down(self):
        """Downward moves are greyed out at the bottom of a group."""
        states = {label: state for label, state in self.menu_for("003")}

        self.assertEqual(states["Move to top"], 'normal')
        self.assertEqual(states["Move up"], 'normal')
        self.assertEqual(states["Move down"], 'disabled')
        self.assertEqual(states["Move to bottom"], 'disabled')

    def test_a_lone_subtask_can_move_nowhere(self):
        """A sub-task without siblings has every move greyed out."""
        self.project.remove_task("005")
        self.task_list.update_task_list()

        states = {label: state for label, state in self.menu_for("004")}
        moves = [state for label, state in states.items()
                 if label.startswith("Move")]

        self.assertTrue(all(state == 'disabled' for state in moves))

    def test_edit_and_delete_stay_available_when_moves_are_not(self):
        """A row that cannot move can still be edited and deleted."""
        self.project.remove_task("005")
        self.task_list.update_task_list()

        states = {label: state for label, state in self.menu_for("004")}

        self.assertEqual(states["Edit"], 'normal')
        self.assertEqual(states["Delete"], 'normal')

    def test_choosing_an_entry_moves_the_task(self):
        """Invoking a menu entry reorders the rows."""
        menu = self.task_list.context_menu._build(self.project, "003")

        menu.invoke(0)  # Move to top

        self.assertEqual(self.rows()[0], "003")

    def test_a_subtask_moves_within_its_parent(self):
        """A sub-task's move keeps it under the same parent."""
        menu = self.task_list.context_menu._build(self.project, "005")

        menu.invoke(0)  # Move to top

        self.assertEqual(self.rows(), ["001", "002", "005", "004", "003"])
        self.assertEqual(
            self.project.get_task_by_id("005").parent_task_id, "002"
        )

    def test_the_menu_binds_the_platform_gesture(self):
        """A context-menu button is bound on the tree."""
        bound = self.task_list.tree.bind()

        if self.task_list.tree.tk.call('tk', 'windowingsystem') == 'aqua':
            # macOS: right button and two-finger click arrive as Button-2
            self.assertIn('<Button-2>', bound)
            self.assertIn('<Control-Button-1>', bound)
        else:
            self.assertIn('<Button-3>', bound)

    def test_edit_opens_the_edit_window(self):
        """Choosing Edit hands the clicked task to the edit callback."""
        opened = []
        self.task_list.on_task_edit = opened.append

        menu = self.task_list.context_menu._build(self.project, "003")
        menu.invoke(5)  # Edit

        self.assertEqual([task.id for task in opened], ["003"])

    def test_edit_acts_on_the_clicked_row_not_the_selection(self):
        """Right-clicking one row while another is selected edits the one clicked."""
        opened = []
        self.task_list.on_task_edit = opened.append
        self.task_list.tree.selection_set("001")

        menu = self.task_list.context_menu._build(self.project, "003")
        menu.invoke(5)

        self.assertEqual([task.id for task in opened], ["003"])

    def test_delete_removes_the_task_once_confirmed(self):
        """Confirming the prompt deletes the row."""
        from unittest import mock

        menu = self.task_list.context_menu._build(self.project, "003")
        with mock.patch('gantt_app.views.task_list.messagebox.askyesno',
                        return_value=True):
            menu.invoke(6)  # Delete

        self.assertNotIn("003", self.rows())
        self.assertIsNone(self.project.get_task_by_id("003"))

    def test_declining_the_prompt_keeps_the_task(self):
        """Answering no leaves the plan untouched."""
        from unittest import mock

        before = self.rows()
        menu = self.task_list.context_menu._build(self.project, "003")
        with mock.patch('gantt_app.views.task_list.messagebox.askyesno',
                        return_value=False):
            menu.invoke(6)

        self.assertEqual(self.rows(), before)

    def test_deleting_a_parent_warns_about_its_subtasks(self):
        """The prompt says how many sub-tasks will go with the parent."""
        from unittest import mock

        menu = self.task_list.context_menu._build(self.project, "002")
        with mock.patch('gantt_app.views.task_list.messagebox.askyesno',
                        return_value=False) as ask:
            menu.invoke(6)

        message = ask.call_args[0][1]
        self.assertIn("2 sub-task", message)

    def test_deleting_a_childless_task_does_not_mention_subtasks(self):
        """A task with no children gets a plain prompt."""
        from unittest import mock

        menu = self.task_list.context_menu._build(self.project, "003")
        with mock.patch('gantt_app.views.task_list.messagebox.askyesno',
                        return_value=False) as ask:
            menu.invoke(6)

        self.assertNotIn("sub-task", ask.call_args[0][1])

    def test_deleting_a_parent_takes_its_subtasks(self):
        """Deleting a parent removes the whole branch."""
        from unittest import mock

        menu = self.task_list.context_menu._build(self.project, "002")
        with mock.patch('gantt_app.views.task_list.messagebox.askyesno',
                        return_value=True):
            menu.invoke(6)

        self.assertEqual(self.rows(), ["001", "003"])

    def test_right_clicking_empty_space_opens_nothing(self):
        """A click below the last row has no row to act on."""
        self.task_list.tree.identify_row = lambda y: ''

        result = self.task_list.context_menu.show(
            SimpleNamespace(x=5, y=900, x_root=0, y_root=0)
        )

        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
