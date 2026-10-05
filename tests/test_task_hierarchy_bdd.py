"""
pytest-bdd tests for task hierarchies deeper than two levels.

Run with:
    python3 -m pytest tests/test_task_hierarchy_bdd.py -q

Nesting is a parent link and nothing more - there is no Subtask type
(issue #63), so a task at any depth can hold rows of its own. Nothing
here needs a display.
"""
import pathlib
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

import gantt_app
from gantt_app.core.models import Project, Task
from gantt_app.core.workdaycalendar import WorkingCalendar

pytestmark = [
    pytest.mark.task_hierarchy,
]

scenarios("features/task_hierarchy.feature")

START = datetime(2024, 1, 1)


@pytest.fixture
def ctx():
    return SimpleNamespace(project=None, task=None, result=None)


def _find(ctx, label):
    """A task by name, or by the id the rows table named it."""
    for task in ctx.project.tasks:
        if task.name == label or task.id == label:
            return task
    raise AssertionError(f"no task named {label!r}")


def _plan_from_rows(rows):
    """A project from (id, type, parent) rows, in hierarchy order."""
    project = Project(name="Levels")
    for row in rows:
        task_id, task_type, parent = row
        project.add_task(Task(
            id=task_id.strip(), name=task_id.strip(),
            task_type=task_type.strip(),
            parent_task_id=parent.strip() or None,
            start_date=datetime(2026, 1, 5),
            end_date=None if task_type.strip() == "Milestone"
            else datetime(2026, 1, 9),
        ))
    project.tasks = project._flatten(project._children_by_parent())
    return project


# ------------------------------------------------------------------
# the three-level chain
# ------------------------------------------------------------------

@given("a three-level hierarchy")
def a_three_level_hierarchy(ctx):
    ctx.level1 = Task.create_task("Level 1", START,
                                  START + timedelta(days=20))
    ctx.level2 = Task.create_subtask("Level 2", parent_task=ctx.level1,
                                     end_date=START + timedelta(days=10))
    ctx.level3 = Task.create_subtask("Level 3", parent_task=ctx.level2,
                                     end_date=START + timedelta(days=5))
    ctx.project = Project(
        name="Deep", tasks=[ctx.level1, ctx.level2, ctx.level3])


@then(parsers.parse('"{name}" sits under "{parent}"'))
def it_sits_under(ctx, name, parent):
    assert _find(ctx, name).parent_task_id == _find(ctx, parent).id


@then(parsers.parse('"{name}" is a "{task_type}"'))
def it_is_a(ctx, name, task_type):
    assert _find(ctx, name).task_type == task_type


@then(parsers.parse('the roots are "{names}"'))
def the_roots_are(ctx, names):
    expected = [n.strip() for n in names.split(',')]
    assert [t.name for t in ctx.project.get_root_tasks()] == expected


@then(parsers.parse('"{parent}" holds "{child}"'))
def it_holds(ctx, parent, child):
    held = ctx.project.get_subtasks(_find(ctx, parent).id)
    assert [t.name for t in held] == [child]


@then(parsers.parse('"{name}"\'s parent is "{parent}"'))
def its_parent_is(ctx, name, parent):
    parent_task = ctx.project.get_parent_task(_find(ctx, name).id)
    assert parent_task.id == _find(ctx, parent).id


@then("every level can hold rows")
def every_level_can_hold_rows(ctx):
    for task in (ctx.level1, ctx.level2, ctx.level3):
        assert task.can_have_children, task.name


@then(parsers.parse('the summaries are "{names}"'))
def the_summaries_are(ctx, names):
    expected = {n.strip() for n in names.split(',')}
    found = {t.name for t in ctx.project.tasks
             if t.id in ctx.project.get_summary_task_ids()}
    assert found == expected


@then(parsers.parse('the critical path is "{names}"'))
def the_critical_path_is(ctx, names):
    expected = [n.strip() for n in names.split(',')]
    assert [t.name for t in ctx.project.get_critical_path()] == expected


# ------------------------------------------------------------------
# which types can hold rows
# ------------------------------------------------------------------

@given(parsers.parse('a row of type "{task_type}"'))
def a_row_of_type(ctx, task_type):
    ctx.project = Project(name="Type Test")
    if task_type == "Phase":
        ctx.task = Task.create_task("Phase", START,
                                    START + timedelta(days=10))
        ctx.task.task_type = "Phase"
    elif task_type == "Subtask":
        parent = Task.create_task("Parent", START,
                                  START + timedelta(days=10))
        ctx.task = Task.create_subtask("Subtask", parent_task=parent)
    elif task_type == "Milestone":
        ctx.task = Task.create_milestone("Milestone", START)
    else:
        ctx.task = Task.create_task("Task", START,
                                    START + timedelta(days=10))
    ctx.project.add_task(ctx.task)


@then(parsers.parse('it "{can}" hold rows'))
def it_can_or_cannot_hold_rows(ctx, can):
    assert ctx.task.can_have_children == (can == "can")


@then(parsers.parse('it is "{stance}"'))
def it_is_a_leaf_or_container(ctx, stance):
    if stance == "a leaf":
        assert ctx.task.is_leaf
    elif stance == "a container":
        assert ctx.task.is_container
        assert not ctx.task.is_leaf
    else:
        assert not ctx.task.is_leaf


@then(parsers.parse('a saved "{task_type}" opens as a "{result}"'))
def a_saved_type_opens_as(ctx, task_type, result):
    ctx.task = Task(id="s", name="S", start_date=START,
                    end_date=None if task_type == "Milestone" else START,
                    task_type=task_type)
    assert ctx.task.task_type == result


# ------------------------------------------------------------------
# rows keep their type wherever they are moved
# ------------------------------------------------------------------

@given("the rows")
def the_rows(ctx, datatable):
    ctx.project = _plan_from_rows(datatable[1:])


@given("the flat rows")
def the_flat_rows(ctx, datatable):
    rows = [(row[0], "Task", "") for row in datatable[1:]]
    ctx.project = _plan_from_rows(rows)


@given(parsers.parse('"{task_id}" is made a phase'))
def it_is_made_a_phase(ctx, task_id):
    _find(ctx, task_id).task_type = "Phase"


@when(parsers.parse('"{task_id}" is indented'))
def one_is_indented(ctx, task_id):
    ctx.result = ctx.project.indent_task(task_id)


@when(parsers.parse('"{task_id}" is outdented'))
def one_is_outdented(ctx, task_id):
    ctx.result = ctx.project.outdent_task(task_id)


@when(parsers.parse('"{ids}" are indented'))
def several_are_indented(ctx, ids):
    ctx.result = ctx.project.indent_tasks(
        [i.strip() for i in ids.split(',')])


@when(parsers.parse('"{ids}" are outdented'))
def several_are_outdented(ctx, ids):
    ctx.result = ctx.project.outdent_tasks(
        [i.strip() for i in ids.split(',')])


@then("indenting nothing reports it moved nothing")
def indenting_nothing_reports(ctx):
    assert not ctx.project.indent_tasks([])


@then("outdenting nothing reports it moved nothing")
def outdenting_nothing_reports(ctx):
    assert not ctx.project.outdent_tasks([])


@then(parsers.parse('"{task_id}" can hold rows'))
def it_can_hold_rows(ctx, task_id):
    assert _find(ctx, task_id).can_have_children


@then(parsers.parse('"{task_id}" is still a milestone'))
def it_is_still_a_milestone(ctx, task_id):
    assert _find(ctx, task_id).is_milestone


@then(parsers.parse('"{task_id}" is at the top level'))
def it_is_at_the_top(ctx, task_id):
    assert _find(ctx, task_id).parent_task_id is None


def _shape_map(text):
    """Turn "A:-, B:A, C:A" into {id: parent-or-None}."""
    return {
        pair.split(':')[0].strip(): (
            None if pair.split(':')[1].strip() == '-'
            else pair.split(':')[1].strip())
        for pair in text.split(',')
    }


@then(parsers.parse('the shape is "{shape}"'))
def the_shape_is(ctx, shape):
    expected = _shape_map(shape)
    assert [(t.id, t.parent_task_id) for t in ctx.project.tasks] == \
        list(expected.items())


@then(parsers.parse('the parents are "{shape}"'))
def the_parents_are(ctx, shape):
    expected = _shape_map(shape)
    found = {t.id: t.parent_task_id for t in ctx.project.tasks}
    assert found == expected


# ------------------------------------------------------------------
# the outline level
# ------------------------------------------------------------------

@given("a chain of one task")
def a_chain_of_one_task(ctx):
    a_chain_of_tasks(ctx, 1)


@given(parsers.parse('a chain of {count:d} task'))
@given(parsers.parse('a chain of {count:d} tasks'))
def a_chain_of_tasks(ctx, count):
    ctx.project = Project(name="Levels")
    for index in range(1, count + 1):
        parent = str(index - 1) if index > 1 else None
        ctx.project.add_task(Task(id=str(index), name=f"Task {index}",
                                  start_date=datetime(2026, 8, 19),
                                  parent_task_id=parent))


@given("a two-row plan whose second row's parent is gone")
def an_orphaned_plan(ctx):
    ctx.project = Project(name="Levels")
    for index, parent in enumerate((None, 'gone'), start=1):
        ctx.project.add_task(Task(id=str(index), name=f"Task {index}",
                                  start_date=datetime(2026, 8, 19),
                                  parent_task_id=parent))


@then(parsers.parse('"{task_id}" sits at level {level:d}'))
def it_sits_at_level(ctx, task_id, level):
    assert ctx.project.outline_level(task_id) == level


@when(parsers.parse('"{task_id}" is pointed at "{parent}"'))
def it_is_pointed_at(ctx, task_id, parent):
    ctx.project.get_task_by_id(task_id).parent_task_id = parent


@then(parsers.parse('"{task_id}" still answers a level of at least '
                    '{level:d}'))
def it_still_answers_a_level(ctx, task_id, level):
    assert ctx.project.outline_level(task_id) >= level


# ------------------------------------------------------------------
# a task answers its own length
# ------------------------------------------------------------------

@given("a five-working-day task")
def a_five_working_day_task(ctx):
    ctx.task = Task(id="T", name="T", task_type="Task",
                    start_date=datetime(2026, 1, 5),
                    end_date=datetime(2026, 1, 9))


@then("its working calendar is a real calendar")
def its_working_calendar_is_real(ctx):
    assert isinstance(ctx.task.working_calendar, WorkingCalendar)


@then(parsers.parse('it measures {days:d} working days'))
def it_measures_working_days(ctx, days):
    assert ctx.task.duration_days == days


@then(parsers.parse('its elapsed reach is {days:d} days'))
def its_elapsed_reach_is(ctx, days):
    assert ctx.task.total_elapsed_days == days


@then(parsers.parse('its start settles on "{day}"'))
def its_start_settles_on(ctx, day):
    expected = datetime.strptime(day, "%Y-%m-%d")
    assert ctx.task.effective_start_date == expected


@then("no module stacks classmethod over property")
def no_module_stacks_classmethod_property():
    stacked = []
    root = pathlib.Path(gantt_app.__file__).parent
    for path in root.rglob('*.py'):
        lines = path.read_text(encoding='utf-8').splitlines()
        for number, line in enumerate(lines[:-1], start=1):
            if (line.strip() == '@classmethod'
                    and lines[number].strip() == '@property'):
                stacked.append(f"{path.name}:{number}")
    assert stacked == [], \
        "classmethod(property) was removed in Python 3.13"


@then("it is flagged a milestone")
def it_is_flagged_a_milestone(ctx):
    assert ctx.task.is_milestone
    assert ctx.task.effective_milestone


@then("its end is its start")
def its_end_is_its_start(ctx):
    assert ctx.task.end_date == ctx.task.start_date
