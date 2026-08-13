"""
Interactive Gantt chart visualization using Plotly for the Gantt Project Management Tool.

Uses Plotly for rendering with interactive features (zoom, pan, hover tooltips).

WHY THIS MODULE EXISTS:
======================
This module provides the visual Gantt chart display for the application.

1. **Interactive Visualization**: 
   - Uses Plotly for interactive charts with zoom, pan, and hover capabilities
   - Provides better user experience with built-in interactivity
   - Supports dynamic updates when project data changes

2. **Reusability**:
   - The core chart drawing logic can be reused for export if needed
"""

import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
import plotly.graph_objects as go

from gantt_app.models import Project
from gantt_app.utils.chart_figure import build_gantt_figure, DEFAULT_WIDTH
from gantt_app.utils.chart_render import render_image
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


class GanttChart(ctk.CTkFrame):
    """
    Interactive Gantt chart visualization with tasks as bars and milestones as diamonds.
    Shows dependencies as lines between tasks.
    
    This class is responsible for:
    - Creating and displaying the Gantt chart in the GUI
    - Updating the chart when project data changes
    - Handling window resizing
    """
    
    def __init__(self, master, project: Project, 
                 width: int = 12, height: int = 8, dpi: int = 100):
        super().__init__(master)
        
        self.master = master
        self.project = project
        self.width = width
        self.height = height
        self.dpi = dpi
        
        # Colors - these match the theme used in the exporters
        self.task_color = '#1f6aa5'
        self.milestone_color = '#e74c3c'
        self.dependency_color = '#e74c3c'
        self.critical_path_color = '#f39c12'
        
        # Chart settings (can be customized via GanttChartSettingsDialog)
        self.chart_settings = {
            "font_size": 12,
            "bg_color": "#ffffff",
            "text_color": "#000000",
            "grid_color": "#ecf0f1"
        }
        
        # Kept so callers can still obtain the interactive figure, for the
        # HTML export and for anything that wants Plotly's own output
        self.figure = go.Figure()

        # Create a frame to hold the chart
        self.chart_frame = ctk.CTkFrame(self)
        self.chart_frame.pack(fill=tk.BOTH, expand=True)

        self._image_label = None
        self._chart_image = None
        self._last_render_width = 0
        self._resize_job = None

        # Draw initial chart
        self.draw_chart()

        # Bind to configure events for resizing
        self.bind('<Configure>', self.on_resize)

    def on_resize(self, event=None):
        """
        Redraw after the window settles.

        DEVELOPMENT NOTES:
        ------------------
        Configure fires continuously while a window is dragged, and each
        redraw rasterises the whole chart, so the work is deferred until the
        resizing stops. Redrawing on every event made the window crawl.
        """
        if self._resize_job is not None:
            try:
                self.after_cancel(self._resize_job)
            except (tk.TclError, ValueError):
                pass
        try:
            self._resize_job = self.after(250, self._resize_settled)
        except tk.TclError:
            self._resize_job = None

    def _resize_settled(self):
        """Redraw once the window has stopped changing size."""
        self._resize_job = None
        if not self.winfo_exists():
            return
        # Only re-rasterise when the width actually changed
        if abs(self.chart_frame.winfo_width() - self._last_render_width) > 20:
            self.draw_chart()
    
    def draw_chart(self):
        """
        Draw the Gantt chart into the window.

        DEVELOPMENT NOTES:
        ------------------
        The chart is rasterised with Pillow rather than handed to Plotly.
        Plotly renders through JavaScript, and the only way to run that
        inside Tkinter is tkinterweb, whose Tkhtml engine executes no
        JavaScript unless the optional PythonMonkey backend is installed -
        and even then Tkhtml is an HTML/CSS renderer, not a browser capable
        of running plotly.js. The result was a permanently blank chart area.

        The same renderer produces the PNG, PDF and SVG exports, so what the
        window shows and what a user exports are now identical. The
        interactive Plotly version is still available through Export > HTML.
        """
        width = self.chart_frame.winfo_width()
        if width < 100:
            # Called before the frame has been sized; use a sensible default
            width = max(int(self.width) * 100, DEFAULT_WIDTH)
        self._last_render_width = width

        try:
            image = render_image(
                self.project,
                settings=self._figure_settings(),
                width=width,
                scale=1.5
            )
        except Exception:
            logger.exception("Could not draw the Gantt chart")
            self._show_message("The chart could not be drawn.\n"
                               "See the Log window for details.", "red")
            return

        self._show_image(image)

        logger.debug("Drew Gantt chart for %r (%d task(s), %dpx wide)",
                     self.project.name, len(self.project.tasks), width)

    def _figure_settings(self):
        """
        Collect the appearance settings passed to the renderers.

        DEVELOPMENT NOTES:
        ------------------
        The settings dialog writes both into chart_settings and onto the
        individual colour attributes, so both are merged here rather than the
        renderer having to know about the widget.
        """
        settings = dict(getattr(self, 'chart_settings', {}) or {})
        settings.setdefault('task_color', self.task_color)
        settings.setdefault('milestone_color', self.milestone_color)
        settings['dependency_color'] = self.dependency_color
        settings['critical_path_color'] = self.critical_path_color
        return settings

    def _clear_frame(self):
        """Remove whatever is currently displayed."""
        for widget in self.chart_frame.winfo_children():
            widget.destroy()
        self._image_label = None

    def _show_image(self, image):
        """Display a rendered chart image, scrollable when it is tall."""
        self._clear_frame()

        # CTkImage keeps its own reference; holding it here stops the
        # underlying PhotoImage being garbage collected while displayed
        self._chart_image = ctk.CTkImage(light_image=image, dark_image=image,
                                         size=image.size)

        canvas = tk.Canvas(self.chart_frame, highlightthickness=0,
                           background=self._figure_settings().get('bg_color',
                                                                  '#ffffff'))
        scrollbar = ttk.Scrollbar(self.chart_frame, orient=tk.VERTICAL,
                                  command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        holder = ctk.CTkLabel(canvas, image=self._chart_image, text="")
        canvas.create_window(0, 0, anchor=tk.NW, window=holder)
        canvas.configure(scrollregion=(0, 0, image.size[0], image.size[1]))

        self._image_label = holder

    def _show_message(self, message: str, colour: str = "gray"):
        """Display a message in place of the chart."""
        self._clear_frame()
        ctk.CTkLabel(self.chart_frame, text=message,
                     text_color=colour).pack(pady=40)

    def build_figure(self):
        """
        Build the interactive Plotly figure for this project.

        RETURNS:
        --------
        go.Figure
            Used by the HTML export, which runs in a real browser where
            plotly.js works.
        """
        self.figure = build_gantt_figure(self.project,
                                         settings=self._figure_settings())
        return self.figure

    def update_chart(self):
        """Update the chart with current project data."""
        self.draw_chart()
    
    def set_project(self, project: Project):
        """Set a new project and redraw the chart."""
        self.project = project
        self.update_chart()
    
    def clear_chart(self):
        """Clear the chart."""
        self.figure = go.Figure()
        self._draw_empty_chart()
        self._render_chart()

    def export_to_png(self, filepath: str, dpi: int = 300) -> bool:
        """
        Export the Gantt chart to a PNG file.

        PARAMETERS:
        -----------
        filepath : str
            Path to save the PNG file.
        dpi : int, optional
            Dots per inch for the output image (default 300).

        RETURNS:
        --------
        bool
            True if successful, False otherwise.

        DEVELOPMENT NOTES:
        ------------------
        Rendering goes through the same Plotly figure shown on screen, so an
        exported image matches the chart exactly. Kaleido drives a Chrome or
        Chromium browser to rasterise it; when none is installed the export
        returns False and logs what to install rather than hanging.
        """
        from gantt_app.utils.image_export import export_gantt_to_png
        return export_gantt_to_png(self.project, filepath,
                                   settings=self._figure_settings())

    def export_to_pdf(self, filepath: str) -> bool:
        """
        Export the Gantt chart to a PDF file.

        PARAMETERS:
        -----------
        filepath : str
            Path to save the PDF file.

        RETURNS:
        --------
        bool
            True if successful, False otherwise.

        DEVELOPMENT NOTES:
        ------------------
        Delegates to the same Plotly renderer as export_to_png.
        """
        from gantt_app.utils.image_export import export_gantt_to_pdf
        return export_gantt_to_pdf(self.project, filepath,
                                   settings=self._figure_settings())
