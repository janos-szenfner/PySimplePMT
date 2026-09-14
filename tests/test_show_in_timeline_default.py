"""
A newly created task defaults to off the timeline (issue #33).

The Gantt should stay empty until the planner puts a task on it, so the
create dialog's stand-in for a new task carries show_in_timeline=False. The
model default is unchanged - loaded plans, imports and existing tasks keep
whatever they already have - so this checks the create path specifically,
without a display, by calling form_template on a light stand-in.
"""

import unittest
from types import SimpleNamespace

from gantt_app.core.models import Project, Task
from gantt_app.views.taskdialogs import CreateTaskDialog


def _template(task_type="Task", parent_task=None):
    """Run CreateTaskDialog.form_template with only what it reads."""
    stub = SimpleNamespace(
        project=Project(name="P"),
        parent_task=parent_task,
        is_milestone=(task_type == "Milestone"),
        task_type=task_type,
        DEFAULT_COLORS=CreateTaskDialog.DEFAULT_COLORS,
        SUBTASK_LENGTH=CreateTaskDialog.SUBTASK_LENGTH,
        DEFAULT_LENGTH=CreateTaskDialog.DEFAULT_LENGTH,
    )
    return CreateTaskDialog.form_template(stub)


class TestNewTaskDefaultsOffTimeline(unittest.TestCase):
    def test_a_new_task_starts_off_the_timeline(self):
        self.assertFalse(_template().show_in_timeline)

    def test_a_new_milestone_starts_off_the_timeline(self):
        self.assertFalse(_template("Milestone").show_in_timeline)

    def test_a_new_subtask_starts_off_the_timeline(self):
        parent = Task(id="p", name="Parent",
                      start_date=Project(name="P").calendar
                      .get_next_working_day(__import__("datetime")
                                            .datetime(2026, 9, 10)))
        self.assertFalse(_template("Subtask", parent).show_in_timeline)

    def test_the_model_default_is_unchanged_for_loaded_tasks(self):
        # A plain Task (as built by importers, sample data and file loads)
        # keeps the long-standing visible default, so existing plans are
        # unaffected.
        task = Task(id="t", name="Loaded",
                    start_date=__import__("datetime").datetime(2026, 9, 10))
        self.assertTrue(task.show_in_timeline)


if __name__ == "__main__":
    unittest.main()
