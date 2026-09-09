Feature: Application icon and logo
  Tests for the application icon and logo built from the shipped logo image

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
  Scenario: Icon corners are rounded
    When drawing a 128x128 icon
    Then the corner pixel at 0,0 should be transparent
    And the corner pixel at 127,0 should be transparent
    And the center pixel at 64,64 should be opaque

  @app_icon
  Scenario: Icon is built from the shipped logo image
    Then the logo source image should exist
    And the icon should carry the logo detail rather than a blank tile

  @app_icon
  Scenario: Full logo loads at its natural aspect ratio
    When loading the logo at width 380
    Then the logo width should be 380
    And the logo should be landscape

  @app_icon
  Scenario: Icon drawing is deterministic
    Then the icon drawing should be the same every time

  @app_icon
  Scenario: Packaging scripts use the same icon source
    Then the macOS packaging script should import draw_icon from appicon
    And the Windows packaging script should import draw_icon from appicon

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
