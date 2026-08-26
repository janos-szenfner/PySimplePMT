"""
Tests for Link Tasks and Unlink Tasks.

WHY THIS FILE EXISTS:
=====================
Linking rows one after another is how a plan gets its shape, and doing it by
typing numbers into the Predecessors column is the slow way round. These two
buttons do to a selection what the reference tool's chain icons do: chain the
rows Finish-to-Start down the list, and break those links again.

The part worth guarding is the order. A chain is only right if it runs the way
the plan reads, and the selection it is built from does not arrive in that
order - a Treeview hands back the rows in the order they were added to the
selection, so shift-clicking upwards gives them bottom-first.
"""

import unittest
from datetime import datetime, timedelta

from gantt_app.models import Project, Task


BASE = datetime(2026, 8, 19)


class LinkingTestCase(unittest.TestCase):
    """A plain plan of four tasks, one after another down the list."""

    def setUp(self):
        """Four unlinked tasks."""
        self.project = Project(name="Plan")
        for task_id, name in (("001", "Alpha"), ("002", "Beta"),
                              ("003", "Gamma"), ("004", "Delta")):
            self.project.add_task(Task(
                id=task_id, name=name, start_date=BASE,
                end_date=BASE + timedelta(days=2), task_type="Task"))

    def links(self, task_id):
        """What one task waits for, by identity."""
        task = self.project.get_task_by_id(task_id)
        return [link.task_id for link in task.dependencies]


class TestLinking(LinkingTestCase):
    """Chaining a selection Finish-to-Start."""

    def test_it_chains_each_row_to_the_one_before_it(self):
        """Not all of them to the first."""
        self.project.link_tasks(["001", "002", "003"])

        self.assertEqual(self.links("001"), [])
        self.assertEqual(self.links("002"), ["001"])
        self.assertEqual(self.links("003"), ["002"])

    def test_the_chain_runs_in_grid_order(self):
        """
        However the rows were picked out.

        A Treeview reports a selection in the order rows were added to it, so
        shift-clicking upwards from the bottom hands them back bottom-first.
        A chain built from that would run backwards through the plan.
        """
        self.project.link_tasks(["003", "001", "002"])

        self.assertEqual(self.links("002"), ["001"])
        self.assertEqual(self.links("003"), ["002"])

    def test_the_link_is_finish_to_start_with_no_lag(self):
        """Which is what a plain link means."""
        self.project.link_tasks(["001", "002"])

        link = self.project.get_task_by_id("002").get_dependency("001")
        self.assertEqual(link.dep_type, 'FS')
        self.assertEqual(link.lag, 0)
        self.assertEqual(link.hardness, 'Hard')

    def test_it_says_which_pairs_it_joined(self):
        """So the caller can tell whether anything happened."""
        made = self.project.link_tasks(["001", "002", "003"])

        self.assertEqual(made, [("001", "002"), ("002", "003")])

    def test_a_row_keeps_the_links_it_already_had(self):
        """
        Linking adds to a plan rather than stating everything a row waits
        for, so a link to something outside the selection survives.
        """
        self.project.get_task_by_id("003").add_dependency("004")

        self.project.link_tasks(["002", "003"])

        self.assertEqual(sorted(self.links("003")), ["002", "004"])

    def test_linking_the_same_rows_twice_changes_nothing(self):
        """The second press has nothing to add."""
        self.project.link_tasks(["001", "002"])

        self.assertEqual(self.project.link_tasks(["001", "002"]), [])
        self.assertEqual(self.links("002"), ["001"])

    def test_one_row_is_nothing_to_chain(self):
        """A chain needs two ends."""
        self.assertEqual(self.project.link_tasks(["001"]), [])
        self.assertEqual(self.links("001"), [])

    def test_a_row_that_is_in_no_plan_is_left_out(self):
        """A stale ID does not break the chain around it."""
        self.project.link_tasks(["001", "nonexistent", "002"])

        self.assertEqual(self.links("002"), ["001"])

    def test_a_pair_that_would_close_a_loop_is_skipped(self):
        """
        And the rest of the chain is still made.

        Refusing the whole selection would mean one awkward pair in the
        middle of it doing nothing at all, with the reason buried.
        """
        self.project.get_task_by_id("001").add_dependency("002")

        made = self.project.link_tasks(["001", "002", "003"])

        self.assertEqual(made, [("002", "003")])
        self.assertEqual(self.links("002"), [])
        self.assertEqual(self.links("003"), ["002"])


class TestUnlinking(LinkingTestCase):
    """Breaking the links again."""

    def test_it_removes_the_links_between_the_chosen_rows(self):
        """The chain the button made, taken back."""
        self.project.link_tasks(["001", "002", "003"])

        self.project.unlink_tasks(["001", "002", "003"])

        self.assertEqual(self.links("002"), [])
        self.assertEqual(self.links("003"), [])

    def test_a_link_outside_the_selection_is_left_alone(self):
        """The user pointed at these rows and not at that one."""
        self.project.link_tasks(["001", "002", "003"])
        self.project.get_task_by_id("003").add_dependency("004")

        self.project.unlink_tasks(["002", "003"])

        self.assertEqual(self.links("003"), ["004"])

    def test_one_row_loses_every_link_it_is_part_of(self):
        """
        There is no "between" for a single row, and unlinking it otherwise
        would do nothing at all.
        """
        self.project.link_tasks(["001", "002", "003"])

        removed = self.project.unlink_tasks(["002"])

        self.assertEqual(self.links("002"), [])
        self.assertEqual(self.links("003"), [])
        self.assertEqual(sorted(removed), [("001", "002"), ("002", "003")])

    def test_it_says_which_links_it_removed(self):
        """Empty when there was nothing between the rows."""
        self.assertEqual(self.project.unlink_tasks(["001", "002"]), [])

    def test_nothing_selected_is_nothing_to_do(self):
        """Rather than every link in the plan."""
        self.project.link_tasks(["001", "002"])

        self.assertEqual(self.project.unlink_tasks([]), [])
        self.assertEqual(self.links("002"), ["001"])


class TestUndoPutsTheDatesBack(unittest.TestCase):
    """
    Undoing a link undoes what the link did to the schedule.

    WHY THESE EXIST:
    ================
    Linking reschedules, and the reschedule was run after the undo entry had
    been recorded - so undo took the link out and left the row sitting where
    the link had pushed it. A plan half reverted is worse than either end of
    it: the column says the rows are not linked and the dates say they are.

    The dates are part of the snapshot now, and the rescheduling runs inside
    the entry. See SnapshotCommand.FIELDS.
    """

    def setUp(self):
        """Two tasks that do not yet wait for each other."""
        from gantt_app.utils.undoredo import (
            UndoRedoManager, ProjectStateTracker,
        )

        self.project = Project(name="Plan")
        for task_id, name in (("001", "Alpha"), ("002", "Beta")):
            self.project.add_task(Task(
                id=task_id, name=name, start_date=BASE,
                end_date=BASE + timedelta(days=2), task_type="Task"))

        self.manager = UndoRedoManager()
        self.tracker = ProjectStateTracker(self.project, self.manager)

    def dates(self):
        """Every row's start and end."""
        return [(t.id, t.start_date, t.end_date) for t in self.project.tasks]

    def link(self):
        """A link recorded the way the task list records it."""
        def apply():
            """The link, and the dates it moves."""
            if not self.project.link_tasks(["001", "002"]):
                return False
            self.project.apply_schedule()
            return True

        self.tracker.run_as_command(apply, "Link Tasks")

    def test_the_link_moves_the_row_it_pushes(self):
        """Otherwise there would be nothing to put back."""
        before = self.dates()

        self.link()

        self.assertNotEqual(self.dates(), before)

    def test_undo_puts_the_dates_back_with_the_link(self):
        """Not the link alone."""
        before = self.dates()

        self.link()
        self.manager.undo()

        self.assertEqual(self.dates(), before)
        self.assertEqual(list(self.project.get_task_by_id("002").dependencies),
                         [])

    def test_redo_moves_them_again(self):
        """The snapshot after the action carries the dates too."""
        self.link()
        after = self.dates()

        self.manager.undo()
        self.manager.redo()

        self.assertEqual(self.dates(), after)

    def test_the_snapshot_names_every_field_scheduling_writes(self):
        """
        A field the passes write and the snapshot does not hold is a field
        undo cannot put back.
        """
        from gantt_app.utils.undoredo import SnapshotCommand

        for name in ('start_date', 'end_date', 'duration'):
            self.assertIn(name, SnapshotCommand.FIELDS)


class TestTheButtonsAndTheirKeys(unittest.TestCase):
    """What the toolbar offers, and what answers to the keyboard."""

    def test_the_row_carries_both_icons(self):
        """Between the dividers, after the group that acts on a row."""
        from gantt_app.views.toolbar import IconToolbar

        row = [name for name, _tip, _action in IconToolbar.ICON_ACTIONS]

        self.assertEqual(row[row.index('link') + 1], 'unlink')
        self.assertEqual(row[row.index('link') - 1], 'outdent')
        self.assertEqual(row[row.index('unlink') + 1], IconToolbar.SEPARATOR)

    def test_both_icons_have_a_drawing_and_a_fallback(self):
        """An icon with neither is a blank button that does nothing."""
        from gantt_app.resources.icons import ICON_STROKES, ICON_EMOJIS

        for name in ('link', 'unlink'):
            self.assertIn(name, ICON_STROKES)
            self.assertIn(name, ICON_EMOJIS)

    def test_both_have_a_handler_on_the_toolbar(self):
        """The row names them; Toolbar has to answer to those names."""
        from gantt_app.views.toolbar import Toolbar

        self.assertTrue(callable(getattr(Toolbar, 'link_selected', None)))
        self.assertTrue(callable(getattr(Toolbar, 'unlink_selected', None)))

    def test_they_are_live_only_with_a_plan_open(self):
        """Like everything else that acts on the task list."""
        from gantt_app.resources.icons import ACTIVE_WHEN_PROJECT_OPEN

        self.assertIn('link', ACTIVE_WHEN_PROJECT_OPEN)
        self.assertIn('unlink', ACTIVE_WHEN_PROJECT_OPEN)

    def test_the_keys_carry_this_platform_s_modifier(self):
        """Command on a Mac, Control elsewhere; see gantt_app.shortcuts."""
        from gantt_app.shortcuts import MODIFIER, sequences

        self.assertEqual(sequences('F2'), (f"<{MODIFIER}-F2>",))
        self.assertEqual(sequences('F2', shift=True),
                         (f"<{MODIFIER}-Shift-F2>",))

    def test_the_captions_are_written_the_way_the_platform_writes_them(self):
        """A caption promising a key that is not bound is worse than none."""
        from gantt_app.shortcuts import IS_MACOS, accelerator

        if IS_MACOS:
            self.assertEqual(accelerator('F2'), '⌘F2')
            self.assertEqual(accelerator('F2', shift=True), '⇧⌘F2')
        else:
            self.assertEqual(accelerator('F2'), 'Ctrl+F2')
            self.assertEqual(accelerator('F2', shift=True), 'Ctrl+Shift+F2')

    def test_the_tooltips_name_the_keys(self):
        """So the row says what it answers to."""
        from gantt_app.shortcuts import accelerator
        from gantt_app.views.toolbar import IconToolbar

        tips = {name: tip for name, tip, _a in IconToolbar.ICON_ACTIONS}

        self.assertIn(accelerator('F2'), tips['link'])
        self.assertIn(accelerator('F2', shift=True), tips['unlink'])


if __name__ == '__main__':
    unittest.main()
