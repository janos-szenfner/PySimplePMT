Feature: The GAN importer reads a GanttProject file into a plan
  Fixtures here mirror what GanttProject 3.x actually writes: no XML
  namespace, schedules given as a start attribute plus a working-day
  duration, milestones flagged with meeting="true", sub-tasks nested
  inside their parent, and <depend> elements naming a *successor*. A
  namespaced fixture is kept to cover files written by older versions.

  # -- The working-day calendar ---------------------------------------

  Scenario: Weekend days are parsed from default-week
    Given the sample GAN calendar
    Then the non-working weekdays are 5 and 6

  Scenario: A holiday with no year recurs every year
    Given the sample GAN calendar
    Then "2024-03-15" is not a working day
    And "2030-03-15" is not a working day

  Scenario: A holiday pinned to a year applies only to that year
    Given the sample GAN calendar
    Then "2024-05-01" is not a working day
    And "2025-05-01" is a working day

  Scenario: Saturdays and Sundays do not count as working days
    Given the sample GAN calendar
    Then "2024-01-06" is not a working day
    And "2024-01-07" is not a working day
    And "2024-01-08" is a working day

  Scenario: Advancing by working days steps over the weekend
    Given the sample GAN calendar
    Then 4 working days from "2024-01-01" lands on "2024-01-05"
    And 5 working days from "2024-01-01" lands on "2024-01-08"
    And 0 working days from "2024-01-01" lands on "2024-01-01"

  Scenario: Advancing by working days steps over declared holidays
    Given the sample GAN calendar
    Then 1 working days from "2024-03-14" lands on "2024-03-18"

  Scenario: A duration of N working days covers N days including the start
    Given the sample GAN calendar
    Then the end of 1 working days from "2024-01-01" is "2024-01-01"
    And the end of 5 working days from "2024-01-01" is "2024-01-05"

  Scenario: With no calendars block, weekends still default to non-working
    Given a GAN calendar built from nothing
    Then the non-working weekdays are 5 and 6

  # -- Date parsing -----------------------------------------------------

  Scenario: GanttProject 3.x writes plain dates
    When the date "2024-01-22" is parsed
    Then it parses as "2024-01-22T00:00:00"

  Scenario: An ISO date with milliseconds parses
    When the date "2024-01-01T10:30:45.123Z" is parsed
    Then it parses with year 2024 hour 10 second 45

  Scenario: An ISO date without milliseconds parses
    When the date "2024-01-01T10:30:45Z" is parsed
    Then it parses with year 2024 and minute 30

  Scenario: A missing date parses as nothing
    When no date is parsed
    Then it parses as nothing

  Scenario: An empty date string parses as nothing
    When an empty date string is parsed
    Then it parses as nothing

  Scenario: An invalid date string parses as nothing
    When the date "invalid-date" is parsed
    Then it parses as nothing

  # -- The structure of the sample file ---------------------------------

  Scenario: Nested tasks are imported alongside top-level ones
    When the sample GAN file is imported
    Then the imported project is named "Sample Project"
    And it holds 6 tasks

  Scenario: A task inside a task becomes a Subtask of it
    When the sample GAN file is imported
    Then the imported task "4" has parent "3" and type "Subtask"
    And the top-level tasks are "1", "2" and "3"

  Scenario: Nesting deeper than one level keeps its real parent
    When the sample GAN file is imported
    Then the imported task "5" has parent "4" and type "Subtask"

  Scenario: A depend element names a successor
    When the sample GAN file is imported
    Then the imported task "1" waits on nothing
    And the imported task "2" waits on "1"
    And the imported task "3" waits on "2"

  Scenario: A meeting marks a milestone with no end date
    When the sample GAN file is imported
    Then the imported task "2" is a milestone with no end date
    And the imported task "2" starts on "2024-01-08"

  Scenario: A task with a duration is not a milestone
    When the sample GAN file is imported
    Then the imported task "1" is not a milestone

  Scenario: A parent task is never a milestone
    When this GanttProject file is imported
      """
      <?xml version="1.0" encoding="UTF-8"?>
      <project name="Summary">
          <tasks>
              <task id="1" name="Parent" start="2024-01-01" duration="0">
                  <task id="2" name="Child" start="2024-01-01" duration="3"/>
              </task>
          </tasks>
      </project>
      """
    Then the imported task "1" is not a milestone

  # -- Scheduling --------------------------------------------------------

  Scenario: Durations expand into end dates across the project calendar
    When the sample GAN file is imported
    Then the imported task "1" starts on "2024-01-01"
    And the imported task "1" ends on "2024-01-05"

  Scenario: A duration longer than a week runs past the weekend
    When the sample GAN file is imported
    Then the imported task "3" starts on "2024-01-08"
    And the imported task "3" ends on "2024-01-19"

  Scenario: The calendar can be ignored
    When the sample GAN file is imported ignoring the calendar
    Then the imported task "3" ends on "2024-01-17"

  Scenario: The complete attribute becomes the task's progress
    When the sample GAN file is imported
    Then the imported task "1" is 25 percent done
    And the imported task "6" is 100 percent done
    And the imported task "3" is 0 percent done

  Scenario: The color attribute is used directly
    When the sample GAN file is imported
    Then the imported task "1" is colored "#8cb6ce"
    And the imported task "3" is colored "#000000"

  Scenario: A task with no color falls back to the default
    When the sample GAN file is imported
    Then the imported task "6" is colored "#1f6aa5"

  Scenario: Project start and end are derived from the imported tasks
    When the sample GAN file is imported
    Then the project starts on "2024-01-01"
    And the project ends on "2024-01-19"

  # -- Compatibility and error handling ----------------------------------

  Scenario: Older namespaced files parse through the same path
    When this GanttProject file is imported
      """
      <?xml version="1.0" encoding="UTF-8"?>
      <project name="Namespaced" xmlns="http://ganttproject.sf.net/">
          <tasks>
              <task id="1" name="Task One" start="2024-01-01" duration="3">
                  <depend id="2" type="2" difference="0" hardness="Strong"/>
              </task>
              <task id="2" name="Task Two" start="2024-01-04" duration="2"/>
          </tasks>
      </project>
      """
    Then it holds 2 tasks
    And the imported task "2" waits on "1"

  Scenario: The legacy depends-on form still works
    When this GanttProject file is imported
      """
      <?xml version="1.0" encoding="UTF-8"?>
      <project name="Legacy">
          <tasks>
              <task id="1" name="First" start="2024-01-01" duration="3"/>
              <task id="2" name="Second" start="2024-01-04" duration="2">
                  <depends-on>
                      <dependency idref="1"/>
                  </depends-on>
              </task>
          </tasks>
      </project>
      """
    Then the imported task "2" waits on "1"

  Scenario: An edge naming a task not in the file does not dangle
    When this GanttProject file is imported
      """
      <?xml version="1.0" encoding="UTF-8"?>
      <project name="Dangling">
          <tasks>
              <task id="1" name="Only" start="2024-01-01" duration="3">
                  <depend id="99" type="2" difference="0" hardness="Strong"/>
              </task>
          </tasks>
      </project>
      """
    Then it holds 1 tasks
    And the imported task "1" waits on nothing

  Scenario: A file with no tasks imports as an empty project
    When this GanttProject file is imported
      """
      <?xml version="1.0" encoding="UTF-8"?>
      <project name="Empty Project">
          <tasks></tasks>
      </project>
      """
    Then the imported project is named "Empty Project"
    And it holds 0 tasks

  Scenario: A project with no name attribute gets a placeholder
    When this GanttProject file is imported
      """
      <?xml version="1.0" encoding="UTF-8"?>
      <project>
          <tasks>
              <task id="1" name="Task" start="2024-01-01" duration="1"/>
          </tasks>
      </project>
      """
    Then the imported project is named "Imported Project"

  Scenario: A task with no start date still imports
    When this GanttProject file is imported
      """
      <?xml version="1.0" encoding="UTF-8"?>
      <project name="No Dates">
          <tasks>
              <task id="1" name="Undated" duration="3"/>
          </tasks>
      </project>
      """
    Then it holds 1 tasks
    And the imported task "1" has a start date

  Scenario: Importing a missing file returns nothing
    When a nonexistent GAN file is imported
    Then nothing comes back

  Scenario: Malformed XML returns nothing rather than raising
    When this GanttProject file is imported
      """
      <project><tasks></project>
      """
    Then nothing comes back

  Scenario: The convenience function works without constructing the importer
    When the sample GAN file is imported through the convenience function
    Then it holds 6 tasks

  # -- The colors lookup table -------------------------------------------

  Scenario: An empty colors block yields the defaults
    When colors are parsed from an empty project element
    Then the "default" color is "#1f6aa5"
    And the "milestone" color is "#f39c12"

  Scenario: RGB colour definitions convert to hex
    When colors are parsed from this document
      """
      <?xml version="1.0" encoding="UTF-8"?>
      <project name="Color Project">
          <colors>
              <color id="custom" r="255" g="128" b="0"/>
          </colors>
          <tasks></tasks>
      </project>
      """
    Then the "custom" color is "#ff8000"

  # -- Namespace stripping -------------------------------------------------

  Scenario: Namespaced tags are reduced to their local names
    When namespaces are stripped from this document
      """
      <project xmlns="http://ganttproject.sf.net/"><tasks/></project>
      """
    Then the stripped root is a "project" element holding "tasks"

  Scenario: Documents without namespaces are left alone
    When namespaces are stripped from this document
      """
      <project><tasks/></project>
      """
    Then the stripped root is a "project" element holding "tasks"
