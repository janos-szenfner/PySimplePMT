Feature: Multi-row movement
  Task movement applies to every selected row. The creation scenarios that
  used to live here went with the Subtask type (issue #63): a row goes
  under another by being indented or pasted as a sub-task, not by being
  created as a Subtask.

  Background:
    Given a project with four root tasks
    And the task list and toolbar are open

  Scenario: Move two selected tasks up together
    Given the second and third root tasks are selected
    When Move Up is invoked on the third selected task
    Then the root task order is "Second, Third, First, Fourth"
    And the second and third root tasks remain selected

  Scenario: Move two selected tasks down together
    Given the second and third root tasks are selected
    When Move Down is invoked on the second selected task
    Then the root task order is "First, Fourth, Second, Third"
    And the second and third root tasks remain selected

  Scenario: Move two selected tasks to the top together
    Given the third and fourth root tasks are selected
    When Move to Top is invoked on the fourth selected task
    Then the root task order is "Third, Fourth, First, Second"

  Scenario: Move two selected tasks to the bottom together
    Given the first and second root tasks are selected
    When Move to Bottom is invoked on the first selected task
    Then the root task order is "Third, Fourth, First, Second"

  Scenario: Moving a selected parent and child moves the branch once
    Given the second root task has a child
    And the second root task and its child are selected
    When Move Up is invoked on the second selected task
    Then the second root task branch appears before the first root task
    And the child remains under the second root task

  Scenario: A selected group at the top does not reverse itself
    Given the first and second root tasks are selected
    When Move Up is invoked on the second selected task
    Then the root task order is "First, Second, Third, Fourth"

  Scenario: Non-adjacent selected tasks each move up
    Given the second and fourth root tasks are selected
    When Move Up is invoked on the fourth selected task
    Then the root task order is "Second, First, Fourth, Third"
    And the second and fourth root tasks remain selected

  Scenario: Moving selected rows can be undone as one action
    Given the second and third root tasks are selected
    When Move Up is invoked on the third selected task
    And the move is undone
    Then the root task order is "First, Second, Third, Fourth"
