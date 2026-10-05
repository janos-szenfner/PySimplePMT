"""
BDD steps for tests/features/workdaycalendar.feature - the
working-day calendar, overrides, country holidays, the working week,
and the picker's region table. Pure domain, no display.
"""

import re

import pytest
from pytest_bdd import given, parsers, scenario, then, when

from datetime import date, datetime, timedelta
from types import SimpleNamespace

from gantt_app.core.models import Project, Task
from gantt_app.core.workdaycalendar import (
    COUNTRY_REGIONS,
    EU_COUNTRIES,
    REGION_ORDER,
    REGION_EUROPE,
    REGION_OTHER,
    CalendarTask,
    DateOverride,
    WorkingCalendar,
    country_holidays,
    default_calendar,
    holidays_available,
    region_of,
    supported_countries,
)

HAVE_HOLIDAYS = holidays_available()


@pytest.fixture
def ctx():
    return SimpleNamespace(calendar=None, second_cal=None, project=None,
                           reloaded=None, reloaded_cal=None, task=None,
                           moved=None, week_answer=None, removal=None)


@pytest.fixture(autouse=True)
def _needs_holidays(request):
    """@holiday_package scenarios need the optional holidays package."""
    if (request.node.get_closest_marker('holiday_package')
            and not HAVE_HOLIDAYS):
        pytest.skip("needs the holidays package")


def _moment(iso):
    """'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM' as a date or datetime."""
    if ' ' in iso:
        return datetime.fromisoformat(iso)
    return date.fromisoformat(iso)


def d(iso):
    """An ISO date or datetime as a datetime - what models.Task holds."""
    return datetime.fromisoformat(iso)


def _days(text):
    return {int(part) for part in text.split(', ')}


def _recurring(text):
    return {tuple(int(part) for part in pair.split('-'))
            for pair in text.split(', ')}


# ---- scenario bindings --------------------------------------------------------


@scenario('features/workdaycalendar.feature', 'Weekdays are worked')
def test_weekdays_are_worked():
    pass


@scenario('features/workdaycalendar.feature', 'The weekend is not')
def test_the_weekend_is_not():
    pass


@scenario('features/workdaycalendar.feature',
          'A datetime is read the same way')
def test_a_datetime_is_read_the_same_way():
    pass


@scenario('features/workdaycalendar.feature', 'A holiday is not worked')
def test_a_holiday_is_not_worked():
    pass


@scenario('features/workdaycalendar.feature',
          'A recurring holiday applies every year')
def test_a_recurring_holiday_applies_every_year():
    pass


@scenario('features/workdaycalendar.feature',
          'A different week can be declared')
def test_a_different_week_can_be_declared():
    pass


@scenario('features/workdaycalendar.feature',
          'A week with no working day does not hang')
def test_a_week_with_no_working_day_does_not_hang():
    pass


@scenario('features/workdaycalendar.feature',
          'A weekend start moves to the Monday')
def test_a_weekend_start_moves_to_the_monday():
    pass


@scenario('features/workdaycalendar.feature',
          'A working start is left alone')
def test_a_working_start_is_left_alone():
    pass


@scenario('features/workdaycalendar.feature', 'It steps over a holiday too')
def test_it_steps_over_a_holiday_too():
    pass


@scenario('features/workdaycalendar.feature',
          'The previous working day is the mirror')
def test_the_previous_working_day_is_the_mirror():
    pass


@scenario('features/workdaycalendar.feature',
          'A datetime keeps its time of day')
def test_a_datetime_keeps_its_time_of_day():
    pass


@scenario('features/workdaycalendar.feature', 'A span inside one week')
def test_a_span_inside_one_week():
    pass


@scenario('features/workdaycalendar.feature',
          'One day ends where it starts')
def test_one_day_ends_where_it_starts():
    pass


@scenario('features/workdaycalendar.feature',
          'A weekend is crossed without spending duration')
def test_a_weekend_is_crossed():
    pass


@scenario('features/workdaycalendar.feature',
          'A long task crosses several weekends')
def test_a_long_task_crosses_several_weekends():
    pass


@scenario('features/workdaycalendar.feature',
          'A weekend start is pushed before counting')
def test_a_weekend_start_is_pushed():
    pass


@scenario('features/workdaycalendar.feature', 'A holiday extends the finish')
def test_a_holiday_extends_the_finish():
    pass


@scenario('features/workdaycalendar.feature',
          'No duration leaves the date alone')
def test_no_duration_leaves_the_date_alone():
    pass


@scenario('features/workdaycalendar.feature',
          'Working backwards is the mirror')
def test_working_backwards_is_the_mirror():
    pass


@scenario('features/workdaycalendar.feature',
          'Working days ignore the weekend')
def test_working_days_ignore_the_weekend():
    pass


@scenario('features/workdaycalendar.feature', 'Elapsed days do not')
def test_elapsed_days_do_not():
    pass


@scenario('features/workdaycalendar.feature', 'A span of one day')
def test_a_span_of_one_day():
    pass


@scenario('features/workdaycalendar.feature',
          'A weekend-only span holds no work')
def test_a_weekend_only_span_holds_no_work():
    pass


@scenario('features/workdaycalendar.feature',
          'A backwards span holds no work')
def test_a_backwards_span_holds_no_work():
    pass


@scenario('features/workdaycalendar.feature', 'Measuring and adding agree')
def test_measuring_and_adding_agree():
    pass


@scenario('features/workdaycalendar.feature',
          'A round trip keeps every day')
def test_a_round_trip_keeps_every_day():
    pass


@scenario('features/workdaycalendar.feature',
          'A missing calendar is the standard week')
def test_a_missing_calendar_is_the_standard_week():
    pass


@scenario('features/workdaycalendar.feature',
          'A damaged calendar falls back rather than raising')
def test_a_damaged_calendar_falls_back():
    pass


@scenario('features/workdaycalendar.feature',
          'A project carries its calendar through a save')
def test_a_project_carries_its_calendar():
    pass


@scenario('features/workdaycalendar.feature',
          'A project saved without one opens on the standard week')
def test_a_project_saved_without_one():
    pass


@scenario('features/workdaycalendar.feature',
          'A calendar task crossing a weekend')
def test_a_calendar_task_crossing_a_weekend():
    pass


@scenario('features/workdaycalendar.feature',
          'A calendar task starting on a Saturday')
def test_a_calendar_task_starting_on_a_saturday():
    pass


@scenario('features/workdaycalendar.feature',
          'It uses the standard week unless given one')
def test_it_uses_the_standard_week():
    pass


@scenario('features/workdaycalendar.feature', 'A task inside one week')
def test_a_task_inside_one_week():
    pass


@scenario('features/workdaycalendar.feature', 'A task crossing a weekend')
def test_a_task_crossing_a_weekend():
    pass


@scenario('features/workdaycalendar.feature',
          'A task on a weekend is still a day long')
def test_a_task_on_a_weekend_is_still_a_day_long():
    pass


@scenario('features/workdaycalendar.feature', 'A milestone has no length')
def test_a_milestone_has_no_length():
    pass


@scenario('features/workdaycalendar.feature',
          'An effective start skips the weekend')
def test_an_effective_start_skips_the_weekend():
    pass


@scenario('features/workdaycalendar.feature',
          'A weekend start is moved to the Monday')
def test_a_weekend_start_is_moved():
    pass


@scenario('features/workdaycalendar.feature',
          'The working duration is kept when the start moves')
def test_the_working_duration_is_kept():
    pass


@scenario('features/workdaycalendar.feature',
          'A finish on a weekend is pulled back')
def test_a_finish_on_a_weekend_is_pulled_back():
    pass


@scenario('features/workdaycalendar.feature', 'A stated duration is honoured')
def test_a_stated_duration_is_honoured():
    pass


@scenario('features/workdaycalendar.feature',
          'A task already on working days is left alone')
def test_a_task_on_working_days_is_left_alone():
    pass


@scenario('features/workdaycalendar.feature',
          'Running it twice changes nothing')
def test_running_it_twice_changes_nothing():
    pass


@scenario('features/workdaycalendar.feature',
          'A milestone moves off the weekend keeping its moment')
def test_a_milestone_moves_off_the_weekend():
    pass


@scenario('features/workdaycalendar.feature',
          'A container takes its dates from its children')
def test_a_container_takes_its_dates():
    pass


@scenario('features/workdaycalendar.feature', 'A holiday calendar is respected')
def test_a_holiday_calendar_is_respected():
    pass


@scenario('features/workdaycalendar.feature',
          'A fixed national holiday is not worked')
def test_a_fixed_national_holiday_is_not_worked():
    pass


@scenario('features/workdaycalendar.feature',
          'A movable Easter holiday is not worked')
def test_a_movable_easter_holiday_is_not_worked():
    pass


@scenario('features/workdaycalendar.feature',
          'Countries are merged as a union')
def test_countries_are_merged_as_a_union():
    pass


@scenario('features/workdaycalendar.feature',
          'A holiday lengthens a task without lengthening its duration')
def test_a_holiday_lengthens_a_task():
    pass


@scenario('features/workdaycalendar.feature',
          'A start on a holiday moves to the next working day')
def test_a_start_on_a_holiday_moves():
    pass


@scenario('features/workdaycalendar.feature',
          'Selecting no countries leaves weekends alone')
def test_selecting_no_countries():
    pass


@scenario('features/workdaycalendar.feature',
          'The countries can be changed afterwards')
def test_the_countries_can_be_changed():
    pass


@scenario('features/workdaycalendar.feature',
          'Changing the countries clears what was worked out')
def test_changing_the_countries_clears_the_cache():
    pass


@scenario('features/workdaycalendar.feature', 'Every EU country resolves')
def test_every_eu_country_resolves():
    pass


@scenario('features/workdaycalendar.feature', 'The selection survives a save')
def test_the_selection_survives_a_save():
    pass


@scenario('features/workdaycalendar.feature',
          'A holiday pushes a scheduled task out')
def test_a_holiday_pushes_a_scheduled_task_out():
    pass


@scenario('features/workdaycalendar.feature',
          'Dropping a country pulls the plan back in')
def test_dropping_a_country_pulls_the_plan_back_in():
    pass


@scenario('features/workdaycalendar.feature',
          'A milestone moves off a holiday')
def test_a_milestone_moves_off_a_holiday():
    pass


@scenario('features/workdaycalendar.feature',
          'An unresolvable country is simply not observed')
def test_an_unresolvable_country_is_simply_not_observed():
    pass


@scenario('features/workdaycalendar.feature',
          'An unknown country code is skipped')
def test_an_unknown_country_code_is_skipped():
    pass


@scenario('features/workdaycalendar.feature', 'The selection is still saved')
def test_the_selection_is_still_saved():
    pass


@scenario('features/workdaycalendar.feature',
          'A Saturday can be made a working day')
def test_a_saturday_can_be_made_a_working_day():
    pass


@scenario('features/workdaycalendar.feature',
          'A weekday can be made a non-working day')
def test_a_weekday_can_be_made_a_non_working_day():
    pass


@scenario('features/workdaycalendar.feature',
          'An override beats a listed holiday')
def test_an_override_beats_a_listed_holiday():
    pass


@scenario('features/workdaycalendar.feature',
          'An override beats a recurring holiday')
def test_an_override_beats_a_recurring_holiday():
    pass


@scenario('features/workdaycalendar.feature',
          'An override beats a country holiday')
def test_an_override_beats_a_country_holiday():
    pass


@scenario('features/workdaycalendar.feature', 'One date holds one ruling')
def test_one_date_holds_one_ruling():
    pass


@scenario('features/workdaycalendar.feature',
          'A datetime is overridden by its date')
def test_a_datetime_is_overridden_by_its_date():
    pass


@scenario('features/workdaycalendar.feature',
          'Removing a ruling restores the ordinary rules')
def test_removing_a_ruling_restores():
    pass


@scenario('features/workdaycalendar.feature',
          'The reason is carried but takes no part')
def test_the_reason_is_carried():
    pass


@scenario('features/workdaycalendar.feature',
          'A non-working ruling survives a broken week')
def test_a_non_working_ruling_survives_a_broken_week():
    pass


@scenario('features/workdaycalendar.feature',
          'A worked Saturday pulls a finish in')
def test_a_worked_saturday_pulls_a_finish_in():
    pass


@scenario('features/workdaycalendar.feature', 'A shutdown pushes a finish out')
def test_a_shutdown_pushes_a_finish_out():
    pass


@scenario('features/workdaycalendar.feature',
          'A task may start on an overridden Saturday')
def test_a_task_may_start_on_an_overridden_saturday():
    pass


@scenario('features/workdaycalendar.feature',
          'A span counts an overridden Saturday as work')
def test_a_span_counts_an_overridden_saturday():
    pass


@scenario('features/workdaycalendar.feature',
          'The project keeps the work and moves the finish')
def test_the_project_keeps_the_work():
    pass


@scenario('features/workdaycalendar.feature',
          'Setting overrides leaves the countries alone')
def test_setting_overrides_leaves_the_countries_alone():
    pass


@scenario('features/workdaycalendar.feature',
          'Setting countries leaves the overrides alone')
def test_setting_countries_leaves_the_overrides_alone():
    pass


@scenario('features/workdaycalendar.feature', 'A ruling round-trips')
def test_a_ruling_round_trips():
    pass


@scenario('features/workdaycalendar.feature',
          'Rulings are saved in date order')
def test_rulings_are_saved_in_date_order():
    pass


@scenario('features/workdaycalendar.feature',
          'A calendar saved before overrides still opens')
def test_a_calendar_saved_before_overrides():
    pass


@scenario('features/workdaycalendar.feature',
          'One damaged ruling does not cost the rest')
def test_one_damaged_ruling_does_not_cost_the_rest():
    pass


@scenario('features/workdaycalendar.feature',
          'Calendars differing only in a ruling are not equal')
def test_calendars_differing_in_a_ruling():
    pass


@scenario('features/workdaycalendar.feature',
          'A six-day week pulls a finish in')
def test_a_six_day_week_pulls_a_finish_in():
    pass


@scenario('features/workdaycalendar.feature',
          'A four-day week pushes a finish out')
def test_a_four_day_week_pushes_a_finish_out():
    pass


@scenario('features/workdaycalendar.feature',
          'The new week is what the calendar answers')
def test_the_new_week_is_what_the_calendar_answers():
    pass


@scenario('features/workdaycalendar.feature',
          'A week with no working day is refused')
def test_a_week_with_no_working_day_is_refused():
    pass


@scenario('features/workdaycalendar.feature',
          'Setting the week leaves the countries and rulings alone')
def test_setting_the_week_leaves_the_others_alone():
    pass


@scenario('features/workdaycalendar.feature',
          'An override still outranks the new week')
def test_an_override_still_outranks_the_new_week():
    pass


@scenario('features/workdaycalendar.feature',
          'The week survives being saved and reopened')
def test_the_week_survives_a_save():
    pass


@scenario('features/workdaycalendar.feature',
          'The standard week works some weekday')
def test_the_standard_week_works_some_weekday():
    pass


@scenario('features/workdaycalendar.feature',
          'A week with nothing in it does not')
def test_a_week_with_nothing_in_it():
    pass


@scenario('features/workdaycalendar.feature',
          'Assigning a new week is noticed')
def test_assigning_a_new_week_is_noticed():
    pass


@scenario('features/workdaycalendar.feature', 'Assigning back is noticed too')
def test_assigning_back_is_noticed_too():
    pass


@scenario('features/workdaycalendar.feature',
          'Mutating the set in place is noticed')
def test_mutating_the_set_in_place_is_noticed():
    pass


@scenario('features/workdaycalendar.feature',
          'Removing a day in place is noticed')
def test_removing_a_day_in_place_is_noticed():
    pass


@scenario('features/workdaycalendar.feature', 'The week still reads back')
def test_the_week_still_reads_back():
    pass


@scenario('features/workdaycalendar.feature',
          'An iterable is taken as well as a set')
def test_an_iterable_is_taken_as_well_as_a_set():
    pass


@scenario('features/workdaycalendar.feature', 'Scheduling is unchanged')
def test_scheduling_is_unchanged():
    pass


@scenario('features/workdaycalendar.feature', 'Every country is placed')
def test_every_country_is_placed():
    pass


@scenario('features/workdaycalendar.feature',
          'Every code in the table is shaped like one')
def test_every_code_is_shaped_like_one():
    pass


@scenario('features/workdaycalendar.feature',
          'Every region named is one of the regions listed')
def test_every_region_named_is_listed():
    pass


@scenario('features/workdaycalendar.feature',
          'Every region has somebody in it')
def test_every_region_has_somebody_in_it():
    pass


@scenario('features/workdaycalendar.feature',
          'A subdivision is placed by its country')
def test_a_subdivision_is_placed_by_its_country():
    pass


@scenario('features/workdaycalendar.feature',
          'An unknown code falls back rather than raising')
def test_an_unknown_code_falls_back():
    pass


@scenario('features/workdaycalendar.feature',
          'A lowercase code is still found')
def test_a_lowercase_code_is_still_found():
    pass


@scenario('features/workdaycalendar.feature',
          'The EU members are all in Europe')
def test_the_eu_members_are_all_in_europe():
    pass


# ---- calendar Givens ----------------------------------------------------------


@given('the standard week')
def the_standard_week(ctx):
    ctx.calendar = WorkingCalendar()


@given('a second standard week ruled worked on "2026-09-12"')
def a_second_standard_week(ctx):
    ctx.second_cal = WorkingCalendar()
    ctx.second_cal.add_override(date(2026, 9, 12), True)


@given(parsers.parse('a calendar with a holiday on "{iso}"'))
def a_calendar_with_a_holiday(ctx, iso):
    ctx.calendar = WorkingCalendar(holidays={date.fromisoformat(iso)})


@given(parsers.parse('a calendar with a recurring holiday on "{pair}"'))
def a_calendar_with_a_recurring_holiday(ctx, pair):
    month, day = (int(part) for part in pair.split('-'))
    ctx.calendar = WorkingCalendar(recurring_holidays={(month, day)})


@given(parsers.parse('a calendar resting on weekdays "{days}"'))
def a_calendar_resting_on(ctx, days):
    ctx.calendar = WorkingCalendar(non_working_days=_days(days))


@given(parsers.parse('a calendar resting on weekdays "{days}" with a holiday '
                     'on "{iso}" and recurring holidays "{pairs}"'))
def a_calendar_resting_full(ctx, days, iso, pairs):
    ctx.calendar = WorkingCalendar(
        non_working_days=_days(days),
        holidays={date.fromisoformat(iso)},
        recurring_holidays=_recurring(pairs))


@given(parsers.parse('a calendar observing "{codes}"'))
def a_calendar_observing(ctx, codes):
    ctx.calendar = WorkingCalendar(countries=codes.split(', '))


@given('a calendar observing nobody')
def a_calendar_observing_nobody(ctx):
    ctx.calendar = WorkingCalendar(countries=[])


@given(parsers.parse('a second calendar observing "{codes}"'))
def a_second_calendar_observing(ctx, codes):
    ctx.second_cal = WorkingCalendar(countries=codes.split(', '))


@given('a calendar observing "HU" that cannot resolve any')
def a_calendar_that_cannot_resolve(ctx, monkeypatch):
    monkeypatch.setattr('gantt_app.core.workdaycalendar.country_holidays',
                        lambda *a, **k: set())
    ctx.calendar = WorkingCalendar(countries=["HU"])


# ---- project Givens ---------------------------------------------------------


@given(parsers.parse('a project named "{name}" on a calendar with a holiday '
                     'on "{iso}"'))
def a_project_on_a_calendar(ctx, name, iso):
    ctx.project = Project(
        name=name,
        calendar=WorkingCalendar(holidays={date.fromisoformat(iso)}))


@given(parsers.parse('a project named "{name}" on a calendar observing '
                     '"{codes}"'))
def a_project_on_countries(ctx, name, codes):
    ctx.project = Project(
        name=name,
        calendar=WorkingCalendar(countries=codes.split(', ')))


@given('a saved project with no calendar block')
def a_saved_project_with_no_calendar(ctx):
    data = Project(name="Old").to_dict()
    del data['calendar']
    ctx.reloaded = Project.from_dict(data)


@given(parsers.parse('a project named "{name}" holding "{task_id}" from '
                     '"{start}" to "{end}"'))
def a_project_holding_task(ctx, name, task_id, start, end):
    ctx.project = Project(name=name)
    ctx.project.add_task(Task(id=task_id, name=task_id,
                              start_date=d(start), end_date=d(end)))


@given(parsers.parse('a project named "{name}" observing "{codes}" holding '
                     '"{task_id}" from "{start}" to "{end}"'))
def a_project_observing_holding(ctx, name, codes, task_id, start, end):
    ctx.project = Project(
        name=name,
        calendar=WorkingCalendar(countries=codes.split(', ')))
    ctx.project.add_task(Task(id=task_id, name=task_id,
                              start_date=d(start), end_date=d(end)))


@given(parsers.parse('a project named "{name}" holding a milestone "{task_id}" '
                     'on "{iso}"'))
def a_project_holding_milestone(ctx, name, task_id, iso):
    ctx.project = Project(name=name)
    ctx.project.add_task(Task(id=task_id, name=task_id, start_date=d(iso),
                              is_milestone=True))


@given(parsers.parse('a project named "{name}" observing "{codes}"'))
def a_project_observing(ctx, name, codes):
    ctx.project = Project(name=name)
    ctx.project.set_holiday_countries(codes.split(', '))


@given(parsers.parse('a project named "{name}"'))
def a_project_named(ctx, name):
    ctx.project = Project(name=name)


# ---- standalone CalendarTask / Task Givens -------------------------------------


@given(parsers.parse('a calendar task "{name}" of {days:d} days from "{iso}"'))
@given(parsers.parse('a calendar task "{name}" of {days:d} day from "{iso}"'))
def a_calendar_task(ctx, name, days, iso):
    ctx.task = CalendarTask(id="T", name=name, duration_days=days,
                            start_date=date.fromisoformat(iso))


@given(parsers.parse('a task "{task_id}" from "{start}" to "{end}"'))
def a_model_task(ctx, task_id, start, end):
    ctx.task = Task(id=task_id, name=task_id, start_date=d(start),
                    end_date=d(end))


@given(parsers.parse('a milestone "{task_id}" on "{iso}"'))
def a_model_milestone(ctx, task_id, iso):
    ctx.task = Task(id=task_id, name=task_id, start_date=d(iso),
                    is_milestone=True)


# ---- enforcement Givens ----------------------------------------------------------


@given(parsers.parse('an enforcement project holding "{task_id}" from '
                     '"{start}" to "{end}"'))
def an_enforcement_project(ctx, task_id, start, end):
    ctx.project = Project(name="Enforcement")
    ctx.project.add_task(Task(id=task_id, name=task_id, start_date=d(start),
                              end_date=d(end)))


@given(parsers.parse('an enforcement project holding "{task_id}" from '
                     '"{start}" to "{end}" with duration {days:d}'))
def an_enforcement_project_with_duration(ctx, task_id, start, end, days):
    an_enforcement_project(ctx, task_id, start, end)
    ctx.project.get_task_by_id(task_id).duration = days


@given(parsers.parse('an enforcement project holding a milestone "{task_id}" '
                     'on "{iso}"'))
def an_enforcement_project_milestone(ctx, task_id, iso):
    ctx.project = Project(name="Enforcement")
    ctx.project.add_task(Task(id=task_id, name=task_id, start_date=d(iso),
                              is_milestone=True))


@given('an enforcement project holding phase "P" and child "C" astride '
       'a weekend')
def an_enforcement_project_with_phase(ctx):
    ctx.project = Project(name="Enforcement")
    ctx.project.add_task(Task(id="P", name="P", start_date=d("2026-01-03"),
                              end_date=d("2026-01-11"), task_type="Phase"))
    ctx.project.add_task(Task(id="C", name="C", start_date=d("2026-01-03"),
                              end_date=d("2026-01-09"), task_type="Subtask",
                              parent_task_id="P"))


@given(parsers.parse('an enforcement project with a holiday on "{iso}"'))
def an_enforcement_project_on_holiday_calendar(ctx, iso):
    ctx.project = Project(name="Enforcement")
    ctx.project.calendar = WorkingCalendar(holidays={d(iso)})


@given(parsers.parse('it holds "{task_id}" from "{start}" to "{end}" '
                     'with duration {days:d}'))
def it_holds_a_task(ctx, task_id, start, end, days):
    ctx.project.add_task(Task(id=task_id, name=task_id, start_date=d(start),
                              end_date=d(end), duration=days))


@given('a four-day task on the standard week')
def a_four_day_task(ctx):
    ctx.project = Project(name="Week")
    ctx.project.add_task(Task(id="A", name="A", start_date=d("2026-09-11"),
                              end_date=d("2026-09-16")))
    ctx.project.reschedule()


# ---- ruling Givens/Whens -------------------------------------------------------


@given(parsers.parse('"{iso}" was ruled worked as "{reason}"'))
def was_ruled_worked_as(ctx, iso, reason):
    ctx.calendar.add_override(_moment(iso), True, reason)


@given(parsers.parse('"{iso}" was ruled worked'))
def was_ruled_worked(ctx, iso):
    ctx.calendar.add_override(_moment(iso), True)


@given(parsers.parse('"{iso}" was ruled off as "{reason}"'))
def was_ruled_off_as(ctx, iso, reason):
    ctx.calendar.add_override(_moment(iso), False, reason)


@given(parsers.parse('"{iso}" was ruled worked on the plan'))
def was_ruled_worked_on_the_plan(ctx, iso):
    ctx.project.set_date_overrides([DateOverride(_moment(iso), True)])


@given(parsers.parse('"{iso}" was ruled off as "{reason}" on the plan'))
def was_ruled_off_on_the_plan(ctx, iso, reason):
    ctx.project.set_date_overrides([DateOverride(_moment(iso), False, reason)])


@given(parsers.parse('the plan observes "{codes}"'))
@when(parsers.parse('the plan observes "{codes}"'))
def the_plan_observes(ctx, codes):
    ctx.project.set_holiday_countries(codes.split(', '))


@when('the plan observes nobody')
def the_plan_observes_nobody(ctx):
    ctx.project.set_holiday_countries([])


@when(parsers.parse('"{iso}" is ruled worked as "{reason}"'))
def is_ruled_worked_as(ctx, iso, reason):
    ctx.calendar.add_override(_moment(iso), True, reason)


@when(parsers.parse('"{iso}" is ruled worked'))
def is_ruled_worked(ctx, iso):
    ctx.calendar.add_override(_moment(iso), True)


@when(parsers.parse('"{iso}" is ruled off as "{reason}"'))
def is_ruled_off_as(ctx, iso, reason):
    ctx.calendar.add_override(_moment(iso), False, reason)


@when(parsers.parse('"{iso}" is ruled off as "{reason}" on the plan'))
def is_ruled_off_on_the_plan(ctx, iso, reason):
    ctx.project.set_date_overrides([DateOverride(_moment(iso), False, reason)])


@when(parsers.parse('"{iso}" is ruled worked on the plan'))
def is_ruled_worked_on_the_plan(ctx, iso):
    ctx.project.set_date_overrides([DateOverride(_moment(iso), True)])


# ---- Whens ----------------------------------------------------------------------


@when(parsers.parse('the calendar observes "{codes}"'))
def the_calendar_observes(ctx, codes):
    ctx.calendar.set_countries(codes.split(', '))


@when('the calendar is enforced')
def the_calendar_is_enforced(ctx):
    ctx.moved = ctx.project.enforce_working_calendar()


@when('the plan is rescheduled')
def the_plan_is_rescheduled(ctx):
    ctx.project.reschedule()


@when('it is saved and reloaded')
def it_is_saved_and_reloaded(ctx):
    ctx.reloaded = Project.from_dict(ctx.project.to_dict())


@when('the calendar is saved and reloaded')
def the_calendar_is_saved_and_reloaded(ctx):
    ctx.reloaded_cal = WorkingCalendar.from_dict(ctx.calendar.to_dict())


@when(parsers.parse('the week rests on "{days}"'))
def the_week_rests_on(ctx, days):
    ctx.week_answer = ctx.project.set_working_week(_days(days))


@when(parsers.parse('the calendar rests on "{days}"'))
def the_calendar_rests_on(ctx, days):
    ctx.calendar.non_working_days = _days(days)


@when(parsers.parse('the calendar rests on the list "{days}"'))
def the_calendar_rests_on_a_list(ctx, days):
    ctx.calendar.non_working_days = [int(part) for part in days.split(', ')]


@when('every weekday is added to the rest days in place')
def every_weekday_added_in_place(ctx):
    for day in range(7):
        ctx.calendar.non_working_days.add(day)


@when(parsers.parse('weekday {day:d} is taken off the rest days in place'))
def a_weekday_taken_off_in_place(ctx, day):
    ctx.calendar.non_working_days.discard(day)


# ---- Thens: worked / not worked -------------------------------------------------


@then(parsers.parse('"{iso}" is worked'))
def is_worked(ctx, iso):
    assert ctx.calendar.is_working_day(_moment(iso))


@then(parsers.parse('"{iso}" is not worked'))
def is_not_worked(ctx, iso):
    assert not ctx.calendar.is_working_day(_moment(iso))


@then(parsers.parse('"{start}" through "{end}" are all worked'))
def through_are_all_worked(ctx, start, end):
    day = date.fromisoformat(start)
    last = date.fromisoformat(end)
    while day <= last:
        assert ctx.calendar.is_working_day(day), day
        day += timedelta(days=1)


@then(parsers.parse('"{iso}" is worked on the first'))
def is_worked_on_the_first(ctx, iso):
    assert ctx.calendar.is_working_day(_moment(iso))


@then(parsers.parse('"{iso}" is worked on the second'))
def is_worked_on_the_second(ctx, iso):
    assert ctx.second_cal.is_working_day(_moment(iso))


@then(parsers.parse('"{iso}" is not worked on the second'))
def is_not_worked_on_the_second(ctx, iso):
    assert not ctx.second_cal.is_working_day(_moment(iso))


@then(parsers.parse('"{iso}" is worked on the plan'))
def is_worked_on_the_plan(ctx, iso):
    assert ctx.project.calendar.is_working_day(_moment(iso))


@then(parsers.parse('"{iso}" is not worked on the plan'))
def is_not_worked_on_the_plan(ctx, iso):
    assert not ctx.project.calendar.is_working_day(_moment(iso))


@then(parsers.parse('"{iso}" is worked on the reloaded'))
def is_worked_on_the_reloaded(ctx, iso):
    cal = ctx.reloaded_cal if ctx.reloaded_cal else ctx.reloaded.calendar
    assert cal.is_working_day(_moment(iso))


@then(parsers.parse('"{iso}" is not worked on the reloaded'))
def is_not_worked_on_the_reloaded(ctx, iso):
    cal = ctx.reloaded_cal if ctx.reloaded_cal else ctx.reloaded.calendar
    assert not cal.is_working_day(_moment(iso))


# ---- Thens: walking ------------------------------------------------------------


@then(parsers.parse('the next working day after "{iso}" is "{expected}"'))
def the_next_working_day(ctx, iso, expected):
    assert ctx.calendar.get_next_working_day(_moment(iso)) == \
        date.fromisoformat(expected)


@then(parsers.parse('the next working moment after "{iso}" is "{expected}"'))
def the_next_working_moment(ctx, iso, expected):
    assert ctx.calendar.get_next_working_day(_moment(iso)) == \
        datetime.fromisoformat(expected)


@then(parsers.parse('the previous working day before "{iso}" is "{expected}"'))
def the_previous_working_day(ctx, iso, expected):
    assert ctx.calendar.get_previous_working_day(_moment(iso)) == \
        date.fromisoformat(expected)


@then(parsers.parse('{count:d} working days from "{iso}" land on "{expected}"'))
@then(parsers.parse('{count:d} working day from "{iso}" lands on "{expected}"'))
def working_days_from(ctx, count, iso, expected):
    assert ctx.calendar.add_working_days(
        _moment(iso), count) == date.fromisoformat(expected)


@then(parsers.parse('{count:d} working days from "{iso}" land on "{expected}" '
                    'on the second'))
def working_days_from_on_the_second(ctx, count, iso, expected):
    assert ctx.second_cal.add_working_days(
        _moment(iso), count) == date.fromisoformat(expected)


@then(parsers.parse('{count:d} working days back from "{iso}" land on '
                    '"{expected}"'))
def working_days_back_from(ctx, count, iso, expected):
    assert ctx.calendar.subtract_working_days(
        _moment(iso), count) == date.fromisoformat(expected)


# ---- Thens: measuring ------------------------------------------------------------


@then(parsers.parse('"{start}" to "{end}" holds {count:d} days of work'))
@then(parsers.parse('"{start}" to "{end}" holds {count:d} day of work'))
def holds_days_of_work(ctx, start, end, count):
    assert ctx.calendar.working_days_between(
        _moment(start), _moment(end)) == count


@then(parsers.parse('"{start}" to "{end}" spans {count:d} days'))
@then(parsers.parse('"{start}" to "{end}" spans {count:d} day'))
def spans_days(ctx, start, end, count):
    assert ctx.calendar.elapsed_days(_moment(start), _moment(end)) == count


@then(parsers.parse('measuring and adding agree for {limit:d} days from '
                    '"{iso}"'))
def measuring_and_adding_agree(ctx, limit, iso):
    start = _moment(iso)
    for offset in range(0, limit):
        end = start + timedelta(days=offset)
        worked = ctx.calendar.working_days_between(start, end)
        if worked == 0:
            continue
        assert ctx.calendar.working_days_between(
            start, ctx.calendar.add_working_days(start, worked)) == worked


# ---- Thens: storage -----------------------------------------------------------------


@then('it round-trips through a save')
def it_round_trips(ctx):
    assert WorkingCalendar.from_dict(ctx.calendar.to_dict()) == ctx.calendar


@then('a missing calendar loads as the standard week')
def a_missing_calendar_loads():
    assert WorkingCalendar.from_dict(None) == WorkingCalendar()


@then('an empty calendar loads as the standard week')
def an_empty_calendar_loads():
    assert WorkingCalendar.from_dict({}) == WorkingCalendar()


@then(parsers.parse('a damaged calendar loads on weekdays "{days}" with a '
                    'holiday on "{iso}" and a recurring holiday "{pair}"'))
def a_damaged_calendar_loads(ctx, days, iso, pair):
    calendar = WorkingCalendar.from_dict({
        'non_working_days': 'weekends',
        'holidays': ['not a date', iso],
        'recurring_holidays': [['March', 15],
                               [int(p) for p in pair.split('-')]],
    })
    month, day = (int(p) for p in pair.split('-'))
    assert calendar.non_working_days == _days(days)
    assert calendar.holidays == {date.fromisoformat(iso)}
    assert calendar.recurring_holidays == {(month, day)}


@then('the reloaded calendar matches')
def the_reloaded_calendar_matches(ctx):
    assert ctx.reloaded.calendar == ctx.project.calendar


@then('it loads on the standard week')
def it_loads_on_the_standard_week(ctx):
    assert ctx.reloaded.calendar == WorkingCalendar()


@then(parsers.parse('the reloaded calendar observes "{codes}"'))
def the_reloaded_calendar_observes(ctx, codes):
    assert ctx.reloaded.calendar.countries == set(codes.split(', '))


@then('its country list round-trips')
def its_country_list_round_trips(ctx):
    reopened = WorkingCalendar.from_dict(ctx.calendar.to_dict())
    assert reopened.countries == ctx.calendar.countries


@then(parsers.parse('"{code}" resolves to no holidays for {year:d}'))
def resolves_to_no_holidays(code, year):
    assert country_holidays([code], year) == set()


@then(parsers.parse('every EU country resolves for {year:d}'))
def every_eu_country_resolves(year):
    for code in EU_COUNTRIES:
        assert country_holidays([code], year), code


# ---- Thens: standalone tasks ------------------------------------------------------


@then(parsers.parse('it effectively starts "{iso}"'))
def it_effectively_starts(ctx, iso):
    expected = _moment(iso)
    actual = ctx.task.effective_start_date
    if isinstance(actual, datetime) and not isinstance(expected, datetime):
        actual = actual.date()
    assert actual == expected


@then(parsers.parse('it ends "{iso}"'))
def it_ends(ctx, iso):
    expected = _moment(iso)
    actual = ctx.task.end_date
    if isinstance(actual, datetime) and not isinstance(expected, datetime):
        actual = actual.date()
    assert actual == expected


@then(parsers.parse('it holds {days:d} days and spans {elapsed:d}'))
@then(parsers.parse('it holds {days:d} day and spans {elapsed:d}'))
def it_holds_and_spans(ctx, days, elapsed):
    assert ctx.task.duration_days == days
    assert ctx.task.total_elapsed_days == elapsed


@then(parsers.parse('it holds {days:d} day'))
def it_holds_one_day(ctx, days):
    assert ctx.task.duration_days == days


@then('its calendar is the standard one')
def its_calendar_is_standard(ctx):
    assert ctx.task.calendar == default_calendar()


# ---- Thens: enforcement / project tasks ---------------------------------------------


@then('the enforcement moved something')
def the_enforcement_moved(ctx):
    assert ctx.moved


@then('the enforcement changes nothing')
def the_enforcement_changes_nothing(ctx):
    assert not ctx.project.enforce_working_calendar()


@then(parsers.parse('"{task_id}" starts "{iso}"'))
def task_starts(ctx, task_id, iso):
    assert ctx.project.get_task_by_id(task_id).start_date == d(iso)


@then(parsers.parse('"{task_id}" ends "{iso}"'))
def task_ends(ctx, task_id, iso):
    assert ctx.project.get_task_by_id(task_id).end_date == d(iso)


@then(parsers.parse('task "{task_id}" holds {days:d} days of work'))
def task_holds_days(ctx, task_id, days):
    task = ctx.project.get_task_by_id(task_id)
    assert ctx.project.working_duration(task) == days


@then(parsers.parse('task "{task_id}" reads {days:d} days by duration'))
def task_reads_days(ctx, task_id, days):
    assert ctx.project.get_task_by_id(task_id).duration_days == days


# ---- Thens: rulings --------------------------------------------------------------------


@then(parsers.parse('the calendar holds {count:d} ruling'))
@then(parsers.parse('the calendar holds {count:d} rulings'))
def the_calendar_holds_rulings(ctx, count):
    assert len(ctx.calendar.overrides) == count


@then(parsers.parse('the plan\'s calendar holds {count:d} ruling'))
def the_plans_calendar_holds_rulings(ctx, count):
    assert len(ctx.project.calendar.overrides) == count


@then(parsers.parse('the rulings are listed as "{dates}"'))
def the_rulings_are_listed(ctx, dates):
    expected = [date.fromisoformat(iso) for iso in dates.split(', ')]
    assert list(ctx.calendar.overrides) == expected


@then(parsers.parse('removing the "{iso}" ruling answers yes'))
def removing_answers_yes(ctx, iso):
    assert ctx.calendar.remove_override(_moment(iso))


@then(parsers.parse('removing the "{iso}" ruling answers no'))
def removing_answers_no(ctx, iso):
    assert not ctx.calendar.remove_override(_moment(iso))


@then(parsers.parse('the ruling for "{iso}" reads "{reason}"'))
def the_ruling_reads(ctx, iso, reason):
    assert ctx.calendar.override_for(_moment(iso)).reason == reason


@then(parsers.parse('"{iso}" has no ruling'))
def has_no_ruling(ctx, iso):
    assert ctx.calendar.override_for(_moment(iso)) is None


@then('the reloaded calendar equals it')
def the_reloaded_calendar_equals(ctx):
    assert ctx.reloaded_cal == ctx.calendar


@then(parsers.parse('the reloaded ruling for "{iso}" reads "{reason}"'))
def the_reloaded_ruling_reads(ctx, iso, reason):
    assert ctx.reloaded_cal.override_for(_moment(iso)).reason == reason


@then(parsers.parse('the saved rulings list "{dates}"'))
def the_saved_rulings_list(ctx, dates):
    saved = [entry['date'] for entry in ctx.calendar.to_dict()['overrides']]
    assert saved == dates.split(', ')


@then(parsers.parse('a calendar dict of countries "{codes}" holds no rulings'))
def a_calendar_dict_holds_no_rulings(codes):
    calendar = WorkingCalendar.from_dict({'countries': codes.split(', ')})
    assert calendar.overrides == {}


@then(parsers.parse('a damaged overrides list keeps the good row "{iso}"'))
def a_damaged_overrides_list(iso):
    calendar = WorkingCalendar.from_dict({'overrides': [
        {'date': 'the twelfth'},
        'not a dictionary at all',
        {'date': iso, 'is_working_day': True, 'reason': 'kept'},
    ]})
    assert [o.override_date for o in calendar.sorted_overrides()] == \
        [date.fromisoformat(iso)]


@then('the two calendars differ')
def the_two_calendars_differ(ctx):
    assert ctx.calendar != ctx.second_cal


# ---- Thens: the working week -------------------------------------------------------------


@then('the week\'s answer was taken')
def the_weeks_answer_taken(ctx):
    assert ctx.week_answer


@then('the week\'s answer was refused')
def the_weeks_answer_refused(ctx):
    assert not ctx.week_answer


@then(parsers.parse('the plan\'s calendar still rests on "{days}"'))
def the_plans_calendar_rests(ctx, days):
    assert ctx.project.calendar.non_working_days == _days(days)


@then(parsers.parse('the plan\'s calendar still observes "{codes}"'))
def the_plans_calendar_observes(ctx, codes):
    assert ctx.project.calendar.countries == set(codes.split(', '))


@then(parsers.parse('the reloaded calendar rests on "{days}"'))
def the_reloaded_calendar_rests(ctx, days):
    assert ctx.reloaded.calendar.non_working_days == _days(days)


@then('the calendar works some weekday')
def the_calendar_works_some_weekday(ctx):
    assert ctx.calendar.works_any_weekday


@then('the calendar works no weekday')
def the_calendar_works_no_weekday(ctx):
    assert not ctx.calendar.works_any_weekday


@then(parsers.parse('the calendar rests on "{days}"'))
def the_calendar_rests_on_check(ctx, days):
    assert ctx.calendar.non_working_days == _days(days)


@then(parsers.parse('its saved form lists "{days}"'))
def its_saved_form_lists(ctx, days):
    assert ctx.calendar.to_dict()['non_working_days'] == \
        [int(part) for part in days.split(', ')]


# ---- Thens: the region table ---------------------------------------------------------------


@then('every country the package knows is placed')
def every_country_is_placed():
    countries = supported_countries()
    missing = sorted(code for code in countries if code not in COUNTRY_REGIONS)
    assert missing == [], (
        "The holidays package knows countries this table does not, so "
        "they are listed under Other Territories at the bottom of the "
        "picker: "
        + ', '.join(f"{code} ({countries[code]})" for code in missing)
        + ". Add each to the right group in "
          "gantt_app.core.workdaycalendar.COUNTRY_REGIONS.")


@then('every code in the table is two capitals')
def every_code_is_two_capitals():
    for code in COUNTRY_REGIONS:
        assert re.fullmatch(r'[A-Z]{2}', code), code


@then('every region named is in the order')
def every_region_named_is_in_the_order():
    assert set(COUNTRY_REGIONS.values()) - set(REGION_ORDER) == set()


@then('every region in the order has a country')
def every_region_has_a_country():
    for region in REGION_ORDER:
        assert region in COUNTRY_REGIONS.values(), region


@then(parsers.parse('"{code}" sits in "{region}"'))
def code_sits_in(code, region):
    assert region_of(code) == region


@then('a missing code sits in "Other Territories"')
def a_missing_code_sits():
    assert region_of(None) == REGION_OTHER


@then('a blank code sits in "Other Territories"')
def a_blank_code_sits():
    assert region_of('') == REGION_OTHER


@then(parsers.parse('"{a}" sits where "{b}" sits'))
def sits_where(a, b):
    assert region_of(a) == region_of(b)


@then(parsers.parse('every EU member sits in "{region}"'))
def every_eu_member_sits_in(region):
    for code in EU_COUNTRIES:
        assert region_of(code) == region, code
