Feature: Dependency link types shift successors
  Regression cover for the scheduling engine the dependency tab drives, drawn
  from the dependency and advanced-engine Gherkin. The application models
  working-day dates (no intraday time), so the source timestamps are read as
  their calendar day and the rules are checked against the engine's own
  working-day arithmetic. These must keep passing whether or not a task also
  carries an Advanced-tab constraint - see the non-interference suite.

  Background:
    Given a project scheduled from "2026-10-01"

  Scenario: A Finish-to-Start link shifts the successor when the predecessor grows
    Given task "A" of 3 working days and task "B" of 2 working days
    And "B" has a "FS" link to "A"
    When the plan is rescheduled
    Then "B" starts the working day after "A" finishes
    When "A" grows to 5 working days
    And the plan is rescheduled
    Then "B" starts the working day after "A" finishes

  Scenario Outline: Each link type enforces its own rule
    Given task "A" of 5 working days and task "B" of 3 working days
    And "B" has a "<link>" link to "A"
    When the plan is rescheduled
    Then "B" <relation>

    Examples:
      | link | relation                  |
      | SS   | starts when A starts      |
      | FF   | finishes when A finishes  |
      | SF   | finishes when A starts    |

  Scenario: A Finish-to-Start link with positive lag respects working days
    Given task "A" of 5 working days and task "B" of 3 working days
    And "B" has a "FS" link to "A" with lag 2
    When the plan is rescheduled
    Then "B" starts 2 working days after the day it would start unlagged

  Scenario: A successor with two driving predecessors takes the later boundary
    Given task "A" of 5 working days and task "B" of 2 working days
    And task "C" of 2 working days
    And "C" has a "FS" link to "A"
    And "C" has a "SS" link to "B" with lag 2
    When the plan is rescheduled
    Then "C" starts at the later of its two link floors

  Scenario: A circular dependency is refused, leaving the network unchanged
    Given task "A" of 2 working days and task "B" of 2 working days
    And "B" has a "FS" link to "A"
    Then making "A" wait for "B" would be circular
    And "B" still has exactly one link
