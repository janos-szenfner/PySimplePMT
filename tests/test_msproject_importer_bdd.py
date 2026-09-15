"""
pytest-bdd tests for the Microsoft Project import: reading MSPDI.

Run with:
    python3 -m pytest tests/test_msproject_importer_bdd.py -q

Nothing here needs a display, and nothing needs Microsoft Project.
Converted from test_msproject_importer.py - every case carried over.
"""
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Project, Task
from gantt_app.utils.msproject_exporter import export_project_to_msproject
from gantt_app.utils.msproject_importer import (
    import_msproject_file, parse_msproject,
)
from gantt_app.core.workdaycalendar import WorkingCalendar

pytestmark = [
    pytest.mark.msproject_importer,
]

scenarios("features/msproject_import.feature")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def sample_project() -> Project:
    """A plan with a phase, nested work, a lagged link and a milestone."""
    project = Project(name="Tosca Implementation")
    base = datetime(2026, 7, 6)          # a Monday

    project.add_task(Task(id="P1", name="Procurement", task_type="Phase",
                          start_date=base, end_date=base + timedelta(days=16)))
    project.add_task(Task(id="T1", name="Business case", task_type="Task",
                          parent_task_id="P1", start_date=base,
                          end_date=base + timedelta(days=4), progress=50,
                          priority="High",
                          details="Signed off by the steering group"))
    project.add_task(Task(id="T2", name="Tender", task_type="Task",
                          parent_task_id="P1",
                          start_date=base + timedelta(days=7),
                          end_date=base + timedelta(days=16),
                          dependencies=[{'task_id': "T1", 'dep_type': 'SS',
                                         'hardness': 'Hard', 'lag': 2}]))
    project.add_task(Task(id="M1", name="Contract signed",
                          task_type="Milestone",
                          start_date=base + timedelta(days=21),
                          dependencies=["T2"]))

    project.calendar.holidays.add(datetime(2026, 7, 8).date())
    return project


#: The header every one of these documents needs, and nothing more.
HEADER = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
          '<Project xmlns="http://schemas.microsoft.com/project">'
          '<Title>Imported</Title><CalendarUID>1</CalendarUID>')


def document(calendars: str, tasks: str) -> str:
    """One MSPDI document from its two interesting halves."""
    return (f"{HEADER}<Calendars>{calendars}</Calendars>"
            f"<Tasks>{tasks}</Tasks></Project>")


def task(uid, name, level, start, finish, extra=''):
    """One <Task> element with the fields every task needs."""
    return (f"<Task><UID>{uid}</UID><Name>{name}</Name>"
            f"<OutlineLevel>{level}</OutlineLevel>"
            f"<Start>{start}T08:00:00</Start>"
            f"<Finish>{finish}T17:00:00</Finish>{extra}</Task>")


def standard_calendar(body=''):
    """A Monday-to-Friday calendar, with whatever is passed appended."""
    days = ''.join(
        f"<WeekDay><DayType>{code}</DayType>"
        f"<DayWorking>{'0' if code in (1, 7) else '1'}</DayWorking>"
        "</WeekDay>" for code in range(1, 8))
    return (f"<Calendar><UID>1</UID><Name>Standard</Name>"
            f"<WeekDays>{days}</WeekDays>{body}</Calendar>")


def parse(xml_text: str) -> Project:
    """Read a plan out of an MSPDI document held as text."""
    return parse_msproject(ET.fromstring(xml_text))


def by_name(project, name):
    return [t for t in project.tasks if t.name == name][0]


# ------------------------------------------------------------------
# GIVEN
# ------------------------------------------------------------------

@given("the sample Tosca Implementation plan", target_fixture="ctx")
def the_sample_plan():
    return SimpleNamespace(project=sample_project())


@given(parsers.parse('"{name}" is floored to "{day}" by a SNET constraint'))
def a_task_is_floored(ctx, name, day):
    tender = ctx.project.get_task_by_id("T2")
    tender.constraint_type = 'SNET'
    tender.constraint_date = datetime.fromisoformat(day)


@given(parsers.parse('"{name}" follows a weekend-only calendar named '
                     '"{cal_name}"'))
def a_task_follows_a_named_calendar(ctx, name, cal_name):
    weekend = ctx.project.calendars.create(
        cal_name, WorkingCalendar(non_working_days={0, 1, 2, 3, 4}))
    ctx.project.get_task_by_id("T2").calendar_id = weekend.id


# ------------------------------------------------------------------
# WHEN - the round trip
# ------------------------------------------------------------------

@when("the plan is exported and imported back through MSPDI")
def the_plan_round_trips(ctx, tmp_path):
    path = tmp_path / "plan.xml"
    assert export_project_to_msproject(ctx.project, str(path))
    ctx.imported = import_msproject_file(str(path))
    assert ctx.imported is not None
    ctx.by_name = {task.name: task for task in ctx.imported.tasks}


# ------------------------------------------------------------------
# WHEN - documents only Project itself writes
# ------------------------------------------------------------------

@when(parsers.parse('an MSPDI document is imported whose standard calendar '
                    'carries a "{reason}" exception from "{start}" to '
                    '"{end}"'), target_fixture="ctx")
def an_mspdi_document_with_an_exception(start, end, reason):
    exceptions = (f"<Exceptions><Exception><DayWorking>0</DayWorking>"
                  f"<Name>{reason}</Name><TimePeriod>"
                  f"<FromDate>{start}T00:00:00</FromDate>"
                  f"<ToDate>{end}T23:59:00</ToDate>"
                  f"</TimePeriod></Exception></Exceptions>")
    xml = document(standard_calendar(exceptions),
                   task(1, "Work", 1, "2026-07-06", "2026-07-10"))
    return SimpleNamespace(imported=parse(xml))


@when(parsers.parse('an MSPDI document is imported holding a level-0 task '
                    '"{summary}" and a level-1 task "{work}"'),
      target_fixture="ctx")
def an_mspdi_document_with_a_summary_row(summary, work):
    xml = document(standard_calendar(),
                   task(0, summary, 0, "2026-07-06", "2026-07-24")
                   + task(1, work, 1, "2026-07-06", "2026-07-10"))
    return SimpleNamespace(imported=parse(xml))


@when(parsers.parse('an MSPDI document is imported holding a null task and '
                    'a level-1 task "{work}"'), target_fixture="ctx")
def an_mspdi_document_with_a_null_task(work):
    xml = document(standard_calendar(),
                   "<Task><UID>1</UID><IsNull>1</IsNull></Task>"
                   + task(2, work, 1, "2026-07-06", "2026-07-10"))
    return SimpleNamespace(imported=parse(xml))


@when(parsers.parse('an MSPDI document is imported holding a level-1 '
                    'summary "{phase}" and a level-3 task "{deep}"'),
      target_fixture="ctx")
def an_mspdi_document_with_a_skipped_level(phase, deep):
    xml = document(standard_calendar(),
                   task(1, phase, 1, "2026-07-06", "2026-07-24",
                        "<Summary>1</Summary>")
                   + task(2, deep, 3, "2026-07-06", "2026-07-10"))
    return SimpleNamespace(imported=parse(xml))


@when(parsers.parse('an MSPDI document is imported holding a task "{name}" '
                    'finishing at "{moment}"'), target_fixture="ctx")
def an_mspdi_document_with_a_midnight_finish(name, moment):
    xml = document(
        standard_calendar(),
        f"<Task><UID>1</UID><Name>{name}</Name><OutlineLevel>1</OutlineLevel>"
        f"<Start>2026-07-06T08:00:00</Start>"
        f"<Finish>{moment}</Finish></Task>")
    return SimpleNamespace(imported=parse(xml))


@when("an MSPDI document is imported whose calendar never describes its "
      "week", target_fixture="ctx")
def an_mspdi_document_with_a_bare_calendar():
    xml = document(
        "<Calendar><UID>1</UID><Name>Standard</Name></Calendar>",
        task(1, "Work", 1, "2026-07-06", "2026-07-10"))
    return SimpleNamespace(imported=parse(xml))


@when("this namespaceless MSPDI document is imported", target_fixture="ctx")
def a_namespaceless_mspdi_document(docstring):
    return SimpleNamespace(imported=parse(docstring))


@when(parsers.parse('an MSPDI document is imported holding a level-1 task '
                    '"{name}" waiting on task "{missing}"'),
      target_fixture="ctx")
def an_mspdi_document_with_a_dangling_link(name, missing):
    link = (f"<PredecessorLink><PredecessorUID>{missing}</PredecessorUID>"
            f"<Type>1</Type></PredecessorLink>")
    xml = document(standard_calendar(),
                   task(1, name, 1, "2026-07-06", "2026-07-10", link))
    return SimpleNamespace(imported=parse(xml))


@when("a nonexistent MSPDI file is imported", target_fixture="ctx")
def a_nonexistent_mspdi_file(tmp_path):
    missing = tmp_path / "no-such-plan.xml"
    return SimpleNamespace(imported=import_msproject_file(str(missing)))


@when("a truncated MSPDI document is imported", target_fixture="ctx")
def a_truncated_mspdi_document(tmp_path):
    path = tmp_path / "broken.xml"
    path.write_text('<Project><Tasks><Task>', encoding='utf-8')
    return SimpleNamespace(imported=import_msproject_file(str(path)))


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@then(parsers.parse('the imported project is named "{name}"'))
def the_project_is_named(ctx, name):
    assert ctx.imported.name == name


@then("the imported task names match the plan's, in order")
def the_task_names_match(ctx):
    assert [task.name for task in ctx.imported.tasks] == \
           [task.name for task in ctx.project.tasks]


@then("every imported task's dates match the plan's")
def the_dates_are_the_dates(ctx):
    for original in ctx.project.tasks:
        returned = ctx.by_name[original.name]
        assert returned.start_date.date() == original.start_date.date(), \
            original.name
        if original.end_date is None:
            assert returned.end_date is None, original.name
        else:
            assert returned.end_date.date() == original.end_date.date(), \
                original.name


@then(parsers.parse('the imported "{first}" and "{second}" sit under '
                    '"{parent}"'))
def the_children_sit_under(ctx, first, second, parent):
    phase = ctx.by_name[parent]
    assert ctx.by_name[first].parent_task_id == phase.id
    assert ctx.by_name[second].parent_task_id == phase.id


@then(parsers.parse('the imported "{name}" sits at the top level'))
def the_task_sits_at_top_level(ctx, name):
    assert ctx.by_name[name].parent_task_id is None


@then(parsers.parse('the imported "{name}" is a "{task_type}"'))
def the_task_is_a_type(ctx, name, task_type):
    assert ctx.by_name[name].task_type == task_type


@then(parsers.parse('the imported "{name}" is a "{task_type}" with no end '
                    'date'))
def the_task_is_a_milestone(ctx, name, task_type):
    milestone = ctx.by_name[name]
    assert milestone.task_type == task_type
    assert milestone.effective_milestone
    assert milestone.end_date is None


@then(parsers.parse('the imported "{name}" waits on "{other}" as an '
                    '"{dep_type}" link lagged {lag:d} days'))
def the_link_keeps_its_type_and_lag(ctx, name, other, dep_type, lag):
    task = ctx.by_name[name]
    assert len(task.dependencies) == 1
    link = task.dependencies[0]
    assert link.task_id == ctx.by_name[other].id
    assert link.dep_type == dep_type
    assert link.lag == lag


@then(parsers.parse('the imported "{name}" is {percent:d} percent done'))
def the_task_is_percent_done(ctx, name, percent):
    assert ctx.by_name[name].progress == percent


@then(parsers.parse('the imported "{name}" notes read "{text}"'))
def the_task_notes_read(ctx, name, text):
    assert ctx.by_name[name].details == text


@then(parsers.parse('the imported "{name}" has priority "{priority}"'))
def the_task_has_priority(ctx, name, priority):
    assert ctx.by_name[name].priority == priority


@then("the imported calendar rests Saturday and Sunday")
def the_imported_calendar_rests_weekends(ctx):
    assert ctx.imported.calendar.non_working_days == {5, 6}


@then(parsers.parse('the imported calendar lists the holiday on "{day}"'))
def the_imported_calendar_lists_the_holiday(ctx, day):
    assert datetime.fromisoformat(day).date() in \
        ctx.imported.calendar.holidays


@then("every imported task is unconstrained")
def every_task_is_unconstrained(ctx):
    for task in ctx.imported.tasks:
        assert task.constraint_type == 'NA', task.name
        assert task.constraint_date is None, task.name


@then(parsers.parse('the imported "{name}" carries a "{ctype}" constraint '
                    'dated "{day}"'))
def the_task_carries_a_constraint(ctx, name, ctype, day):
    task = ctx.by_name[name]
    assert task.constraint_type == ctype
    assert task.constraint_date.date() == \
        datetime.fromisoformat(day).date()


@then(parsers.parse('the imported named calendars are "{names}"'))
def the_named_calendars_are(ctx, names):
    assert [named.name for named in ctx.imported.calendars] == \
        names.split('", "')


@then(parsers.parse('the imported "{name}" still follows a calendar resting '
                    "Monday to Friday's other days"))
def the_task_still_follows_its_calendar(ctx, name):
    task = ctx.by_name[name]
    calendar = ctx.imported.calendar_for(task)
    assert task.calendar_id is not None
    assert calendar.non_working_days == {0, 1, 2, 3, 4}


@then(parsers.parse('the imported "{name}" names no calendar'))
def the_task_names_no_calendar(ctx, name):
    assert ctx.by_name[name].calendar_id is None


@then(parsers.parse('the imported calendar lists holidays on "{d1}", '
                    '"{d2}" and "{d3}"'))
def the_calendar_lists_holidays(ctx, d1, d2, d3):
    for day in (d1, d2, d3):
        assert datetime.fromisoformat(day).date() in \
            ctx.imported.calendar.holidays


@then(parsers.parse('the imported task names are "{name}"'))
def the_imported_task_names_are(ctx, name):
    assert [task.name for task in ctx.imported.tasks] == [name]


@then(parsers.parse('the imported "{name}" sits under "{parent}"'))
def the_task_sits_under(ctx, name, parent):
    deep = by_name(ctx.imported, name)
    phase = by_name(ctx.imported, parent)
    assert deep.parent_task_id == phase.id


@then(parsers.parse('the imported "{name}" ends on "{day}"'))
def the_task_ends_on(ctx, name, day):
    assert by_name(ctx.imported, name).end_date.date() == \
        datetime.fromisoformat(day).date()


@then(parsers.parse('the imported "{name}" waits on nothing'))
def the_task_waits_on_nothing(ctx, name):
    assert list(by_name(ctx.imported, name).dependencies) == []


@then("nothing comes back")
def nothing_comes_back(ctx):
    assert ctx.imported is None
