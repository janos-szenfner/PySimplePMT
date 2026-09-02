"""
Startup settings and the Welcome/Project Selection modal.

Keeps the recent-projects list on disk and provides the launcher UI that
appears when the application starts without a file argument.
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

import customtkinter as ctk
import tkinter as tk

from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


#: Where the recent-projects JSON lives unless the caller overrides it.
DEFAULT_STORAGE_DIR = Path.home() / ".pysimplepmt"


class StartupSettings:
    """Load, save, and manage the list of recently opened project files."""

    def __init__(self, storage_dir: Optional[str] = None, max_recent: int = 5):
        self._max_recent = max_recent
        self.storage_dir = Path(storage_dir) if storage_dir else DEFAULT_STORAGE_DIR
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._path = self.storage_dir / "recent_projects.json"
        self._recent: List[dict] = []
        self.load()

    def load(self):
        """Read the stored recent list, or start empty if it is missing."""
        if not self._path.exists():
            logger.info("No recent-projects file found at %s", self._path)
            self._recent = []
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._recent = data.get("recent", [])
            logger.info("Loaded %d recent project(s) from %s", len(self._recent), self._path)
        except Exception:
            logger.exception("Failed to load recent projects from %s", self._path)
            self._recent = []

    def save(self):
        """Persist the current recent list."""
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump({"recent": self._recent}, f, indent=2)
            logger.info("Saved %d recent project(s) to %s", len(self._recent), self._path)
        except Exception:
            logger.exception("Failed to save recent projects to %s", self._path)

    @property
    def recent(self) -> List[dict]:
        """The recent entries as dicts with path, name, and last_modified."""
        return list(self._recent)

    def add(self, path: str, name: str, last_modified: Optional[str] = None):
        """Add or promote an entry and trim to the maximum length."""
        if last_modified is None:
            last_modified = datetime.now().isoformat()
        path = str(path)
        self._recent = [r for r in self._recent if r.get("path") != path]
        self._recent.insert(0, {
            "path": path,
            "name": name,
            "last_modified": last_modified,
        })
        if len(self._recent) > self._max_recent:
            self._recent = self._recent[: self._max_recent]
        logger.info("Added recent project %r (%s)", name, path)
        self.save()

    def remove(self, path: str):
        """Remove an entry by path."""
        path = str(path)
        self._recent = [r for r in self._recent if r.get("path") != path]
        logger.info("Removed recent project %r from the list", path)
        self.save()

    def clear(self):
        """Empty the recent list."""
        self._recent = []
        logger.info("Cleared the recent-projects list")
        self.save()


class WelcomeModal(ctk.CTkToplevel):
    """Modal launcher for new, sample, or recent projects."""

    def __init__(
        self,
        parent: ctk.CTk,
        recent_items: List[dict],
        on_select_callback: Callable[[str, Optional[str]], None],
    ):
        super().__init__(parent)
        self.title("Welcome to Gantt Project Manager")
        self.geometry("520x480")
        self.resizable(False, False)
        self.transient(parent)

        self.callback = on_select_callback
        self.recent_items = recent_items

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.create_widgets()

        logger.info(
            "Opened Welcome modal with %d recent project(s)", len(recent_items)
        )

        # Wait until the widget is laid out before taking exclusive focus
        self.after(10, self._take_grab)

    def create_widgets(self):
        """Build the welcome UI."""
        lbl_title = ctk.CTkLabel(
            self,
            text="Gantt Project Manager",
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        lbl_title.pack(pady=(20, 10))

        lbl_subtitle = ctk.CTkLabel(
            self,
            text="Select how you would like to start",
            text_color="gray",
        )
        lbl_subtitle.pack(pady=(0, 10))

        frame_actions = ctk.CTkFrame(self)
        frame_actions.pack(padx=20, pady=10, fill=tk.X)

        btn_new = ctk.CTkButton(
            frame_actions,
            text="+ New Empty Project",
            command=lambda: self._select("new"),
        )
        btn_new.pack(padx=10, pady=8, fill=tk.X)

        btn_sample = ctk.CTkButton(
            frame_actions,
            text="Open Built-in Sample Project",
            fg_color="#2b2b2b",
            hover_color="#3a3a3a",
            command=lambda: self._select("sample"),
        )
        btn_sample.pack(padx=10, pady=(0, 8), fill=tk.X)

        self.recent_section = ctk.CTkFrame(self)
        self.recent_section.pack(
            padx=20, pady=(10, 15), fill=tk.BOTH, expand=True
        )

        lbl_recent = ctk.CTkLabel(
            self.recent_section,
            text="Recent Projects:",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        lbl_recent.pack(anchor=tk.W, padx=14, pady=(12, 6))

        self.recent_divider = ctk.CTkFrame(
            self.recent_section, height=1, corner_radius=0,
            fg_color=("gray75", "gray40"),
        )
        self.recent_divider.pack(fill=tk.X, padx=14, pady=(0, 6))

        self.frame_recent = ctk.CTkScrollableFrame(
            self.recent_section, height=140, fg_color="transparent"
        )
        self.frame_recent.pack(
            padx=8, pady=(0, 8), fill=tk.BOTH, expand=True
        )

        self._build_recent_list()

    def _take_grab(self):
        """Take exclusive focus once the window is mapped, if possible."""
        try:
            self.grab_set()
        except tk.TclError:
            logger.debug("Could not grab focus for the Welcome modal")

    def _build_recent_list(self):
        """Populate the recent projects scrollable frame."""
        logger.debug("Building recent project list with %d item(s)", len(self.recent_items))
        for child in self.frame_recent.winfo_children():
            child.destroy()

        if not self.recent_items:
            lbl_empty = ctk.CTkLabel(
                self.frame_recent,
                text="No recent projects found.",
                text_color="gray",
            )
            lbl_empty.pack(pady=10)
            return

        self.recent_project_cards = []
        for entry in self.recent_items:
            path = entry.get("path", "")
            name = entry.get("name", "Unknown")
            last_mod = self._format_recent_timestamp(
                entry.get("last_modified", "")
            )

            card = ctk.CTkFrame(
                self.frame_recent,
                fg_color="transparent",
                corner_radius=6,
                cursor="hand2",
            )
            card.pack(fill=tk.X, padx=6, pady=5)
            card.grid_columnconfigure(0, weight=1)

            name_label = ctk.CTkLabel(
                card,
                text=name,
                anchor=tk.W,
                font=ctk.CTkFont(size=14, weight="bold"),
            )
            name_label.grid(row=0, column=0, sticky=tk.EW, padx=8)

            path_label = ctk.CTkLabel(
                card,
                text=path,
                anchor=tk.W,
                justify=tk.LEFT,
                wraplength=400,
                text_color=("gray40", "gray70"),
                font=ctk.CTkFont(size=11),
            )
            path_label.grid(row=1, column=0, sticky=tk.EW, padx=8, pady=(2, 0))

            timestamp_label = ctk.CTkLabel(
                card,
                text=last_mod,
                anchor=tk.E,
                text_color=("gray60", "gray60"),
                font=ctk.CTkFont(size=9),
            )
            timestamp_label.grid(
                row=2, column=0, sticky=tk.E, padx=8, pady=(0, 3)
            )

            for widget in (card, name_label, path_label, timestamp_label):
                widget.bind(
                    "<Button-1>",
                    lambda _event, p=path: self._select("recent", p),
                )
                widget.configure(cursor="hand2")

            self.recent_project_cards.append({
                "frame": card,
                "name": name_label,
                "path": path_label,
                "timestamp": timestamp_label,
            })
            logger.debug("Built recent project card for %r (%s)", name, path)

    def _format_recent_timestamp(self, value: str) -> str:
        """Format a stored ISO timestamp for the compact recent-project card."""
        if not value:
            return ""
        try:
            formatted = datetime.fromisoformat(value).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        except (TypeError, ValueError):
            formatted = str(value)
        logger.debug("Formatted recent-project timestamp %r as %r",
                     value, formatted)
        return formatted

    def _select(self, mode: str, payload: Optional[str] = None):
        """Return the user's choice and close the modal."""
        logger.info("Welcome modal selected mode=%r payload=%r", mode, payload)
        self.destroy()
        self.callback(mode, payload)

    def _on_close(self):
        """Close the launcher into a clean empty project workspace."""
        logger.info(
            "Welcome modal closed via window manager; starting empty project"
        )
        self.destroy()
        self.callback("new", None)
