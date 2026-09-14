"""
File > Close Project resets to a blank plan without quitting (issue #21).

Closing the file used to mean closing the window, which quit the whole
application. close_project now empties the current plan back to a fresh one
and stays open, offering to save unsaved work first. Tested on a Toolbar
built without its widgets, so no display is needed.
"""

import unittest
from datetime import datetime
from types import SimpleNamespace

from gantt_app.core.models import Project, Task
from gantt_app.views.toolbar import Toolbar


def _toolbar(project, unsaved_choice="discard", save_ok=True):
    toolbar = Toolbar.__new__(Toolbar)
    toolbar.project = project
    toolbar.undo_redo_manager = None      # keeps _forget_the_previous_plan quiet
    toolbar.clipboard_manager = None
    toolbar.current_file_path = "/tmp/plan.json"
    toolbar._changed = False
    toolbar.on_project_changed = lambda: setattr(toolbar, "_changed", True)
    toolbar.master = SimpleNamespace(
        check_unsaved_changes=lambda **k: unsaved_choice,
        save_project=lambda: save_ok,
        mark_clean=lambda: setattr(toolbar, "_marked_clean", True),
    )
    toolbar._marked_clean = False
    return toolbar


class TestCloseProject(unittest.TestCase):
    def _project(self):
        project = Project(name="Real Plan")
        project.add_task(Task(id="t1", name="A", start_date=datetime(2026, 9, 10)))
        return project

    def test_it_empties_the_plan_and_stays_open(self):
        project = self._project()
        toolbar = _toolbar(project)
        toolbar.close_project()

        self.assertEqual(project.tasks, [])
        self.assertEqual(project.name, "New Project")
        self.assertIsNone(toolbar.current_file_path)
        self.assertTrue(toolbar._changed)
        self.assertTrue(toolbar._marked_clean)

    def test_cancelling_the_save_prompt_keeps_the_plan(self):
        project = self._project()
        toolbar = _toolbar(project, unsaved_choice="cancel")
        toolbar.close_project()

        self.assertEqual([t.id for t in project.tasks], ["t1"])
        self.assertEqual(project.name, "Real Plan")
        self.assertEqual(toolbar.current_file_path, "/tmp/plan.json")

    def test_a_failed_save_aborts_the_close(self):
        project = self._project()
        toolbar = _toolbar(project, unsaved_choice="save", save_ok=False)
        toolbar.close_project()

        self.assertEqual([t.id for t in project.tasks], ["t1"])


if __name__ == "__main__":
    unittest.main()
