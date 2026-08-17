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

from gantt_app.models import Task, Project, TASK_TYPES, TASK_TYPE_LABELS
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
    GEOMETRY = "680x680"
    MINSIZE = (680, 480)
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

        general = self.tabs.tab("General")
        scroller = ScrollFrame(general)
        main_frame = scroller.content
        main_frame.columnconfigure(1, weight=1)

        self._build_general(main_frame)
        scroller.pack(fill=tk.BOTH, expand=True, padx=5, pady=(5, 0))
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

        # Details group
        self._build_details(frame)

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

    def _build_duration(self, frame):
        """Show the duration. Only meaningful once dates exist."""

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
        """The milestone tick box."""
        self.is_milestone_var = ctk.BooleanVar(
            value=self.template.is_milestone)
        self.milestone_check = ctk.CTkCheckBox(
            frame, text="", variable=self.is_milestone_var,
            command=self.toggle_milestone,
        )
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
        """Handle changes to the scheduling mode dropdown."""
        self._update_field_states()

    def _update_field_states(self):
        """
        Enable/disable fields based on the selected scheduling mode.
        
        Scheduling modes:
        - Start date is calculated: End date and Duration editable, Begin date disabled
        - End date is calculated: Begin date and Duration editable, End date disabled
        - Duration is calculated: Begin date and End date editable, Duration disabled
        """
        mode = self.scheduling_options_var.get()
        
        # Ensure all date widgets exist
        if not hasattr(self, 'start_date_entry') or self.start_date_entry is None:
            return
        if not hasattr(self, 'end_date_entry') or self.end_date_entry is None:
            return
        if not hasattr(self, 'duration_entry') or self.duration_entry is None:
            return
        
        # Reset all to normal state first
        self.start_date_entry.configure(state=tk.NORMAL)
        if self.end_date_entry:
            self.end_date_entry.configure(state=tk.NORMAL)
        self.duration_entry.configure(state=tk.NORMAL)
        
        # Apply mode-specific disablement
        if mode == "Start date is calculated":
            # Begin date is calculated: disable start date
            self.start_date_entry.configure(state=tk.DISABLED)
        elif mode == "End date is calculated":
            # End date is calculated: disable end date
            if self.end_date_entry:
                self.end_date_entry.configure(state=tk.DISABLED)
        elif mode == "Duration is calculated":
            # Duration is calculated: disable duration
            self.duration_entry.configure(state=tk.DISABLED)

    def _build_duration(self, frame):
        """The duration entry field."""
        # Check if duration should be editable for this task type
        duration_editable = self._should_show_duration()
        
        duration = self.template.duration
        if duration is None:
            # Calculate from dates if not manually set
            duration = self.template.duration_days
        self.duration_entry = ctk.CTkEntry(frame)
        if duration is not None:
            self.duration_entry.insert(0, str(duration))
        self._field(frame, "Duration:", self.duration_entry)
        
        # Disable duration for milestones and containers
        if not duration_editable:
            self.duration_entry.configure(state=tk.DISABLED)

    def _build_earliest_begin(self, frame):
        """The earliest begin date with checkbox and copy button."""
        self.earliest_begin_var = ctk.BooleanVar(value=False)
        self.earliest_begin_check = ctk.CTkCheckBox(
            frame, text="", variable=self.earliest_begin_var
        )
        self.earliest_begin_entry = DateEntry(
            frame, date=self.template.earliest_begin)
        
        # Create a frame to hold the checkbox, date entry, and button
        sub_frame = ctk.CTkFrame(frame)
        self.earliest_begin_check.pack(side=tk.LEFT, padx=0)
        self.earliest_begin_entry.pack(side=tk.LEFT, padx=5)
        
        copy_btn = ctk.CTkButton(
            sub_frame, text="Copy begin date", width=100,
            command=self._copy_begin_date
        )
        copy_btn.pack(side=tk.LEFT, padx=5)
        
        row = self._next_row()
        ctk.CTkLabel(frame, text="Earliest begin").grid(
            row=row, column=0, sticky=tk.W, pady=5)
        sub_frame.grid(row=row, column=1, sticky=tk.EW, pady=5)

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
        """The progress entry field (0-100)."""
        # Check if progress should be editable for this task type
        progress_editable = self._should_show_progress()
        
        progress = self.template.progress
        self.progress_entry = ctk.CTkEntry(frame)
        self.progress_entry.insert(0, str(progress))
        self._field(frame, "Progress:", self.progress_entry)
        
        # Disable progress for containers (rolled up from children)
        if not progress_editable:
            self.progress_entry.configure(state=tk.DISABLED)

    def _build_details(self, frame):
        """The details text area."""
        self.details_text = ctk.CTkTextbox(frame, height=80, width=400)
        if self.template.details:
            self.details_text.insert("1.0", self.template.details)
        # Span across both columns
        row = self._next_row()
        ctk.CTkLabel(frame, text="Details:").grid(
            row=row, column=0, sticky=tk.NW, pady=5)
        self.details_text.grid(row=row, column=1, sticky=tk.EW, pady=5)
        frame.columnconfigure(1, weight=1)

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
