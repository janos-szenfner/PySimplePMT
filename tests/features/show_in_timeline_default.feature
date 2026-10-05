Feature: A new task starts off the timeline
  The create dialog's stand-in for a new task carries
  show_in_timeline=False, so the Gantt stays empty until the planner
  puts work on it. The model default follows (issue #72): a task built
  without the flag is off it too. A plan saved before the flag existed
  is the one exception - its tasks never recorded a choice, and off
  would hide rows the file meant drawn.

  Scenario: A new task starts off the timeline
    When a create-dialog template is built for a "Task"
    Then the template is off the timeline

  Scenario: A new milestone starts off the timeline
    When a create-dialog template is built for a "Milestone"
    Then the template is off the timeline

  Scenario: A new row under a parent starts off the timeline
    Given a parent task exists
    When a create-dialog template is built for a "Task" under it
    Then the template is off the timeline

  Scenario: A task built in code starts off the timeline
    When a task is built the way a new one is built in code
    Then the task is off the timeline

  Scenario: A plan saved before the flag existed still draws its rows
    When a task is loaded from a file that never recorded the flag
    Then the task is on the timeline

  Scenario: A new task runs one day
    # Issue #74: the create dialog used to seed a week; the reference
    # tool's default - and the ask - is one working day.
    When a create-dialog template is built for a "Task"
    Then the template runs one working day
