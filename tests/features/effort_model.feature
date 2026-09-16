Feature: The Task Type and Effort-Driven fields on the model
  These cover the Task and Project data model rather than the effort
  maths: the new fields default safely, survive a save/load round-trip,
  coerce bad values, and are carried through undo/redo.

  # -- Defaults ----------------------------------------------------------

  Scenario: A new task is fixed units, effort driven, auto scheduled
    Given a plain task
    Then its effort type is fixed units
    And it is effort driven
    And it is not manually scheduled

  Scenario: A new project has an eight-hour day
    Then a new project's hours per day is the default

  # -- Coercion -------------------------------------------------------------

  Scenario: An unknown effort type falls back to fixed units
    Given a task with effort type "Fixed Nonsense"
    Then its effort type is fixed units

  Scenario: Fixed work forces effort driven on
    Given a fixed-work task with effort driven off
    Then it is effort driven

  # -- Round trips -----------------------------------------------------------

  Scenario: The effort fields survive save and load
    Given a fixed-work, effort driven, manually scheduled task
    When the task is saved and loaded again
    Then its effort type is fixed work
    And it is effort driven
    And it is manually scheduled

  Scenario: A plan saved before the feature opens at the defaults
    Given a task saved without the effort fields
    When the task is loaded
    Then its effort type is fixed units
    And it is effort driven
    And it is not manually scheduled

  Scenario: Hours per day survives save and load
    Given a project whose day is 7.5 hours
    When the project is saved and loaded again
    Then its hours per day is 7.5

  Scenario: A missing hours-per-day reads as the default
    Given a project saved without hours per day
    Then its hours per day is the default

  Scenario: A zero or negative day reads as the default
    Then hours per day of 0, -3 and "x" each read as the default

  # -- Undo/redo ---------------------------------------------------------------

  Scenario: Editing another field does not reset the effort type
    Given a tracked project holding a fixed-work task
    When the task is renamed through the tracker
    Then its effort type is still fixed work
    And it is still effort driven

  Scenario: The effort type can be changed through the tracker
    Given a tracked project holding a plain task
    When the task's effort type is set to fixed work through the tracker
    Then the tracked task's effort type is fixed work
