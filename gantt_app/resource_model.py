from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
import uuid


logger = logging.getLogger(__name__)
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
DAY_LABELS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
FTE_WEEKLY_HOURS = 40.0


class ResourceType(Enum):
    NAMED = "named"
    GENERIC = "generic"
    TEAM = "team"


class SchedulePattern(Enum):
    STANDARD = "Standard (Mon-Fri)"
    FULL_WEEK = "Full Week (Mon-Sun)"
    WEEKEND_ONLY = "Weekend Only (Sat-Sun)"
    CONTINUOUS = "24/7 Operation"
    CUSTOM = "Custom Daily Breakdown"

    @classmethod
    def read(cls, value):
        if isinstance(value, cls):
            return value
        aliases = {
            "Standard Mon-Fri": cls.STANDARD,
            "Full Week Mon-Sun": cls.FULL_WEEK,
            "Weekend Only": cls.WEEKEND_ONLY,
            "Custom": cls.CUSTOM,
        }
        return aliases[value] if value in aliases else cls(value)


PATTERN_DEFAULTS = {
    SchedulePattern.STANDARD: dict(zip(DAYS, (8, 8, 8, 8, 8, 0, 0))),
    SchedulePattern.FULL_WEEK: dict.fromkeys(DAYS, FTE_WEEKLY_HOURS / 7),
    SchedulePattern.WEEKEND_ONLY: dict(zip(DAYS, (0, 0, 0, 0, 0, 8, 8))),
    SchedulePattern.CONTINUOUS: dict.fromkeys(DAYS, 24.0),
    SchedulePattern.CUSTOM: dict.fromkeys(DAYS, 0.0),
}


def default_daily_capacity(pattern: SchedulePattern) -> Dict[str, float]:
    return {day: float(hours) for day, hours in PATTERN_DEFAULTS[pattern].items()}


def distribute_weekly_capacity(pattern: SchedulePattern,
                               weekly_hours: float) -> Dict[str, float]:
    active = [day for day, hours in PATTERN_DEFAULTS[pattern].items() if hours]
    if not active:
        active = list(DAYS)
    per_day = weekly_hours / len(active)
    return {day: per_day if day in active else 0.0 for day in DAYS}


def capacity_from_entry(pattern: SchedulePattern, value: float,
                        unit: str) -> Dict[str, float]:
    if value < 0:
        raise ValueError("Capacity cannot be negative")
    if unit == "FTE":
        return distribute_weekly_capacity(pattern, value * FTE_WEEKLY_HOURS)
    if unit == "Weekly Hours":
        return distribute_weekly_capacity(pattern, value)
    if unit == "Daily Hours":
        active = [day for day, hours in PATTERN_DEFAULTS[pattern].items() if hours]
        if not active:
            active = list(DAYS)
        return {day: value if day in active else 0.0 for day in DAYS}
    raise ValueError(f"Unknown capacity unit: {unit}")


def _validated_daily(values: Dict[str, float], maximum: Optional[float] = 24) -> Dict[str, float]:
    if not isinstance(values, dict):
        raise ValueError("Daily capacity must be a mapping")
    result = {}
    for day in DAYS:
        try:
            hours = float(values.get(day, 0.0))
        except (TypeError, ValueError) as error:
            raise ValueError(f"Capacity for {day} must be a number") from error
        if hours < 0 or (maximum is not None and hours > maximum):
            raise ValueError("Daily capacity must be between 0 and 24 hours")
        result[day] = hours
    return result


@dataclass(frozen=True)
class DaysOffRange:
    start_date: date
    end_date: date
    reason: str = ""

    def __post_init__(self):
        start = (self.start_date if isinstance(self.start_date, date)
                 else date.fromisoformat(str(self.start_date)))
        end = (self.end_date if isinstance(self.end_date, date)
               else date.fromisoformat(str(self.end_date)))
        if end < start:
            raise ValueError("Days off end date cannot be before its start date")
        object.__setattr__(self, "start_date", start)
        object.__setattr__(self, "end_date", end)
        object.__setattr__(self, "reason", self.reason.strip())

    def to_dict(self):
        return {
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(**data)


@dataclass
class Resource:
    id: str
    name: str
    resource_type: ResourceType
    role_type: str
    weekly_capacity_hours: float = 40.0
    cost_per_hour: float = 0.0
    team_memberships: Dict[str, float] = field(default_factory=dict)
    assigned_project_ids: List[str] = field(default_factory=list)
    schedule_pattern: SchedulePattern = SchedulePattern.STANDARD
    daily_capacity_hours: Dict[str, float] = field(default_factory=dict)
    days_off: List[DaysOffRange] = field(default_factory=list)

    def __post_init__(self):
        if not isinstance(self.resource_type, ResourceType):
            self.resource_type = ResourceType(self.resource_type)
        self.schedule_pattern = SchedulePattern.read(self.schedule_pattern)
        if self.resource_type == ResourceType.TEAM:
            raise ValueError("Team resources must be represented by TeamPool")
        if not self.id.strip() or not self.name.strip():
            raise ValueError("Resource ID and name are required")
        if self.weekly_capacity_hours < 0 or self.cost_per_hour < 0:
            raise ValueError("Capacity and cost cannot be negative")
        if any(ratio < 0 or ratio > 1 for ratio in self.team_memberships.values()):
            raise ValueError("Team allocation ratios must be between 0 and 1")
        daily = (self.daily_capacity_hours or
                 distribute_weekly_capacity(self.schedule_pattern,
                                            self.weekly_capacity_hours))
        self.set_daily_capacity(daily, preserve_pattern=True)
        self.days_off = [item if isinstance(item, DaysOffRange)
                         else DaysOffRange.from_dict(item)
                         for item in self.days_off]

    @property
    def fte(self) -> float:
        return self.weekly_capacity_hours / FTE_WEEKLY_HOURS

    @property
    def average_active_day_hours(self) -> float:
        active = [hours for hours in self.daily_capacity_hours.values() if hours]
        return self.weekly_capacity_hours / len(active) if active else 0.0

    def set_daily_capacity(self, values: Dict[str, float],
                           preserve_pattern: bool = False):
        self.daily_capacity_hours = _validated_daily(values)
        self.weekly_capacity_hours = sum(self.daily_capacity_hours.values())
        if not preserve_pattern:
            self.schedule_pattern = SchedulePattern.CUSTOM

    def apply_capacity(self, pattern: SchedulePattern, value: float, unit: str):
        self.schedule_pattern = SchedulePattern.read(pattern)
        self.set_daily_capacity(capacity_from_entry(self.schedule_pattern,
                                                    value, unit),
                                preserve_pattern=True)

    def workload_status(self, workload_by_day: Dict[str, float]) -> Dict[str, dict]:
        status = {}
        for day in DAYS:
            capacity = self.daily_capacity_hours[day]
            workload = float(workload_by_day.get(day, 0.0))
            percentage = workload / capacity * 100 if capacity else (
                0.0 if workload == 0 else float("inf"))
            status[day] = {
                "capacity": capacity,
                "workload": workload,
                "percentage": percentage,
                "overallocated": workload > capacity,
            }
        return status

    def workload_status_for_dates(self, workload_by_date: Dict[object, float]) -> Dict[str, dict]:
        status = {}
        for value, workload in workload_by_date.items():
            day = value.date() if isinstance(value, datetime) else value
            if not isinstance(day, date):
                day = date.fromisoformat(str(day))
            key = day.isoformat()
            capacity = self.daily_capacity_hours[DAYS[day.weekday()]]
            hours = float(workload)
            percentage = hours / capacity * 100 if capacity else (
                0.0 if hours == 0 else float("inf"))
            status[key] = {
                "capacity": capacity,
                "workload": hours,
                "percentage": percentage,
                "overallocated": hours > capacity,
            }
        return status

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "resource_type": self.resource_type.value,
            "role_type": self.role_type,
            "weekly_capacity_hours": self.weekly_capacity_hours,
            "cost_per_hour": self.cost_per_hour,
            "team_memberships": self.team_memberships,
            "assigned_project_ids": self.assigned_project_ids,
            "schedule_pattern": self.schedule_pattern.value,
            "daily_capacity_hours": self.daily_capacity_hours,
            "days_off": [item.to_dict() for item in self.days_off],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Resource":
        values = data.copy()
        values["resource_type"] = ResourceType(values["resource_type"])
        values["schedule_pattern"] = SchedulePattern.read(
            values.get("schedule_pattern", SchedulePattern.STANDARD.value))
        return cls(**values)


@dataclass
class TeamPool:
    id: str
    name: str
    is_fixed_capacity: bool = False
    fixed_hours: float = 0.0
    schedule_pattern: SchedulePattern = SchedulePattern.STANDARD
    fixed_daily_hours: Dict[str, float] = field(default_factory=dict)

    def __post_init__(self):
        self.schedule_pattern = SchedulePattern.read(self.schedule_pattern)
        if not self.id.strip() or not self.name.strip():
            raise ValueError("Team ID and name are required")
        if self.fixed_hours < 0:
            raise ValueError("Fixed capacity cannot be negative")
        daily = self.fixed_daily_hours
        if not daily and self.fixed_hours:
            daily = distribute_weekly_capacity(self.schedule_pattern,
                                               self.fixed_hours)
        self.fixed_daily_hours = _validated_daily(
            daily or dict.fromkeys(DAYS, 0), maximum=None)
        if self.is_fixed_capacity:
            self.fixed_hours = sum(self.fixed_daily_hours.values())

    @property
    def fixed_fte(self) -> float:
        return self.fixed_hours / FTE_WEEKLY_HOURS

    def calculate_daily_capacity(self, all_resources: List[Resource]) -> Dict[str, float]:
        if self.is_fixed_capacity:
            return dict(self.fixed_daily_hours)
        return {
            day: sum(resource.daily_capacity_hours[day]
                     * resource.team_memberships.get(self.id, 0.0)
                     for resource in all_resources)
            for day in DAYS
        }

    def calculate_effective_capacity(self, all_resources: List[Resource]) -> float:
        return sum(self.calculate_daily_capacity(all_resources).values())

    def member_contribution(self, resource: Resource) -> Dict[str, float]:
        ratio = resource.team_memberships.get(self.id, 0.0)
        return {day: hours * ratio
                for day, hours in resource.daily_capacity_hours.items()}

    def workload_status(self, all_resources: List[Resource],
                        workload_by_day: Dict[str, float]) -> Dict[str, dict]:
        capacities = self.calculate_daily_capacity(all_resources)
        status = {}
        for day, capacity in capacities.items():
            workload = float(workload_by_day.get(day, 0.0))
            percentage = workload / capacity * 100 if capacity else (
                0.0 if workload == 0 else float("inf"))
            status[day] = {
                "capacity": capacity,
                "workload": workload,
                "percentage": percentage,
                "overallocated": workload > capacity,
            }
        return status

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "is_fixed_capacity": self.is_fixed_capacity,
            "fixed_hours": self.fixed_hours,
            "schedule_pattern": self.schedule_pattern.value,
            "fixed_daily_hours": self.fixed_daily_hours,
        }


class ResourceRepository:
    def __init__(self, filepath: str = "resources.json"):
        self.filepath = Path(filepath)
        self.resources: Dict[str, Resource] = {}
        self.teams: Dict[str, TeamPool] = {}

    @staticmethod
    def new_id(prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex}"

    def next_placeholder_name(self, role: str) -> str:
        role = role.strip() or "General"
        prefix = f"{role} Placeholder #"
        numbers = []
        for resource in self.resources.values():
            if resource.name.startswith(prefix):
                try:
                    numbers.append(int(resource.name[len(prefix):]))
                except ValueError:
                    pass
        return f"{prefix}{max(numbers, default=0) + 1}"

    def add_resource(self, resource: Resource):
        self.resources[resource.id] = resource
        logger.info("Added %s resource %r (%s)", resource.resource_type.value,
                    resource.name, resource.id)

    def remove_resource(self, resource_id: str):
        resource = self.resources.pop(resource_id, None)
        if resource:
            logger.info("Removed resource %r (%s)", resource.name, resource_id)

    def add_team(self, team: TeamPool):
        self.teams[team.id] = team
        logger.info("Added resource team %r (%s)", team.name, team.id)

    def remove_team(self, team_id: str):
        team = self.teams.pop(team_id, None)
        for resource in self.resources.values():
            resource.team_memberships.pop(team_id, None)
        if team:
            logger.info("Removed resource team %r (%s)", team.name, team_id)

    def set_team_allocation(self, resource_id: str, team_id: str,
                            percentage: float):
        if resource_id not in self.resources:
            raise KeyError(resource_id)
        if team_id not in self.teams:
            raise KeyError(team_id)
        if percentage < 0 or percentage > 100:
            raise ValueError("Team allocation must be between 0 and 100 percent")
        memberships = self.resources[resource_id].team_memberships
        if percentage == 0:
            memberships.pop(team_id, None)
        else:
            memberships[team_id] = percentage / 100.0
        logger.info("Set resource %s allocation to team %s to %.1f%%",
                    resource_id, team_id, percentage)

    def swap_generic(self, generic_id: str, named_id: str) -> Resource:
        generic = self.resources[generic_id]
        named = self.resources[named_id]
        if generic.resource_type != ResourceType.GENERIC:
            raise ValueError("Only a generic resource can be swapped")
        if named.resource_type != ResourceType.NAMED:
            raise ValueError("The replacement must be a named resource")
        old_name = generic.name
        generic.name = named.name
        generic.resource_type = ResourceType.NAMED
        generic.role_type = named.role_type
        generic.schedule_pattern = named.schedule_pattern
        generic.set_daily_capacity(named.daily_capacity_hours,
                                   preserve_pattern=True)
        generic.cost_per_hour = named.cost_per_hour
        generic.assigned_project_ids = list(dict.fromkeys(
            generic.assigned_project_ids + named.assigned_project_ids))
        logger.info("Swapped generic resource %r (%s) for named resource %r",
                    old_name, generic_id, named.name)
        return generic

    def to_dict(self) -> dict:
        return {
            "resources": [resource.to_dict()
                          for resource in self.resources.values()],
            "teams": [team.to_dict() for team in self.teams.values()],
        }

    @classmethod
    def from_dict(cls, data) -> "ResourceRepository":
        repository = cls()
        repository._load_dict(data)
        return repository

    def save_to_file(self):
        data = self.to_dict()
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.filepath.with_suffix(self.filepath.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=4, ensure_ascii=False)
        temporary.replace(self.filepath)
        logger.info("Saved %d resources and %d teams to %s",
                    len(self.resources), len(self.teams), self.filepath)

    def load_from_file(self):
        try:
            with self.filepath.open("r", encoding="utf-8") as stream:
                data = json.load(stream)
        except FileNotFoundError:
            self.resources = {}
            self.teams = {}
            logger.info("No resource file at %s; using an empty pool", self.filepath)
            return
        self._load_dict(data)
        logger.info("Loaded %d resources and %d teams from %s",
                    len(self.resources), len(self.teams), self.filepath)

    def _load_dict(self, data):
        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise ValueError("Resource settings must contain a JSON object")
        resource_data = data.get("resources", [])
        team_data = data.get("teams", [])
        if not isinstance(resource_data, list) or not isinstance(team_data, list):
            raise ValueError("Resources and teams must be JSON arrays")
        try:
            resources = {
                item["id"]: Resource.from_dict(item)
                for item in resource_data
            }
            teams = {
                item["id"]: TeamPool(**item)
                for item in team_data
            }
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("Resource settings have an invalid structure") from error
        self.resources = resources
        self.teams = teams

    def named_resources(self, excluding: Optional[str] = None) -> List[Resource]:
        return [
            resource for resource in self.resources.values()
            if resource.resource_type == ResourceType.NAMED
            and resource.id != excluding
        ]
