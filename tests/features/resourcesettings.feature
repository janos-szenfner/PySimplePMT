Feature: Resource settings functionality
  Tests for the helper functions in gantt_app.views.resourcesettings

  @resourcesettings
  Scenario: Schedule short names mapping
    Then STANDARD schedule should map to "Standard (M-F)"
    And CONTINUOUS schedule should map to "24/7 Continuous"
    And WEEKEND_ONLY schedule should map to "Weekend Only"
    And FULL_WEEK schedule should map to "Full Week (M-Sun)"
    And CUSTOM schedule should map to "Custom"

  @resourcesettings
  Scenario: Daily summary for uniform week
    Given a standard weekday capacity of 8 hours
    Then the daily summary should be "8h/day (Mon-Fri)"

  @resourcesettings
  Scenario: Daily summary for custom mixed schedule
    Given a custom daily capacity with mixed hours
    Then the daily summary should be "14h/week (custom)"

  @resourcesettings
  Scenario: Allocation status classification
    Then allocation status for 0 percent should be "Free" with green dot
    And allocation status for 80 percent should be "Optimal" with green dot
    And allocation status for 100 percent should be "Full capacity" with yellow dot
    And allocation status for 120 percent should be "Over capacitated" with red dot

  @resourcesettings
  Scenario: Allocation tag mapping
    Then allocation tag for 50 percent should be "available"
    And allocation tag for 100 percent should be "fully_allocated"
    And allocation tag for 120 percent should be "overallocated"

  @resourcesettings
  Scenario: Number parsing from entry fields
    Then reading plain number "12.5" should return 12.5
    And reading percent "75%" should return 75.0
    And reading empty with default 0.0 should return 0.0
    And reading negative number "-5" should raise ValueError
    And reading non-number "abc" should raise ValueError