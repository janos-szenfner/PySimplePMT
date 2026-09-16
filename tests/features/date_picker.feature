@date_picker
Feature: The calendar behind the date boxes

  The weekday headings and the day cells sat in two frames, each with a
  grid of its own, and were sized in different units besides - the
  headings 34 pixels wide, the cells three characters. Two grids cannot
  line their columns up with one another, so Monday stood over no
  particular column and nor did any other day: the calendar read as a
  row of headings above an unrelated block of numbers.

  What is checked is which column each widget was placed in, which is
  what decides where it is drawn. Whether the pixels line up on a
  particular desktop is a matter of what the window manager made of the
  popup, and no test here can see that - but a day in the same column as
  its heading cannot be drawn anywhere else.

  Needs a display; the scenarios skip where there is none.

  Background: the calendar open on March 2026, a month starting on Sunday
    Given the calendar open on March 2026

  Scenario: The headings are in the same grid as the days
    # One grid, so one set of columns. Two frames cannot line their
    # columns up with one another however they are sized.
    Then the top row holds every weekday heading

  Scenario: Each heading is in its own column
    # Monday leftmost, Sunday last, one column each.
    Then every weekday heading sits in its own column

  Scenario: Every day sits under the weekday it falls on
    # Checked against the calendar module, for the whole month.
    Then every day of March 2026 sits under its weekday

  Scenario: The first of the month lands on its weekday
    # March 2026 opens on a Sunday, the last column. A month starting at
    # the right-hand edge is where a grid that has lost its leading
    # blanks shows itself.
    Then day 1 sits in the Sunday column

  Scenario: The days start below the headings
    # Row 0 is the headings, so no day may be in it.
    Then no day cell shares the headings' row

  Scenario: Every column is held to the same width
    # uniform ties them together and minsize gives them a floor. Without
    # it a column of single digits comes out narrower than one holding a
    # two-digit day, and the headings drift off their days as the month
    # goes down the grid.
    Then every column is uniform and floored at one cell

  Scenario: The headings are still there after a month change
    # _draw_month clears the grid, so it puts them back.
    When the calendar steps to the next month
    Then the top row holds every weekday heading

  Scenario: The days of the next month line up too
    # April 2026 starts on a Wednesday.
    When the calendar steps to the next month
    Then the sampled April days sit under their weekdays
