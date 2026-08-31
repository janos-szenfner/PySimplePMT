Feature: Task resource assignments
  Users can assign resources and teams to a task from the Resource tab.

  Background:
    Given a project with resources and teams
    And a task open in the Resource tab

  Scenario: Filter the resource dropdown
    When the user searches for "Core"
    Then the dropdown shows only matching resources or teams

  Scenario: Add a resource to a task
    When the user searches for "Jane"
    And selects the first matching resource
    Then the resource appears in the assignments list

  Scenario: Remove a resource assignment
    Given the task already has a resource assignment
    When the user clears the first assignment
    Then the assignments list is empty

  Scenario: Editing effort updates projected workload
    Given the task already has a resource assignment
    When the user changes the effort to "100"
    Then the workload reflects the new projected load
