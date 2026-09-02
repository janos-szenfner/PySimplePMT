Feature: Subtask creation and multi-row movement
  Creating a subtask uses the selected task as its parent, and task movement
  applies to every selected row.

  Background:
    Given a project with four root tasks
    And the task list and toolbar are open

  Scenario: Create a subtask under the selected task
    Given the second root task is selected
    When the user creates and saves a subtask named "Selected Child"
    Then "Selected Child" exists in the project
    And "Selected Child" is a child of the second root task
    And "Selected Child" appears directly under the second root task

  Scenario: Cancelling subtask creation changes nothing
    Given the second root task is selected
    When the user cancels subtask creation
    Then the project still contains four tasks

  Scenario: A milestone cannot become a subtask parent
    Given the selected row is a milestone
    When the user requests a new subtask
    Then the parent chooser is used instead of the milestone

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
