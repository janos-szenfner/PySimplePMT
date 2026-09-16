@new_task_shortcut
Feature: The new-task shortcut is actually bound to the window

  Cmd+Option+. creates a task where the cursor is. It had been written
  twice and reported as doing nothing both times, and every test of it
  checked the handlers rather than the bindings - so a shortcut that was
  never wired to the window at all would have passed all of them.

  What the handlers do with an event is checked in test_toolbar_menus.
  This checks the other half: that a window handed a task list comes
  away with something bound for the keystroke to land on.

  The sequences cannot be compared as they were written. Tk stores a
  binding under a name of its own choosing - <Command-Option-period>
  comes back as <Mod1-Mod2-Key-period> - so these ask how many key
  bindings arrived and that the catch-all is among them, rather than
  matching the spelling.

  Needs a display; the scenarios skip where there is none.

  Background: a toolbar and a list in one window, wired as the app wires them
    Given a toolbar wired to a task list in one window

  Scenario: The window has key bindings at all
    # The wiring runs when the toolbar is handed the list.
    Then the window has key bindings

  Scenario: The period is bound with both modifiers
    # The plain sequence; see shortcuts.sequences.
    Then the window binds the period with the option modifier

  Scenario: The modifier catch-all is bound
    # For a keystroke Option has taken the letter out of. Tk matches the
    # modifiers and is_key works out the key.
    Then the window binds the any-key catch-all with the option modifier

  Scenario: The bare key net is there on a Mac only
    # It exists for a macOS fault, and every key in the window goes
    # through it - so it is not carried anywhere it earns nothing.
    Then a bare key net is bound exactly when running on macOS

  Scenario: The handler makes a task where the cursor is
    # The end of the chain: the row the cursor is on gets a sibling.
    # The dialog is stubbed out; what is checked is that the keyboard
    # route reaches the same creation the right-click menu does.
    When the new-task hotkey fires
    Then a task is created as a sibling of the focused row
