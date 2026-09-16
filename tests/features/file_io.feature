@file_io
Feature: Saving and loading a project as JSON

  Scenario: Saving writes the file
    Given a two-task project
    When the project is saved to "test_project.json"
    Then the save answered True and the file exists

  Scenario: Saving creates parent directories
    Given a two-task project
    When the project is saved to "nested/dir/test_project.json"
    Then the save answered True and the file exists

  Scenario: Loading reads a saved project back
    Given a two-task project saved to "test_project.json"
    When the file is loaded
    Then the loaded project is "Test Project" with 2 tasks
    And its tasks are named "Task 1" and "Task 2"

  Scenario: A save and load preserves every field
    Given a two-task project
    When the project is saved to "roundtrip_project.json"
    And the file is loaded
    Then every task field survived the round trip

  Scenario: Resources are saved inside the project JSON
    Given a two-task project with a named resource in a team
    When the project is saved to "project_with_resources.json"
    Then the JSON holds "John Doe" and "Core QA" and no sidecar file

  Scenario: Resources load back into the project
    Given a two-task project with a generic resource in a team
    When the project is saved to "resource_roundtrip.json"
    And the file is loaded
    Then the resource pool holds "DevOps Engineer #1" and "Infrastructure"
    And the membership is 40 percent

  Scenario: A legacy project without resources loads an empty pool
    Given a two-task project
    When the project dictionary loses its resources and teams
    Then the rebuilt project's pools are empty

  Scenario: A missing file loads as nothing
    Given a two-task project
    When "nonexistent.json" is loaded
    Then nothing was loaded

  Scenario: Invalid JSON loads as nothing
    Given a file "invalid.json" holding "{ invalid json }"
    When "invalid.json" is loaded
    Then nothing was loaded

  Scenario: Milestones survive a round trip
    Given a task and a milestone project
    When the project is saved to "milestone_project.json"
    And the file is loaded
    Then the loaded project has 2 tasks
    And the milestone is "Review" with no end date

  Scenario: A task with no end date survives a round trip
    Given a project with a task that has no end date
    When the project is saved to "no_end_date.json"
    And the file is loaded
    Then the loaded task has no end date

  Scenario: The saved file is well-formed JSON
    Given a two-task project saved to "valid_json.json"
    Then the file parses with the project and task fields

  Scenario: The status field is saved and loaded
    Given a project with an Inactive task
    When the project is saved to "status.json"
    And the file is loaded
    Then the loaded task's status is "Inactive"

  Scenario: A legacy file without status loads as Active
    Given a legacy project file without a status field
    When "legacy.json" is loaded
    Then the loaded task's status is "Active"

  Scenario: The save convenience function writes the file
    Given a one-task project
    When the project is saved to "convenience_save.json" through the helper
    Then the save answered True and the file exists

  Scenario: The load convenience function reads the file
    Given a one-task project saved to "convenience_load.json"
    When the file is loaded through the helper
    Then the loaded project is "Test Project"

  Scenario: Datetimes serialize to ISO strings
    When a task built at 2024-01-15T10:30:45 to 2024-02-20T14:20:00 is dictified
    Then the dates read "2024-01-15T10:30:45" and "2024-02-20T14:20:00"

  Scenario: ISO strings deserialize to datetimes
    When a task dictionary is built from ISO dates
    Then the task dates are 2024-01-15T10:30:45 and 2024-02-20T14:20:00
