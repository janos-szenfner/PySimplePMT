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

from gantt_app import theme
from gantt_app.calendarregistry import PROJECT_DEFAULT_LABEL
from gantt_app.dependencysyntax import format_links
from gantt_app.workdaycalendar import as_date
from gantt_app.views.datepicker import DateEntry, DATE_FORMAT
from gantt_app.views.modal import grab_when_visible
from gantt_app.views.scrollframe import ScrollFrame
from gantt_app.views.buttonstyle import secondary_button
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)

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

    DEVELOPMENT NOTES:
    ------------------
    One section per visible column, control by kind: a box for text, a
    From/To pair for numbers and dates, a checklist for the columns with a
    fixed set. Nothing applies until Apply - a half-typed date or a
    checklist mid-way through being unticked should not rebuild the grid
    under the window the reader is still working in.
    """

    def __init__(self, master, columns, current, values, on_apply, on_clear):
        super().__init__(master)
        self.title("Filter Tasks")
        self.transient(master)
        self._on_apply = on_apply
        self._on_clear = on_clear
        self._values = values
        #: The control each section feeds back into a spec, by column.
        self._controls = {}

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=12, pady=(12, 4))
        ctk.CTkLabel(
            head, text="Show only the rows where every set rule passes.",
            text_color=theme.MUTED_TEXT,
            font=ctk.CTkFont(size=12),
        ).pack(anchor="w")

        self._body = ScrollFrame(self, height=420)
        self._body.pack(fill="both", expand=True, padx=12, pady=4)

        for column in columns:
            self._build_section(column, (current or {}).get(column))

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", padx=12, pady=(4, 12))
        ctk.CTkButton(buttons, text="Apply", width=90,
                      command=self._apply).pack(side="right", padx=(6, 0))
        secondary_button(buttons, "Close", self.destroy,
                         width=70).pack(side="right")
        secondary_button(buttons, "Clear All", self._clear_all,
                         width=80).pack(side="left")

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        grab_when_visible(self)

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
        The specs the controls currently hold, by column.

        Read back rather than remembered: what is in the boxes is the
        truth, and an Apply after edits asks for exactly what is on screen.
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
        return specs

    def _apply(self):
        """Hand the boxes' contents to whoever opened the dialog."""
        if self._on_apply is not None:
            self._on_apply(self.collect())

    def _clear_all(self):
        """Empty every control, then apply - which puts every row back."""
        for column, control in self._controls.items():
            kind = control[0]
            if kind == 'text':
                control[1].delete(0, 'end')
            elif kind == 'number':
                control[1].delete(0, 'end')
                control[2].delete(0, 'end')
            elif kind == 'date':
                control[1].delete(0, 'end')
                control[2].delete(0, 'end')
            elif kind == 'choice':
                for _value, var in control[1]:
                    var.set(True)
        if self._on_clear is not None:
            self._on_clear()

    def destroy(self):
        """Let go cleanly - the filters themselves live in the task list."""
        try:
            super().destroy()
        except tk.TclError:
            pass
