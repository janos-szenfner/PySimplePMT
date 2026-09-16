@snlt_conflict
Feature: Start/Finish No Later Than conflict detection and resolution
  (issue #28)

  A No-Later-Than constraint was only weighed against a task's own
  direct dependency links, so a task held past its date by its parent
  summary - or sitting past it for any other reason - reported no
  conflict at all and the Save-time dialog never appeared ("nothing
  happens"). Detection now reads where the task actually lands, and the
  Remove Predecessors resolution drops the links and pulls the task to
  the date it was given.

  Background: a plan starting 2026-10-01
    Given a plan starting 2026-10-01

  Scenario: A task sitting past its SNLT conflicts without links
    # The screenshot case: a task placed at 10-20 with no predecessors
    # of its own, told to start no later than 10-05.
    Given task "T" from 2026-10-20 to 2026-10-21 constrained "SNLT" to 2026-10-05
    Then task "T" reports a constraint conflict
    And task "T" is among the conflicts

  Scenario: A child held by its summary conflicts
    Given a phase "P1" from 2026-10-20 to 2026-10-24
    And task "C" under "P1" from 2026-10-20 to 2026-10-21 constrained "SNLT" to 2026-10-05
    Then task "C" reports a constraint conflict

  Scenario: A meetable SNLT is no conflict
    Given task "T" from 2026-10-05 to 2026-10-06 constrained "SNLT" to 2026-10-20
    Then task "T" reports no constraint conflict

  Scenario: A task finishing past its FNLT conflicts
    Given task "T" from 2026-10-19 to 2026-10-23 constrained "FNLT" to 2026-10-05
    Then task "T" reports a constraint conflict

  Scenario: A SNET floor is never a conflict
    # The change must not touch the flexible floors.
    Given task "T" from 2026-10-20 to 2026-10-21 constrained "SNET" to 2026-10-05
    Then task "T" reports no constraint conflict

  Scenario: SNLT meeting dates are on or before the date
    Given task "T" from 2026-10-20 to 2026-10-21 constrained "SNLT" to 2026-10-05
    When the meeting dates are asked for task "T"
    Then the meeting start is 2026-10-05

  Scenario: A weekend SNLT lands on the working day before it
    # 2026-10-04 is a Sunday: starting "no later than" it means the Friday.
    Given task "T" from 2026-10-20 to 2026-10-21 constrained "SNLT" to 2026-10-04
    When the meeting dates are asked for task "T"
    Then the meeting start is 2026-10-02

  Scenario: FNLT meeting dates fix the finish
    Given task "T" from 2026-10-19 to 2026-10-23 constrained "FNLT" to 2026-10-06
    When the meeting dates are asked for task "T"
    Then the meeting end is 2026-10-06

  Scenario: Other constraints have no meeting dates
    Given task "T" from 2026-10-20 constrained "MSO" to 2026-10-05
    When the meeting dates are asked for task "T"
    Then there are no meeting dates

  Scenario: An SNLT conflict clears after removing predecessors
    Given a linked plan where "B" is constrained "SNLT" to 2026-10-02
    And task "B" reports a constraint conflict
    When the predecessors of "B" are removed and the meeting dates applied
    Then task "B" reports no constraint conflict
    And task "B" has no dependencies
    And task "B" starts on 2026-10-02

  Scenario: An FNLT conflict clears after removing predecessors
    Given a linked plan where "B" is constrained "FNLT" to 2026-10-05
    And task "B" reports a constraint conflict
    When the predecessors of "B" are removed and the meeting dates applied
    Then task "B" reports no constraint conflict
    And task "B" ends on 2026-10-05
