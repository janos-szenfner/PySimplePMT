"""
The Settings tab that shows the style presets and edits the custom ones.

WHY THIS MODULE EXISTS:
======================
The four built-in presets are read-only - a plan has to mean the same thing by
"Phase Gate" wherever it is opened - so their rows carry a locked badge in
place of Edit and Delete, and nothing here can change their name, colours or
emphasis. A reader's own presets sit beneath them and can be added, edited and
removed; each change is saved and broadcast so the toolbar's preset menu shows
it without a restart. See REQ-UI-020.

DEVELOPMENT NOTES:
------------------
The grid and every preview are drawn from each preset's own TaskStyle, so a
row promises exactly what the toolbar will apply. The tab subscribes to the
manager, so a change made here - or anywhere - redraws it.
"""

import tkinter as tk
from typing import Callable, Optional

import customtkinter as ctk

from gantt_app import theme
from gantt_app.presets import DEFAULT_CUSTOM_BADGE, PresetManager, StylePreset
from gantt_app.taskstyle import TaskStyle
from gantt_app.utils.log import get_logger
from gantt_app.views.colorpicker import ColorEntry
from gantt_app.views.modal import grab_when_visible

logger = get_logger(__name__)


class StylePresetsTab(ctk.CTkFrame):
    """
    The presets grid: built-ins locked, customs editable.

    PARAMETERS:
    -----------
    master : widget
        The Settings tab to build into.
    manager : PresetManager
        The presets to show and edit.
    """

    def __init__(self, master, manager: PresetManager, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.manager = manager

        self._build()
        self.manager.subscribe(self.refresh)
        self.bind("<Destroy>", self._on_destroy, add="+")
        self.refresh()

    def _on_destroy(self, event):
        """Stop listening when the tab goes, so a dead grid is not redrawn."""
        if event.widget is self:
            self.manager.unsubscribe(self.refresh)

    def _build(self):
        """Title, the scrolling grid, and the add button."""
        ctk.CTkLabel(
            self, text="Style Presets",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(anchor=tk.W, padx=6, pady=(6, 2))
        ctk.CTkLabel(
            self,
            text="The four built-in presets are read-only. Add your own "
                 "below; they appear in the toolbar's preset menu at once.",
            text_color=theme.MUTED_TEXT, anchor=tk.W, justify=tk.LEFT,
            wraplength=680,
        ).pack(anchor=tk.W, padx=6, pady=(0, 8))

        self.grid_frame = ctk.CTkScrollableFrame(self, height=300)
        self.grid_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        ctk.CTkButton(
            self, text="+ Add Custom Preset", width=200,
            command=self._add,
        ).pack(anchor=tk.W, padx=6, pady=(8, 4))

    def refresh(self):
        """Redraw the grid from the manager. Safe once the tab has gone."""
        try:
            if not self.grid_frame.winfo_exists():
                return
        except tk.TclError:
            return

        for child in self.grid_frame.winfo_children():
            child.destroy()

        headers = ("", "Name", "Type", "Preview", "Actions")
        for column, text in enumerate(headers):
            ctk.CTkLabel(
                self.grid_frame, text=text,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=theme.MUTED_TEXT,
            ).grid(row=0, column=column, padx=10, pady=6, sticky=tk.W)

        for index, preset in enumerate(self.manager.all(), start=1):
            self._row(index, preset)

    def _row(self, index: int, preset: StylePreset):
        """One preset's row: badge, name, type, chip, and its actions."""
        ctk.CTkLabel(self.grid_frame, text=preset.badge,
                     text_color=preset.badge_color).grid(
            row=index, column=0, padx=10, pady=4)
        ctk.CTkLabel(self.grid_frame, text=preset.name, anchor=tk.W).grid(
            row=index, column=1, padx=10, pady=4, sticky=tk.W)

        kind = "Built-in (Locked)" if preset.is_builtin else "Custom"
        ctk.CTkLabel(
            self.grid_frame, text=kind, anchor=tk.W,
            text_color=theme.MUTED_TEXT if preset.is_builtin else '#2b8fd4',
        ).grid(row=index, column=2, padx=10, pady=4, sticky=tk.W)

        _preview_chip(self.grid_frame, preset).grid(
            row=index, column=3, padx=10, pady=4)

        actions = ctk.CTkFrame(self.grid_frame, fg_color="transparent")
        actions.grid(row=index, column=4, padx=10, pady=4, sticky=tk.W)

        if preset.is_builtin:
            # The read-only guardrail: no Edit, no Delete, a locked badge in
            # their place. See REQ-UI-020.
            ctk.CTkLabel(
                actions, text="🔒 Locked", text_color=theme.MUTED_TEXT,
                font=ctk.CTkFont(size=11, slant="italic"),
            ).pack(side=tk.LEFT, padx=4)
            return

        ctk.CTkButton(actions, text="Edit", width=54, height=24,
                      command=lambda p=preset: self._edit(p)).pack(
            side=tk.LEFT, padx=2)
        ctk.CTkButton(
            actions, text="Delete", width=60, height=24,
            fg_color='#c0392b', hover_color='#e74c3c',
            command=lambda p=preset: self._delete(p)).pack(
            side=tk.LEFT, padx=2)

    def _add(self):
        """Open the editor on a fresh preset."""
        PresetEditorDialog(
            self, title="Add Custom Preset",
            on_save=lambda name, style, badge, colour:
            self.manager.add_custom(name, style, badge, colour))

    def _edit(self, preset: StylePreset):
        """Open the editor on a custom preset, and store the changes."""
        PresetEditorDialog(
            self, title="Edit Custom Preset", preset=preset,
            on_save=lambda name, style, badge, colour:
            self.manager.update_custom(
                preset.id, name=name, style=style,
                badge=badge, badge_color=colour))

    def _delete(self, preset: StylePreset):
        """Remove a custom preset."""
        self.manager.delete_custom(preset.id)


def _preview_chip(master, preset: StylePreset) -> ctk.CTkLabel:
    """A chip drawn in a preset's own colours and emphasis."""
    style = preset.style
    font = ctk.CTkFont(
        size=11,
        weight="bold" if style.bold else "normal",
        slant="italic" if style.italic else "roman",
        underline=bool(style.underline))
    return ctk.CTkLabel(
        master, text=f"{preset.badge} Sample", font=font,
        fg_color=style.fill_color or "transparent",
        text_color=style.text_color or theme.TEXT,
        corner_radius=6, width=130, height=26)


class PresetEditorDialog(ctk.CTkToplevel):
    """
    Define a custom preset: its name, badge, colours and emphasis.

    PARAMETERS:
    -----------
    master : widget
        The tab that opened it.
    on_save : Callable[[str, TaskStyle, str, str], None]
        Given the name, the TaskStyle, the badge glyph and the badge colour.
    preset : Optional[StylePreset]
        The preset being edited, or None when adding.
    title : str
        The window title.

    DEVELOPMENT NOTES:
    ------------------
    A custom preset always carries both a fill and a text colour, which is
    what the built-ins' None fills are the exception to; that keeps the
    editor two colour pickers rather than two pickers and two "use this"
    switches. The preview updates as the fields change, from the same
    TaskStyle the save hands back.
    """

    GEOMETRY = "420x440"

    def __init__(self, master, on_save: Callable,
                 preset: Optional[StylePreset] = None,
                 title: str = "Custom Preset", **kwargs):
        super().__init__(master, **kwargs)
        self.on_save = on_save

        self.title(title)
        self.geometry(self.GEOMETRY)
        self.transient(master.winfo_toplevel())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda _event: self.destroy())

        seed = preset or _seed_preset()
        self._build(seed)
        grab_when_visible(self)

    def _build(self, seed: StylePreset):
        """Lay out the fields, seeded from the preset being edited or added."""
        pad = {'padx': 16, 'pady': 4}

        ctk.CTkLabel(self, text="Name").pack(anchor=tk.W, **pad)
        self.name_entry = ctk.CTkEntry(self)
        self.name_entry.insert(0, seed.name)
        self.name_entry.pack(fill=tk.X, **pad)

        ctk.CTkLabel(self, text="Badge (a character or two)").pack(
            anchor=tk.W, **pad)
        self.badge_entry = ctk.CTkEntry(self, width=80)
        self.badge_entry.insert(0, seed.badge)
        self.badge_entry.pack(anchor=tk.W, **pad)

        self.badge_colour = self._colour_row("Badge colour",
                                              seed.badge_color)
        self.text_colour = self._colour_row(
            "Text colour", seed.style.text_color or '#1a1a1a')
        self.fill_colour = self._colour_row(
            "Background fill", seed.style.fill_color or '#fff2cc')

        emphasis = ctk.CTkFrame(self, fg_color="transparent")
        emphasis.pack(fill=tk.X, **pad)
        self.bold = self._switch(emphasis, "Bold", seed.style.bold)
        self.italic = self._switch(emphasis, "Italic", seed.style.italic)
        self.underline = self._switch(emphasis, "Underline",
                                      seed.style.underline)

        self.preview = ctk.CTkLabel(self, text="Sample", corner_radius=6,
                                    width=160, height=30)
        self.preview.pack(pady=8)
        self._repaint_preview()

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill=tk.X, **pad)
        ctk.CTkButton(buttons, text="Cancel", width=90, fg_color='#3a3a3a',
                      hover_color='#4a4a4a',
                      command=self.destroy).pack(side=tk.RIGHT, padx=4)
        ctk.CTkButton(buttons, text="Save", width=90,
                      command=self._save).pack(side=tk.RIGHT, padx=4)

    def _colour_row(self, label: str, colour: str) -> ColorEntry:
        """A labelled colour picker that repaints the preview on a change."""
        ctk.CTkLabel(self, text=label).pack(anchor=tk.W, padx=16, pady=(4, 0))
        entry = ColorEntry(self, color=colour,
                           on_change=lambda _c: self._repaint_preview())
        entry.pack(anchor=tk.W, padx=16, pady=(0, 4))
        return entry

    def _switch(self, parent, label: str, on: Optional[bool]) -> ctk.CTkSwitch:
        """One emphasis switch, repainting the preview when it is flicked."""
        var = ctk.BooleanVar(value=bool(on))
        switch = ctk.CTkSwitch(parent, text=label, variable=var,
                               command=self._repaint_preview)
        switch.pack(side=tk.LEFT, padx=(0, 12))
        switch._value_var = var
        return switch

    def _style(self) -> TaskStyle:
        """The TaskStyle the fields describe."""
        return TaskStyle(
            text_color=self.text_colour.get(),
            fill_color=self.fill_colour.get(),
            bold=self.bold._value_var.get(),
            italic=self.italic._value_var.get(),
            underline=self.underline._value_var.get(),
        )

    def _repaint_preview(self):
        """Draw the preview from the fields as they stand."""
        try:
            style = self._style()
            font = ctk.CTkFont(
                weight="bold" if style.bold else "normal",
                slant="italic" if style.italic else "roman",
                underline=bool(style.underline))
            badge = self.badge_entry.get().strip()
            self.preview.configure(
                text=f"{badge} Sample", font=font,
                fg_color=style.fill_color or "transparent",
                text_color=style.text_color or theme.TEXT)
        except tk.TclError:
            pass

    def _save(self):
        """Hand the preset back and close."""
        name = self.name_entry.get().strip() or "Custom preset"
        badge = self.badge_entry.get().strip() or DEFAULT_CUSTOM_BADGE[0]
        colour = self.badge_colour.get() or DEFAULT_CUSTOM_BADGE[1]
        try:
            self.on_save(name, self._style(), badge, colour)
        except Exception:
            logger.exception("Could not save the custom preset")
        self.destroy()


def _seed_preset() -> StylePreset:
    """A starting point for a new custom preset."""
    glyph, colour = DEFAULT_CUSTOM_BADGE
    return StylePreset(
        id='', name='Custom preset',
        style=TaskStyle(fill_color='#fff2cc', text_color='#1a1a1a'),
        badge=glyph, badge_color=colour, is_builtin=False)
