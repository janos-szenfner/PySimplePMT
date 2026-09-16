@completion
Feature: The completion a parent takes from the work under it

  Each level of the plan counts what is under it differently - a Task
  averages its sub-tasks' percentages, a Phase averages its tasks
  evenly, and anything else weights its children by how long they run -
  and which rule is applied to what is the sort of thing that is
  quietly wrong for a long time. The rules are set out in
  models.rolled_up_progress; these are the same rules, written as
  arithmetic somebody can check.

  Scenario: A full sub-task counts as done
    # 100% is the ticked state.
    Then a "Subtask" at 100 percent is completed

  Scenario: An empty sub-task does not
    # 0% is the unticked one.
    Then a "Subtask" at 0 percent is not completed

  Scenario: A part-finished sub-task does not count as done
    # Anything short of 100 is unfinished. Nothing on the form can
    # produce this - a sub-task is entered with a tick box - but an
    # imported file can carry it, and a job half done is not a job
    # done.
    Then a "Subtask" at 60 percent is not completed

  Scenario: None done is none counted
    # A Task with sub-tasks averages their percentages - which is what
    # counting ticks was: these all hold 0 or 100, and the average of
    # those is the proportion ticked.
    Given a "Task" parent
    When it holds two "Subtask" children at 0 and 0 percent
    Then the roll-up is 0

  Scenario: Half done is half counted
    # One of two ticked is half.
    Given a "Task" parent
    When it holds two "Subtask" children at 100 and 0 percent
    Then the roll-up is 50

  Scenario: All done is all counted
    # Every box ticked is finished.
    Given a "Task" parent
    When it holds two "Subtask" children at 100 and 100 percent
    Then the roll-up is 100

  Scenario: Length does not come into it
    # A checklist is counted, not weighted: four sub-tasks of an hour
    # each are four boxes like any other four, so a ticked short one
    # counts the same as a ticked long one.
    Given a "Task" parent
    When it holds two "Subtask" children of 1 and 99 days at 100 and 0 percent
    Then the roll-up is 50

  Scenario: A third rounds to a whole percent
    # One of three is 33, not 33.3.
    Given a "Task" parent
    When it holds three "Subtask" children at 100, 0 and 0 percent
    Then the roll-up is 33

  Scenario: Other parents weight by days
    # Ten finished days of thirty is a third of the way through. This
    # was the Deliverable's rule, and Deliverable is no longer a type a
    # plan can hold; the rule stays as the answer for anything that
    # comes to have children and is neither a Phase nor a Task - a plan
    # can arrive from a file holding whatever its own format allowed.
    Given a "Workstream" parent
    When it holds two "Task" children of 10 and 20 days at 100 and 0 percent
    Then the roll-up is 33

  Scenario: Part-finished tasks count for their part
    # Half of a fortnight is a week's worth.
    Given a "Workstream" parent
    When it holds two "Task" children of 14 and 14 days at 50 and 0 percent
    Then the roll-up is 25

  Scenario: Zero-length children are averaged instead
    # With nothing to weight by, the tasks are averaged - a parent
    # holding only milestones has no days in it, and dividing by that
    # total would be dividing by nothing.
    Given a "Workstream" parent
    When it holds two "Milestone" children at 100 and 0 percent
    Then the roll-up is 50

  Scenario: A phase averages its tasks
    # Two tasks, one done, is half the phase.
    Given a "Phase" parent
    When it holds two "Task" children of 1 and 1 days at 100 and 0 percent
    Then the roll-up is 50

  Scenario: A phase ignores task length too
    # A longer task is not a larger share of the phase - tasks are the
    # units a phase is scoped in; the same two at 100% and 0% make half
    # a phase however long either runs.
    Given a "Phase" parent
    When it holds two "Task" children of 2 and 200 days at 100 and 0 percent
    Then the roll-up is 50

  Scenario: A container with nothing in it is nothing done
    # No work under it, none of it done.
    Then an empty "Phase" rolls up 0 and an empty "Workstream" rolls up 0

  Scenario: A percentage over a hundred is clamped
    # A child outside 0 to 100 does not carry its parent outside it.
    # Task rejects such a value on the way in, so this is set past it -
    # which is the only way one arrives, an imported file having been
    # read into a task that was already built.
    Given a "Workstream" parent
    When it holds a "Task" child set past its guard to 400 percent
    Then the roll-up is 100

  Scenario: A negative percentage is clamped
    # Nor below it.
    Given a "Workstream" parent
    When it holds a "Task" child set past its guard to -50 percent
    Then the roll-up is 0

  Scenario: A ticked sub-task reaches the phase
    # A phase over two tasks, one of them over sub-tasks: one of two
    # sub-tasks ticked carries all the way up.
    Given a phase over a sub-tasked task and a part-done task
    When subtask "S1" is ticked and the plan is settled
    Then "T1" reads 50, "T2" reads 40 and "P" reads 45

  Scenario: Unticking it again carries back up
    # The cascade runs on the way down as well as up.
    Given a phase over a sub-tasked task and a part-done task
    When subtask "S1" is ticked and the plan is settled
    And subtask "S1" is unticked and the plan is settled
    Then "T1" reads 0 and "P" reads 20

  Scenario: A task without sub-tasks keeps what was typed on it
    # Nothing underneath it means nothing to overrule it.
    Given a phase over a sub-tasked task and a part-done task
    When the plan is settled
    Then "T2" reads 40
