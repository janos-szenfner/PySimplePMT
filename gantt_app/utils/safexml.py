"""
Reading XML from files somebody else wrote.

WHY THIS MODULE EXISTS:
======================
Two of the formats this application imports are XML: GanttProject's .gan and
Microsoft Project's MSPDI. Both arrive as files - mailed round a team, pulled
off a share - and both were read with xml.etree.ElementTree straight, which
the standard library's own documentation lists as vulnerable to entity
expansion.

That is not a theoretical entry in a table. Measured on this application's
own parser, a 700-byte file expands to three million characters, and a
150-kilobyte one to a hundred megabytes:

    <!DOCTYPE lolz [
     <!ENTITY lol "lol">
     <!ENTITY lol1 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
     ...
    ]>
    <project><name>&lol6;</name></project>

Each further level multiplies by ten, so a file small enough to attach to a
mail can ask for more memory than the machine has. Nothing in a plan needs
an entity of its own, so none is allowed.

WHAT IS NOT AT RISK:
====================
External entities - the ones that read /etc/passwd or fetch a URL - are
already refused by ElementTree, which does not resolve them and raises on an
undefined entity instead. That was checked rather than assumed. This module
closes the expansion hole, which was open.

WHY NOT defusedxml:
===================
It is the usual answer and it would work. But it is a package, and this
application bundles what it ships: see requirements.txt, which lists every
transitive dependency so the packaged set is auditable, and the note there
about what was deliberately left out. The guard needed here is one expat
handler that says no, and the standard library already has expat.

HOW IT WORKS:
=============
expat is asked to parse the document once with a single handler registered,
one that raises the moment any entity is declared. Declarations come before
the references that use them, so a hostile file is refused at the DOCTYPE
before anything is expanded - the measurements above become fractions of a
millisecond. A file that gets through that pass is then parsed normally.

The first pass registers no other handler, so it is expat tokenising at C
speed with nothing calling back into Python.
"""

import xml.etree.ElementTree as ET
import xml.parsers.expat
from pathlib import Path

from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


class EntitiesRefused(ET.ParseError):
    """
    Raised for a document that declares entities of its own.

    DEVELOPMENT NOTES:
    ------------------
    A ParseError rather than an error of its own kind, because that is what
    it means to the importers: a file that will not be read. Both of them
    already turn a ParseError into a logged failure and a None, so this
    needs no new handling at either call site to be handled properly.
    """


def _refuse_entities(data: bytes, source: str) -> None:
    """
    Raise if the document declares any entity.

    PARAMETERS:
    -----------
    data : bytes
        The whole document.
    source : str
        What to call it in the error, usually the path.

    RAISES:
    -------
    EntitiesRefused
        When an entity is declared.

    DEVELOPMENT NOTES:
    ------------------
    A malformed document is left to the real parse to report, so an expat
    error here is swallowed: this pass answers one question, and answering
    a different one badly would give the importers two places that describe
    the same broken file in two different ways.
    """
    parser = xml.parsers.expat.ParserCreate()

    def declared(name, is_parameter, value, base, system_id, public_id,
                 notation_name):
        """expat's EntityDeclHandler: any entity at all is one too many."""
        raise EntitiesRefused(
            f"{source} declares an XML entity ({name}), which a plan does "
            f"not need and which can be used to exhaust memory. The file "
            f"was not read."
        )

    parser.EntityDeclHandler = declared

    try:
        parser.Parse(data, True)
    except EntitiesRefused:
        raise
    except xml.parsers.expat.ExpatError:
        # Malformed; the real parse says so, with a position
        return


def parse(source) -> ET.ElementTree:
    """
    Read an XML file that came from somewhere else.

    PARAMETERS:
    -----------
    source : str or Path
        The file to read.

    RETURNS:
    --------
    ET.ElementTree
        The parsed document, as ET.parse would return it.

    RAISES:
    -------
    EntitiesRefused
        When the document declares entities; see the note on the module.
    ET.ParseError
        When it is not well-formed, as ET.parse raises.

    DEVELOPMENT NOTES:
    ------------------
    The bytes are read once and used for both passes, rather than opening
    the file twice. They are handed to fromstring as bytes rather than as
    text so that the encoding named in the XML declaration is the one used,
    which is the parser's business and not this function's.
    """
    data = Path(source).read_bytes()
    _refuse_entities(data, str(source))
    return ET.ElementTree(ET.fromstring(data))


def fromstring(text) -> ET.Element:
    """
    Read an XML document already in memory.

    PARAMETERS:
    -----------
    text : str or bytes
        The document.

    RETURNS:
    --------
    ET.Element
        The root element, as ET.fromstring would return it.

    RAISES:
    -------
    EntitiesRefused
        When the document declares entities; see the note on the module.
    """
    data = text.encode('utf-8') if isinstance(text, str) else text
    _refuse_entities(data, "This document")
    return ET.fromstring(data)
