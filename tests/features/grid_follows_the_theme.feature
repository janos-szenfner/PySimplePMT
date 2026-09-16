@grid_follows_the_theme
Feature: The task grid repaints when the appearance changes

  The grid is a ttk Treeview, and every row's colour comes from a tag
  named after the colours it carries. Nothing about that follows a theme
  on its own: the style has to be reconfigured and the rows have to be
  painted again, with tags under new names. Only the first of those was
  being done, so flipping to dark mode darkened the heading and the
  empty space below the rows and left every row white between them -
  the one thing a reader would notice.

  The rows are read back through the widget rather than through the task
  list's own bookkeeping, because the fault was precisely that the two
  disagreed: the cache of tag names had been cleared while the rows on
  screen still wore the old ones.

  Needs a display; the scenarios skip where there is none.

  Background: a three-row plan drawn in the light appearance
    Given a task list over three rows in the light appearance

  Scenario: The rows start in the light palette
    # The fixture is what it claims to be.
    Then every row fill is a light colour

  Scenario: Every row takes the dark palette
    # The banding means a row is one of two colours, so both halves of
    # the dark pair are allowed and neither light one is.
    When the appearance goes dark
    Then every row fill is a dark colour

  Scenario: The banding survives the change
    # Two shades after the flip, as there were before it.
    When the appearance goes dark
    Then the rows still alternate in as many shades as before

  Scenario: The ink follows as well
    # Dark text on a dark grid would be worse than not repainting.
    When the appearance goes dark
    Then the row text is the dark ink

  Scenario: The style follows too
    # The empty space below the rows is the style, not the tags.
    When the appearance goes dark
    Then the grid's field background is the dark row colour
