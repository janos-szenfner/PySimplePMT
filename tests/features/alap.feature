@alap
Feature: As Late As Possible actually moves a task (issue #26)
  The constraint used to be recorded and drawn but never scheduled -
  "nothing happens". A leaf set As Late As Possible is now pushed to the
  latest finish its collection and its successors allow: a child with
  nothing waiting on it ends level with its summary, and one that a
  sibling waits for ends the working day before that sibling starts.

  Background: a summary with an early ALAP child, a later ALAP child a
  sibling waits for, and that sibling driving the summary end
    Given the ALAP plan under a summary

  Scenario: A child with no successor ends level with the summary
    Then task "A" ends level with its summary

  Scenario: A child a sibling waits for ends before that sibling
    Then task "B" ends the working day before task "C" starts

  Scenario: The ALAP child keeps its length
    Then task "A" still takes 3 working days

  Scenario: The plan settles
    When the plan is scheduled again
    Then the reschedule reports nothing moved

  Scenario: ALAP is not pulled to the collection start
    # The summary has a predecessor, so a link-less child would normally
    # be aligned to the collection start (issue #25). ALAP overrides that.
    Given a summary with a predecessor and an ALAP child
    Then task "A" ends level with its summary
    And task "A" starts after 2026-09-14

  Scenario: The latest child is left where it is
    # An ALAP child that is already the last has nothing to slide against.
    Given a summary whose last child is ALAP
    Then task "B" still ends on 2026-09-25

  Scenario: A top-level ALAP task without a successor stays put
    Given a top-level ALAP task from 2026-09-14 for 3 days
    Then task "T" still starts on 2026-09-14

  Scenario: An ALAP milestone is pushed later
    # It no longer sits at the front; it slides to the end of the work.
    Given a summary holding work and an ALAP milestone
    Then the milestone starts after 2026-09-14
    And the milestone sits at its summary's end
