Feature: Link Tasks and Unlink Tasks
  Linking rows one after another is how a plan gets its shape, and
  typing numbers into the Predecessors column is the slow way round.
  These two buttons do to a selection what the reference tool's chain
  icons do: chain the rows Finish-to-Start down the list, and break
  those links again.

  The part worth guarding is the order. A chain is only right if it
  runs the way the plan reads, and the selection it is built from does
  not arrive in that order - a Treeview hands back the rows in the
  order they were added to the selection, so shift-clicking upwards
  gives them bottom-first.

  The plain plan is four unlinked tasks - "001 Alpha", "002 Beta",
  "003 Gamma", "004 Delta" - one after another down the list, each
  starting 2026-08-19 for two days.

  # ---- chaining a selection Finish-to-Start ----------------------------------

  Scenario: Each row is chained to the one before it
    # Not all of them to the first.
    Given a plan of four unlinked tasks
    When "001, 002, 003" are linked
    Then "001" waits for nothing
    And "002" waits for "001"
    And "003" waits for "002"

  Scenario: The chain runs in grid order, however the rows were picked
    # A Treeview reports a selection in the order rows were added to
    # it, so shift-clicking upwards hands them back bottom-first. A
    # chain built from that would run backwards through the plan.
    Given a plan of four unlinked tasks
    When "003, 001, 002" are linked
    Then "002" waits for "001"
    And "003" waits for "002"

  Scenario: The link is finish-to-start with no lag
    # Which is what a plain link means.
    Given a plan of four unlinked tasks
    When "001, 002" are linked
    Then the link into "002" from "001" is a hard finish-to-start

  Scenario: It says which pairs it joined
    # So the caller can tell whether anything happened.
    Given a plan of four unlinked tasks
    When "001, 002, 003" are linked
    Then the pairs joined are "001 > 002, 002 > 003"

  Scenario: A row with a predecessor is left alone
    # Links a row already holds survive, and it gains none. A successor
    # that already waits for something is skipped: the row is sequenced
    # already, and adding the row above it as well would only restate -
    # or fight - the link it has. See issue #18.
    Given a plan of four unlinked tasks
    And "003" already waits for "004"
    When "002, 003" are linked
    Then nothing was joined
    And "003" waits for "004"

  Scenario: Linking the same rows twice changes nothing
    # The second press has nothing to add.
    Given a plan of four unlinked tasks
    When "001, 002" are linked
    And "001, 002" are linked again
    Then nothing was joined
    And "002" waits for "001"

  Scenario: One row is nothing to chain
    # A chain needs two ends.
    Given a plan of four unlinked tasks
    When "001" is linked alone
    Then nothing was joined
    And "001" waits for nothing

  Scenario: A row that is in no plan is left out
    # A stale id does not break the chain around it.
    Given a plan of four unlinked tasks
    When "001, nonexistent, 002" are linked
    Then "002" waits for "001"

  Scenario: A pair that would close a loop is skipped
    # And the rest of the chain is still made - refusing the whole
    # selection would mean one awkward pair in the middle doing
    # nothing at all, with the reason buried.
    Given a plan of four unlinked tasks
    And "001" already waits for "002"
    When "001, 002, 003" are linked
    Then the pairs joined are "002 > 003"
    And "002" waits for nothing
    And "003" waits for "002"

  # ---- breaking the links again ----------------------------------------------

  Scenario: It removes the links between the chosen rows
    # The chain the button made, taken back.
    Given a plan of four unlinked tasks
    And "001, 002, 003" are linked
    When "001, 002, 003" are unlinked
    Then "002" waits for nothing
    And "003" waits for nothing

  Scenario: A link outside the selection is left alone
    # The user pointed at these rows and not at that one.
    Given a plan of four unlinked tasks
    And "001, 002, 003" are linked
    And "003" also waits for "004"
    When "002, 003" are unlinked
    Then "003" waits for "004"

  Scenario: One row loses every link it is part of
    # There is no "between" for a single row, and unlinking it
    # otherwise would do nothing at all.
    Given a plan of four unlinked tasks
    And "001, 002, 003" are linked
    When "002" is unlinked alone
    Then "002" waits for nothing
    And "003" waits for nothing
    And the pairs broken are "001 > 002, 002 > 003"

  Scenario: It says which links it removed
    # Empty when there was nothing between the rows.
    Given a plan of four unlinked tasks
    When "001, 002" are unlinked
    Then nothing was broken

  Scenario: Nothing selected is nothing to do
    # Rather than every link in the plan.
    Given a plan of four unlinked tasks
    And "001, 002" are linked
    When nothing is unlinked
    Then nothing was broken
    And "002" waits for "001"

  # ---- undoing a link undoes what the link did to the schedule -----------------
  # Linking reschedules, and the reschedule used to run after the undo
  # entry was recorded - so undo took the link out and left the row
  # sitting where the link had pushed it. A plan half reverted is worse
  # than either end of it: the column says the rows are not linked and
  # the dates say they are. The dates are part of the snapshot now, and
  # the rescheduling runs inside the entry (SnapshotCommand.FIELDS).

  Scenario: The link moves the row it pushes
    # Otherwise there would be nothing to put back.
    Given two unlinked tasks tracked for undo
    When the link is made the way the task list makes it
    Then the dates moved

  Scenario: Undo puts the dates back with the link
    # Not the link alone.
    Given two unlinked tasks tracked for undo
    When the link is made the way the task list makes it
    And undo is run
    Then the dates are back
    And "002" waits for nothing

  Scenario: Redo moves them again
    # The snapshot after the action carries the dates too.
    Given two unlinked tasks tracked for undo
    When the link is made the way the task list makes it
    And undo is run
    And redo is run
    Then the dates move again

  Scenario: The snapshot names every field scheduling writes
    # A field the passes write and the snapshot does not hold is a
    # field undo cannot put back.
    Then the snapshot covers "start_date, end_date, duration"

  # ---- what the toolbar offers, and what answers to the keyboard ----------------

  Scenario: The row carries both icons in order
    # Between the dividers, after the group that acts on a row.
    Then "link" sits between "outdent" and "unlink"
    And "unlink" is followed by a divider

  Scenario: Both icons have a drawing
    # Without one the button shows the name's first letter instead.
    Then "link" and "unlink" have icons

  Scenario: Both have a handler on the toolbar
    # The row names them; Toolbar has to answer to those names.
    Then "link_selected" and "unlink_selected" are real methods

  Scenario: They are live only with a plan open
    # Like everything else that acts on the task list.
    Then "link" and "unlink" are active only with a project open

  Scenario: The keys carry this platform's modifier
    # Command on a Mac, Control elsewhere; see gantt_app.utils.shortcuts.
    Then F2 is bound under this platform's modifier
    And Shift-F2 is bound under it too

  Scenario: The captions are written the way the platform writes them
    # A caption promising a key that is not bound is worse than none.
    Then the F2 captions read like this platform's

  Scenario: The tooltips name the keys
    # So the row says what it answers to.
    Then the "link" tooltip names F2
    And the "unlink" tooltip names Shift-F2

  # ---- a collector is linked by moving what is inside it -------------------------
  # A project manager linked a selection that included collectors:
  # "the link button sort of works, but on the collectors the dates and
  # the sequencing are completely shredded. So much so that by magic it
  # became 2027, and the row after it didn't follow, it's just tied
  # there with a red dot." Three faults, and each scenario covers one:
  # a chain built in reading order tied every collector to the first
  # row inside it, which is a contradiction rather than a chain; the
  # plan then never settled, so every action moved the dates further
  # out; and a link to a collector was drawn and never obeyed.

  Scenario: A row is never linked to what it holds
    # Its dates are rolled up from that row, so it would be waiting for
    # a date computed from itself.
    Given a plan of two collectors each holding one row
    When "001, 002" are linked
    Then nothing was joined
    And "002" waits for nothing

  Scenario: A selection chains every row it can
    # The chain runs down the whole selection, not just its top level.
    # A parent is never linked to its own child, but the row that
    # follows a finished branch waits on the branch's last row.
    Given a plan of two collectors each holding one row
    When the whole plan is linked
    Then the pairs joined are "002 > 003"

  Scenario: A collector moves when it is linked
    # The red dot with nothing behind it.
    Given a plan of two collectors each holding one row
    When "001, 003" are linked
    And the schedule is applied
    Then "003" starts after "001" ends

  Scenario: What it holds moves with it
    # Otherwise the collector stops bracketing its own rows.
    Given a plan of two collectors each holding one row
    When "001, 003" are linked
    And the schedule is applied
    Then "004" shares the dates of "003"

  Scenario: The plan settles
    # A plan that never settles is left wherever the last pass put it,
    # and every action runs the pass again - which is how one starting
    # in August came to start the following January.
    Given a plan of two collectors each holding one row
    When "001, 003" are linked
    Then applying the schedule reports no "did not settle" warning

  Scenario: The dates stop moving
    # Doing it again changes nothing.
    Given a plan of two collectors each holding one row
    When "001, 003" are linked
    And the schedule is applied
    Then four more passes move nothing

  Scenario: A collector stops claiming a length it does not have
    # The fault underneath the drift: a summary kept the duration it
    # was created with, the working-calendar pass rebuilt its finish
    # from that number, and the roll-up rebuilt it from the children.
    # The two took turns for all twelve passes.
    Given a plan of two collectors each holding one row
    When "001" claims 9 days
    And the schedule is applied
    Then "001" holds the days its bracket measures

  # ---- issue #18: a selection that includes sub-tasks must chain them too --------
  # topmost_of dropped every selected row that had a selected ancestor,
  # so selecting the whole plan collapsed to the five outermost rows and
  # the chain touched none of the siblings inside the branches. The plan
  # below is the reported one; the expected chain is 4->5, 6->7, 7->8
  # and 10->11, with the rows that already wait for something left
  # exactly as they were.

  Scenario: The chain runs through the branches
    # Every free row waits for the selected row above it.
    Given the plan from issue 18
    When the whole plan is linked
    Then the pairs joined are "004 > 005, 006 > 007, 007 > 008, 010 > 011"

  Scenario: Rows that already wait are untouched
    # Existing predecessors are kept, and no new ones are added.
    Given the plan from issue 18
    When the whole plan is linked
    Then "003" waits for "001"
    And "009" waits for "003"
