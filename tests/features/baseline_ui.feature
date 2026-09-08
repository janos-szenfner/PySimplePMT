Feature: Baseline management end-to-end UI
  As a project manager
  I want to set, clear, compare, rename and view baselines
  So that I can track schedule and cost variance from a saved plan.

  Background:
    Given the application is started
    And a project with sample tasks exists

  Scenario: Baseline manager is wired to the application
    Then the toolbar owns the baseline manager
    And the baseline compare dropdown shows "None (Current Only)"

  Scenario: Baseline settings tab shows ten slots
    When the user opens the baseline settings tab
    Then the settings window shows 10 baseline rows
    And the first slot is named "Baseline 1"

  Scenario: Rename a baseline slot in settings
    When the user opens the baseline settings tab
    And the user renames slot 1 to "Initial Approved Scope"
    And the user saves the baseline settings
    And the user sets baseline 1 for the entire project
    Then the toolbar dropdown labels include "Initial Approved Scope"

  Scenario: Settings rejects duplicate slot names
    When the user opens the baseline settings tab
    And the user renames slot 1 to "Approved"
    And the user renames slot 2 to "Approved"
    And the user saves the baseline settings
    Then a baseline settings error is shown

  Scenario: Set baseline for the entire project
    When the user sets baseline 1 for the entire project
    Then baseline 1 is set
    And the baseline compare dropdown shows "Baseline 1 (Saved:"
    And the toolbar dropdown labels include "Baseline 1"

  Scenario: Set baseline for selected tasks only with roll-up
    When the user selects the task named "Task A"
    And the user sets baseline 1 for selected tasks with roll-up
    Then baseline 1 is set
    And the selected task has a baseline snapshot

  Scenario: Clear an entire baseline
    Given the user has set baseline 1 for the entire project
    When the user clears baseline 1 for the entire project
    Then baseline 1 is unset
    And the baseline compare dropdown shows "None (Current Only)"

  Scenario: Clear selected tasks from a baseline
    Given the user has set baseline 1 for the entire project
    When the user clears the selected task from baseline 1
    Then the selected task has no baseline snapshot

  Scenario: Compare with Baseline dropdown selects an active baseline
    Given the user has set baseline 1 for the entire project
    When the user selects "Baseline 1" from the compare dropdown
    Then the active baseline is 1
    And the task list shows the baseline variance columns

  Scenario: Task list variance columns contain correct data
    Given the user has set baseline 1 for the entire project
    When the task "Task A" is shifted one day later
    And the user selects "Baseline 1" from the compare dropdown
    Then the task list row for "Task A" shows start variance of "+1d"

  Scenario: Gantt chart draws baseline overlay
    Given the user has set baseline 1 for the entire project
    When the user selects "Baseline 1" from the compare dropdown
    And the Gantt chart is drawn
    Then the Gantt chart has an active baseline slot
    And the rendered image contains the baseline overlay

  Scenario: End-to-end baseline capture and comparison
    Given the user has set baseline 1 for the entire project
    When the user selects "Baseline 1" from the compare dropdown
    Then the task list shows the baseline variance columns
    And the Gantt chart is drawn with the baseline overlay
