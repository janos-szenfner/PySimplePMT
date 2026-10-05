"""Dialogs for setting and clearing project schedule baselines."""
import tkinter as tk
from typing import Callable, Optional

import customtkinter as ctk

from gantt_app.core.baselines import BaselineManager
from gantt_app.core.models import Project
from gantt_app.utils.log import get_logger
from gantt_app.views import dialogs as messagebox
from gantt_app.views.modal import grab_when_visible

logger = get_logger(__name__)


class _BaselineDialogBase(ctk.CTkToplevel):
    """Common layout and behaviour for the Set and Clear baseline dialogs."""

    def __init__(self, master, title: str):
        super().__init__(master)
        self.title(title)
        self.geometry("420x280")
        self.resizable(False, False)
        self.transient(master.winfo_toplevel())
        self.result: Optional[int] = None
        self._build()
        grab_when_visible(self)

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._body = ctk.CTkFrame(self, fg_color="transparent")
        self._body.grid(row=0, column=0, sticky=tk.NSEW, padx=20, pady=20)
        self._body.grid_columnconfigure(0, weight=1)

        self._button_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._button_frame.grid(row=1, column=0, sticky=tk.EW, padx=20, pady=(0, 15))
        self._button_frame.grid_columnconfigure(0, weight=1)

        self._ok = ctk.CTkButton(
            self._button_frame, text="OK", width=80, command=self._on_ok)
        self._ok.grid(row=0, column=0, sticky=tk.E, padx=(0, 5))
        ctk.CTkButton(
            self._button_frame, text="Cancel", width=80, command=self.destroy
        ).grid(row=0, column=1, sticky=tk.E)

    def _on_ok(self):
        raise NotImplementedError


class BaselineSetDialog(_BaselineDialogBase):
    """
    Modal dialog for capturing a baseline of the whole project.

    MS Project's Scope section - entire project or selected tasks only -
    is not offered: the app captures the entire project, every time
    (issue #84, following #19). The roll-up option still applies to the
    whole plan, so it stays.
    """

    def __init__(self, master, project: Project,
                 baseline_manager: BaselineManager,
                 on_set: Callable[[], None] = None):
        self.project = project
        self.baseline_manager = baseline_manager
        self.on_set = on_set
        super().__init__(master, "Set Baseline")

    def _build(self):
        super()._build()
        self.geometry("460x260")

        # Baseline slot selector
        ctk.CTkLabel(self._body, text="Baseline slot", anchor=tk.W).grid(
            row=0, column=0, sticky=tk.W, pady=(0, 4))
        self._slot_var = ctk.StringVar()
        slot_labels = [slot.status_label() for slot in self.baseline_manager.slots]
        self._slot_menu = ctk.CTkOptionMenu(
            self._body, values=slot_labels, variable=self._slot_var)
        self._slot_menu.grid(row=1, column=0, sticky=tk.EW, pady=(0, 16))
        active = self.baseline_manager.active_slot_number
        if active:
            self._slot_var.set(slot_labels[active - 1])
        else:
            self._slot_var.set(slot_labels[0])

        # Roll-up checkbox
        self._rollup_var = tk.BooleanVar(value=False)
        self._rollup_cb = ctk.CTkCheckBox(
            self._body, text="Roll up baseline data to parent summary tasks",
            variable=self._rollup_var)
        self._rollup_cb.grid(row=2, column=0, sticky=tk.W, pady=(8, 0))

    def _on_ok(self):
        label = self._slot_var.get()
        try:
            number = self.baseline_manager.slots[
                [s.status_label() for s in self.baseline_manager.slots].index(label)
            ].number
        except ValueError:
            self.destroy()
            return

        # Saving a baseline stores it without turning comparison on: a fresh
        # baseline should not appear on the Gantt chart until the reader asks
        # for it through Compare Baseline. set_active would otherwise make
        # the slot the one the chart draws the moment it is captured.
        self.baseline_manager.set_baseline(
            self.project, number, task_ids=None,
            rollup=self._rollup_var.get(), set_active=False)
        logger.info("Baseline %d captured for the entire project", number)
        if self.on_set:
            self.on_set()
        self.destroy()


class BaselineClearDialog(_BaselineDialogBase):
    """
    Modal dialog for clearing a baseline off the whole project.

    As on the Set side there is no Scope section: clearing is done for
    the entire project only (issue #84, following #19), and every clear
    asks the reader to confirm.
    """

    def __init__(self, master, project: Project,
                 baseline_manager: BaselineManager,
                 on_clear: Callable[[], None] = None):
        self.project = project
        self.baseline_manager = baseline_manager
        self.on_clear = on_clear
        super().__init__(master, "Clear Baseline")

    def _build(self):
        super()._build()

        ctk.CTkLabel(self._body, text="Baseline slot to clear", anchor=tk.W).grid(
            row=0, column=0, sticky=tk.W, pady=(0, 4))
        self._slot_var = ctk.StringVar()
        slot_labels = [slot.status_label() for slot in self.baseline_manager.slots]
        self._slot_menu = ctk.CTkOptionMenu(
            self._body, values=slot_labels, variable=self._slot_var)
        self._slot_menu.grid(row=1, column=0, sticky=tk.EW, pady=(0, 16))
        active = self.baseline_manager.active_slot_number
        if active:
            self._slot_var.set(slot_labels[active - 1])
        else:
            first_set = next((s for s in self.baseline_manager.slots if s.is_set), None)
            self._slot_var.set(slot_labels[(first_set.number - 1) if first_set else 0])

    def _on_ok(self):
        label = self._slot_var.get()
        try:
            number = self.baseline_manager.slots[
                [s.status_label() for s in self.baseline_manager.slots].index(label)
            ].number
        except ValueError:
            self.destroy()
            return

        if not self.baseline_manager.get_slot(number).is_set:
            messagebox.showinfo(
                "Clear Baseline",
                f"Baseline {number} is already unset.")
            self.destroy()
            return

        if not messagebox.askyesno(
            "Clear Baseline",
            f"Permanently clear Baseline {number}? This cannot be undone."):
            return

        self.baseline_manager.clear_baseline(number, task_ids=None)
        logger.info("Baseline %d cleared", number)
        if self.on_clear:
            self.on_clear()
        self.destroy()
