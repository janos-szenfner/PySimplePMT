@dependency_chooser
Feature: The dependency editor's list of candidate predecessors

  The chooser names a task by the number the task list shows it as,
  which is where the row sits rather than what the row is - see
  Project.display_ids. Working that out means walking the plan's
  hierarchy, and the chooser was doing it once per row it was about to
  draw: a plan of eight hundred tasks walked its own hierarchy seven
  hundred and ninety-nine times to fill one dropdown, and took a fifth
  of a second to open a dialog.

  It then read the choice back out of the label the dropdown was
  showing, by formatting every candidate's label again and looking for
  the one that matched the string.

  The scenarios drive the real widget, so they skip without a display.

  Scenario: A label carries the number the list shows
    # Not the identity, which the reader has never seen.
    Given an editor over a 6-task plan
    Then task "002" is labelled "002 - Task 2"

  Scenario: Two tasks with the same name are still told apart
    # The number does it, because a number is a position and no two
    # rows share one.
    Given an editor over a 6-task plan
    And tasks "002,003" share the name "Same Name"
    Then every candidate label is distinct

  Scenario: A task that is in no plan is named without a number
    # Rather than raising while drawing a dialog.
    Given an editor over a 6-task plan
    Then a stray task is labelled " - Elsewhere"

  Scenario: The hierarchy is walked once
    # It used to be walked once per candidate. display_id builds the
    # whole map to answer for one task, so calling it per row made
    # drawing the chooser quadratic in the size of the plan.
    Given an editor over a 40-task plan
    When the chooser is refreshed while counting hierarchy walks
    Then the plan was walked once

  Scenario: The cost does not grow with the square of the plan
    # A rough guard rather than a stopwatch: forty times the rows must
    # not cost anything like sixteen hundred times the work. Timings
    # are noisy, so this asserts the shape and leaves room; the count
    # above is the exact statement.
    Given an editor over a 40-task plan
    When a small editor and the large editor are each refreshed
    Then the large refresh stays within the shape bound

  Scenario: The chosen task is the one linked
    # Read from what the dropdown was built from, not from its text.
    Given an editor over a 6-task plan
    And the chooser is refreshed
    When the shown candidate is added
    Then one link was made
    And it links the task the label names

  Scenario: A task further down the list can be chosen
    # Not only whichever one happens to be first.
    Given an editor over a 6-task plan
    And the chooser is refreshed
    When the third candidate is added
    Then the linked task is the one the third label names

  Scenario: A label that names nothing adds no link
    # The user is told to choose one rather than linked to something at
    # random. The prompt is stood in for rather than shown - a real
    # dialog is how this test once hung the macOS build.
    Given an editor over a 6-task plan
    And the chooser is refreshed
    When the label "999 - Not a task in this plan" is added
    Then no link was made
    And the user was told

  Scenario: A task already linked leaves the candidates
    # It cannot be depended on twice.
    Given an editor over a 6-task plan
    And the chooser is refreshed
    When the shown candidate is added
    Then that label no longer appears among the candidates

  Scenario: A link that would run in a circle is refused with the reason
    # A row that holds work takes its dates from the rows inside it, so
    # a link from a child to a task that waits on its parent is
    # circular however it is typed (issue #47).
    Given an editor over a 6-task plan
    And the first task sits in a summary the second waits on
    When the candidate ending "Task 2" is added
    Then no link was made
    And the user was shown the error

  Scenario: A link that closes no loop is still added
    Given an editor over a 6-task plan
    And the first task sits in a summary the second waits on
    When the candidate ending "Task 3" is added
    Then one link was made
