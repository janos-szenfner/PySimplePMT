Feature: Utility functions and project helper functionality
  Core functionality for project utilities, task serialization, and critical path calculations

  Background:
    Given a base date of "2024-01-01"

  @utils
  Scenario: Project date calculation with multiple tasks
    Given a project with tasks having different start dates
    Then the project start_date should be the earliest task start
    And the project end_date should be the latest task end

  @utils
  Scenario: Project empty dates
    Given an empty project for date testing
    Then the project start_date should be None
    And the project end_date should be None

  @utils
  Scenario: Project single task dates
    Given a project with a single task for date testing
    Then the project start_date should be the task start
    And the project end_date should be the task end

  @utils
  Scenario: Circular dependency detection
    Given a project with circular dependencies
    When getting dependencies for a task in the circle
    Then it should return only direct dependencies without infinite loop

  @utils
  Scenario: Complex dependency chains
    Given a project with complex dependency chains
    When getting dependencies for a task with multiple dependencies in complex chains
    Then it should return all direct dependencies

  @utils
  Scenario: Complex dependency chain dependents
    Given a project with complex dependency chains for dependents testing
    When getting dependents for a task
    Then it should return all dependent tasks

  @utils
  Scenario: Task duration calculation for various date ranges
    Given tasks with various date ranges
    Then the duration should be calculated correctly for each task

  @utils
  Scenario: Task serialization roundtrip preserves all fields
    Given a regular task with all fields set
    When serialized to dict and deserialized back to task
    Then all fields should be preserved correctly

  @utils
  Scenario: Milestone serialization roundtrip
    Given a milestone with all fields set
    When serialized to dict and deserialized back to milestone
    Then all milestone fields should be preserved correctly

  @utils
  Scenario: Empty project critical path
    Given an empty project
    Then the critical path should be empty

  @utils
  Scenario: Single task critical path
    Given a project with a single task
    Then the critical path should contain that task

  @utils
  Scenario: Parallel tasks critical path
    Given a project with parallel tasks
    Then the critical path should include the longest task

  @utils
  Scenario: Complex network critical path
    Given a project with complex dependency network
    Then the critical path should follow the longest dependency chain