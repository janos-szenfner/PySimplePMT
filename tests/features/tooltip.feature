Feature: Tooltip functionality
  Tests for the hover text on the toolbar buttons

  @tooltip
  @needs_display
  Scenario: Attaching tooltip to button
    Given a button with tooltip for attachment
    Then attaching should return a Tooltip instance
    And the tooltip should contain the specified text

  @tooltip
  @needs_display
  Scenario: Nothing is attached without text
    Given a button with empty tooltip
    Then attaching should return None

  @tooltip
  @needs_display
  Scenario: Showing tooltip creates window
    Given a button with tooltip for display
    When the tooltip is shown
    Then the tooltip window should be created
    And the tooltip window should display the caption text

  @tooltip
  @needs_display
  Scenario: Leaving destroys tooltip window
    Given a button with tooltip for hide
    When the tooltip is hidden
    Then the tooltip window should be destroyed

  @tooltip
  @needs_display
  Scenario: Canvas has Enter and Leave bindings
    Given a button with tooltip for bindings
    Then the canvas should have Enter binding
    And the canvas should have Leave binding