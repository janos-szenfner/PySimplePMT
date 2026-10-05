Feature: The colours a deliverable's health takes
  Issue #102. The board, its columns, clipboard and menus need a
  display and stay in the unittest module; what a row's dates and
  progress say about it does not.

  # ---- one row --------------------------------------------------------------------------------

  Scenario: A done row is done
    Then a deliverable at 100 reads "done"
    And a deliverable marked "Done" due yesterday reads "done"

  Scenario: An unfinished row past due is overdue
    Then a deliverable at 50 due yesterday reads "overdue"

  Scenario: A started row owed later is on track
    Then a deliverable at 40 due tomorrow reads "on_track"

  Scenario: An unstarted row reads grey
    Then an unstarted deliverable due tomorrow reads "not_started"

  # ---- the whole list ----------------------------------------------------------------------------

  Scenario: The list is green only when everything is done
    Then deliverables "100 | 100" read "done"
    And deliverables "100 | 100 | 90" are not "done"

  Scenario: A late row is amber until the final deadline
    # One row is late but the furthest date owed is still ahead.
    Then deliverables "40 due yesterday | 40 due next week" read "at_risk"

  Scenario: The list is red once the final deadline passes
    Then deliverables "40 due yesterday | 80 due yesterday" read "overdue"

  Scenario: The list is blue while nothing is late
    Then deliverables "40 due tomorrow | 0 due tomorrow" read "on_track"
