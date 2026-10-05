Feature: The working-day calendar and the rules built on it
  Two things are pinned down here, and they are easy to confuse:

    * Working days  - the effort a task holds. Unchanged by a weekend.
    * Calendar days - how far apart its two ends sit. Stretched by one.

  Everything below is a statement about one or the other. Nothing here
  needs a display. Dates are chosen so the weekday matters and is named
  in the comment, because "2026-01-03" tells a later reader nothing on
  its own.

  # ---- which days the standard calendar works -------------------------------------------

  Scenario: Weekdays are worked
    Given the standard week
    Then "2026-01-05" through "2026-01-09" are all worked

  Scenario: The weekend is not
    Given the standard week
    Then "2026-01-03" is not worked
    And "2026-01-04" is not worked

  Scenario: A datetime is read the same way
    # The models hold datetimes, so those have to answer too.
    Given the standard week
    Then "2026-01-03 14:30" is not worked
    And "2026-01-05 14:30" is worked

  Scenario: A holiday is not worked
    # A listed date is not a working day whatever weekday it is.
    Given a calendar with a holiday on "2026-01-06"
    Then "2026-01-06" is not worked
    And "2026-01-07" is worked

  Scenario: A recurring holiday applies every year
    # A fixed-date national holiday need not be listed per year.
    Given a calendar with a recurring holiday on "3-15"
    Then "2026-03-15" is not worked
    And "2031-03-15" is not worked

  Scenario: A different week can be declared
    # A plan working Sunday to Thursday is a plan the calendar allows:
    # Friday and Saturday are the days off.
    Given a calendar resting on weekdays "4, 5"
    Then "2026-01-02" is not worked
    And "2026-01-04" is worked

  Scenario: A week with no working day does not hang
    # A calendar working nothing degrades to plain calendar days.
    # Every loop looks for the next working day, so a week with none
    # would run to the step limit on every date in a redraw. Answering
    # "every day" instead is wrong but finite, and it is logged.
    Given a calendar resting on weekdays "0, 1, 2, 3, 4, 5, 6"
    Then "2026-01-03" is worked
    And 3 working days from "2026-01-01" land on "2026-01-03"

  # ---- a task cannot start on a day nobody works ------------------------------------------------

  Scenario: A weekend start moves to the Monday
    # Saturday and Sunday both push forward.
    Given the standard week
    Then the next working day after "2026-01-03" is "2026-01-05"
    And the next working day after "2026-01-04" is "2026-01-05"

  Scenario: A working start is left alone
    Given the standard week
    Then the next working day after "2026-01-06" is "2026-01-06"

  Scenario: It steps over a holiday too
    # A Monday holiday pushes the start to the Tuesday.
    Given a calendar with a holiday on "2026-01-05"
    Then the next working day after "2026-01-03" is "2026-01-06"

  Scenario: The previous working day is the mirror
    # Backwards, for a plan that works from its finish date.
    Given the standard week
    Then the previous working day before "2026-01-04" is "2026-01-02"

  Scenario: A datetime keeps its time of day
    # Only the date decides; the time is carried through untouched.
    Given the standard week
    Then the next working moment after "2026-01-03 09:15" is "2026-01-05 09:15"

  # ---- turning a working duration into an inclusive finish date -------------------------------------

  Scenario: A span inside one week
    # Five days from a Monday ends on the Friday.
    Given the standard week
    Then 5 working days from "2026-01-05" land on "2026-01-09"

  Scenario: One day ends where it starts
    # A day-long task does not spill onto a second day.
    Given the standard week
    Then 1 working day from "2026-01-05" lands on "2026-01-05"

  Scenario: A weekend is crossed without spending duration
    # The rule the whole module exists for: five days from a Thursday
    # run Thursday, Friday, Monday, Tuesday, Wednesday. Adding four
    # calendar days instead finished on the Monday, having spent two
    # days of the task on a Saturday and a Sunday.
    Given the standard week
    Then 5 working days from "2026-01-01" land on "2026-01-07"

  Scenario: A long task crosses several weekends
    # Twenty days of work from a Monday is four weeks of calendar.
    Given the standard week
    Then 20 working days from "2026-01-05" land on "2026-01-30"

  Scenario: A weekend start is pushed before counting
    # Three days from a Saturday run Monday to Wednesday.
    Given the standard week
    Then 3 working days from "2026-01-03" land on "2026-01-07"

  Scenario: A holiday extends the finish
    # A holiday inside the span is not worked and not counted.
    Given a calendar with a holiday on "2026-01-07"
    Then 3 working days from "2026-01-05" land on "2026-01-08"

  Scenario: No duration leaves the date alone
    # A milestone takes no time, so it finishes where it starts.
    Given the standard week
    Then 0 working days from "2026-01-05" land on "2026-01-05"

  Scenario: Working backwards is the mirror
    # The start a finish and a duration imply.
    Given the standard week
    Then 5 working days back from "2026-01-07" land on "2026-01-01"

  # ---- reading a pair of dates back as effort and as elapsed time -------------------------------------

  Scenario: Working days ignore the weekend
    # Thursday to the following Wednesday holds five days of work.
    Given the standard week
    Then "2026-01-01" to "2026-01-07" holds 5 days of work

  Scenario: Elapsed days do not
    # The same span is seven days of calendar, which is what is drawn.
    Given the standard week
    Then "2026-01-01" to "2026-01-07" spans 7 days

  Scenario: A span of one day
    # Both measures agree on a single working day.
    Given the standard week
    Then "2026-01-05" to "2026-01-05" holds 1 day of work
    And "2026-01-05" to "2026-01-05" spans 1 day

  Scenario: A weekend-only span holds no work
    # A "task" occupying only a Saturday and a Sunday is not work.
    Given the standard week
    Then "2026-01-03" to "2026-01-04" holds 0 days of work

  Scenario: A backwards span holds no work
    # An end before the start counts nothing rather than going negative.
    Given the standard week
    Then "2026-01-07" to "2026-01-01" holds 0 days of work

  Scenario: Measuring and adding agree
    # The two directions are consistent, which is what makes
    # rescheduling stable: measuring a span and adding it back lands
    # on the same day, so a task settled once does not creep every
    # time the plan is rescheduled.
    Given the standard week
    Then measuring and adding agree for 40 days from "2026-01-01"

  # ---- a calendar survives being saved and loaded ------------------------------------------------------

  Scenario: A round trip keeps every day
    # The week, the holidays and the recurring ones all come back.
    Given a calendar resting on weekdays "4, 5" with a holiday on "2026-01-06" and recurring holidays "3-15, 8-20"
    Then it round-trips through a save

  Scenario: A missing calendar is the standard week
    # A file saved before projects carried one opens Monday to Friday.
    Then a missing calendar loads as the standard week
    And an empty calendar loads as the standard week

  Scenario: A damaged calendar falls back rather than raising
    # Junk in the file loads as the standard week; opening it matters
    # more than the entries.
    Then a damaged calendar loads on weekdays "5, 6" with a holiday on "2026-01-06" and a recurring holiday "8-20"

  Scenario: A project carries its calendar through a save
    # The plan's own week is part of the plan.
    Given a project named "Imported" on a calendar with a holiday on "2026-01-06"
    When it is saved and reloaded
    Then the reloaded calendar matches

  Scenario: A project saved without one opens on the standard week
    # Older files have no calendar block at all.
    Given a saved project with no calendar block
    Then it loads on the standard week

  # ---- the rules with nothing else attached --------------------------------------------------------------
  # The worked examples from the specification, kept as tests so the
  # documented behaviour and the code cannot part company.

  Scenario: A calendar task crossing a weekend
    # Five days from Thursday 10 September 2026 ends on the Wednesday.
    Given a calendar task "Backend API" of 5 days from "2026-09-10"
    Then it effectively starts "2026-09-10"
    And it ends "2026-09-16"
    And it holds 5 days and spans 7

  Scenario: A calendar task starting on a Saturday
    # It begins on the Monday and its three days run to the Wednesday.
    Given a calendar task "Database Migration" of 3 days from "2026-09-12"
    Then it effectively starts "2026-09-14"
    And it ends "2026-09-16"

  Scenario: It uses the standard week unless given one
    # A task built without a calendar still knows about weekends.
    Given a calendar task "Anything" of 1 day from "2026-09-12"
    Then its calendar is the standard one

  # ---- what a Task answers about its own length -------------------------------------------------------------

  Scenario: A task inside one week
    # Monday to Friday is five days of work in five days of calendar.
    Given a task "T" from "2026-01-05" to "2026-01-09"
    Then it holds 5 days and spans 5

  Scenario: A task crossing a weekend
    # The two measures part company, which is the point of having both.
    Given a task "T" from "2026-01-01" to "2026-01-07"
    Then it holds 5 days and spans 7

  Scenario: A task on a weekend is still a day long
    # A span holding no work reads as one day rather than none.
    # Nothing in the application can show a task of nought days
    # sensibly; enforce_working_calendar moves it off.
    Given a task "T" from "2026-01-03" to "2026-01-04"
    Then it holds 1 day

  Scenario: A milestone has no length
    # A milestone marks a moment.
    Given a milestone "T" on "2026-01-05"
    Then it holds 0 days and spans 0

  Scenario: An effective start skips the weekend
    # A task placed on a Saturday works from the Monday.
    Given a task "T" from "2026-01-03" to "2026-01-09"
    Then it effectively starts "2026-01-05 00:00"

  # ---- enforcing the calendar on a plan ------------------------------------------------------------------------

  Scenario: A weekend start is moved to the Monday
    # Rule four: a task cannot start on a day nobody works.
    Given an enforcement project holding "A" from "2026-01-03" to "2026-01-08"
    When the calendar is enforced
    Then "A" starts "2026-01-05"
    And the enforcement moved something

  Scenario: The working duration is kept when the start moves
    # Saturday to Thursday holds four days of work - Monday to
    # Thursday - so starting on the Monday it still holds four,
    # ending on the Thursday.
    Given an enforcement project holding "A" from "2026-01-03" to "2026-01-08"
    When the calendar is enforced
    Then "A" starts "2026-01-05"
    And "A" ends "2026-01-08"
    And task "A" holds 4 days of work

  Scenario: A finish on a weekend is pulled back
    # Monday to Sunday holds five days of work, so it ends on Friday.
    Given an enforcement project holding "A" from "2026-01-05" to "2026-01-11"
    When the calendar is enforced
    Then "A" ends "2026-01-09"
    And task "A" reads 5 days by duration

  Scenario: A stated duration is honoured
    # A task carrying its own duration is stretched to match it.
    Given an enforcement project holding "A" from "2026-01-01" to "2026-01-02" with duration 5
    When the calendar is enforced
    Then "A" ends "2026-01-07"

  Scenario: A task already on working days is left alone
    # Nothing moves, and it says so.
    Given an enforcement project holding "A" from "2026-01-05" to "2026-01-09"
    Then the enforcement changes nothing

  Scenario: Running it twice changes nothing
    # It has to be idempotent: it runs inside the reschedule loop,
    # which repeats until nothing moves. A pass that moved a task
    # every time would never settle.
    Given an enforcement project holding "A" from "2026-01-03" to "2026-01-11"
    When the calendar is enforced
    Then the enforcement changes nothing

  Scenario: A milestone moves off the weekend keeping its moment
    # A milestone is a date, and it has to be a date somebody works.
    Given an enforcement project holding a milestone "M" on "2026-01-04"
    When the calendar is enforced
    Then "M" starts "2026-01-05"
    And "M" ends "2026-01-05"

  Scenario: A container takes its dates from its children
    # A Phase is not moved directly - its dates are rolled up from
    # the work inside it, which enforcement has already put on
    # working days.
    Given an enforcement project holding phase "P" and child "C" astride a weekend
    When the calendar is enforced
    Then "P" starts "2026-01-03"
    When the plan is rescheduled
    Then "P" starts "2026-01-05"
    And "P" ends "2026-01-09"

  Scenario: A holiday calendar is respected
    # The project's own calendar is the one enforced, not the
    # standard week: a holiday on the Tuesday stretches the task.
    Given an enforcement project with a holiday on "2026-01-06"
    And it holds "A" from "2026-01-05" to "2026-01-07" with duration 3
    When the calendar is enforced
    Then "A" ends "2026-01-08"

  # ---- public holidays, taken from whichever countries the plan observes --------------------------------------
  # The dates asserted here are real national holidays, chosen because
  # they exercise the three things a hand-written list gets wrong: one
  # country having a holiday another does not, a movable Easter feast,
  # and the union across several countries. These need the holidays
  # package.

  @holiday_package
  Scenario: A fixed national holiday is not worked
    # 23 October is Hungary's national day, and a Friday in 2026.
    Given a calendar observing "HU"
    Then "2026-10-23" is not worked
    And "2026-10-22" is worked

  @holiday_package
  Scenario: A movable Easter holiday is not worked
    # Easter Monday moves every year and is never listed anywhere.
    # This is why the holidays package is asked rather than a table
    # being kept: computing the paschal full moon per country per
    # year is not something to reimplement.
    Given a calendar observing "DE"
    Then "2026-04-06" is not worked
    And "2027-03-29" is not worked

  @holiday_package
  Scenario: Countries are merged as a union
    # A holiday in any selected country is a holiday for the plan.
    # Epiphany is a public holiday in Austria and an ordinary working
    # day in Hungary, so a plan worked in both cannot count on it.
    Given a calendar observing "HU"
    And a second calendar observing "HU, AT"
    Then "2026-01-06" is worked on the first
    And "2026-01-06" is not worked on the second

  @holiday_package
  Scenario: A holiday lengthens a task without lengthening its duration
    # Ten days of work from Monday 30 March run to the Friday of the
    # second week. In Hungary they reach the Tuesday after it:
    # Good Friday and Easter Monday fall inside the span.
    Given the standard week
    And a second calendar observing "HU"
    Then 10 working days from "2026-03-30" land on "2026-04-10"
    And 10 working days from "2026-03-30" land on "2026-04-14" on the second

  @holiday_package
  Scenario: A start on a holiday moves to the next working day
    # New Year's Day 2026 is a Thursday, Hungary takes the Friday
    # with it, and the weekend follows - so work begins on the Monday.
    Given a calendar observing "HU"
    Then the next working day after "2026-01-01" is "2026-01-05"

  @holiday_package
  Scenario: Selecting no countries leaves weekends alone
    # Clearing the list is a plan on weekends only.
    Given a calendar observing nobody
    Then "2026-10-23" is worked
    And "2026-03-30" to "2026-04-10" holds 10 days of work

  @holiday_package
  Scenario: The countries can be changed afterwards
    # Applying a new selection takes effect at once.
    Given the standard week
    Then "2026-01-06" is worked
    When the calendar observes "AT"
    Then "2026-01-06" is not worked

  @holiday_package
  Scenario: Changing the countries clears what was worked out
    # The cached year is dropped, not reused. Holidays are resolved a
    # year at a time and kept, because is_working_day runs for every
    # day of every task on every redraw. A cache that survived a
    # change of country would answer for the old selection forever.
    Given a calendar observing "AT"
    Then "2026-01-06" is not worked
    When the calendar observes "HU"
    Then "2026-01-06" is worked

  @holiday_package
  Scenario: Every EU country resolves
    # All 27 are known to the package; none of them is a typo here.
    Then every EU country resolves for 2026

  @holiday_package
  Scenario: The selection survives a save
    # The codes are saved, so a plan reopened next year still knows.
    Given a project named "EU" on a calendar observing "HU, DE"
    When it is saved and reloaded
    Then the reloaded calendar observes "HU, DE"
    And "2026-04-06" is not worked on the reloaded

  @holiday_package
  Scenario: A holiday pushes a scheduled task out
    # The whole point: the plan moves when the calendar does. Good
    # Friday and Easter Monday appearing inside the task push its
    # finish from the Friday to the Tuesday rather than costing it
    # two days of what it holds.
    Given a project named "EU" holding "A" from "2026-03-30" to "2026-04-10"
    When the plan is rescheduled
    Then "A" ends "2026-04-10"
    When the plan observes "HU"
    Then "A" ends "2026-04-14"
    And task "A" holds 10 days of work

  @holiday_package
  Scenario: Dropping a country pulls the plan back in
    # The change is undoable by making the opposite change.
    Given a project named "EU" observing "HU" holding "A" from "2026-03-30" to "2026-04-14"
    When the plan is rescheduled
    And the plan observes nobody
    Then "A" ends "2026-04-10"
    And task "A" holds 10 days of work

  @holiday_package
  Scenario: A milestone moves off a holiday
    # A date nobody works is not a date to mark something on.
    Given a project named "EU" holding a milestone "M" on "2026-04-06"
    When the plan observes "DE"
    Then "M" starts "2026-04-07"
    And "M" ends "2026-04-07"

  # ---- the optional dependency being absent costs holidays, not the plan ----------------------------------------
  # A wrong holiday list is worth less than a project that will not
  # open, so a missing package is logged once and the calendar carries
  # on with weekends.

  Scenario: An unresolvable country is simply not observed
    # Nothing raises, and the weekend rule still applies.
    Given a calendar observing "HU" that cannot resolve any
    Then "2026-03-16" is worked
    And "2026-03-14" is not worked
    And 10 working days from "2026-03-09" land on "2026-03-20"

  Scenario: An unknown country code is skipped
    # One bad code in a saved file costs that country, not the plan.
    Then "ZZ" resolves to no holidays for 2026

  Scenario: The selection is still saved
    # A plan carrying countries is not silently emptied without them.
    Given a calendar observing "HU, DE"
    Then its country list round-trips

  # ---- the rulings that beat every other rule ------------------------------------------------------------------
  # The whole point of an override is that it wins, so most of what is
  # worth pinning down here is which of two disagreeing rules the
  # calendar picks - not that the override is stored, which is a dict.

  Scenario: A Saturday can be made a working day
    # The make-up day: the case the feature exists for.
    Given the standard week
    Then "2026-09-12" is not worked
    When "2026-09-12" is ruled worked as "Make-up day"
    Then "2026-09-12" is worked

  Scenario: A weekday can be made a non-working day
    # The shutdown: a Tuesday nobody is in.
    Given the standard week
    Then "2026-09-15" is worked
    When "2026-09-15" is ruled off as "Team building"
    Then "2026-09-15" is not worked

  Scenario: An override beats a listed holiday
    # Someone typing a date into the overrides list can see it is a
    # holiday. Letting the holiday win would make the entry
    # impossible to act on.
    Given a calendar with a holiday on "2026-12-28"
    Then "2026-12-28" is not worked
    When "2026-12-28" is ruled worked as "Working through"
    Then "2026-12-28" is worked

  Scenario: An override beats a recurring holiday
    # The same, for the ones listed once and applied every year.
    Given a calendar with a recurring holiday on "8-20"
    Then "2026-08-20" is not worked
    When "2026-08-20" is ruled worked
    Then "2026-08-20" is worked

  @holiday_package
  Scenario: An override beats a country holiday
    # And the ones a country's calendar works out for itself.
    Given a calendar observing "HU"
    Then "2026-08-20" is not worked
    When "2026-08-20" is ruled worked as "Skeleton crew"
    Then "2026-08-20" is worked

  Scenario: One date holds one ruling
    # Overriding a date twice replaces it rather than stacking.
    Given the standard week
    When "2026-09-12" is ruled worked as "Make-up day"
    And "2026-09-12" is ruled off as "Cancelled again"
    Then the calendar holds 1 ruling
    And "2026-09-12" is not worked

  Scenario: A datetime is overridden by its date
    # The models hold datetimes; a ruling names a day, not a moment.
    Given the standard week
    When "2026-09-12 09:30" is ruled worked
    Then "2026-09-12 17:00" is worked
    And the rulings are listed as "2026-09-12"

  Scenario: Removing a ruling restores the ordinary rules
    # A deleted override leaves no trace on the date it covered.
    Given the standard week
    And "2026-09-12" was ruled worked
    Then removing the "2026-09-12" ruling answers yes
    And "2026-09-12" is not worked
    And removing the "2026-09-12" ruling answers no

  Scenario: The reason is carried but takes no part
    # It is for the reader, not the arithmetic.
    Given the standard week
    And "2026-09-12" was ruled worked as "Saturday make-up day"
    Then the ruling for "2026-09-12" reads "Saturday make-up day"
    And "2026-09-19" has no ruling

  Scenario: A non-working ruling survives a broken week
    # An empty week is treated as working every day, but not over a
    # ruling. The fallback exists so a corrupt calendar cannot hang a
    # redraw; a date the user named as not worked is not part of that
    # breakage.
    Given a calendar resting on weekdays "0, 1, 2, 3, 4, 5, 6"
    When "2026-09-15" is ruled off as "Shutdown"
    Then "2026-09-15" is not worked
    And "2026-09-16" is worked

  # ---- what a ruling does to the dates --------------------------------------------------------------------------

  Scenario: A worked Saturday pulls a finish in
    # Two days from a Friday end on the Saturday, not the Monday.
    Given the standard week
    Then 2 working days from "2026-09-11" land on "2026-09-14"
    When "2026-09-12" is ruled worked as "Make-up day"
    Then 2 working days from "2026-09-11" land on "2026-09-12"

  Scenario: A shutdown pushes a finish out
    # The work does not go away; the finish moves.
    Given the standard week
    Then 3 working days from "2026-09-14" land on "2026-09-16"
    When "2026-09-15" is ruled off as "Team building"
    Then 3 working days from "2026-09-14" land on "2026-09-17"

  Scenario: A task may start on an overridden Saturday
    # A start pushed off the weekend has nowhere to be pushed to.
    Given the standard week
    When "2026-09-12" is ruled worked as "Make-up day"
    Then the next working day after "2026-09-12" is "2026-09-12"

  Scenario: A span counts an overridden Saturday as work
    # Measured back the same way it was laid out.
    Given the standard week
    When "2026-09-12" is ruled worked
    Then "2026-09-11" to "2026-09-14" holds 3 days of work

  Scenario: The project keeps the work and moves the finish
    # End to end: a shutdown pushes a task out without shortening it.
    # This is why set_date_overrides goes through apply_calendar.
    Given a project named "Shutdown" holding "A" from "2026-09-07" to "2026-09-18"
    When the plan is rescheduled
    Then task "A" holds 10 days of work
    When "2026-09-15" is ruled off as "Team building" on the plan
    Then task "A" holds 10 days of work
    And "A" ends "2026-09-21"

  Scenario: Setting overrides leaves the countries alone
    # The two halves of the dialog do not overwrite each other.
    Given a project named "Both" observing "HU"
    When "2026-09-12" is ruled worked on the plan
    Then the plan's calendar still observes "HU"
    And "2026-09-12" is worked on the plan

  Scenario: Setting countries leaves the overrides alone
    # And the same the other way round.
    Given a project named "Both"
    And "2026-09-12" was ruled worked on the plan
    When the plan observes "HU"
    Then "2026-09-12" is worked on the plan
    And the plan's calendar holds 1 ruling

  # ---- a ruling has to survive being saved and reopened ----------------------------------------------------------

  Scenario: A ruling round-trips
    # Date, type and reason all come back.
    Given the standard week
    And "2026-09-12" was ruled worked as "Make-up day"
    And "2026-09-15" was ruled off as "Team building"
    When the calendar is saved and reloaded
    Then the reloaded calendar equals it
    And "2026-09-12" is worked on the reloaded
    And "2026-09-15" is not worked on the reloaded
    And the reloaded ruling for "2026-09-12" reads "Make-up day"

  Scenario: Rulings are saved in date order
    # A stable order, so a file does not churn between saves.
    Given the standard week
    When "2026-09-15" is ruled worked
    And "2026-01-03" is ruled worked
    And "2026-12-25" is ruled worked
    Then the saved rulings list "2026-01-03, 2026-09-15, 2026-12-25"

  Scenario: A calendar saved before overrides still opens
    # An older project file has no overrides block at all.
    Then a calendar dict of countries "HU" holds no rulings

  Scenario: One damaged ruling does not cost the rest
    # A bad row is dropped with a line in the log, not raised.
    Then a damaged overrides list keeps the good row "2026-09-12"

  Scenario: Calendars differing only in a ruling are not equal
    # Or applying one would look like a no-op and never redraw.
    Given the standard week
    And a second standard week ruled worked on "2026-09-12"
    Then the two calendars differ

  # ---- changing which weekdays are worked at all ------------------------------------------------------------------

  Scenario: A six-day week pulls a finish in
    # The work does not grow; the finish moves. Four days of work
    # from a Friday reach the Wednesday on a five-day week; once
    # Saturday is worked the same four days reach the Tuesday.
    Given a four-day task on the standard week
    Then task "A" holds 4 days of work
    And "A" ends "2026-09-16"
    When the week rests on "6"
    Then the week's answer was taken
    And task "A" holds 4 days of work
    And "A" ends "2026-09-15"

  Scenario: A four-day week pushes a finish out
    # And the other direction.
    Given a four-day task on the standard week
    When the week rests on "4, 5, 6"
    Then task "A" holds 4 days of work
    And "A" ends "2026-09-17"

  Scenario: The new week is what the calendar answers
    # A Saturday put to work is a working day.
    Given a four-day task on the standard week
    When the week rests on "6"
    Then "2026-09-12" is worked on the plan
    And "2026-09-13" is not worked on the plan

  Scenario: A week with no working day is refused
    # The calendar would take it, and answer with seven working days.
    # That fallback keeps a corrupt file from hanging the scheduler;
    # it is not an answer to somebody asking for it, so the ask is
    # refused and the calendar left alone.
    Given a four-day task on the standard week
    When the week rests on "0, 1, 2, 3, 4, 5, 6"
    Then the week's answer was refused
    And the plan's calendar still rests on "5, 6"

  Scenario: Setting the week leaves the countries and rulings alone
    # The three tabs do not overwrite each other.
    Given a four-day task on the standard week
    And the plan observes "HU"
    And "2026-09-13" was ruled worked on the plan
    When the week rests on "6"
    Then the plan's calendar still observes "HU"
    And the plan's calendar holds 1 ruling
    And the plan's calendar still rests on "6"

  Scenario: An override still outranks the new week
    # A day named as not worked stays not worked, whatever the week.
    Given a four-day task on the standard week
    And "2026-09-12" was ruled off as "Not this one" on the plan
    When the week rests on "6"
    Then "2026-09-12" is not worked on the plan

  Scenario: The week survives being saved and reopened
    # A plan on a six-day week is still on one when it comes back.
    Given a four-day task on the standard week
    When the week rests on "6"
    And it is saved and reloaded
    Then the reloaded calendar rests on "6"
    And "2026-09-12" is worked on the reloaded

  # ---- the working week is not rebuilt every time ------------------------------------------------------------------
  # works_any_weekday is asked before every other rule in
  # is_working_day. One chart redraw on a large plan calls it over two
  # hundred thousand times, so the answer is cached; these are the
  # ways it could go stale.

  Scenario: The standard week works some weekday
    # The plain case, which the cache must not get wrong.
    Given the standard week
    Then the calendar works some weekday

  Scenario: A week with nothing in it does not
    # The guard the whole property exists for.
    Given a calendar resting on weekdays "0, 1, 2, 3, 4, 5, 6"
    Then the calendar works no weekday

  Scenario: Assigning a new week is noticed
    # Which is how the settings dialog changes it.
    Given the standard week
    Then the calendar works some weekday
    When the calendar rests on "0, 1, 2, 3, 4, 5, 6"
    Then the calendar works no weekday

  Scenario: Assigning back is noticed too
    # A cache that only invalidates one way is still a stale cache.
    Given a calendar resting on weekdays "0, 1, 2, 3, 4, 5, 6"
    Then the calendar works no weekday
    When the calendar rests on "5, 6"
    Then the calendar works some weekday

  Scenario: Mutating the set in place is noticed
    # The way round the setter, which a length check catches.
    # Nothing in the application does this today; a cache that
    # silently answers for last week's calendar is a bad way to find
    # out something started.
    Given the standard week
    Then the calendar works some weekday
    When every weekday is added to the rest days in place
    Then the calendar works no weekday

  Scenario: Removing a day in place is noticed
    # The same, the other way.
    Given a calendar resting on weekdays "0, 1, 2, 3, 4, 5, 6"
    Then the calendar works no weekday
    When weekday 0 is taken off the rest days in place
    Then the calendar works some weekday

  Scenario: The week still reads back
    # It is a property now, and everything reads it as a set.
    Given a calendar resting on weekdays "5, 6"
    Then the calendar rests on "5, 6"
    And its saved form lists "5, 6"

  Scenario: An iterable is taken as well as a set
    # The setter normalises, as the constructor always did.
    Given the standard week
    When the calendar rests on the list "0, 1, 1"
    Then the calendar rests on "0, 1"

  Scenario: Scheduling is unchanged
    # The cache is only worth having while the answers are the same.
    Given the standard week
    Then "2026-09-11" is worked
    And "2026-09-12" is not worked
    And 2 working days from "2026-09-11" land on "2026-09-14"

  # ---- which region each country is listed under in the picker ------------------------------------------------
  # The table is 249 codes written out by hand, and the failure it
  # invites is a country quietly left out of it. That country would
  # still appear in the picker - region_of falls back rather than
  # dropping it - but it would appear under Other Territories, at the
  # bottom, where nobody looking for it would think to look. So the
  # table is checked against the package's own list rather than
  # against anything written here.

  Scenario: Every country is placed
    # Nothing falls through to the fallback by accident. This is the
    # test that fires when the holidays package adds a country - it
    # caught Kosovo on a machine with a newer version than the table
    # was written against.
    Then every country the package knows is placed

  Scenario: Every code in the table is shaped like one
    # A guard against a typo, checked by shape rather than by lookup:
    # the table is allowed to be ahead of the package, so it is not
    # looked up - a mistyped code means some real country is no longer
    # named, and "every country is placed" catches that.
    Then every code in the table is two capitals

  Scenario: Every region named is one of the regions listed
    # The order the picker walks has to reach all of them.
    Then every region named is in the order

  Scenario: Every region has somebody in it
    # A heading that can never appear is a heading worth deleting.
    Then every region in the order has a country

  Scenario: A subdivision is placed by its country
    # Bavaria is in Europe because Germany is.
    Then "DE-BY" sits in "Europe Region"
    And "DE" sits where "DE-BY" sits

  Scenario: An unknown code falls back rather than raising
    # The holidays package gains countries between releases. One
    # arriving in an odd group is a great deal better than one
    # vanishing from a list somebody is choosing from.
    Then "ZZ" sits in "Other Territories"
    And a blank code sits in "Other Territories"
    And a missing code sits in "Other Territories"

  Scenario: A lowercase code is still found
    # Codes are upper case here and not everywhere they come from.
    Then "de" sits where "DE" sits

  Scenario: The EU members are all in Europe
    # A cheap check on the largest group anyone will look at.
    Then every EU member sits in "Europe Region"

  # ---- measuring edge cases and the calendar's own description -------------------------------

  Scenario: Asking for no days back keeps the day asked
    Given the standard week
    Then 0 working days back from "2026-01-09" land on "2026-01-09"

  Scenario: A calendar is not equal to what it is not
    Given the standard week
    Then it is not a string

  Scenario: The calendar describes itself
    Given the standard week
    Then its description lists its resting days
