"""
pytest-bdd tests for what survives a save, an open, and a fresh plan
(issues #91, #92, #93).

Run with:
    python3 -m pytest tests/test_plan_persistence_bdd.py -q

The toolbar methods are exercised on a SimpleNamespace stand-in, the
same shape tests/test_toolbar_menus.py uses: the helpers are written
against self.<field> and carry no window state, so a namespace answers
them as well as a Toolbar does. Nothing here needs a display.
"""
import json
from datetime import datetime
from types import MethodType, SimpleNamespace
from unittest import mock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.baselines import BaselineManager
from gantt_app.core.calendarregistry import (
    CalendarRegistry, NamedCalendar,
)
from gantt_app.core.models import Project, Task, SCHEDULE_FROM_FINISH
from gantt_app.core.workdaycalendar import WorkingCalendar
from gantt_app.views import preferences, theme
from gantt_app.views.toolbar import Toolbar, _file_name_for

pytestmark = [
    pytest.mark.plan_persistence,
]

scenarios("features/plan_persistence.feature")

MONDAY = datetime(2026, 8, 17)


def _named(calendar_id='sixday', name='Six-Day Week', off=frozenset({6})):
    return NamedCalendar(
        id=calendar_id, name=name,
        calendar=WorkingCalendar(non_working_days=set(off)))


def _day(text):
    return datetime.strptime(text, "%Y-%m-%d")


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    context = SimpleNamespace(
        project=None, loaded=None, stub=None, tmp=tmp_path,
        monkeypatch=monkeypatch, result=None, task=None, data=None,
        calls=[], dialogs=[])
    return context


def _clean_settings(ctx):
    """Point the app's settings.json at a throwaway directory."""
    ctx.monkeypatch.setattr(theme, 'settings_directory',
                            lambda *a, **k: ctx.tmp)


def _loaded_project():
    project = Project(name="Loaded")
    project.status_date = MONDAY
    project.schedule_from = SCHEDULE_FROM_FINISH
    project.deadline = MONDAY.replace(month=12)
    project.priority = 700
    project.hours_per_day = 6
    project.hidden_grid_columns = ['Label', 'Milestone']
    project.custom_filters = [{'name': 'Late', 'query': 'finish'}]
    project.calendars = CalendarRegistry([_named()])
    project.calendar_id = 'sixday'
    return project


def _saver(ctx, project, path=None, locked=False):
    stub = SimpleNamespace(project=project, baseline_manager=None,
                           current_file_path=path,
                           _file_name_locked=locked, task_list=None,
                           master=SimpleNamespace(), dialogs=ctx.dialogs)
    for method in ('_write_project', 'save_project', 'save_project_as',
                   '_report'):
        setattr(stub, method,
                MethodType(getattr(Toolbar, method), stub))
    return stub


# ------------------------------------------------------------------
# GIVEN - plans and their calendars
# ------------------------------------------------------------------

@given("a plan")
def a_plan(ctx):
    ctx.project = Project(name="P")


@given(parsers.parse('a plan carrying the "{calendar_id}" calendar'))
def a_plan_carrying_a_calendar(ctx, calendar_id):
    a_plan(ctx)
    ctx.project.calendars = CalendarRegistry([_named(calendar_id)])


@given(parsers.parse('a calendar "{calendar_id}" with nothing off'))
def a_calendar_with_nothing_off(ctx, calendar_id):
    ctx.project.calendars.add(_named(calendar_id, calendar_id,
                                     frozenset()))


@given(parsers.parse('a calendar "{calendar_id}" taking Friday and '
                     'Saturday off'))
def a_calendar_taking_friday_saturday_off(ctx, calendar_id):
    ctx.project.calendars = CalendarRegistry(
        [_named(calendar_id, calendar_id, frozenset({4, 5}))])


@given(parsers.parse('the plan\'s calendar is "{calendar_id}"'))
def the_plans_calendar_is(ctx, calendar_id):
    ctx.project.calendar_id = calendar_id


@given(parsers.parse('a task "{name}" running "{start}" to "{end}"'))
def a_task_running(ctx, name, start, end):
    task = Task(id=name, name=name, start_date=_day(start),
                end_date=_day(end))
    ctx.project.tasks = ctx.project.tasks + [task]
    ctx.task = task


@given(parsers.parse('a task "{name}" running "{start}" to "{end}" '
                     'on the "{calendar_id}" calendar'))
def a_task_on_a_calendar(ctx, name, start, end, calendar_id):
    a_task_running(ctx, name, start, end)
    ctx.task.calendar_id = calendar_id


@given("a plan written before the choice existed")
def a_plan_written_before_the_choice(ctx):
    ctx.loaded = Project.from_dict({'name': 'Old', 'tasks': []})


# ------------------------------------------------------------------
# GIVEN - the toolbar stand-ins
# ------------------------------------------------------------------

@given(parsers.parse('a toolbar holding the "{name}" plan'))
def a_toolbar_holding_a_plan(ctx, name):
    ctx.stub = SimpleNamespace(project=Project(name=name))


@given("a toolbar holding a loaded plan with every field set")
def a_toolbar_holding_a_loaded_plan(ctx):
    ctx.stub = SimpleNamespace(project=_loaded_project())
    ctx.library = CalendarRegistry([_named('lib', 'Library')])
    ctx.stub.master = SimpleNamespace(calendar_library=ctx.library)


@given(parsers.parse('a toolbar holding the "{name}" plan over an '
                     'empty library'))
def a_toolbar_over_an_empty_library(ctx, name):
    ctx.library = CalendarRegistry([])
    ctx.stub = SimpleNamespace(
        project=Project(name=name),
        master=SimpleNamespace(calendar_library=ctx.library))


@given(parsers.parse('a toolbar holding the "{name}" plan over a '
                     'library where "{calendar_id}" takes Monday off'))
def a_toolbar_over_a_tuned_library(ctx, name, calendar_id):
    ctx.tuned = _named(calendar_id, 'Six-Day Week', frozenset({0}))
    ctx.library = CalendarRegistry([ctx.tuned])
    ctx.stub = SimpleNamespace(
        project=Project(name=name),
        master=SimpleNamespace(calendar_library=ctx.library))


@given(parsers.parse('a toolbar holding the "{name}" plan with no '
                     'library'))
def a_toolbar_with_no_library(ctx, name):
    ctx.stub = SimpleNamespace(project=Project(name=name),
                               master=SimpleNamespace())


@given("a loaded plan with every field set")
def a_loaded_plan_with_every_field(ctx):
    ctx.loaded = _loaded_project()


@given(parsers.parse('a loaded plan carrying the "{calendar_id}" '
                     'calendar'))
def a_loaded_plan_carrying(ctx, calendar_id):
    ctx.loaded = Project(name="P")
    ctx.loaded.calendars = CalendarRegistry([_named(calendar_id)])
    ctx.loaded_calendars = ctx.loaded.calendars


@given(parsers.parse('a loaded plan with a filter named "{name}"'))
def a_loaded_plan_with_a_filter(ctx, name):
    ctx.loaded = Project(name="Loaded")
    ctx.loaded.custom_filters = [
        {'name': name, 'rules': [
            {'field': 'Progress', 'test': 'equals', 'value': '0'}]}]


@given(parsers.parse('a loaded plan deliberately named "{name}"'))
def a_loaded_plan_deliberately_named(ctx, name):
    ctx.loaded = Project(name=name, name_was_set=True)


# ------------------------------------------------------------------
# GIVEN - the preference store
# ------------------------------------------------------------------

@given("a clean settings file")
def a_clean_settings_file(ctx):
    _clean_settings(ctx)


@given(parsers.parse('a settings file holding "{text}"'))
def a_settings_file_holding(ctx, text):
    _clean_settings(ctx)
    (ctx.tmp / theme.SETTINGS_FILE).write_text(text)


@given(parsers.parse('the theme mode "{mode}" was saved'))
def the_theme_mode_was_saved(ctx, mode):
    theme.save_mode(mode)


@given(parsers.parse('a saved plan carrying three filters all named '
                     '"{name}"'))
def a_saved_plan_with_duplicate_filters(ctx, name):
    ctx.data = Project(name="P").to_dict()
    ctx.data['custom_filters'] = [
        {'name': name, 'rules': [
            {'field': 'Type', 'test': 'equals', 'value': 'Task'}]},
        {'name': name, 'rules': [
            {'field': 'Progress', 'test': 'equals', 'value': '0'}]},
        {'name': name, 'query': 'type = "Phase"'},
    ]


# ------------------------------------------------------------------
# WHEN - calendars, take-on, merges
# ------------------------------------------------------------------

@when(parsers.parse('the plan\'s calendar is set to "{calendar_id}"'))
def the_plans_calendar_is_set(ctx, calendar_id):
    ctx.result = ctx.project.set_plan_calendar(calendar_id)


@when("the plan is saved and loaded")
def the_plan_is_saved_and_loaded(ctx):
    ctx.loaded = Project.from_dict(ctx.project.to_dict())


@when("the toolbar takes on the loaded plan")
def the_toolbar_takes_on(ctx):
    Toolbar._take_on_project_fields(ctx.stub, ctx.loaded)


@when("the toolbar starts a blank project")
def the_toolbar_starts_blank(ctx):
    ctx.stub._take_on_project_fields = MethodType(
        Toolbar._take_on_project_fields, ctx.stub)
    Toolbar._blank_project(ctx.stub, "New Project")


@when("the loaded plan's calendars are merged")
def the_calendars_are_merged(ctx):
    Toolbar._merge_loaded_calendars(ctx.stub, ctx.loaded)


# ------------------------------------------------------------------
# WHEN - the preference store
# ------------------------------------------------------------------

@when(parsers.parse('the "{calendar_id}" calendar is saved to the '
                    'library'))
def a_calendar_is_saved_to_the_library(ctx, calendar_id):
    ctx.result = preferences.save_calendar_library(
        CalendarRegistry([_named(calendar_id)]))


@when("an empty library is saved")
def an_empty_library_is_saved(ctx):
    preferences.save_calendar_library(CalendarRegistry([]))


@when(parsers.parse('baseline slot {slot:d} is named "{name}" in '
                    '"{colour}"'))
def baseline_slot_named_in_colour(ctx, slot, name, colour):
    preferences.save_baseline_slot_preferences(
        {slot: {'name': name, 'color': colour}})
    ctx.manager = BaselineManager()
    ctx.applied = preferences.apply_baseline_slot_preferences(
        ctx.manager)


@when(parsers.parse('baseline slot {slot:d} is named "{name}" with no '
                    'colour'))
def baseline_slot_named_no_colour(ctx, slot, name):
    preferences.save_baseline_slot_preferences(
        {slot: {'name': name, 'color': ''}})


@when("the plan is loaded")
def the_plan_is_loaded(ctx):
    ctx.loaded = Project.from_dict(ctx.data)


# ------------------------------------------------------------------
# WHEN - saving and file names
# ------------------------------------------------------------------

@when(parsers.parse('a file name is suggested for "{name}"'))
def a_file_name_is_suggested(ctx, name):
    if name == '(spaces)':
        name = '   '
    ctx.result = _file_name_for(name)


@given(parsers.parse('a saver for a plan named "{name}" never '
                     'deliberately set'))
def a_saver_for_an_untouched_plan(ctx, name):
    ctx.project = Project(name=name)
    ctx.stub = _saver(ctx, ctx.project)


@given(parsers.parse('a saver for a plan named "{name}"'))
def a_saver_for_a_plan(ctx, name):
    ctx.project = Project(name=name)
    ctx.stub = _saver(ctx, ctx.project)


@given(parsers.parse('a saver for a plan deliberately named "{name}"'))
def a_saver_for_a_deliberate_plan(ctx, name):
    ctx.project = Project(name=name, name_was_set=True)
    ctx.stub = _saver(ctx, ctx.project)


@given(parsers.parse('a plan deliberately named "{name}"'))
def a_plan_deliberately_named(ctx, name):
    ctx.project = Project(name=name, name_was_set=True)


@given(parsers.parse('a saver whose file "{filename}" exists'))
def a_saver_whose_file_exists(ctx, filename):
    old = ctx.tmp / filename
    old.write_text('{}')
    ctx.stub = _saver(ctx, ctx.project, path=str(old), locked=False)


@given(parsers.parse('a saver locked onto "{filename}"'))
def a_saver_locked_onto(ctx, filename):
    ctx.stub = _saver(ctx, ctx.project, path=str(ctx.tmp / filename),
                      locked=True)


@given(parsers.parse('a saver whose file "{filename}" exists beside a '
                     '"{other}" that is not ours'))
def a_saver_beside_a_stranger(ctx, filename, other):
    (ctx.tmp / other).write_text('{"someone": "elses"}')
    ctx.stub = _saver(ctx, ctx.project, path=str(ctx.tmp / filename),
                      locked=False)


@given(parsers.parse('a plan written before the flag existed, named '
                     '"{name}"'))
@when(parsers.parse('a plan written before the flag existed, named '
                    '"{name}"'))
def a_plan_written_before_the_flag(ctx, name):
    ctx.loaded = Project.from_dict({'name': name, 'tasks': []})


@when("the plan is written to a file")
def the_plan_is_written(ctx):
    import gantt_app.views.toolbar as toolbar_mod
    ctx.path = str(ctx.tmp / "p.json")
    with mock.patch.object(toolbar_mod.messagebox, 'showinfo',
                           lambda *a, **k: ctx.dialogs.append(a)):
        Toolbar._write_project(ctx.stub, ctx.path)


@when(parsers.parse('the plan is saved as "{filename}"'))
def the_plan_is_saved_as(ctx, filename):
    import gantt_app.views.toolbar as toolbar_mod
    ctx.path = str(ctx.tmp / filename)
    with mock.patch.object(toolbar_mod.filedialog, 'asksaveasfilename',
                           return_value=ctx.path):
        Toolbar.save_project_as(ctx.stub)


@when("the plan is saved")
def the_plan_is_saved(ctx):
    Toolbar.save_project(ctx.stub)


@when("the plan is saved and the stranger's file is declined")
def the_plan_is_saved_stranger_declined(ctx):
    import gantt_app.views.toolbar as toolbar_mod
    with mock.patch.object(toolbar_mod.messagebox, 'askyesno',
                           return_value=False):
        Toolbar.save_project(ctx.stub)


@when("the plan is saved and the stranger's file is accepted")
def the_plan_is_saved_stranger_accepted(ctx):
    import gantt_app.views.toolbar as toolbar_mod
    with mock.patch.object(toolbar_mod.messagebox, 'askyesno',
                           return_value=True):
        Toolbar.save_project(ctx.stub)


# ------------------------------------------------------------------
# THEN - the plan's calendar
# ------------------------------------------------------------------

@then("the plan names no calendar")
def the_plan_names_no_calendar(ctx):
    assert ctx.project.calendar_id is None


@then("the loaded plan names no calendar")
def the_loaded_plan_names_no_calendar(ctx):
    assert ctx.loaded.calendar_id is None


@then("the plan's own calendar answers for it")
def the_plans_own_answers(ctx):
    assert ctx.project.plan_calendar() is ctx.project.calendar


@then("the plan's own calendar answers for the loaded plan")
def the_plans_own_answers_for_loaded(ctx):
    assert ctx.loaded.plan_calendar() is ctx.loaded.calendar


@then(parsers.parse('the "{calendar_id}" calendar answers for the '
                    'plan'))
def the_named_calendar_answers(ctx, calendar_id):
    named = ctx.project.calendars.get(calendar_id)
    assert ctx.project.plan_calendar() is named.calendar


@then(parsers.parse('the loaded "{calendar_id}" calendar answers for '
                    'it'))
def the_loaded_named_calendar_answers(ctx, calendar_id):
    named = ctx.loaded.calendars.get(calendar_id)
    assert ctx.loaded.plan_calendar() is named.calendar


@then(parsers.parse('the task "{name}" follows the "{calendar_id}" '
                    'calendar'))
def the_task_follows_the_calendar(ctx, name, calendar_id):
    task = next(t for t in ctx.project.tasks if t.name == name)
    named = ctx.project.calendars.get(calendar_id)
    assert ctx.project.calendar_for(task) is named.calendar


@then(parsers.parse('the task "{name}" ends on "{date}"'))
def the_task_ends_on(ctx, name, date):
    task = next(t for t in ctx.project.tasks if t.name == name)
    assert task.end_date.date() == _day(date).date()


@then(parsers.parse('setting it to "{calendar_id}" again is refused'))
def setting_again_is_refused(ctx, calendar_id):
    assert not ctx.project.set_plan_calendar(calendar_id)


@then(parsers.parse('the loaded plan\'s calendar is "{calendar_id}"'))
def the_loaded_plans_calendar_is(ctx, calendar_id):
    assert ctx.loaded.calendar_id == calendar_id


# ------------------------------------------------------------------
# THEN - take-on
# ------------------------------------------------------------------

@then("the plan carries the loaded fields")
def the_plan_carries_the_fields(ctx):
    project = ctx.stub.project
    loaded = ctx.loaded
    assert project.status_date == MONDAY
    assert project.schedule_from == SCHEDULE_FROM_FINISH
    assert project.deadline == MONDAY.replace(month=12)
    assert project.priority == 700
    assert project.hours_per_day == 6
    assert project.hidden_grid_columns == ['Label', 'Milestone']
    assert project.custom_filters == loaded.custom_filters
    assert project.calendars is loaded.calendars
    assert project.calendar_id == 'sixday'


@then("the new plan carries none of the old fields")
def the_new_plan_carries_none(ctx):
    project = ctx.stub.project
    assert project.status_date is None
    assert project.schedule_from == 'start'
    assert project.deadline is None
    assert project.calendar_id is None
    assert project.tasks == []


@then("it keeps the shared calendar library")
def it_keeps_the_library(ctx):
    assert ctx.stub.project.calendars is ctx.library


# ------------------------------------------------------------------
# THEN - the calendar library
# ------------------------------------------------------------------

@then(parsers.parse('the library holds "{calendar_id}"'))
def the_library_holds(ctx, calendar_id):
    assert calendar_id in ctx.library


@then("the loaded plan points at the library")
def the_loaded_plan_points_at_the_library(ctx):
    assert ctx.loaded.calendars is ctx.library


@then("the library was written to the settings file")
def the_library_was_written(ctx):
    saved = json.loads((ctx.tmp / theme.SETTINGS_FILE).read_text())
    assert saved.get('calendars')


@then(parsers.parse('the plan\'s "{calendar_id}" takes Monday off'))
def the_plans_calendar_takes_monday_off(ctx, calendar_id):
    named = ctx.loaded.calendars.get(calendar_id)
    assert named.calendar is ctx.tuned.calendar


@then("the loaded plan keeps its own calendars")
def the_loaded_plan_keeps_its_own(ctx):
    assert ctx.loaded.calendars is ctx.loaded_calendars


@then(parsers.parse('the library loads with "{calendar_id}"'))
def the_library_loads_with(ctx, calendar_id):
    assert [n.id for n in preferences.load_calendar_library()] == \
        [calendar_id]


@then("the library loads with the preset calendars")
def the_library_loads_with_presets(ctx):
    assert len(preferences.load_calendar_library())


@then("the library loads empty")
def the_library_loads_empty(ctx):
    assert len(preferences.load_calendar_library()) == 0


@then(parsers.parse('a fresh baseline manager\'s slot {slot:d} is '
                    '"{name}" in "{colour}"'))
def the_baseline_slot_is(ctx, slot, name, colour):
    assert ctx.applied
    found = ctx.manager.get_slot(slot)
    assert found.display_name == name
    assert found.color == colour


@then(parsers.parse('its slot {slot:d} stays "{name}"'))
def its_slot_stays(ctx, slot, name):
    assert ctx.manager.get_slot(slot).display_name == name


@then(parsers.parse('the settings file still says theme "{mode}"'))
def the_settings_file_says_theme(ctx, mode):
    saved = json.loads((ctx.tmp / theme.SETTINGS_FILE).read_text())
    assert saved.get('theme_mode') == mode


@then(parsers.parse('the theme mode loads as "{mode}"'))
def the_theme_mode_loads_as(ctx, mode):
    assert theme.load_mode() == mode


@then(parsers.parse('the filters are named "{names}"'))
def the_filters_are_named(ctx, names):
    expected = [item.strip() for item in names.split(',')]
    assert [f['name'] for f in ctx.loaded.custom_filters] == expected


@then(parsers.parse('the filter is named "{name}"'))
def the_filter_is_named(ctx, name):
    assert ctx.stub.project.custom_filters[0]['name'] == name


@then("no dialog was shown")
def no_dialog_was_shown(ctx):
    assert ctx.dialogs == []


@then("the file exists")
def the_file_exists(ctx):
    from pathlib import Path
    assert Path(ctx.path).exists()
    assert ctx.stub.current_file_path == ctx.path


@then("applying baseline preferences answers no")
def applying_baseline_preferences_answers_no(ctx):
    manager = BaselineManager()
    assert not preferences.apply_baseline_slot_preferences(manager)


# ------------------------------------------------------------------
# THEN - the file-name coupling
# ------------------------------------------------------------------

@then(parsers.parse('it reads "{suggestion}"'))
def it_reads(ctx, suggestion):
    assert ctx.result == suggestion


@then(parsers.parse('the plan is named "{name}"'))
def the_plan_is_named(ctx, name):
    assert ctx.project.name == name


@then("the file name is locked")
def the_file_name_is_locked(ctx):
    assert ctx.stub._file_name_locked


@then("the file name is not locked")
def the_file_name_is_not_locked(ctx):
    assert not ctx.stub._file_name_locked


@then(parsers.parse('the saved file names the plan "{name}"'))
def the_saved_file_names_the_plan(ctx, name):
    data = json.loads(open(ctx.path).read())
    assert data['name'] == name


@then(parsers.parse('the current file is "{filename}"'))
def the_current_file_is(ctx, filename):
    assert ctx.stub.current_file_path == str(ctx.tmp / filename)


@then(parsers.parse('"{filename}" still exists'))
def the_file_still_exists(ctx, filename):
    assert (ctx.tmp / filename).exists()


@then(parsers.parse('no "{filename}" was written'))
def no_file_was_written(ctx, filename):
    assert not (ctx.tmp / filename).exists()


@then(parsers.parse('"{filename}" still says it is not ours'))
def the_file_still_says_not_ours(ctx, filename):
    assert (ctx.tmp / filename).read_text() == '{"someone": "elses"}'


@then("the loaded plan knows its name was set")
def the_loaded_plan_knows_set(ctx):
    assert ctx.loaded.name_was_set


@then("the loaded plan knows its name was not set")
def the_loaded_plan_knows_not_set(ctx):
    assert not ctx.loaded.name_was_set


@then("the taken-on plan knows its name was set")
def the_taken_on_plan_knows_set(ctx):
    assert ctx.stub.project.name_was_set
