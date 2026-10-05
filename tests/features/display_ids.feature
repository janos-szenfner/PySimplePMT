Feature: A task's shown number is worked out, never stored
  A task carries two numbers that used to be one. Task.id is the
  identity - dependencies, parents, the clipboard, the tree's row ids
  and the undo history key on it, and it never changes because a row
  moved; it is also never shown. The display id is where the row sits,
  counted from one down the list, and it is worked out rather than
  stored - a stored number would have to be rewritten on every reorder,
  insert, delete and indent, and each of those is already recorded
  against Task.id.

  # ---- the numbers are contiguous --------------------------------------

  Scenario: A flat plan counts from one
    # The top of the list is 1, not 0.
    Given a plan with the rows "a, b, c"
    Then the numbers run "a=1, b=2, c=3"

  Scenario: Children are counted where they are shown
    # A sub-task's number follows its parent's, not the list order.
    Given a plan with the rows "a, b, child<a"
    Then the numbers run "a=1, child=2, b=3"

  Scenario: The padded form is what the column shows
    # Zero-padded, the way the list has always written a task number.
    Given a plan with the rows "a, b"
    Then "b" is shown as "002"

  Scenario: A task that is not in the plan has no number
    # Rather than an exception, or a misleading zero.
    Given a plan with the rows "a"
    Then the task "gone" has no number

  # ---- the specification's table, row by row ----------------------------

  Scenario: Inserting between pushes the rest down
    # Task 1, Task 2 becomes Task 1, the new Task 2, Task 3. The new row
    # is appended to the plan and shown under its parent, so this is
    # also the case a numbering that counted list order gets wrong.
    Given a plan with the rows "first, second"
    When a row "inserted" is added under "first"
    Then the numbers run "first=1, inserted=2, second=3"

  Scenario: Moving a row up swaps the two numbers
    # Task 3 dragged above Task 2 becomes Task 2, and it becomes 3.
    Given a plan with the rows "one, two, three"
    When "three" is moved before "two"
    Then the shown order is "one, three, two"
    And the numbers run "one=1, three=2, two=3"

  Scenario: Deleting leaves no gap
    # The rows below collapse up rather than the numbers skipping one.
    Given a plan with the rows "one, two, three"
    When "two" is deleted
    Then the numbers run "one=1, three=2"

  Scenario: Indenting renumbers what moved past it
    # A hierarchy change alters the display order, so it alters the
    # numbers - the fourth trigger the specification names.
    Given a plan with the rows "a, b, c"
    When "c" is indented
    Then the numbers run "a=1, b=2, c=3"
    And "c" now sits under "b"

  # ---- the identity does not move ---------------------------------------

  Scenario: A reorder leaves every identity alone
    # Which is what lets the undo history survive it: every entry there
    # is keyed on Task.id.
    Given a plan with the rows "one, two, three"
    And the identities are noted
    When "three" is moved before "two"
    Then every identity is unchanged

  Scenario: A dependency still points at the same task
    # The link is on the identity, so it survives the row moving - the
    # *number* it is shown as changes, which is the specification's
    # "visual predecessor references adjust dynamically".
    Given a plan with the rows "one, two, three"
    And "three" is linked after "one"
    When "three" is moved before "two"
    Then the link on "three" still points at "one"
    And the numbers run "one=1, three=2, two=3"

  Scenario: A parent reference survives a renumber
    # Hierarchy is held by identity too.
    Given a plan with the rows "parent, child<parent, other"
    When "other" is moved before "parent"
    Then "child" still has parent "parent"

  Scenario: Nothing is stored to go stale
    # A field would need renumbering on four separate triggers; a number
    # worked out from where the row sits is right the moment it moves.
    Given a plan with the rows "a"
    Then no task stores a display number

  Scenario: The saved file carries the identity
    # And not the number, which would be a copy of a fact about order.
    Given a plan with the rows "a"
    When "a" is written to a dictionary
    Then it carries "a" and no display number

  # ---- what is on screen -------------------------------------------------

  Scenario: The search finds a row by the number shown
    # Both the bare number and the padded form the column uses.
    Given a plan with the rows "first, second"
    When "second" is searched
    Then the haystack holds "2" and "002"

  Scenario: The search does not find a row by its identity
    # Nobody can see the identity, so nobody can type it; matching on it
    # would find rows by a number nowhere on screen.
    Given a plan with the rows "ZZTOP"
    And "ZZTOP" is named "Kickoff"
    When "ZZTOP" is searched
    Then the haystack contains "kickoff"
    And the haystack does not hold "zztop"

  # ---- the exports carry the number -------------------------------------
  # An exported file names a task by the number the reader can see; a
  # file naming a task by its identity names it by something the reader
  # cannot look up in the plan they exported.

  Scenario: The shared walk numbers by the display id
    # Which is what both XML exporters write, so neither can drift.
    Given the exportable plan
    Then the shared walk numbers match the display ids

  Scenario: The GanttProject file uses it
    # Both for the task ids and for the links between them.
    Given the exportable plan
    When the plan is exported to GAN
    Then the written task ids are the shown numbers in shown order

  Scenario: The Microsoft file uses it
    # UID and ID alike, which is what its links point at.
    Given the exportable plan
    When the plan is exported to MSPDI
    Then the written task ids are the shown numbers in shown order

  Scenario: No identity reaches either file
    # The check that catches one leaking through a field nobody thought of.
    Given the exportable plan
    When the plan is exported to both XML formats
    Then no task identity reaches the files

  Scenario: The spreadsheet uses it too
    # The sheet holds one row per piece of work and shows the phases as
    # a column beside them, so these numbers have gaps where the phases
    # sit - the right way round: a sheet read against the plan has to
    # call a task what the plan calls it.
    Given the exportable plan
    When the plan is exported to a spreadsheet
    Then every number in the sheet's ID column is one the plan shows
