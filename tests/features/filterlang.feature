Feature: The query language behind the Filter window's Advanced tab
  The language is pure - tokenize, parse and compile touch no widget -
  so every behaviour the window promises can be answered here: what
  parses, where a bad query stops, which rows a query matches, and what
  the suggestion list offers at the cursor. The window itself is tested
  where a display exists, in test_grid_filter.py's dialog tests.

  The sample plan: phase "P" holds design task "A" (half done, label
  "design") and code task "B" (done, label "code"); "C" is a task with
  no label; "M" is a milestone at top level. Dates sit in January 2026
  so the date comparisons have something to bite on.

  # ---- a field name in a query resolves to a grid column --------------------

  Scenario Outline: Field names resolve to grid columns
    Then the field "<name>" resolves to "<column>"

    Examples:
      | name           | column         |
      | name           | Task Name      |
      | status         | Status         |
      | start          | Start          |
      | finish         | End            |
      | calendar       | Task Calendar  |
      | baselineStart  | Baseline Start |
      | Task Name      | Task Name      |
      | "Task Name"    | Task Name      |
      | NAME           | Task Name      |
      | Progress       | Progress       |

  Scenario: An unknown name resolves to nothing
    Then the field "wobble" resolves to nothing

  # ---- the grammar: what parses, and what stops with a position -------------

  Scenario: An empty query parses to nothing
    Then parsing a blank query gives nothing

  Scenario: A condition is a four-tuple
    When 'name ~ "art"' is parsed
    Then the condition's field is "Task Name"
    And the condition's test is "contains"
    And the condition's values are "art"
    And the condition's offset is 0

  Scenario: And binds tighter than or
    # status = X and type = Task or milestone = Yes parses as
    # (status = X and type = Task) or (milestone = Yes)
    When 'status = Done and type = Task or milestone = Yes' is parsed
    Then the tree's root is "or"
    And the left branch is "and"
    And the right branch is a condition on "Milestone"

  Scenario: Brackets override precedence
    When 'status = Done and (type = Task or milestone = Yes)' is parsed
    Then the tree's root is "and"
    And the second branch is "or"

  Scenario: Not negates a condition
    When 'not status = Done' is parsed
    Then the tree's root is "not"

  Scenario: An in list reads its values
    When 'type in (Task, Milestone)' is parsed
    Then the condition's test is "in"
    And the condition's values are "Task, Milestone"

  Scenario: Within reads two values
    When 'start within 2026-01-01, 2026-02-01' is parsed
    Then the condition's test is "within"
    And the condition's values are "2026-01-01, 2026-02-01"

  Scenario: Is empty reads no value
    When 'label is empty' is parsed
    Then the condition's test is "is_empty"
    And the condition holds no values

  Scenario: An unclosed quote is an error with a position
    Then parsing 'name ~ "art' fails at 7

  Scenario: An unknown field is an error with a position
    Then parsing 'wobble = 1' fails at 0

  Scenario: A stray token after a condition is an error
    Then parsing 'progress = 50 nonsense' fails past 0

  Scenario: An operator a field cannot take is an error
    Then parsing 'start ~ "x"' fails

  Scenario: Describe and error position answer the window
    Then describing 'name ~ "art"' is fine
    And describing 'name ~' reports an error with a position

  # ---- what a parsed query matches against a plan -----------------------------

  Scenario: An empty query matches everything
    Given the sample plan
    Then an empty query matches "P, A, B, C, M"

  Scenario: Contains matches a substring without case
    # Draft ARTwork and build chART.
    Given the sample plan
    Then the query 'name ~ "art"' matches "A, B"

  Scenario: Equals matches wildcards
    Given the sample plan
    Then the query 'name = "Draft*"' matches "A"
    And the query 'name = "B???? chart"' matches "B"

  Scenario: Not contains rules out
    Given the sample plan
    Then the query 'name !~ "art"' matches "P, C, M"

  Scenario: A number compares both ways
    # Phases and milestones report 0 progress, so they match too.
    Given the sample plan
    Then the query 'progress >= 50' matches "A, B"
    And the query 'progress < 50' matches "P, C, M"

  Scenario: A number range
    Given the sample plan
    Then the query 'progress within 1, 99' matches "A"

  Scenario: A date compares in every spelling
    Given the sample plan
    Then the query 'start = 2026-01-05' matches "P, A"
    And the query 'start = 2026.01.12' matches "B"
    And the query 'start = 2026/01/19' matches "C"

  Scenario: A date range
    Given the sample plan
    Then the query 'start within 2026-01-10, 2026-01-31' matches "B, C"

  Scenario: A fixed set matches without case
    Given the sample plan
    Then the query 'type = task' matches "A, B, C"

  Scenario: An in list matches the set
    Given the sample plan
    Then the query 'type in (Task, Milestone)' matches "A, B, C, M"

  Scenario: Not in rules the set out
    Given the sample plan
    Then the query 'type not in (Task)' matches "P, M"

  Scenario: Is empty and is not empty
    Given the sample plan
    Then the query 'label is empty' matches "P, C, M"
    And the query 'label is not empty' matches "A, B"

  Scenario: And, or and not compose
    Given the sample plan
    Then the query 'type = Task and progress < 50' matches "C"
    And the query 'type = Task and progress < 50 or milestone = Yes' matches "C, M"
    And the query 'not type = Task' matches "P, M"

  Scenario: Brackets group
    Given the sample plan
    Then the query 'type = Task and (progress = 0 or progress = 100)' matches "B, C"

  Scenario: A value that does not parse matches nothing
    Given the sample plan
    Then the query 'progress >= banana' matches nothing

  Scenario: A saved query definition matches like a rules one
    Given the sample plan
    Then the definition "Q" with query 'progress >= 50' matches "A, B"

  Scenario: A broken saved query matches nothing
    Given the sample plan
    Then the definition "Q" with query 'progress ~' matches nothing

  # ---- issue #82: the language takes SQL's spellings, not invented ones -------

  Scenario: Like matches SQL wildcards
    # % is any run and _ one character, exactly as SQL says.
    Given the sample plan
    Then the query "name like 'Draft%'" matches "A"
    And the query "name like '%art%'" matches "A, B"
    And the query "name like 'Clean u_'" matches "C"
    And the query "name like 'Draft artwork'" matches "A"

  Scenario: Like reads an unquoted pattern
    Given the sample plan
    Then the query "name like Draft%" matches "A"

  Scenario: Not like rules out
    Given the sample plan
    Then the query "name not like '%art%'" matches "P, C, M"

  Scenario: Not-equals takes the SQL angle brackets
    Given the sample plan
    Then the query 'status <> "Active"' matches what 'status != "Active"' matches

  Scenario: Is null reads is empty
    Given the sample plan
    Then the query 'label is null' matches "P, C, M"
    And the query 'label is not null' matches "A, B"

  Scenario: Between takes the SQL and
    Given the sample plan
    Then the query 'start between 2026-01-10 and 2026-01-31' matches "B, C"
    And the query 'progress not between 1 and 99' matches "P, B, C, M"

  Scenario: Single quotes are strings
    Given the sample plan
    Then the query "name = 'Draft artwork'" matches "A"

  Scenario: The first spellings still parse
    # Saved queries carrying ~, !~ and within keep working.
    Given the sample plan
    Then the query 'name ~ "art"' matches "A, B"
    And the query 'name !~ "art"' matches "P, C, M"
    And the query 'start within 2026-01-10, 2026-01-31' matches "B, C"

  Scenario: SQL composes with and, or and not
    Given the sample plan
    Then the query "type = Task and (name like 'B%' or progress < 50)" matches "B, C"

  # ---- the Basic tab's specs and a query say the same thing both ways ----------

  Scenario: Specs render as a query
    Given the sample plan
    When specs for name "art", progress 10 to 80 and status "In Progress" render
    Then the rendered query holds 'name ~ "art"'
    And the rendered query holds 'progress within 10, 80'
    And the rendered query holds 'status = "In Progress"'
    And the rendered query joins them with ' and '

  Scenario: A one-ended range renders as a comparison
    When specs for start from 2026-01-05 render
    Then the rendered query is 'start >= 2026-01-05'

  Scenario: A checklist renders as an in list
    Given the sample plan
    When specs for type "Milestone, Task" render
    Then the rendered query is 'type in ("Milestone", "Task")'

  Scenario: A flat query converts back
    Given the sample plan
    When 'name ~ "art" and progress >= 50 and type = "Task"' is converted to specs
    Then the specs hold name text "art"
    And the specs hold progress from 50
    And the specs hold type "Task"

  Scenario: A within converts to both ends
    Given the sample plan
    When 'start within 2026-01-01, 2026-02-01' is converted to specs
    Then the specs hold start from 2026-01-01 to 2026-02-01

  Scenario: An or query has no basic form
    Given the sample plan
    Then 'progress < 50 or type = Milestone' has no basic form
    And 'not status = Done' has no basic form
    And 'type = Task and (progress = 0 or progress = 100)' has no basic form

  Scenario: A round trip matches the same rows
    Given the sample plan
    And specs for name "art" and progress from 50
    When the specs render and convert back
    Then the round trip matches the same rows

  Scenario: A column name spells its shortest alias
    Then "Task Name" spells "name"
    And "Baseline Start" spells "baselinestart"

  # ---- a query filter lives in the file like a rules one does -------------------

  Scenario: A query definition round-trips
    Given the sample plan with a query filter and a rules filter
    When the plan is saved and loaded
    Then "Half done" still carries the query 'progress >= 50'
    And "Rules" still carries the rules with value "art"

  Scenario: A definition with neither rules nor query is dropped
    Given the sample plan with a filter that has neither rules nor query
    When the plan is saved and loaded
    Then no filters survive

  # ---- what the box may be offered next at each cursor spot ---------------------

  Scenario: An empty box offers fields
    Given the sample plan
    Then suggestions at the start offer "name, status, not, ("

  Scenario: After a field come its operators
    # 'between' leads over 'within' since issue #82; a number field has
    # no contains.
    Given the sample plan
    Then suggestions after 'progress ' offer ">=, between"
    And they do not offer "within, ~"

  Scenario: A text field suggests like, not the tilde
    # 'is null' is suggested, so 'is empty' is not.
    Given the sample plan
    Then suggestions after 'name ' offer "like"
    And they do not offer "~, is empty"

  Scenario: After a comparison come and and or
    Given the sample plan
    Then suggestions after 'progress = 50 ' offer "and, or"

  Scenario: After equals on a fixed set come its values
    Given the sample plan
    Then suggestions after 'type = ' offer "Task, Milestone"

  Scenario: Inside an in list come more values
    Given the sample plan
    Then suggestions after 'type in (Task, ' offer "Milestone, )"

  # ---- the View tab's Grid Only button -------------------------------------------
  # The bug it fixed: panes() answers strings, so a widget never
  # compared equal and the pane was never found to remove. The toolbar
  # here is a stand-in answering in pathnames, as Tk does.

  Scenario: Grid Only leaves only the task list
    Given a shell with the list and the chart paned
    When Grid Only is pressed
    Then only the task list shows
    And the Grid Only flag is set

  Scenario: Grid Only hides the dashboard too
    Given a shell with the list and the dashboard paned
    When Grid Only is pressed
    Then only the task list shows

  Scenario: A second press puts the chart back
    Given a shell with the list and the chart paned
    When Grid Only is pressed twice
    Then the chart shows again
    And the Grid Only flag is clear

  Scenario: The pane check reads pathnames, not widgets
    Given a shell with the list and the chart paned
    Then the chart is reported showing
    And a foreign widget is not
