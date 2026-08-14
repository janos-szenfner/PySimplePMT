"""
Undo/Redo Functionality for the Gantt Project Management Tool.

This module provides a command pattern implementation for undo and redo operations.
It allows users to revert changes made to the project and reapply them.

WHY THIS MODULE EXISTS:
======================
The Gantt Project Management Tool needed a way to allow users to undo and redo
their actions. This is a common requirement for any application that allows
users to make changes to data. By implementing this as a separate module:

1. **Separation of Concerns**: The main application logic doesn't need to 
   handle the complexity of tracking changes and managing undo/redo stacks.

2. **Reusability**: The undo/redo functionality can be used with any type of
   command, not just project modifications.

3. **Testability**: The undo/redo logic can be tested independently of the
   GUI and project models.

4. **Extensibility**: New command types can be added without modifying the
   core undo/redo logic.

5. **Consistency**: Provides a consistent way to implement undoable actions
   across the entire application.

DESIGN DECISIONS:
================
1. **Command Pattern**: This module implements the Command pattern, where each
   action is encapsulated as a command object that knows how to execute and
   undo itself.

2. **Two Stacks**: Uses two stacks - one for undo (past actions) and one for
   redo (future actions that were undone).

3. **Memento Pattern**: Each command stores the state needed to undo its
   action, acting as a memento of the previous state.

4. **Project Integration**: Works with the Project model to track changes to
   tasks, project name, and other project attributes.

5. **Max History**: Limits the number of undo levels to prevent excessive
   memory usage (default: 100 levels).

RELATIONSHIP WITH OTHER MODULES:
=================================
This module is used by:
- main.py: To integrate undo/redo with the main application
- toolbar.py: To provide UI buttons for undo/redo actions

It works with:
- models.py: Uses Project and Task objects
- It doesn't depend on any specific UI framework, making it reusable

USAGE:
======
from gantt_app.utils.undoredo import UndoRedoManager, ProjectCommand

# Create manager
manager = UndoRedoManager(max_history=50)

# Execute a command (will be added to undo stack)
command = AddTaskCommand(project, task)
manager.execute(command)

# Undo the last action
manager.undo()

# Redo the last undone action
manager.redo()

# Check if undo/redo is available
can_undo = manager.can_undo()
can_redo = manager.can_redo()
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, List, Callable
import copy

from gantt_app.models import Project, Task


@dataclass
class Command:
    """
    Base class for all undoable commands.
    
    The Command pattern encapsulates an action and its reverse (undo) action.
    Each command knows how to:
    - execute(): Perform the action
    - undo(): Reverse the action
    
    CONCRETE COMMANDS:
    ------------------
    Subclasses must implement:
    - execute(): Perform the action
    - undo(): Reverse the action
    
    DEVELOPMENT NOTES:
    ------------------
    This is an abstract base class. All concrete commands should inherit from
    this and implement the execute() and undo() methods.
    
    The command should store all the information it needs to both execute and
    undo its action. This typically includes:
    - The target object (e.g., Project, Task)
    - The old state (for undo)
    - The new state or action parameters (for execute)
    """
    # Name of the command for display purposes
    name: str = field(default="Command", init=False)
    
    def execute(self) -> bool:
        """
        Execute the command.
        
        RETURNS:
        --------
        bool
            True if execution was successful, False otherwise
        """
        raise NotImplementedError("Subclasses must implement execute()")
    
    def undo(self) -> bool:
        """
        Undo the command (reverse the action).
        
        RETURNS:
        --------
        bool
            True if undo was successful, False otherwise
        """
        raise NotImplementedError("Subclasses must implement undo()")


@dataclass
class AddTaskCommand(Command):
    """
    Command to add a task to a project.
    
    This command adds a task to the project's task list. When undone, it
    removes the task from the project.
    
    PARAMETERS:
    -----------
    project : Project
        The project to add the task to
    task : Task
        The task to add
    
    DEVELOPMENT NOTES:
    ------------------
    When the command is executed, it adds the task to the project.
    When undone, it removes the task by its ID.
    
    The task object is stored so it can be re-added if the command is redone.
    """
    project: Project
    task: Task
    name: str = field(default="", init=False)
    
    def __post_init__(self):
        self.name = f"Add Task: {self.task.name}"
    
    def execute(self) -> bool:
        """Add the task to the project."""
        # Store the current state in case we need to restore it
        # (e.g., if the task ID already exists)
        if self.task.id in [t.id for t in self.project.tasks]:
            return False
        
        self.project.add_task(self.task)
        return True
    
    def undo(self) -> bool:
        """Remove the task from the project."""
        return self.project.remove_task(self.task.id)


@dataclass
class RemoveTaskCommand(Command):
    """
    Command to remove a task from a project.
    
    This command removes a task from the project. When undone, it re-adds
    the task at its original position.
    
    PARAMETERS:
    -----------
    project : Project
        The project to remove the task from
    task_id : str
        The ID of the task to remove
    task : Task
        The actual task object (stored for redo)
    index : int
        The original index of the task in the project (for redo)
    
    DEVELOPMENT NOTES:
    ------------------
    Undo restores the whole task list rather than re-inserting the one task
    at its index, because removing a task does more than drop it: Project's
    remove_task also deletes every sub-task beneath it, and strips the
    removed ID out of the dependencies of everything left. Putting back only
    the named task lost the sub-tasks for good and left the surviving links
    broken, so deleting a parent and undoing it destroyed its children.

    The dependencies are snapshotted separately because they are rewritten in
    place on tasks that survive the removal - those Task objects are the same
    ones the restored list holds, so the list alone does not carry them.

    The snapshot is taken in execute rather than at construction so redo goes
    through exactly the same path as the original removal.
    """
    project: Project
    task_id: str
    task: Task
    index: int
    name: str = field(default="", init=False)
    _previous_tasks: Optional[List[Task]] = field(default=None, init=False,
                                                  repr=False)
    _previous_dependencies: Optional[Dict[str, list]] = field(
        default=None, init=False, repr=False)

    def __post_init__(self):
        self.name = f"Remove Task: {self.task.name}"

    def execute(self) -> bool:
        """Remove the task, remembering enough to put everything back."""
        self._previous_tasks = list(self.project.tasks)
        self._previous_dependencies = {
            task.id: [copy.copy(link) for link in task.dependencies]
            for task in self.project.tasks
        }
        return self.project.remove_task(self.task_id)

    def undo(self) -> bool:
        """Restore the task list as it was before the removal."""
        if self._previous_tasks is None:
            # Never executed; restore what little is known
            self.project.tasks.insert(self.index, self.task)
            self.project._update_dates()
            return True

        self.project.tasks = list(self._previous_tasks)
        for task in self.project.tasks:
            links = self._previous_dependencies.get(task.id)
            if links is not None:
                task.dependencies = [copy.copy(link) for link in links]

        self.project._update_dates()
        return True


@dataclass
class UpdateTaskCommand(Command):
    """
    Command to update a task's properties.
    
    This command updates one or more properties of a task. When undone, it
    restores the original property values.
    
    PARAMETERS:
    -----------
    project : Project
        The project containing the task
    task_id : str
        The ID of the task to update
    old_task : Task
        The task with its original properties (for undo)
    new_task : Task
        The task with its new properties (for execute)
    
    DEVELOPMENT NOTES:
    ------------------
    This command stores both the old and new versions of the task.
    When executed, it replaces the old task with the new one.
    When undone, it replaces the new task with the old one.
    
    Note: The task IDs must match for this to work correctly.
    """
    project: Project
    task_id: str
    old_task: Task
    new_task: Task
    name: str = field(default="", init=False)
    
    def __post_init__(self):
        self.name = f"Update Task: {self.old_task.name}"
    
    def execute(self) -> bool:
        """Update the task with new properties."""
        # Find and replace the task
        for i, task in enumerate(self.project.tasks):
            if task.id == self.task_id:
                self.project.tasks[i] = self.new_task
                self.project._update_dates()
                return True
        return False
    
    def undo(self) -> bool:
        """Restore the task to its original properties."""
        for i, task in enumerate(self.project.tasks):
            if task.id == self.task_id:
                self.project.tasks[i] = self.old_task
                self.project._update_dates()
                return True
        return False


@dataclass
class UpdateProjectNameCommand(Command):
    """
    Command to update the project name.
    
    This command changes the project's name. When undone, it restores
    the original name.
    
    PARAMETERS:
    -----------
    project : Project
        The project to update
    old_name : str
        The original project name (for undo)
    new_name : str
        The new project name (for execute)
    
    DEVELOPMENT NOTES:
    ------------------
    This is a simple command that just swaps the project name back and forth.
    The undo operation is straightforward since we're just changing a string.
    """
    project: Project
    old_name: str
    new_name: str
    name: str = field(default="", init=False)
    
    def __post_init__(self):
        self.name = f"Update Project Name: {self.new_name}"
    
    def execute(self) -> bool:
        """Set the project name to the new name."""
        self.project.name = self.new_name
        return True

    def undo(self) -> bool:
        """Restore the project name to the old name."""
        self.project.name = self.old_name
        return True


@dataclass
class RestructureTasksCommand(Command):
    """
    Command to change where tasks sit in the hierarchy.

    PARAMETERS:
    -----------
    project : Project
        The project whose structure changed.
    old_snapshot : tuple
        Project.structure_snapshot() taken before the change.
    new_snapshot : tuple
        The same, taken after it.
    label : str
        What to call the change in the undo history.

    DEVELOPMENT NOTES:
    ------------------
    Indenting rewrites parent_task_id and task_type on the Task objects
    themselves, so ReorderTasksCommand cannot undo it: both of its orderings
    hold the same objects, and restoring one puts the list back while leaving
    every task's parent where the indent left it.
    """
    project: Project
    old_snapshot: tuple
    new_snapshot: tuple
    label: str = "Restructure Tasks"
    name: str = field(default="", init=False)

    def __post_init__(self):
        self.name = self.label

    def execute(self) -> bool:
        """Apply the new structure."""
        self.project.restore_structure(self.new_snapshot)
        return True

    def undo(self) -> bool:
        """Restore the previous structure."""
        self.project.restore_structure(self.old_snapshot)
        return True


@dataclass
class ReorderTasksCommand(Command):
    """
    Command to change the order of the tasks in a project.

    PARAMETERS:
    -----------
    project : Project
        The project whose task order changed.
    old_order : List[Task]
        The task list as it was before the move (for undo).
    new_order : List[Task]
        The task list after the move (for execute).

    DEVELOPMENT NOTES:
    ------------------
    Moving a row is the one edit that changes no task at all - only the
    order of the list holding them - so UpdateTaskCommand, which swaps one
    task for another, cannot express it. Both orders hold the same Task
    objects, so this stores two orderings rather than copies.
    """
    project: Project
    old_order: List[Task]
    new_order: List[Task]
    name: str = field(default="", init=False)

    def __post_init__(self):
        self.name = "Reorder Tasks"

    def execute(self) -> bool:
        """Apply the new order."""
        self.project.tasks = list(self.new_order)
        return True

    def undo(self) -> bool:
        """Restore the previous order."""
        self.project.tasks = list(self.old_order)
        return True


@dataclass
class CompoundCommand(Command):
    """
    A command that combines multiple commands into one.
    
    This is useful for operations that consist of multiple steps but should
    be treated as a single undoable action.
    
    PARAMETERS:
    -----------
    commands : List[Command]
        The list of commands to execute together
    name : str
        A name for this compound command
    
    DEVELOPMENT NOTES:
    ------------------
    When executed, all commands are executed in order.
    When undone, all commands are undone in reverse order.
    
    This ensures that complex operations can be undone as a single action.
    
    Example: If you add a task and then set a dependency, these two actions
    should be undoable together as a single "Add task with dependency" operation.
    """
    commands: List[Command] = field(default_factory=list)
    name: str = "Compound Command"
    
    def execute(self) -> bool:
        """Execute all commands in order."""
        success = True
        for command in self.commands:
            if not command.execute():
                success = False
        return success
    
    def undo(self) -> bool:
        """Undo all commands in reverse order."""
        success = True
        for command in reversed(self.commands):
            if not command.undo():
                success = False
        return success


class UndoRedoManager:
    """
    Manages undo and redo operations for a project.
    
    This class maintains two stacks:
    - undo_stack: Commands that have been executed and can be undone
    - redo_stack: Commands that have been undone and can be redone
    
    It provides methods to:
    - execute(): Run a command and add it to the undo stack
    - undo(): Undo the last command and add it to the redo stack
    - redo(): Redo the last undone command and add it back to the undo stack
    - clear(): Clear all undo/redo history
    
    PARAMETERS:
    -----------
    max_history : int, optional
        Maximum number of commands to keep in history (default: 100)
        When this limit is reached, oldest commands are removed.
    
    DEVELOPMENT NOTES:
    ------------------
    This class follows the Memento pattern by storing the state of commands
    that can be used to restore previous states.
    
    The undo/redo stacks work as follows:
    1. When a command is executed via execute(), it's added to undo_stack
    2. When undo() is called, the last command from undo_stack is popped,
       its undo() method is called, and it's pushed to redo_stack
    3. When redo() is called, the last command from redo_stack is popped,
       its execute() method is called, and it's pushed back to undo_stack
    
    Memory management: When the undo stack exceeds max_history, the oldest
    commands are removed. This prevents excessive memory usage for long
    sessions with many changes.
    """
    
    def __init__(self, max_history: int = 100):
        self.max_history = max_history
        self.undo_stack: List[Command] = []
        self.redo_stack: List[Command] = []
        self._current_project: Optional[Project] = None
    
    def set_project(self, project: Project):
        """
        Set the current project for this manager.
        
        PARAMETERS:
        -----------
        project : Project
            The project to manage undo/redo for
        """
        self._current_project = project
    
    def execute(self, command: Command) -> bool:
        """
        Execute a command and add it to the undo stack.
        
        PARAMETERS:
        -----------
        command : Command
            The command to execute
            
        RETURNS:
        --------
        bool
            True if execution was successful, False otherwise
            
        DEVELOPMENT NOTES:
        ------------------
        This method:
        1. Executes the command
        2. If successful, adds it to the undo stack
        3. Clears the redo stack (since new actions invalidate the redo history)
        4. Enforces the max_history limit
        """
        # Execute the command
        if not command.execute():
            return False
        
        # Add to undo stack
        self.undo_stack.append(command)
        
        # Clear redo stack (new actions invalidate redo history)
        self.redo_stack.clear()
        
        # Enforce max history limit
        if len(self.undo_stack) > self.max_history:
            self.undo_stack = self.undo_stack[-self.max_history:]
        
        return True
    
    def undo(self) -> bool:
        """
        Undo the last executed command.
        
        RETURNS:
        --------
        bool
            True if undo was successful, False if there was nothing to undo
            
        DEVELOPMENT NOTES:
        ------------------
        This method:
        1. Pops the last command from the undo stack
        2. Calls its undo() method
        3. Pushes the command to the redo stack
        4. Returns False if the undo stack was empty
        """
        if not self.can_undo():
            return False
        
        # Get the last command
        command = self.undo_stack.pop()
        
        # Undo it
        if not command.undo():
            # If undo failed, put it back
            self.undo_stack.append(command)
            return False
        
        # Add to redo stack
        self.redo_stack.append(command)
        
        return True
    
    def redo(self) -> bool:
        """
        Redo the last undone command.
        
        RETURNS:
        --------
        bool
            True if redo was successful, False if there was nothing to redo
            
        DEVELOPMENT NOTES:
        ------------------
        This method:
        1. Pops the last command from the redo stack
        2. Calls its execute() method
        3. Pushes the command back to the undo stack
        4. Returns False if the redo stack was empty
        """
        if not self.can_redo():
            return False
        
        # Get the last undone command
        command = self.redo_stack.pop()
        
        # Execute it
        if not command.execute():
            # If execute failed, put it back
            self.redo_stack.append(command)
            return False
        
        # Add back to undo stack
        self.undo_stack.append(command)
        
        return True
    
    def can_undo(self) -> bool:
        """
        Check if there are commands that can be undone.
        
        RETURNS:
        --------
        bool
            True if undo is possible, False otherwise
        """
        return len(self.undo_stack) > 0
    
    def can_redo(self) -> bool:
        """
        Check if there are commands that can be redone.
        
        RETURNS:
        --------
        bool
            True if redo is possible, False otherwise
        """
        return len(self.redo_stack) > 0
    
    def clear(self):
        """
        Clear all undo and redo history.
        
        DEVELOPMENT NOTES:
        ------------------
        This is typically called when:
        - A new project is loaded
        - The user starts a new project
        - The application is reset
        """
        self.undo_stack.clear()
        self.redo_stack.clear()
    
    def get_undo_description(self) -> str:
        """
        Get a description of the next undo action.
        
        RETURNS:
        --------
        str
            Description of the next undo action, or empty string if none
        """
        if self.can_undo():
            return f"Undo: {self.undo_stack[-1].name}"
        return ""
    
    def get_redo_description(self) -> str:
        """
        Get a description of the next redo action.
        
        RETURNS:
        --------
        str
            Description of the next redo action, or empty string if none
        """
        if self.can_redo():
            return f"Redo: {self.redo_stack[-1].name}"
        return ""


# Factory functions for creating commands
def create_add_task_command(project: Project, task: Task) -> AddTaskCommand:
    """
    Create a command to add a task to a project.
    
    PARAMETERS:
    -----------
    project : Project
        The project to add the task to
    task : Task
        The task to add
        
    RETURNS:
    --------
    AddTaskCommand
        A command that adds the task when executed
    """
    return AddTaskCommand(project=project, task=task)


def create_remove_task_command(project: Project, task_id: str, task: Task, index: int) -> RemoveTaskCommand:
    """
    Create a command to remove a task from a project.
    
    PARAMETERS:
    -----------
    project : Project
        The project to remove the task from
    task_id : str
        The ID of the task to remove
    task : Task
        The task object (for redo)
    index : int
        The index of the task in the project (for redo)
        
    RETURNS:
    --------
    RemoveTaskCommand
        A command that removes the task when executed
    """
    return RemoveTaskCommand(project=project, task_id=task_id, task=task, index=index)


def create_update_task_command(project: Project, task_id: str, old_task: Task, new_task: Task) -> UpdateTaskCommand:
    """
    Create a command to update a task's properties.
    
    PARAMETERS:
    -----------
    project : Project
        The project containing the task
    task_id : str
        The ID of the task to update
    old_task : Task
        The task with its original properties
    new_task : Task
        The task with its new properties
        
    RETURNS:
    --------
    UpdateTaskCommand
        A command that updates the task when executed
    """
    return UpdateTaskCommand(project=project, task_id=task_id, old_task=old_task, new_task=new_task)


def create_restructure_tasks_command(project: Project, old_snapshot,
                                     new_snapshot,
                                     label: str = "Restructure Tasks"
                                     ) -> RestructureTasksCommand:
    """
    Create a command to change where tasks sit in the hierarchy.

    PARAMETERS:
    -----------
    project : Project
        The project whose structure changed
    old_snapshot, new_snapshot : tuple
        Project.structure_snapshot() from before and after the change
    label : str
        What to call it in the undo history

    RETURNS:
    --------
    RestructureTasksCommand
        A command that applies the new structure when executed
    """
    return RestructureTasksCommand(project=project, old_snapshot=old_snapshot,
                                   new_snapshot=new_snapshot, label=label)


def create_reorder_tasks_command(project: Project, old_order: List[Task],
                                 new_order: List[Task]) -> ReorderTasksCommand:
    """
    Create a command to change the order of a project's tasks.

    PARAMETERS:
    -----------
    project : Project
        The project whose task order changed
    old_order : List[Task]
        The task list before the move
    new_order : List[Task]
        The task list after the move

    RETURNS:
    --------
    ReorderTasksCommand
        A command that applies the new order when executed
    """
    return ReorderTasksCommand(project=project, old_order=old_order,
                               new_order=new_order)


def create_update_project_name_command(project: Project, old_name: str, new_name: str) -> UpdateProjectNameCommand:
    """
    Create a command to update the project name.
    
    PARAMETERS:
    -----------
    project : Project
        The project to update
    old_name : str
        The original project name
    new_name : str
        The new project name
        
    RETURNS:
    --------
    UpdateProjectNameCommand
        A command that updates the project name when executed
    """
    return UpdateProjectNameCommand(project=project, old_name=old_name, new_name=new_name)


def create_compound_command(commands: List[Command], name: str = "Compound Command") -> CompoundCommand:
    """
    Create a compound command from multiple commands.
    
    PARAMETERS:
    -----------
    commands : List[Command]
        The list of commands to combine
    name : str, optional
        A name for the compound command
        
    RETURNS:
    --------
    CompoundCommand
        A command that executes all sub-commands together
    """
    return CompoundCommand(commands=commands, name=name)


# Helper class for managing project state changes
class ProjectStateTracker:
    """
    Helper class that makes it easier to create undoable commands for project changes.
    
    This class wraps a project and an undo/redo manager, providing convenience
    methods for common operations that automatically create the appropriate commands.
    
    PARAMETERS:
    -----------
    project : Project
        The project to track
    manager : UndoRedoManager
        The undo/redo manager to use
    
    DEVELOPMENT NOTES:
    ------------------
    This class provides a more convenient API for creating undoable actions.
    Instead of manually creating commands, you can use methods like:
    
    - add_task(task): Adds a task and creates an undoable command
    - remove_task(task_id): Removes a task and creates an undoable command
    - update_task(task_id, **kwargs): Updates a task and creates an undoable command
    
    This makes it easier to integrate undo/redo with the application logic.
    """
    
    def __init__(self, project: Project, manager: UndoRedoManager):
        self.project = project
        self.manager = manager
        self.manager.set_project(project)
    
    def add_task(self, task: Task) -> bool:
        """
        Add a task to the project with undo support.
        
        PARAMETERS:
        -----------
        task : Task
            The task to add
            
        RETURNS:
        --------
        bool
            True if successful, False otherwise
        """
        command = create_add_task_command(self.project, task)
        return self.manager.execute(command)
    
    def remove_task(self, task_id: str) -> bool:
        """
        Remove a task from the project with undo support.
        
        PARAMETERS:
        -----------
        task_id : str
            The ID of the task to remove
            
        RETURNS:
        --------
        bool
            True if successful, False otherwise
        """
        # Find the task and its index
        task = self.project.get_task_by_id(task_id)
        if not task:
            return False
        
        try:
            index = self.project.tasks.index(task)
        except ValueError:
            return False
        
        command = create_remove_task_command(self.project, task_id, task, index)
        return self.manager.execute(command)
    
    def update_task(self, task_id: str, **kwargs) -> bool:
        """
        Update a task's properties with undo support.
        
        PARAMETERS:
        -----------
        task_id : str
            The ID of the task to update
        **kwargs
            The properties to update (name, start_date, end_date, progress, etc.)
            
        RETURNS:
        --------
        bool
            True if successful, False otherwise
        """
        # Find the task
        task = self.project.get_task_by_id(task_id)
        if not task:
            return False
        
        # Store the old task.
        #
        # copy.copy bypasses __setattr__ and leaves the copy sharing the very
        # DependencyList the live task holds, so a caller that later mutates
        # that list in place would rewrite this undo snapshot too. The links
        # are copied individually because Task.add_dependency updates an
        # existing Dependency in place rather than replacing it.
        old_task = copy.copy(task)
        old_task.dependencies = [copy.copy(d) for d in task.dependencies]
        
        # Create a new task with the updated properties
        # We'll use the same ID and just update the specified properties
        new_task_data = {
            'id': task.id,
            'name': kwargs.get('name', task.name),
            'start_date': kwargs.get('start_date', task.start_date),
            'end_date': kwargs.get('end_date', task.end_date),
            'progress': kwargs.get('progress', task.progress),
            'dependencies': kwargs.get('dependencies', task.dependencies),
            'color': kwargs.get('color', task.color),
            'is_milestone': kwargs.get('is_milestone', task.is_milestone),
            'task_type': kwargs.get('task_type', task.task_type),
            'parent_task_id': kwargs.get('parent_task_id', task.parent_task_id)
        }
        
        new_task = Task(**new_task_data)
        
        command = create_update_task_command(self.project, task_id, old_task, new_task)
        return self.manager.execute(command)
    
    def restructure_tasks(self, old_snapshot, new_snapshot,
                          label: str = "Restructure Tasks") -> bool:
        """
        Record a change to where tasks sit in the hierarchy.

        PARAMETERS:
        -----------
        old_snapshot, new_snapshot : tuple
            Project.structure_snapshot() from before and after the change.
        label : str
            What to call it in the undo history.

        RETURNS:
        --------
        bool
            True if successful, False otherwise.
        """
        command = create_restructure_tasks_command(
            self.project, old_snapshot, new_snapshot, label
        )
        return self.manager.execute(command)

    def reorder_tasks(self, old_order: List[Task], new_order: List[Task]) -> bool:
        """
        Record a change to the order of the project's tasks.

        PARAMETERS:
        -----------
        old_order : List[Task]
            The task list as it was before the move.
        new_order : List[Task]
            The task list after the move.

        RETURNS:
        --------
        bool
            True if successful, False otherwise.

        DEVELOPMENT NOTES:
        ------------------
        The caller has already reordered the project, so executing the
        command re-applies an order that is in place. That keeps this the
        same shape as the other tracker methods, and makes the redo path
        exercise exactly the code the first move did.
        """
        command = create_reorder_tasks_command(
            self.project, list(old_order), list(new_order)
        )
        return self.manager.execute(command)

    def update_project_name(self, new_name: str) -> bool:
        """
        Update the project name with undo support.
        
        PARAMETERS:
        -----------
        new_name : str
            The new project name
            
        RETURNS:
        --------
        bool
            True if successful, False otherwise
        """
        old_name = self.project.name
        command = create_update_project_name_command(self.project, old_name, new_name)
        return self.manager.execute(command)
    
    def undo(self) -> bool:
        """Undo the last action."""
        return self.manager.undo()
    
    def redo(self) -> bool:
        """Redo the last undone action."""
        return self.manager.redo()
    
    def can_undo(self) -> bool:
        """Check if undo is possible."""
        return self.manager.can_undo()
    
    def can_redo(self) -> bool:
        """Check if redo is possible."""
        return self.manager.can_redo()
    
    def clear(self):
        """Clear undo/redo history."""
        self.manager.clear()
