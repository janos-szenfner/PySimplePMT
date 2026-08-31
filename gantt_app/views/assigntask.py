"""
Resource assignment tab for the task create/edit dialog.

This version uses a custom multi-column picker for resources and teams, and
shows the selected assignments in a list with per-row clear buttons.
"""
import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, List, Optional, Tuple

import customtkinter as ctk

from gantt_app.resource_model import (
    FTE_WEEKLY_HOURS, Resource, ResourceRepository, ResourceType, TeamPool,
)
from gantt_app.utils.log import get_logger
from gantt_app.views.resourcesettings import _schedule_short
from gantt_app.views.scrollframe import ScrollFrame

logger = get_logger(__name__)


def _resource_load(resource: Resource) -> Tuple[float, float]:
    """Current team-allocation load for a resource: (used, capacity)."""
    capacity = resource.weekly_capacity_hours
    if not capacity:
        return 0.0, 0.0
    used = sum(resource.team_memberships.values()) * capacity
    return used, capacity


def _team_load(team: TeamPool, resources: List[Resource]) -> Tuple[float, float]:
    """Current team capacity: (used placeholder, capacity hours)."""
    capacity = team.calculate_effective_capacity(resources)
    return 0.0, capacity


def _status_badge(used: float, capacity: float) -> Tuple[str, str, float]:
    """Return (badge, text colour, percentage) for a load."""
    if capacity <= 0:
        return "⚪", theme.now(theme.GRID_TEXT), 0.0
    pct = used / capacity * 100.0
    if pct > 100:
        return "🔴", "#ff6b6b", pct
    if pct >= 85:
        return "🟡", "#f1c40f", pct
    return "🟢", "#2ecc71", pct


def _type_badge(entity) -> str:
    if isinstance(entity, TeamPool):
        return "[TEAM]"
    if entity.resource_type == ResourceType.NAMED:
        return "[NAMED]"
    return "[GENERIC]"


def _entity_schedule(entity) -> str:
    if isinstance(entity, TeamPool):
        return _schedule_short(entity.schedule_pattern)
    return _schedule_short(entity.schedule_pattern)


def _workload_text(entity, resources: List[Resource]) -> Tuple[str, str, float]:
    """Return (display text, colour, percentage) for the weekly workload cell."""
    if isinstance(entity, TeamPool):
        capacity = entity.calculate_effective_capacity(resources)
        if capacity <= 0:
            return "0 / 0 hrs", theme.now(theme.GRID_TEXT), 0.0
        # Teams show capacity and, as a rough indicator, 0% current load
        return (f"0 / {capacity:g} hrs (0%)",
                theme.now(theme.GRID_TEXT), 0.0)
    used, capacity = _resource_load(entity)
    badge, colour, pct = _status_badge(used, capacity)
    if pct > 100:
        text = f"{used:g} / {capacity:g} hrs ({pct:.0f}% OVERLOADED)"
    else:
        text = f"{used:g} / {capacity:g} hrs ({pct:.0f}% loaded)"
    return f"{badge} {text}", colour, pct


class ResourcePicker(ctk.CTkToplevel):
    """
    A custom searchable, multi-column dropdown for choosing a resource or team.
    """

    def __init__(self, master, project, on_select: Callable[[str], None]):
        super().__init__(master)
        self.project = project
        self.on_select = on_select
        self.repo = getattr(project, "resource_repository", ResourceRepository())
        self._selected_id: Optional[str] = None
        self._all_rows: List[Tuple[str, str, str, str, str]] = []

        self.title("Select Resource or Team")
        self.geometry("700x450")
        self.transient(master)
        self.grab_set()

        ctk.CTkLabel(self, text="Search:", anchor=tk.W).pack(
            fill=tk.X, padx=10, pady=(10, 0))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._on_search)
        ctk.CTkEntry(self, textvariable=self.search_var,
                     placeholder_text="Type to filter...").pack(
            fill=tk.X, padx=10, pady=(0, 10))

        columns = ("entity", "schedule", "workload")
        self.tree = ttk.Treeview(
            self, columns=columns, show="headings", height=14,
            selectmode="browse", style="DataGrid.Treeview")
        self.tree.heading("entity", text="Entity Name & Type")
        self.tree.heading("schedule", text="Work Schedule Pattern")
        self.tree.heading("workload", text="Weekly Workload")
        self.tree.column("entity", width=240)
        self.tree.column("schedule", width=160)
        self.tree.column("workload", width=240)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", self._on_double_click)

        ctk.CTkButton(self, text="Select", command=self._confirm).pack(
            side=tk.RIGHT, padx=10, pady=(0, 10))
        ctk.CTkButton(self, text="Cancel", command=self.destroy).pack(
            side=tk.RIGHT, padx=10, pady=(0, 10))

        self._load_rows()
        self._on_search()

        # Basic row-colour tags
        self.tree.tag_configure("over", background="#ffebee",
                                foreground="#b71c1c")
        self.tree.tag_configure("near", background="#fff8e1",
                                foreground="#9c6c0a")
        self.tree.tag_configure("ok", background="#e8f5e9",
                                foreground="#1b5e20")

    def _load_rows(self) -> None:
        resources = list(self.repo.resources.values())
        for entity in sorted(resources, key=lambda r: r.name.lower()):
            badge = _type_badge(entity)
            schedule = _entity_schedule(entity)
            workload, colour, pct = _workload_text(entity, resources)
            self._all_rows.append((
                entity.id,
                f"{entity.name}  {badge}",
                schedule,
                workload,
                _row_tag(pct)))
        for entity in sorted(self.repo.teams.values(),
                             key=lambda t: t.name.lower()):
            badge = _type_badge(entity)
            schedule = _entity_schedule(entity)
            workload, colour, pct = _workload_text(entity, resources)
            self._all_rows.append((
                entity.id,
                f"{entity.name}  {badge}",
                schedule,
                workload,
                _row_tag(pct)))

    def _on_search(self, *_) -> None:
        self.tree.delete(*self.tree.get_children())
        text = self.search_var.get().strip().lower()
        for row in self._all_rows:
            if not text or text in row[1].lower() or text in row[2].lower():
                self.tree.insert("", "end", iid=row[0], values=row[1:4],
                                 tags=(row[4],))

    def _on_tree_select(self, _event=None) -> None:
        selection = self.tree.selection()
        self._selected_id = selection[0] if selection else None

    def _on_double_click(self, _event=None) -> None:
        self._confirm()

    def _confirm(self) -> None:
        if self._selected_id:
            self.on_select(self._selected_id)
        self.destroy()


def _row_tag(pct: float) -> str:
    if pct > 100:
        return "over"
    if pct >= 85:
        return "near"
    return "ok"


class TaskResourceTab(ctk.CTkFrame):
    """
    The Resource tab shown in the task create/edit dialog.
    """

    def __init__(self, parent: ctk.CTkFrame, project, task) -> None:
        self.project = project
        self.task = task
        self.repo = getattr(project, "resource_repository", ResourceRepository())
        self._assignments: List[Dict[str, object]] = []
        super().__init__(parent, fg_color="transparent")
        self._build()

    # ------------------------------------------------------------------
    # Building the widgets
    # ------------------------------------------------------------------

    def _build(self) -> None:
        ctk.CTkLabel(
            self, text="ASSIGNMENTS", font=("Arial", 12, "bold"),
            anchor=tk.W).pack(fill=tk.X, padx=10, pady=(10, 4))

        self.scroller = ScrollFrame(self)
        self.scroller.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 8))
        self._rows_frame = self.scroller.content

        ctk.CTkButton(
            self, text="+ Add Resource / Team",
            command=self._open_picker).pack(anchor=tk.W, padx=10, pady=(0, 10))

    # ------------------------------------------------------------------
    # Rows
    # ------------------------------------------------------------------

    def _refresh_rows(self) -> None:
        for child in list(self._rows_frame.winfo_children()):
            child.destroy()

        for index, assignment in enumerate(self._assignments):
            entity = self._entity_by_id(assignment.get("resource_id", ""))
            if entity is None:
                continue

            row = ctk.CTkFrame(self._rows_frame, fg_color="transparent")
            row.pack(fill=tk.X, pady=2)
            row.columnconfigure(0, weight=0)
            row.columnconfigure(1, weight=0)
            row.columnconfigure(2, weight=0)
            row.columnconfigure(3, weight=0)
            row.columnconfigure(4, weight=0)
            row.columnconfigure(5, weight=0)

            badge = _type_badge(entity)
            ctk.CTkLabel(row, text=f"{entity.name}  {badge}",
                         width=200, anchor=tk.W).grid(row=0, column=0, padx=4)

            schedule = _entity_schedule(entity)
            ctk.CTkLabel(row, text=schedule, width=160,
                         anchor=tk.W).grid(row=0, column=1, padx=4)

            resources = list(self.repo.resources.values())
            workload, colour, _ = _workload_text(entity, resources)
            ctk.CTkLabel(row, text=workload, text_color=colour,
                         width=240, anchor=tk.W).grid(row=0, column=2, padx=4)

            effort = ctk.CTkEntry(row, width=70)
            effort.insert(0, f"{float(assignment.get('estimated_hours', 0.0)):g}")
            effort.grid(row=0, column=3, padx=4)
            effort.bind("<KeyRelease>", self._make_updater(index, "estimated_hours", effort))

            split = ctk.CTkEntry(row, width=60)
            split.insert(0, f"{float(assignment.get('resource_split', 0.0)):g}")
            split.grid(row=0, column=4, padx=4)
            split.bind("<KeyRelease>", self._make_updater(index, "resource_split", split))

            ctk.CTkButton(row, text="Clear", width=70,
                          command=lambda i=index: self._remove(i)).grid(
                row=0, column=5, padx=4)

    def _make_updater(self, index: int, key: str, widget: ctk.CTkEntry):
        def _update(_event=None):
            text = widget.get().strip().rstrip("%")
            try:
                value = float(text) if text else 0.0
            except ValueError:
                value = 0.0
            self._assignments[index][key] = value
        return _update

    def _entity_by_id(self, entity_id: str):
        if entity_id in self.repo.resources:
            return self.repo.resources[entity_id]
        if entity_id in self.repo.teams:
            return self.repo.teams[entity_id]
        return None

    # ------------------------------------------------------------------
    # Add / remove
    # ------------------------------------------------------------------

    def _open_picker(self) -> None:
        ResourcePicker(self.winfo_toplevel(), self.project, self._on_picked)

    def _on_picked(self, entity_id: str) -> None:
        # Avoid duplicates for now; later we can allow split per entity.
        if any(a.get("resource_id") == entity_id for a in self._assignments):
            return
        self._assignments.append({
            "resource_id": entity_id,
            "estimated_hours": 0.0,
            "resource_split": 100.0,
        })
        self._refresh_rows()

    def _remove(self, index: int) -> None:
        del self._assignments[index]
        self._refresh_rows()

    # ------------------------------------------------------------------
    # Public API for the form
    # ------------------------------------------------------------------

    def get_assignments(self) -> List[Dict[str, object]]:
        """Return the current assignment list."""
        return list(self._assignments)

    def set_values(self, task) -> None:
        """Seed the tab from an existing task."""
        self._assignments = [
            dict(a) for a in getattr(task, "resource_assignments", [])
        ]
        self._refresh_rows()
