Feature: The application log keeps a bounded, inspectable record
  The Log window reads an in-memory buffer that a configured logger
  fills; file and stderr sinks are optional. These scenarios pin the
  buffer's bounds, the helpers the window relies on, and that failures
  in imports and ribbon actions reach the log rather than stdout.
  Nothing here needs a display.

  # ---- the memory buffer -------------------------------------------------

  Scenario: Records are stored formatted
    Given a memory handler holding 5 records
    When an INFO record "hello" is emitted
    Then the buffer reads "INFO:hello"

  Scenario: The buffer is bounded
    Given a memory handler holding 5 records
    When 8 numbered INFO records are emitted
    Then the buffer holds 5 records
    And the buffer's last record says "message 7"
    And the buffer does not hold "message 0"

  Scenario: Level filtering narrows the read
    Given a memory handler holding 5 records
    And a DEBUG record "debug" is emitted
    And a WARNING record "warning" is emitted
    And an ERROR record "error" is emitted
    Then the buffer holds 3 records
    And the buffer holds 2 records at WARNING
    And the buffer holds 1 records at ERROR

  Scenario: Counting honours the level filter
    Given a memory handler holding 5 records
    And an INFO record "info" is emitted
    And an ERROR record "error" is emitted
    Then the buffer counts 2 records
    And the buffer counts 1 records at ERROR

  Scenario: Clearing empties the buffer
    Given a memory handler holding 5 records
    And an INFO record "hello" is emitted
    When the buffer is cleared
    Then the buffer holds 0 records

  Scenario: A record that cannot be formatted does not raise
    Given a memory handler holding 5 records
    When a malformed record is emitted
    Then nothing was raised

  # ---- configuring the application logger ----------------------------------

  Scenario: Setup returns the application logger
    Given logging is reset
    When logging is set up in memory only
    Then the logger is the application root
    And it does not propagate

  Scenario: Messages reach the buffer
    Given logging is set up in memory only
    When the module "demo" logs the error "something broke"
    Then the log text holds "something broke"
    And the log counts 1 record at ERROR

  Scenario: Repeated setup does not stack handlers
    Given logging is set up in memory only
    When logging is set up in memory only again
    Then it is the same logger
    And the handler count is unchanged

  Scenario: The buffer keeps debug regardless of level
    # The level argument governs the file and stderr, not the buffer -
    # the Log window offers a Debug filter, so the buffer has to hold
    # DEBUG records for it to filter.
    Given logging is set up in memory only at WARNING
    When the module "demo" logs the debug "quiet"
    And the module "demo" logs the warning "loud"
    Then the log text holds "quiet"
    And the log text holds "loud"
    And the log text at WARNING does not hold "quiet"
    And the log text at WARNING holds "loud"

  Scenario: File logging writes to disk
    Given a temporary state directory
    And logging is set up to file
    When the module "demo" logs the error "written to disk"
    Then the log file exists
    And the log file holds "written to disk"

  Scenario: An unwritable log directory does not raise
    # Startup survives a log directory that cannot be created.
    Given the log directory cannot be created
    When logging is set up to file
    And the module "demo" logs the info "still works"
    Then the log text holds "still works"
    And there is no log file path

  # ---- the helpers the Log window relies on --------------------------------

  Scenario: Module names sit under the application logger
    Given logging is set up in memory only
    Then the logger for "gantt_app.utils.thing" is "gantt_app.utils.thing"
    And the logger for "thing" is "gantt_app.thing"
    And the logger for nothing is the application root
    And the logger for the application root is the application root

  Scenario: An empty buffer reports a placeholder
    Given logging is set up in memory only
    When the log is cleared
    Then the log text at WARNING holds "No log entries"

  Scenario: Clearing leaves a marker
    Given logging is set up in memory only
    And the module "demo" logs the error "first"
    When the log is cleared
    Then the log text does not hold "first"
    And the log text holds "Log cleared"

  Scenario: Records come back as a list
    Given logging is set up in memory only
    When the module "demo" logs the warning "careful"
    Then 1 record comes back at WARNING
    And it says "careful"

  Scenario: The buffered log saves to a file
    Given logging is set up in memory only
    And the module "demo" logs the error "saved entry"
    When the log is saved to a nested file
    Then the save reported success
    And the saved file holds "PySimplePMT log export"
    And the saved file holds "saved entry"

  Scenario: Saving to an impossible path reports failure
    Given logging is set up in memory only
    When the log is saved to "/proc/definitely/not/writable/log.txt"
    Then the save reported failure

  Scenario: An exception log includes the traceback
    Given logging is set up in memory only
    When a ValueError is logged with "caught it"
    Then the log text holds "caught it"
    And the log text holds "ValueError"
    And the log text holds "Traceback"

  Scenario: The exception hook is reversible
    When the exception hook is installed
    Then it is not the original hook

  # ---- the ribbon's presses are logged -------------------------------------

  Scenario: Icon actions log under their tooltips
    Then the icon action "save_project" is labelled "Save Project"
    And the icon action "undo" is labelled "Undo"

  Scenario: Ribbon actions log under their captions
    # A split-button entry keeps its own label rather than the parent's.
    Then the ribbon action "close_project" is labelled "Close Project"
    And the ribbon action "show_log" is labelled "Event Log"
    And the ribbon action "add_phase" is labelled "Phase..."
    And the ribbon action "undo" is labelled "Undo"

  Scenario: A wrapped command logs its label then runs
    Given logging is set up in memory only
    When a command wrapped as "Export: PNG..." runs
    Then the command ran
    And the log text holds "Export: PNG..."

  Scenario: Gallery items log under their labels
    # Nested submenu items included; an item with no command passes
    # through untouched.
    Given logging is set up in memory only
    When the gallery items run
    Then both gallery commands ran
    And the log text holds "Export: PNG..."
    And the log text holds "Export: Deep"
    And the separator stayed a separator

  # ---- where the file is placed --------------------------------------------

  Scenario: The log directory is a usable absolute path
    Then the log directory is absolute
    And the log directory mentions "pysimplepmt"

  # ---- importer failures reach the log -------------------------------------

  Scenario: A missing import file is recorded
    Given logging is set up in memory only
    When a GAN file is imported from "/nonexistent/plan.gan"
    Then nothing came back
    And the log text holds "/nonexistent/plan.gan"

  Scenario: A binary mpp is not an error
    # The file is intact and the user did nothing wrong - the format
    # simply cannot be read outside Project - so the Log window's error
    # count and its Error filter must stay meaningful.
    Given logging is set up in memory only
    When a binary MPP file is imported
    Then nothing came back
    And the log counts 0 records at ERROR
    And the log text does not hold "Traceback"
    And the log text holds "Save it as XML"

  Scenario: A malformed file logs a traceback
    Given logging is set up in memory only
    When a malformed GAN file is imported
    Then nothing came back
    And the log counts at least 1 record at ERROR
    And the log text at ERROR holds "Traceback"

  # ---- the branches only a configuration reaches -------------------------------------------

  Scenario: Set up to echo, the logger gains a stream handler
    # The stderr half of "to_file and to_stderr"; the tests elsewhere
    # turn both off so the suite stays quiet.
    When logging is set up to echo
    Then the logger has a stream handler

  Scenario: Nothing configured answers empty
    # A caller asking for the log before logging exists gets nothing,
    # not a crash - the Log window can open before setup_logging runs.
    Then the log text is empty
    And the log counts 0 records

  Scenario: Interrupt defers to the previous hook without logging
    # Ctrl-C is not an error to record; it is passed straight through
    # so a terminal still behaves like a terminal.
    Given logging is set up in memory only
    When the exception hook is installed
    And a KeyboardInterrupt reaches the hook
    Then the previous hook saw it
    And the log text does not hold "Uncaught exception"
    And the original hook is restored

  Scenario: A Linux box with no XDG home uses the default state directory
    # The fallback for plain Linux: ~/.local/state/pysimplepmt.
    Given linux with no XDG state home
    Then the log directory is the default state directory
