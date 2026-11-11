"""
Microsoft Project import: working out what has actually been handed over.

WHY THIS MODULE EXISTS:
======================
"Import MS Project" means two different files. One is .mpp, Project's own
binary save format. The other is MSPDI, the XML Microsoft publishes a schema
for, which Project writes from File > Save As > XML and every other planning
tool reads. Both are read now - the XML goes to msproject_importer, the
binary to mpp14_reader - so this module only decides which file arrived.

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

Nothing is optional now. MSPDI is read with the standard library and the
binary with pymppwriter, a bundled dependency - so the feature works in a
source checkout and in the packaged build alike, with nothing to install.

WHY SOME .mpp STILL END UP AT SAVE AS XML:
==========================================
The binary reader covers MPP14, the format of Project 2010 through today.
Files older than that, files saved with a password, and damaged files all
fail the read honestly - and for every one of them, the ten seconds it
takes to Save As XML inside Project still produces a file this application
reads completely. That is what BINARY_MPP_MESSAGE says, and it is only
shown when the binary read did not succeed.
"""

from pathlib import Path
from typing import Optional

from gantt_app.core.models import Project
from gantt_app.utils.log import get_logger
from gantt_app.utils.mpp14_reader import import_mpp14_file
from gantt_app.utils.msproject_importer import import_msproject_file

logger = get_logger(__name__)


#: The OLE2 compound document signature every binary .mpp starts with. Also
#: the first bytes of a .doc or an .xls, which is why it says "binary Office
#: document" rather than "Microsoft Project file".
OLE2_SIGNATURE = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'

#: How many bytes are read to tell one format from another.
SNIFF_BYTES = 512

#: What to tell somebody holding a .mpp that could not be read - older
#: than Project 2010, password-protected, or damaged. Kept here rather than
#: in the dialog so the log and the message box say the same thing.
BINARY_MPP_MESSAGE = (
    "This .mpp file could not be read - it was written by a Microsoft "
    "Project older than 2010, is password-protected, or is damaged.\n\n"
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
        project = import_mpp14_file(filepath)
        if project is None:
            # Not an error: the user did nothing wrong and Save As XML is
            # still their way in, so this must stay a warning and must
            # name the way forward - the Log window mirrors the message
            # box the caller is about to show.
            logger.warning("%s is a Microsoft Project file that could "
                           "not be read. Saving it as XML from Project "
                           "would still make it importable.", filepath)
        return project

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
