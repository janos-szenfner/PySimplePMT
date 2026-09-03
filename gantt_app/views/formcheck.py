"""
Checking the task form as it is filled in.

WHY THIS MODULE EXISTS:
======================
The task form asks for a name and two dates. The dates are worth little left
out or written in a way the application cannot read; the name may be left
blank, and only the dates are held to anything here. What
is wrong with a field, when to say so, and how to say it without getting in
the way of typing is a subject of its own, and it was two hundred lines
sitting in the middle of the dialog that builds the form.

Kept apart, the dialog reads as what it is - a form being built and saved -
and this reads as the rules the form is held to.

DEVELOPMENT NOTES:
------------------
A mixin rather than an object the dialog owns. Every check is a question
about a field the dialog holds - is the name box empty, is the milestone
ticked - so an object apart from the dialog would spend its life being handed
the dialog's own widgets back. What it needs from whatever it is mixed into
is set out under FormChecks.
"""

import tkinter as tk
from datetime import datetime

import customtkinter as ctk

from gantt_app.views.datepicker import DateEntry
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


class FormChecks:
    """
    Marks the fields of a task form that have something wrong with them.

    WHAT THIS DOES:
    ---------------
    Every change to either date box runs _check_fields, which asks each field
    what is wrong with it, outlines the ones that answer, and writes the first
    answer under the form.

    WHAT IT EXPECTS OF THE FORM:
    ----------------------------
    name_entry, start_date_entry and end_date_entry - the last may be None
    where a milestone has no end - is_milestone_var, DATE_FORMAT, _read_date,
    and the four dictionaries set up in _prepare_checks. _build_problem_line
    puts the line the answers are written on under the form.

    DEVELOPMENT NOTES:
    ------------------
    Two rules keep it out of the way of typing.

    Nothing is reconfigured while a field's verdict is unchanged. A
    CustomTkinter widget redraws its canvas on every configure() and the
    scrolling frame around the form flushes a full layout pass when it is
    touched, so reasserting a border on each keystroke cost more than working
    the answer out. A keystroke that leaves a good field good costs three
    string comparisons and touches no widget at all.

    An empty date box is only complained about once the user has been in it.
    A form that greets you in red for not yet having typed anything is just
    noise. What is already there and will not parse is pointed at straight
    away, because that is the user's own text and it is wrong now.

    The name is not checked at all: a task may have none. See issue #3.
    """

    #: Border and text colour of a field the form is complaining about.
    INVALID_BORDER_COLOR = '#e74c3c'
    PROBLEM_TEXT_COLOR = '#c0392b'

    #: A field is either missing, or holds something that will not do.
    #: Only the second is worth saying before the user has been in the box.
    MISSING = 'missing'
    MALFORMED = 'malformed'

    def _prepare_checks(self):
        """Start with nothing typed in, nothing marked and nothing watched."""
        #: Fields the user has been in, and so may be complained at about.
        self._touched = set()
        #: What each field is currently marked with, to spot a change.
        self._marked = {}
        #: What each box looks like unmarked, to put it back.
        self._plain_border = {}
        #: The variables the boxes are watched through; see _watch_fields.
        self._field_vars = {}

    def _build_problem_line(self, parent):
        """
        The line under the form that says what is wrong with it.

        DEVELOPMENT NOTES:
        ------------------
        Outside the scrolling area, so a complaint about a field cannot
        itself be scrolled out of sight, and it keeps its row whether or not
        it has anything to say - a message that appeared and disappeared
        would shift the form under the pointer every time a date was typed.
        """
        self.problem_label = ctk.CTkLabel(
            parent, text="", anchor=tk.W, height=18,
            text_color=self.PROBLEM_TEXT_COLOR,
        )
        self.problem_label.pack(fill=tk.X, padx=12, pady=(2, 6))

    def _checked_fields(self):
        """
        The fields watched as the form is filled in, as (key, widget).

        Built from what is actually on the form: a milestone has no end date,
        and the create dialog leaves the box out of the window entirely.
        """
        # The name is not among them: a task may have none, so there is
        # nothing to complain about when the box is empty. See issue #3.
        fields = [('start_date', self.start_date_entry)]
        if self.end_date_entry is not None:
            fields.append(('end_date', self.end_date_entry))
        return fields

    def _watch_fields(self):
        """
        Watch every checked field, and note what an unmarked one looks like.

        DEVELOPMENT NOTES:
        ------------------
        Watched through a variable rather than bound to <KeyRelease>, which
        only hears the keyboard. A date arriving from the calendar button, a
        start date moved by a dependency, or the name cleared by Save & New
        are all changes to the field the user can see, and a mark left over
        from the text they replace has to go the moment they replace it.

        It is also less work per keystroke than a binding: no event object is
        built, and Tk calls straight into _field_edited.
        """
        for key, widget in self._checked_fields():
            entry = self._entry_of(widget)
            self._plain_border[key] = (entry.cget('border_color'),
                                       entry.cget('border_width'))

            variable = ctk.StringVar(value=entry.get())
            entry.configure(textvariable=variable)
            variable.trace_add('write',
                               lambda *_args, k=key: self._field_edited(k))
            # Kept so the variable outlives this loop; a Tk variable that is
            # collected takes its trace with it
            self._field_vars[key] = variable

    @staticmethod
    def _entry_of(widget):
        """
        The box to outline for a field.

        A DateEntry is a frame holding an entry and a calendar button, and it
        is the entry that has a border to colour - outlining the frame draws
        a rectangle around the button as well, inside the space the entry is
        already occupying.
        """
        return widget.entry if isinstance(widget, DateEntry) else widget

    def _field_edited(self, key):
        """
        Note that a field has been filled in, and check the form.

        Guarded because a variable's trace can fire while the dialog is being
        torn down, when the boxes it would read are already gone.
        """
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return

        self._touched.add(key)
        self._check_fields()

    def _problem_with(self, key):
        """
        What is wrong with one field, as (kind, what to say).

        RETURNS:
        --------
        tuple
            (None, '') when there is nothing wrong with it.

        DEVELOPMENT NOTES:
        ------------------
        An end date is asked for but not insisted on. A task may legitimately
        have none - a task with sub-tasks takes its dates from them - so this
        points out the omission and _apply still saves without one.
        """
        widget = (self.start_date_entry if key == 'start_date'
                  else self.end_date_entry)
        label = "start date" if key == 'start_date' else "end date"
        text = widget.get().strip()

        if not text:
            if key == 'end_date' and self.is_milestone_var.get():
                return None, ''         # a milestone takes no time at all
            return self.MISSING, f"Enter a {label}."

        try:
            value = datetime.strptime(text, self.DATE_FORMAT)
        except ValueError:
            return (self.MALFORMED,
                    f"Write the {label} as YYYY-MM-DD, as in 2026-08-15.")

        if key == 'end_date' and not self.is_milestone_var.get():
            start = self._read_date(self.start_date_entry)
            if start is not None and value < start:
                return (self.MALFORMED,
                        "The end date falls before the start date.")
        return None, ''

    def _check_fields(self, _event=None):
        """
        Mark every field that has something wrong with it.

        RETURNS:
        --------
        bool
            True when nothing on the form is wrong, whether or not the user
            has been in the field yet.
        """
        good = True
        announced = ''

        for key, widget in self._checked_fields():
            kind, message = self._problem_with(key)
            if kind is not None:
                good = False
            if kind == self.MISSING and key not in self._touched:
                # Not typed in yet; leave it alone until it is
                kind, message = None, ''
            self._mark(key, widget, message)
            if message and not announced:
                announced = message

        self._announce(announced)
        return good

    def _mark(self, key, widget, message):
        """Outline a field, or put it back the way it was."""
        if self._marked.get(key, '') == message:
            return                      # unchanged; leave the widget alone
        self._marked[key] = message

        entry = self._entry_of(widget)
        color, width = self._plain_border[key]
        try:
            if message:
                entry.configure(border_color=self.INVALID_BORDER_COLOR,
                                border_width=max(width, 2))
            else:
                entry.configure(border_color=color, border_width=width)
        except (tk.TclError, ValueError):
            # The dialog is on its way out from under us
            logger.debug("Could not mark the %s field", key)

    def _announce(self, message):
        """Write the first problem under the form, or clear the line."""
        try:
            if self.problem_label.cget('text') != message:
                self.problem_label.configure(text=message)
        except (tk.TclError, AttributeError):
            pass

    def _first_problem(self) -> str:
        """
        What to say when a save is refused, complaining about everything.

        Pressing Save is the user saying they are finished, so from here on
        an empty box is fair to point at whether or not it was ever visited.
        """
        self._touched.update(key for key, _ in self._checked_fields())
        self._check_fields()
        for key, _widget in self._checked_fields():
            _kind, message = self._problem_with(key)
            if message:
                return message
        return ''
