"""
How a row is painted in the task list, and the palettes offered for it.

WHY THIS MODULE EXISTS:
======================
The chart is where dependencies get sanity-checked; the task list is where the
work actually happens, and a plan of any size is scanned rather than read. A
project manager scanning it is looking for a handful of rows - the payment
milestones, the phase gates, the things that are done - and a column saying so
does not help, because scanning means not reading columns.

So a row can be given a colour, a fill and an emphasis of its own, and those
travel with the plan.

WHY THE EMPHASIS FLAGS ARE THREE-VALUED:
========================================
A summary row is bold without anybody asking, because that is what makes the
outline readable. If bold were a plain True/False on the task, that automatic
bold would be indistinguishable from one somebody chose, and two things would
break: pressing B on a summary row would appear to do nothing (it is already
bold), and clearing a row's formatting would leave a summary looking like a
leaf.

None means "whatever this kind of row is by default", which is what a task
carries until somebody decides otherwise. See resolve.

DEVELOPMENT NOTES:
------------------
Holding no colours at all is the common case by a very long way - almost every
row in almost every plan - so a default style serialises to nothing and takes
no room in the saved file. See TaskStyle.to_dict.
"""

import re
from dataclasses import dataclass, replace
from typing import Any, Dict, Optional, Tuple

#: A colour this module will accept, written the way Tk wants it.
HEX_COLOUR = re.compile(r'^#[0-9a-fA-F]{6}$')


def normalise_colour(value: Any) -> Optional[str]:
    """
    One colour as '#rrggbb', or None where there is no usable colour.

    PARAMETERS:
    -----------
    value : Any
        A hex string, with or without its '#', in three or six digits.

    RETURNS:
    --------
    Optional[str]
        The colour in lower case with its '#', or None.

    DEVELOPMENT NOTES:
    ------------------
    Anything unreadable becomes None rather than raising. These arrive from
    saved files and from colour pickers, and a plan that will not open because
    one row carried a malformed colour would be a poor trade for a row drawn
    in the default ink.
    """
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None
    if not text.startswith('#'):
        text = '#' + text
    # '#abc' is the short form of '#aabbcc'
    if len(text) == 4:
        text = '#' + ''.join(character * 2 for character in text[1:])

    return text.lower() if HEX_COLOUR.match(text) else None


@dataclass(frozen=True)
class TaskStyle:
    """
    The formatting one row carries of its own.

    ATTRIBUTES:
    -----------
    text_color : Optional[str]
        The ink for the row, or None to use the grid's own.
    fill_color : Optional[str]
        The background for the row, or None to leave the banding showing.
    bold, italic, underline : Optional[bool]
        True or False where somebody has decided, None to follow whatever
        the row would be by default; see the note on the module.

    DEVELOPMENT NOTES:
    ------------------
    Frozen, because a style is a value rather than a thing: two rows given
    the same formatting hold equal styles and the task list uses that to
    share one Tk tag between them. A mutable style shared by accident would
    repaint rows nobody touched. Changing one means replacing it - see
    with_changes.
    """

    text_color: Optional[str] = None
    fill_color: Optional[str] = None
    bold: Optional[bool] = None
    italic: Optional[bool] = None
    underline: Optional[bool] = None

    def __post_init__(self):
        """Normalise the colours, whatever form they arrived in."""
        object.__setattr__(self, 'text_color', normalise_colour(self.text_color))
        object.__setattr__(self, 'fill_color', normalise_colour(self.fill_color))
        for name in ('bold', 'italic', 'underline'):
            value = getattr(self, name)
            object.__setattr__(self, name,
                               None if value is None else bool(value))

    @property
    def is_default(self) -> bool:
        """Whether this row has been left alone entirely."""
        return self == TaskStyle()

    def with_changes(self, **changes) -> 'TaskStyle':
        """
        A copy carrying the given changes.

        EXAMPLE:
        --------
        >>> TaskStyle().with_changes(bold=True, fill_color='#fff2cc')
        TaskStyle(text_color=None, fill_color='#fff2cc', bold=True, ...)
        """
        return replace(self, **changes)

    def to_dict(self) -> Optional[Dict[str, Any]]:
        """
        The style as a JSON-safe dictionary, or None where it is the default.

        DEVELOPMENT NOTES:
        ------------------
        None for an untouched row, and only the fields actually set for the
        rest. Almost every row in almost every plan carries no formatting, so
        writing five nulls per task would grow every saved file for nothing.
        """
        if self.is_default:
            return None

        data = {}
        for name in ('text_color', 'fill_color', 'bold', 'italic', 'underline'):
            value = getattr(self, name)
            if value is not None:
                data[name] = value
        return data

    @classmethod
    def from_any(cls, value: Any) -> 'TaskStyle':
        """
        Build a style from a dictionary, another style, or nothing at all.

        RETURNS:
        --------
        TaskStyle
            The default style for None, for an empty dictionary, and for
            anything unreadable - so a plan saved before styles existed, and
            one with a damaged entry, both open with plain rows.
        """
        if isinstance(value, cls):
            return value
        if not isinstance(value, dict):
            return cls()

        return cls(
            text_color=value.get('text_color'),
            fill_color=value.get('fill_color'),
            bold=value.get('bold'),
            italic=value.get('italic'),
            underline=value.get('underline'),
        )


@dataclass(frozen=True)
class ResolvedStyle:
    """
    What a row actually looks like, once its defaults have been folded in.

    ATTRIBUTES:
    -----------
    text_color, fill_color : Optional[str]
        As TaskStyle, still None where the grid's own colour applies.
    bold, italic, underline : bool
        Decided, one way or the other. Nothing downstream has to know what a
        summary row is by default.
    """

    text_color: Optional[str] = None
    fill_color: Optional[str] = None
    bold: bool = False
    italic: bool = False
    underline: bool = False


def resolve(style: Optional[TaskStyle], is_summary: bool = False) -> ResolvedStyle:
    """
    Fold a row's defaults into the formatting it carries.

    PARAMETERS:
    -----------
    style : Optional[TaskStyle]
        What the task carries, which may be nothing.
    is_summary : bool
        Whether this row brackets other rows. A summary is bold unless the
        style says otherwise, which is what makes an outline readable at a
        glance rather than by reading the Type column.

    RETURNS:
    --------
    ResolvedStyle
        Every emphasis decided, so the renderer needs to know nothing about
        what kind of row it is drawing.

    EXAMPLE:
    --------
    >>> resolve(TaskStyle(), is_summary=True).bold
    True
    >>> resolve(TaskStyle(bold=False), is_summary=True).bold
    False
    """
    style = style or TaskStyle()

    return ResolvedStyle(
        text_color=style.text_color,
        fill_color=style.fill_color,
        bold=is_summary if style.bold is None else style.bold,
        italic=bool(style.italic),
        underline=bool(style.underline),
    )


# ---------------------------------------------------------------------------
# What the formatting bar offers
# ---------------------------------------------------------------------------

#: The ink colours on the top row of the font-colour picker.
#:
#: Held here rather than in the toolbar that shows them, for the same reason
#: the countries are held beside the calendar: which colours a plan can be
#: marked up in is a property of the marking up, and the picker is one way of
#: choosing among them.
TEXT_COLOURS: Tuple[Tuple[str, Optional[str]], ...] = (
    ('Default', None),
    ('Red', '#c0392b'),
    ('Green', '#1e8449'),
    ('Amber', '#b9770e'),
    ('Blue', '#1f6aa5'),
    ('Slate', '#566573'),
    ('Black', '#000000'),
)

#: The fills on the background picker.
#:
#: Pale on purpose. A fill has to sit under black text and under whichever ink
#: the row was given, so anything saturated makes the row less readable than
#: the plain grid it replaced - which is the opposite of the point.
FILL_COLOURS: Tuple[Tuple[str, Optional[str]], ...] = (
    ('No fill', None),
    ('Light yellow', '#fff2cc'),
    ('Soft green', '#d5f0dc'),
    ('Soft red', '#fadbd8'),
    ('Light blue', '#d6eaf8'),
    ('Light slate', '#e5e8e8'),
)

#: The combined styles behind the preset menu, in the order it lists them.
#:
#: One click each, because these are the four things a plan actually gets
#: marked up for and picking them out of two colour menus and three toggles
#: every time is how a feature ends up unused.
PRESETS: Tuple[Tuple[str, TaskStyle], ...] = (
    ('Financial Milestone',
     TaskStyle(fill_color='#fff2cc', text_color='#000000', bold=True)),
    ('Work Complete',
     TaskStyle(text_color='#1e8449', bold=False)),
    ('Phase Gate / Approval',
     TaskStyle(text_color='#c0392b', bold=True, italic=True)),
    ('Summary Phase',
     TaskStyle(fill_color='#e5e8e8', bold=True)),
)


#: A badge drawn beside each preset in the menu, as (glyph, colour).
#:
#: The dropdown used to list the four presets as plain names, so a reader had
#: to apply one to find out what it looked like - see issue #9. A badge gives
#: each a shape and a colour to recognise it by, beside the live preview the
#: menu builds from the style itself.
#:
#: A geometric glyph rather than an emoji: these render in the one font Tk has
#: everywhere and take a colour, where a colour emoji shows as an empty box on
#: a machine whose Tk was built without one - the test display among them.
PRESET_BADGES: Dict[str, Tuple[str, str]] = {
    'Financial Milestone': ('◆', '#d4a017'),   # a filled diamond, gold
    'Work Complete':       ('●', '#1e8449'),   # a filled circle, green
    'Phase Gate / Approval': ('▲', '#c0392b'), # a triangle, red
    'Summary Phase':       ('■', '#1f3a5f'),   # a square, navy
}

#: The badge for the entry that clears a row's formatting; see issue #10.
DEFAULT_BADGE: Tuple[str, str] = ('○', '#909497')   # a hollow circle


def preset_badge(name: str) -> Tuple[str, str]:
    """
    The glyph and colour for a preset's badge, as (glyph, colour).

    A named preset the table does not know, and the default entry, both fall
    back to the hollow circle - a badge is decoration and a missing one must
    never be a reason a menu cannot be drawn.
    """
    return PRESET_BADGES.get(name, DEFAULT_BADGE)
