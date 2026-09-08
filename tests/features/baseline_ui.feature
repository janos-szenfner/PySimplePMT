Feature: Baseline management end-to-end UI
  As a project manager
  I want to set, clear, compare, rename and view baselines
  So that I can track schedule and cost variance from a saved plan.

  Background:
    Given the application is started
    And a project with sample tasks exists

  Scenario: Baseline manager is wired to the application
    Then the toolbar owns the baseline manager
    And the Compare Baseline menu offers "None (Current Only)"
    And the Compare Baseline menu offers "Baseline 10"

  Scenario: Baseline settings tab shows ten slots
    When the user opens the baseline settings tab
    Then the settings window shows 10 baseline rows
    And the first slot is named "Baseline 1"

  Scenario: Rename a baseline slot in settings
    When the user opens the baseline settings tab
    And the user renames slot 1 to "Initial Approved Scope"
    And the user saves the baseline settings
    Then the first slot is named "Initial Approved Scope"

  Scenario: Settings rejects duplicate slot names
    When the user opens the baseline settings tab
    And the user renames slot 1 to "Approved"
    And the user renames slot 2 to "Approved"
    And the user saves the baseline settings
    Then a baseline settings error is shown

  Scenario: The Save button sits in a fixed footer with its message beside it
    When the user opens the baseline settings tab
    Then the baseline Save button is in the tab footer, not the scroll area
    And the baseline status message sits to the right of the Save button

  Scenario: Saving baseline settings confirms beside the button
    When the user opens the baseline settings tab
    And the user saves the baseline settings
    Then the baseline status message reads "Settings saved."

  Scenario: Set baseline for the entire project
    When the user sets baseline 1 for the entire project
    Then baseline 1 is set

  Scenario: Saving a baseline does not turn comparison on
    When the user sets baseline 1 for the entire project
    Then baseline 1 is set
    And no baseline is active
    And the Gantt chart has no active baseline slot

  Scenario: Set baseline for selected tasks only with roll-up
    When the user selects the task named "Task A"
    And the user sets baseline 1 for selected tasks with roll-up
    Then baseline 1 is set
    And the selected task has a baseline snapshot

  Scenario: Clear an entire baseline
    Given the user has set baseline 1 for the entire project
    When the user clears baseline 1 for the entire project
    Then baseline 1 is unset

  Scenario: Clear selected tasks from a baseline
    Given the user has set baseline 1 for the entire project
    When the user clears the selected task from baseline 1
    Then the selected task has no baseline snapshot

  Scenario: Compare with Baseline sub-menu selects an active baseline
    Given the user has set baseline 1 for the entire project
    When the user selects "Baseline 1" from the Compare Baseline sub-menu
    Then the active baseline is 1
    And the task list shows the baseline variance columns

  Scenario: Task list variance columns contain correct data
    Given the user has set baseline 1 for the entire project
    When the task "Task A" is shifted one day later
    And the user selects "Baseline 1" from the Compare Baseline sub-menu
    Then the task list row for "Task A" shows start variance of "+1d"

  Scenario: Gantt chart draws baseline overlay
    Given the user has set baseline 1 for the entire project
    When the user selects "Baseline 1" from the Compare Baseline sub-menu
    And the Gantt chart is drawn
    Then the Gantt chart has an active baseline slot
    And the rendered image contains the baseline overlay

  Scenario: End-to-end baseline capture and comparison
    Given the user has set baseline 1 for the entire project
    When the user selects "Baseline 1" from the Compare Baseline sub-menu
    Then the task list shows the baseline variance columns
    And the Gantt chart is drawn with the baseline overlay

  Scenario: Baseline settings tab shows a color picker per slot
    When the user opens the baseline settings tab
    Then a color picker is shown for every baseline slot

  Scenario: Selecting and saving a baseline color persists it
    When the user opens the baseline settings tab
    And the user picks "#ff0000" as the color for slot 1
    And the user saves the baseline settings
    Then baseline slot 1 has color "#ff0000"

  Scenario: Compare Baseline menu shows saved status and timestamp
    Given the user has set baseline 1 for the entire project
    And baseline 1 is being compared
    Then the Compare Baseline menu offers "Saved:"
    And the Compare Baseline menu offers "Active"

  Scenario: Gantt overlay uses the selected baseline color
    Given the user has set baseline 1 for the entire project
    And baseline slot 1 has color "#ff0000"
    And the task "Task A" is shifted one day later
    When the user selects "Baseline 1" from the Compare Baseline sub-menu
    And the Gantt chart is drawn
    Then the rendered image contains red baseline overlay pixels

  Scenario: Baselines persist through project save and load
    Given the user has set baseline 1 for the entire project
    And baseline slot 1 has color "#00ff00"
    And baseline 1 is being compared
    And the active baseline is 1
    When the project is saved to a temporary file
    And the project is loaded from the temporary file
    Then baseline 1 is still set
    And baseline slot 1 still has color "#00ff00"
    And the active baseline is 1
    And the saved task snapshot for "Task A" is restored

  Scenario: Renaming a slot updates the Compare Baseline menu
    When the user opens the baseline settings tab
    And the user renames slot 1 to "Initial Approved Scope"
    And the user saves the baseline settings
    Then the Compare Baseline menu offers "Initial Approved Scope"

  Scenario: Clearing a baseline updates the Compare Baseline menu status
    Given the user has set baseline 1 for the entire project
    When the user clears baseline 1 for the entire project
    Then the Compare Baseline menu offers "(Unset)"
