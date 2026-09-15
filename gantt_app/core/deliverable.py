"""
Deliverables - what the plan produces, tracked apart from the work that
produces it.

WHY THIS MODULE EXISTS:
======================
A deliverable is not a task. It carries no start date, no duration, no
dependency links and no calendar, so it takes no part in scheduling: the
Deliverables tab is a checklist of what is owed, not another way of drawing
the plan. Making it a task type would drag every deliverable onto the Gantt
chart and into the reschedule loop, which is the reason the old Deliverable
task type was retired - see RETIRED_TASK_TYPES in gantt_app.core.models.

What it shares with Task is the shape of the list it lives in: a flat
Project.deliverables collection linked by parent_id, so every hierarchy
operation the task list knows - indent, outdent, re-parent, order - has a
direct equivalent here.

DEVELOPMENT NOTES:
------------------
Progress and status are stored separately and kept in step by the writers
rather than derived from each other. A leaf's status follows its progress
(0 is To Do, 100 is Done, anything between is In Progress) unless somebody
says otherwise, and setting a status writes the matching progress. A
deliverable with children takes its progress from them and its status from
that progress; see roll_up_deliverables on Project.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
import logging
import uuid

# The standard library directly rather than utils.log.get_logger, for the
# same reason models.py does: this is the bottom layer, and utils imports it.
logger = logging.getLogger(__name__)

from gantt_app.core.priority import DEFAULT_PRIORITY, PRIORITY_LEVELS


#: What a deliverable may be. To Do is the default and the first value, so a
#: dropdown opens on it.
DELIVERABLE_STATUSES = ('To Do', 'In Progress', 'Done')


def status_for_progress(progress: int) -> str:
    """
    The status a percentage reads as.

    A leaf with no status chosen shows what its progress says: nothing
    started, underway, or done. The three statuses carry no information the
    percentage does not, so the display derives one from the other rather
    than storing two answers that can disagree.
    """
    progress = max(0, min(100, int(progress or 0)))
    if progress >= 100:
        return 'Done'
    if progress > 0:
        return 'In Progress'
    return 'To Do'


def progress_for_status(status: str, current: int = 0) -> int:
    """
    The percentage a status writes onto a leaf.

    Done is 100 and To Do is 0. In Progress keeps whatever partial progress
    the row already holds - a row at 60% marked In Progress is still 60% -
    and starts at 1 for a row that held none, so the answer is never "in
    progress at nothing".
    """
    if status == 'Done':
        return 100
    if status == 'To Do':
        return 0
    current = max(0, min(100, int(current or 0)))
    return current if 0 < current < 100 else 1


def rolled_up_deliverable_progress(children) -> int:
    """
    The completion a deliverable takes from the items under it.

    PARAMETERS:
    -----------
    children : list
        Its direct children. Deeper levels have already settled by the time
        this is asked - the caller walks deepest first, the way
        Project.roll_up_summaries does for tasks.

    RETURNS:
    --------
    int
        A percentage from 0 to 100. An empty deliverable is 0.

    WHAT THE RULE IS:
    -----------------
    A weighted average: each child counts for its weight, which defaults to
    1. A plan that never sets a weight gets the plain average the formula
    reduces to - (sum of progresses) / (number of children) - which is also
    the answer when every weight is 0, since a row that counts for nothing
    cannot all count for nothing.
    """
    if not children:
        return 0

    percentages = [max(0, min(100, child.progress)) for child in children]
    try:
        weights = [max(0.0, float(getattr(child, 'weight', 1.0) or 0.0))
                   for child in children]
    except (TypeError, ValueError):
        weights = [1.0] * len(children)

    total_weight = sum(weights)
    if total_weight <= 0:
        return int(round(sum(percentages) / len(percentages)))
    return int(round(
        sum(weight * percent
            for weight, percent in zip(weights, percentages)) / total_weight
    ))


@dataclass
class Deliverable:
    """
    One deliverable or sub-deliverable in the Deliverables tab.

    Attributes:
        id: Unique identifier
        name: Display name; may be blank, like a task's
        parent_id: The deliverable it sits under, or None at the top level
        status: One of DELIVERABLE_STATUSES
        progress: Completion percentage (0-100); rolled up while it has
            children
        weight: How much this row counts in its parent's progress
        assignee: Who it belongs to - a resource name or free text
        due_date: When it is owed, or None
        priority: One of PRIORITY_LEVELS
        tags: Free-text tags, shown comma-joined
        details: Notes - description, acceptance criteria
    """
    id: str
    name: str = ""
    parent_id: Optional[str] = None
    status: str = 'To Do'
    progress: int = 0
    weight: float = 1.0
    assignee: str = ""
    due_date: Optional[datetime] = None
    priority: str = DEFAULT_PRIORITY
    tags: List[str] = field(default_factory=list)
    details: str = ""

    def __post_init__(self):
        """Coerce whatever arrived into the values the field means."""
        try:
            self.progress = max(0, min(100, int(self.progress or 0)))
        except (TypeError, ValueError):
            self.progress = 0

        # A status the app does not know - a hand-edited file, an import -
        # reads as what the progress says rather than failing the row.
        if self.status not in DELIVERABLE_STATUSES:
            self.status = status_for_progress(self.progress)

        try:
            self.weight = float(self.weight)
        except (TypeError, ValueError):
            self.weight = 1.0
        if self.weight < 0:
            self.weight = 0.0

        if self.priority not in PRIORITY_LEVELS:
            self.priority = DEFAULT_PRIORITY

        self.tags = [str(tag) for tag in (self.tags or []) if str(tag)]
        self.details = str(self.details or '')
        self.assignee = str(self.assignee or '')
        self.name = str(self.name or '')

    @property
    def is_done(self) -> bool:
        """Whether this row is finished; anything short of 100 is not."""
        return self.progress >= 100

    @classmethod
    def create(cls, name: str = "", parent_id: Optional[str] = None,
               deliverable_id: Optional[str] = None, **kwargs) -> 'Deliverable':
        """
        A new deliverable.

        PARAMETERS:
        -----------
        deliverable_id : str, optional
            Identifier to use. Pass Project.next_deliverable_id() for
            sequential numbering; omitted, a UUID is generated so callers
            without a project to hand still get a unique ID.
        """
        return cls(id=deliverable_id or str(uuid.uuid4()),
                   name=name, parent_id=parent_id, **kwargs)

    def to_dict(self) -> dict:
        """Convert to a dictionary for serialization."""
        return {
            'id': self.id,
            'name': self.name,
            'parent_id': self.parent_id,
            'status': self.status,
            'progress': self.progress,
            'weight': self.weight,
            'assignee': self.assignee,
            'due_date': (self.due_date.isoformat()
                         if self.due_date else None),
            'priority': self.priority,
            'tags': list(self.tags),
            'details': self.details,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Deliverable':
        """
        Build a deliverable from a saved dictionary.

        DEVELOPMENT NOTES:
        ------------------
        The date is parsed here rather than left to the file reader's
        *_date convention: that convention only walks the top level and the
        'tasks' list it knows about, so a 'deliverables' key would reach
        here with the date still a string. The Task.from_dict pattern does
        the same for its own dates.
        """
        due_date = data.get('due_date')
        if isinstance(due_date, str):
            try:
                due_date = datetime.fromisoformat(due_date)
            except (TypeError, ValueError):
                due_date = None
        elif not isinstance(due_date, datetime) and due_date is not None:
            due_date = None

        return cls(
            id=str(data.get('id') or uuid.uuid4()),
            name=str(data.get('name') or ''),
            parent_id=data.get('parent_id') or None,
            status=data.get('status', 'To Do'),
            progress=data.get('progress', 0),
            weight=data.get('weight', 1.0),
            assignee=data.get('assignee') or '',
            due_date=due_date,
            priority=data.get('priority', DEFAULT_PRIORITY),
            tags=list(data.get('tags') or []),
            details=str(data.get('details') or ''),
        )
