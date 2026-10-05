Feature: The search box's matching
  Issue #51's search: a box on the toolbar that filters the grid to
  rows whose fields mention the needle. The plan used throughout has
  something in every field: a Design Phase holding UI Mockups (which
  holds Wireframe), and a Server migration waiting two days on the
  mockups.

  The box itself and the list it filters need a display and stay in
  the unittest module.

  # ---- one field per test, so a failure names the one that stopped working --------------------

  Scenario: By name
    Given the search plan
    Then "mockups" finds "UI Mockups"

  Scenario: By the number shown beside it
    # The identity is a key the reader never sees, so it is
    # deliberately not searchable: matching on it would find rows by a
    # number that is nowhere on screen.
    Given the search plan
    Then "T2's" shown number finds "Server migration"
    And "T2's" shown number padded finds "Server migration"

  Scenario: The identity is not searchable
    # It is a key, and one nobody can see to type.
    Given the search plan
    Then "T2" finds nothing

  Scenario: By type
    Given the search plan
    Then "phase" finds "Design Phase"

  Scenario: By notes
    # The ticket number somebody pasted into the details.
    Given the search plan
    Then "JIRA-4821" finds "UI Mockups"

  Scenario: By start date
    # Written the way every date in the application is.
    Given the search plan
    Then "2026-09-14" finds "Server migration"

  Scenario: By part of a date
    # So a month finds everything in it.
    Given the search plan
    Then "2026-09" finds 4 names

  Scenario: By duration
    Given the search plan
    Then "5" finds "UI Mockups" at least

  Scenario: By progress
    Given the search plan
    Then "40" finds "UI Mockups" at least

  Scenario: By priority
    Given the search plan
    Then "high" finds "UI Mockups"

  Scenario: By what it depends on
    # By the number the predecessor is shown as - not by the
    # predecessor's name, which would answer every name search with
    # rows that merely mentioned the thing being looked for.
    Given the search plan
    Then "T1's" shown number finds "Server migration"
    And "UI Mockups" finds "UI Mockups" and nothing else

  Scenario: By the kind of link
    # The type, the hardness and the lag are all on the row.
    Given the search plan
    Then "Hard" finds "Server migration" at least

  Scenario: By its calendar
    # Not stored on the task - only the id is.
    Given the search plan
    Then "Weekend-Only" finds "Server migration" at least

  Scenario: A milestone is found by the word
    # However its type happens to be spelt on the row.
    Given a plan holding the milestone "Sign-off" on "2026-09-07"
    Then "milestone" finds "Sign-off"

  # ---- case, literalness, and the empty search ----------------------------------------------------

  Scenario: Case is ignored
    # Nobody types a name's capitals to find it.
    Given the search plan
    Then "MOCKUPS" finds what "mockups" finds

  Scenario: A search is taken literally
    # So a date or a ticket finds itself rather than being a pattern.
    Given the search plan
    Then "mock.*" finds nothing

  Scenario: An empty search matches everything
    # Which is what makes clearing the box the same as never typing.
    Given the search plan
    Then an empty search and "   " match every task

  Scenario: An empty search asks the list for nothing
    # None rather than every id, so an empty box costs no work.
    Given the search plan
    Then an empty visible search is unasked

  Scenario: The haystack is one lower-case string
    # Everything downstream assumes it.
    Given the search plan
    Then "T1's" haystack is one lower-case string

  # ---- a match brings its ancestors, and nothing else -------------------------------------------------

  Scenario: A match brings its ancestors
    # Or a matching sub-task floats at the top level with no sign of
    # what it belongs to.
    Given the search plan
    Then "wireframe" leaves "S1, T1, P1" on screen

  Scenario: Ancestors are not counted as matches
    # They are on screen to say where a match sits, not because they
    # hit.
    Given the search plan
    Then "wireframe" matches "S1"

  Scenario: A match does not bring its children
    # A Phase whose name matches shows as itself; showing everything
    # inside it would answer a question nobody asked.
    Given the search plan
    Then "design phase" leaves "P1" on screen

  Scenario: Nothing matching shows nothing
    # Rather than falling back to the whole plan.
    Given the search plan
    Then "zzzz" leaves nothing on screen

  Scenario: A parent loop does not hang the walk
    # A damaged file can carry one, and the walk climbs parents.
    Given the search plan
    When "T1" is made a child of "S1"
    Then "wireframe" leaves "S1" on screen at least

  # ---- it hides rows; it must not touch the plan ------------------------------------------------------

  Scenario: The plan still holds every task
    # Filtering is a view, not a deletion.
    Given the search plan
    When "wireframe" is searched
    Then the plan still holds 4 tasks

  Scenario: The schedule is measured on the whole plan
    # A phase spans all its children, not the visible ones.
    Given the search plan
    When the plan is rescheduled and "zzzz" is searched and it is rescheduled
    Then "P1's" span is what it was
