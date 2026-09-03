"""
The form behind creating and editing a task.

WHY THIS MODULE EXISTS:
======================
Creating a task and editing one show the same form, and TaskFormDialog is it.
The two dialogs that use it are in taskdialogs.py; what they are opened over
is in task_list.py. All three used to be one two-thousand-line module, in
which the form, the two dialogs and the tree they are opened from had nothing
to do with one another beyond sharing a file.

DEVELOPMENT NOTES:
------------------
The checking of the fields as they are filled in is in formcheck.py, mixed in
here as FormChecks.
"""

import tkinter as tk
from tkinter import ttk
# See gantt_app/views/dialogs.py: native on macOS and Windows, drawn
# to match the application on X11
from gantt_app.views import dialogs as messagebox
from datetime import datetime
from typing import Optional, Callable

import customtkinter as ctk

from gantt_app import theme
from gantt_app.calendarregistry import describe_week
from gantt_app.models import (
    Task, Project, TASK_TYPES, TASK_STATUSES, CONTAINER_TYPES,
)
from gantt_app.priority import PRIORITY_LEVELS
from gantt_app.utils.undoredo import ProjectStateTracker
from gantt_app.views.modal import grab_when_visible
from gantt_app.views.colorpicker import ColorEntry
from gantt_app.views.datepicker import DateEntry
from gantt_app.views.formcheck import FormChecks
from gantt_app.views.scrollframe import ScrollFrame
from gantt_app.views.dependency_editor import DependencyEditor
from gantt_app.views.assigntask import TaskResourceTab
from gantt_app.shortcuts import bind_all as bind_shortcut
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


#: How long to keep asking for the focus, and how often; see
#: TaskFormDialog._focus_when_visible. The same shape as the grab's retry in
#: gantt_app.views.modal, and for the same reason - a window that has not been
#: mapped yet can be given neither.
FOCUS_ATTEMPTS = 25
FOCUS_RETRY_MS = 40


class TaskFormDialog(FormChecks, ctk.CTkToplevel):
    """
    The task form shared by creating and editing.

    WHY THIS CLASS EXISTS:
    ======================
    Creating a task and editing one show the same form: a name, a type, a
    parent, two dates, a milestone flag, progress, a colour and a Dependency
    tab. That form was written out twice, in two four-hundred-line classes
    whose toggle_milestone, update_progress_label and center_window were
    byte-identical and whose _create_form differed only in what it seeded the
    fields from.

    Every change had to be made twice as a result, and the one time it was
    not, the create dialog kept a reference to a variable the edit dialog had
    already dropped and crashed on every Add Task until it was noticed.

    PARAMETERS:
    -----------
    master : widget
        Window to open over.
    project : Project
        The plan being edited; used for parent lookups and the Dependency tab.
    title : str
        Window title.
    on_save : Optional[Callable]
        Called with the task once it has been written.
    project_tracker : Optional[ProjectStateTracker]
        Undo support, when there is any.

    DEVELOPMENT NOTES:
    ------------------
    Subclasses set their seed attributes and then call _create_form() and
    center_window() themselves, rather than the base calling them. A Tk widget
    is only half-built until its own __init__ has run, so a base class that
    built the form would be reading attributes the subclass had not set yet.

    Rows are placed by a running counter rather than by hand-counted indices.
    The create dialog worked its out with

        row_offset = 3 if parent or type == "Sub-Task" or not milestone else 2

    which had to be re-derived by anyone adding a field.
    """

    #: The size the window opens at. Its width is MINSIZE's: a GEOMETRY
    #: narrower than the minimum is silently widened to it by the window
    #: manager, which left center_window placing the window from a width it
    #: was never given and every dialog opening off centre.
    GEOMETRY = "980x660"
    MINSIZE = (860, 520)
    DATE_FORMAT = '%Y-%m-%d'


    #: Width of the buttons along the bottom.
    #:
    #: Given explicitly because CTkButton defaults to 140 and only the two
    #: with the longest labels had been set: Close came out wider than
    #: Save & Close, so the row's widths ran backwards against the length of
    #: what was written on them.
    #:
    #: Four at ACTION_WIDTH plus one at DELETE_WIDTH, with their padding and
    #: the frame's, come to 670 - inside MINSIZE, so nothing is clipped when
    #: the dialog is squeezed as far as it goes.
    ACTION_WIDTH = 120
    DELETE_WIDTH = 100

    #: How a field looks when it is the user's to fill in, and when the form
    #: is working it out for them.
    #:
    #: A disabled CustomTkinter box is only very slightly paler than a live
    #: one, so the end date - greyed out because the scheduling mode is
    #: deriving it - looked exactly like the start date you are meant to
    #: type in. A shaded background and a grey caption is how every other
    #: form says a field is not yours to fill.
    #: (light, dark) pairs, from gantt_app.theme. Written as single strings
    #: these were used in both appearances, so the form that read perfectly
    #: in light turned into near-black labels on a near-black panel in dark.
    FIELD_BG = theme.FIELD_BG
    FIELD_BG_DISABLED = theme.FIELD_BG_DISABLED
    FIELD_TEXT = theme.FIELD_TEXT
    FIELD_TEXT_DISABLED = theme.FIELD_TEXT_DISABLED

    #: The field grid is six columns: three pairs of label and field.
    #:
    #: Short fields that belong together share a row - a start beside a
    #: finish, a percentage beside a status beside a priority. One column of
    #: a dozen rows made the form taller than most screens and left two
    #: thirds of every row empty.
    #:
    #: Two of the three pairs are the common case, and they take the first
    #: two so the fields stay beside each other; the outer pair is there for
    #: the one row that holds three. See _cell.
    FIELD_COLUMNS = 6

    #: Where a field sits on its row.
    #:
    #: LEFT opens a row, THIRD may take the middle of it and RIGHT closes
    #: it; FULL runs across all six columns. A field that is not built - a
    #: milestone has no end date - leaves the rest of the row empty rather
    #: than pulling the next field up into a row it does not belong on.
    #:
    #: HALF takes a whole row and puts the widget in the left field column
    #: alone, anchored west at MENU_WIDTH rather than stretched. For a
    #: dropdown: a menu stretched across the form is a control several times
    #: wider than the longest thing it can say, and it grew with the window,
    #: so the mismatch got worse the more room there was. Unlike LEFT it
    #: does not open the row for a RIGHT to fill - nothing belongs beside
    #: these - so the half beside it stays empty.
    LEFT, RIGHT, FULL, HALF, THIRD = 'left', 'right', 'full', 'half', 'third'

    #: How wide a HALF dropdown is drawn, whatever the window does.
    #:
    #: Enough for the longest thing any of the three says - "Start date is
    #: calculated", "Project Default (Mon-Fri)" - and no more. One width for
    #: all three rather than each sized to its own longest option: they sit
    #: in three different sections and a ragged right edge down the form
    #: reads worse than a little slack after "Rounded".
    #:
    #: A named calendar can of course be called something longer than this.
    #: The menu keeps its width and the label is what gives, which is the
    #: trade this makes deliberately.
    MENU_WIDTH = 260

    #: Colour a new row starts on, by what is being created.
    DEFAULT_COLORS = {
        'Phase': "#34495e",        # Dark Blue
        'Task': "#3498db",        # Blue
        'Subtask': "#9b59b6",      # Purple
        'Milestone': "#e74c3c",    # Red
    }

    def __init__(self, master, project: Project, title: str,
                 on_save: Callable[[Task], None] = None,
                 project_tracker: ProjectStateTracker = None):
        super().__init__(master)

        self.project = project
        self.on_save = on_save
        self.project_tracker = project_tracker

        self.title(title)
        self.geometry(self.GEOMETRY)
        # The Dependency tab needs this much to keep its Add button on screen
        self.minsize(*self.MINSIZE)
        self.transient(master)
        # Deferred: grabbing before the window is mapped fails on X11
        grab_when_visible(self)
        self.protocol("WM_DELETE_WINDOW", self.cancel)

        self._row = 0
        #: A row that has been started and is not full yet; see _cell
        self._open_row = None
        #: Whether the open row's middle pair has been taken, which decides
        #: where the field that closes the row goes; see _cell
        self._row_has_third = False
        self._prepare_checks()

        #: The caption beside each field, so greying a field out greys what
        #: it is called; see _field and _set_field_enabled
        self._field_labels = {}

        # Guards _recalculate_schedule against the box it writes to setting
        # it off again; see "Working the calculated field out" below
        self._recalculating = False


    # ------------------------------------------------------------------
    # What the fields start on
    # ------------------------------------------------------------------

    def form_template(self) -> Task:
        """
        The task whose values the fields open on.

        RETURNS:
        --------
        Task
            For an edit that is the task itself; for a creation it is a
            stand-in carrying the defaults.

        DEVELOPMENT NOTES:
        ------------------
        One object rather than a field-by-field set of hooks. Every field but
        the name comes off it, and so does the Dependency tab - the create
        dialog was already building a stand-in task for that tab, so this is
        the same object doing both jobs instead of two that had to agree.
        """
        raise NotImplementedError

    def seed_name(self) -> str:
        """
        Text for the name box.

        Not taken from the template: the stand-in the create dialog is
        seeded with carries a placeholder name, while a new task starts with
        the box empty - and may be saved that way. See issue #3.
        """
        return ""

    def seed_type_locked(self) -> bool:
        """Whether the type menu is fixed."""
        return False

    def _chosen_task_type(self) -> str:
        """
        The type the form is currently set to.

        DEVELOPMENT NOTES:
        ------------------
        The menu rather than the task behind it, so choosing Phase greys the
        boxes a Phase does not own straight away. Read off the template, these
        answered for the type the task was *saved* as: a task switched to Phase
        kept live date boxes until it had been saved and reopened.

        Falls back to the template while the form is still being built, and for
        the create dialog's milestone form, which has no type menu at all.
        """
        variable = getattr(self, 'task_type_var', None)
        chosen = variable.get() if variable is not None else ''
        return chosen or self.form_template().task_type

    def _chosen_milestone(self) -> bool:
        """Whether the form is currently describing a milestone."""
        variable = getattr(self, 'is_milestone_var', None)
        if variable is not None:
            return bool(variable.get())
        return self.form_template().effective_milestone

    def _should_show_dates(self) -> bool:
        """Whether date fields should be shown and editable."""
        return self._chosen_task_type() not in CONTAINER_TYPES

    def _should_show_duration(self) -> bool:
        """Whether duration field should be shown and editable."""
        if self._chosen_task_type() in CONTAINER_TYPES:
            return False
        return not self._chosen_milestone()

    def _should_show_progress(self) -> bool:
        """Whether progress field should be shown and editable."""
        template = self.form_template()
        return template.can_edit_progress

    def seed_has_end(self) -> bool:
        """Whether an end date box is shown at all."""
        return True

    def seed_parent(self) -> Optional[Task]:
        """The parent named on the form, if any."""
        parent_id = self.template.parent_task_id
        return self.project.get_task_by_id(parent_id) if parent_id else None

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _next_row(self) -> int:
        """The next free row in the field grid."""
        row = self._row
        self._row += 1
        return row

    def _heading(self, parent, text: str, rule: bool = False):
        """
        A section title on a row of its own, optionally under a rule.

        PARAMETERS:
        -----------
        rule : bool
            Draw a separator above the title. The title goes below the line,
            not beside it: a heading sharing a row with the first field of
            its section reads as that field's label.

        RETURNS:
        --------
        CTkLabel
            The title, for a caller that wants to reach it again.
        """
        if rule:
            ttk.Separator(parent, orient=tk.HORIZONTAL).grid(
                row=self._next_row(), column=0,
                columnspan=self.FIELD_COLUMNS, sticky=tk.EW, pady=(14, 0))

        title = ctk.CTkLabel(parent, text=text, anchor=tk.W,
                             font=ctk.CTkFont(size=15, weight='bold'))
        title.grid(row=self._next_row(), column=0,
                   columnspan=self.FIELD_COLUMNS, sticky=tk.W,
                   pady=(12 if rule else 4, 2))
        return title

    def _cell(self, where: str):
        """
        The row and label column the next field goes in.

        RETURNS:
        --------
        tuple[int, int, int]
            The row, the column its label takes, and how many columns its
            widget spans.

        DEVELOPMENT NOTES:
        ------------------
        A LEFT opens a row, a THIRD may take the middle of it, and a RIGHT
        closes it. Only the RIGHT and the THIRD join a row already open;
        everything else starts a new one, which is what keeps a field that
        was not built - a milestone has no end date - from pulling the next
        one up into a row it does not belong on.

        Where the RIGHT lands depends on whether a THIRD took the middle,
        which is what _row_has_third is for. A pair sits at the first two
        column pairs and leaves the outer one empty, so the two fields stay
        beside each other rather than being pushed to opposite edges with a
        hole between them; a trio uses all three.
        """
        if where in (self.THIRD, self.RIGHT) and self._open_row is not None:
            row = self._open_row
            if where == self.THIRD:
                self._row_has_third = True
                return row, 2, 1
            self._open_row = None
            column = 4 if self._row_has_third else 2
            self._row_has_third = False
            return row, column, 1

        row = self._next_row()
        if where == self.LEFT:
            self._open_row = row
            self._row_has_third = False
            return row, 0, 1

        self._open_row = None
        self._row_has_third = False
        if where in (self.RIGHT, self.THIRD):
            return row, 2, 1
        if where == self.HALF:
            return row, 0, 1
        return row, 0, self.FIELD_COLUMNS - 1

    def _field(self, parent, label: str, widget=None,
               sticky=tk.EW, label_sticky=tk.W, where=None) -> int:
        """
        Put a labelled widget on the grid and return the row it took.

        PARAMETERS:
        -----------
        where : str
            LEFT, THIRD, RIGHT, FULL or HALF; see those constants. FULL by
            default, which is what a field with nothing to sit beside wants.

        The label is remembered against its widget, so that greying a field
        out can grey what it is called as well - see _set_field_enabled.
        """
        where = where or self.FULL
        row, column, span = self._cell(where)

        if where == self.HALF:
            # Held to its own width rather than filling the column, so the
            # window growing does not stretch it; see MENU_WIDTH
            sticky = tk.W
            try:
                widget.configure(width=self.MENU_WIDTH)
            except (AttributeError, tk.TclError, ValueError):
                logger.debug("Could not set the width of %s", label)

        caption = ctk.CTkLabel(parent, text=label)
        caption.grid(row=row, column=column, sticky=label_sticky, pady=5,
                     padx=(15, 0) if column else 0)
        if widget is not None:
            widget.grid(row=row, column=column + 1, columnspan=span,
                        sticky=sticky, pady=5)
            self._field_labels[widget] = caption
            # Painted as it goes in, so every box on the form is coloured by
            # the same rule rather than only the ones something greys out
            self._paint_field(widget)
        return row

    def _set_field_enabled(self, widget, enabled: bool):
        """
        Let a field be filled in, or stop it, and paint it to say which.

        PARAMETERS:
        -----------
        widget : widget
            The box, menu or tick box on the row.
        enabled : bool
            False greys the row and stops it taking input.

        DEVELOPMENT NOTES:
        ------------------
        A DateEntry passes state on to the box and the calendar button it is
        made of; see datepicker.DateEntry.configure.
        """
        if widget is None:
            return

        try:
            widget.configure(state=tk.NORMAL if enabled else tk.DISABLED)
        except (tk.TclError, ValueError):
            logger.debug("Could not set the state of %s", widget)

        self._paint_field(widget, enabled)

    def _paint_field(self, widget, enabled: Optional[bool] = None):
        """
        Colour a field to say whether it is the user's to fill in.

        PARAMETERS:
        -----------
        widget : widget
            The box, menu or tick box on the row.
        enabled : Optional[bool]
            Left out, it is read off the widget - so painting a field never
            changes whether it can be typed in, only how it looks.

        DEVELOPMENT NOTES:
        ------------------
        Every field is painted, not only the ones something disables. A
        disabled CustomTkinter box is barely paler than a live one, so the
        end date being derived for you looked exactly like the start date
        you are meant to type; and painting only the greyed ones left the
        rest on the toolkit's own theme colours, so two live boxes on the
        same form could be different shades of white.

        The caption goes with the box. That is what the eye reads first, and
        a grey label over a shaded box is how every other form says a field
        is not yours to fill in.
        """
        if widget is None:
            return

        if enabled is None:
            enabled = self._field_is_live(widget)

        entry = self._entry_of(widget)
        if isinstance(entry, (ctk.CTkEntry, ctk.CTkTextbox)):
            try:
                entry.configure(
                    fg_color=(self.FIELD_BG if enabled
                              else self.FIELD_BG_DISABLED),
                    text_color=(self.FIELD_TEXT if enabled
                                else self.FIELD_TEXT_DISABLED),
                )
            except (tk.TclError, ValueError):
                logger.debug("Could not shade %s", widget)

        caption = self._field_labels.get(widget)
        if caption is not None:
            caption.configure(text_color=(self.FIELD_TEXT if enabled
                                          else self.FIELD_TEXT_DISABLED))

    def _field_is_live(self, widget) -> bool:
        """
        Whether a field can be typed in as it stands.

        Read off the widget rather than worked out again, so that painting a
        field cannot quietly re-enable one that was built disabled - the
        type menu on a sub-task being the one that would have noticed.
        """
        try:
            return str(self._entry_of(widget).cget('state')) != tk.DISABLED
        except (tk.TclError, ValueError, AttributeError):
            return True

    def _create_form(self):
        """
        Build the whole dialog: both tabs and the button row.

        DEVELOPMENT NOTES:
        ------------------
        The button row is packed last and stays the final child of the
        window, which is how it is found again.
        """
        self.template = self.form_template()

        self.tabs = ctk.CTkTabview(self, command=self._on_tab_changed)
        self.tabs.add("General")
        self.tabs.add("Notes")
        self.tabs.add("Dependency")
        self.tabs.add("Resource")

        # The notes have a tab to themselves.
        #
        # They were the last row of the field grid once, so a box meant for
        # paragraphs sat under everything else at the height of one, and
        # then a column beside the fields - which gave it the height it
        # wanted but took half the width of the form from the fields to do
        # it, on every edit, whether or not the task had any notes at all.
        # A tab costs the fields nothing and gives the notes the whole
        # window when they are what you came for.
        general = self.tabs.tab("General")

        scroller = ScrollFrame(general)
        main_frame = scroller.content
        # The two field columns a pair uses share what is left after the
        # labels, and share it evenly, so a start date and a finish date
        # beside it are the same size as each other.
        #
        # The third pair, which only the Progress row reaches, is left
        # without weight on purpose: it holds a dropdown drawn at its own
        # width, and giving it a share would open a gap in the middle of
        # every row that has only two fields on it.
        main_frame.columnconfigure(1, weight=1, uniform='field')
        main_frame.columnconfigure(3, weight=1, uniform='field')

        self._build_general(main_frame)
        scroller.pack(fill=tk.BOTH, expand=True, padx=5, pady=(5, 0))
        self._build_details(self.tabs.tab("Notes"))
        self._build_problem_line(general)
        self._build_dependency_tab()
        self._build_resource_tab(self.tabs.tab("Resource"))
        self.resource_tab.set_values(self.template)
        self._build_buttons()

        # Packed once the form inside it is finished; see below
        self.tabs.pack(fill=tk.BOTH, expand=True, padx=15, pady=(15, 5))

        self._watch_fields()
        self._watch_type()
        self._check_fields()
        self._focus_when_visible()

    def _focus_when_visible(self, attempt: int = 0):
        """
        Put the cursor in the Name box once the window is up.

        PARAMETERS:
        -----------
        attempt : int
            Retry counter; callers leave this at its default.

        DEVELOPMENT NOTES:
        ------------------
        The form opened with nothing focused at all - focus_get() answered
        None - so the first thing typed went nowhere and the Name field read
        as one that could not be edited. That it worked at all depended on
        the reader clicking into a box first, and on the window manager
        having given the window keyboard focus by then, which is what made
        it look intermittent.

        Deferred and retried for the same reason the grab is; see
        gantt_app.views.modal. Focus asked for before the window manager has
        mapped the window is given away again as it maps, so asking early is
        the same as not asking. The name is where a form is filled in from,
        and where a reader who opened it to correct a typo is already
        looking.

        Never raises: a form nobody can type into yet is a great deal better
        than one that failed to open.
        """
        entry = getattr(self, 'name_entry', None)
        if entry is None:
            return

        try:
            if not self.winfo_exists() or not entry.winfo_exists():
                return
            if self.winfo_viewable():
                entry.focus_set()
                return
        except tk.TclError:
            return

        if attempt >= FOCUS_ATTEMPTS:
            logger.debug("The form never became viewable; nothing focused")
            return

        try:
            self.after(FOCUS_RETRY_MS, self._focus_when_visible, attempt + 1)
        except tk.TclError:
            pass

    def _build_general(self, frame):
        """
        Lay out the General tab with fields grouped by function.
        
        DEVELOPMENT NOTES:
        ------------------
        Four titled sections, in the order somebody reads them: what the row
        is, when it happens, which week it is scheduled against, and how it
        is drawn. The notes are not here - they have a tab of their own.

        Every section but the first is ruled off. Basic Information opens
        the tab, where the top of the panel already does the dividing.

        The scheduling menu comes first in its section, above the start
        date, because it says which of the three boxes under it the form
        fills in. Read after them it explained a shaded box the user had
        already tried to type in.
        """
        self._heading(frame, "Basic Information")
        self.name_entry = ctk.CTkEntry(frame)
        self._field(frame, "Name:", self.name_entry)
        self.name_entry.insert(0, self.seed_name())
        self._build_type(frame)
        self._build_identity(frame)
        self._build_parent(frame)
        self._build_progress(frame)
        self._build_status(frame)
        self._build_priority(frame)

        self._heading(frame, "Schedule", rule=True)
        self._build_scheduling_options(frame)
        self._build_dates(frame)
        self._build_duration(frame)
        self._build_milestone(frame)
        self._build_earliest_begin(frame)

        # Now that all three of them exist. _update_field_states stands
        # aside while the form is still being built, so the call inside
        # _build_scheduling_options no longer reaches anything.
        self._update_field_states()

        # Titles itself, since it is not built at all in a plan that has no
        # named calendars - and a heading over nothing is worse than no
        # heading
        self._build_working_calendar(frame)

        self._heading(frame, "Display", rule=True)
        self._build_show_in_timeline(frame)
        self._build_shape(frame)
        self._build_color(frame)

    def _build_identity(self, frame):
        """Show the task ID. Only an existing task has one."""

    def _build_type(self, frame):
        """The Task Type menu with all available types."""
        self.task_type_var = ctk.StringVar(value=self.template.task_type)
        self.task_type_menu = ctk.CTkOptionMenu(
            frame, variable=self.task_type_var, values=list(TASK_TYPES),
            state=tk.DISABLED if self.seed_type_locked() else tk.NORMAL,
        )
        self._field(frame, "Type:", self.task_type_menu, where=self.LEFT)

    def _watch_type(self):
        """
        Re-apply which boxes are live when the type changes.

        DEVELOPMENT NOTES:
        ------------------
        Attached once the form is built rather than in _build_type, which the
        create dialog replaces with one of its own - the trace would have gone
        with it, and only the edit dialog would have kept up.

        A row with children takes its dates and its length from the work
        inside it, so those boxes stop being the user's the moment the type is
        chosen rather than the next time the form happens to update.
        """
        variable = getattr(self, 'task_type_var', None)
        if variable is None:
            return                      # a milestone has no type menu
        variable.trace_add("write", lambda *_args: self._update_field_states())

    def _build_parent(self, frame):
        """Name the parent, or offer a choice of one."""
        parent = self.seed_parent()
        if parent is not None:
            self.parent_label = ctk.CTkLabel(frame, text=parent.name)
            self._field(frame, "Parent Task:", self.parent_label,
                        sticky=tk.W)

    def _build_dates(self, frame):
        """The start and end boxes, each with a calendar behind it."""
        # Check if dates should be editable for this task type
        dates_editable = self._should_show_dates()
        
        self.start_date_entry = DateEntry(frame,
                                          date=self.template.start_date)
        self._field(frame, "Start Date:", self.start_date_entry,
                    where=self.LEFT)
        
        # A container takes its dates from the work inside it
        if not dates_editable:
            self._set_field_enabled(self.start_date_entry, False)

        if not self.seed_has_end():
            self.end_date_entry = None
            return

        self.end_date_entry = DateEntry(frame, date=self.template.end_date)
        self._field(frame, "End Date:", self.end_date_entry,
                    where=self.RIGHT)
        
        # A milestone takes no time, and a container is bracketed by
        # whatever is under it
        if self.template.effective_milestone or not dates_editable:
            self._set_field_enabled(self.end_date_entry, False)

    def _build_milestone(self, frame):
        """
        The milestone switch, on when a milestone is being created.

        DEVELOPMENT NOTES:
        ------------------
        A switch rather than a tick box. This is not a form the reader
        fills in and submits: flicking it empties the end date and greys it
        out there and then, which is a setting being turned on rather than
        a box being ticked, and a switch is what says so.

        The switch is told what to show rather than left to work it out
        from the variable it was handed. CustomTkinter decides the opening
        state by comparing the variable against its onvalue, which is the
        number 1 against a BooleanVar holding True - a comparison that
        holds in CPython but is the library's business, not ours, and
        differs between its versions. Choosing Create Milestone and finding
        the switch off is the sort of thing that follows.

        Kept as milestone_check: every other part of the form and the tests
        reach it by that name, and CTkSwitch answers select, deselect and
        get exactly as the tick box did.
        """
        self.is_milestone_var = ctk.BooleanVar(
            value=self.template.is_milestone)
        self.milestone_check = ctk.CTkSwitch(
            frame, text="", variable=self.is_milestone_var,
            command=self.toggle_milestone,
        )
        if self.template.is_milestone:
            self.milestone_check.select()
        else:
            self.milestone_check.deselect()
        self._field(frame, "Is Milestone:", self.milestone_check,
                    sticky=tk.W, where=self.RIGHT)

    def _build_color(self, frame):
        """The color picker with Choose and Default buttons."""
        self.color_entry = ColorEntry(frame, color=self.template.color)
        self._field(frame, "Colors:", self.color_entry,
                    sticky=tk.W, label_sticky=tk.NW)

    def _build_scheduling_options(self, frame):
        """The scheduling options dropdown."""
        self.scheduling_options_var = ctk.StringVar(
            value=self.template.scheduling_options if self.template.scheduling_options in [
                "Start date is calculated", "End date is calculated", "Duration is calculated"
            ] else "End date is calculated")
        self.scheduling_options_menu = ctk.CTkOptionMenu(
            frame, variable=self.scheduling_options_var,
            values=["Start date is calculated", "End date is calculated", "Duration is calculated"]
        )
        self._field(frame, "Scheduling options:",
                    self.scheduling_options_menu, where=self.HALF)
        
        # Trace the variable to update field states when changed
        self.scheduling_options_var.trace_add("write", self._on_scheduling_mode_changed)

    def _on_scheduling_mode_changed(self, *args):
        """Grey the newly calculated box out, and work its value out."""
        self._update_field_states()
        self._recalculate_schedule()

    def _update_field_states(self):
        """
        Grey out the boxes the form is filling in for the user.

        DEVELOPMENT NOTES:
        ------------------
        What the task type forbids is applied after the mode, not before. A
        row with children takes its dates and its length from the work
        inside it, and a milestone has neither an end nor a length; enabling
        everything and then greying out only what the mode calls calculated
        handed those back, so the dates of a task that brackets others could
        be typed over and were then overwritten by its children.

        Each field is worked out as one answer and set once, rather than
        being enabled and then disabled again - which flickered, and left
        the shading of a field depending on which rule spoke last.
        """
        mode = self.scheduling_options_var.get()
        if getattr(self, 'duration_entry', None) is None:
            return                      # the form is still being built

        dates_editable = self._should_show_dates()
        milestone = self.is_milestone_var.get()

        calculated = {
            "Start date is calculated": self.start_date_entry,
            "End date is calculated": self.end_date_entry,
            "Duration is calculated": self.duration_entry,
        }.get(mode)

        for widget in (self.start_date_entry, self.end_date_entry,
                       self.duration_entry):
            if widget is None:
                continue

            enabled = widget is not calculated
            if widget in (self.start_date_entry, self.end_date_entry):
                enabled = enabled and dates_editable
            if widget is self.end_date_entry and milestone:
                enabled = False
            if widget is self.duration_entry:
                enabled = enabled and self._should_show_duration()

            self._set_field_enabled(widget, enabled)

    # ------------------------------------------------------------------
    # Working the calculated field out
    # ------------------------------------------------------------------
    #
    # DEVELOPMENT NOTES:
    # ------------------
    # The scheduling menu chooses which of the start date, the end date and
    # the duration the form works out from the other two. It used to do
    # nothing but grey the chosen box out: nothing ever filled it in, so on
    # the setting every task opens with - End date is calculated - the end
    # date could not be typed and was not derived either, and no task's end
    # date could be changed at all.
    #
    # Durations are inclusive, as everywhere else in the application: a task
    # running from Monday to Friday lasts five days.
    #
    # They are also working days, so the arithmetic goes through the project's
    # working calendar rather than through timedelta - see
    # gantt_app.workdaycalendar. Five days from a Thursday ends on the
    # following Wednesday, because the Saturday and the Sunday between them
    # are not worked. Adding four days to the start instead put the end on the
    # Monday and spent two days of the task over a weekend.

    #: How the calculated box is filled in, by which one it is.
    SCHEDULING_MODES = (
        "Start date is calculated",
        "End date is calculated",
        "Duration is calculated",
    )
    DEFAULT_SCHEDULING_MODE = "End date is calculated"

    def _build_working_calendar(self, frame):
        """
        The calendar this task follows, which may not be the plan's.

        DEVELOPMENT NOTES:
        ------------------
        The menu holds readable names; the ids are kept beside it in
        _calendar_ids, because two calendars may be called the same thing
        while their ids cannot be - see CalendarRegistry.make_id - and a
        lookup by label would pick whichever was added first.

        Nothing is built when the plan has no named calendars. A dropdown
        whose only entry is "Project Default" is a control that cannot be
        used, and it would sit in the middle of the scheduling group of every
        form in a plan that never opened the calendar registry.
        """
        options = self.project.calendars.options()
        if len(options) <= 1:
            self.calendar_var = None
            return

        #: Label to calendar id, for reading the menu back.
        self._calendar_ids = {}
        labels = []
        for calendar_id, name in options:
            calendar = self.project.calendars.resolve(calendar_id,
                                                      self.project.calendar)
            label = f"{name} ({describe_week(calendar)})"
            self._calendar_ids[label] = calendar_id
            labels.append(label)

        current = self.template.calendar_id
        active = labels[0]
        for label, calendar_id in self._calendar_ids.items():
            if calendar_id == current and calendar_id is not None:
                active = label
                break

        self.calendar_var = ctk.StringVar(value=active)
        self.calendar_menu = ctk.CTkOptionMenu(frame, variable=self.calendar_var,
                                               values=labels)
        self._heading(frame, "Calendar", rule=True)
        self._field(frame, "Working calendar:", self.calendar_menu,
                    where=self.HALF)

        # The dates follow the moment the calendar changes, without waiting
        # for Save: picking a weekend-only calendar for a task starting on a
        # Thursday should show it moving to the Saturday there and then.
        self.calendar_var.trace_add("write", self._on_calendar_changed)

    def _on_calendar_changed(self, *_args):
        """
        Move the task onto the new calendar, and show where it lands.

        DEVELOPMENT NOTES:
        ------------------
        The start is rolled forward first, then the rest is recalculated from
        it. Recalculating alone would have left the start box on the Thursday
        a weekend-only task can never begin on: add_working_days rolls the
        start forward internally to reach the right finish, so the end date
        was correct while the start beside it was not, and the form disagreed
        with the plan it was about to write.

        Not done in the mode where the start is the calculated box - there it
        is derived from the finish, and writing to it here would be overwritten
        a line later anyway.
        """
        if self._recalculating:
            return
        if getattr(self, 'start_date_entry', None) is None:
            return                      # the form is still being built

        mode = getattr(self, 'scheduling_options_var', None)
        if mode is not None and mode.get() != "Start date is calculated":
            start = self._read_date(self.start_date_entry)
            if start is not None:
                moved = self.working_calendar.get_next_working_day(start)
                if moved != start:
                    self._recalculating = True
                    try:
                        self._write_date(self.start_date_entry, moved)
                    finally:
                        self._recalculating = False

        self._recalculate_schedule()

    def chosen_calendar_id(self) -> Optional[str]:
        """
        The calendar id the form is set to, or None for the plan's own.

        None as well when the plan has no named calendars, so a caller can
        write it onto a task without asking whether the control was built.
        """
        variable = getattr(self, 'calendar_var', None)
        if variable is None:
            return None
        return self._calendar_ids.get(variable.get())

    @property
    def working_calendar(self):
        """
        The calendar the form's date arithmetic goes through.

        The one the task follows: the plan's own unless the working-calendar
        menu names another, so the dates the form writes are the dates the
        scheduler would have worked out for itself. A plan imported from a
        file that declared its holidays gets them here too.
        """
        return self.project.calendars.resolve(self.chosen_calendar_id(),
                                              self.project.calendar)

    def _recalculate_schedule(self, *_args):
        """
        Fill the calculated box in from the two the user fills in.

        Silent about anything it cannot read: this runs on every keystroke,
        and half-typed dates are what typing a date looks like. What the user
        has got wrong by the time they press Save is _read_schedule's to say.
        """
        if self._recalculating:
            return
        if (getattr(self, 'duration_entry', None) is None
                or getattr(self, 'scheduling_options_var', None) is None):
            return                      # the form is still being built

        self._recalculating = True
        try:
            self._fill_calculated_field()
        except (tk.TclError, ValueError, OverflowError):
            logger.debug("Nothing to work the schedule out from yet")
        finally:
            self._recalculating = False

        # Once, on the way out, rather than twice for every box written to.
        # Writing a date empties the box before it fills it, and each of
        # those is a change the checks would otherwise answer - so a
        # keystroke in the name marked the end date missing and unmissing
        # again on its way past.
        self._check_fields()

    def _fill_calculated_field(self):
        """
        Work out whichever of the three the mode names, and write it.

        DEVELOPMENT NOTES:
        ------------------
        Only the two boxes the answer is derived from are read. Reading all
        three meant the box being calculated could stop its own calculation:
        a duration left at -87 by a half-finished edit made _typed_duration
        raise, which was caught as "nothing to work it out from yet", so the
        duration stayed at -87 and the save was refused for it.
        """
        if self.is_milestone_var.get():
            return                      # a milestone is a day with no length

        mode = self.scheduling_options_var.get()
        calendar = self.working_calendar

        if mode == "Duration is calculated":
            start = self._read_date(self.start_date_entry)
            end = self._read_date(self.end_date_entry)
            if start is None or end is None:
                return
            self._write_duration(calendar.working_days_between(start, end))
        elif mode == "End date is calculated":
            start = self._read_date(self.start_date_entry)
            length = self._typed_duration()
            if start is None or length is None:
                return
            self._write_date(self.end_date_entry,
                             calendar.add_working_days(start, length))
        elif mode == "Start date is calculated":
            end = self._read_date(self.end_date_entry)
            length = self._typed_duration()
            if end is None or length is None:
                return
            self._write_date(self.start_date_entry,
                             calendar.subtract_working_days(end, length))

    def _typed_duration(self) -> Optional[int]:
        """
        The number in the duration box, or None when it is not the user's.

        RAISES:
        -------
        ValueError
            When there is something in the box that is not a whole number of
            days, or is not a length a task could have.

        DEVELOPMENT NOTES:
        ------------------
        A greyed-out box is not read. A row with children takes its
        length from the work inside them, and Task.duration_days answers 0
        for both - so the form read a length of nought days out of a box its
        own rules had disabled, and refused to create either of them for
        being shorter than a day.
        """
        if str(self.duration_entry.cget('state')) == tk.DISABLED:
            return None

        text = self.duration_entry.get().strip()
        if not text:
            return None
        try:
            days = int(text)
        except ValueError:
            raise ValueError(
                "Write the duration as a whole number of days."
            ) from None
        if days < 1:
            raise ValueError("A task lasts at least one day.")
        return days

    def _typed_progress(self) -> int:
        """
        The percentage in the progress box, or 0 when it is empty.

        RAISES:
        -------
        ValueError
            When it is not a percentage.

        DEVELOPMENT NOTES:
        ------------------
        int() is not left to raise on its own here. Its complaint - "invalid
        literal for int() with base 10: 'half'" - was going into the dialog
        the user sees, which tells them what Python was doing rather than
        what they should type.
        """
        text = self.progress_entry.get().strip()
        if not text:
            return 0
        try:
            progress = int(text)
        except ValueError:
            raise ValueError(
                "Write the progress as a whole number from 0 to 100."
            ) from None
        if not 0 <= progress <= 100:
            raise ValueError("Progress runs from 0 to 100.")
        return progress

    def _write_duration(self, days: int):
        """
        Put a length in the duration box, through a disabled one.

        A span that runs backwards is not written. It happens in passing
        while a pair of dates is being retyped, and putting "-87" in the box
        on the way would leave it there if the user stopped at that point.
        The end date falling before the start is what the form says instead.

        Written through the variable rather than into the widget. A disabled
        entry refuses delete() and insert() outright, which is why the state
        was being flipped around them, and the variable is what the box shows
        either way - so the box the mode has greyed out still updates.
        """
        if days < 1:
            return

        self.duration_var.set(str(days))

    def _read_schedule(self):
        """
        The start, end and length the form describes.

        RETURNS:
        --------
        tuple
            (start, end, duration), the one the scheduling mode names having
            been worked out from the other two rather than read back out of
            the box showing it.

        RAISES:
        -------
        ValueError
            When a box the user fills in cannot be read, or the three do not
            describe a task that lasts at least a day.

        DEVELOPMENT NOTES:
        ------------------
        The length that comes back is working days, which is what the task
        stores. A span falling entirely on a weekend holds no work at all, and
        is refused rather than saved as a task of nought days - a start date on
        a Saturday is what puts a task there, and the form says so instead of
        quietly moving it.
        """
        self._recalculate_schedule()

        start = self._typed_date(self.start_date_entry, "start date")
        if start is None:
            raise ValueError("Enter a start date.")

        if self.is_milestone_var.get():
            return start, None, 0

        end = self._typed_date(self.end_date_entry, "end date")
        length = self._typed_duration()

        if end is None and length is not None:
            end = self.working_calendar.add_working_days(start, length)
        if end is None:
            return start, None, None
        if end < start:
            raise ValueError("The end date falls before the start date.")

        worked = self.working_calendar.working_days_between(start, end)
        if worked < 1:
            raise ValueError(
                "The task falls entirely on non-working days. Start it on a "
                "working day, or give it a longer span."
            )

        return start, end, worked

    def _field_edited(self, key):
        """
        Note the change, work the calculated box out, and check the form.

        A change this made itself is not one to answer: _recalculate_schedule
        checks the form once when it is done, and treating its own writes as
        the user's would have the form marking a box it is halfway through
        filling in.
        """
        if self._recalculating:
            return
        super()._field_edited(key)
        self._recalculate_schedule()

    def _build_duration(self, frame):
        """
        The duration entry field.

        DEVELOPMENT NOTES:
        ------------------
        Watched through a variable, like the checked fields in formcheck, so
        the box the mode is deriving fills itself in as the duration is typed.
        The three date fields were watched and this one was not, so on the
        setting every task opens with - End date is calculated - typing a
        duration changed nothing on screen. The end date caught up only when
        Save read the form, which meant the number in front of the user and
        the date beside it disagreed right up until the task was saved.

        The initial value is set before the trace is attached. The scheduling
        menu is built after this box, so a trace firing here would run
        _fill_calculated_field before there was a mode for it to read.
        """
        # Check if duration should be editable for this task type
        duration_editable = self._should_show_duration()

        duration = self.template.duration
        if duration is None:
            # Calculate from dates if not manually set
            duration = self.template.duration_days
        if not duration and self.template.end_date is not None:
            # duration_days answers 0 for a row with children, whose
            # length is the work inside them. Nothing is inside one yet when
            # it is being created, and showing a length of nought days for a
            # task with two dates on the same form reads as a mistake
            duration = self.working_calendar.working_days_between(
                self.template.start_date, self.template.end_date)

        self.duration_var = ctk.StringVar(
            value="" if duration is None else str(duration)
        )
        self.duration_entry = ctk.CTkEntry(frame,
                                           textvariable=self.duration_var)
        self.duration_var.trace_add('write', self._duration_edited)
        self._field(frame, "Duration:", self.duration_entry,
                    where=self.LEFT)

        # A milestone has no length, and a container's is its children's
        if not duration_editable:
            self._set_field_enabled(self.duration_entry, False)

    def _duration_edited(self, *_args):
        """
        Work the calculated box out again, the duration having changed.

        Guarded like formcheck's watcher: a variable's trace can fire while
        the dialog is being torn down, when the boxes it would read are gone.
        """
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return

        self._recalculate_schedule()

    def _build_earliest_begin(self, frame):
        """
        The earliest begin date, with a button to copy the start date in.

        DEVELOPMENT NOTES:
        ------------------
        The three controls belong to a frame of their own, and are packed
        into that. Built against the form frame instead - which every other
        row is placed in with grid - pack and grid each took the form's size
        to be theirs to decide, and settled it between them by resizing it at
        one another until the process stopped responding. Opening a task for
        editing hung the application on the spot.
        """
        self.earliest_begin_var = ctk.BooleanVar(value=False)

        row_frame = ctk.CTkFrame(frame, fg_color='transparent')
        self.earliest_begin_check = ctk.CTkCheckBox(
            row_frame, text="", variable=self.earliest_begin_var
        )
        self.earliest_begin_entry = DateEntry(
            row_frame, date=self.template.earliest_begin)
        copy_button = ctk.CTkButton(
            row_frame, text="Copy begin date", width=120,
            command=self._copy_begin_date
        )

        self.earliest_begin_check.pack(side=tk.LEFT)
        self.earliest_begin_entry.pack(side=tk.LEFT, padx=5)
        copy_button.pack(side=tk.LEFT, padx=5)

        self._field(frame, "Earliest begin:", row_frame, sticky=tk.W)

        # The date and the button beside it mean nothing until the box is
        # ticked, so they are greyed until it is. _field paints the row's
        # frame, which is not a box, so these are painted by name.
        self._earliest_begin_button = copy_button
        self.earliest_begin_var.trace_add(
            'write', lambda *_args: self._update_earliest_begin())
        self._update_earliest_begin()

    def _update_earliest_begin(self):
        """Let the earliest begin date be set only when it is asked for."""
        wanted = bool(self.earliest_begin_var.get())
        self._set_field_enabled(self.earliest_begin_entry, wanted)
        try:
            self._earliest_begin_button.configure(
                state=tk.NORMAL if wanted else tk.DISABLED)
        except (tk.TclError, ValueError):
            logger.debug("Could not set the state of Copy begin date")

    def _copy_begin_date(self):
        """Copy the start date to the earliest begin date."""
        if hasattr(self, 'start_date_entry') and self.start_date_entry:
            start_date = self._read_date(self.start_date_entry)
            if start_date:
                self.earliest_begin_entry.set_date(start_date)

    def _build_priority(self, frame):
        """The priority dropdown."""
        self.priority_var = ctk.StringVar(value=self.template.priority)
        self.priority_menu = ctk.CTkOptionMenu(
            frame, variable=self.priority_var,
            values=PRIORITY_LEVELS
        )
        self._field(frame, "Priority:", self.priority_menu,
                    where=self.RIGHT)

    def _build_status(self, frame):
        """
        Draft or Active, between the percentage and the priority.

        DEVELOPMENT NOTES:
        ------------------
        The middle of the three fields on that row; see _cell for what THIRD
        means to the grid. Read with getattr rather than off the attribute,
        because the template is whatever the dialog was seeded with and an
        older one - a task read back from a file written before the field
        existed - carries no status at all.
        """
        template_status = getattr(self.template, 'status', None)
        if template_status is None:
            logger.debug("The template carries no status; using Active")
            template_status = 'Active'
        self.status_var = ctk.StringVar(value=template_status)
        self.status_menu = ctk.CTkOptionMenu(
            frame, variable=self.status_var,
            values=list(TASK_STATUSES)
        )
        self._field(frame, "Status:", self.status_menu, where=self.THIRD)

    def _build_show_in_timeline(self, frame):
        """The show in timeline checkbox."""
        self.show_in_timeline_var = ctk.BooleanVar(
            value=self.template.show_in_timeline)
        self.show_in_timeline_check = ctk.CTkCheckBox(
            frame, text="", variable=self.show_in_timeline_var
        )
        self._field(frame, "Show in timeline:", self.show_in_timeline_check,
                    sticky=tk.W)

    def _build_shape(self, frame):
        """The shape dropdown."""
        self.shape_var = ctk.StringVar(value=self.template.shape)
        self.shape_menu = ctk.CTkOptionMenu(
            frame, variable=self.shape_var,
            values=["Default", "Rectangle", "Rounded"]
        )
        self._field(frame, "Shape:", self.shape_menu, where=self.HALF)

    def _build_progress(self, frame):
        """
        How far along this is: a percentage on every row that carries its
        own, and nothing to fill in on one that takes it from the work
        underneath.

        DEVELOPMENT NOTES:
        ------------------
        A sub-task was a tick here - done or not - because the task above it
        counted how many of its sub-tasks were ticked, and a 60% that then
        counted as not done would have been a number the form accepted and
        the plan ignored.

        The task above averages its sub-tasks' percentages now, so a 60%
        counts for 60%, and there is no longer anything for a tick to
        protect. A sub-task that is half done can say so.
        """
        self.progress_entry = ctk.CTkEntry(frame)
        self.progress_entry.insert(0, str(self.template.progress))
        self._field(frame, "Progress (%):", self.progress_entry,
                    where=self.LEFT)

        # Rolled up from the children of anything that has them
        if not self._should_show_progress():
            self._set_field_enabled(self.progress_entry, False)

    def _build_details(self, parent):
        """
        The notes box, filling its tab.

        PARAMETERS:
        -----------
        parent : widget
            The Notes tab.
        """
        pane = ctk.CTkFrame(parent, fg_color='transparent')
        pane.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        pane.grid_rowconfigure(0, weight=1)
        pane.grid_columnconfigure(0, weight=1)

        self.details_text = ctk.CTkTextbox(pane, wrap='word')
        self.details_text.grid(row=0, column=0, sticky=tk.NSEW)
        # Painted like every other box on the form. It is not placed by
        # _field, having a column to itself rather than a row.
        self._paint_field(self.details_text)
        if self.template.details:
            self.details_text.insert("1.0", self.template.details)

    def _build_dependency_tab(self):
        """
        Prepare the Dependency tab without filling it in.

        DEVELOPMENT NOTES:
        ------------------
        The editor is built the first time the tab is looked at, not when the
        dialog opens. It costs about ten of the twenty-six milliseconds an
        edit dialog took, and most edits are a name or a date and never go
        near it - paying for it on the way in made every edit slower for the
        sake of the ones that do.
        """
        self._dependency_editor = None

    def _build_resource_tab(self, tab):
        """Build the Resource assignment tab."""
        self.resource_tab = TaskResourceTab(tab, self.project, self.template)
        self.resource_tab.pack(fill=tk.BOTH, expand=True)

    def _on_tab_changed(self):
        """Fill the Dependency tab in the first time it is opened."""
        try:
            if self.tabs.get() == "Dependency":
                self._ensure_dependency_editor()
        except (tk.TclError, AttributeError):
            pass

    def _ensure_dependency_editor(self):
        """Build the dependency editor if it is not there yet."""
        if self._dependency_editor is None:
            self._dependency_editor = DependencyEditor(
                self.tabs.tab("Dependency"), self.project, self.template,
                on_changed=self._on_dependencies_changed,
            )
            self._dependency_editor.pack(fill=tk.BOTH, expand=True,
                                         padx=5, pady=5)
        return self._dependency_editor

    @property
    def dependency_editor(self):
        """
        The Dependency tab's editor, built on first use.

        Reaching for it is what a caller does when it needs the links, so
        asking is enough to bring it into being.
        """
        return self._ensure_dependency_editor()

    def _build_buttons(self):
        """
        The button row.

        DEVELOPMENT NOTES:
        ------------------
        Packed right to left, so it reads Close, Save & Close, Save & New.
        Anything a subclass adds goes on the left, away from these: the edit
        dialog's Delete is the one action here that the button beside it
        cannot take back.
        """
        frame = ctk.CTkFrame(self)
        frame.pack(fill=tk.X, padx=20, pady=10)

        #: The action buttons by label, so their styling can be checked and
        #: so a subclass can reach one without hunting through the frame
        self.action_buttons = {}

        self._build_leading_buttons(frame)

        # Save & Close is the primary action and looks like it; Cancel is
        # the way out and is drawn quietly, as a secondary button. Save & New
        # sits between them at the ordinary weight - it is a save, but not
        # the one Enter performs.
        secondary = {
            'fg_color': 'transparent',
            'border_width': 1,
            'border_color': theme.SEPARATOR,
            'text_color': theme.TEXT,
            'hover_color': theme.MENU_HOVER,
        }

        for label, command, style in (
                ("Save & New", self.save_and_new, {}),
                ("Save & Close", self.save, {}),
                ("Cancel", self.cancel, secondary)):
            button = ctk.CTkButton(frame, text=label, width=self.ACTION_WIDTH,
                                   command=command, **style)
            button.pack(side=tk.RIGHT, padx=5)
            self.action_buttons[label] = button

        self._bind_exit_shortcuts()

    def _bind_exit_shortcuts(self):
        """
        Enter saves and closes, Escape cancels.

        DEVELOPMENT NOTES:
        ------------------
        Bound on the window rather than on each field, so they answer
        wherever the focus is - which is the point of a shortcut for someone
        working down a list of tasks.

        Enter has to leave the notes box alone. A newline is what Enter means
        inside a multi-line box, so the handler asks what has focus and does
        nothing when the answer is a text area. It can afford to: Tk runs the
        widget's own class binding before this one, so by the time this is
        reached the newline has already been typed. The modifier form saves
        from in there, which is the convention everywhere else.
        """
        self.bind('<Return>', self._return_pressed, add='+')
        self.bind('<KP_Enter>', self._return_pressed, add='+')
        self.bind('<Escape>', lambda _event: self.cancel(), add='+')

        # Cmd+Enter on a Mac, Ctrl+Enter elsewhere; see gantt_app.shortcuts
        bind_shortcut(self, 'Return', lambda _event: self.save())
        bind_shortcut(self, 'KP_Enter', lambda _event: self.save())

    def _return_pressed(self, _event=None):
        """
        Save and close, unless the newline was meant for a text box.

        RETURNS:
        --------
        Optional[str]
            'break' when it saved, so nothing further acts on the key.
        """
        if self._focus_is_multiline():
            return None
        self.save()
        return 'break'

    def _focus_is_multiline(self) -> bool:
        """
        Whether what has focus is a box a newline belongs in.

        DEVELOPMENT NOTES:
        ------------------
        A CTkTextbox is a frame holding a tkinter.Text, and which of the two
        Tk names as the focus depends on the CustomTkinter version - so
        neither check is enough on its own. The walk up the parents catches
        both, and catches a scrolled text box wrapped in another frame if one
        ever appears.

        Depth-limited as a guard. Nothing here nests more than a couple of
        levels, but a widget tree that somehow cycled would otherwise spin
        inside a key press.
        """
        try:
            focused = self.focus_get()
        except (tk.TclError, KeyError):
            return False

        for _ in range(4):
            if focused is None or focused is self:
                return False
            if isinstance(focused, (tk.Text, ctk.CTkTextbox)):
                return True
            focused = getattr(focused, 'master', None)
        return False

    def _build_leading_buttons(self, frame):
        """Buttons on the left of the row. Help button by default."""
        ctk.CTkButton(frame, text="Help", width=self.ACTION_WIDTH,
                      command=self._show_editor_help).pack(side=tk.LEFT, padx=5)

    # ------------------------------------------------------------------
    # Behaviour
    # ------------------------------------------------------------------

    def _show_editor_help(self):
        """
        Open the reference on the editor's fields.

        Imported here rather than at the top of the module so the window's
        text is only read in by someone who asks for it: the editor opens
        without it, and most edits never press Help.
        """
        from gantt_app.help.editorhelp import EditorHelpWindow

        EditorHelpWindow.show(self)

    def toggle_milestone(self):
        """
        Switch the end date off for a milestone, and back on for a task.

        DEVELOPMENT NOTES:
        ------------------
        Un-ticking counts as having been in the end date box: the user has
        just asked for a task that needs one, so an empty box is worth
        pointing at right away rather than waiting for them to click into it.

        Which boxes are live is left to _update_field_states rather than being
        decided here. Enabling the end date directly handed it back even when
        the scheduling mode was deriving it, so the box was typable and then
        overwritten. Working the schedule out afterwards is what fills the end
        date in the moment a milestone becomes a task again, rather than
        leaving the box empty until something else is typed.
        """
        if not self.end_date_entry:
            return
        if not self.is_milestone_var.get():
            self._touched.add('end_date')

        self._update_field_states()
        self._recalculate_schedule()



    def _read_date(self, entry) -> Optional[datetime]:
        """Parse a date box, or None when it is empty or will not parse."""
        if entry is None:
            return None
        try:
            text = entry.get().strip()
        except tk.TclError:
            return None
        if not text:
            return None
        try:
            return datetime.strptime(text, self.DATE_FORMAT)
        except ValueError:
            return None

    def _write_date(self, entry, value: datetime):
        """Put a date in a box, through a disabled one if need be."""
        if entry is None:
            return
        entry.set_date(value)

    def _typed_date(self, entry, label: str) -> Optional[datetime]:
        """
        Parse a date box, refusing text that is there but will not parse.

        RETURNS:
        --------
        Optional[datetime]
            The date, or None when the box is empty.

        RAISES:
        -------
        ValueError
            When there is something in the box that is not a date.

        DEVELOPMENT NOTES:
        ------------------
        _read_date answers None for an empty box and for '15/08/2026' alike,
        which is right where a missing date is allowed and wrong where the
        answer is written back: an end date typed the American way round
        parsed as None and silently cleared the date the task already had.
        """
        if entry is None:
            return None
        text = entry.get().strip()
        if not text:
            return None
        try:
            return datetime.strptime(text, self.DATE_FORMAT)
        except ValueError:
            raise ValueError(
                f"Write the {label} as YYYY-MM-DD, as in 2026-08-15."
            ) from None

    # ------------------------------------------------------------------
    # Checking the form as it is filled in
    # ------------------------------------------------------------------
    #

    def _on_dependencies_changed(self):
        """
        Move the dates to satisfy the chosen links.

        DEVELOPMENT NOTES:
        ------------------
        This is what makes choosing a predecessor fill the start date in. A
        Hard link pins it; a Rubber link only moves it when the current date
        would start too early. The task keeps its length, so the end moves
        with the start.

        Both dialogs used to do this with their own copy, differing only in
        where the length came from - one read the task, the other the boxes.
        Reading the boxes works for both, and is what the user is looking at.
        """
        # getattr, not attribute access: this fires while the dialog is
        # still being built, before _build_dependency_tab has run
        editor = getattr(self, '_dependency_editor', None)
        if editor is None or not hasattr(self, 'start_date_entry'):
            # Called while the dialog is still being built
            return

        current = self._read_date(self.start_date_entry)
        if current is None:
            return

        required = editor.required_start_date(current)
        if required is None or required == current:
            return

        end = self._read_date(self.end_date_entry)
        duration = (end - current) if end is not None else None

        self._write_date(self.start_date_entry, required)

        if duration is not None and not self.is_milestone_var.get():
            self._write_date(self.end_date_entry, required + duration)

        logger.debug("Start date moved to %s by a dependency",
                     required.strftime(self.DATE_FORMAT))

    def save(self):
        """Write the form and close."""
        if self._apply():
            self.destroy()

    def save_and_new(self):
        """
        Write the form, then set up for another task.

        DEVELOPMENT NOTES:
        ------------------
        Nothing happens if the save failed, so a rejected date leaves the
        form up with its reason rather than being cleared or replaced.
        """
        if self._apply():
            self._start_another()

    def _start_another(self):
        """What Save & New does once the save succeeded."""
        raise NotImplementedError

    def _apply(self) -> bool:
        """
        Write the form onto a task.

        RETURNS:
        --------
        bool
            True when it was saved, False when the form would not parse -
            which leaves the dialog open showing why.
        """
        raise NotImplementedError

    def _report_invalid(self, error):
        """
        Say why the form was rejected, without closing it.

        DEVELOPMENT NOTES:
        ------------------
        The reasons are written where they are raised, in the words the form
        itself uses beside the field, so there is no table here translating
        one wording into another - a table that went stale the moment either
        side of it was reworded, and matched on the text of exceptions the
        standard library raises rather than on anything this code decides.

        Marking the fields first leaves the offending box outlined behind the
        message, so dismissing it does not lose which one was meant.
        """
        self._first_problem()
        messagebox.showerror("Invalid Entry", str(error), parent=self)

    def cancel(self):
        """Close without saving."""
        self.destroy()

    def center_window(self):
        """
        Centre the window on the screen.

        DEVELOPMENT NOTES:
        ------------------
        The size is taken from GEOMETRY, which was just set, rather than
        measured. Measuring meant update_idletasks, and forcing a full layout
        pass of a form that has only this instant been built was about ten of
        the thirty-five milliseconds an edit dialog took to open - the single
        largest thing in it, spent learning a number already known.
        """
        try:
            width, height = (int(part) for part in self.GEOMETRY.split('x'))
        except ValueError:
            return

        x = (self.winfo_screenwidth() - width) // 2
        y = (self.winfo_screenheight() - height) // 2
        self.geometry(f"{width}x{height}+{max(x, 0)}+{max(y, 0)}")
