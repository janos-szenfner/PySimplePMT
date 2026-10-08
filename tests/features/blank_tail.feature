@blank_tail
Feature: The task grid ends with blank rows to type into

  Issue #111. An empty plan used to open on a bare canvas - nothing to
  click, nothing to type into, and no hint that typing was the way to
  start. The grid now always ends with a block of uncommitted blank
  rows, like the unused rows of a spreadsheet: drawn, selectable and
  editable, but with no task behind them until a cell is typed into,
  which is what turns them into rows of the plan.

  Needs a display; the scenarios skip where there is none.

  Background: a task list, with and without tasks in it
    Given a task list holding two tasks

  Scenario: Every task row is followed by a tail of blank rows
    # At least the twenty-five the issue asked for, or enough to fill
    # the grid plus one.
    Then the tasks are followed by at least twenty-five blank rows

  Scenario: An empty plan is not a blank canvas
    # The welcome line: there is always a row to type into.
    Given the plan is emptied
    Then the tasks are followed by at least twenty-five blank rows

  Scenario: A blank row is not part of the plan
    # No task, no number - drawn only.
    Then no blank row has a task behind it
    And a blank row picked out selects nothing

  Scenario: Typing a name into a blank makes it a row of the plan
    # The first piece of information is what materializes it.
    When "Roofing" is typed into the first blank row's name cell
    Then the plan gains one row called "Roofing"

  Scenario: A blank opened and left commits nothing
    # Opening a cell and clicking away is not a decision.
    When the first blank row's name cell is opened and left empty
    Then the plan gains no rows

  Scenario: A later blank brings the rows between with it
    # So the typed row keeps the place it was pointed at rather than
    # sliding up to meet the list.
    When "Roofing" is typed into the third blank row's name cell
    Then the plan gains three rows
    And the first two are undecided placeholders
    And the third is called "Roofing"

  Scenario: The tail refills once a row is taken
    # There is always somewhere left to type.
    When "Roofing" is typed into the first blank row's name cell
    Then the blank tail is as long as before
