Feature: The settings a whole plan is built from
  Two of these settings are not settings at all in the ordinary sense.

  The start date is not a field on a project - it is derived from the
  tasks - so the box is a command: typing a date moves the whole plan.
  What has to be true afterwards is that every duration and every gap
  survived it, because the alternative implementation, rescheduling
  from the new date, would collapse every gap somebody had put there on
  purpose.

  The direction is the other. Scheduled backward, the plan is packed as
  late as it can go against a deadline - which is a different thing
  from sliding it, and the difference only shows on a task with float:
  a slide keeps it early, and As Late As Possible does not.

  The panel over these settings needs a display and stays in the
  unittest module.

  # ---- what a project holds, and what an older file gets --------------------------------------

  Scenario: A new plan is scheduled forward
    # Which is what every plan did before there was a choice.
    Then a new plan schedules from "start"

  Scenario: A direction it does not know falls back
    # A damaged file opens forward rather than not at all.
    Then a plan asking for direction "sideways" schedules from "start"

  Scenario Outline: The priority is clamped rather than refused
    # It arrives from a text box and from saved files. A plan that will
    # not open because somebody typed 2000 would be a poor trade for a
    # number nothing acts on yet.
    Then a plan with priority <given> holds <expected>

    Examples:
      | given    | expected |
      | 2000     | max      |
      | 0        | min      |
      | nonsense | default  |

  Scenario: The settings survive a saved file
    # All four of them.
    Given a plan scheduled from "finish" with deadline "2026-12-01", status "2026-11-01" and priority 750
    When the plan is saved and read back
    Then it schedules from "finish"
    And its deadline is "2026-12-01"
    And its status date is "2026-11-01"
    And its priority is 750

  Scenario: A plan saved before the settings existed opens
    # With the defaults, which are what those plans meant.
    Given a saved plan with the settings removed
    When the plan is read back
    Then it schedules from "start"
    And it has no deadline
    And it has no status date
    And its priority is the default

  Scenario: An unreadable date does not stop the file opening
    # A setting comes back empty rather than the plan failing to load.
    Given a saved plan with deadline "the third of never"
    When the plan is read back
    Then it has no deadline

  # ---- the start date box, which is a command rather than a setting ------------------------------
  # The fixture: a chain a -> b -> c, plus one task with float hanging
  # off a.

  Scenario: It begins on the date given
    # Which is the whole of what the box promises.
    Given the chain plan
    When the plan is shifted to "2026-09-14"
    Then the plan starts "2026-09-14"

  Scenario: Every duration survives
    # A plan is moved, not rebuilt.
    Given the chain plan
    When the plan is shifted to "2026-09-14"
    Then every working duration is what it was

  Scenario: The gaps between tasks survive
    # Rescheduling from the new date would pull everything up against
    # its links and collapse every gap somebody had put there on
    # purpose.
    Given the chain plan
    When the plan is shifted to "2026-09-14"
    Then the gap between "a" and "c" is what it was

  Scenario: A constraint date moves with it
    # A constraint set relative to the plan around it moves with that
    # plan. Left behind, a plan shifted six months later is full of
    # constraints nobody wrote (issue #32).
    Given the chain plan
    And "c" is pinned "SNET" to "2026-08-24"
    When the plan is shifted to "2026-09-14"
    Then "c" is pinned later than "2026-08-24"

  Scenario: Moving it where it already is changes nothing
    # And says so, so a caller can skip the redraw.
    Given the chain plan
    Then shifting the plan to its own start says nothing moved

  Scenario: An empty plan is not moved
    # There is nothing to move and nothing to fail on.
    Then an empty plan says nothing moved

  # ---- As Late As Possible, against a deadline ---------------------------------------------------

  Scenario: The plan ends on the deadline
    # Which is the point of scheduling from a finish date.
    Given the chain plan
    When it is scheduled backward to "2026-10-30"
    Then the plan ends "2026-10-30"

  Scenario: Durations survive
    # The work is moved, not compressed.
    Given the chain plan
    When it is scheduled backward to "2026-10-30"
    Then every working duration is what it was

  Scenario: The links are still satisfied
    # Nothing is rescheduled afterwards, so this is what says the late
    # dates were right - they satisfy every link by construction, which
    # is what the backward pass computes.
    Given the chain plan
    When it is scheduled backward to "2026-10-30"
    Then "b" still starts after "a" ends
    And "c" still starts after "b" ends

  Scenario: A task with float is moved late
    # The behaviour that tells this apart from sliding the plan. A
    # slide keeps a task with float where it was relative to
    # everything else - early. As Late As Possible pushes it up
    # against the finish.
    Given the chain plan
    When it is scheduled backward to "2026-10-30"
    Then "slack" finishes later in the plan than forward-scheduled

  Scenario: A deadline in the past still moves the plan
    # A deadline that cannot be met from today is what a reader needs
    # to be shown, and refusing to move would hide it.
    Given the chain plan
    When it is scheduled backward to "2020-01-31"
    Then the plan ends "2020-01-31"

  Scenario: A forward plan is settled exactly as before
    # apply_schedule dispatches on the direction, and a plan scheduled
    # forward has to get reschedule and nothing else.
    Given two identical chain plans
    When one applies its schedule and the other reschedules
    Then they agree on every task's dates
