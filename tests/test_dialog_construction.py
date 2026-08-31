"""
Tests that actually build the dialogs and the main widgets.

DEVELOPMENT NOTES:
------------------
The rest of the dialog tests deliberately avoid constructing widgets, reading
methods and menu definitions instead so they run without a display. That left
the constructors themselves untested, and a leftover reference to a name the
old checkbox-based dependency UI defined survived in CreateTaskDialog._create_form
long after that UI was replaced by the Dependency tab. Every attempt to create a
task, sub-task or milestone raised NameError partway through building the form,
so the dialog appeared without its Save and Cancel buttons.

Nothing short of building the widget catches that, so these do. CI runs the
suite under xvfb, and the whole module skips when no display is available so a
developer without one still gets a clean run.
"""

import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace

from gantt_app.models import Project, Task


def _display_available() -> bool:
    """Whether a usable Tk display is present."""
    try:
        import tkinter
        root = tkinter.Tk()
    except Exception:
        return False
    root.destroy()
    return True


HAVE_DISPLAY = _display_available()


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestDialogConstruction(unittest.TestCase):
    """Every dialog builds without raising."""

    def setUp(self):
        """Build a root window and a small project."""
        import customtkinter as ctk

        self.root = ctk.CTk()
        self.root.withdraw()

        self.project = Project(name="Test Project")
        self.parent = Task(
            id="001", name="Parent",
            start_date=datetime(2026, 1, 1),
            end_date=datetime(2026, 1, 10),
        )
        self.other = Task(
            id="002", name="Other",
            start_date=datetime(2026, 1, 11),
            end_date=datetime(2026, 1, 15),
        )
        self.project.add_task(self.parent)
        self.project.add_task(self.other)

    def tearDown(self):
        """Tear the root window down."""
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_the_settings_dialog_builds(self):
        """
        Opening the chart settings does not raise.

        _update_theme_preview was called while the dialog was being built,
        four rows before the colour boxes it writes into existed, so
        View -> Settings raised AttributeError on task_color_entry every
        time and the dialog never came up.
        """
        from gantt_app.views.gantt_chart import GanttChart
        from gantt_app.views.ganttsettingsw import GanttChartSettingsDialog

        chart = GanttChart(self.root, self.project)
        dialog = GanttChartSettingsDialog(self.root, chart)

        self.assertTrue(dialog.winfo_exists())
        self.assertTrue(hasattr(dialog, 'task_color_entry'))

    def test_the_resource_settings_dialog_builds_both_tabs(self):
        from gantt_app.resource_model import ResourceRepository
        from gantt_app.views.resourcesettings import ResourceSettingsWindow

        dialog = ResourceSettingsWindow(
            self.root, ResourceRepository(),
            active_project_ids=[self.project.name],
        )

        self.assertTrue(dialog.winfo_exists())
        self.assertEqual(dialog.tabview.get(), "Resources")
        self.assertTrue(hasattr(dialog, "resource_grid"))
        self.assertTrue(hasattr(dialog, "team_grid"))
        self.assertEqual(dialog.resource_edit_button.cget("state"), "disabled")

    def test_resource_settings_builds_daily_capacity_controls(self):
        from gantt_app.resource_model import ResourceRepository, SchedulePattern
        from gantt_app.views.resourcesettings import ResourceEditorModal

        repository = ResourceRepository()
        dialog = ResourceEditorModal(self.root, repository)

        self.assertEqual(tuple(dialog.daily_entries),
                         ("mon", "tue", "wed", "thu", "fri", "sat", "sun"))
        dialog._apply_pattern(SchedulePattern.CONTINUOUS.value)
        self.assertEqual([float(entry.get())
                          for entry in dialog.daily_entries.values()], [24] * 7)
        self.assertEqual(dialog.capacity_summary.cget("text"),
                         "168 hours/week | 4.20 FTE")

    def test_resource_editor_has_all_four_workflow_tabs(self):
        from gantt_app.resource_model import ResourceRepository
        from gantt_app.views.resourcesettings import ResourceEditorModal

        dialog = ResourceEditorModal(self.root, ResourceRepository())

        self.assertEqual(tuple(dialog.tabs),
                         ("General Settings", "Days Off", "Assigned Teams",
                          "Assigned Tasks (Read-Only)"))

    def test_resource_editor_adds_and_removes_days_off(self):
        from gantt_app.resource_model import ResourceRepository
        from gantt_app.views.datepicker import DateEntry
        from gantt_app.views.resourcesettings import ResourceEditorModal

        dialog = ResourceEditorModal(self.root, ResourceRepository())
        self.assertIsInstance(dialog.day_off_start, DateEntry)
        self.assertIsInstance(dialog.day_off_end, DateEntry)
        dialog.day_off_start.insert(0, "2026-08-10")
        dialog.day_off_end.insert(0, "2026-08-20")
        dialog.day_off_reason.insert(0, "Vacation")

        dialog._add_day_off()
        self.assertEqual(len(dialog.days_off), 1)
        self.assertEqual(dialog.days_off[0].reason, "Vacation")
        dialog._delete_day_off(0)
        self.assertEqual(dialog.days_off, [])

    def test_generic_resource_name_is_generated_from_its_role(self):
        from gantt_app.resource_model import ResourceRepository, ResourceType
        from gantt_app.views.resourcesettings import ResourceEditorModal

        repository = ResourceRepository()
        dialog = ResourceEditorModal(self.root, repository)
        dialog.type_menu.set("Generic (Role Placeholder)")
        dialog.role_entry.insert(0, "DevOps")

        dialog.save_and_apply()

        resource = next(iter(repository.resources.values()))
        self.assertEqual(resource.name, "DevOps Placeholder #1")
        self.assertIs(resource.resource_type, ResourceType.GENERIC)

    def test_resource_grid_filters_and_selects_a_row(self):
        from gantt_app.resource_model import (
            Resource, ResourceRepository, ResourceType,
        )
        from gantt_app.views.resourcesettings import ResourceSettingsWindow

        repository = ResourceRepository()
        repository.add_resource(Resource(
            id="qa", name="John Doe", resource_type=ResourceType.NAMED,
            role_type="QA Manager"))
        repository.add_resource(Resource(
            id="ops", name="Jane Doe", resource_type=ResourceType.NAMED,
            role_type="DevOps"))
        dialog = ResourceSettingsWindow(self.root, repository)

        self.assertEqual(dialog.resource_rows, ["qa", "ops"])
        dialog.resource_search.set("qa")
        self.assertEqual(dialog.resource_rows, ["qa"])
        dialog.resource_grid.select("qa")
        self.assertEqual(dialog.selected_resource_id, "qa")
        self.assertEqual(dialog.resource_edit_button.cget("state"), "normal")

    def test_team_split_recalculates_as_the_box_changes(self):
        from gantt_app.resource_model import (
            Resource, ResourceRepository, ResourceType, TeamPool,
        )
        from gantt_app.views.resourcesettings import TeamEditorModal

        repository = ResourceRepository()
        resource = Resource(
            id="john", name="John Doe", resource_type=ResourceType.NAMED,
            role_type="QA Manager")
        team = TeamPool(id="qa", name="Core QA")
        repository.add_resource(resource)
        repository.add_team(team)
        repository.set_team_allocation(resource.id, team.id, 100)
        dialog = TeamEditorModal(self.root, repository, team)

        dialog.member_split_vars[resource.id].set("50")

        self.assertEqual(dialog.allocations, {resource.id: 50})
        self.assertIn("20 hours/week", dialog.team_capacity_summary.cget("text"))

    def test_team_split_keeps_200_percent_and_marks_over_capacity(self):
        from gantt_app.resource_model import (
            Resource, ResourceRepository, ResourceType, TeamPool,
        )
        from gantt_app.views.resourcesettings import TeamEditorModal

        repository = ResourceRepository()
        resource = Resource(
            id="john", name="John Doe", resource_type=ResourceType.NAMED,
            role_type="QA Manager", team_memberships={"qa": 1.0})
        team = TeamPool(id="qa", name="Core QA")
        repository.add_resource(resource)
        repository.add_team(team)
        dialog = TeamEditorModal(self.root, repository, team)

        dialog.member_split_vars[resource.id].set("200")

        self.assertEqual(dialog.allocations[resource.id], 200)
        self.assertIn("80 hours/week", dialog.team_capacity_summary.cget("text"))
        entry = dialog.member_row_widgets[resource.id]["entry"]
        self.assertEqual(entry._allocation_status, "Over capacitated")
        self.assertEqual(entry.cget("border_color"), "#2196f3")

    def test_allocation_status_boundaries(self):
        from gantt_app.views.resourcesettings import allocation_status

        self.assertEqual(allocation_status(0)[0], "Free")
        self.assertEqual(allocation_status(1)[0], "Optimal")
        self.assertEqual(allocation_status(80)[0], "Optimal")
        self.assertEqual(allocation_status(81)[0], "Full capacity")
        self.assertEqual(allocation_status(100)[0], "Full capacity")
        self.assertEqual(allocation_status(101)[0], "Over capacitated")

    def test_fixed_team_editor_summary_uses_fixed_capacity(self):
        from gantt_app.resource_model import ResourceRepository, SchedulePattern
        from gantt_app.views.resourcesettings import TeamEditorModal

        dialog = TeamEditorModal(self.root, ResourceRepository())
        dialog.mode.set("Fixed")
        dialog._mode_changed()
        dialog.schedule_menu.set(SchedulePattern.CONTINUOUS.value)
        dialog.fixed_entry.insert(0, "168")
        dialog._update_team_summary()

        text = dialog.team_capacity_summary.cget("text")
        self.assertIn("Fixed Daily Capacity", text)
        self.assertIn("4.20 FTE (168 hours/week)", text)

    def test_new_team_does_not_acquire_existing_generic_resource(self):
        from gantt_app.resource_model import (
            Resource, ResourceRepository, ResourceType,
        )
        from gantt_app.views.resourcesettings import TeamEditorModal

        repository = ResourceRepository()
        resource = Resource(
            id="generic", name="DevOps Placeholder #1",
            resource_type=ResourceType.GENERIC, role_type="DevOps")
        repository.add_resource(resource)
        dialog = TeamEditorModal(self.root, repository)
        dialog.name_entry.insert(0, "Infrastructure")

        dialog.save_and_apply()

        self.assertEqual(resource.team_memberships, {})

    def test_zero_team_split_unassigns_member_when_applied(self):
        from gantt_app.resource_model import (
            Resource, ResourceRepository, ResourceType, TeamPool,
        )
        from gantt_app.views.resourcesettings import TeamEditorModal

        repository = ResourceRepository()
        resource = Resource(
            id="generic", name="DevOps Placeholder #1",
            resource_type=ResourceType.GENERIC, role_type="DevOps",
            team_memberships={"team": 0.5})
        team = TeamPool(id="team", name="Infrastructure")
        repository.add_resource(resource)
        repository.add_team(team)
        dialog = TeamEditorModal(self.root, repository, team)

        dialog.member_split_vars[resource.id].set("0")
        dialog.save_and_apply()

        self.assertEqual(resource.team_memberships, {})

    def test_team_grid_uses_the_wireframes_strict_columns(self):
        from gantt_app.resource_model import (
            Resource, ResourceRepository, ResourceType, TeamPool,
        )
        from gantt_app.views.resourcesettings import ResourceSettingsWindow

        repository = ResourceRepository()
        team = TeamPool(id="team", name="Core QA")
        repository.add_team(team)
        for resource_id, name, role in (
                ("john", "John Doe", "QA Manager"),
                ("jane", "Jane Smith", "QA Tester")):
            repository.add_resource(Resource(
                id=resource_id, name=name, resource_type=ResourceType.NAMED,
                role_type=role, team_memberships={team.id: 0.5}))
        dialog = ResourceSettingsWindow(self.root, repository)

        self.assertEqual(tuple(column[0] for column in dialog.TEAM_COLUMNS),
                         ("#", "Team Name", "Schedule Pattern", "Capacity Mode",
                          "Total Capacity", "Member Count", "Daily Summary"))
        dialog.team_grid.select(team.id)
        self.assertEqual(dialog.selected_team_id, team.id)
        self.assertEqual(dialog.team_edit_button.cget("state"), "normal")

    def test_daily_contribution_summary_does_not_print_seven_days(self):
        from gantt_app.resource_model import DAYS
        from gantt_app.views.resourcesettings import _daily_summary

        standard = dict(zip(DAYS, [4, 4, 4, 4, 4, 0, 0]))
        custom = dict(zip(DAYS, [8, 4, 8, 4, 0, 0, 0]))

        self.assertEqual(_daily_summary(standard), "4h/day (Mon-Fri)")
        self.assertEqual(_daily_summary(custom), "24h/week (custom)")

    def test_resource_actions_live_in_a_sticky_footer(self):
        import customtkinter as ctk
        from gantt_app.resource_model import ResourceRepository
        from gantt_app.views.resourcesettings import ResourceSettingsWindow

        dialog = ResourceSettingsWindow(self.root, ResourceRepository())

        self.assertIsInstance(dialog.resource_footer, ctk.CTkFrame)
        self.assertEqual(dialog.resource_footer.pack_info()["side"], "bottom")
        self.assertEqual(dialog.resource_edit_button.cget("state"), "disabled")
        self.assertEqual(dialog.resource_delete_button.cget("state"), "disabled")
        for button in (dialog.resource_delete_button,
                       dialog.team_delete_button):
            self.assertEqual(button.cget("fg_color"), "#e74c3c")
            self.assertEqual(button.cget("hover_color"), "#c0392b")

    def test_resource_settings_copy_paste_buttons_start_disabled(self):
        from gantt_app.resource_model import ResourceRepository
        from gantt_app.views.resourcesettings import ResourceSettingsWindow

        dialog = ResourceSettingsWindow(self.root, ResourceRepository())

        self.assertEqual(dialog.resource_copy_button.cget("state"), "disabled")
        self.assertEqual(dialog.resource_paste_button.cget("state"), "disabled")
        self.assertEqual(dialog.team_copy_button.cget("state"), "disabled")
        self.assertEqual(dialog.team_paste_button.cget("state"), "disabled")

    def test_copy_paste_resource_creates_an_independent_duplicate(self):
        from gantt_app.resource_model import (
            Resource, ResourceRepository, ResourceType,
        )
        from gantt_app.views.resourcesettings import ResourceSettingsWindow

        repository = ResourceRepository()
        repository.add_resource(Resource(
            id="qa", name="John Doe", resource_type=ResourceType.NAMED,
            role_type="QA Manager",
            daily_capacity_hours=dict(zip(
                ("mon", "tue", "wed", "thu", "fri", "sat", "sun"),
                (8, 8, 8, 8, 8, 0, 0))),
            team_memberships={"team_1": 0.5},
            assigned_project_ids=["Project A"]))
        dialog = ResourceSettingsWindow(self.root, repository)
        dialog.resource_grid.select("qa")

        dialog._copy_resource("qa")
        dialog._paste_resource()

        self.assertEqual(len(repository.resources), 2)
        original = repository.resources["qa"]
        copied = [resource for resource in repository.resources.values()
                  if resource.id != "qa"][0]
        self.assertEqual(copied.name, "John Doe (Copy)")
        self.assertEqual(copied.role_type, original.role_type)
        self.assertEqual(copied.resource_type, original.resource_type)
        self.assertEqual(copied.daily_capacity_hours,
                         original.daily_capacity_hours)
        self.assertEqual(copied.team_memberships, original.team_memberships)
        self.assertEqual(copied.assigned_project_ids, [])
        self.assertNotEqual(copied.id, original.id)

    def test_copy_paste_team_keeps_settings_but_not_members(self):
        from gantt_app.resource_model import (
            Resource, ResourceRepository, ResourceType, TeamPool,
        )
        from gantt_app.views.resourcesettings import ResourceSettingsWindow

        repository = ResourceRepository()
        team = TeamPool(
            id="qa", name="Core QA", is_fixed_capacity=True,
            fixed_hours=160, schedule_pattern="24/7 Operation")
        repository.add_team(team)
        repository.add_resource(Resource(
            id="john", name="John Doe", resource_type=ResourceType.NAMED,
            role_type="QA Manager", team_memberships={team.id: 1.0}))
        dialog = ResourceSettingsWindow(self.root, repository)
        dialog.team_grid.select("qa")

        dialog._copy_team("qa")
        dialog._paste_team()

        self.assertEqual(len(repository.teams), 2)
        self.assertEqual(
            [resource for resource in repository.resources.values()][0]
            .team_memberships, {"qa": 1.0})
        copied = [team for team in repository.teams.values()
                  if team.id != "qa"][0]
        self.assertEqual(copied.name, "Core QA (Copy)")
        self.assertTrue(copied.is_fixed_capacity)
        self.assertEqual(copied.fixed_hours, 160)
        self.assertNotEqual(copied.id, "qa")

    def test_copy_paste_avoids_duplicate_names(self):
        from gantt_app.resource_model import Resource, ResourceRepository, ResourceType
        from gantt_app.views.resourcesettings import ResourceSettingsWindow

        repository = ResourceRepository()
        repository.add_resource(Resource(
            id="qa", name="John Doe", resource_type=ResourceType.NAMED,
            role_type="QA Manager"))
        repository.add_resource(Resource(
            id="qa2", name="John Doe (Copy)", resource_type=ResourceType.NAMED,
            role_type="QA Manager"))
        dialog = ResourceSettingsWindow(self.root, repository)
        dialog.resource_grid.select("qa")

        dialog._copy_resource("qa")
        dialog._paste_resource()

        names = {resource.name for resource in repository.resources.values()}
        self.assertIn("John Doe (Copy 2)", names)

    def test_keyboard_shortcut_opens_editor_for_active_tab(self):
        from gantt_app.resource_model import ResourceRepository
        from gantt_app.views.resourcesettings import ResourceSettingsWindow

        dialog = ResourceSettingsWindow(self.root, ResourceRepository())

        dialog._hotkey_create()
        self.assertIsNotNone(getattr(dialog, "resource_editor", None))

        dialog.team_editor = None
        dialog.tabview.set("Teams")
        dialog._hotkey_create()
        self.assertIsNotNone(getattr(dialog, "team_editor", None))

    def test_double_click_opens_resource_editor(self):
        from unittest import mock
        from gantt_app.resource_model import (
            Resource, ResourceRepository, ResourceType,
        )
        from gantt_app.views.resourcesettings import ResourceSettingsWindow

        repository = ResourceRepository()
        repository.add_resource(Resource(
            id="qa", name="John Doe", resource_type=ResourceType.NAMED,
            role_type="QA Manager"))
        dialog = ResourceSettingsWindow(self.root, repository)

        with mock.patch.object(dialog.resource_grid.tree, "identify_row",
                               return_value="qa"):
            dialog.resource_grid._on_double_click(
                mock.Mock(y=10))

        self.assertIsNotNone(getattr(dialog, "resource_editor", None))
        self.assertEqual(dialog.selected_resource_id, "qa")

    def test_double_click_opens_team_editor(self):
        from unittest import mock
        from gantt_app.resource_model import (
            ResourceRepository, TeamPool,
        )
        from gantt_app.views.resourcesettings import ResourceSettingsWindow

        repository = ResourceRepository()
        repository.add_team(TeamPool(id="qa", name="Core QA"))
        dialog = ResourceSettingsWindow(self.root, repository)
        dialog.tabview.set("Teams")

        with mock.patch.object(dialog.team_grid.tree, "identify_row",
                               return_value="qa"):
            dialog.team_grid._on_double_click(
                mock.Mock(y=10))

        self.assertIsNotNone(getattr(dialog, "team_editor", None))
        self.assertEqual(dialog.selected_team_id, "qa")

    def test_resource_settings_save_changes_uses_project_callback(self):
        from gantt_app.resource_model import ResourceRepository
        from gantt_app.views.resourcesettings import ResourceSettingsWindow

        calls = []
        dialog = ResourceSettingsWindow(
            self.root, ResourceRepository(), on_save=lambda: calls.append(True))

        dialog._save_changes()

        self.assertEqual(calls, [True])

    def test_the_settings_dialog_opens_on_the_saved_colours(self):
        """
        Not on the theme's, which would discard what was chosen before.

        The initial paint touches the swatch alone; taking a theme's colours
        is what the theme menu does.
        """
        from gantt_app.views.gantt_chart import GanttChart
        from gantt_app.views.ganttsettingsw import GanttChartSettingsDialog

        chart = GanttChart(self.root, self.project)
        chart.task_color = '#abcdef'
        dialog = GanttChartSettingsDialog(self.root, chart)

        self.assertEqual(dialog.task_color_entry.get(), '#abcdef')

    def test_choosing_a_theme_fills_the_colour_boxes(self):
        """Which is the thing the initial call was trying to do too early."""
        from gantt_app.views.gantt_chart import GanttChart
        from gantt_app.views.ganttsettingsw import (
            GanttChartSettingsDialog, MERMAID_THEMES,
        )

        chart = GanttChart(self.root, self.project)
        dialog = GanttChartSettingsDialog(self.root, chart)
        name = list(MERMAID_THEMES)[1]

        dialog.theme_var.set(name)
        dialog._update_theme_preview()

        self.assertEqual(dialog.task_color_entry.get(),
                         MERMAID_THEMES[name]['task_color'])

    def test_the_settings_dialog_opens_on_what_was_applied(self):
        """
        Every setting, not only the three colours it read off the chart.

        Font size, theme and the background and grid colours were written
        here as defaults, so reopening showed 12px and the Default theme
        however the chart had been set.
        """
        from gantt_app.views.gantt_chart import GanttChart
        from gantt_app.views.ganttsettingsw import (
            GanttChartSettingsDialog, MERMAID_THEMES,
        )

        chart = GanttChart(self.root, self.project)
        first = GanttChartSettingsDialog(self.root, chart)
        theme = [name for name in MERMAID_THEMES if name != 'Default'][0]
        first.theme_var.set(theme)
        first._update_theme_preview()
        first.font_size_slider.set(18)
        first.apply()

        reopened = GanttChartSettingsDialog(self.root, chart)

        self.assertEqual(int(reopened.font_size_slider.get()), 18)
        self.assertEqual(reopened.theme_var.get(), theme)
        self.assertEqual(reopened.bg_color_entry.get(),
                         MERMAID_THEMES[theme]['bg_color'])
        self.assertEqual(reopened.grid_color_entry.get(),
                         MERMAID_THEMES[theme]['grid_color'])

    def test_reapplying_without_a_change_changes_nothing(self):
        """
        Which is what made the defaults actively harmful.

        Opening the dialog and pressing Apply wrote its hardcoded font size,
        theme and background back over whatever had been chosen before.
        """
        from gantt_app.views.gantt_chart import GanttChart
        from gantt_app.views.ganttsettingsw import (
            GanttChartSettingsDialog, MERMAID_THEMES,
        )

        chart = GanttChart(self.root, self.project)
        setup = GanttChartSettingsDialog(self.root, chart)
        setup.theme_var.set(
            [name for name in MERMAID_THEMES if name != 'Default'][0])
        setup._update_theme_preview()
        setup.font_size_slider.set(20)
        setup.apply()
        before = chart.current_settings()

        GanttChartSettingsDialog(self.root, chart).apply()

        self.assertEqual(chart.current_settings(), before)

    def test_the_chart_answers_with_every_setting(self):
        """
        current_settings names them all, so nothing has to be defaulted twice.

        It is what the renderers draw with and what the dialog opens on.
        """
        from gantt_app.utils.chart_figure import DEFAULT_SETTINGS
        from gantt_app.views.gantt_chart import GanttChart

        chart = GanttChart(self.root, self.project)

        self.assertEqual(set(chart.current_settings()) & set(DEFAULT_SETTINGS),
                         set(DEFAULT_SETTINGS))

    def test_creating_a_milestone_opens_with_the_box_ticked(self):
        """
        Choosing Create Milestone means a milestone, so the box says so.

        The box is told what to show rather than left to work it out from
        the variable it is handed: CustomTkinter decides a checkbox's
        opening state by comparing that variable against its onvalue, which
        is its business and differs between its versions.
        """
        from gantt_app.views.taskdialogs import CreateTaskDialog

        dialog = CreateTaskDialog(self.root, self.project,
                                  task_type="Milestone")

        self.assertTrue(dialog.is_milestone_var.get())
        self.assertEqual(dialog.milestone_check.get(), 1)

    def test_creating_anything_else_opens_with_it_clear(self):
        """A task is not a milestone until somebody says so."""
        from gantt_app.views.taskdialogs import CreateTaskDialog

        for kind in ("Phase", "Task", "Subtask"):
            dialog = CreateTaskDialog(self.root, self.project, task_type=kind)

            self.assertFalse(dialog.is_milestone_var.get(), kind)
            self.assertEqual(dialog.milestone_check.get(), 0, kind)

    def test_the_milestone_control_is_a_switch(self):
        """
        A switch rather than a tick box.

        Flicking it empties the end date and greys it out there and then,
        which is a setting being turned on rather than a box being ticked
        towards a form that gets submitted later.
        """
        import customtkinter as ctk

        from gantt_app.views.taskdialogs import CreateTaskDialog

        dialog = CreateTaskDialog(self.root, self.project, task_type="Task")

        self.assertIsInstance(dialog.milestone_check, ctk.CTkSwitch)

    def test_editing_a_milestone_opens_with_the_box_ticked(self):
        """The same box, over a task that is already one."""
        from gantt_app.models import Task
        from gantt_app.views.taskdialogs import EditTaskDialog

        milestone = Task(id="M1", name="Sign-off", task_type="Milestone",
                         start_date=datetime(2026, 1, 1))
        self.project.add_task(milestone)

        dialog = EditTaskDialog(self.root, milestone, self.project,
                                on_save=lambda t: None,
                                on_delete=lambda i: None)

        self.assertEqual(dialog.milestone_check.get(), 1)

    def test_create_task_dialog_builds(self):
        """Creating a task opens a complete form."""
        from gantt_app.views.taskdialogs import CreateTaskDialog

        dialog = CreateTaskDialog(self.root, self.project,
                                  on_save=lambda task: None)

        self.assertTrue(hasattr(dialog, 'name_entry'))
        self.assertTrue(hasattr(dialog, 'dependency_editor'))

    def test_create_milestone_dialog_builds(self):
        """Creating a milestone opens a complete form."""
        from gantt_app.views.taskdialogs import CreateTaskDialog

        dialog = CreateTaskDialog(self.root, self.project,
                                  task_type="Milestone",
                                  on_save=lambda task: None)

        self.assertTrue(dialog.is_milestone)
        self.assertIsNone(dialog.end_date_entry)

    def test_create_subtask_dialog_builds(self):
        """Creating a sub-task under a parent opens a complete form."""
        from gantt_app.views.taskdialogs import CreateTaskDialog

        dialog = CreateTaskDialog(self.root, self.project,
                                  task_type="Subtask",
                                  parent_task=self.parent,
                                  on_save=lambda task: None)

        self.assertEqual(dialog.parent_task, self.parent)

    def test_edit_task_dialog_builds(self):
        """Editing an existing task opens a complete form."""
        from gantt_app.views.taskdialogs import EditTaskDialog

        dialog = EditTaskDialog(self.root, self.other, self.project,
                                on_save=lambda task: None,
                                on_delete=lambda task_id: None)

        self.assertTrue(hasattr(dialog, 'dependency_editor'))

    def test_task_list_and_toolbar_build(self):
        """The two main panes build against a populated project."""
        from gantt_app.views.task_list import DragDropTaskList
        from gantt_app.views.toolbar import Toolbar

        DragDropTaskList(self.root, self.project)
        Toolbar(self.root, self.project)


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestDependencyEditorLayout(unittest.TestCase):
    """
    The Dependency tab keeps its controls inside the dialog.

    DEVELOPMENT NOTES:
    ------------------
    The add controls used to sit on one row of fixed widths totalling roughly
    700px inside a 500px dialog, which put the Add button past the right edge
    with no way to add a dependency at all. These pin the dialog wide enough,
    and the controls narrow enough, that it stays reachable.
    """

    def setUp(self):
        """Build a root window and a project with a few tasks."""
        import customtkinter as ctk

        self.root = ctk.CTk()
        self.root.withdraw()

        self.project = Project(name="Test Project")
        base = datetime(2026, 1, 1)
        for index in range(1, 4):
            self.project.add_task(Task(
                id=f"00{index}", name=f"Task {index}",
                start_date=base, end_date=base + timedelta(days=3),
            ))

    def tearDown(self):
        """Tear the root window down."""
        try:
            self.root.destroy()
        except Exception:
            pass

    def _add_button(self, editor):
        """Find the Dependency tab's Add button."""
        import customtkinter as ctk

        for frame in editor.winfo_children():
            for widget in frame.winfo_children():
                if (isinstance(widget, ctk.CTkButton)
                        and widget.cget('text') == 'Add'):
                    return widget
        self.fail("the Dependency tab has no Add button")

    def _dialog(self):
        """Open an edit dialog squeezed to its minimum size."""
        from gantt_app.views.taskdialogs import EditTaskDialog

        dialog = EditTaskDialog(self.root, self.project.tasks[0], self.project,
                                on_save=lambda task: None,
                                on_delete=lambda task_id: None)
        dialog.geometry("560x480")
        dialog.update_idletasks()
        return dialog

    def test_the_add_button_fits_at_the_minimum_width(self):
        """Squeezed to its minimum, the dialog still shows the Add button."""
        dialog = self._dialog()
        button = self._add_button(dialog.dependency_editor)

        right_edge = (button.winfo_rootx() - dialog.winfo_rootx()
                      + button.winfo_width())

        self.assertLessEqual(right_edge, dialog.winfo_width())

    def test_the_add_controls_are_stacked(self):
        """
        The predecessor menu and the Add button are on separate rows.

        Read from the grid rather than from screen coordinates: those need
        the dialog mapped and laid out at its final size, which is not true
        under a headless display, and the comparison then means nothing.
        """
        dialog = self._dialog()
        editor = dialog.dependency_editor
        button = self._add_button(editor)

        self.assertGreater(int(button.grid_info()['row']),
                           int(editor.candidate_menu.grid_info()['row']))


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestExportFailureReporting(unittest.TestCase):
    """The export error path does not fail on its own imports."""

    def test_reporting_a_failed_export_shows_a_message(self):
        """
        Reporting a failed export reaches its dialog.

        It previously imported NO_BROWSER_MESSAGE, which was removed along
        with Kaleido, so the function that reports a failed export raised
        ImportError instead of explaining anything.
        """
        from unittest import mock

        from gantt_app.views.toolbar import Toolbar

        stub = SimpleNamespace()

        with mock.patch('gantt_app.views.toolbar.messagebox') as box:
            Toolbar._report_static_export_failure(stub, "PNG")

        self.assertTrue(box.showerror.called or box.showwarning.called)


if __name__ == '__main__':
    unittest.main()
