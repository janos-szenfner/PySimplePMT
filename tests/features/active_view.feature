@active_view
Feature: The menu and the keyboard follow the view on top (issue #116)

  Commands and shortcuts answer the view the user is looking at - the
  task grid on Task Planning, the board on Resource Planning, the
  deliverables grid on Deliverables - rather than the hidden task list
  underneath them all. A command that means nothing to the view on top
  is greyed on the ribbon and says so on the status bar when a key press
  reaches it anyway, and switching views hands the keyboard to the view
  that arrived so the arrow keys work without a click first.

  The scenarios build the full application, so they need a display and
  skip without one.

  Background:
    Given the application is started
    And a project with a populated resource pool and tasks

  Scenario: The keyboard goes to the view that comes to the top
    When the "Deliverables" tab is selected
    Then the deliverables grid holds the keyboard focus

  Scenario: The keyboard comes back to the task grid
    # The exact round trip the issue reports: arrows worked on the
    # plan, stopped on return from another tab.
    When the "Deliverables" tab is selected
    And the "Task Planning" tab is selected
    Then the task grid holds the keyboard focus

  Scenario: The resource board's own list takes the keyboard
    When the "Resource Planning" tab is selected
    Then the resource board's list holds the keyboard focus

  Scenario: The usage grid's list takes the keyboard
    When the "Resource Planning" tab is selected
    And the Usage Grid toggle is pressed
    And the "Task Planning" tab is selected
    And the "Resource Planning" tab is selected
    Then the usage grid's list holds the keyboard focus

  Scenario: Copy on the resource board does not reach the task list
    Given the task "Build API" is picked in the task list
    When the "Resource Planning" tab is selected
    And the Copy shortcut runs
    Then nothing is on the plan's clipboard

  Scenario: Delete on the resource board deletes nothing
    Given the task "Build API" is picked in the task list
    When the "Resource Planning" tab is selected
    And the Delete command runs
    Then the plan still has 2 tasks

  Scenario: Delete on the deliverables board removes the deliverable
    Given a deliverable called "API shipped"
    When the "Deliverables" tab is selected
    And the deliverable "API shipped" is picked on the board
    And the Delete command runs
    Then there is no deliverable called "API shipped"

  Scenario: A task command aimed at the board says where it belongs
    When the "Resource Planning" tab is selected
    And the New Task command runs
    Then the plan still has 2 tasks
    And the status bar mentions "belongs to the Task Planning view"

  Scenario: The task buttons grey out off the task view
    # The dashboard's own button stays live - it is a view of its own
    # now, reachable from whichever view is on top (issue #122).
    When the "Resource Planning" tab is selected
    Then ribbon buttons "task,link,unlink,gantt,grid,critical_path,critical_path_report,highlight,grid_filter,grid_filter_clear" are disabled
    And ribbon buttons "paste,cut,copy,edit,delete,indent,outdent" are disabled
    And ribbon buttons "dashboard" are enabled

  Scenario: The task buttons come back with the task view
    When the "Resource Planning" tab is selected
    And the "Task Planning" tab is selected
    Then ribbon buttons "task,link,unlink,gantt,dashboard,grid,edit,delete" are enabled

  Scenario: On Deliverables the shared buttons stay live
    When the "Deliverables" tab is selected
    Then ribbon buttons "paste,cut,copy,edit,delete,indent,outdent" are enabled
    And ribbon buttons "task,link,unlink,gantt,grid" are disabled
    And ribbon buttons "dashboard" are enabled

  Scenario: The dashboard is a footer view of its own
    # Issue #122: a fourth tab beside the other three, not a picture
    # standing in for the chart.
    When the "Dashboard" tab is selected
    Then the "Dashboard" view is on top
    And the dashboard canvas holds the keyboard focus

  Scenario: The dashboard answers from any view
    When the "Deliverables" tab is selected
    And the Dashboard command runs
    Then the "Dashboard" view is on top

  Scenario: The list commands grey out on the dashboard
    # It only reads the plan: there is no list to copy, edit or delete
    # while it is on top (issue #122).
    When the "Dashboard" tab is selected
    Then ribbon buttons "paste,cut,copy,edit,delete,indent,outdent" are disabled
    And ribbon buttons "task,link,unlink,gantt,grid" are disabled
