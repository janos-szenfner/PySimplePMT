@dialog_chrome
Feature: The parts of a dialog that are neither its data nor its layout

  Four separate reports, all of the same kind: a control that is drawn,
  looks right in the code, and does nothing.

    * The critical path icon was in the toolbar row, enabled, with
      nothing connected behind it - the handlers were assigned by hand
      in a list that had to mirror the row's own definition, and it
      drifted the first time an icon was added.
    * Cancel in the holiday picker and Recalculate in the critical path
      window were `fg_color='transparent'`, which leaves
      CustomTkinter's white button text on the window's own
      background: white on white, and invisible.
    * The colour palette and the calendar are separate windows opened
      over a dialog that holds a grab. A grab is exclusive, so neither
      received a single click: no colour could be picked and Close did
      not close.

  None of it is caught by testing what the widgets contain, which is
  why these test how they are wired instead.

  Scenario: Every action names a method on the toolbar
    # Including the overrides, which are named rather than assumed.
    Then every icon action resolves to a callable toolbar method

  Scenario: The critical path icon is among them
    # The one that was missing, named so the regression is obvious.
    Then "toggle_critical_path_rows" is an action with a handler

  Scenario: Every icon reaches a handler for real
    # _connect_icon_toolbar assigns onto the row at runtime, so only a
    # real application says whether a button has anything behind it.
    When the real application is built
    Then every icon on its toolbar reaches a callable handler

  Scenario: The holiday picker's Cancel is drawn
    # It was white on white, and read as empty space.
    Given a holiday dialog is open
    Then its "Cancel" button is filled and its text coloured

  Scenario: The critical path Recalculate is drawn
    # The same button in the same state, in the other window.
    Given a critical path window is open over an empty plan
    Then its "Recalculate" button is filled and its text coloured

  Scenario: A secondary button differs from the primary one
    # Apply and Cancel side by side in the same filled blue is its own
    # problem.
    Given a holiday dialog is open
    Then its "Cancel" button is not filled like its "Apply" button

  Scenario: It carries a colour for each appearance mode
    # CustomTkinter takes a (light, dark) pair, and giving it a single
    # value is the same bug with an extra step.
    Then the secondary fill and text are distinct light-dark pairs

  Scenario: The popup takes the grab
    # Otherwise every click goes to the dialog underneath it.
    Given a dialog holding the grab
    When a popup over it takes the grab
    Then the popup holds the grab

  Scenario: It hands the grab back
    # Or the dialog underneath is left non-modal - the same bug one
    # level up, and harder to notice.
    Given a dialog holding the grab
    When a popup over it takes the grab
    And the popup is destroyed
    Then the dialog holds the grab again

  Scenario: A child being destroyed does not hand it back
    # <Destroy> fires for everything inside the window as well.
    # Restoring on a child's teardown would give the grab away while
    # the popup was still up.
    Given a dialog holding the grab
    When a popup over it takes the grab
    And a child inside the popup is destroyed
    Then the popup holds the grab

  Scenario: The calendar asks for it
    # The colour chooser is the platform's own and manages its grab
    # itself; the calendar is the one custom window left that has to
    # ask.
    Then the calendar popup's constructor takes the grab
