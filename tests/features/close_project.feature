Feature: Close Project empties the plan without quitting
  Closing the file used to mean closing the window, which quit the whole
  application. Close Project now empties the current plan back to a
  fresh one and stays open, offering to save unsaved work first.

  Background:
    Given a plan called "Real Plan" holding one task

  Scenario: Closing empties the plan and stays open
    When the project is closed, discarding unsaved work
    Then the plan holds no tasks
    And the plan is called "New Project"
    And the toolbar holds no file path
    And the change was announced
    And the plan was marked clean

  Scenario: Cancelling the save prompt keeps the plan
    When the project is closed and the save prompt is cancelled
    Then the plan still holds its one task
    And the plan is still called "Real Plan"
    And the toolbar still holds its file path

  Scenario: A failed save aborts the close
    When the project is closed and the save fails
    Then the plan still holds its one task
