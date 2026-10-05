Feature: What survives a save, an open, and a fresh plan
  Issue #93 was that opening a file brought back only a subset of the
  plan that was saved: status date, direction, deadline, priority,
  calendars and grid layout were left behind, and the same partial set
  was what a new or closed project kept - the old plan's settings
  leaking into one that had never seen them. Issue #92 was the other
  direction: named calendars and baseline slot preferences are
  application settings, not plan data, so they live in settings.json.
  Issue #91 keeps the project name and the file name in step. The
  toolbar's side is exercised on a namespace stand-in - the helpers are
  written against self.<field> and carry no window state.

  # ---- the calendar the plan itself follows (#93) -------------------------

  Scenario: A plan names nothing until told otherwise
    Given a plan
    Then the plan names no calendar
    And the plan's own calendar answers for it

  Scenario: A named calendar answers for the plan
    Given a plan carrying the "sixday" calendar
    And the plan's calendar is "sixday"
    Then the "sixday" calendar answers for the plan

  Scenario: An unknown id falls back to the plan's own
    Given a plan
    And the plan's calendar is "long-gone"
    Then the plan's own calendar answers for it

  Scenario: A task with no calendar follows the plan
    Given a plan carrying the "sixday" calendar
    And the plan's calendar is "sixday"
    And a task "T" running "2026-08-17" to "2026-08-17"
    Then the task "T" follows the "sixday" calendar

  Scenario: A task naming its own keeps it
    Given a plan carrying the "sixday" calendar
    And a calendar "always" with nothing off
    And the plan's calendar is "sixday"
    And a task "T" running "2026-08-17" to "2026-08-17" on the "always" calendar
    Then the task "T" follows the "always" calendar

  Scenario: The choice survives a saved file
    Given a plan carrying the "sixday" calendar
    And the plan's calendar is "sixday"
    When the plan is saved and loaded
    Then the loaded plan's calendar is "sixday"
    And the loaded "sixday" calendar answers for it

  Scenario: A file from before the choice opens on the plan's own
    Given a plan written before the choice existed
    Then the loaded plan names no calendar
    And the plan's own calendar answers for the loaded plan

  Scenario: Switching moves the finish, not the work
    # A five-day task Mon-Fri under the standard week; a calendar with
    # Friday and Saturday off makes its finish slide rather than its
    # work shrink. Setting it again is refused as a no-op.
    Given a plan
    And a task "T" running "2026-08-17" to "2026-08-21"
    And a calendar "frioff" taking Friday and Saturday off
    When the plan's calendar is set to "frioff"
    Then the task "T" ends on "2026-08-23"
    And setting it to "frioff" again is refused

  # ---- taking on a loaded project (#93) ---------------------------------

  Scenario: Every persisted field arrives
    Given a toolbar holding the "Old" plan
    And a loaded plan with every field set
    When the toolbar takes on the loaded plan
    Then the plan carries the loaded fields

  Scenario: A blank project keeps nothing but the library
    Given a toolbar holding a loaded plan with every field set
    When the toolbar starts a blank project
    Then the new plan carries none of the old fields
    But it keeps the shared calendar library

  # ---- the calendar library (#92) ---------------------------------------

  Scenario: A file's custom calendar is adopted
    Given a clean settings file
    And a toolbar holding the "Live" plan over an empty library
    And a loaded plan carrying the "sixday" calendar
    When the loaded plan's calendars are merged
    Then the library holds "sixday"
    And the loaded plan points at the library
    And the library was written to the settings file

  Scenario: The library wins an id it already has
    # The file's "sixday" keeps Sundays off; the library's keeps
    # Mondays off - the library's stands.
    Given a toolbar holding the "Live" plan over a library where "sixday" takes Monday off
    And a loaded plan carrying the "sixday" calendar
    When the loaded plan's calendars are merged
    Then the plan's "sixday" takes Monday off

  Scenario: Without a library the file's own stand
    Given a toolbar holding the "Live" plan with no library
    And a loaded plan carrying the "sixday" calendar
    When the loaded plan's calendars are merged
    Then the loaded plan keeps its own calendars

  # ---- the preference store ---------------------------------------------

  Scenario: The calendar library round-trips
    Given a clean settings file
    When the "sixday" calendar is saved to the library
    Then the library loads with "sixday"

  Scenario: A missing key is seeded from the presets
    Given a clean settings file
    Then the library loads with the preset calendars

  Scenario: An empty library is honoured
    # Deleting every named calendar is a choice; it is not the same as
    # the key never having been written.
    Given a clean settings file
    When an empty library is saved
    Then the library loads empty

  Scenario: Baseline names and colours round-trip
    Given a clean settings file
    When baseline slot 2 is named "Go-Live" in "#ff0000"
    Then a fresh baseline manager's slot 2 is "Go-Live" in "#ff0000"
    And its slot 3 stays "Baseline 3"

  Scenario: Other keys in the file are untouched
    Given a clean settings file
    And the theme mode "dark" was saved
    When baseline slot 1 is named "First" with no colour
    And an empty library is saved
    Then the settings file still says theme "dark"
    And the theme mode loads as "dark"

  Scenario: Duplicate filter names are made unique on load
    # Issue #80: a file written before the name guards can carry two
    # filters of a name - they drew as two identical menu rows where
    # only the first answered. The repeats are renamed on the way in.
    Given a saved plan carrying three filters all named "Milestone"
    When the plan is loaded
    Then the filters are named "Milestone, Milestone (2), Milestone (3)"

  Scenario: A filter named like a built-in is renamed on take-on
    # The other half of #80: a saved filter wearing a built-in's label
    # drew a second identical menu row beside it.
    Given a toolbar holding the "Old" plan
    And a loaded plan with a filter named "Milestones"
    When the toolbar takes on the loaded plan
    Then the filter is named "Milestones (2)"

  Scenario: Saving does not pop a dialog
    # Issue #87: the star leaving the title bar is the confirmation a
    # save needs - a "saved successfully" popup on top was noise.
    Given a saver for a plan named "P"
    When the plan is written to a file
    Then no dialog was shown
    And the file exists

  Scenario: A damaged file is not worth failing over
    Given a settings file holding "{not json"
    Then the library loads with the preset calendars
    And applying baseline preferences answers no

  # ---- the file name and the project name (#91) ---------------------------

  Scenario Outline: The suggested file name writes unsafe characters as underscores
    When a file name is suggested for "<name>"
    Then it reads "<suggestion>"

    Examples:
      | name         | suggestion    |
      | My Plan      | My_Plan       |
      | My Plan: v2/a| My_Plan__v2_a |
      | (spaces)     | untitled      |

  Scenario: Save As adopts the chosen name on an untouched plan
    Given a saver for a plan named "New Project" never deliberately set
    When the plan is saved as "my plan_v2.json"
    Then the plan is named "my plan_v2"
    And the file name is locked
    And the saved file names the plan "my plan_v2"

  Scenario: Save As keeps a name the user deliberately set
    Given a saver for a plan deliberately named "Real Name"
    When the plan is saved as "other.json"
    Then the plan is named "Real Name"
    And the file name is locked

  Scenario: Accepting the suggestion leaves the name derived
    Given a saver for a plan deliberately named "My Plan"
    When the plan is saved as "My_Plan.json"
    Then the plan is named "My Plan"
    And the file name is not locked

  Scenario: A rename moves the save while the name is derived
    # The old file is left alone - never silently deleted.
    Given a plan deliberately named "New Name"
    And a saver whose file "Old_Name.json" exists
    When the plan is saved
    Then the current file is "New_Name.json"
    And "Old_Name.json" still exists
    And the file name is not locked

  Scenario: A rename leaves a chosen file name alone
    Given a plan deliberately named "New Name"
    And a saver locked onto "picked.json"
    When the plan is saved
    Then the current file is "picked.json"
    And no "New_Name.json" was written

  Scenario: Save asks before landing on a stranger's file
    Given a plan deliberately named "B"
    And a saver whose file "A.json" exists beside a "B.json" that is not ours
    When the plan is saved and the stranger's file is declined
    Then the current file is "A.json"
    And "B.json" still says it is not ours
    When the plan is saved and the stranger's file is accepted
    Then the current file is "B.json"

  Scenario: The deliberately-set flag survives a saved file
    Given a plan deliberately named "P"
    When the plan is saved and loaded
    Then the loaded plan knows its name was set

  Scenario: An old file guesses from whether the name is the placeholder
    Given a plan written before the flag existed, named "New Project"
    Then the loaded plan knows its name was not set
    When a plan written before the flag existed, named "Vacation Plan"
    Then the loaded plan knows its name was set

  Scenario: Take-on carries the flag
    Given a toolbar holding the "Old" plan
    And a loaded plan deliberately named "Loaded"
    When the toolbar takes on the loaded plan
    Then the taken-on plan knows its name was set
