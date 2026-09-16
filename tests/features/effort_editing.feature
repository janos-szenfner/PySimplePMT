@effort_editing
Feature: The task editor's effort reconciliation (phase 3b)
  These exercise TaskFormDialog._reconcile_effort - the method the Save
  path calls - without building the whole editor: it needs only
  ``self.project`` on the non-conflict path, so a light stand-in stands
  in for the dialog. The conflict-prompt branch is a UI dialog and is
  covered by the engine tests (tests/test_effort_engine.py).

  Background: a project on an eight-hour day
    Given a project on an eight-hour day

  Scenario: A resourced fixed-units duration edit recomputes work
    Given a fixed-units task of 5 days with R1 at 40.0 hours and 100.0 percent
    When the form is saved with duration 10 and R1 at 40.0 hours and 100.0 percent
    Then the saved duration is 10
    And the saved assignment "R1" carries 80.0 hours

  Scenario: An unresourced task is returned unchanged
    Given a plain task of 5 days
    When the form is saved with duration 10 and no assignments
    Then the saved duration is 10
    And no assignments come back

  Scenario: A zero-percent assignment is left alone
    Given a task of 5 days with R1 at 40.0 hours and 0.0 percent
    When the form is saved with duration 10 and R1 at 40.0 hours and 0.0 percent
    Then the saved duration is 10
    And the saved assignment "R1" carries 40.0 hours

  Scenario: A fixed-duration work edit recomputes units
    Given a fixed-duration task of 5 days with R1 at 40.0 hours and 100.0 percent
    When the form is saved as fixed-duration with duration 5 and R1 at 80.0 hours and 100.0 percent
    Then the saved duration is 5
    And the saved assignment "R1" carries 200.0 percent

  Scenario: Adding a resource to an effort-driven task halves the duration
    # Issue #30's core case: ED on, a second 100% resource, and the save
    # preserves the work so the duration halves.
    Given an effort-driven fixed-units task of 10 days with R1 at 80.0 hours
    When the form is saved effort-driven with duration 10 and a second resource "R2" seeded empty
    Then the saved duration is 5
    And the saved assignments total 80.0 hours

  Scenario: Adding a resource with effort-driven off grows the work
    # The same add with ED off holds the duration; the work doubles.
    Given a non-effort-driven fixed-units task of 10 days with R1 at 80.0 hours
    When the form is saved not effort-driven with duration 10 and a second resource "R2" seeded empty
    Then the saved duration is 10
    And the saved assignments total 160.0 hours

  Scenario: Removing a resource from an effort-driven task extends the duration
    # The removed resource's hours pass to the one left, so the work is
    # conserved and the duration extends back.
    Given an effort-driven task of 5 days shared by R1 and R2 at 40.0 hours each
    When the form is saved with duration 5 and R1 at 40.0 hours and 100.0 percent
    Then the saved duration is 10
    And the saved assignment "R1" carries 80.0 hours
