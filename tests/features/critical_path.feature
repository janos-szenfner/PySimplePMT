Feature: The critical path analysis
  Criticality is defined as zero total float, and that needs both
  passes of the critical path method. What is pinned down here is the
  arithmetic: that the float is right, that every zero-float task is
  found rather than one chain through them, and that the link types
  are honoured on the way back.

  Everything is counted in working days, so the fixtures run Monday to
  Friday and the expected numbers are working days rather than
  calendar ones. Nothing here needs a display; the window and the
  painted rows are covered by the unittest module.

  A network is written as a table - id, start, end, and its links as
  predecessor:type:lag triples. An empty end is a milestone.

  # ---- the numbers the two passes produce ---------------------------------------------

  Scenario: The driving chain has no float
    # A, B and D cannot slip by a day.
    Given an analysed network
      | id | start      | end        | links       |
      | A  | 2026-01-05 | 2026-01-09 |             |
      | B  | 2026-01-12 | 2026-01-23 | A:FS:0      |
      | C  | 2026-01-12 | 2026-01-13 | A:FS:0      |
      | D  | 2026-01-26 | 2026-01-30 | B:FS:0,C:FS:0 |
    Then the floats are "A=0, B=0, D=0"

  Scenario: The slack strand has its slack measured
    # C runs two days inside a ten-day window, so it has eight.
    # Working days: the weekend inside the window is not slack
    # anybody can spend, and counting it would overstate the number
    # by four.
    Given an analysed network
      | id | start      | end        | links       |
      | A  | 2026-01-05 | 2026-01-09 |             |
      | B  | 2026-01-12 | 2026-01-23 | A:FS:0      |
      | C  | 2026-01-12 | 2026-01-13 | A:FS:0      |
      | D  | 2026-01-26 | 2026-01-30 | B:FS:0,C:FS:0 |
    Then the float of "C" is 8

  Scenario: The critical path is every zero-float task
    # Not one chain through them.
    Given an analysed network
      | id | start      | end        | links       |
      | A  | 2026-01-05 | 2026-01-09 |             |
      | B  | 2026-01-12 | 2026-01-23 | A:FS:0      |
      | C  | 2026-01-12 | 2026-01-13 | A:FS:0      |
      | D  | 2026-01-26 | 2026-01-30 | B:FS:0,C:FS:0 |
    Then the critical tasks are "A, B, D"

  Scenario: Late dates are the early ones where there is no float
    # A critical task has nowhere to be but where it is.
    Given an analysed network
      | id | start      | end        | links       |
      | A  | 2026-01-05 | 2026-01-09 |             |
      | B  | 2026-01-12 | 2026-01-23 | A:FS:0      |
      | C  | 2026-01-12 | 2026-01-13 | A:FS:0      |
      | D  | 2026-01-26 | 2026-01-30 | B:FS:0,C:FS:0 |
    Then "A, B, D" have their late dates equal their early dates

  Scenario: A slack task may finish later than it does
    # Its latest finish is where the work behind it needs it.
    Given an analysed network
      | id | start      | end        | links       |
      | A  | 2026-01-05 | 2026-01-09 |             |
      | B  | 2026-01-12 | 2026-01-23 | A:FS:0      |
      | C  | 2026-01-12 | 2026-01-13 | A:FS:0      |
      | D  | 2026-01-26 | 2026-01-30 | B:FS:0,C:FS:0 |
    Then "C" may finish 8 days later

  # ---- the case a single chain could not express -----------------------------------------
  # Two strands of equal length between the same two tasks are both
  # critical: either one slipping moves the finish. The old
  # implementation walked back through one predecessor and reported
  # that strand alone.

  Scenario: Both equal strands are critical
    Given an analysed network
      | id    | start      | end        | links              |
      | start | 2026-01-05 | 2026-01-09 |                    |
      | left  | 2026-01-12 | 2026-01-23 | start:FS:0         |
      | right | 2026-01-12 | 2026-01-23 | start:FS:0         |
      | end   | 2026-01-26 | 2026-01-30 | left:FS:0,right:FS:0 |
    Then the critical tasks are "end, left, right, start"

  # ---- what a predecessor has to clear depends on which end the link holds -------------------

  Scenario: A start-start link lets the predecessor run on
    # Only the start has to clear, so the first task may still be
    # running when the second begins. Its latest finish falls after
    # the second task's earliest start, which is the whole difference
    # between this link and a Finish-Start one.
    Given an analysed network
      | id     | start      | end        | links       |
      | first  | 2026-01-05 | 2026-01-09 |             |
      | second | 2026-01-05 | 2026-01-16 | first:SS:0  |
    Then "first" may finish no earlier than "second" starts early

  Scenario: A finish-start link does not
    # The same pair, under the link that says finish first.
    Given an analysed network
      | id     | start      | end        | links       |
      | first  | 2026-01-05 | 2026-01-09 |             |
      | second | 2026-01-12 | 2026-01-23 | first:FS:0  |
    Then "first" must finish strictly before "second" starts early

  Scenario: A finish-finish link ties the two finishes
    # The predecessor may run right up to the successor's finish. A
    # short task tied Finish-Finish to a long one has all the room
    # the difference between them gives it.
    Given an analysed network
      | id    | start      | end        | links      |
      | short | 2026-01-05 | 2026-01-06 |            |
      | long  | 2026-01-05 | 2026-01-16 | short:FF:0 |
    Then "short" finishes late when "long" does
    And "short" has some float

  Scenario: A lag is slack the predecessor does not get
    # The wait is part of the plan, not float. A three-day lag
    # between two tasks does not mean the first has three days to
    # spare: the wait still has to happen after it.
    Given an analysed network
      | id     | start      | end        | links       |
      | first  | 2026-01-05 | 2026-01-09 |             |
      | second | 2026-01-15 | 2026-01-21 | first:FS:3  |
    Then the float of "first" is 0

  # ---- not everything in a plan is work ---------------------------------------------------------

  Scenario: A summary is not analysed
    # It brackets its children rather than being work of its own.
    # Left in, a group bar spanning a fortnight would outrank the
    # work inside it and come out critical on its own account.
    Given a phase "P" over a subtask "T" of the same span
    When the plan is analysed
    Then "P" is not in the analysis
    And "T" is in the analysis

  Scenario: A milestone takes no time and can still be critical
    # It marks a moment, and the moment can be the one that matters.
    Given an analysed network
      | id   | start      | end        | links      |
      | work | 2026-01-05 | 2026-01-09 |            |
      | gate | 2026-01-12 |            | work:FS:0  |
    Then "gate" takes no time
    And "gate" is critical

  Scenario: An empty plan analyses to nothing
    # And says so rather than raising.
    Then an empty plan analyses to nothing

  # ---- a deadline is a limit of its own (issue #39) ------------------------------------------------
  # Slack is measured against it rather than the plan's end, so a
  # finish past it is the negative float it is - which is also what
  # puts the warning flag on the row.

  Scenario: A finish past its deadline is negative float
    # Four days over a deadline is four days of corrective action.
    Given a plan with "A" from "2026-03-02" to "2026-03-06" due "2026-03-04"
    Then the float of "A" is negative

  Scenario: The overrun is measured in working days
    # Finish Friday against a Monday deadline is -4, weekends excluded.
    Given a plan with "A" from "2026-03-02" to "2026-03-06" due "2026-03-02"
    Then the float of "A" is -4

  Scenario: A deadline not yet reached leaves ordinary float
    # Room before it is positive slack, counted to it not the end.
    # 9 working days to the deadline, 4 spent - without the deadline
    # the plan's own end would have allowed ten.
    Given a plan with "A" from "2026-03-02" to "2026-03-06" due "2026-03-13"
    And it also holds "B" from "2026-03-09" to "2026-03-20"
    Then the float of "A" is 5
    And "A" is not critical

  Scenario: Changing the deadline is noticed
    # The cache signature covers it, or the answer would go stale.
    Given a plan with "A" from "2026-03-02" to "2026-03-06"
    And it is analysed once
    When "A" is given a deadline of "2026-03-04"
    Then the analysis is recomputed
    And the float of "A" is negative

  Scenario: A deadline past the plan's end changes nothing
    # A limit looser than the plan's own end never bites.
    Given a plan with "A" from "2026-03-02" to "2026-03-06" due "2026-03-20"
    And a twin plan without the deadline
    Then the two answers agree on "A"

  Scenario: A dependency cycle returns rather than looping
    # The backward pass walks successors, which a cycle never
    # exhausts. An edge it cannot measure contributes nothing rather
    # than the whole analysis failing on a plan that has one - and it
    # is logged, so the cycle is not silently treated as a schedule.
    Given a network
      | id | start      | end        | links   |
      | X  | 2026-01-05 | 2026-01-09 | Y:FS:0  |
      | Y  | 2026-01-12 | 2026-01-16 | X:FS:0  |
    When it is analysed
    Then the analysis covers "X, Y"

  Scenario: A link to a task that is gone is ignored
    # A file can name a predecessor that is not in the plan.
    Given a network
      | id   | start      | end        | links        |
      | only | 2026-01-05 | 2026-01-09 | missing:FS:0 |
    When it is analysed
    Then the analysis covers "only"

  # ---- the shape of what comes back --------------------------------------------------------------------

  Scenario: Every task gets a full set
    # Early, late, float and the verdict, for each.
    Given an analysed network
      | id | start      | end        | links   |
      | A  | 2026-01-05 | 2026-01-09 |         |
      | B  | 2026-01-12 | 2026-01-16 | A:FS:0  |
    Then each finding is internally consistent

  Scenario: The first task starts at offset zero
    # Offsets are working days from the plan's first day; five
    # working days of A put B on the sixth.
    Given an analysed network
      | id | start      | end        | links   |
      | A  | 2026-01-05 | 2026-01-09 |         |
      | B  | 2026-01-12 | 2026-01-16 | A:FS:0  |
    Then "A" has early start 0
    And "B" has early start 5

  # ---- where the analysis is reached from ------------------------------------------------------------------

  Scenario: The icon stands on its own between the groups
    # With a divider on each side: it neither edits a row nor moves
    # anything about, so it belongs to neither of the groups it sits
    # between - pinned to the dividers rather than to whichever icon
    # happens to be its neighbour.
    Then "critical_path" sits between two separators
    And "unlink" precedes it and "cut" follows it

  Scenario: The icon has a drawing and a handler
    # An icon with neither is a blank button that does nothing.
    Then "critical_path" has icon strokes and a Toolbar method

  Scenario: The full report is on the View menu
    # Which is the only place it opens from now. The icon paints the
    # critical rows into the task list instead - "which of these rows
    # cannot slip" is asked while reading the plan, and reading it
    # off a table in a window covering that plan was the long way
    # round.
    Then "View" offers "Critical Path..."

  Scenario: The icon paints the list rather than opening the report
    # The change: one gesture, answered where the reader is looking.
    Then the icon actions include "toggle_critical_path_rows" but not "show_critical_path"
    And "toggle_critical_path_rows" is a real Toolbar method

  # ---- float has to mean the same thing for every task compared on it --------------------------------------
  # A task's duration is counted on the calendar that task follows;
  # the axis every task is placed on counts the plan's. For a plan on
  # one calendar the two agree exactly. For a task on a calendar of
  # its own they do not, and adding one to the other put the task's
  # finish past where it actually was.

  Scenario: A continuous task is not given negative float
    # Five days of a 24/7 run cover three of the plan's working days.
    # Counting the five onto an axis measuring the plan's put the
    # finish two days beyond the real one - a task reported as
    # undeliverable that was on time.
    Given a 24/7 task "A" of 5 days followed by "B" of 2
    Then the float of "A" is 0

  Scenario: The axis agrees with the dates
    # Both ends of a task measured with the one ruler. A runs Thu 10
    # to Mon 14, which is three of the plan's working days; B follows
    # on the Tuesday and Wednesday.
    Given a 24/7 task "A" of 5 days followed by "B" of 2
    Then "A" has early span 0 to 2
    And "B" has early span 3 to 4

  Scenario: A weekend task is placed where it runs
    # The other direction: a task whose week is narrower than the
    # plan's. It runs Sat 12 to Sun 13, neither of which the plan
    # works, so it covers none of the axis at all - and still has no
    # float, being the only task in the plan.
    Given a weekend-shift task "A" of 2 days from "2026-09-10"
    Then "A" really starts "2026-09-12"
    And "A" has equal early bounds and no float

  Scenario: A single-calendar plan is unchanged
    # The fix must not move the numbers everybody already has.
    Given an analysed network
      | id | start      | end        | links   |
      | A  | 2026-03-02 | 2026-03-06 |         |
      | B  | 2026-03-09 | 2026-03-13 | A:FS:0  |
      | C  | 2026-03-09 | 2026-03-11 | A:FS:0  |
    Then "A" has early span 0 to 4
    And "B" has early span 5 to 9
    And the float of "C" is 2

  # ---- the analysis is cached --------------------------------------------------------------------------------
  # The chart asks for this on every redraw, only to colour bars -
  # about 230ms on a thousand-task plan. Cached against a signature of
  # the plan rather than cleared by hand, because tasks are mutated
  # directly all over the dialogs. Every test below is really asking
  # "can it go stale".

  Scenario: An unchanged plan is not analysed twice
    # The whole point: a redraw that changed nothing pays nothing.
    Given an analysed plan of three
    When it is analysed twice
    Then the same answer object comes back

  Scenario: Moving a task is noticed
    # A date is the most obvious thing that changes the answer.
    Given an analysed plan of three
    When "C" is stretched to "2026-03-13"
    Then the analysis is recomputed
    And the float of "C" is 0

  Scenario: Changing a link is noticed
    # Links are read straight off the tasks, not through a method.
    Given an analysed plan of three
    When "C" loses its links
    Then the signature has moved

  Scenario: Adding a task is noticed
    # The signature covers the list, not only what is in each row.
    Given an analysed plan of three
    When "D" is added from "2026-03-16" to "2026-03-18"
    Then the analysis is recomputed

  Scenario: A calendar change is noticed
    # Even one that moves no dates. Float is counted in working
    # days, so a holiday inside the plan changes the answer without
    # any task's dates changing.
    Given an analysed plan of three
    When "2026-03-10" is ruled off as "shutdown" on the plan
    Then the signature has moved

  Scenario: A named calendar change is noticed
    # A task may follow one, so its week is part of the answer.
    Given an analysed plan of three
    When "weekend-shift" gets "2026-03-10" ruled off as "shutdown"
    Then the signature has moved

  Scenario: The cached answer is the right one
    # Caching is only worth having while it agrees with the slow
    # path - what stops the memoisation quietly returning yesterday's
    # answer for the rest of the session.
    Given an analysed plan of three
    Then the cached and computed answers agree

  Scenario: It can be dropped by hand
    # For a caller that did something the signature cannot see.
    Given an analysed plan of three
    When the analysis is invalidated
    Then the analysis is recomputed

  Scenario: A copied project still answers
    # The undo history copies projects, and a copy skips
    # __post_init__. Restored from copy, deepcopy or a pickle, the
    # cache attributes are whatever the original's __dict__ held -
    # or absent entirely.
    Given an analysed plan of three
    Then a shallow copy still analyses
    And a deep copy still analyses
    And a bare restore still analyses

  # ---- the axis every task's float is measured on -----------------------------------------------------------
  # Each offset used to be counted from the plan's first day, so two
  # lookups per task each walked the whole calendar - 211,703 calls
  # to is_working_day on a thousand-task plan, and O(tasks x span)
  # overall. The span is walked once now and remembered.

  Scenario: The indexed answers match the counted ones
    # A faster axis that disagreed with the old one would move every
    # float in the plan and nobody would know which was right.
    Given an axis plan
    Then the indexed and counted analyses agree

  Scenario: It covers every date the plan touches
    # A gap would send that lookup down the slow path silently.
    Given an axis plan
    Then the axis covers every task's start and end

  Scenario: It counts the same as the calendar
    # The table is only worth having while it agrees with the walk.
    Given an axis plan
    Then every axis offset equals the walked count

  Scenario: A date outside the table still answers
    # Slow rather than wrong, for anything unexpected.
    Given an axis plan
    Then the computed analysis is non-empty
