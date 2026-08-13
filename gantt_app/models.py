"""
Data models for the Gantt Project Management Tool.

Contains the Task and Project classes that form the core data structure.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
import uuid


#: How a dependency constrains the dependent task's start.
DEPENDENCY_TYPES = ('SS', 'FS')

#: How strictly the constraint is applied.
DEPENDENCY_HARDNESS = ('Hard', 'Rubber')

#: Labels shown in the user interface.
DEPENDENCY_TYPE_LABELS = {
    'SS': 'Start - Start',
    'FS': 'End - Start',
}
DEPENDENCY_HARDNESS_LABELS = {
    'Hard': 'Hard',
    'Rubber': 'Rubber',
}


@dataclass
class Dependency:
    """
    A link from a predecessor task to the task that depends on it.

    Attributes:
        task_id: ID of the predecessor
        dep_type: 'SS' (Start - Start) or 'FS' (End - Start)
        hardness: 'Hard' or 'Rubber'

    DEVELOPMENT NOTES:
    ------------------
    'SS' means the dependent task starts when the predecessor starts; 'FS'
    means it starts after the predecessor finishes.

    Hardness decides whether that date is fixed or merely a floor. 'Hard'
    pins the start to the computed date; 'Rubber' only forbids starting
    earlier, so a task may be scheduled later than its predecessor allows.

    GanttProject uses the same two concepts, writing type="1"/"2" and
    hardness="Strong"/"Rubber", so a .gan file maps onto this directly.
    """

    task_id: str
    dep_type: str = 'FS'
    hardness: str = 'Hard'

    def __post_init__(self):
        """Normalise the type and hardness to known values."""
        self.task_id = str(self.task_id)

        dep_type = str(self.dep_type or 'FS').upper()
        # Finish-Start is written several ways; anything unknown falls back
        # to it because it is by far the most common link
        self.dep_type = 'SS' if dep_type == 'SS' else 'FS'

        hardness = str(self.hardness or 'Hard').capitalize()
        self.hardness = 'Rubber' if hardness == 'Rubber' else 'Hard'

    @property
    def type_label(self) -> str:
        """Human readable dependency type."""
        return DEPENDENCY_TYPE_LABELS[self.dep_type]

    def to_dict(self) -> dict:
        """Convert to a dictionary for serialization."""
        return {
            'task_id': self.task_id,
            'dep_type': self.dep_type,
            'hardness': self.hardness,
        }

    @classmethod
    def from_any(cls, value) -> 'Dependency':
        """
        Build a Dependency from a plain ID, a dict, or another Dependency.

        DEVELOPMENT NOTES:
        ------------------
        Projects saved before dependencies carried a type stored a bare list
        of task IDs. Accepting a string here keeps those files loading, and
        keeps `dependencies=[task.id]` working everywhere it is already used.
        """
        if isinstance(value, cls):
            return value
        if isinstance(value, dict):
            return cls(
                task_id=value.get('task_id') or value.get('id'),
                dep_type=value.get('dep_type', 'FS'),
                hardness=value.get('hardness', 'Hard'),
            )
        return cls(task_id=str(value))



class DependencyList(list):
    """
    A list of Dependency objects that accepts plain task IDs.

    DEVELOPMENT NOTES:
    ------------------
    Existing code appends bare task IDs - `task.dependencies.append(dep_id)`
    appears in the importers, the task list and the tests. Coercing only on
    assignment left those appends putting raw strings into the list, so
    reading dependency_ids blew up with "'str' object has no attribute
    'task_id'". Every mutation route is normalised here instead.
    """

    def __init__(self, values=()):
        super().__init__(Dependency.from_any(v) for v in values)

    def append(self, value):
        """Append a dependency, accepting an ID, dict or Dependency."""
        super().append(Dependency.from_any(value))

    def insert(self, index, value):
        """Insert a dependency, accepting an ID, dict or Dependency."""
        super().insert(index, Dependency.from_any(value))

    def extend(self, values):
        """Extend with dependencies, accepting IDs, dicts or Dependency."""
        super().extend(Dependency.from_any(v) for v in values)

    def __setitem__(self, index, value):
        """Replace an entry, accepting an ID, dict or Dependency."""
        if isinstance(index, slice):
            super().__setitem__(index, [Dependency.from_any(v) for v in value])
        else:
            super().__setitem__(index, Dependency.from_any(value))

    def __contains__(self, value):
        """Membership works for a Dependency or a bare task ID."""
        if isinstance(value, str):
            return any(d.task_id == value for d in self)
        return super().__contains__(value)

    def remove(self, value):
        """Remove by Dependency or by bare task ID."""
        if isinstance(value, str):
            for item in self:
                if item.task_id == value:
                    super().remove(item)
                    return
            raise ValueError(value)
        super().remove(value)


@dataclass
class Task:
    """
    Represents a task or milestone in the project.
    
    Attributes:
        id: Unique identifier for the task
        name: Display name of the task
        start_date: When the task begins
        end_date: When the task ends (None for milestones)
        progress: Completion percentage (0-100)
        dependencies: List of task IDs that must complete before this task
        color: Hex color string for visualization
        is_milestone: Whether this is a milestone (single-date marker)
        task_type: Type of task - 'Task' or 'Sub-Task'
        parent_task_id: ID of parent task (for Sub-Tasks only, None for regular Tasks)
    
    DEVELOPMENT NOTES:
    ------------------
    - task_type can be 'Task' or 'Sub-Task'
    - Sub-Tasks must have a parent_task_id pointing to a regular Task
    - Sub-Tasks inherit the start_date from their parent by default
    - Duration is calculated from start_date and end_date (if available)
    """
    id: str
    name: str
    start_date: datetime
    end_date: Optional[datetime] = None
    progress: int = 0
    dependencies: List['Dependency'] = field(default_factory=list)
    color: str = "#1f6aa5"
    is_milestone: bool = False
    task_type: str = "Task"
    parent_task_id: Optional[str] = None
    
    def __post_init__(self):
        """
        Validate task data after initialization.

        DEVELOPMENT NOTES:
        ------------------
        Dependencies are coerced into Dependency objects here, so callers
        may still pass a plain list of task IDs. That keeps every existing
        `dependencies=[task.id]` call working and lets projects saved before
        dependencies carried a type load unchanged.
        """
        if not self.name:
            raise ValueError("Task name cannot be empty")
        if self.progress < 0 or self.progress > 100:
            raise ValueError("Progress must be between 0 and 100")
        if self.is_milestone and self.end_date is not None:
            # For milestones, end_date should be None or same as start_date
            self.end_date = None

        self.dependencies = DependencyList(self.dependencies or [])

    def __setattr__(self, name, value):
        """
        Coerce dependencies whenever they are assigned.

        DEVELOPMENT NOTES:
        ------------------
        Plenty of existing code assigns a plain list of task IDs, and the
        importers and undo/redo do it too. Normalising on assignment rather
        than only in __post_init__ means those callers keep working and the
        list can never end up holding a mix of strings and Dependency
        objects.
        """
        if name == 'dependencies' and value is not None:
            value = value if isinstance(value, DependencyList) else DependencyList(value)
        super().__setattr__(name, value)

    @property
    def dependency_ids(self) -> List[str]:
        """
        Get just the predecessor IDs.

        RETURNS:
        --------
        List[str]
            The task IDs this task depends on, without the link details.
            Used by scheduling, rendering and export code that does not care
            how the link is configured.
        """
        return [d.task_id for d in self.dependencies]

    def get_dependency(self, task_id: str) -> Optional['Dependency']:
        """Get the link to a given predecessor, or None."""
        for dependency in self.dependencies:
            if dependency.task_id == task_id:
                return dependency
        return None

    def add_dependency(self, task_id: str, dep_type: str = 'FS',
                       hardness: str = 'Hard') -> 'Dependency':
        """
        Add or update a link to a predecessor.

        RETURNS:
        --------
        Dependency
            The stored link. Adding the same predecessor twice updates the
            existing link rather than duplicating it.
        """
        existing = self.get_dependency(task_id)
        if existing is not None:
            existing.dep_type = dep_type
            existing.hardness = hardness
            existing.__post_init__()
            return existing

        dependency = Dependency(task_id=task_id, dep_type=dep_type,
                                hardness=hardness)
        self.dependencies.append(dependency)
        return dependency

    def remove_dependency(self, task_id: str) -> bool:
        """Remove the link to a predecessor. True when one was removed."""
        before = len(self.dependencies)
        self.dependencies = [d for d in self.dependencies if d.task_id != task_id]
        return len(self.dependencies) < before
    
    @classmethod
    def create_task(cls, name: str, start_date: datetime, end_date: datetime, 
                   color: str = "#1f6aa5", progress: int = 0, 
                   dependencies: List[str] = None,
                   task_id: str = None) -> 'Task':
        """
        Create a new regular task.

        PARAMETERS:
        -----------
        task_id : str, optional
            Identifier to use. Pass Project.next_task_id() for sequential
            numbering; omitted, a UUID is generated so callers that do not
            have a project to hand still get a unique ID.
        """
        return cls(
            id=task_id or str(uuid.uuid4()),
            name=name,
            start_date=start_date,
            end_date=end_date,
            progress=progress,
            dependencies=dependencies or [],
            color=color,
            is_milestone=False
        )
    
    @classmethod
    def create_milestone(cls, name: str, date: datetime, 
                        color: str = "#e74c3c", 
                        dependencies: List[str] = None,
                        task_id: str = None) -> 'Task':
        """
        Create a new milestone (single-date marker).

        PARAMETERS:
        -----------
        task_id : str, optional
            Identifier to use; see create_task.
        """
        return cls(
            id=task_id or str(uuid.uuid4()),
            name=name,
            start_date=date,
            end_date=None,
            progress=0,
            dependencies=dependencies or [],
            color=color,
            is_milestone=True,
            task_type="Task",
            parent_task_id=None
        )
    
    @classmethod
    def create_subtask(cls, name: str, parent_task: 'Task', 
                      end_date: Optional[datetime] = None,
                      color: str = "#9b59b6",
                      progress: int = 0,
                      dependencies: List[str] = None,
                      task_id: str = None) -> 'Task':
        """
        Create a new subtask under a parent task.

        PARAMETERS:
        -----------
        name : str
            Name of the subtask
        parent_task : Task
            The parent task this subtask belongs to
        end_date : datetime, optional
            End date for the subtask. If not provided, only start_date is set.
        color : str, optional
            Hex color for visualization (default: purple)
        progress : int, optional
            Initial progress percentage (default: 0)
        dependencies : List[str], optional
            List of task IDs this subtask depends on
        task_id : str, optional
            Identifier to use; see create_task.

        RETURNS:
        --------
        Task
            A new subtask with task_type='Sub-Task' and parent_task_id set
        
        DEVELOPMENT NOTES:
        ------------------
        Subtasks automatically inherit the start_date from their parent task.
        This ensures that subtasks start when their parent task starts.
        The end_date can be set explicitly or left None for flexible duration.
        """
        # Use parent's start_date for the subtask
        parent_start = parent_task.start_date
        
        # If end_date not provided, set it to same as start_date (1 day) or leave None
        subtask_end = end_date
        if subtask_end is None and not parent_task.is_milestone:
            # Default to 1 day duration if parent has an end_date
            if parent_task.end_date:
                subtask_end = parent_start  # Will be 1 day by default
        
        return cls(
            id=task_id or str(uuid.uuid4()),
            name=name,
            start_date=parent_start,
            end_date=subtask_end,
            progress=progress,
            dependencies=dependencies or [],
            color=color,
            is_milestone=False,
            task_type="Sub-Task",
            parent_task_id=parent_task.id
        )
    
    @property
    def duration_days(self) -> Optional[int]:
        """
        Calculate duration in days from start_date to end_date.
        
        RETURNS:
        --------
        Optional[int]
            Number of days between start_date and end_date (inclusive),
            or 0 for milestones, or None if end_date is not set.
        
        DEVELOPMENT NOTES:
        ------------------
        This is a calculated property that automatically updates when
        start_date or end_date changes. For subtasks without an explicit
        end_date, it returns None.
        """
        if self.is_milestone:
            return 0
        if self.end_date is None:
            return None
        return (self.end_date - self.start_date).days + 1
    
    def to_dict(self) -> dict:
        """
        Convert task to dictionary for serialization.
        
        RETURNS:
        --------
        dict
            Dictionary representation of the task including all fields
        """
        return {
            'id': self.id,
            'name': self.name,
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'progress': self.progress,
            'dependencies': [d.to_dict() for d in self.dependencies],
            'color': self.color,
            'is_milestone': self.is_milestone,
            'task_type': self.task_type,
            'parent_task_id': self.parent_task_id
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Task':
        """
        Create task from dictionary.
        
        PARAMETERS:
        -----------
        data : dict
            Dictionary containing task data
        
        RETURNS:
        --------
        Task
            A new Task instance populated from the dictionary
        
        DEVELOPMENT NOTES:
        ------------------
        Handles backward compatibility by providing defaults for new fields
        (task_type and parent_task_id) if they don't exist in the data.
        """
        # Handle start_date (could be string or datetime)
        start_date = data['start_date']
        if isinstance(start_date, str):
            try:
                start_date = datetime.fromisoformat(start_date)
            except (ValueError, TypeError):
                start_date = datetime.now()
        
        # Handle end_date (could be string, datetime, or None)
        end_date = data.get('end_date')
        if isinstance(end_date, str):
            try:
                end_date = datetime.fromisoformat(end_date)
            except (ValueError, TypeError):
                end_date = None
        
        return cls(
            id=data['id'],
            name=data['name'],
            start_date=start_date,
            end_date=end_date,
            progress=data['progress'],
            dependencies=data['dependencies'],
            color=data['color'],
            is_milestone=data['is_milestone'],
            task_type=data.get('task_type', 'Task'),
            parent_task_id=data.get('parent_task_id', None)
        )


@dataclass
class Project:
    """
    Represents a project containing multiple tasks.
    
    Attributes:
        name: Project name
        tasks: List of Task objects
        start_date: Project start date
        end_date: Project end date
    """
    name: str
    tasks: List[Task] = field(default_factory=list)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    
    def __post_init__(self):
        """Update project dates based on tasks if not set."""
        if self.tasks:
            self._update_dates()
    
    def _update_dates(self):
        """Calculate project start and end dates from tasks."""
        if not self.tasks:
            return
        
        start_dates = [task.start_date for task in self.tasks]
        end_dates = [task.end_date for task in self.tasks if task.end_date is not None]
        
        if start_dates:
            self.start_date = min(start_dates)
        if end_dates:
            self.end_date = max(end_dates)
    
    #: Width of a generated task ID, so numbering reads 001, 002, ...
    ID_WIDTH = 3

    def next_task_id(self) -> str:
        """
        Get the next free sequential task ID.

        RETURNS:
        --------
        str
            A zero-padded number such as '001', one higher than the largest
            number already in use.

        DEVELOPMENT NOTES:
        ------------------
        Numbering continues past whatever a project already contains, so a
        task added to an imported plan cannot collide with an ID that came
        from the file. Non-numeric IDs are ignored when finding the maximum
        but still checked for collisions.
        """
        existing = {task.id for task in self.tasks}

        highest = 0
        for task_id in existing:
            try:
                highest = max(highest, int(str(task_id).strip()))
            except (TypeError, ValueError):
                continue

        candidate_number = highest + 1
        candidate = str(candidate_number).zfill(self.ID_WIDTH)
        while candidate in existing:
            candidate_number += 1
            candidate = str(candidate_number).zfill(self.ID_WIDTH)

        return candidate

    def renumber_task_ids(self) -> dict:
        """
        Renumber every task sequentially from 001, preserving all references.

        RETURNS:
        --------
        dict
            Mapping of old task ID to new task ID.

        DEVELOPMENT NOTES:
        ------------------
        Imported files carry whatever identifiers their format used - UUIDs,
        GanttProject integers, Mermaid labels like 'a1'. Those are meaningless
        to a reader of the task list, so an import renumbers into the same
        simple sequence used for tasks created in the app.

        Dependencies and parent_task_id are remapped in the same pass. Doing
        this in two steps - assigning new IDs, then rewriting references
        through the mapping - is what keeps a task from being re-pointed at a
        number that now belongs to a different task.
        """
        mapping = {}
        for index, task in enumerate(self.tasks, start=1):
            mapping[task.id] = str(index).zfill(self.ID_WIDTH)

        for task in self.tasks:
            task.id = mapping[task.id]
            for dependency in task.dependencies:
                dependency.task_id = mapping.get(dependency.task_id,
                                                 dependency.task_id)
            task.dependencies = [d for d in task.dependencies
                                 if d.task_id in mapping.values()]
            if task.parent_task_id is not None:
                task.parent_task_id = mapping.get(task.parent_task_id)
                if task.parent_task_id is None:
                    # Parent was not in this project; treat as a root task
                    task.task_type = "Task"

        return mapping

    def add_task(self, task: Task):
        """Add a task to the project and update dates."""
        self.tasks.append(task)
        self._update_dates()
    
    def remove_task(self, task_id: str) -> bool:
        """
        Remove a task by ID and update dates.
        
        PARAMETERS:
        -----------
        task_id : str
            The ID of the task to remove
        
        RETURNS:
        --------
        bool
            True if task was removed, False otherwise
        
        DEVELOPMENT NOTES:
        ------------------
        Also removes any subtasks that belong to the removed task.
        Removes the task from dependencies of other tasks.
        """
        initial_count = len(self.tasks)
        
        # First, find all subtasks of the task being removed
        subtask_ids = [t.id for t in self.tasks if t.parent_task_id == task_id]
        
        # Remove the task and all its subtasks
        self.tasks = [t for t in self.tasks if t.id != task_id and t.id not in subtask_ids]
        
        # Remove task from dependencies of other tasks
        for task in self.tasks:
            task.remove_dependency(task_id)
            # Also remove any subtask dependencies
            for subtask_id in subtask_ids:
                task.remove_dependency(subtask_id)
        
        if len(self.tasks) < initial_count:
            self._update_dates()
            return True
        return False
    
    def get_task_by_id(self, task_id: str) -> Optional[Task]:
        """Get a task by its ID."""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None
    
    def get_dependencies(self, task_id: str) -> List[Task]:
        """Get all tasks that this task depends on."""
        task = self.get_task_by_id(task_id)
        if task is None:
            return []
        return [self.get_task_by_id(dep_id) for dep_id in task.dependency_ids
                if self.get_task_by_id(dep_id) is not None]
    
    def get_dependents(self, task_id: str) -> List[Task]:
        """Get all tasks that depend on this task."""
        return [task for task in self.tasks if task_id in task.dependency_ids]
    
    def get_subtasks(self, task_id: str) -> List[Task]:
        """
        Get all subtasks for a given task.
        
        PARAMETERS:
        -----------
        task_id : str
            The ID of the parent task
        
        RETURNS:
        --------
        List[Task]
            List of subtasks that have the specified task as parent
        """
        return [task for task in self.tasks if task.parent_task_id == task_id]
    
    def get_parent_task(self, task_id: str) -> Optional[Task]:
        """
        Get the parent task for a subtask.
        
        PARAMETERS:
        -----------
        task_id : str
            The ID of the subtask
        
        RETURNS:
        --------
        Optional[Task]
            The parent task if this is a subtask, None otherwise
        """
        task = self.get_task_by_id(task_id)
        if task and task.parent_task_id:
            return self.get_task_by_id(task.parent_task_id)
        return None
    
    def get_root_tasks(self) -> List[Task]:
        """
        Get all root-level tasks (not subtasks).
        
        RETURNS:
        --------
        List[Task]
            List of tasks that are not subtasks (parent_task_id is None)
        """
        return [task for task in self.tasks if task.parent_task_id is None]
    
    def to_dict(self) -> dict:
        """Convert project to dictionary for serialization."""
        return {
            'name': self.name,
            'tasks': [task.to_dict() for task in self.tasks],
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Project':
        """Create project from dictionary."""
        # Create project without tasks first
        start_date = None
        end_date = None
        
        if data.get('start_date'):
            try:
                start_date = datetime.fromisoformat(data['start_date'])
            except (ValueError, TypeError):
                start_date = None
        
        if data.get('end_date'):
            try:
                end_date = datetime.fromisoformat(data['end_date'])
            except (ValueError, TypeError):
                end_date = None
        
        # Create empty project first
        project = cls(
            name=data['name'],
            start_date=start_date,
            end_date=end_date,
            tasks=[]  # Start with empty tasks to avoid __post_init__ updating dates prematurely
        )
        
        # Add tasks manually
        project.tasks = [Task.from_dict(task_data) for task_data in data.get('tasks', [])]
        
        # If tasks exist, update project dates based on tasks
        if project.tasks:
            project._update_dates()
        
        return project
    
    def constrained_start_date(self, task: Task) -> Optional[datetime]:
        """
        Work out the start date a task's dependencies require.

        PARAMETERS:
        -----------
        task : Task
            The dependent task.

        RETURNS:
        --------
        Optional[datetime]
            The date the task should start, or None when nothing constrains
            it. A 'Hard' link pins the start exactly; 'Rubber' links only set
            a floor, so the task keeps its own later start if it has one.

        DEVELOPMENT NOTES:
        ------------------
        Start - Start uses the predecessor's start date. End - Start uses the
        day after the predecessor finishes, because end dates in this model
        are inclusive: a task ending on the 5th occupies the whole of the
        5th, so its successor starts on the 6th. Milestones have no end date,
        so both types resolve to the milestone's own date.

        With several links, the hard ones win outright and the latest of them
        applies. Otherwise the rubber links contribute a floor.
        """
        hard_dates = []
        floor_dates = []

        for dependency in task.dependencies:
            predecessor = self.get_task_by_id(dependency.task_id)
            if predecessor is None:
                continue

            if dependency.dep_type == 'SS' or predecessor.is_milestone:
                required = predecessor.start_date
            else:
                end = predecessor.end_date or predecessor.start_date
                required = end + timedelta(days=1)

            if required is None:
                continue
            if dependency.hardness == 'Hard':
                hard_dates.append(required)
            else:
                floor_dates.append(required)

        if hard_dates:
            return max(hard_dates)
        if floor_dates:
            floor = max(floor_dates)
            return floor if task.start_date < floor else task.start_date
        return None

    def apply_dependency_constraints(self, task: Task,
                                     preserve_duration: bool = True) -> bool:
        """
        Move a task so it satisfies its dependency links.

        PARAMETERS:
        -----------
        task : Task
            The task to reschedule.
        preserve_duration : bool
            Keep the task's length, shifting the end date by the same amount.

        RETURNS:
        --------
        bool
            True when the task moved.

        DEVELOPMENT NOTES:
        ------------------
        Called when a dependency is added or changed, which is what makes
        picking a predecessor set the dependent task's start date without
        the user typing it.
        """
        required = self.constrained_start_date(task)
        if required is None or required == task.start_date:
            return False

        shift = required - task.start_date
        task.start_date = required
        if preserve_duration and task.end_date is not None:
            task.end_date = task.end_date + shift

        self._update_dates()
        return True

    def get_summary_task_ids(self) -> set:
        """
        Get the IDs of tasks that have sub-tasks beneath them.

        RETURNS:
        --------
        set
            IDs of every task referenced as a parent by another task.

        DEVELOPMENT NOTES:
        ------------------
        Importers derive these summary tasks from the source file's grouping
        (Mermaid sections, spreadsheet phases, nested GanttProject tasks).
        They span their children rather than representing work of their own,
        so scheduling calculations should look through them.
        """
        return {task.parent_task_id for task in self.tasks if task.parent_task_id}

    def get_critical_path(self) -> List[Task]:
        """
        Calculate the critical path through the project network.

        RETURNS:
        --------
        List[Task]
            The longest chain of dependent tasks ending at the task that
            finishes last, ordered from the start of the project to its end.
            Empty for a project with no tasks.

        DEVELOPMENT NOTES:
        ------------------
        The chain is measured by accumulated duration rather than by comparing
        calendar dates. Plans that are scheduled in working days leave weekend
        and holiday gaps between a task and its successor, and a date-based
        comparison reads those gaps as slack, which would drop most of the
        chain. Accumulated duration is unaffected by them.

        Summary tasks are excluded: they merely envelope their sub-tasks, so
        leaving them in would let a group bar outrank the actual work it
        contains and surface as the critical path itself.

        The endpoint is the task that finishes last, with the longer chain
        winning any tie. An earlier implementation picked whichever tied task
        happened to come first in iteration order, which could end the path
        one task short of the project's real finish.
        """
        if not self.tasks:
            return []

        summary_ids = self.get_summary_task_ids()
        candidates = [t for t in self.tasks if t.id not in summary_ids]
        if not candidates:
            return []

        by_id = {task.id: task for task in candidates}

        children: Dict[Optional[str], List[Task]] = {}
        for task in self.tasks:
            children.setdefault(task.parent_task_id, []).append(task)

        def duration(task: Task) -> int:
            """Length of a task in days; milestones take no time."""
            if task.is_milestone or task.end_date is None:
                return 0
            return max((task.end_date - task.start_date).days + 1, 0)

        resolved_deps: Dict[str, List[Task]] = {}

        def resolve_dependency(dep_id: str) -> List[Task]:
            """
            Expand one dependency into the real tasks it stands for.

            DEVELOPMENT NOTES:
            ------------------
            Depending on a summary task means depending on the work inside it,
            so a summary reference resolves to its non-summary descendants.
            GanttProject files rely on this heavily - several tasks there
            depend on a parent task - and dropping those edges would cut the
            chain in half.
            """
            if dep_id in resolved_deps:
                return resolved_deps[dep_id]

            resolved_deps[dep_id] = []  # guards against a cycle re-entering

            if dep_id in by_id:
                found = [by_id[dep_id]]
            else:
                found = []
                stack = [dep_id]
                seen = set()
                while stack:
                    current_id = stack.pop()
                    if current_id in seen:
                        continue
                    seen.add(current_id)
                    for child in children.get(current_id, []):
                        if child.id in by_id:
                            found.append(child)
                        else:
                            stack.append(child.id)

            resolved_deps[dep_id] = found
            return found

        def predecessors(task: Task) -> List[Task]:
            """The tasks that must finish before this one can start."""
            result = []
            seen = {task.id}
            for dep_id in task.dependency_ids:
                for dep in resolve_dependency(dep_id):
                    if dep.id not in seen:
                        seen.add(dep.id)
                        result.append(dep)
            return result

        # Longest chain of accumulated duration ending at each task. Computed
        # with an explicit stack so deep chains cannot exhaust recursion, and
        # guarded so a dependency cycle cannot loop forever.
        chain_length: Dict[str, int] = {}
        in_progress: Set[str] = set()

        for root in candidates:
            if root.id in chain_length:
                continue
            stack = [(root, False)]
            while stack:
                task, expanded = stack.pop()
                if expanded:
                    in_progress.discard(task.id)
                    best = 0
                    for dep in predecessors(task):
                        best = max(best, chain_length.get(dep.id, 0))
                    chain_length[task.id] = best + duration(task)
                    continue
                if task.id in chain_length or task.id in in_progress:
                    continue
                in_progress.add(task.id)
                stack.append((task, True))
                for dep in predecessors(task):
                    if dep.id not in chain_length and dep.id not in in_progress:
                        stack.append((dep, False))

        def finish_date(task: Task) -> datetime:
            """The date a task finishes, falling back to its start."""
            return task.end_date or task.start_date

        # The project ends with the last task to finish; prefer the longer
        # chain when several finish on the same date
        end_task = max(
            candidates,
            key=lambda t: (finish_date(t), chain_length.get(t.id, 0))
        )

        # Walk back through the predecessor that contributes the longest chain
        critical_path: List[Task] = []
        current: Optional[Task] = end_task
        visited: Set[str] = set()

        while current is not None and current.id not in visited:
            visited.add(current.id)
            critical_path.append(current)

            deps = predecessors(current)
            if not deps:
                break

            current = max(
                deps,
                key=lambda t: (chain_length.get(t.id, 0), finish_date(t))
            )

        return critical_path[::-1]  # Reverse to get start to end order
