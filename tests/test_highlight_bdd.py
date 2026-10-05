"""
The View tab's highlight filters - the selectors and the menu.

The scenarios live in features/highlight.feature. They pin down which
rows each standard filter picks, the one-at-a-time toggle, the gallery's
sections, the paint following edits, copying built-ins into customs, and
the fields the custom-filter dialog offers.

The painting itself is a Treeview and needs a display; it stays in
tests/test_highlight.py.
"""

from datetime import datetime
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Project, Task


scenarios('features/highlight.feature')


@pytest.fixture
def ctx():
    return SimpleNamespace(project=None, bar=None)


def _d(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%d")


def _ids(text: str):
    """An "A, B, C" cell as a set of task ids."""
    return {piece.strip() for piece in text.split(',')}


def _plan() -> Project:
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


# ---- the plan --------------------------------------------------------------------

@given('the nine-row plan')
def the_nine_row_plan(ctx):
    ctx.project = _plan()


@given('the nine-row plan behind a toolbar shell')
def the_plan_behind_a_shell(ctx):
    ctx.project = _plan()
    ctx.bar = _ToolbarShell(ctx.project)


@when(parsers.parse('the status date moves to "{day}"'))
def the_status_date_moves(ctx, day):
    ctx.project.status_date = _d(day)


@when('the status date is cleared')
def the_status_date_is_cleared(ctx):
    ctx.project.status_date = None


@given(parsers.parse('"{child}" sits under "{parent}", a plain task'))
def a_child_under_a_plain_task(ctx, child, parent):
    base, end = datetime(2026, 1, 5), datetime(2026, 1, 9)
    ctx.project.add_task(Task(id=parent, name=parent, task_type="Task",
                              start_date=base, end_date=end))
    baby = Task(id=child, name=child, task_type="Task",
                start_date=base, end_date=end)
    baby.parent_task_id = parent
    ctx.project.add_task(baby)


@given(parsers.parse('a "{name}" calendar exists'))
def a_named_calendar_exists(ctx, name):
    from gantt_app.core.calendarregistry import NamedCalendar
    from gantt_app.core.workdaycalendar import WorkingCalendar

    ctx.project.calendars.add(NamedCalendar(
        id='sixday', name=name,
        calendar=WorkingCalendar(non_working_days={6})))


@given(parsers.parse('"{task_id}" follows the "{calendar_id}" calendar'))
def follows_a_calendar(ctx, task_id, calendar_id):
    ctx.project.get_task_by_id(task_id).calendar_id = calendar_id


@given(parsers.parse('"{task_id}" is assigned the resource "{resource_id}"'))
def assigned_a_resource(ctx, task_id, resource_id):
    from gantt_app.core.resource_model import (
        Resource, ResourceType, SchedulePattern)

    if resource_id != 'missing':
        ctx.project.resource_repository.resources[resource_id] = Resource(
            id=resource_id, name='Dev', resource_type=ResourceType.NAMED,
            role_type='Dev',
            schedule_pattern=SchedulePattern.STANDARD)
    ctx.project.get_task_by_id(task_id).resource_assignments = [
        {'resource_id': resource_id, 'units': 1.0}]


@when(parsers.parse('"{task_id}" is given progress {progress:d}'))
def progress_is_given(ctx, task_id, progress):
    ctx.project.get_task_by_id(task_id).progress = progress


@when(parsers.parse('"{task_id}" is removed'))
def a_task_is_removed(ctx, task_id):
    ctx.project.tasks = [t for t in ctx.project.tasks if t.id != task_id]


# ---- what each filter picks ---------------------------------------------------------

@then(parsers.parse('"{key}" picks "{ids}"'))
def a_filter_picks(ctx, key, ids):
    assert _select(key, ctx.project) == _ids(ids)


@then(parsers.parse('"{key}" picks "{task_id}" at least'))
def a_filter_picks_at_least(ctx, key, task_id):
    assert task_id in _select(key, ctx.project)


@then(parsers.parse('"{key}" picks nothing'))
def a_filter_picks_nothing(ctx, key):
    assert _select(key, ctx.project) == set()


@then(parsers.parse('"{key}" does not pick "{task_id}"'))
def a_filter_does_not_pick(ctx, key, task_id):
    assert task_id not in _select(key, ctx.project)


@then(parsers.parse('"{key}" picks "{kept}" and not "{dropped}"'))
def a_filter_picks_one_not_other(ctx, key, kept, dropped):
    selected = _select(key, ctx.project)
    assert kept in selected
    assert dropped not in selected


@then('every built-in highlight filter has a key and a label')
def every_filter_is_labelled():
    from gantt_app.views.toolbar import Toolbar
    for key, label, _selector in Toolbar.HIGHLIGHT_FILTERS:
        assert key and label


# ---- one at a time ---------------------------------------------------------------------

@when(parsers.parse('"{key}" is applied'))
def a_filter_is_applied(ctx, key):
    ctx.bar.apply_highlight(key)


@when('the highlight is cleared')
def the_highlight_is_cleared(ctx):
    ctx.bar.clear_highlight()


@when('the highlight is refreshed')
def the_highlight_is_refreshed(ctx):
    ctx.bar.refresh_highlight()


@then(parsers.parse('the painted rows are "{ids}"'))
def the_painted_rows_are(ctx, ids):
    assert ctx.bar.task_list.painted == _ids(ids)


@then('nothing is painted')
def nothing_is_painted(ctx):
    assert not ctx.bar.task_list.highlighted_rows_shown()


@then('no highlight is active')
def no_highlight_is_active(ctx):
    assert ctx.bar._active_highlight is None


@then(parsers.parse('the painted rows do not include "{task_id}"'))
def not_painted(ctx, task_id):
    assert task_id not in ctx.bar.task_list.painted


@then(parsers.parse('the active highlight is "{key}"'))
def the_active_highlight_is(ctx, key):
    assert ctx.bar._active_highlight == key


# ---- the gallery ---------------------------------------------------------------------------

def _gallery_labels(ctx):
    return [item.get('label', '')
            for item in ctx.bar._highlight_gallery_items()]


@then(parsers.parse('the gallery labels include "{label}"'))
def the_gallery_includes(ctx, label):
    assert label in _gallery_labels(ctx)


@then(parsers.parse('the gallery labels do not include "{label}"'))
def the_gallery_excludes(ctx, label):
    assert label not in _gallery_labels(ctx)


@then(parsers.parse('the gallery opens with a "{header}" header'))
def the_gallery_opens_with(ctx, header):
    items = ctx.bar._highlight_gallery_items()
    assert items[0].get('type') == 'header'
    assert items[0].get('label') == header


@then(parsers.parse('"{label}" follows it'))
def follows_the_header(ctx, label):
    items = ctx.bar._highlight_gallery_items()
    assert items[1].get('label') == label


@then(parsers.parse('"{first}" comes before "{second}"'))
def comes_before(ctx, first, second):
    labels = _gallery_labels(ctx)
    assert labels.index(first) < labels.index(second)


# ---- custom filters on the plan ---------------------------------------------------------------

def _custom_filter(name, field, test, value, in_menu=True):
    return {'name': name, 'show_in_menu': in_menu,
            'rules': [{'field': field, 'test': test, 'value': value}]}


@given(parsers.parse('a menu filter "{name}" matching "{field}" {test} '
                     '"{value}"'))
def a_menu_filter(ctx, name, field, test, value):
    ctx.project.custom_filters = [
        _custom_filter(name, field, test, value)]


@given(parsers.parse('a filter "{name}" matching "{field}" {test} "{value}"'))
def a_stored_filter(ctx, name, field, test, value):
    ctx.project.custom_filters = [
        _custom_filter(name, field, test, value, in_menu=False)]


@when(parsers.parse('"{key}" is copied'))
def a_filter_is_copied(ctx, key):
    ctx.copies = getattr(ctx, 'copies', []) + [
        ctx.bar._more_filters_copy(key)]


@then(parsers.parse('the copy is named "{name}"'))
def the_copy_is_named(ctx, name):
    assert ctx.copies[-1] == name


@then(parsers.parse('the copies are named "{first}" and "{second}"'))
def the_copies_are_named(ctx, first, second):
    assert ctx.copies[-2:] == [first, second]


@then(parsers.parse('"{name}" paints what "{key}" paints'))
def the_copy_paints_the_same(ctx, name, key):
    from gantt_app.views.gridfilter import definition_matching_ids

    clone = ctx.bar._find_custom_filter(name)
    assert clone is not None
    assert (definition_matching_ids(ctx.project, clone)
            == _select(key, ctx.project))


@then(parsers.parse('"{name}" holds the rule "{field}" {test} "{value}"'))
def the_copy_clones_the_rules(ctx, name, field, test, value):
    clone = ctx.bar._find_custom_filter(name)
    assert clone is not None
    assert clone['rules'] == [{'field': field, 'test': test,
                               'value': value}]


@then("every built-in's rules match its selector")
def the_rules_table_matches():
    from gantt_app.views.gridfilter import definition_matching_ids
    from gantt_app.views.toolbar import Toolbar

    project = _plan()
    for key, _label, selector in Toolbar.HIGHLIGHT_FILTERS:
        rules = Toolbar.HIGHLIGHT_FILTER_RULES[key]
        assert (definition_matching_ids(
                    project, {'name': 'x', 'rules': rules})
                == set(selector(project))), key


@when(parsers.parse('a filter is saved as "{name}" matching "{field}" '
                    '{test} "{value}"'))
def a_filter_is_saved(ctx, name, field, test, value):
    ctx.error = ctx.bar._save_custom_filter(
        {'name': name,
         'rules': [{'field': field, 'test': test, 'value': value}]})


@when(parsers.parse('"{name}" is re-saved matching "{field}" {test} '
                    '"{value}"'))
def a_filter_is_re_saved(ctx, name, field, test, value):
    ctx.error = ctx.bar._save_custom_filter(
        {'name': name,
         'rules': [{'field': field, 'test': test, 'value': value}]},
        old_name=name)


@then('the save is refused')
def the_save_is_refused(ctx):
    assert ctx.error


@then('the save is allowed')
def the_save_is_allowed(ctx):
    assert ctx.error is None


@then(parsers.parse('the custom filters still number {count:d}'))
def the_custom_filters_number(ctx, count):
    assert len(ctx.project.custom_filters) == count


@then('there are no custom filters')
def no_custom_filters(ctx):
    assert ctx.project.custom_filters == []


@then(parsers.parse('"{name}" now matches "{field}" {test} "{value}"'))
def the_filter_now_matches(ctx, name, field, test, value):
    clone = ctx.bar._find_custom_filter(name)
    assert clone['rules'][0]['test'] == test


# ---- the new filter fields ------------------------------------------------------------------------

@then(parsers.parse('the "{field}" choices offer "{value}"'))
def the_choices_offer(ctx, field, value):
    from gantt_app.views.gridfilter import choice_values
    assert value in choice_values(ctx.project, field)


@then(parsers.parse('the "{field}" choices do not offer "{value}"'))
def the_choices_do_not_offer(ctx, field, value):
    from gantt_app.views.gridfilter import choice_values
    assert value not in choice_values(ctx.project, field)


@then(parsers.parse('a "{field}" equals "{value}" rule picks "{ids}"'))
def a_field_rule_picks(ctx, field, value, ids):
    from gantt_app.views.gridfilter import definition_matching_ids

    definition = {'name': 'x', 'rules': [
        {'field': field, 'test': 'equals', 'value': value}]}
    assert definition_matching_ids(ctx.project, definition) == _ids(ids)


@then(parsers.parse('a "{field}" is_not_empty rule picks "{ids}"'))
def a_present_rule_picks(ctx, field, ids):
    from gantt_app.views.gridfilter import definition_matching_ids

    definition = {'name': 'x', 'rules': [
        {'field': field, 'test': 'is_not_empty'}]}
    assert definition_matching_ids(ctx.project, definition) == _ids(ids)


@then(parsers.parse('a "{field}" equals "{value}" rule picks "{task_id}" '
                    'at least'))
def a_rule_picks_at_least(ctx, field, value, task_id):
    from gantt_app.views.gridfilter import definition_matching_ids

    definition = {'name': 'x', 'rules': [
        {'field': field, 'test': 'equals', 'value': value}]}
    assert task_id in definition_matching_ids(ctx.project, definition)
