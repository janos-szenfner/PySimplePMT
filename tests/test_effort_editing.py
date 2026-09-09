"""
Wiring tests for the task editor's effort reconciliation (phase 3b).

These exercise TaskFormDialog._reconcile_effort - the method the Save path
calls - without building the whole editor: it needs only ``self.project`` on
the non-conflict path, so a light stand-in stands in for the dialog. The
conflict-prompt branch is a UI dialog and is covered by the engine tests
(tests/test_effort_engine.py).
"""

import unittest
from datetime import datetime
from types import SimpleNamespace

from gantt_app.models import (
    EFFORT_FIXED_DURATION,
    EFFORT_FIXED_UNITS,
    Project,
    Task,
)
from gantt_app.views.taskform import TaskFormDialog


def _task(**kwargs):
    kwargs.setdefault('id', 'T')
    kwargs.setdefault('name', 'A task')
    kwargs.setdefault('start_date', datetime(2026, 9, 9))
    return Task(**kwargs)


def _reconcile(project, old_task, duration, assignments,
               effort_type=EFFORT_FIXED_UNITS, effort_driven=True):
    """Call the dialog method with a stand-in that only carries the project."""
    stub = SimpleNamespace(project=project)
    return TaskFormDialog._reconcile_effort(
        stub, old_task, duration, assignments, effort_type, effort_driven)


class TestEditorEffortWiring(unittest.TestCase):
    def setUp(self):
        self.project = Project(name='P')
        self.project.hours_per_day = 8.0

    def test_a_resourced_fixed_units_duration_edit_recomputes_work(self):
        old = _task(duration=5, effort_type=EFFORT_FIXED_UNITS,
                    resource_assignments=[
                        {'resource_id': 'R1', 'estimated_hours': 40.0,
                         'resource_split': 100.0}])
        # The form changed duration to 10 days; assignments untouched.
        assignments = [{'resource_id': 'R1', 'estimated_hours': 40.0,
                        'resource_split': 100.0}]
        duration, out = _reconcile(self.project, old, 10, assignments)

        self.assertEqual(duration, 10)
        self.assertEqual(out[0]['estimated_hours'], 80.0)   # 10d x 8h x 1.0

    def test_an_unresourced_task_is_returned_unchanged(self):
        old = _task(duration=5)
        duration, out = _reconcile(self.project, old, 10, [])
        self.assertEqual(duration, 10)
        self.assertEqual(out, [])

    def test_a_zero_percent_assignment_is_left_alone(self):
        old = _task(duration=5, resource_assignments=[
            {'resource_id': 'R1', 'estimated_hours': 40.0,
             'resource_split': 0.0}])
        assignments = [{'resource_id': 'R1', 'estimated_hours': 40.0,
                        'resource_split': 0.0}]
        duration, out = _reconcile(self.project, old, 10, assignments)

        self.assertEqual(duration, 10)
        self.assertEqual(out[0]['estimated_hours'], 40.0)   # untouched

    def test_fixed_duration_work_edit_recomputes_units(self):
        old = _task(duration=5, effort_type=EFFORT_FIXED_DURATION,
                    resource_assignments=[
                        {'resource_id': 'R1', 'estimated_hours': 40.0,
                         'resource_split': 100.0}])
        # The form doubled the resource's hours; duration is locked.
        assignments = [{'resource_id': 'R1', 'estimated_hours': 80.0,
                        'resource_split': 100.0}]
        duration, out = _reconcile(self.project, old, 5, assignments,
                                   effort_type=EFFORT_FIXED_DURATION)

        self.assertEqual(duration, 5)                       # locked
        self.assertEqual(out[0]['resource_split'], 200.0)   # U = 80/40 -> 2.0


if __name__ == '__main__':
    unittest.main()
