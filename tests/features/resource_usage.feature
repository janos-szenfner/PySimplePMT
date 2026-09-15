Feature: The resource usage grid
  The Resource Planning tab's second face: the pool as a tree, each
  entity expanding to the tasks assigned to it. Reached through the
  ribbon's View tab, which offers the Usage Grid toggle only while the
  Resource Planning tab is on top.

  Background:
    Given the application is started
    And a project with a populated resource pool and tasks

  @resource_usage
  @needs_display
  Scenario: The ribbon offers Usage Grid only on the Resource Planning tab
    Then the View page's Resources group is hidden
    When the "Resource Planning" tab is selected
    Then the View page's Resources group is shown
    When the "Task Planning" tab is selected
    Then the View page's Resources group is hidden

  @resource_usage
  @needs_display
  Scenario: The toggle swaps the matrix for the usage grid and back
    When the "Resource Planning" tab is selected
    And the Usage Grid toggle is pressed
    Then the resource board is showing the usage grid
    When the Usage Grid toggle is pressed
    Then the resource board is showing the matrix

  @resource_usage
  @needs_display
  Scenario: The grid lists the pool in sections with tasks beneath
    When the "Resource Planning" tab is selected
    And the Usage Grid toggle is pressed
    Then the grid shows "Platform Team" before "Bob Builder" before "Anna Dev" before "Cement" before "Flight"
    And "Anna Dev" expands to a read-only row for "Build API"
    And "Flight" expands to a row for "Build API" worth "$300"

  @resource_usage
  @needs_display
  Scenario: A team member shows under the team in italic
    When the "Resource Planning" tab is selected
    And the Usage Grid toggle is pressed
    Then "Anna Dev" appears under "Platform Team" in italic
    And "Anna Dev" still has her own row in the Named section

  @resource_usage
  @needs_display
  Scenario: Assigning tasks through the grid is undoable
    When the "Resource Planning" tab is selected
    And the Usage Grid toggle is pressed
    And "Bob Builder" is assigned to "Lay Foundations"
    Then "Lay Foundations" carries "Bob Builder"
    And undo removes the assignment

  @resource_usage
  @needs_display
  Scenario: Removing a task from a resource is undoable
    When the "Resource Planning" tab is selected
    And the Usage Grid toggle is pressed
    And "Build API" is removed from "Anna Dev"
    Then "Build API" no longer carries "Anna Dev"
    And undo restores the assignment

  @resource_usage
  @needs_display
  Scenario: Deleting a resource prunes its assignments and undoes whole
    When the "Resource Planning" tab is selected
    And the Usage Grid toggle is pressed
    And "Anna Dev" is deleted from the pool
    Then the pool no longer holds "Anna Dev"
    And "Build API" no longer carries the deleted entity
    And undo restores the resource and the assignment
