"""
Export a plan as a Mermaid chart: the options sheet behind Export > Mermaid.

WHY THIS WINDOW EXISTS:
======================
The export used to ask only where to save. A Mermaid chart is drawn by the
renderer, though, and the renderer takes two options the file can carry: the
theme to draw it in and the text size to draw it at. Asking at export time
keeps them beside the save-as choice rather than in a settings panel they
have nothing to do with.

The theme list is the one the Gantt chart settings already show - the names
are Mermaid's own (default, base, dark, forest, neutral), and the exporter
writes the pick into the file's init directive, pure text, so nothing here
needs a renderer or a browser.
"""

import tkinter as tk
from typing import Optional

import customtkinter as ctk

from gantt_app.utils.log import get_logger
from gantt_app.utils.mermaid_exporter import export_project_to_mermaid
from gantt_app.views import dialogs as filedialog
from gantt_app.views import dialogs as messagebox
from gantt_app.views.ganttsettingsw import MERMAID_THEMES
from gantt_app.views.modal import grab_when_visible

logger = get_logger(__name__)


class MermaidExportDialog(ctk.CTkToplevel):
    """
    The Export > Mermaid sheet: text size, theme, destination, then Export.

    PARAMETERS:
    -----------
    master : widget
        Window to open over.
    project : Project
        The plan being exported.
    gantt_chart :
        The chart, for the text size and theme it is currently drawn with -
        the export opens on those rather than on bare defaults.
    """

    def __init__(self, master, project, gantt_chart=None):
        super().__init__(master)
        self.project = project

        self.title("Export to Mermaid")
        self.geometry("440x330")
        self.resizable(False, False)
        self.transient(master.winfo_toplevel())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind('<Escape>', lambda _event: self.destroy())

        settings = getattr(gantt_chart, 'chart_settings', None) or {}

        self._build(settings)
        grab_when_visible(self)

    def _row(self, parent, label: str):
        """One labelled line of the form; returns the row number used."""
        row = parent.grid_size()[1]
        ctk.CTkLabel(parent, text=label, anchor=tk.W
                     ).grid(row=row, column=0, sticky=tk.W, padx=(0, 12),
                            pady=(10, 0))
        return row

    def _build(self, settings):
        """Lay the three choices out, then the two buttons."""
        content = ctk.CTkFrame(self, fg_color='transparent')
        content.pack(fill=tk.BOTH, expand=True, padx=16, pady=(10, 0))
        content.grid_columnconfigure(1, weight=1)

        # Text size - the same slider the chart settings use for it
        row = self._row(content, "Text size:")
        self.size_var = tk.IntVar(value=int(settings.get('font_size', 12)))
        self.size_slider = ctk.CTkSlider(
            content, from_=8, to=24, number_of_steps=16,
            variable=self.size_var, command=self._show_size)
        self.size_slider.grid(row=row, column=1, sticky=tk.EW, pady=(10, 0))
        self.size_label = ctk.CTkLabel(
            content, text=f"{self.size_var.get()}px", anchor=tk.W)
        self.size_label.grid(row=row, column=2, sticky=tk.W, padx=(10, 0),
                             pady=(10, 0))

        # Theme - the same names the chart settings offer; they are
        # Mermaid's own, lowercased into the file's init directive
        row = self._row(content, "Theme:")
        self.theme_var = ctk.StringVar(value=settings.get('theme', 'Default'))
        if self.theme_var.get() not in MERMAID_THEMES:
            self.theme_var.set('Default')
        self.theme_menu = ctk.CTkOptionMenu(
            content, variable=self.theme_var, values=list(MERMAID_THEMES))
        self.theme_menu.grid(row=row, column=1, columnspan=2, sticky=tk.EW,
                             pady=(10, 0))

        # Destination - the same native save box the export used to open
        # straight away, now beside a field that shows what was picked
        row = self._row(content, "Destination:")
        self.path_entry = ctk.CTkEntry(
            content, placeholder_text="Choose where to save the .mmd file")
        self.path_entry.grid(row=row, column=1, sticky=tk.EW, pady=(10, 0))
        ctk.CTkButton(content, text="Browse…", width=90,
                      command=self._browse).grid(row=row, column=2,
                                                 sticky=tk.E, padx=(10, 0),
                                                 pady=(10, 0))

        buttons = ctk.CTkFrame(self, fg_color='transparent')
        buttons.pack(fill=tk.X, side=tk.BOTTOM, padx=16, pady=14)
        ctk.CTkButton(buttons, text="Cancel", width=100,
                      fg_color="#e74c3c", hover_color="#c0392b",
                      command=self.destroy).pack(side=tk.RIGHT, padx=(6, 0))
        ctk.CTkButton(buttons, text="Export", width=100,
                      command=self._export).pack(side=tk.RIGHT)

    def _show_size(self, _value=None):
        """Keep the px label beside the slider in step with it."""
        self.size_label.configure(text=f"{self.size_var.get()}px")

    def _browse(self):
        """The native save-as box, filling the destination field."""
        path = filedialog.asksaveasfilename(
            defaultextension=".mmd",
            filetypes=[("Mermaid Files", "*.mmd"), ("All Files", "*.*")],
            title="Export Mermaid File")
        if path:
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, path)

    def _export(self):
        """Write the file where the field says, in the theme chosen."""
        file_path = self.path_entry.get().strip()
        if not file_path:
            # Pressing Export without a pick means the chooser has not been
            # seen yet - open it rather than faulting an empty box.
            self._browse()
            file_path = self.path_entry.get().strip()
            if not file_path:
                return

        theme_name = self.theme_var.get().lower()
        if export_project_to_mermaid(self.project, file_path,
                                     mermaid_theme=theme_name,
                                     font_size=self.size_var.get()):
            logger.info("Exported %r to Mermaid at %s (theme=%s, size=%spx)",
                        self.project.name, file_path, theme_name,
                        self.size_var.get())
            messagebox.showinfo(
                "Success", "Project exported to Mermaid successfully!")
            self.destroy()
        else:
            messagebox.showerror(
                "Error", "Failed to export project to Mermaid")


def export_mermaid_dialog(master, project, gantt_chart=None) -> Optional[
        'MermaidExportDialog']:
    """
    Open the export sheet over a window.

    RETURNS:
    --------
    Optional[MermaidExportDialog]
        The sheet, or None when it could not be built - which is reported
        rather than left to take the window down with it.
    """
    try:
        return MermaidExportDialog(master, project, gantt_chart)
    except Exception:
        logger.exception("Could not open the Mermaid export options")
        messagebox.showerror(
            "Export to Mermaid",
            "Could not open the export options.\n\n"
            "See the Log window for details.")
        return None
