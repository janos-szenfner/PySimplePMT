Feature: The arrangement of the toolbar menus
  The menu tree is read from Toolbar._menu_definitions rather than by
  building a Toolbar, which would need a display. The method only
  returns data, so the structure can be checked directly while the
  commands it names are verified to exist on the class.

  # ---- the order the menus appear in, left to right ------------------------

  Scenario: The top-level order
    Then the menus read "File, Actions, Edit, View, About"

  Scenario: File comes first
    # Where every other application puts it. A second menu called
    # Project used to hold the new/open/save, so the one place a reader
    # looks first for Save was the one place it was not.
    Then "File" leads the menus

  Scenario: Nothing is called Project any more
    # Its entries are under File; the empty menu went with them.
    Then "Project" is not a menu

  Scenario: About is last
    Then "About" ends the menus
    And "View" sits second from the end

  # ---- what sits under each menu -------------------------------------------

  Scenario: The File menu
    Then "File" holds "New Project..., Open Project..., Save Project..., Save Project As..., Close Project, Project Info..."

  Scenario: Actions nests the import and export submenus
    Then "Actions" holds "Update Project..., Baseline, Import, Export"
    And "Baseline", "Import" and "Export" open submenus

  Scenario: Every import format is reachable under Actions > Import
    Then "Import" under "Actions" holds "MS Project..., GAN..., Mermaid..., XLSX..."

  Scenario: Every export format is reachable under Actions > Export
    # The two boards' own exports came with issues #66 and #83.
    Then "Export" under "Actions" holds "GAN..., MS Project..., Mermaid..., HTML..., SVG..., PNG..., PDF..., XLSX..., Dashboard PNG..., Dashboard PDF..., Timeline PNG..., Timeline PDF..."

  Scenario: Project Info opens the unified tabbed hub
    # Issue #91 - a command, not a submenu.
    Then "Project Info..." under "File" runs a command

  Scenario: There is no top-level Settings menu
    # Settings moved into File.
    Then "Settings" is not a menu

  Scenario: Calendar Settings is reached from the settings hub
    Then "edit_holidays" and "open_settings" are real methods

  Scenario: Create offers the things that can be created, nothing else
    Then "Create" under "Edit" holds "Phase..., Task..., Milestone..."

  Scenario: The full Project editor remains wired behind the hub
    Then "edit_project_info" and "open_settings" are real methods

  Scenario: The View menu is what this window shows
    # The appearance, the critical path, and the guide. The chart's own
    # settings went to Settings, beside the plan's other settings.
    # Critical Path came the other way: it changes what the window shows
    # rather than what the plan says. Sort By and AutoFilter joined for
    # the three-level sort dialog and the heading dropdowns (#45, #81);
    # the one-level sort lives on the headings themselves (#46).
    Then "View" holds "Grid View Only, Charts, Sort By..., AutoFilter, Critical Path..."
    And "View" does not hold "Project Info" or "Help"

  Scenario: The appearance controls left the View menu
    # System UI mode moved to Settings > System UI tab.
    Then "View" does not hold "System UI mode"

  Scenario: The About menu holds help, about and the changelog
    Then "About" holds "Help, About PySimplePMT, Changelog"

  Scenario: The Edit menu
    # Create leads, because everything under it acts on a row that has
    # to exist already. The clipboard entries name the key they answer
    # to, in this platform's notation.
    Then "Edit" holds Create, the clipboard entries and the history entries

  # ---- every entry must lead somewhere -------------------------------------

  Scenario: Every leaf names a real method
    # No menu entry points at a command the toolbar does not have.
    Then every leaf command names a method the toolbar has

  Scenario: No leaf is also a submenu
    # An entry either runs a command or opens a submenu, never both.
    Then every item is a command or a submenu, never both

  # ---- the keyboard reaches the task list's own create action ---------------

  Scenario: The toolbar has a new-task hotkey handler
    # Bound in _bind_style_hotkeys, beside the other window hotkeys.
    Then "_hotkey_new_task" is a real method

  Scenario: The hotkey asks the task list to create one
    # And does nothing at all before the list exists.
    Given a toolbar stub with no task list
    When the hotkey is pressed
    Then "break" answers
    Given a toolbar stub whose task list listens
    When the hotkey is pressed
    Then the task list is asked to create at the cursor

  # ---- the ribbon's New Task takes the same route as the hotkey (#59) --------

  Scenario: The menu asks the task list to create at the cursor
    Given a toolbar stub whose task list listens
    When the menu's New Task runs
    Then the task list is asked to create at the cursor

  Scenario: Without a list the menu falls back to appending
    # Before the list exists there is no cursor to insert at.
    Given a toolbar stub with no task list
    When the menu's New Task runs
    Then a plain "Task" is created instead

  # ---- Option is a compose key on macOS, so the keysym cannot be relied on ---

  Scenario: The plain keysym is accepted
    # What a Tk that leaves the keystroke alone reports.
    Then a key event with keysym "period" and char "." answers "."
    And a key event with keysym "Period" and char "." answers "."

  Scenario: The character is accepted
    # Where the keysym is something else but the char survives.
    Then a key event with keysym "Key-47" and char "." answers "."

  Scenario: The composed dead key is still the period key
    # The case that was failing: Option+. produces an ellipsis, so
    # neither keysym nor char says '.'. The keycode names the physical
    # key - the one thing Option cannot change.
    Then a key event with keysym "ellipsis", char "…" and the "." keycode answers "."

  Scenario: Another key held with Option is not it
    # Or every Option shortcut would make a task.
    Then a key event with keysym "j" and char "∆" does not answer "."

  Scenario: The catch-all names the modifiers
    # Tk matches those itself; only the key is left to us.
    Then "any_key_with" alt names the Command-Option keypress

  Scenario: The toolbar routes the period key through
    # And leaves every other Option keystroke alone.
    Given a toolbar stub whose task list listens
    When "period" is pressed with Option
    Then "break" answers
    And the task list is asked to create at the cursor
    When "j" is pressed with Option
    Then the task list is not asked again

  # ---- the net under the new-task shortcut -----------------------------------
  # Two goes at Cmd+Option+. had already been made, and on the machine
  # it was reported from it still did nothing - so the assumption both
  # of them rest on, that Tk will match a sequence naming Command and
  # Option, is the one left to drop. This reads the modifiers out of the
  # event's state instead, and identifies the key by where it sits on
  # the keyboard. Every keystroke in the window passes through it, so
  # what it does *not* do matters as much: plain Cmd+. is not bound, so
  # the net only acts when the physical period key is held with the
  # shortcut modifiers.

  Scenario: The shortcut is caught, however the key is spelt
    Given a toolbar stub whose task list listens
    When "ellipsis" is pressed under Command and Option with the "." keycode
    Then "break" answers
    And the task list is asked to create at the cursor

  Scenario: The Option bit is not insisted on
    # Losing the Option bit is one of the ways this can go wrong.
    # Insisting on it would be insisting on the thing that has gone
    # missing. Plain Cmd+. is not bound to anything here, so the net
    # still identifies the key from its keycode when the bit is lost.
    Given a toolbar stub whose task list listens
    When "ellipsis" is pressed under Command alone with the "." keycode
    Then "break" answers
    And the task list is asked to create at the cursor

  Scenario: Nothing held is left alone
    # A bare keystroke is somebody typing.
    Given a toolbar stub whose task list listens
    When "." is pressed with nothing held
    Then nothing answers
    And the task list is not asked

  Scenario: Ordinary typing is left alone
    # Every key in the window comes through here.
    Given a toolbar stub whose task list listens
    When "a" is pressed with nothing held
    Then nothing answers
    And the task list is not asked

  Scenario: Another key under the same modifiers is left alone
    # Or every Cmd+Option shortcut would make a task.
    Given a toolbar stub whose task list listens
    When "j" is pressed under Command and Option with the "j" keycode
    Then nothing answers
    And the task list is not asked
