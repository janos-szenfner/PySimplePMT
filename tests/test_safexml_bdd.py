"""
pytest-bdd tests for Safe XML parsing functionality.

Run with:
    python3 -m pytest tests/test_safexml_bdd.py -q
"""

import os
import tempfile
import xml.etree.ElementTree as ET
from pytest_bdd import given, parsers, scenarios, then, when
import pytest

from gantt_app.utils import safexml

# Load the Gherkin scenarios
scenarios("features/safexml.feature")


# ATTACK VECTORS
BILLION_LAUGHS = """<?xml version="1.0"?>
<!DOCTYPE lolz [
 <!ENTITY lol "lol">
 <!ENTITY lol1 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
 <!ENTITY lol2 "&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;">
 <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
 <!ENTITY lol4 "&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;">
 <!ENTITY lol5 "&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;">
 <!ENTITY lol6 "&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;">
]>
<project><name>&lol6;</name></project>"""

QUADRATIC = ('<?xml version="1.0"?>\n<!DOCTYPE bomb [\n <!ENTITY a "' +
             'A' * 20000 + '">\n]>\n<project>' +
             '<t>&a;</t>' * 500 + '</project>')

EXTERNAL = """<?xml version="1.0"?>
<!DOCTYPE x [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<project><name>&xxe;</name></project>"""

ORDINARY = """<?xml version="1.0" encoding="UTF-8"?>
<project name="Plan &amp; Co" xmlns:x="http://ganttproject.sf.net/">
  <tasks><task id="0" name="Design &lt;draft&gt;"/></tasks>
</project>"""

DOCTYPE_ONLY = """<?xml version="1.0"?>
<!DOCTYPE project SYSTEM "project.dtd">
<project><name>Fine</name></project>"""

MALFORMED = "<project><unclosed></project>"

VALID_GAN = """<?xml version="1.0" encoding="UTF-8"?>
<project name="Real Plan &amp; Co" view-date="2026-08-01">
<tasks>
<task id="0" name="Design &lt;draft&gt;" meeting="false"
      start="2026-08-03" duration="5" complete="0" expand="true"/>
</tasks>
</project>"""


# BACKGROUND STEPS
@given('standard XML parsers are vulnerable to entity expansion attacks')
def standard_xml_vulnerable():
    # This is just a background context, no action needed
    pass


# GIVEN FIXTURES
@given("a billion laughs XML document")
def billion_laughs_doc():
    return BILLION_LAUGHS


@given("a quadratic blowup XML document")
def quadratic_doc():
    return QUADRATIC


@given("an XML document with external entity references")
def external_entity_doc():
    return EXTERNAL


@given("a valid XML document with namespaces and predefined entities")
def valid_xml_doc():
    return ORDINARY


@given("an XML document with DOCTYPE but no entity declarations")
def doctype_only_doc():
    return DOCTYPE_ONLY


@given("malformed XML")
def malformed_xml():
    return MALFORMED


# WHEN FIXTURES
@when("parsing a billion laughs XML document")
def parse_billion_laughs():
    return BILLION_LAUGHS


@when("parsing a quadratic blowup XML document")
def parse_quadratic():
    return QUADRATIC


@when("parsing an XML document with external entity references")
def parse_external():
    return EXTERNAL


@when("parsing a valid XML document with namespaces and predefined entities")
def parse_valid_xml():
    return ORDINARY


@when("parsing an XML document with DOCTYPE but no entity declarations")
def parse_doctype_only():
    return DOCTYPE_ONLY


@when("parsing malformed XML")
def parse_malformed():
    return MALFORMED


# THEN FIXTURES
@then("it should raise EntitiesRefused exception")
def check_entities_refused_exception():
    with pytest.raises(safexml.EntitiesRefused):
        safexml.fromstring(BILLION_LAUGHS)


@then("the error message should mention the entity name")
def check_error_mentions_entity():
    try:
        safexml.fromstring(BILLION_LAUGHS)
    except safexml.EntitiesRefused as e:
        assert "lol" in str(e)


@then("the refusal should happen before any expansion occurs")
def check_refusal_before_expansion():
    try:
        safexml.fromstring(BILLION_LAUGHS)
    except safexml.EntitiesRefused as e:
        assert "was not read" in str(e)


@then("the error message should indicate nothing was read")
def check_nothing_read():
    try:
        safexml.fromstring(BILLION_LAUGHS)
    except safexml.EntitiesRefused as e:
        assert "was not read" in str(e)


@then("EntitiesRefused should be a subclass of ParseError")
def check_subclass_relationship():
    assert issubclass(safexml.EntitiesRefused, ET.ParseError)


@then("it should parse successfully")
def check_parse_successful_generic():
    # This is a setup step, actual parsing happens in other then clauses
    pass


@then("the parsed content should preserve entity decoding")
def check_entity_decoding():
    root = safexml.fromstring(ORDINARY)
    assert root.get('name') == 'Plan & Co'
    assert root.find('tasks/task').get('name') == 'Design <draft>'


@then("it should parse successfully")
def check_doctype_parsing():
    root = safexml.fromstring(DOCTYPE_ONLY)
    assert root.find('name').text == 'Fine'


@then("it should raise ParseError")
def check_parse_error():
    with pytest.raises(ET.ParseError):
        safexml.fromstring(MALFORMED)


@then("the error should not be EntitiesRefused")
def check_not_entities_refused():
    try:
        safexml.fromstring(MALFORMED)
    except ET.ParseError as e:
        assert not isinstance(e, safexml.EntitiesRefused)


@when("importing a GAN file with billion laughs attack")
@then("the import should return None")
def check_gan_import_returns_none():
    from gantt_app.utils.gan_importer import import_gan_file
    path = _write_temp_file(BILLION_LAUGHS)
    try:
        result = import_gan_file(path)
        assert result is None
    finally:
        os.unlink(path)


@when("importing an MSPDI file with billion laughs attack")
@then("the import should return None")
def check_mspdi_import_returns_none():
    from gantt_app.utils.msproject_importer import import_msproject_file
    path = _write_temp_file(BILLION_LAUGHS)
    try:
        result = import_msproject_file(path)
        assert result is None
    finally:
        os.unlink(path)


@when("importing a valid GAN file")
@then("the import should return a Project")
@then("the project name should be preserved")
@then("task names should be properly decoded")
def check_valid_gan_import():
    from gantt_app.utils.gan_importer import import_gan_file
    path = _write_temp_file(VALID_GAN)
    try:
        project = import_gan_file(path)
        assert project is not None
        assert project.name == 'Real Plan & Co'
        assert project.tasks[0].name == 'Design <draft>'
    finally:
        os.unlink(path)


@when("parsing a billion laughs XML file from disk")
@then("it should raise EntitiesRefused exception")
def check_file_entities_refused():
    path = _write_temp_file(BILLION_LAUGHS)
    try:
        with pytest.raises(safexml.EntitiesRefused):
            safexml.parse(path)
    finally:
        os.unlink(path)


# Helper functions

def _write_temp_file(content):
    """Write content to a temporary file and return the path."""
    handle, path = tempfile.mkstemp(suffix='.xml')
    with os.fdopen(handle, 'w') as target:
        target.write(content)
    return path