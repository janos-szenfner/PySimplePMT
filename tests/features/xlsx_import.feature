Feature: The XLSX importer reads a spreadsheet into a plan
  A workbook shaped like a hand-built spreadsheet - a title block, then
  the table - imports into tasks, phases, dependencies and progress.
  The importer also takes the application's own export back in.

  # -- The sample sheet -----------------------------------------------------

  Scenario: A header row below a title block is found and read
    When the sample worksheet is imported
    Then the imported project is named "Implementation Plan"
    And the imported task names include "Kick-off", "Analysis" and "Build"

  Scenario: Start and end dates come through unchanged
    When the sample worksheet is imported
    Then the imported task "1" starts on "2024-01-01"
    And the imported task "1" ends on "2024-01-05"
    And the imported task "1" lasts 5 days

  Scenario: A semicolon-separated predecessor cell yields several dependencies
    When the sample worksheet is imported
    Then the imported task "3" waits on "1" and "2"

  Scenario: An en-dash placeholder does not become a dependency
    When the sample worksheet is imported
    Then the imported task "1" waits on nothing

  Scenario: Status text is translated into a progress percentage
    When the sample worksheet is imported
    Then the imported task "1" is 50 percent done
    And the imported task "2" is 0 percent done
    And the imported task "3" is 100 percent done

  Scenario: Each phase becomes a parent task holding its rows as Subtasks
    When the sample worksheet is imported
    Then the root tasks are "Phase One" and "Phase Two"
    And "Phase One" holds "Kick-off" and "Analysis" as subtasks

  Scenario: A phase parent covers the range of the rows inside it
    When the sample worksheet is imported
    Then the imported "Phase One" starts on "2024-01-01" and ends on "2024-01-12"

  Scenario: Grouping can be disabled
    When the sample worksheet is imported without phase grouping
    Then it holds 3 tasks, all at the top level

  # -- Durations and dates ----------------------------------------------------

  Scenario: A working-days duration column skips weekends
    When this worksheet is imported
      | ID | Task            | Duration (wd) | Start      |
      | 1  | Week of work    | 5             | 2024-01-01 |
      | 2  | Spans a weekend | 10            | 2024-01-01 |
    Then the imported task "1" ends on "2024-01-05"
    And the imported task "2" ends on "2024-01-12"

  Scenario: A plain Duration column is treated as calendar days
    When this worksheet is imported
      | ID | Task     | Duration | Start      |
      | 1  | Ten days | 10       | 2024-01-01 |
    Then the imported task "1" ends on "2024-01-10"

  Scenario: Dates stored as day serial numbers are converted
    When this worksheet is imported
      | ID | Task         | Start | End   |
      | 1  | Serial dates | 45292 | 45296 |
    Then the imported task "1" starts on "2024-01-01"
    And the imported task "1" ends on "2024-01-05"

  Scenario: A zero-duration row imports as a milestone
    When this worksheet is imported
      | ID | Task    | Duration | Start      |
      | 1  | Go-Live | 0        | 2024-01-10 |
    Then the imported task "1" is a milestone with no end date

  # -- Dependencies -------------------------------------------------------------

  Scenario: Predecessors given as task names resolve to the right tasks
    When this worksheet is imported
      | Task   | Predecessors | Start      | Duration |
      | First  |              | 2024-01-01 | 3        |
      | Second | First        | 2024-01-04 | 3        |
    Then the imported "Second" waits on the imported "First"

  Scenario: A predecessor with no matching task does not create a dangling edge
    When this worksheet is imported
      | ID | Task      | Pred. | Start      | Duration |
      | 1  | Only task | 99    | 2024-01-01 | 3        |
    Then the imported task "1" waits on nothing

  Scenario: A single name with a comma resolves as a whole before splitting
    When this worksheet is imported
      | Task             | Predecessors      | Start      | Duration |
      | Analysis, phase 2|                   | 2024-01-01 | 3        |
      | Build            | Analysis, phase 2 | 2024-01-04 | 3        |
    Then the imported "Build" waits on the imported "Analysis, phase 2"

  # -- Odd sheets -----------------------------------------------------------------

  Scenario: Notes beneath the table are not read as tasks
    When this worksheet is imported
      | ID | Task                  | Start      | Duration |
      | 1  | Real task             | 2024-01-01 | 3        |
      |    |                       |            |          |
      |    |                       |            |          |
      |    |                       |            |          |
      |    | Legend: blue = planned|            |          |
    Then it holds 1 tasks
    And the imported task "1" is named "Real task"

  Scenario: Accented Hungarian column headers are recognised
    When this worksheet is imported
      | Azonosító | Feladat   | Kezdés     | Befejezés  | Státusz     |
      | 1         | Tesztelés | 2024-01-01 | 2024-01-05 | Folyamatban |
    Then it holds 1 tasks
    And the imported task "1" is named "Tesztelés"
    And the imported task "1" starts on "2024-01-01"
    And the imported task "1" is 50 percent done

  Scenario: A Parent Task column is used instead of synthesising phases
    When this worksheet is imported
      | ID | Name   | Parent Task | Start Date | End Date   |
      | 1  | Parent |             | 2024-01-01 | 2024-01-10 |
      | 2  | Child  | Parent      | 2024-01-01 | 2024-01-05 |
    Then it holds 2 tasks
    And the imported task "2" has parent "1" and type "Subtask"

  Scenario: A workbook whose first sheet has no table still imports
    When a workbook is imported whose cover sheet holds notes and whose "Tasks" sheet holds a table
    Then it holds 1 tasks

  Scenario: Importing a missing file returns nothing
    When a nonexistent XLSX file is imported
    Then nothing comes back

  Scenario: A workbook with no task table returns nothing
    When this worksheet is imported
      | Colour | Meaning |
      | Blue   | Planned |
    Then nothing comes back

  Scenario: Two rows sharing an ID do not produce two tasks with one ID
    When this worksheet is imported
      | ID | Task  | Pred. | Start      | Duration |
      | 1  | Alpha |       | 2024-01-01 | 3        |
      | 1  | Beta  |       | 2024-01-05 | 3        |
      | 2  | Gamma | 1     | 2024-01-09 | 3        |
    Then every imported task id is unique
    And the imported "Gamma" waits on the imported "Alpha"

  Scenario: A duplicated ID column value is logged
    Given the log is being watched
    When this worksheet is imported
      | ID | Task  | Start      | Duration |
      | 1  | Alpha | 2024-01-01 | 3        |
      | 1  | Beta  | 2024-01-05 | 3        |
    Then the log mentions "Duplicate task ID"

  Scenario: A Project column heading is not mistaken for a name label
    When this worksheet is imported on a sheet named "Portfolio"
      | ID | Project | Task     | Start      | Duration |
      | 1  | Apollo  | Kick-off | 2024-01-01 | 5        |
      | 2  | Apollo  | Build    | 2024-01-08 | 5        |
    Then the imported project is named "Portfolio"
    And the imported project is not named "Task"

  Scenario: A real Project Name label is used as the project name
    When this worksheet is imported
      | Project Name: | Real Name  |       |            |
      |               |            |       |            |
      | ID            | Task       | Start | Duration   |
      | 1             | Kick-off   | 2024-01-01 | 3   |
    Then the imported project is named "Real Name"

  Scenario: The convenience function works without constructing the importer
    When the sample worksheet is imported through the convenience function
    Then the imported project is named "Implementation Plan"

  # -- The round trip ------------------------------------------------------------

  Scenario: An exported workbook is recognised by the importer
    Given the sample worksheet has been imported and re-exported
    Then the re-import produced a project

  Scenario: No tasks are gained or lost on the round trip
    Given the sample worksheet has been imported and re-exported
    Then the re-import holds as many tasks as the original

  Scenario: The project name survives via the Summary sheet
    Given the sample worksheet has been imported and re-exported
    Then the re-import is named after the original

  Scenario: Every task keeps its dates, progress and milestone flag
    Given the sample worksheet has been imported and re-exported
    Then every re-imported task matches the original's dates, progress and milestone flag

  Scenario: Dependencies survive being written out as task names
    Given the sample worksheet has been imported and re-exported
    Then every re-imported task waits on the same named tasks

  Scenario: Phase parents come back through the Parent Task column
    Given the sample worksheet has been imported and re-exported
    Then every re-imported task has the same named parent

  Scenario: Re-importing does not wrap the phase parents in new parents
    Given the sample worksheet has been imported and re-exported
    Then the re-import has as many root tasks as the original

  # -- Value coercions --------------------------------------------------------------

  Scenario: Header keys are lowercased, de-accented and stripped of colons
    Then "  Kezdés:  " normalises to "kezdes"
    And "Duration  (wd)" normalises to "duration (wd)"

  Scenario: Predecessor cells split on common separators
    Then "1;2" splits into "1" and "2"
    And "1, 2 , 3" splits into "1", "2" and "3"
    And "–" splits into nothing
    And an empty cell splits into nothing
    And the number 4 splits into "4"

  Scenario: Lag notation is reduced to the task reference
    Then "3FS+2d" splits into "3"
    And "7SS-1" splits into "7"
    And "12FF" splits into "12"

  Scenario: A name containing the letters ss or ff is not truncated
    Then "Start the procurement demand process" splits into itself
    And "Functional risk assessment" splits into itself
    And "Staff handoff" splits into itself

  Scenario: A slash never splits a predecessor cell
    Then "Education / training" splits into itself

  Scenario: Dates parse from datetimes, serials and common strings
    Then the cell "2024-01-01T00:00:00" parses to "2024-01-01"
    And the cell serial "45292" parses to "2024-01-01"
    And the cell "2024-01-01" parses to "2024-01-01"
    And the cell "not a date" parses to nothing
    And an empty cell parses to nothing

  Scenario: A duration counted in working days steps over the weekend
    Then 5 working days from "2024-01-01" end on "2024-01-05"
    And 6 working days from "2024-01-01" end on "2024-01-08"
    And 1 working days from "2024-01-01" end on "2024-01-01"

  Scenario: A duration counted in calendar days runs straight through
    Then 7 calendar days from "2024-01-01" end on "2024-01-07"

  Scenario: A sheet giving an end and a duration gets a working-day start
    Then 5 working days ending "2024-01-05" started on "2024-01-01"
    And 5 calendar days ending "2024-01-05" started on "2024-01-01"

  Scenario: An explicit progress column takes precedence over status
    Then progress 75 with status "Done" reads as 75
    And progress 0.5 reads as 50
    And progress 150 reads as 100

  Scenario: A percentage in the status is read out of it
    Then status "Ongoing - 30%" reads as 30
    And status "In progress (75%)" reads as 75
    And status "50 %" reads as 50
    And status "Ongoing - 0%" reads as 0
    And status "Ongoing - 100%" reads as 100

  Scenario: The wording still answers without a percentage
    Then status "Ongoing" reads as 50
    And status "Done" reads as 100

  Scenario: An unreadable percentage falls back to the wording
    Then status "Ongoing - x%" reads as 50

  Scenario: A progress column still wins
    Then progress 10 with status "Ongoing - 90%" reads as 10

  Scenario: An unrecognised status leaves progress at zero
    Then status "Whatever" reads as 0
    And no row data reads as 0
