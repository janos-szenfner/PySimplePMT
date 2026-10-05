@grid_sorting
Feature: Sorting and autofiltering the task grid

  The task list holds its rows in plan order - the order the row
  numbers and the chart agree on - and three issues asked for
  orderings on top of it rather than instead of it: a heading click
  that sorts its column (issue #46), a Sort By dialog taking up to
  three levels (issue #45), and MS Project's AutoFilter - a dropdown
  checklist on every heading, shown or hidden by a View menu switch
  (issue #81).

  None of them reorders the plan: a sort arranges siblings inside
  their own level of the outline, so a task is never pulled out from
  under its summary, and clearing the sort puts the plan order
  straight back.

  The ordering and the checklist answers are pure helpers - the same
  code the grid calls - so they are tested here without a display.
  The scenarios that need the real tree are marked @display_dependent.

  Scenario: A heading click cycles ascending, descending and off
    # The third click puts the plan order back rather than repeating
    # ascending - the cycle a spreadsheet column runs (issue #46).
    Given a plan whose rows are out of order
    When the "Start" heading is clicked once
    Then the sort keys are "Start" ascending
    When the "Start" heading is clicked again
    Then the sort keys are "Start" descending
    When the "Start" heading is clicked a third time
    Then there is no sort

  Scenario: A click on another column starts that column's sort
    # A plain click answers a single-column question, so it replaces a
    # sort already in force rather than amending it.
    Given a plan whose rows are out of order
    And the sort is "Duration" descending
    When the "Task Name" heading is clicked once
    Then the sort keys are "Task Name" ascending

  Scenario: A column sorts ascending
    # Duration reads the working days the cell shows: the milestone
    # holds none, the phase its span.
    Given a plan whose rows are out of order
    When the grid is sorted by "Duration" "ascending"
    Then the roots come in the order "M,E,C,P"

  Scenario: The same column sorts descending
    Given a plan whose rows are out of order
    When the grid is sorted by "Duration" "descending"
    Then the roots come in the order "P,C,E,M"

  Scenario: Three levels break ties in turn
    # Duration descending, then Start ascending, then Progress
    # ascending - the issue's example, level by level (issue #45). The
    # three sub-tasks share a duration, so Start decides and Progress
    # breaks the last tie.
    Given a plan whose rows are out of order
    When the grid is sorted in levels by "Duration" "descending", then "Start" "ascending", then "Progress" "ascending"
    Then the children of "P" come in the order "A,B,D"
    And the roots come in the order "P,C,E,M"

  Scenario: Sorting never mixes the levels of the outline
    # A sub-task is ordered among its siblings, never pulled out from
    # under its summary: the parent rows stay where the sort left them
    # and the children arrange themselves beneath.
    Given a plan whose rows are out of order
    When the grid is sorted by "Progress" "ascending"
    Then the children of "P" come in the order "A,D,B"

  Scenario: Blank cells sort last either way
    # A row with no deadline lands at the bottom ascending and
    # descending alike - the way MS Project and Excel both leave blanks.
    Given a plan whose rows are out of order
    When the grid is sorted by "Deadline" "ascending"
    Then the roots come in the order "E,P,M,C"
    When the grid is sorted by "Deadline" "descending"
    Then the roots come in the order "E,P,M,C"

  Scenario: The sort shows its direction in the heading
    Given a plan whose rows are out of order
    When the sort is "Duration" descending and "Start" ascending
    Then the "Duration" heading reads "▼1"
    And the "Start" heading reads "▲2"
    And the "Progress" heading reads ""

  Scenario: An autofilter checklist hides the unticked values
    # Ticks keep the cell texts the checklist shows - "5" in the
    # Duration column means the three sub-tasks and the task Estimate
    # (issue #81).
    Given a plan whose rows are out of order
    When the autofilter keeps "5" in the "Duration" column
    Then the visible roots are "P,E"
    And the visible rows are "P,A,B,D,E"

  Scenario: A matched sub-task keeps its parent on screen
    # The way the column filters and the search keep ancestors: a found
    # sub-task shown without its phase would float to the top level
    # with no sign of what it belongs to.
    Given a plan whose rows are out of order
    When the autofilter keeps "design" in the "Label" column
    Then the visible roots are "P"
    And the visible rows are "P,A"

  Scenario: Unticking everything hides every row
    # An empty tick set passes nothing - the answer "untick all"
    # deserves, rather than quietly meaning the opposite.
    Given a plan whose rows are out of order
    When the autofilter keeps nothing in the "Type" column
    Then no rows are visible

  Scenario: The checklist lists the values the cells show
    Given a plan whose rows are out of order
    Then the "Type" column offers "Milestone,Phase,Task"
    And the "Deadline" column offers "2026-01-20,(Blanks)"

  @display_dependent
  Scenario: A real heading click sorts the rows
    Given a toolbar and a list over the sorting plan
    When the "Start" heading is pressed
    Then the grid rows are "P,A,B,D,E,C,M"
    And the "Start" heading wears "▲"

  @display_dependent
  Scenario: AutoFilter marks every heading with a dropdown
    Given a toolbar and a list over the sorting plan
    When AutoFilter is switched on
    Then the "Duration" heading wears "▾"

  @display_dependent
  Scenario: An autofilter dropdown removes the unticked rows
    Given a toolbar and a list over the sorting plan
    When AutoFilter is switched on
    And the "Type" dropdown is opened and only "Task" is kept
    Then the grid rows are "P,A,B,D,E,C"

  @display_dependent
  Scenario: Switching AutoFilter off brings every row back
    # Rows hidden by a control that no longer exists would have no way
    # back into view, so the switch clears the checklists with itself.
    Given a toolbar and a list over the sorting plan
    When AutoFilter is switched on
    And the "Type" dropdown is opened and only "Task" is kept
    And AutoFilter is switched off
    Then the grid rows are "P,A,B,D,M,E,C"
