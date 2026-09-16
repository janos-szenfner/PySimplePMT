"""
The one-line description a selection writes to the footer status bar.

The bar under the content cell answers "what is selected" for whichever
view is on top - the paned task view, the resource board in either of its
faces, or the deliverables board. Every view renders its rows through
these helpers so a task reads the same whether it was clicked in the
task list, under a resource in the usage grid or under a deliverable.
"""

from typing import Optional

from gantt_app.core.resource_model import (
    CostResource,
    MaterialResource,
    ResourceType,
    TeamPool,
)


def task_status_line(task) -> str:
    """The status line a task, subtask or milestone selects to."""
    if task.is_milestone:
        start = (task.start_date.strftime('%Y-%m-%d')
                 if task.start_date else 'N/A')
        return (f"Milestone: {task.name} ({start}) | "
                f"Dependencies: {len(task.dependencies)}")
    duration = task.duration_days or 0
    start = task.start_date.strftime('%Y-%m-%d') if task.start_date else 'N/A'
    end = task.end_date.strftime('%Y-%m-%d') if task.end_date else 'N/A'
    return (f"Task: {task.name} | {start} - {end} ({duration} days) | "
            f"Progress: {task.progress}% | "
            f"Dependencies: {len(task.dependencies)}")


def _assigned_task_count(entity_id: str, project) -> int:
    """How many tasks carry an assignment for the pool entity."""
    return sum(
        1 for task in project.tasks
        if any(a.get('resource_id') == entity_id
               for a in task.resource_assignments))


def entity_status_line(entity, project,
                       via_team: Optional[str] = None) -> str:
    """
    The status line a pool entity selects to.

    ``via_team`` names the team an alias row is a lens on, so the same
    member selected under its team reads as itself, in context.
    """
    suffix = f" | in team {via_team}" if via_team else ""
    tasks = _assigned_task_count(entity.id, project)
    if isinstance(entity, TeamPool):
        repo = project.resource_repository
        members = sum(
            1 for r in repo.resources.values()
            if r.team_memberships.get(entity.id, 0.0) > 0)
        capacity = entity.calculate_effective_capacity(
            list(repo.resources.values()))
        return (f"Team: {entity.name} | Members: {members} | "
                f"Capacity: {capacity:g}h/week | Tasks: {tasks}{suffix}")
    if isinstance(entity, MaterialResource):
        label = entity.material_label or 'units'
        return (f"Material: {entity.name} | Unit: {label} | "
                f"Rate: ${entity.cost_per_unit:g} | Tasks: {tasks}{suffix}")
    if isinstance(entity, CostResource):
        return (f"Cost: {entity.name} | "
                f"Accrues: {entity.accrue_at.value.lower()} | "
                f"Tasks: {tasks}{suffix}")
    kind = ('Named' if entity.resource_type == ResourceType.NAMED
            else 'Generic')
    role = f" | {entity.role_type}" if entity.role_type else ""
    return (f"Resource: {entity.name} | {kind}{role} | "
            f"Capacity: {entity.weekly_capacity_hours:g}h/week | "
            f"Tasks: {tasks}{suffix}")


def deliverable_status_line(deliverable) -> str:
    """The status line a deliverable or sub-deliverable selects to."""
    due = (deliverable.due_date.strftime('%Y-%m-%d')
           if deliverable.due_date else 'no due date')
    return (f"Deliverable: {deliverable.name} | {deliverable.status} | "
            f"Progress: {deliverable.progress}% | Due: {due} | "
            f"Tasks: {len(deliverable.task_ids)}")
