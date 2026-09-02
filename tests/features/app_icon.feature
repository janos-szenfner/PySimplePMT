Feature: Application icon functionality
  Tests for the application icon drawing and display

  @app_icon
  Scenario: Icon builds at all packaged sizes
    Then the icon should build at size 16
    And the icon should build at size 24
    And the icon should build at size 32
    And the icon should build at size 48
    And the icon should build at size 64
    And the icon should build at size 128
    And the icon should build at size 256

  @app_icon
  Scenario: Icon corners are cut
    When drawing a 128x128 icon
    Then the corner pixel at 0,0 should be transparent
    And the corner pixel at 127,0 should be transparent
    And the center pixel at 64,64 should be opaque

  @app_icon
  Scenario: Icon is drawn in Python colors
    When drawing a 256x256 icon
    Then the icon should contain BLUE_DARK color
    And the icon should contain BLUE_LIGHT color
    And the icon should contain YELLOW color
    And the icon should contain YELLOW_LIGHT color

  @app_icon
  Scenario: Icon drawing is deterministic
    Then the icon drawing should be the same every time

  @app_icon
  Scenario: Packaging script uses the same icon drawing
    Then the packaging script should import draw_icon from appicon

  @app_icon @needs_display
  Scenario: Icon converts to Tk image
    Given a Tk root window
    When creating a Tk photo image from the icon
    Then the photo should not be None
    And the photo dimensions should be 64x64

  @app_icon @needs_display
  Scenario: Application window wears the icon
    Given a GanttApp instance
    When the app is initialized
    Then the app should have an icon
    And the icon dimensions should be 64x64