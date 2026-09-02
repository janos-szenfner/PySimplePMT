Feature: Toolbar duration functionality
  Tests that the duration entered when creating a task is the duration created

  @toolbar_duration
  Scenario: Created task duration matches the request
    Given a start date of 2024-01-01
    When creating tasks with various requested durations
    Then the task duration should match the requested duration

  @toolbar_duration
  Scenario: Single day task starts and ends together
    Given a start date of 2024-01-01
    When creating a task with duration of 1 day
    Then the task start_date should equal end_date
    And the task duration_days should be 1

  @toolbar_duration
  Scenario: Task duration agrees with the mermaid importer
    Given a start date of 2024-01-01
    When creating tasks and importing tasks with same durations
    Then the created and imported tasks should have the same end dates
    And the created and imported tasks should have the same duration days

  @toolbar_duration
  Scenario: Subtask duration matches the request
    Given a start date of 2024-01-01
    When creating a parent task and subtasks with various durations
    Then the subtask duration should match the requested duration