"""Unified, tabbed launcher for the application's settings editors."""
import tkinter as tk
from typing import Callable, Dict, Optional

import customtkinter as ctk

from gantt_app import theme
from gantt_app.utils.log import get_logger
from gantt_app.views.modal import grab_when_visible

logger = get_logger(__name__)


class SettingsWindow(ctk.CTkToplevel):
    """Modern four-tab hub that preserves the existing settings editors."""

    GEOMETRY = "800x600"
    TABS = ("Project", "Resource", "Gantt", "Calendar")

    def __init__(
        self,
        master,
        project,
        open_project: Callable[[], None],
        open_resource: Callable[[], None],
        open_gantt: Callable[[], None],
        open_calendar: Callable[[], None],
        initial_tab: str = "Project",
        **kwargs,
    ):
        super().__init__(master, **kwargs)
        self.project = project
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
            text="Configure the project, resources, chart, and calendars.",
            text_color=theme.MUTED_TEXT,
        ).pack(anchor=tk.W, pady=(2, 0))

        self.tabview = ctk.CTkTabview(self, command=self._tab_changed)
        self.tabview.pack(padx=20, pady=10, fill=tk.BOTH, expand=True)
        self.tabs = {name: self.tabview.add(name) for name in self.TABS}

        self._build_project_tab()
        self._build_resource_tab()
        self._build_gantt_tab()
        self._build_calendar_tab()

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
