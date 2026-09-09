"""
The Task Editor's Advanced tab: Deadline and scheduling Constraint.

WHY THIS MODULE EXISTS:
======================
REQ-UI-040/041. The General tab holds what a task is and when it runs; the
Advanced tab holds the two boundaries a planner sets around that: a
*deadline* the finish should not slip past, and a *constraint* that pins the
start or the finish to a date. Both are informational to the scheduler here -
they are drawn on the Gantt chart and flag a slipped finish - rather than
rewiring the critical-path solver, which the specification treats as a
separate engine concern.

It is a self-contained CTkFrame so the editor can drop it into a tab the same
way it drops in the Resource tab, and so its field logic - which control is
live, what a date defaults to, how an unparseable date is rejected - lives in
one place rather than spread through the four-hundred-line editor base.

DEVELOPMENT NOTES:
------------------
The look is the editor's: bold section titles, a label on the left and its
control on the right, the same field colours (theme.FIELD_*). The layout is a
plain two-column grid rather than the editor's six-column pairing grid,
because the Advanced tab has one control per row and no pairs to line up.
"""

import tkinter as tk
from datetime import datetime
from tkinter import ttk
from typing import Optional

import customtkinter as ctk

from gantt_app import theme
from gantt_app.models import (
    CONSTRAINT_LABELS, CONSTRAINT_TYPES, CONSTRAINTS_WITH_DATE, HARD_CONSTRAINTS,
    EFFORT_FIXED_UNITS, EFFORT_FIXED_WORK, EFFORT_TYPES,
)
from gantt_app.utils.log import get_logger
from gantt_app.views.datepicker import DateEntry
from gantt_app.views.modal import grab_when_visible
from gantt_app.views.tooltip import attach as attach_tooltip

logger = get_logger(__name__)

DATE_FORMAT = '%Y-%m-%d'

#: Enum -> its title, and back. The dropdown shows the titles; the model
#: stores the enum. Order follows the specification's list.
_LABEL_TO_ENUM = {CONSTRAINT_LABELS[enum]: enum for enum in CONSTRAINT_TYPES}

#: What the dropdown reads when a bulk edit spans tasks whose constraints
#: differ - see REQ-UI-041 §4. Chosen so it never collides with a real title.
MIXED_LABEL = "— Various —"

#: The Task Type dropdown's help, and the Effort-Driven checkbox's, from
#: Task_Type_FRS §7.2 - kept short enough to sit in a tooltip.
TASK_TYPE_TOOLTIP = (
    "How duration, work and resources adjust when one is changed:\n"
    "• Fixed Units (default): each resource's allocation is held; duration "
    "and work adjust.\n"
    "• Fixed Work: total work is held; duration or resources adjust.\n"
    "• Fixed Duration: duration is held; work or resources adjust."
)
EFFORT_DRIVEN_TOOLTIP = (
    "What happens when a resource is added or removed:\n"
    "• On: total work is kept - adding resources shortens the task, "
    "removing them extends it.\n"
    "• Off: total work changes with the resources; the duration is not "
    "moved by the change.\n"
    "Direct edits to duration, work or units follow the Task Type instead."
)


class AdvancedTab(ctk.CTkFrame):
    """
    Deadline and Constraint controls for one task (or a bulk selection).

    PARAMETERS:
    -----------
    master : widget
        The tab frame the editor hands over.
    task : Task
        The task being edited; read for its opening values, never written -
        the editor writes the task on Save, from :meth:`apply_to`.
    is_summary : bool
        Whether the task rolls up children. A summary's length and work come
        from what is under it, so its Task Type and Effort-Driven are shown
        but disabled (Task_Type_FRS §5.8). The tab is handed this because it
        holds the task alone and cannot see the hierarchy.
    """

    #: Field colours, taken from the editor so the two tabs match exactly.
    FIELD_BG = theme.FIELD_BG
    FIELD_BG_DISABLED = theme.FIELD_BG_DISABLED
    FIELD_TEXT = theme.FIELD_TEXT
    FIELD_TEXT_DISABLED = theme.FIELD_TEXT_DISABLED
    ERROR_COLOR = theme.NEGATIVE_TEXT

    def __init__(self, master, task, is_summary: bool = False, **kwargs):
        super().__init__(master, fg_color='transparent', **kwargs)
        self.task = task
        self._is_summary = is_summary
        self._row = 0
        self._last_valid = {}
        self.grid_columnconfigure(1, weight=1)

        # Order follows Task_Type_FRS §7.1: Constraint, then Task Type and
        # Effort-Driven, then Deadline. (Is Milestone lives on the General
        # tab.) The same order is the keyboard tab order, §12.1.
        self._build_constraint()
        self._build_task_type()
        self._build_deadline()
        self._apply_constraint_state()
        self._apply_effort_state()

    # ------------------------------------------------------------------
    # Layout helpers, matching the editor's look
    # ------------------------------------------------------------------
    def _heading(self, text: str, rule: bool = False):
        """A bold section title, optionally under a rule."""
        if rule:
            ttk.Separator(self, orient=tk.HORIZONTAL).grid(
                row=self._row, column=0, columnspan=3, sticky=tk.EW,
                pady=(16, 0), padx=4)
            self._row += 1
        ctk.CTkLabel(self, text=text, anchor=tk.W,
                     font=ctk.CTkFont(size=15, weight='bold')).grid(
            row=self._row, column=0, columnspan=3, sticky=tk.W,
            padx=8, pady=(12 if rule else 6, 2))
        self._row += 1

    def _row_frame(self, label: str) -> ctk.CTkFrame:
        """A row with a caption on the left; returns a frame for the control."""
        caption = ctk.CTkLabel(self, text=label, anchor=tk.W)
        caption.grid(row=self._row, column=0, sticky=tk.W, padx=(8, 10),
                     pady=6)
        holder = ctk.CTkFrame(self, fg_color='transparent')
        holder.grid(row=self._row, column=1, columnspan=2, sticky=tk.EW,
                    pady=6, padx=(0, 8))
        self._captions_for_row = caption
        self._row += 1
        return holder

    def _hint(self, text: str):
        """A muted line of explanation under a control."""
        ctk.CTkLabel(self, text=text, anchor=tk.W, justify=tk.LEFT,
                     text_color=theme.MUTED_TEXT,
                     font=ctk.CTkFont(size=11)).grid(
            row=self._row, column=1, columnspan=2, sticky=tk.W, padx=(0, 8),
            pady=(0, 4))
        self._row += 1

    # ------------------------------------------------------------------
    # Deadline
    # ------------------------------------------------------------------
    def _build_deadline(self):
        """The deadline date box, with a button to clear it back to N/A."""
        self._heading("Deadline", rule=True)

        holder = self._row_frame("Deadline:")
        holder.grid_columnconfigure(0, weight=1)
        self.deadline_entry = DateEntry(holder, date=self.task.deadline)
        self.deadline_entry.grid(row=0, column=0, sticky=tk.EW)
        self._paint(self.deadline_entry)
        self._watch_blur(self.deadline_entry, 'deadline')

        self.deadline_reset = ctk.CTkButton(
            holder, text="Reset to N/A", width=110,
            command=self._reset_deadline)
        self.deadline_reset.grid(row=0, column=1, padx=(8, 0))

        self._hint("A target finish. It does not move the schedule; a finish "
                   "later than it is flagged on the chart.")

    def _reset_deadline(self):
        """Clear the deadline back to N/A (a null date)."""
        self._clear(self.deadline_entry)
        self._last_valid['deadline'] = ''
        self._clear_error(self.deadline_entry)

    # ------------------------------------------------------------------
    # Constraint
    # ------------------------------------------------------------------
    def _build_constraint(self):
        """The constraint type dropdown and the date it may need."""
        self._heading("Constraint")

        holder = self._row_frame("Constraint type:")
        current = self.task.constraint_type
        if current not in CONSTRAINT_TYPES:
            current = 'NA'
        self.constraint_var = ctk.StringVar(value=CONSTRAINT_LABELS[current])
        self.constraint_menu = ctk.CTkOptionMenu(
            holder, variable=self.constraint_var,
            values=[CONSTRAINT_LABELS[enum] for enum in CONSTRAINT_TYPES],
            width=240, command=lambda _v: self._on_constraint_changed())
        self.constraint_menu.pack(side=tk.LEFT)

        holder2 = self._row_frame("Constraint date:")
        holder2.grid_columnconfigure(0, weight=1)
        self.constraint_date_entry = DateEntry(
            holder2, date=self.task.constraint_date)
        self.constraint_date_entry.grid(row=0, column=0, sticky=tk.EW)
        self._paint(self.constraint_date_entry)
        self._watch_blur(self.constraint_date_entry, 'constraint_date')

        self._hint("Enabled for Start/Finish No Earlier/Later Than and Must "
                   "Start/Finish On; the others are dependency-driven.")

    def _on_constraint_changed(self):
        """Re-evaluate the date box, seeding a default when it turns on."""
        enum = self.constraint_enum()
        needs_date = enum in CONSTRAINTS_WITH_DATE
        if needs_date and self.constraint_date_entry.get_date() is None:
            self._seed_constraint_date(enum)
        if not needs_date:
            self._clear(self.constraint_date_entry)
            self._clear_error(self.constraint_date_entry)
        self._apply_constraint_state()

    def _seed_constraint_date(self, enum: str):
        """
        Fill an empty constraint date when a dated constraint is chosen.

        Start constraints open on the task's start, finish constraints on its
        finish - the boundary each one governs - so the reader adjusts a
        sensible date rather than an empty box.
        """
        starts = enum in ('SNET', 'SNLT', 'MSO')
        seed = self.task.start_date if starts else (
            self.task.end_date or self.task.start_date)
        if seed is not None:
            self.constraint_date_entry.set_date(seed)

    def _apply_constraint_state(self):
        """Enable the date box only for a constraint that carries a date."""
        enabled = self.constraint_enum() in CONSTRAINTS_WITH_DATE
        try:
            self.constraint_date_entry.configure(
                state=tk.NORMAL if enabled else tk.DISABLED)
        except (tk.TclError, ValueError):
            logger.debug("Could not set the constraint-date state")
        self._paint(self.constraint_date_entry, enabled)

    # ------------------------------------------------------------------
    # Task Type (Effort Behavior) and Effort-Driven
    # ------------------------------------------------------------------
    def _build_task_type(self):
        """The Task Type dropdown and the Effort-Driven checkbox."""
        self._heading("Task Type", rule=True)

        holder = self._row_frame("Task Type (Effort Behavior):")
        current = self.task.effort_type
        if current not in EFFORT_TYPES:
            current = EFFORT_FIXED_UNITS
        self.effort_type_var = ctk.StringVar(value=current)
        self.effort_type_menu = ctk.CTkOptionMenu(
            holder, variable=self.effort_type_var, values=list(EFFORT_TYPES),
            width=240, command=lambda _v: self._on_effort_type_changed())
        self.effort_type_menu.pack(side=tk.LEFT)
        attach_tooltip(self.effort_type_menu, TASK_TYPE_TOOLTIP)

        holder2 = self._row_frame("Effort-Driven:")
        self.effort_driven_var = ctk.BooleanVar(
            value=bool(self.task.effort_driven))
        self.effort_driven_check = ctk.CTkCheckBox(
            holder2, text="", width=24, variable=self.effort_driven_var)
        self.effort_driven_check.pack(side=tk.LEFT)
        attach_tooltip(self.effort_driven_check, EFFORT_DRIVEN_TOOLTIP)

        self._hint("Which of duration, work and units is held fixed when the "
                   "others change; Effort-Driven keeps total work as "
                   "resources are added or removed.")
        reason = self._effort_off_reason()
        if reason:
            self._hint(reason)

    def _effort_logic_off(self) -> bool:
        """
        Whether Task Type and Effort-Driven do not apply to this task.

        A milestone has no duration or work, a manually scheduled task has
        dates the planner owns, and a summary rolls up its children - none of
        them has effort logic of its own (Task_Type_FRS §4.4, §5.6, §5.8).
        """
        return bool(self.task.effective_milestone
                    or getattr(self.task, 'manually_scheduled', False)
                    or self._is_summary)

    def _effort_off_reason(self) -> str:
        """The muted line saying why the effort fields are disabled, or ''."""
        if self.task.effective_milestone:
            return "Disabled for milestones - they carry no duration or work."
        if getattr(self.task, 'manually_scheduled', False):
            return "Ignored for manually scheduled tasks; the dates are yours."
        if self._is_summary:
            return "Disabled for summary tasks; edit the subtasks instead."
        return ""

    def _on_effort_type_changed(self):
        """Re-evaluate the Effort-Driven checkbox for the chosen type."""
        self._apply_effort_state()

    def _apply_effort_state(self):
        """
        Set the two controls' live/locked state.

        Fixed Work is effort-driven by definition, so its checkbox is forced
        on and locked (Task_Type_FRS §4.2). A milestone, summary or manually
        scheduled task disables both. Otherwise both are the planner's.
        """
        off = self._effort_logic_off()
        try:
            self.effort_type_menu.configure(
                state=tk.DISABLED if off else tk.NORMAL)
        except (tk.TclError, ValueError):
            logger.debug("Could not set the task-type state")

        if off:
            check_state = tk.DISABLED
        elif self.effort_type_var.get() == EFFORT_FIXED_WORK:
            # Locked ON: effort-driven by definition.
            self.effort_driven_var.set(True)
            check_state = tk.DISABLED
        else:
            check_state = tk.NORMAL
        try:
            self.effort_driven_check.configure(state=check_state)
        except (tk.TclError, ValueError):
            logger.debug("Could not set the effort-driven state")

    def effort_type_value(self) -> str:
        """The stored effort type the dropdown shows, defaulted if odd."""
        value = self.effort_type_var.get()
        return value if value in EFFORT_TYPES else EFFORT_FIXED_UNITS

    # ------------------------------------------------------------------
    # Validation on blur - reject an unparseable date, restore, and warn
    # ------------------------------------------------------------------
    def _watch_blur(self, entry: DateEntry, key: str):
        """Remember the last good text and check the box when it loses focus."""
        self._last_valid[key] = entry.get().strip()
        entry.entry.bind('<FocusOut>',
                         lambda _e: self._validate_on_blur(entry, key),
                         add='+')

    def _validate_on_blur(self, entry: DateEntry, key: str):
        """
        Reject a date the calendar has no such day for, restoring the last.

        An empty box is allowed (it means N/A). Anything else must parse as
        YYYY-MM-DD and be a real date; 2026-02-30 is refused on blur with a
        red outline and a tooltip, and the previous good value is put back.
        """
        text = entry.get().strip()
        if not text:
            self._last_valid[key] = ''
            self._clear_error(entry)
            return
        try:
            datetime.strptime(text, DATE_FORMAT)
        except ValueError:
            self._mark_error(entry, "Invalid calendar date")
            previous = self._last_valid.get(key, '')
            self._clear(entry)
            if previous:
                entry.entry.insert(0, previous)
            return
        self._last_valid[key] = text
        self._clear_error(entry)

    def _mark_error(self, entry: DateEntry, message: str):
        """Outline a box red and hang an error tooltip on it."""
        try:
            entry.entry.configure(border_color=self.ERROR_COLOR, border_width=2)
        except (tk.TclError, ValueError):
            pass
        # attach_tooltip reuses the one already on the widget - kept as
        # tooltip_widget, the name it looks for - so the box never gains a
        # second binding however many times it is re-marked.
        entry.entry.tooltip_widget = attach_tooltip(entry.entry, message)

    def _clear_error(self, entry: DateEntry):
        """Take the red outline and the error tooltip off a box."""
        try:
            entry.entry.configure(border_color=theme.now(theme.SEPARATOR),
                                  border_width=1)
        except (tk.TclError, ValueError):
            pass
        existing = getattr(entry.entry, 'tooltip_widget', None)
        if existing is not None:
            existing.set_text("")

    # ------------------------------------------------------------------
    # Painting, matching the editor's field colours
    # ------------------------------------------------------------------
    def _paint(self, entry: DateEntry, enabled: bool = True):
        """Colour a date box the way the editor colours its fields."""
        try:
            entry.entry.configure(
                fg_color=self.FIELD_BG if enabled else self.FIELD_BG_DISABLED,
                text_color=(self.FIELD_TEXT if enabled
                            else self.FIELD_TEXT_DISABLED))
        except (tk.TclError, ValueError):
            logger.debug("Could not paint the date box")

    @staticmethod
    def _clear(entry: DateEntry):
        """Empty a date box, through a disabled one if need be."""
        was_disabled = str(entry.entry.cget('state')) == tk.DISABLED
        if was_disabled:
            entry.entry.configure(state=tk.NORMAL)
        entry.entry.delete(0, tk.END)
        if was_disabled:
            entry.entry.configure(state=tk.DISABLED)

    # ------------------------------------------------------------------
    # Reading the tab back
    # ------------------------------------------------------------------
    def constraint_enum(self) -> str:
        """The stored enum for whatever the dropdown shows now."""
        label = self.constraint_var.get()
        if label == MIXED_LABEL:
            return 'NA'
        return _LABEL_TO_ENUM.get(label, 'NA')

    def _date(self, entry: DateEntry, field: str) -> Optional[datetime]:
        """
        Parse a date box, refusing text that is there but will not parse.

        RAISES:
        -------
        ValueError
            When the box holds something that is not a real YYYY-MM-DD date.
        """
        text = entry.get().strip()
        if not text:
            return None
        try:
            return datetime.strptime(text, DATE_FORMAT)
        except ValueError:
            raise ValueError(
                f"Write the {field} as YYYY-MM-DD, as in 2026-08-15."
            ) from None

    def read_values(self) -> dict:
        """
        The deadline, constraint type and constraint date the tab describes.

        RETURNS:
        --------
        dict
            ``{'deadline', 'constraint_type', 'constraint_date'}`` ready to
            write onto a task. A constraint with no date of its own always
            comes back with ``constraint_date`` None, whatever the (disabled)
            box happens to hold.

        RAISES:
        -------
        ValueError
            When a date box holds an unparseable date, so Save can stop and
            say which - the same way the General tab reports a bad date.
        """
        enum = self.constraint_enum()
        deadline = self._date(self.deadline_entry, "deadline")
        constraint_date = None
        if enum in CONSTRAINTS_WITH_DATE:
            constraint_date = self._date(self.constraint_date_entry,
                                         "constraint date")
            if constraint_date is None:
                raise ValueError(
                    f"{CONSTRAINT_LABELS[enum]} needs a constraint date.")
        # Fixed Work is effort-driven whatever the (locked) checkbox reads,
        # matching what the model enforces; other types take the checkbox.
        effort_type = self.effort_type_value()
        effort_driven = (True if effort_type == EFFORT_FIXED_WORK
                         else bool(self.effort_driven_var.get()))
        return {
            'deadline': deadline,
            'constraint_type': enum,
            'constraint_date': constraint_date,
            'effort_type': effort_type,
            'effort_driven': effort_driven,
        }

    def apply_to(self, task) -> None:
        """
        Write the tab's values onto a task, validating first.

        RAISES:
        -------
        ValueError
            When a date will not parse or a dated constraint has no date.
        """
        values = self.read_values()
        task.deadline = values['deadline']
        task.constraint_type = values['constraint_type']
        task.constraint_date = values['constraint_date']
        task.effort_type = values['effort_type']
        task.effort_driven = values['effort_driven']

    def set_values(self, task) -> None:
        """Reload the controls from a task, e.g. after a Save & New reset."""
        self.task = task
        self._clear(self.deadline_entry)
        if task.deadline is not None:
            self.deadline_entry.set_date(task.deadline)
        self._last_valid['deadline'] = self.deadline_entry.get().strip()

        enum = task.constraint_type if task.constraint_type in CONSTRAINT_TYPES \
            else 'NA'
        self.constraint_var.set(CONSTRAINT_LABELS[enum])
        self._clear(self.constraint_date_entry)
        if task.constraint_date is not None:
            self.constraint_date_entry.set_date(task.constraint_date)
        self._last_valid['constraint_date'] = \
            self.constraint_date_entry.get().strip()
        self._apply_constraint_state()

        effort_type = task.effort_type if task.effort_type in EFFORT_TYPES \
            else EFFORT_FIXED_UNITS
        self.effort_type_var.set(effort_type)
        self.effort_driven_var.set(bool(task.effort_driven))
        self._apply_effort_state()

    def mark_mixed(self) -> None:
        """
        Show the constraint dropdown as -- Various -- for a bulk selection.

        Used when several tasks with different constraints are edited at once
        (REQ-UI-041 §4); the reader picks one value to apply to them all.
        """
        values = [MIXED_LABEL] + [CONSTRAINT_LABELS[e] for e in CONSTRAINT_TYPES]
        self.constraint_menu.configure(values=values)
        self.constraint_var.set(MIXED_LABEL)
        self._apply_constraint_state()


    def revert_to_na(self) -> None:
        """
        Put the constraint back to N/A and clear its date.

        What Cancel Constraint does in the conflict dialog: the constraint is
        abandoned, the dropdown returns to N/A, and the date box empties and
        greys out.
        """
        self.constraint_var.set(CONSTRAINT_LABELS['NA'])
        self._clear(self.constraint_date_entry)
        self._clear_error(self.constraint_date_entry)
        self._apply_constraint_state()


def constraint_title(enum: str) -> str:
    """The display title for a constraint enum, for help and tooltips."""
    return CONSTRAINT_LABELS.get(enum, 'N/A')


class ConstraintConflictDialog(ctk.CTkToplevel):
    """
    The Save-time warning when a constraint clashes with the network.

    PARAMETERS:
    -----------
    master : widget
        The task editor.
    conflict : dict
        What Project.constraint_conflict returned - the constraint, its date,
        the reason, and the predecessor tasks it clashes with.

    The reader chooses Keep Constraint (force it, flag the negative float) or
    Cancel Constraint (drop it back to N/A). The choice is left in ``result``
    as ``"keep"`` or ``"cancel"``; ``"cancel"`` is also what closing the
    window means, so an unanswered dialog never forces a bad constraint.
    """

    def __init__(self, master, conflict: dict):
        super().__init__(master)
        self.result = "cancel"
        self.title("Scheduling Conflict")
        self.transient(master.winfo_toplevel())
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda _e: self._cancel())

        ctype = CONSTRAINT_LABELS.get(conflict['constraint_type'],
                                      conflict['constraint_type'])
        cd = conflict.get('constraint_date')
        when = cd.strftime(DATE_FORMAT) if cd else "N/A"

        ctk.CTkLabel(
            self, text="⚠  Scheduling Conflict",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=theme.NEGATIVE_TEXT,
        ).pack(padx=20, pady=(18, 6), anchor=tk.W)

        ctk.CTkLabel(
            self, justify=tk.LEFT, wraplength=420,
            text=(f'The selected constraint {ctype} set to {when} conflicts '
                  f'with the active scheduling logic.'),
        ).pack(padx=20, pady=(0, 8), anchor=tk.W)

        chain = ", ".join(f"#{num} ({name})"
                          for num, name in conflict.get('predecessors', []))
        if chain:
            detail = (f"Predecessor chain: violates the completion date of "
                      f"{chain}." if conflict.get('reason') == 'predecessor'
                      else f"The task cannot meet this date given {chain}.")
            ctk.CTkLabel(self, justify=tk.LEFT, wraplength=420, text=detail,
                         text_color=theme.MUTED_TEXT).pack(
                padx=20, pady=(0, 4), anchor=tk.W)

        ctk.CTkLabel(
            self, justify=tk.LEFT, wraplength=420, text_color=theme.MUTED_TEXT,
            text=("Keep Constraint forces the date and flags the affected "
                  "tasks with a negative-float warning. Cancel Constraint "
                  "drops it back to N/A."),
        ).pack(padx=20, pady=(0, 12), anchor=tk.W)

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(padx=20, pady=(0, 16), anchor=tk.E)
        ctk.CTkButton(row, text="Cancel Constraint", width=150,
                      fg_color="transparent", border_width=1,
                      border_color=theme.SEPARATOR, text_color=theme.TEXT,
                      hover_color=theme.MENU_HOVER,
                      command=self._cancel).pack(side=tk.LEFT, padx=5)
        ctk.CTkButton(row, text="Keep Constraint", width=150,
                      fg_color=theme.NEGATIVE_TEXT, hover_color="#962d22",
                      command=self._keep).pack(side=tk.LEFT, padx=5)

        grab_when_visible(self)

    def _keep(self):
        self.result = "keep"
        self.destroy()

    def _cancel(self):
        self.result = "cancel"
        self.destroy()

    @classmethod
    def ask(cls, master, conflict: dict) -> str:
        """Show the dialog modally and return "keep" or "cancel"."""
        dialog = cls(master, conflict)
        dialog.wait_window()
        return dialog.result
