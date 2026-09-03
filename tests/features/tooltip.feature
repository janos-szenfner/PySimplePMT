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

  # Restored from test_tooltip.py. The conversion kept the five scenarios
  # above and left behind everything about when the caption appears and
  # goes away, which is the half that can go wrong without looking wrong.

  @tooltip
  @needs_display
  Scenario: Showing twice makes one window
    Given a button with hover text
    When the tooltip is shown twice
    Then both shows should be the same window

  @tooltip
  @needs_display
  Scenario: Entering starts the clock rather than showing at once
    Given a button with hover text
    When the pointer enters the button
    Then a caption should be waiting to appear
    And no tooltip window should exist yet

  @tooltip
  @needs_display
  Scenario: Leaving cancels a caption that had not appeared
    Given a button with hover text
    When the pointer enters the button
    And the pointer leaves the button
    Then nothing should be waiting to appear
    And no tooltip window should exist yet

  @tooltip
  @needs_display
  Scenario: Pressing the button takes the caption away
    Given a button with hover text
    Then the canvas should have a button press binding

  @tooltip
  @needs_display
  Scenario: Attaching again reuses the tooltip
    Given a button with hover text
    When the same button is given the text "Dark mode"
    Then the same tooltip should be returned
    And the tooltip text should be "Dark mode"

  @tooltip
  @needs_display
  Scenario: Attaching twice does not double the binding
    Given a fresh button
    When the button is given hover text
    Then it should cost one binding on the canvas

  @tooltip
  @needs_display
  Scenario: A destroyed widget does not raise
    Given a button with hover text
    When the button is destroyed and the tooltip shown
    Then no tooltip window should exist yet

  @tooltip
  @needs_display
  Scenario: Every icon on the toolbar has hover text
    Given an icon toolbar over an empty plan
    Then every icon button should carry a non-empty caption

  @tooltip
  @needs_display
  Scenario: The caption says what the button does
    Given an icon toolbar over an empty plan
    Then every caption should match the one ICON_ACTIONS declares
