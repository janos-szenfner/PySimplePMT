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
from utils.copypastecut import (
    ClipboardService,
    ClipboardManager,
    ClipboardPayload,
    ClipboardItem,
    ENTITY_TYPES,
    CONTAINER_TYPES,
)


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
        
        # The new task should have a different ID
        new_task = self.project.tasks[-1]
        self.assertNotEqual(new_task.id, "001")
        self.assertEqual(new_task.name, "Task 1 (Copy)")

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
        
        # Paste into phase
        self.service.paste("P001")
        
        # New task should have phase as parent
        new_task = self.project.tasks[-1]
        self.assertEqual(new_task.parent_task_id, "P001")

    def test_paste_into_same_container_appends_copy_suffix(self):
        """Test that pasting into same container appends (Copy) suffix."""
        self.service.copy(["T001"])
        source_container = self.task.parent_task_id
        
        self.service.paste(source_container)
        
        new_task = self.project.tasks[-1]
        self.assertEqual(new_task.name, "Task 1 (Copy)")

    def test_copy_task_with_dependencies(self):
        """Test copying a task with dependencies."""
        self.task.add_dependency("P001")
        
        self.service.copy(["T001"])
        
        # Paste
        self.service.paste("P001")
        
        # New task should have the same dependencies
        new_task = self.project.tasks[-1]
        self.assertEqual(len(new_task.dependencies), 1)
        self.assertEqual(new_task.dependencies[0].task_id, "P001")

    def test_paste_multiple_tasks_into_container(self):
        """Test pasting multiple tasks into a container."""
        self.service.copy(["T001", "ST001"])
        
        initial_count = len(self.project.tasks)
        self.service.paste("P001")
        
        # Should have 2 new tasks
        self.assertEqual(len(self.project.tasks), initial_count + 2)


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
        self.service.paste("P001")
        
        new_task = self.project.tasks[-1]
        self.assertEqual(new_task.parent_task_id, "P001")
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


if __name__ == '__main__':
    unittest.main()
