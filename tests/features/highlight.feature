Feature: The View tab's highlight filters
  Issue #51 asks for MS Project's Highlight: a dropdown of standard
  filters, each painting the rows it matches in one yellow. Only one
  filter is on at a time, a second pick of the same one turns it off,
  and a row both critical and matched keeps the critical red.

  The plan used throughout holds one row for each question the filters
  ask: A is underway, B done, C untouched, D a milestone, E a phase,
  F a deadline met, G a deadline missed, H estimated, I inactive. The
  status date is pinned to the plan's own start, because a real today
  drifting past these fixed dates would flag every row late.

  The painting itself is a Treeview and needs a display; that part
  stays in the unittest module.

  # ---- each standard filter picks the rows it says it does ------------------------------------

  Scenario: Incomplete means anything short of done
    Given the nine-row plan
    Then "incomplete" picks "A, C, D, E, F, G, H, I"

  Scenario: Unstarted means no progress at all
    Given the nine-row plan
    Then "unstarted" picks "C, D, E, F, G, H, I"

  Scenario: In progress means some but not all
    Given the nine-row plan
    Then "in_progress" picks "A"

  Scenario: Complete means done
    Given the nine-row plan
    Then "complete" picks "B"

  Scenario: Milestones picks the milestone
    Given the nine-row plan
    Then "milestones" picks "D"

  Scenario: Summary picks the phase
    Given the nine-row plan
    Then "summary" picks "E"

  Scenario: Deadlines means carrying one
    Given the nine-row plan
    Then "deadlines" picks "F, G"

  Scenario: Late means past the deadline
    Given the nine-row plan
    Then "late" picks "G"

  Scenario: Late means past the finish and undone
    # Issue #76: a finish behind the status date is late, 0% or not.
    Given the nine-row plan
    When the status date moves to "2026-01-12"
    Then "late" picks "A, C, D, E, F, G, H, I"

  Scenario: Late leaves the done row alone
    # B finished days ago but is complete, so it cannot be late.
    Given the nine-row plan
    When the status date moves to "2026-01-12"
    Then "late" does not pick "B"

  Scenario: Late reads today when the plan names no status date
    # The plan's 2026 finishes are all behind any real today, so the
    # unfinished rows are late without a status date being set.
    Given the nine-row plan
    When the status date is cleared
    Then "late" picks "A" and not "B"

  Scenario: Summary means a row with children too
    # Issue #68: a Task holding children is a summary, not just a
    # Phase typed as one.
    Given the nine-row plan
    And "Q" sits under "P", a plain task
    Then "summary" picks "E, P"

  Scenario: Estimated picks the estimated row
    Given the nine-row plan
    Then "estimated" picks "H"

  Scenario: Inactive picks the inactive row
    Given the nine-row plan
    Then "inactive" picks "I"

  Scenario: Every filter has a label a reader would say
    Then every built-in highlight filter has a key and a label

  # ---- only one at a time, and the toggle ---------------------------------------------------------

  Scenario: A pick paints its rows
    Given the nine-row plan behind a toolbar shell
    When "complete" is applied
    Then the painted rows are "B"

  Scenario: A second pick replaces not adds
    Given the nine-row plan behind a toolbar shell
    When "complete" is applied
    And "milestones" is applied
    Then the painted rows are "D"

  Scenario: Picking the active one again turns it off
    Given the nine-row plan behind a toolbar shell
    When "complete" is applied
    And "complete" is applied
    Then nothing is painted
    And no highlight is active

  Scenario: Clear takes the paint off
    Given the nine-row plan behind a toolbar shell
    When "milestones" is applied
    And the highlight is cleared
    Then nothing is painted
    And no highlight is active

  Scenario: The gallery ticks the filter that is on
    Given the nine-row plan behind a toolbar shell
    When "milestones" is applied
    Then the gallery labels include "✓ Milestones"
    And the gallery labels include "Incomplete Tasks"

  Scenario: The gallery ends the way MS Project's does
    Given the nine-row plan behind a toolbar shell
    Then the gallery labels include "Clear Highlight"
    And the gallery labels include "New Highlight Filter..."
    And the gallery labels include "More Highlight Filters..."

  # ---- built-ins and customs are distinct sections (issue #78) -------------------------------------

  Scenario: Built-ins open under their own header
    Given the nine-row plan behind a toolbar shell
    Then the gallery opens with a "Built-in" header
    And "Incomplete Tasks" follows it

  Scenario: Customs list under their own header
    Given the nine-row plan behind a toolbar shell
    And a menu filter "Mine" matching "Progress" equals "0"
    Then the gallery labels include "Custom"
    And "Built-in" comes before "Milestones"
    And "Custom" comes before "Mine"

  Scenario: No custom section when none are kept in the menu
    Given the nine-row plan behind a toolbar shell
    Then the gallery labels do not include "Custom"

  # ---- the paint follows the plan (issue #67) -------------------------------------------------------

  Scenario: A row edited out leaves the paint
    Given the nine-row plan behind a toolbar shell
    When "unstarted" is applied
    And "C" is given progress 10
    And the highlight is refreshed
    Then the painted rows do not include "C"

  Scenario: A row edited in joins the paint
    Given the nine-row plan behind a toolbar shell
    When "complete" is applied
    And "A" is given progress 100
    And the highlight is refreshed
    Then the painted rows are "A, B"

  Scenario: The filter stays on across the refresh
    Given the nine-row plan behind a toolbar shell
    When "unstarted" is applied
    And the highlight is refreshed
    Then the active highlight is "unstarted"

  Scenario: A custom highlight refreshes too
    Given the nine-row plan behind a toolbar shell
    And a menu filter "Done" matching "Progress" gte "100"
    When "custom:Done" is applied
    And "A" is given progress 100
    And the highlight is refreshed
    Then the painted rows are "A, B"

  Scenario: Refresh with nothing on does nothing
    Given the nine-row plan behind a toolbar shell
    When the highlight is refreshed
    Then nothing is painted
    And no highlight is active

  # ---- copying filters (issue #79) --------------------------------------------------------------------

  Scenario: Copying a built-in saves its rules under a copy name
    Given the nine-row plan behind a toolbar shell
    When "late" is copied
    Then the copy is named "Late Tasks - Copy"
    And "Late Tasks - Copy" paints what "late" paints

  Scenario: A second copy takes a numbered name
    Given the nine-row plan behind a toolbar shell
    When "incomplete" is copied
    And "incomplete" is copied
    Then the copies are named "Incomplete Tasks - Copy" and "Incomplete Tasks - Copy 1"

  Scenario: Copying a custom filter clones its rules
    Given the nine-row plan behind a toolbar shell
    And a menu filter "Mine" matching "Progress" lt "50"
    When "Mine" is copied
    Then the copy is named "Mine - Copy"
    And "Mine - Copy" holds the rule "Progress" lt "50"

  Scenario: Every built-in's rules paint what it paints
    # The rules table and the selectors may never drift apart.
    Given the nine-row plan
    Then every built-in's rules match its selector

  Scenario: Two filters cannot share a name
    Given the nine-row plan behind a toolbar shell
    And a filter "Mine" matching "Progress" lt "50"
    When a filter is saved as "Mine" matching "Progress" gt "50"
    Then the save is refused
    And the custom filters still number 1

  Scenario: A filter cannot take a built-in's name
    Given the nine-row plan behind a toolbar shell
    When a filter is saved as "Late Tasks" matching "Progress" lt "50"
    Then the save is refused
    And there are no custom filters

  Scenario: Keeping its own name on edit is not a collision
    Given the nine-row plan behind a toolbar shell
    And a filter "Mine" matching "Progress" lt "50"
    When "Mine" is re-saved matching "Progress" gt "50"
    Then the save is allowed
    And "Mine" now matches "Progress" gt "50"

  # ---- the calendar and resource filters (issue #98) -----------------------------------------------------

  Scenario: Own calendar picks the row carrying one
    Given the nine-row plan
    And a "Six-Day Week" calendar exists
    And "A" follows the "sixday" calendar
    Then "own_calendar" picks "A"

  Scenario: A named calendar nobody uses paints nothing
    Given the nine-row plan
    And a "Six-Day Week" calendar exists
    Then "own_calendar" picks nothing

  Scenario: An override naming nothing is no calendar
    # A dangling calendar id resolves to the default, so it is not "a
    # calendar other than the default" - it is a broken pointer.
    Given the nine-row plan
    And "A" follows the "gone" calendar
    Then "own_calendar" does not pick "A"

  Scenario: No resources picks every row carrying none
    Given the nine-row plan
    Then "unassigned" picks "A, B, C, D, E, F, G, H, I"

  Scenario: No resources leaves the resourced row alone
    Given the nine-row plan
    And "A" is assigned the resource "r1"
    Then "unassigned" does not pick "A"
    And "unassigned" picks "C" at least

  Scenario: A stale assignment still reads as no resource
    Given the nine-row plan
    And "A" is assigned the resource "missing"
    Then "unassigned" picks "A" at least

  # ---- the new filter fields (issue #77) ---------------------------------------------------------------
  # Type offers the whole vocabulary, Phase included.

  Scenario: Type offers Phase even when the plan has none
    # The vocabulary is closed, not drawn from what happens to be there.
    Given the nine-row plan
    When "E" is removed
    Then the "Type" choices offer "Phase"
    And the "Type" choices offer "Task"
    And the "Type" choices offer "Milestone"
    And the "Type" choices do not offer "Subtask"

  Scenario: A phase rule matches the phase row
    Given the nine-row plan
    Then a "Type" equals "Phase" rule picks "E"

  Scenario: Summary and deadline and late are filterable fields
    Given the nine-row plan
    When the status date moves to "2026-01-12"
    Then a "Deadline" is_not_empty rule picks "F, G"
    And a "Summary" equals "Yes" rule picks "E"
    And a "Late" equals "Yes" rule picks "A" at least
