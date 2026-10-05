Feature: The Task Type / Effort-Driven engine
  The scenarios mirror Task_Type_FRS section 9 by number, with
  hours_per_day = 8 so a day is eight hours. Pure maths, so no display
  is needed. The three numbers - duration, work and units - are bound
  by the task type's rule about which one is held.

  # ---- conversions -------------------------------------------------------------

  Scenario: A day is eight hours
    Then 1 day at 8 a day is 8 hours
    And 5 days at 8 a day is 40 hours

  # ---- section 9.1: Fixed Units, effort-driven, add a resource -------------------
  # Work preserved, duration halves.

  Scenario: 9.1 - work preserved, duration halves
    Given a "Fixed Units" state running 8 hours of 8 work holding "R1" at 1.0
    When "R2" at 1.0 is added
    Then the answer was accepted
    And it carries 8 work
    And it runs 4 hours
    And its total units are 2.0

  # ---- section 9.2: Fixed Units, not effort-driven, add a resource -----------------
  # Duration preserved, work doubles.

  Scenario: 9.2 - duration preserved, work doubles
    Given a "Fixed Units" state running 8 hours of 8 work holding "R1" at 1.0
    And effort-driven is off
    When "R2" at 1.0 is added
    Then the answer was accepted
    And it runs 8 hours
    And it carries 16 work

  # ---- section 9.3: Fixed Work ------------------------------------------------------
  # Fixed Work is effort-driven; a manual duration lifts allocation.

  Scenario: 9.3 - effort-driven is forced on
    Given a "Fixed Work" state
    And effort-driven is off
    Then effort-driven reads on

  Scenario: 9.3 - adding a resource preserves the work
    Given a "Fixed Work" state running 40 hours of 40 work holding "R1" at 1.0
    When "R2" at 1.0 is added
    Then it carries 40 work
    And it runs 20 hours

  Scenario: 9.3 - a manual duration recalculates units and warns
    # 4 days x 8 = 32 hours; 40 / 32 = 1.25 - a resource over 100%.
    Given a "Fixed Work" state running 40 hours of 40 work holding "R1" at 1.0
    When the duration is edited to 32 hours
    Then the answer was accepted
    And the answer warned
    And it carries 40 work
    And its total units are 1.25

  Scenario: 9.3 - work cannot be edited directly
    Given a "Fixed Work" state running 40 hours of 40 work holding "R1" at 1.0
    When the work is edited to 80
    Then the answer was refused
    And it carries 40 work

  # ---- section 9.4: Fixed Duration, effort-driven -------------------------------------
  # Duration locked, work preserved, units shared out.

  Scenario: 9.4 - units redistribute to keep the duration
    Given a "Fixed Duration" state running 40 hours of 40 work holding "R1" at 1.0
    When "R2" at 1.0 is added
    Then it runs 40 hours
    And it carries 40 work
    And its total units are 1.0
    And each resource is at 0.5

  # ---- section 9.5: Fixed Duration, not effort-driven -----------------------------------
  # Duration locked, work grows; duration edits refused.

  Scenario: 9.5 - work grows while the duration holds
    Given a "Fixed Duration" state running 40 hours of 40 work holding "R1" at 1.0
    And effort-driven is off
    When "R2" at 1.0 is added
    Then it runs 40 hours
    And it carries 80 work

  Scenario: 9.5 - the duration is locked
    Given a "Fixed Duration" state running 40 hours of 40 work holding "R1" at 1.0
    When the duration is edited to 48 hours
    Then the answer was refused
    And it runs 40 hours

  # ---- section 9.10: partial allocations -------------------------------------------------

  Scenario: 9.10 - a half-time resource added, work preserved
    # 80 / 2.5.
    Given a "Fixed Units" state running 40 hours of 80 work holding "A" at 1.0 and "B" at 1.0
    When "C" at 0.5 is added
    Then it carries 80 work
    And its total units are 2.5
    And it runs 32 hours

  # ---- resource removal ---------------------------------------------------------------------

  Scenario: Removing a resource extends an effort-driven task
    Given a "Fixed Units" state running 4 hours of 8 work holding "R1" at 1.0 and "R2" at 1.0
    When "R2" is removed
    Then it carries 8 work
    And it runs 8 hours

  Scenario: Removing the last resource is refused
    Given a "Fixed Units" state running 8 hours of 8 work holding "R1" at 1.0
    When "R1" is removed
    Then the answer was refused

  Scenario: Effort-driven off, removal shrinks the work
    Given a "Fixed Units" state running 8 hours of 16 work holding "R1" at 1.0 and "R2" at 1.0
    And effort-driven is off
    When "R2" is removed
    Then it runs 8 hours
    And it carries 8 work

  # ---- direct edits -----------------------------------------------------------------------------

  Scenario: Fixed Units - a duration edit recalculates work
    Given a "Fixed Units" state running 8 hours of 8 work holding "R1" at 1.0
    When the duration is edited to 16 hours
    Then it carries 16 work

  Scenario: Fixed Units - a work edit recalculates duration
    Given a "Fixed Units" state running 8 hours of 8 work holding "R1" at 1.0
    When the work is edited to 16
    Then it runs 16 hours

  Scenario: Fixed Duration - a work edit recalculates units
    # 80 / 40.
    Given a "Fixed Duration" state running 40 hours of 40 work holding "R1" at 1.0
    When the work is edited to 80
    Then its total units are 2.0

  # ---- validation ---------------------------------------------------------------------------------

  Scenario: Fixed Work needs work
    Given a "Fixed Work" state carrying 0 work holding "R1" at 1.0
    Then it does not validate

  Scenario: Fixed Work needs a resource
    Given a "Fixed Work" state carrying 40 work
    Then it does not validate

  Scenario: Fixed Duration needs a duration
    Given a "Fixed Duration" state running 0 hours
    Then it does not validate

  Scenario: Work without a resource is refused
    Given a "Fixed Units" state carrying 8 work
    Then it does not validate

  Scenario: A placeholder with no work is valid
    Given a "Fixed Units" state
    Then it validates

  Scenario: Negatives are refused
    Given a "Fixed Units" state carrying -1 work holding "R1" at 1.0
    Then it does not validate

  # ---- changing the task type -----------------------------------------------------------------------

  Scenario: Switching to Fixed Work locks effort-driven on
    Given a "Fixed Units" state running 8 hours of 8 work holding "R1" at 1.0
    And effort-driven is off
    When it switches to "Fixed Work"
    Then the answer was accepted
    And effort-driven reads on

  Scenario: Switching to Fixed Work without work is refused
    Given a "Fixed Units" state carrying 0 work holding "R1" at 1.0
    When it switches to "Fixed Work"
    Then the answer was refused

  Scenario: A hard constraint is flagged
    Given a "Fixed Units" state running 8 hours of 8 work holding "R1" at 1.0
    And it is constrained "MSO"
    When it switches to "Fixed Duration"
    Then the answer warned

  # ---- the effort-driven toggle ------------------------------------------------------------------------

  Scenario: Fixed Work cannot be toggled off
    Given a "Fixed Work" state carrying 8 work holding "R1" at 1.0
    Then switching effort-driven off is refused

  Scenario: A milestone has no effort logic
    Given a "Fixed Units" state that is a milestone
    Then the effort logic does not apply
    And switching effort-driven off is refused

  Scenario: A manually scheduled task has no effort logic
    Given a "Fixed Units" state that is manually scheduled
    Then the effort logic does not apply

  Scenario: Toggling a Fixed Units task
    Given a "Fixed Units" state
    When effort-driven is switched off
    Then the answer was accepted
    And effort-driven reads off

  # ---- recalculate --------------------------------------------------------------------------------------

  Scenario: Fixed Units solves the duration
    Given a "Fixed Units" state carrying 16 work holding "R1" at 1.0
    When it is recalculated
    Then it runs 16 hours

  # ---- spotting what moved ------------------------------------------------------------------------------

  Scenario: It spots each moved number
    Given a state of 8 hours and 8 work holding "R1" at 1.0
    And a second state of 16 hours and 8 work holding "R1" at 1.0
    When they are compared
    Then only "duration" moved

  # ---- the reconcile gate ---------------------------------------------------------------------------------
  # The maths only runs for a resourced, auto-scheduled leaf task.

  Scenario: A task with no units is left alone
    Given a pair of "Fixed Units" states of 8 and 16 hours, 0 work, unresourced
    When the pair is reconciled
    Then there is no conflict
    And the new state carries 0 work
    And the new state runs 16 hours

  Scenario: An assignment at zero percent counts as no units
    Given a pair of "Fixed Units" states of 8 and 16 hours, 8 work, holding "R1" at 0.0
    When the pair is reconciled
    Then there is no conflict
    And the new state carries 8 work

  Scenario: A milestone is left alone
    Given a pair of "Fixed Units" milestone states of 8 and 16 hours, 8 work, holding "R1" at 1.0
    When the pair is reconciled
    Then there is no conflict
    And the new state carries 8 work

  # ---- one adjustable variable changed - the other is recomputed, no prompt --------------------------------

  Scenario: Fixed Units - a duration change recomputes work
    # 16 x 1.0.
    Given a pair of "Fixed Units" states of 8 hours, 8 work, holding "R1" at 1.0
    And the new state runs 16 hours
    When the pair is reconciled
    Then there is no conflict
    And the new state carries 16 work

  Scenario: Fixed Units - a work change recomputes duration
    # 16 / 1.0.
    Given a pair of "Fixed Units" states of 8 hours, 8 work, holding "R1" at 1.0
    And the new state carries 16 work
    When the pair is reconciled
    Then there is no conflict
    And the new state runs 16 hours

  Scenario: Fixed Duration - a work change recomputes units
    # 80 / 40.
    Given a pair of "Fixed Duration" states of 40 hours, 40 work, holding "R1" at 1.0
    And the new state carries 80 work
    When the pair is reconciled
    Then there is no conflict
    And the new state's total units are 2.0

  Scenario: Fixed Work - a units change recomputes duration
    # 40 / 2.0.
    Given a pair of "Fixed Work" states of 40 hours, 40 work, holding "R1" at 1.0
    And the new state's "R1" is at 2.0
    When the pair is reconciled
    Then there is no conflict
    And the new state runs 20 hours

  # ---- both adjustable variables changed - a prompt, then the planner's pick --------------------------------

  Scenario: Changing both raises a conflict
    Given a pair of "Fixed Units" states where duration and work moved
    When the pair is reconciled
    Then a conflict names "units" fixed and "duration, work" the options

  Scenario: Preserving duration recomputes work
    # 16 x 1.0.
    Given a pair of "Fixed Units" states where duration and work moved
    When the pair is reconciled preserving "duration"
    Then there is no conflict
    And the new state runs 16 hours
    And the new state carries 16 work

  Scenario: Preserving work recomputes duration
    # 24 / 1.0.
    Given a pair of "Fixed Units" states where duration and work moved
    When the pair is reconciled preserving "work"
    Then there is no conflict
    And the new state carries 24 work
    And the new state runs 24 hours

  Scenario: The prompt names both variables
    Given a pair of "Fixed Units" states where duration and work moved
    When the pair is reconciled
    Then the conflict's prompt names "Duration" and "Work"

  # ---- roster changes through reconcile - the save path the editor takes -------------------------------------
  # Effort-Driven only speaks when a resource is added or removed, which
  # the form shows as a changed assignment list rather than an edit to
  # duration or work (issue #30's table). On, the work is conserved;
  # off, the duration is.

  Scenario: Fixed Units, effort-driven - adding halves the duration
    Given an 80-hour "Fixed Units" effort-driven pair holding "R1" at 1.0 for 80 hours
    And the new state also holds "R2" at 1.0 for 0 hours
    When the pair is reconciled
    Then there is no conflict
    And the new state carries 80 work
    And the new state runs 40 hours

  Scenario: Fixed Units, not effort-driven - adding grows the work
    Given an 80-hour "Fixed Units" not-effort-driven pair holding "R1" at 1.0 for 80 hours
    And the new state also holds "R2" at 1.0 for 0 hours
    When the pair is reconciled
    Then there is no conflict
    And the new state runs 80 hours
    And the new state carries 160 work

  Scenario: Fixed Duration, effort-driven - adding redistributes the units
    Given an 80-hour "Fixed Duration" effort-driven pair holding "R1" at 1.0 for 80 hours
    And the new state also holds "R2" at 1.0 for 0 hours
    When the pair is reconciled
    Then there is no conflict
    And the new state carries 80 work
    And the new state runs 80 hours
    And the new state's total units are 1.0

  Scenario: Fixed Duration, not effort-driven - the units stay and the work grows
    Given an 80-hour "Fixed Duration" not-effort-driven pair holding "R1" at 1.0 for 80 hours
    And the new state also holds "R2" at 1.0 for 0 hours
    When the pair is reconciled
    Then there is no conflict
    And the new state runs 80 hours
    And the new state carries 160 work
    And the new state's total units are 2.0

  Scenario: Fixed Work - adding halves the duration
    Given an 80-hour "Fixed Work" effort-driven pair holding "R1" at 1.0 for 80 hours
    And the new state also holds "R2" at 1.0 for 0 hours
    When the pair is reconciled
    Then there is no conflict
    And the new state carries 80 work
    And the new state runs 40 hours

  Scenario: Effort-driven removal transfers the work
    # The removed resource's hours pass to those left, so work is
    # conserved and duration extends - the inverse of the add.
    Given a 40-hour "Fixed Units" effort-driven pair holding "R1" at 1.0 for 40 hours and "R2" at 1.0 for 40 hours
    And the new state drops "R2"
    When the pair is reconciled
    Then there is no conflict
    And the new state carries 80 work
    And the new state runs 80 hours

  Scenario: Not-effort-driven removal shrinks the work
    # The hours leave with the resource; the duration is preserved.
    Given a 40-hour "Fixed Units" not-effort-driven pair holding "R1" at 1.0 for 40 hours and "R2" at 1.0 for 40 hours
    And the new state drops "R2"
    When the pair is reconciled
    Then there is no conflict
    And the new state runs 40 hours
    And the new state carries 40 work

  Scenario: The first resource still takes duration x units
    # No work existed to conserve, so a zero-work task's first
    # resource gets duration x units whatever the toggle says.
    Given an 80-hour "Fixed Units" effort-driven pair holding nobody
    And the new state also holds "R1" at 1.0 for 0 hours
    When the pair is reconciled
    Then there is no conflict
    And the new state runs 80 hours
    And the new state carries 80 work

  Scenario: A duration edit on top of an add still wins
    # The toggle only chooses when the planner did not.
    Given an 80-hour "Fixed Units" effort-driven pair holding "R1" at 1.0 for 80 hours
    And the new state also holds "R2" at 1.0 for 0 hours
    And the new state runs 160 hours
    When the pair is reconciled
    Then there is no conflict
    And the new state runs 160 hours
    And the new state carries 320 work

  Scenario: A same-roster units edit is not effort-driven
    # Editing a split is a units edit, not a roster change: the held
    # values follow the task type's own rule either way.
    Given an 80-hour "Fixed Units" effort-driven pair holding "R1" at 1.0 for 80 hours
    And the new state's "R1" is at 0.5
    When the pair is reconciled
    Then there is no conflict
    And the new state runs 80 hours
    And the new state carries 40 work

  # ---- lifting a Task into a state and writing a reconciled one back -------------------------------------------

  Scenario: The state reads days as hours and splits as units
    # 5 days x 8.
    Given a task of 5 days with "R1" for 40 hours at 100 percent
    When it is lifted into a state
    Then the state runs 40 hours
    And the state carries 40 work
    And the state's total units are 1.0

  Scenario: An unresourced task has no units
    Given a task of 5 days with nobody assigned
    When it is lifted into a state
    Then the state's total units are 0.0

  Scenario: Write-back rounds the duration to whole days
    # 8h of work over 2.0 units recalculates to 4h, which rounds to 0
    # days - and a task may not be shorter than one.
    Given a task of 1 day with "R1" for 8 hours at 100 percent and "R2" for 8 hours at 100 percent
    When it is lifted into a state
    And the state's work is set to 8
    And the state is recalculated
    And the state is written back
    Then the task reads 1 day

  Scenario: Write-back shares the work across assignments
    Given a task of 5 days with "R1" for 0 hours at 100 percent and "R2" for 0 hours at 100 percent
    When it is lifted into a state
    And the state's work follows duration x units
    And the state is written back
    Then the assignments carry 80 hours
    And "R1" carries 40 hours

  # ---- the direct units edit, and the refusals the engine guards --------------------------------------------------

  Scenario: A direct units edit on Fixed Work moves the duration
    # 16h of work over 4.0 units is 4h.
    Given a "Fixed Work" state running 8 hours of 16 work holding "R1" at 1.0
    When the "R1" units are edited to 4.0
    Then the answer was accepted
    And the state runs 4 hours

  Scenario: A direct units edit on Fixed Duration moves the work
    # Duration is locked, so halving the hands halves the work: 8h x 0.5.
    Given a "Fixed Duration" state running 8 hours of 16 work holding "R1" at 1.0
    When the "R1" units are edited to 0.5
    Then the answer was accepted
    And the state carries 4 work

  Scenario: A direct units edit on Fixed Units moves the work
    Given a "Fixed Units" state running 8 hours of 16 work holding "R1" at 1.0
    When the "R1" units are edited to 0.5
    Then the answer was accepted
    And the state carries 4 work

  Scenario: Units cannot be negative
    Given a "Fixed Units" state running 8 hours of 16 work holding "R1" at 1.0
    When the "R1" units are edited to -0.5
    Then the answer was refused

  Scenario: Units for a resource that is not there are refused
    Given a "Fixed Units" state running 8 hours of 16 work holding "R1" at 1.0
    When the units of assignment 5 are edited to 1.0
    Then the answer was refused

  Scenario: A Fixed Work edit to zero total units is refused
    # It would ask for an infinite duration.
    Given a "Fixed Work" state running 8 hours of 16 work holding "R1" at 1.0
    When the "R1" units are edited to 0.0
    Then the answer was refused

  Scenario: Removing a resource that is not there is refused
    Given a "Fixed Units" state running 8 hours of 16 work holding "R1" at 1.0
    When the assignment at index 7 is removed
    Then the answer was refused

  Scenario: Fixed Duration, effort-driven - removing shares the units out
    # The work is conserved inside the same duration, so the one left
    # standing takes both shares: 1.0 + 1.0 -> 2.0.
    Given a "Fixed Duration" effort-driven state running 8 hours of 16 work holding "R1" at 1.0 and "R2" at 1.0
    When "R2" is removed
    Then the answer was accepted
    And each resource is at 2.0
    And the state runs 8 hours

  Scenario: A negative-units add is refused
    Given a "Fixed Units" state running 8 hours of 16 work holding "R1" at 1.0
    When "R2" at -1.0 is added
    Then the answer was refused

  Scenario: Fixed Work refuses an add that still leaves nobody working
    # Work with a roster of zeros cannot take a duration.
    Given a "Fixed Work" state running 8 hours of 16 work holding "R1" at 0.0
    When "R2" at 0.0 is added
    Then the answer was refused

  Scenario: Fixed Duration accepts an add with no duration to divide
    # A degenerate state answers the message rather than dividing by it.
    Given a "Fixed Duration" effort-driven state running 0 hours of 16 work holding "R1" at 1.0
    When "R2" at 1.0 is added
    Then the answer was accepted

  Scenario: A negative duration edit is refused
    Given a "Fixed Units" state running 8 hours of 16 work holding "R1" at 1.0
    When the duration is edited to -4 hours
    Then the answer was refused

  Scenario: A negative work edit is refused
    Given a "Fixed Units" state running 8 hours of 16 work holding "R1" at 1.0
    When the work is edited to -4
    Then the answer was refused

  Scenario: Fixed Work refuses a zero-duration edit
    Given a "Fixed Work" state running 8 hours of 16 work holding "R1" at 1.0
    When the duration is edited to 0 hours
    Then the answer was refused

  Scenario: Fixed Work with no roster answers a duration edit politely
    # There is nobody to redistribute the units over, so the message is
    # all there is - no error, no division.
    Given a "Fixed Work" state running 8 hours of 16 work
    When the duration is edited to 4 hours
    Then the answer was accepted

  # ---- switching type: the entry rules refuse what they cannot hold ----------------------------------------------

  Scenario: A type nobody makes is refused
    Given a "Fixed Units" state running 8 hours of 16 work holding "R1" at 1.0
    When it switches to the unknown type "Sideways"
    Then the answer was refused

  Scenario: Fixed Duration refuses a switch into no duration
    Given a "Fixed Units" state running 0 hours holding "R1" at 1.0
    When it switches to "Fixed Duration"
    Then the answer was refused

  Scenario: Fixed Units refuses a switch into work with no hands
    Given a "Fixed Duration" state carrying 16 work
    When it switches to "Fixed Units"
    Then the answer was refused

  Scenario: Fixed Work refuses a switch into no work
    Given a "Fixed Units" state running 8 hours holding "R1" at 1.0
    When it switches to "Fixed Work"
    Then the answer was refused

  # ---- validate: a negative assignment is not a state -------------------------------------------------------------

  Scenario: A negative assignment does not validate
    Given a "Fixed Units" state running 8 hours of 16 work holding "R1" at -0.5
    Then it does not validate

  # ---- reconcile: Fixed Work holding duration scales the units ----------------------------------------------------

  Scenario: Fixed Work, a duration move scales the units instead
    # Work is held by the type; holding the edited duration too leaves
    # units to take the strain: 16h of work over 4h is 4.0 units.
    Given a 8-hour "Fixed Work" effort-driven pair holding "R1" at 1.0 for 16 hours
    And the new state runs 4 hours
    When the pair is reconciled
    Then there is no conflict
    And the new state runs 4 hours
    And the new state's "R1" is at 4.0

  Scenario: A roster change that alters nothing else is not a planner's edit
    # Swapping one pair of hands for another at the same total, with
    # Effort-Driven off, leaves every number alone - the diff is empty,
    # so the toggle picks the conserved quantity by itself.
    Given a 16-hour "Fixed Units" not-effort-driven pair holding "R1" at 1.0 for 16 hours
    And the new state swaps "R1" for "R2" at 1.0 for 16 hours
    When the pair is reconciled
    Then there is no conflict
    And the new state runs 16 hours
    And the new state carries 16 work

  # ---- a day is not always eight hours ----------------------------------------------------------------------------

  Scenario: A zero-length day measures no days
    # A calendar reporting no hours in a day reads as zero, not as a
    # division error.
    Given a "Fixed Units" state running 8 hours on a zero-length day
    Then it measures 0 days

  Scenario: Hours to days on a zero-length day is zero
    Then 8 hours at 0 a day is 0 days

  # ---- the task adapter takes what the file gives it ---------------------------------------------------------------

  Scenario: A gibberish split and gibberish hours read as zero
    # A saved file can carry anything; a bad split is no units and bad
    # hours are no hours, not an import error.
    Given a task of 5 days with "R1" for gibberish hours at gibberish percent
    When it is lifted into a state
    Then the state's total units are 0.0
