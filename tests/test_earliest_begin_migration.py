"""
The retired "Earliest begin" floor migrates to Start No Earlier Than (#32).

Earliest begin was a floor on a task's start - exactly what the Start No
Earlier Than constraint is. The field is gone; a plan that still carries one
keeps its floor by reading it back as the SNET constraint that means the same
thing, so no plan silently loses a date somebody set.
"""

import unittest
from datetime import datetime

from gantt_app.models import Task


BASE = datetime(2026, 1, 1)


def _base_dict(**extra):
    data = {
        'id': '001',
        'name': 'A',
        'start_date': BASE.isoformat(),
        'end_date': None,
        'progress': 0,
        'dependencies': [],
        'color': '#1f6aa5',
        'is_milestone': False,
        'task_type': 'Task',
    }
    data.update(extra)
    return data


class TestEarliestBeginMigration(unittest.TestCase):
    def test_a_legacy_floor_becomes_a_start_no_earlier_than(self):
        task = Task.from_dict(_base_dict(
            earliest_begin=datetime(2026, 3, 2).isoformat()))
        self.assertEqual(task.constraint_type, 'SNET')
        self.assertEqual(task.constraint_date, datetime(2026, 3, 2))

    def test_no_legacy_floor_leaves_the_task_unconstrained(self):
        task = Task.from_dict(_base_dict())
        self.assertEqual(task.constraint_type, 'NA')
        self.assertIsNone(task.constraint_date)

    def test_a_real_constraint_is_kept_over_the_legacy_floor(self):
        # A file that carries both keeps the constraint - it is the canonical
        # one - and drops the legacy floor rather than overwriting it.
        task = Task.from_dict(_base_dict(
            earliest_begin=datetime(2026, 3, 2).isoformat(),
            constraint_type='MSO',
            constraint_date=datetime(2026, 5, 1).isoformat()))
        self.assertEqual(task.constraint_type, 'MSO')
        self.assertEqual(task.constraint_date, datetime(2026, 5, 1))

    def test_the_migrated_constraint_survives_a_further_round_trip(self):
        once = Task.from_dict(_base_dict(
            earliest_begin=datetime(2026, 3, 2).isoformat()))
        twice = Task.from_dict(once.to_dict())
        self.assertEqual(twice.constraint_type, 'SNET')
        self.assertEqual(twice.constraint_date, datetime(2026, 3, 2))

    def test_the_field_is_gone_from_the_task(self):
        task = Task.from_dict(_base_dict())
        self.assertNotIn('earliest_begin', task.to_dict())
        self.assertFalse(hasattr(task, 'earliest_begin'))


if __name__ == '__main__':
    unittest.main()
