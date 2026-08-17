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
from datetime import datetime, timedelta
from typing import Optional, Callable

import customtkinter as ctk

from gantt_app.models import Task, Project, TASK_TYPES
from gantt_app.priority import PRIORITY_LEVELS
from gantt_app.utils.undoredo import ProjectStateTracker
from gantt_app.views.modal import grab_when_visible
from gantt_app.views.colorpicker import ColorEntry
from gantt_app.views.datepicker import DateEntry
from gantt_app.views.formcheck import FormChecks
from gantt_app.views.scrollframe import ScrollFrame
from gantt_app.views.dependency_editor import DependencyEditor
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


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

    #: Colour a new row starts on, by what is being created.
    DEFAULT_COLORS = {
        'Phase': "#34495e",        # Dark Blue
        'Deliverable': "#28a745",   # Green  
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
        self._prepare_checks()

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

        Not taken from the template: a Task must be named to exist, so the
        stand-in has one, while a new task starts with the box empty.
        """
        return ""

    def seed_type_locked(self) -> bool:
        """Whether the type menu is fixed."""
        return False

    def _should_show_dates(self) -> bool:
        """Whether date fields should be shown and editable."""
        template = self.form_template()
        return template.can_edit_dates

    def _should_show_duration(self) -> bool:
        """Whether duration field should be shown and editable."""
        template = self.form_template()
        return template.can_edit_duration

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

    def _field(self, parent, label: str, widget=None,
               sticky=tk.EW, label_sticky=tk.W) -> int:
        """Put a labelled widget on the next row and return that row."""
        row = self._next_row()
        ctk.CTkLabel(parent, text=label).grid(
            row=row, column=0, sticky=label_sticky, pady=5)
        if widget is not None:
            widget.grid(row=row, column=1, sticky=sticky, pady=5)
        return row

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
        self.tabs.add("Dependency")

        # The General tab is two columns: the fields on the left, the notes
        # beside them on the right.
        #
        # The notes used to be the last row of the field grid, so a box
        # meant for paragraphs sat under everything else at the height of
        # one - a scroll away from the name of the task it describes, and
        # squeezing every field above it to make room. Beside the fields it
        # has the height of the form to fill, which is what a notes panel is
        # for, and neither column crowds the other.
        general = self.tabs.tab("General")
        columns = ctk.CTkFrame(general, fg_color='transparent')
        columns.pack(fill=tk.BOTH, expand=True, padx=5, pady=(5, 0))
        columns.grid_rowconfigure(0, weight=1)
        columns.grid_columnconfigure(0, weight=3, uniform='pane')
        columns.grid_columnconfigure(1, weight=2, uniform='pane')

        scroller = ScrollFrame(columns)
        main_frame = scroller.content
        main_frame.columnconfigure(1, weight=1)

        self._build_general(main_frame)
        scroller.grid(row=0, column=0, sticky=tk.NSEW)
        self._build_details(columns)
        self._build_problem_line(general)
        self._build_dependency_tab()
        self._build_buttons()

        # Packed once the form inside it is finished; see below
        self.tabs.pack(fill=tk.BOTH, expand=True, padx=15, pady=(15, 5))

        self._watch_fields()
        self._check_fields()

    def _build_general(self, frame):
        """
        Lay out the General tab with fields grouped by function.
        
        DEVELOPMENT NOTES:
        ------------------
        Fields are organized in logical groups:
        1. Basic Information: name, ID, type, parent
        2. Scheduling: dates, duration, milestone flag
        3. Additional Scheduling: scheduling options, earliest begin
        4. Progress: completion percentage
        5. Appearance: color, shape
        6. Details: notes/details
        
        This grouping makes the dialog more intuitive to use
        without adding any performance overhead.
        """
        # Basic Information group
        self.name_entry = ctk.CTkEntry(frame)
        self._field(frame, "Name:", self.name_entry)
        self.name_entry.insert(0, self.seed_name())
        self._build_identity(frame)
        self._build_type(frame)
        self._build_parent(frame)

        # Separator between Basic Information and Scheduling
        ttk.Separator(frame, orient=tk.HORIZONTAL).grid(
            row=self._next_row(), column=0, columnspan=2, sticky=tk.EW, pady=10
        )

        # Scheduling group
        self._build_dates(frame)
        self._build_duration(frame)
        self._build_milestone(frame)
        self._build_scheduling_options(frame)
        self._build_earliest_begin(frame)

        # Separator between Scheduling and Progress
        ttk.Separator(frame, orient=tk.HORIZONTAL).grid(
            row=self._next_row(), column=0, columnspan=2, sticky=tk.EW, pady=10
        )

        # Progress group
        self._build_progress(frame)
        self._build_priority(frame)
        self._build_show_in_timeline(frame)
        self._build_shape(frame)

        # Separator between Progress and Appearance
        ttk.Separator(frame, orient=tk.HORIZONTAL).grid(
            row=self._next_row(), column=0, columnspan=2, sticky=tk.EW, pady=10
        )

        # Appearance group
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
        self._field(frame, "Type:", self.task_type_menu)

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
        self._field(frame, "Start Date:", self.start_date_entry)
        
        # Disable start date for containers (rolled up from children)
        if not dates_editable:
            self.start_date_entry.configure(state=tk.DISABLED)

        if not self.seed_has_end():
            self.end_date_entry = None
            return

        self.end_date_entry = DateEntry(frame, date=self.template.end_date)
        self._field(frame, "End Date:", self.end_date_entry)
        
        # Disable end date for milestones and containers
        if self.template.effective_milestone or not dates_editable:
            self.end_date_entry.configure(state=tk.DISABLED)

    def _build_milestone(self, frame):
        """
        The milestone tick box, ticked when a milestone is being created.

        DEVELOPMENT NOTES:
        ------------------
        The box is told what to show rather than left to work it out from
        the variable it was handed. CustomTkinter decides a checkbox's
        opening state by comparing the variable against its onvalue, which
        is the number 1 against a BooleanVar holding True - a comparison
        that holds in CPython but is the library's business, not ours, and
        differs between its versions. Choosing Create Milestone and finding
        the box unticked is the sort of thing that follows.
        """
        self.is_milestone_var = ctk.BooleanVar(
            value=self.template.is_milestone)
        self.milestone_check = ctk.CTkCheckBox(
            frame, text="", variable=self.is_milestone_var,
            command=self.toggle_milestone,
        )
        if self.template.is_milestone:
            self.milestone_check.select()
        else:
            self.milestone_check.deselect()
        self._field(frame, "Is Milestone:", self.milestone_check, sticky=tk.W)

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
        self._field(frame, "Scheduling options:", self.scheduling_options_menu)
        
        # Trace the variable to update field states when changed
        self.scheduling_options_var.trace_add("write", self._on_scheduling_mode_changed)
        
        # Initialize field states based on the current mode
        self._update_field_states()

    def _on_scheduling_mode_changed(self, *args):
        """Grey the newly calculated box out, and work its value out."""
        self._update_field_states()
        self._recalculate_schedule()

    def _update_field_states(self):
        """
        Grey out the box the scheduling mode says is not the user's to fill.

        DEVELOPMENT NOTES:
        ------------------
        What the task type forbids is applied after the mode, not before. A
        Phase or a Deliverable takes its dates and its length from the work
        inside it, and a milestone has neither an end nor a length; enabling
        everything and then greying out only what the mode calls calculated
        handed those back, so the dates of a task that brackets others could
        be typed over and were then overwritten by its children.
        """
        mode = self.scheduling_options_var.get()
        if getattr(self, 'duration_entry', None) is None:
            return                      # the form is still being built

        for widget in (self.start_date_entry, self.end_date_entry,
                       self.duration_entry):
            if widget is not None:
                widget.configure(state=tk.NORMAL)

        calculated = {
            "Start date is calculated": self.start_date_entry,
            "End date is calculated": self.end_date_entry,
            "Duration is calculated": self.duration_entry,
        }.get(mode)
        if calculated is not None:
            calculated.configure(state=tk.DISABLED)

        if not self._should_show_dates():
            for widget in (self.start_date_entry, self.end_date_entry):
                if widget is not None:
                    widget.configure(state=tk.DISABLED)
        if not self._should_show_duration():
            self.duration_entry.configure(state=tk.DISABLED)
        if self.end_date_entry is not None and self.is_milestone_var.get():
            self.end_date_entry.configure(state=tk.DISABLED)

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
    # running from the 1st to the 5th lasts five days, so a task of n days
    # ends n - 1 days after it starts.

    #: How the calculated box is filled in, by which one it is.
    SCHEDULING_MODES = (
        "Start date is calculated",
        "End date is calculated",
        "Duration is calculated",
    )
    DEFAULT_SCHEDULING_MODE = "End date is calculated"

    def _recalculate_schedule(self, *_args):
        """
        Fill the calculated box in from the two the user fills in.

        Silent about anything it cannot read: this runs on every keystroke,
        and half-typed dates are what typing a date looks like. What the user
        has got wrong by the time they press Save is _read_schedule's to say.
        """
        if self._recalculating:
            return
        if getattr(self, 'duration_entry', None) is None:
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

        if mode == "Duration is calculated":
            start = self._read_date(self.start_date_entry)
            end = self._read_date(self.end_date_entry)
            if start is None or end is None:
                return
            self._write_duration((end - start).days + 1)
        elif mode == "End date is calculated":
            start = self._read_date(self.start_date_entry)
            length = self._typed_duration()
            if start is None or length is None:
                return
            self._write_date(self.end_date_entry,
                             start + timedelta(days=length - 1))
        elif mode == "Start date is calculated":
            end = self._read_date(self.end_date_entry)
            length = self._typed_duration()
            if end is None or length is None:
                return
            self._write_date(self.start_date_entry,
                             end - timedelta(days=length - 1))

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
        A greyed-out box is not read. A Phase and a Deliverable take their
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
        if self.progress_done_var is not None:
            # A sub-task is ticked or it is not
            return 100 if self.progress_done_var.get() else 0

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
        """
        if days < 1:
            return

        entry = self.duration_entry
        disabled = str(entry.cget('state')) == tk.DISABLED
        if disabled:
            entry.configure(state=tk.NORMAL)
        entry.delete(0, tk.END)
        entry.insert(0, str(days))
        if disabled:
            entry.configure(state=tk.DISABLED)

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
            end = start + timedelta(days=length - 1)
        if end is None:
            return start, None, None
        if end < start:
            raise ValueError("The end date falls before the start date.")

        return start, end, (end - start).days + 1

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
        """The duration entry field."""
        # Check if duration should be editable for this task type
        duration_editable = self._should_show_duration()
        
        duration = self.template.duration
        if duration is None:
            # Calculate from dates if not manually set
            duration = self.template.duration_days
        if not duration and self.template.end_date is not None:
            # duration_days answers 0 for a Phase or a Deliverable, whose
            # length is the work inside them. Nothing is inside one yet when
            # it is being created, and showing a length of nought days for a
            # task with two dates on the same form reads as a mistake
            duration = (self.template.end_date
                        - self.template.start_date).days + 1
        self.duration_entry = ctk.CTkEntry(frame)
        if duration is not None:
            self.duration_entry.insert(0, str(duration))
        self._field(frame, "Duration:", self.duration_entry)
        
        # Disable duration for milestones and containers
        if not duration_editable:
            self.duration_entry.configure(state=tk.DISABLED)

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
        self._field(frame, "Priority:", self.priority_menu)

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
        self._field(frame, "Shape:", self.shape_menu)

    def _build_progress(self, frame):
        """
        How far along this is: a tick for a sub-task, a percentage for the
        rest, and nothing to fill in on a task that takes its own from the
        work underneath it.

        DEVELOPMENT NOTES:
        ------------------
        A sub-task is a tick on a checklist - done or not - and the task
        above it reads how many of its sub-tasks are ticked. Offering a
        percentage box for one invited a 60% that would then count as not
        done, with nothing on the form saying so.
        """
        self.progress_done_var = None
        self.progress_entry = None

        if self.template.task_type == 'Subtask':
            self.progress_done_var = ctk.BooleanVar(
                value=self.template.is_completed)
            self.progress_check = ctk.CTkCheckBox(
                frame, text="", variable=self.progress_done_var)
            self._field(frame, "Completed:", self.progress_check,
                        sticky=tk.W)
            return

        self.progress_entry = ctk.CTkEntry(frame)
        self.progress_entry.insert(0, str(self.template.progress))
        self._field(frame, "Progress (%):", self.progress_entry)

        # Rolled up from the children of anything that has them
        if not self._should_show_progress():
            self.progress_entry.configure(state=tk.DISABLED)

    def _build_details(self, parent):
        """
        The notes panel, filling the column beside the fields.

        PARAMETERS:
        -----------
        parent : widget
            The two-column frame; this takes the right-hand one.
        """
        pane = ctk.CTkFrame(parent, fg_color='transparent')
        pane.grid(row=0, column=1, sticky=tk.NSEW, padx=(10, 0))
        pane.grid_rowconfigure(1, weight=1)
        pane.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(pane, text="Notes", anchor=tk.W).grid(
            row=0, column=0, sticky=tk.EW, pady=(0, 4))

        self.details_text = ctk.CTkTextbox(pane, wrap='word')
        self.details_text.grid(row=1, column=0, sticky=tk.NSEW)
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

        self._build_leading_buttons(frame)

        for label, command in (("Save & New", self.save_and_new),
                               ("Save & Close", self.save),
                               ("Close", self.cancel)):
            ctk.CTkButton(frame, text=label, width=self.ACTION_WIDTH,
                          command=command).pack(side=tk.RIGHT, padx=5)

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
        """
        if not self.end_date_entry:
            return
        milestone = self.is_milestone_var.get()
        self.end_date_entry.configure(
            state=tk.DISABLED if milestone else tk.NORMAL
        )
        if not milestone:
            self._touched.add('end_date')
        self._check_fields()



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
