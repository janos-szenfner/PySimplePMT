"""
pytest-bdd tests for the wiring between dialogs and dependency editor.

Run with:
    python3 -m pytest tests/test_dialog_wiring_bdd.py -q

Display-free: callbacks are exercised against stand-ins and the
waiting behaviour is read out of the source. Converted from
test_dialog_wiring.py - every case carried over.
"""
import inspect
from datetime import datetime
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Project, Task
from gantt_app.views.dependency_editor import DependencyEditor
from gantt_app.views.taskdialogs import CreateTaskDialog, EditTaskDialog

pytestmark = [
    pytest.mark.dialog_wiring,
]

scenarios("features/dialog_wiring.feature")


def _d(text):
    return datetime.strptime(text, "%Y-%m-%d")


def _body_of(function) -> str:
    """
    A function's source with its docstring taken out.

    Both of these explain in prose what they no longer do, and the
    explanation names the call - so reading the source whole finds the
    very word the test is looking for.
    """
    import ast
    import textwrap

    source = textwrap.dedent(inspect.getsource(function))
    tree = ast.parse(source).body[0]
    if (tree.body and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, ast.Constant)):
        tree.body = tree.body[1:]
    return ast.dump(tree)


# ------------------------------------------------------------------
# GIVEN
# ------------------------------------------------------------------

@given("a plan with First and Second", target_fixture="ctx")
def a_plan_with_first_and_second():
    project = Project(name="Wiring")
    first = Task.create_task("First", datetime(2024, 1, 1),
                             datetime(2024, 1, 5),
                             task_id=project.next_task_id())
    project.add_task(first)
    second = Task.create_task("Second", datetime(2024, 2, 1),
                              datetime(2024, 2, 5),
                              task_id=project.next_task_id())
    project.add_task(second)
    return SimpleNamespace(project=project, first=first, second=second)


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------

@when("a half-built edit dialog hears dependencies changed",
      target_fixture="ctx")
def half_built_edit_dialog():
    ctx = SimpleNamespace()
    try:
        EditTaskDialog._on_dependencies_changed(SimpleNamespace())
        ctx.raised = None
    except AttributeError as error:
        ctx.raised = error
    return ctx


@when("a half-built create dialog hears dependencies changed",
      target_fixture="ctx")
def half_built_create_dialog():
    ctx = SimpleNamespace()
    try:
        CreateTaskDialog._on_dependencies_changed(SimpleNamespace())
        ctx.raised = None
    except AttributeError as error:
        ctx.raised = error
    return ctx


@when("an edit dialog with a bare editor hears dependencies changed",
      target_fixture="ctx")
def edit_dialog_with_a_bare_editor():
    ctx = SimpleNamespace()
    stub = SimpleNamespace(_dependency_editor=object())
    try:
        EditTaskDialog._on_dependencies_changed(stub)
        ctx.raised = None
    except AttributeError as error:
        ctx.raised = error
    return ctx


@when(parsers.parse("the required start is asked with no links for {date}"))
def required_start_no_links(ctx, date):
    ctx.required = _required(ctx, [], _d(date))


@when(parsers.parse("the required start is asked with an {kind} {hardness} "
                    "link for {date}"))
def required_start_with_link(ctx, kind, hardness, date):
    from gantt_app.core.models import Dependency

    links = [Dependency(ctx.first.id, kind, hardness)]
    ctx.required = _required(ctx, links, _d(date))


def _required(ctx, links, start):
    """Run the editor's calculation without building the widget."""
    editor = SimpleNamespace(
        project=ctx.project,
        task=ctx.second,
        links=links,
        get_links=lambda: list(links),
    )
    return DependencyEditor.required_start_date(editor, start)


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@then("the editor's constructor refreshes without notifying")
def the_constructor_refreshes_without_notifying():
    source = inspect.getsource(DependencyEditor.__init__)
    assert 'refresh(notify=False)' in source


@then("refresh takes a notify flag defaulting on")
def refresh_takes_a_notify_flag():
    parameters = inspect.signature(DependencyEditor.refresh).parameters
    assert 'notify' in parameters
    assert parameters['notify'].default


@then("refresh only calls back when notifying is asked for")
def refresh_guards_the_callback():
    source = inspect.getsource(DependencyEditor.refresh)
    assert 'if notify and self.on_changed' in source


@then("nothing was raised")
def nothing_was_raised(ctx):
    assert ctx.raised is None


@then("the required start is empty")
def the_required_start_is_empty(ctx):
    assert ctx.required is None


@then(parsers.re(r"the required start is (?P<date>\d{4}-\d{2}-\d{2})"))
def the_required_start_is(ctx, date):
    assert ctx.required == _d(date)


@then("edit_task's body names no wait_window")
def edit_task_names_no_wait_window():
    from gantt_app.main import GanttApp
    assert 'wait_window' not in _body_of(GanttApp.edit_task)


@then("create_task's body names no wait_window")
def create_task_names_no_wait_window():
    from gantt_app.views.task_list import DragDropTaskList
    assert 'wait_window' not in _body_of(DragDropTaskList.create_task)


@then("edit_task's body still names on_save")
def edit_task_still_names_on_save():
    from gantt_app.main import GanttApp
    assert 'on_save' in _body_of(GanttApp.edit_task)


@then("create_task's body still names on_save")
def create_task_still_names_on_save():
    from gantt_app.views.task_list import DragDropTaskList
    assert 'on_save' in _body_of(DragDropTaskList.create_task)
