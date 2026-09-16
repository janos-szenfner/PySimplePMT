Feature: The task list nests every depth and never drops a row
  The tree is rebuilt on every change, so how rows find their parents
  matters: imported plans nest several levels deep, a row whose parent
  is missing must still show, and a parent-child loop must terminate
  rather than hang the refresh.

  Scenario: Four levels nest in order
    Given a plan nesting a phase four levels deep
    When the task list is populated
    Then "phase" holds "level1"
    And "level1" holds "level2"
    And "level2" holds "level3"

  Scenario: Siblings keep the plan's order under their parent
    Given a phase with three children
    When the task list is populated
    Then "phase" lists "first", "second" and "third" in that order

  Scenario: A row whose parent is missing shows at the top level
    Given a plan holding a task whose parent does not exist
    When the task list is populated
    Then "orphan" is a top-level row

  Scenario: A parent-child loop still populates
    Given a plan holding a two-task parent loop
    When the task list is populated
    Then "loopy" is a top-level row
    And "looped" is a top-level row
