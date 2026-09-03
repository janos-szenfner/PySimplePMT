Feature: Application startup behavior
  Tests that the application starts correctly and its components are properly integrated.

  Background:
    Given the application is started

  Scenario: Application fills the usable screen area
    When the application is given a work area of 1600x900
    Then the window should be sized to 1600x900

  Scenario: Application asks window manager for usable area
    Then the usable screen area should match window manager max size

  Scenario: Small screen gets smaller minimum window size
    When the application is given a work area of 1366x728
    Then the minimum width should be less than or equal to 1366
    And the minimum height should be less than or equal to 728

  Scenario: Large screen keeps designed minimum window size
    When the application is given a work area of 2560x1400
    Then the minimum dimensions should match the preferred minimum

  Scenario: Minimum window size never exceeds opened size
    When the application is given work areas of 1024x640, 1366x728, and 1920x1080
    Then for each screen the minimum width should be less than or equal to the current width
    And for each screen the minimum height should be less than or equal to the current height

  Scenario: Scaled desktop does not get window off the edge
    When the application is given a work area of 2880x1560 with scaling 1.5
    Then the window should be sized to 1920x1040

  Scenario: Window manager that will not say still gets a window
    When the application is given a work area of 0x0
    Then the usable screen area should fallback to screen dimensions

  Scenario: Application builds every pane
    Then the application should have toolbar
    And the application should have task_list
    And the application should have gantt_chart
    And the application should have status_bar

  Scenario: Chart knows the task list
    Then the chart task list should be the same as the application task list

  Scenario: Toolbar knows the task list
    Then the toolbar task list should be the same as the application task list

  Scenario: Toolbar knows the chart
    Then the toolbar gantt chart should be the same as the application gantt chart

  Scenario: Clipboard can reach the desktops
    Then the clipboard manager should have a clipboard widget

  Scenario: Chart drew the rows the list is showing
    Then the chart drawn rows should match the task list visible rows

  Scenario: Rows stay lined up across a redraw
    When the task list selection is set to the first visible row
    And the application updates all
    And the chart redraws
    Then the chart top margin should remain consistent across draws

  Scenario: Chart keeps room for its own axis
    When the chart draws
    Then the chart top margin should be greater than or equal to the chart top margin constant

  Scenario: Rows still match after a redraw
    When the application updates all
    Then the chart drawn rows should still match the task list visible rows