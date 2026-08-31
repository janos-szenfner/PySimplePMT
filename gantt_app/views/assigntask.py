"""
Resource assignment tab for the task create/edit dialog.

The tab lives in its own module because the widgetry and the workload
arithmetic for a task-to-resource assignment are sizeable enough to pull
out of the already-long task form.
"""
import tkinter as tk
from typing import Dict, List, Optional, Tuple

import customtkinter as ctk

from gantt_app.resource_model import (
    FTE_WEEKLY_HOURS, Resource, ResourceRepository, ResourceType, TeamPool,
)
from gantt_app.utils.log import get_logger
from gantt_app.views.resourcesettings import _schedule_short

logger = get_logger(__name__)


def _resource_load(resource: Resource) -> Tuple[float, float]:
    """Current allocation for a resource: (used hours, capacity hours)."""
    capacity = resource.weekly_capacity_hours
    if not capacity:
        return 0.0, 0.0
    ratio = sum(resource.team_memberships.values())
    used = ratio * capacity
    return used, capacity


def _load_status(used: float, capacity: float) -> Tuple[float, str]:
    """Return the load percentage and a status message."""
    if capacity <= 0:
        return 0.0, "N/A"
    pct = used / capacity * 100.0
    if pct > 100:
        return pct, f"{used:g} / {capacity:g} hrs ({pct:.0f}% OVERLOADED)"
    if pct >= 85:
        return pct, f"{used:g} / {capacity:g} hrs ({pct:.0f}% loaded)"
    return pct, f"{used:g} / {capacity:g} hrs ({pct:.0f}% loaded)"


def _load_badge(used: float, capacity: float) -> str:
    """A single-character traffic-light badge for the dropdown."""
    if capacity <= 0:
        return "⚪"
    pct = used / capacity * 100.0
    if pct > 100:
        return "🔴"
    if pct >= 85:
        return "🟡"
    return "🟢"


class TaskResourceTab:
    """
    The Resource tab shown in the task create/edit dialog.

    It offers a searchable dropdown of resources and teams, fields for the
    estimated effort and the daily split, and a real-time preview of the
    impact on the selected assignee's workload.
    """

    def __init__(self, parent: ctk.CTkFrame, project, task) -> None:
        self.parent = parent
        self.project = project
        self.task = task
        self.repo = getattr(project, "resource_repository", ResourceRepository())
        self._option_to_id: Dict[str, str] = {}
        self._id_to_data: Dict[str, Tuple[str, str, float, float]] = {}
        self._selected_id: Optional[str] = None
        self._build()
        self._populate_dropdown()

    # ------------------------------------------------------------------
    # Building the widgets
    # ------------------------------------------------------------------

    def _build(self) -> None:
        """Create the tab's controls."""
        pad = {"padx": 10, "pady": (8, 0)}

        ctk.CTkLabel(
            self.parent, text="ASSIGNEE", font=("Arial", 12, "bold"),
            anchor=tk.W).pack(fill=tk.X, **pad)

        ctk.CTkLabel(
            self.parent, text="Search resource or team:", anchor=tk.W
        ).pack(fill=tk.X, padx=10, pady=(4, 0))

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._on_search)
        self.search_entry = ctk.CTkEntry(
            self.parent, textvariable=self.search_var,
            placeholder_text="Type to filter...")
        self.search_entry.pack(fill=tk.X, padx=10, pady=(2, 4))

        self.assignee_menu = ctk.CTkOptionMenu(
            self.parent, values=["(no resources)"], width=300,
            command=self._on_assignee_selected)
        self.assignee_menu.pack(fill=tk.X, padx=10, pady=(0, 8))

        ctk.CTkLabel(
            self.parent, text="ASSIGNMENT PARAMETERS", font=("Arial", 12, "bold"),
            anchor=tk.W).pack(fill=tk.X, **pad)

        params = ctk.CTkFrame(self.parent, fg_color="transparent")
        params.pack(fill=tk.X, padx=10, pady=(4, 0))
        params.columnconfigure(1, weight=1)

        ctk.CTkLabel(params, text="Estimated Effort (hrs):", anchor=tk.W
                     ).grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
        self.effort_entry = ctk.CTkEntry(params, width=80)
        self.effort_entry.insert(0, "0.0")
        self.effort_entry.grid(row=0, column=1, sticky=tk.W)

        ctk.CTkLabel(params, text="Daily Split (%):", anchor=tk.W
                     ).grid(row=1, column=0, sticky=tk.W, padx=(0, 8), pady=(6, 0))
        self.split_entry = ctk.CTkEntry(params, width=80)
        self.split_entry.insert(0, "0")
        self.split_entry.grid(row=1, column=1, sticky=tk.W, pady=(6, 0))

        self.effort_entry.bind("<KeyRelease>", self._on_param_changed)
        self.split_entry.bind("<KeyRelease>", self._on_param_changed)

        ctk.CTkLabel(
            self.parent, text="IMPACT PREVIEW", font=("Arial", 12, "bold"),
            anchor=tk.W).pack(fill=tk.X, **pad)

        self.preview_label = ctk.CTkLabel(
            self.parent, text="", justify=tk.LEFT, anchor=tk.W,
            wraplength=560)
        self.preview_label.pack(fill=tk.X, padx=10, pady=(4, 8))

        self.clear_button = ctk.CTkButton(
            self.parent, text="Clear Assignment", command=self._clear_assignment)
        self.clear_button.pack(anchor=tk.W, padx=10, pady=(0, 8))

    # ------------------------------------------------------------------
    # Populating and filtering the dropdown
    # ------------------------------------------------------------------

    def _collect_options(self) -> List[Tuple[str, str, str, str, float, float]]:
        """Build the flat list of dropdown options, sorted by type."""
        options: List[Tuple[str, str, str, str, float, float]] = []

        for resource in sorted(
                self.repo.resources.values(), key=lambda r: r.name.lower()):
            used, capacity = _resource_load(resource)
            badge = _load_badge(used, capacity)
            option = (f"{badge} [NAMED] {resource.name}" if
                      resource.resource_type == ResourceType.NAMED else
                      f"{badge} [GENERIC] {resource.name}")
            schedule = _schedule_short(resource.schedule_pattern)
            options.append((
                resource.id, option, schedule, f"{used:g} / {capacity:g} hrs",
                used, capacity))

        for team in sorted(
                self.repo.teams.values(), key=lambda t: t.name.lower()):
            all_resources = list(self.repo.resources.values())
            weekly = team.calculate_effective_capacity(all_resources)
            option = f"⚪ [TEAM] {team.name}"
            schedule = _schedule_short(team.schedule_pattern)
            options.append((
                team.id, option, schedule,
                f"{weekly / FTE_WEEKLY_HOURS:.2f} FTE ({weekly:g}h/wk)",
                0.0, weekly))

        return options

    def _populate_dropdown(self) -> None:
        """Fill the dropdown and the lookup maps."""
        raw = self._collect_options()
        self._option_to_id = {row[1]: row[0] for row in raw}
        self._id_to_data = {
            row[0]: (row[1], row[2], row[3], row[4], row[5])
            for row in raw
        }
        values = [r[1] for r in raw]
        if not values:
            values = ["(no resources)"]
        self.assignee_menu.configure(values=values)
        self._on_search()

    def _on_search(self, *_) -> None:
        """Filter the dropdown options by the search field."""
        text = self.search_var.get().strip().lower()
        all_options = [r[1] for r in self._collect_options()]
        if not all_options:
            self.assignee_menu.configure(values=["(no resources)"])
            return
        if not text:
            self.assignee_menu.configure(values=all_options)
            return
        filtered = [o for o in all_options if text in o.lower()]
        if not filtered:
            filtered = ["(no match)"]
        self.assignee_menu.configure(values=filtered)

    def _on_assignee_selected(self, option: str) -> None:
        """A resource or team was picked from the menu."""
        self._selected_id = self._option_to_id.get(option)
        self._update_preview()

    def _on_param_changed(self, _event=None) -> None:
        """Effort or split changed; refresh the preview."""
        self._update_preview()

    def _clear_assignment(self) -> None:
        """Reset every assignment field."""
        self._selected_id = None
        self.search_var.set("")
        self.effort_entry.delete(0, tk.END)
        self.effort_entry.insert(0, "0.0")
        self.split_entry.delete(0, tk.END)
        self.split_entry.insert(0, "0")
        self.assignee_menu.set(self.assignee_menu._values[0] if
                               self.assignee_menu._values else "(no resources)")
        self._update_preview()

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------

    def _update_preview(self) -> None:
        """Write the impact preview from the current selection."""
        if not self._selected_id:
            self.preview_label.configure(text="No assignee selected.")
            return

        data = self._id_to_data.get(self._selected_id)
        if not data:
            self.preview_label.configure(text="Selected assignee not found.")
            return

        name, schedule, load_text, used, capacity = data
        entity = self._entity_by_id(self._selected_id)
        if entity is None:
            self.preview_label.configure(text="Selected assignee not found.")
            return

        split = self._read_split()
        effort = self._read_effort()
        duration = self.task.duration_days or 0

        lines = [f"Selected: {name}",
                 f"Schedule: {schedule}",
                 f"Current load: {load_text}"]

        if isinstance(entity, Resource):
            daily = entity.average_active_day_hours
            task_daily = daily * split / 100.0 if split >= 0 else 0.0
            total_task_hours = task_daily * duration if duration > 0 else 0.0
            new_used = used + task_daily * (entity.weekly_capacity_hours /
                                            entity.average_active_day_hours
                                            if entity.average_active_day_hours
                                            else 0.0)
            # Above is a rough weekly aggregation for the preview only.
            # The clearer number for the user is the projected total load.
            projected_pct = 0.0
            if capacity > 0:
                projected_pct = (used + task_daily * 5) / capacity * 100.0
            # using 5 working days as the weekly window for the preview

            color = "🟢"
            if projected_pct > 100:
                color = "🔴"
            elif projected_pct >= 85:
                color = "🟡"

            lines.append(
                f"This task: {effort:g} hrs, {split:g}% split, "
                f"{task_daily:g}h/day over {duration:g} working days")
            lines.append(
                f"New projected load: {used:g} + {task_daily * 5:g} = "
                f"{used + task_daily * 5:g} / {capacity:g} hrs "
                f"({projected_pct:.0f}%) {color}")

            if projected_pct > 100:
                lines.append(
                    f"⚠️ Warning: this assignment will overload {entity.name}.")
        else:
            # For a team we can only show the capacity and the task size.
            lines.append(
                f"This task: {effort:g} hrs over {duration:g} working days")
            if capacity > 0:
                pct = (effort / capacity * 100.0) if effort else 0.0
                lines.append(
                    f"As a share of the team's weekly capacity: {pct:.0f}%")

        self.preview_label.configure(text="\n".join(lines))

    def _entity_by_id(self, entity_id: str):
        """Return the Resource or TeamPool with the given id."""
        if entity_id in self.repo.resources:
            return self.repo.resources[entity_id]
        if entity_id in self.repo.teams:
            return self.repo.teams[entity_id]
        return None

    def _read_split(self) -> float:
        text = self.split_entry.get().strip().rstrip("%")
        if not text:
            return 0.0
        try:
            return float(text)
        except ValueError:
            return 0.0

    def _read_effort(self) -> float:
        text = self.effort_entry.get().strip()
        if not text:
            return 0.0
        try:
            return float(text)
        except ValueError:
            return 0.0

    # ------------------------------------------------------------------
    # Public API for the form
    # ------------------------------------------------------------------

    def get_values(self) -> Dict[str, object]:
        """Return the current assignment values."""
        return {
            "resource_id": self._selected_id,
            "estimated_hours": self._read_effort(),
            "resource_split": self._read_split(),
        }

    def set_values(self, task) -> None:
        """Seed the tab from an existing task."""
        self.effort_entry.delete(0, tk.END)
        self.effort_entry.insert(0, f"{task.estimated_hours:g}")
        self.split_entry.delete(0, tk.END)
        self.split_entry.insert(0, f"{task.resource_split:g}")

        if task.resource_id and task.resource_id in self._id_to_data:
            self._selected_id = task.resource_id
            option = self._id_to_data[task.resource_id][0]
            self.search_var.set("")
            self._on_search()
            # the filtered values should now include the option
            current = self.assignee_menu._values
            if option in current:
                self.assignee_menu.set(option)
            else:
                self.assignee_menu.configure(values=current + [option])
                self.assignee_menu.set(option)
        else:
            self._selected_id = None

        self._update_preview()
