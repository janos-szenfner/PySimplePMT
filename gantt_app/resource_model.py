from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path
from typing import Dict, List, Optional
import uuid


class ResourceType(Enum):
    NAMED = "named"
    GENERIC = "generic"
    TEAM = "team"


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

    def __post_init__(self):
        if self.resource_type == ResourceType.TEAM:
            raise ValueError("Team resources must be represented by TeamPool")
        if not self.id.strip() or not self.name.strip():
            raise ValueError("Resource ID and name are required")
        if self.weekly_capacity_hours < 0 or self.cost_per_hour < 0:
            raise ValueError("Capacity and cost cannot be negative")
        if any(ratio < 0 or ratio > 1 for ratio in self.team_memberships.values()):
            raise ValueError("Team allocation ratios must be between 0 and 1")

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
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Resource":
        values = data.copy()
        values["resource_type"] = ResourceType(values["resource_type"])
        return cls(**values)


@dataclass
class TeamPool:
    id: str
    name: str
    is_fixed_capacity: bool = False
    fixed_hours: float = 0.0

    def __post_init__(self):
        if not self.id.strip() or not self.name.strip():
            raise ValueError("Team ID and name are required")
        if self.fixed_hours < 0:
            raise ValueError("Fixed capacity cannot be negative")

    def calculate_effective_capacity(self, all_resources: List[Resource]) -> float:
        if self.is_fixed_capacity:
            return self.fixed_hours
        return sum(
            resource.weekly_capacity_hours
            * resource.team_memberships.get(self.id, 0.0)
            for resource in all_resources
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "is_fixed_capacity": self.is_fixed_capacity,
            "fixed_hours": self.fixed_hours,
        }


class ResourceRepository:
    def __init__(self, filepath: str = "resources.json"):
        self.filepath = Path(filepath)
        self.resources: Dict[str, Resource] = {}
        self.teams: Dict[str, TeamPool] = {}

    @staticmethod
    def new_id(prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex}"

    def add_resource(self, resource: Resource):
        self.resources[resource.id] = resource

    def remove_resource(self, resource_id: str):
        self.resources.pop(resource_id, None)

    def add_team(self, team: TeamPool):
        self.teams[team.id] = team

    def remove_team(self, team_id: str):
        self.teams.pop(team_id, None)
        for resource in self.resources.values():
            resource.team_memberships.pop(team_id, None)

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

    def swap_generic(self, generic_id: str, named_id: str) -> Resource:
        generic = self.resources[generic_id]
        named = self.resources[named_id]
        if generic.resource_type != ResourceType.GENERIC:
            raise ValueError("Only a generic resource can be swapped")
        if named.resource_type != ResourceType.NAMED:
            raise ValueError("The replacement must be a named resource")
        generic.name = named.name
        generic.resource_type = ResourceType.NAMED
        generic.role_type = named.role_type
        generic.weekly_capacity_hours = named.weekly_capacity_hours
        generic.cost_per_hour = named.cost_per_hour
        generic.assigned_project_ids = list(dict.fromkeys(
            generic.assigned_project_ids + named.assigned_project_ids))
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

    def load_from_file(self):
        try:
            with self.filepath.open("r", encoding="utf-8") as stream:
                data = json.load(stream)
        except FileNotFoundError:
            self.resources = {}
            self.teams = {}
            return
        self._load_dict(data)

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
        except (KeyError, TypeError) as error:
            raise ValueError("Resource settings have an invalid structure") from error
        self.resources = resources
        self.teams = teams

    def named_resources(self, excluding: Optional[str] = None) -> List[Resource]:
        return [
            resource for resource in self.resources.values()
            if resource.resource_type == ResourceType.NAMED
            and resource.id != excluding
        ]
