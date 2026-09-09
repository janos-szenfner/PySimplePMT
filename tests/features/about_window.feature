Feature: About PySimplePMT window
  The About window shows the logo, name, version and licence

  @about @needs_display
  Scenario: About window opens with the logo and version
    Given a Tk root window
    When the About window is opened
    Then the About window should exist
    And the About window should show the application version
    And the About window should carry the logo image

  @about @needs_display
  Scenario: Opening About twice raises the same window
    Given a Tk root window
    When the About window is opened
    And the About window is opened again
    Then both handles should be the same window
