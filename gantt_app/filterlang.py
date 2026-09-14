"""
The query language behind the Filter window's Advanced tab.

WHY THIS MODULE EXISTS:
======================
The Basic tab's per-column controls answer the common questions; this is
the way to ask the rest - "name ~ \"art\" AND progress < 50", "type in
(Task, Milestone) or milestone = Yes", anything with a NOT or a bracket
in it. The text a reader types parses to a small tree and compiles to a
predicate over a task, so the grid filters a query the same way it
filters a saved definition.

DEVELOPMENT NOTES:
------------------
Nothing here touches a widget: tokenize, parse and compile are pure, and
the tests run them without a display. Cells are read through
views.gridfilter.column_value, so the language and the Basic tab share
one vocabulary - a field means the same thing whichever tab asked.

Values in a query are strings, numbers or dates; dates take the dotted
and slashed forms the date boxes accept as well as the dashed one.
"""

import fnmatch
from datetime import datetime
from typing import Dict, List, Optional, Set

from gantt_app.workdaycalendar import as_date
from gantt_app.views.datepicker import parse_date, DATE_FORMAT
from gantt_app.views.gridfilter import (
    ALERT_NONE, COLUMN_KIND, column_value, choice_values)


class QueryError(Exception):
    """
    A query that does not parse, with where it stopped.

    ``position`` is the character offset into the query text, so the
    window can point at the offending token the way Jira underlines it.
    """

    def __init__(self, message: str, position: int = 0):
        super().__init__(message)
        self.position = position


#: Friendly names for the grid's columns, lowercased for lookup - the
#: name a reader would naturally type for each. Quoted column names
#: ("Task Name") resolve too; see resolve_field.
FIELD_ALIASES = {
    'name': 'Task Name', 'taskname': 'Task Name',
    'label': 'Label',
    'type': 'Type', 'status': 'Status',
    'duration': 'Duration',
    'start': 'Start', 'end': 'End', 'finish': 'End',
    'progress': 'Progress',
    'dependencies': 'Dependencies', 'deps': 'Dependencies',
    'milestone': 'Milestone', 'outline': 'Outline',
    'alert': 'Alert',
    'calendar': 'Task Calendar', 'taskcalendar': 'Task Calendar',
    'baselinestart': 'Baseline Start',
    'baselinefinish': 'Baseline Finish',
    'baselineend': 'Baseline Finish',
    'startvariance': 'Start Variance',
    'finishvariance': 'Finish Variance',
    'baselineduration': 'Baseline Duration',
    'durationvariance': 'Duration Variance',
    'baselinework': 'Baseline Work',
    'workvariance': 'Work Variance',
    'baselinecost': 'Baseline Cost',
    'costvariance': 'Cost Variance',
}

#: The operator spellings, longest first so '!~' is read before '!'.
#: Each maps to a test id: the same set the definition rules use, plus
#: is_empty/is_not_empty which only the language offers.
OPERATORS = (
    ('not within', 'not_within'), ('not in', 'not_in'),
    ('is not empty', 'is_not_empty'), ('is empty', 'is_empty'),
    ('within', 'within'), ('in', 'in'),
    ('!~', 'not_contains'), ('~', 'contains'),
    ('!=', 'not_equals'), ('>=', 'gte'), ('<=', 'lte'),
    ('>', 'gt'), ('<', 'lt'), ('=', 'equals'),
)

#: Which tests each field kind allows, in the order suggestions list them.
OPERATORS_BY_KIND = {
    'text': ('contains', 'not_contains', 'equals', 'not_equals',
             'is_empty', 'is_not_empty'),
    'number': ('equals', 'not_equals', 'lt', 'lte', 'gt', 'gte',
               'within', 'not_within', 'is_empty', 'is_not_empty'),
    'date': ('equals', 'not_equals', 'lt', 'lte', 'gt', 'gte',
             'within', 'not_within', 'is_empty', 'is_not_empty'),
    'choice': ('equals', 'not_equals', 'in', 'not_in',
               'is_empty', 'is_not_empty'),
}

#: The tests that read no value at all.
NO_VALUE_TESTS = ('is_empty', 'is_not_empty')


def resolve_field(name: str) -> Optional[str]:
    """
    The grid column a query field names, or None.

    Aliases first, then the column's own name - "Task Name" and
    taskname land on the same field, and the lookup is indifferent to
    case and to quotes.
    """
    text = (name or '').strip().strip('"').strip()
    if not text:
        return None
    lowered = text.lower().replace(' ', '').replace('_', '')
    if lowered in FIELD_ALIASES:
        return FIELD_ALIASES[lowered]
    for column in COLUMN_KIND:
        if column.lower() == text.lower():
            return column
    return None


# ----------------------------------------------------------------------
# Tokenizer
# ----------------------------------------------------------------------

class _Token:
    """One scanned word: its kind, text and where it stood."""

    __slots__ = ('kind', 'text', 'pos')

    def __init__(self, kind, text, pos):
        self.kind = kind      # 'word' | 'string' | 'number' | 'op' | 'paren' | 'comma'
        self.text = text
        self.pos = pos

    def __repr__(self):
        return f"<{self.kind} {self.text!r} @{self.pos}>"


def _tokenize(text: str) -> List[_Token]:
    """
    The query as a token list.

    Words are the loosest token - an unquoted value, a field name, a
    keyword - and the parser sorts out which. Strings are double-quoted
    and may hold anything but a quote. An unrecognized character is an
    error with its position, because a stray glyph should be pointed at,
    not silently skipped.
    """
    tokens = []
    i, n = 0, len(text)
    while i < n:
        char = text[i]
        if char.isspace():
            i += 1
            continue
        if char == '"':
            end = text.find('"', i + 1)
            if end == -1:
                raise QueryError("Unclosed quote", i)
            tokens.append(_Token('string', text[i + 1:end], i))
            i = end + 1
            continue
        if char in '(),':
            tokens.append(_Token('paren' if char in '()' else 'comma',
                                 char, i))
            i += 1
            continue
        matched = False
        for spelling, _test in OPERATORS:
            if all(c in '=<>!~' for c in spelling) and \
                    text.startswith(spelling, i):
                tokens.append(_Token('op', spelling, i))
                i += len(spelling)
                matched = True
                break
        if matched:
            continue
        if char.isalnum() or char in '._-/':
            # '/' joins a word so a slashed date needs no quotes.
            start = i
            while i < n and (text[i].isalnum() or text[i] in '._-/'):
                i += 1
            word = text[start:i]
            kind = 'number' if word.replace('.', '', 1).replace(
                '-', '', 1).isdigit() else 'word'
            tokens.append(_Token(kind, word, start))
            continue
        raise QueryError(f"Unexpected character {char!r}", i)
    return tokens


# ----------------------------------------------------------------------
# Parser - or / and / not / bracket / condition
# ----------------------------------------------------------------------

#: A condition node is a plain tuple: (field, test, values, position).
#: Compound nodes are ('and'|'or'|'not', [children], position).

def _peek(tokens, index):
    return tokens[index] if index < len(tokens) else None


def _is_keyword(token, *words):
    return (token is not None and token.kind == 'word'
            and token.text.lower() in words)


def _parse_query(tokens):
    """The whole token list as a tree, or a QueryError."""
    node, index = _parse_or(tokens, 0)
    if index < len(tokens):
        raise QueryError(
            f"Unexpected {tokens[index].text!r} - "
            "expected AND, OR or the end", tokens[index].pos)
    return node


def _parse_or(tokens, index):
    node, index = _parse_and(tokens, index)
    while _is_keyword(_peek(tokens, index), 'or'):
        right, index = _parse_and(tokens, index + 1)
        node = ('or', [node, right])
    return node, index


def _parse_and(tokens, index):
    node, index = _parse_not(tokens, index)
    while _is_keyword(_peek(tokens, index), 'and'):
        right, index = _parse_not(tokens, index + 1)
        node = ('and', [node, right])
    return node, index


def _parse_not(tokens, index):
    token = _peek(tokens, index)
    if _is_keyword(token, 'not'):
        child, index = _parse_not(tokens, index + 1)
        return ('not', [child]), index
    if token is not None and token.kind == 'paren' and token.text == '(':
        node, index = _parse_or(tokens, index + 1)
        closer = _peek(tokens, index)
        if closer is None or closer.text != ')':
            pos = closer.pos if closer is not None else \
                (tokens[-1].pos + len(tokens[-1].text) if tokens else 0)
            raise QueryError("Missing closing bracket", pos)
        return node, index + 1
    return _parse_condition(tokens, index)


def _parse_condition(tokens, index):
    """
    One field/test/value triple.

    The field may be quoted ("Task Name" = ...); the test is an operator
    symbol or a keyword phrase (is empty, not in, within); the value is
    what the field's kind expects - free text, a number, a date, or one
    of the fixed set.
    """
    token = _peek(tokens, index)
    if token is None:
        pos = tokens[-1].pos + len(tokens[-1].text) if tokens else 0
        raise QueryError("Expected a field name", pos)
    if token.kind not in ('word', 'string'):
        raise QueryError(f"Expected a field name, got {token.text!r}",
                         token.pos)
    field = resolve_field(token.text)
    if field is None:
        raise QueryError(f"Unknown field {token.text!r}", token.pos)
    index += 1

    test, index = _parse_test(tokens, index, field)
    if test in NO_VALUE_TESTS:
        return (field, test, [], token.pos), index
    return _parse_values(tokens, index, field, test, token.pos)


def _parse_test(tokens, index, field):
    """The operator after a field, checked against its kind."""
    kind = COLUMN_KIND[field]
    start = _peek(tokens, index)
    if start is None:
        pos = tokens[-1].pos + len(tokens[-1].text) if tokens else 0
        raise QueryError(f"Expected an operator after {field!r}", pos)

    # Keyword phrases are words: 'not in', 'is empty', 'within'...
    phrase = None
    if start.kind == 'word':
        words = [start.text.lower()]
        for ahead in (index + 1, index + 2):
            nxt = _peek(tokens, ahead)
            if nxt is not None and nxt.kind == 'word':
                words.append(nxt.text.lower())
        for length in range(min(3, len(words)), 0, -1):
            candidate = ' '.join(words[:length])
            for spelling, test in OPERATORS:
                if spelling == candidate:
                    phrase = (test, length)
                    break
            if phrase:
                break
    if phrase is not None:
        test, eaten = phrase
        index += eaten
    elif start.kind == 'op':
        test = next(t for s, t in OPERATORS if s == start.text)
        index += 1
    else:
        raise QueryError(
            f"Expected an operator after {field!r}, got {start.text!r}",
            start.pos)

    if test not in OPERATORS_BY_KIND[kind]:
        raise QueryError(
            f"That operator does not apply to {field}", start.pos)
    return test, index


def _parse_values(tokens, index, field, test, field_pos):
    """The value(s) a test wants: one, or a bracketed list for 'in'."""
    values = []
    if test in ('in', 'not_in'):
        opener = _peek(tokens, index)
        if opener is None or opener.text != '(':
            raise QueryError(
                "Expected ( after in", opener.pos if opener else field_pos)
        index += 1
        while True:
            token = _peek(tokens, index)
            if token is None:
                raise QueryError("Missing closing bracket", field_pos)
            if token.kind == 'paren' and token.text == ')':
                index += 1
                break
            if token.kind not in ('word', 'string', 'number'):
                raise QueryError("Expected a value", token.pos)
            values.append(token.text)
            index += 1
            token = _peek(tokens, index)
            if token is not None and token.kind == 'comma':
                index += 1
                continue
            if token is not None and token.text == ')':
                index += 1
                break
            raise QueryError("Expected , or )",
                             token.pos if token else field_pos)
        return (field, test, values, field_pos), index

    token = _peek(tokens, index)
    if token is None or token.kind not in ('word', 'string', 'number'):
        raise QueryError("Expected a value",
                         token.pos if token else field_pos)
    values.append(token.text)
    index += 1

    if test in ('within', 'not_within'):
        comma = _peek(tokens, index)
        if comma is None or comma.kind != 'comma':
            raise QueryError("Expected a second value after ,",
                             comma.pos if comma else field_pos)
        index += 1
        token = _peek(tokens, index)
        if token is None or token.kind not in ('word', 'string', 'number'):
            raise QueryError("Expected a second value",
                             token.pos if token else field_pos)
        values.append(token.text)
        index += 1
    return (field, test, values, field_pos), index


# ----------------------------------------------------------------------
# The compiler - tree to predicate
# ----------------------------------------------------------------------

def _coerce_values(field: str, test: str, values: List[str],
                   project, context: Dict) -> list:
    """
    A condition's values in the field's own type.

    Choice fields match case-insensitively against the values actually
    present, so "in progress" finds "In Progress"; numbers and dates parse
    or the condition cannot match anything. A value that does not parse
    makes the condition inert rather than the query an error - the reader
    sees the row count drop to none, which is the honest answer.
    """
    kind = COLUMN_KIND[field]
    if kind == 'choice':
        present = {str(v).lower(): str(v)
                   for v in choice_values(project, field, context)}
        return [present.get(v.strip().lower(), v.strip())
                for v in values]
    if kind == 'number':
        out = []
        for v in values:
            try:
                out.append(float(v))
            except (TypeError, ValueError):
                return None
        return out
    if kind == 'date':
        out = []
        for v in values:
            parsed = parse_date(v)
            if parsed is None:
                return None
            out.append(as_date(parsed))
        return out
    return [str(v) for v in values]


def _compile(node, project, context: Dict):
    """A predicate for one parse node, closing over the plan."""
    tag = node[0]
    if tag == 'and':
        left, right = (_compile(child, project, context)
                       for child in node[1])
        return lambda task: left(task) and right(task)
    if tag == 'or':
        left, right = (_compile(child, project, context)
                       for child in node[1])
        return lambda task: left(task) or right(task)
    if tag == 'not':
        child = _compile(node[1][0], project, context)
        return lambda task: not child(task)

    field, test, raw_values, _pos = node
    kind = COLUMN_KIND[field]
    if test in NO_VALUE_TESTS:
        def empty_check(task):
            value = column_value(task, field, project, context)
            empty = value is None or value == ''
            return empty if test == 'is_empty' else not empty
        return empty_check

    values = _coerce_values(field, test, raw_values, project, context)
    if values is None:
        return lambda task: False

    def compare(task):
        value = column_value(task, field, project, context)
        if kind == 'text':
            text = str(value or '')
            wanted = values[0]
            if test == 'contains':
                return wanted.lower() in text.lower()
            if test == 'not_contains':
                return wanted.lower() not in text.lower()
            matched = fnmatch.fnmatchcase(text.lower(), wanted.lower())
            return matched if test == 'equals' else not matched
        if kind == 'choice':
            shown = ALERT_NONE if value == '' else str(value or '')
            if test in ('in', 'not_in'):
                inside = shown in values
                return inside if test == 'in' else not inside
            matched = shown == values[0]
            return matched if test == 'equals' else not matched
        if value is None:
            return False
        point = float(value) if kind == 'number' else as_date(value)
        lower = values[0]
        upper = values[1] if test in ('within', 'not_within') else None
        if test == 'equals':
            return point == lower
        if test == 'not_equals':
            return point != lower
        if test == 'lt':
            return point < lower
        if test == 'lte':
            return point <= lower
        if test == 'gt':
            return point > lower
        if test == 'gte':
            return point >= lower
        inside = lower <= point <= upper
        return inside if test == 'within' else not inside

    return compare


# ----------------------------------------------------------------------
# The public face
# ----------------------------------------------------------------------

def parse_query(text: str):
    """
    The query's tree, or a QueryError with a position.

    An empty or all-space query is legal and means "everything" - it
    parses to None, which the matching functions read as no filter.
    """
    tokens = _tokenize(text or '')
    if not tokens:
        return None
    return _parse_query(tokens)


def query_matching_ids(project, text: str,
                       variances: Dict = None) -> Set[str]:
    """The rows a query matches in their own right."""
    tree = parse_query(text)
    if tree is None:
        return {task.id for task in project.tasks}
    context = {'variances': variances or {},
               'numbers': project.display_ids(),
               'conflicts': None}
    predicate = _compile(tree, project, context)
    return {task.id for task in project.tasks if predicate(task)}


def describe(text: str) -> str:
    """The parse error for a query, or '' when it parses."""
    try:
        parse_query(text)
        return ''
    except QueryError as error:
        return str(error)


def error_position(text: str) -> Optional[int]:
    """Where a failing query stopped, for the window to underline."""
    try:
        parse_query(text)
        return None
    except QueryError as error:
        return error.position


# ----------------------------------------------------------------------
# Autocomplete - what may stand at the cursor
# ----------------------------------------------------------------------

def _in_list_field(tokens):
    """
    The field an open 'in (' list belongs to, and the values it holds.

    A stack of the brackets still open decides: each '(' remembers the
    field before its 'in' keyword - None where a bracket opened for
    grouping instead. The answer is the innermost open list's field plus
    the values already read into it, so a suggestion can skip them.
    """
    stack = []
    for i, token in enumerate(tokens):
        if token.kind == 'paren' and token.text == '(':
            field = None
            j = i - 1
            if j >= 0 and _is_keyword(tokens[j], 'in'):
                j -= 1
                if j >= 0 and _is_keyword(tokens[j], 'not'):
                    j -= 1
                if j >= 0:
                    field = resolve_field(tokens[j].text)
            stack.append((field, i))
        elif token.kind == 'paren' and token.text == ')' and stack:
            stack.pop()
    if not stack:
        return None, []
    field, opened = stack[-1]
    used = [t.text for t in tokens[opened + 1:]
            if t.kind in ('word', 'string', 'number')]
    return field, used


def suggestions(text: str, cursor: int, project=None) -> List[str]:
    """
    What may be typed next at the cursor, for the dropdown under the box.

    Read off the tokens up to the cursor rather than a parse: a half-typed
    query does not parse, and the suggestions are exactly for that moment.
    The last complete token's role decides - after a field, its operators;
    after a comparison, AND and OR; after an operator on a fixed-set field,
    or inside its 'in (' list, the values the plan actually carries.
    """
    before = (text or '')[:cursor]
    try:
        tokens = _tokenize(before)
    except QueryError:
        # An unclosed quote mid-typing: keep the tokens that scanned.
        tokens = []
        try:
            tokens = _tokenize(before[:before.rfind('"')])
        except QueryError:
            pass

    def _values_for(field, exclude=(), closer=False):
        """The plan's own values for a fixed-set field."""
        if field is None or COLUMN_KIND.get(field) != 'choice' \
                or project is None:
            return []
        context = {'variances': {}, 'numbers': {}, 'conflicts': None}
        wanted = {str(v) for v in choice_values(project, field, context)}
        offered = sorted(wanted - {str(v) for v in exclude})
        return offered + ([')'] if closer else [])

    last = tokens[-1] if tokens else None
    if last is None:
        return sorted(FIELD_ALIASES) + ['not', '(']

    # Inside an open 'in (' list the next word is one of the field's
    # values, whatever kind of token stands last.
    in_field, used = _in_list_field(tokens)
    if in_field is not None:
        offered = _values_for(in_field, exclude=used, closer=True)
        if last.kind in ('word', 'string', 'number'):
            # A value half-typed still offers the rest plus the closer.
            return offered
        return offered

    if last.kind in ('word', 'string'):
        # A word could be a field being typed, a keyword phrase mid-way
        # ('is' -> 'is empty'), or a value on a fixed-set field.
        field = resolve_field(last.text)
        if field is not None and last.kind == 'word':
            kind = COLUMN_KIND[field]
            return [s for s, t in OPERATORS
                    if t in OPERATORS_BY_KIND[kind]]
        prev = tokens[-2] if len(tokens) > 1 else None
        if prev is not None and prev.kind == 'word' and \
                resolve_field(prev.text) is not None:
            field = resolve_field(prev.text)
            kind = COLUMN_KIND[field]
            if kind == 'choice':
                offered = _values_for(field)
                if offered:
                    return offered
            return [s for s, t in OPERATORS
                    if t in OPERATORS_BY_KIND[kind]]
        if _is_keyword(last, 'is'):
            return ['is empty', 'is not empty']
        if _is_keyword(last, 'not'):
            return ['not in', 'not within'] + sorted(FIELD_ALIASES)
        if _is_keyword(last, 'and', 'or'):
            return sorted(FIELD_ALIASES) + ['not', '(']
        # Mid-word on a field name: offer the fields it prefixes.
        fields = [name for name in sorted(FIELD_ALIASES)
                  if name.startswith(last.text.lower())]
        return fields or ['and', 'or']

    if last.kind == 'number':
        return ['and', 'or']
    if last.kind == 'op':
        # An operator wants a value; a fixed-set field's are listable.
        prev = tokens[-2] if len(tokens) > 1 else None
        if prev is not None and prev.kind == 'word':
            return _values_for(resolve_field(prev.text))
        return []
    if last.kind == 'paren' and last.text == '(':
        return sorted(FIELD_ALIASES) + ['not']
    if last.kind == 'paren' and last.text == ')':
        return ['and', 'or']
    if last.kind == 'comma':
        # A comma after 'within' wants a second number or date; inside an
        # in-list the open bracket was answered above.
        return []
    return sorted(FIELD_ALIASES)
