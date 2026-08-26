"""
Unit tests for Copy, Cut, and Paste functionality.

Tests the clipboard operations including:
- ClipboardPayload and ClipboardItem dataclasses
- ClipboardService operations (copy, cut, paste)
- ClipboardManager singleton
- Task serialization/deserialization
- Edge cases and validation
"""

import unittest
from datetime import datetime, timedelta
import uuid
import copy

from gantt_app.models import Task, Project, Dependency
from gantt_app.utils.copypastecut import (
    ClipboardService,
    ClipboardManager,
    ClipboardPayload,
    ClipboardItem,
    ENTITY_TYPES,
    CONTAINER_TYPES,
)


def _display_available() -> bool:
    """Whether a usable Tk display is present."""
    try:
        import tkinter
        root = tkinter.Tk()
    except Exception:
        return False
    root.destroy()
    return True


HAVE_DISPLAY = _display_available()


class TestClipboardPayloadModel(unittest.TestCase):
    """Test cases for ClipboardPayload and ClipboardItem dataclasses."""

    def test_clipboard_item_creation(self):
        """Test creating a ClipboardItem."""
        item = ClipboardItem(
            id="task-001",
            type="task",
            payload={"name": "Test Task", "id": "task-001"}
        )
        
        self.assertEqual(item.id, "task-001")
        self.assertEqual(item.type, "task")
        self.assertEqual(item.payload["name"], "Test Task")

    def test_clipboard_payload_creation(self):
        """Test creating a ClipboardPayload."""
        item = ClipboardItem(
            id="task-001",
            type="task",
            payload={"name": "Test Task"}
        )
        payload = ClipboardPayload(
            operation="copy",
            source_container_id="phase-001",
            items=[item]
        )
        
        self.assertEqual(payload.operation, "copy")
        self.assertEqual(payload.source_container_id, "phase-001")
        self.assertEqual(len(payload.items), 1)
        self.assertEqual(payload.items[0].id, "task-001")

    def test_clipboard_payload_default_values(self):
        """Test default values for ClipboardPayload."""
        payload = ClipboardPayload(operation="cut")
        
        self.assertEqual(payload.operation, "cut")
        self.assertIsNone(payload.source_container_id)
        self.assertEqual(payload.items, [])

    def test_entity_types_constant(self):
        """Test ENTITY_TYPES constant."""
        self.assertIn("task", ENTITY_TYPES)
        self.assertIn("deliverable", ENTITY_TYPES)
        self.assertIn("phase", ENTITY_TYPES)
        self.assertIn("subtask", ENTITY_TYPES)
        self.assertIn("milestone", ENTITY_TYPES)

    def test_container_types_constant(self):
        """Test CONTAINER_TYPES constant."""
        self.assertIn("phase", CONTAINER_TYPES)
        self.assertIn("deliverable", CONTAINER_TYPES)
        self.assertIn("task", CONTAINER_TYPES)
        self.assertNotIn("subtask", CONTAINER_TYPES)
        self.assertNotIn("milestone", CONTAINER_TYPES)


class TestClipboardService(unittest.TestCase):
    """Test cases for ClipboardService class."""

    def setUp(self):
        """Set up test fixtures."""
        self.project = Project(name="Test Project")
        self.service = ClipboardService(self.project)
        
        # Create test tasks
        today = datetime(2024, 1, 1)
        self.task1 = Task.create_task(
            name="Task 1",
            start_date=today,
            end_date=today + timedelta(days=5),
            task_id="001"
        )
        self.task2 = Task.create_task(
            name="Task 2",
            start_date=today + timedelta(days=2),
            end_date=today + timedelta(days=7),
            task_id="002"
        )
        self.phase = Task.create_task(
            name="Phase 1",
            start_date=today,
            end_date=today + timedelta(days=10),
            task_id="003"
        )
        self.phase.task_type = "Phase"
        
        self.project.add_task(self.task1)
        self.project.add_task(self.task2)
        self.project.add_task(self.phase)

    def test_service_initialization(self):
        """Test ClipboardService initialization."""
        self.assertEqual(self.service.project, self.project)
        self.assertIsNone(self.service.active_payload)
        self.assertEqual(self.service.cut_item_ids, set())

    def test_copy_single_task(self):
        """Test copying a single task."""
        self.service.copy(["001"])
        
        self.assertIsNotNone(self.service.active_payload)
        self.assertEqual(self.service.active_payload.operation, "copy")
        self.assertEqual(len(self.service.active_payload.items), 1)
        self.assertEqual(self.service.active_payload.items[0].id, "001")
        self.assertEqual(self.service.active_payload.items[0].type, "task")

    def test_copy_multiple_tasks(self):
        """Test copying multiple tasks."""
        self.service.copy(["001", "002"])
        
        self.assertIsNotNone(self.service.active_payload)
        self.assertEqual(len(self.service.active_payload.items), 2)
        task_ids = [item.id for item in self.service.active_payload.items]
        self.assertIn("001", task_ids)
        self.assertIn("002", task_ids)

    def test_copy_clears_cut_state(self):
        """Test that copy clears any previous cut state."""
        self.service.cut(["001"])
        self.assertEqual(self.service.cut_item_ids, {"001"})
        
        self.service.copy(["002"])
        self.assertEqual(self.service.cut_item_ids, set())

    def test_cut_single_task(self):
        """Test cutting a single task."""
        self.service.cut(["001"])
        
        self.assertIsNotNone(self.service.active_payload)
        self.assertEqual(self.service.active_payload.operation, "cut")
        self.assertEqual(self.service.cut_item_ids, {"001"})

    def test_cut_multiple_tasks(self):
        """Test cutting multiple tasks."""
        self.service.cut(["001", "002"])
        
        self.assertEqual(self.service.cut_item_ids, {"001", "002"})

    def test_cut_clears_previous_cut_state(self):
        """Test that cut clears previous cut state."""
        self.service.cut(["001"])
        self.service.cut(["002"])
        
        self.assertEqual(self.service.cut_item_ids, {"002"})

    def test_paste_copy_creates_new_tasks(self):
        """Test that pasting copied tasks creates new tasks with new IDs."""
        # Copy task
        self.service.copy(["001"])
        
        # Paste to root
        initial_task_count = len(self.project.tasks)
        self.service.paste(None)
        
        # Should have one more task
        self.assertEqual(len(self.project.tasks), initial_task_count + 1)
        
        # The copy is a task of its own, with its own key
        copy_row = next(t for t in self.project.tasks
                        if t.name == "Task 1" and t is not self.task1)
        self.assertNotEqual(copy_row.id, self.task1.id)
        self.assertEqual(copy_row.name, "Task 1")

    def test_paste_cut_moves_tasks(self):
        """Test that pasting cut tasks moves them to new container."""
        # Make task1 a child of phase
        self.task1.parent_task_id = "003"
        
        # Cut task
        self.service.cut(["001"])
        
        # Paste to root (None)
        self.service.paste(None)
        
        # Task should now have parent_task_id = None
        moved_task = self.project.get_task_by_id("001")
        self.assertIsNotNone(moved_task)
        self.assertIsNone(moved_task.parent_task_id)
        
        # Cut state should be cleared
        self.assertEqual(self.service.cut_item_ids, set())
        self.assertIsNone(self.service.active_payload)

    def test_paste_into_container(self):
        """Test pasting tasks into a container task."""
        # Copy task
        self.service.copy(["001"])
        
        # Paste into phase
        self.service.paste("003")
        
        # New task should have phase as parent
        new_task = self.project.tasks[-1]
        self.assertEqual(new_task.parent_task_id, "003")

    def test_cannot_paste_into_leaf(self):
        """Test that paste into a leaf node (non-container) is prevented."""
        # Make task2 a subtask (leaf node)
        self.task2.task_type = "Subtask"
        
        # Copy task
        self.service.copy(["001"])
        
        # Try to paste into subtask - should do nothing
        initial_count = len(self.project.tasks)
        self.service.paste("002")
        
        # No new task should be created
        self.assertEqual(len(self.project.tasks), initial_count)

    def test_clear_clipboard(self):
        """Test clearing the clipboard."""
        self.service.copy(["001"])
        self.assertIsNotNone(self.service.active_payload)
        
        self.service.clear_clipboard()
        self.assertIsNone(self.service.active_payload)
        self.assertEqual(self.service.cut_item_ids, set())

    def test_is_clipboard_empty(self):
        """Test checking if clipboard is empty."""
        self.assertTrue(self.service.is_clipboard_empty())
        
        self.service.copy(["001"])
        self.assertFalse(self.service.is_clipboard_empty())
        
        self.service.clear_clipboard()
        self.assertTrue(self.service.is_clipboard_empty())

    def test_can_copy_or_cut(self):
        """Test checking if copy or cut is possible."""
        # With no selection
        self.assertFalse(self.service.can_copy_or_cut([]))
        
        # With selection
        self.assertTrue(self.service.can_copy_or_cut(["001"]))

    def test_can_paste(self):
        """Test checking if paste is possible."""
        # With empty clipboard
        self.assertFalse(self.service.can_paste(None))
        
        # With items in clipboard
        self.service.copy(["001"])
        self.assertTrue(self.service.can_paste(None))
        self.assertTrue(self.service.can_paste("003"))
        
        # With leaf container
        self.task2.task_type = "Subtask"
        self.assertFalse(self.service.can_paste("002"))

    def test_copy_creates_deep_copy(self):
        """Test that copy creates a deep copy of the task."""
        self.service.copy(["001"])
        
        # Modify original task
        original_name = self.task1.name
        self.task1.name = "Modified Task"
        
        # Clipboard should still have original name
        payload_item = self.service.active_payload.items[0]
        self.assertEqual(payload_item.payload["name"], original_name)

    def test_task_to_dict_handles_datetimes(self):
        """Test that task serialization handles datetime objects."""
        task_dict = self.service._task_to_dict(self.task1)
        
        self.assertIn("start_date", task_dict)
        self.assertIn("end_date", task_dict)
        # Should be ISO format strings
        self.assertIsInstance(task_dict["start_date"], str)
        self.assertIsInstance(task_dict["end_date"], str)

    def test_task_to_dict_handles_dependencies(self):
        """Test that task serialization handles dependencies."""
        self.task1.add_dependency("002", dep_type="FS", hardness="Hard", lag=1)
        
        task_dict = self.service._task_to_dict(self.task1)
        
        self.assertIn("dependencies", task_dict)
        self.assertEqual(len(task_dict["dependencies"]), 1)
        self.assertEqual(task_dict["dependencies"][0]["task_id"], "002")

    def test_dict_to_task_reconstructs_task(self):
        """Test that task deserialization reconstructs Task objects."""
        task_dict = self.service._task_to_dict(self.task1)
        
        reconstructed = self.service._dict_to_task(task_dict)
        
        self.assertEqual(reconstructed.id, self.task1.id)
        self.assertEqual(reconstructed.name, self.task1.name)
        self.assertEqual(reconstructed.start_date, self.task1.start_date)
        self.assertEqual(reconstructed.end_date, self.task1.end_date)

    def test_dict_to_task_handles_dependencies(self):
        """Test that task deserialization handles dependencies."""
        self.task1.add_dependency("002", dep_type="FS", hardness="Rubber", lag=2)
        
        task_dict = self.service._task_to_dict(self.task1)
        reconstructed = self.service._dict_to_task(task_dict)
        
        self.assertEqual(len(reconstructed.dependencies), 1)
        dep = reconstructed.dependencies[0]
        self.assertEqual(dep.task_id, "002")
        self.assertEqual(dep.dep_type, "FS")
        self.assertEqual(dep.hardness, "Rubber")
        self.assertEqual(dep.lag, 2)

    def test_get_entity_type(self):
        """Test getting entity type from task."""
        self.assertEqual(self.service._get_entity_type(self.task1), "task")
        
        self.phase.task_type = "Phase"
        self.assertEqual(self.service._get_entity_type(self.phase), "phase")
        
        milestone = Task.create_milestone(
            name="Milestone",
            date=datetime(2024, 1, 10)
        )
        self.assertEqual(self.service._get_entity_type(milestone), "milestone")

    def test_can_accept_types(self):
        """Test container type validation."""
        # Phase can accept tasks
        self.assertTrue(self.service._can_accept_types("003", ["task"]))
        
        # None (root) can accept all types
        self.assertTrue(self.service._can_accept_types(None, ["task"]))
        self.assertTrue(self.service._can_accept_types(None, ["phase"]))
        
        # Subtask cannot accept children
        self.task2.task_type = "Subtask"
        self.assertFalse(self.service._can_accept_types("002", ["task"]))

    def test_copy_with_nonexistent_task(self):
        """Test copying a task that doesn't exist."""
        self.service.copy(["999"])  # Non-existent task
        
        # Should handle gracefully - no items in clipboard
        self.assertTrue(self.service.is_clipboard_empty())

    def test_copy_with_empty_selection(self):
        """Test copying with empty selection."""
        self.service.copy([])
        
        # Should handle gracefully
        self.assertTrue(self.service.is_clipboard_empty())

    def test_copy_with_no_project(self):
        """Test copying with no project set."""
        service = ClipboardService(None)
        service.copy(["001"])
        
        # Should handle gracefully
        self.assertTrue(service.is_clipboard_empty())

    def test_get_task_by_id(self):
        """Test getting task by ID from project."""
        task = self.service._get_task_by_id("001")
        self.assertEqual(task, self.task1)
        
        task = self.service._get_task_by_id("999")
        self.assertIsNone(task)


class TestClipboardManager(unittest.TestCase):
    """Test cases for ClipboardManager singleton."""

    def setUp(self):
        """Set up test fixtures."""
        # Reset singleton for each test
        ClipboardManager._instance = None
        
        self.project = Project(name="Test Project")
        today = datetime(2024, 1, 1)
        self.task1 = Task.create_task(
            name="Task 1",
            start_date=today,
            end_date=today + timedelta(days=5),
            task_id="001"
        )
        self.project.add_task(self.task1)

    def tearDown(self):
        """Clean up after each test."""
        ClipboardManager._instance = None

    def test_singleton_pattern(self):
        """Test that ClipboardManager is a singleton."""
        manager1 = ClipboardManager(self.project)
        manager2 = ClipboardManager.get_instance()
        
        self.assertIs(manager1, manager2)

    def test_set_project(self):
        """Test setting the project after initialization."""
        manager = ClipboardManager()
        self.assertIsNone(manager.service.project)
        
        manager.set_project(self.project)
        self.assertEqual(manager.service.project, self.project)

    def test_copy_through_manager(self):
        """Test copy operation through manager."""
        manager = ClipboardManager(self.project)
        manager.copy(["001"])
        
        self.assertFalse(manager.is_empty())

    def test_cut_through_manager(self):
        """Test cut operation through manager."""
        manager = ClipboardManager(self.project)
        manager.cut(["001"])
        
        self.assertFalse(manager.is_empty())

    def test_paste_through_manager(self):
        """Test paste operation through manager."""
        manager = ClipboardManager(self.project)
        manager.copy(["001"])
        initial_count = len(self.project.tasks)
        
        manager.paste(None)
        
        self.assertEqual(len(self.project.tasks), initial_count + 1)

    def test_clear_through_manager(self):
        """Test clear operation through manager."""
        manager = ClipboardManager(self.project)
        manager.copy(["001"])
        
        manager.clear()
        self.assertTrue(manager.is_empty())

    def test_manager_delegates_to_service(self):
        """Test that manager methods delegate to service."""
        manager = ClipboardManager(self.project)
        
        self.assertEqual(manager.service, manager.service)
        self.assertIsNotNone(manager.service)


class TestClipboardWithTaskHierarchy(unittest.TestCase):
    """Test cases for clipboard operations with task hierarchy."""

    def setUp(self):
        """Set up test fixtures with hierarchical tasks."""
        self.project = Project(name="Test Project")
        self.service = ClipboardService(self.project)
        
        today = datetime(2024, 1, 1)
        
        # Create a phase
        self.phase = Task.create_task(
            name="Phase 1",
            start_date=today,
            end_date=today + timedelta(days=20),
            task_id="P001"
        )
        self.phase.task_type = "Phase"
        self.project.add_task(self.phase)
        
        # Create a task under the phase
        self.task = Task.create_task(
            name="Task 1",
            start_date=today,
            end_date=today + timedelta(days=5),
            task_id="T001"
        )
        self.task.parent_task_id = "P001"
        self.project.add_task(self.task)
        
        # Create a subtask under the task
        self.subtask = Task.create_task(
            name="Subtask 1",
            start_date=today,
            end_date=today + timedelta(days=2),
            task_id="ST001"
        )
        self.subtask.task_type = "Subtask"
        self.subtask.parent_task_id = "T001"
        self.project.add_task(self.subtask)

    def test_copy_preserves_parent_child_relationship(self):
        """Test that copying a task preserves parent-child relationships."""
        self.service.copy(["T001"])

        pasted = self.service.paste("P001")

        # The phase wears whatever number the renumbering gave it
        self.assertEqual(self.project.get_task_by_id(pasted[0]).parent_task_id,
                         self.phase.id)

    def test_a_copy_keeps_the_name_it_was_copied_from(self):
        """
        Whatever it is pasted into.

        The suffix this used to add appeared only for a paste into the
        container the row came from, so the same operation named the row
        two different ways depending on where it was aimed.
        """
        self.service.copy(["T001"])
        source_container = self.task.parent_task_id

        pasted = self.service.paste(source_container)

        self.assertEqual(self.project.get_task_by_id(pasted[0]).name,
                         "Task 1")

    def test_a_link_to_something_not_copied_is_dropped(self):
        """A copy does not arrive already waiting on work nobody copied."""
        self.task.add_dependency("P001")

        self.service.copy(["T001"])
        self.service.paste("P001")

        new_task = self.project.tasks[-1]
        self.assertEqual(list(new_task.dependencies), [])

    def test_a_link_within_the_selection_follows_the_copies(self):
        """Two tasks copied together stay linked to each other, not to the
        originals."""
        second = Task.create_task(
            name="Task 2", start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 6), task_id="T002")
        second.parent_task_id = "P001"
        self.project.add_task(second)
        second.add_dependency("T001")

        self.service.copy(["T001", "T002"])
        pasted = self.service.paste("P001")

        follower = self.project.get_task_by_id(pasted[1])
        self.assertEqual([d.task_id for d in follower.dependencies],
                         [pasted[0]])

    def test_a_parent_copied_with_its_child_keeps_the_child(self):
        """
        Copying both halves of a parentage reproduces it.

        The sub-task lands under the copy of its own task, not beside it and
        not in the container the paste named - which is also why a selection
        like this one is no longer refused for holding a sub-task that a
        phase could not have taken on its own.
        """
        self.service.copy(["T001", "ST001"])
        pasted = self.service.paste("P001")

        self.assertEqual(len(pasted), 2)
        self.assertEqual(
            self.project.get_task_by_id(pasted[0]).parent_task_id,
            self.phase.id)
        self.assertEqual(
            self.project.get_task_by_id(pasted[1]).parent_task_id, pasted[0])

    def test_paste_multiple_tasks_into_container(self):
        """Test pasting multiple tasks into a container."""
        second = Task.create_task(
            name="Task 2", start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 6), task_id="T002")
        second.parent_task_id = "P001"
        self.project.add_task(second)

        self.service.copy(["T001", "T002"])

        initial_count = len(self.project.tasks)
        self.service.paste("P001")

        # Should have 2 new tasks
        self.assertEqual(len(self.project.tasks), initial_count + 2)

    def test_a_selection_is_refused_where_one_does_not_belong(self):
        """
        A sub-task on its own does not go into a phase, so neither does the
        selection holding it.

        Pasting only the half that fits would leave the user with some of
        what they picked out and no word about the rest. A sub-task whose
        own task was copied with it is a different case, and is allowed -
        see test_a_parent_copied_with_its_child_keeps_the_child.
        """
        self.service.copy(["ST001"])

        initial_count = len(self.project.tasks)
        self.service.paste("P001")

        self.assertEqual(len(self.project.tasks), initial_count)


class TestOnlyWhatIsSelected(unittest.TestCase):
    """
    The clipboard carries the rows picked out, and nothing else.

    WHY THESE EXIST:
    ================
    Copying a phase copies the phase. The work under it is not brought along
    and is not duplicated: a plan is a tree, and duplicating a branch of it
    because its top row was picked out is not what picking out one row means.
    """

    def setUp(self):
        """A phase holding a task, which holds a sub-task."""
        self.project = Project(name="Test Project")
        self.service = ClipboardService(self.project)

        today = datetime(2024, 1, 1)
        self.phase = Task.create_task(name="Phase 1", start_date=today,
                                      end_date=today + timedelta(days=20),
                                      task_id="P001")
        self.phase.task_type = "Phase"
        self.project.add_task(self.phase)

        self.task = Task.create_task(name="Task 1", start_date=today,
                                     end_date=today + timedelta(days=5),
                                     task_id="T001")
        self.task.parent_task_id = "P001"
        self.project.add_task(self.task)

        self.subtask = Task.create_task(name="Subtask 1", start_date=today,
                                        end_date=today + timedelta(days=2),
                                        task_id="ST001")
        self.subtask.task_type = "Subtask"
        self.subtask.parent_task_id = "T001"
        self.project.add_task(self.subtask)

    def test_copying_a_phase_puts_one_item_on_the_clipboard(self):
        """Its task and sub-task are not picked up with it."""
        self.service.copy(["P001"])

        self.assertEqual([item.id for item in self.service.active_payload.items],
                         ["P001"])

    def test_pasting_a_copied_phase_adds_one_task(self):
        """One new row, not a duplicate of the branch."""
        before = len(self.project.tasks)

        self.service.copy(["P001"])
        self.service.paste(None)

        self.assertEqual(len(self.project.tasks), before + 1)

    def test_the_copy_has_no_children(self):
        """Nothing was reparented onto the new phase."""
        self.service.copy(["P001"])
        self.service.paste(None)

        new_phase = self.project.tasks[-1]
        children = [t for t in self.project.tasks
                    if t.parent_task_id == new_phase.id]

        self.assertEqual(children, [])

    def test_the_original_keeps_its_children(self):
        """Copying takes nothing away from what was copied."""
        self.service.copy(["P001"])
        self.service.paste(None)

        # Compared against the live rows: a paste renumbers the plan, and
        # these are the same task objects throughout
        self.assertEqual(self.task.parent_task_id, self.phase.id)
        self.assertEqual(self.subtask.parent_task_id, self.task.id)

    def test_two_selected_rows_give_two_items(self):
        """A parent and its child picked out together are exactly those two."""
        self.service.copy(["P001", "T001"])

        self.assertEqual([item.id for item in self.service.active_payload.items],
                         ["P001", "T001"])

    def test_a_pasted_copy_is_numbered_like_the_rest(self):
        """
        It takes the next ID in the project's sequence.

        The ID is a column in the task list, and a plan that reads 001, 002,
        4f3c8a91-... in the same table does not.
        """
        self.service.copy(["T001"])
        self.service.paste(None)

        new_task = self.project.tasks[-1]

        self.assertTrue(new_task.id.isdigit(),
                        f"{new_task.id!r} is not a plain number")

    def test_two_pasted_copies_do_not_share_an_id(self):
        """Both are numbered, and numbered differently."""
        self.service.copy(["P001", "T001"])
        self.service.paste(None)

        pasted = self.project.tasks[-2:]

        self.assertNotEqual(pasted[0].id, pasted[1].id)


class TestWhatMayGoWhere(unittest.TestCase):
    """
    The levels of the plan are an order, and pasting keeps to it.

    WHY THESE EXIST:
    ================
    Every container accepted every type. A phase could be pasted inside a
    task, which reads as a task containing a phase of the project - and the
    levels the plan totals its progress through stop meaning anything if
    they can be arranged in any order.
    """

    def setUp(self):
        """One row of each type, each under the one above it."""
        self.project = Project(name="Test Project")
        self.service = ClipboardService(self.project)

        today = datetime(2024, 1, 1)
        for task_id, kind, parent in (("P", "Phase", None),
                                      ("D", "Deliverable", "P"),
                                      ("T", "Task", "D"),
                                      ("S", "Subtask", "T"),
                                      ("M", "Milestone", "T")):
            task = Task.create_task(name=kind, start_date=today,
                                    end_date=today + timedelta(days=1),
                                    task_id=task_id)
            task.task_type = kind
            task.parent_task_id = parent
            self.project.add_task(task)

    def test_a_phase_belongs_at_the_top_and_nowhere_else(self):
        """It is the outermost scope; nothing contains it."""
        self.assertTrue(self.service._can_accept_types(None, ["phase"]))
        for container in ("P", "D", "T", "S", "M"):
            self.assertFalse(
                self.service._can_accept_types(container, ["phase"]),
                f"a phase should not go inside {container}")

    def test_a_deliverable_belongs_in_a_phase(self):
        """Or at the top, before it is filed under one."""
        self.assertTrue(self.service._can_accept_types("P", ["deliverable"]))
        self.assertTrue(self.service._can_accept_types(None, ["deliverable"]))
        self.assertFalse(self.service._can_accept_types("T", ["deliverable"]))

    def test_a_subtask_belongs_to_a_task(self):
        """It is a tick on that task's checklist and on nobody else's."""
        self.assertTrue(self.service._can_accept_types("T", ["subtask"]))
        self.assertFalse(self.service._can_accept_types("P", ["subtask"]))
        self.assertFalse(self.service._can_accept_types("D", ["subtask"]))

    def test_a_task_goes_under_the_three_that_hold_work(self):
        """A phase, a deliverable, or another task."""
        for container in ("P", "D", "T"):
            self.assertTrue(
                self.service._can_accept_types(container, ["task"]),
                f"a task should go inside {container}")

    def test_nothing_goes_inside_a_leaf(self):
        """A sub-task and a milestone hold nothing."""
        for container in ("S", "M"):
            for kind in ("task", "subtask", "milestone"):
                self.assertFalse(
                    self.service._can_accept_types(container, [kind]),
                    f"{kind} should not go inside {container}")

    def test_a_phase_pasted_into_a_task_changes_nothing(self):
        """The rule is applied, not merely reported."""
        self.service.copy(["P"])
        before = len(self.project.tasks)

        self.service.paste("T")

        self.assertEqual(len(self.project.tasks), before)


class TestSayingWhatWasPasted(unittest.TestCase):
    """
    Paste answers with the rows that arrived.

    The task list selects them, so that what the user has just pasted is
    what they can immediately drag, rename or move again.
    """

    def setUp(self):
        """A phase with one task under it."""
        self.project = Project(name="Test Project")
        self.service = ClipboardService(self.project)

        today = datetime(2024, 1, 1)
        for task_id, kind, parent in (("P", "Phase", None),
                                      ("T", "Task", "P")):
            task = Task.create_task(name=kind, start_date=today,
                                    end_date=today + timedelta(days=1),
                                    task_id=task_id)
            task.task_type = kind
            task.parent_task_id = parent
            self.project.add_task(task)

    def test_a_copy_answers_with_the_new_rows(self):
        """The new IDs, not the ones copied from."""
        self.service.copy(["T"])

        pasted = self.service.paste("P")

        self.assertEqual(len(pasted), 1)
        self.assertNotIn("T", pasted)
        self.assertIsNotNone(self.project.get_task_by_id(pasted[0]))

    def test_a_cut_answers_with_the_rows_it_moved(self):
        """
        The same rows, having moved rather than been remade.

        They answer to the number the plan gives them once the move has
        renumbered it, which is the number the caller has to select.
        """
        moved = self.project.get_task_by_id("T")

        self.service.cut(["T"])
        pasted = self.service.paste(None)

        self.assertEqual(pasted, [moved.id])
        self.assertIs(self.project.get_task_by_id(pasted[0]), moved)

    def test_a_refused_paste_answers_with_nothing(self):
        """Nothing arrived, so there is nothing to select."""
        self.service.copy(["P"])

        self.assertEqual(self.service.paste("T"), [])


class TestTheCutRowsAreMarked(unittest.TestCase):
    """A cut row is held apart until it is pasted somewhere."""

    def setUp(self):
        """A plan with two rows, and a clipboard over it."""
        self.project = Project(name="Test Project")
        self.service = ClipboardService(self.project)

        today = datetime(2024, 1, 1)
        for task_id in ("001", "002"):
            self.project.add_task(Task.create_task(
                name=f"Task {task_id}", start_date=today,
                end_date=today + timedelta(days=1), task_id=task_id))

    def test_cutting_marks_the_rows(self):
        """They are noted as pending so the list can grey them."""
        self.service.cut(["001"])

        self.assertEqual(self.service.cut_item_ids, {"001"})

    def test_copying_clears_a_previous_cut(self):
        """A copy replaces a cut, and the dimming goes with it."""
        self.service.cut(["001"])
        self.service.copy(["002"])

        self.assertEqual(self.service.cut_item_ids, set())

    def test_pasting_a_cut_clears_the_marking(self):
        """The move is done, so nothing is pending any longer."""
        self.service.cut(["001"])
        self.service.paste(None)

        self.assertEqual(self.service.cut_item_ids, set())


class TestWhereThePastedRowsLand(unittest.TestCase):
    """
    They go beside the row the paste was asked for from.

    WHY THESE EXIST:
    ================
    Paste appended to the end of the branch, so pasting from the middle of a
    long phase put the rows at the bottom of it and left the user to go and
    find them. Creating a task from the same menu has always placed the new
    row beside the one it was created from - see
    DragDropTaskList._save_created - and paste was the one action that did
    not.
    """

    def setUp(self):
        """A phase holding four tasks in a known order."""
        self.project = Project(name="Test Project")
        self.service = ClipboardService(self.project)

        today = datetime(2024, 1, 1)
        phase = Task.create_task(name="Phase", start_date=today,
                                 end_date=today + timedelta(days=30),
                                 task_id="P")
        phase.task_type = "Phase"
        self.project.add_task(phase)

        for number in ("A", "B", "C", "D"):
            task = Task.create_task(name=f"Task {number}", start_date=today,
                                    end_date=today + timedelta(days=2),
                                    task_id=number)
            task.parent_task_id = "P"
            self.project.add_task(task)

    def order(self):
        """
        The names of the phase's children, in the order they read.

        By name rather than by ID: a paste renumbers the plan, so the IDs
        these rows were built with are gone by the time the assertion runs.
        A copy carries its original's name, so a duplicate name in the list
        is the pasted row - which is what these tests are placing.
        """
        phase = next(t for t in self.project.tasks if t.name == "Phase")
        return [task.name for task in self.project.tasks
                if task.parent_task_id == phase.id]

    def test_a_pasted_row_lands_after_the_row_it_came_from(self):
        """Not at the bottom of the branch."""
        self.service.copy(["A"])

        self.service.paste("P", after_task_id="B")

        self.assertEqual(self.order(), ["Task A", "Task B", "Task A",
                                        "Task C", "Task D"])

    def test_several_pasted_rows_keep_their_order(self):
        """
        A, B pasted after C read A, B - not backwards.

        Each row is placed after the one before it rather than all of them
        after the anchor, which would reverse them.
        """
        self.service.copy(["A", "B"])

        self.service.paste("P", after_task_id="C")

        self.assertEqual(self.order(),
                         ["Task A", "Task B", "Task C", "Task A", "Task B",
                          "Task D"])

    def test_without_an_anchor_they_land_at_the_end(self):
        """A paste from the toolbar has no row behind it."""
        self.service.copy(["A"])

        self.service.paste("P")

        self.assertEqual(self.order(), ["Task A", "Task B", "Task C",
                                        "Task D", "Task A"])

    def test_a_row_pasted_under_the_anchor_is_left_where_it_is(self):
        """
        A child of the anchor is already where it belongs.

        Pasting a sub-task into the task that was right-clicked makes it a
        child of that row, not its neighbour, so there is nothing to move.
        """
        subtask = Task.create_task(name="Subtask", start_date=datetime(2024, 1, 1),
                                   end_date=datetime(2024, 1, 2), task_id="S")
        subtask.task_type = "Subtask"
        subtask.parent_task_id = "A"
        self.project.add_task(subtask)

        self.service.copy(["S"])
        self.service.paste("A", after_task_id="A")

        parent = next(t for t in self.project.tasks if t.name == "Task A")
        children = [task.name for task in self.project.tasks
                    if task.parent_task_id == parent.id]

        self.assertEqual(children, ["Subtask", "Subtask"])

    def test_a_cut_row_moves_to_beside_the_anchor(self):
        """The same placement applies to a move, not only to a copy."""
        self.service.cut(["D"])

        self.service.paste("P", after_task_id="A")

        self.assertEqual(self.order(), ["Task A", "Task D", "Task B",
                                        "Task C"])

    def test_an_anchor_that_has_gone_is_ignored(self):
        """A stale row ID leaves the paste where it landed."""
        self.service.copy(["A"])

        self.service.paste("P", after_task_id="nonexistent")

        self.assertEqual(self.order(), ["Task A", "Task B", "Task C",
                                        "Task D", "Task A"])


class TestPastingIntoItself(unittest.TestCase):
    """
    A cut task cannot be pasted inside its own subtree.

    WHY THESE EXIST:
    ================
    Nothing stopped it. Cutting a phase and pasting it into one of its own
    tasks left a loop in the parent links with no root: the phase vanished
    from the tree, which is walked down from the top, and the passes that
    settle the schedule walked the loop instead.
    """

    def setUp(self):
        """A phase holding a task, which holds a sub-task."""
        self.project = Project(name="Test Project")
        self.service = ClipboardService(self.project)

        today = datetime(2024, 1, 1)
        self.phase = Task.create_task(name="Phase 1", start_date=today,
                                      end_date=today + timedelta(days=20),
                                      task_id="P001")
        self.phase.task_type = "Phase"
        self.project.add_task(self.phase)

        self.task = Task.create_task(name="Task 1", start_date=today,
                                     end_date=today + timedelta(days=5),
                                     task_id="T001")
        self.task.parent_task_id = "P001"
        self.project.add_task(self.task)

        self.subtask = Task.create_task(name="Subtask 1", start_date=today,
                                        end_date=today + timedelta(days=2),
                                        task_id="ST001")
        self.subtask.task_type = "Subtask"
        self.subtask.parent_task_id = "T001"
        self.project.add_task(self.subtask)

    def test_a_phase_cannot_be_pasted_into_its_own_task(self):
        """Its parent is left alone rather than pointing inside itself."""
        self.service.cut(["P001"])
        self.service.paste("T001")

        self.assertIsNone(self.phase.parent_task_id)

    def test_a_phase_cannot_be_pasted_into_a_deeper_descendant(self):
        """A grandchild is no more of a home for it than a child."""
        self.service.cut(["P001"])
        self.service.paste("ST001")

        self.assertIsNone(self.phase.parent_task_id)

    def test_a_task_cannot_be_pasted_into_itself(self):
        """Its own row is not somewhere to put it."""
        self.service.cut(["T001"])
        self.service.paste("T001")

        self.assertEqual(self.task.parent_task_id, "P001")

    def test_it_still_moves_somewhere_that_is_not_beneath_it(self):
        """The guard refuses a loop, not every paste."""
        other = Task.create_task(name="Phase 2", start_date=datetime(2024, 1, 1),
                                 end_date=datetime(2024, 1, 5), task_id="P002")
        other.task_type = "Phase"
        self.project.add_task(other)

        self.service.cut(["T001"])
        self.service.paste("P002")

        self.assertEqual(self.task.parent_task_id, other.id)


class TestClipboardWithSpecialTaskTypes(unittest.TestCase):
    """Test cases for clipboard operations with special task types."""

    def setUp(self):
        """Set up test fixtures with various task types."""
        self.project = Project(name="Test Project")
        self.service = ClipboardService(self.project)
        
        today = datetime(2024, 1, 1)
        
        # Create various task types
        self.task = Task.create_task(
            name="Regular Task",
            start_date=today,
            end_date=today + timedelta(days=5),
            task_id="T001"
        )
        
        self.phase = Task.create_task(
            name="Phase",
            start_date=today,
            end_date=today + timedelta(days=20),
            task_id="P001"
        )
        self.phase.task_type = "Phase"
        
        self.deliverable = Task.create_task(
            name="Deliverable",
            start_date=today,
            end_date=today + timedelta(days=15),
            task_id="D001"
        )
        self.deliverable.task_type = "Deliverable"
        
        self.subtask = Task.create_task(
            name="Subtask",
            start_date=today,
            end_date=today + timedelta(days=2),
            task_id="ST001"
        )
        self.subtask.task_type = "Subtask"
        
        self.milestone = Task.create_milestone(
            name="Milestone",
            date=today + timedelta(days=10),
            task_id="M001"
        )
        
        for task in [self.task, self.phase, self.deliverable, self.subtask, self.milestone]:
            self.project.add_task(task)

    def test_copy_phase(self):
        """Test copying a phase task."""
        self.service.copy(["P001"])
        
        self.assertFalse(self.service.is_clipboard_empty())
        self.assertEqual(self.service.active_payload.items[0].type, "phase")

    def test_copy_deliverable(self):
        """Test copying a deliverable task."""
        self.service.copy(["D001"])
        
        self.assertEqual(self.service.active_payload.items[0].type, "deliverable")

    def test_copy_subtask(self):
        """Test copying a subtask."""
        self.service.copy(["ST001"])
        
        self.assertEqual(self.service.active_payload.items[0].type, "subtask")

    def test_copy_milestone(self):
        """Test copying a milestone."""
        self.service.copy(["M001"])
        
        self.assertEqual(self.service.active_payload.items[0].type, "milestone")

    def test_container_types_can_accept_children(self):
        """Test that Phase, Deliverable, Task can accept children."""
        self.assertTrue(self.service._can_accept_types("P001", ["task"]))
        self.assertTrue(self.service._can_accept_types("D001", ["task"]))
        self.assertTrue(self.service._can_accept_types("T001", ["task"]))

    def test_leaf_types_cannot_accept_children(self):
        """Test that Subtask and Milestone cannot accept children."""
        self.assertFalse(self.service._can_accept_types("ST001", ["task"]))
        self.assertFalse(self.service._can_accept_types("M001", ["task"]))

    def test_paste_task_into_phase(self):
        """Test pasting a task into a phase."""
        self.service.copy(["T001"])
        
        initial_count = len(self.project.tasks)
        pasted = self.service.paste("P001")

        # The copy reads inside the phase, so it is no longer the last row
        new_task = self.project.get_task_by_id(pasted[0])
        self.assertEqual(new_task.parent_task_id, self.phase.id)
        self.assertEqual(len(self.project.tasks), initial_count + 1)


class TestClipboardEdgeCases(unittest.TestCase):
    """Test edge cases for clipboard operations."""

    def setUp(self):
        """Set up test fixtures."""
        self.project = Project(name="Test Project")
        self.service = ClipboardService(self.project)
        
        today = datetime(2024, 1, 1)
        self.task = Task.create_task(
            name="Task 1",
            start_date=today,
            end_date=today + timedelta(days=5),
            task_id="001"
        )
        self.project.add_task(self.task)

    def test_copy_with_none_selected_ids(self):
        """Test copy with None selected_ids."""
        self.service.copy(None)
        
        # Should handle gracefully
        self.assertTrue(self.service.is_clipboard_empty())

    def test_cut_with_none_selected_ids(self):
        """Test cut with None selected_ids."""
        self.service.cut(None)
        
        # Should handle gracefully
        self.assertTrue(self.service.is_clipboard_empty())

    def test_paste_with_none_container(self):
        """Test paste with None container_id."""
        self.service.copy(["001"])
        self.service.paste(None)
        
        # Should paste to root level
        self.assertEqual(len(self.project.tasks), 2)
        new_task = self.project.tasks[-1]
        self.assertIsNone(new_task.parent_task_id)

    def test_clear_cut_state(self):
        """Test clearing cut state."""
        self.service.cut(["001"])
        self.assertEqual(self.service.cut_item_ids, {"001"})
        
        self.service.clear_cut_state()
        self.assertEqual(self.service.cut_item_ids, set())

    def test_paste_cut_clears_clipboard(self):
        """Test that pasting cut items clears the clipboard."""
        self.service.cut(["001"])
        self.assertFalse(self.service.is_clipboard_empty())
        
        self.service.paste(None)
        self.assertTrue(self.service.is_clipboard_empty())

    def test_multiple_operations_in_sequence(self):
        """Test multiple clipboard operations in sequence."""
        # Copy
        self.service.copy(["001"])
        self.assertEqual(self.service.active_payload.operation, "copy")
        
        # Cut (should replace copy)
        self.service.cut(["001"])
        self.assertEqual(self.service.active_payload.operation, "cut")
        
        # Copy again (should replace cut)
        self.service.copy(["001"])
        self.assertEqual(self.service.active_payload.operation, "copy")
        
        # Paste
        self.service.paste(None)
        
        # Clear
        self.service.clear_clipboard()
        self.assertTrue(self.service.is_clipboard_empty())


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestTheSelectionReachesTheClipboard(unittest.TestCase):
    """
    What the task list says is selected is what gets copied.

    WHY THESE EXIST:
    ================
    The toolbar and the menu bar ask the task list for
    get_selected_task_ids behind a hasattr. Nothing answered to that name,
    so the test was false every time and Copy, Cut and Paste quietly did
    nothing at all - no error, no entry in the log, no clipboard.
    """

    def setUp(self):
        """A task list over a small plan."""
        import customtkinter as ctk
        from gantt_app.views.task_list import DragDropTaskList

        self.root = ctk.CTk()
        self.root.withdraw()

        self.project = Project(name="Test Project")
        today = datetime(2024, 1, 1)
        for number in ("001", "002", "003"):
            self.project.add_task(Task.create_task(
                name=f"Task {number}", start_date=today,
                end_date=today + timedelta(days=2), task_id=number))

        self.task_list = DragDropTaskList(self.root, self.project)

    def tearDown(self):
        """Tear the root window down."""
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_the_task_list_answers_to_the_name_the_toolbar_uses(self):
        """The hasattr the toolbar guards with has something behind it."""
        self.assertTrue(hasattr(self.task_list, 'get_selected_task_ids'))

    def test_nothing_selected_is_an_empty_list(self):
        """Not None, and not an exception."""
        self.assertEqual(self.task_list.get_selected_task_ids(), [])

    def test_one_selected_row_is_reported(self):
        """The row the user picked out is the one handed on."""
        self.task_list.tree.selection_set("002")

        self.assertEqual(self.task_list.get_selected_task_ids(), ["002"])

    def test_several_selected_rows_are_all_reported(self):
        """Copy acts on every row picked out, not just the first."""
        self.task_list.tree.selection_set("001", "003")

        self.assertEqual(sorted(self.task_list.get_selected_task_ids()),
                         ["001", "003"])

    def test_a_row_whose_task_has_gone_is_left_out(self):
        """A stale selection is not handed on to be looked up and missed."""
        self.task_list.tree.selection_set("002")
        self.project.remove_task("002")

        self.assertEqual(self.task_list.get_selected_task_ids(), [])


class TestWhereAPasteLands(unittest.TestCase):
    """
    A paste takes the place of the row the cursor is on.

    WHY THESE EXIST:
    ================
    A tester copied a task, selected the row below it and pressed paste. The
    copy arrived indented underneath that row as a sub-task, which is not
    what he had asked for and not what the reference tool does. Three routes
    into a paste - the keyboard, the toolbar and the right-click menu - each
    worked out the destination for themselves, and all three of them read a
    selected row as "paste into this" rather than "paste here".

    See ClipboardService.resolve_target, which is now the only thing that
    answers the question.
    """

    def setUp(self):
        """The plan from the tester's screenshots."""
        self.project = Project(name="Plan")
        self.service = ClipboardService(self.project)

        base = datetime(2026, 8, 19)
        rows = [
            ("001", "Elokeszites", "Task", None),
            ("002", "Kovetelmenyek", "Subtask", "001"),
            ("003", "Design Phase", "Task", None),
            ("004", "UI Mockups", "Subtask", "003"),
            ("005", "Implementation", "Task", None),
            ("006", "Design Review", "Milestone", None),
            ("007", "Testing", "Task", None),
            ("008", "Deployment", "Task", None),
        ]
        for task_id, name, task_type, parent in rows:
            self.project.add_task(Task(
                id=task_id, name=name, start_date=base, end_date=base,
                task_type=task_type, parent_task_id=parent))

    def names(self):
        """Every row by name, in the order the list reads."""
        return [task.name for task in self.project.tasks]

    def test_a_copy_lands_beside_the_row_not_inside_it(self):
        """The fault the tester hit: the copy arrived as a sub-task."""
        self.service.copy(["007"])

        pasted = self.service.paste_at("007")

        self.assertIsNone(
            self.project.get_task_by_id(pasted[0]).parent_task_id)

    def test_a_copy_takes_the_place_of_the_row_it_was_pasted_at(self):
        """As the reference tool does: the row it lands on moves down."""
        self.service.copy(["007"])

        pasted = self.service.paste_at("007")

        self.assertEqual(self.names()[6:], ["Testing", "Testing",
                                            "Deployment"])
        self.assertEqual(self.project.display_id(pasted[0]), "007")

    def test_the_numbering_stays_a_sequence(self):
        """
        The tester's other requirement: the rows are renumbered.

        The number beside a row is where it sits, worked out rather than
        stored - see Project.display_ids - so a paste renumbers the plan by
        putting the row somewhere, and nothing is rewritten to do it.
        """
        self.service.copy(["007"])
        self.service.paste_at("007")

        self.assertEqual(
            [self.project.display_id(task.id) for task in self.project.tasks],
            ["001", "002", "003", "004", "005", "006", "007", "008", "009"])

    def test_a_paste_at_a_subtask_stays_at_that_level(self):
        """Beside the sub-task, under the same task - not at the top."""
        self.service.copy(["002"])

        pasted = self.service.paste_at("004")

        parent = self.project.get_task_by_id(pasted[0]).parent_task_id
        self.assertEqual(self.project.get_task_by_id(parent).name,
                         "Design Phase")

    def test_pasting_inside_is_a_separate_answer(self):
        """What the shortcut used to do is still available, by asking."""
        self.service.copy(["005"])

        pasted = self.service.paste_at("007", inside=True)

        self.assertEqual(
            self.project.get_task_by_id(pasted[0]).parent_task_id, "007")

    def test_a_paste_with_nothing_selected_is_refused(self):
        """
        Rather than appended at the end of the plan.

        Which is what it used to do, putting the row somewhere the user was
        not looking and had not pointed at.
        """
        self.service.copy(["007"])

        self.assertEqual(self.service.paste_at(None), [])
        self.assertEqual(len(self.project.tasks), 8)

    def test_a_paste_into_an_empty_plan_needs_no_row(self):
        """The one place where the end and the beginning are the same."""
        self.service.copy(["007"])
        self.project.tasks = []

        self.assertEqual(len(self.service.paste_at(None)), 1)

    def test_several_rows_keep_the_order_they_were_copied_in(self):
        """Not reversed by each one taking the same place in turn."""
        self.service.copy(["005", "006"])

        self.service.paste_at("001")

        self.assertEqual(self.names()[:2], ["Implementation",
                                            "Design Review"])

    def test_a_cut_lands_the_same_way_a_copy_does(self):
        """One rule for both; the tester found cut no better than copy."""
        self.service.cut(["008"])

        self.service.paste_at("005")

        self.assertEqual(self.names()[4], "Deployment")
        self.assertIsNone(self.project.get_task_by_id("005").parent_task_id)


class TestAPasteIsOneUndoStep(unittest.TestCase):
    """
    Undo takes back the paste, and nothing else.

    WHY THESE EXIST:
    ================
    A paste reached the project directly and was never recorded, so the
    history did not know it had happened. The tester pressed undo to take
    back a paste and it deleted a phase he had created earlier - the last
    thing the history did know about - while the pasted row stayed.
    """

    def setUp(self):
        """Two tasks, then a phase created through the history."""
        from gantt_app.utils.undoredo import (
            UndoRedoManager, ProjectStateTracker,
        )

        self.project = Project(name="Plan")
        base = datetime(2026, 8, 19)
        for task_id, name in (("001", "Testing"), ("002", "Deployment")):
            self.project.add_task(Task(id=task_id, name=name,
                                       start_date=base, end_date=base,
                                       task_type="Task"))

        self.manager = UndoRedoManager()
        self.tracker = ProjectStateTracker(self.project, self.manager)
        self.service = ClipboardService(self.project)

        self.tracker.add_task(Task(id="003", name="Phase1", start_date=base,
                                   end_date=base, task_type="Phase"))
        self.before = [(t.id, t.name) for t in self.project.tasks]

    def rows(self):
        """Every row as (number, name)."""
        return [(task.id, task.name) for task in self.project.tasks]

    def paste(self):
        """A paste recorded the way the task list records it."""
        pasted = []

        def apply():
            """The paste itself."""
            pasted.extend(self.service.paste_at("001"))
            return bool(pasted)

        self.tracker.run_as_command(apply, "Paste Tasks")
        return pasted

    def test_undo_takes_back_the_paste(self):
        """Not the action before it."""
        self.service.copy(["001"])
        self.paste()

        self.manager.undo()

        self.assertEqual(self.rows(), self.before)

    def test_the_phase_created_before_it_survives(self):
        """The row the tester lost."""
        self.service.copy(["001"])
        self.paste()

        self.manager.undo()

        self.assertIn("Phase1", [name for _id, name in self.rows()])

    def test_the_numbering_comes_back_with_the_rows(self):
        """The numbers follow the rows, because they are the rows' places."""
        self.service.copy(["001"])
        self.paste()
        self.assertEqual(
            [self.project.display_id(task.id) for task in self.project.tasks],
            ["001", "002", "003", "004"])

        self.manager.undo()

        self.assertEqual(self.rows(), self.before)
        self.assertEqual(
            [self.project.display_id(task.id) for task in self.project.tasks],
            ["001", "002", "003"])

    def test_redo_puts_it_back(self):
        """And undo takes it away again."""
        self.service.copy(["001"])
        self.paste()
        self.manager.undo()

        self.manager.redo()
        self.assertEqual(len(self.project.tasks), 4)

        self.manager.undo()
        self.assertEqual(self.rows(), self.before)

    def test_a_refused_paste_leaves_no_entry_behind(self):
        """Undo should not have to be pressed twice for nothing."""
        self.service.copy(["001"])
        pasted = []

        def apply():
            """A paste with nowhere to go."""
            pasted.extend(self.service.paste_at(None))
            return bool(pasted)

        self.tracker.run_as_command(apply, "Paste Tasks")

        self.manager.undo()

        # The phase, not the paste, is what the one entry holds
        self.assertNotIn("Phase1", [name for _id, name in self.rows()])


class TestWhatReachesTheDesktopClipboard(unittest.TestCase):
    """
    What is copied can be written out as text.

    WHY THESE EXIST:
    ================
    The payload was built straight from the task's attributes, so it carried
    a TaskStyle object - which cannot be written as JSON. Writing to the
    desktop clipboard raised for every task that had one, which is every
    task. The failure was caught and logged, so copying went on working
    inside the application while nothing it copied ever left it.
    """

    def setUp(self):
        """One formatted task."""
        from gantt_app.taskstyle import TaskStyle

        self.project = Project(name="Plan")
        self.service = ClipboardService(self.project)
        base = datetime(2026, 8, 19)
        task = Task(id="001", name="Testing", start_date=base, end_date=base,
                    task_type="Task")
        task.style = TaskStyle(bold=True)
        self.project.add_task(task)

    def test_the_payload_can_be_written_as_json(self):
        """Which is what the desktop clipboard is given."""
        import json

        self.service.copy(["001"])

        json.dumps(self.service._clipboard_text())

    def test_the_formatting_comes_back_on_the_copy(self):
        """Not lost on the way through the clipboard."""
        self.service.copy(["001"])

        pasted = self.service.paste_at("001")

        self.assertTrue(self.project.get_task_by_id(pasted[0]).style.bold)


class TestTheClipboardShortcuts(unittest.TestCase):
    """
    Cmd on a Mac, Ctrl everywhere else, in both letter cases.

    WHY THESE EXIST:
    ================
    These three were the only shortcuts in the application written out by
    hand instead of going through gantt_app.shortcuts. They bound Control as
    well as Command on macOS, where Control+C is not copy, and they bound
    only the lower-case letter - so all three stopped working with caps lock
    on.
    """

    class FakeWidget:
        """Records what is bound to it."""

        def __init__(self):
            self.bindings = {}

        def bind(self, sequence, handler, add=None):
            """Remember the sequence, as Tk would."""
            self.bindings.setdefault(sequence, []).append(handler)

        def focus_get(self):
            """Nothing has the focus, so nothing swallows the keystroke."""
            return None

    def bind(self):
        """Bind the clipboard shortcuts to a widget that records them."""
        from gantt_app.utils.copypastecut import setup_keyboard_bindings

        self.called = []
        widget = self.FakeWidget()
        setup_keyboard_bindings(
            widget,
            lambda: self.called.append('copy'),
            lambda: self.called.append('cut'),
            lambda: self.called.append('paste'),
        )
        return widget

    def test_it_binds_this_platform_s_modifier(self):
        """Command on a Mac, Control elsewhere."""
        from gantt_app.shortcuts import sequences

        widget = self.bind()

        for key in ('c', 'x', 'v'):
            for sequence in sequences(key):
                self.assertIn(sequence, widget.bindings)

    def test_it_binds_both_letter_cases(self):
        """A shortcut that stops working with caps lock on is a fault."""
        from gantt_app.shortcuts import MODIFIER

        widget = self.bind()

        self.assertIn(f"<{MODIFIER}-C>", widget.bindings)
        self.assertIn(f"<{MODIFIER}-X>", widget.bindings)
        self.assertIn(f"<{MODIFIER}-V>", widget.bindings)

    def test_it_does_not_bind_control_on_a_mac(self):
        """Control+C is not copy on macOS and never has been."""
        from gantt_app.shortcuts import IS_MACOS

        widget = self.bind()

        if IS_MACOS:
            self.assertNotIn("<Control-c>", widget.bindings)
        else:
            self.assertIn("<Control-c>", widget.bindings)

    def test_the_handler_consumes_the_keystroke(self):
        """
        So a menu accelerator cannot handle the same press again.

        A paste handled twice inserts the rows twice.
        """
        from gantt_app.shortcuts import sequences

        widget = self.bind()
        handler = widget.bindings[sequences('v')[0]][0]

        self.assertEqual(handler(None), "break")
        self.assertEqual(self.called, ['paste'])

    def test_a_text_field_keeps_its_own_clipboard(self):
        """Editing a cell means copying text, not rows."""
        from gantt_app.shortcuts import sequences

        widget = self.bind()

        class Entry:
            """Something Tk would report as an entry."""

            def winfo_class(self):
                """As ttk.Entry reports itself."""
                return 'TEntry'

        widget.focus_get = lambda: Entry()
        handler = widget.bindings[sequences('c')[0]][0]

        self.assertIsNone(handler(None))
        self.assertEqual(self.called, [])


if __name__ == '__main__':
    unittest.main()
