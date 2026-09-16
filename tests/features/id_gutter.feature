Feature: The fixed "No" gutter down the left of the task list
  The row number was a data column inside the tree, second after Task
  Name. It is now a grey, read-only gutter in its own column to the left
  of the list (like MS Project), mirroring the visible rows. The number
  stays flush for every row whatever its type or depth, and folding a
  branch away drops the hidden rows without renumbering the rest.

  Background:
    Given a task list over a mixed plan

  Scenario: The row number is no longer a main tree column
    Then the main tree has no "ID" column

  Scenario: The gutter header is No
    Then the gutter's header reads "No"

  Scenario: It numbers every visible row flush and uniform
    Then the gutter reads "001", "002", "003" and "004"

  Scenario: It mirrors exactly the visible rows
    Then the gutter holds as many numbers as there are visible rows

  Scenario: Folding drops the hidden row without renumbering
    When the "Phase" branch is folded away
    Then the visible rows are "a", "m" and "c"
    And the gutter reads "001", "003" and "004"

  Scenario: The gutter is read only
    Then the gutter accepts no selection
