"""pytest-bdd coverage for REQ-TSK-012 task group re-parenting."""
import tkinter as tk
from datetime import datetime, timedelta

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.models import Project, Task
from gantt_app.utils.undoredo import ProjectStateTracker, UndoRedoManager


def _display_available() -> bool:
    try:
        root = tk.Tk()
    except Exception:
        return False
    root.destroy()
    return True


HAVE_DISPLAY = _display_available()
pytestmark = [pytest.mark.skipif(not HAVE_DISPLAY, reason="needs a display")]
scenarios("features/task_group_reparenting.feature")


@given("a project with nested task groups", target_fixture="hierarchy")
def a_project_with_nested_task_groups():
    start = datetime(2026, 9, 7)
    implementation = Task(
        id="implementation", name="Implementation", task_type="Phase",
        start_date=start, end_date=start + timedelta(days=12),
    )
    design = Task(
        id="design", name="Design", task_type="Phase",
        start_date=start + timedelta(days=1), end_date=start + timedelta(days=5),
    )
    wireframes = Task(
        id="wireframes", name="Wireframes", task_type="Task",
        parent_task_id="design", start_date=start + timedelta(days=2),
        end_date=start + timedelta(days=4),
        resource_assignments=[{"kind": "resource", "id": "designer", "estimated_hours": 24}],
    )
    project = Project(
        name="Hierarchy BDD", tasks=[implementation, design, wireframes]
    )
    schedules = {
        task.id: (task.start_date, task.end_date) for task in project.tasks
    }
    assignments = {
        task.id: list(task.resource_assignments) for task in project.tasks
    }
    hierarchy = {
        "project": project,
        "moved": None,
        "schedules": schedules,
        "assignments": assignments,
        "hotkey_result": None,
        "status": None,
    }
    yield hierarchy
    root = hierarchy.get("root")
    if root is not None:
        try:
            root.destroy()
        except tk.TclError:
            pass


@pytest.fixture
def project(hierarchy):
    return hierarchy["project"]


def _build_tree(hierarchy, platform=None, undo=False):
    import customtkinter as ctk
    import gantt_app.views.task_list as task_list_module

    if platform is not None:
        task_list_module.sys.platform = platform
    root = ctk.CTk()
    root.withdraw()
    tracker = None
    if undo:
        manager = UndoRedoManager(max_history=10)
        manager.set_project(hierarchy["project"])
        tracker = ProjectStateTracker(hierarchy["project"], manager)
        hierarchy["undo_manager"] = manager
    widget = task_list_module.DragDropTaskList(
        root,
        hierarchy["project"],
        project_tracker=tracker,
        on_status=lambda text: hierarchy.__setitem__("status", text),
    )
    widget.pack(fill=tk.BOTH, expand=True)
    root.update_idletasks()
    hierarchy["root"] = root
    hierarchy["tree"] = widget
    return widget


@when(parsers.parse("the {task_name} group is moved into the {parent_name} group"))
def a_group_is_moved_into_another(hierarchy, task_name, parent_name):
    ids = {"Design": "design", "Implementation": "implementation"}
    hierarchy["moved"] = hierarchy["project"].reparent_task(
        ids[task_name], ids[parent_name]
    )


@when("the Implementation group is moved into itself")
def the_group_is_moved_into_itself(hierarchy):
    hierarchy["moved"] = hierarchy["project"].reparent_task(
        "implementation", "implementation"
    )


@when("the Implementation group is moved into the Wireframes task")
def the_group_is_moved_into_its_descendant(hierarchy):
    assert hierarchy["project"].reparent_task("design", "implementation")
    hierarchy["moved"] = hierarchy["project"].reparent_task(
        "implementation", "wireframes"
    )


@when("the Wireframes task is moved into the Implementation group")
def the_task_is_moved_into_the_group(hierarchy):
    hierarchy["moved"] = hierarchy["project"].reparent_task(
        "wireframes", "implementation"
    )


@given("the Design group is under the Implementation group")
def the_design_group_is_under_implementation(hierarchy):
    assert hierarchy["project"].reparent_task("design", "implementation")


@given("the task tree is open")
def the_task_tree_is_open(hierarchy):
    _build_tree(hierarchy)


@given("the task tree is open with undo support")
def the_task_tree_is_open_with_undo_support(hierarchy):
    _build_tree(hierarchy, undo=True)


@given("the task tree is open for macOS")
def the_task_tree_is_open_for_macos(hierarchy, monkeypatch):
    monkeypatch.setattr("gantt_app.views.task_list.sys.platform", "darwin")
    _build_tree(hierarchy)


@given("the task tree is open for Linux")
def the_task_tree_is_open_for_linux(hierarchy, monkeypatch):
    monkeypatch.setattr("gantt_app.views.task_list.sys.platform", "linux")
    _build_tree(hierarchy)


@given("the Design group is selected")
def the_design_group_is_selected(hierarchy):
    hierarchy["tree"].tree.selection_set("design")


@when("the indent hotkey is invoked")
def the_indent_hotkey_is_invoked(hierarchy):
    hierarchy["hotkey_result"] = hierarchy["tree"]._hotkey_indent()


@when("the outdent hotkey is invoked")
def the_outdent_hotkey_is_invoked(hierarchy):
    hierarchy["hotkey_result"] = hierarchy["tree"]._hotkey_outdent()


@given("the Design group is being dragged over the Implementation group center")
def the_design_group_is_dragged_over_implementation(hierarchy):
    widget = hierarchy["tree"]
    widget.dragged_task_id = "design"
    box = widget.tree.bbox("implementation") or (0, 10, 300, 24)
    original_bbox = widget.tree.bbox
    widget.tree.bbox = lambda item: box if item == "implementation" else original_bbox(item)
    _x, y, _width, height = box
    widget._mark_drop_target("implementation", y + height // 2)


@when("the Design group is drag-reparented into the Implementation group")
def the_design_group_is_drag_reparented(hierarchy):
    hierarchy["tree"].reparent_task("design", "implementation")


@when("the hierarchy move is undone")
def the_hierarchy_move_is_undone(hierarchy):
    hierarchy["tree"].undo()


@then("the Design group parent is the Implementation group")
def the_design_parent_is_implementation(project):
    assert project.get_task_by_id("design").parent_task_id == "implementation"


@then("the Wireframes task parent is the Implementation group")
def wireframes_parent_is_implementation(project):
    assert project.get_task_by_id("wireframes").parent_task_id == "implementation"


@then("the Design branch remains together")
def the_design_branch_remains_together(project):
    order = [task.id for task in project.display_order()]
    assert order.index("design") + 1 == order.index("wireframes")
    assert project.get_task_by_id("wireframes").parent_task_id == "design"


@then("the hierarchy move is rejected")
def the_hierarchy_move_is_rejected(hierarchy):
    assert hierarchy["moved"] is False


@then("the Implementation group remains a root task")
def implementation_remains_root(project):
    assert project.get_task_by_id("implementation").parent_task_id is None


@then("the Design group remains a root task")
def design_remains_root(project):
    assert project.get_task_by_id("design").parent_task_id is None


@then("every task in the Design branch keeps its schedule")
def design_branch_keeps_schedule(hierarchy):
    for task_id in ("design", "wireframes"):
        task = hierarchy["project"].get_task_by_id(task_id)
        assert (task.start_date, task.end_date) == hierarchy["schedules"][task_id]


@then("every task in the Design branch keeps its assignments")
def design_branch_keeps_assignments(hierarchy):
    for task_id in ("design", "wireframes"):
        task = hierarchy["project"].get_task_by_id(task_id)
        assert task.resource_assignments == hierarchy["assignments"][task_id]


@then(parsers.parse("the {task_name} group indentation is {pixels:d} pixels"))
def group_indentation(project, task_name, pixels):
    ids = {"Implementation": "implementation", "Design": "design"}
    assert project.hierarchy_indent_px(ids[task_name]) == pixels


@then(parsers.parse("the Wireframes task indentation is {pixels:d} pixels"))
def wireframes_indentation(project, pixels):
    assert project.hierarchy_indent_px("wireframes") == pixels


@then("the hotkey stops default focus traversal")
def hotkey_stops_default_focus(hierarchy):
    assert hierarchy["hotkey_result"] == "break"


@then("Tab and Shift-Tab hierarchy hotkeys are configured")
def common_hotkeys_are_configured(hierarchy):
    bindings = hierarchy["tree"]._hierarchy_bindings
    assert "<Tab>" in bindings
    assert "<Shift-Tab>" in bindings
    assert "<ISO_Left_Tab>" in bindings


@then("macOS Command and Option hierarchy hotkeys are configured")
def mac_hotkeys_are_configured(hierarchy):
    bindings = hierarchy["tree"]._hierarchy_bindings
    assert "<Command-bracketright>" in bindings
    assert "<Command-bracketleft>" in bindings
    assert "<Option-Shift-Right>" in bindings
    assert "<Option-Shift-Left>" in bindings


@then("Control and Alt hierarchy hotkeys are configured")
def non_mac_hotkeys_are_configured(hierarchy):
    bindings = hierarchy["tree"]._hierarchy_bindings
    assert "<Control-bracketright>" in bindings
    assert "<Control-bracketleft>" in bindings
    assert "<Alt-Shift-Right>" in bindings
    assert "<Alt-Shift-Left>" in bindings


@then("the drop target is marked as a parent")
def drop_target_is_parent(hierarchy):
    widget = hierarchy["tree"]
    assert widget._drop_target == "implementation"
    assert widget._drop_as_parent is True


@then(parsers.parse('the drop target status is "{text}"'))
def drop_target_status(hierarchy, text):
    hierarchy["root"].update_idletasks()
    assert hierarchy["status"] == text
