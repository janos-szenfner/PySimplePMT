Feature: The MSPDI export writes the plan as a Microsoft Project file
  MSPDI hands Project a plan and lets it re-solve the schedule, so an
  export that writes only durations and links opens showing dates nobody
  planned - every task without a predecessor collapsed onto the project
  start. The export therefore pins each piece of work with a Start No
  Earlier Than constraint, and most of what is checked here is that
  pinning: that it is there, that it is on the date the plan says, and
  that summary rows are left alone so Project can compute them.

  The rest is the parts of the format that are easy to write plausibly
  and wrongly - the schema's element order, lag counted in tenths of a
  minute, the weekday numbering that starts at Sunday, and the per-task
  calendars that are the one thing MSPDI holds and the GanttProject
  export cannot.

  Background:
    Given the sample Tosca Implementation plan

  # -- The shape of the document ----------------------------------------

  Scenario: The document is a Project in Microsoft's namespace
    When the plan is exported to MSPDI XML
    Then the root is a Project element in the MSPDI namespace
    And its Title reads "Tosca Implementation"

  Scenario: Hierarchy is an outline rather than nesting
    When the plan is exported to MSPDI XML
    Then the outline reads "Procurement" level 1 WBS "1", "Business case" level 2 WBS "1.1", "Tender" level 2 WBS "1.2" and "Contract signed" level 1 WBS "2"

  Scenario: Work is pinned to the date the plan says
    When the plan is exported to MSPDI XML
    Then the task "Tender" carries constraint type "4"
    And the task "Tender" carries constraint date "2026-07-13T08:00:00"

  Scenario: A summary row carries no constraint
    When the plan is exported to MSPDI XML
    Then the task "Procurement" is marked a summary
    And the task "Procurement" carries constraint type "0"
    And the task "Procurement" carries no constraint date

  Scenario: A floor the user set beats the inferred pin
    Given "Tender" is floored to "2026-07-10" by a SNET constraint
    When the plan is exported to MSPDI XML
    Then the task "Tender" carries constraint date "2026-07-10T08:00:00"

  Scenario: Duration is working hours
    When the plan is exported to MSPDI XML
    Then the task "Business case" has duration "PT32H0M0S"

  Scenario: A milestone takes no time
    When the plan is exported to MSPDI XML
    Then the task "Contract signed" is marked a milestone
    And the task "Contract signed" has duration "PT0H0M0S"
    And the task "Contract signed" finishes where it starts

  Scenario: A finish lands at the end of its last day
    When the plan is exported to MSPDI XML
    Then the task "Business case" finishes at "2026-07-10T17:00:00"

  Scenario: Links are held by the successor
    When the plan is exported to MSPDI XML
    Then the task "Tender" holds one predecessor link to "Business case"
    And the link is of type "1"

  Scenario: Lag is written in tenths of a minute
    When the plan is exported to MSPDI XML
    Then the link on "Tender" carries lag "9600" and format "7"

  Scenario: Element order follows the schema
    Given "Tender" carries notes and a named calendar
    When the plan is exported to MSPDI XML
    Then "Tender" writes CalendarUID between ConstraintType and ConstraintDate
    And "Tender" writes Notes before its PredecessorLink
    And "Tender" writes PredecessorLink last

  Scenario: No element the schema does not name is written
    Given "Tender" is given status "Inactive"
    When the plan is exported to MSPDI XML
    Then no task writes a Status element

  Scenario: Progress and notes travel
    When the plan is exported to MSPDI XML
    Then the task "Business case" is "50" percent complete
    And the task "Business case" notes read "Signed off by the steering group"

  Scenario: The working week is declared from Sunday
    When the plan is exported to MSPDI XML
    Then day type "1" is not worked, "2" and "6" are, and "7" is not

  Scenario: A holiday becomes a dated exception
    When the plan is exported to MSPDI XML
    Then the date "2026-07-08T00:00:00" is a non-working exception

  # -- Per-task calendars ------------------------------------------------

  Scenario: Both calendars are written
    Given "Tender" follows a weekend-only calendar named "Weekend window"
    When the plan is exported to MSPDI XML
    Then the calendars written are "Standard" and "Weekend window"

  Scenario: The task points at its own calendar
    Given "Tender" follows a weekend-only calendar named "Weekend window"
    When the plan is exported to MSPDI XML
    Then the task "Tender" names the UID of calendar "Weekend window"

  Scenario: A task on the plan calendar names nothing
    Given "Tender" follows a weekend-only calendar named "Weekend window"
    When the plan is exported to MSPDI XML
    Then the task "Business case" names no calendar

  Scenario: An unused calendar is not written
    Given "Tender" follows a weekend-only calendar named "Weekend window"
    And a calendar named "Nobody uses this" exists
    When the plan is exported to MSPDI XML
    Then "Nobody uses this" is not among the calendars

  # -- Edge cases -----------------------------------------------------------

  Scenario: An empty plan still writes a file
    Given an empty plan named "Empty"
    When the plan is exported to MSPDI XML
    Then no Task elements are written
    And one calendar is written

  Scenario: A link to a missing task is dropped
    Given a plan with a task depending on "nowhere"
    When the plan is exported to MSPDI XML
    Then no PredecessorLink element is written

  Scenario: A six-day week states its own length
    Given a plan working Saturdays holding a six-day task
    When the plan is exported to MSPDI XML
    Then MinutesPerWeek reads "2880"

  Scenario: A worked weekend is written as an exception
    Given a plan that works "2026-07-11" for "Catch-up"
    When the plan is exported to MSPDI XML
    Then one worked exception reads "2026-07-11T00:00:00" with working times

  Scenario: The file lands on disk and parses
    When the plan is exported to a real MSPDI file
    Then the file's root is a Project element in the MSPDI namespace

  Scenario: Export reports failure rather than raising
    When the plan is exported to a path that cannot be written
    Then the export reports failure
