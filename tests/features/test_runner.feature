Feature: The test runner knows which modules only pytest can load
  The suite has two kinds of test in it: the unittest modules, and the
  pytest-bdd scenarios that only pytest can load. Handing the second
  kind to unittest does not fail politely - pytest_bdd's scenarios()
  reads the configuration of the pytest session that is running, so
  importing one of those modules outside a pytest run raises IndexError
  on an empty CONFIG_STACK even when every package is installed.

  The rule that keeps the two apart is read out of each module's own
  imports rather than written down as a list of filenames, so it cannot
  go stale when somebody adds another. That is worth a test of its own,
  because when it goes wrong the whole suite reports the wrong thing.

  This module is itself one of the pytest-only ones - where the unittest
  original checked its own name was absent, this one checks its own name
  is present. Same self-check, updated for what the file now is.

  Scenario: The rule finds the modules that import pytest
    When the pytest-only module list is read
    Then it matches what each test module's own source imports

  Scenario: An ordinary unittest module is not flagged
    When the pytest-only module list is read
    Then "test_models" is not in it
    And the module carrying these steps is in it

  Scenario: The list is sorted and carries bare module names
    When the pytest-only module list is read
    Then it is sorted
    And no name in it carries the "tests." prefix
    And no name in it ends with ".py"

  Scenario: Every named module is a file that exists
    When the pytest-only module list is read
    Then every name in it is a file in the tests directory

  Scenario: Nothing to run is not a failure
    When an empty module list is run
    Then it is reported a success
