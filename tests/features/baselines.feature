Feature: Baseline Management Engine
  The engine captures, stores and compares up to 10 schedule baselines
  and reports variance across dates, duration, effort and cost.

  Scenario: Ten baseline slots are available by default
    Given a new baseline manager
    Then there are 10 baseline slots
    And the first slot is named "Baseline 1"

  Scenario: Rename a baseline slot
    Given a new baseline manager
    When the user renames slot 1 to "Initial Approved Scope"
    Then slot 1 is named "Initial Approved Scope"

  Scenario: Set an entire project baseline
    Given a project with two tasks
    And a new baseline manager
    When the user sets baseline 1 for the entire project
    Then baseline 1 contains 2 task snapshots
    And baseline 1 is active

  Scenario: Set a baseline for selected tasks only
    Given a project with two tasks
    And a new baseline manager
    When the user sets baseline 1 for the selected task "Task A"
    Then baseline 1 contains 1 task snapshots

  Scenario: Roll up baseline to parent container
    Given a project with a parent task and two child tasks
    And a new baseline manager
    When the user sets baseline 1 for the child tasks with roll-up
    Then the parent task in baseline 1 starts on the earliest child start
    And the parent task in baseline 1 finishes on the latest child finish

  Scenario: Clear a baseline
    Given a project with two tasks
    And a new baseline manager with baseline 1 set
    When the user clears baseline 1
    Then baseline 1 is unset

  Scenario: Compare current project to baseline
    Given a project with a task scheduled for 2026-01-01 to 2026-01-02
    And a new baseline manager with baseline 1 set
    When the task is moved to start on 2026-01-05 and end on 2026-01-06
    Then the start variance is +2 working days
    And the duration variance is 0

  Scenario: Work and cost variance
    Given a project with a 10 hour task assigned to a resource costing 50 per hour
    And a new baseline manager with baseline 1 set
    When the task work is increased to 20 hours
    Then the work variance is +10.0 hours
    And the cost variance is +500.0

  Scenario: Persist baselines through serialization
    Given a new baseline manager with slot 1 renamed to "Scope"
    When the manager is serialized and restored
    Then slot 1 is still named "Scope"
