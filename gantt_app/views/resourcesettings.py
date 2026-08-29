import tkinter as tk
from datetime import date
from typing import Callable, Dict, Optional

import customtkinter as ctk

from gantt_app.resource_model import (
    DAYS, DAY_LABELS, FTE_WEEKLY_HOURS, DaysOffRange, Resource,
    ResourceRepository, ResourceType, SchedulePattern, TeamPool,
    capacity_from_entry, default_daily_capacity,
)
from gantt_app.utils.log import get_logger
from gantt_app.views import dialogs as messagebox
from gantt_app.views.modal import grab_when_visible, take_grab


logger = get_logger(__name__)
CAPACITY_UNITS = ("FTE", "Daily Hours", "Weekly Hours")
TYPE_LABELS = {
    ResourceType.NAMED: "Named (Person)",
    ResourceType.GENERIC: "Generic (Role Placeholder)",
}
TYPE_VALUES = {label: kind for kind, label in TYPE_LABELS.items()}


def _field(parent, label, widget, row):
    ctk.CTkLabel(parent, text=label, anchor=tk.W,
                 font=("Arial", 11, "bold")).grid(
                     row=row, column=0, padx=(12, 8), pady=6, sticky="w")
    widget.grid(row=row, column=1, padx=(0, 12), pady=6, sticky="ew")


def _set_entry(entry, value):
    entry.delete(0, tk.END)
    entry.insert(0, str(value))


def _number(entry, label, default=0.0):
    text = entry.get().strip().rstrip("%")
    try:
        value = float(text) if text else default
    except ValueError as error:
        raise ValueError(f"{label} must be a number.") from error
    if value < 0:
        raise ValueError(f"{label} cannot be negative.")
    return value


def _schedule_short(pattern):
    return {
        SchedulePattern.STANDARD: "Standard (M-F)",
        SchedulePattern.FULL_WEEK: "Full Week (M-Sun)",
        SchedulePattern.WEEKEND_ONLY: "Weekend Only",
        SchedulePattern.CONTINUOUS: "24/7 Continuous",
        SchedulePattern.CUSTOM: "Custom",
    }[pattern]


def _daily_summary(values):
    active = [(index, DAY_LABELS[index], values[day])
              for index, day in enumerate(DAYS) if values[day] > 0]
    if not active:
        return "0h/day"
    hours = {value for _index, _label, value in active}
    if len(hours) != 1:
        return f"{sum(values.values()):g}h/week (custom)"
    indices = [index for index, _label, _value in active]
    labels = [label for _index, label, _value in active]
    days = (f"{labels[0]}-{labels[-1]}"
            if indices == list(range(indices[0], indices[-1] + 1))
            else ", ".join(labels))
    return f"{active[0][2]:g}h/day ({days})"


class DataGrid(ctk.CTkScrollableFrame):
    def __init__(self, master, columns, on_select, **kwargs):
        super().__init__(master, **kwargs)
        self.columns = columns
        self.on_select = on_select
        self.row_widgets = {}
        self.selected_id = None
        for column, (_name, width, weight, _anchor) in enumerate(columns):
            self.grid_columnconfigure(column, weight=weight, minsize=width)
        self._header()

    def _header(self):
        for column, (name, _width, _weight, anchor) in enumerate(self.columns):
            ctk.CTkLabel(self, text=name, font=("Arial", 10, "bold"),
                         anchor=anchor, fg_color=("gray80", "gray25")).grid(
                             row=0, column=column, padx=1, pady=(0, 2),
                             sticky="nsew")

    def clear(self):
        for widgets in self.row_widgets.values():
            for widget in widgets:
                widget.destroy()
        self.row_widgets = {}
        self.selected_id = None

    def add_row(self, item_id, values):
        row = len(self.row_widgets) + 1
        widgets = []
        for column, (value, specification) in enumerate(zip(values, self.columns)):
            _name, width, _weight, anchor = specification
            text, text_color = value if isinstance(value, tuple) else (value, None)
            options = {"text_color": text_color} if text_color else {}
            label = ctk.CTkLabel(
                self, text=text, anchor=anchor, justify=tk.LEFT,
                wraplength=max(width - 10, 40), fg_color="transparent",
                **options)
            label.grid(row=row, column=column, padx=1, pady=1, sticky="nsew")
            label.bind("<Button-1>", lambda _event, key=item_id: self.select(key))
            widgets.append(label)
        self.row_widgets[item_id] = widgets

    def select(self, item_id, notify=True):
        if item_id not in self.row_widgets:
            return
        for key, widgets in self.row_widgets.items():
            color = ("#b9d8f2", "#24577a") if key == item_id else "transparent"
            for widget in widgets:
                widget.configure(fg_color=color)
        self.selected_id = item_id
        if notify:
            self.on_select(item_id)


class BaseEditorModal(ctk.CTkToplevel):
    GEOMETRY = "900x680"

    def __init__(self, master, title, tabs, on_apply):
        super().__init__(master)
        self.on_apply = on_apply
        self.title(title)
        self.geometry(self.GEOMETRY)
        self.minsize(760, 560)
        self.transient(master.winfo_toplevel())
        self.bind("<Escape>", lambda _event: self.destroy())
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill=tk.BOTH, expand=True, padx=14, pady=(14, 6))
        self.tabs = {name: self.tabview.add(name) for name in tabs}
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill=tk.X, padx=14, pady=(0, 14))
        ctk.CTkButton(footer, text="Cancel", width=100,
                      command=self.destroy).pack(side=tk.RIGHT, padx=(6, 0))
        ctk.CTkButton(footer, text="Save & Apply", width=120,
                      command=self.save_and_apply).pack(side=tk.RIGHT)
        self.problem_label = ctk.CTkLabel(
            footer, text="", text_color="#c0392b", anchor=tk.W)
        self.problem_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        take_grab(self)
        self.after_idle(self.focus_set)

    def fail(self, message):
        self.problem_label.configure(text=message)

    def save_and_apply(self):
        raise NotImplementedError


class ResourceEditorModal(BaseEditorModal):
    def __init__(self, master, repo, resource=None, on_apply=None):
        self.repo = repo
        self.resource = resource
        self.days_off = list(resource.days_off) if resource else []
        self.team_controls = {}
        self._updating_capacity = False
        title = f"Resource Editor: {resource.name}" if resource else "Create Resource"
        super().__init__(master, title,
                         ("General Settings", "Days Off", "Assigned Teams",
                          "Assigned Tasks (Read-Only)"), on_apply)
        self._build_general()
        self._build_days_off()
        self._build_teams()
        self._build_tasks()
        if resource:
            self._load_resource()
        else:
            self._apply_pattern(SchedulePattern.STANDARD.value)

    def _build_general(self):
        tab = self.tabs["General Settings"]
        tab.grid_columnconfigure(1, weight=1)
        self.name_entry = ctk.CTkEntry(tab)
        _field(tab, "Resource Name", self.name_entry, 0)
        self.type_menu = ctk.CTkOptionMenu(tab, values=list(TYPE_VALUES))
        self.type_menu.set(TYPE_LABELS[ResourceType.NAMED])
        _field(tab, "Resource Type", self.type_menu, 1)
        self.role_entry = ctk.CTkEntry(tab)
        _field(tab, "Role / Skill Tag", self.role_entry, 2)
        self.schedule_menu = ctk.CTkOptionMenu(
            tab, values=[pattern.value for pattern in SchedulePattern],
            command=self._apply_pattern)
        self.schedule_menu.set(SchedulePattern.STANDARD.value)
        _field(tab, "Work Schedule Pattern", self.schedule_menu, 3)

        capacity = ctk.CTkFrame(tab, fg_color="transparent")
        self.capacity_unit = ctk.CTkSegmentedButton(
            capacity, values=list(CAPACITY_UNITS), command=self._unit_changed)
        self.capacity_unit.set("Weekly Hours")
        self.capacity_unit.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.capacity_entry = ctk.CTkEntry(capacity, width=90)
        self.capacity_entry.pack(side=tk.RIGHT, padx=(8, 0))
        self.capacity_entry.bind("<FocusOut>", self._capacity_changed)
        self.capacity_entry.bind("<Return>", self._capacity_changed)
        _field(tab, "Capacity Unit & Value", capacity, 4)

        day_frame = ctk.CTkFrame(tab, fg_color="transparent")
        self.daily_entries = {}
        for column, (day, label) in enumerate(zip(DAYS, DAY_LABELS)):
            day_frame.grid_columnconfigure(column, weight=1, uniform="days")
            cell = ctk.CTkFrame(day_frame, fg_color="transparent")
            cell.grid(row=0, column=column, padx=2, sticky="ew")
            ctk.CTkLabel(cell, text=label).pack()
            entry = ctk.CTkEntry(cell, width=55)
            entry.pack(fill=tk.X)
            entry.bind("<FocusOut>", self._daily_changed)
            entry.bind("<Return>", self._daily_changed)
            self.daily_entries[day] = entry
        _field(tab, "Day-by-Day Capacity", day_frame, 5)
        self.capacity_summary = ctk.CTkLabel(tab, text="", anchor=tk.W)
        self.capacity_summary.grid(row=6, column=1, padx=(0, 12), sticky="w")
        self.rate_entry = ctk.CTkEntry(tab)
        _field(tab, "Hourly Rate ($)", self.rate_entry, 7)

    def _daily_values(self):
        values = {}
        for day, entry in self.daily_entries.items():
            value = _number(entry, f"{day.title()} capacity")
            if value > 24:
                raise ValueError("Daily capacity cannot exceed 24 hours.")
            values[day] = value
        return values

    def _set_daily(self, values):
        self._updating_capacity = True
        for day, entry in self.daily_entries.items():
            _set_entry(entry, f"{values[day]:g}")
        self._updating_capacity = False
        weekly = sum(values.values())
        self.capacity_summary.configure(
            text=f"{weekly:g} hours/week | {weekly / FTE_WEEKLY_HOURS:.2f} FTE")

    def _apply_pattern(self, value):
        values = default_daily_capacity(SchedulePattern.read(value))
        self._set_daily(values)
        self._set_capacity_value(sum(values.values()))

    def _set_capacity_value(self, weekly):
        unit = self.capacity_unit.get()
        active = len([value for value in self._daily_values().values() if value]) or 1
        value = (weekly / FTE_WEEKLY_HOURS if unit == "FTE"
                 else weekly / active if unit == "Daily Hours" else weekly)
        _set_entry(self.capacity_entry, f"{value:.2f}".rstrip("0").rstrip("."))

    def _unit_changed(self, _value=None):
        try:
            self._set_capacity_value(sum(self._daily_values().values()))
        except ValueError as error:
            self.fail(str(error))

    def _capacity_changed(self, _event=None):
        try:
            value = _number(self.capacity_entry, "Capacity")
            pattern = SchedulePattern.read(self.schedule_menu.get())
            if pattern == SchedulePattern.CUSTOM:
                current = self._daily_values()
                total = sum(current.values())
                active = len([hours for hours in current.values() if hours]) or 7
                target = (value * FTE_WEEKLY_HOURS if self.capacity_unit.get() == "FTE"
                          else value * active if self.capacity_unit.get() == "Daily Hours"
                          else value)
                values = ({day: hours * target / total for day, hours in current.items()}
                          if total else dict.fromkeys(DAYS, target / 7))
            else:
                values = capacity_from_entry(pattern, value,
                                             self.capacity_unit.get())
            self._set_daily(values)
        except ValueError as error:
            self.fail(str(error))

    def _daily_changed(self, _event=None):
        if self._updating_capacity:
            return
        try:
            values = self._daily_values()
            self.schedule_menu.set(SchedulePattern.CUSTOM.value)
            self._set_daily(values)
            self._set_capacity_value(sum(values.values()))
        except ValueError as error:
            self.fail(str(error))

    def _build_days_off(self):
        tab = self.tabs["Days Off"]
        bar = ctk.CTkFrame(tab, fg_color="transparent")
        bar.pack(fill=tk.X, padx=8, pady=8)
        self.day_off_start = ctk.CTkEntry(bar, placeholder_text="Start YYYY-MM-DD")
        self.day_off_start.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)
        self.day_off_end = ctk.CTkEntry(bar, placeholder_text="End YYYY-MM-DD")
        self.day_off_end.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)
        self.day_off_reason = ctk.CTkEntry(bar, placeholder_text="Reason")
        self.day_off_reason.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)
        ctk.CTkButton(bar, text="+ Add Range", width=100,
                      command=self._add_day_off).pack(side=tk.LEFT, padx=3)
        self.days_off_table = ctk.CTkScrollableFrame(tab)
        self.days_off_table.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self._render_days_off()

    def _add_day_off(self):
        try:
            item = DaysOffRange(date.fromisoformat(self.day_off_start.get().strip()),
                                date.fromisoformat(self.day_off_end.get().strip()),
                                self.day_off_reason.get())
        except ValueError as error:
            self.fail(f"Invalid days-off range: {error}")
            return
        self.days_off.append(item)
        for entry in (self.day_off_start, self.day_off_end, self.day_off_reason):
            entry.delete(0, tk.END)
        self._render_days_off()

    def _render_days_off(self):
        for widget in self.days_off_table.winfo_children():
            widget.destroy()
        headers = ("Start Date", "End Date", "Reason", "Actions")
        for column, header in enumerate(headers):
            self.days_off_table.grid_columnconfigure(column, weight=1)
            ctk.CTkLabel(self.days_off_table, text=header,
                         font=("Arial", 10, "bold")).grid(
                             row=0, column=column, padx=5, pady=5, sticky="w")
        for row, item in enumerate(self.days_off, start=1):
            for column, text in enumerate((item.start_date.isoformat(),
                                           item.end_date.isoformat(), item.reason)):
                ctk.CTkLabel(self.days_off_table, text=text).grid(
                    row=row, column=column, padx=5, pady=5, sticky="w")
            ctk.CTkButton(
                self.days_off_table, text="Delete", width=70,
                command=lambda index=row - 1: self._delete_day_off(index)).grid(
                    row=row, column=3, padx=5, pady=5)

    def _delete_day_off(self, index):
        self.days_off.pop(index)
        self._render_days_off()

    def _build_teams(self):
        tab = self.tabs["Assigned Teams"]
        self.teams_table = ctk.CTkScrollableFrame(tab)
        self.teams_table.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        headers = ("Assign", "Team Name", "Schedule Pattern", "Allocation / Split %")
        for column, header in enumerate(headers):
            self.teams_table.grid_columnconfigure(column, weight=(2 if column == 1 else 1))
            ctk.CTkLabel(self.teams_table, text=header,
                         font=("Arial", 10, "bold")).grid(
                             row=0, column=column, padx=5, pady=5, sticky="w")
        for row, team in enumerate(self.repo.teams.values(), start=1):
            ratio = self.resource.team_memberships.get(team.id, 0) if self.resource else 0
            assigned = ctk.BooleanVar(value=ratio > 0)
            split = ctk.StringVar(value=f"{ratio * 100:g}" if ratio else "100")
            ctk.CTkCheckBox(self.teams_table, text="", variable=assigned,
                            width=24).grid(row=row, column=0, padx=5, pady=5)
            ctk.CTkLabel(self.teams_table, text=team.name).grid(
                row=row, column=1, padx=5, pady=5, sticky="w")
            ctk.CTkLabel(self.teams_table,
                         text=_schedule_short(team.schedule_pattern)).grid(
                             row=row, column=2, padx=5, pady=5, sticky="w")
            ctk.CTkEntry(self.teams_table, textvariable=split, width=80).grid(
                row=row, column=3, padx=5, pady=5)
            self.team_controls[team.id] = (assigned, split)

    def _build_tasks(self):
        tab = self.tabs["Assigned Tasks (Read-Only)"]
        ctk.CTkLabel(
            tab, text="Task assignment is managed via the Gantt / Task Scheduler view.",
            font=("Arial", 12, "bold")).pack(pady=18)
        headers = ("Task ID", "Task Name", "Project", "Start Date", "End Date",
                   "Allocated Hours")
        table = ctk.CTkFrame(tab, fg_color="transparent")
        table.pack(fill=tk.X, padx=10)
        for column, header in enumerate(headers):
            table.grid_columnconfigure(column, weight=1)
            ctk.CTkLabel(table, text=header,
                         font=("Arial", 10, "bold")).grid(
                             row=0, column=column, padx=4, sticky="w")

    def _load_resource(self):
        _set_entry(self.name_entry, self.resource.name)
        self.type_menu.set(TYPE_LABELS[self.resource.resource_type])
        _set_entry(self.role_entry, self.resource.role_type)
        self.schedule_menu.set(self.resource.schedule_pattern.value)
        self._set_daily(self.resource.daily_capacity_hours)
        self._set_capacity_value(self.resource.weekly_capacity_hours)
        _set_entry(self.rate_entry, f"{self.resource.cost_per_hour:g}")

    def save_and_apply(self):
        kind = TYPE_VALUES[self.type_menu.get()]
        role = self.role_entry.get().strip() or "General"
        name = self.name_entry.get().strip()
        if not name and kind == ResourceType.GENERIC:
            name = self.repo.next_placeholder_name(role)
        if not name:
            self.fail("Resource Name is required for a named person.")
            return
        try:
            daily = self._daily_values()
            rate = _number(self.rate_entry, "Hourly rate")
            allocations = {}
            for team_id, (assigned, split) in self.team_controls.items():
                if assigned.get():
                    value = float(split.get().strip().rstrip("%"))
                    if value < 0 or value > 100:
                        raise ValueError("Team splits must be between 0 and 100%.")
                    allocations[team_id] = value / 100
        except ValueError as error:
            self.fail(str(error))
            return
        if self.resource:
            resource = self.resource
            resource.name = name
            resource.resource_type = kind
            resource.role_type = role
            resource.schedule_pattern = SchedulePattern.read(self.schedule_menu.get())
            resource.set_daily_capacity(daily, preserve_pattern=True)
            resource.cost_per_hour = rate
            resource.days_off = list(self.days_off)
            resource.team_memberships = allocations
            logger.info("Updated resource %r (%s)", resource.name, resource.id)
        else:
            resource = Resource(
                id=self.repo.new_id("res"), name=name, resource_type=kind,
                role_type=role, schedule_pattern=SchedulePattern.read(
                    self.schedule_menu.get()), daily_capacity_hours=daily,
                cost_per_hour=rate, team_memberships=allocations,
                days_off=list(self.days_off))
            self.repo.add_resource(resource)
        if self.on_apply:
            self.on_apply(resource.id)
        self.destroy()


class TeamEditorModal(BaseEditorModal):
    def __init__(self, master, repo, team=None, on_apply=None):
        self.repo = repo
        self.team = team
        self.allocations = {
            resource.id: resource.team_memberships.get(team.id, 0) * 100
            for resource in repo.resources.values()
            if team and resource.team_memberships.get(team.id, 0) > 0
        }
        self.member_split_vars = {}
        title = f"Team Editor: {team.name}" if team else "Create Team"
        super().__init__(master, title,
                         ("General Settings", "Team Members & Split Matrix",
                          "Assigned Tasks"), on_apply)
        self._build_general()
        self._build_members()
        self._build_tasks()
        if team:
            self._load_team()
        else:
            self._mode_changed()

    def _build_general(self):
        tab = self.tabs["General Settings"]
        tab.grid_columnconfigure(1, weight=1)
        self.name_entry = ctk.CTkEntry(tab)
        _field(tab, "Team Name", self.name_entry, 0)
        self.schedule_menu = ctk.CTkOptionMenu(
            tab, values=[pattern.value for pattern in SchedulePattern],
            command=lambda _value: self._update_team_summary())
        self.schedule_menu.set(SchedulePattern.STANDARD.value)
        _field(tab, "Default Team Schedule Pattern", self.schedule_menu, 1)
        self.mode = ctk.StringVar(value="Dynamic")
        mode_frame = ctk.CTkFrame(tab, fg_color="transparent")
        ctk.CTkRadioButton(
            mode_frame, text="Dynamic (Calculated from Assigned Members)",
            variable=self.mode, value="Dynamic", command=self._mode_changed).pack(
                anchor=tk.W, pady=2)
        ctk.CTkRadioButton(
            mode_frame, text="Fixed Team Capacity (Manual Override)",
            variable=self.mode, value="Fixed", command=self._mode_changed).pack(
                anchor=tk.W, pady=2)
        _field(tab, "Capacity Calculation Mode", mode_frame, 2)
        fixed_frame = ctk.CTkFrame(tab, fg_color="transparent")
        self.fixed_unit = ctk.CTkSegmentedButton(
            fixed_frame, values=list(CAPACITY_UNITS),
            command=lambda _value: self._update_team_summary())
        self.fixed_unit.set("Weekly Hours")
        self.fixed_unit.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.fixed_entry = ctk.CTkEntry(fixed_frame, width=90)
        self.fixed_entry.pack(side=tk.RIGHT, padx=(8, 0))
        self.fixed_entry.bind("<KeyRelease>",
                              lambda _event: self._update_team_summary())
        _field(tab, "Fixed Capacity", fixed_frame, 3)

    def _mode_changed(self):
        state = "normal" if self.mode.get() == "Fixed" else "disabled"
        self.fixed_entry.configure(state=state)
        self.fixed_unit.configure(state=state)
        if hasattr(self, "team_capacity_summary"):
            self._update_team_summary()

    def _build_members(self):
        tab = self.tabs["Team Members & Split Matrix"]
        add_bar = ctk.CTkFrame(tab, fg_color="transparent")
        add_bar.pack(fill=tk.X, padx=8, pady=8)
        self.member_menu = ctk.CTkOptionMenu(add_bar, values=["Select Resource to Add..."])
        self.member_menu.set("Select Resource to Add...")
        self.member_menu.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self.add_split_entry = ctk.CTkEntry(add_bar, width=90,
                                            placeholder_text="Split %")
        self.add_split_entry.insert(0, "100")
        self.add_split_entry.pack(side=tk.LEFT, padx=6)
        ctk.CTkButton(add_bar, text="+ Add to Team", width=110,
                      command=self._add_member).pack(side=tk.LEFT, padx=(6, 0))
        self.member_table = ctk.CTkScrollableFrame(tab)
        self.member_table.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 6))
        self.team_capacity_summary = ctk.CTkLabel(tab, text="", anchor=tk.W,
                                                  justify=tk.LEFT)
        self.team_capacity_summary.pack(fill=tk.X, padx=12, pady=(0, 8))
        self._render_members()

    def _available_member_names(self):
        return [resource.name for resource in self.repo.resources.values()
                if resource.id not in self.allocations]

    def _resource_for_name(self, name):
        return next((resource for resource in self.repo.resources.values()
                     if resource.name == name), None)

    def _add_member(self):
        resource = self._resource_for_name(self.member_menu.get())
        if not resource:
            self.fail("Select a resource to add.")
            return
        try:
            split = _number(self.add_split_entry, "Split percentage", 100)
            if split > 100:
                raise ValueError("Split percentage cannot exceed 100%.")
        except ValueError as error:
            self.fail(str(error))
            return
        self.allocations[resource.id] = split
        self._render_members()

    def _remove_member(self, resource_id):
        self.allocations.pop(resource_id, None)
        self._render_members()

    def _split_changed(self, resource_id, variable):
        text = variable.get().strip().rstrip("%")
        try:
            value = float(text) if text else 0
        except ValueError:
            return
        if 0 <= value <= 100:
            self.allocations[resource_id] = value
            self._update_team_summary()

    def _render_members(self):
        for widget in self.member_table.winfo_children():
            widget.destroy()
        available = self._available_member_names()
        self.member_menu.configure(values=available or ["Select Resource to Add..."])
        self.member_menu.set(available[0] if available else "Select Resource to Add...")
        headers = ("Member Name", "Type", "Role", "Schedule", "Member Capacity",
                   "Team Split %", "Actions")
        widths = (150, 75, 100, 110, 135, 90, 80)
        for column, (header, width) in enumerate(zip(headers, widths)):
            self.member_table.grid_columnconfigure(column, weight=1, minsize=width)
            ctk.CTkLabel(self.member_table, text=header,
                         font=("Arial", 10, "bold")).grid(
                             row=0, column=column, padx=4, pady=5, sticky="w")
        self.member_split_vars = {}
        for row, (resource_id, split) in enumerate(self.allocations.items(), start=1):
            resource = self.repo.resources.get(resource_id)
            if not resource:
                continue
            values = (resource.name, resource.resource_type.value.upper(),
                      resource.role_type, _schedule_short(resource.schedule_pattern),
                      f"{resource.weekly_capacity_hours:g}h/wk ({resource.fte:.2f} FTE)")
            for column, value in enumerate(values):
                ctk.CTkLabel(self.member_table, text=value, anchor=tk.W,
                             wraplength=widths[column] - 8).grid(
                                 row=row, column=column, padx=4, pady=5,
                                 sticky="w")
            variable = ctk.StringVar(value=f"{split:g}")
            ctk.CTkEntry(self.member_table, textvariable=variable,
                         width=75).grid(row=row, column=5, padx=4, pady=5)
            variable.trace_add(
                "write", lambda *_args, key=resource_id, var=variable:
                    self._split_changed(key, var))
            self.member_split_vars[resource_id] = variable
            ctk.CTkButton(
                self.member_table, text="Remove", width=70,
                command=lambda key=resource_id: self._remove_member(key)).grid(
                    row=row, column=6, padx=4, pady=5)
        self._update_team_summary()

    def _calculated_daily(self):
        return {
            day: sum(self.repo.resources[resource_id].daily_capacity_hours[day]
                     * split / 100
                     for resource_id, split in self.allocations.items()
                     if resource_id in self.repo.resources)
            for day in DAYS
        }

    def _update_team_summary(self):
        label = "Aggregated Daily Capacity"
        if self.mode.get() == "Fixed":
            try:
                value = _number(self.fixed_entry, "Fixed capacity")
                daily = capacity_from_entry(
                    SchedulePattern.read(self.schedule_menu.get()), value,
                    self.fixed_unit.get())
            except ValueError:
                daily = dict.fromkeys(DAYS, 0.0)
            label = "Fixed Daily Capacity"
        else:
            daily = self._calculated_daily()
        weekly = sum(daily.values())
        self.team_capacity_summary.configure(
            text=(f"{label}: " + " | ".join(
                f"{day_label}: {daily[day]:g}h"
                for day, day_label in zip(DAYS, DAY_LABELS)) +
                f"\nTotal Weekly Team Capacity: "
                f"{weekly / FTE_WEEKLY_HOURS:.2f} FTE ({weekly:g} hours/week)"))

    def _build_tasks(self):
        tab = self.tabs["Assigned Tasks"]
        ctk.CTkLabel(
            tab, text="Task allocation to teams is managed via the Gantt / Task Scheduler view.",
            font=("Arial", 12, "bold")).pack(pady=18)
        headers = ("Task ID", "Task Name", "Project", "Start Date", "End Date",
                   "Allocated Team Hours")
        table = ctk.CTkFrame(tab, fg_color="transparent")
        table.pack(fill=tk.X, padx=10)
        for column, header in enumerate(headers):
            table.grid_columnconfigure(column, weight=1)
            ctk.CTkLabel(table, text=header,
                         font=("Arial", 10, "bold")).grid(
                             row=0, column=column, padx=4, sticky="w")

    def _load_team(self):
        _set_entry(self.name_entry, self.team.name)
        self.schedule_menu.set(self.team.schedule_pattern.value)
        self.mode.set("Fixed" if self.team.is_fixed_capacity else "Dynamic")
        self.fixed_unit.set("Weekly Hours")
        self.fixed_entry.configure(state="normal")
        _set_entry(self.fixed_entry, f"{self.team.fixed_hours:g}")
        self._mode_changed()

    def save_and_apply(self):
        name = self.name_entry.get().strip()
        if not name:
            self.fail("Team Name is required.")
            return
        pattern = SchedulePattern.read(self.schedule_menu.get())
        fixed = self.mode.get() == "Fixed"
        try:
            value = _number(self.fixed_entry, "Fixed capacity") if fixed else 0
            daily = capacity_from_entry(pattern, value, self.fixed_unit.get())
        except ValueError as error:
            self.fail(str(error))
            return
        if self.team:
            team = self.team
            team.name = name
            team.schedule_pattern = pattern
            team.is_fixed_capacity = fixed
            team.fixed_daily_hours = daily
            team.fixed_hours = sum(daily.values())
            logger.info("Updated resource team %r (%s)", team.name, team.id)
        else:
            team = TeamPool(id=self.repo.new_id("team"), name=name,
                            schedule_pattern=pattern, is_fixed_capacity=fixed,
                            fixed_daily_hours=daily)
            self.repo.add_team(team)
        for resource in self.repo.resources.values():
            split = self.allocations.get(resource.id, 0)
            if split:
                resource.team_memberships[team.id] = split / 100
            else:
                resource.team_memberships.pop(team.id, None)
        if self.on_apply:
            self.on_apply(team.id)
        self.destroy()


class ResourceSettingsWindow(ctk.CTkToplevel):
    GEOMETRY = "1250x760"
    RESOURCE_COLUMNS = (
        ("#", 45, 0, tk.CENTER),
        ("Type", 85, 1, tk.W),
        ("Resource Name", 180, 3, tk.W),
        ("Role / Skill", 130, 2, tk.W),
        ("Schedule", 125, 2, tk.W),
        ("Capacity", 100, 1, tk.W),
        ("Assigned Teams", 160, 2, tk.W),
        ("Days Off Active", 160, 2, tk.W),
    )
    TEAM_COLUMNS = (
        ("#", 45, 0, tk.CENTER),
        ("Team Name", 210, 3, tk.W),
        ("Schedule Pattern", 150, 2, tk.W),
        ("Capacity Mode", 155, 2, tk.W),
        ("Total Capacity", 155, 2, tk.W),
        ("Member Count", 100, 1, tk.W),
        ("Daily Summary", 150, 2, tk.W),
    )

    def __init__(self, master, repo, active_project_ids=None,
                 on_save: Optional[Callable] = None, **kwargs):
        super().__init__(master, **kwargs)
        self.repo = repo
        self.active_project_ids = list(active_project_ids or [])
        self.on_save = on_save
        self.selected_resource_id = None
        self.selected_team_id = None
        self.resource_rows = []
        self.team_rows = []
        self.title("Resource Settings - Manage Resources & Teams")
        self.geometry(self.GEOMETRY)
        self.minsize(1050, 620)
        self.transient(master.winfo_toplevel())
        self.bind("<Escape>", lambda _event: self.destroy())
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill=tk.BOTH, expand=True, padx=14, pady=14)
        self.tab_resources = self.tabview.add("Resources")
        self.tab_teams = self.tabview.add("Teams")
        self._build_resources_tab()
        self._build_teams_tab()
        self._refresh_resources()
        self._refresh_teams()
        logger.info("Opened Resource Settings with %d resources and %d teams",
                    len(repo.resources), len(repo.teams))
        grab_when_visible(self)

    def _build_resources_tab(self):
        footer = self._footer(
            self.tab_resources, "Create New Resource",
            self._create_resource, self._edit_resource, self._delete_resource,
            "resource")
        self.resource_footer = footer
        filters = ctk.CTkFrame(self.tab_resources, fg_color="transparent")
        filters.pack(fill=tk.X, padx=6, pady=(6, 4))
        ctk.CTkLabel(filters, text="SEARCH & FILTER:").pack(side=tk.LEFT)
        self.resource_search = ctk.StringVar(value="")
        ctk.CTkEntry(filters, textvariable=self.resource_search,
                     placeholder_text="Search resource name or role...").pack(
                         side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        ctk.CTkLabel(filters, text="FILTER TYPE:").pack(side=tk.LEFT)
        self.resource_type_filter = ctk.CTkOptionMenu(
            filters, values=["All Types", "Named", "Generic"],
            command=lambda _value: self._refresh_resources(), width=120)
        self.resource_type_filter.set("All Types")
        self.resource_type_filter.pack(side=tk.LEFT, padx=(8, 0))
        self.resource_search.trace_add(
            "write", lambda *_args: self._refresh_resources())
        self.resource_grid = DataGrid(
            self.tab_resources, self.RESOURCE_COLUMNS,
            self._select_resource, border_width=1)
        self.resource_grid.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))

    def _build_teams_tab(self):
        footer = self._footer(
            self.tab_teams, "Create New Team", self._create_team,
            self._edit_team, self._delete_team, "team")
        self.team_footer = footer
        filters = ctk.CTkFrame(self.tab_teams, fg_color="transparent")
        filters.pack(fill=tk.X, padx=6, pady=(6, 4))
        ctk.CTkLabel(filters, text="SEARCH & FILTER:").pack(side=tk.LEFT)
        self.team_search = ctk.StringVar(value="")
        ctk.CTkEntry(filters, textvariable=self.team_search,
                     placeholder_text="Search team name...").pack(
                         side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        self.team_search.trace_add("write", lambda *_args: self._refresh_teams())
        self.team_grid = DataGrid(
            self.tab_teams, self.TEAM_COLUMNS, self._select_team,
            border_width=1)
        self.team_grid.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))

    def _footer(self, tab, create_text, create, edit, delete, prefix):
        footer = ctk.CTkFrame(tab)
        footer.pack(side=tk.BOTTOM, fill=tk.X, padx=6, pady=6)
        ctk.CTkButton(footer, text=create_text, command=create).pack(
            side=tk.LEFT, padx=6, pady=6)
        edit_button = ctk.CTkButton(
            footer, text="Edit Selected", command=edit, state="disabled")
        edit_button.pack(side=tk.LEFT, padx=6, pady=6)
        delete_button = ctk.CTkButton(
            footer, text="Delete Selected", command=delete, state="disabled")
        delete_button.pack(side=tk.LEFT, padx=6, pady=6)
        ctk.CTkButton(footer, text="Close", command=self.destroy).pack(
            side=tk.RIGHT, padx=6, pady=6)
        ctk.CTkButton(footer, text="Save Changes",
                      command=self._save_changes).pack(
                          side=tk.RIGHT, padx=6, pady=6)
        setattr(self, f"{prefix}_edit_button", edit_button)
        setattr(self, f"{prefix}_delete_button", delete_button)
        return footer

    def _save_changes(self):
        logger.info("Saving resource settings changes")
        if self.on_save:
            self.on_save()

    def _resource_days_off(self, resource):
        if not resource.days_off:
            return "None"
        return ", ".join(
            f"{item.start_date.isoformat()}–{item.end_date.isoformat()}"
            for item in resource.days_off)

    def _refresh_resources(self, select_id=None):
        self.resource_grid.clear()
        query = self.resource_search.get().strip().lower()
        type_filter = self.resource_type_filter.get()
        resources = []
        for resource in self.repo.resources.values():
            if query and query not in resource.name.lower() and query not in resource.role_type.lower():
                continue
            if type_filter == "Named" and resource.resource_type != ResourceType.NAMED:
                continue
            if type_filter == "Generic" and resource.resource_type != ResourceType.GENERIC:
                continue
            resources.append(resource)
        self.resource_rows = [item.id for item in resources]
        for index, resource in enumerate(resources, start=1):
            teams = ", ".join(self.repo.teams[team_id].name
                              for team_id in resource.team_memberships
                              if team_id in self.repo.teams) or "None"
            self.resource_grid.add_row(resource.id, (
                str(index),
                (f"[{resource.resource_type.value.upper()}]",
                 "#27ae60" if resource.resource_type == ResourceType.NAMED
                 else "#e67e22"),
                resource.name,
                resource.role_type, _schedule_short(resource.schedule_pattern),
                f"{resource.fte:.2f} FTE", teams,
                self._resource_days_off(resource)))
        self._select_resource(select_id if select_id in self.resource_rows else None)

    def _refresh_teams(self, select_id=None):
        self.team_grid.clear()
        query = self.team_search.get().strip().lower()
        teams = [team for team in self.repo.teams.values()
                 if not query or query in team.name.lower()]
        resources = list(self.repo.resources.values())
        self.team_rows = [item.id for item in teams]
        for index, team in enumerate(teams, start=1):
            daily = team.calculate_daily_capacity(resources)
            weekly = sum(daily.values())
            members = sum(resource.team_memberships.get(team.id, 0) > 0
                          for resource in resources)
            self.team_grid.add_row(team.id, (
                str(index), team.name, _schedule_short(team.schedule_pattern),
                "Fixed Capacity" if team.is_fixed_capacity else "Member-Calculated",
                f"{weekly / FTE_WEEKLY_HOURS:.2f} FTE ({weekly:g}h/wk)",
                f"{members} Member" + ("s" if members != 1 else ""),
                _daily_summary(daily)))
        self._select_team(select_id if select_id in self.team_rows else None)

    def _select_resource(self, resource_id):
        self.selected_resource_id = resource_id
        state = "normal" if resource_id else "disabled"
        self.resource_edit_button.configure(state=state)
        self.resource_delete_button.configure(state=state)
        if resource_id and self.resource_grid.selected_id != resource_id:
            self.resource_grid.select(resource_id, notify=False)

    def _select_team(self, team_id):
        self.selected_team_id = team_id
        state = "normal" if team_id else "disabled"
        self.team_edit_button.configure(state=state)
        self.team_delete_button.configure(state=state)
        if team_id and self.team_grid.selected_id != team_id:
            self.team_grid.select(team_id, notify=False)

    def _create_resource(self):
        self.resource_editor = ResourceEditorModal(
            self, self.repo, on_apply=self._resource_applied)

    def _edit_resource(self):
        if self.selected_resource_id:
            self.resource_editor = ResourceEditorModal(
                self, self.repo, self.repo.resources[self.selected_resource_id],
                self._resource_applied)

    def _resource_applied(self, resource_id):
        self._refresh_resources(resource_id)
        self._refresh_teams()

    def _delete_resource(self):
        if not self.selected_resource_id:
            return
        resource = self.repo.resources[self.selected_resource_id]
        if messagebox.askyesno("Delete Resource",
                               f"Delete {resource.name} from the resource pool?"):
            self.repo.remove_resource(resource.id)
            self._refresh_resources()
            self._refresh_teams()

    def _create_team(self):
        self.team_editor = TeamEditorModal(
            self, self.repo, on_apply=self._team_applied)

    def _edit_team(self):
        if self.selected_team_id:
            self.team_editor = TeamEditorModal(
                self, self.repo, self.repo.teams[self.selected_team_id],
                self._team_applied)

    def _team_applied(self, team_id):
        self._refresh_teams(team_id)
        self._refresh_resources()

    def _delete_team(self):
        if not self.selected_team_id:
            return
        team = self.repo.teams[self.selected_team_id]
        if messagebox.askyesno("Delete Team",
                               f"Delete {team.name} from the resource pool?"):
            self.repo.remove_team(team.id)
            self._refresh_teams()
            self._refresh_resources()
