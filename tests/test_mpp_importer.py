"""
Tests for the Microsoft Project import: telling the two formats apart.

WHY THIS MODULE EXISTS:
======================
"Import MS Project" is offered one of two entirely different files, and the
extension does not settle which: plenty of MSPDI arrives named .mpp because
somebody renamed it, and plenty of .xml on disk is something else. So the file
is sniffed rather than trusted, and this is where that is pinned down.

The binary case matters as much as the readable one. A .mpp cannot be read
outside Project, and what the application does about that - identify it, say
the one thing that fixes it, and not record it as an error - is behaviour a
user depends on, not a fallback nobody sees.

Nothing here needs a display, and nothing here needs an optional package.
"""

import os
import tempfile
import unittest

from gantt_app.utils.mpp_importer import (
    BINARY_MPP_MESSAGE, OLE2_SIGNATURE, import_mpp_file, is_binary_mpp,
    looks_like_xml,
)

#: A whole plan, small enough to write inline, in one line of MSPDI.
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


def write(content: bytes, suffix: str) -> str:
    """Put some bytes in a temporary file and return the path."""
    handle, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(handle, 'wb') as target:
        target.write(content)
    return path


class SniffingTestCase(unittest.TestCase):
    """Which format a file turns out to hold."""

    def setUp(self):
        """Track what to delete."""
        self.paths = []

    def tearDown(self):
        """Remove every file written by a test."""
        for path in self.paths:
            if os.path.exists(path):
                os.unlink(path)

    def temporary(self, content: bytes, suffix: str) -> str:
        """A temporary file that is cleaned up afterwards."""
        path = write(content, suffix)
        self.paths.append(path)
        return path

    def test_mspdi_imports(self):
        """The readable format goes through to the reader."""
        path = self.temporary(MSPDI.encode('utf-8'), '.xml')
        project = import_mpp_file(path)

        self.assertIsNotNone(project)
        self.assertEqual(project.name, "Sniffed")
        self.assertEqual([task.name for task in project.tasks], ["Work"])

    def test_the_extension_is_not_trusted(self):
        """
        MSPDI named .mpp still imports.

        Somebody sending a plan renames it more often than not, and refusing
        a readable file over its name would be a refusal on no evidence.
        """
        path = self.temporary(MSPDI.encode('utf-8'), '.mpp')

        self.assertFalse(is_binary_mpp(path))
        self.assertIsNotNone(import_mpp_file(path))

    def test_a_binary_mpp_is_recognised_and_declined(self):
        """It is identified as binary and nothing is invented from it."""
        path = self.temporary(OLE2_SIGNATURE + b'\x00' * 128, '.mpp')

        self.assertTrue(is_binary_mpp(path))
        self.assertIsNone(import_mpp_file(path))

    def test_a_binary_save_named_xml_is_still_binary(self):
        """The other half of not trusting the extension."""
        path = self.temporary(OLE2_SIGNATURE + b'\x00' * 128, '.xml')

        self.assertTrue(is_binary_mpp(path))
        self.assertIsNone(import_mpp_file(path))

    def test_something_else_entirely_is_declined(self):
        """A file that is neither is not guessed at."""
        path = self.temporary(b'id,name\n1,Work\n', '.mpp')

        self.assertFalse(is_binary_mpp(path))
        self.assertIsNone(import_mpp_file(path))

    def test_a_missing_file_returns_nothing(self):
        """No exception escapes to the caller."""
        self.assertIsNone(import_mpp_file('/nonexistent/plan.mpp'))
        self.assertFalse(is_binary_mpp('/nonexistent/plan.mpp'))

    def test_a_byte_order_mark_does_not_hide_the_xml(self):
        """
        MSPDI written on Windows usually carries one.

        Compared as raw bytes against '<?xml' every one of those files looks
        like something unrecognised, which is a whole platform's worth of
        plans refused for no reason.
        """
        path = self.temporary(b'\xef\xbb\xbf' + MSPDI.encode('utf-8'), '.xml')

        self.assertTrue(looks_like_xml(b'\xef\xbb\xbf<?xml version="1.0"?>'))
        self.assertIsNotNone(import_mpp_file(path))

    def test_leading_whitespace_does_not_hide_the_xml(self):
        """
        Legal before a root element, and templating tools leave it.

        It is not legal before an <?xml?> declaration - the parser refuses
        that, and rightly - so the sniffer's job is only to stop such a file
        being turned away as an unrecognised format before the parser has
        had a chance to say what is actually wrong with it.
        """
        without_declaration = MSPDI.split('?>', 1)[1]
        path = self.temporary(b'\n  ' + without_declaration.encode('utf-8'),
                              '.xml')

        self.assertTrue(looks_like_xml(b'\n  <Project>'))
        self.assertIsNotNone(import_mpp_file(path))


class GuidanceTestCase(unittest.TestCase):
    """What the user is told about a file that cannot be read."""

    def test_the_message_names_the_action_that_fixes_it(self):
        """
        Naming the format is not help; naming the menu path is.

        Somebody holding a .mpp needs to know it is Save As, and that XML is
        the thing to pick.
        """
        self.assertIn("Save As", BINARY_MPP_MESSAGE)
        self.assertIn("XML", BINARY_MPP_MESSAGE)

    def test_no_optional_package_is_mentioned_anywhere(self):
        """
        The old message told people to install tasklib, which is a
        Taskwarrior client and could not have helped.

        There is no optional dependency now, so nothing should ask for one.
        """
        self.assertNotIn("tasklib", BINARY_MPP_MESSAGE.lower())
        self.assertNotIn("pip install", BINARY_MPP_MESSAGE.lower())


if __name__ == '__main__':
    unittest.main()
