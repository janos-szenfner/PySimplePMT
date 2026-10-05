Feature: The Deliverables tab's data - entity, roll-up and hierarchy
  Deliverables are not tasks: they carry no dates the scheduler works
  out and take no part in the Gantt. What they share with tasks is the
  shape of the list - a flat collection linked by parent_id - so every
  rule the task hierarchy keeps has to hold here too: a branch moves
  whole, a row cannot be made its own descendant, and the display order
  is the order the file keeps.

  Progress has a rule of its own. A leaf's percentage is typed or set
  by its status - Done is 100, To Do is 0, In Progress keeps what it
  has - and a deliverable with children takes the weighted average of
  theirs, falling back to the plain average when no weights are set.

  # ---- what a deliverable is on its own ----------------------------------------

  Scenario: Defaults are an unstarted leaf
    When a deliverable is created plain
    Then its status is "To Do"
    And it reads 0 percent
    And its weight is 1.0
    And it has no parent

  Scenario: Progress is clamped
    Then a deliverable at 140 reads 100 percent
    And a deliverable at -5 reads 0 percent

  Scenario: An unknown status reads as what the progress says
    Then a deliverable at 40 marked "Blocked" reads status "In Progress"

  Scenario Outline: Status answers for progress
    Then progress <progress> reads as status "<status>"

    Examples:
      | progress | status      |
      | 0        | To Do       |
      | 40       | In Progress |
      | 100      | Done        |

  Scenario Outline: Progress answers for status
    Then status "<status>" on a row at <held> reads <progress> percent

    Examples:
      # In Progress keeps a partial progress rather than rewriting it,
      # and starts at 1 on a row that held nothing.
      | status      | held | progress |
      | Done        | 0    | 100      |
      | To Do       | 60   | 0        |
      | In Progress | 60   | 60       |
      | In Progress | 0    | 1        |

  Scenario: The statuses are the three the grid offers
    Then the statuses offered are "To Do, In Progress, Done"

  # ---- how a deliverable takes progress from the items under it -----------------

  Scenario: No weights is the plain average
    Then children at "100, 60, 40" roll up to 67

  Scenario: Weights shift the average
    # (200 + 180 + 40) / 6
    Then children at "100, 60, 40" weighted "2, 3, 1" roll up to 70

  Scenario: All zero weights fall back to the average
    Then children at "100, 0" weighted "0, 0" roll up to 50

  Scenario: No children is zero
    Then no children roll up to 0

  Scenario: The roll-up reaches every level
    # A change at the leaf lands on the grandparent, deepest first.
    Given a deliverable plan
      | id | parent |
      | g  |        |
      | p  | g      |
      | l  | p      |
    And "l" is set to 100 percent
    When the roll-up runs
    Then "l" reads 100 percent
    And "p" reads 100 percent
    And "g" reads 100 percent
    And "g" reads status "Done"

  Scenario: The roll-up reports whether anything moved
    Given a deliverable plan
      | id | parent |
      | p  |        |
      | x  | p      |
      | y  | p      |
    And the roll-up has settled
    Then the roll-up reports nothing moved
    When "x" is set to 50 percent
    Then the roll-up reports it moved

  # ---- the moves the grid's indent, outdent and drag gestures make ---------------

  Scenario: Display order is each branch together
    Given a deliverable plan
      | id | parent |
      | a  |        |
      | b  | a      |
      | c  | b      |
      | d  |        |
    Then the display order is "a, b, c, d"

  Scenario: Indent goes under the row above
    Given a deliverable plan
      | id | parent |
      | a  |        |
      | b  |        |
    When "b" is indented
    Then the move worked
    And "b" sits under "a"
    And the display order is "a, b"

  Scenario: The first row cannot indent
    Given a deliverable plan
      | id | parent |
      | a  |        |
      | b  |        |
    When "a" is indented
    Then the move was refused
    And "a" is at the top level

  Scenario: Outdent comes out beside the parent
    Given a deliverable plan
      | id | parent |
      | a  |        |
      | b  | a      |
      | c  | a      |
    When "b" is outdented
    Then the move worked
    And "b" is at the top level
    And the display order is "a, c, b"

  Scenario: Re-parent moves the whole branch
    Given a deliverable plan
      | id | parent |
      | a  |        |
      | b  | a      |
      | c  | b      |
      | d  |        |
    When "b" is re-parented under "d"
    Then the move worked
    And "b" sits under "d"
    And "c" sits under "b"
    And the display order is "a, d, b, c"

  Scenario: A branch cannot go under itself
    Given a deliverable plan
      | id | parent |
      | a  |        |
      | b  | a      |
    Then re-parenting "a" under "b" is refused twice

  Scenario: Moving to a line below a parent nests inside it
    Given a deliverable plan
      | id | parent |
      | a  |        |
      | b  | a      |
      | c  |        |
    When "c" is moved to the line below "a"
    Then the move worked
    And "c" sits under "a"

  Scenario: Move after lands beside the anchor, not inside it
    # "After" means after the whole subtree - a sibling, not a child.
    Given a deliverable plan
      | id | parent |
      | a  |        |
      | b  | a      |
      | c  |        |
    When "c" is moved after "a"
    Then the move worked
    And "c" is at the top level
    And the display order is "a, b, c"

  Scenario: Move up and down stay among siblings
    Given a deliverable plan
      | id | parent |
      | a  |        |
      | b  | a      |
      | c  | a      |
      | d  | a      |
    When "c" is moved "up"
    Then the display order is "a, c, b, d"
    When "c" is moved "down"
    Then the display order is "a, b, c, d"

  Scenario: Sorting happens inside each group
    Given a deliverable plan
      | id | parent |
      | a  |        |
      | z  | a      |
      | b  | a      |
      | d  |        |
    When the deliverables are sorted by name
    Then the display order is "a, b, z, d"

  Scenario: Topmost of a selection drops the nested rows
    Given a deliverable plan
      | id | parent |
      | a  |        |
      | b  | a      |
      | c  |        |
    Then the topmost of "a, b, c" are "a, c"

  Scenario: Removing a row takes the branch with it
    Given a deliverable plan
      | id | parent |
      | a  |        |
      | b  | a      |
      | c  | b      |
      | d  |        |
    When "a" is removed
    Then the move worked
    And the display order is "d"

  Scenario: The next id counts on from the highest
    Given a deliverable plan
      | id  | parent |
      | 001 |        |
      | 002 |        |
    Then the next deliverable id is "003"

  Scenario: Display ids count down the order
    Given a deliverable plan
      | id | parent |
      | a  |        |
      | b  | a      |
      | c  |        |
    Then the display ids are "a:1, b:2, c:3"

  # ---- deliverables going to the file and coming back -----------------------------

  Scenario: A round trip keeps every field
    Given a plan holding an "API" deliverable with every field set
    When the plan is saved and loaded
    Then "001" kept its name, progress, weight, assignees, due date, priority, tags and details
    And "002" still sits under "001"

  Scenario: A file without the key loads empty
    # Every plan saved before this tab existed means none owed.
    When a plan saved without the deliverables key is loaded
    Then it carries no deliverables

  Scenario: A legacy single assignee loads as a list
    # Files from before assignees became a list carry one string.
    Then a saved deliverable with assignee "@Sarah" loads assignees "@Sarah"

  Scenario: Assignees normalise
    # A bare string reads as a list; blank entries drop out.
    Then assignees written "@Sarah, @Tom" load as "@Sarah, @Tom"
    And assignees listed as "@Sarah, (blank), (blank)" load as "@Sarah"

  Scenario: An unreadable entry is skipped, not fatal
    When a plan whose deliverables hold a bad entry is loaded
    Then the deliverables are "x"

  # ---- every grid gesture lands as one undoable step --------------------------------

  Scenario: A change undoes and redoes
    Given a tracked deliverable plan of "a, b under a, c"
    When "b" is finished the way the grid does
    Then "b" reads 100 percent
    And "a" reads 100 percent
    When undo is run
    Then "b" reads 0 percent
    And "a" reads 0 percent
    When redo is run
    Then "b" reads 100 percent

  Scenario: A restructure undoes to the old shape
    Given a tracked deliverable plan of "a, b under a, c"
    When "c" is re-parented under "a" the way the grid does
    Then "c" sits under "a"
    When undo is run
    Then "c" is at the top level
    And the display order is "a, b, c"

  Scenario: An action that changed nothing leaves no entry
    Given a tracked deliverable plan of "a, b under a, c"
    When a command that changes nothing runs
    Then undo is not offered

  # ---- the many-to-many link: tasks assigned to deliverables -------------------------
  # …and the progress they lend them. The two tasks are "t1" at 40 and
  # "t2" at 80.

  Scenario: A task can sit under several deliverables
    Given a deliverable plan with two tasks
      | id | parent |
      | a  |        |
      | b  |        |
    And "a" takes task "t1"
    And "b" takes task "t1"
    Then "t1" is listed under "a, b"

  Scenario: A deliverable can hold several tasks
    Given a deliverable plan with two tasks
      | id | parent |
      | a  |        |
    And "a" takes tasks "t1, t2"
    Then "a" is fed by "t1, t2"

  Scenario: Assigned tasks count into the progress
    # (40 + 80) / 2
    Given a deliverable plan with two tasks
      | id | parent |
      | a  |        |
    And "a" takes tasks "t1, t2"
    When the roll-up runs
    Then "a" reads 60 percent
    And "a" reads status "In Progress"

  Scenario: Children and tasks count together
    # A parent's inputs are its children AND its own assigned tasks:
    # (child 100 + task 40) / 2.
    Given a deliverable plan with two tasks
      | id | parent |
      | p  |        |
      | c  | p      |
    And "c" is set to 100 percent
    And "p" takes task "t1"
    When the roll-up runs
    Then "p" reads 70 percent

  Scenario: Tasks, subtasks and milestones all count
    Given a deliverable plan
      | id | parent |
      | a  |        |
    And "a" takes "t1" at 100, its subtask "t2" at 50 and milestone "t3" at 0
    When the roll-up runs
    Then "a" reads 50 percent

  Scenario: The same task counts under each row it feeds
    Given a deliverable plan with two tasks
      | id | parent |
      | a  |        |
      | b  |        |
    And "a" takes task "t1"
    And "b" takes task "t1"
    When the roll-up runs
    Then "a" reads 40 percent
    And "b" reads 40 percent

  Scenario: Setting a task's deliverables writes both sides
    Given a deliverable plan with two tasks
      | id | parent |
      | a  |        |
      | b  |        |
    And "a" takes task "t1"
    When "t1" is assigned to "b"
    Then "a" holds no tasks
    And "b" holds tasks "t1"

  Scenario: Setting what is already set changes nothing
    Given a deliverable plan with two tasks
      | id | parent |
      | a  |        |
    Then assigning "t1" to nothing changes nothing
    When "t1" is assigned to "a"
    Then assigning "t1" to "a" again changes nothing

  Scenario: Removing the last task hands progress back
    # With no inputs left, the roll-up leaves the row alone.
    Given a deliverable plan with two tasks
      | id | parent |
      | a  |        |
    And "a" takes task "t1"
    And the roll-up has settled
    When "a" drops its tasks
    And "a" is set to 90 percent
    And the roll-up runs
    Then "a" reads 90 percent

  Scenario: Removing a task prunes it from membership
    Given a deliverable plan with two tasks
      | id | parent |
      | a  |        |
      | b  |        |
    And "a" takes tasks "t1, t2"
    And "b" takes task "t1"
    When task "t1" is deleted
    Then "a" holds tasks "t2"
    And "b" holds no tasks

  Scenario: Removing a task re-rolls the progress
    Given a deliverable plan with two tasks
      | id | parent |
      | a  |        |
    And "a" takes tasks "t1, t2"
    And the roll-up has settled
    When task "t1" is deleted
    Then "a" reads 80 percent

  Scenario: Membership survives a round trip
    Given a deliverable plan with two tasks
      | id | parent |
      | a  |        |
    And "a" takes tasks "t2, t1"
    When the plan is saved and loaded
    Then "a" holds tasks "t2, t1"

  Scenario: Ids of tasks that do not exist are pruned on load
    Given a deliverable plan with two tasks
      | id | parent |
      | a  |        |
    When the saved file names "t1" and a ghost under "a"
    Then "a" holds tasks "t1"

  Scenario: A file without the task_ids key loads empty
    Then a saved deliverable with no task_ids key holds no tasks

  Scenario: Duplicate ids are kept once
    Then a deliverable holding "t1, t1, t2" holds tasks "t1, t2"

  # ---- assigning and removing tasks is one undoable step either way -----------------

  Scenario: An assign undoes and redoes
    Given a tracked deliverable plan of "a, b" with task "t1" at 50
    When "t1" is assigned to "a" the way the grid does
    Then "a" holds tasks "t1"
    When undo is run
    Then "a" holds no tasks
    When redo is run
    Then "a" holds tasks "t1"

  Scenario: The progress the assign derived undoes with it
    Given a tracked deliverable plan of "a, b" with task "t1" at 50
    When "t1" is assigned to "a" the way the grid does
    Then "a" reads 50 percent
    When undo is run
    Then "a" holds no tasks
    # The derived number goes back with the membership that made it.
    And "a" reads 0 percent

  Scenario: Undoing a task delete restores the membership
    Given a tracked deliverable plan of "a, b" with task "t1" at 50
    And "a" takes task "t1"
    And the roll-up has settled
    When task "t1" is deleted as a command
    Then "a" holds no tasks
    When undo is run
    Then "a" holds tasks "t1"

  # ---- coercion: a saved file can carry anything -----------------------------------------

  Scenario: A gibberish progress coerces to zero
    # Rather than failing the row.
    When a deliverable is made with progress "banana"
    Then it reads 0 percent

  Scenario: A gibberish weight coerces to one
    When a deliverable is made with weight "banana"
    Then its weight is 1.0

  Scenario: A negative weight clamps to zero
    # A row that counts for nothing cannot be negative about it.
    When a deliverable is made with weight "-2"
    Then its weight is 0.0

  Scenario: Assignees given as one string split on commas
    When a deliverable is made with assignees "Ann, Bob"
    Then its assignees are "Ann, Bob"

  Scenario: Done means a hundred
    When a deliverable is made with progress "99"
    Then it is not done
    When its progress becomes 100
    Then it is done

  Scenario: An unreadable due date is dropped, not fatal
    # A hand-edited file's due date reads as none, with a line in the log.
    Then a saved due date of "not a date" loads as none
    And a saved due date of "42" loads as none

  Scenario: An unreadable roll-up weight counts every child alike
    # One bad weight drops the whole weighting to shares rather than
    # losing the roll-up.
    Given a plan of deliverables "a"
    And "a" takes child "b" weighing "banana" at 80 percent
    And "a" takes child "c" weighing "2" at 40 percent
    Then "a" rolls up to 60 percent
