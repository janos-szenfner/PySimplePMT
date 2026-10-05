Feature: Undo and redo
  Every change a planner makes - adding, removing, editing, reordering
  tasks, renaming the project, touching the resource pool - lands on the
  undo stack as a command holding enough to put it back. Undo walks the
  stack down, redo walks it up, and a fresh edit abandons whatever redo
  was holding.

  # ---- the commands themselves -------------------------------------------------------

  Scenario: AddTaskCommand puts a task in and takes it back out
    Given an undoable project
    And an add-task command for "Test Task"
    When the command executes
    Then the project holds 1 task
    And the project calls it "Test Task"
    When the command undoes
    Then the project holds 0 tasks

  Scenario: RemoveTaskCommand deletes a task and restores it
    Given an undoable project holding "Test Task"
    And a remove-task command for it
    When the command executes
    Then the project holds 0 tasks
    When the command undoes
    Then the project holds 1 task
    And the project calls it "Test Task"

  Scenario: UpdateTaskCommand swaps a task and swaps it back
    Given an undoable project holding "Original"
    And an update-task command renaming it to "Updated"
    When the command executes
    Then the project calls it "Updated"
    When the command undoes
    Then the project calls it "Original"

  Scenario: UpdateProjectNameCommand renames and restores
    Given an undoable project named "Test Project"
    And an update-name command changing it to "New Name"
    When the command executes
    Then the project is called "New Name"
    When the command undoes
    Then the project is called "Test Project"

  # ---- the manager ----------------------------------------------------------------------

  Scenario: Executing through the manager makes it undoable
    Given a project with a manager
    When the manager adds "Test Task"
    Then the project holds 1 task
    And it can undo but not redo

  Scenario: Undo through the manager
    Given a project with a manager
    And the manager added "Test Task"
    When the manager undoes
    Then the project holds 0 tasks
    And it can redo but not undo

  Scenario: Redo through the manager
    Given a project with a manager
    And the manager added "Test Task"
    And the manager undid
    When the manager redoes
    Then the project holds 1 task
    And it can undo but not redo

  Scenario: A fresh edit clears the redo stack
    # Undo "Task 1", then add "Task 2" - redoing the first is gone.
    Given a project with a manager
    And the manager added "Task 1"
    And the manager undid
    When the manager adds "Task 2"
    Then it cannot redo
    And it can undo

  Scenario: The history keeps only the newest few
    Given a project with a manager of history 3
    When the manager adds 5 tasks
    Then the undo stack holds 3 commands
    And the project holds 5 tasks

  Scenario: Undo on an empty stack says no
    Given a project with a manager
    Then the manager's undo is refused
    And the manager's redo is refused

  Scenario: Clear empties both stacks
    Given a project with a manager
    And the manager added "Test Task"
    When the manager is cleared
    Then it cannot undo
    And it cannot redo

  Scenario: The undo description names the command
    Given a project with a manager
    And the manager added "Test Task"
    Then the undo description mentions "Add Task: Test Task"

  Scenario: The redo description names the command
    Given a project with a manager
    And the manager added "Test Task"
    And the manager undid
    Then the redo description mentions "Add Task: Test Task"

  # ---- compound commands -------------------------------------------------------------------

  Scenario: A compound command executes its members
    Given an undoable project
    And a compound command "Add Two Tasks" of two adds
    When the command executes
    Then the project holds 2 tasks

  Scenario: A compound command undoes its members
    Given an undoable project
    And a compound command "Add Two Tasks" of two adds
    When the command executes
    And the command undoes
    Then the project holds 0 tasks

  # ---- the factory functions -----------------------------------------------------------------

  Scenario: Factories build each command kind
    Given an undoable project holding "Original"
    Then the add factory makes an AddTaskCommand on the project
    And the remove factory makes a RemoveTaskCommand
    And the update factory makes an UpdateTaskCommand
    And the rename factory makes an UpdateProjectNameCommand
    And the compound factory makes a CompoundCommand

  # ---- the state tracker ---------------------------------------------------------------------

  Scenario: The tracker adds a task undoably
    Given a project with a tracker
    When the tracker adds "Test Task"
    Then the project holds 1 task
    And the tracker can undo

  Scenario: The tracker removes a task undoably
    Given a project with a tracker
    And the project holds a task "Test Task"
    When the tracker removes it
    Then the project holds 0 tasks
    And the tracker can undo

  Scenario: The tracker updates a task undoably
    Given a project with a tracker
    And the project holds a task "Original"
    When the tracker renames it to "Updated"
    Then the project calls it "Updated"
    And the tracker can undo

  Scenario: The tracker renames the project undoably
    Given a project with a tracker
    When the tracker renames the project to "New Name"
    Then the project is called "New Name"
    And the tracker can undo

  Scenario: The tracker undoes and redoes an add
    Given a project with a tracker
    And the tracker added "Test Task"
    When the tracker undoes
    Then the project holds 0 tasks
    When the tracker redoes
    Then the project holds 1 task

  # ---- undoing a dependency change --------------------------------------------------------------
  # The task list's drag-and-drop handlers appended to
  # task.dependencies before calling update_task. The tracker snapshots
  # the task as it finds it, so the snapshot already held the new link
  # and undo restored the state it was meant to be undoing - the
  # dependency simply stayed.

  Scenario: Undo takes a newly linked dependency back off
    Given a project with a tracker holding "First" and "Second"
    When the tracker gives "Second" the dependencies "001"
    Then "Second" waits for "001"
    When the manager undoes
    Then "Second" waits for nothing

  Scenario: Redo puts the dependency back
    Given a project with a tracker holding "First" and "Second"
    And the tracker gave "Second" the dependencies "001"
    And the manager undid
    When the manager redoes
    Then "Second" waits for "001"

  Scenario: The undo snapshot is independent of the live task
    # The shallow copy behind the snapshot must not share the live
    # task's DependencyList, or mutating it afterwards would rewrite
    # the undo record.
    Given a project with a tracker holding "First" and "Second"
    And "Second" already waits for "001" hard
    When the tracker gives "Second" the dependencies "001" and renames it "Renamed"
    And the old copy grows a "999" dependency of "Rubber" hardness
    And the manager undoes
    Then "Second" waits for "001"
    And "Second"'s "001" link is "FS" and "Hard"

  # ---- undoing a delete ------------------------------------------------------------------------------
  # Project.remove_task deletes the task's sub-tasks too, and strips
  # the removed ID out of every dependency list. Undo must re-insert
  # the whole branch and mend the links the delete broke.

  Scenario: Deleting a parent takes its sub-tasks
    Given a tracked project of a parent, two children and a dependent
    When the tracker removes "001"
    Then the ids are "004"

  Scenario: Undo restores the sub-tasks
    Given a tracked project of a parent, two children and a dependent
    And the tracker removed "001"
    When the manager undoes
    Then the ids are "001, 002, 003, 004"

  Scenario: Undo restores dependencies on surviving tasks
    Given a tracked project of a parent, two children and a dependent
    And the tracker removed "001"
    Then task "004" waits for nothing
    When the manager undoes
    Then task "004" waits for "001"

  Scenario: Undo restores the link details
    Given a tracked project of a parent, two children and a dependent
    And the tracker removed "001"
    And the manager undid
    Then task "004"'s "001" link is "FS" and "Hard"

  Scenario: Redo deletes the branch again
    Given a tracked project of a parent, two children and a dependent
    And the tracker removed "001"
    And the manager undid
    When the manager redoes
    Then the ids are "004"
    And task "004" waits for nothing

  Scenario: Undo after redo still restores
    # The snapshot survives a round trip through redo.
    Given a tracked project of a parent, two children and a dependent
    And the tracker removed "001"
    And the manager undid
    And the manager redid
    When the manager undoes
    Then the ids are "001, 002, 003, 004"
    And task "004" waits for "001"

  Scenario: Deleting a childless task is undoable
    Given a tracked project of a parent, two children and a dependent
    When the tracker removes "004"
    Then the ids are "001, 002, 003"
    When the manager undoes
    Then the ids are "001, 002, 003, 004"

  # ---- undoing a reorder --------------------------------------------------------------------------------

  Scenario: Undo puts a moved task back where it was
    Given a tracked project of "Alpha, Beta, Gamma"
    When "Gamma" moves to the top, recorded
    Then the ids are "003, 001, 002"
    When the manager undoes
    Then the ids are "001, 002, 003"

  Scenario: Redo reapplies the move
    Given a tracked project of "Alpha, Beta, Gamma"
    And "Gamma" moved to the top, recorded
    And the manager undid
    When the manager redoes
    Then the ids are "003, 001, 002"

  Scenario: The recorded orders are independent
    # The command holds two orderings of the same Task objects, so it
    # has to keep its own lists; storing the caller's would let the
    # next move rewrite the history behind it.
    Given a tracked project of "Alpha, Beta, Gamma"
    And "Gamma" moved to the top, recorded
    And "Beta" moved to the top, recorded
    Then the ids are "002, 003, 001"
    When the manager undoes
    Then the ids are "003, 001, 002"
    When the manager undoes
    Then the ids are "001, 002, 003"

  # ---- the resource pool's undo paths ---------------------------------------------------------------------
  # The pool snapshot command, the pre-seeded record of a modal's own
  # write, and the task snapshot's coverage of the pool and the
  # assignments a delete prunes.

  Scenario: A pool command undoes a creation
    Given a tracked project's pool
    When a command adds resource "r1" "Anna"
    Then the pool holds "r1"
    When the manager undoes
    Then the pool does not hold "r1"
    When the manager redoes
    Then the pool holds "r1"
    And the pool calls "r1" "Anna"

  Scenario: A modal's own write is recorded, not re-run
    Given a tracked project's pool
    And the pool holds a resource "r1" "Anna"
    When the pool change "Edit Resource" records "r1" taking initials "AX"
    Then the recording was made
    When the manager undoes
    Then the pool's "r1" initials are "AN"
    When the manager redoes
    Then the pool's "r1" initials are "AX"

  Scenario: An unchanged pool makes no history entry
    Given a tracked project's pool
    And the pool holds a resource "r1" "Anna"
    When the pool change "No-op" records nothing changed
    Then the recording was not made
    And the manager cannot undo

  Scenario: The task snapshot restores assignments and pool
    # run_as_command covers the collections a delete reaches - the
    # pool entity and its id in every task's resource_assignments.
    Given a tracked project's pool holding "r1" assigned to "Build"
    When a command deletes "r1" and its assignments
    Then the pool does not hold "r1"
    And "Build" has 0 assignments
    When the manager undoes
    Then the pool holds "r1"
    And "Build" has 1 assignment of 8 hours at 100 percent

  Scenario: The snapshot survives an in-place assignment edit
    # The snapshot copies the assignments list, so an action that
    # mutates it in place does not rewrite the history.
    Given a tracked project's pool holding "r1" assigned to "Build"
    When a command clears "Build"'s assignments in place
    Then "Build" has 0 assignments
    When the manager undoes
    Then "Build" has 1 assignment

  Scenario: Pool restore keeps the repository object
    # Undo swaps contents in place, so holders of the repo stay live.
    Given a tracked project's pool holding "r1"
    When a command removes "r1" from the pool
    And the manager undoes
    Then the repository is the same object
    And the pool holds "r1"
