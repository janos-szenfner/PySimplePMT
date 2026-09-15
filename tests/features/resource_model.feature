Feature: Resource model functionality
  Core functionality for resource management, teams, schedules, and repositories

  @resource_model
  Scenario: Resource round trip preserves enum and mappings
    Given a named resource with team memberships and project assignments
    When serialized to dict and deserialized back as resource
    Then the restored resource should equal the original
    And the resource type should be preserved as NAMED

  @resource_model
  Scenario: Days off ranges round trip with a resource
    Given a resource with days off range for summer vacation
    When serialized to dict and deserialized back with days off
    Then the days off should be preserved
    And the days off reason should be preserved

  @resource_model
  Scenario: Days off range rejects end before start
    When creating a days off range with end before start
    Then a ValueError should be raised for invalid date range

  @resource_model
  Scenario: Resource rejects team type
    When creating a resource with TEAM type
    Then a ValueError should be raised for TEAM type resource

  @resource_model
  Scenario: Resource rejects negative weekly capacity
    When creating a resource with negative weekly capacity
    Then a ValueError should be raised for negative weekly capacity

  @resource_model
  Scenario: Resource rejects negative team membership
    When creating a resource with negative team membership percentage
    Then a ValueError should be raised for negative team membership

  @resource_model
  Scenario: Dynamic team capacity uses member percentages
    Given a team and resources with various membership percentages
    Then the calculated effective capacity should be correct

  @resource_model
  Scenario: Fixed team capacity overrides members
    Given a team with fixed capacity
    Then the calculated effective capacity should be the fixed hours

  @resource_model
  Scenario: Team allocation 60 percent
    Given a resource repository with resources and teams for 60 percent allocation
    When setting team allocation to 60 percent
    Then the resource team memberships should be updated for 60 percent

  @resource_model
  Scenario: Team allocation 200 percent
    Given a resource repository with resources and teams having 200 percent allocation
    When setting team allocation to 200 percent
    Then the resource team memberships should be updated for 200 percent
    And the team effective capacity should be calculated correctly for 200 percent

  @resource_model
  Scenario: Team allocation zero percent detaches
    Given a resource repository with resources and teams having high allocation
    When setting team allocation to zero percent
    Then the resource should be detached from the team

  @resource_model
  Scenario: Team allocation negative value
    Given a resource repository with resources and teams for negative allocation test
    When setting team allocation to negative value
    Then a ValueError should be raised for negative allocation

  @resource_model
  Scenario: Over capacity allocation survives serialization
    Given a resource with over capacity team membership
    When serialized to dict and deserialized back with over capacity
    Then the over capacity allocation should be preserved

  @resource_model
  Scenario: Removing team cleans every resource membership
    Given a resource repository with teams and resources
    When a team is removed
    Then the team should not be in the repository
    And the resource team memberships should be cleaned

  @resource_model
  Scenario: Generic swap preserves identity and allocations
    Given a resource repository with generic and named resources
    When swapping a generic resource with a named resource
    Then the replacement should preserve the original ID
    And the replacement should have the named resource properties
    And the replacement should preserve team memberships
    And the replacement should preserve assigned project IDs
    And the named resource should be added to repository

  @resource_model
  Scenario: Standard full week weekend and continuous defaults
    Then standard schedule should have 8 hours on weekdays and 0 on weekends
    And full week schedule should sum to 40 hours
    And weekend only schedule should have 0 on weekdays and 8 on weekends
    And continuous schedule should have 24 hours every day

  @resource_model
  Scenario: Capacity units recalculate daily weekly and fte
    Given capacity entries with different units
    Then weekly hours capacity should be calculated correctly
    And daily hours capacity should be calculated correctly
    And FTE capacity should be calculated correctly

  @resource_model
  Scenario: Custom daily grid drives weekly capacity and fte
    Given a resource with custom daily capacity
    Then the schedule pattern should be CUSTOM
    And the weekly capacity hours should be calculated correctly
    And the FTE should be calculated correctly

  @resource_model
  Scenario: Daily workload flags only the overbooked day
    Given a resource with workload status
    Then overbooked days should be flagged correctly
    And percentages should be calculated correctly

  @resource_model
  Scenario: Workload by calendar date uses that weekdays capacity
    Given a resource with workload for specific dates
    Then workload status should use the correct weekday capacity
    And overallocated status should be set correctly

  @resource_model
  Scenario: Team daily capacity applies each member split
    Given a team with resources having different schedules and memberships
    Then daily capacity should be calculated correctly per day
    And effective capacity should be calculated correctly for team daily split

  @resource_model
  Scenario: Fixed team uses its own daily schedule
    Given a fixed team with continuous schedule
    Then daily capacity should use the team schedule
    And effective capacity should be calculated correctly for fixed team
    And fixed FTE should be calculated correctly

  @resource_model
  Scenario: Generic placeholder names increment by role for DevOps
    Given a resource repository with generic resources
    Then the next name should be incremented

  @resource_model
  Scenario: Generic placeholder names increment by role for QA
    Given a resource repository with generic resources
    Then the next name should start from 1

  @resource_model
  Scenario: Resource operations are logged
    Given a resource repository
    Then operations should be logged correctly

  @resource_model
  Scenario: Legacy resource gains a standard daily schedule
    Given a legacy resource without schedule pattern
    Then it should default to STANDARD schedule pattern
    And daily capacity hours should be set correctly

  @resource_model
  Scenario: Repository persists and loads resources and teams
    Given a resource repository with resources and teams for persistence test
    Then resources should be preserved
    And teams should be preserved
    And resource types should be preserved

  @resource_model
  Scenario: Repository rejects non object or malformed sections
    Given malformed repository files
    Then a ValueError should be raised for malformed file

  @resource_model
  Scenario: Missing repository file loads an empty pool
    Given a resource repository with missing file
    Then resources should be empty
    And teams should be empty
  @resource_model
  Scenario: Material round trip preserves the sheet's fields
    Given a material resource with label initials group rate accrual and code
    When serialized to dict and deserialized back as material
    Then the restored material should equal the original

  @resource_model
  Scenario: Material rejects a negative standard rate
    When a material with a negative standard rate is built
    Then a ValueError was raised for the material

  @resource_model
  Scenario: Material requires a name
    When a material with an empty name is built
    Then a ValueError was raised for the material

  @resource_model
  Scenario: An unknown accrue at value reads as prorated
    When a material dict with an unknown accrue at value is loaded
    Then the material accrual should be prorated

  @resource_model
  Scenario: Repository persists and loads materials
    Given a resource repository with a material for persistence test
    Then materials should be preserved

  @resource_model
  Scenario: A file without a materials section loads an empty material pool
    When a repository dict without a materials section is loaded
    Then the materials pool should be empty

  @resource_model
  Scenario: A saved project keeps its material pool
    Given a project holding a material resource
    When the project is saved to a dict and read back
    Then the material should still be in its pool

  @resource_model
  Scenario: Material units parse a fixed quantity
    When the material units "20" are parsed
    Then the parsed units should be 20.0 with no period

  @resource_model
  Scenario: Material units parse a daily rate
    When the material units "5/d" are parsed
    Then the parsed units should be 5.0 per "d"

  @resource_model
  Scenario: Material units reject malformed input
    When the malformed material units "soon" are parsed
    Then a ValueError was raised for the units

  @resource_model
  Scenario: A fixed material quantity ignores task duration
    Given a material assignment of "20" on a ten-day task
    Then the consumed quantity should be 20.0

  @resource_model
  Scenario: A daily material rate scales with task duration
    Given a material assignment of "5/d" on a ten-day task
    Then the consumed quantity should be 50.0
    And the assignment cost should be quantity times the standard rate

  @resource_model
  Scenario: Material assignments stay out of the effort engine
    Given a task with a work assignment and a material assignment
    When the effort state is built and written back
    Then the state should hold only the work assignment
    And the material assignment should be untouched

  @resource_model
  Scenario: A task's cost includes its material consumption
    Given a task with a "5/d" material assignment at fifty a unit
    When the task cost is computed
    Then the cost should be 250.0

  @resource_model
  Scenario: A task dict keeps its material assignment
    Given a task carrying a material assignment
    When the task is saved to a dict and read back
    Then the restored assignment should still be a material with its units

  @resource_model
  Scenario: A work resource carries the sheet's cost fields
    Given a named resource with overtime cost per use and accrual
    When the resource is serialized and read back
    Then the overtime rate cost per use and accrual should be preserved

  @resource_model
  Scenario: A resource file without the cost fields takes the defaults
    When a legacy resource dict without cost fields is loaded
    Then the resource should default to no overtime no use fee and prorated

  @resource_model
  Scenario: A resource rejects a negative overtime rate
    When a resource with a negative overtime rate is built
    Then a ValueError was raised for the resource

  @resource_model
  Scenario: Max units is the capacity read as a percentage
    Given a half-time named resource
    Then the max units should be 50.0

  @resource_model
  Scenario: Assignment cost splits overtime and charges the use fee
    Given a resource at fifty an hour seventy-five overtime and twenty-five per use
    And a ten-hour assignment with two overtime hours
    When the task cost is computed for it
    Then the rated cost should be 575.0
