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

from gantt_app.views import theme
from gantt_app.core.models import Project
from gantt_app.utils.chart_figure import (
    build_gantt_figure, DEFAULT_WIDTH, DEFAULT_SETTINGS,
)
from PIL import ImageTk

from gantt_app.utils.chart_render import (
    render_image, preferred_width, MIN_WIDTH, RowPlan,
    MARGIN_TOP as CHART_TOP_MARGIN,
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
        # bg_color is handed over rather than detected: the master is a
        # ttk.PanedWindow, which CustomTkinter cannot read a colour from and
        # falls back to black for. The sash palette is what the paned window
        # itself wears, so the frame's edges blend with what is actually
        # behind it in both appearances.
        super().__init__(master, bg_color=theme.pair(theme.SASH_BG))
        
        self.master = master
        self.project = project
        self.width = width
        self.height = height
        self.dpi = dpi

        #: The task list this chart is drawn beside, once main.py has built
        #: both and introduced them - see set_task_list. With one, the chart
        #: draws the rows the list is showing, at the list's row height, so
        #: a bar sits on the line of the task it belongs to. Without one it
        #: chooses its own rows and prints its own labels, which is what the
        #: exports do.
        self.task_list = None
        
        # Colors - these match the theme used in the exporters
        self.task_color = '#1f6aa5'
        self.milestone_color = '#f39c12'
        self.dependency_color = '#e74c3c'
        self.critical_path_color = '#e74c3c'
        
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
        # controls in the status bar step it, and Fit returns to 1.0
        self._zoom = 1.0
        #: Set by build_zoom_controls, which main.py calls with the status
        #: bar as the host - a strip inside this pane would take height from
        #: the chart and put its last row out of line with the list's
        #: (issue #70)
        self._zoom_label = None

        # Create a frame to hold the chart
        self.chart_frame = ctk.CTkFrame(self)
        self.chart_frame.pack(fill=tk.BOTH, expand=True)

        self._image_label = None
        self._chart_image = None
        #: The chart's scrollable canvas. Named _chart_canvas rather than
        #: _canvas on purpose: CTkFrame's own drawing surface is already
        #: called _canvas, and pointing the name at the chart canvas left
        #: the frame's surface unpainted on a theme change - the dark band
        #: that stayed under the chart after a switch back to day mode.
        self._chart_canvas = None
        self._last_render_width = 0
        self._resize_job = None
        self._drawing = False
        self._photo = None

        # What the last drawing was of, so a scroll can be told from a change
        # of rows, and the chart scrolled in the rows it actually has
        self._drawn_rows = []
        self._drawn_row_height = 0
        self._drawn_top_margin = 0
        self._drawn_height = 0

        # Which task IDs the drawn guide lines mark, and the redraw the
        # last selection event is still waiting for (issue #119)
        self._drawn_selection = set()
        self._select_after = None

        # Where the chart's first row goes, measured once the panes have
        # been laid out; see _first_row_offset
        self._row_offset = None

        # Draw initial chart
        self.draw_chart()

        # Bind to configure events for resizing
        self.bind('<Configure>', self.on_resize)

    def build_zoom_controls(self, host):
        """
        Build the zoom controls inside the frame they are offered.

        PARAMETERS:
        -----------
        host : tk widget
            The frame to hold them - the application's status bar, which is
            where the reference tool keeps its chart zoom. Not packed here:
            the caller places the returned frame where it belongs.

        RETURNS:
        --------
        ctk.CTkFrame
            A strip holding zoom out, zoom in, Fit, Reset and the level.

        DEVELOPMENT NOTES:
        ------------------
        They used to sit in a row under the chart inside its own pane.
        Anything in the pane that is not chart costs the canvas height, and
        the rows down at the bottom stopped lining up with the task list
        beside it - which is the one thing the panes are measured against
        (issue #70). Given a host they live wherever they are put, and the
        chart pane is nothing but chart.
        """
        bar = ctk.CTkFrame(host, fg_color="transparent")

        ctk.CTkButton(bar, text="−", width=36,
                      command=self.zoom_out).pack(side=tk.LEFT, padx=(0, 2))
        ctk.CTkButton(bar, text="+", width=36,
                      command=self.zoom_in).pack(side=tk.LEFT, padx=2)
        ctk.CTkButton(bar, text="Fit", width=48,
                      command=self.zoom_to_fit).pack(side=tk.LEFT, padx=(6, 2))
        ctk.CTkButton(bar, text="Reset", width=58,
                      command=self.zoom_reset).pack(side=tk.LEFT, padx=2)

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
        logger.info("Gantt chart zoomed to fit: %.0f%%", self._zoom * 100)

    def zoom_in(self):
        """Show a shorter span across the same width."""
        self.set_zoom(self._zoom * ZOOM_STEP)
        logger.info("Gantt chart zoomed in to %.0f%%", self._zoom * 100)

    def zoom_out(self):
        """Show a longer span across the same width."""
        self.set_zoom(self._zoom / ZOOM_STEP)
        logger.info("Gantt chart zoomed out to %.0f%%", self._zoom * 100)

    def zoom_reset(self):
        """Return to 100%, the width the chart draws itself at."""
        self.set_zoom(1.0)
        logger.info("Gantt chart zoom reset to %.0f%%", self._zoom * 100)

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

        # The panes have moved, so where the rows start is worth asking again
        self._row_offset = None

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

    def destroy(self):
        """
        Cancel a pending resize redraw before the chart goes.

        A settle timer left armed would otherwise run _resize_settled on a
        dead widget. Done in a destroy() override rather than off a <Destroy>
        binding because a CustomTkinter widget's own <Destroy> does not reach
        a self.bind handler, and because the canvas child - whose <Destroy>
        does fire - is torn down and rebuilt on every redraw, so binding
        there would cancel a live resize mid-draw.
        """
        if self._resize_job is not None:
            try:
                self.after_cancel(self._resize_job)
            except (tk.TclError, ValueError):
                pass
            self._resize_job = None
        super().destroy()

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

        plan = self._row_plan()

        baseline = None
        baseline_color = None
        if getattr(self, '_baseline_manager', None) and self._baseline_slot:
            slot = self._baseline_manager.get_slot(self._baseline_slot)
            if slot and slot.baseline:
                baseline = slot.baseline
                baseline_color = slot.effective_color

        try:
            image = render_image(
                self.project,
                settings=self._figure_settings(),
                width=width,
                scale=SCREEN_SCALE,
                min_width=MIN_ZOOMED_WIDTH if self._zoom < 1.0 else MIN_WIDTH,
                rows=plan,
                baseline=baseline,
                baseline_color=baseline_color,
            )
        except Exception:
            logger.exception("Could not draw the Gantt chart")
            self._show_message("The chart could not be drawn.\n"
                               "See the Log window for details.", "red")
            return

        self._show_image(image)

        if plan is not None:
            self._drawn_rows = [task.id for task in plan.tasks]
            self._drawn_row_height = plan.row_height
            self._drawn_top_margin = plan.top_margin
            self._drawn_selection = {plan.tasks[i].id
                                     for i in plan.selected}
        else:
            self._drawn_rows = []
            self._drawn_selection = set()
        self._drawn_height = image.size[1] / SCREEN_SCALE

        # The canvas was just rebuilt, so it is back at the top while the
        # list beside it is wherever the reader scrolled it - put the chart
        # back on the same row before the difference can be seen (issue #70)
        self._scroll_to_match()

        logger.debug("Drew Gantt chart for %r (%d task(s), %dpx wide)",
                     self.project.name, len(self.project.tasks), width)

    def set_task_list(self, task_list):
        """
        Draw this chart against the rows of a task list.

        PARAMETERS:
        -----------
        task_list : DragDropTaskList
            The grid to the left of the chart.
        """
        self.task_list = task_list
        self._row_offset = None
        task_list.on_rows_changed(self._rows_changed)
        try:
            # The picked row's guide line has to move when the pick does -
            # a redraw that waits a beat, so a keyboard sweep down the
            # list rasterises once rather than once per row passed
            task_list.tree.bind('<<TreeviewSelect>>',
                                self._selection_moved, add='+')
        except tk.TclError:
            pass
        self.draw_chart()

    def _selection_moved(self, _event=None):
        """
        Requeue the guide-line redraw when the list's pick changed.

        DEVELOPMENT NOTES:
        ------------------
        <<TreeviewSelect>> also fires while the list is rebuilt - the
        selection is dropped and put back around every refresh - so the
        draw is held until the event burst has settled, and skipped
        entirely when the pick comes back as the same rows (issue #119).
        """
        try:
            picked = set(self.task_list.get_selected_task_ids())
        except Exception:
            picked = set()
        if picked == self._drawn_selection:
            return
        if self._select_after is not None:
            try:
                self.after_cancel(self._select_after)
            except (tk.TclError, ValueError):
                pass
        try:
            self._select_after = self.after(60, self._selection_settled)
        except tk.TclError:
            self._select_after = None

    def _selection_settled(self):
        """Draw again once the selection has stopped moving (#119)."""
        self._select_after = None
        if not self._drawing:
            self.draw_chart()

    def _rows_changed(self):
        """
        Follow the list: redraw when its rows change, scroll when it does.

        DEVELOPMENT NOTES:
        ------------------
        Folding a branch away takes rows off the list, so the chart is drawn
        again from what is left - otherwise the bars below the fold stayed
        where they were and every one of them was a row out of place.

        A plain scroll changes no rows, so it only moves the chart. Redrawing
        on every scroll step would rasterise the whole plan for each notch of
        the wheel.
        """
        rows = self.task_list.visible_rows() if self.task_list else []
        if rows != self._drawn_rows:
            # _draw_chart_now scrolls to match once it finishes; calling it
            # here as well would run against the canvas about to be replaced
            self.draw_chart()
            return
        self._scroll_to_match()

    def _scroll_to_match(self):
        """
        Put the chart at the row the list has scrolled to.

        DEVELOPMENT NOTES:
        ------------------
        Worked out in rows rather than passed straight through as a
        fraction. The two panes are not the same height and the chart has a
        title and a date axis above its first row, so the same fraction of
        each is not the same row of the plan.

        The scroll is first_row * row_height, and no more: the image's own
        top margin is drawn to sit where the list's heading sits, so a row
        scrolled up by i row-heights still lands the same distance below the
        top of its pane as the row beside it. Taking the margin into the
        scroll as well put every row out by that much the moment the list
        moved - the misalignment issue #70 was raised over.
        """
        if self._chart_canvas is None or not self._drawn_rows:
            return

        try:
            fraction = self.task_list.rows_scrolled_to()
            first_row = round(fraction * len(self._drawn_rows))
            top = first_row * self._drawn_row_height
            height = max(self._drawn_height, 1)
            self._chart_canvas.yview_moveto(max(0.0, top / height))
        except (tk.TclError, AttributeError, ZeroDivisionError):
            logger.debug("Could not scroll the chart to match the task list")

    def _row_plan(self):
        """
        The rows to draw, taken from the task list beside the chart.

        RETURNS:
        --------
        Optional[RowPlan]
            None when there is no task list, or it is showing nothing - the
            chart then chooses its own rows, as it does for an export.

        DEVELOPMENT NOTES:
        ------------------
        The rows are the list's, in the list's order, at the list's row
        height, so the two panes read as one table. Only the top margin is
        the chart's own: it carries a title and a row of dates above the
        first bar, and the list carries a heading above its first row.
        _first_row_offset measures what the list uses so the chart can leave
        the same.
        """
        if self.task_list is None:
            return None

        try:
            visible = self.task_list.visible_rows()
        except Exception:
            logger.exception("Could not read the task list's rows")
            return None

        tasks = [self.project.get_task_by_id(task_id) for task_id in visible]
        tasks = [task for task in tasks if task is not None]
        if not tasks:
            return None

        # Which of the drawn rows the list has picked - the guide line
        # runs across the chart at those bands (issue #119)
        try:
            picked = set(self.task_list.get_selected_task_ids())
        except Exception:
            picked = set()
        selected = tuple(index for index, task in enumerate(tasks)
                         if task.id in picked)

        return RowPlan(
            tasks=tasks,
            row_height=self.task_list.GRID_ROW_HEIGHT,
            top_margin=self._first_row_offset(),
            label_width=0,
            selected=selected,
        )

    def _first_row_offset(self) -> int:
        """
        How far down the chart's first row sits, to match the list's.

        RETURNS:
        --------
        int
            Pixels from the top of the chart image to the top of row one.

        DEVELOPMENT NOTES:
        ------------------
        Measured rather than assumed. The two panes are packed separately -
        the list under a heading of its own, the chart in a canvas - so how
        far each starts from the top of its pane is a matter of what the
        window manager made of them, not of any number written here.

        Measured against chart_frame every time, and never against the
        canvas. The canvas is built afresh by _show_image on every draw, so
        it does not exist for the first one: the offset was taken from the
        frame once and from the canvas afterwards, and the two differ - so
        the rows jumped out of line the moment anything redrew the chart,
        which selecting a task does.

        Measured once, and then kept until the panes are resized. A window
        being built reports positions that go on changing until it settles,
        so measuring afresh on every draw moved the rows about even with the
        right widgets being measured. Nothing is kept until the tree can say
        where its first row actually is, which it can only do once it is on
        screen with rows in it.
        """
        if self._row_offset is not None:
            # Measured once, kept until the panes are resized. Re-measuring
            # on every draw asked a list mid-rebuild where its rows are, and
            # the fallback answer it came back with moved every bar (the
            # broken alignment an ordinary task edit left behind - #70).
            return self._row_offset

        try:
            rows_top, settled = self._task_rows_top()
            frame_top = self.chart_frame.winfo_rooty()
        except (tk.TclError, AttributeError):
            return CHART_TOP_MARGIN

        offset = int(rows_top - frame_top)
        if not settled:
            # Not laid out yet; the chart's own margin stands in, and
            # nothing is remembered
            return CHART_TOP_MARGIN

        # The chart carries a title and a row of dates above its first bar,
        # and they need the room. Where the list's rows begin higher up than
        # that, the two cannot be lined up without drawing bars over the date
        # axis - so the axis keeps its room and the panes go slightly out.
        offset = max(offset, CHART_TOP_MARGIN)

        logger.debug("Chart rows start %dpx down, to match the task list",
                     offset)
        self._row_offset = offset
        return offset

    def _task_rows_top(self):
        """
        Where the task list's first row begins, in screen pixels.

        RETURNS:
        --------
        tuple
            (y, settled). The tree answers bbox for a row only once it is on
            screen, so a box coming back is what says the panes have been
            laid out and the answer is worth keeping.

        The box is relative to the tree, and counts the column heading above
        it. With nothing to ask about the heading is taken to be one row
        tall, which is what ttk draws it as.
        """
        tree = self.task_list.tree
        top = tree.winfo_rooty()

        rows = tree.get_children('')
        if rows:
            box = tree.bbox(rows[0])
            if box:
                return top + int(box[1]), True

        return top + self.task_list.GRID_ROW_HEIGHT, False

    def current_settings(self):
        """
        The appearance settings the chart is drawing with.

        RETURNS:
        --------
        dict
            Every key chart_figure.DEFAULT_SETTINGS names, with whatever has
            been applied on top.

        DEVELOPMENT NOTES:
        ------------------
        The one answer to what the chart looks like. The settings live in two
        places - a dict for most of it and three loose attributes for the
        colours the dialog used to set directly - so they are merged here
        rather than every caller having to know about both.

        The settings dialog seeds itself from this. It used to build its own
        dict instead, taking three colours from the attributes and hardcoding
        the other five, so reopening it showed a font size of 12 and the
        Default theme however the chart had been set - and pressing Apply
        without touching anything wrote those defaults back over what the
        user had chosen.
        """
        # Three layers, each overriding the one before it: what a chart
        # looks like by default, then the colours held on this widget, then
        # whatever was last applied through the settings dialog - which sets
        # both, so the two agree from then on.
        settings = dict(DEFAULT_SETTINGS)
        settings['task_color'] = self.task_color
        settings['milestone_color'] = self.milestone_color
        settings['dependency_color'] = self.dependency_color
        settings['critical_path_color'] = self.critical_path_color
        settings.update(getattr(self, 'chart_settings', {}) or {})
        # The same highlight the task list paints: its toggle answers for
        # the chart too, so the bars go red with the rows and back with them.
        shown = getattr(self.task_list, 'critical_path_rows_shown', None)
        settings['show_critical_path'] = bool(shown and shown())
        return settings

    def _figure_settings(self):
        """
        The settings the on-screen chart is drawn with.

        DEVELOPMENT NOTES:
        ------------------
        The screen and the exports part company here, and deliberately. What
        is drawn in the window follows the light/dark setting like the rest
        of it; what is *written to a file* does not. A PNG or a PDF is shared
        and printed, and a dark chart on paper is a page of ink - so
        export_to_png, export_to_pdf and the HTML export go through
        current_settings and stay light.
        """
        return self.screen_settings()

    def screen_settings(self):
        """
        The chart settings with the appearance applied.

        RETURNS:
        --------
        dict
            current_settings, with the background, the text and the gridlines
            swapped for the ones the window is currently in - unless the user
            has chosen their own.

        DEVELOPMENT NOTES:
        ------------------
        A colour the user picked in View > Settings wins over the theme.
        That is worked out by comparing against the default rather than by
        holding a "has been customised" flag: the settings dialog writes the
        whole block back whenever anything in it is applied, including the
        font size, so a flag would say "customised" the first time somebody
        changed the type size and the chart would stop following the theme
        for a reason nobody could see.
        """
        settings = self.current_settings()

        for key, palette in (('bg_color', theme.CHART_BG),
                             ('text_color', theme.CHART_TEXT),
                             ('grid_color', theme.CHART_GRID),
                             ('header_month_bg', theme.HEADER_MONTH_BG),
                             ('header_cell_bg', theme.HEADER_CELL_BG),
                             ('header_rule', theme.HEADER_RULE),
                             ('header_week_rule', theme.HEADER_WEEK_RULE),
                             ('header_month_text', theme.HEADER_MONTH_TEXT),
                             ('header_day_text', theme.HEADER_DAY_TEXT),
                             ('header_non_working', theme.HEADER_NON_WORKING),
                             ('header_today_bg', theme.HEADER_TODAY_BG),
                             ('header_today_text', theme.HEADER_TODAY_TEXT)):
            # The light half is the default this application ships; anything
            # else in the box is the user's own and is left alone.
            if settings.get(key) == palette[0]:
                settings[key] = theme.now(palette)

        return settings

    def apply_theme(self):
        """
        Redraw for the appearance now in force.

        The canvas holds a picture that was drawn with the old colours in it,
        so nothing about it follows a theme change until it is drawn again.
        """
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
        # A new theme can mean a new heading height in the list, so the
        # measured offset is worth asking for again
        self._row_offset = None
        self.update_chart()

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
        except (tk.TclError, AttributeError) as error:
            # Said rather than swallowed. This is not currently leaking -
            # the Tk image count holds flat across a hundred redraws - and
            # the reason it does is that this call keeps succeeding. A
            # failure here would be invisible and would leak a full-size
            # bitmap per redraw, so it is worth a line in the log.
            logger.warning("Could not delete the previous chart image: %s",
                           error)
        self._photo = None

    def _clear_frame(self):
        """Remove whatever is currently displayed."""
        for widget in self.chart_frame.winfo_children():
            widget.destroy()
        self._image_label = None
        self._chart_canvas = None

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

        # Themed, not left to Tk's default. A bare tk.Frame keeps a fixed
        # grey (a near-black on some builds), and the canvas and the two
        # scrollbars do not cover all of it - the square where they meet, and
        # a hairline round the edges, show the frame itself. Unthemed, that
        # square and border stayed dark after a switch to the light
        # appearance, framing the chart in black. Rebuilt with the chart, so
        # it follows every theme change the redraw already carries.
        container = tk.Frame(self.chart_frame,
                             background=theme.now(theme.CHART_BG))
        container.pack(fill=tk.BOTH, expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        canvas = tk.Canvas(
            container, highlightthickness=0,
            background=self._figure_settings().get(
                'bg_color', theme.now(theme.CHART_BG))
        )
        # The vertical scrollbar drives the task list rather than this
        # canvas: the list's scroll answers back through the row watchers
        # and puts the chart where it belongs, so the two panes read as one
        # table whichever side is dragged (issue #70)
        tree = getattr(getattr(self, 'task_list', None), 'tree', None)
        vertical = ttk.Scrollbar(
            container, orient=tk.VERTICAL,
            command=(tree.yview if tree is not None else canvas.yview))
        horizontal = ttk.Scrollbar(container, orient=tk.HORIZONTAL,
                                   command=canvas.xview)
        # Classic scrollbars on Tk 8.5 take no TScrollbar style; see
        # theme.style_scrollbar
        theme.style_scrollbar(vertical)
        theme.style_scrollbar(horizontal)
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

        self._chart_canvas = canvas
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
                # The list drives: its scroll event reports back through the
                # row watchers and the chart is put where it belongs, so the
                # wheel moves both panes whatever side it landed on (#70)
                tree = getattr(getattr(self, 'task_list', None),
                               'tree', None)
                if tree is not None:
                    tree.yview_scroll(steps, 'units')
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

    def set_active_baseline(self, baseline_manager=None, slot_number=None):
        """Store the active baseline for the Gantt chart and redraw."""
        self._baseline_manager = baseline_manager
        self._baseline_slot = slot_number
        logger.info("Gantt chart active baseline set to slot %s", slot_number)
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
        # current_settings, not the screen's: an exported picture stays light
        # however the window is set. See _figure_settings.
        return export_gantt_to_png(self.project, filepath,
                                   settings=self.current_settings())

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
        # Light, like the PNG - a dark chart on paper is a page of ink
        return export_gantt_to_pdf(self.project, filepath,
                                   settings=self.current_settings())
