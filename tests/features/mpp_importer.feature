Feature: Microsoft Project import format detection
  Functionality for detecting and importing both MSPDI (XML) and binary MPP formats

  Background:
    Given Microsoft Project files can arrive with any extension and need format detection

  @mpp_importer
  Scenario: MSPDI XML file imports successfully
    When importing an MSPDI XML file
    Then it should return a Project
    And the project name should be correct
    And the task list should be imported

  @mpp_importer
  Scenario: MSPDI file with .mpp extension still imports
    When importing an MSPDI file named with .mpp extension
    Then it should not be detected as binary
    And it should import successfully

  @mpp_importer
  Scenario: Binary MPP file is recognized and declined
    When importing a binary MPP file
    Then it should be detected as binary
    And it should return None

  @mpp_importer
  Scenario: Binary file with .xml extension is still detected as binary
    When importing a binary file named with .xml extension
    Then it should be detected as binary
    And it should return None

  @mpp_importer
  Scenario: Non-MPP non-XML file is declined
    When importing a file that is neither MPP nor XML
    Then it should not be detected as binary
    And it should return None

  @mpp_importer
  Scenario: Missing file returns nothing gracefully
    When importing a non-existent file
    Then it should return None
    And binary detection should return False

  @mpp_importer
  Scenario: MSPDI file with byte order mark imports successfully
    When importing an MSPDI file with UTF-8 BOM
    Then it should detect XML content
    And it should import successfully

  @mpp_importer
  Scenario: MSPDI file with leading whitespace imports successfully
    When importing an MSPDI file with leading whitespace
    Then it should detect XML content
    And it should import successfully

  @mpp_importer
  Scenario: Binary MPP guidance message is helpful
    Then the binary MPP message should mention "Save As"
    And the binary MPP message should mention "XML"

  @mpp_importer
  Scenario: Binary MPP guidance does not mention optional packages
    Then the binary MPP message should not mention tasklib
    And the binary MPP message should not mention pip install