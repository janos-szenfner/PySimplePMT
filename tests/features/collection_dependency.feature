@collection_dependency
Feature: A dependency on a collection row drives the work inside it
  (issue #25)

  Two faults were reported on the same plan:

    * A Task- or Subtask-typed row that had grown children never
      settled: the working-calendar pass rebuilt it from its stored
      duration while the roll-up rebuilt it from its children, and the
      two took turns for every pass of the reschedule loop.
    * A child with no link of its own sat wherever it had been placed,
      ignoring the predecessor set on the collection above it. The
      reporter expected the child to begin when the collection could.

  Scenario: A task with children settles without a cycle warning
    # A "Task" (not a Phase) that has grown children, and carries a
    # stored duration of its own - the shape that used to oscillate.
    Given a task-typed parent of 10 stored days with two children
    When the plan is rescheduled under logging
    Then no "did not settle" warning was logged

  Scenario: Rescheduling again moves nothing
    Given a task-typed parent of 10 stored days with two children
    And the plan is rescheduled
    When the plan is scheduled again
    Then the reschedule reports nothing moved

  Scenario: A link-less child starts when the collection can
    Given the collection plan waiting on UI Mockups
    Then task "F3" starts when task "UX" starts
    And task "F3" starts on 2026-09-14

  Scenario: The collection still spans its children
    Given the collection plan waiting on UI Mockups
    Then task "UX" spans tasks "F1,F3,F2"

  Scenario: A child with its own link is not pulled to the start
    # F2 waits for F3.
    Given the collection plan waiting on UI Mockups
    Then task "F2" does not start when task "UX" starts

  Scenario: The collection plan is stable
    Given the collection plan waiting on UI Mockups
    When the plan is scheduled again
    Then the reschedule reports nothing moved

  Scenario: A collection without a predecessor leaves children alone
    # No predecessor on the collection, so nothing pulls Y forward.
    Given a free collection with children X and Y
    Then task "Y" still starts on 2026-09-21

  Scenario: A top-level task is untouched
    Given a lone top-level task from 2026-09-21
    Then task "T" still starts on 2026-09-21

  Scenario: A child follows the nearest constrained ancestor
    # Outer waits for M (ends 09-11 -> 09-14); an inner sub-phase waits
    # for a later task, so its link-less child follows the inner one.
    Given a nested plan with an outer and an inner constrained ancestor
    Then task "K" starts when task "IN" starts
    And task "K" starts on 2026-09-21
