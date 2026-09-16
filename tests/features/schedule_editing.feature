@schedule_editing
Feature: Editing the start, end and duration (issues #23 and #31)

  The scheduling-options mode is gone: all three fields are editable,
  and Project.reconcile_schedule settles the other two when one
  changes -

    * a new Duration moves the End, the Start held;
    * a new End moves the Start, the Duration held;
    * a new Start sets a Start No Earlier Than and the Duration
      follows, the End held.

  The grid edits the same three cells in place through the same rules.

  A plain Monday-to-Friday plan; the fixture task runs Mon 5 - Fri 9
  Oct 2026, five working days.

  Scenario: A new duration moves the end and holds the start
    Given a task from 2026-10-05 to 2026-10-09 for 5 days
    When the schedule is reconciled with duration 8
    Then the reconciled start is 2026-10-05
    And the reconciled duration is 8
    And the reconciled end is 2026-10-14
    And no floor is set

  Scenario: A new end moves the start and holds the duration
    Given a task from 2026-10-05 to 2026-10-09 for 5 days
    When the schedule is reconciled with end 2026-10-16
    Then the reconciled end is 2026-10-16
    And the reconciled duration is 5
    And the reconciled start is 2026-10-12
    And no floor is set

  Scenario: A new start sets a floor and recomputes the duration
    Given a task from 2026-10-05 to 2026-10-09 for 5 days
    When the schedule is reconciled with start 2026-10-07
    Then the reconciled start is 2026-10-07
    And the reconciled end is 2026-10-09
    And the reconciled duration is 3
    And the floor is 2026-10-07

  Scenario: A start past the end keeps at least a day
    Given a task from 2026-10-05 to 2026-10-09 for 5 days
    When the schedule is reconciled with start 2026-10-19
    Then the reconciled start is 2026-10-19
    And the reconciled duration is 1
    And the reconciled end is 2026-10-19
    And the floor is 2026-10-19

  Scenario: No change returns the task as it was
    Given a task from 2026-10-05 to 2026-10-09 for 5 days
    When the schedule is reconciled unchanged
    Then the reconciled row reads 2026-10-05 to 2026-10-09 for 5 days
    And no floor is set

  Scenario: Start takes precedence when more than one changed
    # Both start and end retyped: the start rule wins, holding the
    # new end.
    Given a task from 2026-10-05 to 2026-10-09 for 5 days
    When the schedule is reconciled with start 2026-10-06 and end 2026-10-15
    Then the reconciled start is 2026-10-06
    And the reconciled end is 2026-10-15
    And the floor is 2026-10-06

  Scenario: A milestone start sets a floor and no length
    Given a milestone on 2026-10-05
    When the milestone is reconciled to start 2026-10-09
    Then the reconciled start is 2026-10-09
    And the reconciled end is empty
    And the reconciled duration is 0
    And the floor is 2026-10-09

  Scenario: Setting the duration in the grid moves the end
    # update_task rebuilds the task, so it is read back from the plan.
    Given a task list over the five-day task
    When the grid sets duration 8 and end 2026-10-14
    Then task "T" has duration 8
    And task "T" ends on 2026-10-14
    And task "T" starts on 2026-10-05

  Scenario: Setting the start in the grid pins a start-no-earlier-than
    Given a task list over the five-day task
    When the grid sets start 2026-10-07 with a floor
    Then task "T" is constrained "SNET" to 2026-10-07

  Scenario: A grid schedule edit is one undo step
    Given a task list over the five-day task
    When the grid sets duration 8 and end 2026-10-14
    Then task "T" has duration 8
    When the edit is undone
    Then task "T" has duration 5

  Scenario: A container cell is not typed in place
    Given a task list over the five-day task
    And a phase "P1" holding task "T"
    Then the "Start" cell of "P1" is not editable
    And the "Duration" cell of "T" is editable
