@progress_field
Feature: The completion a row carries and the one it takes from below

  It began as "the progress bar is not viewable on a different Mac",
  with two editors side by side: one showing "Progress (%): 30" and one
  showing a "Completed:" tick and no percentage. Nothing about it
  depended on the machine - they were a Task and a Sub-task, and the
  editor deliberately offered a different control for each.

  The reason it did was the roll-up: a Task counted how many of its
  sub-tasks were ticked, so a sub-task at 60% would have counted for
  nothing, and a percentage box would have been a number the form took
  and the plan ignored.

  Asked for, and now the case: a sub-task carries a percentage like
  every other row, and the Task above it averages those percentages
  instead of counting ticks. Evenly, which is what counting ticks was
  all along - a checklist holds nothing but 0 and 100, and the average
  of those is the proportion ticked, so every plan that existed before
  this reads exactly as it did.

  The editor scenarios need a display and skip without one; the roll-up
  scenarios are model-only.

  Scenario: A task is offered a percentage
    # As it always was.
    Given a plan with a phase, tasks, a subtask and a milestone
    Then the editor for "003" offers a percentage box

  Scenario: A subtask is offered a percentage
    # The change asked for. It was a tick, because a Task counted how
    # many of its sub-tasks were ticked and a 60% would have counted
    # for nothing. The Task averages percentages now, so 60% counts
    # for 60%.
    Given a plan with a phase, tasks, a subtask and a milestone
    Then the editor for "004" offers a percentage box

  Scenario: A phase and a summary task are offered a percentage
    # Shown but not editable: they read theirs from what is under.
    Given a plan with a phase, tasks, a subtask and a milestone
    Then the editors for "001,003" offer a percentage box

  Scenario: A milestone is offered a percentage
    Given a plan with a phase, tasks, a subtask and a milestone
    Then the editor for "005" offers a percentage box

  Scenario: No row is offered a tick any more
    # One control, so there is one thing for the form to read back.
    Given a plan with a phase, tasks, a subtask and a milestone
    Then the editors for "001,002,003,004,005" offer no tick

  Scenario: Nothing about the form asks the machine
    # Which was the whole answer to "it is not viewable on a different
    # Mac": the two forms compared were a Task and a Sub-task.
    Then the progress builder's source names no platform

  Scenario: A checklist reads as it always did
    # Nothing but ticks and empty boxes, and the same answers.
    Then every checklist rolls up to its proportion ticked

  Scenario: A part-finished subtask now counts for its part
    # Which is the point of the change.
    Then subtasks "60,0" roll up to 30
    And subtasks "25,50,75" roll up to 50

  Scenario: It is still counted rather than weighted
    # A checklist is a checklist. Four sub-tasks of an hour each are
    # four entries like any other four; length is the Phase's
    # business, one level up.
    Then a done one-day subtask and an empty twenty-day one average to 50

  Scenario: It carries all the way up a plan
    # A sub-task at 60% reaches the phase above it.
    Given a nested plan with a subtask at 60 percent
    When the summaries are rolled up
    Then tasks "001,003" read 53 percent
