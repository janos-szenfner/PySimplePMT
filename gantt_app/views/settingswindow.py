"""Unified, tabbed launcher for the application's settings editors."""
import tkinter as tk
from tkinter import colorchooser
from typing import Callable, Dict, Optional

import customtkinter as ctk

from gantt_app import theme
from gantt_app.baselines import BaselineManager
from gantt_app.utils.log import get_logger
from gantt_app.views.modal import grab_when_visible

logger = get_logger(__name__)


class SettingsWindow(ctk.CTkToplevel):
    """Modern four-tab hub that preserves the existing settings editors."""

    GEOMETRY = "800x600"
    TABS = ("Project", "Resource", "Gantt", "Calendar", "Presets", "Baseline")

    def __init__(
        self,
        master,
        project,
        open_project: Callable[[], None],
        open_resource: Callable[[], None],
        open_gantt: Callable[[], None],
        open_calendar: Callable[[], None],
        baseline_manager: Optional[BaselineManager] = None,
        initial_tab: str = "Project",
        on_baseline_changed: Optional[Callable[[], None]] = None,
        **kwargs,
    ):
        super().__init__(master, **kwargs)
        self.project = project
        self.baseline_manager = baseline_manager
        self.on_baseline_changed = on_baseline_changed
        self._openers: Dict[str, Callable[[], None]] = {
            "Project": open_project,
            "Resource": open_resource,
            "Gantt": open_gantt,
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
            text="Configure the project, resources, chart, calendars and baselines.",
            text_color=theme.MUTED_TEXT,
        ).pack(anchor=tk.W, pady=(2, 0))

        self.tabview = ctk.CTkTabview(self, command=self._tab_changed)
        self.tabview.pack(padx=20, pady=10, fill=tk.BOTH, expand=True)
        self.tabs = {name: self.tabview.add(name) for name in self.TABS}

        self._build_project_tab()
        self._build_resource_tab()
        self._build_gantt_tab()
        self._build_calendar_tab()
        self._build_presets_tab()
        self._build_baseline_tab()

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

    def _build_gantt_tab(self):
        """Build the Gantt settings overview."""
        self._card(
            "Gantt",
            "Gantt Chart Settings",
            "Configure chart fonts, theme, task and milestone colours, "
            "dependency lines, background, and grid appearance.",
            (
                ("Chart", "Current project Gantt chart"),
                ("Appearance", "Uses the active application theme"),
            ),
            "Open Gantt Settings",
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
