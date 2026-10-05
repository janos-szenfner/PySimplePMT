"""
The hidden-columns setting on the project.

The scenarios live in features/grid_column_visibility.feature. They pin
the default and the file round-trip down. The grid reading the setting
and the Settings tab that edits it need a display and stay in
tests/test_grid_column_visibility.py.
"""

from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Project


scenarios('features/grid_column_visibility.feature')


@pytest.fixture
def ctx():
    return SimpleNamespace(project=None)


def _names(text: str):
    return [piece.strip() for piece in text.split(',')]


@then(parsers.parse('a new plan hides "{columns}"'))
def the_default_hides(columns):
    assert Project(name="P").hidden_grid_columns == _names(columns)


@given(parsers.parse('a plan hiding "{columns}"'))
def a_plan_hiding(ctx, columns):
    ctx.project = Project(name="P")
    ctx.project.hidden_grid_columns = _names(columns)


@given('a saved plan with hidden columns removed')
def a_plan_without_the_setting(ctx):
    ctx.saved = Project(name="P").to_dict()
    del ctx.saved['hidden_grid_columns']


@when('it is saved and read back')
def saved_and_read_back(ctx):
    ctx.project = Project.from_dict(ctx.project.to_dict())


@when('it is read back')
def it_is_read_back(ctx):
    ctx.project = Project.from_dict(ctx.saved)


@then(parsers.parse('it hides "{columns}"'))
def it_hides(ctx, columns):
    assert ctx.project.hidden_grid_columns == _names(columns)
