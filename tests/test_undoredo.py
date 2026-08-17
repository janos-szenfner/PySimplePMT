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


class TestDependencyUndo(unittest.TestCase):
    """
    Undoing a dependency change restores the previous links.

    DEVELOPMENT NOTES:
    ------------------
    The task list's drag-and-drop handlers appended to task.dependencies before
    calling update_task. The tracker snapshots the task as it finds it, so the
    snapshot already held the new link and undo restored the state it was meant
    to be undoing - the dependency simply stayed.

    The shallow copy behind that snapshot is covered too: copy.copy leaves the
    copy sharing the live task's DependencyList, so an in-place mutation after
    the fact would rewrite the undo record.
    """

    def setUp(self):
        """Set up a project with two independent tasks."""
        self.project = Project(name="Test Project")
        start = datetime(2026, 1, 1)
        self.first = Task(id="001", name="First", start_date=start,
                          end_date=start + timedelta(days=2))
        self.second = Task(id="002", name="Second",
                           start_date=start + timedelta(days=3),
                           end_date=start + timedelta(days=5))
        self.project.add_task(self.first)
        self.project.add_task(self.second)

        self.manager = UndoRedoManager()
        self.manager.set_project(self.project)
        self.tracker = ProjectStateTracker(self.project, self.manager)

    def test_undo_removes_an_added_dependency(self):
        """Undo takes a newly linked dependency back off the task."""
        task = self.project.get_task_by_id("002")
        self.tracker.update_task(
            "002", dependencies=list(task.dependencies) + ["001"]
        )
        self.assertEqual(
            self.project.get_task_by_id("002").dependency_ids, ["001"]
        )

        self.assertTrue(self.manager.undo())

        self.assertEqual(self.project.get_task_by_id("002").dependency_ids, [])

    def test_redo_puts_the_dependency_back(self):
        """Redo reapplies the link undo removed."""
        self.tracker.update_task("002", dependencies=["001"])
        self.manager.undo()

        self.assertTrue(self.manager.redo())

        self.assertEqual(
            self.project.get_task_by_id("002").dependency_ids, ["001"]
        )

    def test_undo_snapshot_is_independent_of_the_live_task(self):
        """Mutating the task afterwards does not rewrite the undo record."""
        task = self.project.get_task_by_id("002")
        task.add_dependency("001", "FS", "Hard")

        self.tracker.update_task("002", dependencies=["001"], name="Renamed")

        # The task object the snapshot was taken from is no longer in the
        # project; mutating it must not disturb the recorded history
        task.dependencies.append("999")
        task.dependencies[0].hardness = "Rubber"

        self.assertTrue(self.manager.undo())

        restored = self.project.get_task_by_id("002")
        self.assertEqual(restored.dependency_ids, ["001"])
        self.assertEqual(restored.dependencies[0].hardness, "Hard")


class TestRemoveUndo(unittest.TestCase):
    """
    Undoing a delete restores everything the delete took.

    DEVELOPMENT NOTES:
    ------------------
    Project.remove_task deletes the task's sub-tasks too, and strips the
    removed ID out of every dependency list. Undo re-inserted only the named
    task, so deleting a parent and undoing it destroyed its children and left
    the surviving links broken.
    """

    def setUp(self):
        """A parent with two sub-tasks, and a later task depending on it."""
        self.project = Project(name="Test Project")
        base = datetime(2026, 1, 1)

        self.project.add_task(Task(id="001", name="Parent", start_date=base,
                                   end_date=base + timedelta(days=5)))
        for task_id, name in [("002", "Child A"), ("003", "Child B")]:
            self.project.add_task(Task(
                id=task_id, name=name, start_date=base,
                task_type="Subtask", parent_task_id="001",
            ))

        later = Task(id="004", name="Later",
                     start_date=base + timedelta(days=6),
                     end_date=base + timedelta(days=8))
        later.add_dependency("001", "FS", "Hard")
        self.project.add_task(later)

        self.manager = UndoRedoManager()
        self.manager.set_project(self.project)
        self.tracker = ProjectStateTracker(self.project, self.manager)

    def _ids(self):
        """The project's task IDs in order."""
        return [task.id for task in self.project.tasks]

    def test_deleting_a_parent_takes_its_subtasks(self):
        """The delete itself removes the whole branch."""
        self.assertTrue(self.tracker.remove_task("001"))

        self.assertEqual(self._ids(), ["004"])

    def test_undo_restores_the_subtasks(self):
        """Undo brings the children back, not just the parent."""
        self.tracker.remove_task("001")

        self.assertTrue(self.manager.undo())

        self.assertEqual(self._ids(), ["001", "002", "003", "004"])

    def test_undo_restores_dependencies_on_surviving_tasks(self):
        """A link to the deleted task comes back with it."""
        self.tracker.remove_task("001")
        self.assertEqual(self.project.get_task_by_id("004").dependency_ids, [])

        self.manager.undo()

        self.assertEqual(self.project.get_task_by_id("004").dependency_ids,
                         ["001"])

    def test_undo_restores_the_link_details(self):
        """The restored link keeps its type and hardness."""
        self.tracker.remove_task("001")
        self.manager.undo()

        link = self.project.get_task_by_id("004").get_dependency("001")

        self.assertIsNotNone(link)
        self.assertEqual(link.dep_type, 'FS')
        self.assertEqual(link.hardness, 'Hard')

    def test_redo_deletes_the_branch_again(self):
        """Redo repeats the whole removal."""
        self.tracker.remove_task("001")
        self.manager.undo()

        self.assertTrue(self.manager.redo())

        self.assertEqual(self._ids(), ["004"])
        self.assertEqual(self.project.get_task_by_id("004").dependency_ids, [])

    def test_undo_after_redo_still_restores(self):
        """The snapshot survives a round trip through redo."""
        self.tracker.remove_task("001")
        self.manager.undo()
        self.manager.redo()

        self.assertTrue(self.manager.undo())

        self.assertEqual(self._ids(), ["001", "002", "003", "004"])
        self.assertEqual(self.project.get_task_by_id("004").dependency_ids,
                         ["001"])

    def test_deleting_a_childless_task_is_undoable(self):
        """The simple case still works."""
        self.tracker.remove_task("004")
        self.assertEqual(self._ids(), ["001", "002", "003"])

        self.assertTrue(self.manager.undo())

        self.assertEqual(self._ids(), ["001", "002", "003", "004"])


class TestReorderUndo(unittest.TestCase):
    """Reordering rows is undoable."""

    def setUp(self):
        """Three root tasks in a known order."""
        self.project = Project(name="Test Project")
        base = datetime(2026, 1, 1)
        for task_id, name in [("001", "Alpha"), ("002", "Beta"),
                              ("003", "Gamma")]:
            self.project.add_task(Task(id=task_id, name=name, start_date=base,
                                       end_date=base + timedelta(days=2)))

        self.manager = UndoRedoManager()
        self.manager.set_project(self.project)
        self.tracker = ProjectStateTracker(self.project, self.manager)

    def _ids(self):
        """The project's task IDs in order."""
        return [task.id for task in self.project.tasks]

    def test_undo_restores_the_previous_order(self):
        """Undo puts a moved task back where it was."""
        before = list(self.project.tasks)
        self.project.move_task("003", 'top')
        self.tracker.reorder_tasks(before, list(self.project.tasks))
        self.assertEqual(self._ids(), ["003", "001", "002"])

        self.assertTrue(self.manager.undo())

        self.assertEqual(self._ids(), ["001", "002", "003"])

    def test_redo_reapplies_the_move(self):
        """Redo restores the order undo took away."""
        before = list(self.project.tasks)
        self.project.move_task("003", 'top')
        self.tracker.reorder_tasks(before, list(self.project.tasks))
        self.manager.undo()

        self.assertTrue(self.manager.redo())

        self.assertEqual(self._ids(), ["003", "001", "002"])

    def test_the_recorded_orders_are_independent(self):
        """
        Later moves do not disturb an earlier undo entry.

        The command holds two orderings of the same Task objects, so it has
        to keep its own lists; storing the caller's would let the next move
        rewrite the history behind it.
        """
        before = list(self.project.tasks)
        self.project.move_task("003", 'top')
        after = list(self.project.tasks)
        self.tracker.reorder_tasks(before, after)

        # A second move, recorded the same way
        self.project.move_task("002", 'top')
        self.tracker.reorder_tasks(after, list(self.project.tasks))
        self.assertEqual(self._ids(), ["002", "003", "001"])

        self.assertTrue(self.manager.undo())
        self.assertEqual(self._ids(), ["003", "001", "002"])

        self.assertTrue(self.manager.undo())
        self.assertEqual(self._ids(), ["001", "002", "003"])


if __name__ == '__main__':
    unittest.main()