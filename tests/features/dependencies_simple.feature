Feature: Task dependency management
  Core functionality for creating, managing, and serializing task dependencies

  Background:
    Given a base date of "2024-01-01"

  @dependencies
  Scenario: Default dependency type
    Given a dependency created from a bare task ID
    Then the dependency type should default to "FS"
    And the dependency hardness should default to "Hard"

  @dependencies
  Scenario: Dependency type labels
    Given dependency type labels
    Then "SS" should map to "Start - Start"
    And "FS" should map to "Finish - Start"
    And "FF" should map to "Finish - Finish"
    And "SF" should map to "Start - Finish"

  @dependencies
  Scenario: Dependency values normalization
    Given dependency with lowercase type "ss"
    Then the type should be normalized to "SS"
    And the hardness should be normalized to "Rubber"

  @dependencies
  Scenario: Dependency normalization for unknown values
    Given dependency with unknown type "nonsense"
    Then the type should default to "FS"
    And the hardness should default to "Hard"

  @dependencies
  Scenario: Dependency serialization roundtrip
    Given a dependency with type "SS" and hardness "Rubber"
    When serialized to dict and back
    Then the restored dependency should equal the original

  @dependencies
  Scenario: DependencyList accepts bare IDs
    Given an empty DependencyList
    When a bare task ID is appended
    Then the list should contain a Dependency object
    And the dependency should have the correct task ID

  @dependencies
  Scenario: DependencyList membership by ID
    Given a DependencyList containing "001"
    Then "001" should be in the list
    And "002" should not be in the list

  @dependencies
  Scenario: Task dependency assignment coercion
    Given a task
    When assigned a list of bare IDs
    Then the task should have the correct dependency IDs

  @dependencies
  Scenario: Task dependency append coercion
    Given a task
    When a bare ID is appended to dependencies
    Then the task should have the appended dependency ID

  @dependencies
  Scenario: Add dependency with specific type and hardness
    Given a task
    When a dependency is added with type "SS" and hardness "Rubber"
    Then the dependency should have the correct type
    And the dependency should have the correct hardness

  @dependencies
  Scenario: Adding dependency twice updates instead of duplicates
    Given a task
    When the same dependency is added twice with different types
    Then the task should have only one dependency
    And the dependency should have the latest type

  @dependencies
  Scenario: Remove dependency by ID
    Given a task with a dependency
    When the dependency is removed
    Then the dependencies list should be empty
    And removing non-existent dependency should return False

  @dependencies
  Scenario: Latest hard link applies
    Given tasks with multiple hard dependencies
    When rescheduled
    Then the task should start on the latest hard constraint date

  @dependencies
  Scenario: Project serialization preserves dependency types
    Given a project with tasks having specific dependency types
    When serialized and deserialized
    Then the dependencies should preserve their types and hardness