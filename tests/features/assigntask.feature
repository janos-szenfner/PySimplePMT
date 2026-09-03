Feature: Resource assignment task functionality
  Tests for the resource assignment tab and its helper functions.

  Scenario: Resource load with no memberships returns zero used capacity
    When calculating resource load for a resource with no memberships and 40.0 weekly capacity
    Then the used capacity should be 0.0
    And the total capacity should be 40.0

  Scenario: Resource load with memberships calculates used capacity correctly
    When calculating resource load for a resource with team memberships totaling 0.75 and 40.0 weekly capacity
    Then the used capacity should be 30.0
    And the total capacity should be 40.0

  Scenario: Workload text flags overloaded resources
    When calculating workload text for an overloaded resource with 1.5 allocation and 40.0 weekly capacity
    Then the text should contain "60 / 40 hrs"
    And the text should contain "OVERLOADED"
    And the percentage should be 150.0

  Scenario: Workload text flags available resources
    When calculating workload text for an available resource with 0.5 allocation and 40.0 weekly capacity
    Then the text should contain "20 / 40 hrs"
    And the percentage should be 50.0

  Scenario: Task resource tab builds and round-trips existing assignments
    Given a task with resource assignments
    And a task resource tab for that task
    When the tab is created and updated
    Then the tab should return the same assignments as the task

  Scenario: Task resource tab can add and remove assignments
    Given an empty task
    And a task resource tab for that task
    When a team is picked for assignment
    Then the tab should have 1 assignment
    And the assignment resource ID should be "t1"
    When the assignment is removed
    Then the tab should have 0 assignments

  Scenario: Task resource tab rejects duplicate resources
    Given a task with existing resource assignments
    And a task resource tab for that task
    When the same resource is picked again
    Then the tab should still have 1 assignment

  Scenario: Task resource tab dropdown filters on search
    Given a task resource tab with resources
    When the search text is set to "Core"
    And the search is triggered
    Then the dropdown should only show the "t1" resource

  Scenario: Task resource tab enter selects first filtered resource
    Given a task resource tab with resources
    When the search text is set to "Core"
    And the search is triggered
    And the first filtered resource is confirmed
    Then the assignments should include both "r1" and "t1"

  Scenario: Task resource tab effort field change updates assignment
    Given a task resource tab with existing assignments
    When the effort field is changed to 300
    Then the first assignment estimated hours should be 300.0

  Scenario: Task resource tab split field change updates assignment
    Given a task resource tab with existing assignments
    When the split field is changed to 50
    Then the first assignment resource split should be 50.0

  Scenario: Task resource tab assignment cells align
    Given a task with multiple resource assignments
    And a task resource tab for that task
    When the tab is created and updated
    Then all assignment row cells should have the same width and position