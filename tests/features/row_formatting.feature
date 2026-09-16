@row_formatting
Feature: How a row is painted: the hierarchy, and the formatting on top

  Two separate promises meet on one Treeview row.

  The first is the outline: a row that brackets other rows is bold and
  its children are indented, and that has to be true whether or not the
  Type column is on screen - a reader scanning the list is not reading
  columns.

  The second is the formatting somebody applied. That has to survive
  alongside the banding, the greying of a cut row and the outline's own
  bold, and a Treeview settles which of two tags wins in a way this
  application should not be relying on. So the whole appearance is
  resolved in Python onto one tag, and what that tag ends up saying is
  what these check.

  Rows are inspected through the tags on them rather than by looking
  at pixels. The module skips without a display; CI provides one
  through xvfb.

  Scenario: A container row is bold
    # A Phase brackets what is under it, so it reads as a heading.
    Given a plan with a phase, work under it and a standalone task
    Then the font on "P1" reads bold

  Scenario: Work under it is not bold
    # Bold everywhere would say nothing anywhere.
    Given a plan with a phase, work under it and a standalone task
    Then the font on "T1" is not bold

  Scenario: A task with children is bold too
    # Whatever its Type says - having work nested under it is what
    # makes a row a summary of that work; the type column is for
    # scheduling, not for grouping.
    Given a plan with a phase, work under it and a standalone task
    When a subtask is nested under "T2"
    Then "T2" is a summary row
    And the font on "T2" reads bold

  Scenario: An empty phase still reads as one
    # It is the bracket it is, whether anything is in it yet or not.
    Given a plan with a phase, work under it and a standalone task
    When the task under "P1" is removed
    Then the font on "P1" reads bold

  Scenario: The child hangs under its parent in the tree
    # Which is what draws the indent and the chevron - the Treeview
    # supplies both from the parent-child relation, so this is the
    # assertion behind "indented one level with an expander".
    Given a plan with a phase, work under it and a standalone task
    Then "T1" hangs under "P1" and "P1" hangs at the top

  Scenario: A fill becomes the row background
    # Rather than the banding it replaces.
    Given a plan with a phase, work under it and a standalone task
    When "T2" is styled with fill "#fff2cc"
    Then the background on "T2" is "#fff2cc"

  Scenario: An ink becomes the row foreground
    # The task name is drawn in it.
    Given a plan with a phase, work under it and a standalone task
    When "T2" is styled with ink "#c0392b"
    Then the foreground on "T2" is "#c0392b"

  Scenario: Every emphasis reaches the font
    # All three at once, which is what the red italic preset needs.
    Given a plan with a phase, work under it and a standalone task
    When "T2" is styled bold, italic and underlined
    Then the font on "T2" carries bold, italic and underline

  Scenario: A summary keeps its bold when given a colour
    # Setting one thing must not quietly clear another.
    Given a plan with a phase, work under it and a standalone task
    When "P1" is styled with ink "#c0392b"
    Then the font on "P1" reads bold
    And the foreground on "P1" is "#c0392b"

  Scenario: A summary can be told not to be bold
    # An explicit choice outranks the default for the row type.
    Given a plan with a phase, work under it and a standalone task
    When "P1" is styled explicitly not bold
    Then the font on "P1" is not bold

  Scenario: An unformatted row still gets its banding
    # The alternating shading is on the same tag as everything else.
    Given a plan with a phase, work under it and a standalone task
    Then the backgrounds on "P1" and "T1" differ

  Scenario: Rows formatted alike share one tag
    # Forty rows marked as financial milestones configure one tag.
    # Worth pinning: a tag per row would leave the widget carrying one
    # configuration per task in the plan.
    Given a plan with a phase, work under it and a standalone task
    When "T1" and "T2" are styled with fill "#fff2cc" and bold
    Then the visual tags on "T1" and "T2" are the same tag

  Scenario: A cut row is greyed whatever ink it carries
    # The formatting is still on the task; it just is not drawn now.
    Given a plan with a phase, work under it and a standalone task
    When "T2" is styled with ink "#c0392b" and cut
    Then the foreground on "T2" is not "#c0392b"

  Scenario: The fill is left alone while a row is cut
    # Only the ink says "not this one" - dropping the fill as well
    # would make a marked-up row unrecognisable the moment it was cut,
    # and the user has to be able to see what they are about to move.
    Given a plan with a phase, work under it and a standalone task
    When "T2" is styled with fill "#fff2cc" and cut
    Then the background on "T2" is "#fff2cc"

  Scenario: A subtask is still marked as one
    # The marker is what the rest of the file identifies rows by.
    Given a plan with a phase, work under it and a standalone task
    When a subtask is nested under "T2"
    Then the tags on the new subtask include "subtask"

  Scenario: The markers paint nothing
    # Every colour is on the resolved tag, and only there - two tags
    # both setting a background leaves Tk to decide which wins, which
    # is the thing the single resolved tag exists to avoid.
    Given a plan with a phase, work under it and a standalone task
    Then no marker tag paints a colour
