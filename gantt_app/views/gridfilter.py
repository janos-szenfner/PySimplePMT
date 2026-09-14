"""
Filtering the task grid by what each column carries.

WHY THIS MODULE EXISTS:
======================
The search box finds rows by any text on them; this answers the narrower
question a project manager actually asks: "show me the tasks starting in
September", "only the milestones", "everything less than half done". Each
visible column takes a filter of its own kind - a date or number column a
range, a fixed-value column a checklist, a text column a substring - and a
row stays on screen only while every set filter passes it.

The ribbon's Filter button opens the dialog; Clear empties it again. While
a filter is in force the chart follows the grid, because the chart draws
the rows the tree is showing.

DEVELOPMENT NOTES:
------------------
The matching is pure and lives at the top of this module: column_value
reads what a cell means (a date stays a date, not its text), row passes or
not, and filtered_task_ids answers the id set the list keeps. None of it
touches a widget, so it is tested without a display. The dialog below only
collects the specs and hands them to the task list, which owns the tree.

A match keeps its ancestors on screen, as the search does: without them a
matching sub-task floats to the top level with no sign of what it belongs
to. Ancestors are shown as ordinary rows - MS Project's "related summary
rows" - and a column with no matches under a branch hides the branch.
"""

import tkinter as tk
from datetime import datetime
from typing import Dict, Optional, Set

import customtkinter as ctk

import fnmatch

from gantt_app import theme
from gantt_app.calendarregistry import PROJECT_DEFAULT_LABEL
from gantt_app.dependencysyntax import format_links
from gantt_app.workdaycalendar import as_date
from gantt_app.views.datepicker import DateEntry, DATE_FORMAT, parse_date
from gantt_app.views.modal import grab_when_visible
from gantt_app.views.scrollframe import ScrollFrame
from gantt_app.views.buttonstyle import secondary_button
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)

#: The picker rows read like menu items; the same pair the menus use.
MENU_TEXT = theme.MENU_TEXT
MENU_HOVER = theme.MENU_HOVER

#: Which kind of filter each column takes: 'text' a substring box,
#: 'number' and 'date' a From/To pair, 'choice' a tick per value present.
#: Task Name is the tree column (#0) rather than a member of
#: GRID_DATA_COLUMNS, but a name filter is the one everybody reaches for.
COLUMN_KIND = {
    'Task Name': 'text', 'Label': 'text', 'Dependencies': 'text',
    'Alert': 'choice', 'Type': 'choice', 'Status': 'choice',
    'Milestone': 'choice', 'Task Calendar': 'choice',
    'Duration': 'number', 'Progress': 'number', 'Outline': 'number',
    'Start Variance': 'number', 'Finish Variance': 'number',
    'Baseline Duration': 'number', 'Duration Variance': 'number',
    'Baseline Work': 'number', 'Work Variance': 'number',
    'Baseline Cost': 'number', 'Cost Variance': 'number',
    'Start': 'date', 'End': 'date',
    'Baseline Start': 'date', 'Baseline Finish': 'date',
}

#: How much text a text filter wants before it means anything. A letter or
#: two matches half the plan and costs a rebuild for nothing, so "art"
#: filters and "a" does not.
TEXT_MIN = 3

#: What an unticked-or-ticked Alert choice says, for a column whose real
#: values are a warning sign and nothing.
ALERT_MARK = '⚠'
ALERT_NONE = '(none)'


def column_value(task, column: str, project, context: Dict = None):
    """
    The value a grid cell carries, in its own type.

    PARAMETERS:
    -----------
    task : Task
        The row being read.
    column : str
        A grid column name - 'Task Name' for the tree column.
    project : Project
        The plan, for the questions a task cannot answer alone: its
        outline level, the calendar name it resolves to, the numbers its
        predecessors are shown as.
    context : Dict, optional
        Worked out once per filtering rather than once per row: 'variances'
        the baseline compare answers, 'conflicts' the at-risk ids the
        Alert column flags, 'numbers' the display ids.

    RETURNS:
    --------
    A str for text and choice columns, a number for number columns, a
    datetime for date columns. None where the cell is empty.
    """
    context = context or {}
    if column == 'Task Name':
        return task.name or ''
    if column == 'Label':
        return getattr(task, 'label', '') or ''
    if column == 'Type':
        return task.task_type or ''
    if column == 'Status':
        return task.status or ''
    if column == 'Milestone':
        return 'Yes' if task.effective_milestone else 'No'
    if column == 'Alert':
        conflicts = context.get('conflicts')
        if conflicts is None and project is not None:
            # Worked out once and handed back through the context, so a
            # plan filtered on Alert does not recompute it per row.
            conflicts = project.tasks_in_conflict()
            context['conflicts'] = conflicts
        return ALERT_MARK if task.id in (conflicts or ()) else ''
    if column == 'Task Calendar':
        named = project.calendars.get(getattr(task, 'calendar_id', None))
        return named.name if named is not None else PROJECT_DEFAULT_LABEL
    if column == 'Dependencies':
        numbers = context.get('numbers')
        if numbers is None and project is not None:
            numbers = project.display_ids()
        return format_links(task.dependencies, numbers or {})
    if column == 'Outline':
        return project.outline_level(task.id) if project is not None else 1
    if column == 'Duration':
        if task.is_container and project is not None:
            return project.working_duration(task)
        return task.duration_days
    if column == 'Progress':
        return task.progress
    if column == 'Start':
        return task.start_date
    if column == 'End':
        return task.end_date

    variance = (context.get('variances') or {}).get(task.id)
    if column == 'Baseline Start':
        return variance.baseline_start if variance is not None else None
    if column == 'Baseline Finish':
        return variance.baseline_finish if variance is not None else None
    if column == 'Start Variance':
        return variance.start_variance_days if variance is not None else None
    if column == 'Finish Variance':
        return variance.finish_variance_days if variance is not None else None
    if column == 'Baseline Duration':
        return variance.baseline_duration if variance is not None else None
    if column == 'Duration Variance':
        return variance.duration_variance_days if variance is not None else None
    if column == 'Baseline Work':
        return variance.baseline_work if variance is not None else None
    if column == 'Work Variance':
        return variance.work_variance_hours if variance is not None else None
    if column == 'Baseline Cost':
        return variance.baseline_cost if variance is not None else None
    if column == 'Cost Variance':
        return variance.cost_variance if variance is not None else None
    return None


def choice_values(project, column: str, context: Dict = None) -> list:
    """
    The distinct values a fixed-set column carries in this plan, sorted.

    What the checklist offers: Type and Status have a closed list, Task
    Calendar lists whichever calendars the plan names, Alert offers the
    warning sign and "(none)" for the rows that carry nothing.
    """
    values = {column_value(task, column, project, context)
              for task in project.tasks}
    if column == 'Alert':
        return sorted(ALERT_NONE if v == '' else v for v in values)
    return sorted(v for v in values if v not in (None, ''))


def filter_is_active(column: str, spec, project=None,
                     context: Dict = None) -> bool:
    """
    Whether a spec actually rules any row out.

    An empty text box, a range with no ends and a checklist with every
    value ticked all pass everything, so they count as no filter - the
    grid would otherwise be rebuilt for a spec that changes nothing.
    """
    if spec is None:
        return False
    kind = COLUMN_KIND.get(column)
    if kind == 'text':
        return len((spec.get('text') or '').strip()) >= TEXT_MIN
    if kind == 'number':
        return spec.get('min') is not None or spec.get('max') is not None
    if kind == 'date':
        return spec.get('from') is not None or spec.get('to') is not None
    if kind == 'choice':
        allowed = spec.get('allowed')
        if allowed is None or project is None:
            return allowed is not None
        present = set(choice_values(project, column, context))
        shown = {ALERT_NONE if v == '' else v for v in allowed}
        return shown != present
    return False


def row_matches(task, column: str, spec, project,
                context: Dict = None) -> bool:
    """
    Whether one row passes one column's filter.

    A spec that asks nothing passes everything - see filter_is_active - so
    a half-typed word does not empty the grid while it is being typed.
    """
    if not filter_is_active(column, spec, project, context):
        return True
    kind = COLUMN_KIND.get(column)
    value = column_value(task, column, project, context)

    if kind == 'text':
        return spec['text'].strip().lower() in str(value or '').lower()
    if kind == 'number':
        if value is None:
            return False
        lower, upper = spec.get('min'), spec.get('max')
        if lower is not None and value < lower:
            return False
        if upper is not None and value > upper:
            return False
        return True
    if kind == 'date':
        if value is None:
            return False
        day = as_date(value)
        lower, upper = spec.get('from'), spec.get('to')
        if lower is not None and day < as_date(lower):
            return False
        if upper is not None and day > as_date(upper):
            return False
        return True
    if kind == 'choice':
        shown = ALERT_NONE if value == '' else value
        return shown in {ALERT_NONE if v == '' else v
                         for v in spec.get('allowed', ())}
    return True


def filtered_task_ids(project, filters: Dict,
                      variances: Dict = None) -> Optional[Set[str]]:
    """
    Which rows a set of column filters leaves on screen.

    PARAMETERS:
    -----------
    project : Project
        The plan being filtered.
    filters : Dict
        Column name to spec; see COLUMN_KIND for the shapes.
    variances : Dict, optional
        The baseline compare's answers, for the baseline columns. None
        while no baseline is compared, which is also when those columns
        are off the grid.

    RETURNS:
    --------
    Optional[Set[str]]
        The ids to show - matches and their ancestors - or None when no
        filter is set, which the task list reads as "everything".

    DEVELOPMENT NOTES:
    ------------------
    Every set filter has to pass for a row to stay - the columns AND, the
    way MS Project's AutoFilter combines its column rules. A match keeps
    its ancestors so a found sub-task still shows the phase it sits in.
    """
    context = {
        'variances': variances or {},
        'numbers': project.display_ids(),
        'conflicts': None,  # asked lazily, and only by the Alert column
    }
    active = {column: spec for column, spec in (filters or {}).items()
              if filter_is_active(column, spec, project, context)}
    if not active:
        return None

    by_id = {task.id: task for task in project.tasks}
    visible: Set[str] = set()

    for task in project.tasks:
        if not all(row_matches(task, column, spec, project, context)
                   for column, spec in active.items()):
            continue
        visible.add(task.id)

        # Ancestors come along for context - a looped parent chain on a
        # damaged file is walked once rather than forever.
        seen = {task.id}
        parent_id = task.parent_task_id
        while parent_id and parent_id not in seen:
            seen.add(parent_id)
            visible.add(parent_id)
            parent = by_id.get(parent_id)
            if parent is None:
                break
            parent_id = parent.parent_task_id

    return visible


def matching_task_ids(project, filters: Dict,
                      variances: Dict = None) -> Set[str]:
    """The rows matching in their own right - what the count reports."""
    context = {'variances': variances or {}, 'numbers': project.display_ids(),
               'conflicts': None}
    active = {column: spec for column, spec in (filters or {}).items()
              if filter_is_active(column, spec, project, context)}
    if not active:
        return set()
    return {task.id for task in project.tasks
            if all(row_matches(task, column, spec, project, context)
                   for column, spec in active.items())}


# ------------------------------------------------------------------
# Named filter definitions
# ------------------------------------------------------------------
#
# A saved filter is a name, a show-in-menu flag and a list of rules; each
# rule is {join, field, test, value, value2?} with every value a string.
# Rows chain the way MS Project's Filter Definition reads them: an 'or'
# join starts a new group, so "A and B or C and D" means
# (A and B) or (C and D). The first row's join is ignored, as is MS's.

#: The tests each kind of field offers, by identifier. The labels the
#: dialog shows for them sit in TEST_LABELS.
TESTS_BY_KIND = {
    'text': ('equals', 'does_not_equal', 'contains', 'does_not_contain'),
    'number': ('equals', 'does_not_equal', 'lt', 'lte', 'gt', 'gte',
               'within', 'not_within'),
    'date': ('equals', 'does_not_equal', 'lt', 'lte', 'gt', 'gte',
             'within', 'not_within'),
    'choice': ('equals', 'does_not_equal', 'is_one_of', 'not_one_of'),
}

TEST_LABELS = {
    'equals': "equals",
    'does_not_equal': "does not equal",
    'contains': "contains",
    'does_not_contain': "does not contain",
    'lt': "is less than",
    'lte': "is less than or equal to",
    'gt': "is greater than",
    'gte': "is greater than or equal to",
    'within': "is within",
    'not_within': "is not within",
    'is_one_of': "is one of",
    'not_one_of': "is not one of",
}

#: The tests that take two values; every other test takes one.
TWO_VALUE_TESTS = ('within', 'not_within')

#: The fields a definition may name, in the order the dialog lists them -
#: the tree column first, then the data columns in grid order.
FILTER_FIELDS = ['Task Name'] + [
    c for c in COLUMN_KIND if c != 'Task Name']


def _rule_value(rule: Dict, which: str = 'value') -> str:
    """The string a rule carries under a key; never None, never raises."""
    value = rule.get(which)
    return str(value).strip() if value is not None else ''


def rule_matches(task, rule: Dict, project,
                 context: Dict = None) -> bool:
    """
    Whether one row passes one rule of a named filter.

    A rule naming a field or a test this build does not know cannot match -
    a file can outlive the vocabulary it was written with, and the honest
    answer to an unreadable rule is no row, not an exception. The same for
    a value that will not parse as its field's kind, and for a cell that
    is empty where the rule wants a number or a date.
    """
    field = rule.get('field')
    kind = COLUMN_KIND.get(field)
    test = rule.get('test')
    if kind is None or test not in TESTS_BY_KIND.get(kind, ()):
        return False
    value = column_value(task, field, project, context)

    if kind == 'text':
        text = str(value or '')
        wanted = _rule_value(rule)
        if test == 'contains':
            return wanted.lower() in text.lower()
        if test == 'does_not_contain':
            return wanted.lower() not in text.lower()
        # Equals and its negative take MS Project's wildcards: * any run
        # of characters, ? one character. A pattern without them is a
        # plain case-insensitive equality.
        matched = fnmatch.fnmatchcase(text.lower(), wanted.lower())
        return matched if test == 'equals' else not matched

    if kind == 'choice':
        shown = ALERT_NONE if value == '' else str(value or '')
        if test in ('is_one_of', 'not_one_of'):
            # The saved shape is a list; a comma-joined string is read the
            # same, so a hand-edited file still works.
            wanted = rule.get('value')
            if isinstance(wanted, str):
                wanted = [v.strip() for v in wanted.split(',')]
            inside = shown in (wanted or [])
            return inside if test == 'is_one_of' else not inside
        matched = shown == _rule_value(rule)
        return matched if test == 'equals' else not matched

    # Number and date share the shape: compare the cell's typed value
    # against the rule's parsed bound(s).
    if value is None:
        return False
    if kind == 'number':
        try:
            point = float(value)
            lower = float(_rule_value(rule))
            upper = (float(_rule_value(rule, 'value2'))
                     if test in TWO_VALUE_TESTS else None)
        except (TypeError, ValueError):
            return False
    else:
        point = as_date(value)
        lower = parse_date(_rule_value(rule))
        upper = (parse_date(_rule_value(rule, 'value2'))
                 if test in TWO_VALUE_TESTS else None)
        if lower is not None:
            lower = as_date(lower)
        if upper is not None:
            upper = as_date(upper)
        if lower is None or (test in TWO_VALUE_TESTS and upper is None):
            return False

    if test == 'equals':
        return point == lower
    if test == 'does_not_equal':
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


def definition_matching_ids(project, definition: Dict,
                            variances: Dict = None) -> Set[str]:
    """
    The rows a named filter matches in their own right.

    The definition carries either And/Or 'rules' or a 'query' - the
    Advanced tab's text, saved under a name. An empty rule list or an
    unparseable query matches nothing rather than everything: an
    unfinished filter hiding the whole grid is the kind of surprise that
    reads as a defect.
    """
    definition = definition or {}
    if definition.get('query'):
        from gantt_app import filterlang
        try:
            return filterlang.query_matching_ids(
                project, definition['query'], variances)
        except filterlang.QueryError:
            return set()
    rules = definition.get('rules') or []
    if not rules:
        return set()
    context = {'variances': variances or {},
               'numbers': project.display_ids(),
               'conflicts': None}

    # 'or' opens a new group; every other join extends the current one.
    groups = [[]]
    for index, rule in enumerate(rules):
        if index > 0 and rule.get('join') == 'or':
            groups.append([rule])
        else:
            groups[-1].append(rule)

    return {task.id for task in project.tasks
            if any(all(rule_matches(task, rule, project, context)
                       for rule in group) for group in groups)}


def _with_ancestors(project, matches: Set[str]) -> Set[str]:
    """
    A match set plus the chain above each of its rows.

    A found sub-task shown without its phase floats to the top level with
    no sign of what it belongs to; the phase rows come along as context,
    as they do for the column filters and the search.
    """
    by_id = {task.id: task for task in project.tasks}
    visible = set(matches)
    for task_id in matches:
        seen = {task_id}
        parent_id = getattr(by_id.get(task_id), 'parent_task_id', None)
        while parent_id and parent_id not in seen:
            seen.add(parent_id)
            visible.add(parent_id)
            parent = by_id.get(parent_id)
            if parent is None:
                break
            parent_id = parent.parent_task_id
    return visible


def definition_visible_ids(project, definition: Dict,
                           variances: Dict = None) -> Optional[Set[str]]:
    """
    The rows a named filter leaves on screen: matches and their ancestors.

    None rather than a set while the definition carries no rules, so the
    caller reads it the way it reads the column filters' None: nothing is
    being filtered.
    """
    definition = definition or {}
    if not definition.get('rules') and not definition.get('query'):
        return None
    return _with_ancestors(
        project, definition_matching_ids(project, definition, variances))


def specs_to_rules(filters: Dict, project=None) -> list:
    """
    The per-column dialog's specs as definition rules, for Save As.

    A range with both ends becomes 'within', one end its one-sided test;
    a checklist becomes one 'equals' rule per allowed value, 'or'-joined -
    the definition's way of saying what the ticks said. A spec that asks
    nothing contributes no rule, and a definition built of no rules is a
    filter that was never saved.
    """
    rules = []
    for column, spec in (filters or {}).items():
        kind = COLUMN_KIND.get(column)
        if spec is None:
            continue
        if kind == 'text':
            text = (spec.get('text') or '').strip()
            if len(text) >= TEXT_MIN:
                rules.append({'field': column, 'test': 'contains',
                              'value': text})
        elif kind == 'number':
            lower, upper = spec.get('min'), spec.get('max')
            if lower is not None and upper is not None:
                rules.append({'field': column, 'test': 'within',
                              'value': str(lower), 'value2': str(upper)})
            elif lower is not None:
                rules.append({'field': column, 'test': 'gte',
                              'value': str(lower)})
            elif upper is not None:
                rules.append({'field': column, 'test': 'lte',
                              'value': str(upper)})
        elif kind == 'date':
            lower, upper = spec.get('from'), spec.get('to')
            stamp = lambda d: d.strftime(DATE_FORMAT)
            if lower is not None and upper is not None:
                rules.append({'field': column, 'test': 'within',
                              'value': stamp(lower), 'value2': stamp(upper)})
            elif lower is not None:
                rules.append({'field': column, 'test': 'gte',
                              'value': stamp(lower)})
            elif upper is not None:
                rules.append({'field': column, 'test': 'lte',
                              'value': stamp(upper)})
        elif kind == 'choice':
            allowed = spec.get('allowed')
            if allowed is None:
                continue
            present = (set(choice_values(project, column))
                       if project is not None else None)
            if present is not None and set(allowed) == present:
                continue
            # One rule carrying the whole set: "Type is one of Task,
            # Milestone" - the flat And/Or chain cannot say "(this or
            # that) and (those)", and it does not have to.
            rules.append({'field': column, 'test': 'is_one_of',
                          'value': sorted(str(v) for v in allowed)})
    # Every rule after the first joins with 'and' - the first row's join
    # is read but ignored, the way MS Project's is.
    for index, rule in enumerate(rules):
        rule['join'] = 'and'
    return rules


def field_name_for_query(column: str) -> str:
    """
    The way a column is written in a query.

    The shortest alias that resolves back to it, or the column's own name
    quoted when it holds a space - "Task Name" stays readable either way.
    """
    from gantt_app.filterlang import FIELD_ALIASES, resolve_field
    best = None
    for alias, target in FIELD_ALIASES.items():
        if target == column and (best is None or len(alias) < len(best)):
            best = alias
    if best is not None:
        return best
    return f'"{column}"' if ' ' in column else column


def specs_to_query(filters: Dict, project=None) -> str:
    """
    The Basic tab's specs as Advanced-tab text.

    The inverse of query_to_specs, used when the reader switches tabs:
    the form's rules are written out as the query that asks the same
    thing. A spec that asks nothing contributes nothing.
    """
    parts = []
    for column, spec in (filters or {}).items():
        if spec is None or not filter_is_active(column, spec, project):
            continue
        kind = COLUMN_KIND.get(column)
        name = field_name_for_query(column)
        if kind == 'text':
            parts.append(f'{name} ~ "{spec["text"].strip()}"')
        elif kind == 'number':
            lower, upper = spec.get('min'), spec.get('max')
            if lower is not None and upper is not None:
                parts.append(f'{name} within {lower}, {upper}')
            elif lower is not None:
                parts.append(f'{name} >= {lower}')
            else:
                parts.append(f'{name} <= {upper}')
        elif kind == 'date':
            lower, upper = spec.get('from'), spec.get('to')
            stamp = lambda d: d.strftime(DATE_FORMAT)
            if lower is not None and upper is not None:
                parts.append(f'{name} within {stamp(lower)}, '
                             f'{stamp(upper)}')
            elif lower is not None:
                parts.append(f'{name} >= {stamp(lower)}')
            else:
                parts.append(f'{name} <= {stamp(upper)}')
        elif kind == 'choice':
            allowed = sorted(str(v) for v in spec.get('allowed', ()))
            if len(allowed) == 1:
                parts.append(f'{name} = "{allowed[0]}"')
            else:
                parts.append(f"{name} in ("
                             + ", ".join(f'"{v}"' for v in allowed) + ")")
    return ' and '.join(parts)


def query_to_specs(text: str, project=None) -> Optional[Dict]:
    """
    The Basic-tab equivalent of a query, or None where there is none.

    Only a flat AND of conditions the columns can express converts -
    the same limit Jira's Basic mode has. Contains becomes the text box,
    a two-ended range or an equals becomes min and max, a one-ended range
    its single end, and equals/in on a fixed-set field becomes the
    checklist. Anything with or, not or a bracket answers None and stays
    on the Advanced tab.
    """
    from gantt_app import filterlang

    try:
        tree = filterlang.parse_query(text)
    except filterlang.QueryError:
        return None
    if tree is None:
        return {}
    conditions = [tree] if tree[0] not in ('and', 'or', 'not') else None
    if tree[0] == 'and':
        conditions = tree[1]
        # A chain of ands nests left-deep: flatten it.
        while conditions and conditions[0][0] == 'and':
            conditions = conditions[0][1] + conditions[1:]
    if conditions is None:
        return None
    if any(c[0] in ('and', 'or', 'not') for c in conditions):
        return None

    specs = {}
    # A fixed-set value is canonicalized against what the plan carries,
    # so "in progress" lands on "In Progress" in the checklist.
    present = {}
    if project is not None:
        for field_name in FILTER_FIELDS:
            if COLUMN_KIND.get(field_name) == 'choice':
                present[field_name] = {
                    str(v).lower(): v
                    for v in choice_values(project, field_name)}

    try:
        for field, test, values, _pos in conditions:
            kind = COLUMN_KIND.get(field)
            if field in specs:
                return None  # two conditions on one column - can't show
            if kind == 'text':
                if test != 'contains':
                    return None
                specs[field] = {'text': values[0]}
            elif kind == 'number':
                spec = {'min': None, 'max': None}
                if test == 'equals':
                    spec = {'min': float(values[0]),
                            'max': float(values[0])}
                elif test == 'within':
                    spec = {'min': float(values[0]),
                            'max': float(values[1])}
                elif test == 'gte':
                    spec['min'] = float(values[0])
                elif test == 'lte':
                    spec['max'] = float(values[0])
                else:
                    return None
                specs[field] = spec
            elif kind == 'date':
                days = [parse_date(v) for v in values]
                if any(d is None for d in days):
                    return None
                spec = {'from': None, 'to': None}
                if test == 'equals':
                    spec = {'from': days[0], 'to': days[0]}
                elif test == 'within':
                    spec = {'from': days[0], 'to': days[1]}
                elif test == 'gte':
                    spec['from'] = days[0]
                elif test == 'lte':
                    spec['to'] = days[0]
                else:
                    return None
                specs[field] = spec
            elif kind == 'choice':
                canonical = [present.get(field, {}).get(
                    str(v).strip().lower(), str(v).strip())
                    for v in values]
                if test == 'equals':
                    specs[field] = {'allowed': {canonical[0]}}
                elif test == 'in':
                    specs[field] = {'allowed': set(canonical)}
                elif test in ('not_equals', 'not_in') \
                        and project is not None:
                    # A whitelist only: "not X" is "everything but X".
                    excluded = {canonical[0]} if test == 'not_equals' \
                        else set(canonical)
                    specs[field] = {
                        'allowed': set(present.get(field, ())) - excluded}
                else:
                    return None
            else:
                return None
    except (ValueError, IndexError):
        return None
    return specs


class GridFilterDialog(ctk.CTkToplevel):
    """
    The window the View tab's Filter button opens.

    PARAMETERS:
    -----------
    master : widget
        The application window.
    columns : list
        The grid's visible columns in display order, Task Name first.
    current : Dict
        The specs already in force, so reopening shows what is set rather
        than a fresh form.
    values : callable
        column name -> the distinct values to offer a choice column.
    on_apply : callable
        Given the spec dict when Apply is pressed.
    on_clear : callable
        Run by Clear All, which also empties every control.
    on_save_as : callable, optional
        Given the collected specs by Save As..., which stores them as a
        named filter - MS Project's AutoFilter Save. No button when absent.

    DEVELOPMENT NOTES:
    ------------------
    One section per visible column, control by kind: a box for text, a
    From/To pair for numbers and dates, a checklist for the columns with a
    fixed set. Nothing applies until Apply - a half-typed date or a
    checklist mid-way through being unticked should not rebuild the grid
    under the window the reader is still working in.
    """

    def __init__(self, master, columns, current, values, on_apply, on_clear,
                 on_save_as=None, project=None, variances=None,
                 query='', history=None):
        super().__init__(master)
        self.title("Filter Tasks")
        self.transient(master)
        self._on_apply = on_apply
        self._on_clear = on_clear
        self._on_save_as = on_save_as
        self._values = values
        self._project = project
        self._variances = variances
        self._history = list(history or [])
        #: The control each section feeds back into a spec, by column.
        self._controls = {}
        self._suggest_after = None
        self._suggest_popup = None

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=12, pady=(12, 4))
        ctk.CTkLabel(
            head, text="Show only the rows where every set rule passes.",
            text_color=theme.MUTED_TEXT,
            font=ctk.CTkFont(size=12),
        ).pack(anchor="w")

        # Basic is the per-column form; Advanced is the query box. The
        # tabview's command carries the state across on every switch.
        self.tabview = ctk.CTkTabview(self, command=self._tab_switched)
        self.tabview.pack(fill="both", expand=True, padx=12, pady=4)
        basic = self.tabview.add("Basic")
        advanced = self.tabview.add("Advanced")

        self._body = ScrollFrame(basic, height=420)
        self._body.pack(fill="both", expand=True)
        for column in columns:
            self._build_section(column, (current or {}).get(column))

        self._build_advanced(advanced, query)

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", padx=12, pady=(4, 12))
        ctk.CTkButton(buttons, text="Apply", width=90,
                      command=self._apply).pack(side="right", padx=(6, 0))
        secondary_button(buttons, "Close", self.destroy,
                         width=70).pack(side="right")
        secondary_button(buttons, "Clear All", self._clear_all,
                         width=80).pack(side="left")
        if self._on_save_as is not None:
            secondary_button(buttons, "Save As...", self._save_as,
                             width=80).pack(side="left", padx=(6, 0))

        if query:
            # set() rather than _set_tab: the prefilled query is the
            # state, not something to re-render from the Basic specs.
            self.tabview.set("Advanced")

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        grab_when_visible(self)

    # ------------------------------------------------------------------
    # The Advanced tab
    # ------------------------------------------------------------------

    def _build_advanced(self, tab, query):
        """The query box, its verdict line, and the recent queries."""
        from gantt_app import filterlang

        ctk.CTkLabel(
            tab,
            text='Write the filter: name ~ "art" and progress < 50, '
                 'type in (Task, Milestone), start >= 2026-09-01.',
            anchor="w", wraplength=520, justify="left",
            text_color=theme.MUTED_TEXT,
            font=ctk.CTkFont(size=12),
        ).pack(fill="x", pady=(6, 4))

        entry_row = ctk.CTkFrame(tab, fg_color="transparent")
        entry_row.pack(fill="x")
        self._query_entry = ctk.CTkEntry(
            entry_row, placeholder_text='status = "In Progress" ...')
        self._query_entry.pack(side="left", fill="x", expand=True)
        if query:
            self._query_entry.insert(0, query)
        if self._history:
            secondary_button(
                entry_row, "Recent", self._post_history,
                width=64).pack(side="left", padx=(6, 0))

        self._query_status = ctk.CTkLabel(tab, text="", anchor="w",
                                          font=ctk.CTkFont(size=12))
        self._query_status.pack(fill="x", pady=(4, 0))

        self._query_entry.bind('<KeyRelease>', lambda _e:
                               self._query_changed())
        self._query_entry.bind('<Return>', lambda _e: self._apply())
        self._query_entry.bind('<Escape>', lambda _e:
                               self._close_suggestions())
        self._query_entry.bind('<Down>', lambda _e: self._open_suggestions())
        self._query_changed()

    def _post_history(self):
        """The Recent button's menu: past queries, newest first."""
        menu = tk.Menu(self, tearoff=0)
        for query in self._history:
            menu.add_command(
                label=query,
                command=lambda q=query: (
                    self._query_entry.delete(0, 'end'),
                    self._query_entry.insert(0, q),
                    self._query_changed()))
        button = self._query_entry
        try:
            menu.post(button.winfo_rootx() + button.winfo_width(),
                      button.winfo_rooty() + button.winfo_height())
        except tk.TclError:
            pass

    def _set_tab(self, name: str):
        """
        Switch the tab the way a click does.

        CTkTabview.set() moves the tabs but not the command - only the
        segmented button's own callback runs it - so a programmatic switch
        calls the carry-over itself.
        """
        self.tabview.set(name)
        self._tab_switched()

    def _active_tab(self) -> str:
        """'advanced' while the query tab is the one on show."""
        return 'advanced' if self.tabview.get() == "Advanced" else 'basic'

    def _query_changed(self):
        """
        Re-read the box after each keystroke.

        The verdict line answers before Apply does: a parse error in red
        with where it stopped, or the match count in green - the reader
        sees what the query will do while writing it. The suggestion list
        is rebuilt on the same keystroke.
        """
        from gantt_app import filterlang

        text = self._query_entry.get()
        try:
            parse_query_text = filterlang.parse_query(text)
        except filterlang.QueryError as error:
            self._query_status.configure(
                text=f"✗ {error} (position {error.position})",
                text_color=('#b00020', '#ff6b6b'))
            self._offer_suggestions()
            return
        try:
            matches = filterlang.query_matching_ids(
                self._project, text, self._variances) \
                if self._project is not None else set()
            note = ("everything" if filterlang.parse_query(text) is None
                    else f"{len(matches)} row(s) match")
            self._query_status.configure(
                text=f"✓ {note}",
                text_color=theme.POSITIVE_TEXT)
        except Exception as error:
            self._query_status.configure(
                text=f"✓ parses; matching failed: {error}",
                text_color=theme.MUTED_TEXT)
        self._offer_suggestions()

    # ------------------------------------------------------------------
    # Suggestions - the dropdown that knows what may come next
    # ------------------------------------------------------------------

    def _offer_suggestions(self):
        """Refresh the floating suggestion list for the cursor's spot."""
        if self._active_tab() != 'advanced':
            return
        from gantt_app import filterlang
        text = self._query_entry.get()
        cursor = min(self._query_entry.index('insert'), len(text))
        found = filterlang.suggestions(text, cursor, self._project)
        # A word half-typed narrows the list rather than hiding it.
        start = cursor
        while start > 0 and (text[start - 1].isalnum()
                             or text[start - 1] in '._-'):
            start -= 1
        prefix = text[start:cursor].lower()
        if prefix:
            found = [s for s in found if s.lower().startswith(prefix)]
        if not found or (self._suggest_popup is not None
                         and not self._suggest_popup.winfo_exists()):
            self._close_suggestions()
            if not found:
                return
        self._show_suggestions(found, start)

    def _show_suggestions(self, items, word_start):
        """Open or refill the popup under the entry."""
        if self._suggest_popup is None or \
                not self._suggest_popup.winfo_exists():
            popup = tk.Toplevel(self)
            popup.wm_overrideredirect(True)
            popup.transient(self.winfo_toplevel())
            listing = tk.Listbox(popup, height=min(8, len(items)),
                                 activestyle='dotbox', exportselection=0)
            listing.pack(fill="both", expand=True)
            listing.bind('<ButtonRelease-1>', lambda _e:
                         self._take_suggestion(word_start))
            popup._listing = listing
            self._suggest_popup = popup
        listing = self._suggest_popup._listing
        listing.delete(0, 'end')
        for item in items:
            listing.insert('end', item)
        if items:
            listing.selection_set(0)
        try:
            x = self._query_entry.winfo_rootx()
            y = (self._query_entry.winfo_rooty()
                 + self._query_entry.winfo_height() + 2)
            self._suggest_popup.geometry(f"320x+{x}+{y}")
        except tk.TclError:
            pass
        self._suggest_popup._word_start = word_start

    def _open_suggestions(self):
        """Down-arrow: pop the list and move focus into it."""
        if self._suggest_popup is None or \
                not self._suggest_popup.winfo_exists():
            self._offer_suggestions()
            return
        self._suggest_popup._listing.focus_set()

    def _take_suggestion(self, word_start=None):
        """Write the picked suggestion over the word being typed."""
        popup = self._suggest_popup
        if popup is None or not popup.winfo_exists():
            return
        listing = popup._listing
        picked = listing.get('active') or (
            listing.get(0) if listing.size() else None)
        if not picked:
            self._close_suggestions()
            return
        text = self._query_entry.get()
        cursor = self._query_entry.index('insert')
        start = word_start if word_start is not None else cursor
        while start > 0 and (text[start - 1].isalnum()
                             or text[start - 1] in '._-'):
            start -= 1
        self._query_entry.delete(start, cursor)
        addition = picked + (' ' if not picked.startswith('(') else '')
        self._query_entry.insert(start, addition)
        self._query_entry.icursor(start + len(addition))
        self._close_suggestions()
        self._query_entry.focus_set()
        self._query_changed()

    def _close_suggestions(self):
        if self._suggest_popup is not None:
            try:
                if self._suggest_popup.winfo_exists():
                    self._suggest_popup.destroy()
            except tk.TclError:
                pass
            self._suggest_popup = None

    def _tab_switched(self):
        """
        Carry the filter across the Basic/Advanced switch.

        Basic to Advanced renders the column rules as query text - the
        language teaches itself by showing the form's own answer. Advanced
        to Basic fills the form back only when the query is a flat AND of
        conditions the columns can express - anything with an or, a not or
        a bracket stays a query, as it does in Jira.
        """
        if self._active_tab() == 'advanced':
            text = specs_to_query(self.collect()['specs'], self._project)
            if text:
                self._query_entry.delete(0, 'end')
                self._query_entry.insert(0, text)
            self._query_changed()
        else:
            self._close_suggestions()
            specs = query_to_specs(self._query_entry.get(), self._project)
            if specs is not None:
                self._fill_sections(specs)

    def _fill_sections(self, specs: Dict):
        """Refill the Basic tab's controls from a spec dict."""
        for column, control in self._controls.items():
            kind = control[0]
            spec = (specs or {}).get(column)
            if kind == 'text':
                control[1].delete(0, 'end')
                if spec:
                    control[1].insert(0, spec.get('text', ''))
            elif kind == 'number':
                control[1].delete(0, 'end')
                control[2].delete(0, 'end')
                if spec:
                    if spec.get('min') is not None:
                        control[1].insert(0, str(spec['min']))
                    if spec.get('max') is not None:
                        control[2].insert(0, str(spec['max']))
            elif kind == 'date':
                control[1].delete(0, 'end')
                control[2].delete(0, 'end')
                if spec:
                    if spec.get('from') is not None:
                        control[1].set_date(spec['from'])
                    if spec.get('to') is not None:
                        control[2].set_date(spec['to'])
            elif kind == 'choice':
                allowed = set(spec['allowed']) if spec else None
                for value, var in control[1]:
                    var.set(allowed is None or value in allowed)

    def _build_section(self, column: str, spec):
        """One column's controls: a caption, then the kind's widgets."""
        kind = COLUMN_KIND.get(column)
        section = ctk.CTkFrame(self._body.content, fg_color="transparent")
        section.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(
            section, text=column, anchor="w",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(anchor="w")

        if kind == 'text':
            entry = ctk.CTkEntry(section, placeholder_text="contains...",
                                 width=280)
            entry.pack(anchor="w", pady=2)
            if spec:
                entry.insert(0, spec.get('text', ''))
            entry.bind('<Return>', lambda _e: self._apply())
            self._controls[column] = ('text', entry)

        elif kind == 'number':
            row = ctk.CTkFrame(section, fg_color="transparent")
            row.pack(anchor="w", pady=2)
            lower = ctk.CTkEntry(row, placeholder_text="from", width=110)
            lower.pack(side="left")
            ctk.CTkLabel(row, text=" to ").pack(side="left")
            upper = ctk.CTkEntry(row, placeholder_text="to", width=110)
            upper.pack(side="left")
            if spec:
                if spec.get('min') is not None:
                    lower.insert(0, str(spec['min']))
                if spec.get('max') is not None:
                    upper.insert(0, str(spec['max']))
            for entry in (lower, upper):
                entry.bind('<Return>', lambda _e: self._apply())
            self._controls[column] = ('number', lower, upper)

        elif kind == 'date':
            row = ctk.CTkFrame(section, fg_color="transparent")
            row.pack(anchor="w", pady=2)
            lower = DateEntry(row)
            lower.pack(side="left")
            ctk.CTkLabel(row, text=" to ").pack(side="left")
            upper = DateEntry(row)
            upper.pack(side="left")
            if spec:
                if spec.get('from') is not None:
                    lower.set_date(spec['from'])
                if spec.get('to') is not None:
                    upper.set_date(spec['to'])
            self._controls[column] = ('date', lower, upper)

        elif kind == 'choice':
            present = self._values(column)
            allowed = (set(spec['allowed']) if spec
                       and spec.get('allowed') is not None else set(present))
            ticks = []
            for value in present:
                var = ctk.BooleanVar(value=value in allowed)
                ctk.CTkCheckBox(
                    section, text=str(value), variable=var,
                    checkbox_width=18, checkbox_height=18,
                    font=ctk.CTkFont(size=12),
                ).pack(anchor="w", padx=8)
                ticks.append((value, var))
            self._controls[column] = ('choice', ticks)

    @staticmethod
    def _number(entry) -> Optional[float]:
        """What a number box holds; an unparseable one asks nothing."""
        try:
            return float(entry.get().strip())
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def _day(entry) -> Optional[datetime]:
        """What a date box holds; an unparseable one asks nothing."""
        try:
            return entry.get_date()
        except Exception:
            return None

    def collect(self) -> Dict:
        """
        What the window currently asks, as one payload.

        'specs' holds the Basic tab's per-column rules; 'query' holds the
        Advanced tab's text; 'mode' says which tab is live. Read back
        rather than remembered: what is in the boxes is the truth, and an
        Apply after edits asks for exactly what is on screen.
        """
        specs = {}
        for column, control in self._controls.items():
            kind = control[0]
            if kind == 'text':
                specs[column] = {'text': control[1].get()}
            elif kind == 'number':
                specs[column] = {'min': self._number(control[1]),
                                 'max': self._number(control[2])}
            elif kind == 'date':
                specs[column] = {'from': self._day(control[1]),
                                 'to': self._day(control[2])}
            elif kind == 'choice':
                specs[column] = {'allowed': {v for v, var in control[1]
                                             if var.get()}}
        return {'mode': self._active_tab(), 'specs': specs,
                'query': self._query_entry.get()}

    def _apply(self):
        """Hand the live tab's contents to whoever opened the dialog."""
        if self._on_apply is not None:
            self._on_apply(self.collect())

    def _save_as(self):
        """Hand the live tab to whoever names and keeps filters."""
        if self._on_save_as is not None:
            self._on_save_as(self.collect())

    def _clear_all(self):
        """Empty every control, then apply - which puts every row back."""
        self._fill_sections({})
        self._query_entry.delete(0, 'end')
        self._query_changed()
        if self._on_clear is not None:
            self._on_clear()

    def destroy(self):
        """Let go cleanly - the filters themselves live in the task list."""
        self._close_suggestions()
        try:
            super().destroy()
        except tk.TclError:
            pass


class FilterDefinitionDialog(ctk.CTkToplevel):
    """
    The builder behind New... and Edit... in the filter manager.

    PARAMETERS:
    -----------
    master : widget
        The application window.
    values_for : callable
        field name -> the values a fixed-set field carries, for the
        dropdown a choice rule gets.
    definition : Dict, optional
        The filter being edited; None builds an empty one.
    on_save : callable
        Given the collected definition when Save succeeds.

    DEVELOPMENT NOTES:
    ------------------
    The row grid is MS Project's Filter Definition: And/Or, Field Name,
    Test, Value(s). Each row's test list and value widget follow the field
    it names - a date field gets calendar boxes, a fixed-set field a box
    that offers the plan's own values, and a two-value test ('is within')
    shows a second box rather than asking for two values in one. A row can
    be dropped with its own button; Add Row appends, which is what Insert
    Row is for in practice.
    """

    def __init__(self, master, values_for, definition=None, on_save=None):
        super().__init__(master)
        self.title("Filter Definition")
        self.transient(master)
        self._values_for = values_for
        self._on_save = on_save
        #: The live rows, in order: dicts of the widgets each row reads.
        self._rows = []

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=12, pady=(12, 4))
        ctk.CTkLabel(head, text="Name:", anchor="w").pack(side="left")
        self._name = ctk.CTkEntry(head, width=280)
        self._name.pack(side="left", padx=(6, 12))
        self._show_in_menu = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(head, text="Show in menu",
                        variable=self._show_in_menu,
                        checkbox_width=18, checkbox_height=18,
                        font=ctk.CTkFont(size=12)).pack(side="left")

        self._body = ScrollFrame(self, height=300)
        self._body.pack(fill="both", expand=True, padx=12, pady=4)

        # The column headers sit above the rows, as the dialog's grid does.
        grid_head = ctk.CTkFrame(self._body.content, fg_color="transparent")
        grid_head.pack(fill="x")
        for text, width in (("", 64), ("Field Name", 170),
                            ("Test", 190), ("Value(s)", 300), ("", 30)):
            ctk.CTkLabel(grid_head, text=text, anchor="w", width=width,
                         font=ctk.CTkFont(size=11, weight="bold"),
                         text_color=theme.MUTED_TEXT,
                         ).pack(side="left", padx=2)

        self._rows_frame = ctk.CTkFrame(self._body.content,
                                        fg_color="transparent")
        self._rows_frame.pack(fill="x")

        secondary_button(self._body.content, "Add Row", self._add_row,
                         width=80).pack(anchor="w", pady=(6, 0))

        self._warning = ctk.CTkLabel(self, text="", anchor="w",
                                   text_color=('#b00020', '#ff6b6b'),
                                   font=ctk.CTkFont(size=12))
        self._warning.pack(fill="x", padx=12)

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", padx=12, pady=(4, 12))
        ctk.CTkButton(buttons, text="Save", width=90,
                      command=self._save).pack(side="right", padx=(6, 0))
        secondary_button(buttons, "Cancel", self.destroy,
                         width=70).pack(side="right")

        for rule in ((definition or {}).get('rules') or []):
            self._add_row(rule)
        if not self._rows:
            self._add_row()
        if definition:
            self._name.insert(0, definition.get('name', ''))
            self._show_in_menu.set(bool(definition.get('show_in_menu', True)))

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        grab_when_visible(self)

    # ------------------------------------------------------------------
    # Rows
    # ------------------------------------------------------------------

    def _add_row(self, rule: Dict = None):
        """One more row of the grid, filled from a rule when editing."""
        rule = rule or {}
        frame = ctk.CTkFrame(self._rows_frame, fg_color="transparent")
        frame.pack(fill="x", pady=1)

        join_var = ctk.StringVar(
            value="And" if rule.get('join', 'and') == 'and' else "Or")
        # Every row shows the And/Or box, the first included - its value is
        # ignored at match time, the way MS Project ignores it, and leaving
        # it there keeps the grid's columns lined up.
        ctk.CTkOptionMenu(frame, variable=join_var,
                          values=["And", "Or"], width=64).pack(
            side="left", padx=2)

        field_var = ctk.StringVar(value=rule.get('field') or FILTER_FIELDS[0])
        ctk.CTkOptionMenu(frame, variable=field_var, values=FILTER_FIELDS,
                          width=170).pack(side="left", padx=2)

        row = {'frame': frame, 'join_var': join_var, 'field_var': field_var,
               'test_var': ctk.StringVar(), 'rule': rule}
        self._rows.append(row)
        field_var.trace_add('write', lambda *_a, r=row: self._rebuild(r))
        self._rebuild(row)

    def _rebuild(self, row: Dict):
        """Redraw a row's test list and value boxes for its field."""
        for key in ('test_menu', 'value', 'value2', 'and_label', 'delete'):
            widget = row.pop(key, None)
            if widget is not None:
                widget.destroy()

        kind = COLUMN_KIND.get(row['field_var'].get()) or 'text'
        rule = row.get('rule') or {}
        labels = [TEST_LABELS[t] for t in TESTS_BY_KIND[kind]]
        by_label = {TEST_LABELS[t]: t for t in TESTS_BY_KIND[kind]}
        saved = rule.get('test')
        start = (TEST_LABELS.get(saved)
                 if saved in TESTS_BY_KIND[kind] else labels[0])
        row['test_var'].set(start)
        menu = ctk.CTkOptionMenu(row['frame'], variable=row['test_var'],
                                 values=labels, width=190,
                                 command=lambda _v, r=row:
                                 self._rebuild_value(r))
        menu.pack(side="left", padx=2)
        row['test_menu'] = menu
        row['by_label'] = by_label

        delete = secondary_button(row['frame'], "✕",
                                  lambda r=row: self._drop_row(r), width=30)
        delete.pack(side="right", padx=2)
        row['delete'] = delete
        self._rebuild_value(row)

    def _rebuild_value(self, row: Dict):
        """Redraw a row's value box(es) for its field and test."""
        for key in ('value', 'value2', 'and_label'):
            widget = row.pop(key, None)
            if widget is not None:
                widget.destroy()

        kind = COLUMN_KIND.get(row['field_var'].get()) or 'text'
        test = row['by_label'].get(row['test_var'].get(), 'equals')
        rule = row.get('rule') or {}
        saved = str(rule.get('value', '')) if rule.get('value') is not None else ''
        if isinstance(rule.get('value'), list):
            saved = ", ".join(str(v) for v in rule['value'])
        saved2 = str(rule.get('value2', '')) if rule.get('value2') is not None else ''

        holder = row['frame']
        if kind == 'date':
            value = DateEntry(holder)
            if saved:
                value.insert(0, saved)
        elif kind == 'choice':
            value = ctk.CTkComboBox(
                holder, values=[str(v) for v in
                                self._values_for(row['field_var'].get())],
                width=300)
            if saved:
                value.set(saved)
        else:
            value = ctk.CTkEntry(holder, width=300)
            if saved:
                value.insert(0, saved)
        value.pack(side="left", padx=2)
        row['value'] = value

        if test in TWO_VALUE_TESTS:
            and_label = ctk.CTkLabel(holder, text="and", width=24)
            and_label.pack(side="left", padx=2)
            if kind == 'date':
                value2 = DateEntry(holder)
                if saved2:
                    value2.insert(0, saved2)
            else:
                value2 = ctk.CTkEntry(holder, width=120)
                if saved2:
                    value2.insert(0, saved2)
            value2.pack(side="left", padx=2)
            row['and_label'] = and_label
            row['value2'] = value2
        # The row's own copy of the rule is spent once the boxes hold it.
        row['rule'] = None

    def _drop_row(self, row: Dict):
        """Take a row out of the grid; the last row empties instead."""
        if len(self._rows) == 1:
            row['rule'] = None
            self._rebuild(row)
            return
        self._rows.remove(row)
        row['frame'].destroy()

    # ------------------------------------------------------------------
    # Collecting and saving
    # ------------------------------------------------------------------

    def _collect(self) -> Dict:
        """The definition the rows currently describe."""
        rules = []
        for index, row in enumerate(self._rows):
            test = row['by_label'].get(row['test_var'].get(), 'equals')
            field = row['field_var'].get()
            value = row['value'].get()
            rule = {'join': ('and' if index == 0 else
                             row['join_var'].get().lower()),
                    'field': field, 'test': test}
            if (COLUMN_KIND.get(field) == 'choice'
                    and test in ('is_one_of', 'not_one_of')):
                rule['value'] = [v.strip() for v in value.split(',')
                                 if v.strip()]
            else:
                rule['value'] = value
            if test in TWO_VALUE_TESTS and row.get('value2') is not None:
                rule['value2'] = row['value2'].get()
            rules.append(rule)
        return {'name': self._name.get().strip(),
                'show_in_menu': bool(self._show_in_menu.get()),
                'rules': rules}

    def _save(self):
        """Check the definition is usable, then hand it back."""
        definition = self._collect()
        if not definition['name']:
            self._warning.configure(text="Give the filter a name.")
            return
        rules = [r for r in definition['rules']
                 if r.get('value') not in (None, '', [])
                 or r.get('value2') not in (None, '')]
        if not rules:
            self._warning.configure(
                text="A filter needs at least one rule with a value.")
            return
        definition['rules'] = rules
        if self._on_save is not None:
            self._on_save(definition)
        self.destroy()

    def destroy(self):
        try:
            super().destroy()
        except tk.TclError:
            pass


class MoreFiltersDialog(ctk.CTkToplevel):
    """
    The filter list, as MS Project's More Filters dialog draws it.

    PARAMETERS:
    -----------
    master : widget
        The application window.
    entries : list
        (key, label, kind) triples - 'standard' or 'custom' - in the order
        they are listed. Custom entries can be edited, copied and deleted;
        standard ones cannot, the way the built-in set is fixed.
    callbacks : Dict
        'apply', 'highlight', 'new', 'edit', 'copy', 'delete' - each
        called with the selected entry's key where that makes sense; the
        dialog itself only lists and asks.

    DEVELOPMENT NOTES:
    ------------------
    Apply and Highlight are the two uses one definition has: hide the rows
    it fails, or paint the rows it passes. The dialog stays open after
    either so a filter can be tried and swapped without reopening.
    """

    def __init__(self, master, entries, callbacks):
        super().__init__(master)
        self.title("More Filters")
        self.resizable(False, False)
        self.transient(master)
        self._callbacks = callbacks or {}
        self._selected = None
        self._rows = {}

        ctk.CTkLabel(self, text="Filters", anchor="w",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     ).pack(anchor="w", padx=12, pady=(12, 2))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=4)

        listing = ScrollFrame(body, height=240, width=320)
        listing.pack(side="left", fill="both", expand=True)
        for key, label, kind in entries:
            row = ctk.CTkButton(
                listing.content, text=label, anchor="w",
                fg_color="transparent", text_color=MENU_TEXT,
                hover_color=MENU_HOVER,
                command=lambda k=key: self._select(k))
            row.pack(fill="x", pady=1)
            self._rows[key] = (row, kind)

        side = ctk.CTkFrame(body, fg_color="transparent")
        side.pack(side="left", padx=(10, 0))
        for text, action in (("Apply", 'apply'), ("Highlight", 'highlight'),
                             ("New...", 'new'), ("Edit...", 'edit'),
                             ("Copy", 'copy'), ("Delete", 'delete')):
            secondary_button(side, text,
                             lambda a=action: self._run(a),
                             width=90).pack(pady=2)
        secondary_button(self, "Close", self.destroy,
                         width=90).pack(pady=(4, 12))

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        grab_when_visible(self)

    def _select(self, key):
        """Mark a row as the one the side buttons act on."""
        self._selected = key
        for k, (row, _kind) in self._rows.items():
            row.configure(fg_color=('#cfe2f3', '#1f4e79') if k == key
                          else "transparent")

    def _run(self, action: str):
        """The button presses, handed to whoever opened the dialog."""
        callback = self._callbacks.get(action)
        if callback is None:
            return
        if action in ('new',):
            callback()
            return
        if self._selected is None:
            return
        kind = self._rows.get(self._selected, (None, None))[1]
        if kind != 'custom' and action in ('edit', 'copy', 'delete'):
            # The built-in set is fixed; a copy starts from New.
            return
        callback(self._selected)
        if action in ('delete',):
            self._selected = None

    def destroy(self):
        try:
            super().destroy()
        except tk.TclError:
            pass
