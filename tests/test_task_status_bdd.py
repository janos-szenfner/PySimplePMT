"""
pytest-bdd tests for the task status - Active, Estimated and Inactive.

Run with:
    python3 -m pytest tests/test_task_status_bdd.py -q

WHY THIS MODULE EXISTS:
======================
The status field grew a third value and shed the one it shipped with. Active
is now the quiet default the Status column leaves blank; Estimated shows a
bold E; Inactive shows a bold I and, being set aside, strikes its whole row
through and greys it - the way the screenshot marks a dropped task. The
dashboard's summary counts the two marked shares and no longer names the
Draft share, which was the second half of a two-way split that no longer
exists.

DEVELOPMENT NOTES:
------------------
A Treeview styles a whole row through a tag, not one cell, so the bold on the
E and the strike-through on the I are read off the row's own visual tag rather
than off the letter. The letter itself is the Status column's value. The
scenarios that build a list need a display - CI provides one through xvfb -
and skip without one; the model and dashboard-metric scenarios need none and
run everywhere.
"""
import os
import tempfile
import tkinter as tk
from datetime import datetime, timedelta

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app import theme
from gantt_app.models import TASK_STATUSES, Project, Task
from gantt_app.views.project_dashboard import dashboard_rows, kpi_metrics

BASE = datetime(2026, 7, 6)


def _display_available() -> bool:
    """Whether a usable Tk display is present."""
    try:
        root = tk.Tk()
    except Exception:
        return False
    root.destroy()
    return True


HAVE_DISPLAY = _display_available()

scenarios("features/task_status.feature")


# ---------------------------------------------------------------------------
# The status set and the model default, which need no display
# ---------------------------------------------------------------------------

@given("the set of task statuses", target_fixture="statuses")
def the_set_of_task_statuses():
    """The tuple the editor's dropdown and every reader validate against."""
    return TASK_STATUSES


@then(parsers.parse(
    'it holds exactly "{first}", "{second}" and "{third}"'))
def it_holds_exactly(statuses, first, second, third):
    """Three values, no more - the two marked ones and the default."""
    assert tuple(statuses) == (first, second, third)


@then(parsers.parse('the first value is "{status}"'))
def the_first_value_is(statuses, status):
    """First, so the dropdown opens on it; see _build_status."""
    assert statuses[0] == status


@given("a task created without a status", target_fixture="plain_task")
def a_task_created_without_a_status():
    """What a new row is before anyone touches its status."""
    return Task(id="1", name="New", start_date=BASE)


@then(parsers.parse('its status is "{status}"'))
def its_status_is(plain_task, status):
    """The default, and where an unknown value is coerced to."""
    assert plain_task.status == status


@given(parsers.parse('a task dict carrying the old "{status}" status'),
       target_fixture="legacy_dict")
def a_task_dict_carrying_the_old_status(status):
    """A file written before the field changed still says Draft."""
    task = Task(id="1", name="Legacy", start_date=BASE)
    data = task.to_dict()
    data['status'] = status
    return data


@when("the dict is read back into a task", target_fixture="plain_task")
def the_dict_is_read_back_into_a_task(legacy_dict):
    """from_dict validates the status, as every reader does."""
    return Task.from_dict(legacy_dict)


# ---------------------------------------------------------------------------
# The list, which needs a display
# ---------------------------------------------------------------------------

@pytest.fixture
def list_state():
    """A window and a list, torn down whatever the scenario does."""
    if not HAVE_DISPLAY:
        pytest.skip("needs a display")
    import customtkinter as ctk

    from gantt_app.views.task_list import DragDropTaskList

    root = ctk.CTk()
    root.withdraw()
    project = Project(name="Plan")
    task_list = DragDropTaskList(root, project)
    state = {"root": root, "project": project, "list": task_list}
    yield state
    try:
        root.destroy()
    except tk.TclError:
        pass


def _visual_tag(task_list, task_id):
    """The one row_ tag the list resolves the whole appearance onto."""
    tags = task_list.tree.item(task_id, 'tags')
    visual = [tag for tag in tags if tag.startswith('row_')]
    assert len(visual) == 1, f"{task_id} should carry one visual tag"
    return task_list.tree.tag_configure(visual[0])


@given(parsers.parse('a task list holding an "{status}" task'),
       target_fixture="list_state")
def a_task_list_holding_a_task(list_state, status):
    """One task at the given status, drawn."""
    list_state["project"].add_task(Task(
        id="T1", name="The task", task_type="Task", start_date=BASE,
        end_date=BASE + timedelta(days=2), status=status))
    list_state["list"].update_task_list()
    list_state["root"].update_idletasks()
    return list_state


@when(parsers.parse('the task is set to "{status}" and the list is redrawn'))
def the_task_is_set_and_redrawn(list_state, status):
    """Change the status the way saving the editor would, then repaint."""
    list_state["project"].get_task_by_id("T1").status = status
    list_state["list"].update_task_list()
    list_state["root"].update_idletasks()


@then("the Status cell for that task is empty")
def the_status_cell_is_empty(list_state):
    """Active says nothing, so the column stays quiet."""
    assert list_state["list"].tree.set("T1", "Status") == ""


@then(parsers.parse('the Status cell for that task is "{letter}"'))
def the_status_cell_is(list_state, letter):
    """The initial the marked statuses wear - E or I."""
    assert list_state["list"].tree.set("T1", "Status") == letter


@then("that row's font is bold")
def that_rows_font_is_bold(list_state):
    """The marked letter is bold; the whole row's tag carries it."""
    font = str(_visual_tag(list_state["list"], "T1")['font'])
    assert 'bold' in font, font


@then("that row's font is not bold")
def that_rows_font_is_not_bold(list_state):
    """An ordinary Active task is drawn in the plain grid font."""
    font = str(_visual_tag(list_state["list"], "T1")['font'])
    assert 'bold' not in font, font


@then("that row's font is struck through")
def that_rows_font_is_struck_through(list_state):
    """Inactive draws a line through the row - Tk's overstrike."""
    font = str(_visual_tag(list_state["list"], "T1")['font'])
    assert 'overstrike' in font, font


@then("that row's font is not struck through")
def that_rows_font_is_not_struck_through(list_state):
    """Everything other than Inactive leaves the row unstruck."""
    font = str(_visual_tag(list_state["list"], "T1")['font'])
    assert 'overstrike' not in font, font


@then("that row is greyed")
def that_row_is_greyed(list_state):
    """A dormant row is dimmed to the light grey that goes with the line."""
    fg = str(_visual_tag(list_state["list"], "T1")['foreground'])
    assert fg == theme.now(theme.GRID_INACTIVE_TEXT), fg


@then("that row is not greyed")
def that_row_is_not_greyed(list_state):
    """Back to Active, the row carries the ordinary grid ink again."""
    fg = str(_visual_tag(list_state["list"], "T1")['foreground'])
    assert fg != theme.now(theme.GRID_INACTIVE_TEXT), fg


# ---------------------------------------------------------------------------
# The dashboard shares, which need no display
# ---------------------------------------------------------------------------

def _four_task_plan():
    """Four Tasks: two Active, one Estimated, one Inactive."""
    project = Project(name="Four")
    marks = ('Active', 'Active', 'Estimated', 'Inactive')
    for i, status in enumerate(marks, start=1):
        project.add_task(Task(
            id=f"{i}", name=f"Task {i}", task_type="Task", start_date=BASE,
            end_date=BASE + timedelta(days=2), status=status))
    return project


@given("a plan of four tasks, one Estimated and one Inactive",
       target_fixture="plan")
def a_plan_of_four_tasks():
    """A quarter each for the marked shares, the rest Active."""
    return _four_task_plan()


@when("the summary metrics are computed", target_fixture="metrics")
def the_summary_metrics_are_computed(plan):
    """The figures the summary box reads from."""
    return kpi_metrics(dashboard_rows(plan))


@then(parsers.parse("the active share is {percent:d} percent"))
def the_active_share_is(metrics, percent):
    """Active is the remainder once the marked ones are counted."""
    assert round(metrics['active_share']) == percent


@then(parsers.parse("the estimated share is {percent:d} percent"))
def the_estimated_share_is(metrics, percent):
    """Counted on its own, not taken as a remainder."""
    assert round(metrics['estimated_share']) == percent


@then(parsers.parse("the inactive share is {percent:d} percent"))
def the_inactive_share_is(metrics, percent):
    """Counted on its own, not taken as a remainder."""
    assert round(metrics['inactive_share']) == percent


@then("the three shares add up to a hundred")
def the_three_shares_add_up(metrics):
    """Read as a set, so they must close."""
    total = (metrics['active_share'] + metrics['estimated_share']
             + metrics['inactive_share'])
    assert round(total, 6) == 100.0


@then("there is no draft share")
def there_is_no_draft_share(metrics):
    """The old two-way split is gone; nothing reports a Draft share."""
    assert 'draft_share' not in metrics


# ---------------------------------------------------------------------------
# The summary box, which needs a display
# ---------------------------------------------------------------------------

@given("a rendered dashboard for a plan with an Estimated and an Inactive "
       "task", target_fixture="summary_texts")
def a_rendered_dashboard(request):
    """The captions the drawn summary box actually writes."""
    if not HAVE_DISPLAY:
        pytest.skip("needs a display")
    import customtkinter as ctk

    from gantt_app.views.project_dashboard import ProjectDashboardFrame

    root = ctk.CTk()
    root.withdraw()
    request.addfinalizer(lambda: _safe_destroy(root))

    frame = ProjectDashboardFrame(root, _four_task_plan())
    frame.canvas.configure(width=1200, height=800)
    frame.refresh()
    return [frame.canvas.itemcget(item, 'text')
            for item in frame.canvas.find_all()
            if frame.canvas.type(item) == 'text']


def _safe_destroy(root):
    """Tear the window down without minding a dead interpreter."""
    try:
        root.destroy()
    except tk.TclError:
        pass


@then(parsers.parse('the summary box shows an "{caption}" line'))
def the_summary_box_shows(summary_texts, caption):
    """The caption naming a share the box now carries."""
    assert caption in summary_texts, summary_texts


@then(parsers.parse('the summary box shows no "{caption}" line'))
def the_summary_box_shows_no(summary_texts, caption):
    """The Draft caption the box has stopped writing."""
    assert caption not in summary_texts, summary_texts
