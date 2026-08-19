"""
Tests for finding a work item by anything written on it.

WHY THIS MODULE EXISTS:
======================
A search that quietly misses a field is worse than no search: somebody types
a ticket number, sees nothing, and concludes the number is not in the plan.
So most of what is pinned here is coverage - every field a work item carries
has a test saying it can be found by.

The other half is what a search must *not* do. It hides rows; it must not
change the plan. Roll-up, the schedule and the critical path are measured on
every task whether or not the list is showing it.

DEVELOPMENT NOTES:
------------------
The matching is pure, so most of this needs no display. The widget tests are
kept apart and skip without one.
"""

import unittest
from datetime import datetime

from gantt_app.models import Project, Task
from gantt_app.views.searchbox import (
    matching_task_ids, task_haystack, task_matches, visible_task_ids,
)


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


class SearchTestCase(unittest.TestCase):
    """A small plan with something in every field."""

    def setUp(self):
        """Build the plan the tests search."""
        self.project = Project(name="Search")

        self.phase = Task(id="P1", name="Design Phase",
                          start_date=datetime(2026, 9, 7),
                          end_date=datetime(2026, 9, 18),
                          task_type='Phase')
        self.task = Task(id="T1", name="UI Mockups",
                         start_date=datetime(2026, 9, 7),
                         end_date=datetime(2026, 9, 11),
                         parent_task_id="P1", duration=5, progress=40,
                         priority="High",
                         details="Blocked by JIRA-4821, waiting on vendor")
        self.subtask = Task(id="S1", name="Wireframe",
                            start_date=datetime(2026, 9, 7),
                            end_date=datetime(2026, 9, 8),
                            parent_task_id="T1", task_type='Subtask')
        self.other = Task(id="T2", name="Server migration",
                          start_date=datetime(2026, 9, 14),
                          end_date=datetime(2026, 9, 15),
                          calendar_id="weekend-shift")
        self.other.add_dependency("T1", "FS", "Hard", lag=2)

        for task in (self.phase, self.task, self.subtask, self.other):
            self.project.add_task(task)

    def found(self, needle):
        """The names that match, in plan order."""
        ids = matching_task_ids(self.project, needle)
        return [t.name for t in self.project.tasks if t.id in ids]


class TestEveryFieldCanBeSearched(SearchTestCase):
    """
    A field left out is one somebody searches once and gives up on.

    DEVELOPMENT NOTES:
    ------------------
    One test per field rather than one test listing them, so a failure names
    the field that stopped working.
    """

    def test_by_name(self):
        self.assertEqual(self.found("mockups"), ["UI Mockups"])

    def test_by_id(self):
        self.assertIn("Server migration", self.found("T2"))

    def test_by_type(self):
        self.assertEqual(self.found("subtask"), ["Wireframe"])

    def test_by_notes(self):
        """The ticket number somebody pasted into the details."""
        self.assertEqual(self.found("JIRA-4821"), ["UI Mockups"])

    def test_by_start_date(self):
        """Written the way every date in the application is."""
        self.assertIn("Server migration", self.found("2026-09-14"))

    def test_by_part_of_a_date(self):
        """So a month finds everything in it."""
        self.assertEqual(len(self.found("2026-09")), 4)

    def test_by_duration(self):
        self.assertIn("UI Mockups", self.found("5"))

    def test_by_progress(self):
        self.assertIn("UI Mockups", self.found("40"))

    def test_by_priority(self):
        self.assertEqual(self.found("high"), ["UI Mockups"])

    def test_by_what_it_depends_on(self):
        """
        By the id the link holds, which is what the task stores.

        Not by the predecessor's name: including that meant searching a task
        by name also returned everything depending on it, so the commonest
        search of all came back with rows that merely mentioned the thing
        being looked for.
        """
        self.assertIn("Server migration", self.found("T1"))
        self.assertEqual(self.found("UI Mockups"), ["UI Mockups"])

    def test_by_the_kind_of_link(self):
        """The type, the hardness and the lag are all on the row."""
        self.assertIn("Server migration", self.found("Hard"))

    def test_by_its_calendar(self):
        """Also not stored on the task - only the id is."""
        self.assertIn("Server migration", self.found("Weekend-Only"))

    def test_a_milestone_is_found_by_the_word(self):
        """However its type happens to be spelt on the row."""
        project = Project(name="M")
        project.add_task(Task(id="M1", name="Sign-off",
                              start_date=datetime(2026, 9, 7),
                              is_milestone=True))

        self.assertTrue(task_matches(project.tasks[0], "milestone", project))


class TestHowMatchingBehaves(SearchTestCase):
    """Case, literalness, and the empty search."""

    def test_case_is_ignored(self):
        """Nobody types a name's capitals to find it."""
        self.assertEqual(self.found("MOCKUPS"), self.found("mockups"))

    def test_a_search_is_taken_literally(self):
        """So a date or a ticket finds itself rather than being a pattern."""
        self.assertEqual(self.found("mock.*"), [])

    def test_an_empty_search_matches_everything(self):
        """Which is what makes clearing the box the same as never typing."""
        for task in self.project.tasks:
            self.assertTrue(task_matches(task, "", self.project))
            self.assertTrue(task_matches(task, "   ", self.project))

    def test_an_empty_search_asks_the_list_for_nothing(self):
        """None rather than every id, so an empty box costs no work."""
        self.assertIsNone(visible_task_ids(self.project, ""))

    def test_the_haystack_is_one_lower_case_string(self):
        """Everything downstream assumes it."""
        haystack = task_haystack(self.task, self.project)

        self.assertIsInstance(haystack, str)
        self.assertEqual(haystack, haystack.lower())


class TestWhatStaysOnScreen(SearchTestCase):
    """A match brings its ancestors, and nothing else."""

    def test_a_match_brings_its_ancestors(self):
        """
        Or a matching sub-task floats at the top level with no sign of what
        it belongs to, and the indentation shows a structure that is not
        there.
        """
        visible = visible_task_ids(self.project, "wireframe")

        self.assertEqual(visible, {"S1", "T1", "P1"})

    def test_ancestors_are_not_counted_as_matches(self):
        """They are on screen to say where a match sits, not because they hit."""
        self.assertEqual(matching_task_ids(self.project, "wireframe"), {"S1"})

    def test_a_match_does_not_bring_its_children(self):
        """
        A Phase whose name matches shows as itself.

        Showing everything inside it would answer a question nobody asked,
        and one broad word would put the whole plan back on screen.
        """
        visible = visible_task_ids(self.project, "design phase")

        self.assertEqual(visible, {"P1"})

    def test_nothing_matching_shows_nothing(self):
        """Rather than falling back to the whole plan."""
        self.assertEqual(visible_task_ids(self.project, "zzzz"), set())

    def test_a_parent_loop_does_not_hang_the_walk(self):
        """A damaged file can carry one, and the walk climbs parents."""
        self.task.parent_task_id = "S1"      # T1 -> S1 -> T1

        visible = visible_task_ids(self.project, "wireframe")

        self.assertIn("S1", visible)


class TestSearchingChangesNothingButTheView(SearchTestCase):
    """
    It hides rows. It must not touch the plan.

    DEVELOPMENT NOTES:
    ------------------
    Nothing in models consults the view, so this holds by construction - but
    it is the assumption the whole feature rests on, and a later change that
    broke it would be found by somebody whose dates had quietly moved.
    """

    def test_the_plan_still_holds_every_task(self):
        """Filtering is a view, not a deletion."""
        before = len(self.project.tasks)

        visible_task_ids(self.project, "wireframe")

        self.assertEqual(len(self.project.tasks), before)

    def test_the_schedule_is_measured_on_the_whole_plan(self):
        """A phase spans all its children, not the visible ones."""
        self.project.reschedule()
        span = (self.phase.start_date, self.phase.end_date)

        visible_task_ids(self.project, "zzzz")
        self.project.reschedule()

        self.assertEqual((self.phase.start_date, self.phase.end_date), span)


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestTheBoxOnTheToolbar(unittest.TestCase):
    """The widget, and what it reports."""

    def setUp(self):
        """A search box over a recording callback."""
        import customtkinter as ctk
        from gantt_app.views.searchbox import TaskSearchBox

        self.root = ctk.CTk()
        self.root.withdraw()
        self.searched = []
        self.box = TaskSearchBox(self.root, on_search=self.searched.append)
        self.box.update_idletasks()

    def tearDown(self):
        """Tear the window down."""
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_typing_is_handed_over(self):
        """Fired at once here rather than waiting out the settle delay."""
        self.box.search_var.set("mockup")
        self.box._fire_now()

        self.assertEqual(self.searched[-1], "mockup")

    def test_it_reports_how_much_is_left(self):
        """
        The safeguard, not decoration.

        A filtered list looks exactly like a short plan to somebody who has
        forgotten the box has text in it.
        """
        self.box.search_var.set("mockup")
        self.box.report(2, 40)

        self.assertEqual(self.box.count_label.cget('text'), "2 of 40")

    def test_an_empty_box_says_nothing_and_offers_nothing(self):
        """No count, and no Clear button to explain away."""
        self.box.report(40, 40)

        self.assertEqual(self.box.count_label.cget('text'), "")
        self.assertFalse(self.box.clear_button.winfo_manager())

    def test_clear_appears_only_while_searching(self):
        """Beside the thing that needs explaining."""
        self.box.search_var.set("mockup")
        self.box.report(2, 40)

        self.assertTrue(self.box.clear_button.winfo_manager())

    def test_clearing_empties_the_box_and_says_so(self):
        """Which puts every row back."""
        self.box.search_var.set("mockup")
        self.box._fire_now()

        self.box.clear()

        self.assertEqual(self.box.needle, "")
        self.assertEqual(self.searched[-1], "")

    def test_typing_is_not_acted_on_per_keystroke(self):
        """
        Each one would rebuild the tree and redraw the chart with it.

        Nine renders while somebody types "milestone" is eight nobody sees.
        """
        for text in ("m", "mi", "mil", "mile"):
            self.box.search_var.set(text)

        self.assertEqual(self.searched, [])


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestTheListAndChartFollow(unittest.TestCase):
    """End to end: what the reader actually sees."""

    def setUp(self):
        """The whole application, over a fake settings file."""
        from unittest import mock
        from gantt_app import theme

        saver = mock.patch.object(theme, 'save_mode', return_value=True)
        saver.start()
        self.addCleanup(saver.stop)

        from gantt_app.main import GanttApp
        self.app = GanttApp()
        self.app.update_idletasks()
        self.addCleanup(self._destroy)

    def _destroy(self):
        """Tear the window down."""
        try:
            self.app.destroy()
        except Exception:
            pass

    def test_the_list_narrows_to_the_matches_and_their_ancestors(self):
        """The rows on screen, not the ids in a set."""
        task_list = self.app.task_list
        everything = len(task_list.visible_rows())

        task_list.apply_search("mockup")

        self.assertLess(len(task_list.visible_rows()), everything)

    def test_clearing_puts_every_row_back(self):
        """A search that could not be undone would be a trap."""
        task_list = self.app.task_list
        everything = len(task_list.visible_rows())

        task_list.apply_search("mockup")
        task_list.apply_search("")

        self.assertEqual(len(task_list.visible_rows()), everything)

    def test_the_chart_follows_without_being_told(self):
        """
        It draws from visible_rows, which reads the tree.

        This is why the search touches nothing in the chart at all.
        """
        task_list = self.app.task_list
        task_list.apply_search("mockup")
        self.app.gantt_chart.draw_chart()
        self.app.update_idletasks()

        self.assertEqual(len(self.app.gantt_chart._drawn_rows),
                         len(task_list.visible_rows()))

    def test_the_plan_is_not_touched(self):
        """Hiding a row is not deleting it."""
        before = len(self.app.project.tasks)

        self.app.task_list.apply_search("mockup")

        self.assertEqual(len(self.app.project.tasks), before)


if __name__ == '__main__':
    unittest.main()
