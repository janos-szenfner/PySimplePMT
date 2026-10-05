"""
pytest-bdd tests for the query language behind the Filter window's
Advanced tab.

Run with:
    python3 -m pytest tests/test_filterlang_bdd.py -q

The language is pure - tokenize, parse and compile touch no widget. The
Grid Only section drives the toolbar through stand-ins answering in
pathnames, as Tk does; nothing here opens a window.
"""
from datetime import datetime
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Project, Task
from gantt_app.views import filterlang
from gantt_app.views.filterlang import QueryError
from gantt_app.views.gridfilter import (
    definition_matching_ids, field_name_for_query, matching_task_ids,
    query_to_specs, specs_to_query,
)
from gantt_app.views.toolbar import Toolbar

pytestmark = [
    pytest.mark.filterlang,
]

scenarios("features/filterlang.feature")


def _plan():
    """A plan shaped to answer every clause the language has."""
    base = datetime(2026, 1, 5)
    project = Project(name="Plan")
    project.add_task(Task.create_phase("Phase One", base,
                                       datetime(2026, 1, 30),
                                       task_id="P"))
    project.add_task(Task(id="A", name="Draft artwork",
                          task_type="Task", start_date=base,
                          end_date=datetime(2026, 1, 9), progress=50,
                          parent_task_id="P", label="design"))
    project.add_task(Task(id="B", name="Build chart", task_type="Task",
                          start_date=datetime(2026, 1, 12),
                          end_date=datetime(2026, 1, 16), progress=100,
                          parent_task_id="P", label="code"))
    project.add_task(Task(id="C", name="Clean up", task_type="Task",
                          start_date=datetime(2026, 1, 19),
                          end_date=datetime(2026, 1, 23), progress=0))
    project.add_task(Task.create_milestone("Sign-off",
                                           datetime(2026, 2, 2),
                                           task_id="M"))
    return project


def _ids(project, text):
    return filterlang.query_matching_ids(project, text)


def _listed(text):
    """Turn "P, A, B" into the set the query helpers answer."""
    return {item.strip() for item in text.split(',') if item.strip()}


@pytest.fixture
def ctx():
    return SimpleNamespace(project=None, tree=None, text=None,
                           specs=None, back=None, bar=None,
                           suggestions=None)


# ------------------------------------------------------------------
# fields
# ------------------------------------------------------------------

@then(parsers.parse('the field "{name}" resolves to "{column}"'))
def the_field_resolves(name, column):
    assert filterlang.resolve_field(name) == column


@then(parsers.parse('the field "{name}" resolves to nothing'))
def the_field_resolves_to_nothing(name):
    assert filterlang.resolve_field(name) is None


# ------------------------------------------------------------------
# parsing
# ------------------------------------------------------------------

@then("parsing a blank query gives nothing")
def parsing_a_blank_query():
    assert filterlang.parse_query("") is None
    assert filterlang.parse_query("   ") is None


@when(parsers.parse("'{query}' is parsed"))
@when(parsers.parse('"{query}" is parsed'))
def a_query_is_parsed(ctx, query):
    ctx.tree = filterlang.parse_query(query)


@then(parsers.parse('the condition\'s field is "{field}"'))
def the_conditions_field_is(ctx, field):
    assert ctx.tree[0] == field


@then(parsers.parse('the condition\'s test is "{test}"'))
def the_conditions_test_is(ctx, test):
    assert ctx.tree[1] == test


@then(parsers.parse('the condition\'s values are "{values}"'))
def the_conditions_values_are(ctx, values):
    assert ctx.tree[2] == [v.strip() for v in values.split(',')]


@then("the condition holds no values")
def the_condition_holds_no_values(ctx):
    assert ctx.tree[2] == []


@then(parsers.parse('the condition\'s offset is {offset:d}'))
def the_conditions_offset_is(ctx, offset):
    assert ctx.tree[3] == offset


@then(parsers.parse('the tree\'s root is "{root}"'))
def the_trees_root_is(ctx, root):
    assert ctx.tree[0] == root


@then(parsers.parse('the left branch is "{kind}"'))
def the_left_branch_is(ctx, kind):
    assert ctx.tree[1][0][0] == kind


@then(parsers.parse('the right branch is a condition on "{field}"'))
def the_right_branch_is_a_condition(ctx, field):
    assert ctx.tree[1][1][0] == field


@then(parsers.parse('the second branch is "{kind}"'))
def the_second_branch_is(ctx, kind):
    assert ctx.tree[1][1][0] == kind


@then(parsers.parse("parsing '{query}' fails at {position:d}"))
def parsing_fails_at(query, position):
    with pytest.raises(QueryError) as raised:
        filterlang.parse_query(query)
    assert raised.value.position == position


@then(parsers.parse("parsing '{query}' fails past {position:d}"))
def parsing_fails_past(query, position):
    with pytest.raises(QueryError) as raised:
        filterlang.parse_query(query)
    assert raised.value.position > position


@then(parsers.parse("parsing '{query}' fails"))
def parsing_fails(query):
    with pytest.raises(QueryError):
        filterlang.parse_query(query)


@then(parsers.parse("describing '{query}' is fine"))
def describing_is_fine(query):
    assert filterlang.describe(query) == ''
    assert filterlang.error_position(query) is None


@then(parsers.parse("describing '{query}' reports an error with a "
                    "position"))
def describing_reports_an_error(query):
    assert filterlang.describe(query) != ''
    assert filterlang.error_position(query) is not None


# ------------------------------------------------------------------
# matching
# ------------------------------------------------------------------

@given("the sample plan")
def the_sample_plan(ctx):
    ctx.project = _plan()


@then(parsers.parse('an empty query matches "{ids}"'))
def an_empty_query_matches(ctx, ids):
    assert _ids(ctx.project, "") == _listed(ids)


@then(parsers.parse("the query '{query}' matches \"{ids}\""))
@then(parsers.parse('the query "{query}" matches "{ids}"'))
def the_query_matches(ctx, query, ids):
    assert _ids(ctx.project, query) == _listed(ids)


@then(parsers.parse("the query '{query}' matches nothing"))
@then(parsers.parse('the query "{query}" matches nothing'))
def the_query_matches_nothing(ctx, query):
    assert _ids(ctx.project, query) == set()


@then(parsers.parse("the query '{first}' matches what '{second}' "
                    "matches"))
def the_queries_match_the_same(ctx, first, second):
    assert _ids(ctx.project, first) == _ids(ctx.project, second)


@then(parsers.parse("the definition \"{name}\" with query '{query}' "
                    "matches \"{ids}\""))
def the_definition_matches(ctx, name, query, ids):
    definition = {'name': name, 'query': query}
    assert definition_matching_ids(ctx.project, definition) == \
        _listed(ids)


@then(parsers.parse("the definition \"{name}\" with query '{query}' "
                    "matches nothing"))
def the_definition_matches_nothing(ctx, name, query):
    definition = {'name': name, 'query': query}
    assert definition_matching_ids(ctx.project, definition) == set()


# ------------------------------------------------------------------
# conversions
# ------------------------------------------------------------------

@when(parsers.parse('specs for name "{text}", progress {low:d} to '
                    '{high:d} and status "{status}" render'))
def the_full_specs_render(ctx, text, low, high, status):
    ctx.text = specs_to_query({
        'Task Name': {'text': text},
        'Progress': {'min': low, 'max': high},
        'Status': {'allowed': {status}},
    }, ctx.project)


@when(parsers.parse('specs for start from {day} render'))
def a_one_ended_range_renders(ctx, day):
    start = datetime.strptime(day, "%Y-%m-%d")
    ctx.text = specs_to_query({'Start': {'from': start, 'to': None}})


@when(parsers.parse('specs for type "{types}" render'))
def a_checklist_renders(ctx, types):
    ctx.text = specs_to_query(
        {'Type': {'allowed': _listed(types)}}, ctx.project)


@then(parsers.parse("the rendered query holds '{part}'"))
def the_rendered_query_holds(ctx, part):
    assert part in ctx.text


@then(parsers.parse("the rendered query joins them with '{joiner}'"))
def the_rendered_query_joins(ctx, joiner):
    assert joiner in ctx.text


@then(parsers.parse("the rendered query is '{text}'"))
def the_rendered_query_is(ctx, text):
    assert ctx.text == text


@when(parsers.parse("'{query}' is converted to specs"))
def a_query_is_converted(ctx, query):
    ctx.specs = query_to_specs(query, ctx.project)


@then(parsers.parse('the specs hold name text "{text}"'))
def the_specs_hold_name_text(ctx, text):
    assert ctx.specs['Task Name'] == {'text': text}


@then(parsers.parse('the specs hold progress from {low:d}'))
def the_specs_hold_progress_from(ctx, low):
    assert ctx.specs['Progress'] == {'min': float(low), 'max': None}


@then(parsers.parse('the specs hold type "{type_name}"'))
def the_specs_hold_type(ctx, type_name):
    assert ctx.specs['Type'] == {'allowed': {type_name}}


@then(parsers.parse('the specs hold start from {first} to {second}'))
def the_specs_hold_start_range(ctx, first, second):
    spec = ctx.specs['Start']
    assert spec['from'] == datetime.strptime(first, "%Y-%m-%d")
    assert spec['to'] == datetime.strptime(second, "%Y-%m-%d")


@then(parsers.parse("'{query}' has no basic form"))
def there_is_no_basic_form(ctx, query):
    assert query_to_specs(query, ctx.project) is None


@given(parsers.parse('specs for name "{text}" and progress from '
                     '{low:d}'))
def specs_for_the_round_trip(ctx, text, low):
    ctx.specs = {'Task Name': {'text': text},
                 'Progress': {'min': low, 'max': None}}


@when("the specs render and convert back")
def the_specs_render_and_convert_back(ctx):
    ctx.text = specs_to_query(ctx.specs, ctx.project)
    ctx.back = query_to_specs(ctx.text, ctx.project)


@then("the round trip matches the same rows")
def the_round_trip_matches(ctx):
    assert matching_task_ids(ctx.project, ctx.back) == \
        _ids(ctx.project, ctx.text)


@then(parsers.parse('"{column}" spells "{alias}"'))
def the_column_spells_its_alias(column, alias):
    assert field_name_for_query(column) == alias


# ------------------------------------------------------------------
# persistence
# ------------------------------------------------------------------

@given("the sample plan with a query filter and a rules filter")
def the_plan_with_two_filters(ctx):
    ctx.project = _plan()
    ctx.project.custom_filters = [
        {'name': 'Half done', 'show_in_menu': True,
         'query': 'progress >= 50'},
        {'name': 'Rules', 'show_in_menu': False,
         'rules': [{'join': 'and', 'field': 'Task Name',
                    'test': 'contains', 'value': 'art'}]},
    ]


@given("the sample plan with a filter that has neither rules nor query")
def the_plan_with_an_empty_filter(ctx):
    ctx.project = _plan()
    ctx.project.custom_filters = [{'name': 'Empty', 'rules': None}]


@when("the plan is saved and loaded")
def the_plan_is_saved_and_loaded(ctx):
    ctx.project = Project.from_dict(ctx.project.to_dict())


@then(parsers.parse('"{name}" still carries the query \'{query}\''))
def the_filter_still_carries_the_query(ctx, name, query):
    by_name = {d['name']: d for d in ctx.project.custom_filters}
    assert by_name[name]['query'] == query


@then(parsers.parse('"{name}" still carries the rules with value '
                    '"{value}"'))
def the_filter_still_carries_the_rules(ctx, name, value):
    by_name = {d['name']: d for d in ctx.project.custom_filters}
    assert by_name[name]['rules'][0]['value'] == value


@then("no filters survive")
def no_filters_survive(ctx):
    assert ctx.project.custom_filters == []


# ------------------------------------------------------------------
# suggestions
# ------------------------------------------------------------------

@then(parsers.parse('suggestions at the start offer "{items}"'))
def suggestions_at_the_start(ctx, items):
    found = filterlang.suggestions('', 0, ctx.project)
    for item in _listed(items) | {'('}:
        assert item in found, item


@then(parsers.parse("suggestions after '{typed}' offer \"{items}\""))
def suggestions_after_offer(ctx, typed, items):
    ctx.suggestions = filterlang.suggestions(typed, len(typed),
                                             ctx.project)
    for item in _listed(items):
        assert item in ctx.suggestions, item


@then(parsers.parse('they do not offer "{items}"'))
def they_do_not_offer(ctx, items):
    for item in _listed(items):
        assert item not in ctx.suggestions, item


# ------------------------------------------------------------------
# the View tab's Grid Only button
# ------------------------------------------------------------------

class _Panes:
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


class _Var:
    def __init__(self):
        self.value = False

    def set(self, v):
        self.value = v

    def get(self):
        return self.value


def _shell():
    """A Toolbar without a window: the panes and var it toggles."""
    bar = type('Shell', (), {})()
    bar.content_panes = _Panes()
    bar.task_list = object()
    bar.gantt_chart = object()
    bar.dashboard_frame = object()
    bar.grid_view_only_var = _Var()
    bar.toggle_grid_view_only = (
        Toolbar.toggle_grid_view_only.__get__(bar))
    bar.show_gantt_chart = Toolbar.show_gantt_chart.__get__(bar)
    bar._showing = Toolbar._showing.__get__(bar)
    bar._hide_pane = Toolbar._hide_pane.__get__(bar)
    return bar


@given("a shell with the list and the chart paned")
def a_shell_with_list_and_chart(ctx):
    ctx.bar = _shell()
    ctx.bar.content_panes.add(ctx.bar.task_list)
    ctx.bar.content_panes.add(ctx.bar.gantt_chart)


@given("a shell with the list and the dashboard paned")
def a_shell_with_list_and_dashboard(ctx):
    ctx.bar = _shell()
    ctx.bar.content_panes.add(ctx.bar.task_list)
    ctx.bar.content_panes.add(ctx.bar.dashboard_frame)


@when("Grid Only is pressed")
def grid_only_is_pressed(ctx):
    ctx.bar.toggle_grid_view_only()


@when("Grid Only is pressed twice")
def grid_only_is_pressed_twice(ctx):
    ctx.bar.toggle_grid_view_only()
    ctx.bar.toggle_grid_view_only()


@then("only the task list shows")
def only_the_task_list_shows(ctx):
    assert ctx.bar.content_panes.panes() == [str(ctx.bar.task_list)]


@then("the Grid Only flag is set")
def the_flag_is_set(ctx):
    assert ctx.bar.grid_view_only_var.get()


@then("the Grid Only flag is clear")
def the_flag_is_clear(ctx):
    assert not ctx.bar.grid_view_only_var.get()


@then("the chart shows again")
def the_chart_shows_again(ctx):
    assert str(ctx.bar.gantt_chart) in ctx.bar.content_panes.panes()


@then("the chart is reported showing")
def the_chart_is_reported_showing(ctx):
    assert ctx.bar._showing(ctx.bar.gantt_chart)


@then("a foreign widget is not")
def a_foreign_widget_is_not(ctx):
    assert not ctx.bar._showing(object())
