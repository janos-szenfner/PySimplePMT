"""
Tests for the dependency editor's list of candidate predecessors.

WHY THIS FILE EXISTS:
=====================
The chooser names a task by the number the task list shows it as, which is
where the row sits rather than what the row is - see Project.display_ids.
Working that out means walking the plan's hierarchy, and the chooser was
doing it once per row it was about to draw: a plan of eight hundred tasks
walked its own hierarchy seven hundred and ninety-nine times to fill one
dropdown, and took a fifth of a second to open a dialog.

It then read the choice back out of the label the dropdown was showing, by
formatting every candidate's label again and looking for the one that
matched the string.
"""

import time
import unittest
from datetime import datetime, timedelta

import customtkinter as ctk

from gantt_app.models import Project, Task
from gantt_app.views.dependency_editor import DependencyEditor


BASE = datetime(2026, 8, 19)


class ChooserTestCase(unittest.TestCase):
    """An editor over a plain plan of tasks."""

    SIZE = 6

    def setUp(self):
        """A plan, and an editor for its first task."""
        self.root = ctk.CTk()
        self.root.withdraw()

        self.project = Project(name="Plan")
        for number in range(1, self.SIZE + 1):
            self.project.add_task(Task(
                id=str(number).zfill(3), name=f"Task {number}",
                start_date=BASE + timedelta(days=number),
                end_date=BASE + timedelta(days=number + 1),
                task_type="Task"))

        self.editor = DependencyEditor(self.root, self.project,
                                       self.project.tasks[0])

    def tearDown(self):
        """Tear the window down."""
        try:
            self.root.destroy()
        except Exception:
            pass


class TestTheLabelsTheChooserShows(ChooserTestCase):
    """A task is named by its number and its name."""

    def test_a_label_carries_the_number_the_list_shows(self):
        """Not the identity, which the reader has never seen."""
        numbers = self.project.display_ids()
        second = self.project.get_task_by_id("002")

        self.assertEqual(self.editor._label_for(second, numbers),
                         "002 - Task 2")

    def test_two_tasks_with_the_same_name_are_still_told_apart(self):
        """
        The number does it, because a number is a position and no two rows
        share one.
        """
        self.project.get_task_by_id("002").name = "Same Name"
        self.project.get_task_by_id("003").name = "Same Name"
        numbers = self.project.display_ids()

        labels = [self.editor._label_for(task, numbers)
                  for task in self.editor.candidate_tasks()]

        self.assertEqual(len(labels), len(set(labels)))

    def test_a_task_that_is_in_no_plan_is_named_without_a_number(self):
        """Rather than raising while drawing a dialog."""
        stray = Task(id="999", name="Elsewhere", start_date=BASE,
                     end_date=BASE, task_type="Task")

        self.assertEqual(self.editor._label_for(stray, {}), " - Elsewhere")


class TestThePlanIsWalkedOncePerRedraw(ChooserTestCase):
    """However many rows the dropdown ends up holding."""

    SIZE = 40

    def walks(self):
        """Count the hierarchy walks one refresh costs."""
        counted = {'n': 0}
        real = Project.display_order

        def counting(project):
            """Project.display_order, keeping score."""
            counted['n'] += 1
            return real(project)

        Project.display_order = counting
        try:
            self.editor.refresh(notify=False)
        finally:
            Project.display_order = real
        return counted['n']

    def test_the_hierarchy_is_walked_once(self):
        """
        It used to be walked once per candidate.

        display_id builds the whole map to answer for one task, so calling
        it per row made drawing the chooser quadratic in the size of the
        plan.
        """
        self.assertEqual(self.walks(), 1)

    def test_the_cost_does_not_grow_with_the_square_of_the_plan(self):
        """
        A rough guard rather than a stopwatch: forty times the rows must not
        cost anything like sixteen hundred times the work.

        Timings are noisy on a busy machine, so this asserts the shape and
        leaves plenty of room; the count above is the exact statement.
        """
        small = Project(name="Small")
        small.add_task(Task(id="001", name="Only", start_date=BASE,
                            end_date=BASE, task_type="Task"))
        editor = DependencyEditor(self.root, small, small.tasks[0])

        start = time.time()
        editor.refresh(notify=False)
        one_row = time.time() - start

        start = time.time()
        self.editor.refresh(notify=False)
        forty_rows = time.time() - start

        editor.destroy()
        self.assertLess(forty_rows, max(one_row * 40, 0.5))


class TestChoosingACandidate(ChooserTestCase):
    """What the dropdown is showing is what gets linked."""

    def test_the_chosen_task_is_the_one_linked(self):
        """Read from what the dropdown was built from, not from its text."""
        self.editor.refresh(notify=False)
        chosen = self.editor.candidate_var.get()

        self.editor.add_selected()

        self.assertEqual(len(self.editor.links), 1)
        linked = self.project.get_task_by_id(self.editor.links[0].task_id)
        self.assertTrue(chosen.endswith(linked.name))

    def test_a_task_further_down_the_list_can_be_chosen(self):
        """Not only whichever one happens to be first."""
        self.editor.refresh(notify=False)
        values = self.editor.candidate_menu.cget('values')
        self.editor.candidate_var.set(values[2])

        self.editor.add_selected()

        linked = self.project.get_task_by_id(self.editor.links[0].task_id)
        self.assertEqual(values[2], f"{self.project.display_id(linked.id)} - "
                                    f"{linked.name}")

    def test_a_label_that_names_nothing_adds_no_link(self):
        """
        The user is told to choose one rather than linked to something at
        random.

        The prompt is stood in for rather than shown. A test that opens a
        real dialog stops and waits for somebody to click it, which is how
        this one hung the macOS build and left the Ubuntu one printing
        pages of after-script errors from the windows it never got to.
        """
        from unittest import mock

        self.editor.refresh(notify=False)
        self.editor.candidate_var.set("999 - Not a task in this plan")

        with mock.patch(
                'gantt_app.views.dependency_editor.messagebox.showinfo'
        ) as prompt:
            self.editor.add_selected()

        self.assertEqual(self.editor.links, [])
        self.assertTrue(prompt.called, "the user was told nothing")

    def test_a_task_already_linked_leaves_the_candidates(self):
        """It cannot be depended on twice."""
        self.editor.refresh(notify=False)
        first = self.editor.candidate_var.get()

        self.editor.add_selected()

        self.assertNotIn(first, self.editor.candidate_menu.cget('values'))


if __name__ == '__main__':
    unittest.main()
