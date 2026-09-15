"""
pytest-bdd tests for the Earliest begin migration (issue #32).

Run with:
    python3 -m pytest tests/test_earliest_begin_migration_bdd.py -q

Pure model loading - no display is needed. Converted from
test_earliest_begin_migration.py - every case carried over.
"""
from datetime import datetime
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Task

pytestmark = [
    pytest.mark.earliest_begin_migration,
]

scenarios("features/earliest_begin_migration.feature")

BASE = datetime(2026, 1, 1)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _base_dict(**extra):
    data = {
        'id': '001',
        'name': 'A',
        'start_date': BASE.isoformat(),
        'end_date': None,
        'progress': 0,
        'dependencies': [],
        'color': '#1f6aa5',
        'is_milestone': False,
        'task_type': 'Task',
    }
    data.update(extra)
    return data


# ------------------------------------------------------------------
# GIVEN
# ------------------------------------------------------------------

@given(parsers.parse('a saved task carrying an earliest begin of "{day}" '
                     'was loaded'), target_fixture="ctx")
def a_saved_task_with_a_floor_was_loaded(day):
    task = Task.from_dict(_base_dict(
        earliest_begin=datetime.fromisoformat(day).isoformat()))
    return SimpleNamespace(task=task)


@given("a loaded task", target_fixture="ctx")
def a_loaded_task():
    return SimpleNamespace(task=Task.from_dict(_base_dict()))


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------

@when(parsers.parse('a saved task carrying an earliest begin of "{day}" '
                    'is loaded'), target_fixture="ctx")
def a_saved_task_with_a_floor_is_loaded(day):
    task = Task.from_dict(_base_dict(
        earliest_begin=datetime.fromisoformat(day).isoformat()))
    return SimpleNamespace(task=task)


@when("a saved task with no legacy floor is loaded", target_fixture="ctx")
def a_saved_task_with_no_floor_is_loaded():
    return SimpleNamespace(task=Task.from_dict(_base_dict()))


@when(parsers.parse('a saved task carrying an earliest begin of "{floor}" '
                    'and an "{ctype}" constraint dated "{cday}" is loaded'),
      target_fixture="ctx")
def a_saved_task_with_both_is_loaded(floor, ctype, cday):
    task = Task.from_dict(_base_dict(
        earliest_begin=datetime.fromisoformat(floor).isoformat(),
        constraint_type=ctype,
        constraint_date=datetime.fromisoformat(cday).isoformat()))
    return SimpleNamespace(task=task)


@when("the task is saved and loaded again")
def the_task_is_saved_and_loaded_again(ctx):
    ctx.task = Task.from_dict(ctx.task.to_dict())


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@then(parsers.parse('the constraint type is "{ctype}"'))
def the_constraint_type_is(ctx, ctype):
    assert ctx.task.constraint_type == ctype


@then(parsers.parse('the constraint date is "{day}"'))
def the_constraint_date_is(ctx, day):
    assert ctx.task.constraint_date == datetime.fromisoformat(day)


@then("there is no constraint date")
def there_is_no_constraint_date(ctx):
    assert ctx.task.constraint_date is None


@then(parsers.parse('"{field}" is not in its saved form'))
def the_field_is_not_in_its_saved_form(ctx, field):
    assert field not in ctx.task.to_dict()


@then(parsers.parse('the task has no "{field}" attribute'))
def the_task_has_no_attribute(ctx, field):
    assert not hasattr(ctx.task, field)
