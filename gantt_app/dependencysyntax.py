"""
Reading and writing the Dependencies column the way a planner types it.

WHY THIS MODULE EXISTS:
======================
"003SS+1d" is how every planning tool has spelt a dependency for thirty years,
and it is what somebody moving a plan across from one will type. Until now the
only way to state a link here was a dialog with four controls in it, which is
fine for one link and slow for a column of them.

The grammar is small enough to state in a sentence: a predecessor's number,
then optionally the kind of link, then optionally a lag. Everything else is
defaults - a link with no type stated is Finish-Start, and a lag with no unit
stated is days.

WHAT THE NUMBER IS:
===================
The number shown beside the predecessor in the ID column, not its identity.
The identity is a key the reader never sees - see Project.display_ids - so a
column that took it would be asking for something not on screen. Resolving the
number to the task it names is the caller's job; see Project.parse_dependencies,
which also does the checks a number alone cannot answer.

DEVELOPMENT NOTES:
------------------
Parsing reports what it could not read rather than raising or dropping it. A
column where one bad token silently vanishes is a column that loses work: the
reader sees three links go in, four come back, and no reason given.
"""

import re
from dataclasses import dataclass
from typing import List, Tuple

from gantt_app.models import DEPENDENCY_TYPES, LAG_DAYS, LAG_PERCENT

#: What separates one link from the next. Both, because a plan pasted out of
#: a spreadsheet uses whichever its locale writes lists with.
SEPARATORS = re.compile(r'[,;]')

#: One link: a number, an optional type, an optional signed lag with an
#: optional unit. Whitespace anywhere sensible.
#:
#: The number is digits only, which is what the ID column shows. A name would
#: be ambiguous against the type - "003FS" has to split one way, and a
#: predecessor called "FS" would make that impossible to decide.
TOKEN = re.compile(
    r'^\s*(?P<number>\d+)\s*'
    r'(?P<type>FS|SS|FF|SF)?\s*'
    r'(?:(?P<sign>[+-])\s*(?P<lag>\d+)\s*(?P<unit>days?|d|%)?)?\s*$',
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ParsedLink:
    """
    One link as it was typed, before it is matched to a task.

    ATTRIBUTES:
    -----------
    number : str
        The predecessor's number, exactly as written - '3' and '003' are
        both kept as they came, so an error message can quote them back.
    dep_type : str
        One of DEPENDENCY_TYPES. Finish-Start when none was stated.
    lag : int
        Days, or a percentage of the predecessor's duration; negative is
        lead time.
    lag_unit : str
        LAG_DAYS or LAG_PERCENT.
    """

    number: str
    dep_type: str = 'FS'
    lag: int = 0
    lag_unit: str = LAG_DAYS


def parse(text: str) -> Tuple[List[ParsedLink], List[str]]:
    """
    Read a Dependencies cell.

    PARAMETERS:
    -----------
    text : str
        What the reader typed: '001, 003SS+1d'. Empty means no links, which
        is how a cell is cleared.

    RETURNS:
    --------
    Tuple[List[ParsedLink], List[str]]
        The links that could be read, and a message for each token that
        could not. A token that fails is left out of the first list and
        named in the second; nothing is guessed at.

    EXAMPLE:
    --------
    >>> links, errors = parse('001, 003SS+1d')
    >>> [(l.number, l.dep_type, l.lag) for l in links]
    [('001', 'FS', 0), ('003', 'SS', 1)]
    """
    links: List[ParsedLink] = []
    errors: List[str] = []

    for token in SEPARATORS.split(text or ''):
        if not token.strip():
            continue

        found = TOKEN.match(token)
        if found is None:
            errors.append(f"Cannot read {token.strip()!r}. Write a task "
                          f"number, optionally FS, SS, FF or SF, optionally "
                          f"+2d or -1d - for example 003SS+1d.")
            continue

        links.append(_link_from(found))

    return links, errors


def _link_from(found) -> ParsedLink:
    """
    Build one link from a matched token.

    DEVELOPMENT NOTES:
    ------------------
    The regex has already decided the shape, so nothing here can fail. The
    unit is read from its first character: 'd', 'day' and 'days' all mean the
    same thing and a reader should not have to know which one is expected.
    """
    dep_type = (found.group('type') or 'FS').upper()
    if dep_type not in DEPENDENCY_TYPES:
        dep_type = 'FS'

    lag = 0
    unit = LAG_DAYS
    if found.group('lag') is not None:
        lag = int(found.group('lag'))
        if found.group('sign') == '-':
            lag = -lag
        if (found.group('unit') or '').startswith('%'):
            unit = LAG_PERCENT

    return ParsedLink(number=found.group('number'), dep_type=dep_type,
                      lag=lag, lag_unit=unit)


def format_links(dependencies, numbers) -> str:
    """
    Write a Dependencies cell back out.

    PARAMETERS:
    -----------
    dependencies : Iterable[Dependency]
        The links on a task.
    numbers : Mapping[str, int]
        Task identity to the number it is shown as; see Project.display_ids.

    RETURNS:
    --------
    str
        The links in the same grammar parse() reads, comma separated, or an
        empty string when there are none.

    DEVELOPMENT NOTES:
    ------------------
    A link whose predecessor is not in the mapping is left out. That means a
    link to a task no longer in the plan, and writing a number for it would
    invent one - the cell would then say something parse() would refuse.
    """
    written = [link.to_syntax_string(numbers[link.task_id])
               for link in dependencies if link.task_id in numbers]
    return ', '.join(written)
