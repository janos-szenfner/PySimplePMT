Feature: The System UI tab in Project Settings
  The old View > System UI mode submenu became a day/night toggle and a
  Sync with System button on a Settings tab, wired to the same
  ThemeController. Display-gated, like the other Settings-window tests.

  Scenario: There is a System UI tab
    Given a settings window on a system-following controller
    Then "System UI" is among the tabs

  Scenario: The toggle reflects a dark appearance
    Given a settings window on a dark controller
    Then the theme toggle is on

  Scenario: Toggling on sets night mode
    Given a settings window on a system-following controller
    When the theme toggle is switched on
    Then the controller is asked for dark mode

  Scenario: Toggling off sets day mode
    Given a settings window on a dark controller
    When the theme toggle is switched off
    Then the controller is asked for light mode

  Scenario: The sync button follows the system
    Given a settings window on a dark controller
    When sync with system is pressed
    Then the controller follows the system

  Scenario: The status names who is deciding
    Given a settings window on a system-following controller
    Then the theme status says "Following the system"

  Scenario: Without a controller the controls are disabled
    Given a settings window without a controller
    Then the theme toggle is disabled
