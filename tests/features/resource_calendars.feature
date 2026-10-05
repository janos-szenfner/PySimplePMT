Feature: A task is scheduled where its calendar and its resources' agree
  Resource calendars (issue #38): "Scheduling ignores resource
  calendars" on the Advanced tab is the escape, and it is off by
  default. The calendar mechanics run without a display; the checkbox
  scenarios are @display_dependent.

  # ---- the resource's own week ----------------------------------------

  Scenario: A working weekday is worked
    Given the resource "Ann" works a standard week
    Then "Ann" works on "2026-01-05"

  Scenario: A weekend day is not worked
    Given the resource "Ann" works a standard week
    Then "Ann" does not work on "2026-01-10"

  Scenario: A days-off range wins over the weekday
    Given the resource "Ann" works a standard week
    And "Ann" is off from "2026-01-07" to "2026-01-08"
    Then "Ann" does not work on "2026-01-07"
    And "Ann" does not work on "2026-01-08"
    And "Ann" works on "2026-01-09"

  Scenario: A datetime is taken by its date
    Given the resource "Ann" works a standard week
    And "Ann" is off from "2026-01-07" to "2026-01-07"
    Then "Ann" does not work at "2026-01-07 15:30"

  # ---- the intersection the task works --------------------------------

  Scenario: With no assignments the task calendar rules
    Given a plan
    And a task "Build" running "2026-01-05" to "2026-01-09" of 5 days
    Then "2026-01-07" is a working day for "Build"
    And "2026-01-10" is not a working day for "Build"

  Scenario: The resource's days off are not worked
    Given a plan
    And the resource "Ann" works a standard week
    And "Ann" is off from "2026-01-07" to "2026-01-08"
    And a task "Build" running "2026-01-05" to "2026-01-09" of 5 days
    And "Build" is assigned to "Ann"
    Then "2026-01-07" is not a working day for "Build"
    And "2026-01-08" is not a working day for "Build"
    And "2026-01-09" is a working day for "Build"

  Scenario: The task calendar still rules
    # Intersection: the project closing a day closes it for everyone.
    Given a plan
    And the resource "Bob" works the full week
    And a task "Build" running "2026-01-05" to "2026-01-09" of 5 days
    And "Build" is assigned to "Bob"
    Then "2026-01-10" is not a working day for "Build"
    And "2026-01-06" is a working day for "Build"

  Scenario: Several resources work in parallel
    # A day counts when at least one assigned resource can work it.
    Given a plan
    And the resource "Ann" works a standard week
    And "Ann" is off from "2026-01-07" to "2026-01-07"
    And the resource "Bob" works a standard week
    And a task "Build" running "2026-01-05" to "2026-01-09" of 5 days
    And "Build" is assigned to both "Ann" and "Bob"
    Then "2026-01-07" is a working day for "Build"

  Scenario: An assignment nobody has is skipped
    Given a plan
    And a task "Build" running "2026-01-05" to "2026-01-09" of 5 days
    And "Build" is assigned to a resource nobody has
    Then "2026-01-07" is a working day for "Build"

  Scenario: A resource that never works is left out
    Given a plan
    And the resource "Ann" never works
    And a task "Build" running "2026-01-05" to "2026-01-09" of 5 days
    And "Build" is assigned to "Ann"
    Then "2026-01-07" is a working day for "Build"

  Scenario: The flag leaves the task calendar alone
    Given a plan
    And the resource "Ann" works a standard week
    And "Ann" is off from "2026-01-07" to "2026-01-07"
    And a task "Build" running "2026-01-05" to "2026-01-09" of 5 days
    And "Build" is assigned to "Ann"
    And "Build" ignores resource calendars
    Then "2026-01-07" is a working day for "Build"

  # ---- the stretch the issue describes --------------------------------
  # Finish moves when work cannot.

  Scenario: A task stretches over the resource's days off
    # Mon, Tue, [off, off], Fri, [weekend], Mon, Tue
    Given a plan
    And the resource "Ann" works a standard week
    And "Ann" is off from "2026-01-07" to "2026-01-08"
    And a task "Build" running "2026-01-05" to "2026-01-09" of 5 days
    And "Build" is assigned to "Ann"
    When the work is scheduled
    Then "Build" starts on "2026-01-05"
    And "Build" ends on "2026-01-13"

  Scenario: The flag keeps the finish where it was
    Given a plan
    And the resource "Ann" works a standard week
    And "Ann" is off from "2026-01-07" to "2026-01-08"
    And a task "Build" running "2026-01-05" to "2026-01-09" of 5 days
    And "Build" is assigned to "Ann"
    And "Build" ignores resource calendars
    When the work is scheduled
    Then "Build" ends on "2026-01-09"

  Scenario: A milestone moves off a day the resource has off
    Given a plan
    And the resource "Ann" works a standard week
    And "Ann" is off from "2026-01-07" to "2026-01-08"
    And a milestone "Kick" on "2026-01-07"
    And "Kick" is assigned to "Ann"
    When the work is scheduled
    Then "Kick" starts on "2026-01-09"

  # ---- the flag itself --------------------------------------------------

  Scenario: The flag is off by default
    Given a plan
    And a task "Build" running "2026-01-05" to "2026-01-09"
    Then "Build" does not ignore resource calendars

  Scenario: The flag survives a save round trip
    Given a plan
    And a task "Build" running "2026-01-05" to "2026-01-09"
    And "Build" ignores resource calendars
    When "Build" is saved and loaded again
    Then the loaded task ignores resource calendars

  # ---- the Advanced tab checkbox ----------------------------------------
  # Needs a display - the box itself is a widget.

  @display_dependent
  Scenario: The box opens unticked
    Given a task "Build" is open on the Advanced tab
    Then the ignores-calendars box is unticked

  @display_dependent
  Scenario: Without a task calendar the box is disabled
    Given a task "Build" is open on the Advanced tab
    Then the ignores-calendars box is disabled

  @display_dependent
  Scenario: With a task calendar the box is enabled
    Given a task "Build" with a task calendar is open on the Advanced tab
    Then the ignores-calendars box is enabled

  @display_dependent
  Scenario: The tick reads into the saved values
    Given a task "Build" with a task calendar is open on the Advanced tab
    When the ignores-calendars box is ticked
    Then the saved values ignore resource calendars

  @display_dependent
  Scenario: Disabling the box clears its tick
    Given a task "Build" with a task calendar is open on the Advanced tab
    And the ignores-calendars box is ticked
    When the ignores-calendars box is disabled
    Then the ignores-calendars box is unticked
