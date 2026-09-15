Feature: The status bar follows the active view's selection
  The line at the foot of the window answers "what is selected" for
  whichever view is on top - a task on the planning view, a resource on
  the Resource Planning board, a deliverable on its board - and a view
  sitting underneath cannot overwrite it.

  Background:
    Given the application is started
    And a project with a populated resource pool and tasks

  Scenario: A selected task describes itself
    When the task "Build API" is picked in the task list
    Then the status bar mentions "Task: Build API"

  Scenario: A selected resource describes itself on the board
    When the "Resource Planning" tab is selected
    And the resource "Anna Dev" is picked on the board
    Then the status bar mentions "Resource: Anna Dev"
    And the status bar mentions "Named"

  Scenario: A selected row describes itself in the usage grid
    When the "Resource Planning" tab is selected
    And the Usage Grid toggle is pressed
    And the usage-grid row for "Anna Dev" is picked
    Then the status bar mentions "Resource: Anna Dev"

  Scenario: A task row under a resource describes the task
    When the "Resource Planning" tab is selected
    And the Usage Grid toggle is pressed
    And a usage-grid task row for "Build API" is picked
    Then the status bar mentions "Task: Build API"

  Scenario: A selected deliverable describes itself
    Given a deliverable called "API shipped"
    When the "Deliverables" tab is selected
    And the deliverable "API shipped" is picked on the board
    Then the status bar mentions "Deliverable: API shipped"

  Scenario: Switching views restores each view's own line
    When the task "Build API" is picked in the task list
    And the "Resource Planning" tab is selected
    And the resource "Anna Dev" is picked on the board
    And the "Task Planning" tab is selected
    Then the status bar mentions "Task: Build API"

  Scenario: A hidden view cannot overwrite the line
    When the "Resource Planning" tab is selected
    And the resource "Anna Dev" is picked on the board
    And the task "Lay Foundations" is picked in the task list
    Then the status bar mentions "Resource: Anna Dev"
    And the status bar does not mention "Task: Lay Foundations"
