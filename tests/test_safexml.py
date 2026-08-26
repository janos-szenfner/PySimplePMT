"""
Tests for reading XML that came from somewhere else.

WHY THIS FILE EXISTS:
=====================
The .gan and MSPDI importers read files that arrive from outside - mailed
round a team, pulled off a share - and read them with ElementTree straight,
which the standard library's own documentation lists as vulnerable to entity
expansion. It is not theoretical: measured against this application's own
parser before the guard went in, a 700-byte file expanded to three million
characters and a 150-kilobyte one to a hundred megabytes.

Nothing in a plan needs an entity of its own, so none is allowed.
"""

import os
import tempfile
import unittest
import xml.etree.ElementTree as ET

from gantt_app.utils import safexml


#: Six levels of tenfold expansion: a million copies of "lol" from 700 bytes.
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

#: One big entity referenced many times - the other shape of the same attack.
QUADRATIC = ('<?xml version="1.0"?>\n<!DOCTYPE bomb [\n <!ENTITY a "'
             + 'A' * 20000 + '">\n]>\n<project>'
             + '<t>&a;</t>' * 500 + '</project>')

#: The one that tries to read a file off the machine.
EXTERNAL = """<?xml version="1.0"?>
<!DOCTYPE x [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<project><name>&xxe;</name></project>"""

#: An ordinary plan: namespaced, and using the predefined entities that every
#: XML document may use without declaring anything.
ORDINARY = """<?xml version="1.0" encoding="UTF-8"?>
<project name="Plan &amp; Co" xmlns:x="http://ganttproject.sf.net/">
  <tasks><task id="0" name="Design &lt;draft&gt;"/></tasks>
</project>"""

#: A DOCTYPE that declares nothing, which is not the thing being guarded
#: against and must go on working.
DOCTYPE_ONLY = """<?xml version="1.0"?>
<!DOCTYPE project SYSTEM "project.dtd">
<project><name>Fine</name></project>"""


def written(text):
    """Put a document in a temporary file and return the path."""
    handle, path = tempfile.mkstemp(suffix='.xml')
    with os.fdopen(handle, 'w') as target:
        target.write(text)
    return path


class TestEntitiesAreRefused(unittest.TestCase):
    """No document read by this application declares entities of its own."""

    def test_a_billion_laughs_file_is_refused(self):
        """The file that expands to a million copies of itself."""
        with self.assertRaises(safexml.EntitiesRefused):
            safexml.fromstring(BILLION_LAUGHS)

    def test_a_quadratic_blowup_file_is_refused(self):
        """One large entity, referenced over and over."""
        with self.assertRaises(safexml.EntitiesRefused):
            safexml.fromstring(QUADRATIC)

    def test_an_external_entity_is_refused(self):
        """
        ElementTree already refuses to resolve these, so the file was never
        read off the machine. It is refused earlier and more plainly now.
        """
        with self.assertRaises(safexml.EntitiesRefused):
            safexml.fromstring(EXTERNAL)

    def test_it_is_refused_before_anything_is_expanded(self):
        """
        Which is the point: a declaration comes before the references that
        use it, so nothing large is ever built.
        """
        try:
            safexml.fromstring(BILLION_LAUGHS)
        except safexml.EntitiesRefused as refusal:
            # Named in the message so the log says which file and why
            self.assertIn('lol', str(refusal))
            self.assertIn('was not read', str(refusal))

    def test_the_refusal_is_a_parse_error(self):
        """
        So the importers, which already turn a ParseError into a logged
        failure and a None, need no new handling to handle it properly.
        """
        self.assertTrue(issubclass(safexml.EntitiesRefused, ET.ParseError))

    def test_a_file_on_disk_is_refused_too(self):
        """Which is how the importers read them."""
        path = written(BILLION_LAUGHS)
        try:
            with self.assertRaises(safexml.EntitiesRefused):
                safexml.parse(path)
        finally:
            os.unlink(path)


class TestOrdinaryFilesStillRead(unittest.TestCase):
    """A guard that refuses real plans would be worse than no guard."""

    def test_an_ordinary_document_parses(self):
        """Namespaces, attributes and the predefined entities."""
        root = safexml.fromstring(ORDINARY)

        self.assertEqual(root.get('name'), 'Plan & Co')
        self.assertEqual(root.find('tasks/task').get('name'), 'Design <draft>')

    def test_a_doctype_declaring_nothing_parses(self):
        """It is entities that are refused, not doctypes."""
        self.assertEqual(
            safexml.fromstring(DOCTYPE_ONLY).find('name').text, 'Fine')

    def test_a_file_on_disk_parses(self):
        """The path the importers take."""
        path = written(ORDINARY)
        try:
            tree = safexml.parse(path)
            self.assertEqual(tree.getroot().get('name'), 'Plan & Co')
        finally:
            os.unlink(path)

    def test_a_malformed_file_still_raises_a_parse_error(self):
        """
        And is left to the real parse to describe, which reports where the
        fault is. Two passes describing the same broken file two different
        ways would be worse than one.
        """
        with self.assertRaises(ET.ParseError) as caught:
            safexml.fromstring("<project><unclosed></project>")

        self.assertNotIsInstance(caught.exception, safexml.EntitiesRefused)


class TestTheImportersUseIt(unittest.TestCase):
    """Both formats that come from outside go through the guard."""

    def test_a_gan_bomb_is_not_imported(self):
        """It comes back as a failed import, logged, rather than as memory."""
        from gantt_app.utils.gan_importer import import_gan_file

        path = written(BILLION_LAUGHS)
        try:
            self.assertIsNone(import_gan_file(path))
        finally:
            os.unlink(path)

    def test_an_mspdi_bomb_is_not_imported(self):
        """The same file through the other importer."""
        from gantt_app.utils.msproject_importer import import_msproject_file

        path = written(BILLION_LAUGHS)
        try:
            self.assertIsNone(import_msproject_file(path))
        finally:
            os.unlink(path)

    def test_a_real_gan_file_still_imports(self):
        """The guard is not in the way of the thing it guards."""
        from gantt_app.utils.gan_importer import import_gan_file

        path = written("""<?xml version="1.0" encoding="UTF-8"?>
<project name="Real Plan &amp; Co" view-date="2026-08-01">
<tasks>
<task id="0" name="Design &lt;draft&gt;" meeting="false"
      start="2026-08-03" duration="5" complete="0" expand="true"/>
</tasks>
</project>""")
        try:
            project = import_gan_file(path)
            self.assertIsNotNone(project)
            self.assertEqual(project.name, 'Real Plan & Co')
            self.assertEqual(project.tasks[0].name, 'Design <draft>')
        finally:
            os.unlink(path)


if __name__ == '__main__':
    unittest.main()
