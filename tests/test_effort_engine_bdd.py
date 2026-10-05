"""
BDD steps for tests/features/effort_engine.feature - the Task Type /
Effort-Driven engine's maths (Task_Type_FRS section 9), pure numbers.
"""

import pytest
from pytest_bdd import given, parsers, scenario, then, when

from datetime import datetime
from types import SimpleNamespace

from gantt_app.core.effort import (
    Assignment,
    EditConflict,
    EffortState,
    add_resource,
    change_effort_type,
    classify_changes,
    days_to_hours,
    edit_duration,
    edit_units,
    edit_work,
    hours_to_days,
    effort_driven_effective,
    logic_applies,
    recalculate,
    reconcile,
    remove_resource,
    set_effort_driven,
    state_from_task,
    validate,
    write_state_to_task,
)
from gantt_app.core.models import (
    EFFORT_FIXED_DURATION,
    EFFORT_FIXED_UNITS,
    EFFORT_FIXED_WORK,
    Task,
)

TYPES = {
    'Fixed Units': EFFORT_FIXED_UNITS,
    'Fixed Duration': EFFORT_FIXED_DURATION,
    'Fixed Work': EFFORT_FIXED_WORK,
}


@pytest.fixture
def ctx():
    return SimpleNamespace(state=None, task=None, result=None,
                           conflict=None, old=None, new=None)


# ---- conversions ---------------------------------------------------------

@scenario('features/effort_engine.feature', 'A day is eight hours')
def test_a_day_is_eight_hours():
    pass


# ---- 9.1 Fixed Units, effort-driven ----------------------------------------

@scenario('features/effort_engine.feature', '9.1 - work preserved, duration halves')
def test_work_preserved_duration_halves():
    pass


# ---- 9.2 Fixed Units, not effort-driven --------------------------------------

@scenario('features/effort_engine.feature', '9.2 - duration preserved, work doubles')
def test_duration_preserved_work_doubles():
    pass


# ---- 9.3 Fixed Work -----------------------------------------------------------

@scenario('features/effort_engine.feature', '9.3 - effort-driven is forced on')
def test_effort_driven_is_forced_on():
    pass


@scenario('features/effort_engine.feature',
          '9.3 - adding a resource preserves the work')
def test_add_resource_preserves_work():
    pass


@scenario('features/effort_engine.feature',
          '9.3 - a manual duration recalculates units and warns')
def test_manual_duration_recalculates_units_and_warns():
    pass


@scenario('features/effort_engine.feature', '9.3 - work cannot be edited directly')
def test_work_cannot_be_edited_directly():
    pass


# ---- 9.4 Fixed Duration, effort-driven -------------------------------------------

@scenario('features/effort_engine.feature',
          '9.4 - units redistribute to keep the duration')
def test_units_redistribute_to_keep_duration():
    pass


# ---- 9.5 Fixed Duration, not effort-driven -------------------------------------------

@scenario('features/effort_engine.feature',
          '9.5 - work grows while the duration holds')
def test_work_grows_duration_holds():
    pass


@scenario('features/effort_engine.feature', '9.5 - the duration is locked')
def test_duration_is_locked():
    pass


# ---- 9.10 partial allocations --------------------------------------------------------

@scenario('features/effort_engine.feature',
          '9.10 - a half-time resource added, work preserved')
def test_mixed_units_add():
    pass


# ---- resource removal --------------------------------------------------------------------

@scenario('features/effort_engine.feature',
          'Removing a resource extends an effort-driven task')
def test_removing_a_resource_extends_an_effort_driven_task():
    pass


@scenario('features/effort_engine.feature', 'Removing the last resource is refused')
def test_removing_the_last_resource_is_refused():
    pass


@scenario('features/effort_engine.feature',
          'Effort-driven off, removal shrinks the work')
def test_effort_driven_off_removal_shrinks_work():
    pass


# ---- direct edits ---------------------------------------------------------------------------

@scenario('features/effort_engine.feature',
          'Fixed Units - a duration edit recalculates work')
def test_fixed_units_duration_edit_recalculates_work():
    pass


@scenario('features/effort_engine.feature',
          'Fixed Units - a work edit recalculates duration')
def test_fixed_units_work_edit_recalculates_duration():
    pass


@scenario('features/effort_engine.feature',
          'Fixed Duration - a work edit recalculates units')
def test_fixed_duration_work_edit_recalculates_units():
    pass


# ---- validation ---------------------------------------------------------------------------------

@scenario('features/effort_engine.feature', 'Fixed Work needs work')
def test_fixed_work_needs_work():
    pass


@scenario('features/effort_engine.feature', 'Fixed Work needs a resource')
def test_fixed_work_needs_a_resource():
    pass


@scenario('features/effort_engine.feature', 'Fixed Duration needs a duration')
def test_fixed_duration_needs_duration():
    pass


@scenario('features/effort_engine.feature', 'Work without a resource is refused')
def test_work_without_a_resource_is_refused():
    pass


@scenario('features/effort_engine.feature', 'A placeholder with no work is valid')
def test_a_placeholder_with_no_work_is_valid():
    pass


@scenario('features/effort_engine.feature', 'Negatives are refused')
def test_negatives_are_refused():
    pass


# ---- changing the task type ------------------------------------------------------------------------

@scenario('features/effort_engine.feature',
          'Switching to Fixed Work locks effort-driven on')
def test_switching_to_fixed_work_locks_effort_driven_on():
    pass


@scenario('features/effort_engine.feature',
          'Switching to Fixed Work without work is refused')
def test_switching_to_fixed_work_without_work_is_refused():
    pass


@scenario('features/effort_engine.feature', 'A hard constraint is flagged')
def test_a_hard_constraint_is_flagged():
    pass


# ---- the effort-driven toggle -------------------------------------------------------------------------

@scenario('features/effort_engine.feature', 'Fixed Work cannot be toggled off')
def test_fixed_work_cannot_be_toggled():
    pass


@scenario('features/effort_engine.feature', 'A milestone has no effort logic')
def test_a_milestone_has_no_effort_logic():
    pass


@scenario('features/effort_engine.feature',
          'A manually scheduled task has no effort logic')
def test_a_manually_scheduled_task_has_no_effort_logic():
    pass


@scenario('features/effort_engine.feature', 'Toggling a Fixed Units task')
def test_toggling_a_fixed_units_task():
    pass


# ---- recalculate ----------------------------------------------------------------------------------------

@scenario('features/effort_engine.feature', 'Fixed Units solves the duration')
def test_fixed_units_solves_duration():
    pass


# ---- spotting what moved ---------------------------------------------------------------------------------

@scenario('features/effort_engine.feature', 'It spots each moved number')
def test_it_spots_each_moved_number():
    pass


# ---- the reconcile gate ------------------------------------------------------------------------------------

@scenario('features/effort_engine.feature', 'A task with no units is left alone')
def test_a_task_with_no_units_is_left_alone():
    pass


@scenario('features/effort_engine.feature',
          'An assignment at zero percent counts as no units')
def test_an_assignment_at_zero_percent_counts_as_no_units():
    pass


@scenario('features/effort_engine.feature', 'A milestone is left alone')
def test_a_milestone_is_left_alone():
    pass


# ---- one adjustable variable changed -------------------------------------------------------------------------

@scenario('features/effort_engine.feature',
          'Fixed Units - a duration change recomputes work')
def test_fixed_units_duration_change_recomputes_work():
    pass


@scenario('features/effort_engine.feature',
          'Fixed Units - a work change recomputes duration')
def test_fixed_units_work_change_recomputes_duration():
    pass


@scenario('features/effort_engine.feature',
          'Fixed Duration - a work change recomputes units')
def test_fixed_duration_work_change_recomputes_units():
    pass


@scenario('features/effort_engine.feature',
          'Fixed Work - a units change recomputes duration')
def test_fixed_work_units_change_recomputes_duration():
    pass


# ---- both adjustable variables changed ------------------------------------------------------------------------

@scenario('features/effort_engine.feature', 'Changing both raises a conflict')
def test_changing_both_raises_a_conflict():
    pass


@scenario('features/effort_engine.feature', 'Preserving duration recomputes work')
def test_preserving_duration_recomputes_work():
    pass


@scenario('features/effort_engine.feature', 'Preserving work recomputes duration')
def test_preserving_work_recomputes_duration():
    pass


@scenario('features/effort_engine.feature', 'The prompt names both variables')
def test_the_prompt_names_both_variables():
    pass


# ---- roster changes through reconcile ---------------------------------------------------------------------------

@scenario('features/effort_engine.feature',
          'Fixed Units, effort-driven - adding halves the duration')
def test_fixed_units_ed_on_add_halves_duration():
    pass


@scenario('features/effort_engine.feature',
          'Fixed Units, not effort-driven - adding grows the work')
def test_fixed_units_ed_off_add_grows_work():
    pass


@scenario('features/effort_engine.feature',
          'Fixed Duration, effort-driven - adding redistributes the units')
def test_fixed_duration_ed_on_add_redistributes_units():
    pass


@scenario('features/effort_engine.feature',
          'Fixed Duration, not effort-driven - the units stay and the work grows')
def test_fixed_duration_ed_off_add_grows_work():
    pass


@scenario('features/effort_engine.feature',
          'Fixed Work - adding halves the duration')
def test_fixed_work_add_halves_duration():
    pass


@scenario('features/effort_engine.feature', 'Effort-driven removal transfers the work')
def test_ed_on_removal_transfers_the_work():
    pass


@scenario('features/effort_engine.feature',
          'Not-effort-driven removal shrinks the work')
def test_ed_off_removal_shrinks_work():
    pass


@scenario('features/effort_engine.feature',
          'The first resource still takes duration x units')
def test_the_first_resource_still_takes_duration_x_units():
    pass


@scenario('features/effort_engine.feature',
          'A duration edit on top of an add still wins')
def test_a_duration_edit_on_top_of_an_add_still_wins():
    pass


@scenario('features/effort_engine.feature',
          'A same-roster units edit is not effort-driven')
def test_a_same_roster_units_edit_is_not_effort_driven():
    pass


# ---- the task adapter ----------------------------------------------------------------------------------------------

@scenario('features/effort_engine.feature',
          'The state reads days as hours and splits as units')
def test_state_reads_days_as_hours_and_splits_as_units():
    pass


@scenario('features/effort_engine.feature', 'An unresourced task has no units')
def test_an_unresourced_task_has_no_units():
    pass


@scenario('features/effort_engine.feature',
          'Write-back rounds the duration to whole days')
def test_write_back_rounds_duration_to_whole_days():
    pass


@scenario('features/effort_engine.feature',
          'Write-back shares the work across assignments')
def test_write_back_shares_work_across_assignments():
    pass


# ---- helpers --------------------------------------------------------------------------------------------------


def _state(**kwargs):
    """An EffortState with hours_per_day 8 unless overridden."""
    kwargs.setdefault('hours_per_day', 8.0)
    return EffortState(**kwargs)


# ---- Givens: a single state ------------------------------------------------------


@given(parsers.parse('a "{type}" state'))
def a_typed_state(ctx, type):
    ctx.state = _state(effort_type=TYPES[type])


@given('effort-driven is off')
def effort_driven_off(ctx):
    ctx.state.effort_driven = False


@given(parsers.parse('a "{type}" state running {hours:d} hours'))
def a_state_running(ctx, type, hours):
    ctx.state = _state(effort_type=TYPES[type], duration_hours=hours)


@given(parsers.parse('a "{type}" state running {hours:d} hours '
                     'of {work:d} work holding "{rid}" at {units:g}'))
def a_state_running_one(ctx, type, hours, work, rid, units):
    ctx.state = _state(effort_type=TYPES[type], duration_hours=hours,
                       work=work, assignments=[Assignment(rid, units)])


@given(parsers.parse('a "{type}" state running {hours:d} hours '
                     'of {work:d} work holding "{rid}" at {units:g} '
                     'and "{rid2}" at {units2:g}'))
def a_state_running_two(ctx, type, hours, work, rid, units, rid2, units2):
    ctx.state = _state(effort_type=TYPES[type], duration_hours=hours,
                       work=work,
                       assignments=[Assignment(rid, units),
                                    Assignment(rid2, units2)])


@given(parsers.parse('a "{type}" state carrying {work:d} work'))
def a_state_carrying(ctx, type, work):
    ctx.state = _state(effort_type=TYPES[type], work=work)


@given(parsers.parse('a "{type}" state carrying {work:d} work '
                     'holding "{rid}" at {units:g}'))
def a_state_carrying_one(ctx, type, work, rid, units):
    ctx.state = _state(effort_type=TYPES[type], work=work,
                       assignments=[Assignment(rid, units)])


@given('a "Fixed Units" state carrying -1 work holding "R1" at 1.0')
def a_state_carrying_negative(ctx):
    ctx.state = _state(effort_type=EFFORT_FIXED_UNITS, work=-1,
                       assignments=[Assignment('R1', 1.0)])


@given('a "Fixed Units" state that is a milestone')
def a_milestone_state(ctx):
    ctx.state = _state(effort_type=EFFORT_FIXED_UNITS, is_milestone=True)


@given('a "Fixed Units" state that is manually scheduled')
def a_manual_state(ctx):
    ctx.state = _state(effort_type=EFFORT_FIXED_UNITS, manually_scheduled=True)


@given(parsers.parse('it is constrained "{ctype}"'))
def it_is_constrained(ctx, ctype):
    ctx.state.constraint_type = ctype


# ---- Givens: two states to compare ---------------------------------------------


@given(parsers.parse('a state of {hours:d} hours and {work:d} work '
                     'holding "{rid}" at {units:g}'))
def a_first_state(ctx, hours, work, rid, units):
    ctx.old = _state(duration_hours=hours, work=work,
                     assignments=[Assignment(rid, units)])


@given(parsers.parse('a second state of {hours:d} hours and {work:d} work '
                     'holding "{rid}" at {units:g}'))
def a_second_state(ctx, hours, work, rid, units):
    ctx.new = _state(duration_hours=hours, work=work,
                     assignments=[Assignment(rid, units)])


# ---- Givens: a reconcile pair ----------------------------------------------------


@given(parsers.parse('a pair of "{type}" states of {old_hours:d} and '
                     '{new_hours:d} hours, {work:d} work, unresourced'))
def a_pair_unresourced(ctx, type, old_hours, new_hours, work):
    ctx.old = _state(effort_type=TYPES[type], duration_hours=old_hours,
                     work=work, assignments=[])
    ctx.new = _state(effort_type=TYPES[type], duration_hours=new_hours,
                     work=work, assignments=[])


@given(parsers.parse('a pair of "{type}" states of {old_hours:d} and '
                     '{new_hours:d} hours, {work:d} work, holding '
                     '"{rid}" at {units:g}'))
def a_pair_two_durations(ctx, type, old_hours, new_hours, work, rid, units):
    ctx.old = _state(effort_type=TYPES[type], duration_hours=old_hours,
                     work=work, assignments=[Assignment(rid, units)])
    ctx.new = _state(effort_type=TYPES[type], duration_hours=new_hours,
                     work=work, assignments=[Assignment(rid, units)])


@given(parsers.parse('a pair of "{type}" milestone states of {old_hours:d} '
                     'and {new_hours:d} hours, {work:d} work, holding '
                     '"{rid}" at {units:g}'))
def a_pair_milestone(ctx, type, old_hours, new_hours, work, rid, units):
    ctx.old = _state(effort_type=TYPES[type], duration_hours=old_hours,
                     work=work, is_milestone=True,
                     assignments=[Assignment(rid, units)])
    ctx.new = _state(effort_type=TYPES[type], duration_hours=new_hours,
                     work=work, is_milestone=True,
                     assignments=[Assignment(rid, units)])


@given(parsers.parse('a pair of "{type}" states of {hours:d} hours, '
                     '{work:d} work, holding "{rid}" at {units:g}'))
def a_pair_same(ctx, type, hours, work, rid, units):
    ctx.old = _state(effort_type=TYPES[type], duration_hours=hours, work=work,
                     assignments=[Assignment(rid, units)])
    ctx.new = _state(effort_type=TYPES[type], duration_hours=hours, work=work,
                     assignments=[Assignment(rid, units)])


@given(parsers.parse('a pair of "{type}" states where duration and work moved'))
def a_pair_both_moved(ctx, type):
    ctx.old = _state(effort_type=TYPES[type], duration_hours=8, work=8,
                     assignments=[Assignment('R1', 1.0)])
    ctx.new = _state(effort_type=TYPES[type], duration_hours=16, work=24,
                     assignments=[Assignment('R1', 1.0)])


def _roster_pair(ctx, type, driven, hours, roster):
    """old/new states built from (id, units, hours) triples."""
    assignments = [Assignment(i, u, h) for i, u, h in roster]
    work = sum(h for _i, _u, h in roster)
    ctx.old = _state(effort_type=TYPES[type], effort_driven=driven,
                     duration_hours=hours, work=work,
                     assignments=list(assignments))
    ctx.new = _state(effort_type=TYPES[type], effort_driven=driven,
                     duration_hours=hours, work=work,
                     assignments=[Assignment(i, u, h)
                                  for i, u, h in roster])


@given(parsers.parse('an {hours:d}-hour "{type}" effort-driven pair '
                     'holding "{rid}" at {units:g} for {wh:d} hours'))
@given(parsers.parse('a {hours:d}-hour "{type}" effort-driven pair '
                     'holding "{rid}" at {units:g} for {wh:d} hours'))
def a_roster_pair_one(ctx, hours, type, rid, units, wh):
    _roster_pair(ctx, type, True, hours, [(rid, units, float(wh))])


@given(parsers.parse('a {hours:d}-hour "{type}" not-effort-driven pair '
                     'holding "{rid}" at {units:g} for {wh:d} hours'))
@given(parsers.parse('an {hours:d}-hour "{type}" not-effort-driven pair '
                     'holding "{rid}" at {units:g} for {wh:d} hours'))
def a_roster_pair_one_off(ctx, hours, type, rid, units, wh):
    _roster_pair(ctx, type, False, hours, [(rid, units, float(wh))])


@given(parsers.parse('a {hours:d}-hour "{type}" effort-driven pair '
                     'holding "{rid}" at {units:g} for {wh:d} hours '
                     'and "{rid2}" at {units2:g} for {wh2:d} hours'))
def a_roster_pair_two(ctx, hours, type, rid, units, wh, rid2, units2, wh2):
    _roster_pair(ctx, type, True, hours,
                 [(rid, units, float(wh)), (rid2, units2, float(wh2))])


@given(parsers.parse('a {hours:d}-hour "{type}" not-effort-driven pair '
                     'holding "{rid}" at {units:g} for {wh:d} hours '
                     'and "{rid2}" at {units2:g} for {wh2:d} hours'))
def a_roster_pair_two_off(ctx, hours, type, rid, units, wh, rid2, units2, wh2):
    _roster_pair(ctx, type, False, hours,
                 [(rid, units, float(wh)), (rid2, units2, float(wh2))])


@given(parsers.parse('an {hours:d}-hour "{type}" effort-driven pair '
                     'holding nobody'))
def a_roster_pair_empty(ctx, hours, type):
    _roster_pair(ctx, type, True, hours, [])


@given(parsers.parse('the new state also holds "{rid}" at {units:g} '
                     'for {wh:d} hours'))
def the_new_state_also_holds(ctx, rid, units, wh):
    ctx.new.assignments.append(Assignment(rid, units, float(wh)))


@given(parsers.parse('the new state drops "{rid}"'))
def the_new_state_drops(ctx, rid):
    ctx.new.assignments = [a for a in ctx.new.assignments
                           if a.resource_id != rid]
    ctx.new.work = sum(a.hours for a in ctx.new.assignments)


@given(parsers.parse('the new state runs {hours:d} hours'))
def the_new_state_runs(ctx, hours):
    ctx.new.duration_hours = hours


@given(parsers.parse('the new state carries {work:d} work'))
def the_new_state_carries(ctx, work):
    ctx.new.work = work


@given(parsers.parse('the new state\'s "{rid}" is at {units:g}'))
def the_new_state_units(ctx, rid, units):
    for a in ctx.new.assignments:
        if a.resource_id == rid:
            a.units = units


# ---- Givens: a task to lift -------------------------------------------------------


def _task(days, roster):
    """A task with (id, estimated_hours, resource_split) triples."""
    return Task(id='T', name='A task', start_date=datetime(2026, 9, 9),
                duration=days,
                resource_assignments=[
                    {'resource_id': rid, 'estimated_hours': hours,
                     'resource_split': split}
                    for rid, hours, split in roster])


@given(parsers.parse('a task of {days:d} days with "{rid}" for {hours:g} '
                     'hours at {pct:g} percent'))
@given(parsers.parse('a task of {days:d} day with "{rid}" for {hours:g} '
                     'hours at {pct:g} percent'))
def a_task_with_one(ctx, days, rid, hours, pct):
    ctx.task = _task(days, [(rid, hours, pct)])


@given(parsers.parse('a task of {days:d} days with "{rid}" for {hours:g} '
                     'hours at {pct:g} percent and "{rid2}" for {hours2:g} '
                     'hours at {pct2:g} percent'))
@given(parsers.parse('a task of {days:d} day with "{rid}" for {hours:g} '
                     'hours at {pct:g} percent and "{rid2}" for {hours2:g} '
                     'hours at {pct2:g} percent'))
def a_task_with_two(ctx, days, rid, hours, pct, rid2, hours2, pct2):
    ctx.task = _task(days, [(rid, hours, pct), (rid2, hours2, pct)])


@given(parsers.parse('a task of {days:d} days with nobody assigned'))
def a_task_unresourced(ctx, days):
    ctx.task = _task(days, [])


# ---- Whens: single-state operations ----------------------------------------------


@when(parsers.parse('"{rid}" at {units:g} is added'))
def a_resource_is_added(ctx, rid, units):
    ctx.result = add_resource(ctx.state, rid, units)


@when(parsers.parse('"{rid}" is removed'))
def a_resource_is_removed(ctx, rid):
    index = next(i for i, a in enumerate(ctx.state.assignments)
                 if a.resource_id == rid)
    ctx.result = remove_resource(ctx.state, index)


@when(parsers.parse('the duration is edited to {hours:d} hours'))
def the_duration_is_edited(ctx, hours):
    ctx.result = edit_duration(ctx.state, hours)


@when(parsers.parse('the work is edited to {work:d}'))
def the_work_is_edited(ctx, work):
    ctx.result = edit_work(ctx.state, work)


@when(parsers.parse('it switches to "{type}"'))
def it_switches_type(ctx, type):
    ctx.result = change_effort_type(ctx.state, TYPES[type])


@when('effort-driven is switched off')
def effort_driven_is_switched_off(ctx):
    ctx.result = set_effort_driven(ctx.state, False)


@when('it is recalculated')
def it_is_recalculated(ctx):
    recalculate(ctx.state)


@when('they are compared')
def they_are_compared(ctx):
    ctx.changed = classify_changes(ctx.old, ctx.new)


@when('the pair is reconciled')
def the_pair_is_reconciled(ctx):
    ctx.result, ctx.conflict = reconcile(ctx.old, ctx.new)


@when(parsers.parse('the pair is reconciled preserving "{var}"'))
def the_pair_is_reconciled_preserving(ctx, var):
    ctx.result, ctx.conflict = reconcile(ctx.old, ctx.new, preserve=var)


@when('it is lifted into a state')
def it_is_lifted(ctx):
    ctx.state = state_from_task(ctx.task, hours_per_day=8)


@when(parsers.parse('the state\'s work is set to {work:d}'))
def the_states_work_is_set(ctx, work):
    ctx.state.work = work


@when('the state\'s work follows duration x units')
def the_states_work_follows(ctx):
    ctx.state.work = ctx.state.duration_hours * ctx.state.total_units


@when('the state is recalculated')
def the_state_is_recalculated(ctx):
    recalculate(ctx.state)


@when('the state is written back')
def the_state_is_written_back(ctx):
    write_state_to_task(ctx.state, ctx.task, hours_per_day=8)


# ---- Thens ---------------------------------------------------------------------


@then(parsers.parse('{days:d} day at {rate:d} a day is {expected:d} hours'))
@then(parsers.parse('{days:d} days at {rate:d} a day is {expected:d} hours'))
def days_are_hours(days, rate, expected):
    assert days_to_hours(days, rate) == expected


@then('the answer was accepted')
def the_answer_was_accepted(ctx):
    assert ctx.result.ok


@then('the answer was refused')
def the_answer_was_refused(ctx):
    assert not ctx.result.ok


@then('the answer warned')
def the_answer_warned(ctx):
    assert ctx.result.warnings


@then('switching effort-driven off is refused')
def switching_effort_driven_off_is_refused(ctx):
    assert not set_effort_driven(ctx.state, False).ok


@then('effort-driven reads on')
def effort_driven_reads_on(ctx):
    assert effort_driven_effective(ctx.state)


@then('effort-driven reads off')
def effort_driven_reads_off(ctx):
    assert not effort_driven_effective(ctx.state)


@then('the effort logic does not apply')
def the_effort_logic_does_not_apply(ctx):
    assert not logic_applies(ctx.state)


@then(parsers.parse('it runs {hours:d} hours'))
def it_runs(ctx, hours):
    assert ctx.state.duration_hours == hours


@then(parsers.parse('it carries {work:d} work'))
def it_carries(ctx, work):
    assert ctx.state.work == work


@then(parsers.parse('its total units are {units:g}'))
def its_total_units(ctx, units):
    assert ctx.state.total_units == pytest.approx(units)


@then(parsers.parse('each resource is at {units:g}'))
def each_resource_is_at(ctx, units):
    for a in ctx.state.assignments:
        assert a.units == pytest.approx(units)


@then('it validates')
def it_validates(ctx):
    assert validate(ctx.state).ok


@then('it does not validate')
def it_does_not_validate(ctx):
    assert not validate(ctx.state).ok


@then(parsers.parse('only "{name}" moved'))
def only_that_moved(ctx, name):
    for key, moved in ctx.changed.items():
        assert moved == (key == name)


@then('there is no conflict')
def there_is_no_conflict(ctx):
    assert ctx.conflict is None


@then(parsers.parse('a conflict names "{fixed}" fixed and "{options}" '
                    'the options'))
def a_conflict_names(ctx, fixed, options):
    assert ctx.result is None
    assert isinstance(ctx.conflict, EditConflict)
    assert ctx.conflict.fixed == fixed
    assert set(ctx.conflict.options) == set(options.split(', '))


@then(parsers.parse('the conflict\'s prompt names "{a}" and "{b}"'))
def the_prompt_names(ctx, a, b):
    text = ctx.conflict.prompt()
    assert a in text
    assert b in text


@then(parsers.parse('the new state runs {hours:d} hours'))
def the_new_state_runs_check(ctx, hours):
    assert ctx.new.duration_hours == hours


@then(parsers.parse('the new state carries {work:d} work'))
def the_new_state_carries_check(ctx, work):
    assert ctx.new.work == work


@then(parsers.parse('the new state\'s total units are {units:g}'))
def the_new_state_units_check(ctx, units):
    assert ctx.new.total_units == pytest.approx(units)


@then(parsers.parse('the state runs {hours:d} hours'))
def the_state_runs(ctx, hours):
    assert ctx.state.duration_hours == hours


@then(parsers.parse('the state carries {work:d} work'))
def the_state_carries(ctx, work):
    assert ctx.state.work == work


@then(parsers.parse('the state\'s total units are {units:g}'))
def the_state_units(ctx, units):
    assert ctx.state.total_units == pytest.approx(units)


@then(parsers.parse('the task reads {days:d} day'))
def the_task_reads(ctx, days):
    assert ctx.task.duration == days


@then(parsers.parse('the assignments carry {total:d} hours'))
def the_assignments_carry(ctx, total):
    assert sum(a['estimated_hours']
               for a in ctx.task.resource_assignments) == total


@then(parsers.parse('"{rid}" carries {hours:d} hours'))
def the_assignment_carries(ctx, rid, hours):
    by_id = {a['resource_id']: a['estimated_hours']
             for a in ctx.task.resource_assignments}
    assert by_id[rid] == hours


# ---- the direct units edit and the remaining refusals --------------------------------


@when(parsers.parse('the "{rid}" units are edited to {units:g}'))
def the_units_are_edited(ctx, rid, units):
    index = next(i for i, a in enumerate(ctx.state.assignments)
                 if a.resource_id == rid)
    ctx.result = edit_units(ctx.state, index, units)


@when(parsers.parse('the units of assignment {index:d} are edited to '
                    '{units:g}'))
def the_indexed_units_are_edited(ctx, index, units):
    ctx.result = edit_units(ctx.state, index, units)


@when(parsers.parse('the assignment at index {index:d} is removed'))
def the_indexed_assignment_is_removed(ctx, index):
    ctx.result = remove_resource(ctx.state, index)


@given(parsers.parse('a "{type}" effort-driven state running {hours:d} '
                     'hours of {work:d} work holding "{rid}" at {units:g} '
                     'and "{rid2}" at {units2:g}'))
def an_ed_state_running_two(ctx, type, hours, work, rid, units, rid2,
                            units2):
    ctx.state = _state(effort_type=TYPES[type], effort_driven=True,
                       duration_hours=hours, work=work,
                       assignments=[Assignment(rid, units),
                                    Assignment(rid2, units2)])


@given(parsers.parse('a "{type}" effort-driven state running {hours:d} '
                     'hours of {work:d} work holding "{rid}" at {units:g}'))
def an_ed_state_running_one(ctx, type, hours, work, rid, units):
    ctx.state = _state(effort_type=TYPES[type], effort_driven=True,
                       duration_hours=hours, work=work,
                       assignments=[Assignment(rid, units)])


@given(parsers.parse('a "{type}" state running {hours:d} hours '
                     'of {work:d} work'))
def a_state_running_bare(ctx, type, hours, work):
    ctx.state = _state(effort_type=TYPES[type], duration_hours=hours,
                       work=work)


@given(parsers.parse('a "{type}" state running {hours:d} hours '
                     'holding "{rid}" at {units:g}'))
def a_state_running_holding(ctx, type, hours, rid, units):
    ctx.state = _state(effort_type=TYPES[type], duration_hours=hours,
                       assignments=[Assignment(rid, units)])


@given(parsers.parse('a "{type}" state running {hours:d} hours on a '
                     'zero-length day'))
def a_state_on_a_zero_day(ctx, type, hours):
    ctx.state = _state(effort_type=TYPES[type], duration_hours=hours,
                       hours_per_day=0.0)


@then(parsers.parse('it measures {days:g} days'))
def it_measures_days(ctx, days):
    assert ctx.state.duration_days == days


@then(parsers.parse('{hours:d} hours at {rate:d} a day is {days:g} days'))
def hours_are_days(hours, rate, days):
    assert hours_to_days(hours, rate) == days


@when(parsers.parse('it switches to the unknown type "{name}"'))
def it_switches_to_unknown(ctx, name):
    ctx.result = change_effort_type(ctx.state, name)


@given(parsers.parse('a task of {days:d} days with "{rid}" for gibberish '
                     'hours at gibberish percent'))
def a_task_with_gibberish(ctx, days, rid):
    ctx.task = Task(id='T', name='A task',
                    start_date=datetime(2026, 9, 9), duration=days,
                    resource_assignments=[
                        {'resource_id': rid,
                         'estimated_hours': 'banana',
                         'resource_split': 'not a number'}])


@given(parsers.parse('the new state swaps "{gone}" for "{rid}" at {units:g} '
                     'for {wh:d} hours'))
def the_new_state_swaps(ctx, gone, rid, units, wh):
    ctx.new.assignments = [a for a in ctx.new.assignments
                           if a.resource_id != gone]
    ctx.new.assignments.append(Assignment(rid, units, float(wh)))


@scenario('features/effort_engine.feature',
          'A direct units edit on Fixed Work moves the duration')
def test_direct_units_edit_fixed_work():
    pass


@scenario('features/effort_engine.feature',
          'A direct units edit on Fixed Duration moves the work')
def test_direct_units_edit_fixed_duration():
    pass


@scenario('features/effort_engine.feature',
          'A direct units edit on Fixed Units moves the work')
def test_direct_units_edit_fixed_units():
    pass


@scenario('features/effort_engine.feature', 'Units cannot be negative')
def test_units_cannot_be_negative():
    pass


@scenario('features/effort_engine.feature',
          'Units for a resource that is not there are refused')
def test_units_bad_index_refused():
    pass


@scenario('features/effort_engine.feature',
          'A Fixed Work edit to zero total units is refused')
def test_fixed_work_zero_units_refused():
    pass


@scenario('features/effort_engine.feature',
          'Removing a resource that is not there is refused')
def test_remove_missing_refused():
    pass


@scenario('features/effort_engine.feature',
          'Fixed Duration, effort-driven - removing shares the units out')
def test_fixed_duration_removal_redistributes():
    pass


@scenario('features/effort_engine.feature',
          'A negative-units add is refused')
def test_negative_units_add_refused():
    pass


@scenario('features/effort_engine.feature',
          'Fixed Work refuses an add that still leaves nobody working')
def test_fixed_work_add_zero_units_refused():
    pass


@scenario('features/effort_engine.feature',
          'Fixed Duration accepts an add with no duration to divide')
def test_fixed_duration_degenerate_add():
    pass


@scenario('features/effort_engine.feature',
          'A negative duration edit is refused')
def test_negative_duration_refused():
    pass


@scenario('features/effort_engine.feature', 'A negative work edit is refused')
def test_negative_work_refused():
    pass


@scenario('features/effort_engine.feature',
          'Fixed Work refuses a zero-duration edit')
def test_fixed_work_zero_duration_refused():
    pass


@scenario('features/effort_engine.feature',
          'Fixed Work with no roster answers a duration edit politely')
def test_fixed_work_no_roster_duration_edit():
    pass


@scenario('features/effort_engine.feature', 'A type nobody makes is refused')
def test_unknown_type_refused():
    pass


@scenario('features/effort_engine.feature',
          'Fixed Duration refuses a switch into no duration')
def test_fixed_duration_no_duration_refused():
    pass


@scenario('features/effort_engine.feature',
          'Fixed Units refuses a switch into work with no hands')
def test_fixed_units_work_no_resource_refused():
    pass


@scenario('features/effort_engine.feature',
          'Fixed Work refuses a switch into no work')
def test_fixed_work_no_work_refused():
    pass


@scenario('features/effort_engine.feature',
          'A negative assignment does not validate')
def test_negative_assignment_invalid():
    pass


@scenario('features/effort_engine.feature',
          'Fixed Work, a duration move scales the units instead')
def test_fixed_work_duration_move_scales_units():
    pass


@scenario('features/effort_engine.feature',
          "A roster change that alters nothing else is not a planner's edit")
def test_roster_swap_no_other_change():
    pass


@scenario('features/effort_engine.feature',
          'A zero-length day measures no days')
def test_zero_length_day():
    pass


@scenario('features/effort_engine.feature',
          'Hours to days on a zero-length day is zero')
def test_hours_to_days_zero_rate():
    pass


@scenario('features/effort_engine.feature',
          'A gibberish split and gibberish hours read as zero')
def test_gibberish_assignment_reads_zero():
    pass


@then(parsers.parse('the new state\'s "{rid}" is at {units:g}'))
def the_new_state_units_check_rid(ctx, rid, units):
    units_by_id = {a.resource_id: a.units for a in ctx.new.assignments}
    assert units_by_id[rid] == pytest.approx(units)
