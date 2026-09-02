"""
pytest-bdd tests for resource settings functionality.

Run with:
    python3 -m pytest tests/test_resourcesettings_bdd.py -v
"""

from types import SimpleNamespace
from pytest_bdd import given, parsers, scenarios, then, when
import pytest

from gantt_app.resource_model import SchedulePattern, DAYS
from gantt_app.views.resourcesettings import (
    _schedule_short,
    _daily_summary,
    allocation_status,
    _allocation_tag,
    _number,
)


# Load the Gherkin scenarios
scenarios("features/resourcesettings.feature")


# SCENARIO: Schedule short names mapping
@then("STANDARD schedule should map to \"Standard (M-F)\"")
def check_standard_schedule_short():
    assert _schedule_short(SchedulePattern.STANDARD) == "Standard (M-F)"


@then("CONTINUOUS schedule should map to \"24/7 Continuous\"")
def check_continuous_schedule_short():
    assert _schedule_short(SchedulePattern.CONTINUOUS) == "24/7 Continuous"


@then("WEEKEND_ONLY schedule should map to \"Weekend Only\"")
def check_weekend_only_schedule_short():
    assert _schedule_short(SchedulePattern.WEEKEND_ONLY) == "Weekend Only"


@then("FULL_WEEK schedule should map to \"Full Week (M-Sun)\"")
def check_full_week_schedule_short():
    assert _schedule_short(SchedulePattern.FULL_WEEK) == "Full Week (M-Sun)"


@then("CUSTOM schedule should map to \"Custom\"")
def check_custom_schedule_short():
    assert _schedule_short(SchedulePattern.CUSTOM) == "Custom"


# SCENARIO: Daily summary for uniform week
@given("a standard weekday capacity of 8 hours", target_fixture="standard_capacity")
def standard_capacity():
    return {day: (8.0 if day in {"mon", "tue", "wed", "thu", "fri"}
                  else 0.0) for day in DAYS}


@then("the daily summary should be \"8h/day (Mon-Fri)\"")
def check_standard_daily_summary(standard_capacity):
    assert _daily_summary(standard_capacity) == "8h/day (Mon-Fri)"


# SCENARIO: Daily summary for custom mixed schedule
@given("a custom daily capacity with mixed hours", target_fixture="custom_capacity")
def custom_capacity():
    values = {day: 0.0 for day in DAYS}
    values.update({"mon": 4.0, "tue": 6.0, "wed": 4.0})
    return values


@then("the daily summary should be \"14h/week (custom)\"")
def check_custom_daily_summary(custom_capacity):
    assert _daily_summary(custom_capacity) == "14h/week (custom)"


# SCENARIO: Allocation status classification
@then("allocation status for 0 percent should be \"Free\" with green dot")
def check_allocation_status_0_percent():
    status, (bg, fg), dot = allocation_status(0)
    assert status == "Free"
    assert dot == "#22c55e"


@then("allocation status for 80 percent should be \"Optimal\" with green dot")
def check_allocation_status_80_percent():
    status, (bg, fg), dot = allocation_status(80)
    assert status == "Optimal"
    assert dot == "#22c55e"


@then("allocation status for 100 percent should be \"Full capacity\" with yellow dot")
def check_allocation_status_100_percent():
    status, (bg, fg), dot = allocation_status(100)
    assert status == "Full capacity"
    assert dot == "#eab308"


@then("allocation status for 120 percent should be \"Over capacitated\" with red dot")
def check_allocation_status_120_percent():
    status, (bg, fg), dot = allocation_status(120)
    assert status == "Over capacitated"
    assert dot == "#ef4444"


# SCENARIO: Allocation tag mapping
@then("allocation tag for 50 percent should be \"available\"")
def check_allocation_tag_50_percent():
    assert _allocation_tag(50) == "available"


@then("allocation tag for 100 percent should be \"fully_allocated\"")
def check_allocation_tag_100_percent():
    assert _allocation_tag(100) == "fully_allocated"


@then("allocation tag for 120 percent should be \"overallocated\"")
def check_allocation_tag_120_percent():
    assert _allocation_tag(120) == "overallocated"


# SCENARIO: Number parsing from entry fields
@then("reading plain number \"12.5\" should return 12.5")
def check_number_parsing_plain():
    entry = SimpleNamespace(get=lambda: "12.5")
    assert _number(entry, "Hours") == 12.5


@then("reading percent \"75%\" should return 75.0")
def check_number_parsing_percent():
    entry = SimpleNamespace(get=lambda: "75%")
    assert _number(entry, "Split") == 75.0


@then("reading empty with default 0.0 should return 0.0")
def check_number_parsing_empty_with_default():
    entry = SimpleNamespace(get=lambda: "")
    assert _number(entry, "Hours", default=0.0) == 0.0


@then("reading negative number \"-5\" should raise ValueError")
def check_number_parsing_negative_raises_error():
    entry = SimpleNamespace(get=lambda: "-5")
    with pytest.raises(ValueError):
        _number(entry, "Hours")


@then("reading non-number \"abc\" should raise ValueError")
def check_number_parsing_non_number_raises_error():
    entry = SimpleNamespace(get=lambda: "abc")
    with pytest.raises(ValueError):
        _number(entry, "Hours")