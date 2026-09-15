Feature: The GAN export writes the plan as a GanttProject file
  GanttProject never stores an end date. It stores a start and a
  duration in working days, and replays the calendar in the file to work
  out where a task finishes - so an export can be entirely well-formed,
  open without complaint, and show a plan finishing on the wrong day.
  The dates are what a reader acts on, so most of what is checked here
  is a round trip: export the plan, read it back through the importer
  that replays the calendar, and compare the dates against the plan that
  went in. The rest is the two things the format is easy to get
  backwards - which end of a dependency the <depend> element hangs off,
  and that sub-tasks nest inside their parent rather than naming it.

  Background:
    Given the sample Tosca Implementation plan

  # -- The shape of the document --------------------------------------

  Scenario: The document is a project element carrying the plan's name
    When the plan is exported to GanttProject XML
    Then the root is a "project" element named "Tosca Implementation"

  Scenario: Subtasks nest inside their parent
    When the plan is exported to GanttProject XML
    Then the task "Procurement" nests "Business case" and "Tender"
    And the task "Procurement" carries no parent attribute

  Scenario: A dependency hangs off the predecessor
    When the plan is exported to GanttProject XML
    Then the task "Business case" depends on the exported id of "Tender"
    And that depend reads as a strong Finish-Start
    And the task "Contract signed" carries no depend elements

  Scenario: A milestone is written both ways
    When the plan is exported to GanttProject XML
    Then the task "Contract signed" is a meeting of zero duration

  Scenario: Duration is counted in working days
    When the plan is exported to GanttProject XML
    Then the task "Business case" has a duration of "4"

  Scenario: Progress and notes travel
    When the plan is exported to GanttProject XML
    Then the task "Business case" is "50" percent complete
    And the task "Business case" notes read "Signed off by the steering group"

  Scenario: The working week is declared
    When the plan is exported to GanttProject XML
    Then the default week works Monday and rests Saturday and Sunday

  Scenario: A recurring holiday keeps its empty year
    When the plan is exported to GanttProject XML
    Then one calendar date reads month "12" day "25" with no year

  Scenario: A dated holiday is written with its year
    When the plan is exported to GanttProject XML
    Then one calendar date reads year "2026" month "7" day "8"

  Scenario: Task ids are integers
    When the plan is exported to GanttProject XML
    Then the exported task ids are "1" to "4"

  # -- The round trip ---------------------------------------------------

  Scenario: Every task survives the round trip
    When the plan is exported and imported back
    Then the imported task names match the plan's, in order

  Scenario: The dates are the dates
    When the plan is exported and imported back
    Then every imported task's dates match the plan's

  Scenario: The calendar survives the round trip
    When the plan is exported and imported back
    Then the imported calendar rests Saturday and Sunday
    And the imported calendar lists the holiday on "2026-07-08"
    And the imported calendar recurs on "12-25"

  Scenario: Links come back the right way round
    When the plan is exported and imported back
    Then the imported "Tender" waits on "Business case" Finish-Start

  Scenario: The hierarchy survives the round trip
    When the plan is exported and imported back
    Then the imported "Business case" and "Tender" sit under "Procurement"
    And the imported "Procurement" sits at the top level

  # -- Edge cases -------------------------------------------------------

  Scenario: An empty plan still writes a file
    Given an empty plan named "Nothing yet"
    When the plan is exported to GanttProject XML
    Then the root is a "project" element named "Nothing yet"
    And the tasks element holds no task elements

  Scenario: A link to a missing task is dropped
    Given a plan with a task depending on "nowhere"
    When the plan is exported to GanttProject XML
    Then no depend element is written

  Scenario: A six-day week is written as one
    Given a plan working Saturdays holding a seven-day task
    When the plan is exported to GanttProject XML
    Then the default week works Saturday and rests Sunday
    And the task "Work" has a duration of "6"

  Scenario: A task with no end date lasts a day
    Given a plan with a task that has no end date
    When the plan is exported to GanttProject XML
    Then the task "Work" has a duration of "1"

  Scenario: Export reports failure rather than raising
    When the plan is exported to a path that cannot be written
    Then the export reports failure
