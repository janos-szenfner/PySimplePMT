Feature: What "on track" means
  A task's on-track completion is a share of *working* days, not of
  calendar days, and the difference shows up every weekend: a five-day
  task starting on a Friday is 20% through by Sunday, because one of
  its five days has been worked, not 40% because two nights have
  passed.

  The progress toolbar - the five presets, Mark on Track, the
  thresholds and the group styling - needs a display and stays in the
  unittest module.

  The fixture below is a five-working-day task, Monday 17 to Friday 21
  August 2026, and every offset is counted from that Monday.

  Scenario: Work that has not started is at nothing
    # A future task keeps its zero.
    Given the working-week task
    Then on-track a day before it starts is 0

  Scenario: Work whose finish has passed is done
    # The past is complete, whatever it says now.
    Given the working-week task
    Then on-track a week in is 100

  Scenario: The finish day itself counts as done
    # The boundary is "finish on or before the status date".
    Given the working-week task
    Then on-track 4 days in is 100

  Scenario: The first day is one day of five
    # A day worked is a day counted, not a day elapsed.
    Given the working-week task
    Then on-track 0 days in is 20

  Scenario: It climbs a day at a time
    # Monday to Thursday, one fifth each.
    Given the working-week task
    Then on-track the first four days reads "20, 40, 60, 80"

  Scenario: A weekend adds nothing
    # Saturday and Sunday are not worked, so a task sitting across them
    # is no further on by Monday morning than it was on Friday evening.
    Given the working-week task
    Then on-track the weekend days read the same as Friday

  Scenario: A task over a weekend is not ahead of itself
    # A Friday start is a fifth done by Sunday, not two fifths.
    Given the working-week task
    And a task "T2" running "2026-08-21" to "2026-08-27"
    Then "T2" is 20 on-track on "2026-08-23"

  Scenario: A milestone is done or it is not
    # There is no proportion of a moment.
    Given the working-week task
    And a milestone "M1" on "2026-08-19"
    Then "M1" is 0 on-track on "2026-08-17"
    And "M1" is 100 on-track on "2026-08-19"

  Scenario: A holiday shortens both halves of the sum
    # The task's own calendar decides which days were worked. A Tuesday
    # holiday takes a day off the elapsed count and off the total alike:
    # the span Monday to Friday now holds four working days, so Monday
    # alone is a quarter of the task rather than a fifth. Both halves
    # have to use the same calendar or the percentage drifts.
    Given the working-week task
    And "2026-08-18" is a holiday
    Then on-track 0 days in is 25
    And on-track 1 days in is 25
    And on-track 2 days in is 50

  Scenario: A task with no end date is a single day
    # It cannot be part done, so it is not started or it is finished.
    Given the working-week task
    And an open-ended task "T3" starting "2026-08-17"
    Then "T3" is 100 on-track on "2026-08-17"
    And "T3" is 0 on-track on "2026-08-16"

  Scenario: The answer is always a percentage
    # Never below zero, never above a hundred, always whole.
    Given the working-week task
    Then on-track is a whole percentage at every offset tried
