"""
Tests for the helper functions in gantt_app.views.resourcesettings.
"""
import unittest
from types import SimpleNamespace

from gantt_app.resource_model import SchedulePattern
from gantt_app.views.resourcesettings import (
    _schedule_short,
    _daily_summary,
    allocation_status,
    _allocation_tag,
    _number,
)


class TestScheduleShort(unittest.TestCase):
    """The schedule name mapper."""

    def test_standard(self):
        self.assertEqual(_schedule_short(SchedulePattern.STANDARD),
                         "Standard (M-F)")

    def test_continuous(self):
        self.assertEqual(_schedule_short(SchedulePattern.CONTINUOUS),
                         "24/7 Continuous")

    def test_weekend_only(self):
        self.assertEqual(_schedule_short(SchedulePattern.WEEKEND_ONLY),
                         "Weekend Only")

    def test_full_week(self):
        self.assertEqual(_schedule_short(SchedulePattern.FULL_WEEK),
                         "Full Week (M-Sun)")

    def test_custom(self):
        self.assertEqual(_schedule_short(SchedulePattern.CUSTOM), "Custom")


class TestDailySummary(unittest.TestCase):
    """The daily-capacity summary string."""

    def test_uniform_week(self):
        from gantt_app.resource_model import DAYS
        values = {day: (8.0 if day in {"mon", "tue", "wed", "thu", "fri"}
                        else 0.0) for day in DAYS}
        self.assertEqual(_daily_summary(values),
                         "8h/day (Mon-Fri)")

    def test_custom_mixed(self):
        from gantt_app.resource_model import DAYS
        values = {day: 0.0 for day in DAYS}
        values.update({"mon": 4.0, "tue": 6.0, "wed": 4.0})
        self.assertEqual(_daily_summary(values), "14h/week (custom)")


class TestAllocationStatus(unittest.TestCase):
    """The colour/status classification for a load percentage."""

    def test_free(self):
        status, (bg, fg), dot = allocation_status(0)
        self.assertEqual(status, "Free")
        self.assertEqual(dot, "#22c55e")

    def test_optimal(self):
        status, (bg, fg), dot = allocation_status(80)
        self.assertEqual(status, "Optimal")
        self.assertEqual(dot, "#22c55e")

    def test_full(self):
        status, (bg, fg), dot = allocation_status(100)
        self.assertEqual(status, "Full capacity")
        self.assertEqual(dot, "#eab308")

    def test_over(self):
        status, (bg, fg), dot = allocation_status(120)
        self.assertEqual(status, "Over capacitated")
        self.assertEqual(dot, "#ef4444")


class TestAllocationTag(unittest.TestCase):
    """The tag name used by the DataGrid for background colouring."""

    def test_optimal_tag(self):
        self.assertEqual(_allocation_tag(50), "available")

    def test_full_tag(self):
        self.assertEqual(_allocation_tag(100), "fully_allocated")

    def test_over_tag(self):
        self.assertEqual(_allocation_tag(120), "overallocated")


class TestReadNumber(unittest.TestCase):
    """The float extractor for entry fields."""

    def test_reads_plain_number(self):
        entry = SimpleNamespace(get=lambda: "12.5")
        self.assertEqual(_number(entry, "Hours"), 12.5)

    def test_reads_percent(self):
        entry = SimpleNamespace(get=lambda: "75%")
        self.assertEqual(_number(entry, "Split"), 75.0)

    def test_uses_default_when_empty(self):
        entry = SimpleNamespace(get=lambda: "")
        self.assertEqual(_number(entry, "Hours", default=0.0), 0.0)

    def test_rejects_negative(self):
        entry = SimpleNamespace(get=lambda: "-5")
        with self.assertRaises(ValueError):
            _number(entry, "Hours")

    def test_rejects_non_number(self):
        entry = SimpleNamespace(get=lambda: "abc")
        with self.assertRaises(ValueError):
            _number(entry, "Hours")
