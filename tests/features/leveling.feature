Feature: Resource levelling on float
  Levelling spends a task's float to clear the days a resource is booked
  past its capacity. Free float is spent first - the measure that cannot
  move a successor - and anything no delay can clear is reported rather
  than hidden.

  Scenario: A task with free float slides to clear the overload
    Given a levelling plan with a double-booked resource
    When the plan is levelled
    Then the float task is delayed within its free float
    And the critical task did not move
    And the project finish did not slip

  Scenario: An overload no float can clear is reported
    Given a levelling plan where nothing has float
    When the plan is levelled
    Then no task moved
    And the unresolved list names the resource and the day

  Scenario: A Must Start On task is skipped, not moved
    Given a levelling plan with a locked task in the overload
    When the plan is levelled
    Then the locked task kept its dates
    And the skipped list says why

  Scenario: A deadline caps the delay
    Given a levelling plan where the float task has a deadline
    When the plan is levelled
    Then the task is not pushed past its deadline

  Scenario: Lower priority moves before higher
    Given a levelling plan where both overloaded tasks differ in priority
    When the plan is levelled
    Then the lower-priority task moved first

  Scenario: Within-free-float leaves every successor where it was
    Given a levelling plan where each overloaded task feeds a tight successor
    When the plan is levelled within free float
    Then the successors kept their dates

  Scenario: Retired priority names land on the new ladder
    Given a task saved with the legacy priority "Normal"
    Then its priority reads "Medium"

  @needs_display
  Scenario: The preview moves nothing until Apply
    Given the application is started
    And a project with an overallocated resource
    When the levelling preview is opened
    Then the table lists the move
    And the plan itself has not changed
    When the preview is applied
    Then the task moved
    And one undo takes the whole run back
