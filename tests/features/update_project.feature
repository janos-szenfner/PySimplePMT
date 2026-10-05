Feature: Update Project reschedules uncompleted work behind a line
  The status date is only a marker; this is the action that catches the
  plan up to it, the way Microsoft Project's Update Project window does.
  Only its 'Reschedule uncompleted work' half exists - marking work
  complete is Mark on Track's job - and it runs over the whole plan.

  Background:
    Given a plan

  Scenario: An unstarted task begins on the line
    Given a task "Planned" running "2026-01-05" to "2026-01-09"
    When uncompleted work is rescheduled behind "2026-01-15"
    Then the moved count is 1
    And the task "Planned" starts on "2026-01-15"

  Scenario: A rescheduled task keeps its working duration
    # Five working days from Thursday is next Wednesday.
    Given a task "Planned" running "2026-01-05" to "2026-01-09"
    When uncompleted work is rescheduled behind "2026-01-15"
    Then the task "Planned" ends on "2026-01-21"

  Scenario: A task already past the line stays
    Given a task "Later" running "2026-02-02" to "2026-02-06"
    When uncompleted work is rescheduled behind "2026-01-15"
    Then the moved count is 0
    And the task "Later" starts on "2026-02-02"

  Scenario: A line on a weekend resumes on Monday
    # The row begins on the next working day, not on a Saturday.
    Given a task "Planned" running "2026-01-05" to "2026-01-09"
    When uncompleted work is rescheduled behind "2026-01-17"
    Then the task "Planned" starts on "2026-01-19"

  Scenario: An unstarted milestone moves to the line
    Given a milestone "Kick" on "2026-01-08"
    When uncompleted work is rescheduled behind "2026-01-15"
    Then the moved count is 1
    And the task "Kick" starts on "2026-01-15"

  Scenario: An overdue underway task pushes its remainder
    # Half of a five-day task is still to do, so two working days of it
    # resume on the line - the worked part keeps its dates in the past.
    Given a task "Late" running "2026-01-05" to "2026-01-09" at 50%
    When uncompleted work is rescheduled behind "2026-01-15"
    Then the moved count is 1
    And the task "Late" starts on "2026-01-05"
    And the task "Late" ends on "2026-01-16"

  Scenario: An underway task running through the line stays
    Given a task "Running" running "2026-01-12" to "2026-01-30" at 50%
    When uncompleted work is rescheduled behind "2026-01-15"
    Then the moved count is 0
    And the task "Running" ends on "2026-01-30"

  Scenario: Done, inactive and pinned rows stay
    Given a task "Done" running "2026-01-05" to "2026-01-09" at 100%
    And an inactive task "Shelved" running "2026-01-05" to "2026-01-09"
    And a task "Pinned" running "2026-01-05" to "2026-01-09" must start on "2026-01-05"
    When uncompleted work is rescheduled behind "2026-01-15"
    Then the moved count is 0
    And the task "Done" starts on "2026-01-05"
    And the task "Shelved" starts on "2026-01-05"
    And the task "Pinned" starts on "2026-01-05"

  Scenario: Summaries follow their children
    # A container is never moved directly - its dates are its
    # children's, rolled up after they move.
    Given a phase "Phase" running "2026-01-05" to "2026-01-30"
    And a task "Inside" running "2026-01-05" to "2026-01-09" inside "Phase"
    When uncompleted work is rescheduled behind "2026-01-15"
    Then the task "Phase" starts on "2026-01-15"

  Scenario: Successors settle after the move
    # A task pushed past the line drags the links waiting on it.
    Given a task "First" running "2026-01-05" to "2026-01-09"
    And a task "Second" running "2026-01-12" to "2026-01-14" after "First"
    When uncompleted work is rescheduled behind "2026-01-15"
    Then the task "Second" starts after the task "First" ends

  Scenario: Nothing to move reports zero
    Given a task "Later" running "2026-02-02" to "2026-02-06"
    When uncompleted work is rescheduled behind "2026-01-15"
    Then the moved count is 0

  # ---- the edges the cases above leave open -----------------------------

  Scenario: No line at all moves nothing
    # The window can be called without a date; nothing happens.
    Given a task "Planned" running "2026-01-05" to "2026-01-09"
    When uncompleted work is rescheduled behind no line
    Then the moved count is 0
    And the task "Planned" starts on "2026-01-05"

  Scenario: A task with no dates is skipped
    Given a task "Undated" with no dates
    When uncompleted work is rescheduled behind "2026-01-15"
    Then the moved count is 0

  Scenario: A task starting exactly on the line stays
    # start >= line is not "behind" - the line is where it resumes, not a
    # day it must clear.
    Given a task "OnLine" running "2026-01-15" to "2026-01-16"
    When uncompleted work is rescheduled behind "2026-01-15"
    Then the moved count is 0
    And the task "OnLine" starts on "2026-01-15"

  Scenario: An underway task finishing exactly on the line stays
    # finish < line is strict: ending on the line is not behind it.
    Given a task "Tight" running "2026-01-12" to "2026-01-15" at 50%
    When uncompleted work is rescheduled behind "2026-01-15"
    Then the moved count is 0
    And the task "Tight" ends on "2026-01-15"

  Scenario: An underway task with no finish date pushes its remainder
    # With no end date the start stands in for the finish, and the row is
    # behind the line - so its remaining day resumes on it.
    Given a task "Open" starting "2026-01-05" at 50%
    When uncompleted work is rescheduled behind "2026-01-15"
    Then the moved count is 1
    And the task "Open" starts on "2026-01-05"
    And the task "Open" ends on "2026-01-15"

  Scenario: A must-finish-on pin stays too
    # MSO is pinned in the scenario above; MFO is the other hard kind.
    Given a task "Pinned" running "2026-01-05" to "2026-01-09" must finish on "2026-01-09"
    When uncompleted work is rescheduled behind "2026-01-15"
    Then the moved count is 0
    And the task "Pinned" ends on "2026-01-09"

  Scenario: The remainder never rounds down to nothing
    # 99% of five days rounds to zero working days; the floor is one, so
    # the row still gets a day on the line rather than no answer.
    Given a task "Nearly" running "2026-01-05" to "2026-01-09" at 99%
    When uncompleted work is rescheduled behind "2026-01-15"
    Then the moved count is 1
    And the task "Nearly" ends on "2026-01-15"
