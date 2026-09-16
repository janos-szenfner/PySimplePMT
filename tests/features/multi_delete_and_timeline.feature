@multi_delete_and_timeline
Feature: Multi-row Delete and Add-to-Timeline in the task list
  (issues #17, #34)

  Deleting a multi-row selection removes every selected row as one
  undoable step, and the right-click Add to Timeline turns
  Show-in-timeline on for the whole selection. Both drive the real
  widget, so the scenarios are display-gated like the other task-list
  suites.

  Background: a list over four tasks, confirmations answered Yes
    Given a task list over four tasks

  Scenario: Deleting a selection removes every row
    When rows "t1,t2,t3" are deleted
    Then the plan holds tasks "t4"

  Scenario: A multi delete is one undo step
    When rows "t1,t2,t3" are deleted
    And the delete is undone
    Then the plan holds all of tasks "t1,t2,t3,t4"

  Scenario: Deleting a single row still works
    When row "t2" is deleted
    Then the plan holds tasks "t1,t3,t4"

  Scenario: Cancelling the prompt keeps every row
    Given the confirmation answers No
    When rows "t1,t2" are deleted
    Then the plan still holds 4 tasks

  Scenario: Add to Timeline turns the flag on for the selection
    Given no task is on the timeline
    When rows "t1,t3" are added to the timeline
    Then tasks "t1,t3" are on the timeline
    And tasks "t2,t4" are not on the timeline

  Scenario: Add to Timeline is one undo step
    Given no task is on the timeline
    When rows "t1,t2" are added to the timeline
    And the add is undone
    Then no task is on the timeline

  Scenario: Rows already on the timeline need no undo step
    Given task "t1" is already on the timeline
    When rows "t1" are added to the timeline
    Then there is nothing to undo

  Scenario: Added rows become visible on the Gantt
    Given no task is on the timeline
    Then the Gantt shows nothing yet
    When rows "t1,t2" are added to the timeline
    Then the Gantt-visible tasks are "t1,t2"

  Scenario: The flag the editor reads is set
    # The task editor's checkbox reads task.show_in_timeline directly, so
    # a flag turned on here shows ticked when the row is next opened.
    Given no task is on the timeline
    When rows "t3" are added to the timeline
    Then task "t3" reads on the timeline
