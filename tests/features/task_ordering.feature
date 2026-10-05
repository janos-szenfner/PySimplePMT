Feature: Reordering tasks within a project
  Ordering lives on Project rather than in the task list widget, so the
  rules a move has to obey - staying among siblings, carrying sub-tasks
  along, never losing a task - are all checked here without needing a
  display. The widget tests only cover the gesture that triggers a
  move.

  The ordering plan is three root tasks - "001 Alpha", "002 Beta",
  "003 Gamma" - the middle one carrying two sub-tasks "004" and "005".

  # ---- moving a task among its siblings ------------------------------------------

  Scenario: The starting order is the display order
    # add_task keeps the flat list in hierarchy order, so a sub-task
    # lands behind its parent even when it is added after later roots.
    # The "No." column counts down this list (issue #64).
    Given the ordering plan
    Then the order reads "001, 002, 004, 005, 003"

  Scenario Outline: A move to "<direction>"
    Given the ordering plan
    When "003" is moved "<direction>"
    Then the move worked
    And the order reads "<order>"

    Examples:
      | direction | order                     |
      | top       | 003, 001, 002, 004, 005   |
      | up        | 001, 003, 002, 004, 005   |

  Scenario Outline: Another move to "<direction>"
    Given the ordering plan
    When "001" is moved "<direction>"
    Then the move worked
    And the order reads "<order>"

    Examples:
      | direction | order                     |
      | down      | 002, 004, 005, 001, 003   |
      | bottom    | 002, 004, 005, 003, 001   |

  Scenario: A parent carries its sub-tasks
    Given the ordering plan
    When "002" is moved "top"
    Then the order reads "002, 004, 005, 001, 003"

  Scenario: Sub-tasks move among themselves
    # A sub-task reorders inside its parent, not into the root list.
    Given the ordering plan
    When "005" is moved "top"
    Then the order reads "001, 002, 005, 004, 003"
    And "005" still belongs to "002"

  Scenario: Moving past the end does nothing
    # A task already at one end reports that it did not move.
    Given the ordering plan
    Then "001" refuses to move "up"
    And "001" refuses to move "top"
    And "003" refuses to move "down"
    And "003" refuses to move "bottom"
    And the order reads "001, 002, 004, 005, 003"

  Scenario: An only child cannot move
    # A sub-task with no siblings has nowhere to go.
    Given the ordering plan
    When "005" is removed
    Then "004" refuses to move "top"
    And "004" refuses to move "bottom"

  Scenario: An unknown task is ignored
    Given the ordering plan
    Then "nope" refuses to move "top"

  Scenario: An unknown target is rejected
    # A misspelled move target raises rather than moving silently.
    Given the ordering plan
    Then moving "001" "sideways" raises an error

  Scenario: No task is lost
    Given the ordering plan
    Then moving "003:top, 002:bottom, 005:up, 001:down" loses no task

  Scenario: An orphaned task survives a move
    # Rebuilding the list by walking down from the roots never reaches
    # an orphan, so one would vanish on the first move without the
    # sweep that collects whatever the walk missed.
    Given the ordering plan
    And the orphan "099" is added
    When "003" is moved "top"
    Then "099" is still there

  # ---- dropping onto a sibling's position -----------------------------------------

  Scenario: The drop lands in the target's position
    Given the drop plan
    When "003" is dropped before "001"
    Then the move worked
    And the order reads "003, 001, 002, 004"

  Scenario: Dropping onto a non-sibling is refused
    # A sub-task cannot be dropped onto a root task.
    Given the drop plan
    When "004" is dropped before "001"
    Then the move was refused
    And the order reads "001, 002, 004, 003"

  Scenario: Dropping onto itself does nothing
    Given the drop plan
    When "001" is dropped before "001"
    Then the move was refused

  Scenario: Unknown ids are ignored
    Given the drop plan
    Then dropping "001" before "nope" is refused
    And dropping "nope" before "001" is refused

  # ---- indenting makes a task a sub-task of the row above it -----------------------

  Scenario: It goes under the row above
    Given three root tasks "A, B, C"
    When "B" is indented
    Then "B" sits under "A"

  Scenario: It keeps its type
    # The level changes; what the row is does not. A Task indented
    # under a Task used to come back a Subtask, which took away its
    # ability to hold the sub-tasks it was built with.
    Given three root tasks "A, B, C"
    When "B" is indented
    Then "B" is a "Task"

  Scenario: The first row cannot indent
    # There is nothing above it to go under.
    Given three root tasks "A, B, C"
    Then "A" cannot indent
    And indenting "A" is refused

  Scenario: It can nest further
    # Indenting twice puts a task two levels down.
    Given three root tasks "A, B, C"
    When "B" is indented
    And "C" is indented
    And "C" is indented
    Then "C" sits under "B"

  Scenario: A task carries its sub-tasks
    # The whole branch moves down a level.
    Given three root tasks "A, B, C"
    And "B" holds the sub-task "B1"
    When "B" is indented
    Then "B" sits under "A"
    And "B1" sits under "B"

  Scenario: A milestone cannot take children
    # A milestone marks a moment rather than spanning one, so it cannot
    # bracket sub-tasks - and the next reschedule would promote them
    # straight back out again.
    Given three root tasks "A, B, C"
    And "A" is made a milestone
    Then "B" cannot indent
    And indenting "B" is refused

  Scenario: Indenting under a predecessor is allowed
    # The ordinary way a phase gets built out of the work that follows
    # it. Refusing it left Indent greyed out on nearly every row of a
    # normal plan, where each task follows the one above.
    Given three root tasks "A, B, C"
    And "B" waits for "A"
    Then "B" can indent

  Scenario: The link to the new parent is dropped
    # A task cannot wait for something it is now part of: a summary
    # takes its finish from its children, so a child that must also
    # start after that summary finishes has no possible date.
    Given three root tasks "A, B, C"
    And "B" waits for "A"
    When "B" is indented
    Then "B" waits for nothing

  Scenario: An unrelated link survives the indent
    # Only links onto the new ancestors go.
    Given three root tasks "A, B, C"
    And "B" waits for "C"
    When "B" is indented
    Then "B" waits for "C"

  Scenario: A sub-task's link to the new parent is dropped too
    # The whole branch is checked, not only the task itself.
    Given three root tasks "A, B, C"
    And "B" holds the sub-task "B1"
    And "B1" waits for "A"
    When "B" is indented
    Then "B1" waits for nothing

  Scenario: The plan still settles afterwards
    # The point of dropping the link: left in place it makes the
    # schedule unsatisfiable, and rescheduling gives up after its pass
    # limit instead of settling.
    Given three root tasks "A, B, C"
    And "B" waits for "A"
    When "B" is indented
    Then rescheduling settles
    And rescheduling again changes nothing

  Scenario: A cycle in the links does not hang
    # The walk is guarded, so a corrupt file cannot lock it up.
    Given three root tasks "A, B, C"
    And "B" waits for "C"
    And "C" waits for "B"
    When "C" is indented
    Then the order reads "A, B, C"

  Scenario: The row stays in place
    # A task indented under the row above does not jump elsewhere.
    Given three root tasks "A, B, C"
    When "B" is indented
    Then the order reads "A, B, C"

  Scenario: Indenting something that is not there does nothing
    Given three root tasks "A, B, C"
    Then indenting "nope" is refused

  # ---- outdenting lifts a task to sit beside its parent -----------------------------
  # A parent "A" with two sub-tasks "B" and "C", and a task "D" after it.

  Scenario: It leaves its parent
    Given the outdent plan
    When "B" is outdented
    Then "B" is at the top level

  Scenario: It keeps its type at the top level
    # The top of the plan is a position rather than a type.
    Given the outdent plan
    When "B" is outdented
    Then "B" is a "Task"

  Scenario: It stays a task when still nested
    # Coming out of a nested level leaves it a task.
    Given the outdent plan
    When "C" is indented
    And "C" is outdented
    Then "C" sits under "A"
    And "C" is a "Task"

  Scenario: A root task cannot outdent
    # There is no level above the top one.
    Given the outdent plan
    Then "A" cannot outdent
    And outdenting "A" is refused

  Scenario: It lands after its old parent
    # The task slots in behind the branch it came out of.
    Given the outdent plan
    When "B" is outdented
    Then the order reads "A, C, B, D"

  Scenario: It carries its sub-tasks
    # The whole branch comes up a level.
    Given the outdent plan
    When "C" is indented
    And "B" is outdented
    Then "B" is at the top level
    And "C" sits under "B"

  Scenario: Outdenting something that is not there does nothing
    Given the outdent plan
    Then outdenting "nope" is refused

  Scenario: Outdent then indent restores the level
    # A task put back returns to the parent it came from. Its position
    # among that parent's children does not come back: going out moved
    # it past its former siblings, and coming in again puts it at the
    # end. Move up is the way back.
    Given the outdent plan
    When "B" is outdented
    And "B" is indented
    Then "B" sits under "A"
    And "B" is a "Task"
    And the order reads "A, C, B, D"

  # ---- the structure snapshot -----------------------------------------------------
  # Indenting rewrites parent_task_id and task_type on the tasks
  # themselves, so restoring an ordering alone leaves every parent
  # where the indent put it - both orderings hold the same objects.

  Scenario: It restores the hierarchy
    # Parent and type come back, not just the order.
    Given three root tasks "A, B, C"
    And a structure snapshot
    When "B" is indented
    And the snapshot is restored
    Then "B" is at the top level
    And "B" is a "Task"

  Scenario: It restores the order
    Given three root tasks "A, B, C"
    And a structure snapshot
    When "C" is moved "top"
    And the snapshot is restored
    Then the order reads "A, B, C"

  # ---- the stored list is the "No." sequence, not a shadow of it (#64) ---------------
  # The number beside each row counts down display_order(). The list
  # itself is what to_dict saves and the exports walk, so any add or
  # re-parent that leaves it different from the drawn order writes a
  # file whose plan order is not the one on screen.

  Scenario: A child added late lands under its parent
    # Append-at-end would leave the stored order unlike the shown one.
    Given a plan of phase "001" and root "002"
    When a child "003" is added under "001"
    Then the order reads "001, 003, 002"
    And the stored order is the display order

  Scenario: The numbers follow the stored order
    Given a plan of phase "001" and root "002"
    When a child "003" is added under "001"
    Then the numbers read "001:1, 003:2, 002:3"

  Scenario: A divergent file is normalised on load
    # A plan saved out of hierarchy order opens in display order.
    Given a plan of phase "001" and root "002"
    When the saved file gains a child "003" under "001" at the end
    Then the order reads "001, 003, 002"
    And the stored order is the display order

  # ---- the sibling group a move is confined to ---------------------------------------
  # Two roots "001" and "002", the second holding "003" and "004".

  Scenario: Root tasks are siblings
    Given the siblings plan
    Then the siblings of "001" are "001, 002"

  Scenario: Sub-tasks group under their parent
    Given the siblings plan
    Then the siblings of "003" are "003, 004"

  Scenario: An unknown task has no siblings
    Given the siblings plan
    Then "nope" has no siblings
