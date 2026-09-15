"""
pytest-bdd tests for the Microsoft Project export: the plan as MSPDI.

Run with:
    python3 -m pytest tests/test_msproject_exporter_bdd.py -q

Nothing here needs a display, and nothing needs Microsoft Project.
Converted from test_msproject_exporter.py - every case carried over.
"""
import os
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Project, Task
from gantt_app.utils.msproject_exporter import (
    MSPDI_NAMESPACE, export_project_to_msproject, generate_msproject_content,
)
from gantt_app.core.workdaycalendar import WorkingCalendar

pytestmark = [
    pytest.mark.msproject_exporter,
]

scenarios("features/msproject_export.feature")

#: Every element sits in the MSPDI namespace, so every find has to say so.
NS = {'ms': MSPDI_NAMESPACE}


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
                          details="Signed off by the steering group"))
    project.add_task(Task(id="T2", name="Tender", task_type="Task",
                          parent_task_id="P1",
                          start_date=base + timedelta(days=7),
                          end_date=base + timedelta(days=16),
                          dependencies=[{'task_id': "T1", 'dep_type': 'FS',
                                         'hardness': 'Hard', 'lag': 2}]))
    project.add_task(Task(id="M1", name="Contract signed",
                          task_type="Milestone",
                          start_date=base + timedelta(days=21),
                          dependencies=["T2"]))

    project.calendar.holidays.add(datetime(2026, 7, 8).date())
    return project


def tasks(root):
    return root.findall('ms:Tasks/ms:Task', NS)


def task_by_name(root, name):
    """Find one <Task> element by the name it carries."""
    for element in tasks(root):
        if element.find('ms:Name', NS).text == name:
            return element
    raise AssertionError(f"No task named {name!r} in the exported file")


def value(element, tag):
    """The text of one child element, or None when it is absent."""
    child = element.find(f'ms:{tag}', NS)
    return None if child is None else child.text


def calendar_elements(root):
    return root.findall('ms:Calendars/ms:Calendar', NS)


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


@given("a plan working Saturdays holding a six-day task",
       target_fixture="ctx")
def a_plan_working_saturdays():
    project = Project(name="Six days",
                      calendar=WorkingCalendar(non_working_days={6}))
    project.add_task(Task(id="T1", name="Work",
                          start_date=datetime(2026, 7, 6),
                          end_date=datetime(2026, 7, 11)))
    return SimpleNamespace(project=project)


@given(parsers.parse('a plan that works "{day}" for "{reason}"'),
       target_fixture="ctx")
def a_plan_with_a_worked_weekend(day, reason):
    project = Project(name="Make-up day")
    project.calendar.add_override(datetime.fromisoformat(day).date(),
                                  is_working_day=True, reason=reason)
    project.add_task(Task(id="T1", name="Work",
                          start_date=datetime(2026, 7, 6),
                          end_date=datetime(2026, 7, 11)))
    return SimpleNamespace(project=project)


@given(parsers.parse('"{name}" is floored to "{day}" by a SNET constraint'))
def a_task_is_floored(ctx, name, day):
    tender = ctx.project.get_task_by_id("T2")
    tender.constraint_type = 'SNET'
    tender.constraint_date = datetime.fromisoformat(day)


@given(parsers.parse('"{name}" carries notes and a named calendar'))
def a_task_with_notes_and_calendar(ctx, name):
    tender = ctx.project.get_task_by_id("T2")
    tender.details = "Three bidders shortlisted"
    tender.calendar_id = ctx.project.calendars.create("Weekend window").id


@given(parsers.parse('"{name}" is given status "{status}"'))
def a_task_is_given_status(ctx, name, status):
    ctx.project.get_task_by_id("T2").status = status


@given(parsers.parse('"{name}" follows a weekend-only calendar named '
                     '"{cal_name}"'))
def a_task_follows_a_named_calendar(ctx, name, cal_name):
    weekend = ctx.project.calendars.create(
        cal_name, WorkingCalendar(non_working_days={0, 1, 2, 3, 4}))
    ctx.project.get_task_by_id("T2").calendar_id = weekend.id


@given(parsers.parse('a calendar named "{cal_name}" exists'))
def a_calendar_exists(ctx, cal_name):
    ctx.project.calendars.create(cal_name)


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------

@when("the plan is exported to MSPDI XML")
def the_plan_is_exported(ctx):
    ctx.root = ET.fromstring(generate_msproject_content(ctx.project))


@when("the plan is exported to a real MSPDI file")
def the_plan_is_exported_to_a_file(ctx, tmp_path):
    ctx.path = tmp_path / "plan.xml"
    ctx.exported_ok = export_project_to_msproject(ctx.project,
                                                  str(ctx.path))


@when("the plan is exported to a path that cannot be written")
def the_plan_is_exported_to_a_bad_path(ctx):
    ctx.exported_ok = export_project_to_msproject(
        ctx.project,
        os.path.join(tempfile.gettempdir(), "no-such\0path.xml"))


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@then("the root is a Project element in the MSPDI namespace")
def the_root_is_a_project(ctx):
    assert ctx.root.tag == f'{{{MSPDI_NAMESPACE}}}Project'


@then(parsers.parse('its Title reads "{title}"'))
def its_title_reads(ctx, title):
    assert value(ctx.root, 'Title') == title


@then(parsers.parse('the outline reads "{p}" level {pl:d} WBS "{pw}", '
                    '"{bc}" level {bcl:d} WBS "{bcw}", "{t}" level {tl:d} '
                    'WBS "{tw}" and "{m}" level {ml:d} WBS "{mw}"'))
def the_outline_reads(ctx, p, pl, pw, bc, bcl, bcw, t, tl, tw, m, ml, mw):
    levels = [(value(task, 'Name'), value(task, 'OutlineLevel'),
               value(task, 'WBS')) for task in tasks(ctx.root)]
    assert levels == [
        (p, str(pl), pw), (bc, str(bcl), bcw),
        (t, str(tl), tw), (m, str(ml), mw)]


@then(parsers.parse('the task "{name}" carries constraint type "{ctype}"'))
def the_task_carries_constraint_type(ctx, name, ctype):
    assert value(task_by_name(ctx.root, name), 'ConstraintType') == ctype


@then(parsers.parse('the task "{name}" carries constraint date "{day}"'))
def the_task_carries_constraint_date(ctx, name, day):
    assert value(task_by_name(ctx.root, name), 'ConstraintDate') == day


@then(parsers.parse('the task "{name}" carries no constraint date'))
def the_task_carries_no_constraint_date(ctx, name):
    assert value(task_by_name(ctx.root, name), 'ConstraintDate') is None


@then(parsers.parse('the task "{name}" is marked a summary'))
def the_task_is_a_summary(ctx, name):
    assert value(task_by_name(ctx.root, name), 'Summary') == '1'


@then(parsers.parse('the task "{name}" is marked a milestone'))
def the_task_is_a_milestone(ctx, name):
    assert value(task_by_name(ctx.root, name), 'Milestone') == '1'


@then(parsers.parse('the task "{name}" has duration "{duration}"'))
def the_task_has_duration(ctx, name, duration):
    assert value(task_by_name(ctx.root, name), 'Duration') == duration


@then(parsers.parse('the task "{name}" finishes where it starts'))
def the_task_finishes_where_it_starts(ctx, name):
    task = task_by_name(ctx.root, name)
    assert value(task, 'Start') == value(task, 'Finish')


@then(parsers.parse('the task "{name}" finishes at "{moment}"'))
def the_task_finishes_at(ctx, name, moment):
    assert value(task_by_name(ctx.root, name), 'Finish') == moment


@then(parsers.parse('the task "{name}" holds one predecessor link to '
                    '"{other}"'))
def the_task_holds_a_link(ctx, name, other):
    tender = task_by_name(ctx.root, name)
    business_case = task_by_name(ctx.root, other)
    links = tender.findall('ms:PredecessorLink', NS)
    assert len(links) == 1
    assert links[0].find('ms:PredecessorUID', NS).text == \
        value(business_case, 'UID')
    ctx.link = links[0]


@then(parsers.parse('the link is of type "{ltype}"'))
def the_link_is_of_type(ctx, ltype):
    assert ctx.link.find('ms:Type', NS).text == ltype


@then(parsers.parse('the link on "{name}" carries lag "{lag}" and format '
                    '"{fmt}"'))
def the_link_carries_lag(ctx, name, lag, fmt):
    link = task_by_name(ctx.root, name).find('ms:PredecessorLink', NS)
    assert link.find('ms:LinkLag', NS).text == lag
    assert link.find('ms:LagFormat', NS).text == fmt


@then(parsers.parse('"{name}" writes CalendarUID between ConstraintType and '
                    'ConstraintDate'))
def calendar_uid_sits_between(ctx, name):
    element = task_by_name(ctx.root, name)
    tags = [child.tag.split('}')[1] for child in element]
    assert tags[tags.index('ConstraintType'):tags.index('ConstraintDate') + 1] \
        == ['ConstraintType', 'CalendarUID', 'ConstraintDate']
    ctx.tags = tags


@then(parsers.parse('"{name}" writes Notes before its PredecessorLink'))
def notes_before_link(ctx, name):
    tags = ctx.tags
    assert tags.index('Notes') < tags.index('PredecessorLink')


@then(parsers.parse('"{name}" writes PredecessorLink last'))
def predecessor_link_is_last(ctx, name):
    assert ctx.tags[-1] == 'PredecessorLink'


@then("no task writes a Status element")
def no_status_element(ctx):
    for element in tasks(ctx.root):
        tags = [child.tag.split('}')[1] for child in element]
        assert 'Status' not in tags


@then(parsers.parse('the task "{name}" is "{percent}" percent complete'))
def the_task_is_percent_complete(ctx, name, percent):
    assert value(task_by_name(ctx.root, name), 'PercentComplete') == percent


@then(parsers.parse('the task "{name}" notes read "{text}"'))
def the_task_notes_read(ctx, name, text):
    assert value(task_by_name(ctx.root, name), 'Notes') == text


@then(parsers.parse('day type "{sun}" is not worked, "{mon}" and "{fri}" '
                    'are, and "{sat}" is not'))
def the_week_is_declared_from_sunday(ctx, sun, mon, fri, sat):
    weekdays = ctx.root.findall(
        'ms:Calendars/ms:Calendar/ms:WeekDays/ms:WeekDay', NS)
    week = {day.find('ms:DayType', NS).text:
            day.find('ms:DayWorking', NS).text
            for day in weekdays if day.find('ms:DayType', NS).text != '0'}
    assert week[sun] == '0'
    assert week[mon] == '1'
    assert week[fri] == '1'
    assert week[sat] == '0'


@then(parsers.parse('the date "{moment}" is a non-working exception'))
def the_date_is_a_nonworking_exception(ctx, moment):
    exceptions = [day for day in ctx.root.findall(
        'ms:Calendars/ms:Calendar/ms:WeekDays/ms:WeekDay', NS)
        if day.find('ms:DayType', NS).text == '0']
    dates = {day.find('ms:TimePeriod/ms:FromDate', NS).text:
             day.find('ms:DayWorking', NS).text for day in exceptions}
    assert dates.get(moment) == '0'


@then(parsers.parse('the calendars written are "{first}" and "{second}"'))
def the_calendars_written_are(ctx, first, second):
    names = [element.find('ms:Name', NS).text
             for element in calendar_elements(ctx.root)]
    assert names == [first, second]


@then(parsers.parse('the task "{name}" names the UID of calendar '
                    '"{cal_name}"'))
def the_task_names_its_calendar(ctx, name, cal_name):
    task = task_by_name(ctx.root, name)
    calendar = [element for element in calendar_elements(ctx.root)
                if element.find('ms:Name', NS).text == cal_name][0]
    assert task.find('ms:CalendarUID', NS).text == \
        calendar.find('ms:UID', NS).text


@then(parsers.parse('the task "{name}" names no calendar'))
def the_task_names_no_calendar(ctx, name):
    assert task_by_name(ctx.root, name).find('ms:CalendarUID', NS) is None


@then(parsers.parse('"{cal_name}" is not among the calendars'))
def the_calendar_is_not_written(ctx, cal_name):
    names = [element.find('ms:Name', NS).text
             for element in calendar_elements(ctx.root)]
    assert cal_name not in names


@then("no Task elements are written")
def no_task_elements(ctx):
    assert tasks(ctx.root) == []


@then("one calendar is written")
def one_calendar_is_written(ctx):
    assert len(calendar_elements(ctx.root)) == 1


@then("no PredecessorLink element is written")
def no_predecessor_links(ctx):
    assert ctx.root.findall('.//ms:PredecessorLink', NS) == []


@then(parsers.parse('MinutesPerWeek reads "{minutes}"'))
def minutes_per_week_reads(ctx, minutes):
    assert ctx.root.find('ms:MinutesPerWeek', NS).text == minutes


@then(parsers.parse('one worked exception reads "{moment}" with working '
                    'times'))
def one_worked_exception(ctx, moment):
    worked = [day for day in ctx.root.findall(
        'ms:Calendars/ms:Calendar/ms:WeekDays/ms:WeekDay', NS)
        if day.find('ms:DayType', NS).text == '0'
        and day.find('ms:DayWorking', NS).text == '1']
    assert len(worked) == 1
    assert worked[0].find('ms:TimePeriod/ms:FromDate', NS).text == moment
    assert worked[0].findall('ms:WorkingTimes/ms:WorkingTime', NS)


@then("the file's root is a Project element in the MSPDI namespace")
def the_files_root_is_a_project(ctx):
    assert ctx.exported_ok
    assert ET.parse(str(ctx.path)).getroot().tag == \
        f'{{{MSPDI_NAMESPACE}}}Project'


@then("the export reports failure")
def the_export_reports_failure(ctx):
    assert ctx.exported_ok is False
