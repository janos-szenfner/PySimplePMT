Feature: The Dependencies column's grammar
  "003SS+1d" is how every planning tool has spelt a dependency for thirty
  years, and the column now takes it. That makes the grammar a contract:
  what a reader types, and what is written back into the cell afterwards,
  have to be the same language or the column loses work every time it
  normalises.

  Typing into the grid itself needs a display and stays in the unittest
  module.

  # ---- every row of the token reference, in order ----------------------------------------

  Scenario: A bare number is finish-to-start
    # The default, and by a long way the commonest link.
    When "003" is parsed
    Then it gives 1 link and no errors
    And the link reads as "003" FS lag 0 "days"

  Scenario: A type and a lag in days
    # 003FS+2d.
    When "003FS+2d" is parsed
    Then it gives 1 link and no errors
    And the link reads as "003" FS lag 2 "days"

  Scenario: A negative lag is lead time
    # 003SS-1d, which is how a schedule is compressed.
    When "003SS-1d" is parsed
    Then it gives 1 link and no errors
    And the link reads as "003" SS lag -1 "days"

  Scenario: A type with no lag
    # 003FF.
    When "003FF" is parsed
    Then it gives 1 link and no errors
    And the link reads as "003" FF lag 0 "days"

  Scenario: A lag as a share of the predecessor
    # 003SF+50%, which says "when that one is half done".
    When "003SF+50%" is parsed
    Then it gives 1 link and no errors
    And the link reads as "003" SF lag 50 "percent"

  # ---- the forms a reader will type without being told to --------------------------------

  Scenario: Several links separated by commas
    # The example from the specification.
    When "001, 003SS+1d" is parsed
    Then it gives 2 links and no errors
    And they read as "001" FS lag 0 "days" and "003" SS lag 1 "days"

  Scenario: Semicolons separate them too
    # A plan pasted out of a spreadsheet uses whichever its locale does.
    When "001;003" is parsed
    Then it gives 2 links

  Scenario: The case of the type does not matter
    # Nobody holds shift for this.
    When "3ss" is parsed
    Then the link reads as "3" SS lag 0 "days"

  Scenario: Spaces anywhere sensible
    # A cell that has been read back and edited collects them.
    When " 3 fs + 2 days " is parsed
    Then the link reads as "3" FS lag 2 "days"

  Scenario: A lag with no type
    # 003+2d means Finish-Start with two days on it.
    When "003+2d" is parsed
    Then the link reads as "003" FS lag 2 "days"

  Scenario: A lag with no unit is days
    # Which is what it is everywhere else in the application.
    When "003FS+2" is parsed
    Then the link's unit is "days"

  Scenario: An empty cell is no links rather than an error
    # It is how a cell is cleared.
    Then an empty cell gives no links and no errors
    And "   ,  ; " gives no links and no errors

  # ---- nothing is guessed at, and nothing vanishes without a word ---------------------------

  Scenario: A token it cannot read is reported
    # Rather than dropped. A column where one bad token silently
    # disappears is a column that loses work: three links go in, two come
    # back, no reason given.
    When "abc" is parsed
    Then it gives no links
    And 1 error mentioning "abc"

  Scenario: The message says what the grammar is
    # An error naming only the problem leaves the reader guessing.
    When "003XX" is parsed
    Then an error mentions "003SS+1d"

  Scenario: A lag with no number is refused
    # "003FS+" is half a thought, not a link with no lag.
    When "003FS+" is parsed
    Then it gives no links

  Scenario: The good tokens in a bad cell are still read
    # So the caller can say which part failed.
    When "001, junk, 003" is parsed
    Then it gives 2 links
    And 1 error

  # ---- what the cell shows is what the cell takes ------------------------------------------

  Scenario Outline: Every form survives being written and read
    # The contract the column rests on. A cell is normalised after every
    # edit, so a form that came out differently from how it went in would
    # rewrite the reader's work.
    When a "<dep_type>" link of lag <lag> "<unit>" is written for number 3
    Then it reads back as "3" "<dep_type>" lag <lag> "<unit>"

    Examples:
      | dep_type | lag | unit    |
      | FS       | 0   | days    |
      | FS       | 2   | days    |
      | SS       | -1  | days    |
      | FF       | 0   | days    |
      | SF       | 50  | percent |

  Scenario: A plain link is written as the number alone
    # "003FS" on every ordinary link would be noise.
    Then a plain link writes as "003"

  Scenario: The type comes back when there is a lag
    # "003+2d" reads as if the type had been left out by mistake.
    Then an FS link of lag 2 days writes as "3FS+2d"

  Scenario: Links are written comma-separated
    # Which is what parse splits on.
    Then links to tasks 1 and 3 write as "1, 3SS+1d"

  Scenario: A link to a task that has gone is not written
    # Inventing a number for it would produce a cell parse refuses.
    Then a link to a missing task writes as nothing

  Scenario: The unit survives a saved file
    # A share of a duration is not the same as that many days.
    Then an SF link of lag 50 percent keeps its unit through a save

  Scenario: A link saved before units existed reads as days
    # Which is what every one of them meant.
    Then a saved link with no unit reads as "days"

  # ---- what a number alone cannot answer ----------------------------------------------------
  # A cell can name a task that is not there, name itself, name the same
  # task twice, or close a loop - and a column that quietly dropped any
  # of those would leave the reader comparing what they typed against
  # what came back to notice.

  Scenario: A number becomes the task it names
    # The cell holds the number; the link holds the identity. The number
    # moves when rows move and the identity does not.
    Given a plan of three tasks
    When "third" reads "1"
    Then the links point at "first"

  Scenario: A number naming nothing is refused
    # Typing 9 in a plan of three is a typo, not a link.
    Given a plan of three tasks
    When "third" reads "9"
    Then it gives no links
    And an error mentions "no task 9"

  Scenario: A task cannot depend on itself
    # The specification's self-reference guard.
    Given a plan of three tasks
    When "third" reads "3"
    Then it gives no links
    And an error mentions "itself"

  Scenario: The same task twice is refused
    # One of them would silently replace the other.
    Given a plan of three tasks
    When "third" reads "1, 1"
    Then it gives 1 link
    And an error mentions "more than once"

  Scenario: A loop is refused
    # A plan with a loop cannot be scheduled - every pass moves a task
    # and the next pass moves it back - so it is caught before it is
    # stored.
    Given a plan of three tasks
    And "second" already waits on "third"
    When "third" reads "2"
    Then it gives no links
    And an error mentions "circle"

  Scenario: A loop formed within one cell is refused
    # Typing "1, 2" where 2 already waits for 1 is a loop that only
    # exists once both have been taken - so each is checked against the
    # ones already accepted, not only against what the task holds now.
    Given a plan of three tasks
    And "second" already waits on "third"
    When "third" reads "1, 2"
    Then the links point at "first"
    And an error is given

  Scenario: A task cannot depend on its own subtask
    # Which is a loop through the hierarchy rather than through links.
    Given a plan of three tasks
    And "first" sits under "third"
    When "third" reads the number of "first"
    Then it gives no links
    And an error is given

  Scenario: The plan is left alone by a check that fails
    # The cycle check puts the candidate links on the task to ask about
    # them. A plan left holding a probe's links would be a far worse
    # fault than the one being guarded against.
    Given a plan of three tasks
    When "third" reads "1, 2, 9"
    Then "third" holds the links it always did

  # ---- the engine is unchanged ---------------------------------------------------------------
  # Adding a unit to the lag put a branch in front of every read of it.
  # The whole of the existing plan is in days, so that branch has to be
  # invisible: the scheduler must compute the same dates it always did,
  # and a percentage - which could not previously be stated at all - is
  # the only thing that behaves differently.

  Scenario: A plain link starts the next working day
    # Friday finish, Monday start - the weekend is not worked.
    Given two five-day tasks beginning "2026-08-17"
    When "second" waits on "first"
    Then "second" begins "2026-08-24"

  Scenario: A lag in days is read as days
    # Two working days after, so the Wednesday.
    Given two five-day tasks beginning "2026-08-17"
    When "second" waits on "first" with lag 2 "days"
    Then "second" begins "2026-08-26"

  Scenario: A lead in days pulls it back
    # Negative lag overlaps the two, which is how a plan is compressed.
    Given two five-day tasks beginning "2026-08-17"
    Then a lag of -2 days starts "second" before a plain link does

  Scenario: The days path does not go near the new arithmetic
    # A lag in days is returned untouched, by construction: whatever
    # lag_days does for a percentage, for days it hands back the number
    # the link holds.
    Given two five-day tasks beginning "2026-08-17"
    When "second" waits on "first" with lag 3 "days"
    Then the link's lag days are 3
    And the lag days equal the link's lag

  Scenario: A percentage is a share of the predecessor
    # The share is of the task being waited for - "start this when that
    # one is half done" is a statement about that one.
    Given two five-day tasks beginning "2026-08-17"
    When "second" waits on "first" with lag 50 "percent"
    Then "first" works 5 days
    And the link's lag days are 3

  Scenario: A percentage of nothing delays nothing
    # A link whose predecessor has gone must not stop the redraw.
    Given two five-day tasks beginning "2026-08-17"
    And "second" waits on "first" with lag 50 "percent"
    When the link's predecessor is changed to "vanished"
    Then the link's lag days are 0

  Scenario: The unit reaches the critical path cache key
    # Or a plan whose lag changed only in unit would keep the old answer.
    Given two five-day tasks beginning "2026-08-17"
    And "second" waits on "first" with lag 2 "days"
    When the link's unit becomes "percent"
    Then the analysis signature has moved

  Scenario: The unit survives an undo snapshot
    # A copy that dropped the unit would turn a share into that many
    # days the first time anything was undone.
    Given two five-day tasks beginning "2026-08-17"
    And "second" waits on "first" with lag 50 "percent"
    Then the undo snapshot keeps the unit "percent" on "second"

  Scenario: The unit survives being copied
    # The clipboard rebuilds a task from a dictionary.
    Given two five-day tasks beginning "2026-08-17"
    And "second" waits on "first" with lag 50 "percent"
    Then the clipboard keeps the unit "percent" on "second"

  Scenario: Half a task rounds the way people expect
    # Half of five days is three, not two. Python's round() rounds half
    # to even, so half a five-day task came out as two days and half a
    # seven-day task as four - a rule nobody would guess at and not one
    # worth explaining.
    Given two five-day tasks beginning "2026-08-17"
    When "second" waits on "first" with lag 50 "percent"
    Then the link's lag days are 3

  Scenario: A negative share rounds the same way
    # Away from zero in both directions, or a lead is not a mirror.
    Given two five-day tasks beginning "2026-08-17"
    When "second" waits on "first" with lag -50 "percent"
    Then the link's lag days are -3
