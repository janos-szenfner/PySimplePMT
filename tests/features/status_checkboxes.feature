Feature: Status as two checkboxes - Estimated and Inactive
  The Status dropdown became an Estimated checkbox and an Inactive
  checkbox. The single status field still drives the grid, the chart
  and the KPIs, and is derived from the two boxes - both ticked reads
  as Inactive, while the Estimated tick is remembered so clearing
  Inactive returns to Estimated.

  # -- The model flag -------------------------------------------------------

  Scenario: A new task is active and not estimated
    Given a plain task
    Then its status is "Active"
    And it is not estimated

  Scenario: An Estimated status implies the flag
    Given a task with status "Estimated"
    Then it is estimated

  Scenario: Inactive can remember estimated
    Given an inactive task that remembers estimated
    Then its status is "Inactive"
    And it is estimated

  Scenario: The flag survives save and load
    Given an inactive task that remembers estimated
    When the task is saved and loaded again
    Then its status is "Inactive"
    And it is estimated

  Scenario: An old estimated file backfills the flag
    Given a task saved as "Estimated" without the flag
    When the task is loaded
    Then it is estimated

  # -- The editor ------------------------------------------------------------

  Scenario: An active task opens with both boxes clear
    Given the task editor is open on an "Active" task
    Then the estimated box is clear
    And the inactive box is clear
    And the status reads "Active"

  Scenario: An estimated task opens with estimated ticked
    Given the task editor is open on an "Estimated" task
    Then the estimated box is ticked
    And the inactive box is clear
    And the status reads "Estimated"

  Scenario: Both ticked reads as inactive
    Given the task editor is open on an inactive task that remembers estimated
    Then the estimated box is ticked
    And the inactive box is ticked
    And the status reads "Inactive"

  Scenario: Clearing inactive returns to estimated
    Given the task editor is open on an inactive task that remembers estimated
    When the inactive box is cleared
    Then the status reads "Estimated"
    And the estimated flag is still held

  Scenario: Clearing both is active
    Given the task editor is open on an inactive task that remembers estimated
    When the inactive box is cleared
    And the estimated box is cleared
    Then the status reads "Active"
