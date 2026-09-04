Feature: Task and Project model functionality
  Core functionality for creating, managing, and serializing tasks and projects

  Background:
    Given a base date of "2024-01-01"

  @models
  Scenario: Create a basic task
    Given a task with id, name, start_date, and end_date
    Then the task should have the correct id
    And the task should have the correct name
    And the task should have the correct start_date
    And the task should have the correct end_date
    And the task progress should default to 0
    And the task dependencies should default to empty list
    And the task color should default to "#1f6aa5"
    And the task should not be a milestone

  @models
  Scenario: Create task using factory method
    Given a task created with Task.create_task
    Then the task should have an auto-generated factory id
    And the task should have the specified factory name
    And the task should have the specified factory dates
    And the task should have the specified factory color
    And the task should have the specified factory progress
    And the task should have the specified factory dependencies
    And the task should not be a factory milestone

  @models
  Scenario: Create milestone using factory method
    Given a milestone created with Task.create_milestone
    Then the milestone should have an auto-generated milestone id
    And the milestone should have the specified milestone name
    And the milestone should have the specified milestone date as start_date
    And the milestone end_date should be None
    And the milestone should have the specified milestone color
    And the milestone should have the specified milestone dependencies
    And the milestone should be marked as a milestone

  @models
  Scenario: A task may be created with an empty name
    When creating a task with an empty name
    Then the task should be created with a blank name

  @models
  Scenario: Task validation - invalid progress low
    When creating a task with progress -1
    Then a ValueError should be raised

  @models
  Scenario: Task validation - invalid progress high
    When creating a task with progress 101
    Then a ValueError should be raised

  @models
  Scenario: Milestone end_date handling
    Given a milestone with end_date initially set
    Then the end_date should be None after creation

  @models
  Scenario: Task duration calculation within one week
    Given a task spanning Monday to Friday
    Then the duration should be 5 days
    And the total elapsed days should be 5 days

  @models
  Scenario: Task duration calculation over weekend
    Given a task spanning 10 calendar days including weekend
    Then the duration should be 8 working days
    And the total elapsed days should be 10 days

  @models
  Scenario: Manual duration overrides date calculation
    Given a task with explicit duration of 3 days
    Then the duration_days should be 3

  @models
  Scenario: Milestone duration is always zero
    Given a milestone
    Then the duration_days should be 0

  @models
  Scenario: Task with no end date has no duration
    Given a task with end_date None
    Then the duration_days should be None

  @models
  Scenario: Project creation with empty task list
    Given an empty project
    Then the project name should be correct
    And the project tasks should be empty
    And the project start_date should be None
    And the project end_date should be None

  @models
  Scenario: Project creation with tasks
    Given a project with multiple tasks
    Then the project should contain the created tasks
    And the project start_date should be the earliest task start
    And the project end_date should be the latest task end

  @models
  Scenario: Add task to project
    Given a project
    When a task is added to the project
    Then the project should contain the task
    And the project start_date should be the task start
    And the project end_date should be the task end

  @models
  Scenario: Add multiple tasks to project
    Given a project
    When multiple tasks are added
    Then the project should contain all added tasks
    And the project start_date should be the earliest start
    And the project end_date should be the latest end

  @models
  Scenario: Remove task from project
    Given a project with tasks
    When a task is removed from the project
    Then the project should no longer contain the task
    And removing non-existent task should return False

  @models
  Scenario: Remove task updates dependencies
    Given a project with dependent tasks
    When the predecessor task is removed
    Then the dependent task should have no dependencies

  @models
  Scenario: Get task by ID
    Given a project with tasks
    When getting a task by its ID
    Then the correct task should be returned
    And getting non-existent task should return None

  @models
  Scenario: Get dependencies for a task
    Given a project with dependent tasks
    When getting dependencies for a dependent task
    Then all direct dependencies should be returned

  @models
  Scenario: Get dependents for a task
    Given a project with dependent tasks
    When getting dependents for a predecessor task
    Then all dependent tasks should be returned

  @models
  Scenario: Task serialization to dict
    Given a task with all fields for serialization
    When serialized to dict with all fields
    Then the dict should contain all fields with correct values

  @models
  Scenario: Task deserialization from dict
    Given a task dictionary for deserialization
    When deserialized to Task object
    Then all task fields should be correctly restored

  @models
  Scenario: Project serialization to dict
    Given a project with tasks for serialization
    When serialized to dict
    Then the dict should contain project name, tasks, start_date, and end_date

  @models
  Scenario: Project deserialization from dict
    Given a project dictionary
    When deserialized to Project object
    Then all project fields should be correctly restored

  @models
  Scenario: Task status defaults to Active
    Given a task without status specified
    Then the created task status should default to "Active"

  @models
  Scenario: Task accepts valid status values
    Given valid status values "Estimated" and "Inactive"
    When creating tasks with these statuses
    Then the tasks should have the specified statuses

  @models
  Scenario: Task status invalid defaults to Active
    Given an invalid status value
    When creating a task with this status
    Then the task status should default to "Active"

  @models
  Scenario: Task serialization includes status
    Given a task with status "Estimated"
    When serialized to dict to check status
    Then the dict should include the status field

  @models
  Scenario: Task deserialization reads status
    Given a task dict with status "Inactive" for deserialization
    When deserialized to Task to check status
    Then the task should have status "Inactive"

  @models
  Scenario: Task deserialization defaults status to Active
    Given a task dict without status
    When deserialized to Task
    Then the deserialized task status should be "Active"

  # Restored from test_models.py. The conversion carried the status
  # round-trips across and left behind the resource-assignment ones and the
  # guard against a property being called as a method - none of which the
  # rest of the suite covers.

  @models
  Scenario: Resource assignments survive a round trip
    Given a task carrying two resource assignments
    When the task is serialized and read back
    Then the read-back assignments should equal the originals

  @models
  Scenario: A file's old single resource fields are converted
    Given a task dict with the old resource_id, estimated_hours and split
    When the legacy dict is deserialized to Task
    Then the task should carry one assignment built from those fields

  @models
  Scenario: A model property is never called as a method
    When every source file is scanned for calls to a model property
    Then no file should call one

  @models
  Scenario: Two tasks with the same name coexist in a project
    Given a project
    When two tasks named "Review" are added
    Then the project should hold two tasks
    And each should be reachable by its own id
