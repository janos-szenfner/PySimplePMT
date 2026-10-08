Feature: 4-Panel Resource Planning Matrix
  The resource board gives a single-screen view for assigning resources,
  inspecting tasks, and checking capacity.

  Background:
    Given the application is started

  Scenario: The footer has Task Planning, Resource Planning, Deliverables and Dashboard tabs
    Then the footer contains the "Task Planning" tab
    And the footer contains the "Resource Planning" tab
    And the footer contains the "Deliverables" tab
    And the footer contains the "Dashboard" tab
    And the "Deliverables" tab is enabled

  Scenario: The three panels sit in a draggable split kept at the default
    # Issue #126 folded the inspector into the task list - its fields
    # are columns now, its buttons live under the list, and the
    # assignee preview sits under the pool.
    Then the resource board panels are a resizable split
    And the resource board uses compact panel proportions
    When the user drags a panel divider
    Then the default panel split is no longer reasserted

  Scenario: The task list answers the mouse wheel
    Then the task list scrolls vertically with the wheel

  Scenario: Opening the resource board left-aligns the heatmap
    When the resource board is shown
    Then the heatmap is scrolled to its left edge

  Scenario: Resource Planning follows live day and night changes
    When the user switches the application to night mode
    Then the resource task list uses dark colors
    And the resource canvases use dark colors
    When the user switches the application to day mode
    Then the resource task list uses light colors
    And the resource canvases use light colors

  Scenario: The default view is Task Planning
    Then the resource planning switch is off
    And the "Task Planning" tab is active
    And the Task Planning view is on top

  Scenario: Toggle to Resource Planning view
    When the user clicks the "Resource Planning" tab
    Then the "Resource Planning" tab is active
    And the Resource Planning view is on top

  Scenario: Toggle back to Task Planning view
    When the user clicks the "Resource Planning" tab
    Then the Resource Planning view is on top
    When the user clicks the "Task Planning" tab
    Then the "Task Planning" tab is active
    And the Task Planning view is on top

  Scenario: Task list shows all tasks with assignment status
    Given a resource board with a project that has unassigned and assigned tasks
    Then the task list contains "Requirements Gathering" with status "Unassigned"
    And the task list contains "Database Migration" with status "Assigned"

  Scenario: Search filters the task list
    Given a resource board with a project that has two unassigned tasks
    When the user searches the task list for "API"
    Then the task list shows only the task named "API Integration"

  Scenario: Selecting a task does not rebuild the task list
    Given a resource board with a project that has unassigned and assigned tasks
    When the user selects the "Requirements Gathering" task without rebuilding the task list
    Then the task list shows "Requirements Gathering" as the selected row

  Scenario: A task row carries the fields the inspector used to
    # Issue #126: the details sit in the row's own columns now.
    Given a resource board with a project that has unassigned and assigned tasks
    Then the task list row for "Requirements Gathering" carries effort, cost and priority

  Scenario: Resource pool lists every resource and team
    Given a resource board with a project that has resources and a team
    Then the resource pool contains "Jane Smith"
    And the resource pool contains "John Doe"
    And the resource pool contains "Core QA Team"

  Scenario: Resource pool type filter limits the list
    Given a resource board with a project that has resources and a team
    When the user filters the resource pool to "Team"
    Then the resource pool contains only "Core QA Team"

  Scenario: Selecting a long-named resource keeps compact panel proportions and wraps text
    Given a resource board with a long-named resource
    When the user selects the "DevOps Lead Placeholder Number One" resource
    Then the resource board uses compact panel proportions
    And long resource text is wrapped

  Scenario: Selecting a resource updates the assignee preview
    Given a resource board with a project that has unassigned and assigned tasks
    When the user selects the "Requirements Gathering" task
    And the user selects the "John Doe" resource
    Then the preview label contains "John Doe"

  Scenario: An overbooked resource is red in the resource pool
    Given a resource board with an existing overbooked allocation
    Then the resource pool card for "Jane Smith" is red
    And the resource pool card for "Jane Smith" shows "50 / 40 hrs (125%)"

  Scenario: Assigning a selected resource adds it to the task
    Given a resource board with a project that has unassigned and assigned tasks
    When the user selects the "Requirements Gathering" task
    And the user selects the "John Doe" resource
    And the user assigns the selected resource
    Then the task "Requirements Gathering" has an assignment to "John Doe"
    And the task list shows "Requirements Gathering" with status "Assigned"

  Scenario: Assigning a team updates its booking hours
    Given a resource board with a project that has unassigned and assigned tasks
    When the user selects the "Requirements Gathering" task
    And the user selects the "Core QA Team" team
    And the user assigns the selected resource
    Then the task "Requirements Gathering" has an assignment to "Core QA Team"
    And the resource pool card for "Core QA Team" shows "8 / 80 hrs (10%)"

  Scenario: Assigning asks what share of the resource's week the task takes
    Given a resource board with a project that has unassigned and assigned tasks
    When the user selects the "Requirements Gathering" task
    And the user selects the "John Doe" resource
    And the user assigns the selected resource at 30 percent
    Then the assignment on "Requirements Gathering" to "John Doe" is at 30 percent

  Scenario: Cancelling the share question assigns nothing
    Given a resource board with a project that has unassigned and assigned tasks
    When the user selects the "Requirements Gathering" task
    And the user selects the "John Doe" resource
    And the user cancels the assignment share question
    Then the task "Requirements Gathering" has no assignment to "John Doe"

  Scenario: De-assigning a task updates its status
    Given a resource board with a project that has an assigned task
    When the user selects the assigned task in the list
    And the user de-assigns the selected task
    Then the task has no resource assignments
    And the task list shows "Database Migration" with status "Unassigned"

  Scenario: Heatmap spans the complete project timeline
    Given a resource board with a task spanning multiple weeks
    Then the heatmap starts on "Thu 01 Jan"
    And the heatmap ends on "Tue 20 Jan"
    And the heatmap contains 20 day columns

  Scenario: Heatmap shows a row for every resource and team
    Given a resource board with a project that has resources and a team
    Then the heatmap canvas has drawing items
    And the heatmap contains text for "Jane Smith"
    And the heatmap contains text for "Core QA Team"

  Scenario: Heatmap shows existing resource overbooking
    Given a resource board with an existing overbooked allocation
    Then the heatmap cell for "Jane Smith" on "Thu 01 Jan" is over capacity

  Scenario: Heatmap colors reflect capacity load
    Given a resource board with an overloaded resource
    Then the heatmap contains an over-capacity rectangle

  Scenario: Resource pool shows load percentages
    Given a resource board with an overloaded resource
    Then the resource pool card for "Jane Smith" shows a percentage above 100

  Scenario: Indented tasks are on the list without being unfolded
    # Issue #124. Rows used to arrive folded, so everything under a
    # parent was hidden until each expander was clicked - and an
    # assign's refresh folded them again.
    Given a resource board with a project that has an indented task
    Then the indented task is on the task list

  Scenario: A fold the reader made survives a refresh
    # The reader's fold is remembered; everything else stays open.
    Given a resource board with a project that has an indented task
    When the reader folds the indented task's parent
    And the resource board refreshes
    Then the indented task's parent stays folded

  Scenario: The pool's type filter applies to the heat map too
    # Issue #127. The two lists answer the same question - a type the
    # filter drops from the pool leaves the heat map with it.
    Given a resource board with a project that has resources and a team
    When the user filters the resource pool to "Team"
    Then the heatmap contains text for "Core QA Team"
    And the heatmap does not contain text for "Jane Smith"

  Scenario: Cost resources hold a heat-map row like the pool holds a card
    # A cost commits money rather than hours, so its cells stay blank,
    # but the row is there - the lists name the same set.
    Given a resource board with a project that has a cost resource
    When the user filters the resource pool to "Cost"
    Then the heatmap contains text for "Licence Fee"
    And the heatmap does not contain text for "Jane Smith"

  Scenario: Picking a resource repaints the heat map's projected load
    # The overlay answering "what if this task went to this resource"
    # follows the pick rather than the next full refresh (issue #127).
    Given a resource board with a project that has unassigned and assigned tasks
    When heat-map redraws are being counted
    And the user selects the "John Doe" resource
    Then the heatmap was redrawn for the pick
