"""
pytest-bdd tests for Microsoft Project import format detection.

Run with:
    python3 -m pytest tests/test_mpp_importer_bdd.py -q
"""

import os
import tempfile
from pytest_bdd import given, scenarios, then, when

from gantt_app.utils.mpp_importer import (
    BINARY_MPP_MESSAGE, OLE2_SIGNATURE, import_mpp_file, is_binary_mpp,
    looks_like_xml,
)


# Load the Gherkin scenarios
scenarios("features/mpp_importer.feature")


# TEST DATA
MSPDI = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Project xmlns="http://schemas.microsoft.com/project">'
    '<Title>Sniffed</Title><CalendarUID>1</CalendarUID>'
    '<Calendars><Calendar><UID>1</UID><Name>Standard</Name></Calendar>'
    '</Calendars>'
    '<Tasks><Task><UID>1</UID><Name>Work</Name><OutlineLevel>1</OutlineLevel>'
    '<Start>2026-07-06T08:00:00</Start><Finish>2026-07-10T17:00:00</Finish>'
    '</Task></Tasks></Project>'
)


def write_temp_file(content: bytes, suffix: str) -> str:
    """Put some bytes in a temporary file and return the path."""
    handle, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(handle, 'wb') as target:
        target.write(content)
    return path


# BACKGROUND STEPS
@given('Microsoft Project files can arrive with any extension and need format detection')
def mpp_files_need_detection():
    # This is just a background context, no action needed
    pass


# WHEN AND THEN STEPS COMBINED FOR SIMPLICITY
@when("importing an MSPDI XML file")
@then("it should return a Project")
@then("the project name should be correct")
@then("the task list should be imported")
def check_mspdi_import():
    path = write_temp_file(MSPDI.encode('utf-8'), '.xml')
    try:
        project = import_mpp_file(path)
        assert project is not None
        assert project.name == "Sniffed"
        assert [task.name for task in project.tasks] == ["Work"]
    finally:
        os.unlink(path)


@when("importing an MSPDI file named with .mpp extension")
@then("it should not be detected as binary")
@then("it should import successfully")
def check_mspdi_with_mpp_extension():
    path = write_temp_file(MSPDI.encode('utf-8'), '.mpp')
    try:
        assert not is_binary_mpp(path)
        project = import_mpp_file(path)
        assert project is not None
    finally:
        os.unlink(path)


def write_temp_mpp(suffix: str) -> str:
    """A real MPP14 file in a temporary .mpp - built, not bundled."""
    from datetime import datetime

    from tests.mpphelp import write_mpp14

    handle, path = tempfile.mkstemp(suffix=suffix)
    os.close(handle)
    write_mpp14(
        path,
        tasks=[
            dict(uid=1, name='Phase One', outline_level=1, parent_uid=0,
                 start=datetime(2026, 7, 6, 8),
                 finish=datetime(2026, 7, 7, 17), duration_days=2.0),
            dict(uid=2, name='Work', outline_level=2, parent_uid=1,
                 start=datetime(2026, 7, 6, 8),
                 finish=datetime(2026, 7, 7, 17), duration_days=2.0,
                 percent_complete=40),
            dict(uid=3, name='Done', outline_level=1, parent_uid=0,
                 start=datetime(2026, 7, 8, 8),
                 finish=datetime(2026, 7, 8, 8), duration_days=0.0),
        ],
        relations=[dict(pred=2, succ=3, type='FS', lag_days=0.0)],
        title='Binary Plan',
        project_start=datetime(2026, 7, 6, 8))
    return path


@when("importing a binary MPP file")
@then("it should be detected as binary")
@then("the binary project should import with its tasks and links")
def check_binary_mpp_import():
    path = write_temp_mpp('.mpp')
    try:
        assert is_binary_mpp(path)
        project = import_mpp_file(path)
        assert project is not None
        assert project.name == 'Binary Plan'
        names = [task.name for task in project.tasks]
        assert names == ['Phase One', 'Work', 'Done']
        work = project.tasks[1]
        assert work.parent_task_id == '1'
        assert work.progress == 40
        done = project.tasks[2]
        assert done.is_milestone
        assert [(dep.task_id, dep.dep_type)
                for dep in done.dependencies] == [('2', 'FS')]
    finally:
        os.unlink(path)


@when("importing a binary file named with .xml extension")
@then("it should be detected as binary")
@then("it should import successfully")
def check_binary_with_xml_extension():
    path = write_temp_mpp('.xml')
    try:
        assert is_binary_mpp(path)
        assert import_mpp_file(path) is not None
    finally:
        os.unlink(path)


@when("importing binary bytes that are not a project")
@then("it should be detected as binary")
@then("it should return None")
def check_corrupt_binary():
    path = write_temp_file(OLE2_SIGNATURE + b'\x00' * 128, '.mpp')
    try:
        assert is_binary_mpp(path)
        assert import_mpp_file(path) is None
    finally:
        os.unlink(path)


@when("importing a file that is neither MPP nor XML")
@then("it should not be detected as binary")
@then("it should return None")
def check_neither_format():
    path = write_temp_file(b'id,name\n1,Work\n', '.mpp')
    try:
        assert not is_binary_mpp(path)
        assert import_mpp_file(path) is None
    finally:
        os.unlink(path)


@when("importing a non-existent file")
@then("it should return None")
@then("binary detection should return False")
def check_missing_file():
    assert import_mpp_file('/nonexistent/plan.mpp') is None
    assert not is_binary_mpp('/nonexistent/plan.mpp')


@when("importing an MSPDI file with UTF-8 BOM")
@then("it should detect XML content")
@then("it should import successfully")
def check_bom_xml():
    path = write_temp_file(b'\xef\xbb\xbf' + MSPDI.encode('utf-8'), '.xml')
    try:
        assert looks_like_xml(b'\xef\xbb\xbf<?xml version="1.0"?>')
        assert import_mpp_file(path) is not None
    finally:
        os.unlink(path)


@when("importing an MSPDI file with leading whitespace")
@then("it should detect XML content")
@then("it should import successfully")
def check_whitespace_xml():
    without_declaration = MSPDI.split('?>', 1)[1]
    path = write_temp_file(b'\n  ' + without_declaration.encode('utf-8'), '.xml')
    try:
        assert looks_like_xml(b'\n  <Project>')
        assert import_mpp_file(path) is not None
    finally:
        os.unlink(path)


@then("the binary MPP message should mention \"Save As\"")
def check_message_mentions_save_as():
    assert "Save As" in BINARY_MPP_MESSAGE


@then("the binary MPP message should mention \"XML\"")
def check_message_mentions_xml():
    assert "XML" in BINARY_MPP_MESSAGE


@then("the binary MPP message should not mention tasklib")
def check_message_no_tasklib():
    assert "tasklib" not in BINARY_MPP_MESSAGE.lower()


@then("the binary MPP message should not mention pip install")
def check_message_no_pip_install():
    assert "pip install" not in BINARY_MPP_MESSAGE.lower()
