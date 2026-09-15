Feature: The MSPDI import reads a Microsoft Project file into a plan
  This replaced an import that called a function which did not exist, in
  a library that had nothing to do with Microsoft Project, behind a
  check for whether that library was installed - so it reported "install
  tasklib" and returned nothing whether or not tasklib was there.
  Nothing caught it because nothing tested the reading of an actual
  file.

  So the centre of this feature is a round trip against the exporter:
  write the plan out, read it back, and compare every field that decides
  a date. The rest covers what a file written by Project itself carries
  and this application's own exporter does not - the newer <Exceptions>
  calendar block, a project summary row at outline level 0, and an
  outline that skips a level.

  # -- The round trip ----------------------------------------------------

  Background:
    Given the sample Tosca Implementation plan
    When the plan is exported and imported back through MSPDI

  Scenario: The plan keeps its name
    Then the imported project is named "Tosca Implementation"

  Scenario: Every task survives in order
    Then the imported task names match the plan's, in order

  Scenario: The dates are the dates
    Then every imported task's dates match the plan's

  Scenario: The hierarchy survives
    Then the imported "Business case" and "Tender" sit under "Procurement"
    And the imported "Procurement" sits at the top level

  Scenario: The summary row comes back as a container
    Then the imported "Procurement" is a "Phase"
    And the imported "Business case" is a "Task"

  Scenario: A milestone comes back as a milestone
    Then the imported "Contract signed" is a "Milestone" with no end date

  Scenario: The link keeps its type and its lag
    Then the imported "Tender" waits on "Business case" as an "SS" link lagged 2 days

  Scenario: Progress, notes and priority travel
    Then the imported "Business case" is 50 percent done
    And the imported "Business case" notes read "Signed off by the steering group"
    And the imported "Business case" has priority "High"

  Scenario: The calendar survives
    Then the imported calendar rests Saturday and Sunday
    And the imported calendar lists the holiday on "2026-07-08"

  Scenario: A pin on the task's own start is not read back
    Then every imported task is unconstrained

  Scenario: A real floor does come back
    Given "Tender" is floored to "2026-07-10" by a SNET constraint
    When the plan is exported and imported back through MSPDI
    Then the imported "Tender" carries a "SNET" constraint dated "2026-07-10"

  # -- Per-task calendars ---------------------------------------------------

  Scenario: The named calendar comes back
    Given "Tender" follows a weekend-only calendar named "Weekend window"
    When the plan is exported and imported back through MSPDI
    Then the imported named calendars are "Weekend window"

  Scenario: The task still follows it
    Given "Tender" follows a weekend-only calendar named "Weekend window"
    When the plan is exported and imported back through MSPDI
    Then the imported "Tender" still follows a calendar resting Monday to Friday's other days

  Scenario: A task on the plan calendar names nothing
    Given "Tender" follows a weekend-only calendar named "Weekend window"
    When the plan is exported and imported back through MSPDI
    Then the imported "Business case" names no calendar

  # -- What only Project itself writes ----------------------------------------

  Scenario: The newer Exceptions block is read
    When an MSPDI document is imported whose standard calendar carries a "Company shutdown" exception from "2026-12-24" to "2026-12-26"
    Then the imported calendar lists holidays on "2026-12-24", "2026-12-25" and "2026-12-26"

  Scenario: A project summary row is not imported as work
    When an MSPDI document is imported holding a level-0 task "Tosca Implementation" and a level-1 task "Work"
    Then the imported task names are "Work"

  Scenario: A null task is skipped
    When an MSPDI document is imported holding a null task and a level-1 task "Work"
    Then the imported task names are "Work"

  Scenario: An outline that skips a level still attaches
    When an MSPDI document is imported holding a level-1 summary "Phase" and a level-3 task "Deep"
    Then the imported "Deep" sits under "Phase"

  Scenario: A finish at midnight means the day before
    When an MSPDI document is imported holding a task "Work" finishing at "2026-07-11T00:00:00"
    Then the imported "Work" ends on "2026-07-10"

  Scenario: A file with no calendar keeps the standard week
    When an MSPDI document is imported whose calendar never describes its week
    Then the imported calendar rests Saturday and Sunday

  Scenario: A namespaceless document parses
    When this namespaceless MSPDI document is imported
      """
      <Project><Title>Bare</Title><CalendarUID>1</CalendarUID><Calendars><Calendar><UID>1</UID><Name>Standard</Name><WeekDays><WeekDay><DayType>1</DayType><DayWorking>0</DayWorking></WeekDay><WeekDay><DayType>2</DayType><DayWorking>1</DayWorking></WeekDay><WeekDay><DayType>3</DayType><DayWorking>1</DayWorking></WeekDay><WeekDay><DayType>4</DayType><DayWorking>1</DayWorking></WeekDay><WeekDay><DayType>5</DayType><DayWorking>1</DayWorking></WeekDay><WeekDay><DayType>6</DayType><DayWorking>1</DayWorking></WeekDay><WeekDay><DayType>7</DayType><DayWorking>0</DayWorking></WeekDay></WeekDays></Calendar></Calendars><Tasks><Task><UID>1</UID><Name>Work</Name><OutlineLevel>1</OutlineLevel><Start>2026-07-06T08:00:00</Start><Finish>2026-07-10T17:00:00</Finish></Task></Tasks></Project>
      """
    Then the imported project is named "Bare"
    And the imported task names are "Work"

  Scenario: A link to a task that is not there is dropped
    When an MSPDI document is imported holding a level-1 task "Work" waiting on task "99"
    Then the imported "Work" waits on nothing

  # -- Failures ---------------------------------------------------------------

  Scenario: A missing file returns nothing
    When a nonexistent MSPDI file is imported
    Then nothing comes back

  Scenario: Malformed XML returns nothing
    When a truncated MSPDI document is imported
    Then nothing comes back
