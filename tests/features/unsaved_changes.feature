Feature: Unsaved changes protection
  The application prompts to save when the user tries to close it or start a new project while there are unsaved changes.

  Background:
    Given the application is open

  Scenario: Closing a clean project exits immediately
    Given the project has no unsaved changes
    When the user tries to close the application
    Then the application exits
    And the project is no longer dirty

  Scenario: Closing a dirty project can be cancelled
    Given the project has unsaved changes
    And the user will choose "cancel"
    When the user tries to close the application
    Then the application stays open
    And the project is still dirty

  Scenario: Closing a dirty project can be discarded
    Given the project has unsaved changes
    And the user will choose "discard"
    When the user tries to close the application
    Then the application exits
    And the project is no longer dirty

  Scenario: Closing a dirty project can be saved
    Given the project has unsaved changes
    And the user will choose "save"
    And saving will succeed
    When the user tries to close the application
    Then the application exits
    And the project is no longer dirty

  Scenario: Creating a new project can be cancelled
    Given the project has unsaved changes
    And the user will choose "cancel"
    When the user tries to create a new project
    Then the current project is unchanged
    And the project is still dirty

  Scenario: Creating a new project can be discarded
    Given the project has unsaved changes
    And the user will choose "discard"
    And the new project name will be "New Project"
    When the user tries to create a new project
    Then a new empty project is created
    And the project is no longer dirty
