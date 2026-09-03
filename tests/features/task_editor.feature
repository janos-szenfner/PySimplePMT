Feature: Editing a task from the task list
  Opening a row's editor gives one window, ready to type into.

  Background:
    Given an application with a plan in it

  Scenario: The editor opens ready to type the name
    When the user opens the editor for the first task
    And the window is mapped
    Then the cursor is in the Name field

  Scenario: Opening the same task twice keeps one window
    When the user opens the editor for the first task
    And the user opens the editor for the first task again
    Then only one editor is open
    And both opens returned the same window

  Scenario: Opening a row six times still gives one window
    When the user opens the editor for the first task 6 times
    Then only one editor is open

  Scenario: A second task gets an editor of its own
    When the user opens the editor for the first task
    And the user opens the editor for the second task
    Then 2 editors are open

  Scenario: Closing an editor lets the row be opened again
    When the user opens the editor for the first task
    And the user closes the editor
    And the user opens the editor for the first task again
    Then only one editor is open
    And the reopened window is a new one
