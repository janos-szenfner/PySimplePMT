Feature: Task hierarchies deeper than two levels
  Nesting is a parent link and nothing more - there is no Subtask type
  (issue #63), so a task at any depth can hold rows of its own, and the
  model questions asked here are the ones the rest of the app asks.

  # ---- tasks nested below other tasks -----------------------------------------

  Scenario: The model tracks a parent chain of any depth
    # Nested rows are Tasks: depth is the hierarchy's business now.
    Given a three-level hierarchy
    Then "Level 3" sits under "Level 2"
    And "Level 2" sits under "Level 1"
    And "Level 3" is a "Task"
    And the roots are "Level 1"
    And "Level 2" holds "Level 3"
    And "Level 3"'s parent is "Level 2"

  Scenario: Every level can hold rows
    # A task at any depth may be a grouping row (issues #56 and #63).
    Given a three-level hierarchy
    Then every level can hold rows

  Scenario: An imported hierarchy keeps its real depth
    # Only tasks with children count as summaries; the leaf is the only
    # real work, so it is the whole critical path.
    Given a three-level hierarchy
    Then the summaries are "Level 1, Level 2"
    And the critical path is "Level 3"

  # ---- which types can hold rows ----------------------------------------------

  Scenario Outline: A "<type>" row's stance on children
    Given a row of type "<type>"
    Then it "<can>" hold rows
    And it is "<leaf>"

    Examples:
      | type      | can    | leaf        |
      | Phase     | can    | a container |
      | Task      | can    | not a leaf  |
      | Subtask   | can    | not a leaf  |
      | Milestone | cannot | a leaf      |

  Scenario: A saved Subtask type loads as a Task
    # Issue #63: files written before the type went carry 'Subtask' and
    # 'Sub-Task' rows; being under another row is what made them
    # sub-tasks, so they open as plain Tasks and keep their place.
    Then a saved "Subtask" opens as a "Task"
    And a saved "Sub-Task" opens as a "Task"

  Scenario: A saved Milestone type loads as a flagged task
    # Issue #73: taking no time is what made them milestones, so they
    # open as Tasks with the switch on - and an end that is their
    # start, since a moment finishes where it begins.
    Then a saved "Milestone" opens as a "Task"
    And it is flagged a milestone
    And its end is its start

  # ---- a row keeps its type wherever it is moved --------------------------------
  # Indenting made everything a Subtask whatever it was moved under,
  # which flattened the levels the types exist to describe. The type is
  # now left alone entirely: it is the user's statement about what a
  # row is; where the row sits is a separate statement. Each plan below
  # states the hierarchy outright rather than building it by indenting,
  # because indenting moves a task under the sibling above it - which
  # is how an earlier version of these tests passed while exercising
  # the wrong parent.

  Scenario: A task under a phase stays a task
    # And so keeps being able to hold sub-tasks.
    Given the rows
      | id | type  | parent |
      | D  | Phase |        |
      | T  | Task  |        |
    When "T" is indented
    Then "T" is a "Task"
    And "T" sits under "D"
    And "T" can hold rows

  Scenario: A task under a task stays a task
    # The case the older rule still retyped: a Task indented under a
    # Task came back a Subtask, so the row you had built with sub-tasks
    # of its own dropped a level and could no longer hold them.
    Given the rows
      | id | type  | parent |
      | D  | Phase |        |
      | T1 | Task  | D      |
      | T2 | Task  | D      |
    When "T2" is indented
    Then "T2" is a "Task"
    And "T2" sits under "T1"
    And "T2" can hold rows

  Scenario: A milestone stays a milestone wherever it lands
    # It marks a moment in whatever it is a moment in.
    Given the rows
      | id | type      | parent |
      | T  | Task      |        |
      | M  | Milestone |        |
    When "M" is indented
    Then "M" is a "Task"
    And "M" is still a milestone

  Scenario: A subtask lifted into a phase stays a task
    # Until somebody says otherwise, which is what the Type column is.
    Given the rows
      | id | type  | parent |
      | P  | Phase |        |
      | T  | Task  | P      |
      | S  | Task  | T      |
    When "S" is outdented
    Then "S" is a "Task"
    And "S" sits under "P"

  Scenario: A subtask lifted clear of everything stays a task
    # The top of the plan is a position, not a type.
    Given the rows
      | id | type | parent |
      | T  | Task |        |
      | S  | Task | T      |
    When "S" is outdented
    Then "S" is a "Task"
    And "S" is at the top level

  Scenario: A phase indented under a phase stays a phase
    # Nothing about a move changes what a row is.
    Given the rows
      | id | type  | parent |
      | P1 | Phase |        |
      | P2 | Phase |        |
    When "P2" is indented
    Then "P2" is a "Phase"

  Scenario: A round trip leaves the type where it started
    # Indent then outdent used to be a one-way trip down the levels: a
    # Task went in and a Subtask came out.
    Given the rows
      | id | type  | parent |
      | D  | Phase |        |
      | T1 | Task  | D      |
      | T2 | Task  | D      |
    When "T2" is indented
    And "T2" is outdented
    Then "T2" is a "Task"
    And "T2" sits under "D"

  # ---- indent and outdent act on everything selected ----------------------------
  # They acted on the clicked row alone, so selecting five rows and
  # pressing Indent moved the first one and left the other four. Order
  # is the whole difficulty: indenting moves a row under the sibling
  # above it, so a flat selection worked bottom-up comes out as a
  # staircase rather than a group; outdenting places a row after its
  # old parent's remaining children, so worked top-down it reverses
  # them. The two run in opposite directions for that reason.

  Scenario: Every selected row is indented
    # Not just the first one.
    Given the flat rows
      | id |
      | A  |
      | B  |
      | C  |
      | D  |
    When "B, C, D" are indented
    Then the shape is "A:-, B:A, C:A, D:A"

  Scenario: They land side by side rather than in a staircase
    # Worked top to bottom, which is what keeps the group together -
    # bottom to top puts each row under the one above it.
    Given the flat rows
      | id |
      | A  |
      | B  |
      | C  |
      | D  |
    When "D, C, B" are indented
    Then the parents are "A:-, B:A, C:A, D:A"

  Scenario: Outdenting keeps them in order
    # Worked bottom to top, which is the order that preserves theirs.
    Given the rows
      | id | type | parent |
      | A  | Task |        |
      | B  | Task | A      |
      | C  | Task | A      |
      | D  | Task | A      |
    When "B, C, D" are outdented
    Then the shape is "A:-, B:-, C:-, D:-"

  Scenario: A row that cannot move does not stop the rest
    # The first row of a group has nothing above it to go under; a
    # selection that happens to start at one should still indent
    # everything after it.
    Given the flat rows
      | id |
      | A  |
      | B  |
      | C  |
    When "A, B, C" are indented
    Then the parents are "A:-, B:A, C:A"

  Scenario: A branch moves once, not twice
    # Selecting a parent and its child indents the branch, not both
    # rows - the child is carried by its parent.
    Given the rows
      | id | type | parent |
      | A  | Task |        |
      | B  | Task |        |
      | C  | Task | B      |
    When "B, C" are indented
    Then the parents are "A:-, B:A, C:B"

  Scenario: Nothing selected moves nothing
    # And says so, rather than silently doing something.
    Given the flat rows
      | id |
      | A  |
      | B  |
    Then indenting nothing reports it moved nothing
    And outdenting nothing reports it moved nothing

  Scenario: An unknown id is ignored
    # A row deleted since the menu opened is not a reason to fail.
    Given the flat rows
      | id |
      | A  |
      | B  |
    When "B, gone" are indented
    Then "B" sits under "A"

  Scenario: The types follow the level each row lands at
    # The same rule a single indent uses; see child_type_for.
    Given the flat rows
      | id |
      | P  |
      | T1 |
      | T2 |
    And "P" is made a phase
    When "T1, T2" are indented
    Then "T1" is a "Task"
    And "T2" is a "Task"

  # ---- how deep a task sits, counted from one ------------------------------------
  # Counted from one because that is the number the Outline Level
  # column shows, and the number Microsoft Project shows in its own.

  Scenario: A root task is level one
    # The top of the plan, not level zero.
    Given a chain of one task
    Then "1" sits at level 1

  Scenario: Each step down adds one
    Given a chain of 4 tasks
    Then "1" sits at level 1
    And "2" sits at level 2
    And "3" sits at level 3
    And "4" sits at level 4

  Scenario: A task that is not in the plan is level one
    # An unknown row is drawn at the top rather than not at all.
    Given a chain of one task
    Then "nope" sits at level 1

  Scenario: A parent cycle does not hang
    # The level is asked for every row on every refresh, so a cycle
    # here is a window that stops responding rather than a wrong
    # number.
    Given a chain of 3 tasks
    When "1" is pointed at "3"
    Then "1" still answers a level of at least 1

  Scenario: A missing parent stops the count
    # An orphan is as deep as the chain that is actually there.
    Given a two-row plan whose second row's parent is gone
    Then "2" sits at level 1

  # ---- a task can answer its own length -------------------------------------------
  # working_calendar was written @classmethod above @property - a
  # spelling Python supported for exactly two releases. On 3.13 it does
  # not raise: the attribute hands back the property object itself, and
  # every caller fails with AttributeError - so on 3.13 the application
  # could not show a task list at all. These check the behaviour, not
  # the decorator.

  Scenario: It hands back a calendar
    # Not a property object, which is what 3.13 gave.
    Given a five-working-day task
    Then its working calendar is a real calendar

  Scenario: A task can be asked how long it is
    Given a five-working-day task
    Then it measures 5 working days

  Scenario: A task can be asked how far it reaches
    Given a five-working-day task
    Then its elapsed reach is 5 days

  Scenario: A task can settle its own start
    Given a five-working-day task
    Then its start settles on "2026-01-05"

  Scenario: No source stacks classmethod over property
    # The general guard: on the versions where the chain still works
    # there is nothing wrong to observe, so this reads the source and
    # is meant to fail before the code reaches a Python that removed it.
    Then no module stacks classmethod over property
