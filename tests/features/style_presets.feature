Feature: The visual style-preset menu
  The Style Preset dropdown shows each preset as it will look, and offers a
  one-click way back to no style at all.

  # Issue #9: the dropdown listed plain names, so a reader had to apply a
  # preset to find out what it looked like. Issue #10: putting a tried preset
  # back meant leaving the menu for the Clear button.

  @style_presets
  Scenario: Every preset has a badge to recognise it by
    Then every preset should have a badge glyph and colour

  @style_presets
  Scenario: The default entry falls back to a hollow badge
    Then the badge for an unknown preset should be the hollow default

  @style_presets
  @needs_display
  Scenario: The menu opens with a Default entry ahead of the presets
    Given a style bar with a selection
    When the preset menu is opened
    Then the first entry should be "Default (no style)"
    And a preview row should follow for every preset

  @style_presets
  @needs_display
  Scenario: Each preset is shown as a preview of its own style
    Given a style bar with a selection
    When the preset menu is opened
    Then the "Financial Milestone" preview should match its style
    And every preview chip should match the style it applies

  @style_presets
  @needs_display
  Scenario: Choosing a preset applies that style
    Given a style bar with a selection
    When the preset menu is opened
    And the "Work Complete" entry is chosen
    Then the style bar should apply the "Work Complete" preset

  @style_presets
  @needs_display
  Scenario: Choosing Default clears the formatting
    Given a style bar with a selection
    When the preset menu is opened
    And the "Default (no style)" entry is chosen
    Then the style bar should clear the formatting

  @style_presets
  @needs_display
  Scenario: A preview row draws a badge, a name and a chip
    Given a preview menu for the presets
    Then the "Summary Phase" row should show its badge, name and chip
