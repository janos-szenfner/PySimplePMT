import tkinter as tk
from typing import Dict, Optional

import customtkinter as ctk

from gantt_app.resource_model import (
    DAYS, DAY_LABELS, FTE_WEEKLY_HOURS, Resource, ResourceRepository,
    ResourceType, SchedulePattern, TeamPool, capacity_from_entry,
    default_daily_capacity,
)
from gantt_app.utils.log import get_logger
from gantt_app.views import dialogs as messagebox
from gantt_app.views.modal import grab_when_visible


logger = get_logger(__name__)
CAPACITY_UNITS = ("FTE", "Daily Hours", "Weekly Hours")


class ResourceSettingsWindow(ctk.CTkToplevel):
    GEOMETRY = "1250x780"

    def __init__(self, master, repo: ResourceRepository,
                 active_project_ids=None, **kwargs):
        super().__init__(master, **kwargs)
        self.repo = repo
        self.active_project_ids = list(active_project_ids or [])
        self.editing_resource_id: Optional[str] = None
        self.editing_team_id: Optional[str] = None
        self.editing_resource_team_id: Optional[str] = None
        self.project_vars: Dict[str, ctk.BooleanVar] = {}
        self._updating_capacity = False

        self.title("Resource Settings - Manage Resources & Teams")
        self.geometry(self.GEOMETRY)
        self.minsize(1050, 650)
        self.transient(master.winfo_toplevel())
        self.bind("<Escape>", lambda _event: self.destroy())

        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        self.tab_resources = self.tabview.add("Resources")
        self.tab_teams = self.tabview.add("Teams")
        self._setup_resources_tab()
        self._setup_teams_tab()
        logger.info("Opened Resource Settings with %d resources and %d teams",
                    len(repo.resources), len(repo.teams))
        grab_when_visible(self)

    @staticmethod
    def _label(parent, text):
        ctk.CTkLabel(parent, text=text, anchor=tk.W,
                     font=("Arial", 11, "bold")).pack(
                         fill=tk.X, padx=10, pady=(8, 1))

    def _setup_resources_tab(self):
        form = ctk.CTkScrollableFrame(self.tab_resources, width=365)
        form.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)
        ctk.CTkLabel(form, text="Resource Details",
                     font=("Arial", 16, "bold")).pack(pady=10)

        self._label(form, "Resource Name")
        self.entry_name = ctk.CTkEntry(form)
        self.entry_name.pack(fill=tk.X, padx=10)
        self._label(form, "Resource Type")
        self.combo_type = ctk.CTkComboBox(
            form, values=["Named (Person)", "Generic (Role Placeholder)"],
            state="readonly")
        self.combo_type.set("Named (Person)")
        self.combo_type.pack(fill=tk.X, padx=10)
        self._label(form, "Role / Skill Tag")
        self.entry_role = ctk.CTkEntry(form)
        self.entry_role.pack(fill=tk.X, padx=10)

        self._label(form, "Work Schedule Pattern")
        self.combo_schedule = ctk.CTkOptionMenu(
            form, values=[pattern.value for pattern in SchedulePattern],
            command=self._schedule_changed)
        self.combo_schedule.set(SchedulePattern.STANDARD.value)
        self.combo_schedule.pack(fill=tk.X, padx=10)

        self._label(form, "Capacity Entry & Units")
        capacity_row = ctk.CTkFrame(form, fg_color="transparent")
        capacity_row.pack(fill=tk.X, padx=10)
        self.combo_capacity_unit = ctk.CTkSegmentedButton(
            capacity_row, values=list(CAPACITY_UNITS),
            command=self._capacity_unit_changed)
        self.combo_capacity_unit.set("Weekly Hours")
        self.combo_capacity_unit.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry_capacity = ctk.CTkEntry(capacity_row, width=75)
        self.entry_capacity.insert(0, "40")
        self.entry_capacity.pack(side=tk.RIGHT, padx=(6, 0))
        self.entry_capacity.bind("<FocusOut>", self._capacity_entry_changed)
        self.entry_capacity.bind("<Return>", self._capacity_entry_changed)

        self._label(form, "Day-by-Day Capacity Breakdown Grid")
        day_row = ctk.CTkFrame(form, fg_color="transparent")
        day_row.pack(fill=tk.X, padx=10)
        self.daily_entries = {}
        for column, (day, label) in enumerate(zip(DAYS, DAY_LABELS)):
            cell = ctk.CTkFrame(day_row, fg_color="transparent")
            cell.grid(row=0, column=column, padx=2, sticky="ew")
            day_row.grid_columnconfigure(column, weight=1)
            ctk.CTkLabel(cell, text=label).pack()
            entry = ctk.CTkEntry(cell, width=42)
            entry.pack()
            entry.bind("<FocusOut>", self._daily_grid_changed)
            entry.bind("<Return>", self._daily_grid_changed)
            self.daily_entries[day] = entry
        self.capacity_summary = ctk.CTkLabel(form, text="")
        self.capacity_summary.pack(fill=tk.X, padx=10, pady=(2, 0))
        self._set_daily_entries(default_daily_capacity(SchedulePattern.STANDARD))

        self._label(form, "Hourly Billing Rate ($)")
        self.entry_cost = ctk.CTkEntry(form)
        self.entry_cost.insert(0, "0")
        self.entry_cost.pack(fill=tk.X, padx=10)
        self._label(form, "Assign to Team")
        self.combo_team = ctk.CTkOptionMenu(form, values=["None"])
        self.combo_team.set("None")
        self.combo_team.pack(fill=tk.X, padx=10)

        self._label(form, "Project Availability")
        project_frame = ctk.CTkScrollableFrame(form, height=80)
        project_frame.pack(fill=tk.X, padx=10)
        if not self.active_project_ids:
            ctk.CTkLabel(project_frame, text="No active projects").pack(anchor=tk.W)
        for project_id in self.active_project_ids:
            variable = ctk.BooleanVar(value=False)
            ctk.CTkCheckBox(project_frame, text=project_id,
                            variable=variable).pack(anchor=tk.W, pady=2)
            self.project_vars[project_id] = variable

        self.resource_problem = ctk.CTkLabel(form, text="", text_color="#c0392b",
                                             wraplength=330)
        self.resource_problem.pack(fill=tk.X, padx=10, pady=(8, 0))
        self.save_resource_button = ctk.CTkButton(
            form, text="Add Resource", command=self._save_resource)
        self.save_resource_button.pack(fill=tk.X, padx=10, pady=(8, 4))
        ctk.CTkButton(form, text="Clear", command=self._clear_form).pack(
            fill=tk.X, padx=10, pady=(0, 12))

        self.list_frame = ctk.CTkScrollableFrame(self.tab_resources)
        self.list_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True,
                             padx=10, pady=10)
        self._refresh_resource_list()

    def _number(self, entry, label: str, default: float) -> float:
        text = entry.get().strip()
        try:
            value = float(text) if text else default
        except ValueError as error:
            raise ValueError(f"{label} must be a number.") from error
        if value < 0:
            raise ValueError(f"{label} cannot be negative.")
        return value

    def _daily_values(self):
        values = {}
        for day, entry in self.daily_entries.items():
            value = self._number(entry, f"{day.title()} capacity", 0)
            if value > 24:
                raise ValueError("Daily capacity cannot exceed 24 hours.")
            values[day] = value
        return values

    def _set_daily_entries(self, values):
        self._updating_capacity = True
        for day, entry in self.daily_entries.items():
            entry.delete(0, tk.END)
            entry.insert(0, f"{values.get(day, 0):g}")
        self._updating_capacity = False
        self._update_capacity_summary(values)

    def _update_capacity_summary(self, values):
        weekly = sum(values.values())
        self.capacity_summary.configure(
            text=f"{weekly:g} hours/week | {weekly / FTE_WEEKLY_HOURS:.2f} FTE")

    def _schedule_changed(self, value):
        pattern = SchedulePattern.read(value)
        values = default_daily_capacity(pattern)
        self._set_daily_entries(values)
        self._set_capacity_entry(sum(values.values()))

    def _set_capacity_entry(self, weekly):
        unit = self.combo_capacity_unit.get()
        active = len([entry for entry in self.daily_entries.values()
                      if self._number(entry, "Daily capacity", 0) > 0]) or 1
        value = (weekly / FTE_WEEKLY_HOURS if unit == "FTE"
                 else weekly / active if unit == "Daily Hours" else weekly)
        self.entry_capacity.delete(0, tk.END)
        self.entry_capacity.insert(0, f"{value:.2f}".rstrip("0").rstrip("."))

    def _capacity_unit_changed(self, _value=None):
        try:
            self._set_capacity_entry(sum(self._daily_values().values()))
        except ValueError as error:
            self.resource_problem.configure(text=str(error))

    def _capacity_entry_changed(self, _event=None):
        try:
            value = self._number(self.entry_capacity, "Capacity", 0)
            pattern = SchedulePattern.read(self.combo_schedule.get())
            if pattern == SchedulePattern.CUSTOM:
                current = self._daily_values()
                active = len([hours for hours in current.values() if hours]) or 7
                target = (value * FTE_WEEKLY_HOURS
                          if self.combo_capacity_unit.get() == "FTE"
                          else value * active
                          if self.combo_capacity_unit.get() == "Daily Hours"
                          else value)
                total = sum(current.values())
                values = ({day: hours * target / total
                           for day, hours in current.items()} if total else
                          dict.fromkeys(DAYS, target / 7))
            else:
                values = capacity_from_entry(
                    pattern, value, self.combo_capacity_unit.get())
            self._set_daily_entries(values)
        except ValueError as error:
            self.resource_problem.configure(text=str(error))

    def _daily_grid_changed(self, _event=None):
        if self._updating_capacity:
            return
        try:
            values = self._daily_values()
        except ValueError as error:
            self.resource_problem.configure(text=str(error))
            return
        self.combo_schedule.set(SchedulePattern.CUSTOM.value)
        self._update_capacity_summary(values)
        self._set_capacity_entry(sum(values.values()))

    def _save_resource(self):
        resource_type = (ResourceType.NAMED if self.combo_type.get().startswith("Named")
                         else ResourceType.GENERIC)
        role = self.entry_role.get().strip() or "General"
        name = self.entry_name.get().strip()
        if not name and resource_type == ResourceType.GENERIC:
            name = self.repo.next_placeholder_name(role)
        if not name:
            self.resource_problem.configure(
                text="Resource Name is required for a named person.")
            return
        try:
            daily = self._daily_values()
            cost = self._number(self.entry_cost, "Hourly billing rate", 0)
        except ValueError as error:
            self.resource_problem.configure(text=str(error))
            return

        project_ids = [project_id for project_id, variable
                       in self.project_vars.items() if variable.get()]
        selected_team = self._team_id_for_name(self.combo_team.get())
        if self.editing_resource_id:
            resource = self.repo.resources[self.editing_resource_id]
            project_ids = [project_id for project_id in resource.assigned_project_ids
                           if project_id not in self.project_vars] + project_ids
            resource.name = name
            resource.resource_type = resource_type
            resource.role_type = role
            resource.schedule_pattern = SchedulePattern.read(
                self.combo_schedule.get())
            resource.set_daily_capacity(daily, preserve_pattern=True)
            resource.cost_per_hour = cost
            resource.assigned_project_ids = project_ids
            logger.info("Updated resource %r (%s)", resource.name, resource.id)
        else:
            resource = Resource(
                id=self.repo.new_id("res"), name=name,
                resource_type=resource_type, role_type=role,
                cost_per_hour=cost, assigned_project_ids=project_ids,
                schedule_pattern=SchedulePattern.read(self.combo_schedule.get()),
                daily_capacity_hours=daily)
            self.repo.add_resource(resource)
        if (not self.editing_resource_id
                or selected_team != self.editing_resource_team_id):
            for team_id in list(resource.team_memberships):
                self.repo.set_team_allocation(resource.id, team_id, 0)
            if selected_team:
                self.repo.set_team_allocation(resource.id, selected_team, 100)
        self._clear_form()
        self._refresh_resource_list()
        self._refresh_team_list()

    def _team_id_for_name(self, name):
        return next((team.id for team in self.repo.teams.values()
                     if team.name == name), None)

    def _edit_resource(self, resource_id: str):
        resource = self.repo.resources[resource_id]
        self.editing_resource_id = resource_id
        self.entry_name.delete(0, tk.END)
        self.entry_name.insert(0, resource.name)
        self.combo_type.set("Named (Person)" if resource.resource_type == ResourceType.NAMED
                            else "Generic (Role Placeholder)")
        self.entry_role.delete(0, tk.END)
        self.entry_role.insert(0, resource.role_type)
        self.combo_schedule.set(resource.schedule_pattern.value)
        self._set_daily_entries(resource.daily_capacity_hours)
        self._set_capacity_entry(resource.weekly_capacity_hours)
        self.entry_cost.delete(0, tk.END)
        self.entry_cost.insert(0, str(resource.cost_per_hour))
        team_id = next(iter(resource.team_memberships), None)
        self.editing_resource_team_id = team_id
        self.combo_team.set(self.repo.teams[team_id].name
                            if team_id in self.repo.teams else "None")
        for project_id, variable in self.project_vars.items():
            variable.set(project_id in resource.assigned_project_ids)
        self.save_resource_button.configure(text="Update Resource")
        self.resource_problem.configure(text="")

    def _delete_resource(self, resource_id: str):
        if not messagebox.askyesno("Delete Resource",
                                   "Delete this resource from the project pool?"):
            return
        self.repo.remove_resource(resource_id)
        self._refresh_resource_list()
        self._refresh_team_list()

    def _swap_generic(self, generic_id: str, named_id: str):
        self.repo.swap_generic(generic_id, named_id)
        self._refresh_resource_list()
        self._refresh_team_list()

    def _refresh_resource_list(self):
        for widget in self.list_frame.winfo_children():
            widget.destroy()
        for resource in self.repo.resources.values():
            card = ctk.CTkFrame(self.list_frame)
            card.pack(fill=tk.X, pady=5, padx=5)
            tag = resource.resource_type.value.upper()
            color = "#27ae60" if resource.resource_type == ResourceType.NAMED else "#e67e22"
            teams = ", ".join(self.repo.teams[team_id].name
                              for team_id in resource.team_memberships
                              if team_id in self.repo.teams) or "None"
            projects = ", ".join(resource.assigned_project_ids) or "None"
            active_hours = resource.average_active_day_hours
            schedule = (f"{resource.schedule_pattern.value} | "
                        f"{active_hours:.2f}h/active day | "
                        f"{resource.weekly_capacity_hours:g}h/week")
            ctk.CTkLabel(card, text=f"[{tag}]", text_color=color,
                         font=("Arial", 11, "bold")).pack(side=tk.LEFT, padx=8)
            text = (f"{resource.name} | {resource.role_type}\n[{schedule}] | "
                    f"Team: {teams} | Projects: {projects} | "
                    "Workload: No assignments")
            ctk.CTkLabel(card, text=text, anchor=tk.W, justify=tk.LEFT).pack(
                side=tk.LEFT, fill=tk.X, expand=True, padx=5)
            ctk.CTkButton(card, text="Delete", width=58,
                          command=lambda rid=resource.id: self._delete_resource(rid)).pack(
                              side=tk.RIGHT, padx=(2, 8), pady=5)
            ctk.CTkButton(card, text="Edit", width=48,
                          command=lambda rid=resource.id: self._edit_resource(rid)).pack(
                              side=tk.RIGHT, padx=2, pady=5)
            replacements = self.repo.named_resources(excluding=resource.id)
            if resource.resource_type == ResourceType.GENERIC and replacements:
                choices = {item.name: item.id for item in replacements}
                selector = ctk.CTkComboBox(
                    card, values=list(choices), width=130,
                    command=lambda name, gid=resource.id, ids=choices:
                        self._swap_generic(gid, ids[name]), state="readonly")
                selector.set("Swap with...")
                selector.pack(side=tk.RIGHT, padx=2, pady=5)

    def _clear_form(self):
        self.editing_resource_id = None
        self.editing_resource_team_id = None
        for entry in (self.entry_name, self.entry_role, self.entry_cost):
            entry.delete(0, tk.END)
        self.entry_cost.insert(0, "0")
        self.combo_type.set("Named (Person)")
        self.combo_schedule.set(SchedulePattern.STANDARD.value)
        self.combo_capacity_unit.set("Weekly Hours")
        self._set_daily_entries(default_daily_capacity(SchedulePattern.STANDARD))
        self._set_capacity_entry(40)
        self.combo_team.configure(values=["None"] + [team.name
                                  for team in self.repo.teams.values()])
        self.combo_team.set("None")
        for variable in self.project_vars.values():
            variable.set(False)
        self.save_resource_button.configure(text="Add Resource")
        self.resource_problem.configure(text="")

    def _setup_teams_tab(self):
        form = ctk.CTkScrollableFrame(self.tab_teams, width=365)
        form.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)
        ctk.CTkLabel(form, text="Team Pool Details",
                     font=("Arial", 16, "bold")).pack(pady=10)
        self._label(form, "Team Name")
        self.entry_team_name = ctk.CTkEntry(form)
        self.entry_team_name.pack(fill=tk.X, padx=10)
        self._label(form, "Team Schedule Pattern")
        self.combo_team_schedule = ctk.CTkOptionMenu(
            form, values=[pattern.value for pattern in SchedulePattern])
        self.combo_team_schedule.set(SchedulePattern.STANDARD.value)
        self.combo_team_schedule.pack(fill=tk.X, padx=10)
        self._label(form, "Capacity Calculation Mode")
        self.team_capacity_mode = ctk.StringVar(value="Calculated from Assigned Members")
        for value in ("Calculated from Assigned Members", "Fixed Team Capacity"):
            ctk.CTkRadioButton(form, text=value, value=value,
                               variable=self.team_capacity_mode,
                               command=self._team_mode_changed).pack(
                                   anchor=tk.W, padx=15, pady=3)
        self._label(form, "Fixed Daily/Weekly Capacity (Fixed Mode Only)")
        fixed_row = ctk.CTkFrame(form, fg_color="transparent")
        fixed_row.pack(fill=tk.X, padx=10)
        self.entry_team_fixed_daily = ctk.CTkEntry(
            fixed_row, placeholder_text="Daily hours")
        self.entry_team_fixed_daily.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry_team_fixed_weekly = ctk.CTkEntry(
            fixed_row, placeholder_text="Weekly hours")
        self.entry_team_fixed_weekly.pack(side=tk.RIGHT, fill=tk.X,
                                          expand=True, padx=(6, 0))
        self.team_problem = ctk.CTkLabel(form, text="", text_color="#c0392b",
                                         wraplength=330)
        self.team_problem.pack(fill=tk.X, padx=10, pady=(8, 0))
        self.save_team_button = ctk.CTkButton(
            form, text="Create Team", command=self._save_team_form)
        self.save_team_button.pack(fill=tk.X, padx=10, pady=(8, 4))
        ctk.CTkButton(form, text="Clear", command=self._clear_team_form).pack(
            fill=tk.X, padx=10, pady=(0, 12))
        self._team_mode_changed()

        self.team_list_frame = ctk.CTkScrollableFrame(self.tab_teams)
        self.team_list_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True,
                                  padx=10, pady=10)
        self._refresh_team_list()

    def _team_mode_changed(self):
        state = ("normal" if self.team_capacity_mode.get() == "Fixed Team Capacity"
                 else "disabled")
        self.entry_team_fixed_daily.configure(state=state)
        self.entry_team_fixed_weekly.configure(state=state)

    def _save_team_form(self):
        name = self.entry_team_name.get().strip()
        if not name:
            self.team_problem.configure(text="Enter a team name.")
            return
        fixed = self.team_capacity_mode.get() == "Fixed Team Capacity"
        pattern = SchedulePattern.read(self.combo_team_schedule.get())
        try:
            daily = self._number(self.entry_team_fixed_daily,
                                 "Fixed daily capacity", 0)
            weekly = self._number(self.entry_team_fixed_weekly,
                                  "Fixed weekly capacity", 0)
        except ValueError as error:
            self.team_problem.configure(text=str(error))
            return
        fixed_daily = (capacity_from_entry(pattern, daily, "Daily Hours")
                       if daily else capacity_from_entry(
                           pattern, weekly, "Weekly Hours"))
        if self.editing_team_id:
            team = self.repo.teams[self.editing_team_id]
            team.name = name
            team.schedule_pattern = pattern
            team.is_fixed_capacity = fixed
            team.fixed_daily_hours = fixed_daily
            team.fixed_hours = sum(fixed_daily.values())
            logger.info("Updated resource team %r (%s)", team.name, team.id)
        else:
            self.repo.add_team(TeamPool(
                id=self.repo.new_id("team"), name=name,
                schedule_pattern=pattern, is_fixed_capacity=fixed,
                fixed_daily_hours=fixed_daily))
        self._clear_team_form()
        self._refresh_team_list()
        self._clear_form()

    def _edit_team(self, team_id):
        team = self.repo.teams[team_id]
        self.editing_team_id = team_id
        self.entry_team_name.delete(0, tk.END)
        self.entry_team_name.insert(0, team.name)
        self.combo_team_schedule.set(team.schedule_pattern.value)
        self.team_capacity_mode.set("Fixed Team Capacity" if team.is_fixed_capacity
                                    else "Calculated from Assigned Members")
        self._team_mode_changed()
        active = [value for value in team.fixed_daily_hours.values() if value]
        daily = active[0] if active and len(set(active)) == 1 else 0
        self.entry_team_fixed_daily.configure(state="normal")
        self.entry_team_fixed_daily.delete(0, tk.END)
        self.entry_team_fixed_daily.insert(0, f"{daily:g}")
        self.entry_team_fixed_weekly.configure(state="normal")
        self.entry_team_fixed_weekly.delete(0, tk.END)
        self.entry_team_fixed_weekly.insert(0, f"{team.fixed_hours:g}")
        self._team_mode_changed()
        self.save_team_button.configure(text="Update Team")

    def _clear_team_form(self):
        self.editing_team_id = None
        self.entry_team_name.delete(0, tk.END)
        self.combo_team_schedule.set(SchedulePattern.STANDARD.value)
        self.team_capacity_mode.set("Calculated from Assigned Members")
        for entry in (self.entry_team_fixed_daily, self.entry_team_fixed_weekly):
            entry.configure(state="normal")
            entry.delete(0, tk.END)
        self._team_mode_changed()
        self.save_team_button.configure(text="Create Team")
        self.team_problem.configure(text="")

    def _save_allocations(self, team_id, entries):
        try:
            allocations = {resource_id: self._number(
                entry, "Team split percentage", 0)
                for resource_id, entry in entries.items()}
            if any(value > 100 for value in allocations.values()):
                raise ValueError("Team split percentage cannot exceed 100.")
        except ValueError as error:
            self.team_problem.configure(text=str(error))
            return
        for resource_id, percentage in allocations.items():
            self.repo.set_team_allocation(resource_id, team_id, percentage)
        self.team_problem.configure(text="")
        self._refresh_team_list()
        self._refresh_resource_list()

    def _delete_team(self, team_id: str):
        if not messagebox.askyesno("Delete Team", "Delete this team pool?"):
            return
        self.repo.remove_team(team_id)
        self._refresh_team_list()
        self._clear_form()

    def _refresh_team_list(self):
        for widget in self.team_list_frame.winfo_children():
            widget.destroy()
        resources = list(self.repo.resources.values())
        for team in self.repo.teams.values():
            card = ctk.CTkFrame(self.team_list_frame)
            card.pack(fill=tk.X, pady=8, padx=5)
            daily = team.calculate_daily_capacity(resources)
            heading = ctk.CTkFrame(card, fg_color="transparent")
            heading.pack(fill=tk.X, padx=10, pady=(8, 2))
            ctk.CTkLabel(
                heading,
                text=(f"{team.name} | {team.schedule_pattern.value}\n"
                      f"Daily: " + " | ".join(
                          f"{label} {daily[day]:g}h"
                          for day, label in zip(DAYS, DAY_LABELS)) +
                      f"\nWeekly: {sum(daily.values()):g}h | "
                      f"{sum(daily.values()) / FTE_WEEKLY_HOURS:.2f} FTE"),
                font=("Arial", 13, "bold"), justify=tk.LEFT,
                anchor=tk.W).pack(side=tk.LEFT, fill=tk.X, expand=True)
            ctk.CTkButton(heading, text="Delete", width=58,
                          command=lambda tid=team.id: self._delete_team(tid)).pack(
                              side=tk.RIGHT, padx=2)
            ctk.CTkButton(heading, text="Edit", width=48,
                          command=lambda tid=team.id: self._edit_team(tid)).pack(
                              side=tk.RIGHT, padx=2)

            headers = ("Member", "Schedule", "Daily Capacity", "Split %",
                       "Contributed Daily", "Contributed Weekly")
            table = ctk.CTkFrame(card, fg_color="transparent")
            table.pack(fill=tk.X, padx=10, pady=(5, 8))
            for column, header in enumerate(headers):
                table.grid_columnconfigure(column, weight=1)
                ctk.CTkLabel(table, text=header,
                             font=("Arial", 10, "bold")).grid(
                                 row=0, column=column, padx=3, sticky="w")
            entries = {}
            for row, resource in enumerate(resources, start=1):
                contribution = team.member_contribution(resource)
                ctk.CTkLabel(table, text=resource.name).grid(
                    row=row, column=0, padx=3, sticky="w")
                ctk.CTkLabel(table, text=resource.schedule_pattern.value).grid(
                    row=row, column=1, padx=3, sticky="w")
                ctk.CTkLabel(table, text="/".join(
                    f"{resource.daily_capacity_hours[day]:g}"
                    for day in DAYS)).grid(row=row, column=2, padx=3, sticky="w")
                entry = ctk.CTkEntry(table, width=55)
                entry.insert(0, f"{resource.team_memberships.get(team.id, 0) * 100:g}")
                entry.grid(row=row, column=3, padx=3)
                entries[resource.id] = entry
                ctk.CTkLabel(table, text="/".join(
                    f"{contribution[day]:g}" for day in DAYS)).grid(
                        row=row, column=4, padx=3, sticky="w")
                ctk.CTkLabel(table, text=f"{sum(contribution.values()):g}h").grid(
                    row=row, column=5, padx=3, sticky="w")
            ctk.CTkButton(
                card, text="Save Member Splits", width=130,
                command=lambda tid=team.id, values=entries:
                    self._save_allocations(tid, values)).pack(
                        anchor=tk.E, padx=10, pady=(0, 8))
