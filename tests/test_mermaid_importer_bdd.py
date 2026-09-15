"""
pytest-bdd tests for the Mermaid importer and exporter.

Run with:
    python3 -m pytest tests/test_mermaid_importer_bdd.py -q

Nothing here needs a display. Converted from test_mermaid_importer.py -
every case carried over.
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Project, Task
from gantt_app.utils.mermaid_importer import (
    MermaidImporter, MermaidExporter,
    import_mermaid_file, export_mermaid_file
)

pytestmark = [
    pytest.mark.mermaid_importer,
]

scenarios("features/mermaid.feature")


#: The sectioned chart several scenarios share.
SECTIONED = """gantt
    title Sectioned Project
    dateFormat YYYY-MM-DD

    section Phase One
    Task 1 :a1, 2024-01-01, 5d
    Task 2 :a2, 2024-01-08, 3d

    section Phase Two
    Task 3 :b1, 2024-02-01, 10d
"""


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def build_full_fidelity() -> Project:
    """A plan with every level, a percentage, a colour and a typed link."""
    base = datetime(2026, 8, 17)
    project = Project(name="Round trip")

    def add(task_id, name, task_type, parent, days,
            progress=0, milestone=False, colour="#1f6aa5"):
        task = Task(
            id=task_id, name=name, task_type=task_type,
            parent_task_id=parent, start_date=base,
            end_date=None if milestone else base + timedelta(days=days),
            progress=progress, is_milestone=milestone, color=colour,
        )
        project.add_task(task)
        return task

    add("P1", "Planning", "Phase", None, 0)
    add("D1", "Signed contract", "Task", "P1", 0)
    add("T1", "Business case", "Subtask", "D1", 4, progress=30,
        colour="#ff0000")
    add("T2", "Procurement", "Subtask", "D1", 9).add_dependency(
        "T1", 'FS', 'Hard')
    add("P2", "Delivery", "Phase", None, 0)
    add("T3", "Build", "Subtask", "P2", 9, progress=100).add_dependency(
        "T2", 'SS', 'Hard', 2)
    add("M1", "Go-Live", "Milestone", "P2", 0,
        milestone=True).add_dependency("T3", 'FS', 'Hard')

    project.reschedule()
    return project


def snapshot(project):
    """Everything about a plan that ought to survive."""
    return [
        (task.id, task.name, task.task_type, task.parent_task_id,
         task.progress, task.color, task.start_date,
         task.end_date, task.is_milestone,
         sorted((link.task_id, link.dep_type, link.hardness, link.lag)
                for link in task.dependencies))
        for task in project.tasks
    ]


def two_task_plan(name, start, second_start_offset=6,
                  first_days=5, second_days=10):
    """Task 1 then Task 2, as several scenarios share them."""
    project = Project(name=name)
    project.add_task(Task.create_task(
        "Task 1", start, start + timedelta(days=first_days)))
    project.add_task(Task.create_task(
        "Task 2", start + timedelta(days=second_start_offset),
        start + timedelta(days=second_days)))
    return project


# ------------------------------------------------------------------
# WHEN - importing
# ------------------------------------------------------------------

@when("this Mermaid chart is imported", target_fixture="ctx")
def this_mermaid_chart_is_imported(docstring):
    project = MermaidImporter()._parse_mermaid_content(docstring)
    return SimpleNamespace(project=project)


@when("the sectioned Mermaid chart is imported", target_fixture="ctx")
def the_sectioned_chart_is_imported():
    project = MermaidImporter()._parse_mermaid_content(SECTIONED)
    return SimpleNamespace(project=project)


@when("the sectioned Mermaid chart is imported without section grouping",
      target_fixture="ctx")
def the_sectioned_chart_imported_flat():
    importer = MermaidImporter(group_by_section=False)
    project = importer._parse_mermaid_content(SECTIONED)
    return SimpleNamespace(project=project)


@when("a nonexistent Mermaid file is imported", target_fixture="ctx")
def a_nonexistent_mermaid_file(tmp_path):
    missing = tmp_path / "no-such.mmd"
    return SimpleNamespace(project=MermaidImporter()
                           .import_mermaid(str(missing)))


# ------------------------------------------------------------------
# GIVEN - plans to export
# ------------------------------------------------------------------

@given(parsers.parse('a plan named "{name}" with tasks from "{day}"'),
       target_fixture="ctx")
def a_plan_with_tasks_from(name, day):
    start = datetime.fromisoformat(day)
    return SimpleNamespace(project=two_task_plan(name, start))


@given(parsers.parse('a plan named "{name}" with linked tasks from "{day}"'),
       target_fixture="ctx")
def a_plan_with_linked_tasks_from(name, day):
    start = datetime.fromisoformat(day)
    project = Project(name=name)

    task1 = Task.create_task("Task 1", start, start + timedelta(days=5))
    project.add_task(task1)

    task2 = Task.create_task("Task 2", start + timedelta(days=6),
                             start + timedelta(days=10))
    task2.dependencies = [task1.id]
    project.add_task(task2)
    project.reschedule()
    return SimpleNamespace(project=project)


@given(parsers.parse('a plan named "{name}" holding a milestone on "{day}"'),
       target_fixture="ctx")
def a_plan_holding_a_milestone(name, day):
    project = Project(name=name)
    project.add_task(Task.create_milestone(
        "Milestone 1", datetime.fromisoformat(day)))
    return SimpleNamespace(project=project)


@given(parsers.parse('a plan named "{name}" holding a start-start linked '
                     'task'), target_fixture="ctx")
def a_plan_with_a_start_start_link(name):
    start = datetime(2024, 1, 1)
    project = Project(name=name)

    first = Task.create_task("First", start, start + timedelta(days=4))
    project.add_task(first)
    second = Task.create_task("Second", start, start + timedelta(days=9))
    second.add_dependency(first.id, 'SS', 'Hard')
    project.add_task(second)
    project.reschedule()
    ctx = SimpleNamespace(project=project)
    ctx.second = second
    return ctx


@given(parsers.parse('a plan named "{name}" holding one task'),
       target_fixture="ctx")
def a_plan_holding_one_task(name):
    project = Project(name=name)
    start = datetime(2024, 1, 1)
    project.add_task(Task.create_task("Task", start,
                                      start + timedelta(days=1)))
    return SimpleNamespace(project=project)


@given(parsers.parse('a plan holding an "{first}" and an "{second}"'),
       target_fixture="ctx")
def a_plan_holding_statused_tasks(first, second):
    project = Project(name="Status")
    start = datetime(2024, 1, 1)
    estimated = Task.create_task(first, start, start + timedelta(days=2))
    estimated.status = 'Estimated'
    project.add_task(estimated)
    project.add_task(Task.create_task(second, start,
                                      start + timedelta(days=2)))
    return SimpleNamespace(project=project)


@given("the sectioned Mermaid chart as a plan", target_fixture="ctx")
def the_sectioned_chart_as_a_plan():
    content = """gantt
    title Sectioned
    dateFormat YYYY-MM-DD
    section Phase One
    Task 1 :a1, 2024-01-01, 5d
    Task 2 :a2, after a1, 3d
    section Phase Two
    Task 3 :b1, 2024-02-01, 10d
"""
    project = MermaidImporter()._parse_mermaid_content(content)
    return SimpleNamespace(project=project)


@given("the chained Mermaid chart as a plan", target_fixture="ctx")
def the_chained_chart_as_a_plan():
    content = """gantt
    title Dates
    dateFormat YYYY-MM-DD
    section Phase One
    Task 1 :a1, 2024-01-01, 5d
    Task 2 :a2, after a1, 3d
"""
    project = MermaidImporter()._parse_mermaid_content(content)
    return SimpleNamespace(project=project)


@given("the duplicate-named chart as a plan", target_fixture="ctx")
def the_duplicate_named_chart_as_a_plan():
    content = """gantt
    title Dup
    section Work
    T1 :a1, 2024-01-01, 3d
    section Other
    T2 :a2, 2024-01-08, 3d
"""
    project = MermaidImporter()._parse_mermaid_content(content)
    roots = project.get_root_tasks()
    assert len(roots) == 2
    # Make the two distinct parents share a name
    roots[1].name = roots[0].name
    return SimpleNamespace(project=project)


@given("the agreement chart as a plan", target_fixture="ctx")
def the_agreement_chart_as_a_plan():
    content = """gantt
    title Agreement
    section Phase One
    Task 1 :a1, 2024-01-01, 5d
"""
    project = MermaidImporter()._parse_mermaid_content(content)
    return SimpleNamespace(project=project)


@given("the full-fidelity plan", target_fixture="ctx")
def the_full_fidelity_plan():
    return SimpleNamespace(project=build_full_fidelity())


# ------------------------------------------------------------------
# WHEN - exporting
# ------------------------------------------------------------------

@when("the plan is exported to Mermaid text")
def the_plan_is_exported_to_text(ctx):
    ctx.content = MermaidExporter().export_mermaid_content(ctx.project)


@when("the plan is exported to a Mermaid file")
def the_plan_is_exported_to_a_file(ctx, tmp_path):
    ctx.path = tmp_path / "chart.mmd"
    ctx.exported_ok = export_mermaid_file(ctx.project, str(ctx.path))


@when("the plan is exported to a Mermaid file in a missing subdirectory")
def the_plan_is_exported_to_a_missing_dir(ctx, tmp_path):
    ctx.path = tmp_path / "subdir" / "test.mmd"
    ctx.exported_ok = export_mermaid_file(ctx.project, str(ctx.path))


@when("the plan is exported and imported back through Mermaid")
def the_plan_round_trips(ctx, tmp_path):
    path = tmp_path / "plan.mmd"
    assert export_mermaid_file(ctx.project, str(path))
    if path.exists():
        ctx.exported_text = path.read_text(encoding='utf-8')
    ctx.imported = import_mermaid_file(str(path))
    assert ctx.imported is not None


@when("the plan is exported and imported back through Mermaid, then "
      "rescheduled")
def the_plan_round_trips_and_reschedules(ctx, tmp_path):
    path = tmp_path / "plan.mmd"
    assert export_mermaid_file(ctx.project, str(path))
    ctx.imported = import_mermaid_file(str(path))
    assert ctx.imported is not None
    ctx.imported.reschedule()


@when("the plan is exported to Mermaid text and imported back")
def the_plan_is_exported_to_text_and_back(ctx):
    ctx.content = MermaidExporter().export_mermaid_content(ctx.project)
    ctx.imported = MermaidImporter()._parse_mermaid_content(ctx.content)


# ------------------------------------------------------------------
# THEN - parsing
# ------------------------------------------------------------------

@then(parsers.parse('the imported project is named "{name}"'))
def the_project_is_named(ctx, name):
    assert ctx.project is not None
    assert ctx.project.name == name


@then("the imported project is not nothing")
def the_project_is_not_nothing(ctx):
    assert ctx.project is not None


@then(parsers.parse('it holds {count:d} tasks'))
def it_holds_tasks(ctx, count):
    assert ctx.project is not None
    assert len(ctx.project.tasks) == count


@then("nothing comes back")
def nothing_comes_back(ctx):
    assert ctx.project is None


@then("both are milestones with no end date")
def both_are_milestones(ctx):
    for task in ctx.project.tasks:
        assert task.is_milestone
        assert task.end_date is None


@then(parsers.parse('the imported task "{task_id}" is named "{name}"'))
def the_task_is_named(ctx, task_id, name):
    assert ctx.project.get_task_by_id(task_id).name == name


@then(parsers.parse('the imported task "{task_id}" starts on "{start}" and '
                    'ends on "{end}"'))
def the_task_starts_and_ends(ctx, task_id, start, end):
    task = ctx.project.get_task_by_id(task_id)
    assert task.start_date == datetime.fromisoformat(start)
    assert task.end_date == datetime.fromisoformat(end)


@then(parsers.parse('the imported task "{task_id}" starts on "{start}"'))
def the_task_starts_on(ctx, task_id, start):
    task = ctx.project.get_task_by_id(task_id)
    assert task.start_date == datetime.fromisoformat(start)


@then(parsers.parse('the imported task "{task_id}" lasts {days:d} days'))
def the_task_lasts(ctx, task_id, days):
    assert ctx.project.get_task_by_id(task_id).duration_days == days


@then(parsers.parse('the imported task "{task_id}" waits on "{other}"'))
def the_task_waits_on(ctx, task_id, other):
    assert ctx.project.get_task_by_id(task_id).dependency_ids == [other]


@then(parsers.parse('the imported task "{task_id}" is a milestone and '
                    '"{other}" is not'))
def the_task_is_a_milestone_and_other_is_not(ctx, task_id, other):
    milestone = ctx.project.get_task_by_id(task_id)
    task = ctx.project.get_task_by_id(other)
    assert milestone.is_milestone
    assert not task.is_milestone


@then(parsers.parse('the imported task "{task_id}" sits at the top level'))
def the_task_sits_at_top_level(ctx, task_id):
    assert ctx.project.get_task_by_id(task_id).parent_task_id is None


@then(parsers.parse('the imported task "{task_id}" is a "{task_type}"'))
def the_task_is_a_type(ctx, task_id, task_type):
    assert ctx.project.get_task_by_id(task_id).task_type == task_type


@then(parsers.parse('the imported "{name}" starts on "{start}" and ends on '
                    '"{end}"'))
def the_named_task_starts_and_ends(ctx, name, start, end):
    task = next(t for t in ctx.project.get_root_tasks() if t.name == name)
    assert task.start_date == datetime.fromisoformat(start)
    assert task.end_date == datetime.fromisoformat(end)


@then(parsers.parse('the imported "{name}" is {percent:d} percent done'))
def the_named_task_is_percent_done(ctx, name, percent):
    task = next(t for t in ctx.project.tasks if t.name == name)
    assert task.progress == percent


@then(parsers.parse('the imported "{name}" waits on "{task_id}"'))
def the_named_task_waits_on(ctx, name, task_id):
    task = next(t for t in ctx.project.tasks if t.name == name)
    assert task.dependency_ids == [task_id]


@then(parsers.parse('the imported "{name}" is a milestone'))
def the_named_task_is_a_milestone(ctx, name):
    task = next(t for t in ctx.project.tasks if t.name == name)
    assert task.is_milestone


@then(parsers.parse('the imported task names are "{name}"'))
def the_imported_task_names_are(ctx, name):
    assert [task.name for task in ctx.project.tasks] == [name]


# ------------------------------------------------------------------
# THEN - date/duration parsing
# ------------------------------------------------------------------

@then(parsers.parse('"{text}" parses as "{day}"'))
def the_date_parses_as(text, day):
    result = MermaidImporter()._parse_date(text, "%Y-%m-%d")
    assert result == datetime.fromisoformat(day)


@then(parsers.parse('"{text}" parses as nothing'))
def the_date_parses_as_nothing(text):
    assert MermaidImporter()._parse_date(text, "%Y-%m-%d") is None


@then(parsers.parse('"{duration}" from "{start}" ends on "{end}"'))
def the_duration_ends_on(duration, start, end):
    result = MermaidImporter()._parse_duration(
        duration, datetime.fromisoformat(start))
    assert result == datetime.fromisoformat(end)


# ------------------------------------------------------------------
# THEN - sections
# ------------------------------------------------------------------

@then(parsers.parse('the root tasks are "{a}" and "{b}"'))
def the_root_tasks_are(ctx, a, b):
    roots = ctx.project.get_root_tasks()
    assert [t.name for t in roots] == [a, b]


@then(parsers.parse('the root tasks are "{a}" and "{b}" with distinct ids'))
def the_root_tasks_have_distinct_ids(ctx, a, b):
    roots = ctx.project.get_root_tasks()
    assert len(roots) == 2
    assert [t.name for t in roots] == [a, b]
    assert roots[0].id != roots[1].id
    ctx.roots = roots


@then(parsers.parse('"{phase}" holds "{a}" and "{b}" as subtasks'))
def the_phase_holds_subtasks(ctx, phase, a, b):
    parent = next(t for t in ctx.project.get_root_tasks()
                  if t.name == phase)
    assert parent.task_type == "Task"
    subtasks = ctx.project.get_subtasks(parent.id)
    assert [t.name for t in subtasks] == [a, b]
    for subtask in subtasks:
        assert subtask.task_type == "Subtask"


@then(parsers.parse('the first "{a}" holds "{ta}" and the second holds '
                    '"{tb}"'))
def the_two_named_roots_hold(ctx, a, ta, tb):
    roots = ctx.roots
    assert [t.name for t in ctx.project.get_subtasks(roots[0].id)] == [ta]
    assert [t.name for t in ctx.project.get_subtasks(roots[1].id)] == [tb]


@then(parsers.parse('the task order is "{a}", "{b}", "{c}", "{d}" and '
                    '"{e}"'))
def the_task_order_is(ctx, a, b, c, d, e):
    names = [t.name for t in ctx.project.tasks]
    assert names == [a, b, c, d, e]


@then(parsers.parse('it holds {count:d} tasks, all at the top level'))
def it_holds_flat_tasks(ctx, count):
    assert len(ctx.project.tasks) == count
    assert all(t.parent_task_id is None for t in ctx.project.tasks)


@then("every imported task id is unique")
def every_task_id_is_unique(ctx):
    ids = [t.id for t in ctx.project.tasks]
    assert len(ids) == len(set(ids))


# ------------------------------------------------------------------
# THEN - exporting
# ------------------------------------------------------------------

@then(parsers.parse('the content opens with "{text}"'))
def the_content_opens_with(ctx, text):
    assert text in ctx.content


@then(parsers.parse('the content names "{text}"'))
def the_content_names(ctx, text):
    assert f"title {text}" in ctx.content or text in ctx.content


@then(parsers.parse('the content carries "{text}"'))
def the_content_carries(ctx, text):
    assert text in ctx.content


@then(parsers.parse('the content carries both "{a}" and "{b}"'))
def the_content_carries_both(ctx, a, b):
    assert a in ctx.content
    assert b in ctx.content


@then(parsers.parse('the row for "{name}" is written without "{word}"'))
def the_row_is_written_without(ctx, name, word):
    rows = [line for line in ctx.content.splitlines()
            if name in line and not line.strip().startswith('%%')]
    assert len(rows) == 1
    assert word not in rows[0]
    ctx.row = rows[0]


@then(parsers.parse('the row for "{name}" carries the task\'s own start '
                    'date'))
def the_row_carries_the_start_date(ctx, name):
    assert ctx.second.start_date.strftime('%Y-%m-%d') in ctx.row


@then(parsers.parse('the file exists and opens with "{text}"'))
def the_file_exists_and_opens_with(ctx, text):
    assert ctx.exported_ok
    assert ctx.path.exists()
    assert text in ctx.path.read_text(encoding='utf-8')


@then("the file exists")
def the_file_exists(ctx):
    assert ctx.exported_ok
    assert ctx.path.exists()


# ------------------------------------------------------------------
# THEN - round trips
# ------------------------------------------------------------------

@then("it holds as many tasks as went out")
def it_holds_as_many(ctx):
    assert len(ctx.imported.tasks) == len(ctx.project.tasks)


@then("every task name survived")
def every_task_name_survived(ctx):
    original_names = {t.name for t in ctx.project.tasks}
    imported_names = {t.name for t in ctx.imported.tasks}
    assert original_names == imported_names


@then(parsers.parse('the imported "{name}" has status "{status}"'))
def the_task_has_status(ctx, name, status):
    statuses = {task.name: task.status for task in ctx.imported.tasks}
    assert statuses.get(name) == status


@then(parsers.parse('the exported text names "{a}" and "{b}"'))
def the_exported_text_names(ctx, a, b):
    assert a in ctx.exported_text
    assert b in ctx.exported_text


@then("the subtask names match what went out")
def the_subtask_names_match(ctx):
    original_subtasks = {t.name for t in ctx.project.tasks
                         if t.parent_task_id}
    imported_subtasks = {t.name for t in ctx.imported.tasks
                         if t.parent_task_id}
    assert original_subtasks == imported_subtasks


@then("every task's dates match what went out")
def every_tasks_dates_match(ctx):
    original_by_name = {t.name: t for t in ctx.project.tasks}
    imported_by_name = {t.name: t for t in ctx.imported.tasks}
    for name, task in original_by_name.items():
        other = imported_by_name[name]
        assert task.start_date == other.start_date, name
        assert task.end_date == other.end_date, name


@then(parsers.parse('the exported text carries "{text}" twice'))
def the_exported_text_carries_twice(ctx, text):
    assert ctx.content.count(text) == 2


@then(parsers.parse('the re-import has {count:d} root tasks'))
def the_reimport_has_roots(ctx, count):
    assert len(ctx.imported.get_root_tasks()) == count


@then("the class exporter and the function exporter agree")
def the_exporters_agree(ctx):
    from gantt_app.utils.mermaid_exporter import generate_mermaid_content
    assert MermaidExporter().export_mermaid_content(ctx.project) == \
        generate_mermaid_content(ctx.project)


@then(parsers.parse('the imported "{a}" and "{b}" are both there'))
def both_tasks_are_there(ctx, a, b):
    names = {t.name for t in ctx.imported.tasks}
    assert a in names
    assert b in names


# ------------------------------------------------------------------
# THEN - the faithful round trip
# ------------------------------------------------------------------

@then("every task's full snapshot matches what went out")
def every_task_matches(ctx):
    assert snapshot(ctx.imported) == snapshot(ctx.project)


@then(parsers.parse('"{p}" is a "Phase", "{d}" a "Task" under it, and '
                    '"{t}" a "Subtask" under "{d}"'))
def the_levels_survive(ctx, p, d, t):
    types = {task.id: task.task_type for task in ctx.imported.tasks}
    assert types[p] == "Phase"
    assert types[d] == "Task"
    assert ctx.imported.get_task_by_id(d).parent_task_id == p
    assert ctx.imported.get_task_by_id(t).parent_task_id == d


@then(parsers.parse('the reimported "{name}" is {percent:d} percent done'))
def the_imported_percent_survives(ctx, name, percent):
    assert ctx.imported.get_task_by_id(name).progress == percent


@then(parsers.parse('the imported "{name}" link is "{dep_type}" lagged '
                    '{lag:d} days'))
def the_link_kind_survives(ctx, name, dep_type, lag):
    link = ctx.imported.get_task_by_id(name).dependencies[0]
    assert (link.dep_type, link.lag) == (dep_type, lag)


@then(parsers.parse('the imported "{name}" starts where it started'))
def the_task_keeps_its_date(ctx, name):
    assert ctx.imported.get_task_by_id(name).start_date == \
        ctx.project.get_task_by_id(name).start_date


@then(parsers.parse('the first line is "{text}"'))
def the_first_line_is(ctx, text):
    lines = [line.strip() for line in ctx.content.splitlines()]
    assert lines[0] == text


@then(parsers.parse('a "{prefix}" comment line is present'))
def a_comment_line_is_present(ctx, prefix):
    lines = [line.strip() for line in ctx.content.splitlines()]
    assert any(line.startswith(prefix) for line in lines)


@then(parsers.parse('a "{prefix}" line is present'))
def a_section_line_is_present(ctx, prefix):
    lines = [line.strip() for line in ctx.content.splitlines()]
    assert any(line.startswith(prefix) for line in lines)


@then(parsers.parse('the line "{line}" is present'))
def the_line_is_present(ctx, line):
    lines = [l.strip() for l in ctx.content.splitlines()]
    assert line in lines
