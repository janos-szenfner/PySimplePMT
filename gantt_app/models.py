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

from gantt_app.priority import PRIORITY_LEVELS, DEFAULT_PRIORITY
from gantt_app.workdaycalendar import WorkingCalendar, default_calendar


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

#: Task types in the new hierarchy
TASK_TYPES = ('Phase', 'Deliverable', 'Task', 'Subtask', 'Milestone')

#: Task type display labels
TASK_TYPE_LABELS = {
    'Phase': 'Phase',
    'Deliverable': 'Deliverable', 
    'Task': 'Task',
    'Subtask': 'Subtask',
    'Milestone': 'Milestone',
}

#: Container types that have children and roll up dates/progress
CONTAINER_TYPES = ('Phase', 'Deliverable')

#: Work types that represent actual work items
WORK_TYPES = ('Task', 'Subtask')

#: Types that can have subtasks
PARENT_TYPES = ('Phase', 'Deliverable', 'Task')

#: Types that cannot have children (leaf nodes)
LEAF_TYPES = ('Subtask', 'Milestone')


def rolled_up_progress(parent, children) -> int:
    """
    The completion a parent takes from the work under it.

    PARAMETERS:
    -----------
    parent : Task
        The task whose progress is being worked out. Its type decides which
        rule applies.
    children : list
        Its direct children. Only these; the rule for each level is written
        in terms of the level below it, and the levels below that have
        already settled by the time this is asked - see roll_up_summaries.

    RETURNS:
    --------
    int
        A percentage from 0 to 100. An empty container is 0.

    WHAT THE RULES ARE:
    -------------------
    Each level of the plan counts what is under it in the way that suits
    what that level is.

    A Subtask is a tick on a checklist: done or not, nothing in between.
    See Task.is_completed.

    A Task with sub-tasks reads how many of them are ticked. It is a
    checklist, and a checklist is counted, not weighted - four sub-tasks of
    an hour each are four boxes like any other four. A Task without
    sub-tasks keeps the percentage the user typed on it.

    A Deliverable weights its tasks by how long they run, so a fortnight's
    work counts for more towards it than an afternoon's. Where nothing under
    it has any length - all milestones, say - there is nothing to weight by
    and it averages them instead.

    A Phase averages its deliverables evenly. Deliverables are the units a
    phase is scoped in, and one being longer than another is not a reason
    for it to count for more of the phase.

    DEVELOPMENT NOTES:
    ------------------
    Percentages are clamped as they are read. A child holding something
    outside 0 to 100 - which nothing should write, but an imported file can
    carry - would otherwise pull its parent outside it too.

    The answer is rounded to a whole percent, which is the width of the
    field it is stored in and finer than the chart can draw.
    """
    if not children:
        return 0

    percentages = [max(0, min(100, child.progress)) for child in children]

    if parent.task_type == 'Task':
        finished = sum(1 for child in children if child.is_completed)
        return int(round(finished / len(children) * 100))

    if parent.task_type == 'Phase':
        return int(round(sum(percentages) / len(percentages)))

    # A Deliverable, and anything else that has come to have children
    lengths = [child.duration_days or 0 for child in children]
    total = sum(lengths)
    if total <= 0:
        return int(round(sum(percentages) / len(percentages)))
    return int(round(
        sum(length * percent for length, percent in zip(lengths, percentages))
        / total
    ))


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
        task_type: Type of task - one of TASK_TYPES (Phase, Deliverable, Task, Subtask, Milestone)
        parent_task_id: ID of parent task (for hierarchical organization)
        duration: Duration in days (can be manually set)
        priority: Task priority level
        shape: Visual shape for the task
        show_in_timeline: Whether to show in timeline view
        earliest_begin: Earliest possible start date
        scheduling_options: Scheduling mode for the task
        details: Additional notes/details about the task
        is_milestone: Legacy flag, now determined by task_type='Milestone'
    
    DEVELOPMENT NOTES:
    ------------------
    - task_type can be 'Phase', 'Deliverable', 'Task', 'Subtask', or 'Milestone'
    - Phase and Deliverable are container types that roll up dates and progress from children
    - Task is the primary work unit with duration, start/end dates, and completion
    - Subtask is a micro-action under a Task for basic completion tracking
    - Milestone is a zero-duration marker representing key events
    - is_milestone flag is maintained for backward compatibility but task_type='Milestone' is authoritative
    """
    id: str
    name: str
    start_date: datetime
    end_date: Optional[datetime] = None
    progress: int = 0
    dependencies: List['Dependency'] = field(default_factory=list)
    color: str = "#1f6aa5"
    task_type: str = "Task"
    parent_task_id: Optional[str] = None
    duration: Optional[int] = None
    priority: str = DEFAULT_PRIORITY
    shape: str = "Default"
    show_in_timeline: bool = True
    earliest_begin: Optional[datetime] = None
    scheduling_options: str = "End date is calculated"
    details: str = ""
    is_milestone: bool = False
    
    def __post_init__(self):
        """
        Validate task data after initialization.

        DEVELOPMENT NOTES:
        ------------------
        Dependencies are coerced into Dependency objects here, so callers
        may still pass a plain list of task IDs. That keeps every existing
        `dependencies=[task.id]` call working and lets projects saved before
        dependencies carried a type load unchanged.
        
        Handles backward compatibility for legacy is_milestone flag and
        old task_type values ('Task', 'Subtask').
        """
        if not self.name:
            raise ValueError("Task name cannot be empty")
        if self.progress < 0 or self.progress > 100:
            raise ValueError("Progress must be between 0 and 100")
        
        # Handle backward compatibility for legacy task types
        if self.task_type == "Sub-Task":
            self.task_type = "Subtask"
        
        # Synchronize is_milestone with task_type for backward compatibility
        if self.task_type == "Milestone":
            self.is_milestone = True
            self.end_date = None  # Milestones have no duration
        elif self.is_milestone and self.task_type != "Milestone":
            # Legacy milestone flag: convert to new type
            self.task_type = "Milestone"
            self.end_date = None
        
        # For container types (Phase, Deliverable), ensure they don't have end_date if they shouldn't
        # Actually, containers CAN have end dates as they roll up from children
        
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

    @property
    def is_container(self) -> bool:
        """Whether this task is a container type (Phase or Deliverable)."""
        return self.task_type in CONTAINER_TYPES

    @property
    def is_work_item(self) -> bool:
        """Whether this task is a work item (Task or Subtask)."""
        return self.task_type in WORK_TYPES

    @property
    def can_have_children(self) -> bool:
        """Whether this task type can have child tasks."""
        return self.task_type in PARENT_TYPES

    @property
    def is_leaf(self) -> bool:
        """Whether this task is a leaf node (cannot have children)."""
        return self.task_type in LEAF_TYPES

    @property
    def is_completed(self) -> bool:
        """
        Whether this counts as finished when its parent totals its children.

        DEVELOPMENT NOTES:
        ------------------
        A sub-task is a tick on a checklist: done or not. The editor offers
        it as a tick box rather than a percentage, so a sub-task entered here
        holds 0 or 100 and nothing else.

        Anything short of 100 is unfinished, which is what decides a
        sub-task that arrived from an imported file at some middling
        percentage. It is not rewritten - the number is the source file's to
        state - but a job that is half done is not a job that is done.
        """
        return self.progress >= 100

    @property
    def effective_milestone(self) -> bool:
        """Whether this task behaves as a milestone (zero duration)."""
        return self.task_type == "Milestone" or self.is_milestone

    @property
    def can_edit_dates(self) -> bool:
        """Whether dates can be directly edited (not rolled up from children)."""
        return not self.is_container

    @property
    def can_edit_progress(self) -> bool:
        """Whether progress can be directly edited (not rolled up from children)."""
        return not self.is_container

    @property
    def can_have_dependencies(self) -> bool:
        """Whether this task type can have dependencies."""
        # Container types can have dependencies, but leaf nodes like Subtasks might not
        return self.task_type != "Subtask"  # Subtasks typically don't have complex dependencies

    @property
    def can_edit_duration(self) -> bool:
        """Whether duration can be edited."""
        # Milestones and containers have fixed/rolled up duration
        return not self.effective_milestone and not self.is_container

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
        Create a new regular task (Work Unit).

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
            task_type="Task",
            is_milestone=False
        )
    
    @classmethod
    def create_milestone(cls, name: str, date: datetime, 
                        color: str = "#e74c3c", 
                        dependencies: List[str] = None,
                        task_id: str = None) -> 'Task':
        """
        Create a new milestone (zero-duration key event marker).

        PARAMETERS:
        -----------
        task_id : str, optional
            Identifier to use; see create_task.
        """
        return cls(
            id=task_id or str(uuid.uuid4()),
            name=name,
            start_date=date,
            end_date=None,  # Milestones have no end date (zero duration)
            progress=0,
            dependencies=dependencies or [],
            color=color,
            task_type="Milestone",
            is_milestone=True,
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
            task_type="Subtask",
            parent_task_id=parent_task.id
        )
    
    @classmethod
    def create_phase(cls, name: str, start_date: datetime, 
                     color: str = "#34495e", progress: int = 0,
                     dependencies: List[str] = None, task_id: str = None) -> 'Task':
        """
        Create a new Phase (high-level lifecycle container).
        
        PARAMETERS:
        -----------
        name : str
            Name of the phase
        start_date : datetime
            Start date of the phase
        color : str, optional
            Hex color for visualization (default: gray)
        progress : int, optional
            Initial progress percentage (default: 0)
        dependencies : List[str], optional
            List of task IDs this phase depends on
        task_id : str, optional
            Identifier to use; see create_task.
        
        RETURNS:
        --------
        Task
            A new Phase with task_type='Phase' and no parent
        """
        return cls(
            id=task_id or str(uuid.uuid4()),
            name=name,
            start_date=start_date,
            end_date=None,  # Will be rolled up from children
            progress=progress,
            dependencies=dependencies or [],
            color=color,
            task_type="Phase",
            is_milestone=False,
            parent_task_id=None
        )
    
    @classmethod
    def create_deliverable(cls, name: str, start_date: datetime, 
                           color: str = "#28a745", progress: int = 0,
                           dependencies: List[str] = None, task_id: str = None) -> 'Task':
        """
        Create a new Deliverable (major work package / scope output).
        
        PARAMETERS:
        -----------
        name : str
            Name of the deliverable
        start_date : datetime
            Start date of the deliverable
        color : str, optional
            Hex color for visualization (default: green)
        progress : int, optional
            Initial progress percentage (default: 0)
        dependencies : List[str], optional
            List of task IDs this deliverable depends on
        task_id : str, optional
            Identifier to use; see create_task.
        
        RETURNS:
        --------
        Task
            A new Deliverable with task_type='Deliverable' and no parent
        """
        return cls(
            id=task_id or str(uuid.uuid4()),
            name=name,
            start_date=start_date,
            end_date=None,  # Will be rolled up from children
            progress=progress,
            dependencies=dependencies or [],
            color=color,
            task_type="Deliverable",
            is_milestone=False,
            parent_task_id=None
        )
    
    @property
    def working_calendar(self) -> WorkingCalendar:
        """
        The calendar this task's own arithmetic is measured against.

        DEVELOPMENT NOTES:
        ------------------
        The standard Monday-to-Friday week. A task does not carry a calendar
        of its own: it is a property of the plan, so Project holds it and
        passes it to everything that schedules. What a task can answer on its
        own - how long it is - is answered against the standard week, which is
        what every project has unless a file said otherwise.
        """
        return default_calendar()

    @property
    def effective_start_date(self) -> datetime:
        """
        The day work actually begins.

        A task placed on a Saturday cannot start on it, so the start is
        pushed forward to the next working day. Project.enforce_working_calendar
        writes that back onto the task; this answers it for a task that has
        not been through the plan yet.
        """
        return self.working_calendar.get_next_working_day(self.start_date)

    @property
    def duration_days(self) -> Optional[int]:
        """
        How much working effort the task holds, in days.

        RETURNS:
        --------
        Optional[int]
            Working days between start_date and end_date, both included, or
            0 for milestones and container types, or None if end_date is not
            set. If duration is manually set, that value is returned.

        DEVELOPMENT NOTES:
        ------------------
        Working days, not calendar days: a task running Thursday to the
        following Wednesday holds five days of work, not seven, because
        nothing was worked on the Saturday or the Sunday. That is the whole
        point of the working calendar - see gantt_app.workdaycalendar - and it
        is why a task crossing a weekend keeps its duration while its bar
        stretches. total_elapsed_days answers the other one.

        A span falling entirely on non-working days holds no work at all, but
        a task is at least a day long, so the count has a floor of one. A
        start date on a weekend is what puts a task there, and
        Project.enforce_working_calendar moves it off.
        """
        # The type is answered before the stored number. A Phase or a
        # Deliverable holds no work of its own whatever is written on it, and
        # the task form writes a duration onto everything it saves - so a
        # container edited once carried a number that stopped following its
        # children and then disagreed with its own two dates.
        if self.effective_milestone or self.is_container:
            return 0
        if self.duration is not None:
            return self.duration
        if self.end_date is None:
            return None
        worked = self.working_calendar.working_days_between(self.start_date,
                                                            self.end_date)
        return max(worked, 1)

    @property
    def total_elapsed_days(self) -> Optional[int]:
        """
        How many calendar days the task spans, weekends included.

        RETURNS:
        --------
        Optional[int]
            Days from start to end inclusive, or 0 for a milestone, or None
            when there is no end date. This is the span the chart draws;
            duration_days is the effort inside it.
        """
        if self.effective_milestone:
            return 0
        if self.end_date is None:
            return None
        return self.working_calendar.elapsed_days(self.start_date,
                                                  self.end_date)

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
            'parent_task_id': self.parent_task_id,
            'duration': self.duration,
            'priority': self.priority,
            'shape': self.shape,
            'show_in_timeline': self.show_in_timeline,
            'earliest_begin': self.earliest_begin.isoformat() if self.earliest_begin else None,
            'scheduling_options': self.scheduling_options,
            'details': self.details
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
        
        # Handle earliest_begin (could be string, datetime, or None)
        earliest_begin = data.get('earliest_begin')
        if isinstance(earliest_begin, str):
            try:
                earliest_begin = datetime.fromisoformat(earliest_begin)
            except (ValueError, TypeError):
                earliest_begin = None
        
        # Handle backward compatibility for scheduling_options
        scheduling_options = data.get('scheduling_options', 'End date is calculated')
        # Map old values to new ones
        old_to_new = {
            'in this dialog': 'End date is calculated',
            'auto': 'End date is calculated',
            'manual': 'End date is calculated'
        }
        scheduling_options = old_to_new.get(scheduling_options, scheduling_options)
        
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
            parent_task_id=data.get('parent_task_id', None),
            duration=data.get('duration', None),
            priority=data.get('priority', DEFAULT_PRIORITY),
            shape=data.get('shape', 'Default'),
            show_in_timeline=data.get('show_in_timeline', True),
            earliest_begin=earliest_begin,
            scheduling_options=scheduling_options,
            details=data.get('details', '')
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
        calendar: Which days the project works; see enforce_working_calendar

    DEVELOPMENT NOTES:
    ------------------
    The calendar belongs to the project rather than to each task: which days
    are worked is a property of the plan, and a plan whose tasks each held
    their own idea of the week could not be scheduled at all. Everything that
    turns a duration into dates goes through it - see gantt_app.workdaycalendar.
    """
    name: str
    tasks: List[Task] = field(default_factory=list)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    calendar: WorkingCalendar = field(default_factory=WorkingCalendar)

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
        task.task_type = "Subtask"

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
        task.task_type = "Task" if task.parent_task_id is None else "Subtask"

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
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'calendar': self.calendar.to_dict()
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
        
        # Create empty project first. A file saved before projects carried a
        # calendar has no calendar block, and WorkingCalendar.from_dict answers
        # the standard week for it - which is what those plans were built on.
        project = cls(
            name=data['name'],
            start_date=start_date,
            end_date=end_date,
            tasks=[],  # Start with empty tasks to avoid __post_init__ updating dates prematurely
            calendar=WorkingCalendar.from_dict(data.get('calendar'))
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

            required = self._shift_working_days(required, dependency.lag)

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

    def _shift_working_days(self, moment: datetime, days: int) -> datetime:
        """
        Move a date by a number of working days.

        PARAMETERS:
        -----------
        moment : datetime
            The date a link requires before its lag is applied.
        days : int
            Working days of lag; negative is lead time.

        RETURNS:
        --------
        datetime
            The date that many working days away.

        DEVELOPMENT NOTES:
        ------------------
        Working days, because every other length in the application is. Added
        as calendar days, a lag of one or two over a weekend did nothing at
        all: the date landed on the Saturday or Sunday and was pushed back to
        the Monday it would have had with no lag, so "wait two days after this
        finishes" was a wait of nought.

        The calendar's arithmetic is inclusive - a span of one day ends where
        it starts - so shifting by n days asks it for n + 1.
        """
        if not days:
            return moment
        if days > 0:
            return self.calendar.add_working_days(moment, days + 1)
        return self.calendar.subtract_working_days(moment, -days + 1)

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

        A floor still applies when a hard link is present. It used to be
        dropped: a task pinned by a hard link to one predecessor and floored
        by a rubber link to another was placed on the hard date even when that
        fell before the rubber predecessor had finished - so the rubber link
        the user had set was quietly broken. Both are constraints, and the
        date that satisfies both is the later of the two.
        """
        if hard_dates:
            pinned = max(hard_dates)
            if floor_dates:
                return max(pinned, max(floor_dates))
            return pinned
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
            return self.calendar.get_next_working_day(start)
        if end is None:
            return None

        return self.calendar.subtract_working_days(end,
                                                   self.working_duration(task))

    def working_duration(self, task: Task) -> int:
        """
        How many working days of effort a task holds, against this calendar.

        RETURNS:
        --------
        int
            The task's own duration when it states one, otherwise the working
            days its dates cover. Zero for a milestone, which takes no time.
            Never less than one for anything else: a task is at least a day.

        DEVELOPMENT NOTES:
        ------------------
        Task.duration_days answers nearly the same thing, but against the
        standard week rather than this project's calendar - a task cannot know
        which plan it is in. Scheduling has to use the plan's calendar, so
        anything moving a task asks here.
        """
        if task.is_milestone:
            return 0
        # A container spans its children, so its dates are the answer and a
        # number stored on it is not - see Task.duration_days
        if task.duration is not None and not task.is_container:
            return max(int(task.duration), 1)
        if task.end_date is None:
            return 1
        return max(self.calendar.working_days_between(task.start_date,
                                                      task.end_date), 1)

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

        A moved task keeps its working duration, not its calendar span. Moving
        a task from a Monday to a Thursday puts a weekend inside it, and adding
        the old span of calendar days back on spent two days of it on the
        Saturday and Sunday - the task lost two days of work by being moved.
        The dates are placed on working days for the same reason: a link that
        lands a task on a Saturday means it starts on the Monday.
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

        duration = self.working_duration(task)
        new_start, new_end = task.start_date, task.end_date

        # Both edges held is not a conflict to resolve - it is a span being
        # stated. Start-Start onto the first task and Finish-Finish onto the
        # last is how a row is made to cover a stretch of the plan, and there
        # is nothing else the pair can mean. Honouring only the start and
        # putting the old length back left such a row the length of whatever
        # it happened to be before, which for a deliverable linked across two
        # tasks was the length of the first one.
        holds_span = (required_start is not None and required_end is not None
                      and not task.is_milestone
                      and required_end >= required_start)

        if holds_span:
            new_start = self.calendar.get_next_working_day(required_start)
            new_end = self.calendar.get_next_working_day(required_end)
            if new_end < new_start:
                # Both landed in the same weekend
                new_end = new_start
        elif required_start is not None:
            if required_end is not None:
                # A finish required before the start is not a span but a
                # contradiction. The start still places the task, and saying
                # so beats silently drawing a bar that runs backwards.
                logger.warning(
                    "Task %r is required to finish on %s, before the %s its "
                    "links require it to start; keeping its length",
                    task.name, required_end.date(), required_start.date()
                )
            new_start = self.calendar.get_next_working_day(required_start)
            if preserve_duration and task.end_date is not None:
                new_end = self.calendar.add_working_days(new_start, duration)
        elif required_end is not None:
            # Forward, not back, for a finish landing on a weekend. A link
            # says a task may not finish before a date, so pulling it back to
            # the Friday would break the link it is being moved to satisfy.
            new_end = self.calendar.get_next_working_day(required_end)
            if preserve_duration:
                new_start = self.calendar.subtract_working_days(new_end,
                                                                duration)

        if task.is_milestone:
            new_end = None

        if new_start == task.start_date and new_end == task.end_date:
            return False

        task.start_date = new_start
        task.end_date = new_end

        # A span redefines how much the task holds, so a duration written onto
        # it has to follow. Left alone, the stored number and the two dates
        # disagreed, and the next pass over the working calendar rebuilt the
        # finish from the stale number and undid the span - the two rules then
        # took turns until the reschedule loop gave up and reported a cycle
        # that was not there.
        if holds_span and task.duration is not None:
            task.duration = max(
                self.calendar.working_days_between(new_start, new_end), 1)

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

    def apply_calendar(self, calendar: WorkingCalendar) -> bool:
        """
        Change which days the project works, holding what every task contains.

        PARAMETERS:
        -----------
        calendar : WorkingCalendar
            The calendar to schedule on from now on.

        RETURNS:
        --------
        bool
            True when anything moved.

        DEVELOPMENT NOTES:
        ------------------
        Every task's working duration is read under the *old* calendar and its
        dates rebuilt under the new one, so a day that has just become a
        holiday pushes finishes out rather than quietly eating the work that
        was planned for it.

        That is the whole reason this exists rather than the caller assigning
        to `calendar` and calling reschedule. enforce_working_calendar derives
        a task's duration from its dates every time, which is what makes it
        idempotent and safe to run in a loop - but it also means that adding a
        holiday in the middle of a ten day task would have left the task where
        it was, now holding nine days of work. The task got shorter because the
        calendar changed, which is backwards: the work does not go away, the
        finish moves.

        Containers are skipped; their dates come from the children, which are
        rebuilt here, and roll_up_summaries brings them along afterwards.
        """
        durations = {task.id: self.working_duration(task)
                     for task in self.tasks}

        self.calendar = calendar
        moved = False

        for task in self.tasks:
            if task.is_container:
                continue

            new_start = calendar.get_next_working_day(task.start_date)
            if task.effective_milestone or task.end_date is None:
                new_end = None
            else:
                new_end = calendar.add_working_days(new_start,
                                                    durations[task.id])

            if new_start == task.start_date and new_end == task.end_date:
                continue

            task.start_date = new_start
            task.end_date = new_end
            moved = True

        settled = self.reschedule()
        if moved or settled:
            self._update_dates()
        return moved or settled

    def set_holiday_countries(self, codes) -> bool:
        """
        Observe the public holidays of the given countries.

        PARAMETERS:
        -----------
        codes : Iterable[str]
            ISO 3166-1 alpha-2 country codes. A date that is a public holiday
            in any of them becomes a non-working day; an empty list observes
            none and leaves the plan on weekends.

        RETURNS:
        --------
        bool
            True when the plan moved.
        """
        calendar = WorkingCalendar(
            non_working_days=self.calendar.non_working_days,
            holidays=self.calendar.holidays,
            recurring_holidays=self.calendar.recurring_holidays,
            countries=codes,
        )
        return self.apply_calendar(calendar)

    def enforce_working_calendar(self) -> bool:
        """
        Put every task on working days, without changing what it holds.

        RETURNS:
        --------
        bool
            True when any task moved.

        DEVELOPMENT NOTES:
        ------------------
        Three rules. Two come from gantt_app.workdaycalendar:

          * A task cannot start on a non-working day, so a start landing on a
            Saturday is pushed to the Monday.
          * A task's finish is its start plus its working duration, walked
            over the calendar. A task crossing a weekend therefore ends
            further out without holding any more work, and one that had been
            given a finish on a Sunday ends on the Friday instead.

        The third is the task's own earliest begin date, which is a floor on
        when the work can start. The form has offered it, and the file has
        saved it, since before there was a scheduler to read it - so a date
        typed there did nothing at all.

        The duration is read before either date moves and written back after,
        which is what makes this leave the effort alone: the task ends up
        somewhere else in calendar time holding exactly the work it held.

        Containers are skipped. A Phase or a Deliverable takes its dates from
        the children beneath it - see roll_up_summaries - and those are on
        working days by the time this is done with them, so bracketing them
        cannot land on a weekend.

        Running twice changes nothing: a task already on working days spanning
        its own duration is left exactly where it is, which is what lets this
        sit inside the reschedule loop.
        """
        changed = False

        for task in self.tasks:
            if task.is_container:
                continue

            wanted = task.start_date
            if task.earliest_begin is not None and wanted < task.earliest_begin:
                # A date the user has said the work cannot begin before -
                # material not delivered, a gate not passed. It is a floor,
                # so it only ever pushes a task later.
                logger.debug("%r cannot begin before %s; moving it there",
                             task.name, task.earliest_begin.date())
                wanted = task.earliest_begin

            new_start = self.calendar.get_next_working_day(wanted)

            if task.effective_milestone:
                new_end = None
            elif task.end_date is None:
                # Nothing states how long it is, so there is no finish to work
                # out - only the start to move off the weekend.
                new_end = None
            else:
                duration = self.working_duration(task)
                new_end = self.calendar.add_working_days(new_start, duration)

            if new_start == task.start_date and new_end == task.end_date:
                continue

            logger.debug("Working calendar moved %r from %s-%s to %s-%s",
                         task.name, task.start_date, task.end_date,
                         new_start, new_end)
            task.start_date = new_start
            task.end_date = new_end
            changed = True

        return changed

    def roll_up_summaries(self) -> bool:
        """
        Make every task with children span the work beneath it with new rollup rules.

        RETURNS:
        --------
        bool
            True when any summary's dates or progress changed.

        DEVELOPMENT NOTES:
        ------------------
        Anything with children spans them: its start is the earliest of
        theirs and its end the latest. Which rule turns their progress into
        its own is rolled_up_progress's to say.

        Children are walked deepest first, so a parent totals children that
        have already settled - the bottom-up cascade a change to one
        sub-task sets off, reaching the phase above it in the same pass.
        """
        children = self._children_by_parent()
        changed = False

        for task in self._deepest_first():
            brood = children.get(task.id)
            if not brood:
                # An empty Phase or Deliverable holds no work, so none of it
                # is done. Its dates are left alone: there is nothing under
                # it to take them from, and the ones it was given are the
                # only ones it has.
                if task.is_container and task.progress != 0:
                    task.progress = 0
                    changed = True
                continue

            # Calculate new start and end dates for container types
            starts = [c.start_date for c in brood if c.start_date is not None]
            ends = [c.end_date or c.start_date for c in brood
                    if (c.end_date or c.start_date) is not None]
            
            if not starts or not ends:
                continue

            new_start, new_end = min(starts), max(ends)

            new_progress = rolled_up_progress(task, brood)

            # Anything with children brackets them, whatever it is called.
            #
            # Rolling the dates up for Phase and Deliverable alone left every
            # other parent holding whatever dates it happened to have: a
            # plain Task with sub-tasks stopped spanning them, and so did
            # every parent the importers build - a Mermaid section, a
            # spreadsheet phase, a nested GanttProject task all arrive as
            # ordinary Tasks. Which progress rule applies still goes by type.
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

        The working calendar is enforced inside the loop, between the two. A
        link can land a task on a Saturday, and a task pushed off a Saturday
        moves its summary, so doing it once before or after the loop left one
        of the two disagreeing with the calendar. It only ever moves a task
        forward onto a working day, so it cannot fight the link pass.
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

            if self.enforce_working_calendar():
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
            """
            Working length of a task; milestones take no time.

            Working days rather than calendar days, which is what makes the
            weekend gaps this docstring talks about drop out. Measured in
            calendar days, a chain that happens to straddle more weekends
            outranked a chain holding more actual work.
            """
            if task.is_milestone or task.end_date is None:
                return 0
            return self.calendar.working_days_between(task.start_date,
                                                      task.end_date)

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
