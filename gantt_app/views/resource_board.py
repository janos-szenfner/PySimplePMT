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
from datetime import date, datetime, timedelta
from tkinter import ttk
from typing import Callable, Dict, List, Optional, Set, Tuple

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

STATUS_UNASSIGNED = "Status: Unassigned"


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
        if task.is_milestone:
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
            raw_workdays = [
                start + timedelta(days=i)
                for i in range((end - start).days + 1)
            ]
            workdays = [
                (d.date() if isinstance(d, datetime) else d)
                for d in raw_workdays
                if calendar.is_working_day(d)
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
        super().__init__(parent)
        self.project = project
        self.on_status = on_status

        self._selected_task_id: Optional[str] = None
        self._selected_resource_id: Optional[str] = None
        self._expanded_task_ids: Set[str] = set()
        self._drag_task_id: Optional[str] = None
        self._drag_origin: Optional[Tuple[int, int]] = None
        self._drag_window: Optional[tk.Toplevel] = None

        # Give all four panels equal shares of the available width.  The
        # heatmap still needs more room than it had, and equal shares stop the
        # inspector from dominating the layout.
        self.grid_columnconfigure((0, 1, 2, 3), weight=1, minsize=180)
        self.grid_rowconfigure(0, weight=1)

        self._build_task_list_panel()
        self._build_inspector_panel()
        self._build_pool_panel()
        self._build_heatmap_panel()

        self.refresh()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build_task_list_panel(self) -> None:
        p1 = ctk.CTkFrame(self, corner_radius=6)
        p1.grid(row=0, column=0, padx=2, pady=2, sticky="nsew")
        p1.grid_rowconfigure(2, weight=1)
        p1.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            p1, text="1. TASK LIST",
            font=ctk.CTkFont(weight="bold"),
        ).grid(row=0, column=0, pady=(8, 4), padx=8, sticky="w")

        self.backlog_search = ctk.CTkEntry(p1, placeholder_text="Search...")
        self.backlog_search.grid(
            row=1, column=0, padx=8, pady=(0, 4), sticky="ew")
        self.backlog_search.bind(
            "<KeyRelease>", lambda _e: self._filter_task_list())

        theme.style_treeview('ResourceBoard.Treeview', row_height=30)
        ttk.Style().configure('ResourceBoard.Treeview', indent=20)

        self.backlog_frame = ctk.CTkFrame(p1, fg_color="transparent")
        self.backlog_frame.grid(row=2, column=0, padx=8, pady=(0, 8),
                                sticky="nsew")
        self.backlog_frame.grid_rowconfigure(0, weight=1)
        self.backlog_frame.grid_columnconfigure(0, weight=1)

        self.task_tree = ttk.Treeview(
            self.backlog_frame,
            columns=("effort", "duration", "status"),
            show="tree headings",
            style='ResourceBoard.Treeview',
            selectmode='browse',
        )
        self.task_tree.heading("#0", text="Task")
        self.task_tree.heading("effort", text="Effort")
        self.task_tree.heading("duration", text="Duration")
        self.task_tree.heading("status", text="Status")
        self.task_tree.column("#0", width=120, minwidth=80)
        self.task_tree.column("effort", width=60, anchor="center")
        self.task_tree.column("duration", width=60, anchor="center")
        self.task_tree.column("status", width=110, anchor="w")
        self.task_tree.grid(row=0, column=0, sticky="nsew")

        self.task_tree_scrollbar = ttk.Scrollbar(
            self.backlog_frame, orient="vertical",
            command=self.task_tree.yview)
        self.task_tree.configure(yscrollcommand=self.task_tree_scrollbar.set)
        self.task_tree_scrollbar.grid(row=0, column=1, sticky="ns")

        self.task_tree.bind("<<TreeviewSelect>>", self._on_task_tree_select)
        self.task_tree.bind("<<TreeviewOpen>>", self._on_task_tree_open_close)
        self.task_tree.bind("<<TreeviewClose>>", self._on_task_tree_open_close)
        self.task_tree.bind("<ButtonPress-1>", self._on_task_drag_start)
        self.task_tree.bind("<B1-Motion>", self._on_task_drag_motion)
        self.task_tree.bind("<ButtonRelease-1>", self._on_task_drag_drop)

    def _build_inspector_panel(self) -> None:
        p2 = ctk.CTkFrame(self, corner_radius=6)
        p2.grid(row=0, column=1, padx=2, pady=2, sticky="nsew")
        p2.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            p2, text="2. TASK INSPECTOR",
            font=ctk.CTkFont(weight="bold"),
        ).pack(pady=(8, 4))

        self.inspector_text = ctk.CTkTextbox(
            p2, wrap="word", height=160, width=180, state="disabled")
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

        self.heatmap_frame = ctk.CTkFrame(p4, fg_color="transparent")
        self.heatmap_frame.grid(row=1, column=0, padx=8, pady=(0, 8),
                                sticky="nsew")
        self.heatmap_frame.grid_rowconfigure(0, weight=1)
        self.heatmap_frame.grid_columnconfigure(0, weight=1)

        self.heatmap_canvas = tk.Canvas(
            self.heatmap_frame, bg=theme.now(theme.CHART_BG),
            highlightthickness=0)
        self.heatmap_canvas.grid(row=0, column=0, sticky="nsew")

        self.heatmap_hbar = ttk.Scrollbar(
            self.heatmap_frame, orient="horizontal",
            command=self.heatmap_canvas.xview)
        self.heatmap_vbar = ttk.Scrollbar(
            self.heatmap_frame, orient="vertical",
            command=self.heatmap_canvas.yview)
        self.heatmap_canvas.configure(
            xscrollcommand=self.heatmap_hbar.set,
            yscrollcommand=self.heatmap_vbar.set)
        self.heatmap_hbar.grid(row=1, column=0, sticky="ew")
        self.heatmap_vbar.grid(row=0, column=1, sticky="ns")

        self.heatmap_canvas.bind("<Enter>", self._bind_heatmap_wheel)
        self.heatmap_canvas.bind("<Leave>", self._unbind_heatmap_wheel)

    def _bind_heatmap_wheel(self, _event=None):
        for sequence in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
            self.heatmap_canvas.bind_all(sequence, self._on_heatmap_wheel,
                                         add='+')

    def _unbind_heatmap_wheel(self, _event=None):
        for sequence in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
            try:
                self.heatmap_canvas.unbind_all(sequence)
            except tk.TclError:
                pass

    def _on_heatmap_wheel(self, event: tk.Event) -> str:
        delta = getattr(event, 'delta', 0)
        if delta:
            steps = -1 if delta > 0 else 1
            if abs(delta) >= 120:
                steps = int(-delta / 120)
        else:
            steps = -1 if getattr(event, 'num', 5) == 4 else 1
        if self._pointer_over_heatmap():
            if event.state & 0x0001:  # Shift held: horizontal scroll
                self.heatmap_canvas.xview_scroll(steps, 'units')
            else:
                self.heatmap_canvas.yview_scroll(steps, 'units')
            return 'break'
        return ''

    def _pointer_over_heatmap(self) -> bool:
        try:
            under = self.winfo_containing(*self.winfo_pointerxy())
        except tk.TclError:
            return False
        if under is None:
            return False
        canvas = self.heatmap_canvas
        widget = under
        for _ in range(8):
            if widget is canvas:
                return True
            try:
                widget = widget.master
            except AttributeError:
                break
        return False

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        """Reload every panel from the current project state."""
        if not self.project:
            return
        try:
            self._filter_task_list()
            self._filter_pool()
            self._draw_heatmap()
            if self._selected_task_id:
                self._show_task(self._selected_task_id)
        except Exception:
            logger.exception("Could not refresh the resource board")

    # ------------------------------------------------------------------
    # Task list (panel 1)
    # ------------------------------------------------------------------
    def _filter_task_list(self) -> None:
        search = (self.backlog_search.get() or "").lower()
        logger.debug("Filtering task list by %r", search or "<none>")

        selected = self._selected_task_id
        # Preserve expansion state while rebuilding.
        open_items = set(self.task_tree.get_children())

        for child in self.task_tree.get_children():
            self.task_tree.delete(child)

        visible_ids = self._visible_task_ids_for(search)
        display_ids = self.project.display_ids()

        def add_task(task: Task, parent: str = "") -> None:
            if task.id not in visible_ids:
                return
            text = f"#{display_ids.get(task.id, task.id)} {task.name}"
            values = (
                f"{self._task_effort(task):.1f}h",
                f"{self._task_duration(task)}d",
                self._task_status_text(task),
            )
            is_open = task.id in self._expanded_task_ids
            item = self.task_tree.insert(
                parent, tk.END, iid=task.id, text=text, values=values,
                open=is_open)
            if task.id == selected:
                self.task_tree.selection_set(item)
            for child in self._child_tasks(task):
                add_task(child, item)

        for root_task in self.project.get_root_tasks():
            add_task(root_task)

    def _visible_task_ids_for(self, search: str) -> Set[str]:
        """Return IDs of tasks matching the search, including their ancestors."""
        all_ids = {task.id for task in self.project.tasks}
        if not search:
            return all_ids
        matched: Set[str] = set()
        for task in self.project.tasks:
            status = self._task_status_text(task).lower()
            if (search in task.name.lower()
                    or search in task.id.lower()
                    or search in status):
                matched.add(task.id)
        if not matched:
            return set()
        visible = set(matched)
        for task_id in matched:
            parent_id = self._parent_id(task_id)
            while parent_id:
                visible.add(parent_id)
                parent_id = self._parent_id(parent_id)
        return visible

    def _parent_id(self, task_id: str) -> Optional[str]:
        task = self.project.get_task_by_id(task_id)
        return task.parent_task_id if task else None

    def _child_tasks(self, task: Task) -> List[Task]:
        return [t for t in self.project.tasks
                if t.parent_task_id == task.id]

    def _task_effort(self, task: Task) -> float:
        return sum(float(a.get("estimated_hours", 0.0))
                   for a in task.resource_assignments) or 0.0

    def _task_duration(self, task: Task) -> int:
        if task.start_date and task.end_date:
            return _working_days_between(task.start_date, task.end_date)
        return 0

    def _task_status_text(self, task: Task) -> str:
        if task.is_milestone:
            return "Status: Milestone"
        if not task.resource_assignments:
            return STATUS_UNASSIGNED
        names = self._assigned_resource_names(task)
        if names:
            return f"Status: Assigned ({', '.join(names)})"
        return "Status: Assigned"

    def _assigned_resource_names(self, task: Task) -> List[str]:
        repo = self.project.resource_repository
        names: List[str] = []
        seen: Set[str] = set()
        for assignment in task.resource_assignments:
            entity = _entity_by_id(repo, assignment.get("resource_id", ""))
            if entity and entity.id not in seen:
                names.append(entity.name)
                seen.add(entity.id)
        return names

    def _on_task_tree_select(self, _event=None) -> None:
        selection = self.task_tree.selection()
        if selection:
            self._select_task(selection[0])

    def _on_task_tree_open_close(self, _event=None) -> None:
        for item in self.task_tree.get_children():
            self._sync_expansion(item)

    def _sync_expansion(self, item: str) -> None:
        task_id = self.task_tree.item(item, "iid")
        if self.task_tree.item(item, "open"):
            self._expanded_task_ids.add(task_id)
        else:
            self._expanded_task_ids.discard(task_id)
        for child in self.task_tree.get_children(item):
            self._sync_expansion(child)

    # ------------------------------------------------------------------
    # Drag and drop from the task list
    # ------------------------------------------------------------------
    def _on_task_drag_start(self, event: tk.Event) -> None:
        row = self.task_tree.identify_row(event.y)
        self._drag_task_id = row or None
        self._drag_origin = (event.x, event.y) if row else None

    def _on_task_drag_motion(self, event: tk.Event) -> None:
        if self._drag_task_id is None or self._drag_origin is None:
            return
        if self._drag_window is None:
            origin_x, origin_y = self._drag_origin
            if max(abs(event.x - origin_x), abs(event.y - origin_y)) < 5:
                return
            task = self.project.get_task_by_id(self._drag_task_id)
            if task is None:
                return
            self._drag_window = tk.Toplevel(self)
            self._drag_window.overrideredirect(True)
            self._drag_window.attributes("-alpha", 0.7)
            tk.Label(self._drag_window, text=task.name, bg="#1f6aa5",
                     fg="white", padx=8, pady=4).pack()
        self._drag_window.deiconify()
        self._move_drag_window(event)

    def _move_drag_window(self, event: tk.Event) -> None:
        if self._drag_window is None:
            return
        x = self.task_tree.winfo_rootx() + event.x + 12
        y = self.task_tree.winfo_rooty() + event.y + 12
        self._drag_window.geometry(f"+{x}+{y}")

    def _on_task_drag_drop(self, _event: tk.Event) -> None:
        was_dragging = self._drag_window is not None
        if self._drag_window:
            self._drag_window.destroy()
            self._drag_window = None

        task_id = self._drag_task_id
        self._drag_task_id = None
        self._drag_origin = None
        if task_id is None or not was_dragging:
            return

        try:
            pointer_x, pointer_y = self.winfo_pointerxy()
            target = self.winfo_containing(pointer_x, pointer_y)
        except tk.TclError:
            return

        resource_id = getattr(target, "_resource_id", None)
        if resource_id is None:
            # Walk up through CustomTkinter's internal widgets.
            parent = target
            for _ in range(6):
                if parent is None:
                    break
                resource_id = getattr(parent, "_resource_id", None)
                if resource_id:
                    break
                try:
                    parent = parent.master
                except AttributeError:
                    break
        if resource_id:
            self._assign_task(task_id, resource_id)

    # ------------------------------------------------------------------
    # Inspector
    # ------------------------------------------------------------------
    def _select_task(self, task_id: str) -> None:
        self._selected_task_id = task_id
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
            self.preview_label.configure(
                text=f"Assignee preview: {resource.name} - {text}",
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
        logger.debug("Filtering resource pool by %r", selected_filter)
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
                anchor="w",
                command=lambda e=entity.id: self._select_resource(e),
            )
            card._resource_id = entity.id
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
    def _projected_daily_load(
        self,
        task: Optional[Task],
        resource: Optional[Resource],
    ) -> Dict[date, float]:
        """Simulated daily load if *task* were assigned to *resource*."""
        load: Dict[date, float] = {}
        if task is None or resource is None or isinstance(resource, TeamPool):
            return load
        effort = self._task_effort(task) or 8.0
        start = task.start_date
        end = task.end_date or start
        if not start or not end:
            return load
        calendar = self.project.calendar_for(task)
        raw_workdays = [
            start + timedelta(days=i)
            for i in range((end - start).days + 1)
        ]
        workdays = [
            (d.date() if isinstance(d, datetime) else d)
            for d in raw_workdays
            if calendar.is_working_day(d)
        ]
        if not workdays:
            return load
        per_day = effort / len(workdays)
        return {day: per_day for day in workdays}

    def _draw_heatmap(self) -> None:
        canvas = self.heatmap_canvas
        canvas.delete("all")
        logger.debug("Drawing resource heatmap")

        repo = self.project.resource_repository
        entities = list(repo.resources.values()) + list(repo.teams.values())
        if not entities:
            canvas.create_text(
                80, 30, text="No resources loaded",
                fill=theme.now(theme.GRID_TEXT), anchor="w")
            canvas.configure(scrollregion=canvas.bbox("all"))
            return

        selected_task = self.project.get_task_by_id(
            self._selected_task_id or "")
        selected_resource = _entity_by_id(
            repo, self._selected_resource_id or "")
        projected = self._projected_daily_load(selected_task, selected_resource)

        earliest = date.today()
        for task in self.project.tasks:
            if task.start_date:
                d = (task.start_date.date()
                     if isinstance(task.start_date, datetime)
                     else task.start_date)
                if d < earliest:
                    earliest = d
        days = [earliest + timedelta(days=i) for i in range(7)]
        day_width = 100
        row_height = 50
        left = 160
        right = left + len(days) * day_width + 8
        bottom = 40 + len(entities) * row_height + 8

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

            if (entity.id == getattr(selected_resource, "id", None)
                    and projected):
                for day, hours in projected.items():
                    loads[day] = loads.get(day, 0.0) + hours

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

        canvas.configure(scrollregion=(0, 0, right, bottom))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _assign_task(self, task_id: str, resource_id: str) -> None:
        task = self.project.get_task_by_id(task_id)
        resource = _entity_by_id(self.project.resource_repository, resource_id)
        if not task or not resource:
            self._say("Select both a task and a resource first.")
            return

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

    def _assign_selected(self) -> None:
        self._assign_task(self._selected_task_id or "",
                          self._selected_resource_id or "")

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
