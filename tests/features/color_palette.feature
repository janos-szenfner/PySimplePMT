Feature: Color palette functionality
  Tests for the color picker and column sizing functionality.

  # PALETTE CONTENT TESTS (no display needed)

  Scenario: Every palette entry is a hex color
    When checking all palette entries
    Then every entry value should be a valid hex color

  Scenario: Every palette entry is named
    When checking all palette entries
    Then every entry should have a non-empty name

  Scenario: No duplicate colors in palette
    When checking all palette entries
    Then there should be no duplicate color values

  Scenario: Application default colors are included in palette
    When checking all palette entries
    Then the palette should contain "#3498db"
    And the palette should contain "#9b59b6"
    And the palette should contain "#e74c3c"
    And the palette should contain "#1f6aa5"

  # COLOR ENTRY WIDGET TESTS (need display)

  Scenario: ColorEntry starts on the given color
    Given a color entry widget with color "#2ecc71"
    When the widget is created
    Then the widget color should be "#2ecc71"

  Scenario: Setting a new color programmatically
    Given a color entry widget
    When setting the color to "#f39c12"
    Then the widget color should be "#f39c12"

  Scenario: Default button resets to blue color
    Given a color entry widget with color "#2ecc71"
    When setting the default color
    Then the widget color should be the default color
    And the widget color should be "#1f6aa5"

  Scenario: ColorEntry reports color changes
    Given a color entry widget with change callback
    When setting the color to "#1abc9c"
    Then the change callback should have been called with "#1abc9c"

  Scenario: Reselecting the same color reports nothing
    Given a color entry widget with color "#1abc9c" and change callback
    When setting the color to "#1abc9c"
    Then the change callback should not have been called

  Scenario: Missing color falls back to default
    Given a color entry widget with empty color
    When getting the color
    Then the color should start with "#"

  # COLOR NORMALIZATION TESTS (need display)

  Scenario: Hex color is left alone and lowercased
    When normalizing "#2ECC71"
    Then the result should be "#2ecc71"

  Scenario: Bare hex gains hash prefix
    When normalizing "2ecc71"
    Then the result should be "#2ecc71"

  Scenario: Color name is left as name
    When normalizing "red"
    Then the result should be "red"

  Scenario: Empty or None value becomes default color
    When normalizing empty string
    Then the result should be the default color
    When normalizing None
    Then the result should be the default color

  # PALETTE BUILDING TESTS (need display)

  Scenario: No popup until color picker is asked for
    Given a color entry widget
    When the widget is created
    Then the popup should be None

  Scenario: Opening picker builds the palette
    Given a color entry widget
    When opening the color picker
    Then the popup should have buttons for all palette entries

  Scenario: Opening picker twice reuses the same window
    Given a color entry widget
    When opening the picker first time
    And opening the picker second time
    Then both open calls should return the same popup

  Scenario: Palette opens at size of palette
    Given a color entry widget
    When opening the picker and updating
    Then the popup width should be at least the grid frame required width
    And the popup height should be at least the grid frame required height

  Scenario: Palette that fits shows no scrollbar
    Given a color entry widget
    When opening the picker and updating
    Then the scrollbar should not be visible

  Scenario: Mouse wheel is bound to swatches
    Given a color entry widget
    When opening the picker
    Then the swatch buttons should have mouse wheel binding

  # DIALOG COLOR PICKING TESTS (need display)

  Scenario: Edit dialog shows the task color
    Given a project with a task colored "#2ecc71"
    And an edit task dialog for the task
    Then the color entry should show "#2ecc71"

  Scenario: Saving dialog stores the picked color
    Given a project with a task
    And an edit task dialog for the task
    When setting the color entry to "#f39c12"
    And saving the dialog
    Then the task color should be "#f39c12"

  Scenario: Create dialog defaults by task type
    Given a project
    When creating a task dialog for "Task" type
    Then the color entry should default to "#3498db"
    When creating a task dialog for "Milestone" type
    Then the color entry should default to "#e74c3c"

  # COLUMN SIZING TESTS (need display)

  Scenario: No column stretches
    Given a task list with columns
    When checking all columns
    Then no column should have stretch enabled

  Scenario: Every column has a minimum width
    Given a task list with columns
    When checking all columns
    Then every column should have minimum width greater than 0

  Scenario: Column width survives a refresh
    Given a task list with columns
    When setting column "#0" width to 420
    And refreshing the task list
    Then the column "#0" width should still be 420

  Scenario: Name column is the widest by default
    Given a task list with columns
    When checking all column widths
    Then the name column should be the widest