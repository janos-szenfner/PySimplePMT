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
                                  task_type="Sub-Task",
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
