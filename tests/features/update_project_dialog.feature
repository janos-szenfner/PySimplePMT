Feature: The Update Project window
  The window asks one question - which date uncompleted work resumes on -
  and hands it back through on_update. What the plan does with the date is
  covered by update_project.feature; these scenarios are about the window
  itself: what it opens on, what OK does, and what it refuses.

  Needs a display; the scenarios skip where there is none.

  Scenario: The box opens on the plan's status date
    # The line the plan is reported against is the sane default.
    Given a plan with a status date of "2026-09-15"
    When the window opens
    Then the box holds "2026-09-15"

  Scenario: With no status date the box opens on today
    Given a plan with no status date
    When the window opens
    Then the box holds today's date

  Scenario: OK hands back the date in the box
    Given a plan with a status date of "2026-09-15"
    And the window is open
    When the box is set to "2026-10-01" and OK is pressed
    Then the date "2026-10-01" came back
    And the window is gone

  Scenario: OK with nobody listening still closes
    # on_update is optional - a window that closes on OK is not
    # broken for having no caller.
    Given a plan with a status date of "2026-09-15"
    And the window is open with nobody listening
    When OK is pressed
    Then the window is gone

  Scenario: An empty box is refused and said so
    # A warning, not a silent close - nothing came back and the
    # window stays up for another try.
    Given a plan with a status date of "2026-09-15"
    And the window is open
    When the box is emptied and OK is pressed
    Then a warning was shown
    And nothing came back
    And the window is still up

  Scenario: Cancel hands back nothing
    Given a plan with a status date of "2026-09-15"
    And the window is open
    When Cancel is pressed
    Then nothing came back
    And the window is gone
