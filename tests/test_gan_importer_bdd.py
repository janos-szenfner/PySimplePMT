"""
pytest-bdd tests for the GAN file importer.

Run with:
    python3 -m pytest tests/test_gan_importer_bdd.py -q

Nothing here needs a display. Converted from test_gan_importer.py -
every case carried over.
"""
import xml.etree.ElementTree as ET
from datetime import datetime
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.utils.gan_importer import (
    GANImporter, GanttProjectCalendar, import_gan_file, strip_namespaces
)

pytestmark = [
    pytest.mark.gan_importer,
]

scenarios("features/gan_import.feature")


#: A plan exercising nesting, milestones, dependencies and a holiday.
SAMPLE_GAN = '''<?xml version="1.0" encoding="UTF-8"?>
<project name="Sample Project" company="" version="3.2.3247">
    <calendars base-id="Hungary">
        <day-types>
            <day-type id="0"/>
            <day-type id="1"/>
            <default-week id="1" name="default" sun="1" mon="0" tue="0" wed="0" thu="0" fri="0" sat="1"/>
            <only-show-weekends value="false"/>
        </day-types>
        <date year="" month="3" date="15" type="HOLIDAY"/>
        <date year="2024" month="5" date="1" type="HOLIDAY"/>
    </calendars>
    <tasks empty-milestones="true">
        <taskproperties>
            <taskproperty id="tpd3" name="name" type="default" valuetype="text"/>
        </taskproperties>
        <task id="1" name="Kick-Off" color="#8cb6ce" meeting="false" start="2024-01-01" duration="5" complete="25" expand="true">
            <depend id="2" type="2" difference="0" hardness="Strong"/>
        </task>
        <task id="2" name="Approval" color="#8cb6ce" meeting="true" start="2024-01-08" duration="0" complete="0" expand="true">
            <depend id="3" type="2" difference="0" hardness="Strong"/>
        </task>
        <task id="3" name="Delivery" color="#000000" meeting="false" start="2024-01-08" duration="10" complete="0" expand="true">
            <task id="4" name="Build" color="#8cb6ce" meeting="false" start="2024-01-08" duration="5" complete="0" expand="true">
                <task id="5" name="Sub-build" color="#8cb6ce" meeting="false" start="2024-01-08" duration="2" complete="0" expand="true"/>
            </task>
            <task id="6" name="Ship" meeting="false" start="2024-01-15" duration="5" complete="100" expand="true"/>
        </task>
    </tasks>
    <resources/>
    <allocations/>
</project>
'''


# ------------------------------------------------------------------
# GIVEN - the calendar
# ------------------------------------------------------------------

@given("the sample GAN calendar", target_fixture="calendar")
def the_sample_gan_calendar():
    root = ET.fromstring(SAMPLE_GAN)
    return GanttProjectCalendar.from_element(root.find('calendars'))


@given("a GAN calendar built from nothing", target_fixture="calendar")
def a_gan_calendar_built_from_nothing():
    return GanttProjectCalendar.from_element(None)


# ------------------------------------------------------------------
# THEN - the calendar
# ------------------------------------------------------------------

@then("the non-working weekdays are 5 and 6")
def the_nonworking_weekdays(calendar):
    assert calendar.non_working_weekdays == {5, 6}


@then(parsers.parse('"{day}" is a working day'))
def the_day_is_working(calendar, day):
    assert calendar.is_working_day(datetime.fromisoformat(day))


@then(parsers.parse('"{day}" is not a working day'))
def the_day_is_not_working(calendar, day):
    assert not calendar.is_working_day(datetime.fromisoformat(day))


@then(parsers.parse('{days:d} working days from "{start}" lands on "{end}"'))
def working_days_lands_on(calendar, days, start, end):
    assert calendar.add_working_days(datetime.fromisoformat(start), days) == \
        datetime.fromisoformat(end)


@then(parsers.parse('the end of {days:d} working days from "{start}" is '
                    '"{end}"'))
def the_end_of_working_days(calendar, days, start, end):
    assert calendar.end_date_for(datetime.fromisoformat(start), days) == \
        datetime.fromisoformat(end)


# ------------------------------------------------------------------
# WHEN - date parsing
# ------------------------------------------------------------------

@when(parsers.parse('the date "{text}" is parsed'), target_fixture="parsed")
def the_date_is_parsed(text):
    return GANImporter().parse_date(text)


@when("no date is parsed", target_fixture="parsed")
def no_date_is_parsed():
    return GANImporter().parse_date(None)


@when("an empty date string is parsed", target_fixture="parsed")
def an_empty_date_string_is_parsed():
    return GANImporter().parse_date("")


# ------------------------------------------------------------------
# THEN - date parsing
# ------------------------------------------------------------------

@then(parsers.parse('it parses as "{expected}"'))
def it_parses_as(parsed, expected):
    assert parsed == datetime.fromisoformat(expected)


@then(parsers.parse('it parses with year {year:d} hour {hour:d} second '
                    '{second:d}'))
def it_parses_with_hms(parsed, year, hour, second):
    assert parsed is not None
    assert parsed.year == year
    assert parsed.hour == hour
    assert parsed.second == second


@then(parsers.parse('it parses with year {year:d} and minute {minute:d}'))
def it_parses_with_minute(parsed, year, minute):
    assert parsed is not None
    assert parsed.year == year
    assert parsed.minute == minute


@then("it parses as nothing")
def it_parses_as_nothing(parsed):
    assert parsed is None


# ------------------------------------------------------------------
# WHEN - importing
# ------------------------------------------------------------------

@when("the sample GAN file is imported", target_fixture="ctx")
def the_sample_file_is_imported(tmp_path):
    path = tmp_path / "test.gan"
    path.write_text(SAMPLE_GAN, encoding='utf-8')
    return SimpleNamespace(project=GANImporter().import_gan(str(path)))


@when("the sample GAN file is imported ignoring the calendar",
      target_fixture="ctx")
def the_sample_file_is_imported_ignoring_the_calendar(tmp_path):
    path = tmp_path / "test.gan"
    path.write_text(SAMPLE_GAN, encoding='utf-8')
    importer = GANImporter(respect_calendar=False)
    return SimpleNamespace(project=importer.import_gan(str(path)))


@when("the sample GAN file is imported through the convenience function",
      target_fixture="ctx")
def the_sample_file_is_imported_via_the_function(tmp_path):
    path = tmp_path / "test.gan"
    path.write_text(SAMPLE_GAN, encoding='utf-8')
    return SimpleNamespace(project=import_gan_file(str(path)))


@when("this GanttProject file is imported", target_fixture="ctx")
def this_file_is_imported(tmp_path, docstring):
    path = tmp_path / "test.gan"
    path.write_text(docstring, encoding='utf-8')
    return SimpleNamespace(project=GANImporter().import_gan(str(path)))


@when("a nonexistent GAN file is imported", target_fixture="ctx")
def a_nonexistent_file_is_imported(tmp_path):
    missing = tmp_path / "nonexistent.gan"
    return SimpleNamespace(project=GANImporter().import_gan(str(missing)))


# ------------------------------------------------------------------
# THEN - importing
# ------------------------------------------------------------------

@then(parsers.parse('the imported project is named "{name}"'))
def the_project_is_named(ctx, name):
    assert ctx.project is not None
    assert ctx.project.name == name


@then(parsers.parse('it holds {count:d} tasks'))
def it_holds_tasks(ctx, count):
    assert ctx.project is not None
    assert len(ctx.project.tasks) == count


@then("nothing comes back")
def nothing_comes_back(ctx):
    assert ctx.project is None


@then(parsers.parse('the imported task "{task_id}" has parent "{parent}" '
                    'and type "{task_type}"'))
def the_task_has_parent_and_type(ctx, task_id, parent, task_type):
    task = ctx.project.get_task_by_id(task_id)
    assert task.parent_task_id == parent
    assert task.task_type == task_type


@then(parsers.parse('the top-level tasks are "{a}", "{b}" and "{c}"'))
def the_top_level_tasks_are(ctx, a, b, c):
    top_level = {t.id for t in ctx.project.get_root_tasks()}
    assert top_level == {a, b, c}


@then(parsers.parse('the imported task "{task_id}" waits on nothing'))
def the_task_waits_on_nothing(ctx, task_id):
    assert ctx.project.get_task_by_id(task_id).dependency_ids == []


@then(parsers.parse('the imported task "{task_id}" waits on "{parent}"'))
def the_task_waits_on(ctx, task_id, parent):
    assert ctx.project.get_task_by_id(task_id).dependency_ids == [parent]


@then(parsers.parse('the imported task "{task_id}" is a milestone with no '
                    'end date'))
def the_task_is_a_milestone(ctx, task_id):
    task = ctx.project.get_task_by_id(task_id)
    assert task.is_milestone
    assert task.end_date is None


@then(parsers.parse('the imported task "{task_id}" is not a milestone'))
def the_task_is_not_a_milestone(ctx, task_id):
    assert not ctx.project.get_task_by_id(task_id).is_milestone


@then(parsers.parse('the imported task "{task_id}" starts on "{day}"'))
def the_task_starts_on(ctx, task_id, day):
    task = ctx.project.get_task_by_id(task_id)
    assert task.start_date == datetime.fromisoformat(day)


@then(parsers.parse('the imported task "{task_id}" ends on "{day}"'))
def the_task_ends_on(ctx, task_id, day):
    task = ctx.project.get_task_by_id(task_id)
    assert task.end_date == datetime.fromisoformat(day)


@then(parsers.parse('the imported task "{task_id}" has a start date'))
def the_task_has_a_start(ctx, task_id):
    assert ctx.project.get_task_by_id(task_id).start_date is not None


@then(parsers.parse('the imported task "{task_id}" is {percent:d} percent '
                    'done'))
def the_task_is_percent_done(ctx, task_id, percent):
    assert ctx.project.get_task_by_id(task_id).progress == percent


@then(parsers.parse('the imported task "{task_id}" is colored "{color}"'))
def the_task_is_colored(ctx, task_id, color):
    assert ctx.project.get_task_by_id(task_id).color == color


@then(parsers.parse('the project starts on "{day}"'))
def the_project_starts_on(ctx, day):
    assert ctx.project.start_date == datetime.fromisoformat(day)


@then(parsers.parse('the project ends on "{day}"'))
def the_project_ends_on(ctx, day):
    assert ctx.project.end_date == datetime.fromisoformat(day)


# ------------------------------------------------------------------
# Colors
# ------------------------------------------------------------------

@when("colors are parsed from an empty project element",
      target_fixture="colors")
def colors_from_empty_element():
    return GANImporter().parse_colors(ET.Element('project'))


@when("colors are parsed from this document", target_fixture="colors")
def colors_from_a_document(docstring):
    root = strip_namespaces(ET.fromstring(docstring))
    return GANImporter().parse_colors(root)


@then(parsers.parse('the "{name}" color is "{value}"'))
def the_color_is(colors, name, value):
    assert name in colors
    assert colors[name] == value


# ------------------------------------------------------------------
# Namespace stripping
# ------------------------------------------------------------------

@when("namespaces are stripped from this document", target_fixture="stripped")
def namespaces_are_stripped(docstring):
    return strip_namespaces(ET.fromstring(docstring))


@then(parsers.parse('the stripped root is a "{tag}" element holding '
                    '"{child}"'))
def the_stripped_root_is(stripped, tag, child):
    assert stripped.tag == tag
    assert stripped.find(child) is not None
