"""
pytest-bdd tests for the GAN export: the plan as a GanttProject file.

Run with:
    python3 -m pytest tests/test_gan_exporter_bdd.py -q

Nothing here needs a display. Converted from test_gan_exporter.py -
every case carried over.
"""
import os
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Project, Task
from gantt_app.utils.gan_exporter import (
    export_project_to_gan, generate_gan_content,
)
from gantt_app.utils.gan_importer import import_gan_file
from gantt_app.core.workdaycalendar import WorkingCalendar

pytestmark = [
    pytest.mark.gan_exporter,
]

scenarios("features/gan_export.feature")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def sample_project() -> Project:
    """A plan with a phase, nested work, a link, a milestone and a holiday."""
    project = Project(name="Tosca Implementation")
    base = datetime(2026, 7, 6)          # a Monday

    phase = Task(id="P1", name="Procurement", task_type="Phase",
                 start_date=base, end_date=base + timedelta(days=16))
    project.add_task(phase)

    project.add_task(Task(id="T1", name="Business case", task_type="Task",
                          parent_task_id="P1", start_date=base,
                          end_date=base + timedelta(days=4), progress=50,
                          details="Signed off by the steering group"))
    project.add_task(Task(id="T2", name="Tender", task_type="Task",
                          parent_task_id="P1",
                          start_date=base + timedelta(days=7),
                          end_date=base + timedelta(days=16),
                          dependencies=["T1"]))
    project.add_task(Task(id="M1", name="Contract signed",
                          task_type="Milestone",
                          start_date=base + timedelta(days=21),
                          dependencies=["T2"]))

    project.calendar.holidays.add(datetime(2026, 7, 8).date())
    project.calendar.recurring_holidays.add((12, 25))
    return project


def task_by_name(root, name):
    """Find one <task> element anywhere in the outline."""
    for element in root.iter('task'):
        if element.get('name') == name:
            return element
    raise AssertionError(f"No task named {name!r} in the exported file")


# ------------------------------------------------------------------
# GIVEN
# ------------------------------------------------------------------

@given("the sample Tosca Implementation plan", target_fixture="ctx")
def the_sample_plan():
    return SimpleNamespace(project=sample_project())


@given(parsers.parse('an empty plan named "{name}"'), target_fixture="ctx")
def an_empty_plan(name):
    return SimpleNamespace(project=Project(name=name))


@given(parsers.parse('a plan with a task depending on "{task_id}"'),
       target_fixture="ctx")
def a_plan_with_a_dangling_link(task_id):
    project = Project(name="Dangling")
    base = datetime(2026, 7, 6)
    project.add_task(Task(id="T1", name="Work", start_date=base,
                          end_date=base, dependencies=[task_id]))
    return SimpleNamespace(project=project)


@given("a plan working Saturdays holding a seven-day task",
       target_fixture="ctx")
def a_plan_working_saturdays():
    project = Project(name="Six days",
                      calendar=WorkingCalendar(non_working_days={6}))
    base = datetime(2026, 7, 6)
    project.add_task(Task(id="T1", name="Work", start_date=base,
                          end_date=base + timedelta(days=6)))
    return SimpleNamespace(project=project)


@given("a plan with a task that has no end date", target_fixture="ctx")
def a_plan_with_an_open_ended_task():
    project = Project(name="Open ended")
    project.add_task(Task(id="T1", name="Work",
                          start_date=datetime(2026, 7, 6), end_date=None))
    return SimpleNamespace(project=project)


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------

@when("the plan is exported to GanttProject XML")
def the_plan_is_exported(ctx):
    ctx.root = ET.fromstring(generate_gan_content(ctx.project))


@when("the plan is exported and imported back")
def the_plan_is_exported_and_imported_back(ctx, tmp_path):
    path = tmp_path / "plan.gan"
    assert export_project_to_gan(ctx.project, str(path))
    ctx.imported = import_gan_file(str(path))


@when("the plan is exported to a path that cannot be written")
def the_plan_is_exported_to_a_bad_path(ctx):
    ctx.exported_ok = export_project_to_gan(
        ctx.project,
        os.path.join(tempfile.gettempdir(), "no-such\0path.gan"))


# ------------------------------------------------------------------
# THEN - document shape
# ------------------------------------------------------------------

@then(parsers.parse('the root is a "{tag}" element named "{name}"'))
def the_root_is_named(ctx, tag, name):
    assert ctx.root.tag == tag
    assert ctx.root.get('name') == name


@then(parsers.parse('the task "{parent}" nests "{first}" and "{second}"'))
def the_task_nests(ctx, parent, first, second):
    phase = task_by_name(ctx.root, parent)
    nested = [child.get('name') for child in phase.findall('task')]
    assert nested == [first, second]


@then(parsers.parse('the task "{name}" carries no parent attribute'))
def the_task_carries_no_parent(ctx, name):
    assert task_by_name(ctx.root, name).get('parent') is None


@then(parsers.parse('the task "{first}" depends on the exported id of '
                    '"{second}"'))
def the_task_depends_on(ctx, first, second):
    first_el = task_by_name(ctx.root, first)
    second_el = task_by_name(ctx.root, second)
    depends = first_el.findall('depend')
    assert len(depends) == 1
    assert depends[0].get('id') == second_el.get('id')
    ctx.depend = depends[0]


@then("that depend reads as a strong Finish-Start")
def the_depend_is_strong_fs(ctx):
    assert ctx.depend.get('type') == '2'
    assert ctx.depend.get('hardness') == 'Strong'


@then(parsers.parse('the task "{name}" carries no depend elements'))
def the_task_carries_no_depends(ctx, name):
    assert task_by_name(ctx.root, name).findall('depend') == []


@then(parsers.parse('the task "{name}" is a meeting of zero duration'))
def the_task_is_a_meeting(ctx, name):
    milestone = task_by_name(ctx.root, name)
    assert milestone.get('meeting') == 'true'
    assert milestone.get('duration') == '0'


@then(parsers.parse('the task "{name}" has a duration of "{days}"'))
def the_task_has_a_duration(ctx, name, days):
    assert task_by_name(ctx.root, name).get('duration') == days


@then(parsers.parse('the task "{name}" is "{percent}" percent complete'))
def the_task_is_percent_complete(ctx, name, percent):
    assert task_by_name(ctx.root, name).get('complete') == percent


@then(parsers.parse('the task "{name}" notes read "{text}"'))
def the_task_notes_read(ctx, name, text):
    assert task_by_name(ctx.root, name).find('notes').text == text


@then("the default week works Monday and rests Saturday and Sunday")
def the_default_week_is_declared(ctx):
    week = ctx.root.find('.//default-week')
    assert week.get('mon') == '0'
    assert week.get('sat') == '1'
    assert week.get('sun') == '1'


@then(parsers.parse('one calendar date reads month "{month}" day "{day}" '
                    'with no year'))
def one_calendar_date_reads(ctx, month, day):
    entries = [element for element in ctx.root.findall('calendars/date')
               if element.get('month') == month
               and element.get('date') == day]
    assert len(entries) == 1
    assert entries[0].get('year') == ''


@then(parsers.parse('one calendar date reads year "{year}" month "{month}" '
                    'day "{day}"'))
def one_dated_calendar_date_reads(ctx, year, month, day):
    entries = [element for element in ctx.root.findall('calendars/date')
               if element.get('year') == year
               and element.get('month') == month
               and element.get('date') == day]
    assert len(entries) == 1


@then(parsers.parse('the exported task ids are "{first}" to "{last}"'))
def the_exported_task_ids_are(ctx, first, last):
    ids = [element.get('id') for element in ctx.root.iter('task')]
    assert ids == [str(n) for n in range(int(first), int(last) + 1)]


@then("the tasks element holds no task elements")
def the_tasks_element_is_empty(ctx):
    assert list(ctx.root.find('tasks').iter('task')) == []


@then("no depend element is written")
def no_depend_element_is_written(ctx):
    assert list(ctx.root.iter('depend')) == []


@then("the default week works Saturday and rests Sunday")
def the_default_week_works_saturday(ctx):
    week = ctx.root.find('.//default-week')
    assert week.get('sat') == '0'
    assert week.get('sun') == '1'


@then("the export reports failure")
def the_export_reports_failure(ctx):
    assert ctx.exported_ok is False


# ------------------------------------------------------------------
# THEN - round trip
# ------------------------------------------------------------------

@then("the imported task names match the plan's, in order")
def the_task_names_match(ctx):
    assert [task.name for task in ctx.imported.tasks] == \
           [task.name for task in ctx.project.tasks]


@then("every imported task's dates match the plan's")
def the_dates_are_the_dates(ctx):
    by_name = {task.name: task for task in ctx.imported.tasks}
    for original in ctx.project.tasks:
        returned = by_name[original.name]
        assert returned.start_date.date() == original.start_date.date(), \
            original.name
        if original.end_date is None:
            assert returned.end_date is None, original.name
        else:
            assert returned.end_date.date() == original.end_date.date(), \
                original.name


@then("the imported calendar rests Saturday and Sunday")
def the_imported_calendar_rests_weekends(ctx):
    assert ctx.imported.calendar.non_working_days == {5, 6}


@then(parsers.parse('the imported calendar lists the holiday on "{day}"'))
def the_imported_calendar_lists_the_holiday(ctx, day):
    assert datetime.fromisoformat(day).date() in ctx.imported.calendar.holidays


@then(parsers.parse('the imported calendar recurs on "{month_day}"'))
def the_imported_calendar_recurs(ctx, month_day):
    month, day = (int(part) for part in month_day.split('-'))
    assert (month, day) in ctx.imported.calendar.recurring_holidays


@then(parsers.parse('the imported "{successor}" waits on "{predecessor}" '
                    'Finish-Start'))
def the_link_comes_back(ctx, successor, predecessor):
    by_name = {task.name: task for task in ctx.imported.tasks}
    numbers = {task.id: name for name, task in by_name.items()}
    task = by_name[successor]
    assert [numbers[d.task_id] for d in task.dependencies] == [predecessor]
    assert [d.dep_type for d in task.dependencies] == ["FS"]


@then(parsers.parse('the imported "{first}" and "{second}" sit under '
                    '"{parent}"'))
def the_children_sit_under(ctx, first, second, parent):
    by_name = {task.name: task for task in ctx.imported.tasks}
    phase = by_name[parent]
    assert by_name[first].parent_task_id == phase.id
    assert by_name[second].parent_task_id == phase.id


@then(parsers.parse('the imported "{name}" sits at the top level'))
def the_task_sits_at_top_level(ctx, name):
    by_name = {task.name: task for task in ctx.imported.tasks}
    assert by_name[name].parent_task_id is None
