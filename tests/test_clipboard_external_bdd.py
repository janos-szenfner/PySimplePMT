"""
pytest-bdd tests for the readable desktop clipboard (issue #16).

Run with:
    python3 -m pytest tests/test_clipboard_external_bdd.py -q

The desktop clipboard is a fake, so no display is needed. Converted
from test_clipboard_external.py - every case carried over.
"""
from datetime import datetime
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Project, Task
from gantt_app.utils.copypastecut import CLIPBOARD_COLUMNS, ClipboardService

pytestmark = [
    pytest.mark.clipboard_external,
]

scenarios("features/clipboard_external.feature")


class _FakeClipboard:
    """Records what the service writes to the desktop clipboard."""

    def __init__(self, holds=""):
        self.written = None
        self._holds = holds

    def clipboard_clear(self):
        self.written = None

    def clipboard_append(self, text):
        self.written = text

    def clipboard_get(self):
        return self._holds


def _project():
    base = datetime(2026, 9, 14)
    project = Project(name="Plan")
    project.add_task(Task(id="001", name="Design Phase", task_type="Task",
                          start_date=base, end_date=datetime(2026, 9, 18)))
    project.add_task(Task(id="002", name="UI Mockups", task_type="Subtask",
                          parent_task_id="001", start_date=base,
                          end_date=base))
    project.add_task(Task(id="003", name="Design Review",
                          task_type="Milestone", start_date=base))
    return project


# ------------------------------------------------------------------
# GIVEN
# ------------------------------------------------------------------

@given("a clipboard service over the sample plan", target_fixture="ctx")
def a_clipboard_service_over_the_plan():
    project = _project()
    return SimpleNamespace(project=project,
                           service=ClipboardService(project))


@given("the desktop clipboard is a recorder")
def the_desktop_clipboard_is_a_recorder(ctx):
    ctx.service.clipboard_widget = _FakeClipboard()


@given("the desktop clipboard holds table text")
def the_desktop_clipboard_holds_text(ctx):
    ctx.service.clipboard_widget = _FakeClipboard(
        holds="Design Phase\tTask\t...\n")


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------

@when(parsers.parse('"{a}" is copied'))
def one_task_is_copied(ctx, a):
    ctx.service.copy([a])


@when(parsers.parse('"{a}" and "{b}" are copied'))
def two_tasks_are_copied(ctx, a, b):
    ctx.service.copy([a, b])


@when(parsers.parse('"{a}", "{b}" and "{c}" are copied'))
def three_tasks_are_copied(ctx, a, b, c):
    ctx.service.copy([a, b, c])


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@then("the first clipboard line is the column header")
def the_first_line_is_the_header(ctx):
    first = ctx.service._clipboard_text().splitlines()[0]
    assert first == "\t".join(CLIPBOARD_COLUMNS)


@then(parsers.parse('the clipboard text names "{a}", "{b}" and "{c}"'))
def the_clipboard_names_all(ctx, a, b, c):
    text = ctx.service._clipboard_text()
    for name in (a, b, c):
        assert name in text


@then(parsers.parse('the first task row\'s cells are "{name}" and "{type}"'))
def the_first_row_cells(ctx, name, type):
    row = ctx.service._clipboard_text().splitlines()[1]
    cells = row.split("\t")
    assert cells[0].strip() == name
    assert cells[1] == type


@then(parsers.parse('the "{name}" line starts with a space'))
def the_line_is_indented(ctx, name):
    lines = ctx.service._clipboard_text().splitlines()
    subtask_line = next(l for l in lines if name in l)
    assert subtask_line.startswith(" ")


@then(parsers.parse('the first task row mentions "{text}"'))
def the_first_row_mentions(ctx, text):
    row = ctx.service._clipboard_text().splitlines()[1]
    assert text in row


@then("the clipboard text carries no internal payload words")
def no_internal_json_leaks(ctx):
    text = ctx.service._clipboard_text()
    for leak in ("payload", "operation", "PySimplePMT tasks",
                 "source_container_id"):
        assert leak not in text


@then("the recorder holds exactly the clipboard text")
def the_recorder_holds_the_text(ctx):
    ctx.written = ctx.service.clipboard_widget.written
    assert ctx.written == ctx.service._clipboard_text()


@then(parsers.parse('it names "{name}"'))
def the_recording_names(ctx, name):
    assert name in ctx.written


@then("resolving the payload finds nothing")
def the_payload_resolves_to_nothing(ctx):
    assert ctx.service._resolve_payload() is None


@then("paste is not offered")
def paste_is_not_offered(ctx):
    assert not ctx.service.can_paste(None)


@then(parsers.parse('pasting at "{task_id}" succeeds'))
def pasting_succeeds(ctx, task_id):
    assert ctx.service.paste_at(task_id)
