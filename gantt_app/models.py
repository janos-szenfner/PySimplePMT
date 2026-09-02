"""
Data models for the Gantt Project Management Tool.

Contains the Task and Project classes that form the core data structure.
"""

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
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
from gantt_app.resource_model import ResourceRepository
from gantt_app.taskstyle import TaskStyle
from gantt_app.calendarregistry import CalendarRegistry, default_registry
from gantt_app.workdaycalendar import (
    WorkingCalendar, as_date, default_calendar,
)


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

#: Which end of the plan its dates are worked out from.
#:
#: 'start' schedules forward: everything begins as soon as its links allow,
#: which is what a plan does unless somebody says otherwise. 'finish'
#: schedules backward from a deadline: everything happens as late as it can
#: without missing it, which is what a plan does when the date is the fixed
#: thing and the work has to fit before it.
SCHEDULE_FROM_START = 'start'
SCHEDULE_FROM_FINISH = 'finish'
SCHEDULE_FROM = (SCHEDULE_FROM_START, SCHEDULE_FROM_FINISH)

#: What a project's priority may be, and what it is when nobody has said.
#: The range is Microsoft Project's, so a plan moved between the two keeps
#: its number rather than being rescaled.
MIN_PROJECT_PRIORITY = 1
MAX_PROJECT_PRIORITY = 1000
DEFAULT_PROJECT_PRIORITY = 500

#: What a lag is counted in.
#:
#: 'days' is a number of working days. 'percent' is a share of the
#: predecessor's own duration, which is how a plan says "start this when the
#: one before it is half done" without having to work out what half of it is
#: and re-work it every time that task's length changes.
LAG_DAYS = 'days'
LAG_PERCENT = 'percent'
LAG_UNITS = (LAG_DAYS, LAG_PERCENT)

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
TASK_TYPES = ('Phase', 'Task', 'Subtask', 'Milestone')

#: Available status values for tasks
TASK_STATUSES = ('Draft', 'Active')

#: Task type display labels
TASK_TYPE_LABELS = {
    'Phase': 'Phase',
    'Task': 'Task',
    'Subtask': 'Subtask',
    'Milestone': 'Milestone',
}

#: What a type that is no longer offered becomes when a plan carrying it is
#: opened.
#:
#: Deliverable was a level between Phase and Task. Plans, saved files and
#: imports still carry it, and a row whose type is not one this application
#: knows would be a row nothing could decide anything about - which rule
#: rolls its progress up, whether it may hold children, what it is called in
#: the Type column. Read as the nearest thing that is still offered instead,
#: which is a Task: it holds work, it may have rows beneath it, and a phase
#: full of them reads as it did.
RETIRED_TASK_TYPES = {
    'Deliverable': 'Task',
    'Sub-Task': 'Subtask',
}

#: Container types that have children and roll up dates/progress
CONTAINER_TYPES = ('Phase',)

#: Work types that represent actual work items
WORK_TYPES = ('Task', 'Subtask')

#: Types that can have subtasks
PARENT_TYPES = ('Phase', 'Task')

#: Types that cannot have children (leaf nodes)
LEAF_TYPES = ('Subtask', 'Milestone')

#: What a task is allowed to be, by the type of the parent it sits under.
#:
#: The types describe a three-level plan - Phase > Task > Subtask - with a
#: Milestone allowed at any level, since a milestone marks a moment in
#: whatever it is a moment in.
ALLOWED_CHILD_TYPES = {
    'Phase': ('Task', 'Milestone'),
    'Task': ('Subtask', 'Milestone'),
}

#: What a task becomes when its own type is not one the parent can hold.
#:
#: Always work rather than a container: something being moved under a Phase
#: is being placed in a plan, not promoted into a bracket over other rows.
DEFAULT_CHILD_TYPE = {
    'Phase': 'Task',
    'Task': 'Subtask',
}

#: What a task is allowed to be at the top of the plan. A Subtask is not:
#: it is the level below a Task, so lifted clear of one it becomes a Task.
ROOT_TYPES = ('Phase', 'Task', 'Milestone')


def child_type_for(parent: Optional['Task'], task: 'Task') -> str:
    """
    The type a row should start on under a given parent.

    PARAMETERS:
    -----------
    parent : Optional[Task]
        What it is being placed under, or None for the top of the plan.
    task : Task
        The row being placed, carrying whatever type it starts with.

    RETURNS:
    --------
    str
        Its own type where the parent can hold it, and the level the parent
        expects where it cannot.

    DEVELOPMENT NOTES:
    ------------------
    For rows arriving without a type anybody chose: created from a parent's
    Create menu, or read out of an imported outline that states depth and
    nothing else. It settles what such a row should be.

    It is no longer applied to a row being *moved*. Indenting and outdenting
    leave the type alone - see indent_task - because by then the type is
    something the user has either chosen or accepted, and a move is a
    statement about where a row sits rather than about what it is.
    """
    if parent is None:
        return task.task_type if task.task_type in ROOT_TYPES else 'Task'

    allowed = ALLOWED_CHILD_TYPES.get(parent.task_type, ('Subtask',))
    if task.task_type in allowed:
        return task.task_type
    return DEFAULT_CHILD_TYPE.get(parent.task_type, 'Subtask')


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

A Subtask carries a percentage of its own, like every other row.

    A Task with sub-tasks averages their percentages, evenly. It is a
    checklist, and a checklist is counted rather than weighted - four
    sub-tasks of an hour each are four entries like any other four. A Task
    without sub-tasks keeps the percentage the user typed on it.

    Evenly averaging percentages is what counting ticks was, generalised: a
    checklist of ticks holds nothing but 0 and 100, and the average of those
    is the proportion ticked. Two of four ticked was 50 and still is; what
    is new is that a sub-task half done now says so instead of counting for
    nothing.

    A Phase averages its tasks evenly. Tasks are the units a phase is scoped
    in, and one being longer than another is not a reason for it to count
    for more of the phase.

    Anything else that has come to have children weights them by how long
    they run, so a fortnight's work counts for more than an afternoon's.
    Nothing offered carries children other than a Phase or a Task, but a
    plan can arrive from a file holding whatever its own format allowed, and
    a rule that covers it beats a row that totals to nothing.

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
        return int(round(sum(percentages) / len(percentages)))

    if parent.task_type == 'Phase':
        return int(round(sum(percentages) / len(percentages)))

    # Anything else that has come to have children; see the note above
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
    #: What the lag counts in; see LAG_UNITS. Days unless something says
    #: otherwise, which is what every link written before this existed meant.
    lag_unit: str = LAG_DAYS

    def __post_init__(self):
        """Normalise the type, hardness and lag to usable values."""
        self.task_id = str(self.task_id)

        unit = str(self.lag_unit or LAG_DAYS).lower()
        self.lag_unit = unit if unit in LAG_UNITS else LAG_DAYS

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

    def to_syntax_string(self, predecessor_number) -> str:
        """
        The link written the way the Dependencies column takes it.

        PARAMETERS:
        -----------
        predecessor_number : int or str
            The number the predecessor is shown as - what the reader typed
            and what they will read back. The link itself holds an identity,
            which is a key nobody sees; see Project.display_ids.

        RETURNS:
        --------
        str
            '003', '003SS+1d', '003FF', '003SF+50%'.

        DEVELOPMENT NOTES:
        ------------------
        A plain Finish-Start link with no lag is written as the number alone,
        because that is by far the commonest link and 'FS' on the end of
        every one of them is noise. The type reappears the moment there is a
        lag to attach it to, so '003+2d' - which reads as if the type had
        been forgotten - is never produced.
        """
        unit = '%' if self.lag_unit == LAG_PERCENT else 'd'
        if self.lag > 0:
            lag_text = f"+{self.lag}{unit}"
        elif self.lag < 0:
            lag_text = f"{self.lag}{unit}"
        else:
            lag_text = ''

        type_text = '' if self.dep_type == 'FS' and not lag_text else self.dep_type
        return f"{predecessor_number}{type_text}{lag_text}"

    def to_dict(self) -> dict:
        """Convert to a dictionary for serialization."""
        return {
            'task_id': self.task_id,
            'dep_type': self.dep_type,
            'hardness': self.hardness,
            'lag': self.lag,
            'lag_unit': self.lag_unit,
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
                # Absent from every link saved before a lag could be a
                # share of anything, and days is what those meant
                lag_unit=value.get('lag_unit', LAG_DAYS),
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


@dataclass(frozen=True)
class TaskFloat:
    """
    What the critical path method says about one task.

    ATTRIBUTES:
    -----------
    task_id : str
        The task this describes.
    early_start, early_finish : int
        Where the task is, as working days from the plan's first day.
    late_start, late_finish : int
        The latest it could be without the project finishing later.
    total_float : int
        Working days of slack: how long it could slip before it starts
        pushing the finish out. Zero means it cannot slip at all.
    is_critical : bool
        Whether it has no float, and so sits on the critical path.

    DEVELOPMENT NOTES:
    ------------------
    Working days rather than dates, and offsets rather than calendar days,
    because that is the only unit in which float means anything: a weekend
    between two tasks is not slack anybody can spend.

    Float can come out negative where links contradict each other - a task
    required to finish before something it also has to follow - and that is
    reported rather than clamped. A negative float is a plan that cannot be
    delivered as drawn, which is worth seeing.
    """

    task_id: str
    early_start: int
    early_finish: int
    late_start: int
    late_finish: int
    total_float: int
    is_critical: bool


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
        task_type: Type of task - one of TASK_TYPES (Phase, Task, Subtask, Milestone)
        parent_task_id: ID of parent task (for hierarchical organization)
        duration: Duration in days (can be manually set)
        priority: Task priority level
        shape: Visual shape for the task
        show_in_timeline: Whether to show in timeline view
        earliest_begin: Earliest possible start date
        scheduling_options: Scheduling mode for the task
        details: Additional notes/details about the task
        is_milestone: Legacy flag, now determined by task_type='Milestone'
        calendar_id: Named calendar this task follows, or None for the plan's own
    
    DEVELOPMENT NOTES:
    ------------------
    - task_type can be 'Phase', 'Task', 'Subtask', or 'Milestone'
    - A Phase is a container type that rolls up dates and progress from its
      children; so does any other row that comes to have them
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
    status: str = "Active"
    #: Which named calendar this task follows, or None to follow the plan's
    #: own - see gantt_app.calendarregistry. An id naming a calendar that has
    #: since been deleted falls back to the plan's own too, so removing a
    #: calendar never leaves a task without one.
    calendar_id: Optional[str] = None
    #: How this row is painted in the task list: its ink, its fill and its
    #: emphasis. Default for almost every row in almost every plan - see
    #: gantt_app.taskstyle, which is also where the defaults a summary row
    #: gets without asking are folded in.
    style: TaskStyle = field(default_factory=TaskStyle)
    resource_assignments: List[Dict[str, object]] = field(default_factory=list)
    
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
        
        # A type this application no longer offers is read as the nearest
        # thing it does; see RETIRED_TASK_TYPES
        self.task_type = RETIRED_TASK_TYPES.get(self.task_type,
                                                self.task_type)
        
        # Synchronize is_milestone with task_type for backward compatibility
        if self.task_type == "Milestone":
            self.is_milestone = True
            self.end_date = None  # Milestones have no duration
        elif self.is_milestone and self.task_type != "Milestone":
            # Legacy milestone flag: convert to new type
            self.task_type = "Milestone"
            self.end_date = None
        
        # For container types, ensure they don't have end_date if they shouldn't
        # Actually, containers CAN have end dates as they roll up from children
        
        # Validate status
        if self.status not in TASK_STATUSES:
            logger.warning(
                "Invalid status '%s' for task '%s', defaulting to 'Active'",
                self.status, self.name
            )
            self.status = 'Active'
        
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
        # The same courtesy for the row's formatting: the importers, the
        # undo history and every saved file hand over a plain dictionary
        elif name == 'style':
            value = TaskStyle.from_any(value)
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
        """Whether this task is a container type (a Phase)."""
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
        Whether this row is finished.

        DEVELOPMENT NOTES:
        ------------------
        Anything short of 100 is unfinished: a job that is half done is not
        a job that is done.

        This decided what a parent counted, when a sub-task was a tick and a
        Task above it counted how many were ticked. Sub-tasks carry a
        percentage now and the Task averages those instead, so this is left
        as what it says on the face of it - a question anything may ask of
        any row - rather than a rule about roll-up.
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
                       hardness: str = 'Hard', lag: int = 0,
                       lag_unit: str = LAG_DAYS) -> 'Dependency':
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
            existing.lag_unit = lag_unit
            existing.__post_init__()
            return existing

        dependency = Dependency(task_id=task_id, dep_type=dep_type,
                                hardness=hardness, lag=lag,
                                lag_unit=lag_unit)
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

        A plain property. This carried @classmethod above @property as well,
        which is a spelling of "class property" that Python supported for two
        releases: it was deprecated in 3.11 and removed in 3.13. On 3.13 the
        chain stops working silently in the worst possible way - the attribute
        hands back the property object itself rather than a calendar, so every
        caller fails with

            AttributeError: 'property' object has no attribute
                            'working_days_between'

        and every one of them is somewhere that only wanted a task's length:
        drawing a row, opening a form, rendering a page. It is reached on
        instances everywhere it is reached at all, so the classmethod bought
        nothing even while it worked.
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
        # A row with children holds no work of its own whatever is written
        # on it, and
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
            'status': self.status,
            'shape': self.shape,
            'show_in_timeline': self.show_in_timeline,
            'earliest_begin': self.earliest_begin.isoformat() if self.earliest_begin else None,
            'scheduling_options': self.scheduling_options,
            'details': self.details,
            'calendar_id': self.calendar_id,
            'resource_assignments': list(self.resource_assignments),
            # None for a row nobody has formatted, which is nearly all of
            # them; see TaskStyle.to_dict
            'style': self.style.to_dict(),
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
        
        # Validate status and provide default for backward compatibility
        status = data.get('status', 'Active')
        if status not in TASK_STATUSES:
            logger.info(
                "Task %r has an invalid status %r in the file; reading "
                "it as Active", data.get('name', 'unknown'), status
            )
            status = 'Active'

        assignments = data.get('resource_assignments')
        if not assignments and data.get('resource_id'):
            assignments = [{
                'resource_id': data['resource_id'],
                'estimated_hours': data.get('estimated_hours', 0.0),
                'resource_split': data.get('resource_split', 100.0),
            }]
        assignments = assignments or []
        
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
            status=status,
            shape=data.get('shape', 'Default'),
            show_in_timeline=data.get('show_in_timeline', True),
            earliest_begin=earliest_begin,
            scheduling_options=scheduling_options,
            details=data.get('details', ''),
            calendar_id=data.get('calendar_id') or None,
            resource_assignments=assignments,
            # Absent in every plan saved before formatting existed, which
            # opens with plain rows rather than failing
            style=TaskStyle.from_any(data.get('style')),
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
        calendars: Named calendars a task may follow instead; see calendar_for

    DEVELOPMENT NOTES:
    ------------------
    The calendar on the plan is the default, and most tasks follow it: which
    days are worked is usually a property of the plan rather than of each
    piece of work in it. But not always - a migration that can only touch
    production at the weekend is scheduled wrong by any week the rest of the
    plan keeps - so a task may name one of the calendars in `calendars`
    instead, and calendar_for is what every piece of scheduling asks. A task
    that names nothing, or names a calendar that has been deleted, follows the
    plan's own; see gantt_app.calendarregistry.
    """
    name: str
    tasks: List[Task] = field(default_factory=list)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    calendar: WorkingCalendar = field(default_factory=WorkingCalendar)
    calendars: CalendarRegistry = field(default_factory=default_registry)
    #: Which end the dates are worked out from; see SCHEDULE_FROM.
    schedule_from: str = SCHEDULE_FROM_START
    #: The date the plan must be finished by, when it is scheduled backward.
    #: Ignored while it is scheduled forward, where the finish is an answer
    #: rather than a question.
    deadline: Optional[datetime] = None
    #: The date progress is reported against, when it is not today. None
    #: means today, which is what a plan means until somebody freezes it for
    #: a status meeting.
    status_date: Optional[datetime] = None
    #: What the plan is worth against other plans, for whoever is levelling
    #: resources across them. Carried rather than used: nothing here levels
    #: anything, and a number a reader typed should still be theirs when
    #: they come back to it.
    priority: int = DEFAULT_PROJECT_PRIORITY
    resource_repository: ResourceRepository = field(
        default_factory=ResourceRepository, compare=False)

    def calendar_for(self, task: Task) -> WorkingCalendar:
        """
        The calendar one task is scheduled against.

        RETURNS:
        --------
        WorkingCalendar
            The named calendar the task follows, or the plan's own when it
            names none - or names one that no longer exists.

        DEVELOPMENT NOTES:
        ------------------
        Every piece of scheduling that touches a single task goes through
        here rather than reading `self.calendar`, which is what makes a
        per-task calendar work at all. The plan-wide numbers - the span the
        chart draws, where the project starts - stay on `self.calendar`,
        because they are not about any one task.
        """
        return self.calendars.resolve(task.calendar_id, self.calendar)

    def __setattr__(self, name: str, value) -> None:
        """Invalidate the ID index whenever the task list is replaced."""
        super().__setattr__(name, value)
        if name == 'tasks' and hasattr(self, '_id_to_task'):
            self._id_to_task = None

    def __post_init__(self):
        """Update project dates based on tasks if not set."""
        direction = str(self.schedule_from or SCHEDULE_FROM_START).lower()
        self.schedule_from = (direction if direction in SCHEDULE_FROM
                              else SCHEDULE_FROM_START)
        self.priority = self._clamped_priority(self.priority)
        #: The last schedule_analysis result, and the signature of the plan
        #: it was worked out from. Not dataclass fields: they are derived
        #: from the plan rather than part of it, so they are neither saved
        #: nor compared when two projects are tested for equality.
        self._analysis_cache = None
        self._analysis_signature_seen = None
        #: Lookup dict for get_task_by_id, invalidated by add/remove/renumber.
        self._id_to_task: Optional[Dict[str, Task]] = None

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
    
    @staticmethod
    def _clamped_priority(value) -> int:
        """
        A priority inside the range, whatever arrived.

        DEVELOPMENT NOTES:
        ------------------
        Clamped rather than refused. This arrives from a text box and from
        saved files, and a plan that will not open because somebody typed
        2000 would be a poor trade for a number nothing in the application
        acts on yet.
        """
        try:
            number = int(float(value))
        except (TypeError, ValueError):
            return DEFAULT_PROJECT_PRIORITY
        return max(MIN_PROJECT_PRIORITY, min(MAX_PROJECT_PRIORITY, number))

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

        self._id_to_task = None
        return mapping

    def add_task(self, task: Task):
        """Add a task to the project and update dates."""
        self.tasks.append(task)
        self._id_to_task = None
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

    def with_descendants(self, task_ids) -> List[str]:
        """
        The named rows and everything beneath them, in reading order.

        PARAMETERS:
        -----------
        task_ids : Sequence[str]
            The rows picked out.

        RETURNS:
        --------
        List[str]
            Those rows and all of their descendants, top to bottom, each
            once.

        DEVELOPMENT NOTES:
        ------------------
        What a reader means by picking out a phase. A row that holds work
        stands for that work: copying the row alone gave an empty container
        and left the reader to rebuild what was under it by hand, which is
        the opposite of why anybody copies a branch of a plan.
        """
        wanted = set()
        for task_id in task_ids or []:
            if self.get_task_by_id(task_id) is None:
                continue
            wanted.add(task_id)
            wanted |= self._descendant_ids(task_id)

        return [task.id for task in self.display_order() if task.id in wanted]

    def topmost_of(self, task_ids) -> List[str]:
        """
        The named rows with any that sit under another one left out.

        PARAMETERS:
        -----------
        task_ids : Sequence[str]
            The rows picked out.

        RETURNS:
        --------
        List[str]
            Only the highest of each branch, in reading order.

        DEVELOPMENT NOTES:
        ------------------
        For a move, where a row carries its own descendants with it because
        they go on pointing at it. Naming a child as well as its parent
        would move the child in its own right - out of the parent it is
        supposed to be travelling inside - so a selection of a task and its
        sub-task cut and pasted came out as two rows side by side.
        """
        named = {task_id for task_id in task_ids or []
                 if self.get_task_by_id(task_id) is not None}

        return [task.id for task in self.display_order()
                if task.id in named
                and not any(other != task.id
                            and self.is_descendant(task.id, other)
                            for other in named)]

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

    def can_reparent_task(self, task_id: str,
                          new_parent_id: Optional[str]) -> bool:
        """Whether a task branch may be moved under a new parent."""
        task = self.get_task_by_id(task_id)
        if task is None:
            logger.debug("Cannot re-parent missing task %r", task_id)
            return False
        if new_parent_id is None:
            allowed = task.parent_task_id is not None
            logger.debug("Can re-parent task %r to root: %s", task_id, allowed)
            return allowed

        new_parent = self.get_task_by_id(new_parent_id)
        if new_parent is None or new_parent.is_milestone:
            logger.debug("Task %r is not a valid parent for %r",
                         new_parent_id, task_id)
            return False
        if task.parent_task_id == new_parent_id:
            logger.debug("Task %r is already under %r", task_id, new_parent_id)
            return False
        allowed = not self.is_descendant(new_parent_id, task_id)
        logger.debug("Can re-parent task %r under %r: %s",
                     task_id, new_parent_id, allowed)
        return allowed

    def reparent_task(self, task_id: str,
                      new_parent_id: Optional[str]) -> bool:
        """Move a task and its complete branch under a different parent."""
        if not self.can_reparent_task(task_id, new_parent_id):
            logger.warning("Rejected re-parenting task %r under %r",
                           task_id, new_parent_id)
            return False

        task = self.get_task_by_id(task_id)
        old_parent_id = task.parent_task_id
        children = self._children_by_parent()
        old_siblings = children.get(old_parent_id, [])
        if task in old_siblings:
            old_siblings.remove(task)

        task.parent_task_id = new_parent_id
        children.setdefault(new_parent_id, []).append(task)
        self.tasks = self._flatten(children)
        removed = self.strip_ancestor_links(task_id)
        logger.info(
            "Re-parented task %r from %r to %r with %d descendant(s); "
            "removed %d invalid dependency link(s)",
            task_id, old_parent_id, new_parent_id,
            len(self._descendant_ids(task_id)), len(removed),
        )
        return True

    def hierarchy_indent_px(self, task_id: str) -> int:
        """Return the visual hierarchy indent using the required 24px step."""
        indent = max(0, self.outline_level(task_id) - 1) * 24
        logger.debug("Task %r hierarchy indent is %dpx", task_id, indent)
        return indent

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

        The task keeps its type. Every one of them, wherever it lands: a
        Task indented under another Task is still a Task.

        It used to be retyped to whatever the new parent expected, so
        indenting a Task under a Task made it a Subtask - and the row you
        had built as a task, with sub-tasks of its own, came back a level
        down and could no longer hold them. The type is the user's
        statement about what a row is; where it sits is a separate
        statement, and moving a row says nothing about the first. Change it
        in the Type column or in the editor, which is where it is asked for.
        """
        new_parent = self.indent_target(task_id)
        if new_parent is None:
            return False

        task = self.get_task_by_id(task_id)
        task.parent_task_id = new_parent.id

        self.tasks = self._flatten(self._children_by_parent())
        self.strip_ancestor_links(task_id)
        return True

    def _topmost(self, task_ids) -> List[str]:
        """
        The selected tasks that no other selected task contains.

        RETURNS:
        --------
        List[str]
            The IDs, in the order the plan holds them.

        DEVELOPMENT NOTES:
        ------------------
        A branch moves as a whole, so moving a task that sits inside another
        task being moved would move it twice - once carried by its parent and
        once on its own account, ending a level deeper than everything it was
        selected with. Selecting a parent and its children and pressing Indent
        is an ordinary thing to do, and it has to mean the branch.
        """
        wanted = {task_id for task_id in task_ids
                  if self.get_task_by_id(task_id) is not None}

        def has_selected_ancestor(task: Task) -> bool:
            """Whether anything above this task is selected as well."""
            seen = {task.id}
            parent_id = task.parent_task_id
            while parent_id and parent_id not in seen:
                if parent_id in wanted:
                    return True
                seen.add(parent_id)
                parent = self.get_task_by_id(parent_id)
                if parent is None:
                    break
                parent_id = parent.parent_task_id
            return False

        return [task.id for task in self.tasks
                if task.id in wanted and not has_selected_ancestor(task)]

    def indent_tasks(self, task_ids) -> bool:
        """
        Make several tasks sub-tasks of the row above the topmost of them.

        RETURNS:
        --------
        bool
            True when anything moved.

        DEVELOPMENT NOTES:
        ------------------
        Worked top to bottom, which is what keeps the group together. Each
        indent moves a task under the sibling above it, so once the first has
        gone under that sibling the next one's sibling above is the same
        task - and they all land side by side beneath it.

        Bottom to top does something quite different: the last row goes under
        the second to last, which then goes under the one above that, and a
        flat selection comes out as a staircase.

        A row that cannot be indented is stepped over rather than stopping
        the rest. The first row of a group has nothing above it to go under,
        and a selection that happens to start at one should still indent
        everything after it.
        """
        moved = False
        for task_id in self._topmost(task_ids):
            if self.indent_task(task_id):
                moved = True
        return moved

    def outdent_tasks(self, task_ids) -> bool:
        """
        Move several tasks out to sit beside their parent.

        RETURNS:
        --------
        bool
            True when anything moved.

        DEVELOPMENT NOTES:
        ------------------
        Worked bottom to top, which is the order that keeps them in the order
        they were in. A task lifted out is placed after its old parent's
        remaining children, so lifting the first one puts it behind the
        siblings it used to be in front of - and doing that down the list
        reverses them. Lifting the last one first leaves nothing behind it to
        be placed after.
        """
        moved = False
        for task_id in reversed(self._topmost(task_ids)):
            if self.outdent_task(task_id):
                moved = True
        return moved

    def outdent_task(self, task_id: str) -> bool:
        """
        Move a task out to sit beside its parent.

        RETURNS:
        --------
        bool
            True when the task moved.

        DEVELOPMENT NOTES:
        ------------------
        The task keeps its type, at the top of the plan as anywhere else -
        a Subtask lifted clear of its task is still a Subtask until
        somebody says otherwise. See indent_task for why.

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
            {t.id: [Dependency(d.task_id, d.dep_type, d.hardness, d.lag,
                               d.lag_unit)
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
                    Dependency(d.task_id, d.dep_type, d.hardness, d.lag,
                               d.lag_unit)
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

        # Taking the task out first shifts everything after it up one, so a
        # task moving down the list has to be put back one place earlier
        # than the index the target had. Without this it landed after the
        # target rather than at its position - which is what the drop line
        # promises and what this is named for - and only when moving down,
        # so dragging a row upwards behaved and dragging it down did not.
        if index < target_index:
            target_index -= 1

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
            self._id_to_task = None
            self._update_dates()
            return True
        return False
    
    def _rebuild_id_index(self):
        """Build the task ID lookup dict from self.tasks."""
        self._id_to_task = {task.id: task for task in self.tasks}

    def get_task_by_id(self, task_id: str) -> Optional[Task]:
        """Get a task by its ID."""
        if self._id_to_task is None:
            self._rebuild_id_index()
        return self._id_to_task.get(task_id)
    
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
    
    #: Ceiling on the walk up a parent chain in outline_level. A plan cannot
    #: nest deeper than this, and a file whose parents form a cycle should
    #: cost a warning rather than a loop with no end.
    MAX_OUTLINE_DEPTH = 100

    def date_for_offset(self, offset: int) -> Optional[datetime]:
        """
        A working-day offset from the plan's first day, as a date.

        PARAMETERS:
        -----------
        offset : int
            As schedule_analysis counts: 0 is the plan's first working day.

        RETURNS:
        --------
        Optional[datetime]
            The date, or None for a plan with no start.

        DEVELOPMENT NOTES:
        ------------------
        The plan's own calendar, deliberately, even for a task following one
        of its own: the axis is the single ruler every task's float is
        measured on, and reading an offset back against a different week
        would land on a different day than the one it was counted out from.

        The +1 is the axis's own convention rather than an adjustment: an
        offset of 0 is the first working day, and add_working_days counts
        the days it advances over.
        """
        if self.start_date is None:
            return None
        return self.calendar.add_working_days(self.start_date, offset + 1)

    def apply_backward_schedule(self) -> bool:
        """
        Move every piece of work as late as it can go, ending on the deadline.

        RETURNS:
        --------
        bool
            True when anything moved.

        DEVELOPMENT NOTES:
        ------------------
        As Late As Possible, which is what scheduling from a finish date
        means: the deadline is the fixed thing and the work is fitted in
        before it, so nothing starts earlier than it has to.

        The dates come from the backward pass the critical path analysis
        already runs. Its late_start and late_finish are the definition of
        "as late as this can be without the project finishing later", so
        there is no second scheduler here - the answer was already being
        computed and thrown away after the float was read off it.

        The plan is settled forward first. The backward pass measures against
        a consistent plan, and a plan whose links have not been applied is
        not one.

        Nothing is rescheduled afterwards, and that is deliberate: reschedule
        only ever moves a task later, which is exactly what this has just
        finished doing on purpose. Running it here would push everything
        forward again and undo the whole operation. The late dates satisfy
        every link by construction - that is what the backward pass computes -
        so there is nothing left to settle.

        Summaries are left to roll up from their children, as everywhere
        else: a bracket's dates are its contents' dates.
        """
        if not self.tasks:
            return False

        self.reschedule()
        analysis = self.schedule_analysis()
        summary_ids = self.get_summary_task_ids()

        moved = False
        for task in self.tasks:
            if task.id in summary_ids:
                continue
            found = analysis.get(task.id)
            if found is None:
                continue

            new_start = self.date_for_offset(found.late_start)
            if new_start is None:
                continue

            if task.effective_milestone:
                if as_date(task.start_date) != as_date(new_start):
                    task.start_date = new_start
                    moved = True
                continue

            new_end = self.date_for_offset(found.late_finish)
            current = (as_date(task.start_date),
                       as_date(task.end_date) if task.end_date else None)
            if current != (as_date(new_start), as_date(new_end)):
                task.start_date = new_start
                task.end_date = new_end
                moved = True

        self.enforce_working_calendar()
        self.roll_up_summaries()
        self._update_dates()

        if self.deadline is not None and self.shift_to_finish(self.deadline):
            moved = True

        if moved:
            logger.info("Scheduled %r backwards from %s", self.name,
                        as_date(self.deadline) if self.deadline
                        else 'its own finish')
        return moved

    def shift_to_finish(self, deadline: datetime) -> bool:
        """
        Move the whole plan so its last day is the one given.

        PARAMETERS:
        -----------
        deadline : datetime
            The date the plan must be finished by.

        RETURNS:
        --------
        bool
            True when anything moved.

        DEVELOPMENT NOTES:
        ------------------
        The mirror of shift_to_start, anchored on the other end. Backward
        scheduling packs the work as late as it can go and then this puts
        that packed plan against the deadline - a plan can only be as late as
        possible relative to something, and the deadline is the something.

        It may well move the plan into the past. That is not a fault to
        guard against: a deadline that cannot be met from today is exactly
        what a reader needs to be shown, and quietly refusing to move would
        hide it.
        """
        finishes = [task.end_date or task.start_date for task in self.tasks
                    if task.start_date is not None]
        if not finishes:
            return False

        delta = as_date(deadline) - as_date(max(finishes))
        if delta.days == 0:
            return False

        for task in self.tasks:
            if task.start_date is not None:
                task.start_date += delta
            if task.end_date is not None:
                task.end_date += delta
            if task.earliest_begin is not None:
                task.earliest_begin += delta

        self.enforce_working_calendar()
        self.roll_up_summaries()
        self._update_dates()
        logger.info("Moved %r by %d day(s) to finish on %s",
                    self.name, delta.days, as_date(deadline))
        return True

    def apply_schedule(self) -> bool:
        """
        Settle the plan from whichever end it is scheduled from.

        RETURNS:
        --------
        bool
            True when anything moved.

        DEVELOPMENT NOTES:
        ------------------
        The one call everything else makes, so that which direction a plan
        is scheduled in is answered in one place rather than at every refresh
        that wanted the dates settled.

        A plan scheduled forward gets exactly what it always got: reschedule
        and nothing else. That is not a courtesy - it is the whole of the
        existing behaviour, and every plan is forward until somebody says
        otherwise.
        """
        if self.schedule_from == SCHEDULE_FROM_FINISH:
            return self.apply_backward_schedule()
        return self.reschedule()

    def shift_to_start(self, new_start: datetime) -> bool:
        """
        Move the whole plan so it begins on a given date.

        PARAMETERS:
        -----------
        new_start : datetime
            The date the earliest task should begin on.

        RETURNS:
        --------
        bool
            True when anything moved.

        DEVELOPMENT NOTES:
        ------------------
        Every task is moved by the same number of calendar days, which is
        what preserves the plan: a task keeps its length, two tasks keep the
        gap between them, and a link that was satisfied stays satisfied
        because both ends moved together. Rescheduling from the new date
        instead would collapse every gap somebody had put there on purpose.

        The earliest begin dates move with it. They are floors somebody set
        relative to the plan around them, and a plan shifted six months
        later with its floors left behind is a plan full of constraints
        nobody wrote.

        The calendar is enforced afterwards, so a task whose new start lands
        on a weekend is pushed to the next working day - which means the
        shift is not uniform to the day for those tasks. That is the right
        way round: a task cannot start on a day nobody works, and the
        alternative is a plan that begins on a Sunday.
        """
        starts = [task.start_date for task in self.tasks
                  if task.start_date is not None]
        if not starts:
            return False

        delta = as_date(new_start) - as_date(min(starts))
        if delta.days == 0:
            return False

        for task in self.tasks:
            if task.start_date is not None:
                task.start_date += delta
            if task.end_date is not None:
                task.end_date += delta
            if task.earliest_begin is not None:
                task.earliest_begin += delta

        self.enforce_working_calendar()
        self.reschedule()
        self._update_dates()
        logger.info("Moved %r by %d day(s) to start on %s",
                    self.name, delta.days, as_date(new_start))
        return True

    def lag_days(self, dependency) -> int:
        """
        A link's lag as a number of working days.

        PARAMETERS:
        -----------
        dependency : Dependency
            The link to measure.

        RETURNS:
        --------
        int
            The lag itself when it is already in days, and the share of the
            predecessor's duration it names when it is a percentage.

        DEVELOPMENT NOTES:
        ------------------
        A lag in days is returned untouched, which is not a detail: every
        link that existed before a lag could be a share of anything is in
        days, so the scheduler computes exactly what it computed before.
        The percentage is the only new arithmetic, and it can only apply to
        a link that could not previously be stated at all.

        The share is of the *predecessor's* duration - "start this when that
        one is half done" is a statement about that one - which is what
        every planning tool means by it.

        A link whose predecessor has gone contributes nothing rather than
        raising. The scheduler runs on every redraw, and a plan that will
        not draw because a link dangles is a far worse answer than a link
        that adds no delay.
        """
        if dependency.lag_unit != LAG_PERCENT:
            return dependency.lag

        predecessor = self.get_task_by_id(dependency.task_id)
        if predecessor is None:
            return 0

        days = self.working_duration(predecessor) * dependency.lag / 100
        # Rounded half away from zero rather than with round(), which rounds
        # half to even: half of a five-day task would come out as two days
        # and half of a seven-day task as four, which is not a rule anybody
        # would guess at and not one worth explaining.
        return int(days + 0.5) if days >= 0 else -int(-days + 0.5)

    def would_create_dependency_cycle(self, successor_id: str,
                                      predecessor_id: str) -> bool:
        """
        Whether one more link would close a loop.

        PARAMETERS:
        -----------
        successor_id : str
            The task that would wait.
        predecessor_id : str
            The task it would wait for.

        RETURNS:
        --------
        bool
            True for a task depending on itself, on one of its own
            descendants, or on anything that already waits for it however
            far around.

        DEVELOPMENT NOTES:
        ------------------
        A plan with a loop in it cannot be scheduled - every pass moves a
        task and the next pass moves it back - so this is checked before a
        link is stored rather than left for the scheduler to fail on.

        Walking forward from the predecessor and looking for the successor
        is the cheap direction: it stops at the first hit, and a plan has
        far fewer links than tasks.

        This lived in the task list, which is a view. It is a fact about the
        plan, and the Dependencies column needed the same answer - so rather
        than have two of it, it is here.
        """
        if successor_id == predecessor_id:
            return True
        if self.is_descendant(predecessor_id, successor_id):
            return True

        seen = set()
        stack = [predecessor_id]
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)

            task = self.get_task_by_id(current)
            if task is None:
                continue
            for link in task.dependency_ids:
                if link == successor_id:
                    return True
                stack.append(link)

        return False

    def parse_dependencies(self, task_id: str, text: str):
        """
        Read a Dependencies cell into links this plan can hold.

        PARAMETERS:
        -----------
        task_id : str
            The task the cell belongs to.
        text : str
            What was typed; see gantt_app.dependencysyntax for the grammar.

        RETURNS:
        --------
        Tuple[List[Dependency], List[str]]
            The links, and a message for everything that could not become
            one. Anything rejected is left out rather than guessed at.

        DEVELOPMENT NOTES:
        ------------------
        The numbers are resolved here rather than in the parser, because
        only the plan knows what number names what task - and the three
        things that can be wrong with a link once it has been read all need
        the plan too: a number naming nothing, a task depending on itself,
        and a link that would close a loop.

        Each link is checked against the ones already accepted from the same
        cell, not only against what the task holds now. Typing "4, 5" where
        5 already waits for 4 is a loop that only exists once both have been
        taken, and checking against the stored links alone would let it
        through.
        """
        from gantt_app.dependencysyntax import parse

        parsed, errors = parse(text)
        numbers = self.display_ids()
        by_number = {number: identity for identity, number in numbers.items()}

        links = []
        taken = set()
        for item in parsed:
            try:
                predecessor = by_number.get(int(item.number))
            except (TypeError, ValueError):
                predecessor = None

            if predecessor is None:
                errors.append(f"There is no task {item.number} in this plan.")
                continue
            if predecessor == task_id:
                errors.append("A task cannot depend on itself.")
                continue
            if predecessor in taken:
                errors.append(f"Task {item.number} is listed more than once.")
                continue

            # Against what has been accepted so far as well as what is
            # stored, so a cell that closes a loop within itself is caught
            probe = Task(id=task_id, name='probe',
                         start_date=datetime.now(),
                         dependencies=[Dependency(link.task_id) for link in links])
            with self._links_replaced(task_id, probe.dependencies):
                if self.would_create_dependency_cycle(task_id, predecessor):
                    errors.append(
                        f"Task {item.number} already waits for this one, so "
                        f"linking them would run in a circle.")
                    continue

            taken.add(predecessor)
            links.append(Dependency(predecessor, item.dep_type, 'Hard',
                                    item.lag, item.lag_unit))

        return links, errors

    @contextmanager
    def _links_replaced(self, task_id: str, links):
        """
        Hold a different set of links on one task for the length of a check.

        DEVELOPMENT NOTES:
        ------------------
        The cycle check reads the plan, so testing a link that has not been
        stored yet means putting it there and taking it out again. A context
        manager rather than a pair of assignments because the check between
        them can raise, and a plan left holding a probe's links would be a
        far worse fault than the one being guarded against.
        """
        task = self.get_task_by_id(task_id)
        if task is None:
            yield
            return

        original = list(task.dependencies)
        task.dependencies = links
        try:
            yield
        finally:
            task.dependencies = original

    def _in_display_order(self, task_ids) -> List[Task]:
        """
        The named tasks, in the order the list shows them.

        PARAMETERS:
        -----------
        task_ids : Sequence[str]
            The rows to put in order. Names that are in no plan are left
            out, and a row named twice is taken once.

        RETURNS:
        --------
        List[Task]
            Top to bottom, whatever order they were named in.

        DEVELOPMENT NOTES:
        ------------------
        Linking is order-sensitive and the order that matters is the one on
        screen, not the one the selection happens to be held in. A Treeview
        reports a selection in the order rows were added to it, so
        shift-clicking upwards from the bottom of a group hands back the
        rows bottom-first - and a chain built from that would run backwards
        through the plan.
        """
        places = {task.id: number
                  for number, task in enumerate(self.display_order())}

        chosen = {}
        for task_id in task_ids or []:
            task = self.get_task_by_id(task_id)
            if task is not None:
                chosen[task.id] = task

        return sorted(chosen.values(),
                      key=lambda task: places.get(task.id, len(places)))

    def link_tasks(self, task_ids) -> List[tuple]:
        """
        Chain the named tasks Finish-to-Start, down the list.

        PARAMETERS:
        -----------
        task_ids : Sequence[str]
            The rows to link. Fewer than two of them is nothing to do.

        RETURNS:
        --------
        List[tuple]
            (predecessor id, successor id) for each link made. Empty when
            nothing was: the rows were already chained, or every link the
            chain wanted would have closed a loop.

        DEVELOPMENT NOTES:
        ------------------
        One link per neighbouring pair, top to bottom: the first row becomes
        the predecessor of the second, the second of the third, and so on.
        Finish-to-Start with no lag, which is what a plain link means and
        what the reference tool gives you.

        Links a row already holds are left alone. Linking is something added
        to a plan rather than a statement of everything a row waits for, so
        a task that already waits for something outside the selection goes
        on waiting for it.

        A pair that would close a loop is skipped and the rest of the chain
        is still made. Refusing the whole thing would mean a selection with
        one awkward pair in the middle of it doing nothing at all, with the
        reason buried; skipping is what the user can see, because the rows
        that did link say so in their own column.

        A chain is built from the topmost rows of the selection. A row that
        holds work is bracketed by that work, so a selection of a row and
        the rows inside it is one thing running one after another, not four,
        and chaining every row of it in reading order linked each container
        to the first thing inside it. That is a contradiction rather than a
        long chain: the container's dates are rolled up from its children,
        so a child made to wait for its own parent waits for a date that is
        computed from it. The plan then never settled - each pass moved it
        further out - which is how a plan starting in August came to start
        the following January.
        """
        chosen = [self.get_task_by_id(task_id)
                  for task_id in self.topmost_of(task_ids)]
        if len(chosen) < 2:
            return []

        linked = []
        for predecessor, successor in zip(chosen, chosen[1:]):
            if successor.get_dependency(predecessor.id) is not None:
                continue
            if (self.is_descendant(successor.id, predecessor.id)
                    or self.is_descendant(predecessor.id, successor.id)):
                # Belt and braces: topmost_of has already dropped these, but
                # a caller reaching the plan directly must not be able to
                # write a link the scheduler cannot honour
                logger.info("Not linking %s to %s: one holds the other",
                            predecessor.id, successor.id)
                continue
            if self.would_create_dependency_cycle(successor.id,
                                                  predecessor.id):
                logger.info("Not linking %s to %s: it would run in a circle",
                            predecessor.id, successor.id)
                continue

            successor.add_dependency(predecessor.id, 'FS', 'Hard', 0)
            linked.append((predecessor.id, successor.id))

        if linked:
            logger.info("Linked %d pair(s): %s", len(linked), linked)
        return linked

    def unlink_tasks(self, task_ids) -> List[tuple]:
        """
        Break the links between the named tasks.

        PARAMETERS:
        -----------
        task_ids : Sequence[str]
            The rows to unlink.

        RETURNS:
        --------
        List[tuple]
            (predecessor id, successor id) for each link removed.

        DEVELOPMENT NOTES:
        ------------------
        With several rows named, the links *between them* go and nothing
        else: a row in the selection that waits for something outside it
        goes on waiting, because the user pointed at these rows and not at
        that one.

        With a single row named there is no "between", so what goes is every
        link that row is part of - the ones it holds and the ones held on
        it. That is the reference tool's answer and the only useful one:
        unlinking one row otherwise does nothing at all.
        """
        chosen = self._in_display_order(task_ids)
        if not chosen:
            return []

        removed = []
        if len(chosen) == 1:
            alone = chosen[0]
            for link in list(alone.dependencies):
                if alone.remove_dependency(link.task_id):
                    removed.append((link.task_id, alone.id))
            for task in self.tasks:
                if task is alone:
                    continue
                if task.remove_dependency(alone.id):
                    removed.append((alone.id, task.id))
        else:
            within = {task.id for task in chosen}
            for task in chosen:
                for link in list(task.dependencies):
                    if link.task_id in within and \
                            task.remove_dependency(link.task_id):
                        removed.append((link.task_id, task.id))

        if removed:
            logger.info("Unlinked %d link(s): %s", len(removed), removed)
        return removed

    def display_order(self) -> List[Task]:
        """
        Every task in the order the list shows them.

        RETURNS:
        --------
        List[Task]
            Parents before their children, siblings in plan order, and any
            task orphaned by a missing parent at the end rather than lost.

        DEVELOPMENT NOTES:
        ------------------
        The same walk the reordering uses, so what the list draws and what
        the numbering counts cannot disagree - see _flatten, which is where
        the orphan rule lives.
        """
        return self._flatten(self._children_by_parent())

    def display_ids(self) -> Dict[str, int]:
        """
        The number each task shows, counted down the display order.

        RETURNS:
        --------
        Dict[str, int]
            Task ID to the number beside it: 1 for the first row, N for the
            last, contiguous throughout.

        DEVELOPMENT NOTES:
        ------------------
        Worked out rather than stored, and that is the whole design.

        A stored number would have to be rewritten on every reorder, every
        insert, every delete and every indent - and each of those is already
        recorded in the undo history against Task.id. Renumbering a stored
        field after the change would leave the history pointing at numbers
        that no longer name anything, so undo would restore an order of rows
        that had ceased to exist.

        Derived, there is nothing to renumber and nothing to undo. The number
        is a fact about where a row currently sits, so it is right the moment
        the row moves, and it cannot drift out of step with the list.

        Task.id stays what it always was: the identity. Dependencies, parents,
        the clipboard, the tree's own row ids and every undo snapshot are
        keyed on it, and none of them is touched by a row moving. That is the
        static key the specification asks for; this is the number beside it.
        """
        return {task.id: number
                for number, task in enumerate(self.display_order(), start=1)}

    def display_id(self, task_id: str) -> str:
        """
        The number one task shows, written the way the list writes it.

        RETURNS:
        --------
        str
            Zero-padded to ID_WIDTH - '001', '002' - or an empty string for
            a task that is not in the plan.

        DEVELOPMENT NOTES:
        ------------------
        Convenient for one task and wasteful for a list of them: it walks the
        whole plan to answer. Anything drawing more than a row or two asks
        display_ids once instead.
        """
        number = self.display_ids().get(task_id)
        return '' if number is None else str(number).zfill(self.ID_WIDTH)

    def progress_on_track(self, task: Task, status_date: datetime) -> int:
        """
        The completion a task would have if it were exactly on schedule.

        PARAMETERS:
        -----------
        task : Task
            The task to measure.
        status_date : datetime
            The date the plan is being reported against. Today, unless the
            reader names another.

        RETURNS:
        --------
        int
            0 for work that has not started, 100 for work whose finish has
            passed, and the share of its working days that have elapsed for
            anything in between.

        DEVELOPMENT NOTES:
        ------------------
        Counted in working days against the task's own calendar rather than
        in calendar days, which is the whole reason this is here rather than
        a subtraction at the call site. A five-day task starting on a Friday
        is not 40% done by Sunday; it is 20% done, because one of its five
        days has been worked.

        A milestone is a moment rather than a span, so it is done or it is
        not - there is no proportion of a milestone.

        The task's own dates are read, not the summary's. A container's
        completion is rolled up from its children and would be overwritten
        by the next reschedule; see roll_up_summaries.
        """
        start = as_date(task.start_date)
        status = as_date(status_date)

        if task.effective_milestone:
            return 100 if start <= status else 0

        finish = as_date(task.end_date) if task.end_date else start
        if finish <= status:
            return 100
        if start > status:
            return 0

        calendar = self.calendar_for(task)
        total = max(self.working_duration(task), 1)
        elapsed = calendar.working_days_between(start, status)

        return max(0, min(100, int(round(elapsed / total * 100))))

    def outline_level(self, task_id: str) -> int:
        """
        How deep a task sits in the plan, counting from one.

        PARAMETERS:
        -----------
        task_id : str
            The task to measure.

        RETURNS:
        --------
        int
            1 for a task at the top of the plan, 2 for one under it, and so
            on. 1 for a task that is not in the plan at all, which is what
            an unknown row is drawn as.

        DEVELOPMENT NOTES:
        ------------------
        Counted from one rather than zero because this is the number shown
        in the Outline Level column, and it is the number Microsoft Project
        shows there too - a reader comparing the two should not find them
        off by one.

        The walk is capped and remembers where it has been. A saved file
        whose parent references form a cycle would otherwise hang the
        redraw, and one damaged plan should not take the window with it.
        """
        level = 1
        seen = {task_id}
        task = self.get_task_by_id(task_id)

        while task is not None and task.parent_task_id:
            if task.parent_task_id in seen or level > self.MAX_OUTLINE_DEPTH:
                logger.warning("Task %r sits in a parent cycle; showing it at "
                               "level %d", task_id, level)
                break
            seen.add(task.parent_task_id)
            task = self.get_task_by_id(task.parent_task_id)
            if task is None:
                break
            level += 1

        return level

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
            'calendar': self.calendar.to_dict(),
            'calendars': self.calendars.to_dict(),
            'schedule_from': self.schedule_from,
            'deadline': self.deadline.isoformat() if self.deadline else None,
            'status_date': (self.status_date.isoformat()
                            if self.status_date else None),
            'priority': self.priority,
            **self.resource_repository.to_dict(),
        }

    @staticmethod
    def _read_date(value) -> Optional[datetime]:
        """
        One saved date, or None where there is not a usable one.

        DEVELOPMENT NOTES:
        ------------------
        Unreadable becomes None rather than raising. These are settings on a
        plan, and a plan that will not open because a date somebody typed
        was malformed is a far worse answer than a setting coming back
        empty.
        """
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value))
        except (TypeError, ValueError):
            logger.warning("Ignoring unreadable project date %r", value)
            return None

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
            calendar=WorkingCalendar.from_dict(data.get('calendar')),
            # Nothing is invented for a file that did not have it. A plan
            # written before calendars could be named opens with none, and
            # the settings dialog's New... is one click away if its author
            # wants some - which is a better answer than three calendars
            # appearing in a file nobody added them to. Only a brand new
            # project is seeded; see the field's default.
            calendars=CalendarRegistry.from_dict(data.get('calendars')),
            # Absent from every plan saved before the settings existed, and
            # the defaults are what those plans meant: scheduled forward,
            # no deadline, reported against today
            schedule_from=data.get('schedule_from', SCHEDULE_FROM_START),
            deadline=cls._read_date(data.get('deadline')),
            status_date=cls._read_date(data.get('status_date')),
            priority=data.get('priority', DEFAULT_PROJECT_PRIORITY),
            resource_repository=ResourceRepository.from_dict({
                'resources': data.get('resources', []),
                'teams': data.get('teams', []),
            }),
        )
        
        # Add tasks manually
        project.tasks = [Task.from_dict(task_data) for task_data in data.get('tasks', [])]

        # If tasks exist, update project dates based on tasks
        if project.tasks:
            project._id_to_task = None
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

            # Counted on the plan's own calendar, whatever week either end
            # of the link keeps; see _shift_working_days.
            required = self._shift_working_days(required,
                                                self.lag_days(dependency))

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

    def _shift_working_days(self, moment: datetime, days: int,
                            calendar: Optional[WorkingCalendar] = None
                            ) -> datetime:
        """
        Move a date by a number of working days.

        PARAMETERS:
        -----------
        moment : datetime
            The date a link requires before its lag is applied.
        days : int
            Working days of lag; negative is lead time.
        calendar : Optional[WorkingCalendar]
            The calendar to count them on. The plan's own when not given,
            which is what every caller uses; see the note below.

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

        The plan's calendar rather than either linked task's, and deliberately.
        A lag is a number somebody types onto a link, and it has to mean the
        same thing wherever it is typed: counted on the successor's week, the
        same "2 days" was two days for an ordinary task, two days for a task
        on a 24/7 run, and eight calendar days for one on a weekend-only
        shift - which is not a wait anybody asked for. The successor's own
        calendar still decides where it may start once the wait is over, so
        nothing about its week is lost; only the length of the wait is held
        steady.
        """
        if not days:
            return moment
        calendar = calendar or self.calendar
        if days > 0:
            return calendar.add_working_days(moment, days + 1)
        return calendar.subtract_working_days(moment, -days + 1)

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
        calendar = self.calendar_for(task)
        start, end = self.constrained_dates(task)
        if start is not None:
            return calendar.get_next_working_day(start)
        if end is None:
            return None

        return calendar.subtract_working_days(end, self.working_duration(task))

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
        return max(self.calendar_for(task).working_days_between(
            task.start_date, task.end_date), 1)

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
        # it happened to be before, which for a phase linked across two of
        # its tasks was the length of the first one.
        holds_span = (required_start is not None and required_end is not None
                      and not task.is_milestone
                      and required_end >= required_start)

        calendar = self.calendar_for(task)

        if holds_span:
            new_start = calendar.get_next_working_day(required_start)
            new_end = calendar.get_next_working_day(required_end)
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
            new_start = calendar.get_next_working_day(required_start)
            if preserve_duration and task.end_date is not None:
                new_end = calendar.add_working_days(new_start, duration)
        elif required_end is not None:
            # Forward, not back, for a finish landing on a weekend. A link
            # says a task may not finish before a date, so pulling it back to
            # the Friday would break the link it is being moved to satisfy.
            new_end = calendar.get_next_working_day(required_end)
            if preserve_duration:
                new_start = calendar.subtract_working_days(new_end, duration)

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
                calendar.working_days_between(new_start, new_end), 1)

        return True

    def _pull_branch_after_its_links(self, summary: Task) -> bool:
        """
        Move a row that holds work, and the work with it, to obey its links.

        PARAMETERS:
        -----------
        summary : Task
            A row with children, which is therefore bracketing them.

        RETURNS:
        --------
        bool
            True when the branch moved.

        DEVELOPMENT NOTES:
        ------------------
        A row that holds work has no dates of its own: it spans its
        children, and roll_up_summaries writes it from them on every pass.
        The link pass therefore skipped such rows altogether, which meant a
        link *to* one was made, drawn on the chart, and never obeyed - "the
        one behind it didn't jump after it, it's just nicely tied there with
        a red dot".

        The link is answered where the dates actually live. What the links
        require of the summary is asked of constrained_dates, which reads
        without writing, and the whole branch is then moved by that many
        calendar days - the uniform shift shift_to_start uses on a whole
        plan, for the same reason: every row keeps its length, two rows keep
        the gap between them, and a link inside the branch that was
        satisfied stays satisfied because both of its ends moved together.

        The summary's own dates are moved with the rest so the plan is never
        momentarily inconsistent, and roll_up_summaries rebuilds them from
        the children later in the same pass.

        Only ever later, like the rest of the pass - see forward_only on
        apply_dependency_constraints. A branch dragged backwards by a link
        would undo dates somebody set on purpose.

        The working calendar is enforced afterwards, inside the same loop,
        so a child landing on a Saturday is pushed to the Monday. That makes
        the shift not quite uniform for those rows, which is the right way
        round: work does not happen on a day nobody works.
        """
        required_start, _required_end = self.constrained_dates(summary)
        if required_start is None or summary.start_date is None:
            return False

        delta = as_date(required_start) - as_date(summary.start_date)
        if delta.days <= 0:
            return False

        branch = self._descendant_ids(summary.id) | {summary.id}
        for task_id in branch:
            task = self.get_task_by_id(task_id)
            if task is None:
                continue
            if task.start_date is not None:
                task.start_date += delta
            if task.end_date is not None:
                task.end_date += delta
            if task.earliest_begin is not None:
                task.earliest_begin += delta

        logger.info("Moved %r and the %d row(s) it holds %d day(s), to follow "
                    "what it waits for", summary.name, len(branch) - 1,
                    delta.days)
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

    def apply_calendar(self, calendar: WorkingCalendar,
                       calendars: Optional[CalendarRegistry] = None) -> bool:
        """
        Change which days the project works, holding what every task contains.

        PARAMETERS:
        -----------
        calendar : WorkingCalendar
            The calendar to schedule on from now on - the plan's own, which
            every task follows unless it names another.
        calendars : Optional[CalendarRegistry]
            The named calendars to go with it. Left alone when not given, so
            a caller changing only the plan's week does not have to hand the
            registry back to keep it.

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
        if calendars is not None:
            self.calendars = calendars
        moved = False

        for task in self.tasks:
            if task.is_container:
                continue

            # The task's own calendar, not the one just passed in: a task
            # following a named calendar is not rebuilt on the plan's week
            # just because the plan's week changed.
            task_calendar = self.calendar_for(task)

            new_start = task_calendar.get_next_working_day(task.start_date)
            if task.effective_milestone or task.end_date is None:
                new_end = None
            else:
                new_end = task_calendar.add_working_days(new_start,
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
            overrides=self.calendar.sorted_overrides(),
        )
        return self.apply_calendar(calendar)

    def set_calendars(self, calendars) -> bool:
        """
        Replace the named calendars a task may follow.

        PARAMETERS:
        -----------
        calendars : Iterable[NamedCalendar] or CalendarRegistry
            The complete set from now on, not additions to it. The settings
            dialog hands back everything it holds, so a calendar deleted
            there has to disappear here, which a merge would not do.

        RETURNS:
        --------
        bool
            True when the plan moved.

        DEVELOPMENT NOTES:
        ------------------
        Applied through apply_calendar, like the plan's own calendar and for
        the same reason: a task following a calendar whose week has just
        changed keeps the work it holds and has its finish moved. Editing a
        weekend calendar to add Friday should pull its tasks in, not quietly
        give each of them another day of effort.

        A task naming a calendar that is not in the new set is not touched.
        It falls back to the plan's own through calendar_for, which is what
        makes deleting a calendar safe without walking the whole plan.
        """
        registry = (calendars if isinstance(calendars, CalendarRegistry)
                    else CalendarRegistry(calendars))
        return self.apply_calendar(self.calendar, registry)

    def set_working_week(self, non_working_days) -> bool:
        """
        Change which weekdays the project works at all.

        PARAMETERS:
        -----------
        non_working_days : Iterable[int]
            Weekday indices never worked, as date.weekday() numbers them -
            Monday 0 through Sunday 6. The standard {5, 6} is Saturday and
            Sunday off; {6} alone is a six-day week.

        RETURNS:
        --------
        bool
            True when the plan moved. False when the week was refused, which
            leaves the calendar exactly as it was.

        DEVELOPMENT NOTES:
        ------------------
        A week with no working day in it is refused here rather than stored.
        WorkingCalendar tolerates one - it treats such a calendar as working
        every day, so a corrupted file cannot hang the day-by-day walks
        looking for a working day that does not exist - but that is damage
        limitation for bad data, not an answer to somebody asking for it. A
        plan told to work no days would come back scheduling seven of them,
        which is the opposite of what was asked and says so only in the log.

        Otherwise a sibling of set_holiday_countries and set_date_overrides,
        applied the same way and for the same reason: through apply_calendar,
        so every task keeps the work it holds and its finish moves. Putting
        Saturday to work should pull the finishes of the tasks crossing it in
        rather than quietly handing each of them another day of effort.
        """
        week = {int(day) for day in non_working_days}

        if not set(range(7)) - week:
            logger.warning(
                "Refusing a working week with no working day in it; the "
                "calendar is unchanged"
            )
            return False

        calendar = WorkingCalendar(
            non_working_days=week,
            holidays=self.calendar.holidays,
            recurring_holidays=self.calendar.recurring_holidays,
            countries=self.calendar.countries,
            overrides=self.calendar.sorted_overrides(),
        )
        return self.apply_calendar(calendar)

    def set_date_overrides(self, overrides) -> bool:
        """
        Replace the hand-made rulings on individual dates.

        PARAMETERS:
        -----------
        overrides : Iterable[DateOverride]
            The complete list of rulings from now on - not additions to what
            is already there. The overrides tab hands back everything it is
            showing, so a deletion in it has to remove the ruling here, which
            a merge would not do.

        RETURNS:
        --------
        bool
            True when the plan moved.

        DEVELOPMENT NOTES:
        ------------------
        A sibling of set_holiday_countries, and applied the same way and for
        the same reason: through apply_calendar, so a task keeps the work it
        holds and its finish moves. Naming a Saturday as worked should pull
        the finishes of the tasks crossing it *in* by a day, not quietly hand
        every one of them an extra day of effort.
        """
        calendar = WorkingCalendar(
            non_working_days=self.calendar.non_working_days,
            holidays=self.calendar.holidays,
            recurring_holidays=self.calendar.recurring_holidays,
            countries=self.calendar.countries,
            overrides=overrides,
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

        Containers are skipped. A row with children takes its dates from
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

            calendar = self.calendar_for(task)
            new_start = calendar.get_next_working_day(wanted)

            if task.effective_milestone:
                new_end = None
            elif task.end_date is None:
                # Nothing states how long it is, so there is no finish to work
                # out - only the start to move off the weekend.
                new_end = None
            else:
                duration = self.working_duration(task)
                new_end = calendar.add_working_days(new_start, duration)

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
                # An empty Phase holds no work, so none of it
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
            # Rolling the dates up for the named container types alone left
            # every other parent holding whatever dates it had: a
            # plain Task with sub-tasks stopped spanning them, and so did
            # every parent the importers build - a Mermaid section, a
            # spreadsheet phase, a nested GanttProject task all arrive as
            # ordinary Tasks. Which progress rule applies still goes by type.
            # The span a row holds is what it now says it holds. A summary
            # that kept the duration it was created with had two answers for
            # its own length, and the working-calendar pass believed the
            # stored one: it rebuilt the finish from the number while this
            # rebuilt it from the children, and the two took turns for all
            # twelve passes of the reschedule loop, which then reported a
            # cycle in links that had none and left the dates wherever the
            # last pass happened to put them. Every action ran the loop
            # again and left them somewhere else - which is what a project
            # manager saw as a plan that "totally scrambles the dates" on
            # its collectors.
            new_duration = max(
                self.calendar_for(task).working_days_between(
                    new_start, new_end), 1)

            if (task.start_date != new_start or task.end_date != new_end
                    or task.progress != new_progress
                    or (task.duration is not None
                        and task.duration != new_duration)):
                task.start_date = new_start
                task.end_date = new_end
                task.progress = new_progress
                if task.duration is not None:
                    task.duration = new_duration
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
        from their children. A summary's own dates are not written by the
        link pass, because they come from below and writing them would put
        the row out of step with the children it brackets - it is moved by
        moving those children instead; see _pull_branch_after_its_links.

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
                    if self._pull_branch_after_its_links(task):
                        moved = True
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

    def _working_day_axis(self, origin: datetime,
                          tasks: List[Task]) -> Dict[date, int]:
        """
        Every date the plan touches, as working days from its first day.

        RETURNS:
        --------
        Dict[date, int]
            The same number offset() used to count out, for every date from
            the plan's first day to its last.

        DEVELOPMENT NOTES:
        ------------------
        Built once and read, rather than counted from the origin on every
        lookup. Counting made the float analysis O(tasks x span): each of
        two lookups per task walked the whole calendar from the plan's start,
        which came to 211,703 calls to is_working_day on a thousand-task
        plan. Walking the span once and remembering makes it O(span + tasks).

        The plan's own calendar, like the offsets it replaces. A task
        following a calendar of its own is still placed on this axis - it is
        the one ruler every task's float is compared against.
        """
        finish = origin
        for task in tasks:
            end = task.end_date or task.start_date
            if end is not None and end > finish:
                finish = end

        axis: Dict[date, int] = {}
        calendar = self.calendar
        worked = 0
        day = as_date(origin)
        last = as_date(finish)

        while day <= last:
            if calendar.is_working_day(day):
                worked += 1
            axis[day] = max(worked - 1, 0)
            day += timedelta(days=1)

        return axis

    def _analysis_signature(self):
        """
        Everything schedule_analysis reads, as a cheap comparable value.

        RETURNS:
        --------
        tuple
            The dates, lengths, links and calendars the analysis depends on.
            Two plans with the same signature must give the same analysis.

        DEVELOPMENT NOTES:
        ------------------
        A signature rather than explicit invalidation, and deliberately.
        Tasks are mutated directly all over the dialogs - `task.start_date =
        x` - so a cache cleared by hand would have to be cleared from a dozen
        places and would go stale the first time somebody added a
        thirteenth. A signature cannot go stale: it is derived from the same
        state the answer is.

        It is worth doing because it costs nothing beside the answer. At a
        thousand tasks the analysis takes about 140ms and this about 0.3ms.
        The calendars go in exactly, through to_dict, because 10 microseconds
        is not worth risking a wrong answer over - a length-based check would
        miss one holiday being swapped for another.
        """
        return (
            repr(self.calendar.to_dict()),
            tuple(repr(named.calendar.to_dict()) for named in self.calendars),
            tuple(
                (task.id, task.start_date, task.end_date, task.duration,
                 task.is_milestone, task.task_type, task.parent_task_id,
                 task.calendar_id,
                 tuple((link.task_id, link.dep_type, link.hardness,
                        link.lag, link.lag_unit)
                       for link in task.dependencies))
                for task in self.tasks
            ),
        )

    def invalidate_schedule_analysis(self) -> None:
        """
        Forget the cached analysis.

        Not needed in the ordinary way - the signature notices a change on
        its own - but a caller that has done something the signature cannot
        see has a way to say so.
        """
        self._analysis_cache = None
        self._analysis_signature_seen = None

    def schedule_analysis(self) -> Dict[str, 'TaskFloat']:
        """
        Early and late dates, float, and criticality for every task.

        Cached against a signature of the plan; see _analysis_signature. The
        chart asks for this on every redraw - only to decide which bars are
        drawn as critical - so a resize, a zoom or a theme change used to pay
        for the whole forward-and-backward pass again. The mapping returned
        is the cached one and must not be modified by callers.

        RETURNS:
        --------
        Dict[str, TaskFloat]
            One entry per task that holds work, keyed by task ID. Summary
            tasks are left out: they envelope their children rather than
            being work, so a group bar would otherwise outrank the work
            inside it and come out critical on its own account.

        DEVELOPMENT NOTES:
        ------------------
        The critical path method, both passes:

          * **Forward** - the earliest each task can finish. Taken from the
            plan as scheduled rather than recomputed from the network, so a
            task deliberately held back by an earliest begin date, or simply
            placed later, is measured where it actually is. Recomputing would
            answer a different question - how early *could* everything be -
            and would call a task critical that has a fortnight of air in
            front of it.
          * **Backward** - the latest each task could finish without moving
            the project's finish. Every task with no successor may run to the
            end of the plan; every other one must clear the way for what
            follows it.

        Total float is the gap between the two, in working days, and a task
        with none of it is critical: it cannot slip by a day without the
        whole plan finishing later. That is the definition, and it finds
        *every* such task rather than one chain through them - two parallel
        strands of work can both be critical, and a plan that only ever
        highlighted one of them was hiding half the risk.

        Everything is counted in working days offset from the plan's start,
        not in calendar days. A chain that happens to straddle more weekends
        would otherwise outrank one holding more actual work, and the gaps
        the weekends leave would read as float that nobody can use.

        The link types are honoured on the way back. What a predecessor has
        to clear depends on which end the link holds: a Finish-Start
        successor needs it finished, while a Start-Start one only needs it
        started, so the two allow very different amounts of float.
        """
        # getattr rather than attribute access: a Project rebuilt by copy,
        # deepcopy or unpickling gets its __dict__ restored without
        # __post_init__ running, and the undo history copies projects.
        cached = getattr(self, '_analysis_cache', None)
        signature = self._analysis_signature()
        if (cached is not None
                and getattr(self, '_analysis_signature_seen', None) == signature):
            return cached

        analysis = self._compute_schedule_analysis()
        self._analysis_signature_seen = signature
        self._analysis_cache = analysis
        return analysis

    def _compute_schedule_analysis(self) -> Dict[str, 'TaskFloat']:
        """
        Work the analysis out from scratch; see schedule_analysis.

        Kept apart from the caching so the arithmetic can be read - and
        tested - without the memoisation in front of it.
        """
        summary_ids = self.get_summary_task_ids()
        tasks = [t for t in self.tasks if t.id not in summary_ids]
        if not tasks:
            return {}

        by_id = {task.id: task for task in tasks}
        origin = min(task.start_date for task in tasks)

        # Every date the plan touches, counted once - see _working_day_axis
        axis = self._working_day_axis(origin, tasks)

        def offset(moment: datetime) -> int:
            """
            Working days from the plan's first day to a date.

            Measured on the plan's own calendar even where a task follows
            another. This is the axis every task's float is compared on, and
            a task measured against its own week would sit at a different
            number for the same day - so slack between two tasks on different
            calendars would come out as whatever the difference between their
            weeks happened to be.

            Read from a table built once rather than counted from the plan's
            first day on every call; see _working_day_axis. A date outside
            the table - which nothing in the plan should produce - falls back
            to counting, so an unexpected one is slow rather than wrong.
            """
            found = axis.get(as_date(moment))
            if found is not None:
                return found
            return max(self.calendar.working_days_between(origin, moment) - 1, 0)

        # ---- forward: where each task is, as scheduled ------------------
        early_start = {t.id: offset(t.start_date) for t in tasks}

        # Read off the axis rather than added to the start as a length.
        #
        # A task's duration is counted on the calendar that task follows,
        # and the axis counts the plan's. For a plan on one calendar those
        # agree exactly and this is the same number either way. For a task
        # on a calendar of its own they do not: five days of a 24/7 run
        # spans three of the plan's working days, and adding the five put
        # the task's finish two days past where it actually is - which came
        # out as two days of negative float on a task that was never even
        # late. Both ends are measured with the one ruler instead.
        early_finish = {
            t.id: max(offset(t.end_date or t.start_date), early_start[t.id])
            for t in tasks
        }

        #: How much of the axis each task covers. Zero for a milestone, and
        #: for anything else the distance between its own two ends.
        span = {t.id: 0 if t.effective_milestone
                else early_finish[t.id] - early_start[t.id]
                for t in tasks}

        finish = max(early_finish.values())

        # ---- the network, both ways ------------------------------------
        successors: Dict[str, List[Dependency]] = {t.id: [] for t in tasks}
        for task in tasks:
            for dependency in task.dependencies:
                for resolved in self._resolve_to_work(dependency.task_id,
                                                      by_id, summary_ids):
                    successors[resolved].append(
                        Dependency(task_id=task.id,
                                   dep_type=dependency.dep_type,
                                   hardness=dependency.hardness,
                                   lag=dependency.lag,
                                   lag_unit=dependency.lag_unit)
                    )

        # ---- backward: how late each could be without moving the end ----
        #
        # Walked in reverse topological order so a task is answered only once
        # everything that follows it has been. A cycle in the links would
        # never settle, so the pass is capped and what is left keeps the
        # finish date it started with - wrong, but finite and visible.
        late_finish: Dict[str, int] = {}

        def latest_finish(task_id: str) -> int:
            """The latest finish that still clears everything downstream."""
            limit = finish
            for link in successors[task_id]:
                other = by_id.get(link.task_id)
                if other is None:
                    continue
                if other.id not in late_finish:
                    # Reached before its own successors were settled, which
                    # only happens inside a dependency cycle - the order the
                    # backward pass walks is otherwise exactly the order that
                    # prevents it. The edge contributes nothing rather than
                    # the whole analysis failing on a plan that has one.
                    logger.warning(
                        "Link from %r to %r could not be measured; the plan "
                        "probably contains a dependency cycle",
                        by_id[task_id].name, other.name
                    )
                    continue
                other_late_start = late_finish[other.id] - span[other.id]
                # In days, whatever the link states it in. For a link in
                # days this is the link's own number, so the backward pass
                # computes exactly what it computed before; see lag_days.
                lag = self.lag_days(link)
                if link.dep_type == 'FS':
                    allowed = other_late_start - 1 - lag
                elif link.dep_type == 'SS':
                    # Only the start has to clear, so this may run on past it
                    allowed = (other_late_start - lag
                               + span[task_id])
                elif link.dep_type == 'FF':
                    allowed = late_finish[other.id] - lag
                else:                                   # SF
                    allowed = (late_finish[other.id] - lag
                               + span[task_id])
                limit = min(limit, allowed)
            return limit

        for task in self._reverse_schedule_order(tasks, successors):
            late_finish[task.id] = latest_finish(task.id)

        for task in tasks:
            late_finish.setdefault(task.id, finish)

        analysis: Dict[str, TaskFloat] = {}
        for task in tasks:
            late = late_finish[task.id]
            total_float = late - early_finish[task.id]
            analysis[task.id] = TaskFloat(
                task_id=task.id,
                early_start=early_start[task.id],
                early_finish=early_finish[task.id],
                late_start=late - span[task.id],
                late_finish=late,
                total_float=total_float,
                is_critical=total_float <= 0,
            )

        return analysis

    def _resolve_to_work(self, task_id: str, by_id: Dict[str, Task],
                         summary_ids: Set[str]) -> List[str]:
        """
        The tasks that hold the work a dependency refers to.

        DEVELOPMENT NOTES:
        ------------------
        Depending on a summary means depending on the work inside it, so a
        summary reference resolves to its non-summary descendants. Imported
        GanttProject files rely on this heavily - several tasks there depend
        on a parent - and dropping those edges would cut the network in half.
        """
        if task_id in by_id:
            return [task_id]

        children = self._children_by_parent()
        found: List[str] = []
        stack = [task_id]
        seen: Set[str] = set()
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            for child in children.get(current, []):
                if child.id in by_id:
                    found.append(child.id)
                else:
                    stack.append(child.id)
        return found

    @staticmethod
    def _reverse_schedule_order(tasks: List[Task],
                                successors: Dict[str, List['Dependency']]
                                ) -> List[Task]:
        """
        Tasks ordered so everything that follows one comes before it.

        The order the backward pass needs: a task's latest finish depends on
        its successors', so those have to be settled first. A depth-first
        walk with an explicit stack, guarded so a cycle in the links stops
        rather than looping.
        """
        by_id = {task.id: task for task in tasks}
        ordered: List[Task] = []
        placed: Set[str] = set()
        in_progress: Set[str] = set()

        for root in tasks:
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
                for link in successors.get(task.id, []):
                    following = by_id.get(link.task_id)
                    if (following is not None
                            and following.id not in placed
                            and following.id not in in_progress):
                        stack.append((following, False))

        return ordered

    def get_critical_path(self) -> List[Task]:
        """
        Every task that cannot slip without moving the project's finish.

        RETURNS:
        --------
        List[Task]
            The tasks with no float, in the order the plan holds them. Empty
            for a project with no tasks.

        DEVELOPMENT NOTES:
        ------------------
        This used to return a single chain: the longest run of dependent
        tasks ending at whatever finished last. That is one critical path
        rather than the critical path, and a plan whose risk sits in two
        parallel strands had half of it hidden - the chart coloured one
        strand and left the other looking like ordinary work with room to
        spare, which it did not have.

        Criticality is now what it is defined as: zero total float, from the
        forward and backward passes in schedule_analysis. Two strands that
        both drive the finish both come out critical, and a chain with a day
        of slack in it correctly comes out with none of its tasks on the
        path.

        Returned in plan order rather than chain order. There is no longer
        one chain to order by, and the plan's own order is what the task list
        and the chart draw.
        """
        analysis = self.schedule_analysis()
        if not analysis:
            return []

        return [task for task in self.tasks
                if task.id in analysis and analysis[task.id].is_critical]
