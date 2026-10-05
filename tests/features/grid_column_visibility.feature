Feature: The hidden-columns setting
  The setting lives on the project - hidden_grid_columns - so it
  travels with the file. The grid reading it and the Settings tab that
  edits it need a display and stay in the unittest module.

  Scenario: Label is hidden by default
    # The column a plan only needs once it has labels.
    Then a new plan hides "Label"

  Scenario: It survives a save round trip
    # The point of putting it on the project is that it is saved.
    Given a plan hiding "Label, Outline"
    When it is saved and read back
    Then it hides "Label, Outline"

  Scenario: An old plan reads the default
    # A file from before the setting still hides the Label column.
    Given a saved plan with hidden columns removed
    When it is read back
    Then it hides "Label"
