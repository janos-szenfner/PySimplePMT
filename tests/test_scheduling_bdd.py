"""
BDD steps for tests/features/scheduling.feature - dependency types,
lead/lag, the automatic pass, roll-up and milestone rules. Pure
Project-level behaviour, no display.
"""

import logging
import pytest
from pytest_bdd import given, parsers, scenario, then, when

from datetime import datetime
from types import SimpleNamespace

from gantt_app.core.models import (
    DEPENDENCY_TYPE_LABELS,
    DEPENDENCY_TYPES,
    Dependency,
    Project,
    Task,
)


@pytest.fixture
def ctx():
    return SimpleNamespace(project=None, saved_length=None,
                           before=None, settled=None, caught=None)


def d(iso):
    return datetime.fromisoformat(iso)


def _task(task_id, name, start, end=None, **kwargs):
    return Task(id=task_id, name=name, start_date=d(start),
                end_date=d(end) if end else None, **kwargs)


# ---- scenario bindings ----------------------------------------------------------

@scenario('features/scheduling.feature',
          'Finish-Start follows the predecessor')
def test_finish_to_start_follows_the_predecessor():
    pass


@scenario('features/scheduling.feature', 'Start-Start aligns the starts')
def test_start_to_start_aligns_the_starts():
    pass


@scenario('features/scheduling.feature', 'Finish-Finish aligns the finishes')
def test_finish_to_finish_aligns_the_finishes():
    pass


@scenario('features/scheduling.feature',
          'Start-Finish ends at the predecessor\'s start')
def test_start_to_finish_ends_at_the_predecessor_start():
    pass


@scenario('features/scheduling.feature', 'Duration is preserved')
def test_duration_is_preserved():
    pass


@scenario('features/scheduling.feature', 'Every type is supported')
def test_every_type_is_supported():
    pass


@scenario('features/scheduling.feature',
          'An unknown type falls back to Finish-Start')
def test_an_unknown_type_falls_back():
    pass


@scenario('features/scheduling.feature', 'The labels cover every type')
def test_the_labels_cover_every_type():
    pass


@scenario('features/scheduling.feature',
          'Only the finish types constrain the finish')
def test_only_the_finish_types_constrain_the_finish():
    pass


@scenario('features/scheduling.feature', 'It covers both tasks')
def test_it_covers_both_tasks():
    pass


@scenario('features/scheduling.feature',
          'Its length is the span, not what it used to be')
def test_its_length_is_the_span():
    pass


@scenario('features/scheduling.feature', 'It survives a reschedule')
def test_it_survives_a_reschedule():
    pass


@scenario('features/scheduling.feature',
          'A single link still preserves the length')
def test_a_single_link_still_preserves_the_length():
    pass


@scenario('features/scheduling.feature',
          'A finish required before the start keeps the length')
def test_a_finish_required_before_the_start():
    pass


@scenario('features/scheduling.feature', 'Lag delays the successor')
def test_lag_delays_the_successor():
    pass


@scenario('features/scheduling.feature',
          'A short lag is not swallowed by a weekend')
def test_a_short_lag_is_not_swallowed():
    pass


@scenario('features/scheduling.feature', 'Lead pulls the successor in')
def test_lead_pulls_the_successor_in():
    pass


@scenario('features/scheduling.feature', 'Lag applies to a finish link')
def test_lag_applies_to_a_finish_link():
    pass


@scenario('features/scheduling.feature', 'Lag defaults to none')
def test_lag_defaults_to_none():
    pass


@scenario('features/scheduling.feature', 'A bad lag is treated as zero')
def test_a_bad_lag_is_treated_as_zero():
    pass


@scenario('features/scheduling.feature', 'Lag survives serialisation')
def test_lag_survives_serialisation():
    pass


@scenario('features/scheduling.feature', 'Hard pulls a late task back')
def test_hard_pulls_a_late_task_back():
    pass


@scenario('features/scheduling.feature',
          'Rubber leaves a later task alone')
def test_rubber_leaves_a_later_task_alone():
    pass


@scenario('features/scheduling.feature',
          'A link never leaves a task on a weekend')
def test_a_link_never_leaves_a_task_on_a_weekend():
    pass


@scenario('features/scheduling.feature',
          'Rubber still pushes an early task out')
def test_rubber_still_pushes_an_early_task_out():
    pass


@scenario('features/scheduling.feature',
          'A span updates the stored length')
def test_a_span_updates_the_stored_length():
    pass


@scenario('features/scheduling.feature',
          'A span survives the working-calendar pass')
def test_a_span_survives_the_working_calendar_pass():
    pass


@scenario('features/scheduling.feature',
          'A container ignores a length written onto it')
def test_a_container_ignores_a_length_written_onto_it():
    pass


@scenario('features/scheduling.feature', 'It pushes a task forward')
def test_it_pushes_a_task_forward():
    pass


@scenario('features/scheduling.feature', 'It lands on a working day')
def test_it_lands_on_a_working_day():
    pass


@scenario('features/scheduling.feature', 'It is a floor, not a pin')
def test_it_is_a_floor_not_a_pin():
    pass


@scenario('features/scheduling.feature', 'The task keeps its length')
def test_the_task_keeps_its_length():
    pass


@scenario('features/scheduling.feature', 'A plan with one still settles')
def test_a_plan_with_one_still_settles():
    pass


@scenario('features/scheduling.feature',
          'Finish-Start lands on the milestone date')
def test_finish_start_lands_on_the_milestone_date():
    pass


@scenario('features/scheduling.feature',
          'Start-Start lands on the milestone date')
def test_start_start_lands_on_the_milestone_date():
    pass


@scenario('features/scheduling.feature', 'The chain settles')
def test_the_chain_settles():
    pass


@scenario('features/scheduling.feature',
          'Moving the head moves everything')
def test_moving_the_head_moves_everything():
    pass


@scenario('features/scheduling.feature', 'A settled plan does not move')
def test_a_settled_plan_does_not_move():
    pass


@scenario('features/scheduling.feature', 'A cycle does not hang')
def test_a_cycle_does_not_hang():
    pass


@scenario('features/scheduling.feature',
          'A missing predecessor is ignored')
def test_a_missing_predecessor_is_ignored():
    pass


@scenario('features/scheduling.feature', 'Slack is left alone')
def test_slack_is_left_alone():
    pass


@scenario('features/scheduling.feature', 'A violation is repaired')
def test_a_violation_is_repaired():
    pass


@scenario('features/scheduling.feature',
          'Moving a predecessor later drags the successor')
def test_moving_a_predecessor_later_drags_the_successor():
    pass


@scenario('features/scheduling.feature',
          'Choosing a predecessor still pins exactly')
def test_choosing_a_predecessor_still_pins_exactly():
    pass


@scenario('features/scheduling.feature', 'It spans its children')
def test_it_spans_its_children():
    pass


@scenario('features/scheduling.feature',
          'Progress counts finished sub-tasks')
def test_progress_counts_finished_subtasks():
    pass


@scenario('features/scheduling.feature',
          'A child moving out stretches the parent')
def test_a_child_moving_out_stretches_the_parent():
    pass


@scenario('features/scheduling.feature', 'Nested summaries total upwards')
def test_nested_summaries_total_upwards():
    pass


@scenario('features/scheduling.feature',
          'A childless task keeps its own dates')
def test_a_childless_task_keeps_its_own_dates():
    pass


@scenario('features/scheduling.feature',
          'A link moves a summary by moving what is in it')
def test_a_link_moves_a_summary():
    pass


@scenario('features/scheduling.feature', 'The children move with it')
def test_the_children_move_with_it():
    pass


@scenario('features/scheduling.feature', 'It still spans them afterwards')
def test_it_still_spans_them_afterwards():
    pass


@scenario('features/scheduling.feature',
          'Link-less children follow the collection\'s predecessor')
def test_link_less_children_follow_the_collection_predecessor():
    pass


@scenario('features/scheduling.feature',
          'A child chain sequences from the collection\'s start')
def test_a_child_chain_sequences_from_the_collection_start():
    pass


@scenario('features/scheduling.feature',
          'A plan linked through a summary settles')
def test_a_plan_linked_through_a_summary_settles():
    pass


@scenario('features/scheduling.feature', 'It stays where it landed')
def test_it_stays_where_it_landed():
    pass


@scenario('features/scheduling.feature', 'An end date is cleared')
def test_an_end_date_is_cleared():
    pass


@scenario('features/scheduling.feature',
          'A child is promoted off a milestone')
def test_a_child_is_promoted_off_a_milestone():
    pass


@scenario('features/scheduling.feature', 'A milestone has no duration')
def test_a_milestone_has_no_duration():
    pass


@scenario('features/scheduling.feature', 'A milestone is not a summary')
def test_a_milestone_is_not_a_summary():
    pass


@scenario('features/scheduling.feature', 'No links constrain nothing')
def test_no_links_constrain_nothing():
    pass


@scenario('features/scheduling.feature',
          'A start link returns only a start')
def test_a_start_link_returns_only_a_start():
    pass


@scenario('features/scheduling.feature',
          'A finish link returns only a finish')
def test_a_finish_link_returns_only_a_finish():
    pass


@scenario('features/scheduling.feature', 'The latest hard link wins')
def test_the_latest_hard_link_wins():
    pass


@scenario('features/scheduling.feature',
          'A start link wins over a finish link')
def test_a_start_link_wins_over_a_finish_link():
    pass


# ---- fixtures -------------------------------------------------------------


@given('a scheduling pair')
def a_scheduling_pair(ctx):
    """A predecessor running 1-5 January and a successor, unlinked."""
    ctx.project = Project(name="Test Project")
    ctx.project.add_task(_task("A", "First", "2026-01-01", "2026-01-05"))
    ctx.project.add_task(_task("B", "Second", "2026-01-01", "2026-01-03"))


@given('a scheduling pair and a span row')
def a_pair_and_a_span(ctx):
    """Two tasks running back to back, and a row spanning both."""
    a_scheduling_pair(ctx)
    second = ctx.project.get_task_by_id("B")
    second.start_date = d("2026-01-06")
    second.end_date = d("2026-01-09")
    ctx.project.add_task(_task("D", "Span", "2026-01-01", "2026-01-05",
                               task_type="Task"))


@given('a scheduling pair with slack')
def a_pair_with_slack(ctx):
    """A predecessor and a successor with a deliberate gap between."""
    ctx.project = Project(name="Test Project")
    ctx.project.add_task(_task("A", "First", "2026-01-01", "2026-01-05"))
    second = _task("B", "Second", "2026-01-12", "2026-01-15")
    second.add_dependency("A", 'FS', 'Hard')
    ctx.project.add_task(second)


@given('a phase "P" holding "T" into late January')
def a_phase_holding_work(ctx):
    ctx.project = Project(name="Container")
    ctx.project.add_task(_task("P", "Phase", "2026-01-05", "2026-01-09",
                               task_type="Phase"))
    ctx.project.add_task(_task("T", "Work", "2026-01-05", "2026-01-30",
                               task_type="Subtask", parent_task_id="P"))


@given(parsers.parse('a chain of "{names}" rescheduled'))
def a_chain_rescheduled(ctx, names):
    """Tasks linked Finish-Start, settled once."""
    ctx.project = Project(name="Test Project")
    previous = None
    for name in names.split(', '):
        task = _task(name, name, "2026-01-01", "2026-01-03")
        if previous:
            task.add_dependency(previous, 'FS', 'Hard')
        ctx.project.add_task(task)
        previous = name
    ctx.project.reschedule()


@given('a cyclic project')
def a_cyclic_project(ctx):
    ctx.project = Project(name="Cyclic")
    first = _task("X", "X", "2026-01-01", "2026-01-02")
    second = _task("Y", "Y", "2026-01-01", "2026-01-02")
    first.add_dependency("Y", 'FS', 'Hard')
    second.add_dependency("X", 'FS', 'Hard')
    ctx.project.add_task(first)
    ctx.project.add_task(second)


@given('a phase of "One" and "Two"')
def a_phase_of_one_and_two(ctx):
    """A parent with two children of differing spans and progress."""
    ctx.project = Project(name="Test Project")
    ctx.project.add_task(_task("P1", "Phase", "2026-06-01", "2026-06-02"))
    ctx.project.add_task(_task("C1", "One", "2026-01-01", "2026-01-10",
                               progress=100, task_type="Subtask",
                               parent_task_id="P1"))
    ctx.project.add_task(_task("C2", "Two", "2026-01-05", "2026-01-24",
                               task_type="Subtask", parent_task_id="P1"))


@given('a phase of "One" and "Two" preceded by "Z" in September')
def a_phase_preceded_by_z(ctx):
    a_phase_of_one_and_two(ctx)
    ctx.project.add_task(_task("Z", "Z", "2026-09-01", "2026-09-05"))
    ctx.project.get_task_by_id("P1").add_dependency("Z", 'FS', 'Hard')


@given('a nested project')
def a_nested_project(ctx):
    ctx.project = Project(name="Nested")
    ctx.project.add_task(_task("TOP", "Top", "2026-01-01", "2026-01-02"))
    ctx.project.add_task(_task("MID", "Mid", "2026-01-01", "2026-01-02",
                               task_type="Subtask", parent_task_id="TOP"))
    ctx.project.add_task(_task("LEAF", "Leaf", "2026-04-01", "2026-04-30",
                               task_type="Subtask", parent_task_id="MID"))


@given('a milestone "M" with a stray child "S"')
def a_milestone_with_a_stray_child(ctx):
    ctx.project = Project(name="Test Project")
    ctx.project.add_task(_task("M", "Sign-off", "2026-01-01",
                               is_milestone=True))
    ctx.project.add_task(_task("S", "Child", "2026-01-01", "2026-01-03",
                               task_type="Subtask", parent_task_id="M"))


# ---- Givens on a task -----------------------------------------------------


@given(parsers.parse('"{name}" is re-dated "{start}" to "{end}"'))
def is_re_dated(ctx, name, start, end):
    task = ctx.project.get_task_by_id(name)
    task.start_date = d(start)
    task.end_date = d(end)


@given(parsers.parse('"{name}" is re-dated its end to "{end}"'))
@when(parsers.parse('"{name}" is re-dated its end to "{end}"'))
def is_re_dated_its_end(ctx, name, end):
    ctx.project.get_task_by_id(name).end_date = d(end)


@given(parsers.parse('"{name}" holds its length'))
def holds_its_length(ctx, name):
    task = ctx.project.get_task_by_id(name)
    ctx.saved_length = ctx.project.working_duration(task)


@given(parsers.parse('"{name}" is a milestone on "{iso}"'))
def is_a_milestone_on(ctx, name, iso):
    task = ctx.project.get_task_by_id(name)
    task.is_milestone = True
    task.end_date = None
    task.start_date = d(iso)


@given(parsers.parse('"{name}" carries a stored duration of {days:d}'))
def carries_a_stored_duration(ctx, name, days):
    ctx.project.get_task_by_id(name).duration = days


@given(parsers.parse('"{name}" is given a stale duration of {days:d}'))
@when(parsers.parse('"{name}" is given a stale duration of {days:d}'))
def is_given_a_stale_duration(ctx, name, days):
    ctx.project.get_task_by_id(name).duration = days


@given(parsers.parse('"{name}" is given an end of "{iso}"'))
def is_given_an_end(ctx, name, iso):
    ctx.project.get_task_by_id(name).end_date = d(iso)


@given(parsers.parse('"{name}" has a floor of "{iso}"'))
def has_a_floor(ctx, name, iso):
    task = ctx.project.get_task_by_id(name)
    task.constraint_type = 'SNET'
    task.constraint_date = d(iso)


@given(parsers.parse('"{name}" waits "{dep_type}" "{hardness}" on "{pid}"'))
def waits_on(ctx, name, dep_type, hardness, pid):
    """A dependency added without applying - for raw constraint reads."""
    ctx.project.get_task_by_id(name).add_dependency(pid, dep_type, hardness)


@given(parsers.parse('"{name}" also waits on "{pid}"'))
def also_waits_on(ctx, name, pid):
    ctx.project.get_task_by_id(name).add_dependency(pid, 'FS', 'Hard')


@given(parsers.parse('"{name}" spanned "{a}" to "{b}"'))
def spanned(ctx, name, a, b):
    """The two links applied - the Given twin of the spanning When."""
    spans(ctx, name, a, b)


@given(parsers.parse('a third task running "{start}" to "{end}"'))
def a_third_task(ctx, start, end):
    ctx.project.add_task(_task("C", "Third", start, end))


@given('the children note their starts')
def the_children_note_their_starts(ctx):
    ctx.before = {task_id: ctx.project.get_task_by_id(task_id).start_date
                  for task_id in ("C1", "C2")}


# ---- Whens -----------------------------------------------------------------


@when(parsers.parse('"{name}" waits "{dep_type}" "{hardness}" lag {lag} '
                    'on "{pid}"'))
def waits_with_lag(ctx, name, dep_type, hardness, lag, pid):
    """Link and apply - the way the dialog does it."""
    task = ctx.project.get_task_by_id(name)
    task.dependencies = []
    task.add_dependency(pid, dep_type, hardness, int(lag))
    ctx.project.apply_dependency_constraints(task)


@when(parsers.parse('"{name}" also waits "{dep_type}" "{hardness}" '
                    'lag {lag} on "{pid}"'))
def also_waits_with_lag(ctx, name, dep_type, hardness, lag, pid):
    task = ctx.project.get_task_by_id(name)
    task.add_dependency(pid, dep_type, hardness, int(lag))
    ctx.project.apply_dependency_constraints(task)


@when(parsers.parse('"{name}" spans "{a}" to "{b}"'))
def spans(ctx, name, a, b):
    """Start with the first, finish with the last - a span by two links."""
    task = ctx.project.get_task_by_id(name)
    task.add_dependency(a, 'SS', 'Hard')
    ctx.project.apply_dependency_constraints(task)
    task.add_dependency(b, 'FF', 'Hard')
    ctx.project.apply_dependency_constraints(task)


@when('the plan is rescheduled')
def the_plan_is_rescheduled(ctx):
    ctx.project.reschedule()


@when(parsers.parse('"{name}" is moved to "{start}" to "{end}"'))
def is_moved(ctx, name, start, end):
    is_re_dated(ctx, name, start, end)


@when(parsers.parse('"{name}" is pinned by its link'))
@when(parsers.parse('"{name}" is pinned by its links'))
def is_pinned(ctx, name):
    task = ctx.project.get_task_by_id(name)
    ctx.project.apply_dependency_constraints(task)


@when('it is rescheduled three more times')
def rescheduled_three_more_times(ctx):
    ctx.settled = {t.id: (t.start_date, t.end_date)
                   for t in ctx.project.tasks}
    for _ in range(3):
        ctx.project.reschedule()


@when('the plan is rescheduled with logging')
def rescheduled_with_logging(ctx):
    logger = logging.getLogger('gantt_app.core.models')
    handler = _Capture()
    logger.addHandler(handler)
    try:
        ctx.project.reschedule()
    finally:
        logger.removeHandler(handler)
    ctx.caught = handler


class _Capture(logging.Handler):
    def __init__(self):
        super().__init__(level='WARNING')
        self.records = []

    def emit(self, record):
        self.records.append(record.getMessage())


# ---- Thens -----------------------------------------------------------------


@then(parsers.parse('"{name}" starts "{iso}"'))
def starts(ctx, name, iso):
    assert ctx.project.get_task_by_id(name).start_date == d(iso)


@then(parsers.parse('"{name}" ends "{iso}"'))
def ends(ctx, name, iso):
    assert ctx.project.get_task_by_id(name).end_date == d(iso)


@then(parsers.parse('"{name}" starts after "{other}" ends'))
def starts_after(ctx, name, other):
    task = ctx.project.get_task_by_id(name)
    anchor = ctx.project.get_task_by_id(other)
    assert task.start_date > anchor.end_date


@then(parsers.parse('"{name}" still holds that length'))
def still_holds_that_length(ctx, name):
    task = ctx.project.get_task_by_id(name)
    assert ctx.project.working_duration(task) == ctx.saved_length


@then(parsers.parse('"{name}" holds {days:d} days of work'))
def holds_days_of_work(ctx, name, days):
    task = ctx.project.get_task_by_id(name)
    assert ctx.project.working_duration(task) == days


@then(parsers.parse('"{name}" holds its span as days of work'))
def holds_its_span(ctx, name):
    task = ctx.project.get_task_by_id(name)
    assert ctx.project.working_duration(task) == \
        ctx.project.calendar.working_days_between(task.start_date,
                                                  task.end_date)


@then(parsers.parse('"{name}" does not end before it starts'))
def does_not_end_before_it_starts(ctx, name):
    task = ctx.project.get_task_by_id(name)
    assert task.end_date >= task.start_date


@then(parsers.parse('"{name}"\'s stored duration matches its span'))
def stored_duration_matches_span(ctx, name):
    task = ctx.project.get_task_by_id(name)
    assert task.duration == ctx.project.calendar.working_days_between(
        task.start_date, task.end_date)


@then(parsers.parse('"{name}" reads {days:d} days by duration'))
def reads_days_by_duration(ctx, name, days):
    assert ctx.project.get_task_by_id(name).duration_days == days


@then(parsers.parse('"{name}" reads {pct:d} percent'))
def reads_percent(ctx, name, pct):
    assert ctx.project.get_task_by_id(name).progress == pct


@then('each dependency type round-trips')
def each_type_round_trips():
    for dep_type in DEPENDENCY_TYPES:
        assert Dependency("A", dep_type).dep_type == dep_type


@then(parsers.parse('a "{code}" link reads as "{dep_type}"'))
def a_code_reads_as(code, dep_type):
    assert Dependency("A", code).dep_type == dep_type


@then('each type has a label')
def each_type_has_a_label():
    assert set(DEPENDENCY_TYPE_LABELS) == set(DEPENDENCY_TYPES)


@then(parsers.parse('"{t1}" and "{t2}" hold the finish but "{t3}" and '
                    '"{t4}" do not'))
def only_finish_types_hold(t1, t2, t3, t4):
    assert Dependency("A", t1).constrains_finish
    assert Dependency("A", t2).constrains_finish
    assert not Dependency("A", t3).constrains_finish
    assert not Dependency("A", t4).constrains_finish


@then('a link with no lag stated has none')
def a_link_with_no_lag():
    assert Dependency("A").lag == 0


@then(parsers.parse('a "{junk}" lag reads as 0'))
def a_bad_lag_reads_as_zero(junk):
    assert Dependency("A", 'FS', 'Hard', junk).lag == 0


@then(parsers.parse('a lag of {lag:d} round-trips'))
def a_lag_round_trips(lag):
    link = Dependency("A", 'FS', 'Hard', lag)
    assert Dependency.from_any(link.to_dict()).lag == lag


@then('rescheduling settles')
def rescheduling_settles(ctx):
    assert not ctx.project.reschedule(), "the plan did not settle"


@then(parsers.parse('the starts are "{mapping}"'))
def the_starts_are(ctx, mapping):
    expected = {key: d(value) for key, value in
                (pair.split('=') for pair in mapping.split(', '))}
    actual = {t.id: t.start_date for t in ctx.project.tasks}
    assert actual == expected


@then(parsers.parse('the project holds {count:d} tasks'))
def the_project_holds_tasks(ctx, count):
    assert len(ctx.project.tasks) == count


@then(parsers.parse('"{name}" is constrained to "{start}" and "{end}"'))
def is_constrained_to(ctx, name, start, end):
    task = ctx.project.get_task_by_id(name)
    actual = ctx.project.constrained_dates(task)
    assert actual == (None if start == "none" else d(start),
                      None if end == "none" else d(end))


@then(parsers.parse('"{name}" has no parent and is a "{task_type}"'))
def has_no_parent(ctx, name, task_type):
    task = ctx.project.get_task_by_id(name)
    assert task.parent_task_id is None
    assert task.task_type == task_type


@then(parsers.parse('"{name}" is not a summary'))
def is_not_a_summary(ctx, name):
    assert name not in ctx.project.get_summary_task_ids()


@then(parsers.parse('"{a}" and "{b}" start together after "{z}" ends'))
def start_together_after(ctx, a, b, z):
    first = ctx.project.get_task_by_id(a)
    second = ctx.project.get_task_by_id(b)
    anchor = ctx.project.get_task_by_id(z)
    assert first.start_date == second.start_date
    assert first.start_date > anchor.end_date


@then(parsers.parse('"{a}" starts with "{b}"'))
def starts_with(ctx, a, b):
    assert ctx.project.get_task_by_id(a).start_date == \
        ctx.project.get_task_by_id(b).start_date


@then(parsers.parse('"{a}" and "{b}" were not left behind'))
def were_not_left_behind(ctx, a, b):
    for task_id in (a, b):
        was = ctx.before[task_id]
        now = ctx.project.get_task_by_id(task_id).start_date
        assert now > was, f"{task_id} was left behind"


@then(parsers.parse('"{p}" brackets "{a}" and "{b}"'))
def brackets(ctx, p, a, b):
    parent = ctx.project.get_task_by_id(p)
    children = [ctx.project.get_task_by_id(i) for i in (a, b)]
    assert parent.start_date == min(c.start_date for c in children)
    assert parent.end_date == max(c.end_date for c in children)


@then(parsers.parse('no "{text}" warning was logged'))
def no_warning_logged(ctx, text):
    assert [r for r in ctx.caught.records if text in r] == []


@then('the dates did not creep')
def the_dates_did_not_creep(ctx):
    assert {t.id: (t.start_date, t.end_date)
            for t in ctx.project.tasks} == ctx.settled
