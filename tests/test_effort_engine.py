"""
Unit tests for the Task Type / Effort-Driven engine (gantt_app/effort.py).

The scenarios mirror Task_Type_FRS §9 by number, with hours_per_day = 8 so a
day is eight hours. Pure maths, so no display is needed.
"""

import unittest

from gantt_app.effort import (
    Assignment,
    EffortState,
    add_resource,
    change_effort_type,
    days_to_hours,
    edit_duration,
    edit_units,
    edit_work,
    effort_driven_effective,
    logic_applies,
    recalculate,
    remove_resource,
    set_effort_driven,
    validate,
)
from gantt_app.models import (
    EFFORT_FIXED_DURATION,
    EFFORT_FIXED_UNITS,
    EFFORT_FIXED_WORK,
)


def _state(**kwargs):
    """An EffortState with hours_per_day 8 unless overridden."""
    kwargs.setdefault('hours_per_day', 8.0)
    return EffortState(**kwargs)


class TestConversions(unittest.TestCase):
    def test_a_day_is_eight_hours(self):
        self.assertEqual(days_to_hours(1, 8), 8)
        self.assertEqual(days_to_hours(5, 8), 40)


class TestExample91FixedUnitsEdOnAddResource(unittest.TestCase):
    """§9.1: work preserved, duration halves."""

    def test_work_preserved_duration_halves(self):
        state = _state(effort_type=EFFORT_FIXED_UNITS, effort_driven=True,
                       duration_hours=8, work=8,
                       assignments=[Assignment('R1', 1.0)])
        result = add_resource(state, 'R2', 1.0)

        self.assertTrue(result.ok)
        self.assertEqual(state.work, 8)
        self.assertEqual(state.duration_hours, 4)          # 8 / 2.0
        self.assertEqual(state.total_units, 2.0)


class TestExample92FixedUnitsEdOffAddResource(unittest.TestCase):
    """§9.2: duration preserved, work doubles."""

    def test_duration_preserved_work_doubles(self):
        state = _state(effort_type=EFFORT_FIXED_UNITS, effort_driven=False,
                       duration_hours=8, work=8,
                       assignments=[Assignment('R1', 1.0)])
        result = add_resource(state, 'R2', 1.0)

        self.assertTrue(result.ok)
        self.assertEqual(state.duration_hours, 8)
        self.assertEqual(state.work, 16)                   # 8 × 2.0


class TestExample93FixedWork(unittest.TestCase):
    """§9.3: Fixed Work is effort-driven; manual duration lifts allocation."""

    def test_effort_driven_is_forced_on(self):
        state = _state(effort_type=EFFORT_FIXED_WORK, effort_driven=False)
        self.assertTrue(effort_driven_effective(state))

    def test_add_resource_preserves_work(self):
        state = _state(effort_type=EFFORT_FIXED_WORK, effort_driven=True,
                       duration_hours=40, work=40,
                       assignments=[Assignment('R1', 1.0)])
        add_resource(state, 'R2', 1.0)

        self.assertEqual(state.work, 40)
        self.assertEqual(state.duration_hours, 20)         # 40 / 2.0

    def test_manual_duration_recalculates_units_and_warns(self):
        state = _state(effort_type=EFFORT_FIXED_WORK,
                       duration_hours=40, work=40,
                       assignments=[Assignment('R1', 1.0)])
        result = edit_duration(state, 32)                  # 4 days

        self.assertTrue(result.ok)
        self.assertEqual(state.work, 40)
        self.assertAlmostEqual(state.total_units, 1.25)    # 40 / 32
        self.assertTrue(result.warnings)                   # 125% > 100%

    def test_work_cannot_be_edited_directly(self):
        state = _state(effort_type=EFFORT_FIXED_WORK, duration_hours=40,
                       work=40, assignments=[Assignment('R1', 1.0)])
        result = edit_work(state, 80)

        self.assertFalse(result.ok)
        self.assertEqual(state.work, 40)


class TestExample94FixedDurationEdOnAddResource(unittest.TestCase):
    """§9.4: duration locked, work preserved, units shared out."""

    def test_units_redistribute_to_keep_duration(self):
        state = _state(effort_type=EFFORT_FIXED_DURATION, effort_driven=True,
                       duration_hours=40, work=40,
                       assignments=[Assignment('R1', 1.0)])
        add_resource(state, 'R2', 1.0)

        self.assertEqual(state.duration_hours, 40)
        self.assertEqual(state.work, 40)
        self.assertAlmostEqual(state.total_units, 1.0)
        for assignment in state.assignments:
            self.assertAlmostEqual(assignment.units, 0.5)  # each at 50%


class TestExample95FixedDurationEdOff(unittest.TestCase):
    """§9.5: duration locked, work grows; duration edits refused."""

    def test_work_grows_duration_holds(self):
        state = _state(effort_type=EFFORT_FIXED_DURATION, effort_driven=False,
                       duration_hours=40, work=40,
                       assignments=[Assignment('R1', 1.0)])
        add_resource(state, 'R2', 1.0)

        self.assertEqual(state.duration_hours, 40)
        self.assertEqual(state.work, 80)                   # 40 × 2.0

    def test_duration_is_locked(self):
        state = _state(effort_type=EFFORT_FIXED_DURATION, duration_hours=40,
                       work=40, assignments=[Assignment('R1', 1.0)])
        result = edit_duration(state, 48)

        self.assertFalse(result.ok)
        self.assertEqual(state.duration_hours, 40)


class TestExample910PartialAllocations(unittest.TestCase):
    """§9.10: a half-time resource added, work preserved."""

    def test_mixed_units_add(self):
        state = _state(effort_type=EFFORT_FIXED_UNITS, effort_driven=True,
                       duration_hours=40, work=80,
                       assignments=[Assignment('A', 1.0), Assignment('B', 1.0)])
        add_resource(state, 'C', 0.5)

        self.assertEqual(state.work, 80)
        self.assertEqual(state.total_units, 2.5)
        self.assertEqual(state.duration_hours, 32)         # 80 / 2.5


class TestResourceRemoval(unittest.TestCase):
    def test_removing_a_resource_extends_an_effort_driven_task(self):
        state = _state(effort_type=EFFORT_FIXED_UNITS, effort_driven=True,
                       duration_hours=4, work=8,
                       assignments=[Assignment('R1', 1.0),
                                    Assignment('R2', 1.0)])
        remove_resource(state, 1)

        self.assertEqual(state.work, 8)
        self.assertEqual(state.duration_hours, 8)          # 8 / 1.0

    def test_removing_the_last_resource_is_refused(self):
        state = _state(effort_type=EFFORT_FIXED_UNITS, effort_driven=True,
                       duration_hours=8, work=8,
                       assignments=[Assignment('R1', 1.0)])
        result = remove_resource(state, 0)

        self.assertFalse(result.ok)

    def test_effort_driven_off_removal_shrinks_work(self):
        state = _state(effort_type=EFFORT_FIXED_UNITS, effort_driven=False,
                       duration_hours=8, work=16,
                       assignments=[Assignment('R1', 1.0),
                                    Assignment('R2', 1.0)])
        remove_resource(state, 1)

        self.assertEqual(state.duration_hours, 8)
        self.assertEqual(state.work, 8)                    # 8 × 1.0


class TestDirectEdits(unittest.TestCase):
    def test_fixed_units_duration_edit_recalculates_work(self):
        state = _state(effort_type=EFFORT_FIXED_UNITS, duration_hours=8,
                       work=8, assignments=[Assignment('R1', 1.0)])
        edit_duration(state, 16)
        self.assertEqual(state.work, 16)

    def test_fixed_units_work_edit_recalculates_duration(self):
        state = _state(effort_type=EFFORT_FIXED_UNITS, duration_hours=8,
                       work=8, assignments=[Assignment('R1', 1.0)])
        edit_work(state, 16)
        self.assertEqual(state.duration_hours, 16)

    def test_fixed_duration_work_edit_recalculates_units(self):
        state = _state(effort_type=EFFORT_FIXED_DURATION, duration_hours=40,
                       work=40, assignments=[Assignment('R1', 1.0)])
        edit_work(state, 80)
        self.assertAlmostEqual(state.total_units, 2.0)     # 80 / 40


class TestValidation(unittest.TestCase):
    def test_fixed_work_needs_work(self):
        state = _state(effort_type=EFFORT_FIXED_WORK, work=0,
                       assignments=[Assignment('R1', 1.0)])
        self.assertFalse(validate(state).ok)

    def test_fixed_work_needs_a_resource(self):
        state = _state(effort_type=EFFORT_FIXED_WORK, work=40, assignments=[])
        self.assertFalse(validate(state).ok)

    def test_fixed_duration_needs_duration(self):
        state = _state(effort_type=EFFORT_FIXED_DURATION, duration_hours=0)
        self.assertFalse(validate(state).ok)

    def test_work_without_a_resource_is_refused(self):
        state = _state(effort_type=EFFORT_FIXED_UNITS, work=8, assignments=[])
        self.assertFalse(validate(state).ok)

    def test_a_placeholder_with_no_work_is_valid(self):
        state = _state(effort_type=EFFORT_FIXED_UNITS, work=0, assignments=[])
        self.assertTrue(validate(state).ok)

    def test_negatives_are_refused(self):
        state = _state(effort_type=EFFORT_FIXED_UNITS, work=-1,
                       assignments=[Assignment('R1', 1.0)])
        self.assertFalse(validate(state).ok)


class TestChangingTheTaskType(unittest.TestCase):
    def test_switching_to_fixed_work_locks_effort_driven_on(self):
        state = _state(effort_type=EFFORT_FIXED_UNITS, effort_driven=False,
                       duration_hours=8, work=8,
                       assignments=[Assignment('R1', 1.0)])
        result = change_effort_type(state, EFFORT_FIXED_WORK)

        self.assertTrue(result.ok)
        self.assertTrue(state.effort_driven)

    def test_switching_to_fixed_work_without_work_is_refused(self):
        state = _state(effort_type=EFFORT_FIXED_UNITS, work=0,
                       assignments=[Assignment('R1', 1.0)])
        result = change_effort_type(state, EFFORT_FIXED_WORK)
        self.assertFalse(result.ok)

    def test_a_hard_constraint_is_flagged(self):
        state = _state(effort_type=EFFORT_FIXED_UNITS, duration_hours=8,
                       work=8, assignments=[Assignment('R1', 1.0)],
                       constraint_type='MSO')
        result = change_effort_type(state, EFFORT_FIXED_DURATION)
        self.assertTrue(result.warnings)


class TestEffortDrivenToggle(unittest.TestCase):
    def test_fixed_work_cannot_be_toggled(self):
        state = _state(effort_type=EFFORT_FIXED_WORK, work=8,
                       assignments=[Assignment('R1', 1.0)])
        self.assertFalse(set_effort_driven(state, False).ok)

    def test_a_milestone_has_no_effort_logic(self):
        state = _state(effort_type=EFFORT_FIXED_UNITS, is_milestone=True)
        self.assertFalse(logic_applies(state))
        self.assertFalse(set_effort_driven(state, False).ok)

    def test_a_manually_scheduled_task_has_no_effort_logic(self):
        state = _state(effort_type=EFFORT_FIXED_UNITS, manually_scheduled=True)
        self.assertFalse(logic_applies(state))

    def test_toggling_a_fixed_units_task(self):
        state = _state(effort_type=EFFORT_FIXED_UNITS, effort_driven=True)
        self.assertTrue(set_effort_driven(state, False).ok)
        self.assertFalse(state.effort_driven)


class TestRecalculate(unittest.TestCase):
    def test_fixed_units_solves_duration(self):
        state = _state(effort_type=EFFORT_FIXED_UNITS, work=16,
                       assignments=[Assignment('R1', 1.0)])
        recalculate(state)
        self.assertEqual(state.duration_hours, 16)


if __name__ == '__main__':
    unittest.main()
