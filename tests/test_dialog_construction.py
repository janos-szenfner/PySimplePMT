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
        from gantt_app.views.task_list import CreateTaskDialog

        dialog = CreateTaskDialog(self.root, self.project,
                                  on_save=lambda task: None)

        self.assertTrue(hasattr(dialog, 'name_entry'))
        self.assertTrue(hasattr(dialog, 'dependency_editor'))

    def test_create_milestone_dialog_builds(self):
        """Creating a milestone opens a complete form."""
        from gantt_app.views.task_list import CreateTaskDialog

        dialog = CreateTaskDialog(self.root, self.project,
                                  task_type="Milestone",
                                  on_save=lambda task: None)

        self.assertTrue(dialog.is_milestone)
        self.assertIsNone(dialog.end_date_entry)

    def test_create_subtask_dialog_builds(self):
        """Creating a sub-task under a parent opens a complete form."""
        from gantt_app.views.task_list import CreateTaskDialog

        dialog = CreateTaskDialog(self.root, self.project,
                                  task_type="Sub-Task",
                                  parent_task=self.parent,
                                  on_save=lambda task: None)

        self.assertEqual(dialog.parent_task, self.parent)

    def test_edit_task_dialog_builds(self):
        """Editing an existing task opens a complete form."""
        from gantt_app.views.task_list import EditTaskDialog

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
