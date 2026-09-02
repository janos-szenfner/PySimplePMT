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

        lbl_recent = ctk.CTkLabel(
            self,
            text="Recent Projects:",
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        lbl_recent.pack(anchor=tk.W, padx=25, pady=(10, 2))

        self.frame_recent = ctk.CTkScrollableFrame(self, height=140)
        self.frame_recent.pack(padx=20, pady=(0, 15), fill=tk.BOTH, expand=True)

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

        for entry in self.recent_items:
            path = entry.get("path", "")
            name = entry.get("name", "Unknown")
            last_mod = entry.get("last_modified", "")

            container = ctk.CTkFrame(self.frame_recent, fg_color="transparent")
            container.pack(fill=tk.X, pady=2)

            text = f"{name}\n{path}\n{last_mod}"
            btn = ctk.CTkButton(
                container,
                text=text,
                anchor=tk.W,
                fg_color="transparent",
                text_color=("gray10", "gray90"),
                hover_color=("gray70", "gray30"),
                command=lambda p=path: self._select("recent", p),
            )
            btn.pack(fill=tk.X)

    def _select(self, mode: str, payload: Optional[str] = None):
        """Return the user's choice and close the modal."""
        logger.info("Welcome modal selected mode=%r payload=%r", mode, payload)
        self.destroy()
        self.callback(mode, payload)

    def _on_close(self):
        """If the user closes the launcher with the X, treat it as cancel."""
        logger.info("Welcome modal closed via window manager; treating as cancel")
        self.destroy()
        self.callback("cancel", None)
