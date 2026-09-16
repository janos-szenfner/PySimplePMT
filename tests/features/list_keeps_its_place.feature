@list_keeps_its_place
Feature: The task list survives being rebuilt

  Every refresh destroys every row and builds them again, and until now
  nothing was carried across that. The consequence was not subtle:
  pressing Bold cleared the selection, the formatting bar - which is
  only live while something is selected - greyed itself out, and the
  row had to be clicked again between every single change. Indent and
  outdent did the same, because they restored the selection themselves
  and then told the application the project had changed, which rebuilt
  the list a second time underneath them.

  Folding had the same fault from the other side. Every rebuilt row is
  inserted open, so a branch folded away sprang back open on the next
  change anywhere in the plan.

  The refresh is driven through the methods the buttons call, which is
  the same path a press takes. The module skips without a display.

  Scenario: Formatting a row keeps it selected
    # Otherwise the next change means clicking the row again.
    Given a toolbar and a list over a small plan
    When row "2" is selected and made bold
    Then the selection is "2"

  Scenario: The formatting bar stays live
    # Which is the part the reader actually notices - the bar is only
    # enabled while something is selected, so a lost selection greys
    # out every control the moment one is used.
    Given a toolbar and a list over a small plan
    When row "2" is selected and made bold
    Then the formatting bar is enabled

  Scenario: Several changes run together
    # Bold then italic then a colour, without reselecting.
    Given a toolbar and a list over a small plan
    When row "2" is selected and made bold, italic and filled "#fff2cc"
    Then task "2" is bold, italic and filled "#fff2cc"

  Scenario: Indent keeps the row selected
    # So it can be indented twice without picking it out again.
    Given a toolbar and a list over a small plan
    When row "2" is selected and indented
    Then the selection is "2"

  Scenario: Indenting twice gets two levels
    # Which is only possible if the first press left it selected. The
    # row above has to be indented first, or there is nothing at the
    # deeper level for the second press to go under.
    Given a toolbar and a list over a small plan
    When row "2" is selected and indented
    And row "3" is selected and indented twice
    Then task "3" sits at outline level 3

  Scenario: A first child cannot indent further
    # There is nothing above it at its own level to go under. Microsoft
    # Project refuses the same press for the same reason, so the row
    # stays where it is rather than being pushed somewhere it does not
    # belong.
    Given a toolbar and a list over a small plan
    When row "3" is selected and indented
    Then task "3" sits at outline level 2
    When row "3" is indented
    Then task "3" sits at outline level 2
    And the selection is "3"

  Scenario: Outdent keeps the row selected
    # The same, on the way back out.
    Given a toolbar and a list over a small plan
    When row "2" is selected and indented
    And the selection is outdented
    Then the selection is "2"

  Scenario: A whole selection survives
    # Several rows marked at once stay marked.
    Given a toolbar and a list over a small plan
    When rows "2" and "3" are selected and made bold
    Then the selection is "2" and "3"

  Scenario: A deleted row is not reselected
    # A selection naming a row that has gone would raise. This runs on
    # every refresh in the application, so it has to cope with the rows
    # having changed underneath it.
    Given a toolbar and a list over a small plan
    When row "2" is selected and then removed
    Then nothing is selected

  Scenario: A folded branch does not spring back open
    # Every rebuilt row is inserted open, so this has to be restored.
    Given a toolbar and a list over a small plan
    When row "2" is selected and indented
    And row "1" is folded and the list is rebuilt
    Then row "1" is folded

  Scenario: An open branch stays open
    # The restore puts back what was there, not what it prefers.
    Given a toolbar and a list over a small plan
    When row "2" is selected and indented
    And the list is rebuilt
    Then row "1" is open

  Scenario: The name is in the column that indents it
    # Column #0 is the only one that draws the indentation - a name
    # anywhere else sits flush left however deep the task is.
    Given a toolbar and a list over a small plan
    Then the tree text on "1" is "Előkészítés"

  Scenario: There is an outline level column
    # Named as Microsoft Project names it, so the two read alike.
    Given a toolbar and a list over a small plan
    Then the tree has an "Outline" column headed "Outline Level"

  Scenario: It counts from one at the top
    # Matching the screenshot: the top is 1, under it is 2.
    Given a toolbar and a list over a small plan
    Then row "1" shows outline level "1"

  Scenario: It follows an indent
    # The number and the indentation say the same thing.
    Given a toolbar and a list over a small plan
    When row "2" is selected and indented
    Then row "2" shows outline level "2"

  Scenario: The row really moves under its parent
    # Which is what draws the indent and the expander beside it.
    Given a toolbar and a list over a small plan
    When row "2" is selected and indented
    Then row "2" hangs under "1"

  Scenario: It follows an outdent back
    # And back out again.
    Given a toolbar and a list over a small plan
    When row "2" is selected and indented
    And the selection is outdented
    Then row "2" shows outline level "1"
    And row "2" hangs at the top

  Scenario: A deep row counts all the way down
    # Four levels, as the screenshot has.
    Given a toolbar and a list over a small plan
    When row "2" is selected and indented
    And row "3" is selected and indented twice
    Then row "3" shows outline level "3"
