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
