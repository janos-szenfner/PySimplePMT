@indent_tasks_view
Feature: Show and hide indented rows from the View menu

  Issue #113. MS Project carries Show Subtasks and Hide Subtasks on the
  View ribbon - one press opens or folds the selected summary's children
  rather than clicking the row's arrow. The app has no sub-task type,
  only indented rows, so the View menu offers "Show Indent Tasks" and
  "Hide Indent Tasks" instead.

  Needs a display; the scenarios skip where there is none.

  Background: a phase with two levels of children under it
    Given a task list over a phase with nested children

  Scenario: The commands are on the View menu
    Then "View" offers "Show Indent Tasks" and "Hide Indent Tasks"

  Scenario: Hide Indent Tasks folds the selected row's children away
    # One press; the same as clicking the row's fold arrow.
    When the phase is picked and Hide Indent Tasks runs
    Then only the phase and the rows beside it remain on screen

  Scenario: Show Indent Tasks opens every folded level at once
    # A nested branch folded inside a folded parent opens all the way -
    # shown with grandchildren still tucked away would read half-done.
    When every branch is folded and the phase is picked
    And Show Indent Tasks runs
    Then all the children are on screen again

  Scenario: A leaf under the command has nothing to fold
    # No children - nothing for Hide to take away, nothing for Show to
    # open. The command answers zero and the menu reports it rather
    # than doing nothing in silence.
    When a leaf row is picked
    Then Hide Indent Tasks folds nothing
    And Show Indent Tasks opens nothing

  Scenario: The blank tail rows have nothing to show or hide
    # The uncommitted rows carry no children, so both commands leave
    # them be.
    When a blank tail row is picked
    Then Hide Indent Tasks folds nothing
    And Show Indent Tasks opens nothing
