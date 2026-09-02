"""pytest-bdd regression coverage for GitHub issue #7."""
import tkinter as tk
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.models import Project, Task


def _display_available() -> bool:
    try:
        root = tk.Tk()
    except Exception:
        return False
    root.destroy()
    return True


HAVE_DISPLAY = _display_available()
pytestmark = [pytest.mark.skipif(not HAVE_DISPLAY, reason="needs a display")]
scenarios("features/single_task_drag_placement.feature")


@given("the issue 7 project hierarchy", target_fixture="drag_context")
def the_issue_7_project_hierarchy(monkeypatch):
    import customtkinter as ctk

    start = datetime(2026, 9, 1)

    def task(task_id, name, parent=None, task_type="Task"):
        return Task(
            id=task_id, name=name, parent_task_id=parent,
            task_type=task_type, start_date=start,
            end_date=start + timedelta(days=1),
        )

    project = Project(name="Issue 7", tasks=[
        task("project", "Project", task_type="Phase"),
        task("planning", "Planning", "project", "Phase"),
        task("design", "Design Phase", "planning", "Task"),
        task("ui", "UI Mockups", "design", "Subtask"),
        task("implementation", "Implementation", "project", "Task"),
        task("testing", "Testing", "project", "Task"),
    ])
    root = ctk.CTk()
    root.withdraw()
    log_messages = []

    def record_log(message, *args):
        log_messages.append(message % args if args else message)

    monkeypatch.setattr("gantt_app.models.logger.info", record_log)
    context = {
        "project": project,
        "root": root,
        "moved": None,
        "log_messages": log_messages,
    }
    yield context
    try:
        root.destroy()
    except tk.TclError:
        pass


@given("the task list is open for drag placement")
def task_list_is_open(drag_context):
    from gantt_app.views.task_list import DragDropTaskList

    widget = DragDropTaskList(drag_context["root"], drag_context["project"])
    widget.pack(fill=tk.BOTH, expand=True)
    drag_context["root"].update_idletasks()
    drag_context["widget"] = widget


@when(parsers.parse("{source} is dropped {edge} {target}"))
def task_is_dropped_at_line(drag_context, source, edge, target):
    ids = {
        "Implementation": "implementation",
        "Project": "project",
        "UI Mockups": "ui",
        "Design Phase": "design",
        "Testing": "testing",
    }
    drag_context["moved"] = drag_context["widget"].move_task_to_line(
        ids[source], ids[target], edge == "above"
    )


@given(parsers.parse("Implementation is being dragged over the {edge} edge of {target}"))
def implementation_is_being_dragged(drag_context, edge, target):
    target_id = {"Testing": "testing", "UI Mockups": "ui"}[target]
    widget = drag_context["widget"]
    widget.dragged_task_id = "implementation"
    widget._dragging = True
    box = widget.tree.bbox(target_id) or (0, 10, 300, 24)
    original_bbox = widget.tree.bbox
    widget.tree.bbox = lambda item: box if item == target_id else original_bbox(item)
    _x, y, _width, height = box
    pointer_y = y + (1 if edge == "upper" else height - 1)
    widget._mark_drop_target(target_id, pointer_y)


@when("the mouse button is released")
def mouse_button_is_released(drag_context):
    drag_context["widget"].on_release(SimpleNamespace(x=0, y=0))


@then("Implementation is the first child of Design Phase")
def implementation_is_first_design_child(drag_context):
    project = drag_context["project"]
    implementation = project.get_task_by_id("implementation")
    children = [task.id for task in project.display_order()
                if task.parent_task_id == "design"]
    assert implementation.parent_task_id == "design"
    assert children[0] == "implementation"


@then("Implementation is a child of Design Phase")
def implementation_is_design_child(drag_context):
    assert drag_context["project"].get_task_by_id(
        "implementation").parent_task_id == "design"


@then(parsers.parse("Implementation appears immediately {edge} {target}"))
def implementation_appears_at_edge(drag_context, edge, target):
    target_id = {"UI Mockups": "ui", "Testing": "testing"}[target]
    siblings = drag_context["project"].get_siblings("implementation")
    order = [task.id for task in siblings]
    implementation_index = order.index("implementation")
    target_index = order.index(target_id)
    difference = implementation_index - target_index
    assert difference == (-1 if edge == "before" else 1)


@then("UI Mockups is accepted as the line drop target")
def ui_mockups_is_accepted_as_line_target(drag_context):
    widget = drag_context["widget"]
    assert widget._drop_target == "ui"
    assert widget._drop_as_parent is False


@then("the upper insertion edge is remembered")
def upper_insertion_edge_is_remembered(drag_context):
    assert drag_context["widget"]._drop_above is True


@then("the line drop is rejected")
def line_drop_is_rejected(drag_context):
    assert drag_context["moved"] is False


@then("Project remains a root task")
def project_remains_root(drag_context):
    assert drag_context["project"].get_task_by_id("project").parent_task_id is None


@then("the drag placement log names Implementation, UI Mockups, and above")
def drag_log_names_placement(drag_context):
    text = "\n".join(drag_context["log_messages"])
    assert "Implementation" in text
    assert "UI Mockups" in text
    assert "above" in text
