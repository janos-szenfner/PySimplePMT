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

  # ---- the calendar the task names ------------------------------------

  Scenario: A task follows its own named calendar
    # The task's calendar, not the plan's, is what crosses the
    # resources' - a Saturday its calendar works is a day it can spend.
    Given a plan
    And a calendar "Saturday Shift" that works "2026-01-10"
    And a task "Shift" running "2026-01-05" to "2026-01-09" of 5 days
    And "Shift" follows the "Saturday Shift" calendar
    Then "2026-01-10" is a working day for "Shift"

  Scenario: A calendar id that resolves nowhere falls back
    # A deleted calendar must not strand the task - it quietly follows
    # the plan's own.
    Given a plan
    And a task "Build" running "2026-01-05" to "2026-01-09" of 5 days
    And "Build" follows the "ghost" calendar
    Then "2026-01-07" is a working day for "Build"
    And "2026-01-10" is not a working day for "Build"

  Scenario: A material assignment leaves the calendar alone
    # Materials are used up, not worked - there is no calendar to cross.
    Given a plan
    And the material "Bricks" exists
    And a task "Build" running "2026-01-05" to "2026-01-09" of 5 days
    And "Build" is assigned to the material "Bricks"
    Then "2026-01-07" is a working day for "Build"

  Scenario: A weekend-only resource empties the working week
    # Intersection is honest: Mon-Fri crossed with Sat-Sun works no day
    # at all, and the task becomes unschedulable rather than pretend.
    Given a plan
    And the resource "Crew" works weekends only
    And a task "Build" running "2026-01-05" to "2026-01-09" of 5 days
    And "Build" is assigned to "Crew"
    Then "2026-01-05" is not a working day for "Build"
    And "2026-01-10" is not a working day for "Build"

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

  Scenario: A successor waits across the resource's days off
    # The predecessor's stretch drags the row linked to it: Build lands
    # Tue the 13th, so three days follow on from Wednesday the 14th.
    Given a plan
    And the resource "Ann" works a standard week
    And "Ann" is off from "2026-01-07" to "2026-01-08"
    And a task "Build" running "2026-01-05" to "2026-01-09" of 5 days
    And "Build" is assigned to "Ann"
    And a task "Follow" running "2026-01-12" to "2026-01-14" of 3 days
    And "Follow" runs after "Build"
    When the work is scheduled
    Then "Build" ends on "2026-01-13"
    And "Follow" starts on "2026-01-14"

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

  # ---- the intersecting calendar, in both directions ------------------------------
  # Scheduling leans on the intersection for forward walking; a link that
  # fixes a finish walks it backwards, and the measuring methods are what
  # the chart draws.

  Scenario: The intersection looks back over days off
    # Bob is off Monday to Wednesday; looking back from Wednesday, the
    # last day both sides work is the Friday before.
    Given a plan
    And the resource "Bob" works a standard week
    And "Bob" is off from "2026-01-05" to "2026-01-07"
    And a task "Build" running "2026-01-05" to "2026-01-09"
    And "Build" is assigned to "Bob"
    Then the "Build" calendar looks back from "2026-01-07" to "2026-01-02"

  Scenario: Working days can be subtracted as well as added
    # Two days back from Friday spends one on Thursday; Wednesday is off.
    Given a plan
    And the resource "Bob" works a standard week
    And "Bob" is off from "2026-01-05" to "2026-01-07"
    And a task "Build" running "2026-01-05" to "2026-01-09"
    And "Build" is assigned to "Bob"
    Then 2 working days back from "2026-01-09" lands "Build" on "2026-01-08"
    And 0 working days back from "2026-01-09" lands "Build" on "2026-01-09"
    And 0 working days forward from "2026-01-08" lands "Build" on "2026-01-08"

  Scenario: The intersection counts the days both sides work
    # Bob is off three of the five weekdays, so two of the five count.
    Given a plan
    And the resource "Bob" works a standard week
    And "Bob" is off from "2026-01-05" to "2026-01-07"
    And a task "Build" running "2026-01-05" to "2026-01-09"
    And "Build" is assigned to "Bob"
    Then "Build" counts 2 days worked between "2026-01-05" and "2026-01-09"
    And "Build" counts 0 days worked between "2026-01-09" and "2026-01-05"

  Scenario: Elapsed days are calendar days either way
    # The measure WorkingCalendar gives, on the intersection too: the
    # weekends are in the number.
    Given a plan
    And the resource "Bob" works a standard week
    And a task "Build" running "2026-01-05" to "2026-01-09"
    And "Build" is assigned to "Bob"
    Then "Build" measures 5 elapsed days between "2026-01-05" and "2026-01-09"

  Scenario: A resource that never works leaves every date alone
    # A zero-capacity resource cannot be intersected into a schedule, so
    # calendar_for leaves it out - but an intersection built with one
    # still gives up after the step limit rather than running forever,
    # leaving the date where it was, with a line in the log.
    Given a plan
    And the resource "Nobody" never works
    And a task "Build" running "2026-01-05" to "2026-01-09"
    And "Build" is assigned to "Nobody"
    Then "Build" follows the plan's own calendar, not an empty one
    And an intersection over "Nobody" finds no working day on or after "2026-01-05"
    And an intersection over "Nobody" finds no working day on or before "2026-01-05"
