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
        self.assertEqual(dialog.tabview.get(), "Resources (Named & Generic)")
        self.assertIn(self.project.name, dialog.project_vars)
        self.assertTrue(hasattr(dialog, "team_list_frame"))

    def test_resource_settings_builds_daily_capacity_controls(self):
        from gantt_app.resource_model import ResourceRepository, SchedulePattern
        from gantt_app.views.resourcesettings import ResourceSettingsWindow

        repository = ResourceRepository()
        dialog = ResourceSettingsWindow(self.root, repository)

        self.assertEqual(tuple(dialog.daily_entries),
                         ("mon", "tue", "wed", "thu", "fri", "sat", "sun"))
        dialog._schedule_changed(SchedulePattern.CONTINUOUS.value)
        self.assertEqual([float(entry.get())
                          for entry in dialog.daily_entries.values()], [24] * 7)
        self.assertEqual(dialog.capacity_summary.cget("text"),
                         "168 hours/week | 4.20 FTE")

    def test_generic_resource_name_is_generated_from_its_role(self):
        from gantt_app.resource_model import ResourceRepository, ResourceType
        from gantt_app.views.resourcesettings import ResourceSettingsWindow

        repository = ResourceRepository()
        dialog = ResourceSettingsWindow(self.root, repository)
        dialog.combo_type.set("Generic (Role Placeholder)")
        dialog.entry_role.insert(0, "DevOps")

        dialog._save_resource()

        resource = next(iter(repository.resources.values()))
        self.assertEqual(resource.name, "DevOps Placeholder #1")
        self.assertIs(resource.resource_type, ResourceType.GENERIC)

    def test_resource_catalog_filters_by_role_and_has_status_bar(self):
        import customtkinter as ctk
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

        self.assertEqual(len(dialog.resource_cards), 2)
        dialog.resource_filter_var.set("qa")
        self.assertEqual(len(dialog.resource_cards), 1)

        def descendants(widget):
            children = widget.winfo_children()
            return children + [nested for child in children
                               for nested in descendants(child)]

        self.assertTrue(any(isinstance(widget, ctk.CTkProgressBar)
                            for widget in descendants(dialog.resource_cards[0])))

    def test_team_split_recalculates_as_the_box_changes(self):
        from gantt_app.resource_model import (
            Resource, ResourceRepository, ResourceType, TeamPool,
        )
        from gantt_app.views.resourcesettings import ResourceSettingsWindow

        repository = ResourceRepository()
        resource = Resource(
            id="john", name="John Doe", resource_type=ResourceType.NAMED,
            role_type="QA Manager")
        team = TeamPool(id="qa", name="Core QA")
        repository.add_resource(resource)
        repository.add_team(team)
        dialog = ResourceSettingsWindow(self.root, repository)

        dialog.team_split_vars[(team.id, resource.id)].set("50")

        self.assertEqual(resource.team_memberships, {team.id: 0.5})
        self.assertEqual(team.calculate_effective_capacity([resource]), 20)

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
