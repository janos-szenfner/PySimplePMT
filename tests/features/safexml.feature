Feature: Safe XML parsing functionality
  Security-focused XML parsing that prevents entity expansion attacks

  Background:
    Given standard XML parsers are vulnerable to entity expansion attacks

  @safexml
  Scenario: Billion laughs attack is refused
    When parsing a billion laughs XML document
    Then it should raise EntitiesRefused exception
    And the error message should mention the entity name

  @safexml
  Scenario: Quadratic blowup attack is refused
    When parsing a quadratic blowup XML document
    Then it should raise EntitiesRefused exception

  @safexml
  Scenario: External entity attack is refused
    When parsing an XML document with external entity references
    Then it should raise EntitiesRefused exception

  @safexml
  Scenario: Entities are refused before expansion
    When parsing a billion laughs XML document
    Then the refusal should happen before any expansion occurs
    And the error message should indicate nothing was read

  @safexml
  Scenario: EntitiesRefused is a ParseError subclass
    Then EntitiesRefused should be a subclass of ParseError

  @safexml
  Scenario: Ordinary XML document parses correctly
    When parsing a valid XML document with namespaces and predefined entities
    Then it should parse successfully
    And the parsed content should preserve entity decoding

  @safexml
  Scenario: DOCTYPE without entities parses correctly
    When parsing an XML document with DOCTYPE but no entity declarations
    Then it should parse successfully

  @safexml
  Scenario: Malformed XML raises ParseError
    When parsing malformed XML
    Then it should raise ParseError
    And the error should not be EntitiesRefused

  @safexml
  Scenario: GAN file with malicious entities is not imported
    When importing a GAN file with billion laughs attack
    Then the import should return None

  @safexml
  Scenario: MSPDI file with malicious entities is not imported
    When importing an MSPDI file with billion laughs attack
    Then the import should return None

  @safexml
  Scenario: Valid GAN file imports successfully
    When importing a valid GAN file
    Then the import should return a Project
    And the project name should be preserved
    And task names should be properly decoded

  @safexml
  Scenario: File-based attack is refused
    When parsing a billion laughs XML file from disk
    Then it should raise EntitiesRefused exception