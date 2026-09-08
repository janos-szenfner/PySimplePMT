"""
pytest-bdd tests for the Task Editor's Advanced tab (REQ-UI-040/041).

Run with:
    python3 -m pytest tests/test_advanced_tab_bdd.py -q

The model and chart-marker scenarios need no display; the ones that drive the
AdvancedTab widget build one and skip where there is none, as the rest of the
UI suites do.
"""
import tkinter as tk
from datetime import datetime, timedelta

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.models import Project, Task
from gantt_app.utils import chart_render as cr


def _display_available() -> bool:
    try:
        root = tk.Tk()
    except Exception:
        return False
    root.destroy()
    return True


HAVE_DISPLAY = _display_available()

scenarios("features/advanced_tab.feature")

BASE = datetime(2026, 9, 1)


@pytest.fixture
def ctx():
    return {}


# ---------------------------------------------------------------------------
# Model - no display
# ---------------------------------------------------------------------------
@given("a new task", target_fixture="subject")
def a_new_task():
    return Task(id="1", name="New", start_date=BASE)


@given("a task with a deadline and a Must Finish On constraint",
       target_fixture="original")
def a_task_with_deadline_and_constraint():
    return Task(id="1", name="Build", start_date=BASE,
                end_date=BASE + timedelta(days=5),
                deadline=BASE + timedelta(days=7),
                constraint_type="MFO",
                constraint_date=BASE + timedelta(days=6))


@given("a task dict written before the Advanced tab existed",
       target_fixture="legacy")
def a_legacy_task_dict():
    data = Task(id="1", name="Old", start_date=BASE).to_dict()
    data.pop("deadline", None)
    data.pop("constraint_type", None)
    data.pop("constraint_date", None)
    return data


@given(parsers.parse('a task dict whose constraint is "{ctype}" but carries '
                     'a date'), target_fixture="legacy")
def a_dict_with_stray_date(ctype):
    data = Task(id="1", name="Stray", start_date=BASE).to_dict()
    data["constraint_type"] = ctype
    data["constraint_date"] = (BASE + timedelta(days=2)).isoformat()
    return data


@when("it is written to a dict and read back", target_fixture="subject")
def written_and_read_back(original):
    import json
    return Task.from_dict(json.loads(json.dumps(original.to_dict())))


@when("it is read back", target_fixture="subject")
def read_back(legacy):
    return Task.from_dict(legacy)


@then("its deadline is not set")
def deadline_not_set(subject):
    assert subject.deadline is None


@then(parsers.parse('its constraint type is "{ctype}"'))
def constraint_type_is(subject, ctype):
    assert subject.constraint_type == ctype


@then("its constraint date is not set")
def constraint_date_not_set(subject):
    assert subject.constraint_date is None


@then("the read-back deadline matches")
def reread_deadline_matches(original, subject):
    assert subject.deadline == original.deadline


@then(parsers.parse('the read-back constraint type is "{ctype}"'))
def reread_constraint_type(subject, ctype):
    assert subject.constraint_type == ctype


@then("the read-back constraint date matches")
def reread_constraint_date(original, subject):
    assert subject.constraint_date == original.constraint_date


# ---------------------------------------------------------------------------
# The AdvancedTab widget - needs a display
# ---------------------------------------------------------------------------
@given("an Advanced tab for a task", target_fixture="tab")
def an_advanced_tab(ctx):
    if not HAVE_DISPLAY:
        pytest.skip("needs a display")
    import customtkinter as ctk
    from gantt_app.views.advanced_tab import AdvancedTab

    root = ctk.CTk()
    root.withdraw()
    ctx["root"] = root
    task = Task(id="1", name="X", start_date=BASE,
                end_date=BASE + timedelta(days=3))
    tab = AdvancedTab(root, task)
    tab.update_idletasks()
    yield tab
    try:
        root.destroy()
    except tk.TclError:
        pass


def _state(tab):
    return str(tab.constraint_date_entry.entry.cget("state"))


@then("the constraint date box is disabled")
def constraint_date_disabled(tab):
    assert _state(tab) == tk.DISABLED


@then("the constraint date box is enabled")
def constraint_date_enabled(tab):
    assert _state(tab) == tk.NORMAL


@when(parsers.parse('the constraint type is set to "{title}"'))
def set_constraint_type(tab, title):
    tab.constraint_var.set(title)
    tab._on_constraint_changed()
    tab.update_idletasks()


@when("the constraint date is cleared")
def clear_constraint_date(tab):
    tab._clear(tab.constraint_date_entry)


@then("reading the tab is refused")
def reading_refused(tab):
    with pytest.raises(ValueError):
        tab.read_values()


@when("a deadline is picked")
def pick_deadline(tab):
    tab.deadline_entry.set_date(BASE + timedelta(days=10))


@when("the deadline is reset")
def reset_deadline(tab):
    tab._reset_deadline()


@then("the tab reports no deadline")
def tab_no_deadline(tab):
    assert tab.read_values()["deadline"] is None


# ---------------------------------------------------------------------------
# The Gantt markers - no display
# ---------------------------------------------------------------------------
def _one_task_layout(**task_kwargs):
    project = Project(name="Chart")
    project.add_task(Task(id="A", name="Anchor", start_date=BASE,
                          end_date=BASE + timedelta(days=1)))
    project.add_task(Task(id="T", name="Work", start_date=BASE,
                          end_date=BASE + timedelta(days=4), **task_kwargs))
    return cr.layout_chart(project, width=1200)


@given("a chart task finishing before its deadline", target_fixture="layout")
def task_before_deadline():
    return _one_task_layout(deadline=BASE + timedelta(days=10))


@given("a chart task finishing after its deadline", target_fixture="layout")
def task_after_deadline():
    return _one_task_layout(deadline=BASE + timedelta(days=1))


@given(parsers.parse('a chart task with a "{ctype}" constraint'),
       target_fixture="layout")
def task_with_constraint(ctype):
    return _one_task_layout(constraint_type=ctype,
                            constraint_date=BASE + timedelta(days=2))


def _markers(layout, kind):
    return [m for m in layout.markers if m["kind"] == kind]


@then("the deadline marker is green")
def deadline_green(layout):
    marks = _markers(layout, "deadline")
    assert marks and marks[0]["color"] == cr.DEADLINE_ON_TRACK


@then("the deadline marker is red")
def deadline_red(layout):
    marks = _markers(layout, "deadline")
    assert marks and marks[0]["color"] == cr.DEADLINE_SLIPPED


@then("the deadline marker has a dashed guide line")
def deadline_dashed(layout):
    assert _markers(layout, "deadline")[0]["dashed"] is True


@then("the bar is not marked slipped")
def bar_not_slipped(layout):
    work = next(b for b in layout.bars if b["task_id"] == "T")
    assert not work.get("slipped")


@then("the bar is marked slipped")
def bar_slipped(layout):
    work = next(b for b in layout.bars if b["task_id"] == "T")
    assert work.get("slipped")


@then("there is a red lock marker")
def red_lock(layout):
    marks = _markers(layout, "constraint_lock")
    assert marks and marks[0]["color"] == cr.CONSTRAINT_RED


@then("there is a blue bracket marker")
def blue_bracket(layout):
    marks = _markers(layout, "constraint_bracket")
    assert marks and marks[0]["color"] == cr.CONSTRAINT_BLUE
