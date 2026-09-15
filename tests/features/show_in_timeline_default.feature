Feature: A new task starts off the timeline
  The create dialog's stand-in for a new task carries
  show_in_timeline=False, so the Gantt stays empty until the planner
  puts work on it. The model default is unchanged - loaded plans,
  imports and existing tasks keep whatever they already have.

  Scenario: A new task starts off the timeline
    When a create-dialog template is built for a "Task"
    Then the template is off the timeline

  Scenario: A new milestone starts off the timeline
    When a create-dialog template is built for a "Milestone"
    Then the template is off the timeline

  Scenario: A new subtask starts off the timeline
    Given a parent task exists
    When a create-dialog template is built for a "Subtask" under it
    Then the template is off the timeline

  Scenario: A loaded task keeps the model's default
    When a task is built the way importers and file loads build one
    Then the task is on the timeline
