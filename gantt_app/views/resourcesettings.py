import tkinter as tk
from typing import Dict, Optional

import customtkinter as ctk

from gantt_app.resource_model import (
    Resource, ResourceRepository, ResourceType, TeamPool,
)
from gantt_app.views import dialogs as messagebox
from gantt_app.views.modal import grab_when_visible


class ResourceSettingsWindow(ctk.CTkToplevel):
    GEOMETRY = "1050x720"

    def __init__(self, master, repo: ResourceRepository,
                 active_project_ids=None, **kwargs):
        super().__init__(master, **kwargs)
        self.repo = repo
        self.active_project_ids = list(active_project_ids or [])
        self.editing_resource_id: Optional[str] = None
        self.project_vars: Dict[str, ctk.BooleanVar] = {}

        self.title("Resource Settings - Manage Resources & Teams")
        self.geometry(self.GEOMETRY)
        self.minsize(900, 600)
        self.transient(master.winfo_toplevel())
        self.bind("<Escape>", lambda _event: self.destroy())

        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        self.tab_resources = self.tabview.add("Resources")
        self.tab_teams = self.tabview.add("Teams")
        self._setup_resources_tab()
        self._setup_teams_tab()
        grab_when_visible(self)

    def _setup_resources_tab(self):
        form = ctk.CTkScrollableFrame(self.tab_resources, width=320)
        form.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)
        ctk.CTkLabel(form, text="Resource Details",
                     font=("Arial", 16, "bold")).pack(pady=10)

        self.entry_name = ctk.CTkEntry(form, placeholder_text="Resource name")
        self.entry_name.pack(fill=tk.X, padx=10, pady=5)
        self.combo_type = ctk.CTkComboBox(
            form, values=["Named (Person)", "Generic (Role Placeholder)"],
            state="readonly")
        self.combo_type.set("Named (Person)")
        self.combo_type.pack(fill=tk.X, padx=10, pady=5)
        self.entry_role = ctk.CTkEntry(form, placeholder_text="Role or skill")
        self.entry_role.pack(fill=tk.X, padx=10, pady=5)
        self.entry_capacity = ctk.CTkEntry(
            form, placeholder_text="Weekly capacity (hours)")
        self.entry_capacity.insert(0, "40")
        self.entry_capacity.pack(fill=tk.X, padx=10, pady=5)
        self.entry_cost = ctk.CTkEntry(form, placeholder_text="Hourly cost")
        self.entry_cost.insert(0, "0")
        self.entry_cost.pack(fill=tk.X, padx=10, pady=5)

        ctk.CTkLabel(form, text="Available to projects",
                     font=("Arial", 12, "bold")).pack(
                         anchor=tk.W, padx=10, pady=(12, 2))
        if not self.active_project_ids:
            ctk.CTkLabel(form, text="No active projects").pack(
                anchor=tk.W, padx=15, pady=2)
        for project_id in self.active_project_ids:
            variable = ctk.BooleanVar(value=False)
            ctk.CTkCheckBox(form, text=project_id, variable=variable).pack(
                anchor=tk.W, padx=15, pady=2)
            self.project_vars[project_id] = variable

        self.resource_problem = ctk.CTkLabel(form, text="", text_color="#c0392b",
                                             wraplength=280)
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

    def _save_resource(self):
        name = self.entry_name.get().strip()
        if not name:
            self.resource_problem.configure(text="Enter a resource name.")
            return
        try:
            capacity = self._number(self.entry_capacity, "Weekly capacity", 40)
            cost = self._number(self.entry_cost, "Hourly cost", 0)
        except ValueError as error:
            self.resource_problem.configure(text=str(error))
            return

        resource_type = (ResourceType.NAMED if self.combo_type.get().startswith("Named")
                         else ResourceType.GENERIC)
        project_ids = [project_id for project_id, variable
                       in self.project_vars.items() if variable.get()]
        if self.editing_resource_id:
            resource = self.repo.resources[self.editing_resource_id]
            project_ids = [
                project_id for project_id in resource.assigned_project_ids
                if project_id not in self.project_vars
            ] + project_ids
            resource.name = name
            resource.resource_type = resource_type
            resource.role_type = self.entry_role.get().strip() or "General"
            resource.weekly_capacity_hours = capacity
            resource.cost_per_hour = cost
            resource.assigned_project_ids = project_ids
        else:
            resource = Resource(
                id=self.repo.new_id("res"), name=name,
                resource_type=resource_type,
                role_type=self.entry_role.get().strip() or "General",
                weekly_capacity_hours=capacity, cost_per_hour=cost,
                assigned_project_ids=project_ids)
            self.repo.add_resource(resource)
        self._clear_form()
        self._refresh_resource_list()
        self._refresh_team_list()

    def _edit_resource(self, resource_id: str):
        resource = self.repo.resources[resource_id]
        self.editing_resource_id = resource_id
        self.entry_name.delete(0, tk.END)
        self.entry_name.insert(0, resource.name)
        self.combo_type.set("Named (Person)" if resource.resource_type == ResourceType.NAMED
                            else "Generic (Role Placeholder)")
        self.entry_role.delete(0, tk.END)
        self.entry_role.insert(0, resource.role_type)
        self.entry_capacity.delete(0, tk.END)
        self.entry_capacity.insert(0, str(resource.weekly_capacity_hours))
        self.entry_cost.delete(0, tk.END)
        self.entry_cost.insert(0, str(resource.cost_per_hour))
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
            ctk.CTkLabel(card, text=f"[{tag}]", text_color=color,
                         font=("Arial", 11, "bold")).pack(
                             side=tk.LEFT, padx=8)
            projects = ", ".join(resource.assigned_project_ids) or "None"
            text = (f"{resource.name} | {resource.role_type} | "
                    f"{resource.weekly_capacity_hours:g}h/week | Projects: {projects}")
            ctk.CTkLabel(card, text=text, anchor=tk.W).pack(
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
                selector = ctk.CTkComboBox(card, values=list(choices), width=130,
                    command=lambda name, gid=resource.id, ids=choices:
                        self._swap_generic(gid, ids[name]), state="readonly")
                selector.set("Swap with...")
                selector.pack(side=tk.RIGHT, padx=2, pady=5)

    def _clear_form(self):
        self.editing_resource_id = None
        for entry in (self.entry_name, self.entry_role, self.entry_capacity,
                      self.entry_cost):
            entry.delete(0, tk.END)
        self.entry_capacity.insert(0, "40")
        self.entry_cost.insert(0, "0")
        self.combo_type.set("Named (Person)")
        for variable in self.project_vars.values():
            variable.set(False)
        self.save_resource_button.configure(text="Add Resource")
        self.resource_problem.configure(text="")

    def _setup_teams_tab(self):
        form = ctk.CTkFrame(self.tab_teams, width=320)
        form.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)
        ctk.CTkLabel(form, text="Create Team Pool",
                     font=("Arial", 16, "bold")).pack(pady=10)
        self.entry_team_name = ctk.CTkEntry(form, placeholder_text="Team name")
        self.entry_team_name.pack(fill=tk.X, padx=10, pady=5)
        self.team_problem = ctk.CTkLabel(form, text="", text_color="#c0392b",
                                         wraplength=280)
        self.team_problem.pack(fill=tk.X, padx=10, pady=(8, 0))
        ctk.CTkButton(form, text="Create Team", command=self._add_team).pack(
            fill=tk.X, padx=10, pady=(8, 15))

        self.team_list_frame = ctk.CTkScrollableFrame(self.tab_teams)
        self.team_list_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True,
                                  padx=10, pady=10)
        self._refresh_team_list()

    def _add_team(self):
        name = self.entry_team_name.get().strip()
        if not name:
            self.team_problem.configure(text="Enter a team name.")
            return
        self.repo.add_team(TeamPool(id=self.repo.new_id("team"), name=name))
        self.entry_team_name.delete(0, tk.END)
        self.team_problem.configure(text="")
        self._refresh_team_list()

    def _save_team(self, team_id: str, fixed_var, fixed_entry,
                   allocation_entries):
        team = self.repo.teams[team_id]
        try:
            fixed_hours = self._number(fixed_entry, "Fixed capacity", 0)
            allocations = {
                resource_id: self._number(entry, "Allocation percentage", 0)
                for resource_id, entry in allocation_entries.items()
            }
            if any(value > 100 for value in allocations.values()):
                raise ValueError("Allocation percentage cannot exceed 100.")
        except ValueError as error:
            self.team_problem.configure(text=str(error))
            return
        team.is_fixed_capacity = bool(fixed_var.get())
        team.fixed_hours = fixed_hours
        for resource_id, percentage in allocations.items():
            self.repo.set_team_allocation(resource_id, team_id, percentage)
        self.team_problem.configure(text="")
        self._refresh_team_list()

    def _delete_team(self, team_id: str):
        if not messagebox.askyesno("Delete Team", "Delete this team pool?"):
            return
        self.repo.remove_team(team_id)
        self._refresh_team_list()

    def _refresh_team_list(self):
        for widget in self.team_list_frame.winfo_children():
            widget.destroy()
        resources = list(self.repo.resources.values())
        for team in self.repo.teams.values():
            card = ctk.CTkFrame(self.team_list_frame)
            card.pack(fill=tk.X, pady=8, padx=5)
            heading = ctk.CTkFrame(card, fg_color="transparent")
            heading.pack(fill=tk.X, padx=10, pady=(8, 2))
            ctk.CTkLabel(heading, text=team.name,
                         font=("Arial", 14, "bold")).pack(side=tk.LEFT)
            capacity = team.calculate_effective_capacity(resources)
            ctk.CTkLabel(heading, text=f"{capacity:g} hours/week").pack(
                side=tk.RIGHT)

            fixed_var = ctk.BooleanVar(value=team.is_fixed_capacity)
            ctk.CTkSwitch(card, text="Fixed capacity", variable=fixed_var).pack(
                anchor=tk.W, padx=10, pady=3)
            fixed_entry = ctk.CTkEntry(card, width=110,
                                       placeholder_text="Fixed hours")
            fixed_entry.insert(0, str(team.fixed_hours))
            fixed_entry.pack(anchor=tk.W, padx=10, pady=3)

            entries = {}
            for resource in resources:
                row = ctk.CTkFrame(card, fg_color="transparent")
                row.pack(fill=tk.X, padx=10, pady=2)
                ctk.CTkLabel(row, text=resource.name, anchor=tk.W).pack(
                    side=tk.LEFT, fill=tk.X, expand=True)
                entry = ctk.CTkEntry(row, width=70, placeholder_text="%")
                entry.insert(0, str(resource.team_memberships.get(team.id, 0) * 100))
                entry.pack(side=tk.RIGHT)
                entries[resource.id] = entry
            actions = ctk.CTkFrame(card, fg_color="transparent")
            actions.pack(fill=tk.X, padx=10, pady=(5, 8))
            ctk.CTkButton(actions, text="Save", width=70,
                          command=lambda tid=team.id, fv=fixed_var, fe=fixed_entry,
                          values=entries: self._save_team(tid, fv, fe, values)).pack(
                              side=tk.RIGHT, padx=2)
            ctk.CTkButton(actions, text="Delete", width=70,
                          command=lambda tid=team.id: self._delete_team(tid)).pack(
                              side=tk.RIGHT, padx=2)
