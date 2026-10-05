Feature: Dependency types, lead/lag and automatic scheduling
  Everything here goes against Project directly, so none of it needs a
  display. The four types split into two groups - FS and SS place a
  task's start, FF and SF its finish - which is why constrained_dates
  returns a pair rather than the single start date the model used to
  work with.

  Scheduling runs on the project's working calendar, so the dates here
  are read against a Monday-to-Friday week. Two things follow, and both
  are asserted rather than assumed: a task is never left starting or
  finishing on a weekend, and a task that moves keeps its working
  duration rather than its calendar span. The fixture runs from
  Thursday 1 January 2026, which puts a weekend inside the first chain
  deliberately.

  # ---- the four types -----------------------------------------------------------------

  Scenario: Finish-Start follows the predecessor
    # FS starts the day after the predecessor's inclusive end.
    Given a scheduling pair
    When "B" waits "FS" "Hard" lag 0 on "A"
    Then "B" starts "2026-01-06"

  Scenario: Start-Start aligns the starts
    Given a scheduling pair
    When "B" waits "SS" "Hard" lag 0 on "A"
    Then "B" starts "2026-01-01"

  Scenario: Finish-Finish aligns the finishes
    Given a scheduling pair
    When "B" waits "FF" "Hard" lag 0 on "A"
    Then "B" ends "2026-01-05"

  Scenario: Start-Finish ends at the predecessor's start
    Given a scheduling pair
    When "B" waits "SF" "Hard" lag 0 on "A"
    Then "B" ends "2026-01-01"

  Scenario: Duration is preserved
    # Moving a task keeps its working length. Its calendar span may
    # well change, and that is the point: the successor starts on
    # Thursday the 1st and ends on Saturday the 3rd, two days of work
    # inside a three-day span. Moved to the Tuesday it holds the same
    # two days of work in two days of calendar. Adding the old span
    # back on instead would have spent one of them on the Saturday.
    Given a scheduling pair
    And "B" holds its length
    When "B" waits "FS" "Hard" lag 0 on "A"
    Then "B" still holds that length
    And "B" starts "2026-01-06"
    And "B" ends "2026-01-07"

  Scenario: Every type is supported
    # All four codes round-trip through a Dependency.
    Then each dependency type round-trips

  Scenario: An unknown type falls back to Finish-Start
    # A code from a newer file does not break the link.
    Then a "ZZ" link reads as "FS"

  Scenario: The labels cover every type
    Then each type has a label

  Scenario: Only the finish types constrain the finish
    # FF and SF hold the finish; FS and SS hold the start.
    Then "FF" and "SF" hold the finish but "FS" and "SS" do not

  # ---- a span stated by two links --------------------------------------------------------
  # Start-Start onto the first task and Finish-Finish onto the last is
  # how a row is made to cover a stretch of the plan - a summary row
  # spanning the work that produces it, without that work being nested
  # inside it. Only the start was honoured before, and the task's old
  # length was put back on top of it.

  Scenario: It covers both tasks
    # From the first task's start to the last one's finish.
    Given a scheduling pair and a span row
    When "D" spans "A" to "B"
    Then "D" starts "2026-01-01"
    And "D" ends "2026-01-09"

  Scenario: Its length is the span, not what it used to be
    # The duration follows from the two dates rather than being
    # preserved. The row was five days long before the links were
    # added; it would otherwise have stayed the length of the first
    # task alone.
    Given a scheduling pair and a span row
    When "D" spans "A" to "B"
    Then "D" holds its span as days of work

  Scenario: It survives a reschedule
    # Settling the plan does not put the old length back.
    Given a scheduling pair and a span row
    And "D" spanned "A" to "B"
    When the plan is rescheduled
    Then "D" starts "2026-01-01"
    And "D" ends "2026-01-09"

  Scenario: A single link still preserves the length
    # One link places the task and keeps what it holds; only a start
    # and a finish together state a span.
    Given a scheduling pair and a span row
    And "B" holds its length
    When "B" waits "FS" "Hard" lag 0 on "A"
    Then "B" still holds that length

  Scenario: A finish required before the start keeps the length
    # Contradictory links are not a span, and do not draw a bar
    # backwards. The finish is required on the 5th and the start on
    # the 6th, which no task can do; the start places it and its
    # length is kept.
    Given a scheduling pair and a span row
    And "D" is re-dated "2026-01-06" to "2026-01-09"
    When "D" waits "SS" "Hard" lag 0 on "B"
    And "D" also waits "FF" "Hard" lag 0 on "A"
    Then "D" does not end before it starts

  # ---- lag and lead -------------------------------------------------------------------------

  Scenario: Lag delays the successor
    # A positive lag pushes the start out, by working days. The link
    # places the successor on Tuesday the 6th and three working days
    # of lag is the Friday. Counted in calendar days it was the Friday
    # too - but a lag of one or two landed on the weekend and was
    # pushed back to the Monday, so waiting a day or two was no wait
    # at all.
    Given a scheduling pair
    When "B" waits "FS" "Hard" lag 3 on "A"
    Then "B" starts "2026-01-09"

  Scenario: A short lag is not swallowed by a weekend
    # One working day of lag delays the successor by one working day.
    Given a scheduling pair
    When "B" waits "FS" "Hard" lag 1 on "A"
    Then "B" starts "2026-01-07"
    When "B" waits "FS" "Hard" lag 2 on "A"
    Then "B" starts "2026-01-08"

  Scenario: Lead pulls the successor in
    # A negative lag is lead time, counted in working days. The link
    # would place the successor on Tuesday the 6th; two working days
    # of lead off that is the Friday before. Counted in calendar days
    # it reached Sunday the 4th and was pushed back to the Monday, so
    # a lead of two bought one day and a lead of one bought nothing.
    Given a scheduling pair
    When "B" waits "FS" "Hard" lag -2 on "A"
    Then "B" starts "2026-01-02"

  Scenario: Lag applies to a finish link
    Given a scheduling pair
    When "B" waits "FF" "Hard" lag 4 on "A"
    Then "B" ends "2026-01-09"

  Scenario: Lag defaults to none
    Then a link with no lag stated has none

  Scenario: A bad lag is treated as zero
    # Junk from a file does not break loading.
    Then a "nonsense" lag reads as 0

  Scenario: Lag survives serialisation
    Then a lag of 5 round-trips

  # ---- hardness ------------------------------------------------------------------------------

  Scenario: Hard pulls a late task back
    # A hard link fixes the date exactly, earlier or later.
    Given a scheduling pair
    And "B" is re-dated "2026-03-01" to "2026-03-03"
    When "B" waits "FS" "Hard" lag 0 on "A"
    Then "B" starts "2026-01-06"

  Scenario: Rubber leaves a later task alone
    # A rubber link only forbids being earlier.
    Given a scheduling pair
    And "B" is re-dated "2026-03-02" to "2026-03-04"
    When "B" waits "FS" "Rubber" lag 0 on "A"
    Then "B" starts "2026-03-02"

  Scenario: A link never leaves a task on a weekend
    # Whatever a link works out, the task lands on a working day. A
    # task sitting on a Sunday is moved to the Monday even by a
    # rubber link that had nothing else to say: every date the
    # scheduler writes is a date somebody could work.
    Given a scheduling pair
    And "B" is re-dated "2026-03-01" to "2026-03-04"
    When "B" waits "FS" "Rubber" lag 0 on "A"
    Then "B" starts "2026-03-02"

  Scenario: Rubber still pushes an early task out
    # A rubber link is a floor, so it moves a task that starts too soon.
    Given a scheduling pair
    When "B" waits "FS" "Rubber" lag 0 on "A"
    Then "B" starts "2026-01-06"

  # ---- a length written onto a task ------------------------------------------------------------
  # A task can carry an explicit duration as well as two dates, and
  # the task form writes one on every save. A span stated by a pair of
  # links changed the dates without changing the number, so the next
  # pass rebuilt the finish from the stale number and undid the span.

  Scenario: A span updates the stored length
    # The number follows the dates the links produced.
    Given a scheduling pair and a span row
    And "B" is re-dated "2026-01-12" to "2026-01-16"
    And "D" carries a stored duration of 3
    When "D" spans "A" to "B"
    Then "D"'s stored duration matches its span

  Scenario: A span survives the working-calendar pass
    # The stale number rebuilt the finish on every pass, so the two
    # rules alternated until the iteration cap reported a cycle that
    # was not there.
    Given a scheduling pair and a span row
    And "B" is re-dated "2026-01-12" to "2026-01-16"
    And "D" carries a stored duration of 3
    And "D" spanned "A" to "B"
    When the plan is rescheduled
    Then "D" ends "2026-01-16"
    And rescheduling settles

  Scenario: A container ignores a length written onto it
    # A Phase spans its children whatever number is stored on it. The
    # form derives a duration from the two dates even where its own
    # rules have greyed the box out, so a container edited once was
    # frozen at whatever its children happened to span that day.
    Given a phase "P" holding "T" into late January
    When the plan is rescheduled
    And "P" is given a stale duration of 5
    Then "P" reads 0 days by duration
    And "P" holds 20 days of work

  # ---- Start No Earlier Than -----------------------------------------------------------------------
  # The retired "Earliest begin" field was exactly this constraint by
  # another name (issue #32), so the floor it used to describe is
  # proved here on the SNET constraint that carries the idea now.

  Scenario: It pushes a task forward
    Given a scheduling pair
    And "B" has a floor of "2026-03-02"
    When the plan is rescheduled
    Then "B" starts "2026-03-02"

  Scenario: It lands on a working day
    # A Sunday floor means the Monday, like every other date.
    Given a scheduling pair
    And "B" has a floor of "2026-03-01"
    When the plan is rescheduled
    Then "B" starts "2026-03-02"

  Scenario: It is a floor, not a pin
    # A task already starting later is left where it is.
    Given a scheduling pair
    And "B" is re-dated "2026-06-01" to "2026-06-05"
    And "B" has a floor of "2026-03-02"
    When the plan is rescheduled
    Then "B" starts "2026-06-01"

  Scenario: The task keeps its length
    # Being held back moves a task; it does not shorten it.
    Given a scheduling pair
    And "B" holds its length
    And "B" has a floor of "2026-03-02"
    When the plan is rescheduled
    Then "B" still holds that length

  Scenario: A plan with one still settles
    # The floor only ever moves a task later, so the pass converges.
    Given a scheduling pair
    And "B" has a floor of "2026-03-02"
    When the plan is rescheduled
    Then rescheduling settles

  # ---- a milestone predecessor ------------------------------------------------------------------------
  # A milestone marks a moment rather than occupying a day. The
  # inclusive-end rule adds a day to a real task's finish, because it
  # occupies that whole day; a milestone takes no time, so adding a
  # day would leave a gap that is not there.

  Scenario: Finish-Start lands on the milestone date
    Given a scheduling pair
    And "A" is a milestone on "2026-01-15"
    When "B" waits "FS" "Hard" lag 0 on "A"
    Then "B" starts "2026-01-15"

  Scenario: Start-Start lands on the milestone date
    # SS behaves the same for a zero-duration predecessor.
    Given a scheduling pair
    And "A" is a milestone on "2026-01-15"
    When "B" waits "SS" "Hard" lag 0 on "A"
    Then "B" starts "2026-01-15"

  # ---- the auto-scheduling pass ------------------------------------------------------------------------

  Scenario: The chain settles
    # Each task follows the one before it, on working days. Every
    # task holds two days of work. A starts Thursday the 1st and ends
    # on the Friday; B would follow on Saturday the 3rd, so it starts
    # on the Monday; C follows it on the Wednesday.
    Given a chain of "A, B, C" rescheduled
    Then the starts are "A=2026-01-01, B=2026-01-05, C=2026-01-07"

  Scenario: Moving the head moves everything
    # Links used to be applied only when one was created, so moving a
    # predecessor afterwards left everything downstream where it was.
    # The head is moved onto Sunday 1 February, which it cannot start
    # on, so the chain runs from the Monday.
    Given a chain of "A, B, C" rescheduled
    When "A" is moved to "2026-02-01" to "2026-02-03"
    And the plan is rescheduled
    Then the starts are "A=2026-02-02, B=2026-02-04, C=2026-02-06"

  Scenario: A settled plan does not move
    # Rescheduling twice changes nothing the second time.
    Given a chain of "A, B, C" rescheduled
    Then rescheduling settles

  Scenario: A cycle does not hang
    # Mutually dependent tasks stop rather than looping. The pass
    # repeats until nothing moves, so a cycle would never settle
    # without the iteration cap.
    Given a cyclic project
    When the plan is rescheduled
    Then the project holds 2 tasks

  Scenario: A missing predecessor is ignored
    # A link to a deleted task does not stop the rest scheduling.
    Given a chain of "A, B, C" rescheduled
    And "B" also waits on "gone"
    When the plan is rescheduled
    Then "C" starts "2026-01-07"

  # ---- the automatic pass only moves forward --------------------------------------------------------------
  # A hard link pins a date exactly, which is right when the user has
  # just chosen a predecessor and wrong to apply unasked to a whole
  # plan. An imported GanttProject file is the clearest case: its dates
  # come from replaying the file's working-day calendar, so a task sits
  # after a weekend, and pinning it to the day after its predecessor
  # put the plan on dates GanttProject never showed.

  Scenario: Slack is left alone
    # A gap the user or a file put there survives.
    Given a scheduling pair with slack
    When the plan is rescheduled
    Then "B" starts "2026-01-12"

  Scenario: A violation is repaired
    # A successor starting too early is still pushed out.
    Given a scheduling pair with slack
    And "B" is re-dated "2026-01-02" to "2026-01-04"
    When the plan is rescheduled
    Then "B" starts "2026-01-06"

  Scenario: Moving a predecessor later drags the successor
    # The point of auto-scheduling still holds.
    Given a scheduling pair with slack
    And "A" is re-dated "2026-03-01" to "2026-03-05"
    When the plan is rescheduled
    Then "B" starts "2026-03-06"

  Scenario: Choosing a predecessor still pins exactly
    # The dialog's own call is unaffected. Picking a predecessor
    # should place the task on the link's date, which is what fills
    # the start date in without the user typing it.
    Given a scheduling pair with slack
    When "B" is pinned by its link
    Then "B" starts "2026-01-06"

  # ---- summary roll-up ---------------------------------------------------------------------------------
  # A task with sub-tasks derives its dates from them.

  Scenario: It spans its children
    # The parent runs from the earliest child to the latest. The
    # later child was given a finish on Saturday the 24th; it holds
    # the same work ending on the Friday, so that is where the
    # parent reaches.
    Given a phase of "One" and "Two"
    When the plan is rescheduled
    Then "P1" starts "2026-01-01"
    And "P1" ends "2026-01-23"

  Scenario: Progress counts finished sub-tasks
    # One of its two sub-tasks is finished, so it reads 50% - the
    # length of each does not come into it.
    Given a phase of "One" and "Two"
    When the plan is rescheduled
    Then "P1" reads 50 percent

  Scenario: A child moving out stretches the parent
    # The parent grows rather than the child being clipped. The
    # child is stretched to Sunday 15 March, so its last working day
    # is the Friday before, and the parent reaches exactly that far.
    Given a phase of "One" and "Two"
    When the plan is rescheduled
    And "C2" is re-dated its end to "2026-03-15"
    And the plan is rescheduled
    Then "P1" ends "2026-03-13"

  Scenario: Nested summaries total upwards
    # A summary of summaries takes what its children settled on.
    Given a nested project
    When the plan is rescheduled
    Then "TOP" starts "2026-04-01"
    And "TOP" ends "2026-04-30"

  Scenario: A childless task keeps its own dates
    # Roll-up only touches tasks that have sub-tasks.
    Given a phase of "One" and "Two"
    When the plan is rescheduled
    Then "C1" starts "2026-01-01"

  Scenario: A link moves a summary by moving what is in it
    # A summary's dates come from its children, so it is moved by
    # moving them. The link pass used to skip a summary altogether,
    # which left a link to a summary drawn on the chart and never
    # obeyed - "it didn't jump after it, it's just nicely tied there
    # with a red dot".
    Given a phase of "One" and "Two" preceded by "Z" in September
    When the plan is rescheduled
    Then "P1" starts after "Z" ends

  Scenario: The children move with it
    # Which is what keeps the summary bracketing them.
    Given a phase of "One" and "Two" preceded by "Z" in September
    And the children note their starts
    When the plan is rescheduled
    Then "C1" and "C2" were not left behind

  Scenario: It still spans them afterwards
    # The whole point of moving the branch rather than the row.
    Given a phase of "One" and "Two" preceded by "Z" in September
    When the plan is rescheduled
    Then "P1" brackets "C1" and "C2"

  Scenario: Link-less children follow the collection's predecessor
    # A dependency on a collection drives the work inside it (issue
    # #25). The children carry no links of their own, so the phase's
    # predecessor says when they may begin: both start on the date it
    # sets, rather than keeping the arbitrary offsets they had.
    Given a phase of "One" and "Two" preceded by "Z" in September
    When the plan is rescheduled
    Then "C1" and "C2" start together after "Z" ends
    And "P1" starts with "C1"

  Scenario: A child chain sequences from the collection's start
    # Only a link-less child follows the collection start; one that
    # waits for a sibling follows that sibling instead, so a chain
    # still runs in order from wherever its first member begins.
    Given a phase of "One" and "Two" preceded by "Z" in September
    And "C2" waits "FS" "Hard" on "C1"
    When the plan is rescheduled
    Then "C1" starts after "Z" ends
    And "C2" starts after "C1" ends

  Scenario: A plan linked through a summary settles
    # The pass repeats until nothing moves, capped so a cycle cannot
    # spin forever, and warns when it hits the cap. Hitting it means
    # the dates are wherever the last pass left them.
    Given a phase of "One" and "Two" preceded by "Z" in September
    When the plan is rescheduled with logging
    Then no "did not settle" warning was logged

  Scenario: It stays where it landed
    # A plan that creeps on every pass is the fault guarded against
    # here: the dates were different every time anything touched them.
    Given a phase of "One" and "Two" preceded by "Z" in September
    When the plan is rescheduled
    And it is rescheduled three more times
    Then the dates did not creep

  # ---- milestone rules ---------------------------------------------------------------------------------------
  # Milestones stay zero-duration markers.

  Scenario: An end date is cleared
    # A milestone's end is its start - a moment, not a span.
    Given a milestone "M" with a stray child "S"
    And "M" is given an end of "2026-02-02"
    When the plan is rescheduled
    Then "M" ends "2026-01-01"

  Scenario: A child is promoted off a milestone
    # A milestone cannot have sub-tasks - it would have to span them,
    # which contradicts taking no time. The child is promoted rather
    # than dropped, so no work is lost.
    Given a milestone "M" with a stray child "S"
    When the plan is rescheduled
    Then "S" has no parent and is a "Task"

  Scenario: A milestone has no duration
    Given a milestone "M" with a stray child "S"
    When the plan is rescheduled
    Then "M" reads 0 days by duration

  Scenario: A milestone is not a summary
    # Once its child is promoted, nothing hangs off it.
    Given a milestone "M" with a stray child "S"
    When the plan is rescheduled
    Then "M" is not a summary

  # ---- the raw constraint calculation ---------------------------------------------------------------------------

  Scenario: No links constrain nothing
    Given a scheduling pair
    Then "B" is constrained to "none" and "none"

  Scenario: A start link returns only a start
    # FS says when to start and nothing about the finish.
    Given a scheduling pair
    And "B" waits "FS" "Hard" on "A"
    Then "B" is constrained to "2026-01-06" and "none"

  Scenario: A finish link returns only a finish
    Given a scheduling pair
    And "B" waits "FF" "Hard" on "A"
    Then "B" is constrained to "none" and "2026-01-05"

  Scenario: The latest hard link wins
    # With several hard links the latest applies.
    Given a scheduling pair
    And a third task running "2026-02-01" to "2026-02-10"
    And "B" waits "FS" "Hard" on "A"
    And "B" waits "FS" "Hard" on "C"
    Then "B" is constrained to "2026-02-11" and "none"

  Scenario: A start link wins over a finish link
    # FS and SS place a task; FF and SF only hold its finish.
    # Honouring the finish first would drag a task away from the
    # predecessor it is meant to follow.
    Given a scheduling pair
    And "B" waits "FS" "Hard" on "A"
    And "B" waits "FS" "Hard" on "A"
    When "B" is pinned by its links
    Then "B" starts "2026-01-06"
