Feature: The About > Changelog window
  The parsing is pure and checked without a display; the window build
  and single-instance behaviour are display-gated, like the other help
  windows.

  # -- Parsing ----------------------------------------------------------

  Scenario: Each version becomes a section
    When the sample changelog is parsed
    Then the section headings are "2.0.0 - 2026-09-09" and "1.0.0 - 2026-01-01"

  Scenario: The top title is dropped
    When the sample changelog is parsed
    Then no section is headed "Changelog"

  Scenario: Bold and code marks are stripped
    When the sample changelog is parsed
    Then the first section carries "• A bold change with a code bit."

  Scenario: A wrapped bullet is rejoined
    When the sample changelog is parsed
    Then the first section carries "• A bullet wrapped over two lines."

  Scenario: An empty changelog still yields a section
    When a changelog holding only a title is parsed
    Then there is at least one section

  # -- The shipped file ---------------------------------------------------

  Scenario: The real changelog loads with the latest first
    Then the shipped changelog's first section starts with "1.71.5"

  # -- The window itself - needs a display ----------------------------------

  Scenario: It opens titled Changelog
    Given a running application shell
    When the changelog window is shown
    Then its title is "Changelog"

  Scenario: Opening it twice raises the same window
    Given a running application shell
    When the changelog window is shown twice
    Then both are the same window
