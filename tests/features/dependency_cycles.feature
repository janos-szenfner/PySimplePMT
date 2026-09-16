@dependency_cycles
Feature: Circular links through the roll-up, and links obeyed when typed

  Two faults were reported on the same plan (issue #47):

    * A link typed into the Dependencies column as "7SS" - or "7FF",
      "7SF" - changed nothing: the pass that settles the plan only ever
      moves a task later, so a link whose required date was earlier
      than where the task sat was silently not applied. A link just
      typed is meant to be obeyed, so the column edit now settles the
      plan without the forward-only rule.

    * A link added in the task dialog sent a summary row's duration
      past two thousand days and wrecked the chart. The link closed a
      loop the cycle check could not see: the check walked dependency
      edges only, but a row that holds work takes its dates from the
      rows inside it, so waiting on anything that waits on one of
      those - or on the parent itself - is circular all the same. Each
      pass moved the task past the end the summary had just rolled up,
      the summary followed, and the loop never settled.

  The report's plan, simplified: a phase holds a summary, the summary
  holds the linked leaf, and a chain hangs off the phase - so a link
  from the leaf to anywhere on the chain runs in a circle through the
  roll-up, whatever the type.

  Scenario: A child depending on its parent is circular
    # The parent's dates are the children's; a child that waits on it
    # waits on itself.
    Given the reported plan
    Then "F2" waiting on "UX" would close a circle

  Scenario: A child depending on a higher ancestor is circular
    Given the reported plan
    Then "F2" waiting on "P1" would close a circle

  Scenario: A link to a task that waits on the branch is circular
    # The reported case: an SF link from the leaf to a task downstream
    # of the phase, which waits on the phase, which takes its dates
    # from the leaf. Every reschedule grew the summary by another span.
    Given the reported plan
    Then "F2" waiting on "T3" would close a circle

  Scenario: A summary depending on its descendant is circular
    # The other way round, caught before this change and still.
    Given the reported plan
    Then "UX" waiting on "F2" would close a circle

  Scenario: A leaf depending on a summary that waits on it
    # A link to a summary one of whose children waits on the leaf: the
    # summary's dates are the child's, which are the leaf's.
    Given a summary whose child waits on the leaf
    Then "L" waiting on "S" would close a circle

  Scenario: An ordinary link is still allowed
    # A sibling waits on nothing the leaf feeds.
    Given the reported plan
    Then "F1" waiting on "F3" would not close a circle

  Scenario: A link to a summary outside the branch is allowed
    # Linking to a summary is legitimate when the summary does not hold
    # the task - the rule is circles, not summary rows.
    Given the reported plan
    Then "T3" waiting on "P1" would not close a circle

  Scenario: A parent's number is refused
    # parse_dependencies says why, in the column's own words.
    Given the reported plan
    When "F2" is typed the number of "UX"
    Then no links were parsed and the error says "holds this task inside it"

  Scenario: A descendant's number is refused
    Given the reported plan
    When "UX" is typed the number of "F2"
    Then no links were parsed and the error says "holds task"

  Scenario: A downstream number is refused
    Given the reported plan
    When "F2" is typed the number of "T3" with type "SF"
    Then no links were parsed and the error says "circle"

  Scenario: The summary stays its own size
    # The refused link is the one that sent the collector's duration
    # past two thousand days: with it refused, the plan still settles.
    Given the reported plan
    When the plan is settled
    Then "UX" covers fewer than 500 working days
    And settling again changes nothing

  Scenario: Start-Start pulls the task to the predecessor's start
    # A link just stated moves the task, even when that means earlier.
    # feature2 sits after feature3, waiting on it Finish-to-Start.
    Given the reported plan settled with F2 after F3
    When "F2" is given a Hard "SS" link to "F3" and settled by the edit
    Then "F2" starts where "F3" starts

  Scenario: Finish-Finish holds the task's end
    Given the reported plan settled with F2 after F3
    When "F2" is given a Hard "FF" link to "F3" and settled by the edit
    Then "F2" ends where "F3" ends

  Scenario: Start-Finish holds the task's end at the start
    Given the reported plan settled with F2 after F3
    When "F2" is given a Hard "SF" link to "F3" and settled by the edit
    Then "F2" ends where "F3" starts

  Scenario: The automatic pass still keeps deliberate slack
    # The forward-only rule is untouched for the pass nobody asked
    # for: re-settling the plan does not close a gap a planner left.
    Given the reported plan settled with F2 after F3
    When "F2" is given a Hard "SS" link to "F3" and settled by the edit
    And "F2" is moved to 2026-10-26 to 2026-11-23 with a Rubber "SS" link to "F3"
    And the plan is settled
    Then "F2" still starts 2026-10-26
