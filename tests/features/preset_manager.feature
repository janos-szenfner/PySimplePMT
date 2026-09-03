Feature: Built-in and custom style presets
  Four presets ship read-only; a reader adds their own, which the toolbar
  offers at once. See REQ-UI-020.

  # --- The read-only guardrails, which need no display ---

  @preset_manager
  Scenario: The four built-ins are always present
    Given a preset manager with an isolated settings file
    Then the built-in presets are Financial Milestone, Work Complete, Phase Gate / Approval and Summary Phase

  @preset_manager
  Scenario: A built-in cannot be deleted
    Given a preset manager with an isolated settings file
    When a built-in preset is deleted
    Then the deletion is refused
    And the four built-ins are still present

  @preset_manager
  Scenario: A built-in cannot be edited
    Given a preset manager with an isolated settings file
    When a built-in preset is renamed
    Then the change is refused
    And the built-in keeps its name

  # --- Custom presets ---

  @preset_manager
  Scenario: A custom preset is added and offered beside the built-ins
    Given a preset manager with an isolated settings file
    When a custom preset "Gold Star" is added
    Then the manager holds one custom preset
    And "Gold Star" appears after the built-ins

  @preset_manager
  Scenario: A custom preset survives a reload
    Given a preset manager with an isolated settings file
    When a custom preset "Kept" is added
    And the manager is reloaded from the same file
    Then the reloaded manager holds a custom preset named "Kept"

  @preset_manager
  Scenario: A custom preset can be edited
    Given a preset manager with an isolated settings file
    When a custom preset "Draft" is added
    And that custom preset is renamed to "Final"
    Then the manager holds a custom preset named "Final"

  @preset_manager
  Scenario: A custom preset can be deleted
    Given a preset manager with an isolated settings file
    When a custom preset "Temporary" is added
    And that custom preset is deleted
    Then the manager holds no custom presets

  # --- The broadcast ---

  @preset_manager
  Scenario: Adding a custom preset tells the listeners
    Given a preset manager with an isolated settings file
    And a listener subscribed to the manager
    When a custom preset "Broadcast" is added
    Then the listener was told once

  @preset_manager
  Scenario: A listener is told on an edit and a delete too
    Given a preset manager with an isolated settings file
    And a listener subscribed to the manager
    When a custom preset "Twice" is added
    And that custom preset is renamed to "Thrice"
    And that custom preset is deleted
    Then the listener was told three times

  # --- The toolbar menu, which needs a display ---

  @preset_manager
  @needs_display
  Scenario: With no custom presets the menu shows only the standard section
    Given a preset manager with an isolated settings file
    And a style bar reading that manager
    When the preset menu items are built
    Then there is a "STANDARD PRESETS" header
    And there is no "CUSTOM PRESETS" header

  @preset_manager
  @needs_display
  Scenario: A custom preset gives the menu a custom section
    Given a preset manager with an isolated settings file
    And a style bar reading that manager
    When a custom preset "Live" is added
    And the preset menu items are built
    Then there is a "STANDARD PRESETS" header
    And there is a "CUSTOM PRESETS" header
    And a preview row named "Live" is in the menu

  # --- The Settings tab, which needs a display ---

  @preset_manager
  @needs_display
  Scenario: The settings grid locks the built-ins
    Given a preset manager with an isolated settings file
    And a style-presets settings tab reading that manager
    Then every built-in row shows a locked badge
    And no built-in row offers Edit or Delete

  @preset_manager
  @needs_display
  Scenario: Adding a custom preset redraws the settings grid at once
    Given a preset manager with an isolated settings file
    And a style-presets settings tab reading that manager
    When a custom preset "Shown" is added
    Then the settings grid shows a row named "Shown"
    And that row offers Edit and Delete
