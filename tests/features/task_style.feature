Feature: The formatting a row carries, and the defaults folded into it
  Two things here are easy to get wrong and invisible when they are.
  The first is the three-valued emphasis: a summary row is bold without
  anybody asking, so a plain True/False could not tell that automatic
  bold from one somebody chose. The second is what a default style
  serialises to: almost every row in almost every plan carries no
  formatting, so a style that wrote five nulls per task would grow
  every saved file for nothing. Nothing here needs a display.

  # ---- what counts as a colour -----------------------------------------

  Scenario Outline: Colour text is normalised
    When the colour "<text>" is normalised
    Then the colour reads as "<colour>"

    Examples:
      | text    | colour  |
      | #FFF2CC | #fff2cc |
      | fff2cc  | #fff2cc |
      | #abc    | #aabbcc |

  Scenario Outline: What is not a colour becomes no colour
    # These arrive from saved files; a plan that will not open because
    # one row carried a damaged colour would be a bad trade for a row
    # drawn in the default ink.
    When the colour value <value> is normalised
    Then no colour comes out

    Examples:
      | value         |
      | empty         |
      | spaces        |
      | red           |
      | #12345        |
      | #gggggg       |
      | nothing       |
      | a number      |
      | a list        |

  # ---- the style a task carries ----------------------------------------

  Scenario: A new style is the default
    # Nothing set, nothing to save.
    Given a fresh style
    Then it is the default
    And it writes nothing

  Scenario: Only what is set is written
    Given a style marked bold
    Then it writes only "bold: True"

  Scenario: A style survives a round trip
    Given a fully marked style
    When the style is written and read back
    Then it comes back the same

  Scenario Outline: Anything unreadable reads as the default
    # A plan saved before formatting existed opens with plain rows.
    When a saved style of <value> is read
    Then it is the default

    Examples:
      | value    |
      | nothing  |
      | empty    |
      | nonsense |
      | a number |
      | a list   |

  Scenario: Colours are normalised on the way in
    # Whatever form they arrived in.
    Given a style with text colour "C0392B"
    Then its text colour reads as "#c0392b"

  Scenario: A style is a value
    # Two rows formatted the same way hold equal styles - the task list
    # shares one Tk tag between rows that resolve the same way.
    Then two styles marked bold are equal
    And they share one set entry

  Scenario: Changing one leaves the original alone
    # It is frozen, so a change is a new style.
    Given a style marked bold
    When it is changed to be italic
    Then the new style is italic
    And the original still is not

  # ---- folding defaults into the formatting -----------------------------

  Scenario: A summary is bold without being asked
    # What makes an outline readable at a glance.
    When a summary row wearing nothing is resolved
    Then it is bold

  Scenario: A leaf is not
    # Bold everywhere is bold nowhere.
    When a leaf row wearing nothing is resolved
    Then it is not bold

  Scenario: A summary can be un-bolded on purpose
    # The whole reason the flag is three-valued: with a plain False
    # meaning "not set", a summary could never be anything but bold and
    # the B would be a button that did nothing.
    When a summary row wearing a style marked not bold is resolved
    Then it is not bold

  Scenario: Clearing a summary returns it to bold
    # Default formatting for a summary row is bold, not plain.
    When a summary row wearing nothing is resolved
    Then it is bold

  Scenario: The other two are off unless asked for
    # Nothing is italic or underlined by default, at any level.
    When a summary row wearing nothing is resolved
    Then it is not italic and not underlined
    When a leaf row wearing nothing is resolved
    Then it is not italic and not underlined

  Scenario: Colours pass straight through
    # There is no default ink or fill; the grid supplies those.
    When a summary row wearing text colour "#c0392b" is resolved
    Then its text colour reads as "#c0392b"
    And it has no fill colour

  Scenario: Nothing at all resolves
    # A task with no style is the ordinary case, not an error.
    When no style is resolved for a leaf
    Then it is not bold

  # ---- what the formatting bar offers -----------------------------------

  Scenario: Every offered colour is usable
    # A swatch Tk cannot parse is a swatch that paints nothing.
    Then every colour the bar offers is usable

  Scenario: Both palettes offer a way back
    # The default ink and no fill at all are choices too.
    Then both palettes offer a way back to default

  Scenario: The presets are the four the spec names
    # One press each, because two menus and three toggles is not.
    Then the presets are "Financial Milestone", "Work Complete", "Phase Gate / Approval" and "Summary Phase"

  Scenario: The financial preset is yellow and bold
    # The one a payment milestone is marked with.
    Then the "Financial Milestone" preset fills "#fff2cc" and is bold

  Scenario: The approval preset is red, bold and italic
    # A phase gate has to stop the eye.
    Then the "Phase Gate / Approval" preset is "#c0392b" bold and italic

  Scenario: Every preset says something
    # A preset that resolves to the default would be a dead entry.
    Then no preset is the default

  # ---- the style reaches the model --------------------------------------

  Scenario: A task starts with no formatting
    # Which is what nearly every row in nearly every plan carries.
    Given a task
    Then it wears no formatting

  Scenario: A plain dictionary is accepted
    # The importers, the undo history and every saved file hand one
    # over; it is coerced on assignment so no caller has to know a style
    # is its own type.
    Given a task
    When its style is set from a plain dictionary
    Then it wears a real style with fill "#fff2cc"

  Scenario: The formatting survives being saved and read back
    # The formatting travels with the plan, which is the point.
    Given a task wearing a style
    When the task is saved and read back
    Then its formatting came back the same

  Scenario: A plan saved before formatting existed still opens
    # With plain rows rather than an exception.
    Given a task saved without a style entry
    Then it wears no formatting

  Scenario: An ordinary edit does not strip it
    # The undo tracker rebuilds a task from a list of fields; anything
    # missing from that list is reset to its default by any update at
    # all - which is what was happening to calendar_id, and would have
    # happened to the formatting the moment somebody renamed a row they
    # had just marked up.
    Given a task with a calendar and a style
    When it is renamed through the undo tracker
    Then its style and calendar survived
