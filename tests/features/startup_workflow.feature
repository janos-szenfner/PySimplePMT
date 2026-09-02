Feature: Software startup and project selection
  The application opens a Welcome screen that lets users start a new project,
  open the built-in sample, or pick from recent project files.

  Background:
    Given the application is started with the welcome dialog

  Scenario: New Empty Project starts a clean project
    When the user selects "new" in the Welcome modal
    Then the project has no tasks
    And the project is clean

  Scenario: Open Sample Project loads demo data
    When the user selects "sample" in the Welcome modal
    Then the project has tasks
    And the project is clean

  Scenario: A recent project can be opened
    Given a project file exists in the recent list
    When the user selects that recent project
    Then the project name is "Recent Project"
    And the project is clean

  Scenario: A missing recent project is removed
    Given a missing project path is in the recent list
    When the user selects the missing recent project
    Then a warning is shown
    And the missing path is removed from the recent list

  Scenario: Saving a project adds it to the recent list
    Given the application has a project named "Planning"
    When the project is saved to "planning.json"
    Then the recent list contains "planning.json"

  Scenario: Welcome modal cancel closes the application
    When the user selects "cancel" in the Welcome modal
    Then the application closes

  Scenario: The recent list keeps the most recent project first
    Given project files "A" and "B" are in the recent list in that order
    And the Welcome modal is open
    Then the first recent project is "B"

  Scenario: Loading a recent project moves it to the top
    Given project files "A" and "B" are in the recent list in that order
    When the user selects the project "B" recent project
    Then the first recent project in the list is "B"

  Scenario: The Welcome modal shows up to 5 recent projects
    Given the recent list contains 7 projects
    And the Welcome modal is open
    Then the Welcome modal displays 5 recent projects

  Scenario: The Welcome modal shows project details for a recent project
    Given a project file exists in the recent list
    And the Welcome modal is open
    Then the first recent project shows the project name, path, and last modified
    And the project name is visually emphasized
    And the path uses muted text
    And the timestamp is right aligned

  Scenario: Recent Projects has a section divider
    Given the Welcome modal is open
    Then the Recent Projects heading has a divider beneath it

  Scenario: A recent project card is clickable
    Given a project file exists in the recent list
    And the Welcome modal is open
    When the first recent project card is clicked
    Then the project name is "Recent Project"

  Scenario: Closing the Welcome modal starts an empty project
    Given the Welcome modal is open
    When the Welcome modal is closed with the window control
    Then the application remains open
    And the project has no tasks
    And the project is clean

  Scenario: Command-line file path loads the project directly
    Given a project file named "Command-Line Project" exists as "cmd.json"
    When the application starts with that file path
    Then the project name is "Command-Line Project"
    And the welcome dialog is not shown
