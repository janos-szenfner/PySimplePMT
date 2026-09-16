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

from gantt_app.core.models import Project, Task
from gantt_app.views.gridfilter import (
    _with_ancestors, choice_values, column_value,
    filter_is_active, definition_matching_ids, definition_visible_ids,
    filtered_task_ids, matching_task_ids, row_matches, rule_matches,
    specs_to_rules)


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

    def apply_grid_filters(self, filters=None, variances=None,
                           definition=None):
        if definition is not None:
            self._filter_visible = definition_visible_ids(
                self.project, definition, variances)
            self._filter_matches = definition_matching_ids(
                self.project, definition, variances)
        else:
            self._filter_visible = filtered_task_ids(
                self.project, filters or {}, variances)
            self._filter_matches = matching_task_ids(
                self.project, filters or {}, variances)
        return len(self._filter_matches), len(self.project.tasks)

    def apply_matching_ids(self, matches):
        self._filter_matches = set(matches)
        self._filter_visible = _with_ancestors(self.project,
                                               self._filter_matches)
        return len(self._filter_matches), len(self.project.tasks)

    def clear_grid_filters(self):
        self._filter_visible = None
        self._filter_matches = set()

    def clear_highlight(self):
        pass

    def show_highlighted_rows(self, ids):
        return len(list(ids))

    def grid_filters_active(self):
        return self._filter_visible is not None


def _payload(specs=None, query='', mode='basic'):
    """What the tabbed filter window's Apply sends the toolbar."""
    return {'mode': mode, 'specs': specs or {}, 'query': query}


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
        self._apply_query_filter = (
            Toolbar._apply_query_filter.__get__(self))
        self.clear_grid_filter = Toolbar.clear_grid_filter.__get__(self)
        self.apply_named_filter = (
            Toolbar.apply_named_filter.__get__(self))
        self._find_custom_filter = (
            Toolbar._find_custom_filter.__get__(self))
        self._more_filters_delete = (
            Toolbar._more_filters_delete.__get__(self))
        self.clear_highlight = Toolbar.clear_highlight.__get__(self)
        self._refresh_toggle_states = (
            Toolbar._refresh_toggle_states.__get__(self))
        self._report = lambda _m: None
        self.after_idle = lambda fn: fn()
        self.on_project_changed = None
        self._active_named_filter = None
        self._active_highlight = None
        self._active_query = None
        self._query_history = []


class TestTheHandlers(unittest.TestCase):
    """What Apply and Clear do to the list through the toolbar."""

    def setUp(self):
        self.project = _plan()
        self.bar = _ToolbarShell(self.project)

    def test_apply_hides_the_rows_no_filter_passes(self):
        self.bar._apply_grid_filters(
            _payload({'Task Name': {'text': 'chart'}}))
        self.assertEqual(self.bar.task_list._filter_visible, {"B", "P"})

    def test_the_specs_are_kept_for_the_next_opening(self):
        self.bar._apply_grid_filters(
            _payload({'Task Name': {'text': 'chart'}}))
        self.assertEqual(self.bar._grid_filters,
                         {'Task Name': {'text': 'chart'}})

    def test_clear_puts_every_row_back(self):
        self.bar._apply_grid_filters(
            _payload({'Task Name': {'text': 'chart'}}))
        self.bar.clear_grid_filter()
        self.assertIsNone(self.bar.task_list._filter_visible)
        self.assertEqual(self.bar._grid_filters, {})

    def test_apply_with_nothing_set_is_everything(self):
        self.bar._apply_grid_filters(_payload())
        self.assertIsNone(self.bar.task_list._filter_visible)

    def test_an_advanced_payload_applies_the_query(self):
        self.bar._apply_grid_filters(
            _payload(query='type = Task and progress >= 50',
                     mode='advanced'))
        self.assertEqual(self.bar.task_list._filter_matches, {"A", "B"})
        self.assertEqual(self.bar._active_query,
                         'type = Task and progress >= 50')

    def test_a_query_remembers_itself_in_the_history(self):
        self.bar._apply_grid_filters(
            _payload(query='milestone = Yes', mode='advanced'))
        self.bar._apply_grid_filters(
            _payload(query='progress = 100', mode='advanced'))
        self.assertEqual(self.bar._query_history,
                         ['progress = 100', 'milestone = Yes'])

    def test_an_unparseable_query_applies_nothing(self):
        self.bar._apply_grid_filters(
            _payload(query='progress ~', mode='advanced'))
        self.assertIsNone(self.bar.task_list._filter_visible)
        self.assertIsNone(self.bar._active_query)

    def test_clear_drops_the_query_too(self):
        self.bar._apply_grid_filters(
            _payload(query='milestone = Yes', mode='advanced'))
        self.bar.clear_grid_filter()
        self.assertIsNone(self.bar.task_list._filter_visible)
        self.assertIsNone(self.bar._active_query)

    def test_a_named_filter_rules_the_grid(self):
        self.project.custom_filters = [{
            'name': 'Only milestones', 'show_in_menu': True,
            'rules': [{'join': 'and', 'field': 'Milestone',
                       'test': 'equals', 'value': 'Yes'}]}]
        self.bar.apply_named_filter('Only milestones')
        self.assertEqual(self.bar.task_list._filter_matches, {"M"})
        self.assertEqual(self.bar._active_named_filter,
                         'Only milestones')

    def test_repeating_the_named_filter_turns_it_off(self):
        self.project.custom_filters = [{
            'name': 'Only milestones', 'show_in_menu': True,
            'rules': [{'join': 'and', 'field': 'Milestone',
                       'test': 'equals', 'value': 'Yes'}]}]
        self.bar.apply_named_filter('Only milestones')
        self.bar.apply_named_filter('Only milestones')
        self.assertIsNone(self.bar.task_list._filter_visible)
        self.assertIsNone(self.bar._active_named_filter)

    def test_an_unknown_name_is_a_no_op(self):
        self.bar.apply_named_filter('never saved')
        self.assertIsNone(self.bar.task_list._filter_visible)

    def test_deleting_the_active_named_filter_puts_rows_back(self):
        self.project.custom_filters = [{
            'name': 'Only milestones', 'show_in_menu': True,
            'rules': [{'join': 'and', 'field': 'Milestone',
                       'test': 'equals', 'value': 'Yes'}]}]
        self.bar.apply_named_filter('Only milestones')
        self.bar._more_filters_delete('Only milestones')
        self.assertEqual(self.project.custom_filters, [])
        self.assertIsNone(self.bar.task_list._filter_visible)


class TestTheRules(unittest.TestCase):
    """One rule of a named filter, for each test the builder offers."""

    def setUp(self):
        self.project = _plan()
        self.a = self.project.get_task_by_id("A")

    def _passes(self, field, test, value, value2=None, task=None):
        rule = {'field': field, 'test': test, 'value': value}
        if value2 is not None:
            rule['value2'] = value2
        return rule_matches(task or self.a, rule, self.project)

    def test_text_contains(self):
        self.assertTrue(self._passes('Task Name', 'contains', 'art'))
        self.assertFalse(self._passes('Task Name', 'does_not_contain',
                                      'art'))

    def test_text_equals_takes_wildcards(self):
        """MS's * and ? on equality, over the name."""
        self.assertTrue(self._passes('Task Name', 'equals', 'Draft*'))
        self.assertTrue(self._passes('Task Name', 'equals',
                                     'Draft artwor?'))
        self.assertFalse(self._passes('Task Name', 'equals', 'Draft'))
        self.assertTrue(self._passes('Task Name', 'does_not_equal',
                                     'Draft'))

    def test_text_equals_is_case_insensitive(self):
        self.assertTrue(self._passes('Task Name', 'equals',
                                     'draft artwork'))

    def test_number_tests(self):
        self.assertTrue(self._passes('Progress', 'equals', '50'))
        self.assertTrue(self._passes('Progress', 'lt', '60'))
        self.assertTrue(self._passes('Progress', 'gte', '50'))
        self.assertFalse(self._passes('Progress', 'gt', '50'))
        self.assertTrue(self._passes('Progress', 'within', '40', '60'))
        self.assertFalse(self._passes('Progress', 'not_within', '40', '60'))

    def test_an_unparseable_number_asks_nothing(self):
        self.assertFalse(self._passes('Progress', 'equals', 'lots'))

    def test_date_tests(self):
        self.assertTrue(self._passes('Start', 'equals', '2026-01-05'))
        self.assertTrue(self._passes('Start', 'lt', '2026-01-10'))
        self.assertTrue(self._passes('Start', 'gte', '2026-01-05'))
        self.assertTrue(self._passes('Start', 'within',
                                     '2026-01-01', '2026-01-10'))
        self.assertFalse(self._passes('Start', 'within',
                                      '2026-01-06', '2026-01-10'))

    def test_date_values_take_dots(self):
        """The request's own shape, 2026.09.01, parses in a rule too."""
        self.assertTrue(self._passes('Start', 'gte', '2026.01.01'))

    def test_an_empty_cell_passes_no_number_or_date_rule(self):
        task = self.project.get_task_by_id("B")
        task.start_date = None
        self.assertFalse(self._passes('Start', 'gte', '2026-01-01',
                                      task=task))

    def test_choice_equals_and_set(self):
        self.assertTrue(self._passes('Type', 'equals', 'Task'))
        self.assertFalse(self._passes('Type', 'equals', 'Phase'))
        self.assertTrue(self._passes('Type', 'is_one_of',
                                     ['Phase', 'Task']))
        self.assertFalse(self._passes('Type', 'is_one_of', ['Phase']))
        self.assertTrue(self._passes('Type', 'not_one_of', ['Phase']))

    def test_a_rule_naming_nothing_known_matches_nothing(self):
        self.assertFalse(self._passes('No Such Field', 'equals', 'x'))
        self.assertFalse(self._passes('Task Name', 'explodes', 'x'))


class TestADefinition(unittest.TestCase):
    """The whole saved filter: how its rows chain and what it leaves."""

    def setUp(self):
        self.project = _plan()

    def test_and_rows_must_all_pass(self):
        definition = {'name': 'd', 'rules': [
            {'join': 'and', 'field': 'Type', 'test': 'equals',
             'value': 'Task'},
            {'join': 'and', 'field': 'Progress', 'test': 'gte',
             'value': '60'}]}
        self.assertEqual(definition_matching_ids(self.project, definition),
                         {"B"})

    def test_or_opens_a_second_group(self):
        """'A and B or C' means (A and B) or C, the way MS reads it."""
        definition = {'name': 'd', 'rules': [
            {'join': 'and', 'field': 'Type', 'test': 'equals',
             'value': 'Task'},
            {'join': 'and', 'field': 'Progress', 'test': 'gte',
             'value': '60'},
            {'join': 'or', 'field': 'Milestone', 'test': 'equals',
             'value': 'Yes'}]}
        self.assertEqual(definition_matching_ids(self.project, definition),
                         {"B", "M"})

    def test_the_first_rows_join_is_read_but_ignored(self):
        definition = {'name': 'd', 'rules': [
            {'join': 'or', 'field': 'Type', 'test': 'equals',
             'value': 'Task'},
            {'join': 'and', 'field': 'Progress', 'test': 'gte',
             'value': '60'}]}
        self.assertEqual(definition_matching_ids(self.project, definition),
                         {"B"})

    def test_no_rules_matches_nothing_and_filters_nothing(self):
        empty = {'name': 'd', 'rules': []}
        self.assertEqual(definition_matching_ids(self.project, empty),
                         set())
        self.assertIsNone(definition_visible_ids(self.project, empty))

    def test_matches_keep_their_ancestors(self):
        definition = {'name': 'd', 'rules': [
            {'join': 'and', 'field': 'Task Name', 'test': 'contains',
             'value': 'chart'}]}
        self.assertEqual(definition_visible_ids(self.project, definition),
                         {"B", "P"})


class TestSpecsToRules(unittest.TestCase):
    """What Save As makes of the column window's specs."""

    def setUp(self):
        self.project = _plan()

    def test_a_text_spec_becomes_contains(self):
        rules = specs_to_rules({'Task Name': {'text': 'art'}},
                               self.project)
        self.assertEqual(rules, [{'join': 'and', 'field': 'Task Name',
                                  'test': 'contains', 'value': 'art'}])

    def test_a_two_ended_range_becomes_within(self):
        rules = specs_to_rules(
            {'Progress': {'min': 40, 'max': 60}}, self.project)
        self.assertEqual(rules[0]['test'], 'within')
        self.assertEqual(rules[0]['value'], '40')
        self.assertEqual(rules[0]['value2'], '60')

    def test_a_one_ended_range_keeps_its_end(self):
        rules = specs_to_rules({'Progress': {'min': 40, 'max': None}},
                               self.project)
        self.assertEqual(rules[0]['test'], 'gte')

    def test_a_checklist_becomes_one_set_rule(self):
        """Ticking Task and Milestone saves 'Type is one of ...' - one
        rule, so two checklists on different columns still AND."""
        rules = specs_to_rules(
            {'Type': {'allowed': {'Task', 'Milestone'}}}, self.project)
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]['test'], 'is_one_of')
        self.assertEqual(rules[0]['value'], ['Milestone', 'Task'])

    def test_specs_that_ask_nothing_save_nothing(self):
        self.assertEqual(specs_to_rules({'Task Name': {'text': 'ar'}},
                                        self.project), [])


class TestSavedInThePlan(unittest.TestCase):
    """The file keeps what the filters dialog saved."""

    def test_a_saved_filter_survives_the_round_trip(self):
        project = _plan()
        project.custom_filters = [{
            'name': 'Late tasks', 'show_in_menu': True,
            'rules': [{'join': 'and', 'field': 'Start', 'test': 'lt',
                       'value': '2026-09-01'}]}]
        revived = Project.from_dict(project.to_dict())
        self.assertEqual(revived.custom_filters[0]['name'], 'Late tasks')
        self.assertEqual(revived.custom_filters[0]['rules'][0]['value'],
                         '2026-09-01')
        self.assertTrue(revived.custom_filters[0]['show_in_menu'])

    def test_a_plan_without_filters_reads_empty(self):
        project = _plan()
        revived = Project.from_dict(project.to_dict())
        self.assertEqual(revived.custom_filters, [])

    def test_a_damaged_entry_is_dropped_not_raised(self):
        data = _plan().to_dict()
        data['custom_filters'] = [{'rules': []}, 'not a dict',
                                  {'name': 'ok', 'rules': []}]
        revived = Project.from_dict(data)
        self.assertEqual([d['name'] for d in revived.custom_filters],
                         ['ok'])


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
class TestTheFilterWindow(unittest.TestCase):
    """The tabbed window itself: its tabs, its verdict, its payload."""

    def setUp(self):
        import customtkinter as ctk
        from gantt_app.views.gridfilter import GridFilterDialog

        self.ctk = ctk
        self.opening_mode = str(ctk.get_appearance_mode())
        ctk.set_appearance_mode('light')
        self.root = ctk.CTk()
        self.root.withdraw()

        self.project = _plan()
        self.applied = []
        # The values callback is the same source the window's checklists
        # and the active check share - choice_values over the plan.
        self.window = GridFilterDialog(
            self.root, ['Task Name', 'Progress', 'Type'],
            current={},
            values=lambda c: choice_values(self.project, c),
            on_apply=self.applied.append,
            on_clear=lambda: None,
            on_save_as=lambda _p: None,
            project=self.project,
            history=['milestone = Yes'])
        self.root.update_idletasks()

    def tearDown(self):
        try:
            self.window.destroy()
            self.root.destroy()
        except Exception:
            pass
        try:
            self.ctk.set_appearance_mode(self.opening_mode)
        except Exception:
            pass

    def test_the_window_has_a_basic_and_an_advanced_tab(self):
        self.assertEqual(self.window._active_tab(), 'basic')
        self.window._set_tab("Advanced")
        self.assertEqual(self.window._active_tab(), 'advanced')

    def test_a_valid_query_reports_its_matches(self):
        self.window._set_tab("Advanced")
        self.window._query_entry.insert(0, 'progress >= 50')
        self.window._query_changed()
        self.assertIn('2 row', self.window._query_status.cget('text'))

    def test_a_bad_query_reports_where_it_stopped(self):
        self.window._set_tab("Advanced")
        self.window._query_entry.insert(0, 'progress ~')
        self.window._query_changed()
        self.assertIn('✗', self.window._query_status.cget('text'))
        self.assertIn('position', self.window._query_status.cget('text'))

    def test_apply_sends_the_live_tab(self):
        self.window._set_tab("Advanced")
        self.window._query_entry.insert(0, 'milestone = Yes')
        self.window._apply()
        self.assertEqual(self.applied[-1]['mode'], 'advanced')
        self.assertEqual(self.applied[-1]['query'], 'milestone = Yes')

    def test_basic_apply_sends_the_specs(self):
        self.window._apply()
        self.assertEqual(self.applied[-1]['mode'], 'basic')
        self.assertIn('Task Name', self.applied[-1]['specs'])

    def test_basic_specs_render_as_a_query_on_the_tab_switch(self):
        control = self.window._controls['Task Name']
        control[1].insert(0, 'art')
        self.window._set_tab("Advanced")
        self.assertIn('name ~ "art"', self.window._query_entry.get())


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestTheBuilder(unittest.TestCase):
    """The definition window: rows collect into the saved shape."""

    def setUp(self):
        import customtkinter as ctk
        self.ctk = ctk
        self.opening_mode = str(ctk.get_appearance_mode())
        ctk.set_appearance_mode('light')
        self.root = ctk.CTk()
        self.root.withdraw()
        self.project = _plan()

    def tearDown(self):
        try:
            self.root.destroy()
        except Exception:
            pass
        try:
            self.ctk.set_appearance_mode(self.opening_mode)
        except Exception:
            pass

    def _open(self, definition=None):
        from gantt_app.views.gridfilter import FilterDefinitionDialog
        self.collected = []
        return FilterDefinitionDialog(
            self.root,
            values_for=lambda c: choice_values(self.project, c),
            definition=definition,
            on_save=self.collected.append)

    def test_a_blank_window_opens_with_one_row(self):
        dialog = self._open()
        self.assertEqual(len(dialog._rows), 1)
        dialog.destroy()

    def test_save_refuses_a_nameless_filter(self):
        dialog = self._open()
        dialog._rows[0]['value'].insert(0, 'art')
        dialog._save()
        self.assertEqual(self.collected, [])
        self.assertTrue(dialog._warning.cget('text'))
        dialog.destroy()

    def test_save_refuses_a_ruleless_filter(self):
        dialog = self._open()
        dialog._name.insert(0, 'Named')
        dialog._save()
        self.assertEqual(self.collected, [])
        dialog.destroy()

    def test_a_filled_row_collects(self):
        dialog = self._open()
        dialog._name.insert(0, 'Artwork')
        dialog._rows[0]['field_var'].set('Task Name')
        dialog._rows[0]['test_var'].set('contains')
        dialog._rows[0]['value'].insert(0, 'art')
        dialog._save()
        self.assertEqual(len(self.collected), 1)
        saved = self.collected[0]
        self.assertEqual(saved['name'], 'Artwork')
        self.assertEqual(saved['rules'][0]['field'], 'Task Name')
        self.assertEqual(saved['rules'][0]['test'], 'contains')
        self.assertEqual(saved['rules'][0]['value'], 'art')
        self.assertFalse(dialog.winfo_exists())

    def test_an_edited_definition_refills_its_rows(self):
        definition = {'name': 'Old', 'show_in_menu': False, 'rules': [
            {'join': 'and', 'field': 'Progress', 'test': 'gte',
             'value': '40'},
            {'join': 'or', 'field': 'Milestone', 'test': 'equals',
             'value': 'Yes'}]}
        dialog = self._open(definition)
        self.assertEqual(len(dialog._rows), 2)
        self.assertEqual(dialog._name.get(), 'Old')
        self.assertFalse(dialog._show_in_menu.get())
        self.assertEqual(dialog._rows[1]['join_var'].get(), 'Or')
        dialog._save()
        self.assertEqual(len(self.collected[0]['rules']), 2)
        dialog.destroy()

    def test_dropping_a_row_keeps_the_rest(self):
        dialog = self._open()
        dialog._add_row()
        dialog._drop_row(dialog._rows[0])
        self.assertEqual(len(dialog._rows), 1)
        dialog.destroy()


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestTheManager(unittest.TestCase):
    """The More Filters window lists and dispatches."""

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

    def test_every_entry_lists_and_the_buttons_dispatch(self):
        from gantt_app.views.gridfilter import MoreFiltersDialog
        calls = []
        dialog = MoreFiltersDialog(
            self.root,
            [('incomplete', 'Incomplete Tasks', 'standard'),
             ('mine', 'Mine', 'custom')],
            callbacks={'apply': lambda k: calls.append(('apply', k)),
                       'edit': lambda k: calls.append(('edit', k)),
                       'new': lambda: calls.append(('new',))})
        dialog._select('mine')
        dialog._run('apply')
        dialog._run('edit')
        dialog._run('new')
        self.assertEqual(calls, [('apply', 'mine'), ('edit', 'mine'),
                                 ('new',)])
        dialog.destroy()

    def test_standard_entries_cannot_be_edited_or_deleted(self):
        from gantt_app.views.gridfilter import MoreFiltersDialog
        calls = []
        dialog = MoreFiltersDialog(
            self.root, [('incomplete', 'Incomplete Tasks', 'standard')],
            callbacks={'edit': lambda k: calls.append(k),
                       'delete': lambda k: calls.append(k)})
        dialog._select('incomplete')
        dialog._run('edit')
        dialog._run('delete')
        self.assertEqual(calls, [])
        dialog.destroy()


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
