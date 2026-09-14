"""
Tests for the View tab's highlight filters.

WHY THIS MODULE EXISTS:
======================
Issue #51 asks for MS Project's Highlight: a dropdown of standard filters,
each painting the rows it matches in one yellow. Only one filter is on at a
time, a second pick of the same one turns it off, and a row both critical
and matched keeps the critical red.

The filters themselves are answered without a window - each is a selector
asked of the project - so most of this file runs anywhere. The painting is
a Treeview, which needs a display, and is skipped where there is none.
"""

import unittest
from datetime import datetime

from gantt_app.models import Project, Task


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


def _plan():
    """
    A plan with one row for each question the filters ask.

    A: an ordinary task underway. B: done. C: untouched. D: a milestone.
    E: a phase, so a container. F: a deadline met. G: a deadline missed.
    H: estimated. I: inactive.
    """
    base = datetime(2026, 1, 5)
    end = datetime(2026, 1, 9)
    project = Project(name="Plan")
    project.add_task(Task(id="A", name="A", task_type="Task",
                          start_date=base, end_date=end, progress=50))
    project.add_task(Task(id="B", name="B", task_type="Task",
                          start_date=base, end_date=end, progress=100))
    project.add_task(Task(id="C", name="C", task_type="Task",
                          start_date=base, end_date=end, progress=0))
    project.add_task(Task.create_milestone("D", base, task_id="D"))
    project.add_task(Task.create_phase("E", base, end, task_id="E"))
    project.add_task(Task(id="F", name="F", task_type="Task",
                          start_date=base, end_date=end,
                          deadline=datetime(2026, 1, 30)))
    project.add_task(Task(id="G", name="G", task_type="Task",
                          start_date=base, end_date=end,
                          deadline=datetime(2026, 1, 7)))
    project.add_task(Task(id="H", name="H", task_type="Task",
                          start_date=base, end_date=end,
                          status="Estimated"))
    project.add_task(Task(id="I", name="I", task_type="Task",
                          start_date=base, end_date=end,
                          status="Inactive"))
    return project


def _select(key, project):
    """What one filter answers for the plan, as a set of ids."""
    from gantt_app.views.toolbar import Toolbar
    selector = dict((k, s) for k, _l, s in Toolbar.HIGHLIGHT_FILTERS)[key]
    return set(selector(project))


class TestTheFilters(unittest.TestCase):
    """Each standard filter picks the rows it says it does."""

    def setUp(self):
        self.project = _plan()

    def test_incomplete_means_anything_short_of_done(self):
        self.assertEqual(
            _select('incomplete', self.project),
            {"A", "C", "D", "E", "F", "G", "H", "I"})

    def test_unstarted_means_no_progress_at_all(self):
        self.assertEqual(
            _select('unstarted', self.project),
            {"C", "D", "E", "F", "G", "H", "I"})

    def test_in_progress_means_some_but_not_all(self):
        self.assertEqual(_select('in_progress', self.project), {"A"})

    def test_complete_means_done(self):
        self.assertEqual(_select('complete', self.project), {"B"})

    def test_milestones_picks_the_milestone(self):
        self.assertEqual(_select('milestones', self.project), {"D"})

    def test_summary_picks_the_phase(self):
        self.assertEqual(_select('summary', self.project), {"E"})

    def test_deadlines_means_carrying_one(self):
        self.assertEqual(_select('deadlines', self.project), {"F", "G"})

    def test_late_means_past_the_deadline(self):
        self.assertEqual(_select('late', self.project), {"G"})

    def test_estimated_picks_the_estimated_row(self):
        self.assertEqual(_select('estimated', self.project), {"H"})

    def test_inactive_picks_the_inactive_row(self):
        self.assertEqual(_select('inactive', self.project), {"I"})

    def test_every_filter_has_a_label_a_reader_would_say(self):
        from gantt_app.views.toolbar import Toolbar
        for key, label, _selector in Toolbar.HIGHLIGHT_FILTERS:
            self.assertTrue(key and label)


class _FakeTaskList:
    """The slice of DragDropTaskList the highlight handlers use."""

    def __init__(self):
        self.painted = set()

    def show_highlighted_rows(self, task_ids):
        self.painted = set(task_ids)
        return len(self.painted)

    def clear_highlight(self):
        self.show_highlighted_rows(())

    def highlighted_rows_shown(self):
        return bool(self.painted)


class _ToolbarShell:
    """A Toolbar without its window: the attributes the handlers read."""

    def __init__(self, project):
        from gantt_app.views.toolbar import Toolbar
        self.HIGHLIGHT_FILTERS = Toolbar.HIGHLIGHT_FILTERS
        self.project = project
        self.task_list = _FakeTaskList()
        self._active_highlight = None
        self.on_project_changed = None
        self.apply_highlight = Toolbar.apply_highlight.__get__(self)
        self.clear_highlight = Toolbar.clear_highlight.__get__(self)
        self._highlight_gallery_items = (
            Toolbar._highlight_gallery_items.__get__(self))
        self._custom_filters_in_menu = (
            Toolbar._custom_filters_in_menu.__get__(self))
        self._refresh_toggle_states = (
            Toolbar._refresh_toggle_states.__get__(self))
        self.new_highlight_filter = (
            Toolbar.new_highlight_filter.__get__(self))
        self.more_highlight_filters = (
            Toolbar.more_highlight_filters.__get__(self))
        self._report = lambda _m: None
        self.after_idle = lambda fn: fn()
        self.icon_toolbar = None


class TestOneHighlightAtATime(unittest.TestCase):
    """The exclusivity and the toggle the menu promises."""

    def setUp(self):
        self.project = _plan()
        self.bar = _ToolbarShell(self.project)

    def test_a_pick_paints_its_rows(self):
        self.bar.apply_highlight('complete')
        self.assertEqual(self.bar.task_list.painted, {"B"})

    def test_a_second_pick_replaces_not_adds(self):
        self.bar.apply_highlight('complete')
        self.bar.apply_highlight('milestones')
        self.assertEqual(self.bar.task_list.painted, {"D"})

    def test_picking_the_active_one_again_turns_it_off(self):
        self.bar.apply_highlight('complete')
        self.bar.apply_highlight('complete')
        self.assertFalse(self.bar.task_list.highlighted_rows_shown())
        self.assertIsNone(self.bar._active_highlight)

    def test_clear_takes_the_paint_off(self):
        self.bar.apply_highlight('milestones')
        self.bar.clear_highlight()
        self.assertFalse(self.bar.task_list.highlighted_rows_shown())
        self.assertIsNone(self.bar._active_highlight)

    def test_the_gallery_ticks_the_filter_that_is_on(self):
        self.bar.apply_highlight('milestones')
        labels = [item.get('label', '')
                  for item in self.bar._highlight_gallery_items()]
        self.assertIn("✓ Milestones", labels)
        self.assertIn("Incomplete Tasks", labels)

    def test_the_gallery_ends_the_way_ms_projects_does(self):
        labels = [item.get('label', '')
                  for item in self.bar._highlight_gallery_items()]
        self.assertIn("Clear Highlight", labels)
        self.assertIn("New Highlight Filter...", labels)
        self.assertIn("More Highlight Filters...", labels)


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestThePaintedRows(unittest.TestCase):
    """What the rows look like while a filter is painting them."""

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

    def _fill(self, task_id):
        """The background the row is actually painted with."""
        tags = [tag for tag in self.task_list.tree.item(task_id, 'tags')
                if tag.startswith('row_')]
        return str(self.task_list.tree.tag_configure(tags[0], 'background'))

    def test_matched_rows_take_the_highlight_yellow(self):
        from gantt_app import theme
        self.task_list.show_highlighted_rows({"A", "C"})
        self.assertEqual(self._fill("A"), theme.now(theme.GRID_HIGHLIGHT_BG))
        self.assertEqual(self._fill("C"), theme.now(theme.GRID_HIGHLIGHT_BG))

    def test_unmatched_rows_keep_their_banding(self):
        self.task_list.show_highlighted_rows({"A"})
        self.assertNotEqual(
            self._fill("B"),
            str(self.ctk.ThemeManager.theme["CTkFrame"]["fg_color"]))

    def test_the_paint_survives_a_rebuild(self):
        from gantt_app import theme
        self.task_list.show_highlighted_rows({"A"})
        self.task_list.update_task_list()
        self.assertEqual(self._fill("A"), theme.now(theme.GRID_HIGHLIGHT_BG))

    def test_critical_red_beats_the_yellow(self):
        """A row both critical and matched stays red."""
        from gantt_app import theme
        self.task_list.show_critical_path_rows({"A"})
        self.task_list.show_highlighted_rows({"A", "B"})
        self.assertEqual(self._fill("A"), theme.now(theme.GRID_CRITICAL_BG))
        self.assertEqual(self._fill("B"), theme.now(theme.GRID_HIGHLIGHT_BG))

    def test_the_yellow_follows_the_appearance(self):
        from gantt_app import theme
        self.task_list.show_highlighted_rows({"A"})
        self.ctk.set_appearance_mode('dark')
        self.task_list.apply_theme()
        self.assertEqual(self._fill("A"), theme.GRID_HIGHLIGHT_BG[1])

    def test_clearing_leaves_every_row_alone(self):
        self.task_list.show_highlighted_rows({"A"})
        self.task_list.clear_highlight()
        self.assertFalse(self.task_list.highlighted_rows_shown())


if __name__ == "__main__":
    unittest.main()
