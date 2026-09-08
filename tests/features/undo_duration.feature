Feature: Undo and redo task duration changes with dependent tasks
  As a project manager
  I want to undo and redo duration edits
  So that dependent tasks reschedule in both directions and every action is logged.

  Background:
    Given the application is started
    And a project with linked tasks exists

  Scenario: Increasing a predecessor duration pushes the successor later
    When the user changes the duration of "Task 1" to 10 days
    Then "Task 2" starts after "Task 1" finishes

  Scenario: Undo restores the original duration and pulls the successor back
    Given the user has changed the duration of "Task 1" to 10 days
    When the user undoes the last change
    Then "Task 1" has its original duration
    And "Task 2" has its original start date

  Scenario: Redo reapplies the duration change and pushes the successor later again
    Given the user has changed the duration of "Task 1" to 10 days
    And the user has undone the last change
    When the user redoes the last change
    Then "Task 1" has a duration of 10 days
    And "Task 2" starts after "Task 1" finishes

  Scenario: Undo is logged
    Given the user has changed the duration of "Task 1" to 10 days
    When the user undoes the last change
    Then the log contains an undo entry

  Scenario: Manually shortening the predecessor pulls the successor earlier
    Given the user has changed the duration of "Task 1" to 10 days
    When the user changes the duration of "Task 1" to 5 days
    Then "Task 1" has a duration of 5 days
    And "Task 2" has its original start date

  Scenario: Undo logs include the command name
    Given the user has changed the duration of "Task 1" to 10 days
    When the user undoes the last change
    Then the log contains an undo entry
    And the log contains "Update Task"

  Scenario: Redo is logged
    Given the user has changed the duration of "Task 1" to 10 days
    And the user has undone the last change
    When the user redoes the last change
    Then the log contains a redo entry

  Scenario: Undo restores a duration change made in the task editor
    Given the user has opened the task editor for "Task 1"
    When the user changes the dialog duration to 10 days and saves
    Then "Task 1" has a duration of 10 days
    And "Task 2" starts after "Task 1" finishes
    When the user undoes the last change
    Then "Task 2" has its original start date
