Feature: The user guide, its reference, and the chart's framing
  Two things here fail quietly rather than loudly.

  A guide fails by being wrong: the worked examples in it are dates, and
  a date that disagrees with the scheduler is worse than no example at
  all, because the reader believes it and only finds out much later.
  Every number in the guide is re-derived here from the scheduler that
  produced it.

  The chart's framing fails by being ugly, which nobody writes a test
  for and everybody notices. The range used to be padded a week on each
  side, so a month-long plan opened with a quarter of the chart showing
  nothing at all.

  The windows the guide opens in, the buttons that reach it, and the
  modal case need a display and stay in the unittest module.

  # ---- the guide covers what a reader arrives asking about ------------------------------------

  Scenario: It is a guide rather than a page
    # A tooltip's worth of text would not be worth a window.
    Then the guide runs to more than 15 sections
    And its body runs past 8000 characters

  Scenario: Every section has a heading and something under it
    # An empty section is a heading that leads nowhere.
    Then every guide section has a heading and a non-empty paragraph

  Scenario: The task types are all explained
    # The hierarchy is the first thing anybody has to understand.
    Then the guide mentions every task type

  Scenario: The scheduling rules are explained
    # Which is what "why did my task move" comes down to.
    Then the guide mentions "working day, calendar day, duration, constraint, change the start"

  Scenario: The link types are all named
    # All four, or the one that is missing is the one being looked up.
    Then the guide mentions "finish - start, start - start, finish - finish, start - finish, lag, hardness"

  Scenario: The calendar rules are explained
    # Including the priority between them, which surprises people.
    Then the guide mentions "override, public holiday, working week, critical path, float"

  Scenario: Resource management and capacity statuses are explained
    Then the guide mentions "resource information, named resources, generic resources, team members & split matrix, days off, 200%, free (neutral), optimal (green), full capacity (yellow), over capacitated (red)"

  Scenario: Import and export formats are listed
    # A reader looking for "can it read X" should find the answer.
    Then the guide mentions "gan, xlsx, mermaid, mpp, pdf"

  # ---- every date in the guide, re-derived from the scheduler ---------------------------------

  Scenario: Five days from a Thursday
    # "five days ... starting Thursday 3 September 2026 finishes on
    # Wednesday 9 September".
    Then 5 working days from "2026-09-03" land on "2026-09-09", a Wednesday

  Scenario: A six-day week pulls the example in
    # "a four-day task running Friday 11 September 2026 to Wednesday 16
    # September ends on Tuesday 15 September once Saturday is worked,
    # still holding four days".
    Given a task "a" from "2026-09-11" to "2026-09-16"
    Then "a" ends "2026-09-16" and works 4 days
    When the working week gains 6
    Then "a" ends "2026-09-15" and works 4 days

  Scenario: The three calendars example
    # "Three tasks of three days each, all starting Thursday 10
    # September 2026" - on the plan's own, a weekend-only and a 24/7
    # calendar.
    Given three-day tasks "d, w, c" from "2026-09-10" on the plan, weekend-shift and continuous calendars
    Then "d" runs "2026-09-10" to "2026-09-14"
    And "w" starts "2026-09-12"
    And "c" runs "2026-09-10" to "2026-09-12"

  # ---- where the chart is framed when it is first drawn ----------------------------------------

  Scenario: Almost nothing is drawn before the first bar
    # A day, so the bar does not sit on the axis line.
    Given a one-task plan of 28 days
    Then the chart range leads the first bar by 1 day

  Scenario: The lead-in is a sliver of the width
    # Rather than the quarter of it that a week each side came to. This
    # is the number the complaint was actually about.
    Given a one-task plan of 28 days
    Then the lead-in is under 6 percent of the width

  Scenario: There is room after the last bar for its label
    # Every bar is labelled to its right, including the last one.
    Given a one-task plan of 28 days
    Then the chart range trails the last bar by at least 4 days

  Scenario: A long plan gets proportionally more room after it
    # A day is fewer pixels the longer the plan, so a label needs more
    # of them - not the fixed few a short plan does.
    Then a 365-day plan trails further than a 10-day plan

  Scenario: The lead-in does not grow with the plan
    # It is there to keep the bar off the axis, and that is all.
    Then the lead-in stays 1 day for plans of 10, 100 and 365 days

  Scenario: An empty plan still gives a range
    # The chart has to draw something before there is anything in it.
    Then the chart range for no tasks is still a range

  # ---- the reference behind the task editor's Help button ---------------------------------------
  # It used to explain the form's older half - dates, milestones,
  # progress, colour - and say nothing about the fields that decide
  # where a task actually lands. Somebody asking "why did this finish
  # there" found nothing.

  Scenario: It covers every field on the form
    # A box with nothing said about it is the one being looked up.
    Then the editor reference mentions "type, start date, end date, duration, is milestone, constraint, working calendar, progress, priority, show in timeline, shape, colour, details"

  Scenario: It says how the dates are worked out
    # Which was the largest thing missing from it.
    Then the editor reference mentions "walked, not added, working, calendar days, change the duration, change the end, change the start, start no earlier than"

  Scenario: It explains the working calendar and its priority
    # All four rules, in the order they are read.
    Then the editor reference mentions "manual override, public holiday, working week, highest priority"

  Scenario: It explains a shaded box
    # The commonest "is this broken" question about the form. A shaded
    # field is one the application is filling in, and nothing on the
    # form itself says so.
    Then the editor reference mentions "shaded"

  Scenario: Its worked examples are true
    # The reference is read while the form is open, so a wrong example
    # is acted on immediately.
    Then 5 working days from "2026-09-03" land on "2026-09-09", a Wednesday
    And three-day tasks "d, w, c" from "2026-09-10" end "2026-09-14", start "2026-09-12" and end "2026-09-12"

  # ---- the date header: a month band and a cell per day --------------------------------------------
  # The axis stays linear in calendar days. Dropping the non-working
  # columns is what most calendar strips do and cannot be done here: a
  # task may follow a calendar of its own, so a 24/7 task genuinely
  # works Saturdays and would have nowhere to be drawn.

  Scenario: A month of plan gets a cell for every day
    # Which is the whole look: 1, 2, 3, 4 rather than one date a week.
    Given a strip plan of 24 days
    When the chart is laid out at 1400px
    Then the header mode is "day"
    And there are more than 20 day cells

  Scenario: The cells carry the day number alone
    # The month and the year are in the band above. That is what lets a
    # cell be about 22px wide where a full date needed 82.
    Given a strip plan of 24 days
    When the chart is laid out at 1400px
    Then every day cell is a bare day number

  Scenario: The band names every month the plan touches
    # Or a bare 17 has nothing to say which 17 it is.
    Given a strip plan of 24 days
    When the chart is laid out at 1400px
    Then the month bands read "AUGUST 2026, SEPTEMBER 2026"

  Scenario: The cells run edge to edge without gaps
    # A strip with holes in it reads as a broken grid.
    Given a strip plan of 24 days
    When the chart is laid out at 1400px
    Then the day cells run edge to edge

  Scenario: Non-working days are marked
    # Shading is what carries "not worked" now the letters are gone.
    Given a strip plan of 24 days
    When the chart is laid out at 1400px
    Then the cells mark working and non-working days alike

  Scenario: A weekend is still given a column
    # The axis stays linear: a task on a 24/7 calendar works Saturdays,
    # and an override exists to make one particular Saturday worked.
    Given a strip plan of 24 days
    When the chart is laid out at 1400px
    Then every non-working cell still has width

  Scenario: Today is picked out
    # The reference highlights it, and nothing used to.
    Given a strip plan of 10 days around today
    When the chart is laid out at 1400px
    Then exactly 1 cell is flagged today

  Scenario: A plan outside today marks nothing
    # The tint is a fact about the plan, not decoration.
    Given a strip plan of 24 days from "2031-01-06"
    When the chart is laid out at 1400px
    Then no cell is flagged today

  Scenario: Week starts are flagged
    # They carry the heavier rule that gives the strip its rhythm.
    Given a strip plan of 24 days
    When the chart is laid out at 1400px
    Then the week-start flags match the date ticks

  Scenario: A long plan falls back through the units
    # A cell that cannot be read is worse than a coarser one.
    Given a strip plan
    Then these plans get these header modes
      | days | width | mode    |
      | 24   | 1400  | day     |
      | 120  | 1400  | week    |
      | 400  | 1400  | month   |
      | 1200 | 900   | quarter |
      | 3000 | 900   | half    |
      | 8000 | 900   | year    |

  Scenario: Coarse cells name their unit
    # A month cell reads Sep, a quarter reads Q3 - the year is above.
    Given a strip plan
    Then a 400-day plan at 1400px names cells "Aug, Sep, Oct"
    And a 1200-day plan at 900px names every cell starting "Q"

  Scenario: The band carries years once the cells do not
    # Months under years is the two-line header the issue asked for.
    Given a strip plan
    Then a 400-day plan at 1400px carries bands "2026, 2027"

  Scenario: A band that cannot fit its label shortens it
    # SEPTEMBER 2026 down to SEP - an empty band is the last resort.
    Then a band for "2026-09-01" fits 200px as "SEPTEMBER 2026"
    And a band for "2026-09-01" fits 95px as "SEP 2026"
    And a band for "2026-09-01" fits 45px as "SEP"
    And a band for "2026-09-01" in 20px is left blank

  Scenario: The year floor still names its bands
    # The coarsest header is a row of years, not a blank strip.
    Given a strip plan
    Then an 8000-day plan at 900px has no cells and names its bands

  Scenario: The month band survives every mode
    # It is what says where in the calendar the chart is.
    Given a strip plan
    Then these plans still carry a month band
      | days | width |
      | 24   | 1400  |
      | 120  | 1400  |
      | 1200 | 900   |

  Scenario: Both renderers draw it
    # The PIL image and the SVG share the layout, not the drawing.
    Given a strip plan of 24 days
    Then the svg names "AUGUST 2026" and the image draws

  Scenario: The header colours come from the settings
    # So the export keeps the light ones however dark the window is.
    # screen_settings swaps them for the appearance; the exporters go
    # through current_settings and do not.
    Then the header colours match the default settings
