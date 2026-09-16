@dialog_wiring
Feature: The wiring between the task dialogs and the dependency editor

  Building the dialogs needs a display, so these exercise the callback
  methods directly against a stand-in object. That is enough to catch
  the failure they guard against: DependencyEditor calls back into the
  dialog while the dialog is still inside the constructor that assigns
  it, so the attribute holding the editor does not exist yet.

  Scenario: The initial refresh does not notify
    # Notifying during construction reached for an attribute the dialog
    # had not assigned yet, and would also have rescheduled the task
    # simply because its dialog was opened.
    Then the editor's constructor refreshes without notifying

  Scenario: Refresh accepts a notify flag
    Then refresh takes a notify flag defaulting on

  Scenario: Notify guards the callback
    Then refresh only calls back when notifying is asked for

  Scenario: The edit dialog survives a missing editor
    # The exact state that raised "'EditTaskDialog' object has no
    # attribute 'dependency_editor'".
    When a half-built edit dialog hears dependencies changed
    Then nothing was raised

  Scenario: The create dialog survives a missing editor
    When a half-built create dialog hears dependencies changed
    Then nothing was raised

  Scenario: The edit dialog survives a missing date field
    # An editor without the date widgets is also handled.
    When an edit dialog with a bare editor hears dependencies changed
    Then nothing was raised

  Scenario: No links implies nothing
    # With no dependencies the start date is left alone.
    Given a plan with First and Second
    When the required start is asked with no links for 2024-02-01
    Then the required start is empty

  Scenario: End-Start hard pins to the next working day
    # The predecessor finishes Friday 5 January; the date offered is
    # the Monday - the same date the scheduler would settle on.
    Given a plan with First and Second
    When the required start is asked with an FS Hard link for 2024-02-01
    Then the required start is 2024-01-08

  Scenario: Start-Start hard pins to the predecessor's start
    Given a plan with First and Second
    When the required start is asked with an SS Hard link for 2024-02-01
    Then the required start is 2024-01-01

  Scenario: A rubber link leaves a later start
    Given a plan with First and Second
    When the required start is asked with an FS Rubber link for 2024-02-01
    Then the required start is 2024-02-01

  Scenario: Editing returns without waiting
    # Both forms were opened and then waited on with wait_window(),
    # which runs a second event loop until the form closes - entered
    # from inside a native menu's tracking loop, that is a place an
    # application can stop and not come back from.
    Then edit_task's body names no wait_window

  Scenario: Creating returns without waiting
    Then create_task's body names no wait_window

  Scenario: The forms still say what they are for
    # Both still hand their result back through a callback, which is
    # what made the wait unnecessary in the first place.
    Then edit_task's body still names on_save
    And create_task's body still names on_save
