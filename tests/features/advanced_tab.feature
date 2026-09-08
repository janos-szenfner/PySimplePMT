Feature: Task Editor Advanced tab - deadline and constraint
  The Advanced tab carries a target deadline and a scheduling constraint.
  Both are stored on the task and drawn on the Gantt chart; a deadline the
  forecast finish overruns is flagged, and each constraint type has its own
  marker.

  @advanced
  Scenario: A new task is unconstrained with no deadline
    Given a new task
    Then its deadline is not set
    And its constraint type is "NA"
    And its constraint date is not set

  @advanced
  Scenario: The deadline and constraint survive save and load
    Given a task with a deadline and a Must Finish On constraint
    When it is written to a dict and read back
    Then the read-back deadline matches
    And the read-back constraint type is "MFO"
    And the read-back constraint date matches

  @advanced
  Scenario: An older task without the fields opens unconstrained
    Given a task dict written before the Advanced tab existed
    When it is read back
    Then its constraint type is "NA"
    And its deadline is not set

  @advanced
  Scenario: A constraint with no place for a date drops any stray one
    Given a task dict whose constraint is "ASAP" but carries a date
    When it is read back
    Then its constraint date is not set

  @advanced @needs_display
  Scenario: The constraint date is enabled only for a dated constraint
    Given an Advanced tab for a task
    Then the constraint date box is disabled
    When the constraint type is set to "Must Finish On"
    Then the constraint date box is enabled
    When the constraint type is set to "As Soon As Possible"
    Then the constraint date box is disabled

  @advanced @needs_display
  Scenario: A dated constraint with no date is refused on read
    Given an Advanced tab for a task
    When the constraint type is set to "Start No Earlier Than"
    And the constraint date is cleared
    Then reading the tab is refused

  @advanced @needs_display
  Scenario: Reset to N/A clears the deadline
    Given an Advanced tab for a task
    When a deadline is picked
    And the deadline is reset
    Then the tab reports no deadline

  @advanced
  Scenario: A deadline the finish beats is drawn green, on track
    Given a chart task finishing before its deadline
    Then the deadline marker is green
    And the bar is not marked slipped

  @advanced
  Scenario: A deadline the finish overruns is drawn red and dashed
    Given a chart task finishing after its deadline
    Then the deadline marker is red
    And the deadline marker has a dashed guide line
    And the bar is marked slipped

  @advanced
  Scenario: A Must Finish On constraint shows a red lock marker
    Given a chart task with a "MFO" constraint
    Then there is a red lock marker

  @advanced
  Scenario: A Start No Earlier Than constraint shows a blue bracket
    Given a chart task with a "SNET" constraint
    Then there is a blue bracket marker
