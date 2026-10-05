Feature: The named calendars a plan holds, and which one a task follows
  The registry's whole job is to answer "which calendar is this task
  scheduled on", and everything downstream - where the task starts, how
  long its bar is, what the critical path measures - follows from that
  answer being right. Most of what is worth pinning down is the
  resolution rule and its edges: the task that names nothing, and the
  task naming a calendar that has since been deleted. Dates are chosen
  so the weekday matters; 2026-09-10 is a Thursday, 2026-09-12 a
  Saturday.

  # ---- ids are built from names, and have to stay usable ------------------

  Scenario: A name becomes a readable id
    Then slugifying "Weekend Shift" gives "weekend-shift"

  Scenario: Punctuation collapses rather than surviving into the id
    Then slugifying "24/7  Continuous!! Run" gives "24-7-continuous-run"

  Scenario: A name with nothing usable still gives an id
    # An empty id would be a calendar nothing could point at.
    Then slugifying "!!!" gives "calendar"
    And slugifying a blank name gives "calendar"

  # ---- holding calendars, in the order they went in -----------------------

  Scenario: The presets are offered
    # A plan that has never opened the dialog still has something.
    Given a registry
    Then the calendar ids are "standard-week, weekend-shift, continuous"

  Scenario: The default leads the options
    # It is what most tasks follow and what one is put back to.
    Given a registry
    Then the options lead with the plan's own
    And there is an option for every calendar

  Scenario: Order is the order they were added
    # Not whatever a dictionary happened to give back.
    Given a registry
    When a calendar "Aardvark" is created
    Then the last calendar id is "aardvark"

  Scenario: Replacing keeps its place
    # Editing one must not move it to the bottom of every dropdown.
    Given a registry
    When "weekend-shift" is replaced by "Changed"
    Then the calendar ids are "standard-week, weekend-shift, continuous"
    And "weekend-shift" is now named "Changed"

  Scenario: Two calendars of the same name get different ids
    # The name is the user's to repeat; the id is what the tasks point
    # at - or the second silently takes every task following the first.
    Given a registry
    When two calendars named "Site Visit" are created
    Then they hold different ids
    And the registry holds 5 calendars

  Scenario: Renaming leaves the id alone
    # Every task following it names it by id.
    Given a registry
    When "weekend-shift" is renamed "Weekend Cover"
    Then "weekend-shift" is now named "Weekend Cover"

  Scenario: Removing reports whether there was one
    # So a caller can tell a deletion from a no-op.
    Given a registry
    Then removing "continuous" works
    And removing "continuous" again does not

  # ---- the one rule the whole feature rests on ----------------------------

  Scenario: A named calendar is followed
    # A weekend calendar works the Saturday the plan does not.
    Given a registry
    When "weekend-shift" is resolved
    Then the Saturday 2026-09-12 is worked

  Scenario: Naming nothing follows the plan
    # Which is what almost every task does.
    Given a registry
    When nothing is resolved
    Then the plan's own week answers
    And the Saturday 2026-09-12 is not worked

  Scenario: Naming a deleted calendar falls back rather than raising
    # A calendar can be deleted while tasks still point at it. A plan
    # that will not open - or a task with no calendar at all, which
    # would hang the day-by-day walks - is a far worse answer than a
    # task quietly back on the plan's own week.
    Given a registry
    When "weekend-shift" is removed
    And "weekend-shift" is resolved
    Then the plan's own week answers

  Scenario: An empty registry resolves everything to the plan
    # A plan that never named a calendar behaves exactly as before.
    Given an empty registry
    Then resolving "anything" answers the plan's own week
    And resolving nothing answers the plan's own week

  # ---- the summary shown beside a calendar's name --------------------------

  Scenario: The standard week is named, not spelt out
    Then a calendar working Monday to Friday reads "Mon-Fri"

  Scenario: The weekend is named
    Then a calendar working only the weekend reads "Sat-Sun"

  Scenario: Every day is named
    Then a calendar working every day reads "every day"

  Scenario: An unusual week is spelt out
    # There is no name for it, so the days are named.
    Then a calendar working Monday, Wednesday and Friday reads "Mon, Wed, Fri"

  Scenario: A week with nothing in it still reads
    Then a calendar working nothing reads "no days worked"

  # ---- a registry has to survive being saved and reopened -------------------

  Scenario: A registry round-trips
    # Ids, names, order and each calendar's own contents.
    Given a registry where "weekend-shift" takes 2026-12-25 off for "Christmas off even here"
    When the registry is saved and loaded
    Then it equals what was saved
    And "weekend-shift" still holds the "Christmas off even here" override

  Scenario: The shape the feature was specified in is accepted
    # A dictionary keyed by id, as well as a list - a hand-written file
    # is likelier to arrive that way than to be rejected for it.
    When a dictionary keyed by id is loaded
    Then the calendar ids are "a, b"

  Scenario: One damaged calendar does not cost the rest
    # A bad entry is dropped with a line in the log, not raised.
    When a list with two bad entries is loaded
    Then the calendar ids are "kept"

  Scenario: Nothing saved gives an empty registry
    # Rather than raising on a plan that predates the feature.
    When nothing is loaded
    Then the registry is empty

  # ---- one strand of work on a different week ------------------------------
  # Three tasks starting the same Thursday 2026-09-10, on three calendars.

  Scenario: The plan's own calendar skips the weekend
    # Two days from a Thursday reach the Friday.
    Given a plan "Mixed" with three tasks on three calendars
    When the plan is rescheduled
    Then "Frontend Work" runs 2026-09-10 to 2026-09-11

  Scenario: A weekend task starts on the Saturday
    # Its start rolls forward to a day it can actually begin on: a
    # Thursday is not a working day on a weekend-only calendar.
    Given a plan "Mixed" with three tasks on three calendars
    When the plan is rescheduled
    Then "Server Migration" runs 2026-09-12 to 2026-09-13

  Scenario: A continuous task runs straight through
    # Nothing is skipped, so two days are two days.
    Given a plan "Mixed" with three tasks on three calendars
    When the plan is rescheduled
    Then "Load Test" runs 2026-09-10 to 2026-09-11

  Scenario: Each task keeps the work it holds
    # Three calendars, three sets of dates, the same two days each.
    Given a plan "Mixed" with three tasks on three calendars
    When the plan is rescheduled
    Then every task holds 2 days of work

  Scenario: A task naming a deleted calendar is scheduled anyway
    # Back on the plan's own week, rather than not at all. It lands on
    # the Monday, not back on the Thursday it was first given:
    # rescheduling rolls a start forward off a day nobody works and
    # never pulls one backwards.
    Given a plan "Mixed" with three tasks on three calendars
    When the plan is rescheduled
    Then "Server Migration" starts on 2026-09-12
    When "weekend-shift" is removed from the plan
    And the plan is rescheduled
    Then "Server Migration" runs 2026-09-14 to 2026-09-15

  Scenario: The calendar a task follows survives saving
    # Both the id on the task and the calendar it names.
    Given a plan "Mixed" with three tasks on three calendars
    When the plan is rescheduled
    And the plan is saved and loaded
    Then "Server Migration" still follows "weekend-shift"
    And every task ends where it did

  # ---- changing a calendar moves the tasks that follow it, and only those ---

  Scenario: Editing a calendar holds the work and moves the finish
    # The reason set_calendars goes through apply_calendar: adding
    # Friday to a weekend calendar should pull its task in by a day,
    # not hand it a third day of effort.
    Given a plan "Edit" with "Migration" on "weekend-shift" for 3 days starting "2026-09-10"
    When the plan is rescheduled
    Then "Migration" ends on 2026-09-19
    When "weekend-shift" gains Friday
    Then "Migration" still holds 3 days of work
    And "Migration" runs 2026-09-12 to 2026-09-18

  Scenario: Tasks on other calendars are left alone
    # Editing one calendar is not editing the plan.
    Given a plan "Edit" with "Ordinary" on the plan's week for 3 days starting "2026-09-10"
    When the plan is rescheduled
    And "weekend-shift" gains Friday
    Then "Ordinary" still ends where it did

  Scenario: Changing the plan's week leaves a named task alone
    # apply_calendar rebuilt every task on whatever calendar it was
    # handed, which put the weekend task back on the plan's week the
    # first time anybody touched the holiday settings.
    Given a plan "Edit" with "Migration" on "weekend-shift" for 2 days starting "2026-09-10"
    When the plan is rescheduled
    Then "Migration" starts on 2026-09-12
    When the plan takes on a six-day week
    Then "Migration" starts on 2026-09-12

  Scenario: An override on a named calendar is honoured
    # The whole of WorkingCalendar comes along, not just the week.
    Given a plan "Edit" whose "weekend-shift" takes 2026-09-12 off for "Site closed"
    And a task "Migration" on "weekend-shift" for 1 day starting "2026-09-10"
    When the plan is rescheduled
    Then "Migration" starts on 2026-09-13

  # ---- seeded, but never invented for a file that did not have them --------

  Scenario: A new project is seeded so the feature is there to be found
    Then a new plan's calendar ids are "standard-week, weekend-shift, continuous"

  Scenario: A plan written before calendars gets none
    # Three calendars in a file nobody added them to is worse.
    Then a legacy plan gets no calendars

  Scenario: A deliberately emptied registry stays empty
    # Deleting them all has to survive a save.
    Then a legacy plan saving an empty registry still has no calendars

  Scenario: The seeding happens once, not on every open
    Given a new plan with "continuous" removed
    When the plan is saved and loaded
    Then the loaded plan's calendar ids are "standard-week, weekend-shift"

  # ---- one number, one meaning, wherever it is typed ------------------------

  Scenario Outline: The wait after a lag is the same length on every calendar
    # Counted on the successor's week, a lag of 2 was two days for an
    # ordinary task, two for a 24/7 run, and eight calendar days for a
    # weekend-only shift - not a wait anybody asked for. The wait is
    # held steady on the plan's calendar; where the task lands is the
    # successor's own week. A Friday finish, a lag of two, and a
    # successor that follows some calendar.
    Given a follower on "<calendar>" lagging a Friday finish by 2
    When the plan is rescheduled
    Then the follower starts on "<date>"

    Examples:
      | calendar       | date       |
      | the plan's own | 2026-09-16 |
      | continuous     | 2026-09-16 |
      | weekend-shift  | 2026-09-19 |
