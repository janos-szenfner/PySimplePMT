"""
Microsoft Project import: working out what has actually been handed over.

WHY THIS MODULE EXISTS:
======================
"Import MS Project" means two different files. One is .mpp, Project's own
binary save format. The other is MSPDI, the XML Microsoft publishes a schema
for, which Project writes from File > Save As > XML and every other planning
tool reads. Only the second can be read by anything that is not Project, so
this sniffs the file it is given and sends the XML to msproject_importer.

WHAT HAPPENED TO THE OPTIONAL READER:
=====================================
This module used to call `tasklib.ProjectFile(filepath)` behind a check for
whether tasklib was installed, and reported "install tasklib" whenever the
import produced nothing - which was always. tasklib is the official Python
library for *Taskwarrior*, the command-line to-do list. It has no ProjectFile
and nothing to do with Microsoft Project, so the call raised AttributeError,
the surrounding except swallowed it, and the import returned None. Installing
the package it recommended would not have changed that. MS Project import has
therefore never worked, and the "optional dependency" was a dependency on the
wrong library for a call that could not succeed.

Nothing is optional now. MSPDI is read with the standard library, so the
feature works in a source checkout and in the packaged build alike, with
nothing installed and nothing bundled.

WHY .mpp IS STILL NOT READ:
===========================
It is an OLE2 compound document holding undocumented, partly compressed
streams whose layout changes with every release of Project. The one complete
reader is MPXJ, which is a large Java library and decades of reverse
engineering; the JPype bridge to it was removed from this application
precisely because it needed a JVM and a jar that cannot go inside a
self-contained package. There is no Python reader to bundle instead.

Guessing at the format would be worse than not reading it. A plan is acted
on: a file that half-parses into tasks with plausible names and wrong dates
is more expensive than one that refuses to open and says why. So a binary
.mpp is identified as one, and the message names the one action that turns it
into a file this application can read completely - which takes about ten
seconds in Project.
"""

from pathlib import Path
from typing import Optional

from gantt_app.models import Project
from gantt_app.utils.log import get_logger
from gantt_app.utils.msproject_importer import import_msproject_file

logger = get_logger(__name__)


#: The OLE2 compound document signature every binary .mpp starts with. Also
#: the first bytes of a .doc or an .xls, which is why it says "binary Office
#: document" rather than "Microsoft Project file".
OLE2_SIGNATURE = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'

#: How many bytes are read to tell one format from another.
SNIFF_BYTES = 512

#: What to tell somebody holding a .mpp. Kept here rather than in the dialog
#: so the log and the message box say the same thing.
BINARY_MPP_MESSAGE = (
    "This is a binary .mpp file, which only Microsoft Project itself can "
    "read.\n\n"
    "Open it in MS Project and choose File > Save As, then pick "
    "\"XML Format (*.xml)\". Importing that file brings in the whole plan - "
    "tasks, hierarchy, dependencies, calendars and progress."
)


def looks_like_xml(head: bytes) -> bool:
    """
    Whether a file's opening bytes are XML.

    DEVELOPMENT NOTES:
    ------------------
    Decoded rather than compared as bytes, because MSPDI written on Windows
    frequently carries a UTF-8 or UTF-16 byte order mark, and a comparison
    against b'<?xml' misses every one of those files. Whitespace before the
    declaration is legal and appears in files that have been through a
    templating step.
    """
    for encoding in ('utf-8-sig', 'utf-16', 'utf-8'):
        try:
            text = head.decode(encoding, errors='strict').lstrip('﻿ \t\r\n')
        except (UnicodeDecodeError, UnicodeError):
            continue
        if text.startswith('<'):
            return True
    return False


def import_mpp_file(filepath: str) -> Optional[Project]:
    """
    Import a Microsoft Project file, whichever of the two it turns out to be.

    PARAMETERS:
    -----------
    filepath : str
        Path to the file. The extension is not trusted: a .mpp that is really
        MSPDI imports, and an .xml that is really a binary save does not.

    RETURNS:
    --------
    Optional[Project]
        The plan for an MSPDI file, or None for a binary .mpp or anything
        unrecognised - with the reason in the log either way.

    EXAMPLE:
    --------
    >>> from gantt_app.utils.mpp_importer import import_mpp_file
    >>> project = import_mpp_file("/path/to/plan.xml")
    """
    path = Path(filepath)
    if not path.exists():
        logger.warning("File not found: %s", filepath)
        return None

    try:
        with open(path, 'rb') as handle:
            head = handle.read(SNIFF_BYTES)
    except OSError:
        logger.exception("Could not read %s", filepath)
        return None

    if head.startswith(OLE2_SIGNATURE):
        # Not an error: the file is intact and the user did nothing wrong,
        # so this must not count towards the Log window's error total
        logger.warning("%s is a binary Microsoft Project file, which cannot "
                       "be read outside Project. Save it as XML from Project "
                       "and import that instead.", filepath)
        return None

    if not looks_like_xml(head):
        logger.warning("%s is neither MSPDI XML nor a Microsoft Project "
                       "binary; nothing to import", filepath)
        return None

    return import_msproject_file(filepath)


def is_binary_mpp(filepath: str) -> bool:
    """
    Whether a file is a binary .mpp rather than something readable.

    RETURNS:
    --------
    bool
        True for an OLE2 compound document. Used by the import action to tell
        somebody what to do about it, rather than reporting a failure.
    """
    try:
        with open(filepath, 'rb') as handle:
            return handle.read(len(OLE2_SIGNATURE)) == OLE2_SIGNATURE
    except OSError:
        return False
