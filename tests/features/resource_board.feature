Feature: 4-Panel Resource Planning Matrix
  The resource board gives a single-screen view for assigning resources,
  inspecting tasks, and checking capacity.

  Background:
    Given the application is started

  Scenario: The footer has Task Planning and Resource Planning labels with Close on the right
    Then the footer contains the "Task Planning" label
    And the footer contains the "Resource Planning" label
    And the footer contains a "Close" button
    And the "Close" button is to the right of the switch

  Scenario: Resource Planning follows live day and night changes
    When the user switches the application to night mode
    Then the resource task list uses dark colors
    And the resource canvases use dark colors
    When the user switches the application to day mode
    Then the resource task list uses light colors
    And the resource canvases use light colors

  Scenario: The default view is Task Planning
    Then the resource planning switch is off
    And the Task Planning view is on top

  Scenario: Toggle to Resource Planning view
    When the user turns on resource planning
    Then the resource planning switch is on
    And the Resource Planning view is on top

  Scenario: Toggle back to Task Planning view
    When the user turns on resource planning
    Then the Resource Planning view is on top
    When the user turns off resource planning
    Then the resource planning switch is off
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
    Then the inspector shows "Requirements Gathering"

  Scenario: Selecting a task shows its details in the inspector
    Given a resource board with a project that has unassigned and assigned tasks
    When the user selects the "Requirements Gathering" task
    Then the inspector shows "Requirements Gathering"
    And the inspector shows "Effort:"
    And the inspector shows "Priority:"

  Scenario: Resource pool lists every resource and team
    Given a resource board with a project that has resources and a team
    Then the resource pool contains "Jane Smith"
    And the resource pool contains "John Doe"
    And the resource pool contains "Core QA Team"

  Scenario: Resource pool type filter limits the list
    Given a resource board with a project that has resources and a team
    When the user filters the resource pool to "Team"
    Then the resource pool contains only "Core QA Team"

  Scenario: Selecting a long-named resource keeps panels equal and wraps text
    Given a resource board with a long-named resource
    When the user selects the "DevOps Lead Placeholder Number One" resource
    Then the resource board panels remain equal in width
    And long resource text is wrapped

  Scenario: Selecting a resource updates the assignee preview
    Given a resource board with a project that has unassigned and assigned tasks
    When the user selects the "Requirements Gathering" task
    And the user selects the "John Doe" resource
    Then the preview label contains "John Doe"

  Scenario: Assigning a selected resource adds it to the task
    Given a resource board with a project that has unassigned and assigned tasks
    When the user selects the "Requirements Gathering" task
    And the user selects the "John Doe" resource
    And the user assigns the selected resource
    Then the task "Requirements Gathering" has an assignment to "John Doe"
    And the task list shows "Requirements Gathering" with status "Assigned"

  Scenario: De-assigning a task updates its status
    Given a resource board with a project that has an assigned task
    When the user selects the assigned task in the inspector
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
