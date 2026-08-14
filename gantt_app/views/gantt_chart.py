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
from PIL import ImageTk

from gantt_app.utils.chart_render import (
    render_image, preferred_width, MIN_WIDTH
)
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


#: How long to wait after the last resize event before redrawing.
RESIZE_SETTLE_MS = 350

#: Ignore width changes smaller than this; a redraw is expensive.
RESIZE_THRESHOLD_PX = 24

#: Supersampling for the on-screen chart. Every extra step multiplies both
#: the render time and the Tk image memory, so it is lower than the exports.
SCREEN_SCALE = 1.0

#: How far one press of the zoom buttons moves.
ZOOM_STEP = 1.25

#: Zoom limits. Beyond these the chart is either unreadable or large enough
#: to hit the renderer's pixel budget, which would silently compress it back.
ZOOM_MIN = 0.25
ZOOM_MAX = 8.0

#: Floor for a zoomed-out chart, below which the labels collide.
MIN_ZOOMED_WIDTH = 320


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

        # How far the chart is zoomed in. 1.0 fits the available width; the
        # buttons below the chart step it, and Fit returns to 1.0
        self._zoom = 1.0

        # The controls go in first so the chart cannot squeeze them out when
        # a tall plan fills the pane
        self._zoom_bar = self._build_zoom_bar()
        self._zoom_bar.pack(side=tk.BOTTOM, fill=tk.X, padx=6, pady=(0, 4))

        # Create a frame to hold the chart
        self.chart_frame = ctk.CTkFrame(self)
        self.chart_frame.pack(fill=tk.BOTH, expand=True)

        self._image_label = None
        self._chart_image = None
        self._canvas = None
        self._last_render_width = 0
        self._resize_job = None
        self._drawing = False
        self._photo = None

        # Draw initial chart
        self.draw_chart()

        # Bind to configure events for resizing
        self.bind('<Configure>', self.on_resize)

    def _build_zoom_bar(self):
        """
        Build the zoom controls that sit under the chart.

        RETURNS:
        --------
        ctk.CTkFrame
            A strip holding zoom out, zoom in, Fit and the current level.
        """
        bar = ctk.CTkFrame(self)

        ctk.CTkButton(bar, text="−", width=36,
                      command=self.zoom_out).pack(side=tk.LEFT, padx=(6, 2),
                                                  pady=4)
        ctk.CTkButton(bar, text="+", width=36,
                      command=self.zoom_in).pack(side=tk.LEFT, padx=2, pady=4)
        ctk.CTkButton(bar, text="Fit", width=48,
                      command=self.zoom_to_fit).pack(side=tk.LEFT, padx=(6, 2),
                                                     pady=4)
        ctk.CTkButton(bar, text="Reset", width=58,
                      command=self.zoom_reset).pack(side=tk.LEFT, padx=2,
                                                    pady=4)

        self._zoom_label = ctk.CTkLabel(bar, text="100%", width=52)
        self._zoom_label.pack(side=tk.LEFT, padx=6)

        return bar

    def zoom_to_fit(self):
        """
        Zoom so the whole chart fits the width available.

        DEVELOPMENT NOTES:
        ------------------
        Fit used to mean 100%, which is not the same thing: at 100% a long
        plan is drawn wider than the pane on purpose, so every day gets
        enough pixels to stay readable, and the chart scrolls. Fitting means
        working out how much narrower than that the pane is and zooming out
        by exactly that ratio, which leaves nothing to scroll to.

        Reset is the button that goes back to 100%.
        """
        available = self.chart_frame.winfo_width()
        if available < 100:
            # The pane has not been sized yet, so there is nothing to fit to
            return

        natural = preferred_width(self.project, available)
        if natural <= 0:
            return

        self.set_zoom(available / natural)

    def zoom_in(self):
        """Show a shorter span across the same width."""
        self.set_zoom(self._zoom * ZOOM_STEP)

    def zoom_out(self):
        """Show a longer span across the same width."""
        self.set_zoom(self._zoom / ZOOM_STEP)

    def zoom_reset(self):
        """Return to 100%, the width the chart draws itself at."""
        self.set_zoom(1.0)

    def set_zoom(self, zoom: float):
        """
        Set the zoom level and redraw.

        PARAMETERS:
        -----------
        zoom : float
            Multiplier on the rendered width. Clamped to ZOOM_MIN..ZOOM_MAX.

        DEVELOPMENT NOTES:
        ------------------
        Zooming widens the image rather than scaling it after the fact, so
        the bars stay sharp and the extra width is reached with the
        horizontal scrollbar the chart already has.

        A redraw at the same level is skipped: the buttons are easy to hold
        down at a limit, and each redraw rasterises a multi-megapixel image.
        """
        zoom = max(ZOOM_MIN, min(float(zoom), ZOOM_MAX))
        if abs(zoom - self._zoom) < 1e-6:
            return

        self._zoom = zoom
        self._update_zoom_label()
        self.draw_chart()

    def _update_zoom_label(self):
        """Show the current level beside the buttons."""
        try:
            self._zoom_label.configure(text=f"{self._zoom * 100:.0f}%")
        except (tk.TclError, AttributeError):
            pass

    def on_resize(self, event=None):
        """
        Redraw once the window has settled at a new size.

        DEVELOPMENT NOTES:
        ------------------
        Configure fires continuously while a pane divider is dragged, and
        each redraw rasterises a multi-megapixel image and hands it to Tk,
        whose image memory Python does not manage. Doing that per event
        exhausted memory badly enough to lock up the machine, so the work is
        deferred until the events stop and skipped entirely while a draw is
        already in progress.

        Events from child widgets are ignored: rebuilding the canvas inside
        this frame raises Configure of its own, and acting on those is what
        turns a redraw into a loop that feeds itself.
        """
        if event is not None and getattr(event, 'widget', None) is not self:
            return

        if self._resize_job is not None:
            try:
                self.after_cancel(self._resize_job)
            except (tk.TclError, ValueError):
                pass
            self._resize_job = None

        try:
            self._resize_job = self.after(RESIZE_SETTLE_MS, self._resize_settled)
        except tk.TclError:
            self._resize_job = None

    def _resize_settled(self):
        """Redraw once the window has stopped changing size."""
        self._resize_job = None

        if self._drawing or not self.winfo_exists():
            return

        # Only re-rasterise when the width actually changed by a visible amount
        if abs(self.chart_frame.winfo_width() - self._last_render_width) > RESIZE_THRESHOLD_PX:
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
        if self._drawing:
            # A redraw triggered from inside a redraw would recurse
            return
        self._drawing = True
        try:
            self._draw_chart_now()
        finally:
            self._drawing = False

    def _draw_chart_now(self):
        """Rasterise the chart and put it on screen."""
        available = self.chart_frame.winfo_width()
        if available < 100:
            # Called before the frame has been sized; use a sensible default
            available = max(int(self.width) * 100, DEFAULT_WIDTH)
        self._last_render_width = available

        # Draw wide enough that a long plan stays readable and scrolls,
        # rather than squeezing every bar into the visible pane, then apply
        # the zoom on top. Zooming out below the pane width is allowed here -
        # preferred_width's floor is about legibility at 100%, and holding it
        # would make the zoom-out button do nothing on a short plan.
        width = preferred_width(self.project, available)
        if self._zoom != 1.0:
            width = max(int(width * self._zoom), MIN_ZOOMED_WIDTH)

        try:
            image = render_image(
                self.project,
                settings=self._figure_settings(),
                width=width,
                scale=SCREEN_SCALE,
                min_width=MIN_ZOOMED_WIDTH if self._zoom < 1.0 else MIN_WIDTH
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

    def _release_photo(self):
        """
        Drop the Tk image currently on screen.

        DEVELOPMENT NOTES:
        ------------------
        Tk owns this memory, so letting the Python reference go is not
        enough on its own; the image is deleted explicitly before the next
        one is built.
        """
        if self._photo is None:
            return
        try:
            self.tk.call('image', 'delete', str(self._photo))
        except (tk.TclError, AttributeError):
            pass
        self._photo = None

    def _clear_frame(self):
        """Remove whatever is currently displayed."""
        for widget in self.chart_frame.winfo_children():
            widget.destroy()
        self._image_label = None
        self._canvas = None

    def _show_image(self, image):
        """
        Display a rendered chart image, scrollable in both directions.

        DEVELOPMENT NOTES:
        ------------------
        The chart has a minimum width, so narrowing the pane makes it wider
        than the space available rather than squashing it. A horizontal
        scrollbar is what lets the far end of a long plan be reached, in the
        same way the task list scrolls sideways past its columns.
        """
        self._clear_frame()

        # A single ImageTk.PhotoImage drawn straight onto the canvas.
        # CTkImage was building two Tk images per redraw, one for the light
        # theme and one for the dark, and Tk image memory is not managed by
        # Python's collector - repeated redraws while dragging the divider
        # piled those up until the machine ran out of memory.
        self._release_photo()
        self._photo = ImageTk.PhotoImage(image)

        container = tk.Frame(self.chart_frame)
        container.pack(fill=tk.BOTH, expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        canvas = tk.Canvas(
            container, highlightthickness=0,
            background=self._figure_settings().get('bg_color', '#ffffff')
        )
        vertical = ttk.Scrollbar(container, orient=tk.VERTICAL,
                                 command=canvas.yview)
        horizontal = ttk.Scrollbar(container, orient=tk.HORIZONTAL,
                                   command=canvas.xview)
        canvas.configure(yscrollcommand=vertical.set,
                         xscrollcommand=horizontal.set)

        canvas.grid(row=0, column=0, sticky=tk.NSEW)
        vertical.grid(row=0, column=1, sticky=tk.NS)
        horizontal.grid(row=1, column=0, sticky=tk.EW)

        # create_image rather than a label in a canvas window: one fewer
        # widget, and nothing that reports the image size as a size request,
        # which could otherwise push the pane wider and trigger another redraw
        canvas.create_image(0, 0, anchor=tk.NW, image=self._photo)
        canvas.configure(scrollregion=(0, 0, image.size[0], image.size[1]))

        self._bind_scrolling(canvas)

        self._canvas = canvas
        self._image_label = None

    def _bind_scrolling(self, canvas):
        """
        Let the wheel and trackpad scroll the chart.

        DEVELOPMENT NOTES:
        ------------------
        Wheel events differ by platform: Windows and macOS deliver
        <MouseWheel> with a delta, X11 sends Button-4 and Button-5. Shift
        with the wheel scrolls sideways, which is the usual convention and
        saves reaching for the scrollbar on a wide plan.
        """
        def on_wheel(event):
            """Scroll vertically, or horizontally when Shift is held."""
            if event.delta:
                steps = -1 if event.delta > 0 else 1
                # macOS reports small deltas; Windows reports multiples of 120
                if abs(event.delta) >= 120:
                    steps = int(-event.delta / 120)
            else:
                steps = -1 if event.num == 4 else 1

            if event.state & 0x0001:  # Shift
                canvas.xview_scroll(steps, 'units')
            else:
                canvas.yview_scroll(steps, 'units')

        def on_horizontal_wheel(event):
            """Trackpad sideways scrolling."""
            steps = -1 if getattr(event, 'delta', 0) > 0 else 1
            canvas.xview_scroll(steps, 'units')

        for widget in (canvas, self.chart_frame):
            widget.bind('<MouseWheel>', on_wheel, add='+')
            widget.bind('<Shift-MouseWheel>', on_wheel, add='+')
            widget.bind('<Button-4>', on_wheel, add='+')
            widget.bind('<Button-5>', on_wheel, add='+')
            widget.bind('<Shift-Button-4>', on_horizontal_wheel, add='+')
            widget.bind('<Shift-Button-5>', on_horizontal_wheel, add='+')

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
        """
        Clear the chart.

        DEVELOPMENT NOTES:
        ------------------
        This called _draw_empty_chart and _render_chart, which were the
        matplotlib-era drawing helpers and went away with that renderer,
        leaving the method raising AttributeError for anything that used it.
        The Tk image is released here too, since dropping the Python
        reference alone does not free image memory Tk owns.
        """
        self.figure = go.Figure()
        self._clear_frame()
        self._release_photo()
        self._show_message("No chart to display.")

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
        Rendering goes through the same Pillow renderer that draws the chart
        on screen, so an exported image matches the window exactly and nothing
        is downloaded to produce it.
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
