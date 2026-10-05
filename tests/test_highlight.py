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

    The status date is pinned to the plan's own start: Late Tasks reads
    finishes against it, and a real 'today' drifting past these fixed
    dates would flag every row late and age the assertions into lies.
    """
    base = datetime(2026, 1, 5)
    end = datetime(2026, 1, 9)
    project = Project(name="Plan")
    project.status_date = base
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

    def test_late_means_past_the_finish_and_undone(self):
        """Issue #76: a finish behind the status date is late, 0% or not."""
        base = datetime(2026, 1, 5)
        project = _plan()
        # The day after every row finishes: all the unfinished are late.
        project.status_date = datetime(2026, 1, 12)
        self.assertEqual(
            _select('late', project),
            {"A", "C", "D", "E", "F", "G", "H", "I"})

    def test_late_leaves_the_done_row_alone(self):
        project = _plan()
        project.status_date = datetime(2026, 1, 12)
        # B finished days ago but is complete, so it cannot be late.
        self.assertNotIn("B", _select('late', project))

    def test_late_reads_today_when_the_plan_names_no_status_date(self):
        project = _plan()
        project.status_date = None
        # The plan's 2026 finishes are all behind any real today, so the
        # unfinished rows are late without a status date being set.
        late = _select('late', project)
        self.assertIn("A", late)
        self.assertNotIn("B", late)

    def test_summary_means_a_row_with_children_too(self):
        """Issue #68: a Task holding children is a summary, not just a
        Phase typed as one."""
        project = _plan()
        parent = Task(id="P", name="P", task_type="Task",
                      start_date=datetime(2026, 1, 5),
                      end_date=datetime(2026, 1, 9))
        child = Task(id="Q", name="Q", task_type="Task",
                     start_date=datetime(2026, 1, 5),
                     end_date=datetime(2026, 1, 9))
        child.parent_task_id = "P"
        project.add_task(parent)
        project.add_task(child)
        self.assertEqual(_select('summary', project), {"E", "P"})

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
        self.HIGHLIGHT_FILTER_RULES = Toolbar.HIGHLIGHT_FILTER_RULES
        self.project = project
        self.task_list = _FakeTaskList()
        self._active_highlight = None
        self.on_project_changed = None
        for name in ('apply_highlight', 'clear_highlight',
                     'refresh_highlight', '_highlight_matching_ids',
                     '_highlight_gallery_items', '_custom_filters_in_menu',
                     '_find_custom_filter', '_save_custom_filter',
                     '_unique_filter_name', '_more_filters_entries',
                     '_more_filters_copy', '_more_filters_delete',
                     '_reload_more_filters',
                     'new_highlight_filter', 'more_highlight_filters'):
            setattr(self, name, getattr(Toolbar, name).__get__(self))
        self._more_filters_dialog = None
        self._refresh_toggle_states = (
            Toolbar._refresh_toggle_states.__get__(self))
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


class TestTheGallerySections(unittest.TestCase):
    """Issue #78: built-ins and customs are distinct menu sections."""

    def setUp(self):
        self.project = _plan()
        self.bar = _ToolbarShell(self.project)

    def test_built_ins_open_under_their_own_header(self):
        items = self.bar._highlight_gallery_items()
        self.assertEqual(items[0].get('type'), 'header')
        self.assertEqual(items[0].get('label'), 'Built-in')
        self.assertEqual(items[1].get('label'), 'Incomplete Tasks')

    def test_customs_list_under_their_own_header(self):
        self.project.custom_filters = [
            {'name': 'Mine', 'show_in_menu': True,
             'rules': [{'field': 'Progress', 'test': 'equals',
                        'value': '0'}]}]
        items = self.bar._highlight_gallery_items()
        labels = [item.get('label') for item in items]
        self.assertIn('Custom', labels)
        self.assertLess(labels.index('Built-in'),
                        labels.index('Milestones'))
        self.assertLess(labels.index('Custom'), labels.index('Mine'))

    def test_no_custom_section_when_none_are_kept_in_the_menu(self):
        labels = [item.get('label')
                  for item in self.bar._highlight_gallery_items()]
        self.assertNotIn('Custom', labels)


class TestTheHighlightFollowingEdits(unittest.TestCase):
    """Issue #67: the paint follows the plan, not a remembered id set."""

    def setUp(self):
        self.project = _plan()
        self.bar = _ToolbarShell(self.project)

    def test_a_row_edited_out_leaves_the_paint(self):
        self.bar.apply_highlight('unstarted')
        self.assertIn("C", self.bar.task_list.painted)
        self.project.get_task_by_id("C").progress = 10
        self.bar.refresh_highlight()
        self.assertNotIn("C", self.bar.task_list.painted)

    def test_a_row_edited_in_joins_the_paint(self):
        self.bar.apply_highlight('complete')
        self.assertEqual(self.bar.task_list.painted, {"B"})
        self.project.get_task_by_id("A").progress = 100
        self.bar.refresh_highlight()
        self.assertEqual(self.bar.task_list.painted, {"A", "B"})

    def test_the_filter_stays_on_across_the_refresh(self):
        self.bar.apply_highlight('unstarted')
        self.bar.refresh_highlight()
        self.assertEqual(self.bar._active_highlight, 'unstarted')

    def test_a_custom_highlight_refreshes_too(self):
        self.project.custom_filters = [
            {'name': 'Done', 'show_in_menu': True,
             'rules': [{'field': 'Progress', 'test': 'gte',
                        'value': '100'}]}]
        self.bar.apply_highlight('custom:Done')
        self.assertEqual(self.bar.task_list.painted, {"B"})
        self.project.get_task_by_id("A").progress = 100
        self.bar.refresh_highlight()
        self.assertEqual(self.bar.task_list.painted, {"A", "B"})

    def test_refresh_with_nothing_on_does_nothing(self):
        self.bar.refresh_highlight()
        self.assertFalse(self.bar.task_list.highlighted_rows_shown())
        self.assertIsNone(self.bar._active_highlight)


class TestCopyingFilters(unittest.TestCase):
    """Issue #79: copy works on built-ins and names never collide."""

    def setUp(self):
        self.project = _plan()
        self.bar = _ToolbarShell(self.project)

    def test_copying_a_built_in_saves_its_rules_under_a_copy_name(self):
        name = self.bar._more_filters_copy('late')
        self.assertEqual(name, 'Late Tasks - Copy')
        clone = self.bar._find_custom_filter(name)
        self.assertIsNotNone(clone)
        from gantt_app.views.gridfilter import definition_matching_ids
        self.assertEqual(
            definition_matching_ids(self.project, clone),
            _select('late', self.project))

    def test_a_second_copy_takes_a_numbered_name(self):
        first = self.bar._more_filters_copy('incomplete')
        second = self.bar._more_filters_copy('incomplete')
        self.assertEqual(first, 'Incomplete Tasks - Copy')
        self.assertEqual(second, 'Incomplete Tasks - Copy 1')

    def test_copying_a_custom_filter_clones_its_rules(self):
        self.project.custom_filters = [
            {'name': 'Mine', 'show_in_menu': True,
             'rules': [{'field': 'Progress', 'test': 'lt',
                        'value': '50'}]}]
        name = self.bar._more_filters_copy('Mine')
        self.assertEqual(name, 'Mine - Copy')
        clone = self.bar._find_custom_filter(name)
        self.assertEqual(clone['rules'],
                         [{'field': 'Progress', 'test': 'lt',
                           'value': '50'}])

    def test_every_built_in_copy_paints_what_the_built_in_paints(self):
        """The rules table and the selectors may never drift apart."""
        from gantt_app.views.gridfilter import definition_matching_ids
        from gantt_app.views.toolbar import Toolbar
        for key, _label, selector in Toolbar.HIGHLIGHT_FILTERS:
            rules = Toolbar.HIGHLIGHT_FILTER_RULES[key]
            self.assertEqual(
                definition_matching_ids(
                    self.project, {'name': 'x', 'rules': rules}),
                set(selector(self.project)), key)

    def test_two_filters_cannot_share_a_name(self):
        self.project.custom_filters = [
            {'name': 'Mine', 'show_in_menu': False,
             'rules': [{'field': 'Progress', 'test': 'lt',
                        'value': '50'}]}]
        error = self.bar._save_custom_filter(
            {'name': 'Mine', 'rules': [{'field': 'Progress',
                                       'test': 'gt', 'value': '50'}]})
        self.assertTrue(error)
        self.assertEqual(len(self.project.custom_filters), 1)

    def test_a_filter_cannot_take_a_built_ins_name(self):
        error = self.bar._save_custom_filter(
            {'name': 'Late Tasks',
             'rules': [{'field': 'Progress', 'test': 'lt',
                        'value': '50'}]})
        self.assertTrue(error)
        self.assertEqual(self.project.custom_filters, [])

    def test_keeping_its_own_name_on_edit_is_not_a_collision(self):
        self.project.custom_filters = [
            {'name': 'Mine', 'show_in_menu': False,
             'rules': [{'field': 'Progress', 'test': 'lt',
                        'value': '50'}]}]
        error = self.bar._save_custom_filter(
            {'name': 'Mine',
             'rules': [{'field': 'Progress', 'test': 'gt',
                        'value': '50'}]}, old_name='Mine')
        self.assertIsNone(error)
        self.assertEqual(
            self.project.custom_filters[0]['rules'][0]['test'], 'gt')


class TestTheNewFilterFields(unittest.TestCase):
    """Issue #77: Type offers the whole vocabulary, Phase included."""

    def setUp(self):
        self.project = _plan()

    def test_type_offers_phase_even_when_the_plan_has_none(self):
        from gantt_app.views.gridfilter import choice_values
        project = _plan()
        # Drop the phase row so only present values remain: Phase is
        # still offered, the vocabulary being closed rather than empty.
        project.tasks = [t for t in project.tasks if t.id != 'E']
        values = choice_values(project, 'Type')
        self.assertIn('Phase', values)
        self.assertIn('Task', values)
        self.assertIn('Milestone', values)
        self.assertNotIn('Subtask', values)

    def test_a_phase_rule_matches_the_phase_row(self):
        from gantt_app.views.gridfilter import definition_matching_ids
        definition = {'name': 'Phases',
                      'rules': [{'field': 'Type', 'test': 'equals',
                                 'value': 'Phase'}]}
        self.assertEqual(
            definition_matching_ids(self.project, definition), {"E"})

    def test_summary_and_deadline_and_late_are_filterable_fields(self):
        from gantt_app.views.gridfilter import definition_matching_ids
        self.project.status_date = datetime(2026, 1, 12)
        deadline = {'name': 'x', 'rules': [
            {'field': 'Deadline', 'test': 'is_not_empty'}]}
        self.assertEqual(
            definition_matching_ids(self.project, deadline), {"F", "G"})
        summary = {'name': 'x', 'rules': [
            {'field': 'Summary', 'test': 'equals', 'value': 'Yes'}]}
        self.assertEqual(
            definition_matching_ids(self.project, summary), {"E"})
        late = {'name': 'x', 'rules': [
            {'field': 'Late', 'test': 'equals', 'value': 'Yes'}]}
        self.assertIn("A",
                      definition_matching_ids(self.project, late))


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
            _shut_down(self.root)
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
        from gantt_app.views import theme
        self.task_list.show_highlighted_rows({"A", "C"})
        self.assertEqual(self._fill("A"), theme.now(theme.GRID_HIGHLIGHT_BG))
        self.assertEqual(self._fill("C"), theme.now(theme.GRID_HIGHLIGHT_BG))

    def test_unmatched_rows_keep_their_banding(self):
        self.task_list.show_highlighted_rows({"A"})
        self.assertNotEqual(
            self._fill("B"),
            str(self.ctk.ThemeManager.theme["CTkFrame"]["fg_color"]))

    def test_the_paint_survives_a_rebuild(self):
        from gantt_app.views import theme
        self.task_list.show_highlighted_rows({"A"})
        self.task_list.update_task_list()
        self.assertEqual(self._fill("A"), theme.now(theme.GRID_HIGHLIGHT_BG))

    def test_critical_red_beats_the_yellow(self):
        """A row both critical and matched stays red."""
        from gantt_app.views import theme
        self.task_list.show_critical_path_rows({"A"})
        self.task_list.show_highlighted_rows({"A", "B"})
        self.assertEqual(self._fill("A"), theme.now(theme.GRID_CRITICAL_BG))
        self.assertEqual(self._fill("B"), theme.now(theme.GRID_HIGHLIGHT_BG))

    def test_the_yellow_follows_the_appearance(self):
        from gantt_app.views import theme
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
