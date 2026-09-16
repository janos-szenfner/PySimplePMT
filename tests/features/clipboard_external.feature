Feature: Copy puts a readable table on the desktop clipboard, and
  internal paste never reads it
  Copying selected rows should let other programs (a spreadsheet, a
  note) paste the task rows - at least the names - while copy/cut/paste
  inside the application keep working from the in-memory clipboard, not
  the desktop one.

  Background:
    Given a clipboard service over the sample plan

  Scenario: The first line is the header
    When "001", "002" and "003" are copied
    Then the first clipboard line is the column header

  Scenario: Every task name is present
    When "001", "002" and "003" are copied
    Then the clipboard text names "Design Phase", "UI Mockups" and "Design Review"

  Scenario: Rows are tab separated with the type
    When "001" is copied
    Then the first task row's cells are "Design Phase" and "Task"

  Scenario: A subtask name is indented
    When "001" and "002" are copied
    Then the "UI Mockups" line starts with a space

  Scenario: A milestone shows zero days
    When "003" is copied
    Then the first task row mentions "0 days"

  Scenario: No internal JSON leaks to the clipboard
    When "001", "002" and "003" are copied
    Then the clipboard text carries no internal payload words

  Scenario: The table is what reaches the desktop clipboard
    Given the desktop clipboard is a recorder
    When "001" and "002" are copied
    Then the recorder holds exactly the clipboard text
    And it names "Design Phase"

  Scenario: Paste reads only the in-memory copy
    Given the desktop clipboard holds table text
    Then resolving the payload finds nothing
    And paste is not offered

  Scenario: An internal copy still pastes
    When "001" is copied
    Then pasting at "001" succeeds
