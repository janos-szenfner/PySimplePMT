@dependency_help
Feature: The dependency reference window and the Help button that opens it

  The content is checked as data so the coverage assertions do not
  depend on a display. Only the window and the button need one, and
  those scenarios skip without it; CI provides one through xvfb.

  Scenario: Every type is explained
    # Each of the four types has a section of its own. The tab's Type
    # menu offers all four, so a reader who meets an unfamiliar one has
    # somewhere to look it up.
    Then every dependency type label has a section heading

  Scenario: Lag and lead are explained
    # Lead time is the half of the lag field that needs explaining.
    Then the help text mentions "lead time" and "negative"

  Scenario: Hardness is explained
    # Both hardness settings are described.
    Then the help text mentions "Hard" and "Rubber"

  Scenario: The scheduling behaviour is explained
    # The forward-only rule is described - the behaviour most likely to
    # look wrong without an explanation: gaps survive rescheduling on
    # purpose.
    Then the help text mentions "later" and "gap"

  Scenario: No external links are shown
    # The reference stands on its own: it describes standard scheduling
    # concepts in this application's own terms, so pointing readers at
    # someone else's page added nothing.
    Then the help text contains no "http"

  Scenario: Every section has content
    # No heading is left with nothing under it.
    Then every help section has non-empty paragraphs

  Scenario: The window opens
    # The window builds and shows the reference.
    Given a root window
    When the dependency help is shown
    Then the help window exists

  Scenario: It holds every section
    # All the content reaches the body.
    Given a root window
    When the dependency help is shown
    Then the help body carries every section heading

  Scenario: The body is read-only
    # Readable and selectable, but not editable - leaving it editable
    # would let a reader type into the reference.
    Given a root window
    When the dependency help is shown
    Then the help body is disabled

  Scenario: Opening twice reuses the window
    # A second click raises the open window rather than stacking
    # another - the button sits beside controls people click
    # repeatedly.
    Given a root window
    When the dependency help is shown twice
    Then the same window came back

  Scenario: Closing forgets it
    # A closed window is not handed out again.
    Given a root window
    When the dependency help is shown and closed
    Then no open help window is remembered

  Scenario: It reopens after closing
    # Closing and clicking again gives a fresh window.
    Given a root window
    When the dependency help is shown, closed and shown again
    Then a fresh help window exists

  Scenario: Only field labels remain on the tab
    # Nothing on the tab is a paragraph of explanation - the block that
    # used to sit under the grid took room the grid wanted and could
    # still only afford a line per setting.
    Given an edit dialog over a two-task project
    Then every label on the dependency editor is shorter than 30 characters

  Scenario: The help button is offered
    # The explanation is a click away.
    Given an edit dialog over a two-task project
    Then a "Help" button is on the dependency editor

  Scenario: The button opens the window
    # Clicking Help shows the reference.
    Given an edit dialog over a two-task project
    When the editor is asked for help
    Then an open help window is remembered
