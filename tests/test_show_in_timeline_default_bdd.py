"""
pytest-bdd tests for the create dialog's timeline default (issue #33).

Run with:
    python3 -m pytest tests/test_show_in_timeline_default_bdd.py -q

form_template is exercised on a light stand-in, so no display is needed.
Converted from test_show_in_timeline_default.py - every case carried over.
"""
from datetime import datetime
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Project, Task
from gantt_app.views.taskdialogs import CreateTaskDialog

pytestmark = [
    pytest.mark.show_in_timeline_default,
]

scenarios("features/show_in_timeline_default.feature")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _template(task_type="Task", parent_task=None):
    """Run CreateTaskDialog.form_template with only what it reads."""
    stub = SimpleNamespace(
        project=Project(name="P"),
        parent_task=parent_task,
        is_milestone=(task_type == "Milestone"),
        task_type=task_type,
        DEFAULT_COLORS=CreateTaskDialog.DEFAULT_COLORS,
        SUBTASK_LENGTH=CreateTaskDialog.SUBTASK_LENGTH,
        DEFAULT_LENGTH=CreateTaskDialog.DEFAULT_LENGTH,
    )
    return CreateTaskDialog.form_template(stub)


# ------------------------------------------------------------------
# GIVEN
# ------------------------------------------------------------------

@given("a parent task exists", target_fixture="parent")
def a_parent_task_exists():
    return Task(id="p", name="Parent",
                start_date=Project(name="P").calendar
                .get_next_working_day(datetime(2026, 9, 10)))


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------

@when(parsers.parse('a create-dialog template is built for a "{kind}"'),
      target_fixture="template")
def a_template_is_built(kind):
    return _template(kind)


@when(parsers.parse('a create-dialog template is built for a "{kind}" '
                    'under it'), target_fixture="template")
def a_template_is_built_under_the_parent(kind, parent):
    return _template(kind, parent)


@when("a task is built the way importers and file loads build one",
      target_fixture="template")
def a_task_is_built_the_plain_way():
    return Task(id="t", name="Loaded", start_date=datetime(2026, 9, 10))


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@then("the template is off the timeline")
def the_template_is_off_the_timeline(template):
    assert template.show_in_timeline is False


@then("the task is on the timeline")
def the_task_is_on_the_timeline(template):
    assert template.show_in_timeline is True
