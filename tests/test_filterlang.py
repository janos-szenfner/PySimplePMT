"""
Tests for the query language behind the Filter window's Advanced tab.

WHY THIS MODULE EXISTS:
======================
The language is pure - tokenize, parse and compile touch no widget - so
every behaviour the window promises can be answered here: what parses,
where a bad query stops, which rows a query matches, and what the
suggestion list offers at the cursor. The window itself is tested where
a display exists, in test_grid_filter.py's dialog tests.
"""

import unittest
from datetime import datetime

from gantt_app import filterlang
from gantt_app.filterlang import QueryError
from gantt_app.models import Project, Task


def _plan():
    """
    A plan shaped to answer every clause the language has.

    Phase P holds design task A (half done, label "design") and code task
    B (done, label "code", no label would test is-empty, so C has none);
    M is a milestone at top level. Dates sit in January 2026 so the date
    comparisons have something to bite on.
    """
    base = datetime(2026, 1, 5)
    project = Project(name="Plan")
    project.add_task(Task.create_phase("Phase One", base,
                                       datetime(2026, 1, 30), task_id="P"))
    project.add_task(Task(id="A", name="Draft artwork", task_type="Task",
                          start_date=base, end_date=datetime(2026, 1, 9),
                          progress=50, parent_task_id="P",
                          label="design"))
    project.add_task(Task(id="B", name="Build chart", task_type="Task",
                          start_date=datetime(2026, 1, 12),
                          end_date=datetime(2026, 1, 16), progress=100,
                          parent_task_id="P", label="code"))
    project.add_task(Task(id="C", name="Clean up", task_type="Task",
                          start_date=datetime(2026, 1, 19),
                          end_date=datetime(2026, 1, 23), progress=0))
    project.add_task(Task.create_milestone("Sign-off", datetime(2026, 2, 2),
                                           task_id="M"))
    return project


def _ids(project, text):
    """What a query matches, as a set of ids."""
    return filterlang.query_matching_ids(project, text)


class TestFields(unittest.TestCase):
    """A field name in a query resolves to a grid column."""

    def test_aliases_resolve(self):
        self.assertEqual(filterlang.resolve_field("name"), "Task Name")
        self.assertEqual(filterlang.resolve_field("status"), "Status")
        self.assertEqual(filterlang.resolve_field("start"), "Start")
        self.assertEqual(filterlang.resolve_field("finish"), "End")
        self.assertEqual(filterlang.resolve_field("calendar"),
                         "Task Calendar")
        self.assertEqual(filterlang.resolve_field("baselineStart"),
                         "Baseline Start")

    def test_column_names_resolve_quoted_or_not(self):
        self.assertEqual(filterlang.resolve_field("Task Name"),
                         "Task Name")
        self.assertEqual(filterlang.resolve_field('"Task Name"'),
                         "Task Name")

    def test_lookup_is_indifferent_to_case(self):
        self.assertEqual(filterlang.resolve_field("NAME"), "Task Name")
        self.assertEqual(filterlang.resolve_field("Progress"),
                         "Progress")

    def test_an_unknown_name_resolves_to_none(self):
        self.assertIsNone(filterlang.resolve_field("wobble"))


class TestParsing(unittest.TestCase):
    """The grammar: what parses, and what stops with a position."""

    def test_empty_query_parses_to_none(self):
        self.assertIsNone(filterlang.parse_query(""))
        self.assertIsNone(filterlang.parse_query("   "))

    def test_a_condition_is_a_four_tuple(self):
        node = filterlang.parse_query('name ~ "art"')
        self.assertEqual(node, ("Task Name", "contains", ["art"], 0))

    def test_and_binds_tighter_than_or(self):
        # status = X and type = Task or milestone = Yes parses as
        # (status = X and type = Task) or (milestone = Yes)
        tree = filterlang.parse_query(
            'status = Done and type = Task or milestone = Yes')
        self.assertEqual(tree[0], 'or')
        left, right = tree[1]
        self.assertEqual(left[0], 'and')
        self.assertEqual(right[0], 'Milestone')

    def test_brackets_override_precedence(self):
        tree = filterlang.parse_query(
            'status = Done and (type = Task or milestone = Yes)')
        self.assertEqual(tree[0], 'and')
        self.assertEqual(tree[1][1][0], 'or')

    def test_not_negates_a_condition(self):
        tree = filterlang.parse_query('not status = Done')
        self.assertEqual(tree[0], 'not')

    def test_an_in_list_reads_its_values(self):
        tree = filterlang.parse_query('type in (Task, Milestone)')
        self.assertEqual(tree[1], 'in')
        self.assertEqual(tree[2], ['Task', 'Milestone'])

    def test_within_reads_two_values(self):
        tree = filterlang.parse_query(
            'start within 2026-01-01, 2026-02-01')
        self.assertEqual(tree[1], 'within')
        self.assertEqual(tree[2], ['2026-01-01', '2026-02-01'])

    def test_is_empty_reads_no_value(self):
        tree = filterlang.parse_query('label is empty')
        self.assertEqual(tree[1], 'is_empty')
        self.assertEqual(tree[2], [])

    def test_an_unclosed_quote_is_an_error_with_a_position(self):
        with self.assertRaises(QueryError) as raised:
            filterlang.parse_query('name ~ "art')
        self.assertEqual(raised.exception.position, 7)

    def test_an_unknown_field_is_an_error_with_a_position(self):
        with self.assertRaises(QueryError) as raised:
            filterlang.parse_query('wobble = 1')
        self.assertEqual(raised.exception.position, 0)

    def test_a_stray_token_after_a_condition_is_an_error(self):
        with self.assertRaises(QueryError) as raised:
            filterlang.parse_query('progress = 50 nonsense')
        self.assertGreater(raised.exception.position, 0)

    def test_an_operator_a_field_cannot_take_is_an_error(self):
        with self.assertRaises(QueryError):
            filterlang.parse_query('start ~ "x"')

    def test_describe_and_error_position_answer_the_window(self):
        self.assertEqual(filterlang.describe('name ~ "art"'), '')
        self.assertIsNone(filterlang.error_position('name ~ "art"'))
        self.assertNotEqual(filterlang.describe('name ~'), '')
        self.assertIsNotNone(filterlang.error_position('name ~'))


class TestMatching(unittest.TestCase):
    """What a parsed query matches against a plan."""

    def setUp(self):
        self.project = _plan()

    def test_empty_query_matches_everything(self):
        self.assertEqual(_ids(self.project, ""), {"P", "A", "B", "C", "M"})

    def test_contains_matches_a_substring_without_case(self):
        self.assertEqual(_ids(self.project, 'name ~ "art"'),
                         {"A", "B"})  # draft ARTwork and build chART

    def test_equals_matches_wildcards(self):
        self.assertEqual(_ids(self.project, 'name = "Draft*"'), {"A"})
        self.assertEqual(_ids(self.project, 'name = "B???? chart"'),
                         {"B"})

    def test_not_contains_rules_out(self):
        self.assertEqual(_ids(self.project, 'name !~ "art"'),
                         {"P", "C", "M"})

    def test_a_number_compares(self):
        self.assertEqual(_ids(self.project, 'progress >= 50'), {"A", "B"})
        # Phases and milestones report 0 progress, so they match too.
        self.assertEqual(_ids(self.project, 'progress < 50'),
                         {"P", "C", "M"})

    def test_a_number_range(self):
        self.assertEqual(
            _ids(self.project, 'progress within 1, 99'), {"A"})

    def test_a_date_compares_in_every_spelling(self):
        self.assertEqual(_ids(self.project, 'start = 2026-01-05'), {"P", "A"})
        self.assertEqual(_ids(self.project, 'start = 2026.01.12'), {"B"})
        self.assertEqual(_ids(self.project, 'start = 2026/01/19'), {"C"})

    def test_a_date_range(self):
        self.assertEqual(
            _ids(self.project,
                 'start within 2026-01-10, 2026-01-31'), {"B", "C"})

    def test_a_fixed_set_matches_without_case(self):
        self.assertEqual(_ids(self.project, 'type = task'),
                         {"A", "B", "C"})

    def test_an_in_list_matches_the_set(self):
        self.assertEqual(_ids(self.project, 'type in (Task, Milestone)'),
                         {"A", "B", "C", "M"})

    def test_not_in_rules_the_set_out(self):
        self.assertEqual(_ids(self.project, 'type not in (Task)'),
                         {"P", "M"})

    def test_is_empty_and_is_not_empty(self):
        self.assertEqual(_ids(self.project, 'label is empty'),
                         {"P", "C", "M"})
        self.assertEqual(_ids(self.project, 'label is not empty'),
                         {"A", "B"})

    def test_and_or_and_not_compose(self):
        self.assertEqual(
            _ids(self.project, 'type = Task and progress < 50'), {"C"})
        self.assertEqual(
            _ids(self.project,
                 'type = Task and progress < 50 or milestone = Yes'),
            {"C", "M"})
        self.assertEqual(
            _ids(self.project, 'not type = Task'), {"P", "M"})

    def test_brackets_group(self):
        self.assertEqual(
            _ids(self.project,
                 'type = Task and (progress = 0 or progress = 100)'),
            {"B", "C"})

    def test_a_value_that_does_not_parse_matches_nothing(self):
        self.assertEqual(_ids(self.project, 'progress >= banana'),
                         set())

    def test_a_query_definition_matches_like_a_rules_one(self):
        from gantt_app.views.gridfilter import definition_matching_ids
        self.assertEqual(
            definition_matching_ids(
                self.project, {'name': 'Q', 'query': 'progress >= 50'}),
            {"A", "B"})

    def test_a_broken_saved_query_matches_nothing(self):
        from gantt_app.views.gridfilter import definition_matching_ids
        self.assertEqual(
            definition_matching_ids(
                self.project, {'name': 'Q', 'query': 'progress ~'}),
            set())


class TestConversions(unittest.TestCase):
    """The Basic tab's specs and a query say the same thing both ways."""

    def setUp(self):
        self.project = _plan()

    def test_specs_render_as_a_query(self):
        from gantt_app.views.gridfilter import specs_to_query
        text = specs_to_query({
            'Task Name': {'text': 'art'},
            'Progress': {'min': 10, 'max': 80},
            'Status': {'allowed': {'In Progress'}},
        }, self.project)
        self.assertIn('name ~ "art"', text)
        self.assertIn('progress within 10, 80', text)
        self.assertIn('status = "In Progress"', text)
        self.assertIn(' and ', text)

    def test_a_one_ended_range_renders_as_a_comparison(self):
        from gantt_app.views.gridfilter import specs_to_query
        self.assertEqual(
            specs_to_query({'Start': {'from': datetime(2026, 1, 5),
                                      'to': None}}),
            'start >= 2026-01-05')

    def test_a_checklist_renders_as_an_in_list(self):
        from gantt_app.views.gridfilter import specs_to_query
        text = specs_to_query(
            {'Type': {'allowed': {'Task', 'Milestone'}}}, self.project)
        self.assertEqual(text, 'type in ("Milestone", "Task")')

    def test_a_flat_query_converts_back(self):
        from gantt_app.views.gridfilter import query_to_specs
        specs = query_to_specs(
            'name ~ "art" and progress >= 50 and type = "Task"',
            self.project)
        self.assertEqual(specs['Task Name'], {'text': 'art'})
        self.assertEqual(specs['Progress'], {'min': 50.0, 'max': None})
        self.assertEqual(specs['Type'], {'allowed': {'Task'}})

    def test_a_within_converts_to_both_ends(self):
        from gantt_app.views.gridfilter import query_to_specs
        specs = query_to_specs(
            'start within 2026-01-01, 2026-02-01', self.project)
        self.assertEqual(specs['Start']['from'], datetime(2026, 1, 1))
        self.assertEqual(specs['Start']['to'], datetime(2026, 2, 1))

    def test_an_or_query_has_no_basic_form(self):
        from gantt_app.views.gridfilter import query_to_specs
        self.assertIsNone(query_to_specs(
            'progress < 50 or type = Milestone', self.project))
        self.assertIsNone(query_to_specs(
            'not status = Done', self.project))
        self.assertIsNone(query_to_specs(
            'type = Task and (progress = 0 or progress = 100)',
            self.project))

    def test_a_round_trip_matches_the_same_rows(self):
        from gantt_app.views.gridfilter import (
            matching_task_ids, query_to_specs, specs_to_query)
        specs = {'Task Name': {'text': 'art'},
                 'Progress': {'min': 50, 'max': None}}
        text = specs_to_query(specs, self.project)
        back = query_to_specs(text, self.project)
        self.assertEqual(
            matching_task_ids(self.project, back),
            _ids(self.project, text))

    def test_a_column_name_spells_its_shortest_alias(self):
        from gantt_app.views.gridfilter import field_name_for_query
        self.assertEqual(field_name_for_query('Task Name'), 'name')
        self.assertEqual(field_name_for_query('Baseline Start'),
                         'baselinestart')


class TestPersistence(unittest.TestCase):
    """A query filter lives in the file like a rules one does."""

    def test_a_query_definition_round_trips(self):
        project = _plan()
        project.custom_filters = [
            {'name': 'Half done', 'show_in_menu': True,
             'query': 'progress >= 50'},
            {'name': 'Rules', 'show_in_menu': False,
             'rules': [{'join': 'and', 'field': 'Task Name',
                        'test': 'contains', 'value': 'art'}]},
        ]
        loaded = Project.from_dict(project.to_dict())
        by_name = {d['name']: d for d in loaded.custom_filters}
        self.assertEqual(by_name['Half done']['query'], 'progress >= 50')
        self.assertEqual(by_name['Rules']['rules'][0]['value'], 'art')

    def test_a_definition_with_neither_rules_nor_query_is_dropped(self):
        project = _plan()
        project.custom_filters = [{'name': 'Empty', 'rules': None}]
        loaded = Project.from_dict(project.to_dict())
        self.assertEqual(loaded.custom_filters, [])


class TestSuggestions(unittest.TestCase):
    """What the box may be offered next at each cursor spot."""

    def setUp(self):
        self.project = _plan()

    def test_an_empty_box_offers_fields(self):
        found = filterlang.suggestions('', 0, self.project)
        self.assertIn('name', found)
        self.assertIn('status', found)
        self.assertIn('not', found)
        self.assertIn('(', found)

    def test_after_a_field_come_its_operators(self):
        found = filterlang.suggestions('progress ', 9, self.project)
        self.assertIn('>=', found)
        self.assertIn('within', found)
        self.assertNotIn('~', found)   # a number field has no contains

    def test_after_a_comparison_come_and_or(self):
        found = filterlang.suggestions('progress = 50 ', 14,
                                       self.project)
        self.assertIn('and', found)
        self.assertIn('or', found)

    def test_after_equals_on_a_fixed_set_come_its_values(self):
        found = filterlang.suggestions('type = ', 7, self.project)
        self.assertIn('Task', found)
        self.assertIn('Milestone', found)

    def test_inside_an_in_list_come_more_values(self):
        found = filterlang.suggestions('type in (Task, ', 15,
                                       self.project)
        self.assertIn('Milestone', found)
        self.assertIn(')', found)


class TestGridOnly(unittest.TestCase):
    """The View tab's Grid Only button - the bug it fixed and its state."""

    def _bar(self):
        """A Toolbar without a window: the panes and var it toggles."""
        from gantt_app.views.toolbar import Toolbar

        class Panes:
            """A stand-in paned window answering in pathnames, as Tk does."""
            def __init__(self):
                self.contents = []
            def panes(self):
                return [str(w) for w in self.contents]
            def add(self, widget, weight=None):
                if widget not in self.contents:
                    self.contents.append(widget)
            def forget(self, widget):
                if widget in self.contents:
                    self.contents.remove(widget)

        class Var:
            def __init__(self):
                self.value = False
            def set(self, v):
                self.value = v
            def get(self):
                return self.value

        bar = type('Shell', (), {})()
        bar.content_panes = Panes()
        bar.task_list = object()
        bar.gantt_chart = object()
        bar.dashboard_frame = object()
        bar.grid_view_only_var = Var()
        bar.content_panes.add(bar.task_list)
        bar.content_panes.add(bar.gantt_chart)
        bar.toggle_grid_view_only = (
            Toolbar.toggle_grid_view_only.__get__(bar))
        bar.show_gantt_chart = Toolbar.show_gantt_chart.__get__(bar)
        bar._showing = Toolbar._showing.__get__(bar)
        bar._hide_pane = Toolbar._hide_pane.__get__(bar)
        return bar

    def test_grid_only_leaves_only_the_task_list(self):
        bar = self._bar()
        bar.toggle_grid_view_only()
        self.assertEqual(bar.content_panes.panes(), [str(bar.task_list)])
        self.assertTrue(bar.grid_view_only_var.get())

    def test_grid_only_hides_the_dashboard_too(self):
        bar = self._bar()
        bar.content_panes.forget(bar.gantt_chart)
        bar.content_panes.add(bar.dashboard_frame)
        bar.toggle_grid_view_only()
        self.assertEqual(bar.content_panes.panes(), [str(bar.task_list)])

    def test_a_second_press_puts_the_chart_back(self):
        bar = self._bar()
        bar.toggle_grid_view_only()
        bar.toggle_grid_view_only()
        self.assertIn(str(bar.gantt_chart), bar.content_panes.panes())
        self.assertFalse(bar.grid_view_only_var.get())

    def test_the_pane_check_reads_pathnames_not_widgets(self):
        # The original defect: panes() answers strings, so a widget never
        # compared equal and the pane was never found to remove.
        bar = self._bar()
        self.assertTrue(bar._showing(bar.gantt_chart))
        self.assertFalse(bar._showing(object()))


if __name__ == '__main__':
    unittest.main()
