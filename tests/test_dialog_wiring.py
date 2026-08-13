"""
Tests for the wiring between the task dialogs and the dependency editor.

DEVELOPMENT NOTES:
------------------
Building the dialogs needs a display, so these exercise the callback methods
directly against a stand-in object. That is enough to catch the failure they
guard against: DependencyEditor calls back into the dialog while the dialog is
still inside the constructor that assigns it, so the attribute holding the
editor does not exist yet.
"""

import inspect
import unittest
from datetime import datetime
from types import SimpleNamespace

from gantt_app.models import Project, Task
from gantt_app.views.dependency_editor import DependencyEditor
from gantt_app.views.task_list import CreateTaskDialog, EditTaskDialog


class TestConstructionOrder(unittest.TestCase):
    """The editor must not call back before the dialog has finished building."""

    def test_initial_refresh_does_not_notify(self):
        """
        DependencyEditor.__init__ refreshes without notifying.

        Notifying during construction reached for an attribute the dialog had
        not assigned yet, and would also have rescheduled the task simply
        because its dialog was opened.
        """
        source = inspect.getsource(DependencyEditor.__init__)

        self.assertIn('refresh(notify=False)', source)

    def test_refresh_accepts_a_notify_flag(self):
        """refresh can be told not to call back."""
        parameters = inspect.signature(DependencyEditor.refresh).parameters

        self.assertIn('notify', parameters)
        self.assertTrue(parameters['notify'].default)

    def test_notify_guards_the_callback(self):
        """The callback is only invoked when notifying is asked for."""
        source = inspect.getsource(DependencyEditor.refresh)

        self.assertIn('if notify and self.on_changed', source)


class TestDialogCallbackGuards(unittest.TestCase):
    """The dialogs tolerate being called before they are fully built."""

    def _stub(self, **attributes):
        """A stand-in for a half-built dialog."""
        return SimpleNamespace(**attributes)

    def test_edit_dialog_survives_a_missing_editor(self):
        """
        The callback returns quietly when the editor is not assigned yet.

        This is the exact state that raised
        "'EditTaskDialog' object has no attribute 'dependency_editor'".
        """
        stub = self._stub()

        try:
            EditTaskDialog._on_dependencies_changed(stub)
        except AttributeError as error:
            self.fail(f"callback raised on a half-built dialog: {error}")

    def test_create_dialog_survives_a_missing_editor(self):
        """The create dialog has the same guard."""
        stub = self._stub()

        try:
            CreateTaskDialog._on_dependencies_changed(stub)
        except AttributeError as error:
            self.fail(f"callback raised on a half-built dialog: {error}")

    def test_edit_dialog_survives_a_missing_date_field(self):
        """An editor without the date widgets is also handled."""
        stub = self._stub(dependency_editor=object())

        try:
            EditTaskDialog._on_dependencies_changed(stub)
        except AttributeError as error:
            self.fail(f"callback raised without the date fields: {error}")


class TestRequiredStartDate(unittest.TestCase):
    """The date a set of links implies, which the dialogs display."""

    def setUp(self):
        """A project with one predecessor."""
        self.project = Project(name="Wiring")
        self.first = Task.create_task("First", datetime(2024, 1, 1),
                                      datetime(2024, 1, 5),
                                      task_id=self.project.next_task_id())
        self.project.add_task(self.first)

        self.second = Task.create_task("Second", datetime(2024, 2, 1),
                                       datetime(2024, 2, 5),
                                       task_id=self.project.next_task_id())
        self.project.add_task(self.second)

    def _required(self, links, start):
        """Run the editor's calculation without building the widget."""
        editor = SimpleNamespace(
            project=self.project,
            task=self.second,
            links=links,
            get_links=lambda: list(links),
        )
        return DependencyEditor.required_start_date(editor, start)

    def test_no_links_implies_nothing(self):
        """With no dependencies the start date is left alone."""
        self.assertIsNone(self._required([], datetime(2024, 2, 1)))

    def test_end_start_hard(self):
        """End - Start pins to the day after the predecessor ends."""
        from gantt_app.models import Dependency

        required = self._required([Dependency(self.first.id, 'FS', 'Hard')],
                                  datetime(2024, 2, 1))

        self.assertEqual(required, datetime(2024, 1, 6))

    def test_start_start_hard(self):
        """Start - Start pins to the predecessor's start."""
        from gantt_app.models import Dependency

        required = self._required([Dependency(self.first.id, 'SS', 'Hard')],
                                  datetime(2024, 2, 1))

        self.assertEqual(required, datetime(2024, 1, 1))

    def test_rubber_leaves_a_later_start(self):
        """A Rubber link does not pull a later start backwards."""
        from gantt_app.models import Dependency

        required = self._required([Dependency(self.first.id, 'FS', 'Rubber')],
                                  datetime(2024, 2, 1))

        self.assertEqual(required, datetime(2024, 2, 1))


if __name__ == '__main__':
    unittest.main()
