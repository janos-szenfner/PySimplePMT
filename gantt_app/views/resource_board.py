"""
4-Panel Resource Planning Matrix.

A single-screen resource view that sits beside the standard WBS / Gantt
viewport and is toggled from the bottom status bar.  It shows the unassigned
backlog, a task inspector, the resource pool with capacity indicators, and a
weekly stacking heatmap.

This first version uses selection + buttons for assignment and a Tk canvas
for the heatmap.  Full drag-and-drop and a plotly renderer can be layered on
later without changing the public shape of the class.
"""

import tkinter as tk
from datetime import date, timedelta
from typing import Callable, Dict, List, Optional

import customtkinter as ctk

from gantt_app import theme
from gantt_app.models import Project, Task
from gantt_app.resource_model import (
    FTE_WEEKLY_HOURS, Resource, ResourceRepository, ResourceType, TeamPool,
)
from gantt_app.utils.log import get_logger
from gantt_app.views.assigntask import _projected_workload_text, _status_badge
from gantt_app.views.scrollframe import ScrollFrame

logger = get_logger(__name__)

DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
DAY_LABELS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _entity_by_id(repo: ResourceRepository, entity_id: str):
    return repo.resources.get(entity_id) or repo.teams.get(entity_id)


def _working_days_between(start: date, end: date) -> int:
    if not start or not end or end < start:
        return 0
    days = 0
    current = start
    while current <= end:
        days += 1
        current += timedelta(days=1)
    return days


def _daily_load_for_resource(
    resource: Resource,
    project: Project,
) -> Dict[date, float]:
    """Spread each assignment's effort evenly over the task's working days."""
    load: Dict[date, float] = {}
    repo = project.resource_repository
    for task in project.tasks:
        if not task.is_leaf or task.is_milestone:
            continue
        for assignment in task.resource_assignments:
            entity_id = assignment.get("resource_id")
            if entity_id != resource.id:
                continue
            estimated = float(assignment.get("estimated_hours", 0.0))
            split = float(assignment.get("resource_split", 100.0)) / 100.0
            effort = estimated * split
            if effort <= 0:
                continue
            start = task.start_date
            end = task.end_date or start
            if not start or not end:
                continue
            calendar = project.calendar_for(task)
            workdays = [
                start + timedelta(days=i)
                for i in range((end - start).days + 1)
                if calendar.is_working_day(start + timedelta(days=i))
            ]
            if not workdays:
                continue
            per_day = effort / len(workdays)
            for day in workdays:
                load[day] = load.get(day, 0.0) + per_day
    return load


def _team_load_for_date(
    team: TeamPool,
    resources: List[Resource],
    project: Project,
) -> Dict[date, float]:
    """Aggregate load for all members of a team on each date."""
    load: Dict[date, float] = {}
    for resource in resources:
        if team.id not in resource.team_memberships:
            continue
        ratio = resource.team_memberships[team.id]
        for day, hours in _daily_load_for_resource(resource, project).items():
            if ratio > 0 and hours > 0:
                load[day] = load.get(day, 0.0) + hours * ratio
    return load


class ResourceBoard(ctk.CTkFrame):
    """
    The 4-panel resource planning view.

    PARAMETERS:
    -----------
    parent : ctk.CTkFrame
        The viewport frame that will hold this view.
    project : Project
        The active project.
    on_status : Callable[[str], None]
        Optional callback to mirror status messages to the footer.
    """

    def __init__(
        self,
        parent,
        project: Project,
        on_status: Optional[Callable[[str], None]] = None,
    ) -> None:
        super().__init__(parent, fg_color="transparent")
        self.project = project
        self.on_status = on_status

        self._selected_task_id: Optional[str] = None
        self._selected_resource_id: Optional[str] = None

        self.grid_columnconfigure((0, 1, 2), weight=2)
        self.grid_columnconfigure(3, weight=5)
        self.grid_rowconfigure(0, weight=1)

        self._build_backlog_panel()
        self._build_inspector_panel()
        self._build_pool_panel()
        self._build_heatmap_panel()

        self.refresh()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build_backlog_panel(self) -> None:
        p1 = ctk.CTkFrame(self, corner_radius=6)
        p1.grid(row=0, column=0, padx=2, pady=2, sticky="nsew")
        p1.grid_rowconfigure(2, weight=1)
        p1.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            p1, text="1. UNASSIGNED BACKLOG",
            font=ctk.CTkFont(weight="bold"),
        ).grid(row=0, column=0, pady=(8, 4), padx=8, sticky="w")

        self.backlog_search = ctk.CTkEntry(p1, placeholder_text="Search...")
        self.backlog_search.grid(
            row=1, column=0, padx=8, pady=(0, 4), sticky="ew")
        self.backlog_search.bind(
            "<KeyRelease>", lambda _e: self._filter_backlog())

        self.backlog_frame = ScrollFrame(p1)
        self.backlog_frame.grid(row=2, column=0, padx=8, pady=(0, 8),
                                sticky="nsew")
        self.backlog_frame.content.grid_columnconfigure(0, weight=1)

    def _build_inspector_panel(self) -> None:
        p2 = ctk.CTkFrame(self, corner_radius=6)
        p2.grid(row=0, column=1, padx=2, pady=2, sticky="nsew")
        p2.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            p2, text="2. TASK INSPECTOR",
            font=ctk.CTkFont(weight="bold"),
        ).pack(pady=(8, 4))

        self.inspector_text = ctk.CTkTextbox(
            p2, wrap="word", height=160, state="disabled")
        self.inspector_text.pack(padx=10, pady=4, fill="x")

        self.preview_label = ctk.CTkLabel(p2, text="Assignee preview:",
                                          anchor="w")
        self.preview_label.pack(padx=10, pady=(8, 2), fill="x")

        ctk.CTkButton(
            p2, text="Assign Task",
            fg_color="#1f6aa5", hover_color="#144870",
            command=self._assign_selected,
        ).pack(padx=10, pady=5, fill="x")

        ctk.CTkButton(
            p2, text="De-assign / Move to Backlog",
            fg_color="#c0392b", hover_color="#962d22",
            command=self._deassign_selected,
        ).pack(padx=10, pady=5, fill="x")

    def _build_pool_panel(self) -> None:
        p3 = ctk.CTkFrame(self, corner_radius=6)
        p3.grid(row=0, column=2, padx=2, pady=2, sticky="nsew")
        p3.grid_rowconfigure(2, weight=1)
        p3.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            p3, text="3. RESOURCE POOL",
            font=ctk.CTkFont(weight="bold"),
        ).grid(row=0, column=0, pady=(8, 4), padx=8, sticky="w")

        self.pool_filter = ctk.CTkOptionMenu(
            p3, values=["All Types", "Named", "Generic", "Team"])
        self.pool_filter.grid(row=1, column=0, padx=8, pady=(0, 4),
                              sticky="ew")
        self.pool_filter.set("All Types")
        self.pool_filter.configure(command=lambda _v: self._filter_pool())

        self.pool_frame = ScrollFrame(p3)
        self.pool_frame.grid(row=2, column=0, padx=8, pady=(0, 8),
                             sticky="nsew")
        self.pool_frame.content.grid_columnconfigure(0, weight=1)

    def _build_heatmap_panel(self) -> None:
        p4 = ctk.CTkFrame(self, corner_radius=6)
        p4.grid(row=0, column=3, padx=2, pady=2, sticky="nsew")
        p4.grid_rowconfigure(1, weight=1)
        p4.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            p4, text="4. LIVE STACKING & HEATMAP",
            font=ctk.CTkFont(weight="bold"),
        ).grid(row=0, column=0, pady=(8, 4), padx=8, sticky="w")

        self.heatmap_canvas = tk.Canvas(
            p4, bg=theme.now(theme.GRID_ROW_BG), highlightthickness=0)
        self.heatmap_canvas.grid(row=1, column=0, padx=8, pady=(0, 8),
                                 sticky="nsew")

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        """Reload every panel from the current project state."""
        if not self.project:
            return
        try:
            self._filter_backlog()
            self._filter_pool()
            self._draw_heatmap()
            if self._selected_task_id:
                self._show_task(self._selected_task_id)
        except Exception:
            logger.exception("Could not refresh the resource board")

    # ------------------------------------------------------------------
    # Backlog
    # ------------------------------------------------------------------
    def _filter_backlog(self) -> None:
        search = (self.backlog_search.get() or "").lower()
        for child in list(self.backlog_frame.content.winfo_children()):
            child.destroy()

        row = 0
        for task in self.project.tasks:
            if not self._is_unassigned(task):
                continue
            label = f"{task.name or task.id}  (#{task.id})"
            if search and search not in label.lower():
                continue

            card = ctk.CTkButton(
                self.backlog_frame.content,
                text=f"#{task.id}\n{task.name or '(unnamed)'}\n"
                     f"Effort: {self._task_effort(task)}h | "
                     f"Duration: {self._task_duration(task)}d",
                anchor="w", justify="left",
                command=lambda t=task.id: self._select_task(t),
            )
            card.grid(row=row, column=0, pady=3, padx=2, sticky="ew")
            if task.id == self._selected_task_id:
                card.configure(fg_color="#1f6aa5")
            row += 1

    def _is_unassigned(self, task: Task) -> bool:
        return bool(task.is_leaf and not task.is_milestone and
                    not task.resource_assignments)

    def _task_effort(self, task: Task) -> float:
        return sum(float(a.get("estimated_hours", 0.0))
                   for a in task.resource_assignments) or 0.0

    def _task_duration(self, task: Task) -> int:
        if task.start_date and task.end_date:
            return _working_days_between(task.start_date, task.end_date)
        return 0

    # ------------------------------------------------------------------
    # Inspector
    # ------------------------------------------------------------------
    def _select_task(self, task_id: str) -> None:
        self._selected_task_id = task_id
        self._filter_backlog()
        self._show_task(task_id)
        logger.debug("Resource board selected task %s", task_id)

    def _show_task(self, task_id: str) -> None:
        task = self.project.get_task_by_id(task_id)
        if task is None:
            return

        self.inspector_text.configure(state="normal")
        self.inspector_text.delete("0.0", "end")
        info = (
            f"TASK: #{task.id} {task.name}\n"
            f"Effort: {self._task_effort(task)}h\n"
            f"Duration: {self._task_duration(task)}d\n"
            f"Priority: {task.priority}\n"
            f"Calendar: {task.calendar_id or 'project'}\n"
        )
        self.inspector_text.insert("0.0", info)
        self.inspector_text.configure(state="disabled")

        self._update_preview()

    def _update_preview(self) -> None:
        task = self.project.get_task_by_id(self._selected_task_id or "")
        resource = _entity_by_id(self.project.resource_repository,
                                 self._selected_resource_id or "")
        if task and resource:
            effort = self._task_effort(task) or 8.0
            resources = list(self.project.resource_repository.resources.values())
            text, colour, _ = _projected_workload_text(
                resource, resources, effort)
            self.preview_label.configure(text=f"Assignee preview: {text}",
                                         text_color=colour)
        else:
            self.preview_label.configure(
                text="Assignee preview: select a resource",
                text_color=theme.now(theme.GRID_TEXT))

    # ------------------------------------------------------------------
    # Resource pool
    # ------------------------------------------------------------------
    def _filter_pool(self) -> None:
        selected_filter = self.pool_filter.get()
        repo = self.project.resource_repository
        resources = list(repo.resources.values())

        for child in list(self.pool_frame.content.winfo_children()):
            child.destroy()

        row = 0
        for entity in list(repo.resources.values()) + list(repo.teams.values()):
            is_team = isinstance(entity, TeamPool)
            if selected_filter == "Named" and entity.resource_type != ResourceType.NAMED:
                continue
            if selected_filter == "Generic" and entity.resource_type != ResourceType.GENERIC:
                continue
            if selected_filter == "Team" and not is_team:
                continue

            if is_team:
                capacity = entity.calculate_effective_capacity(resources)
                used = sum(_team_load_for_date(
                    entity, resources, self.project).values())
            else:
                used, capacity = self._resource_used(entity)

            badge, colour, pct = _status_badge(used, capacity)
            load_text = (f"{used:g} / {capacity:g} hrs "
                         f"({pct:.0f}%)")
            kind = "TEAM" if is_team else entity.resource_type.value.upper()
            text = f"{badge} {entity.name} ({kind})\n{load_text}"

            card = ctk.CTkButton(
                self.pool_frame.content,
                text=text,
                anchor="w", justify="left",
                command=lambda e=entity.id: self._select_resource(e),
            )
            card.grid(row=row, column=0, pady=3, padx=2, sticky="ew")
            if entity.id == self._selected_resource_id:
                card.configure(fg_color="#1f6aa5")
            row += 1

    def _resource_used(self, resource: Resource) -> tuple:
        total = sum(_daily_load_for_resource(resource, self.project).values())
        return total, resource.weekly_capacity_hours

    def _select_resource(self, entity_id: str) -> None:
        self._selected_resource_id = entity_id
        self._filter_pool()
        self._update_preview()
        logger.debug("Resource board selected resource %s", entity_id)

    # ------------------------------------------------------------------
    # Heatmap
    # ------------------------------------------------------------------
    def _draw_heatmap(self) -> None:
        canvas = self.heatmap_canvas
        canvas.delete("all")

        repo = self.project.resource_repository
        entities = list(repo.resources.values()) + list(repo.teams.values())
        if not entities:
            canvas.create_text(
                80, 30, text="No resources loaded",
                fill=theme.now(theme.GRID_TEXT), anchor="w")
            return

        today = date.today()
        days = [today + timedelta(days=i) for i in range(5)]
        day_width = 120
        row_height = 50
        left = 160

        for col, day in enumerate(days):
            x = left + col * day_width
            canvas.create_text(
                x + day_width // 2, 15,
                text=day.strftime("%a %d"),
                fill=theme.now(theme.GRID_TEXT), font=("Arial", 10, "bold"))

        resources = list(repo.resources.values())
        for row, entity in enumerate(entities):
            is_team = isinstance(entity, TeamPool)
            y = 40 + row * row_height
            canvas.create_text(
                10, y + row_height // 2,
                text=entity.name,
                fill=theme.now(theme.GRID_TEXT), anchor="w", width=150)

            if is_team:
                capacity_per_day = entity.calculate_daily_capacity(resources)
                loads = _team_load_for_date(entity, resources, self.project)
            else:
                capacity_per_day = entity.daily_capacity_hours
                loads = _daily_load_for_resource(entity, self.project)

            for col, day in enumerate(days):
                x = left + col * day_width
                weekday = DAYS[day.weekday()]
                cap = float(capacity_per_day.get(weekday, 0.0))
                used = float(loads.get(day, 0.0))

                if used > cap:
                    colour = "#e74c3c"
                elif used >= cap * 0.85:
                    colour = "#f1c40f"
                else:
                    colour = "#2ecc71" if used > 0 else "#d5dbdb"

                canvas.create_rectangle(
                    x + 2, y + 2, x + day_width - 2, y + row_height - 2,
                    fill=colour, outline=theme.now(theme.GRID_TEXT))

                label = f"{used:.1f}h"
                if cap > 0:
                    label += f" / {cap:.0f}h"
                canvas.create_text(
                    x + day_width // 2, y + row_height // 2,
                    text=label,
                    fill="#ffffff" if colour != "#d5dbdb" else "#2c3e50",
                    font=("Arial", 9))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _assign_selected(self) -> None:
        task = self.project.get_task_by_id(self._selected_task_id or "")
        resource = _entity_by_id(self.project.resource_repository,
                                 self._selected_resource_id or "")
        if not task or not resource:
            self._say("Select both a backlog task and a resource first.")
            return

        repo = self.project.resource_repository
        if isinstance(resource, TeamPool):
            self._say("Team assignment is not yet supported here.")
            return

        if any(a.get("resource_id") == resource.id
               for a in task.resource_assignments):
            self._say(f"{resource.name} is already assigned to this task.")
            return

        effort = self._task_effort(task) or 8.0
        task.resource_assignments.append({
            "resource_id": resource.id,
            "estimated_hours": effort,
            "resource_split": 100.0,
        })

        logger.info("Assigned %r to task %s (%s)",
                    resource.name, task.id, task.name)
        self._say(f"Assigned {resource.name} to {task.name}.")
        self.refresh()

    def _deassign_selected(self) -> None:
        task = self.project.get_task_by_id(self._selected_task_id or "")
        if not task:
            self._say("Select an assigned task first.")
            return

        if not task.resource_assignments:
            self._say("The selected task has no assignments.")
            return

        count = len(task.resource_assignments)
        task.resource_assignments.clear()
        logger.info("Cleared %d assignment(s) from task %s (%s)",
                    count, task.id, task.name)
        self._say(f"De-assigned {count} resource(s) from {task.name}.")
        self._selected_resource_id = None
        self.refresh()

    def _say(self, message: str) -> None:
        logger.info(message)
        if self.on_status:
            self.on_status(message)
