Feature: Advanced tab constraints and deadlines
  From advanced-tab-gherkin and advancede2e-gherkin. The Advanced tab's
  deadline and constraint are extra planner settings: they are stored, saved
  with the project, and drawn on the Gantt chart, but - by design, so they
  cannot break existing behaviour - they do not drive the scheduler. The
  scheduler stays dependency-driven, and a constraint's "expected behaviour"
  here is therefore read as "recorded and shown, schedule unchanged". Dates
  are the application's working-day dates (no intraday time), so the source
  timestamps are read as their calendar day.

  Background:
    Given a project scheduled from "2026-10-01"

  # --- The full constraint matrix: stored, serialized, and drawn -----------

  Scenario Outline: Every dated constraint is stored, serialized and marked
    Given a two-day task "T" with constraint "<enum>" on "<date>"
    Then the task's constraint type is "<enum>"
    And the task's constraint date is "<date>"
    And the reloaded task's constraint date is "<date>"
    And the Gantt shows a "<marker>" marker in "<color>" for "T"

    Examples:
      | enum | date       | marker             | color   |
      | SNET | 2026-10-05 | constraint_bracket | #3498DB |
      | SNLT | 2026-10-07 | constraint_bracket | #3498DB |
      | FNET | 2026-10-06 | constraint_bracket | #3498DB |
      | FNLT | 2026-10-08 | constraint_bracket | #3498DB |
      | MSO  | 2026-10-12 | constraint_lock    | #E74C3C |
      | MFO  | 2026-10-14 | constraint_lock    | #E74C3C |

  Scenario: As Late As Possible carries no date but still draws a bracket
    Given a two-day task "T" with constraint "ALAP"
    Then the task's constraint date is not set
    And the Gantt shows a "constraint_bracket" marker in "#3498DB" for "T"

  # --- Constraints drive the schedule (CPM enforcement) --------------------

  Scenario: A Must Start On constraint overrides the dependency and drives the date
    Given task "A" of 3 working days and task "B" of 2 working days
    And "B" has a "FS" link to "A"
    And the plan is rescheduled
    When "B" is given a "MSO" constraint on "2026-10-01"
    And the plan is rescheduled
    Then "B" starts on "2026-10-01"

  Scenario: A Start No Earlier Than floor pushes a task later
    Given task "A" of 3 working days and task "B" of 2 working days
    And the plan is rescheduled
    When "B" is given a "SNET" constraint on "2026-10-09"
    And the plan is rescheduled
    Then "B" starts on "2026-10-09"

  Scenario: A No-Later constraint bounds the late dates without moving the task
    Given task "A" of 3 working days and task "B" of 2 working days
    And "B" has a "FS" link to "A"
    And the plan is rescheduled
    And "B"'s start is remembered
    When "B" is given a "FNLT" constraint on "2026-10-20"
    And the plan is rescheduled
    Then "B"'s start is unchanged

  # --- Deadline: slip visual and reset -------------------------------------

  Scenario: A finish past the deadline is flagged, and reset clears it
    Given a two-day task "T" starting "2026-10-05"
    And "T" has a deadline of "2026-10-01"
    Then the "T" bar is marked slipped
    And the deadline marker for "T" is red
    When the deadline for "T" is reset to N/A
    Then the "T" bar is not marked slipped
    And there is no deadline marker for "T"

  # --- Persistence: saved with the project ---------------------------------

  Scenario: The deadline and constraint survive a project save and load
    Given a two-day task "T" with constraint "MFO" on "2026-10-09"
    And "T" has a deadline of "2026-10-08"
    When the project is saved and loaded from disk
    Then the reloaded "T" has constraint "MFO" on "2026-10-09"
    And the reloaded "T" has a deadline of "2026-10-08"

  # --- Undo/redo of an Advanced-tab change ---------------------------------

  Scenario: Changing a deadline is one atomic undo/redo step
    Given a two-day task "T" starting "2026-10-01"
    When a deadline of "2026-10-20" is applied to "T" through the tracker
    Then "T" has a deadline of "2026-10-20"
    When the change is undone
    Then "T" has no deadline
    When the change is redone
    Then "T" has a deadline of "2026-10-20"

  # --- Conflict resolution (CPM §3) ----------------------------------------

  Scenario: A Must Finish On earlier than a predecessor allows is a conflict
    Given task "A" of 5 working days and task "B" of 2 working days
    And "B" has a "FS" link to "A"
    And the plan is rescheduled
    When "B" is given a "MFO" constraint on "2026-10-02"
    Then "B" is reported in conflict with predecessor "A"
    And "B" is flagged at negative float
    And the "B" bar is marked slipped

  Scenario: A Finish No Later Than the links can meet is no conflict
    Given task "A" of 5 working days and task "B" of 2 working days
    And "B" has a "FS" link to "A"
    And the plan is rescheduled
    When "B" is given a "FNLT" constraint on "2026-12-31"
    Then "B" is not reported in conflict
    And no task is flagged at negative float

  @needs_display
  Scenario: The conflict dialog offers Keep and Cancel
    Given a conflict report for a task
    Then answering the conflict dialog "keep" returns "keep"
    And answering the conflict dialog "cancel" returns "cancel"

  @needs_display
  Scenario: Cancelling a constraint reverts the Advanced tab to N/A
    Given an Advanced tab set to Must Finish On
    When the tab is reverted to N/A
    Then the tab's chosen constraint is "NA"
    And the tab reports no constraint date

  # --- Bulk: each task keeps its own constraint ----------------------------

  Scenario: Constraints applied across a selection persist per task
    Given tasks "T-10", "T-11" and "T-12" each of 2 working days
    When each is given a "MSO" constraint on "2026-10-05"
    And the project is saved and loaded from disk
    Then each of "T-10", "T-11", "T-12" has constraint "MSO" on "2026-10-05"
