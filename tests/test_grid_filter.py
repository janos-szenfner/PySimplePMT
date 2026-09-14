"""
Tests for the column filters behind the View tab's Filter button.

WHY THIS MODULE EXISTS:
======================
Each kind of filter - text, number range, date range, checklist - answers
a different question about a cell, and every one can be quietly wrong in a
way a click-through would miss: a text filter that fires on one letter, a
range that drops the rows with nothing in the cell, a checklist that
counts "everything ticked" as a filter. The matching is pure by design -
see gantt_app.views.gridfilter - so it is tested without a display here;
the tree-hiding is tested where a display exists.
"""

import unittest
from datetime import datetime

from gantt_app.models import Project, Task
from gantt_app.views.gridfilter import (
    COLUMN_KIND, TEXT_MIN, choice_values, column_value, filter_is_active,
    filtered_task_ids, matching_task_ids, row_matches)


def _plan():
    """
    A plan shaped to answer every filter kind.

    Design tasks A and B inside phase P; a milestone M at top level; a
    second phase Q with nothing in it. A is 50% done, B is done, M is a
    milestone; the phases roll up their children.
    """
    base = datetime(2026, 1, 5)
    project = Project(name="Plan")
    phase = Task.create_phase("Phase One", base, datetime(2026, 1, 30),
                              task_id="P")
    project.add_task(phase)
    project.add_task(Task(id="A", name="Draft artwork", task_type="Task",
                          start_date=base, end_date=datetime(2026, 1, 9),
                          progress=50, parent_task_id="P",
                          label="design"))
    project.add_task(Task(id="B", name="Build chart", task_type="Task",
                          start_date=datetime(2026, 1, 12),
                          end_date=datetime(2026, 1, 16), progress=100,
                          parent_task_id="P", label="code"))
    project.add_task(Task.create_milestone("Sign-off", datetime(2026, 2, 2),
                                           task_id="M"))
    project.add_task(Task.create_phase("Phase Two", base,
                                       datetime(2026, 1, 30), task_id="Q"))
    return project


class TestColumnValues(unittest.TestCase):
    """What a cell means, read back in its own type."""

    def setUp(self):
        self.project = _plan()
        self.task = self.project.get_task_by_id("A")

    def test_name_is_text(self):
        self.assertEqual(column_value(self.task, 'Task Name', self.project),
                         "Draft artwork")

    def test_start_is_a_date(self):
        self.assertEqual(
            column_value(self.task, 'Start', self.project),
            datetime(2026, 1, 5))

    def test_progress_is_a_number(self):
        self.assertEqual(column_value(self.task, 'Progress', self.project),
                         50)

    def test_milestone_is_a_fixed_value(self):
        milestone = self.project.get_task_by_id("M")
        self.assertEqual(column_value(milestone, 'Milestone', self.project),
                         "Yes")
        self.assertEqual(column_value(self.task, 'Milestone', self.project),
                         "No")

    def test_outline_counts_depth(self):
        self.assertEqual(column_value(self.task, 'Outline', self.project), 2)

    def test_calendar_falls_back_to_the_project_default(self):
        self.assertEqual(
            column_value(self.task, 'Task Calendar', self.project),
            "Project Default")


class TestTheKinds(unittest.TestCase):
    """Each filter kind, on the rows it should keep and drop."""

    def setUp(self):
        self.project = _plan()

    def _matching(self, column, spec):
        """Which ids a single column's rule leaves matching."""
        return {t.id for t in self.project.tasks
                if row_matches(t, column, spec, self.project)}

    def test_text_matches_inside_a_word(self):
        """'art' finds Draft artwork and Build chART alike."""
        self.assertEqual(self._matching('Task Name', {'text': 'art'}),
                         {"A", "B"})

    def test_text_is_case_insensitive(self):
        self.assertEqual(self._matching('Task Name', {'text': 'DRAFT'}),
                         {"A"})

    def test_short_text_asks_nothing(self):
        """Two letters match everything and so filter nothing."""
        spec = {'text': 'ar'}
        self.assertFalse(filter_is_active('Task Name', spec, self.project))
        self.assertEqual(len(self._matching('Task Name', spec)),
                         len(self.project.tasks))

    def test_number_range_keeps_the_inside(self):
        spec = {'min': 40, 'max': 60}
        self.assertEqual(self._matching('Progress', spec), {"A"})

    def test_number_range_with_one_end_is_open(self):
        self.assertEqual(self._matching('Progress', {'min': 80, 'max': None}),
                         {"B"})
        self.assertEqual(self._matching('Progress', {'min': None, 'max': 60}),
                         {"A", "M", "P", "Q"})

    def test_date_range_keeps_the_inside(self):
        spec = {'from': datetime(2026, 1, 10), 'to': datetime(2026, 1, 20)}
        self.assertEqual(self._matching('Start', spec), {"B"})

    def test_date_range_with_one_end_is_open(self):
        self.assertEqual(
            self._matching('Start', {'from': datetime(2026, 1, 10)}),
            {"B", "M"})
        self.assertEqual(
            self._matching('Start', {'to': datetime(2026, 1, 10)}),
            {"A", "P", "Q"})

    def test_choice_unticks_what_is_not_wanted(self):
        spec = {'allowed': {'Task'}}
        self.assertEqual(self._matching('Type', spec), {"A", "B"})

    def test_a_checklist_with_everything_ticked_is_no_filter(self):
        present = choice_values(self.project, 'Type')
        spec = {'allowed': set(present)}
        self.assertFalse(filter_is_active('Type', spec, self.project))

    def test_an_empty_checklist_hides_everything(self):
        """Unticking all of a kind is a real answer, not no answer."""
        spec = {'allowed': set()}
        self.assertTrue(filter_is_active('Type', spec, self.project))
        self.assertEqual(self._matching('Type', spec), set())


class TestTheSet(unittest.TestCase):
    """How the filters combine over the whole plan."""

    def setUp(self):
        self.project = _plan()

    def test_no_specs_means_no_filter(self):
        self.assertIsNone(filtered_task_ids(self.project, {}))

    def test_specs_that_ask_nothing_mean_no_filter(self):
        self.assertIsNone(filtered_task_ids(
            self.project, {'Task Name': {'text': 'a'}}))

    def test_columns_combine_with_and(self):
        """Progress <60 AND a 'phase' in the name keeps only the phase row
        under A's filter - wait, AND means both must pass."""
        filters = {'Type': {'allowed': {'Task'}},
                   'Progress': {'min': 60, 'max': None}}
        self.assertEqual(matching_task_ids(self.project, filters), {"B"})

    def test_matches_keep_their_ancestors(self):
        """A found child shows the phase it sits in, not a floating row."""
        filters = {'Task Name': {'text': 'chart'}}
        visible = filtered_task_ids(self.project, filters)
        self.assertEqual(visible, {"B", "P"})

    def test_an_empty_branch_is_not_kept_for_nothing(self):
        """Phase Two holds no match, so it does not stay on screen."""
        filters = {'Task Name': {'text': 'chart'}}
        visible = filtered_task_ids(self.project, filters)
        self.assertNotIn("Q", visible)

    def test_matching_counts_only_the_matches(self):
        filters = {'Task Name': {'text': 'phase'}}
        self.assertEqual(matching_task_ids(self.project, filters),
                         {"P", "Q"})


class _FakeTaskList:
    """The slice of DragDropTaskList the filter handlers use."""

    def __init__(self, project):
        self.project = project
        self._filter_visible = None
        self._filter_matches = set()
        self._task_variances = None

    def apply_grid_filters(self, filters, variances=None):
        self._filter_visible = filtered_task_ids(self.project, filters,
                                                 variances)
        self._filter_matches = matching_task_ids(self.project, filters,
                                                 variances)
        return len(self._filter_matches), len(self.project.tasks)

    def clear_grid_filters(self):
        self._filter_visible = None
        self._filter_matches = set()

    def grid_filters_active(self):
        return self._filter_visible is not None


class _ToolbarShell:
    """A Toolbar without its window: the attributes the handlers read."""

    def __init__(self, project):
        from gantt_app.views.toolbar import Toolbar
        self.project = project
        self.task_list = _FakeTaskList(project)
        self._grid_filters = {}
        self._grid_filter_dialog = None
        self.icon_toolbar = None
        self._apply_grid_filters = (
            Toolbar._apply_grid_filters.__get__(self))
        self.clear_grid_filter = Toolbar.clear_grid_filter.__get__(self)
        self._refresh_toggle_states = (
            Toolbar._refresh_toggle_states.__get__(self))
        self._report = lambda _m: None
        self.after_idle = lambda fn: fn()


class TestTheHandlers(unittest.TestCase):
    """What Apply and Clear do to the list through the toolbar."""

    def setUp(self):
        self.project = _plan()
        self.bar = _ToolbarShell(self.project)

    def test_apply_hides_the_rows_no_filter_passes(self):
        self.bar._apply_grid_filters({'Task Name': {'text': 'chart'}})
        self.assertEqual(self.bar.task_list._filter_visible, {"B", "P"})

    def test_the_specs_are_kept_for_the_next_opening(self):
        self.bar._apply_grid_filters({'Task Name': {'text': 'chart'}})
        self.assertEqual(self.bar._grid_filters,
                         {'Task Name': {'text': 'chart'}})

    def test_clear_puts_every_row_back(self):
        self.bar._apply_grid_filters({'Task Name': {'text': 'chart'}})
        self.bar.clear_grid_filter()
        self.assertIsNone(self.bar.task_list._filter_visible)
        self.assertEqual(self.bar._grid_filters, {})

    def test_apply_with_nothing_set_is_everything(self):
        self.bar._apply_grid_filters({})
        self.assertIsNone(self.bar.task_list._filter_visible)


def _display_available() -> bool:
    """Whether a Tk window can be opened here."""
    try:
        import tkinter
        root = tkinter.Tk()
        root.destroy()
        return True
    except Exception:
        return False


HAVE_DISPLAY = _display_available()


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestTheDateBox(unittest.TestCase):
    """The dialog's date fields take the day however it is typed."""

    def setUp(self):
        import customtkinter as ctk
        self.ctk = ctk
        self.opening_mode = str(ctk.get_appearance_mode())
        ctk.set_appearance_mode('light')
        self.root = ctk.CTk()
        self.root.withdraw()

    def tearDown(self):
        try:
            self.root.destroy()
        except Exception:
            pass
        try:
            self.ctk.set_appearance_mode(self.opening_mode)
        except Exception:
            pass

    def _boxed(self, text):
        from gantt_app.views.datepicker import DateEntry
        box = DateEntry(self.root)
        box.insert(0, text)
        return box.get_date()

    def test_dotted_dates_parse(self):
        """2026.09.01 is how the request wrote it, and it is a date."""
        self.assertEqual(self._boxed('2026.09.01'),
                         datetime(2026, 9, 1))

    def test_slashed_dates_parse(self):
        self.assertEqual(self._boxed('2026/09/01'),
                         datetime(2026, 9, 1))

    def test_dashed_dates_still_parse(self):
        self.assertEqual(self._boxed('2026-09-01'),
                         datetime(2026, 9, 1))

    def test_an_unparseable_box_asks_nothing(self):
        self.assertIsNone(self._boxed('not a date'))
        self.assertIsNone(self._boxed(''))


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestTheGridItself(unittest.TestCase):
    """The rows the tree keeps while a filter is in force."""

    def setUp(self):
        import customtkinter as ctk
        from gantt_app.utils.undoredo import (
            ProjectStateTracker, UndoRedoManager,
        )
        from gantt_app.views.task_list import DragDropTaskList

        self.ctk = ctk
        self.opening_mode = str(ctk.get_appearance_mode())
        ctk.set_appearance_mode('light')

        self.root = ctk.CTk()
        self.root.withdraw()

        self.project = _plan()
        self.task_list = DragDropTaskList(
            self.root, self.project,
            project_tracker=ProjectStateTracker(self.project,
                                                UndoRedoManager()))
        self.task_list.update_task_list()
        self.root.update_idletasks()

    def tearDown(self):
        try:
            self.root.destroy()
        except Exception:
            pass
        try:
            self.ctk.set_appearance_mode(self.opening_mode)
        except Exception:
            pass

    def _on_screen(self):
        """The ids the tree is showing, in display order."""
        return [item for item in self.task_list._rows_in_display_order()]

    def test_a_text_filter_shows_the_match_and_its_phase(self):
        self.task_list.apply_grid_filters(
            {'Task Name': {'text': 'chart'}})
        self.assertEqual(self._on_screen(), ["P", "B"])

    def test_a_filter_survives_the_rebuild_an_edit_causes(self):
        self.task_list.apply_grid_filters(
            {'Task Name': {'text': 'chart'}})
        self.task_list.update_task_list()
        self.assertEqual(self._on_screen(), ["P", "B"])

    def test_clearing_puts_every_row_back(self):
        self.task_list.apply_grid_filters(
            {'Task Name': {'text': 'chart'}})
        self.task_list.clear_grid_filters()
        self.assertEqual(set(self._on_screen()), {"P", "A", "B", "M", "Q"})

    def test_grid_filters_active_answers_the_state(self):
        self.assertFalse(self.task_list.grid_filters_active())
        self.task_list.apply_grid_filters(
            {'Task Name': {'text': 'chart'}})
        self.assertTrue(self.task_list.grid_filters_active())
        self.task_list.clear_grid_filters()
        self.assertFalse(self.task_list.grid_filters_active())


if __name__ == "__main__":
    unittest.main()
