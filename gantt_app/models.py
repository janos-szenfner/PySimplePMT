"""
Data models for the Gantt Project Management Tool.

Contains the Task and Project classes that form the core data structure.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
import logging
import uuid

# The standard library directly rather than utils.log.get_logger: models is
# the bottom layer and everything in utils imports it, so reaching back into
# that package runs gantt_app.utils.__init__ mid-import and deadlocks on a
# circular import. get_logger only prefixes bare names, and this one is
# already dotted, so the logger is exactly the same object either way.
logger = logging.getLogger(__name__)


#: How a dependency constrains the dependent task.
#:
#: FS  the successor starts after the predecessor finishes
#: SS  the successor starts once the predecessor starts
#: FF  the successor finishes after the predecessor finishes
#: SF  the successor finishes once the predecessor starts
DEPENDENCY_TYPES = ('FS', 'SS', 'FF', 'SF')

#: The two that constrain the successor's finish rather than its start.
FINISH_CONSTRAINED_TYPES = ('FF', 'SF')

#: How strictly the constraint is applied.
DEPENDENCY_HARDNESS = ('Hard', 'Rubber')

#: Labels shown in the user interface.
DEPENDENCY_TYPE_LABELS = {
    'FS': 'Finish - Start',
    'SS': 'Start - Start',
    'FF': 'Finish - Finish',
    'SF': 'Start - Finish',
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
        dep_type: one of DEPENDENCY_TYPES
        hardness: 'Hard' or 'Rubber'
        lag: days to wait after the constraint is met; negative is lead time

    DEVELOPMENT NOTES:
    ------------------
    The four types are the standard set. FS and SS decide when the successor
    may start; FF and SF decide when it may finish, which is why applying a
    link cannot be expressed as a start date alone.

    Lag delays the successor by a number of days once its constraint is
    satisfied. A negative lag is lead time: the successor may overlap its
    predecessor by that much, which is how a schedule is compressed.

    Hardness decides whether the resulting date is fixed or merely a floor.
    'Hard' pins it; 'Rubber' only forbids being earlier, so a task may sit
    later than its predecessor requires.

    GanttProject writes type="1".."4" and hardness="Strong"/"Rubber", so a
    .gan file maps onto this directly.
    """

    task_id: str
    dep_type: str = 'FS'
    hardness: str = 'Hard'
    lag: int = 0

    def __post_init__(self):
        """Normalise the type, hardness and lag to usable values."""
        self.task_id = str(self.task_id)

        dep_type = str(self.dep_type or 'FS').upper()
        # Anything unrecognised falls back to Finish-Start, by far the most
        # common link and what every importer defaults to
        self.dep_type = dep_type if dep_type in DEPENDENCY_TYPES else 'FS'

        hardness = str(self.hardness or 'Hard').capitalize()
        self.hardness = 'Rubber' if hardness == 'Rubber' else 'Hard'

        try:
            self.lag = int(self.lag or 0)
        except (TypeError, ValueError):
            self.lag = 0

    @property
    def type_label(self) -> str:
        """Human readable dependency type."""
        return DEPENDENCY_TYPE_LABELS[self.dep_type]

    @property
    def constrains_finish(self) -> bool:
        """Whether this link fixes the successor's finish rather than start."""
        return self.dep_type in FINISH_CONSTRAINED_TYPES

    def to_dict(self) -> dict:
        """Convert to a dictionary for serialization."""
        return {
            'task_id': self.task_id,
            'dep_type': self.dep_type,
            'hardness': self.hardness,
            'lag': self.lag,
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
                lag=value.get('lag', 0),
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
                       hardness: str = 'Hard', lag: int = 0) -> 'Dependency':
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
            existing.lag = lag
            existing.__post_init__()
            return existing

        dependency = Dependency(task_id=task_id, dep_type=dep_type,
                                hardness=hardness, lag=lag)
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

    def _children_by_parent(self) -> Dict[Optional[str], List[Task]]:
        """Group tasks by their parent, each group in current list order."""
        children: Dict[Optional[str], List[Task]] = {}
        for task in self.tasks:
            children.setdefault(task.parent_task_id, []).append(task)
        return children

    def _flatten(self, children: Dict[Optional[str], List[Task]]) -> List[Task]:
        """
        Rebuild the task list from a parent-to-children mapping.

        PARAMETERS:
        -----------
        children : Dict[Optional[str], List[Task]]
            Tasks grouped by parent, each group in the order wanted.

        RETURNS:
        --------
        List[Task]
            Every task, each one immediately followed by its descendants.

        DEVELOPMENT NOTES:
        ------------------
        Walking down from the roots only reaches tasks whose ancestry is
        intact. A task orphaned by a missing parent, or caught in a parent
        cycle, is never reached, so anything left over is appended rather than
        dropped - losing tasks during a reorder would be far worse than
        showing them in an odd place.
        """
        ordered: List[Task] = []
        emitted: Set[str] = set()

        def walk(parent_id: Optional[str]):
            """Emit a parent's children, each followed by its own."""
            for child in children.get(parent_id, []):
                if child.id in emitted:
                    continue
                emitted.add(child.id)
                ordered.append(child)
                walk(child.id)

        walk(None)

        for task in self.tasks:
            if task.id not in emitted:
                emitted.add(task.id)
                ordered.append(task)

        return ordered

    def get_siblings(self, task_id: str) -> List[Task]:
        """
        Get the tasks that share a parent with this one, in display order.

        RETURNS:
        --------
        List[Task]
            Includes the task itself. Root tasks are siblings of each other.
        """
        task = self.get_task_by_id(task_id)
        if task is None:
            return []
        return [t for t in self.tasks if t.parent_task_id == task.parent_task_id]

    def move_task(self, task_id: str, where: str) -> bool:
        """
        Move a task within the group of tasks that share its parent.

        PARAMETERS:
        -----------
        task_id : str
            The task to move.
        where : str
            'top', 'up', 'down' or 'bottom'.

        RETURNS:
        --------
        bool
            True when the task actually moved. False when it is already at
            that end of its group, so callers can skip a pointless redraw.

        DEVELOPMENT NOTES:
        ------------------
        Moving is confined to siblings: a sub-task reorders among the
        sub-tasks of its own parent and a root task among the root tasks.
        That keeps a move from silently reparenting anything, and matches
        what the row indentation shows.

        A task carries its sub-tasks with it, because the list is rebuilt
        from the hierarchy rather than by swapping two positions - moving a
        parent one row up would otherwise step it into the middle of its own
        children.
        """
        task = self.get_task_by_id(task_id)
        if task is None:
            return False

        children = self._children_by_parent()
        siblings = children.get(task.parent_task_id, [])
        if len(siblings) < 2:
            return False

        index = siblings.index(task)
        if where == 'top':
            new_index = 0
        elif where == 'up':
            new_index = index - 1
        elif where == 'down':
            new_index = index + 1
        elif where == 'bottom':
            new_index = len(siblings) - 1
        else:
            raise ValueError(f"Unknown move target: {where!r}")

        new_index = max(0, min(new_index, len(siblings) - 1))
        if new_index == index:
            return False

        siblings.insert(new_index, siblings.pop(index))
        self.tasks = self._flatten(children)
        return True

    def indent_target(self, task_id: str) -> Optional[Task]:
        """
        The task that indenting would move this one under.

        RETURNS:
        --------
        Optional[Task]
            The sibling directly above, or None when indenting is not
            possible: the first task in a group has nothing above it to go
            under, and a milestone cannot take sub-tasks because it marks a
            moment rather than spanning one.
        """
        task = self.get_task_by_id(task_id)
        if task is None:
            return None

        siblings = self.get_siblings(task_id)
        index = next((i for i, t in enumerate(siblings) if t.id == task_id),
                     None)
        if index is None or index == 0:
            return None

        above = siblings[index - 1]
        if above.is_milestone:
            return None
        return above

    def _descendant_ids(self, task_id: str) -> Set[str]:
        """Every task beneath this one, however deeply nested."""
        children = self._children_by_parent()
        found: Set[str] = set()
        stack = [task_id]
        while stack:
            current = stack.pop()
            for child in children.get(current, []):
                if child.id not in found:
                    found.add(child.id)
                    stack.append(child.id)
        return found

    def is_descendant(self, task_id: str, ancestor_id: str) -> bool:
        """
        Whether a task sits at or below another in the hierarchy.

        PARAMETERS:
        -----------
        task_id : str
            The task being tested.
        ancestor_id : str
            The task it might sit under.

        RETURNS:
        --------
        bool
            True when they are the same task, or task_id is a sub-task of
            ancestor_id at any depth.

        DEVELOPMENT NOTES:
        ------------------
        This is what keeps a task from depending on itself or on its own
        sub-tasks, which is a cycle however it is drawn. It lives here rather
        than on the widgets that ask: there were three copies, two of them
        dead, and the live pair walked the same chain in slightly different
        ways - one guarded against a parent cycle and the other did not.
        """
        if task_id == ancestor_id:
            return True
        return ancestor_id in self._ancestor_ids(task_id)

    def _ancestor_ids(self, task_id: str) -> Set[str]:
        """Every task this one sits under, walking up to the root."""
        found: Set[str] = set()
        current = self.get_task_by_id(task_id)
        while current is not None and current.parent_task_id:
            if current.parent_task_id in found:
                break                       # a parent cycle in a bad file
            found.add(current.parent_task_id)
            current = self.get_task_by_id(current.parent_task_id)
        return found

    def strip_ancestor_links(self, task_id: str) -> List[tuple]:
        """
        Drop links from a branch onto the tasks it now sits under.

        PARAMETERS:
        -----------
        task_id : str
            The task that just moved. Its descendants are covered too.

        RETURNS:
        --------
        List[tuple]
            The (successor_id, predecessor_id) links that were removed.

        DEVELOPMENT NOTES:
        ------------------
        A task cannot wait for something it is part of. A summary takes its
        finish from its children, so a child that must also start after that
        summary finishes has no possible date: every scheduling pass pushes
        the child out, which pushes the summary out with it, and the plan
        never settles.

        Indenting a task under its own predecessor is a natural thing to do -
        it is how a phase gets built out of the work that follows it - and
        refusing it left Indent greyed out on nearly every row of a normal
        plan. Dropping the link that has become meaningless is what planners
        do, and it is reported rather than done quietly.
        """
        branch = {task_id} | self._descendant_ids(task_id)
        removed = []

        for member_id in branch:
            member = self.get_task_by_id(member_id)
            if member is None:
                continue
            forbidden = self._ancestor_ids(member_id)
            for dep_id in list(member.dependency_ids):
                if dep_id in forbidden:
                    member.remove_dependency(dep_id)
                    removed.append((member_id, dep_id))

        return removed

    def can_indent(self, task_id: str) -> bool:
        """Whether the task can be moved a level deeper."""
        return self.indent_target(task_id) is not None

    def can_outdent(self, task_id: str) -> bool:
        """Whether the task can be moved a level shallower."""
        task = self.get_task_by_id(task_id)
        if task is None or not task.parent_task_id:
            return False
        return self.get_task_by_id(task.parent_task_id) is not None

    def indent_task(self, task_id: str) -> bool:
        """
        Make a task a sub-task of the sibling directly above it.

        RETURNS:
        --------
        bool
            True when the task moved.

        DEVELOPMENT NOTES:
        ------------------
        The task keeps its own sub-tasks, which follow it down a level
        because they point at it rather than at its parent.

        The new parent becomes a summary, so the next reschedule derives its
        dates from its children - including the task just moved under it.
        That is the point of indenting: a phase spans the work inside it.

        No repositioning is needed. The task already sits immediately after
        the sibling it is going under, so rebuilding the list from the
        hierarchy puts it at the end of that sibling's children.

        A link from the branch onto whatever it now sits under is dropped -
        see strip_ancestor_links. Indenting a task under its own predecessor
        is the ordinary way a phase gets built, so the link has to give way
        rather than the indent being refused.
        """
        new_parent = self.indent_target(task_id)
        if new_parent is None:
            return False

        task = self.get_task_by_id(task_id)
        task.parent_task_id = new_parent.id
        task.task_type = "Sub-Task"

        self.tasks = self._flatten(self._children_by_parent())
        self.strip_ancestor_links(task_id)
        return True

    def outdent_task(self, task_id: str) -> bool:
        """
        Move a task out to sit beside its parent.

        RETURNS:
        --------
        bool
            True when the task moved.

        DEVELOPMENT NOTES:
        ------------------
        A task lifted all the way out has no parent left, so it becomes a
        task in its own right; one that is still nested stays a sub-task of
        whatever it landed in.

        It keeps its own sub-tasks. Its old parent may stop being a summary
        entirely, in which case that parent goes back to holding its own
        dates rather than deriving them.

        As with indenting, position looks after itself: the task already
        follows its old parent in the list, so rebuilding from the hierarchy
        drops it in directly after that parent's remaining children.
        """
        if not self.can_outdent(task_id):
            return False

        task = self.get_task_by_id(task_id)
        parent = self.get_task_by_id(task.parent_task_id)

        task.parent_task_id = parent.parent_task_id
        task.task_type = "Task" if task.parent_task_id is None else "Sub-Task"

        self.tasks = self._flatten(self._children_by_parent())
        return True

    def structure_snapshot(self):
        """
        Capture the order, the hierarchy and the links, for undo.

        RETURNS:
        --------
        Tuple[List[Task], Dict[str, tuple], Dict[str, list]]
            The task list, each task's parent and type by ID, and a copy of
            each task's dependency links.

        DEVELOPMENT NOTES:
        ------------------
        Indenting changes parent_task_id and task_type on the Task objects
        themselves, which restoring an ordering alone would not put back -
        both lists hold the same objects.

        Links are captured too because indenting drops any that the move has
        made impossible; without them undo would put the task back where it
        was and leave the dependency gone for good.
        """
        return (
            list(self.tasks),
            {t.id: (t.parent_task_id, t.task_type) for t in self.tasks},
            {t.id: [Dependency(d.task_id, d.dep_type, d.hardness, d.lag)
                    for d in t.dependencies]
             for t in self.tasks},
        )

    def restore_structure(self, snapshot) -> None:
        """Put back an order, hierarchy and links from structure_snapshot."""
        order, parents, links = snapshot
        self.tasks = list(order)
        for task in self.tasks:
            if task.id in parents:
                task.parent_task_id, task.task_type = parents[task.id]
            if task.id in links:
                task.dependencies = [
                    Dependency(d.task_id, d.dep_type, d.hardness, d.lag)
                    for d in links[task.id]
                ]
        self._update_dates()

    @staticmethod
    def dropped_links(before, after) -> List[tuple]:
        """
        The links present in one structure snapshot and gone from another.

        RETURNS:
        --------
        List[tuple]
            (successor_id, predecessor_id) for each link that disappeared.
        """
        _order, _parents, old_links = before
        _order2, _parents2, new_links = after

        lost = []
        for task_id, links in old_links.items():
            kept = {d.task_id for d in new_links.get(task_id, [])}
            for link in links:
                if link.task_id not in kept:
                    lost.append((task_id, link.task_id))
        return lost

    def move_task_before(self, task_id: str, target_id: str) -> bool:
        """
        Put a task at the position a sibling currently occupies.

        PARAMETERS:
        -----------
        task_id : str
            The task being moved.
        target_id : str
            The sibling whose position it should take.

        RETURNS:
        --------
        bool
            True when the task moved. False when the two are not siblings,
            which is what a drop onto an unrelated row amounts to.

        DEVELOPMENT NOTES:
        ------------------
        This is what a drag-and-drop resolves to. Restricting it to siblings
        keeps dropping a row onto an unrelated one from reparenting it by
        accident; the drag handler refuses such a drop rather than guessing.
        """
        task = self.get_task_by_id(task_id)
        target = self.get_task_by_id(target_id)
        if task is None or target is None or task is target:
            return False
        if task.parent_task_id != target.parent_task_id:
            return False

        children = self._children_by_parent()
        siblings = children.get(task.parent_task_id, [])

        index = siblings.index(task)
        target_index = siblings.index(target)
        if index == target_index:
            return False

        siblings.insert(target_index, siblings.pop(index))
        self.tasks = self._flatten(children)
        return True
    
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
    
    def constrained_dates(self, task: Task):
        """
        Work out the dates a task's dependency links require.

        PARAMETERS:
        -----------
        task : Task
            The dependent task.

        RETURNS:
        --------
        Tuple[Optional[datetime], Optional[datetime]]
            The (start, end) the links require. Either may be None when
            nothing constrains it. Both are None when the task has no
            resolvable predecessors.

        DEVELOPMENT NOTES:
        ------------------
        The four types split into two groups. FS and SS decide when the task
        may start; FF and SF decide when it may finish. That is why this
        returns a pair - the old version returned a start date alone and so
        could not express a Finish-Finish link at all.

            FS  start  after the predecessor's finish
            SS  start  with the predecessor's start
            FF  finish after the predecessor's finish
            SF  finish once the predecessor has started

        End dates are inclusive here: a task ending on the 5th occupies the
        whole of the 5th, so an FS successor starts on the 6th. Milestones
        have no end date, so their finish is read as their own date.

        Lag shifts the result by that many days, and a negative lag is lead
        time, letting the successor overlap its predecessor.

        Where several links constrain the same edge, the hard ones win
        outright and the latest of them applies; otherwise the rubber links
        only contribute a floor, and the task keeps its own later date.
        """
        hard_starts, floor_starts = [], []
        hard_ends, floor_ends = [], []

        for dependency in task.dependencies:
            predecessor = self.get_task_by_id(dependency.task_id)
            if predecessor is None:
                continue

            predecessor_start = predecessor.start_date
            predecessor_end = predecessor.end_date or predecessor.start_date
            if predecessor_start is None:
                continue

            # A milestone marks a moment rather than occupying a day, so the
            # inclusive-end rule below does not apply to it: a task following
            # a milestone on the 15th starts on the 15th, not the 16th.
            finish = (predecessor_start if predecessor.is_milestone
                      else predecessor_end + timedelta(days=1))

            if dependency.dep_type == 'SS':
                required = predecessor_start
            elif dependency.dep_type == 'FS':
                required = finish
            elif dependency.dep_type == 'FF':
                required = predecessor_end
            else:                                   # SF
                required = predecessor_start

            required += timedelta(days=dependency.lag)

            if dependency.constrains_finish:
                target = hard_ends if dependency.hardness == 'Hard' else floor_ends
            else:
                target = hard_starts if dependency.hardness == 'Hard' else floor_starts
            target.append(required)

        start = self._resolve_constraint(hard_starts, floor_starts,
                                         task.start_date)
        end = self._resolve_constraint(hard_ends, floor_ends,
                                       task.end_date or task.start_date)
        return start, end

    @staticmethod
    def _resolve_constraint(hard_dates: List[datetime],
                            floor_dates: List[datetime],
                            current: Optional[datetime]) -> Optional[datetime]:
        """
        Reduce one edge's links to a single date.

        DEVELOPMENT NOTES:
        ------------------
        A hard link pins the date outright, so the latest of them wins. A
        rubber link is only a floor, so the task keeps its own date when that
        is already late enough.
        """
        if hard_dates:
            return max(hard_dates)
        if floor_dates:
            floor = max(floor_dates)
            if current is None or current < floor:
                return floor
            return current
        return None

    def constrained_start_date(self, task: Task) -> Optional[datetime]:
        """
        The start date a task's links require.

        DEVELOPMENT NOTES:
        ------------------
        Kept because the dialogs ask for a start date to fill in while a task
        is being edited. A task constrained only by its finish is turned back
        into a start by holding its duration.
        """
        start, end = self.constrained_dates(task)
        if start is not None:
            return start
        if end is None:
            return None

        span = self._task_span(task)
        return end - span

    @staticmethod
    def _task_span(task: Task) -> timedelta:
        """How long a task lasts, as the gap between its two dates."""
        if task.is_milestone or task.end_date is None:
            return timedelta(0)
        return max(task.end_date - task.start_date, timedelta(0))

    def apply_dependency_constraints(self, task: Task,
                                     preserve_duration: bool = True,
                                     forward_only: bool = False) -> bool:
        """
        Move a task so it satisfies its dependency links.

        PARAMETERS:
        -----------
        task : Task
            The task to reschedule.
        preserve_duration : bool
            Keep the task's length, moving both dates together.
        forward_only : bool
            Only ever move the task later. Used by the automatic pass; see
            the note below.

        RETURNS:
        --------
        bool
            True when the task moved.

        DEVELOPMENT NOTES:
        ------------------
        Called when a dependency is added or changed, which is what makes
        picking a predecessor set the dependent task's dates without the user
        typing them.

        A start constraint wins when both apply: FS and SS are the links that
        place a task, while FF and SF only hold its finish, so honouring the
        finish first would drag a task away from the predecessor it is meant
        to follow.

        forward_only exists because a hard link pins a date exactly, which is
        right when the user has just chosen a predecessor but wrong to apply
        unasked to a whole plan: it removes every gap. An imported
        GanttProject file is the clearest case - its dates come from replaying
        the file's working-day calendar, so a task sits after a weekend, and
        pinning it to the day after its predecessor threw that away and put
        the plan on dates GanttProject never showed. Repairing violations
        without closing deliberate slack is what "keep the links satisfied"
        actually asks for.
        """
        required_start, required_end = self.constrained_dates(task)
        if required_start is None and required_end is None:
            return False

        if forward_only:
            if required_start is not None and required_start < task.start_date:
                required_start = None
            current_end = task.end_date or task.start_date
            if required_end is not None and required_end < current_end:
                required_end = None
            if required_start is None and required_end is None:
                return False

        span = self._task_span(task)
        new_start, new_end = task.start_date, task.end_date

        if required_start is not None:
            new_start = required_start
            if preserve_duration and task.end_date is not None:
                new_end = required_start + span
        elif required_end is not None:
            new_end = required_end
            if preserve_duration:
                new_start = required_end - span

        if task.is_milestone:
            new_end = None

        if new_start == task.start_date and new_end == task.end_date:
            return False

        task.start_date = new_start
        task.end_date = new_end
        self._update_dates()
        return True

    #: Cap on the reschedule fixed-point loop. Auto-scheduling and roll-up
    #: feed each other - moving a leaf resizes its parent, which can move a
    #: task linked to that parent - so the pass repeats until nothing changes.
    #: A cycle in the links would otherwise never settle.
    MAX_SCHEDULE_PASSES = 12

    def normalise_milestones(self) -> bool:
        """
        Enforce the rules a milestone has to obey.

        RETURNS:
        --------
        bool
            True when something changed.

        DEVELOPMENT NOTES:
        ------------------
        A milestone marks a moment, so it carries no end date and takes no
        time. A milestone with sub-tasks would have to span them, which
        contradicts that, so anything parented to one is promoted to a task
        of its own rather than being silently dropped.
        """
        changed = False

        milestone_ids = {t.id for t in self.tasks if t.is_milestone}

        for task in self.tasks:
            if task.is_milestone and task.end_date is not None:
                task.end_date = None
                changed = True
            if task.parent_task_id in milestone_ids:
                task.parent_task_id = None
                task.task_type = "Task"
                changed = True

        return changed

    def roll_up_summaries(self) -> bool:
        """
        Make every task with sub-tasks span the work beneath it.

        RETURNS:
        --------
        bool
            True when any summary's dates or progress changed.

        DEVELOPMENT NOTES:
        ------------------
        A summary task brackets its children rather than holding work of its
        own, so its dates are derived: it starts with the earliest child and
        ends with the latest. That is also what keeps a sub-task inside its
        parent - the parent stretches rather than the child being clipped,
        which would lose work the user entered.

        Progress is weighted by duration, so a long child that is half done
        counts for more than a short one that is finished. Children are
        walked deepest first, so a summary of summaries totals what its own
        children have already settled on.
        """
        children = self._children_by_parent()
        changed = False

        for task in self._deepest_first():
            brood = children.get(task.id)
            if not brood:
                continue

            starts = [c.start_date for c in brood if c.start_date is not None]
            ends = [c.end_date or c.start_date for c in brood
                    if (c.end_date or c.start_date) is not None]
            if not starts or not ends:
                continue

            new_start, new_end = min(starts), max(ends)

            total = sum(max((c.end_date or c.start_date) - c.start_date,
                            timedelta(0)).days + 1 for c in brood)
            if total:
                done = sum(
                    (max((c.end_date or c.start_date) - c.start_date,
                         timedelta(0)).days + 1) * max(0, min(100, c.progress))
                    for c in brood
                )
                new_progress = int(round(done / total))
            else:
                new_progress = task.progress

            if (task.start_date != new_start or task.end_date != new_end
                    or task.progress != new_progress):
                task.start_date = new_start
                task.end_date = new_end
                task.progress = new_progress
                changed = True

        return changed

    def _deepest_first(self) -> List[Task]:
        """
        Tasks ordered so a child always comes before its parent.

        DEVELOPMENT NOTES:
        ------------------
        Depth is counted by walking up the parent chain, guarded against a
        cycle so a corrupted file cannot hang the sort.
        """
        def depth(task: Task) -> int:
            """How far below the root a task sits."""
            seen = {task.id}
            level = 0
            current = task
            while current.parent_task_id:
                parent = self.get_task_by_id(current.parent_task_id)
                if parent is None or parent.id in seen:
                    break
                seen.add(parent.id)
                current = parent
                level += 1
            return level

        return sorted(self.tasks, key=depth, reverse=True)

    def _schedule_order(self) -> List[Task]:
        """
        Tasks ordered so a predecessor comes before the tasks that follow it.

        DEVELOPMENT NOTES:
        ------------------
        A depth-first topological sort with an explicit stack, so a deep
        chain cannot exhaust recursion, and an in-progress set so a cycle
        stops rather than looping. Anything caught in a cycle still comes out,
        just in an order that satisfies only part of its links - dropping it
        would remove the task from the schedule entirely.
        """
        ordered: List[Task] = []
        placed: Set[str] = set()
        in_progress: Set[str] = set()

        for root in self.tasks:
            if root.id in placed:
                continue
            stack = [(root, False)]
            while stack:
                task, expanded = stack.pop()
                if expanded:
                    in_progress.discard(task.id)
                    if task.id not in placed:
                        placed.add(task.id)
                        ordered.append(task)
                    continue
                if task.id in placed or task.id in in_progress:
                    continue
                in_progress.add(task.id)
                stack.append((task, True))
                for dep_id in task.dependency_ids:
                    predecessor = self.get_task_by_id(dep_id)
                    if (predecessor is not None
                            and predecessor.id not in placed
                            and predecessor.id not in in_progress):
                        stack.append((predecessor, False))

        return ordered

    def reschedule(self) -> bool:
        """
        Settle the whole plan: apply every link, then roll summaries up.

        RETURNS:
        --------
        bool
            True when anything moved.

        DEVELOPMENT NOTES:
        ------------------
        This is the auto-scheduling the dependency types exist for: moving a
        predecessor drags everything that follows it, rather than the links
        being applied once when they are created and never again.

        Order matters. Links are applied to the leaves in predecessor-first
        order so a chain settles in one sweep, then summaries are rolled up
        from their children. Summaries are skipped by the link pass because
        their dates come from below; letting a link move one would put it out
        of step with the children it is supposed to bracket.

        The pass only ever moves a task later - see forward_only on
        apply_dependency_constraints. Choosing a predecessor in the dialog
        still pins the date exactly; it is applying that to a whole plan
        unasked that destroys imported schedules.

        The two feed each other - a resized summary can move a task linked to
        it - so the pass repeats until nothing changes, capped so a cycle in
        the links cannot spin here forever.
        """
        changed = False

        if self.normalise_milestones():
            changed = True

        for _ in range(self.MAX_SCHEDULE_PASSES):
            summary_ids = self.get_summary_task_ids()

            moved = False
            for task in self._schedule_order():
                if task.id in summary_ids:
                    continue
                if self.apply_dependency_constraints(task, forward_only=True):
                    moved = True

            if self.roll_up_summaries():
                moved = True

            if not moved:
                break
            changed = True
        else:
            logger.warning(
                "Rescheduling %r did not settle in %d passes; the links "
                "probably contain a cycle",
                self.name, self.MAX_SCHEDULE_PASSES
            )

        if changed:
            self._update_dates()
        return changed

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
