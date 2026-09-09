"""
Model-level tests for the Task Type / Effort-Driven fields.

These cover the Task and Project data model rather than the effort maths
(tests/test_effort_engine.py): the new fields default safely, survive a
save/load round-trip, coerce bad values, and are carried through undo/redo.
"""

import json
import unittest
from datetime import datetime

from gantt_app.models import (
    DEFAULT_HOURS_PER_DAY,
    EFFORT_FIXED_UNITS,
    EFFORT_FIXED_WORK,
    Project,
    Task,
)
from gantt_app.utils.undoredo import ProjectStateTracker, UndoRedoManager


def _task(**kwargs):
    kwargs.setdefault('id', 'T')
    kwargs.setdefault('name', 'A task')
    kwargs.setdefault('start_date', datetime(2026, 9, 9))
    return Task(**kwargs)


class TestDefaults(unittest.TestCase):
    def test_a_new_task_is_fixed_units_effort_driven_auto(self):
        task = _task()
        self.assertEqual(task.effort_type, EFFORT_FIXED_UNITS)
        self.assertTrue(task.effort_driven)
        self.assertFalse(task.manually_scheduled)

    def test_a_new_project_has_an_eight_hour_day(self):
        self.assertEqual(Project(name='P').hours_per_day, DEFAULT_HOURS_PER_DAY)


class TestPostInitCoercion(unittest.TestCase):
    def test_an_unknown_effort_type_falls_back_to_fixed_units(self):
        task = _task(effort_type='Fixed Nonsense')
        self.assertEqual(task.effort_type, EFFORT_FIXED_UNITS)

    def test_fixed_work_forces_effort_driven_on(self):
        task = _task(effort_type=EFFORT_FIXED_WORK, effort_driven=False)
        self.assertTrue(task.effort_driven)


class TestTaskRoundTrip(unittest.TestCase):
    def test_the_effort_fields_survive_save_and_load(self):
        task = _task(effort_type=EFFORT_FIXED_WORK, effort_driven=True,
                     manually_scheduled=True)
        reread = Task.from_dict(json.loads(json.dumps(task.to_dict())))

        self.assertEqual(reread.effort_type, EFFORT_FIXED_WORK)
        self.assertTrue(reread.effort_driven)
        self.assertTrue(reread.manually_scheduled)

    def test_a_plan_without_the_fields_opens_at_the_defaults(self):
        # A task dict saved before the feature existed.
        data = _task().to_dict()
        for key in ('effort_type', 'effort_driven', 'manually_scheduled'):
            data.pop(key, None)
        reread = Task.from_dict(data)

        self.assertEqual(reread.effort_type, EFFORT_FIXED_UNITS)
        self.assertTrue(reread.effort_driven)
        self.assertFalse(reread.manually_scheduled)


class TestProjectHoursPerDayRoundTrip(unittest.TestCase):
    def test_it_survives_save_and_load(self):
        project = Project(name='P')
        project.hours_per_day = 7.5
        reread = Project.from_dict(json.loads(json.dumps(project.to_dict())))
        self.assertEqual(reread.hours_per_day, 7.5)

    def test_a_missing_value_reads_as_eight(self):
        data = Project(name='P').to_dict()
        data.pop('hours_per_day', None)
        self.assertEqual(Project.from_dict(data).hours_per_day,
                         DEFAULT_HOURS_PER_DAY)

    def test_a_zero_or_negative_day_reads_as_eight(self):
        for bad in (0, -3, 'x'):
            data = Project(name='P').to_dict()
            data['hours_per_day'] = bad
            self.assertEqual(Project.from_dict(data).hours_per_day,
                             DEFAULT_HOURS_PER_DAY)


class TestUndoRedoCarriesTheFields(unittest.TestCase):
    def test_editing_another_field_does_not_reset_the_effort_type(self):
        project = Project(name='P')
        task = _task(effort_type=EFFORT_FIXED_WORK, effort_driven=True)
        project.add_task(task)
        tracker = ProjectStateTracker(project, UndoRedoManager())

        # Change only the name; the effort fields must be preserved.
        tracker.update_task('T', name='Renamed')

        self.assertEqual(project.get_task_by_id('T').effort_type,
                         EFFORT_FIXED_WORK)
        self.assertTrue(project.get_task_by_id('T').effort_driven)

    def test_the_effort_type_can_be_changed_through_the_tracker(self):
        project = Project(name='P')
        project.add_task(_task())
        tracker = ProjectStateTracker(project, UndoRedoManager())

        tracker.update_task('T', effort_type=EFFORT_FIXED_WORK)
        self.assertEqual(project.get_task_by_id('T').effort_type,
                         EFFORT_FIXED_WORK)


if __name__ == '__main__':
    unittest.main()
