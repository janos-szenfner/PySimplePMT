"""
Tests for the Undo/Redo functionality.
"""

import unittest
from datetime import datetime, timedelta
import copy

from gantt_app.models import Project, Task
from gantt_app.utils.undoredo import (
    UndoRedoManager,
    AddTaskCommand,
    RemoveTaskCommand,
    UpdateTaskCommand,
    UpdateProjectNameCommand,
    CompoundCommand,
    ProjectStateTracker,
    create_add_task_command,
    create_remove_task_command,
    create_update_task_command,
    create_update_project_name_command,
    create_compound_command
)


class TestCommandPattern(unittest.TestCase):
    """Tests for the command pattern implementation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.project = Project(name="Test Project")
        self.start_date = datetime(2024, 1, 1)
    
    def test_add_task_command(self):
        """Test AddTaskCommand execute and undo."""
        task = Task.create_task("Test Task", self.start_date, self.start_date + timedelta(days=5))
        command = AddTaskCommand(project=self.project, task=task)
        
        # Execute
        self.assertTrue(command.execute())
        self.assertEqual(len(self.project.tasks), 1)
        self.assertEqual(self.project.tasks[0].name, "Test Task")
        
        # Undo
        self.assertTrue(command.undo())
        self.assertEqual(len(self.project.tasks), 0)
    
    def test_remove_task_command(self):
        """Test RemoveTaskCommand execute and undo."""
        task = Task.create_task("Test Task", self.start_date, self.start_date + timedelta(days=5))
        self.project.add_task(task)
        
        index = self.project.tasks.index(task)
        command = RemoveTaskCommand(project=self.project, task_id=task.id, task=task, index=index)
        
        # Execute
        self.assertTrue(command.execute())
        self.assertEqual(len(self.project.tasks), 0)
        
        # Undo
        self.assertTrue(command.undo())
        self.assertEqual(len(self.project.tasks), 1)
        self.assertEqual(self.project.tasks[0].name, "Test Task")
    
    def test_update_task_command(self):
        """Test UpdateTaskCommand execute and undo."""
        task = Task.create_task("Original", self.start_date, self.start_date + timedelta(days=5))
        self.project.add_task(task)
        
        # Create updated task
        old_task = copy.copy(task)
        new_task = Task(
            id=task.id,
            name="Updated",
            start_date=task.start_date,
            end_date=task.end_date,
            progress=task.progress,
            dependencies=task.dependencies,
            color=task.color,
            is_milestone=task.is_milestone
        )
        
        command = UpdateTaskCommand(
            project=self.project, 
            task_id=task.id, 
            old_task=old_task, 
            new_task=new_task
        )
        
        # Execute
        self.assertTrue(command.execute())
        self.assertEqual(self.project.tasks[0].name, "Updated")
        
        # Undo
        self.assertTrue(command.undo())
        self.assertEqual(self.project.tasks[0].name, "Original")
    
    def test_update_project_name_command(self):
        """Test UpdateProjectNameCommand execute and undo."""
        old_name = self.project.name
        new_name = "New Name"
        
        command = UpdateProjectNameCommand(
            project=self.project,
            old_name=old_name,
            new_name=new_name
        )
        
        # Execute
        self.assertTrue(command.execute())
        self.assertEqual(self.project.name, new_name)
        
        # Undo
        self.assertTrue(command.undo())
        self.assertEqual(self.project.name, old_name)


class TestUndoRedoManager(unittest.TestCase):
    """Tests for the UndoRedoManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.project = Project(name="Test Project")
        self.manager = UndoRedoManager(max_history=10)
        self.manager.set_project(self.project)
        self.start_date = datetime(2024, 1, 1)
    
    def test_execute_add_task(self):
        """Test executing a command via manager."""
        task = Task.create_task("Test Task", self.start_date, self.start_date + timedelta(days=5))
        command = AddTaskCommand(project=self.project, task=task)
        
        self.assertTrue(self.manager.execute(command))
        self.assertEqual(len(self.project.tasks), 1)
        self.assertTrue(self.manager.can_undo())
        self.assertFalse(self.manager.can_redo())
    
    def test_undo_add_task(self):
        """Test undoing a command."""
        task = Task.create_task("Test Task", self.start_date, self.start_date + timedelta(days=5))
        command = AddTaskCommand(project=self.project, task=task)
        
        self.manager.execute(command)
        self.assertTrue(self.manager.undo())
        self.assertEqual(len(self.project.tasks), 0)
        self.assertTrue(self.manager.can_redo())
        self.assertFalse(self.manager.can_undo())
    
    def test_redo_add_task(self):
        """Test redoing a command."""
        task = Task.create_task("Test Task", self.start_date, self.start_date + timedelta(days=5))
        command = AddTaskCommand(project=self.project, task=task)
        
        self.manager.execute(command)
        self.manager.undo()
        self.assertTrue(self.manager.redo())
        self.assertEqual(len(self.project.tasks), 1)
        self.assertTrue(self.manager.can_undo())
        self.assertFalse(self.manager.can_redo())
    
    def test_undo_clears_redo_stack(self):
        """Test that new actions clear the redo stack."""
        task1 = Task.create_task("Task 1", self.start_date, self.start_date + timedelta(days=5))
        task2 = Task.create_task("Task 2", self.start_date + timedelta(days=6), self.start_date + timedelta(days=10))
        
        # Add first task
        self.manager.execute(AddTaskCommand(project=self.project, task=task1))
        # Undo it
        self.manager.undo()
        
        # Now add second task - should clear redo stack
        self.manager.execute(AddTaskCommand(project=self.project, task=task2))
        
        # Redo stack should be empty
        self.assertFalse(self.manager.can_redo())
        # But we should still have one undo
        self.assertTrue(self.manager.can_undo())
    
    def test_max_history_limit(self):
        """Test that max history limit is enforced."""
        manager = UndoRedoManager(max_history=3)
        manager.set_project(self.project)
        
        # Add 5 tasks
        for i in range(5):
            task = Task.create_task(f"Task {i}", self.start_date, self.start_date + timedelta(days=i+1))
            manager.execute(AddTaskCommand(project=self.project, task=task))
        
        # Should only have 3 in undo stack
        self.assertEqual(len(manager.undo_stack), 3)
        # All 5 tasks should still be in the project
        self.assertEqual(len(self.project.tasks), 5)
    
    def test_cannot_undo_when_empty(self):
        """Test that undo returns False when stack is empty."""
        self.assertFalse(self.manager.undo())
    
    def test_cannot_redo_when_empty(self):
        """Test that redo returns False when stack is empty."""
        self.assertFalse(self.manager.redo())
    
    def test_clear(self):
        """Test clearing the undo/redo history."""
        task = Task.create_task("Test Task", self.start_date, self.start_date + timedelta(days=5))
        self.manager.execute(AddTaskCommand(project=self.project, task=task))
        
        self.assertTrue(self.manager.can_undo())
        
        self.manager.clear()
        
        self.assertFalse(self.manager.can_undo())
        self.assertFalse(self.manager.can_redo())
    
    def test_get_undo_description(self):
        """Test getting undo description."""
        task = Task.create_task("Test Task", self.start_date, self.start_date + timedelta(days=5))
        self.manager.execute(AddTaskCommand(project=self.project, task=task))
        
        description = self.manager.get_undo_description()
        self.assertIn("Add Task: Test Task", description)
    
    def test_get_redo_description(self):
        """Test getting redo description."""
        task = Task.create_task("Test Task", self.start_date, self.start_date + timedelta(days=5))
        self.manager.execute(AddTaskCommand(project=self.project, task=task))
        self.manager.undo()
        
        description = self.manager.get_redo_description()
        self.assertIn("Add Task: Test Task", description)


class TestCompoundCommand(unittest.TestCase):
    """Tests for the CompoundCommand class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.project = Project(name="Test Project")
        self.start_date = datetime(2024, 1, 1)
    
    def test_execute_compound_command(self):
        """Test executing a compound command."""
        task1 = Task.create_task("Task 1", self.start_date, self.start_date + timedelta(days=5))
        task2 = Task.create_task("Task 2", self.start_date + timedelta(days=6), self.start_date + timedelta(days=10))
        
        commands = [
            AddTaskCommand(project=self.project, task=task1),
            AddTaskCommand(project=self.project, task=task2)
        ]
        
        compound = CompoundCommand(commands=commands, name="Add Two Tasks")
        
        self.assertTrue(compound.execute())
        self.assertEqual(len(self.project.tasks), 2)
    
    def test_undo_compound_command(self):
        """Test undoing a compound command."""
        task1 = Task.create_task("Task 1", self.start_date, self.start_date + timedelta(days=5))
        task2 = Task.create_task("Task 2", self.start_date + timedelta(days=6), self.start_date + timedelta(days=10))
        
        commands = [
            AddTaskCommand(project=self.project, task=task1),
            AddTaskCommand(project=self.project, task=task2)
        ]
        
        compound = CompoundCommand(commands=commands, name="Add Two Tasks")
        
        compound.execute()
        self.assertTrue(compound.undo())
        self.assertEqual(len(self.project.tasks), 0)


class TestFactoryFunctions(unittest.TestCase):
    """Tests for the factory functions."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.project = Project(name="Test Project")
        self.start_date = datetime(2024, 1, 1)
    
    def test_create_add_task_command(self):
        """Test creating an AddTaskCommand via factory."""
        task = Task.create_task("Test Task", self.start_date, self.start_date + timedelta(days=5))
        command = create_add_task_command(self.project, task)
        
        self.assertIsInstance(command, AddTaskCommand)
        self.assertEqual(command.project, self.project)
        self.assertEqual(command.task, task)
    
    def test_create_remove_task_command(self):
        """Test creating a RemoveTaskCommand via factory."""
        task = Task.create_task("Test Task", self.start_date, self.start_date + timedelta(days=5))
        self.project.add_task(task)
        
        index = self.project.tasks.index(task)
        command = create_remove_task_command(self.project, task.id, task, index)
        
        self.assertIsInstance(command, RemoveTaskCommand)
    
    def test_create_update_task_command(self):
        """Test creating an UpdateTaskCommand via factory."""
        task = Task.create_task("Original", self.start_date, self.start_date + timedelta(days=5))
        self.project.add_task(task)
        
        old_task = copy.copy(task)
        new_task = Task(
            id=task.id,
            name="Updated",
            start_date=task.start_date,
            end_date=task.end_date,
            progress=task.progress,
            dependencies=task.dependencies,
            color=task.color,
            is_milestone=task.is_milestone
        )
        
        command = create_update_task_command(self.project, task.id, old_task, new_task)
        
        self.assertIsInstance(command, UpdateTaskCommand)
    
    def test_create_update_project_name_command(self):
        """Test creating an UpdateProjectNameCommand via factory."""
        command = create_update_project_name_command(self.project, "Old", "New")
        
        self.assertIsInstance(command, UpdateProjectNameCommand)
    
    def test_create_compound_command(self):
        """Test creating a CompoundCommand via factory."""
        commands = []
        command = create_compound_command(commands, "Test")
        
        self.assertIsInstance(command, CompoundCommand)


class TestProjectStateTracker(unittest.TestCase):
    """Tests for the ProjectStateTracker helper class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.project = Project(name="Test Project")
        self.manager = UndoRedoManager()
        self.tracker = ProjectStateTracker(self.project, self.manager)
        self.start_date = datetime(2024, 1, 1)
    
    def test_add_task(self):
        """Test adding a task via tracker."""
        task = Task.create_task("Test Task", self.start_date, self.start_date + timedelta(days=5))
        
        self.assertTrue(self.tracker.add_task(task))
        self.assertEqual(len(self.project.tasks), 1)
        self.assertTrue(self.tracker.can_undo())
    
    def test_remove_task(self):
        """Test removing a task via tracker."""
        task = Task.create_task("Test Task", self.start_date, self.start_date + timedelta(days=5))
        self.project.add_task(task)
        
        self.assertTrue(self.tracker.remove_task(task.id))
        self.assertEqual(len(self.project.tasks), 0)
        self.assertTrue(self.tracker.can_undo())
    
    def test_update_task(self):
        """Test updating a task via tracker."""
        task = Task.create_task("Original", self.start_date, self.start_date + timedelta(days=5))
        self.project.add_task(task)
        
        self.assertTrue(self.tracker.update_task(task.id, name="Updated"))
        self.assertEqual(self.project.tasks[0].name, "Updated")
        self.assertTrue(self.tracker.can_undo())
    
    def test_update_project_name(self):
        """Test updating project name via tracker."""
        self.assertTrue(self.tracker.update_project_name("New Name"))
        self.assertEqual(self.project.name, "New Name")
        self.assertTrue(self.tracker.can_undo())
    
    def test_undo_redo(self):
        """Test undo and redo via tracker."""
        task = Task.create_task("Test Task", self.start_date, self.start_date + timedelta(days=5))
        
        # Add task
        self.tracker.add_task(task)
        self.assertEqual(len(self.project.tasks), 1)
        
        # Undo
        self.assertTrue(self.tracker.undo())
        self.assertEqual(len(self.project.tasks), 0)
        
        # Redo
        self.assertTrue(self.tracker.redo())
        self.assertEqual(len(self.project.tasks), 1)


if __name__ == '__main__':
    unittest.main()