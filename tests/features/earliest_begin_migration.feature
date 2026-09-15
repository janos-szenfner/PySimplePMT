Feature: The retired Earliest begin floor becomes Start No Earlier Than
  Earliest begin was a floor on a task's start - exactly what the Start
  No Earlier Than constraint is. The field is gone; a plan that still
  carries one keeps its floor by reading it back as the SNET constraint
  that means the same thing, so no plan silently loses a date somebody
  set.

  Scenario: A legacy floor becomes a Start No Earlier Than
    When a saved task carrying an earliest begin of "2026-03-02" is loaded
    Then the constraint type is "SNET"
    And the constraint date is "2026-03-02"

  Scenario: No legacy floor leaves the task unconstrained
    When a saved task with no legacy floor is loaded
    Then the constraint type is "NA"
    And there is no constraint date

  Scenario: A real constraint is kept over the legacy floor
    When a saved task carrying an earliest begin of "2026-03-02" and an "MSO" constraint dated "2026-05-01" is loaded
    Then the constraint type is "MSO"
    And the constraint date is "2026-05-01"

  Scenario: The migrated constraint survives a further round trip
    Given a saved task carrying an earliest begin of "2026-03-02" was loaded
    When the task is saved and loaded again
    Then the constraint type is "SNET"
    And the constraint date is "2026-03-02"

  Scenario: The field is gone from the task
    Given a loaded task
    Then "earliest_begin" is not in its saved form
    And the task has no "earliest_begin" attribute
