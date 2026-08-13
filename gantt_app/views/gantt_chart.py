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
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple, Any

import customtkinter as ctk
import plotly.graph_objects as go

from gantt_app.models import Task, Project
from gantt_app.utils.chart_figure import (
    build_gantt_figure, build_empty_figure, DEFAULT_WIDTH
)
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
        
        # Create figure
        self.figure = go.Figure()
        
        # Try to import tkinterweb for embedding
        self.has_tkinterweb = False
        self.browser = None
        try:
            import tkinterweb
            self.has_tkinterweb = True
        except ImportError:
            logger.warning("tkinterweb is not installed; the chart cannot be displayed")
        
        # Create a frame to hold the chart
        self.chart_frame = ctk.CTkFrame(self)
        self.chart_frame.pack(fill=tk.BOTH, expand=True)
        
        # Draw initial chart
        self.draw_chart()
        
        # Bind to configure events for resizing
        self.bind('<Configure>', self.on_resize)
    
    def on_resize(self, event):
        """Handle window resize by redrawing the chart."""
        self.draw_chart()
    
    def draw_chart(self):
        """Build the Plotly figure for the project and render it."""
        try:
            self.figure = build_gantt_figure(
                self.project,
                settings=self._figure_settings(),
                width=DEFAULT_WIDTH
            )
        except Exception:
            logger.exception("Could not build the Gantt figure")
            self.figure = build_empty_figure(self._figure_settings())

        self._render_chart()

    def _figure_settings(self):
        """
        Collect the appearance settings passed to the figure builder.

        DEVELOPMENT NOTES:
        ------------------
        The settings dialog writes both into chart_settings and onto the
        individual colour attributes, so both are merged here rather than the
        builder having to know about the widget.
        """
        settings = dict(getattr(self, 'chart_settings', {}) or {})
        settings.setdefault('task_color', self.task_color)
        settings.setdefault('milestone_color', self.milestone_color)
        settings['dependency_color'] = self.dependency_color
        settings['critical_path_color'] = self.critical_path_color
        return settings

    def _render_chart(self):
        """
        Render the current figure into the Tkinter frame.

        DEVELOPMENT NOTES:
        ------------------
        plotly.js is inlined rather than pulled from a CDN. The packaged
        application is meant to work with no network at all, and a CDN
        reference left the chart area blank whenever the machine was offline.
        """
        for widget in self.chart_frame.winfo_children():
            widget.destroy()

        if not self.has_tkinterweb:
            ctk.CTkLabel(
                self.chart_frame,
                text=("The Gantt chart needs tkinterweb.\n"
                      "Install it with:  pip install tkinterweb"),
                text_color="gray"
            ).pack(pady=40)
            logger.warning("tkinterweb is unavailable; chart not rendered")
            return

        try:
            import tkinterweb

            html = self.figure.to_html(include_plotlyjs=True, full_html=True)

            self.browser = tkinterweb.HtmlFrame(self.chart_frame,
                                                messages_enabled=False)
            self.browser.load_html(html)
            self.browser.pack(fill=tk.BOTH, expand=True)

            logger.debug("Rendered Gantt chart for %r (%d tasks)",
                         self.project.name, len(self.project.tasks))

        except Exception as e:
            logger.exception("Error rendering the Gantt chart")
            ctk.CTkLabel(
                self.chart_frame,
                text=f"Error rendering chart: {e}",
                text_color="red"
            ).pack(pady=20)


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
