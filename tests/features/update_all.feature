Feature: A change raised mid-refresh runs once more, not nested
  update_all rebuilds everything on every change. If a callback fired
  while that rebuild was running asked for another update, the second
  rebuild used to be able to stack inside the first. The refresh now
  finishes, then runs once more.

  Scenario: A nested update is coalesced into one more pass
    Given a refresh whose rebuild raises one more change
    When update_all runs
    Then the rebuild ran exactly twice
    And the second run was not inside the first

  Scenario: Two nested changes still coalesce into one more pass
    Given a refresh whose rebuild raises two more changes
    When update_all runs
    Then the rebuild ran exactly twice

  Scenario: A quiet refresh runs once
    Given a refresh whose rebuild raises nothing
    When update_all runs
    Then the rebuild ran exactly once
