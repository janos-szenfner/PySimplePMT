Feature: Task status on the list and the dashboard
  A task carries one of three statuses - Active, Estimated or Inactive.
  Active is the default and the quiet case: the Status column stays empty
  for it. Estimated and Inactive are marked, both in the list and in the
  dashboard's summary, which used to talk about a Draft status that no
  longer exists.

  @status
  Scenario: The status set offers the three values with Active first
    Given the set of task statuses
    Then it holds exactly "Active", "Estimated" and "Inactive"
    And the first value is "Active"

  @status
  Scenario: A new task is Active by default
    Given a task created without a status
    Then its status is "Active"

  @status
  Scenario: An older Draft status is read back as Active
    Given a task dict carrying the old "Draft" status
    When the dict is read back into a task
    Then its status is "Active"

  @status
  Scenario: An Active row shows no letter in the Status column
    Given a task list holding an "Active" task
    Then the Status cell for that task is empty
    And that row's font is not bold
    And that row's font is not struck through

  @status
  Scenario: An Estimated row shows a bold E
    Given a task list holding an "Estimated" task
    Then the Status cell for that task is "E"
    And that row's font is bold
    And that row's font is not struck through

  @status
  Scenario: An Inactive row shows a bold, struck-through I on a greyed line
    Given a task list holding an "Inactive" task
    Then the Status cell for that task is "I"
    And that row's font is bold
    And that row's font is struck through
    And that row is greyed

  @status
  Scenario: Switching a task back to Active clears the marks
    Given a task list holding an "Inactive" task
    When the task is set to "Active" and the list is redrawn
    Then the Status cell for that task is empty
    And that row's font is not struck through
    And that row is not greyed

  @status
  Scenario: The dashboard summary counts Estimated and Inactive
    Given a plan of four tasks, one Estimated and one Inactive
    When the summary metrics are computed
    Then the active share is 50 percent
    And the estimated share is 25 percent
    And the inactive share is 25 percent

  @status
  Scenario: The three dashboard shares always come to a hundred
    Given a plan of four tasks, one Estimated and one Inactive
    When the summary metrics are computed
    Then the three shares add up to a hundred

  @status
  Scenario: The dashboard summary no longer carries a Draft share
    Given a plan of four tasks, one Estimated and one Inactive
    When the summary metrics are computed
    Then there is no draft share

  @status
  Scenario: The summary box names Estimated and Inactive, not Draft
    Given a rendered dashboard for a plan with an Estimated and an Inactive task
    Then the summary box shows an "Estimated Status" line
    And the summary box shows an "Inactive Status" line
    And the summary box shows no "Draft Status" line
