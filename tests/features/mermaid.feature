Feature: Mermaid Gantt charts import and export
  The importer reads Mermaid's gantt syntax - sections, "after" links,
  milestones and durations counted in working days - and the exporter
  writes a plain chart plus a %% comment line carrying what Mermaid
  cannot draw.

  # -- Parsing ---------------------------------------------------------

  Scenario: A basic chart parses into dated tasks
    When this Mermaid chart is imported
      """
      gantt
          title Test Project
          dateFormat  YYYY-MM-DD
          Task 1 :a1, 2024-01-01, 5d
          Task 2 :a2, 2024-01-06, 3d
      """
    Then the imported project is named "Test Project"
    And it holds 2 tasks
    And the imported task "a1" is named "Task 1"
    And the imported task "a1" starts on "2024-01-01" and ends on "2024-01-05"
    And the imported task "a1" lasts 5 days
    And the imported task "a2" is named "Task 2"
    And the imported task "a2" starts on "2024-01-06" and ends on "2024-01-10"
    And the imported task "a2" lasts 3 days

  Scenario: Milestone rows parse as milestones
    When this Mermaid chart is imported
      """
      gantt
          title Project with Milestone
          milestone Milestone 1 :m1, 2024-01-10
          milestone Milestone 2 :m2, 2024-01-20
      """
    Then it holds 2 tasks
    And both are milestones with no end date

  Scenario: "after" rows become dependencies
    When this Mermaid chart is imported
      """
      gantt
          title Project with Dependencies
          Task 1 :a1, 2024-01-01, 5d
          Task 2 :a2, after a1, 3d
          Task 3 :a3, after a2, 2d
      """
    Then it holds 3 tasks
    And the imported task "a2" waits on "a1"
    And the imported task "a3" waits on "a2"
    And the imported task "a1" starts on "2024-01-01" and ends on "2024-01-05"
    And the imported task "a2" starts on "2024-01-08" and ends on "2024-01-10"
    And the imported task "a3" starts on "2024-01-11" and ends on "2024-01-12"

  Scenario: A milestone sits inside the dependency chain
    When this Mermaid chart is imported
      """
      gantt
          title Project with Milestone Dependencies
          Task 1 :a1, 2024-01-01, 5d
          milestone Design Review :m1, after a1
          Implementation :a2, after m1, 10d
      """
    Then it holds 3 tasks
    And the imported task "m1" waits on "a1"
    And the imported task "a2" waits on "m1"
    And the imported task "m1" is a milestone and "a2" is not
    And the imported task "a1" starts on "2024-01-01" and ends on "2024-01-05"
    And the imported task "m1" starts on "2024-01-08"
    And the imported task "a2" starts on "2024-01-08" and ends on "2024-01-19"
    And the imported task "a2" lasts 10 days

  Scenario: Importing a missing file returns nothing
    When a nonexistent Mermaid file is imported
    Then nothing comes back

  Scenario: Date formats parse and invalid ones do not
    Then "2024-01-15" parses as "2024-01-15"
    And "invalid" parses as nothing

  Scenario: Durations count working days inclusively
    Then "5d" from "2024-01-01" ends on "2024-01-05"
    And "2w" from "2024-01-01" ends on "2024-01-12"
    And "1m" from "2024-01-01" ends on "2024-01-26"
    And "0d" from "2024-01-01" ends on "2024-01-01"

  Scenario: A duration pauses over the weekend
    Then "5d" from "2024-01-04" ends on "2024-01-10"

  Scenario: A weekend start begins on the Monday
    Then "1d" from "2024-01-06" ends on "2024-01-08"

  # -- Sections --------------------------------------------------------

  Scenario: Each section becomes a parent task holding its tasks as Subtasks
    When the sectioned Mermaid chart is imported
    Then it holds 5 tasks
    And the root tasks are "Phase One" and "Phase Two"
    And "Phase One" holds "Task 1" and "Task 2" as subtasks

  Scenario: A section parent covers the full range of the tasks inside it
    When the sectioned Mermaid chart is imported
    Then the imported "Phase One" starts on "2024-01-01" and ends on "2024-01-10"

  Scenario: Section parents are ordered ahead of the tasks they contain
    When the sectioned Mermaid chart is imported
    Then the task order is "Phase One", "Task 1", "Task 2", "Phase Two" and "Task 3"

  Scenario: Two section blocks sharing a name are not merged
    When this Mermaid chart is imported
      """
      gantt
          title Repeated
          section Work
          Task 1 :a1, 2024-01-01, 3d
          section Work
          Task 2 :a2, 2024-01-08, 3d
      """
    Then the root tasks are "Work" and "Work" with distinct ids
    And the first "Work" holds "Task 1" and the second holds "Task 2"

  Scenario: Grouping can be disabled
    When the sectioned Mermaid chart is imported without section grouping
    Then it holds 3 tasks, all at the top level

  Scenario: Tasks defined before any section are not given a parent
    When this Mermaid chart is imported
      """
      gantt
          title Mixed
          Loose Task :a0, 2024-01-01, 2d
          section Phase One
          Task 1 :a1, 2024-01-05, 5d
      """
    Then the imported task "a0" sits at the top level
    And the imported task "a0" is a "Task"

  Scenario: A section parent never reuses an existing task ID
    When this Mermaid chart is imported
      """
      gantt
          section Phase One
          Task 1 :section_phase_one, 2024-01-01, 5d
      """
    Then every imported task id is unique

  # -- Frontmatter and directives ---------------------------------------

  Scenario: Config frontmatter is stripped and never parsed as tasks
    When this Mermaid chart is imported
      """
      ---
      config:
        theme: forest
      ---
      gantt
          title Themed Project
          dateFormat YYYY-MM-DD
          Task 1 :a1, 2024-01-01, 5d
      """
    Then the imported project is named "Themed Project"
    And it holds 1 tasks
    And the imported task "a1" is named "Task 1"

  Scenario: Chart directives are skipped rather than parsed as tasks
    When this Mermaid chart is imported
      """
      gantt
          title Directives
          dateFormat YYYY-MM-DD
          axisFormat %Y. %m.
          excludes weekends
          todayMarker off
          Task 1 :a1, 2024-01-01, 5d
      """
    Then it holds 1 tasks
    And the imported task "a1" is named "Task 1"

  # -- Exporting ----------------------------------------------------------

  Scenario: A basic project exports the gantt skeleton
    Given a plan named "Test Project" with tasks from "2024-01-01"
    When the plan is exported to Mermaid text
    Then the content opens with "gantt"
    And the content names "Test Project"
    And the content carries "dateFormat"
    And the content carries both "Task 1" and "Task 2"
    And the content carries "2024-01-01"

  Scenario: A milestone exports as a milestone row
    Given a plan named "Project with Milestone" holding a milestone on "2024-01-10"
    When the plan is exported to Mermaid text
    Then the content carries "milestone Milestone 1"
    And the content carries "2024-01-10"

  Scenario: A Finish-Start chain is written as after
    Given a plan named "Project with Deps" with linked tasks from "2024-01-01"
    When the plan is exported to Mermaid text
    Then the content carries "after"

  Scenario: A link that after cannot express is written as a date
    Given a plan named "Overlapping" holding a start-start linked task
    When the plan is exported to Mermaid text
    Then the row for "Second" is written without "after"
    And the row for "Second" carries the task's own start date

  Scenario: Exporting writes a real file
    Given a plan named "Test Export" holding one task
    When the plan is exported to a Mermaid file
    Then the file exists and opens with "gantt"

  Scenario: A path in a missing directory is created
    Given a plan named "Test" holding one task
    When the plan is exported to a Mermaid file in a missing subdirectory
    Then the file exists

  # -- Round trips ----------------------------------------------------------

  Scenario: A project exports and imports back
    Given a plan named "Roundtrip Test" with tasks from "2024-01-01"
    When the plan is exported and imported back through Mermaid
    Then the imported project is named "Roundtrip Test"
    And it holds as many tasks as went out
    And every task name survived

  Scenario: An estimated row comes back an estimated row
    Given a plan holding an "Estimated row" and an "Active row"
    When the plan is exported and imported back through Mermaid
    Then the imported "Estimated row" has status "Estimated"
    And the imported "Active row" has status "Active"

  Scenario: Section grouping survives an export and re-import
    Given the sectioned Mermaid chart as a plan
    When the plan is exported and imported back through Mermaid
    Then the exported text names "section Phase One" and "section Phase Two"
    And it holds as many tasks as went out
    And the root tasks are "Phase One" and "Phase Two"
    And the subtask names match what went out

  Scenario: Task dates are unchanged by an export and re-import
    Given the chained Mermaid chart as a plan
    When the plan is exported and imported back through Mermaid
    Then every task's dates match what went out

  Scenario: Two parents sharing a name survive an export and re-import
    Given the duplicate-named chart as a plan
    When the plan is exported to Mermaid text and imported back
    Then the exported text carries "section Work" twice
    And the re-import has 2 root tasks

  Scenario: Both exporter entry points produce the same content
    Given the agreement chart as a plan
    Then the class exporter and the function exporter agree

  Scenario: Dependencies survive the round trip
    Given a plan named "Dependencies Test" with linked tasks from "2024-01-01"
    When the plan is exported and imported back through Mermaid
    Then it holds 2 tasks
    And the imported "Task 1" and "Task 2" are both there

  # -- A faithful round trip ---------------------------------------------------
  # Mermaid has one grouping level where a plan has four, two states of
  # progress where it has a percentage, and one kind of link where it has
  # four - so a plan came back flattened, untyped, at nought per cent and,
  # worst of all, on dates it never held. What Mermaid cannot say now
  # travels in a %% comment line that every renderer ignores.

  Scenario: The whole plan survives field by field
    Given the full-fidelity plan
    When the plan is exported and imported back through Mermaid, then rescheduled
    Then every task's full snapshot matches what went out

  Scenario: The levels survive
    Given the full-fidelity plan
    When the plan is exported and imported back through Mermaid, then rescheduled
    Then "P1" is a "Phase", "D1" a "Task" under it, and "T1" a "Subtask" under "D1"

  Scenario: The exact percentage survives
    Given the full-fidelity plan
    When the plan is exported and imported back through Mermaid, then rescheduled
    Then the reimported "T1" is 30 percent done
    And the reimported "T3" is 100 percent done

  Scenario: The link kinds survive, lag included
    Given the full-fidelity plan
    When the plan is exported and imported back through Mermaid, then rescheduled
    Then the imported "T3" link is "SS" lagged 2 days

  Scenario: A start-start link keeps its date
    Given the full-fidelity plan
    When the plan is exported and imported back through Mermaid, then rescheduled
    Then the imported "T3" starts where it started

  Scenario: The chart itself is still a chart
    Given the full-fidelity plan
    When the plan is exported to Mermaid text
    Then the first line is "gantt"
    And a "%%" comment line is present
    And a "section " line is present
    And the line "Business case :active, T1, 2026-08-17, 5d" is present

  Scenario: A chart from anywhere else still imports
    When this Mermaid chart is imported
      """
      gantt
          title A Gantt Diagram
          dateFormat YYYY-MM-DD
          section Section
          A task           :done, a1, 2014-01-01, 30d
          Another task     :active, after a1, 20d
          Future task      :         des3, after a1, 5d
          milestone Review :milestone, m1, after des3
      """
    Then the imported "A task" is 100 percent done
    And the imported "Another task" is 50 percent done
    And the imported "Another task" waits on "a1"
    And the imported "Review" is a milestone

  Scenario: An unreadable metadata line is stepped over
    When this Mermaid chart is imported
      """
      gantt
          title Damaged
          dateFormat YYYY-MM-DD
          %% pysimplepmt:{not json at all
          Task one :t1, 2024-01-01, 5d
      """
    Then the imported project is not nothing
    And the imported task names are "Task one"
