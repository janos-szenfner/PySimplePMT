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
                task_type="Subtask", parent_task_id="002",
            ))

        self.task_list = DragDropTaskList(self.root, self.project)

    def tearDown(self):
        """Tear the root window down."""
        try:
            self.root.destroy()
        except Exception:
            pass

    def entry_index(self, menu, label):
        """
        Position of a menu entry by its label.

        Looked up rather than hardcoded: entries have been inserted ahead of
        Edit and Delete more than once, and a stale index silently invokes
        the wrong action instead of failing.
        """
        for index in range(menu.index('end') + 1):
            if menu.type(index) == 'separator':
                continue
            if menu.entrycget(index, 'label') == label:
                return index
        self.fail(f"no {label!r} entry in the menu")

    def invoke_entry(self, task_id, label):
        """
        Build the menu for a task and invoke one of its entries.

        DEVELOPMENT NOTES:
        ------------------
        The idle queue is drained afterwards. Entries that open a window -
        Create, Edit, Delete - schedule themselves there rather than running
        inside the menu's own event loop; see TaskContextMenu._after_menu.
        Without the drain those entries would appear to do nothing here.
        """
        menu = self.task_list.context_menu._build(self.project, task_id)
        menu.invoke(self.entry_index(menu, label))
        self.root.update_idletasks()
        return menu

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

    Showing #0 fixed the expander and only half the indentation: the names
    were still in a column of their own, which sits flush left however deep
    the task is, so a nested plan drew its whole hierarchy into 34 pixels of
    empty space beside names that all started at the same place. The names
    are in #0 now, where the indentation is.
    """

    def test_the_tree_column_is_shown(self):
        """Column #0 is displayed, which is what draws the expander."""
        self.assertIn('tree', str(self.task_list.tree.cget('show')))

    def test_the_tree_column_is_wide_enough_for_the_names(self):
        """It holds the name, the indentation and the expander together."""
        self.assertGreaterEqual(self.task_list.tree.column('#0', 'width'), 200)

    def test_a_parent_reports_children(self):
        """The sub-tasks hang off their parent, so ttk draws an expander."""
        self.assertEqual(list(self.task_list.tree.get_children("002")),
                         ["004", "005"])

    def test_a_leaf_reports_none(self):
        """A task without sub-tasks gets no expander."""
        self.assertEqual(list(self.task_list.tree.get_children("001")), [])

    def test_names_are_not_prefixed(self):
        """
        The name is the name, with no drawn-in tree characters.

        The indentation is the widget's, so nothing is faked into the text.
        """
        self.assertEqual(self.task_list.tree.item("004", 'text'), "Beta one")

    def test_the_name_is_in_the_column_that_indents_it(self):
        """
        Which is the whole point of putting it there.

        A nested task drew flush left while column #0 carried the entire
        hierarchy in 34 pixels of blank space nobody could read.
        """
        self.assertNotIn("Beta one", self.task_list.tree.item("004", 'values'))

    def test_selecting_a_subtask_works(self):
        """
        select_task reaches a nested row.

        It used to scan only the top level and compare against the item's
        'text', so selecting a sub-task quietly did nothing.
        """
        self.task_list.select_task("005")

        self.assertEqual(self.task_list.tree.selection(), ("005",))


class TestIndentOutdent(TaskListTestCase):
    """The Indent and Outdent entries, and what they do to the tree."""

    def levels(self):
        """Each task's type and parent, by ID."""
        return {t.id: (t.task_type, t.parent_task_id)
                for t in self.project.tasks}

    def states(self, task_id):
        """The Indent and Outdent entry states for a row."""
        menu = self.task_list.context_menu._build(self.project, task_id)
        found = {}
        for index in range(menu.index('end') + 1):
            if menu.type(index) == 'separator':
                continue
            label = menu.entrycget(index, 'label')
            if label in ("Indent", "Outdent"):
                found[label] = str(menu.entrycget(index, 'state'))
        return found

    def test_both_entries_are_offered(self):
        """The menu carries Indent and Outdent."""
        self.assertEqual(set(self.states("002")), {"Indent", "Outdent"})

    def test_indent_is_greyed_out_on_the_first_row(self):
        """There is nothing above it to go under."""
        self.assertEqual(self.states("001")["Indent"], 'disabled')

    def test_indent_is_offered_further_down(self):
        """A row with a sibling above it can go under that sibling."""
        self.assertEqual(self.states("002")["Indent"], 'normal')

    def test_outdent_is_greyed_out_at_the_top_level(self):
        """A root task has no level to come out of."""
        self.assertEqual(self.states("002")["Outdent"], 'disabled')

    def test_outdent_is_offered_for_a_subtask(self):
        """A sub-task can be lifted out."""
        self.assertEqual(self.states("004")["Outdent"], 'normal')

    def test_indent_moves_every_selected_row(self):
        """
        Not just the one the menu was opened on.

        The menu acted on the clicked row alone, so a selection of several
        had its first row indented and the rest left where they were.
        """
        self.task_list.tree.selection_set("002", "003")

        self.invoke_entry("002", "Indent")

        levels = self.levels()
        self.assertEqual(levels["002"][1], "001")
        self.assertEqual(levels["003"][1], "001")

    def test_the_moved_rows_stay_selected(self):
        """So the group can be indented again without picking it out twice."""
        self.task_list.tree.selection_set("002", "003")

        self.invoke_entry("002", "Indent")

        self.assertEqual(set(self.task_list.tree.selection()), {"002", "003"})

    def test_indent_is_offered_when_any_selected_row_can_move(self):
        """
        A selection starting at the top of a group still indents the rest.

        Greying the entry out because the first row cannot move would refuse
        a perfectly ordinary selection.
        """
        self.task_list.tree.selection_set("001", "002")

        menu = self.task_list.context_menu._build(self.project, "001")

        index = self.entry_index(menu, "Indent")
        self.assertEqual(str(menu.entrycget(index, 'state')), 'normal')

    def test_a_multi_row_indent_is_one_undo(self):
        """
        One press, one entry in the history.

        Recording an entry per row would make the user press Undo once per
        row to put back something they did in a single action.
        """
        from gantt_app.utils.undoredo import (
            UndoRedoManager, ProjectStateTracker,
        )

        manager = UndoRedoManager()
        manager.set_project(self.project)
        self.task_list.project_tracker = ProjectStateTracker(self.project,
                                                             manager)

        self.task_list.tree.selection_set("002", "003")
        self.invoke_entry("002", "Indent")
        self.assertEqual(self.levels()["003"][1], "001")

        manager.undo()
        self.task_list.update_task_list()

        levels = self.levels()
        self.assertIsNone(levels["002"][1])
        self.assertIsNone(levels["003"][1])

    def test_indenting_reparents_and_keeps_the_type(self):
        """The row goes under the one above and stays what it was."""
        self.invoke_entry("002", "Indent")

        self.assertEqual(self.levels()["002"], ("Task", "001"))

    def test_indenting_nests_the_row_in_the_tree(self):
        """The change is visible, not just in the model."""
        self.invoke_entry("002", "Indent")

        self.assertIn("002", self.task_list.tree.get_children("001"))

    def test_outdenting_lifts_a_subtask_without_retyping_it(self):
        """It reaches the top level and is still a sub-task."""
        self.invoke_entry("004", "Outdent")

        self.assertEqual(self.levels()["004"], ("Subtask", None))

    def test_the_moved_row_stays_selected(self):
        """The task stays put so it can be moved again."""
        self.invoke_entry("002", "Indent")

        self.assertEqual(self.task_list.tree.selection(), ("002",))

    def test_a_collapsed_parent_is_reopened(self):
        """
        A row indented into a folded branch is still shown.

        Left closed it would vanish from view, which reads as the task
        having been deleted.
        """
        self.task_list.tree.item("001", open=False)

        self.invoke_entry("002", "Indent")

        self.assertTrue(self.task_list.tree.item("001", 'open'))

    def test_indenting_carries_the_subtasks(self):
        """A branch moves as a whole, and none of it is retyped."""
        self.invoke_entry("002", "Indent")

        levels = self.levels()
        self.assertEqual(levels["002"], ("Task", "001"))
        self.assertEqual(levels["004"], ("Subtask", "002"))

    def test_indenting_under_a_milestone_is_refused(self):
        """A milestone cannot bracket sub-tasks."""
        first = self.project.get_task_by_id("001")
        first.is_milestone = True
        first.end_date = None

        self.assertEqual(self.states("002")["Indent"], 'disabled')


class TestIndentUndo(TaskListTestCase):
    """
    Indenting is undoable, hierarchy and all.

    DEVELOPMENT NOTES:
    ------------------
    The reorder entry cannot express this: both of its orderings hold the
    same Task objects, so restoring one puts the list back while leaving
    every parent where the indent left it.
    """

    def setUp(self):
        """Add an undo manager to the shared fixture."""
        super().setUp()
        from gantt_app.utils.undoredo import (
            UndoRedoManager, ProjectStateTracker,
        )

        self.manager = UndoRedoManager()
        self.manager.set_project(self.project)
        self.task_list.project_tracker = ProjectStateTracker(
            self.project, self.manager
        )

    def level_of(self, task_id):
        """A task's type and parent."""
        task = self.project.get_task_by_id(task_id)
        return task.task_type, task.parent_task_id

    def test_undo_restores_the_parent(self):
        """Undoing an indent puts the task back at its old level."""
        self.task_list.indent_task("002")
        self.assertEqual(self.level_of("002"), ("Task", "001"))

        self.manager.undo()

        self.assertEqual(self.level_of("002"), ("Task", None))

    def test_redo_reapplies_the_indent(self):
        """Redo puts it back under the row above."""
        self.task_list.indent_task("002")
        self.manager.undo()

        self.manager.redo()

        self.assertEqual(self.level_of("002"), ("Task", "001"))

    def test_undo_restores_an_outdent(self):
        """The same holds coming the other way."""
        self.task_list.outdent_task("004")
        self.assertEqual(self.level_of("004"), ("Subtask", None))

        self.manager.undo()

        self.assertEqual(self.level_of("004"), ("Subtask", "002"))

    def test_a_refused_change_records_nothing(self):
        """Indenting the first row leaves the undo history alone."""
        self.task_list.indent_task("001")

        self.assertFalse(self.manager.can_undo())


class TestCreateSubmenu(TaskListTestCase):
    """The Create submenu builds a task at the row it was opened on."""

    def setUp(self):
        """Add an undo manager and stub the create dialog."""
        super().setUp()
        from unittest import mock
        from datetime import datetime as dt
        from gantt_app.utils.undoredo import (
            UndoRedoManager, ProjectStateTracker,
        )
        import gantt_app.views.task_list as task_list_module

        self.manager = UndoRedoManager()
        self.manager.set_project(self.project)
        self.task_list.project_tracker = ProjectStateTracker(
            self.project, self.manager
        )

        def fake_dialog(master, project, task_type="Task", parent_task=None,
                        on_save=None, project_tracker=None):
            """Stand in for the dialog, saving as a user pressing Save would."""
            new_id = project.next_task_id()
            if task_type == "Subtask":
                task = Task.create_subtask("New", parent_task, task_id=new_id)
            elif task_type == "Milestone":
                task = Task.create_milestone("New", dt(2026, 1, 1),
                                             task_id=new_id)
            else:
                task = Task.create_task("New", dt(2026, 1, 1),
                                        dt(2026, 1, 2), task_id=new_id)
            self.created = task
            on_save(task)
            return mock.Mock()

        self._patch = mock.patch.object(task_list_module, 'CreateTaskDialog',
                                        fake_dialog)
        self._patch.start()
        self.addCleanup(self._patch.stop)

    def submenu_labels(self, task_id):
        """The Create submenu's entries."""
        menu = self.task_list.context_menu._build(self.project, task_id)
        index = self.entry_index(menu, "Create")
        submenu = menu.nametowidget(menu.entrycget(index, 'menu'))
        return [submenu.entrycget(i, 'label')
                for i in range(submenu.index('end') + 1)]

    def test_it_offers_every_type(self):
        """The four the plan is built from, outermost first."""
        self.assertEqual(
            self.submenu_labels("001"),
            ["Phase", "Task", "Subtask", "Milestone"])

    def test_a_task_lands_below_the_clicked_row(self):
        """
        The new task goes where the menu was opened, not at the end.

        add_task appends, so without repositioning a task created from the
        middle of a plan appeared at the bottom of it.
        """
        self.task_list.create_task("Task", "001")

        self.assertEqual(self.rows()[1], self.created.id)

    def test_a_task_keeps_the_level_of_the_clicked_row(self):
        """Creating beside a sub-task gives another sub-task of the parent."""
        self.task_list.create_task("Task", "004")

        self.assertEqual(self.created.parent_task_id, "002")

    def test_a_subtask_lands_under_the_clicked_row(self):
        """A sub-task is created inside the task the menu was opened on."""
        self.task_list.create_task("Subtask", "001")

        self.assertEqual(self.created.parent_task_id, "001")
        self.assertIn(self.created.id,
                      self.task_list.tree.get_children("001"))

    def test_a_milestone_lands_below_the_clicked_row(self):
        """A milestone is a sibling, like a task."""
        self.task_list.create_task("Milestone", "001")

        self.assertTrue(self.created.is_milestone)
        self.assertEqual(self.rows()[1], self.created.id)

    def test_the_new_row_is_selected(self):
        """The task just created is what the next action applies to."""
        self.task_list.create_task("Task", "001")

        self.assertEqual(self.task_list.tree.selection(), (self.created.id,))

    def test_creating_is_undoable(self):
        """Undo takes the new task away again."""
        self.task_list.create_task("Task", "001")
        self.assertIn(self.created.id, [t.id for t in self.project.tasks])

        self.manager.undo()

        self.assertNotIn(self.created.id, [t.id for t in self.project.tasks])

    def test_an_unknown_row_creates_nothing(self):
        """
        A stale row ID is ignored.

        Not the same as no row at all: a row naming a task that has since
        gone must not quietly add one at the end of the plan.
        """
        before = len(self.project.tasks)

        self.task_list.create_task("Task", "gone")

        self.assertEqual(len(self.project.tasks), before)

    def test_no_row_creates_at_the_end(self):
        """Right-clicking the empty space adds a task to the plan."""
        self.task_list.create_task("Task", None)

        self.assertEqual(self.rows()[-1], self.created.id)
        self.assertIsNone(self.created.parent_task_id)

    def test_no_row_creates_a_milestone_at_the_end(self):
        """Milestones work the same way there."""
        self.task_list.create_task("Milestone", None)

        self.assertTrue(self.created.is_milestone)
        self.assertEqual(self.rows()[-1], self.created.id)

    def test_no_row_cannot_create_a_subtask(self):
        """A sub-task has nothing to go under."""
        before = len(self.project.tasks)

        self.task_list.create_task("Subtask", None)

        self.assertEqual(len(self.project.tasks), before)


class TestUndoRedoEntries(TaskListTestCase):
    """Undo and Redo on the context menu."""

    def setUp(self):
        """Add an undo manager to the shared fixture."""
        super().setUp()
        from gantt_app.utils.undoredo import (
            UndoRedoManager, ProjectStateTracker,
        )

        self.manager = UndoRedoManager()
        self.manager.set_project(self.project)
        self.task_list.project_tracker = ProjectStateTracker(
            self.project, self.manager
        )

    def states(self, task_id):
        """The Undo and Redo entry states."""
        menu = self.task_list.context_menu._build(self.project, task_id)
        found = {}
        for index in range(menu.index('end') + 1):
            if menu.type(index) == 'separator':
                continue
            label = menu.entrycget(index, 'label')
            if label in ("Undo", "Redo"):
                found[label] = str(menu.entrycget(index, 'state'))
        return found

    def test_both_are_greyed_out_with_no_history(self):
        """Nothing has happened yet."""
        self.assertEqual(self.states("001"),
                         {"Undo": 'disabled', "Redo": 'disabled'})

    def test_undo_becomes_available_after_a_change(self):
        """A move puts something on the history."""
        self.task_list.move_task("003", 'top')

        self.assertEqual(self.states("001")["Undo"], 'normal')

    def test_redo_becomes_available_after_an_undo(self):
        """Undoing something makes it redoable."""
        self.task_list.move_task("003", 'top')
        self.task_list.undo()

        self.assertEqual(self.states("001")["Redo"], 'normal')

    def test_undo_reverses_the_change(self):
        """Choosing Undo puts the rows back."""
        before = self.rows()
        self.task_list.move_task("003", 'top')

        self.invoke_entry("001", "Undo")

        self.assertEqual(self.rows(), before)

    def test_redo_reapplies_it(self):
        """Choosing Redo brings the change back."""
        self.task_list.move_task("003", 'top')
        self.task_list.undo()

        self.invoke_entry("001", "Redo")

        self.assertEqual(self.rows()[0], "003")

    def test_undo_without_history_does_nothing(self):
        """A disabled entry invoked anyway is harmless."""
        before = self.rows()

        self.task_list.undo()

        self.assertEqual(self.rows(), before)

    def test_it_works_without_a_tracker(self):
        """A task list built with no undo support still opens its menu."""
        self.task_list.project_tracker = None

        self.assertFalse(self.task_list.can_undo())
        self.assertEqual(self.states("001")["Undo"], 'disabled')


class TestMenuDismissal(TaskListTestCase):
    """
    The menu goes away when clicked out of.

    DEVELOPMENT NOTES:
    ------------------
    grab_release() was called unconditionally straight after tk_popup. On
    macOS the menu is a native one that manages its own grab, and dropping
    it took away the grab used to notice a click outside - so the menu
    stayed up until an entry was chosen.
    """

    def test_the_grab_is_left_alone_on_macos(self):
        """The native menu keeps the grab it needs to dismiss itself."""
        self.assertIn(self.task_list.context_menu._windowing,
                      ('aqua', 'x11', 'win32'))

    def test_escape_and_focus_loss_are_bound(self):
        """Both routes out of the menu are wired up."""
        menu = self.task_list.context_menu._build(self.project, "001")
        self.task_list.context_menu._menu = menu
        menu.bind('<FocusOut>',
                  lambda _e: self.task_list.context_menu._unpost(), add='+')

        self.assertTrue(menu.bind('<FocusOut>'))

    def test_unposting_is_safe_with_no_menu(self):
        """Nothing blows up if there is nothing posted."""
        self.task_list.context_menu._menu = None

        self.task_list.context_menu._unpost()


class TestDoubleClick(TaskListTestCase):
    """Double-click folds a branch instead of opening the edit dialog."""

    def double_click(self, item):
        """Double-click the given row."""
        self.task_list.tree.identify_row = lambda y: item
        return self.task_list.on_double_click(SimpleNamespace(x=5, y=0))

    def test_double_click_does_not_fold_a_parent(self):
        """
        Folding is on the expander beside the row, not on this gesture.

        It used to be on both, which meant a double-click on a parent's
        name folded the branch away instead of letting the name be typed
        over - and the name is what somebody double-clicking it wants.
        """
        self.assertTrue(self.task_list.tree.item("002", 'open'))

        self.double_click("002")

        self.assertTrue(self.task_list.tree.item("002", 'open'))

    def test_a_closed_parent_stays_closed(self):
        """The same, from the other side."""
        self.task_list.tree.item("002", open=False)

        self.double_click("002")

        self.assertFalse(self.task_list.tree.item("002", 'open'))

    def test_double_click_opens_the_edit_dialog(self):
        """
        Two clicks in quick succession open the row's editor.

        They used to open the name box, so there was no gesture that reached
        the editor at all. Renaming in place is the slow pair now - click,
        pause, click - which is what a file manager renames with; see
        DragDropTaskList.on_release.
        """
        opened = []
        self.task_list.on_task_edit = opened.append

        self.double_click("002")
        self.double_click("001")

        self.assertEqual([t.id for t in opened], ["002", "001"])

    def test_double_click_leaves_the_rows_alone(self):
        """It opens an editor over one; it does not reorder anything."""
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
        """Moves, level changes, task actions, the clipboard, the history."""
        labels = [label for label, _ in self.menu_for("002")]

        self.assertEqual(labels, ["Move to top", "Move up",
                                  "Move down", "Move to bottom",
                                  "Indent", "Outdent",
                                  "Create", "Edit", "Delete",
                                  "Copy", "Cut", "Paste",
                                  "Paste as Sub-Task",
                                  "Undo", "Redo"])

    def test_undo_and_redo_come_last(self):
        """The history entries close the menu."""
        labels = [label for label, _ in self.menu_for("002")]

        self.assertEqual(labels[-2:], ["Undo", "Redo"])

    def test_separators_divide_the_groups(self):
        """
        Moves, level changes, task actions, clipboard and history apart.

        Four separators for five groups: the clipboard entries came in
        between the task actions and the history.
        """
        menu = self.task_list.context_menu._build(self.project, "002")

        kinds = [menu.type(i) for i in range(menu.index('end') + 1)]

        self.assertEqual(kinds.count('separator'), 4)
        self.assertEqual(kinds.index('separator'), 4)

    def test_a_middle_row_can_move_either_way(self):
        """Every move is available to a task with siblings on both sides."""
        states = {label: state for label, state in self.menu_for("002")}
        moves = [state for label, state in states.items()
                 if label.startswith("Move")]

        self.assertTrue(all(state == 'normal' for state in moves))

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
        self.invoke_entry("003", "Move to top")

        self.assertEqual(self.rows()[0], "003")

    def test_a_subtask_moves_within_its_parent(self):
        """A sub-task's move keeps it under the same parent."""
        self.invoke_entry("005", "Move to top")

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

    def test_opening_a_submenu_does_not_close_the_menu(self):
        """
        Clicking Create must open its submenu, not dismiss everything.

        Opening a submenu moves focus into it, which the menu that owns the
        submenu sees as its own focus going away - so unposting on that event
        took the whole menu down the instant Create was clicked, and its
        submenu never appeared.
        """
        menu = self.task_list.context_menu._build(self.project, "003")
        self.task_list.context_menu._menu = menu
        submenu = menu._create_submenu

        unposted = []
        self.task_list.context_menu._unpost = lambda: unposted.append(1)
        menu.focus_get = lambda: submenu

        self.task_list.context_menu._unpost_if_focus_left()

        self.assertEqual(unposted, [], "the menu closed on its own submenu")

    def test_focus_leaving_the_menu_entirely_does_close_it(self):
        """Clicking away still dismisses it, which is what the binding is for."""
        menu = self.task_list.context_menu._build(self.project, "003")
        self.task_list.context_menu._menu = menu

        unposted = []
        self.task_list.context_menu._unpost = lambda: unposted.append(1)
        menu.focus_get = lambda: self.task_list.tree

        self.task_list.context_menu._unpost_if_focus_left()

        self.assertEqual(unposted, [1])

    def test_a_menu_with_a_similar_path_is_not_one_of_ours(self):
        """
        Compared by path, so the trailing dot matters.

        Without it '.!menu2' would count '.!menu20' - a different menu
        entirely - as one of its own, and the real menu would never close.
        """
        import tkinter as tk

        menu = self.task_list.context_menu._build(self.project, "003")
        self.task_list.context_menu._menu = menu

        lookalike = tk.Menu(self.root, tearoff=0)
        lookalike._w = str(menu) + "0"

        self.assertFalse(self.task_list.context_menu._inside_menu(lookalike))
        self.assertTrue(
            self.task_list.context_menu._inside_menu(menu._create_submenu))

    def test_macos_leaves_dismissal_to_the_native_menu(self):
        """
        No focus binding at all there.

        The native menu dismisses itself on an outside click - the same
        reason its grab is left alone - and binding focus on top of that is
        what closed it on its own submenu.
        """
        import tkinter as tk
        from types import SimpleNamespace

        context = self.task_list.context_menu
        bound = {}
        original = tk.Menu.tk_popup
        tk.Menu.tk_popup = lambda self, *a, **k: bound.setdefault('menu', self)
        try:
            for windowing in ('aqua', 'x11'):
                context._windowing = windowing
                context._menu = None
                bound.clear()
                context.show(SimpleNamespace(x=1, y=1, x_root=1, y_root=1))
                sequences = set(bound['menu'].bind())
                with self.subTest(windowing=windowing):
                    self.assertIn('<Key-Escape>', sequences)
                    if windowing == 'aqua':
                        self.assertNotIn('<FocusOut>', sequences)
                    else:
                        self.assertIn('<FocusOut>', sequences)
        finally:
            tk.Menu.tk_popup = original

    def test_a_window_opening_entry_waits_for_the_menu_to_close(self):
        """
        Create, Edit and Delete are scheduled, not run where they stand.

        A menu entry's command runs inside the menu's own event loop, and on
        macOS that loop is the system's own: a dialog built in there comes up
        underneath a menu that has not finished tracking, so the first click
        looked like it had done nothing and the second one worked. The entries
        that open a window schedule themselves onto the idle queue instead.
        """
        opened = []
        self.task_list.on_task_edit = opened.append

        menu = self.task_list.context_menu._build(self.project, "003")
        menu.invoke(self.entry_index(menu, "Edit"))

        self.assertEqual(opened, [], "the window opened inside the menu loop")

        self.root.update_idletasks()

        self.assertEqual([task.id for task in opened], ["003"])

    def test_a_move_still_happens_where_it_stands(self):
        """
        Only the entries that open a window are deferred.

        A move changes the tree and nothing else, so making it wait would be
        latency for its own sake.
        """
        menu = self.task_list.context_menu._build(self.project, "003")
        menu.invoke(self.entry_index(menu, "Move to top"))

        self.assertEqual(self.rows()[0], "003")

    def test_edit_opens_the_edit_window(self):
        """Choosing Edit hands the clicked task to the edit callback."""
        opened = []
        self.task_list.on_task_edit = opened.append

        self.invoke_entry("003", "Edit")

        self.assertEqual([task.id for task in opened], ["003"])

    def test_edit_acts_on_the_clicked_row_not_the_selection(self):
        """Right-clicking one row while another is selected edits the one clicked."""
        opened = []
        self.task_list.on_task_edit = opened.append
        self.task_list.tree.selection_set("001")

        self.invoke_entry("003", "Edit")

        self.assertEqual([task.id for task in opened], ["003"])

    def test_delete_removes_the_task_once_confirmed(self):
        """Confirming the prompt deletes the row."""
        from unittest import mock

        with mock.patch('gantt_app.views.task_list.messagebox.askyesno',
                        return_value=True):
            self.invoke_entry("003", "Delete")

        self.assertNotIn("003", self.rows())
        self.assertIsNone(self.project.get_task_by_id("003"))

    def test_declining_the_prompt_keeps_the_task(self):
        """Answering no leaves the plan untouched."""
        from unittest import mock

        before = self.rows()
        with mock.patch('gantt_app.views.task_list.messagebox.askyesno',
                        return_value=False):
            self.invoke_entry("003", "Delete")

        self.assertEqual(self.rows(), before)

    def test_deleting_a_parent_warns_about_its_subtasks(self):
        """The prompt says how many sub-tasks will go with the parent."""
        from unittest import mock

        with mock.patch('gantt_app.views.task_list.messagebox.askyesno',
                        return_value=False) as ask:
            self.invoke_entry("002", "Delete")

        message = ask.call_args[0][1]
        self.assertIn("2 sub-task", message)

    def test_deleting_a_childless_task_does_not_mention_subtasks(self):
        """A task with no children gets a plain prompt."""
        from unittest import mock

        with mock.patch('gantt_app.views.task_list.messagebox.askyesno',
                        return_value=False) as ask:
            self.invoke_entry("003", "Delete")

        self.assertNotIn("sub-task", ask.call_args[0][1])

    def test_deleting_a_parent_takes_its_subtasks(self):
        """Deleting a parent removes the whole branch."""
        from unittest import mock

        with mock.patch('gantt_app.views.task_list.messagebox.askyesno',
                        return_value=True):
            self.invoke_entry("002", "Delete")

        self.assertEqual(self.rows(), ["001", "003"])

    def test_right_clicking_empty_space_opens_the_menu(self):
        """
        A click below the last row still opens a menu.

        It used to do nothing at all, leaving the empty space - the obvious
        place to right-click to add a task - inert.
        """
        menu = self.task_list.context_menu._build(self.project, None)

        labels = [menu.entrycget(i, 'label')
                  for i in range(menu.index('end') + 1)
                  if menu.type(i) != 'separator']

        self.assertIn("Create", labels)

    def test_row_actions_are_greyed_out_over_empty_space(self):
        """Nothing that needs a task is offered where there is none."""
        menu = self.task_list.context_menu._build(self.project, None)
        states = {menu.entrycget(i, 'label'): str(menu.entrycget(i, 'state'))
                  for i in range(menu.index('end') + 1)
                  if menu.type(i) != 'separator'}

        for label in ("Move to top", "Move up", "Move down", "Move to bottom",
                      "Indent", "Outdent", "Edit", "Delete"):
            self.assertEqual(states[label], 'disabled', label)

    def test_create_stays_available_over_empty_space(self):
        """Adding a task is the reason to right-click there."""
        menu = self.task_list.context_menu._build(self.project, None)
        index = self.entry_index(menu, "Create")
        submenu = menu.nametowidget(menu.entrycget(index, 'menu'))

        states = {submenu.entrycget(i, 'label'):
                  str(submenu.entrycget(i, 'state'))
                  for i in range(submenu.index('end') + 1)}

        self.assertEqual(states["Task"], 'normal')
        self.assertEqual(states["Milestone"], 'normal')

    def test_a_subtask_cannot_be_created_over_empty_space(self):
        """There is no row for it to go under."""
        menu = self.task_list.context_menu._build(self.project, None)
        index = self.entry_index(menu, "Create")
        submenu = menu.nametowidget(menu.entrycget(index, 'menu'))

        states = {submenu.entrycget(i, 'label'):
                  str(submenu.entrycget(i, 'state'))
                  for i in range(submenu.index('end') + 1)}

        self.assertEqual(states["Subtask"], 'disabled')


if __name__ == '__main__':
    unittest.main()
