Feature: Unified tabbed settings window
  Users can reach all existing settings editors from one modern settings hub.

  Background:
    Given a project with resources and calendars
    And the unified Settings window is open

  Scenario: The Settings window presents four categories
    Then the Settings tabs are "Project, Resource, Gantt, Calendar"

  Scenario: Project tab shows the current project summary
    When the Project tab is selected
    Then the Project tab shows the project name, scheduling direction, and priority

  Scenario: Resource tab shows repository counts
    When the Resource tab is selected
    Then the Resource tab shows resource and team counts

  Scenario: Gantt tab describes chart appearance settings
    When the Gantt tab is selected
    Then the Gantt tab offers the existing Gantt settings editor

  Scenario: Calendar tab shows calendar counts
    When the Calendar tab is selected
    Then the Calendar tab shows working days, holiday countries, and named calendars

  Scenario Outline: Each tab opens its existing full editor
    When the "<tab>" tab editor button is invoked
    Then the "<tab>" settings editor callback is called
    And the unified Settings window closes

    Examples:
      | tab      |
      | Project  |
      | Resource |
      | Gantt    |
      | Calendar |

  Scenario: Escape or Close leaves settings unchanged
    When the unified Settings window is closed
    Then the project settings remain unchanged

  Scenario: Opening Settings twice reuses the existing window
    Given the Settings hub was opened from the toolbar
    When Settings is opened again on the Calendar tab
    Then only one unified Settings window exists
    And the Calendar tab is selected
