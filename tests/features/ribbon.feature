Feature: The ribbon
  The tabbed command band that took the place of the menu row and the
  icon row. Its buttons name the same actions the menus did; what changed
  is how they are arranged - captioned groups on tabbed pages, a quick
  access row and a File backstage.

  Background:
    Given a toolbar over an open plan

  @ribbon
  @needs_display
  Scenario: The strip carries the tabs
    Then the ribbon offers the tabs "Task", "View" and "Project"
    And the "Task" tab is showing

  @ribbon
  @needs_display
  Scenario: Picking a tab shows its page
    When the user picks the "View" tab
    Then the "View" tab is showing
    And the "Task" tab's page is not shown

  @ribbon
  @needs_display
  Scenario: The band is divided into captioned groups
    Then the "Task" tab has the groups "Clipboard", "Insert", "Tasks", "Outline", "Font" and "Progress"
    And the "View" tab has the groups "Views", "Resources", "Analysis", "Highlight", "Filter", "Appearance" and "Window"
    And the "Project" tab has the groups "Properties", "Baseline", "Calendar" and "Resources"

  @ribbon
  @needs_display
  Scenario: The formatting bar stands in the Font group
    Then the "Font" group holds the formatting bar

  @ribbon
  @needs_display
  Scenario: The progress controls stand in the Progress group
    Then the "Progress" group holds the progress controls

  @ribbon
  @needs_display
  Scenario: Quick access stays on the strip
    Then the strip offers the icons "save", "save_as", "undo" and "redo"

  @ribbon
  @needs_display
  Scenario: A ribbon button runs its action
    When the "paste" button is pressed
    Then the "paste_tasks" handler ran

  @ribbon
  @needs_display
  Scenario: The split button drops the work-item gallery
    When the "New Task" arrow is pressed
    Then a drop-down offers "Task...", "Phase...", "Subtask..." and "Milestone..."

  @ribbon
  @needs_display
  Scenario: The Compare gallery offers the baselines
    When the "Compare" gallery is opened
    Then it offers "None (Current Only)"

  @ribbon
  @needs_display
  Scenario: File opens the backstage
    When the user opens the File backstage
    Then the backstage is showing
    And the backstage offers "New Project...", "Open Project...", "Save", "Save As..." and "Close Project"
    When the user goes back
    Then the backstage is gone

  @ribbon
  @needs_display
  Scenario: The ribbon folds away
    When the ribbon is folded
    Then the band is not shown
    When the ribbon is unfolded
    Then the "Task" tab is showing

  @ribbon
  @needs_display
  Scenario: Every button reaches a handler
    Then every action the ribbon names resolves to a callable

  @ribbon
  @needs_display
  Scenario: The menus still answer behind the ribbon
    Then the menu bar still offers "Baseline" under "Actions"
