"""
pytest-bdd tests for the two identifiers a task has, and which of them
is on screen (Project.display_ids / display_id).

Run with:
    python3 -m pytest tests/test_display_ids_bdd.py -q

Nothing here needs a display.
"""
import io
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Project, Task

pytestmark = [
    pytest.mark.display_ids,
]

scenarios("features/display_ids.feature")

BASE = datetime(2026, 8, 25)


@pytest.fixture
def ctx():
    return SimpleNamespace(project=None, ids_before=None,
                           haystack=None, gan=None, msxml=None)


def _task(task_id, parent=None, name=None):
    return Task(id=task_id, name=name or task_id, task_type="Task",
                parent_task_id=parent, start_date=BASE,
                end_date=BASE + timedelta(days=1))


# ------------------------------------------------------------------
# GIVEN - plans
# ------------------------------------------------------------------

@given(parsers.parse('a plan with the rows "{rows}"'))
def a_plan_with_rows(ctx, rows):
    """'a, b, child<a' - 'x<y' means x sits under y."""
    ctx.project = Project(name="Plan")
    for row in rows.split(","):
        row = row.strip()
        name, _, parent = row.partition("<")
        ctx.project.add_task(_task(name, parent=parent or None))


@given("the exportable plan")
def the_exportable_plan(ctx):
    """A plan whose identities are nothing like its numbers."""
    ctx.project = Project(name="Demo")
    for task_id, parent in (('zz-1', None), ('aa-2', 'zz-1'),
                            ('mm-3', None)):
        ctx.project.add_task(_task(task_id, parent=parent,
                                   name=task_id.upper()))
    ctx.project.get_task_by_id('mm-3').add_dependency('zz-1')


@given("the identities are noted")
def the_identities_are_noted(ctx):
    ctx.ids_before = {task.id for task in ctx.project.tasks}


@given(parsers.parse('"{task}" is linked after "{pred}"'))
def task_is_linked_after(ctx, task, pred):
    ctx.project.get_task_by_id(task).add_dependency(pred)


@given(parsers.parse('"{task}" is named "{name}"'))
def task_is_named(ctx, task, name):
    # Named differently from its identity, or the name would put the
    # identity into the haystack and the check would prove nothing.
    ctx.project.get_task_by_id(task).name = name


# ------------------------------------------------------------------
# WHEN - moving the plan around
# ------------------------------------------------------------------

@when(parsers.parse('a row "{name}" is added under "{parent}"'))
def a_row_is_added_under(ctx, name, parent):
    ctx.project.add_task(_task(name, parent=parent, name="New"))


@when(parsers.parse('"{task}" is moved before "{other}"'))
def task_is_moved_before(ctx, task, other):
    ctx.project.move_task_before(task, other)


@when(parsers.parse('"{task}" is deleted'))
def task_is_deleted(ctx, task):
    ctx.project.remove_task(task)


@when(parsers.parse('"{task}" is indented'))
def task_is_indented(ctx, task):
    ctx.project.indent_tasks([task])


@when(parsers.parse('"{task}" is written to a dictionary'))
def task_is_written(ctx, task):
    ctx.data = ctx.project.get_task_by_id(task).to_dict()


@when(parsers.parse('"{task}" is searched'))
def task_is_searched(ctx, task):
    from gantt_app.views.searchbox import task_haystack
    ctx.haystack = task_haystack(
        ctx.project.get_task_by_id(task), ctx.project)


@when("the plan is exported to GAN")
def the_plan_is_exported_to_gan(ctx):
    from gantt_app.utils.gan_exporter import generate_gan_content
    ctx.gan = generate_gan_content(ctx.project)


@when("the plan is exported to MSPDI")
def the_plan_is_exported_to_mspdi(ctx):
    from gantt_app.utils.msproject_exporter import (
        generate_msproject_content,
    )
    ctx.msxml = generate_msproject_content(ctx.project)


@when("the plan is exported to both XML formats")
def the_plan_is_exported_to_both(ctx):
    the_plan_is_exported_to_gan(ctx)
    the_plan_is_exported_to_mspdi(ctx)


@when("the plan is exported to a spreadsheet")
def the_plan_is_exported_to_a_spreadsheet(ctx):
    from gantt_app.utils.xlsx_exporter import (
        OPENPYXL_AVAILABLE, generate_xlsx_bytes,
    )
    if not OPENPYXL_AVAILABLE:
        pytest.skip("openpyxl is not installed")
    import openpyxl

    ctx.sheet = openpyxl.load_workbook(
        io.BytesIO(generate_xlsx_bytes(ctx.project))).worksheets[0]


# ------------------------------------------------------------------
# THEN - the numbers
# ------------------------------------------------------------------

@then(parsers.parse('the numbers run "{mapping}"'))
def the_numbers_run(ctx, mapping):
    expected = {pair.split("=")[0].strip(): int(pair.split("=")[1])
                for pair in mapping.split(",")}
    assert ctx.project.display_ids() == expected


@then(parsers.parse('the shown order is "{order}"'))
def the_shown_order_is(ctx, order):
    shown = [task.id for task in ctx.project.display_order()]
    assert shown == [item.strip() for item in order.split(",")]


@then(parsers.parse('"{task}" is shown as "{padded}"'))
def task_is_shown_as(ctx, task, padded):
    assert ctx.project.display_id(task) == padded


@then(parsers.parse('the task "{task}" has no number'))
def the_task_has_no_number(ctx, task):
    assert ctx.project.display_id(task) == ''


@then(parsers.parse('"{child}" now sits under "{parent}"'))
def child_now_sits_under(ctx, child, parent):
    assert ctx.project.get_task_by_id(child).parent_task_id == parent


# ------------------------------------------------------------------
# THEN - the identity held
# ------------------------------------------------------------------

@then("every identity is unchanged")
def every_identity_is_unchanged(ctx):
    assert {task.id for task in ctx.project.tasks} == ctx.ids_before


@then(parsers.parse('the link on "{task}" still points at "{pred}"'))
def the_link_still_points(ctx, task, pred):
    link = ctx.project.get_task_by_id(task).dependencies[0]
    assert link.task_id == pred


@then(parsers.parse('"{child}" still has parent "{parent}"'))
def child_still_has_parent(ctx, child, parent):
    child_now_sits_under(ctx, child, parent)


@then("no task stores a display number")
def no_task_stores_a_display_number(ctx):
    assert not hasattr(ctx.project.tasks[0], 'display_id')


@then(parsers.parse('it carries "{identity}" and no display number'))
def it_carries_identity_not_number(ctx, identity):
    assert ctx.data['id'] == identity
    assert 'display_id' not in ctx.data


# ------------------------------------------------------------------
# THEN - the search haystack
# ------------------------------------------------------------------

@then(parsers.parse('the haystack holds "{first}" and "{second}"'))
def the_haystack_holds_both(ctx, first, second):
    assert first in ctx.haystack.split()
    assert second in ctx.haystack.split()


@then(parsers.parse('the haystack contains "{text}"'))
def the_haystack_holds(ctx, text):
    assert text in ctx.haystack


@then(parsers.parse('the haystack does not hold "{text}"'))
def the_haystack_does_not_hold(ctx, text):
    assert text not in ctx.haystack


# ------------------------------------------------------------------
# THEN - the exports
# ------------------------------------------------------------------

@then("the shared walk numbers match the display ids")
def the_shared_walk_matches(ctx):
    from gantt_app.utils.plan_export import numbering, outline
    assert numbering(outline(ctx.project)) == ctx.project.display_ids()


@then("the written task ids are the shown numbers in shown order")
def the_written_ids_match(ctx):
    shown = ctx.project.display_ids()
    expected = [str(shown[task.id])
                for task in ctx.project.display_order()]
    if ctx.gan is not None:
        root = ET.fromstring(ctx.gan)
        found = [element.get('id') for element in root.iter('task')]
    else:
        from gantt_app.utils.msproject_exporter import MSPDI_NAMESPACE
        root = ET.fromstring(ctx.msxml)
        namespace = {'ms': MSPDI_NAMESPACE}
        found = [task.find('ms:UID', namespace).text
                 for task in root.findall('ms:Tasks/ms:Task', namespace)]
    assert found == expected


@then("no task identity reaches the files")
def no_identity_reaches_the_files(ctx):
    written = ctx.gan + ctx.msxml
    for task in ctx.project.tasks:
        assert task.id not in written, task.id


@then("every number in the sheet's ID column is one the plan shows")
def the_sheet_numbers_are_shown(ctx):
    sheet = ctx.sheet
    written = {sheet.cell(row=row, column=1).value
               for row in range(6, sheet.max_row + 1)
               if sheet.cell(row=row, column=1).value is not None}
    assert written, "the sheet wrote no ID column"
    assert written <= set(ctx.project.display_ids().values())
