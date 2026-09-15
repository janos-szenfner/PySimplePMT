Feature: The XLSX export writes a live project plan sheet
  The export used to be three sheets of raw fields, which was a faithful
  record of the model and no use to anybody who wanted to look at the
  plan. What it writes now is a project plan sheet - a title, an
  editable start date, one row per piece of work grouped by phase, and a
  week-by-week chart drawn in the cells beside it - and the things worth
  pinning down are the ones a reader would notice: where the table
  starts, what the columns are, and whether the formulas in it agree
  with the plan they came from.

  The sheet is live: Start and End are WORKDAY formulas over an editable
  duration. A formula that disagreed with the dates this application
  worked out would open in Excel showing a plan nobody scheduled, so
  several of these scenarios are about exactly that - the formula is
  written where it reproduces the answer and the date itself is written
  where it would not.

  # -- The shape of the sheet --------------------------------------------

  Scenario: The sheet is named after the project
    Given the Tosca plan
    When the plan is exported to a workbook
    Then the plan sheet is titled "Tosca Implementation"

  Scenario: The title names the plan
    Given the Tosca plan
    When the plan is exported to a workbook
    Then cell "A1" names "Tosca Implementation"

  Scenario: The start date is one editable cell
    Given the Tosca plan
    When the plan is exported to a workbook
    Then cell "A3" reads "Project Start Date:"
    And cell "C3" reads "=DATE(2026,7,6)"

  Scenario: The headings are the plan columns
    Given the Tosca plan
    When the plan is exported to a workbook
    Then row 5 carries the ten plan headings

  Scenario: The header stays put when the plan scrolls
    Given the Tosca plan
    When the plan is exported to a workbook
    Then the freeze pane is "A6"

  Scenario: The totals are on their own sheet
    Given the Tosca plan
    When the plan is exported to a workbook
    Then a "Summary" sheet names the project "Tosca Implementation"

  # -- Which tasks get rows --------------------------------------------------

  Scenario: The work gets the rows
    Given the Tosca plan
    When the plan is exported to a workbook
    Then the task column lists "Business case", "Procurement demand" and "URS"

  Scenario: A phase is a column not a row
    Given the Tosca plan
    When the plan is exported to a workbook
    Then the task column does not list "1. Procurement"
    And the row for "Business case" carries phase "1. Procurement"

  Scenario: The key deliverable column says what a row produces
    Given the Tosca plan
    When the plan is exported to a workbook
    Then the row for "Business case" carries key deliverable "Signed contract"

  Scenario: Each phase gets its own banding
    Given the Tosca plan
    When the plan is exported to a workbook
    Then the phase cells for "Business case" and "URS" differ in colour

  Scenario: An empty phase still gets a row
    Given a plan holding only a phase named "Discovery"
    When the plan is exported to a workbook
    Then the first task row reads "Discovery"

  # -- The sheet is live -----------------------------------------------------

  Scenario: The first task hangs off the start date
    Given the Tosca plan
    When the plan is exported to a workbook
    Then the row for "Business case" starts with "=$C$3"

  Scenario: A following task chains onto its predecessor
    Given the Tosca plan
    When the plan is exported to a workbook
    Then the row for "Procurement demand" starts the working day after "Business case" finishes

  Scenario: The finish is the duration walked over the calendar
    Given the Tosca plan
    When the plan is exported to a workbook
    Then the row for "Procurement demand" finishes by a plain WORKDAY

  Scenario: The duration is the working days the task holds
    Given the Tosca plan
    When the plan is exported to a workbook
    Then the row for "Business case" holds the task's working duration

  Scenario: The timeline is drawn from the dates
    Given the Tosca plan
    When the plan is exported to a workbook
    Then the row for "Business case" draws its week K bar by overlap

  Scenario: The weeks run from the start date
    Given the Tosca plan
    When the plan is exported to a workbook
    Then cell "K5" reads "=$C$3" and cell "L5" reads "=K5+7"

  # -- Formulas never disagree with the plan ----------------------------------

  Scenario: A start-start link is written as a date
    Given the Tosca plan with "URS" following "Procurement demand" start-to-start
    When the plan is exported to a workbook
    Then the row for "URS" starts with the task's own start date
    And the row for "URS" reads its predecessor as "T2" with an "SS" suffix

  Scenario: A lagged link is written as a date
    Given the Tosca plan with "Procurement demand" lagged 3 days behind "Business case"
    When the plan is exported to a workbook
    Then the row for "Procurement demand" starts with the task's own start date
    And the row for "Procurement demand" reads its predecessor as "T1" with an "FS+3" suffix

  Scenario: An unlinked task that starts later keeps its date
    Given a plan with tasks starting "2026-07-06" and "2026-08-03"
    When the plan is exported to a workbook
    Then the first row starts with "=$C$3"
    And the second row starts with the date "2026-08-03"

  Scenario: No predecessor reads as a dash
    Given the Tosca plan
    When the plan is exported to a workbook
    Then the row for "Business case" reads its predecessor as "–"

  # -- Milestones and status ---------------------------------------------------

  Scenario: A milestone takes no time
    Given the Tosca plan with a milestone "Go-Live" on "2026-08-03"
    When the plan is exported to a workbook
    Then the row for "Go-Live" has a zero duration
    And the row for "Go-Live" finishes on its own start

  Scenario: Progress becomes a status word
    Given the Tosca plan
    When the plan is exported to a workbook
    Then the row for "Business case" reads status "Ongoing - 50%"
    And the row for "Procurement demand" reads status "Not started"
    And the row for "URS" reads status "Done"

  Scenario: The status colour follows the state not the number
    Given the Tosca plan
    When the plan is exported to a workbook
    Then the status cell for "Business case" is filled with the ongoing colour

  # -- Holidays reach the formulas ----------------------------------------------

  Scenario: No holiday sheet when the calendar has none
    Given the Tosca plan
    When the plan is exported to a workbook
    Then there is no "Holidays" sheet
    And the row for "Procurement demand" finishes by a plain WORKDAY

  Scenario: A calendar with holidays writes them out
    Given the Tosca plan with Hungarian holidays
    When the plan is exported to a workbook
    Then a hidden "Holidays" sheet exists
    And the row for "Procurement demand" finishes by a WORKDAY over the holiday sheet

  Scenario: A manual shutdown reaches the holiday sheet
    Given the Tosca plan with a manual shutdown on its second working day
    When the plan is exported to a workbook
    Then the "Holidays" sheet lists the shutdown date

  Scenario: A task over a worked Saturday is written as a date
    Given a plan working "2026-09-12" as a make-up day
    When the plan is exported to a workbook
    Then the task ends on "2026-09-12" and its row's finish is the date itself

  Scenario: A shutdown still recalculates through the holiday sheet
    Given a plan resting "2026-09-15" for a company shutdown
    When the plan is exported to a workbook
    Then the "Holidays" sheet exists
    And the first row finishes by a WORKDAY over the holiday sheet

  # -- The other entry point -----------------------------------------------------

  Scenario: The bytes entry point returns a workbook
    Given a plan holding one task named "Work"
    When the plan is exported to workbook bytes
    Then the bytes open as a sheet whose first task row reads "Work"
