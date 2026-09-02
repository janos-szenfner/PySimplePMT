Feature: Task group hierarchy and re-parenting
  Users can move task groups and individual tasks into other groups without
  creating cycles or losing nested schedules and assignments.

  Background:
    Given a project with nested task groups

  Scenario: Move a task group into another task group
    When the Design group is moved into the Implementation group
    Then the Design group parent is the Implementation group
    And the Design branch remains together

  Scenario: Prevent moving a group into itself
    When the Implementation group is moved into itself
    Then the hierarchy move is rejected
    And the Implementation group remains a root task

  Scenario: Prevent moving a group into its descendant
    When the Implementation group is moved into the Wireframes task
    Then the hierarchy move is rejected
    And the Implementation group remains a root task

  Scenario: Re-parent an individual task
    When the Wireframes task is moved into the Implementation group
    Then the Wireframes task parent is the Implementation group

  Scenario: Moving a branch preserves schedules and assignments
    When the Design group is moved into the Implementation group
    Then every task in the Design branch keeps its schedule
    And every task in the Design branch keeps its assignments

  Scenario: Hierarchy indentation uses 24 pixels per level
    When the Design group is moved into the Implementation group
    Then the Implementation group indentation is 0 pixels
    And the Design group indentation is 24 pixels
    And the Wireframes task indentation is 48 pixels

  Scenario: Indent hotkey moves the selected group under the group above
    Given the task tree is open
    And the Design group is selected
    When the indent hotkey is invoked
    Then the Design group parent is the Implementation group
    And the hotkey stops default focus traversal

  Scenario: Outdent hotkey promotes the selected group
    Given the Design group is under the Implementation group
    And the task tree is open
    And the Design group is selected
    When the outdent hotkey is invoked
    Then the Design group remains a root task
    And the hotkey stops default focus traversal

  Scenario: macOS hierarchy hotkeys are configured
    Given the task tree is open for macOS
    Then Tab and Shift-Tab hierarchy hotkeys are configured
    And macOS Command and Option hierarchy hotkeys are configured

  Scenario: Windows and Linux hierarchy hotkeys are configured
    Given the task tree is open for Linux
    Then Tab and Shift-Tab hierarchy hotkeys are configured
    And Control and Alt hierarchy hotkeys are configured

  Scenario: Dragging over the center of a group selects it as parent
    Given the task tree is open
    And the Design group is being dragged over the Implementation group center
    Then the drop target is marked as a parent
    And the drop target status is "Drop Target: Parent"

  Scenario: A drag-and-drop parent move can be undone
    Given the task tree is open with undo support
    When the Design group is drag-reparented into the Implementation group
    And the hierarchy move is undone
    Then the Design group remains a root task
