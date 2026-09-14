"""Unified, tabbed launcher for the application's settings editors."""
import tkinter as tk
from tkinter import colorchooser, ttk
from typing import Callable, Dict, Optional

import customtkinter as ctk

from gantt_app import theme
from gantt_app.baselines import BaselineManager
from gantt_app.models import GRID_DATA_COLUMNS, order_grid_columns
from gantt_app.utils.log import get_logger
from gantt_app.views.modal import grab_when_visible

logger = get_logger(__name__)


class SettingsWindow(ctk.CTkToplevel):
    """Modern four-tab hub that preserves the existing settings editors."""

    GEOMETRY = "800x600"
    TABS = ("Project", "Resource", "Calendar", "Presets", "Baseline",
            "Task Grid", "System UI")

    #: The title the task grid gives each hideable column; keyed by the
    #: column name the tree knows it by, which is what the hidden list
    #: stores.
    GRID_COLUMN_TITLES = {
        'Alert': 'Alert', 'Label': 'Label', 'Type': 'Type', 'Status': 'Status',
        'Duration': 'Duration (Days)', 'Start': 'Start Date',
        'End': 'End Date', 'Progress': 'Progress',
        'Dependencies': 'Dependencies', 'Milestone': 'Milestone',
        'Outline': 'Outline Level', 'Baseline Start': 'Baseline Start',
        'Start Variance': 'Start Var', 'Baseline Finish': 'Baseline Finish',
        'Finish Variance': 'Finish Var',
        'Baseline Duration': 'Base Duration',
        'Duration Variance': 'Dur Var', 'Baseline Work': 'Base Work',
        'Work Variance': 'Work Var', 'Baseline Cost': 'Base Cost',
        'Cost Variance': 'Cost Var', 'Task Calendar': 'Task Calendar',
    }

    def __init__(
        self,
        master,
        project,
        open_project: Callable[[], None],
        open_resource: Callable[[], None],
        open_calendar: Callable[[], None],
        baseline_manager: Optional[BaselineManager] = None,
        initial_tab: str = "Project",
        on_baseline_changed: Optional[Callable[[], None]] = None,
        theme_controller=None,
        task_list=None,
        **kwargs,
    ):
        super().__init__(master, **kwargs)
        self.project = project
        self.baseline_manager = baseline_manager
        self.on_baseline_changed = on_baseline_changed
        self.theme_controller = theme_controller
        self.task_list = task_list
        self._openers: Dict[str, Callable[[], None]] = {
            "Project": open_project,
            "Resource": open_resource,
            "Calendar": open_calendar,
        }

        self.title("Settings")
        self.geometry(self.GEOMETRY)
        self.minsize(680, 500)
        self.transient(master.winfo_toplevel())
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", lambda _event: self.close())

        self._build()
        if initial_tab in self.TABS:
            self.tabview.set(initial_tab)
        grab_when_visible(self)
        logger.info("Opened Settings window on the %s tab", self.tabview.get())

    def _build(self):
        """Build the heading, four-tab body, and footer."""
        logger.debug("Building unified Settings window")
        heading = ctk.CTkFrame(self, fg_color="transparent")
        heading.pack(fill=tk.X, padx=20, pady=(18, 6))
        ctk.CTkLabel(
            heading,
            text="Settings",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(anchor=tk.W)
        ctk.CTkLabel(
            heading,
            text="Configure the project, resources, calendars, baselines "
                 "and appearance.",
            text_color=theme.MUTED_TEXT,
        ).pack(anchor=tk.W, pady=(2, 0))

        self.tabview = ctk.CTkTabview(self, command=self._tab_changed)
        self.tabview.pack(padx=20, pady=10, fill=tk.BOTH, expand=True)
        self.tabs = {name: self.tabview.add(name) for name in self.TABS}

        self._build_project_tab()
        self._build_resource_tab()
        self._build_calendar_tab()
        self._build_presets_tab()
        self._build_baseline_tab()
        self._build_task_grid_tab()
        self._build_system_ui_tab()

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill=tk.X, padx=20, pady=(0, 18))
        ctk.CTkButton(
            footer, text="Close", width=100, command=self.close
        ).pack(side=tk.RIGHT)

    def _tab_changed(self):
        """Log navigation between settings categories."""
        logger.info("Settings tab changed to %s", self.tabview.get())

    def _card(self, tab_name: str, title: str, description: str,
              details, button_text: str):
        """Build one consistent settings-category card."""
        logger.debug("Building %s settings tab", tab_name)
        frame = ctk.CTkScrollableFrame(self.tabs[tab_name])
        frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        card = ctk.CTkFrame(frame, corner_radius=12)
        card.pack(fill=tk.X, padx=14, pady=14)
        ctk.CTkLabel(
            card,
            text=title,
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(anchor=tk.W, padx=20, pady=(20, 6))
        ctk.CTkLabel(
            card,
            text=description,
            justify=tk.LEFT,
            anchor=tk.W,
            wraplength=650,
            text_color=theme.MUTED_TEXT,
        ).pack(fill=tk.X, padx=20, pady=(0, 16))

        for label, value in details:
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill=tk.X, padx=20, pady=3)
            ctk.CTkLabel(row, text=label, width=170, anchor=tk.W).pack(
                side=tk.LEFT
            )
            ctk.CTkLabel(
                row, text=str(value), anchor=tk.W,
                font=ctk.CTkFont(weight="bold"),
            ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        ctk.CTkButton(
            card,
            text=button_text,
            height=38,
            command=lambda: self.open_editor(tab_name),
        ).pack(fill=tk.X, padx=20, pady=(20, 20))

    def _build_project_tab(self):
        """Build the Project settings overview."""
        direction = (
            "Project finish date"
            if self.project.schedule_from == "finish"
            else "Project start date"
        )
        self._card(
            "Project",
            "Project Settings",
            "Edit the project title, scheduling direction, dates, default "
            "calendar, status date, and priority.",
            (
                ("Project name", self.project.name or "New Project"),
                ("Schedule from", direction),
                ("Priority", self.project.priority),
            ),
            "Open Project Settings",
        )

    def _build_resource_tab(self):
        """Build the Resource settings overview."""
        repository = self.project.resource_repository
        self._card(
            "Resource",
            "Resource Settings",
            "Manage named resources, generic placeholders, team pools, "
            "availability, capacity, schedules, and team allocations.",
            (
                ("Resources", len(repository.resources)),
                ("Teams", len(repository.teams)),
                ("Active project", self.project.name or "New Project"),
            ),
            "Open Resource Settings",
        )

    def _build_calendar_tab(self):
        """Build the Calendar settings overview."""
        calendar = self.project.calendar
        self._card(
            "Calendar",
            "Calendar Settings",
            "Configure the working week, public-holiday countries, manual "
            "date overrides, and named task calendars.",
            (
                ("Working days", 7 - len(calendar.non_working_days)),
                ("Holiday countries", len(calendar.countries)),
                ("Named calendars", len(self.project.calendars)),
            ),
            "Open Calendar Settings",
        )

    def _build_presets_tab(self):
        """
        Build the style-presets manager inside its tab.

        Hosted in the tab directly rather than behind an Open button like the
        other four: the built-ins and the reader's own customs are edited in
        place, and the grid is the whole of it. See views/presetsettings.py.
        """
        from gantt_app.presets import default_manager
        from gantt_app.views.presetsettings import StylePresetsTab

        StylePresetsTab(self.tabs["Presets"], default_manager()).pack(
            fill=tk.BOTH, expand=True, padx=10, pady=10)

    def _build_baseline_tab(self):
        """Build the baseline slot manager tab."""
        tab = self.tabs["Baseline"]
        # Rebuilt in place when a slot's data is cleared, so clear what is
        # there first rather than stacking a second copy on top.
        for child in tab.winfo_children():
            child.destroy()

        # Save sits in a fixed footer so it is always in view without
        # scrolling to the foot of ten slots, with the status message beside
        # it on the right rather than stacked above it.
        self._baseline_footer = ctk.CTkFrame(tab, fg_color="transparent")
        self._baseline_footer.pack(side=tk.BOTTOM, fill=tk.X,
                                   padx=20, pady=(4, 12))
        self._baseline_save_button = ctk.CTkButton(
            self._baseline_footer, text="Save Settings", width=120,
            command=self._save_baseline_settings,
        )
        self._baseline_save_button.pack(side=tk.LEFT)
        self._baseline_error = ctk.CTkLabel(
            self._baseline_footer, text="", text_color=theme.NEGATIVE_TEXT)
        self._baseline_error.pack(side=tk.LEFT, padx=(12, 0))

        scroll = ctk.CTkScrollableFrame(tab)
        scroll.pack(side=tk.TOP, fill=tk.BOTH, expand=True,
                    padx=10, pady=(10, 0))
        scroll.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            scroll,
            text="Baseline slots",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, columnspan=4, sticky=tk.W, pady=(0, 10))

        self._baseline_entries: Dict[int, ctk.CTkEntry] = {}
        self._baseline_color_vars: Dict[int, str] = {}
        self._baseline_color_buttons: Dict[int, ctk.CTkButton] = {}
        if self.baseline_manager is None:
            ctk.CTkLabel(scroll, text="No baseline manager found.",
                         text_color=theme.MUTED_TEXT).grid(
                             row=1, column=0, sticky=tk.W)
            return

        for i, slot in enumerate(self.baseline_manager.slots, start=1):
            ctk.CTkLabel(scroll, text=f"{slot.number:02d}", width=40).grid(
                row=i, column=0, sticky=tk.W, padx=(0, 8))
            entry = ctk.CTkEntry(scroll)
            entry.insert(0, slot.display_name)
            entry.grid(row=i, column=1, sticky=tk.EW, padx=(0, 8))
            self._baseline_entries[slot.number] = entry
            status = ctk.CTkLabel(scroll, text=slot.status_label(),
                                  text_color=theme.MUTED_TEXT)
            status.grid(row=i, column=2, sticky=tk.W, padx=(0, 8))
            color_button = ctk.CTkButton(
                scroll, text="Color", width=60,
                fg_color=slot.effective_color,
                text_color="white" if slot.effective_color == "#000000" else "black",
                command=lambda n=slot.number: self._pick_baseline_color(n),
            )
            color_button.grid(row=i, column=3, sticky=tk.W, padx=(0, 8))
            self._baseline_color_vars[slot.number] = slot.color
            self._baseline_color_buttons[slot.number] = color_button
            ctk.CTkButton(
                scroll, text="Clear Data", width=80,
                command=lambda n=slot.number: self._clear_baseline_data(n),
            ).grid(row=i, column=4, sticky=tk.W)

    def _pick_baseline_color(self, number: int):
        current = self._baseline_color_vars.get(number, "")
        result = colorchooser.askcolor(color=current or None,
                                       title=f"Choose color for Baseline {number}")
        if result is None or result[1] is None:
            return
        self._baseline_color_vars[number] = result[1]
        button = self._baseline_color_buttons.get(number)
        if button is not None:
            button.configure(fg_color=result[1])
        logger.info("Selected color %s for baseline %d", result[1], number)

    def _save_baseline_settings(self):
        if self.baseline_manager is None:
            return
        names = []
        for number, entry in self._baseline_entries.items():
            name = entry.get().strip()
            if not name:
                name = f"Baseline {number}"
            if name in names:
                self._baseline_error.configure(
                    text=f"Duplicate display name: {name}")
                return
            names.append(name)
        for number, entry in self._baseline_entries.items():
            self.baseline_manager.rename_slot(number, entry.get().strip())
            self.baseline_manager.set_slot_color(
                number, self._baseline_color_vars.get(number, ""))
        self._baseline_error.configure(text="Settings saved.",
                                       text_color=theme.POSITIVE_TEXT)
        logger.info("Saved baseline slot names and colors")
        if self.on_baseline_changed:
            self.on_baseline_changed()

    def _clear_baseline_data(self, number: int):
        if self.baseline_manager is None:
            return
        self.baseline_manager.clear_baseline(number)
        self._build_baseline_tab()
        logger.info("Cleared data for baseline %d from settings", number)

    def _build_task_grid_tab(self):
        """
        Which columns the task grid shows.

        A two-column grid of its own, styled like the task list's: the
        column's name on the left and its visibility on the right, where
        a click opens a Viewable/Hidden dropdown over the cell - the same
        in-place editing the task grid uses for its own cells. Task Name
        is not in the list: it carries the outline's expander, so it can
        never leave. Save writes the hidden set onto the project, which is
        what makes it part of the file.
        """
        logger.debug("Building Task Grid settings tab")
        tab = self.tabs["Task Grid"]

        # Save sits in a fixed footer, like the baseline tab's, so it is
        # always in view however many columns the list grows to.
        footer = ctk.CTkFrame(tab, fg_color="transparent")
        footer.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=(4, 12))
        ctk.CTkButton(
            footer, text="Save", width=100,
            command=self._save_grid_columns,
        ).pack(side=tk.LEFT)
        ctk.CTkButton(
            footer, text="Reset Task List Layout", width=170,
            command=self._reset_grid_layout,
        ).pack(side=tk.RIGHT)
        ctk.CTkButton(
            footer, text="Reset Task List Visibility", width=185,
            command=self._reset_grid_visibility,
        ).pack(side=tk.RIGHT, padx=(0, 8))
        self._grid_columns_status = ctk.CTkLabel(footer, text="")
        self._grid_columns_status.pack(side=tk.LEFT, padx=(12, 0))

        ctk.CTkLabel(
            tab,
            text="Choose which columns the task grid shows. Click a "
                 "visibility cell for the dropdown.",
            anchor=tk.W, wraplength=650, text_color=theme.MUTED_TEXT,
        ).pack(fill=tk.X, padx=20, pady=(14, 6))

        grid_frame = ctk.CTkFrame(tab)
        grid_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 10))
        grid_frame.grid_rowconfigure(0, weight=1)
        grid_frame.grid_columnconfigure(0, weight=1)

        # 'tree headings' like the task grid itself: the column's name
        # sits in the tree column, the dropdown in the one beside it.
        self._grid_columns_tree = ttk.Treeview(
            grid_frame, columns=('visibility',), show='tree headings',
            style='Gantt.Treeview', selectmode='browse')
        self._grid_columns_tree.heading('#0', text='Column')
        self._grid_columns_tree.heading('visibility', text='Visibility')
        self._grid_columns_tree.column('#0', width=280, minwidth=140,
                                       stretch=False, anchor=tk.W)
        self._grid_columns_tree.column('visibility', width=140,
                                       minwidth=90, stretch=False,
                                       anchor=tk.W)

        scrollbar = ttk.Scrollbar(grid_frame, orient=tk.VERTICAL,
                                  command=self._grid_columns_tree.yview)
        theme.style_scrollbar(scrollbar)
        self._grid_columns_tree.configure(yscrollcommand=scrollbar.set)
        self._grid_columns_tree.grid(row=0, column=0, sticky=tk.NSEW)
        scrollbar.grid(row=0, column=1, sticky=tk.NS)

        hidden = set(self.project.hidden_grid_columns)
        for column in self._grid_column_names():
            self._grid_columns_tree.insert(
                '', tk.END, iid=column,
                text=self.GRID_COLUMN_TITLES.get(column, column),
                values=('Hidden' if column in hidden else 'Viewable',))

        self._grid_columns_tree.bind(
            '<Button-1>', self._grid_columns_click)
        self._grid_columns_editor = None

    def _grid_column_names(self):
        """
        The hideable columns, in the order the task grid shows them.

        Asked of the task list when there is one so the two cannot drift -
        and so a rearranged layout lists its columns where they stand;
        the settings window can also be built without one in tests, where
        the fallback list is the same set in the factory order.
        """
        if self.task_list is not None:
            return self.task_list.column_order()
        return list(GRID_DATA_COLUMNS)

    def _grid_columns_click(self, event):
        """Open the Viewable/Hidden dropdown over the cell that was hit."""
        tree = self._grid_columns_tree
        row = tree.identify_row(event.y)
        if not row or tree.identify_column(event.x) != '#1':
            self._close_grid_columns_editor()
            return
        box = tree.bbox(row, '#1')
        if not box:
            return
        x, y, width, height = box
        self._close_grid_columns_editor()

        combo = ttk.Combobox(tree, values=('Viewable', 'Hidden'),
                             state='readonly')
        combo.set(tree.item(row, 'values')[0])
        combo.place(x=x, y=y, width=width, height=height)
        combo.focus_set()

        def commit(_event=None):
            tree.item(row, values=(combo.get(),))
            self._close_grid_columns_editor()

        combo.bind('<<ComboboxSelected>>', commit)
        combo.bind('<Return>', commit)
        combo.bind('<KP_Enter>', commit)
        # Not a plain commit-on-FocusOut: opening the list moves focus into
        # the list's own popup window, and committing there would store the
        # value and shut the dropdown the instant it opened - which is what
        # made the cell look like it could not be changed.
        combo.bind('<FocusOut>',
                   lambda _e: self._grid_editor_focus_left(combo))
        combo.bind('<Escape>', lambda _e: self._close_grid_columns_editor())
        self._grid_columns_editor = combo
        # Open the list straight away; a second click on the box would do
        # it, but the cell already said what the click meant.
        self.after_idle(lambda: self._open_grid_editor_list(combo))

    def _grid_editor_focus_left(self, combo):
        """
        Close the visibility dropdown once focus has really left it.

        Checked after the event settles: at the moment FocusOut fires the
        focus may be in transit to the dropdown's popup or landing back on
        the field. Only a focus that ended up outside both - a click on
        another row or off the field - closes the editor without a pick.
        """
        def settle():
            if self._grid_columns_editor is not combo:
                return
            try:
                if not combo.winfo_exists():
                    return
                focused = str(combo.tk.call('focus', '-displayof', combo))
                popdown = str(combo.tk.call(
                    'ttk::combobox::PopdownWindow', combo))
            except tk.TclError:
                return
            path = str(combo)
            if focused and (focused == path
                            or focused.startswith(path + '.')
                            or (popdown and focused.startswith(popdown))):
                return
            self._close_grid_columns_editor()

        try:
            combo.after_idle(settle)
        except tk.TclError:
            pass

    def _open_grid_editor_list(self, combo):
        """Post the dropdown's list, if the editor is still there to open."""
        try:
            if combo.winfo_exists():
                combo.event_generate('<Button-1>')
        except tk.TclError:
            pass

    def _close_grid_columns_editor(self):
        """Take the dropdown off the cell again."""
        if self._grid_columns_editor is not None:
            self._grid_columns_editor.destroy()
            self._grid_columns_editor = None

    def _save_grid_columns(self):
        """Write the Hidden rows onto the plan and repaint the grid."""
        tree = self._grid_columns_tree
        hidden = [
            row for row in tree.get_children()
            if tree.item(row, 'values')[0] == 'Hidden'
        ]
        self.project.hidden_grid_columns = hidden
        # Hidden columns always trail the layout: one nobody can see has
        # no place among the ones they can, and one that comes back lands
        # at the end rather than wherever it once stood. The stored order
        # is rewritten - it already has the old hidden set at the tail.
        order = list(self.project.grid_column_order or GRID_DATA_COLUMNS)
        self.project.grid_column_order = order_grid_columns(order, hidden)
        self._grid_columns_status.configure(
            text="Settings saved.", text_color=theme.POSITIVE_TEXT)
        logger.info("Saved hidden task-grid columns: %s",
                    self.project.hidden_grid_columns)

        if self.task_list is not None:
            self.task_list.apply_column_visibility()
        # The choice lives in the project file, so saving it is a change
        # the unsaved-work guard has to know about. The guard is the main
        # window's - self is itself a toplevel, so winfo_toplevel would
        # only find this window again.
        mark_dirty = getattr(self.master, 'mark_dirty', None)
        if mark_dirty is not None:
            mark_dirty()

    def _reset_grid_layout(self):
        """Put the grid's columns back in their factory order."""
        if self.task_list is not None:
            # reset_column_order writes the plan, repaints and marks it
            self.task_list.reset_column_order()
        else:
            self.project.grid_column_order = order_grid_columns(
                list(GRID_DATA_COLUMNS), self.project.hidden_grid_columns)
            mark_dirty = getattr(self.master, 'mark_dirty', None)
            if mark_dirty is not None:
                mark_dirty()
        self._grid_columns_status.configure(
            text="Layout reset.", text_color=theme.POSITIVE_TEXT)
        logger.info("Task-grid layout reset from Settings")

    def _reset_grid_visibility(self):
        """
        Put the visibility choices back to the application's default.

        The default is what a brand-new plan opens with: Label hidden, the
        rest shown - the same default from_dict gives a file that predates
        the setting. It is written straight through, the way the layout
        reset is: the plan, the grid, the rows in this tab and the
        unsaved-work guard all change together rather than waiting for
        Save to be pressed.
        """
        default_hidden = ['Label']
        self.project.hidden_grid_columns = list(default_hidden)
        # Hidden columns trail the layout, so the restored default puts
        # Label back at the end and returns anything else to the visible
        # run in the order it stood.
        order = list(self.project.grid_column_order or GRID_DATA_COLUMNS)
        self.project.grid_column_order = order_grid_columns(
            order, default_hidden)

        for row in self._grid_columns_tree.get_children():
            self._grid_columns_tree.item(
                row, values=('Hidden' if row in default_hidden
                             else 'Viewable',))

        if self.task_list is not None:
            self.task_list.apply_column_visibility()
        mark_dirty = getattr(self.master, 'mark_dirty', None)
        if mark_dirty is not None:
            mark_dirty()
        self._grid_columns_status.configure(
            text="Visibility reset.", text_color=theme.POSITIVE_TEXT)
        logger.info("Task-grid column visibility reset from Settings")

    def _build_system_ui_tab(self):
        """
        The appearance controls, moved here from the View menu.

        The old View > System UI mode submenu (Sync with system / Always Day /
        Always Night) becomes a day-or-night toggle and a Sync with System
        button, wired to the same ThemeController, so the workflow is the same
        while the controls live under Project Settings.
        """
        logger.debug("Building System UI settings tab")
        self._suppress_theme_switch = False

        frame = ctk.CTkScrollableFrame(self.tabs["System UI"])
        frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        card = ctk.CTkFrame(frame, corner_radius=12)
        card.pack(fill=tk.X, padx=14, pady=14)
        ctk.CTkLabel(
            card, text="System UI", font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(anchor=tk.W, padx=20, pady=(20, 6))
        ctk.CTkLabel(
            card,
            text="Choose day or night, or hand the choice back to the "
                 "system so the application follows the desktop's own "
                 "light and dark setting.",
            justify=tk.LEFT, anchor=tk.W, wraplength=650,
            text_color=theme.MUTED_TEXT,
        ).pack(fill=tk.X, padx=20, pady=(0, 16))

        toggle_row = ctk.CTkFrame(card, fg_color="transparent")
        toggle_row.pack(fill=tk.X, padx=20, pady=6)
        ctk.CTkLabel(toggle_row, text="Night mode", width=170,
                     anchor=tk.W).pack(side=tk.LEFT)
        self._theme_switch = ctk.CTkSwitch(
            toggle_row, text="", command=self._on_theme_switch)
        self._theme_switch.pack(side=tk.LEFT)

        self._sync_button = ctk.CTkButton(
            card, text="Sync with System", height=38,
            command=self._on_sync_system)
        self._sync_button.pack(fill=tk.X, padx=20, pady=(16, 6))

        self._theme_status = ctk.CTkLabel(
            card, text="", anchor=tk.W, text_color=theme.MUTED_TEXT)
        self._theme_status.pack(fill=tk.X, padx=20, pady=(0, 20))

        self._refresh_system_ui()
        if self.theme_controller is not None:
            # Owner-scoped, so it is dropped when this window is destroyed.
            self.theme_controller.subscribe(
                lambda _mode, _appearance: self._refresh_system_ui(),
                owner=self._theme_switch)

    def _refresh_system_ui(self):
        """Reflect the controller's current mode in the toggle and status."""
        controller = self.theme_controller
        switch = getattr(self, "_theme_switch", None)
        if switch is None:
            return
        try:
            if controller is None:
                switch.configure(state=tk.DISABLED)
                self._sync_button.configure(state=tk.DISABLED)
                self._theme_status.configure(
                    text="Theme control is not available here.")
                return

            self._suppress_theme_switch = True
            if controller.is_dark:
                switch.select()
            else:
                switch.deselect()
            self._suppress_theme_switch = False

            if controller.following_system:
                self._theme_status.configure(
                    text=f"Following the system ({controller.appearance}).")
            else:
                self._theme_status.configure(
                    text=f"Manual ({controller.appearance}).")
        except tk.TclError:
            pass

    def _on_theme_switch(self):
        """Toggle takes manual control: on is night, off is day."""
        if self._suppress_theme_switch or self.theme_controller is None:
            return
        wanted = theme.MODE_DARK if self._theme_switch.get() else theme.MODE_LIGHT
        logger.info("System UI toggle set to %s", wanted)
        self.theme_controller.set_mode(wanted)
        self._refresh_system_ui()

    def _on_sync_system(self):
        """Hand the choice back to the desktop."""
        if self.theme_controller is None:
            return
        logger.info("System UI set to follow the system")
        self.theme_controller.sync_with_system()
        self._refresh_system_ui()

    def open_editor(self, tab_name: str):
        """Close the hub and open the selected existing settings editor."""
        opener: Optional[Callable] = self._openers.get(tab_name)
        if opener is None:
            logger.error("No settings editor is registered for %s", tab_name)
            return
        logger.info("Opening %s settings editor from unified Settings", tab_name)
        self.destroy()
        opener()

    def close(self):
        """Close the unified Settings window without changing settings."""
        logger.info("Closed unified Settings window")
        self.destroy()
