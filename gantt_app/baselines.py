"""
Baseline Management Engine & Variance Analysis.

Captures, retains, tracks and compares up to 10 project schedule baselines,
providing full baseline-versus-current variance analysis across task dates,
durations, effort and cost.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from gantt_app.models import Project, Task
from gantt_app.resource_model import ResourceRepository
from gantt_app.utils.log import get_logger
from gantt_app.workdaycalendar import WorkingCalendar, as_date

logger = get_logger(__name__)

MAX_BASELINES = 10


def _task_work_hours(task: Task) -> float:
    """Total allocated work hours for a task."""
    total = 0.0
    for assignment in (task.resource_assignments or []):
        hours = float(assignment.get("estimated_hours", 0.0) or 0.0)
        split = float(assignment.get("resource_split", 100.0) or 100.0)
        total += hours * (split / 100.0)
    return total


def _task_cost(task: Task, repository: ResourceRepository) -> float:
    """Estimated cost for a task from resource/team hourly rates."""
    total = 0.0
    for assignment in (task.resource_assignments or []):
        hours = float(assignment.get("estimated_hours", 0.0) or 0.0)
        split = float(assignment.get("resource_split", 100.0) or 100.0)
        allocated = hours * (split / 100.0)
        resource_id = assignment.get("resource_id")
        if not resource_id:
            continue
        entity = repository.resources.get(resource_id) or repository.teams.get(resource_id)
        if entity is None:
            continue
        rate = getattr(entity, "cost_per_hour", 0.0) or 0.0
        total += allocated * rate
    return total


def _working_day_shift(current: Optional[datetime],
                       baseline: Optional[datetime],
                       calendar: WorkingCalendar) -> Optional[int]:
    """Signed working-day offset of current date relative to baseline."""
    if current is None or baseline is None:
        return None
    cur = as_date(current)
    base = as_date(baseline)
    if cur == base:
        return 0
    if cur > base:
        return calendar.working_days_between(base + timedelta(days=1), cur)
    return -calendar.working_days_between(cur, base - timedelta(days=1))


def _to_iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value is not None else None


def _from_iso(value: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(value) if value else None


@dataclass
class TaskBaseline:
    task_id: str
    name: str
    start_date: Optional[datetime] = None
    finish_date: Optional[datetime] = None
    duration: Optional[int] = None
    work_hours: float = 0.0
    cost: float = 0.0
    progress: int = 0
    parent_task_id: Optional[str] = None
    task_type: str = "Task"
    is_milestone: bool = False
    resource_assignments: List[Dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "start_date": _to_iso(self.start_date),
            "finish_date": _to_iso(self.finish_date),
            "duration": self.duration,
            "work_hours": self.work_hours,
            "cost": self.cost,
            "progress": self.progress,
            "parent_task_id": self.parent_task_id,
            "task_type": self.task_type,
            "is_milestone": self.is_milestone,
            "resource_assignments": self.resource_assignments,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TaskBaseline":
        return cls(
            task_id=data["task_id"],
            name=data["name"],
            start_date=_from_iso(data.get("start_date")),
            finish_date=_from_iso(data.get("finish_date")),
            duration=data.get("duration"),
            work_hours=data.get("work_hours", 0.0),
            cost=data.get("cost", 0.0),
            progress=data.get("progress", 0),
            parent_task_id=data.get("parent_task_id"),
            task_type=data.get("task_type", "Task"),
            is_milestone=data.get("is_milestone", False),
            resource_assignments=data.get("resource_assignments", []),
        )


@dataclass
class ProjectBaseline:
    name: str = ""
    saved_at: Optional[datetime] = None
    task_snapshots: Dict[str, TaskBaseline] = field(default_factory=dict)
    project_start: Optional[datetime] = None
    project_finish: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "saved_at": _to_iso(self.saved_at),
            "task_snapshots": {
                tid: snap.to_dict()
                for tid, snap in self.task_snapshots.items()
            },
            "project_start": _to_iso(self.project_start),
            "project_finish": _to_iso(self.project_finish),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProjectBaseline":
        snapshots = {
            tid: TaskBaseline.from_dict(snap)
            for tid, snap in data.get("task_snapshots", {}).items()
        }
        return cls(
            name=data.get("name", ""),
            saved_at=_from_iso(data.get("saved_at")),
            task_snapshots=snapshots,
            project_start=_from_iso(data.get("project_start")),
            project_finish=_from_iso(data.get("project_finish")),
        )


@dataclass
class TaskVariance:
    task_id: str
    baseline_start: Optional[datetime] = None
    current_start: Optional[datetime] = None
    start_variance_days: Optional[int] = None
    baseline_finish: Optional[datetime] = None
    current_finish: Optional[datetime] = None
    finish_variance_days: Optional[int] = None
    baseline_duration: Optional[int] = None
    current_duration: Optional[int] = None
    duration_variance_days: Optional[int] = None
    baseline_work: float = 0.0
    current_work: float = 0.0
    work_variance_hours: float = 0.0
    baseline_cost: float = 0.0
    current_cost: float = 0.0
    cost_variance: float = 0.0

    def variance_sign(self) -> Dict[str, str]:
        """Return a sign label for each variance type."""
        def sign(value):
            if value is None:
                return ""
            if value > 0:
                return "positive"
            if value < 0:
                return "negative"
            return "zero"
        return {
            "start": sign(self.start_variance_days),
            "finish": sign(self.finish_variance_days),
            "duration": sign(self.duration_variance_days),
            "work": sign(self.work_variance_hours),
            "cost": sign(self.cost_variance),
        }


@dataclass
class BaselineSlot:
    number: int
    display_name: str = ""
    saved_at: Optional[datetime] = None
    active: bool = False
    baseline: Optional[ProjectBaseline] = None

    def __post_init__(self):
        if not self.display_name:
            self.display_name = f"Baseline {self.number}"

    @property
    def is_set(self) -> bool:
        return self.baseline is not None

    def status_label(self) -> str:
        if not self.is_set:
            return f"{self.display_name} (Unset)"
        timestamp = self.saved_at.strftime("%Y-%m-%d %H:%M") if self.saved_at else "Unknown"
        active = " [Active]" if self.active else ""
        return f"{self.display_name} (Saved: {timestamp}){active}"

    def to_dict(self) -> dict:
        return {
            "number": self.number,
            "display_name": self.display_name,
            "saved_at": _to_iso(self.saved_at),
            "active": self.active,
            "baseline": self.baseline.to_dict() if self.baseline else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BaselineSlot":
        baseline = None
        if data.get("baseline"):
            baseline = ProjectBaseline.from_dict(data["baseline"])
        return cls(
            number=data["number"],
            display_name=data.get("display_name") or f"Baseline {data['number']}",
            saved_at=_from_iso(data.get("saved_at")),
            active=data.get("active", False),
            baseline=baseline,
        )


class BaselineManager:
    """Manage up to 10 schedule baselines for a project."""

    def __init__(self):
        self.slots: List[BaselineSlot] = [
            BaselineSlot(number=n) for n in range(1, MAX_BASELINES + 1)
        ]

    @property
    def active_slot_number(self) -> Optional[int]:
        for slot in self.slots:
            if slot.active:
                return slot.number
        return None

    @active_slot_number.setter
    def active_slot_number(self, number: Optional[int]):
        for slot in self.slots:
            slot.active = (slot.number == number)

    def get_slot(self, number: int) -> Optional[BaselineSlot]:
        if 1 <= number <= MAX_BASELINES:
            return self.slots[number - 1]
        return None

    def set_active(self, number: Optional[int]) -> Optional[BaselineSlot]:
        logger.info("Active baseline set to %s", number)
        self.active_slot_number = number
        return self.get_slot(number) if number else None

    def set_baseline(self, project: Project, number: int,
                     task_ids: Optional[List[str]] = None,
                     rollup: bool = False,
                     set_active: bool = True) -> BaselineSlot:
        slot = self.get_slot(number)
        if slot is None:
            raise ValueError(f"Invalid baseline number {number}")
        logger.info("Setting baseline %d with %d tasks (rollup=%s)",
                    number, len(project.tasks), rollup)
        slot.baseline = self._capture(project, task_ids, rollup)
        slot.saved_at = datetime.now()
        if set_active:
            self.active_slot_number = number
        logger.info("Baseline %d saved at %s", number, slot.saved_at)
        return slot

    def clear_baseline(self, number: int,
                       task_ids: Optional[List[str]] = None) -> BaselineSlot:
        slot = self.get_slot(number)
        if slot is None:
            raise ValueError(f"Invalid baseline number {number}")
        if slot.baseline is None:
            return slot
        logger.info("Clearing baseline %d (selected=%s)", number,
                    task_ids is not None)
        if task_ids is None:
            slot.baseline = None
            slot.saved_at = None
        else:
            for task_id in task_ids:
                slot.baseline.task_snapshots.pop(task_id, None)
            self._recompute_project_dates(slot.baseline)
            if not slot.baseline.task_snapshots:
                slot.baseline = None
                slot.saved_at = None
        if self.active_slot_number == number and slot.baseline is None:
            self.active_slot_number = None
        return slot

    def rename_slot(self, number: int, name: str) -> BaselineSlot:
        slot = self.get_slot(number)
        if slot is None:
            raise ValueError(f"Invalid baseline number {number}")
        old = slot.display_name
        slot.display_name = name.strip() or f"Baseline {number}"
        logger.info("Renamed baseline %d from %r to %r", number, old,
                    slot.display_name)
        return slot

    def compare(self, project: Project, number: Optional[int] = None,
                calendar: Optional[WorkingCalendar] = None) -> Dict[str, TaskVariance]:
        if number is None:
            number = self.active_slot_number
        slot = self.get_slot(number) if number else None
        if slot is None or slot.baseline is None:
            logger.debug("No baseline to compare for slot %s", number)
            return {}
        baseline = slot.baseline
        logger.info("Comparing project against baseline %d", number)
        cal = calendar or project.calendar
        variances = {}
        for task in project.tasks:
            snapshot = baseline.task_snapshots.get(task.id)
            if snapshot is None:
                continue
            tv = TaskVariance(task_id=task.id)
            tv.baseline_start = snapshot.start_date
            tv.current_start = task.start_date
            tv.start_variance_days = _working_day_shift(
                task.start_date, snapshot.start_date, cal)
            tv.baseline_finish = snapshot.finish_date
            tv.current_finish = task.end_date
            tv.finish_variance_days = _working_day_shift(
                task.end_date, snapshot.finish_date, cal)
            tv.baseline_duration = snapshot.duration
            tv.current_duration = task.duration_days
            if snapshot.duration is not None and task.duration_days is not None:
                tv.duration_variance_days = task.duration_days - snapshot.duration
            tv.baseline_work = snapshot.work_hours
            tv.current_work = _task_work_hours(task)
            tv.work_variance_hours = tv.current_work - snapshot.work_hours
            tv.baseline_cost = snapshot.cost
            tv.current_cost = _task_cost(task, project.resource_repository)
            tv.cost_variance = tv.current_cost - snapshot.cost
            variances[task.id] = tv
        return variances

    def _capture(self, project: Project, task_ids: Optional[List[str]],
                 rollup: bool) -> ProjectBaseline:
        task_set = set(task_ids) if task_ids else None
        snapshots: Dict[str, TaskBaseline] = {}
        for task in project.tasks:
            if task_set is not None and task.id not in task_set:
                continue
            snapshots[task.id] = TaskBaseline(
                task_id=task.id,
                name=task.name,
                start_date=task.start_date,
                finish_date=task.end_date,
                duration=task.duration_days,
                work_hours=_task_work_hours(task),
                cost=_task_cost(task, project.resource_repository),
                progress=task.progress,
                parent_task_id=task.parent_task_id,
                task_type=task.task_type,
                is_milestone=task.is_milestone,
                resource_assignments=[dict(a) for a in (task.resource_assignments or [])],
            )
        if rollup:
            snapshots = self._rollup(snapshots, project)
        baseline = ProjectBaseline(
            saved_at=datetime.now(),
            task_snapshots=snapshots,
        )
        self._recompute_project_dates(baseline)
        return baseline

    @staticmethod
    def _rollup(snapshots: Dict[str, TaskBaseline],
                project: Project) -> Dict[str, TaskBaseline]:
        by_parent: Dict[str, List[TaskBaseline]] = {}
        for snap in snapshots.values():
            if snap.parent_task_id:
                by_parent.setdefault(snap.parent_task_id, []).append(snap)
        for task in project.tasks:
            if not task.is_container:
                continue
            children = by_parent.get(task.id, [])
            if not children:
                continue
            starts = [c.start_date for c in children if c.start_date]
            finishes = [c.finish_date for c in children if c.finish_date]
            if task.id not in snapshots:
                snapshots[task.id] = TaskBaseline(
                    task_id=task.id,
                    name=task.name,
                    parent_task_id=task.parent_task_id,
                    task_type=task.task_type,
                    is_milestone=task.is_milestone,
                )
            snap = snapshots[task.id]
            if starts:
                snap.start_date = min(starts)
            if finishes:
                snap.finish_date = max(finishes)
            if snap.start_date and snap.finish_date:
                snap.duration = project.calendar.working_days_between(
                    snap.start_date, snap.finish_date)
            snap.work_hours = sum(c.work_hours for c in children)
            snap.cost = sum(c.cost for c in children)
            snap.progress = int(round(
                sum(c.progress for c in children) / len(children)))
        return snapshots

    @staticmethod
    def _recompute_project_dates(baseline: ProjectBaseline):
        starts = [s.start_date for s in baseline.task_snapshots.values() if s.start_date]
        finishes = [s.finish_date for s in baseline.task_snapshots.values() if s.finish_date]
        baseline.project_start = min(starts) if starts else None
        baseline.project_finish = max(finishes) if finishes else None

    def to_dict(self) -> dict:
        return {
            "active_slot": self.active_slot_number,
            "slots": [slot.to_dict() for slot in self.slots],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BaselineManager":
        manager = cls()
        if data and "slots" in data:
            for slot_data in data["slots"]:
                number = slot_data.get("number")
                if isinstance(number, int) and 1 <= number <= MAX_BASELINES:
                    manager.slots[number - 1] = BaselineSlot.from_dict(slot_data)
        active = data.get("active_slot") if data else None
        if active:
            manager.active_slot_number = active
        return manager
