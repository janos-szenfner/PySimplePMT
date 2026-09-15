Feature: Color entry functionality
  Tests for the color entry and column sizing functionality.

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

  # THE PICKER (needs a display; the system chooser itself is stubbed)

  Scenario: The picker opens the system colour chooser on the current color
    Given a color entry widget with color "#2ecc71"
    When opening the picker and the chooser answers "#e74c3c"
    Then the chooser should have opened on "#2ecc71"
    And the widget color should be "#e74c3c"

  Scenario: Cancelling the chooser keeps the color
    Given a color entry widget with color "#2ecc71"
    When opening the picker and the chooser is cancelled
    Then the widget color should be "#2ecc71"

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
    Then the color entry should default to "#1f6aa5"
    When creating a task dialog for "Milestone" type
    Then the color entry should default to "#f39c12"

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