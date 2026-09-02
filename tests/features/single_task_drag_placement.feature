Feature: Precise single-task drag placement
  A task can be dropped on any visible insertion line, including a line that
  crosses a hierarchy boundary, and the indicated above or below edge is used.

  Background:
    Given the issue 7 project hierarchy
    And the task list is open for drag placement

  Scenario: Drop Implementation above UI Mockups
    When Implementation is dropped above UI Mockups
    Then Implementation is the first child of Design Phase
    And Implementation appears immediately before UI Mockups

  Scenario: Drop Implementation below the expanded Design Phase
    When Implementation is dropped below Design Phase
    Then Implementation is the first child of Design Phase
    And Implementation appears immediately before UI Mockups

  Scenario: Drop Implementation below UI Mockups
    When Implementation is dropped below UI Mockups
    Then Implementation is a child of Design Phase
    And Implementation appears immediately after UI Mockups

  Scenario: Above and below edges produce different sibling positions
    When Implementation is dropped above Testing
    Then Implementation appears immediately before Testing
    When Implementation is dropped below Testing
    Then Implementation appears immediately after Testing

  Scenario: A line drop cannot create a hierarchy cycle
    When Project is dropped above UI Mockups
    Then the line drop is rejected
    And Project remains a root task

  Scenario: A successful line drop is logged
    When Implementation is dropped above UI Mockups
    Then the drag placement log names Implementation, UI Mockups, and above

  Scenario: A cross-parent insertion line is offered during drag
    Given Implementation is being dragged over the upper edge of UI Mockups
    Then UI Mockups is accepted as the line drop target
    And the upper insertion edge is remembered

  Scenario: Releasing on the lower edge uses the lower drop line
    Given Implementation is being dragged over the lower edge of Testing
    When the mouse button is released
    Then Implementation appears immediately after Testing

  Scenario: Releasing on the upper edge uses the upper drop line
    Given Implementation is being dragged over the upper edge of Testing
    When the mouse button is released
    Then Implementation appears immediately before Testing
