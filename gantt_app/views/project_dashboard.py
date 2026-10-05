"""
The dashboard as a window frame - a shell around what is drawn in it.

WHAT THIS FILE IS:
==================
The dashboard's drawing - the rows it reads, the four panels, the grid
they are laid out in - lives in utils.boardrender, because the drawing
has to run twice: onto this canvas, and into a Pillow image for PNG/PDF
export. What is left here is the shell: the header strip with the
Panels checklist, the canvas the drawing lands on, the clicks that
maximize a panel, and apply_theme.

The four metric functions and the panel draws are re-exported from
boardrender so every test and caller that already imports them here
keeps working.

DEVELOPMENT NOTES:
------------------
Which panels show is the dashboard's only state. It is handed in as a
list of boardrender panel ids and told back through on_panels_changed
when the checklist changes it; main.py persists it in settings.json,
so the layout is "my dashboard", not something a project file carries
(issue #66).

Maximizing is a mode, not a layout: the same one draw is told to give
one panel the whole canvas, and the clicks that turn it on - the title
glyph and a double-click - are honoured by hit-testing the rectangles
the draw reported.
"""

import tkinter as tk
from typing import Callable, Dict, List, Optional

import customtkinter as ctk

from gantt_app.utils import boardrender
from gantt_app.utils.boardrender import (
    DASHBOARD_PANELS, MAX_PANELS,
    dashboard_rows, duration_by_type, kpi_metrics, weighted_progress,
)
from gantt_app.utils.drawpen import CanvasPen
from gantt_app.utils.log import get_logger
from gantt_app.views import theme

logger = get_logger(__name__)

__all__ = [
    'dashboard_rows', 'duration_by_type', 'kpi_metrics',
    'weighted_progress', 'ProjectDashboardFrame',
    'DASHBOARD_PANELS', 'MAX_PANELS',
]


class ProjectDashboardFrame(ctk.CTkFrame):
    """
    The dashboard shell: a header, a canvas, and which panels are on.

    PARAMETERS:
    -----------
    master : widget
        The pane the dashboard sits in.
    get_project : callable or Project
        Hands the drawing the plan to read. A plain Project is what the
        tests hand in; main.py hands a callable so the frame follows the
        plan the window is currently showing rather than the one it was
        born with.
    enabled_ids : list[str], optional
        The panels to start with; None is all of them. Ids the registry
        does not know are dropped, and the list stops at the four-panel
        cap - the settings a file kept are honoured exactly that far.
    on_panels_changed : callable, optional
        Called with the enabled ids whenever the checklist changes
        them - main.py writes that to the application settings.
    """

    HEADER_H = 34
    #: Below this the canvas is too small for a chart to say anything;
    #: the Configure that follows a real layout draws it then.
    MIN_USEFUL_PX = 240

    def __init__(self, master, get_project: Callable = None,
                 enabled_ids: Optional[List[str]] = None,
                 on_panels_changed: Optional[Callable] = None,
                 **kwargs):
        super().__init__(master, corner_radius=0,
                         fg_color="transparent", **kwargs)

        if callable(get_project):
            self._get_project = get_project
        else:
            self._get_project = (lambda p=get_project: p)
        self._on_panels_changed = on_panels_changed
        self.enabled = boardrender.sanitize_panel_ids(
            enabled_ids if enabled_ids is not None
            else boardrender.all_panel_ids())
        if not self.enabled:
            self.enabled = boardrender.all_panel_ids()
        #: The one panel with the whole board, or None in grid mode.
        self.maximized: Optional[str] = None

        # Where the last draw put each panel and its maximize glyph, so
        # a click can be answered by hit-testing rather than re-laying.
        self._panel_rects: Dict[str, tuple] = {}
        self._glyph_rects: Dict[str, tuple] = {}
        self._escape_bound = False
        self._redraw_pending = False
        #: The size the last Configure reported - see _size for why a
        #: canvas that was never mapped still needs a size to draw at.
        self._last_size = (0, 0)

        self._build_header()

        self.canvas = tk.Canvas(self, bd=0, highlightthickness=0)
        self.canvas.configure(background=theme.now(theme.DASH_BOARD_BG))
        self.canvas.pack(fill='both', expand=True)
        self.canvas.bind('<Configure>', self._on_configure)
        self.canvas.bind('<Button-1>', self._on_click)
        self.canvas.bind('<Double-Button-1>', self._on_double_click)
        self.canvas.bind('<Motion>', self._on_motion)

    # -- the header ----------------------------------------------------------

    def _build_header(self):
        """The thin strip above the canvas: name, Panels list, restore."""
        self.header = ctk.CTkFrame(self, height=self.HEADER_H,
                                   corner_radius=0,
                                   fg_color=theme.pair(theme.HEADER_MONTH_BG))
        self.header.pack(fill='x')
        self.header.pack_propagate(False)

        ctk.CTkLabel(
            self.header, text="Dashboard",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(side='left', padx=(12, 4), pady=4)

        # The Panels checklist - the toggle list issue #66 asks for.
        self.panels_btn = ctk.CTkButton(
            self.header, text="Panels ▾", width=86, height=24,
            font=ctk.CTkFont(size=11), corner_radius=6,
            command=self._panels_menu)
        self.panels_btn.pack(side='left', padx=6, pady=4)

        # While a panel owns the board this brings the grid back; it is
        # only drawn then, because the rest of the time it says nothing.
        self.restore_btn = ctk.CTkButton(
            self.header, text="◱ All panels", width=86, height=24,
            font=ctk.CTkFont(size=11), corner_radius=6,
            command=self.restore)
        # packed lazily in set_maximized

        # The hint that a panel can grow - the affordance nobody finds
        # on their own.
        self.hint_label = ctk.CTkLabel(
            self.header, text="double-click a panel to enlarge it",
            font=ctk.CTkFont(size=10),
            text_color=theme.pair(theme.MUTED_TEXT))
        self.hint_label.pack(side='right', padx=10, pady=4)

    def _panels_menu(self):
        """The checklist of panels, ticked where they show."""
        from gantt_app.views.toolbar import CTkDropdownMenu

        items = []
        for pid, title, _draw in DASHBOARD_PANELS:
            var = ctk.BooleanVar(value=pid in self.enabled)
            items.append({'type': 'toggle', 'text': title,
                          'variable': var,
                          'command': lambda _v, p=pid, vv=var:
                          self._toggle_panel(p, vv)})

        menu = CTkDropdownMenu(self, items=items, opener=self.panels_btn)
        x = self.panels_btn.winfo_rootx()
        y = (self.panels_btn.winfo_rooty()
             + self.panels_btn.winfo_height() + 2)
        menu.geometry(f"+{x}+{y}")
        try:
            menu.lift()
        except tk.TclError:
            pass

    # -- which panels are on --------------------------------------------------

    def _toggle_panel(self, pid: str, var):
        """
        A checklist tick: the panel joins or leaves the board.

        The cap is four and at least one stays - an untick that would
        empty the board or a tick on a full one is answered by ticking
        the row back, which the caller sees as the click not taking.
        """
        if var.get():
            if pid in self.enabled:
                return
            if len(self.enabled) >= MAX_PANELS:
                var.set(False)
                self._note_cap()
                logger.info("Panel %r refused: the dashboard already shows "
                            "%d", pid, MAX_PANELS)
                return
            # Registry order, so the grid does not reshuffle on a tick:
            # the panels list - not the clicking order - decides where
            # each one lands.
            self.enabled = [p for p in boardrender.all_panel_ids()
                            if p in self.enabled or p == pid]
            logger.info("Panel %r enabled; showing %s", pid, self.enabled)
        else:
            if pid not in self.enabled:
                return
            if len(self.enabled) <= 1:
                var.set(True)
                logger.info("Panel %r stays: the dashboard keeps at least "
                            "one panel", pid)
                return
            self.enabled = [p for p in self.enabled if p != pid]
            if self.maximized == pid:
                self.maximized = None
            logger.info("Panel %r disabled; showing %s", pid, self.enabled)
        self._panels_told()
        self.refresh()

    def _note_cap(self):
        """The four-panel cap being reached, said quietly in the header."""
        self.hint_label.configure(
            text=f"a dashboard shows {MAX_PANELS} panels at most")
        self.after(3000, lambda: self.hint_label.configure(
            text="double-click a panel to enlarge it"))

    def _panels_told(self):
        """Hand the new selection to whoever keeps the settings."""
        if self._on_panels_changed:
            try:
                self._on_panels_changed(list(self.enabled))
            except Exception:
                logger.exception("Could not save the panel selection")

    # -- maximize --------------------------------------------------------------

    def set_maximized(self, pid: Optional[str]):
        """One panel owns the board; None gives every panel its cell back."""
        if pid == self.maximized:
            return
        self.maximized = pid if pid in self.enabled else None
        logger.info("Dashboard %s",
                    f"maximized {self.maximized!r}" if self.maximized
                    else "restored to the grid")
        if self.maximized and not self.restore_btn.winfo_ismapped():
            self.restore_btn.pack(side='left', padx=4, pady=4)
        elif not self.maximized:
            self.restore_btn.pack_forget()
        self._bind_escape(bool(self.maximized))
        self.refresh()

    def restore(self):
        """Back to the grid - the restore button's click lands here."""
        self.set_maximized(None)

    def _bind_escape(self, on: bool):
        """Escape leaves a maximized panel; only bound while one is."""
        try:
            top = self.winfo_toplevel()
            if on and not self._escape_bound:
                top.bind('<Escape>', self._on_escape)
                self._escape_bound = True
            elif not on and self._escape_bound:
                top.unbind('<Escape>')
                self._escape_bound = False
        except tk.TclError:
            pass

    def _on_escape(self, _event=None):
        if self.maximized:
            self.restore()
            return 'break'
        return None

    # -- clicks -----------------------------------------------------------------

    def _on_configure(self, event=None):
        """A resize redraws - debounced, and not for a stray pixel."""
        if event is not None:
            if (abs(event.width - self._last_size[0]) < 4
                    and abs(event.height - self._last_size[1]) < 4):
                return
            self._last_size = (event.width, event.height)
        if self._redraw_pending:
            return
        self._redraw_pending = True
        self.after_idle(self._redraw_now)

    def _on_motion(self, event):
        """The pointer over a maximize glyph says so by becoming a hand."""
        for rect in self._glyph_rects.values():
            if rect[0] <= event.x <= rect[2] and rect[1] <= event.y <= rect[3]:
                self.canvas.configure(cursor='hand2')
                return
        self.canvas.configure(cursor='')

    def _panel_at(self, x, y) -> Optional[str]:
        """Which panel's rectangle the point is in, if any."""
        for pid, rect in self._panel_rects.items():
            if rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]:
                return pid
        return None

    def _glyph_at(self, x, y) -> Optional[str]:
        """Which panel's maximize glyph the point is on, if any."""
        for pid, rect in self._glyph_rects.items():
            if rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]:
                return pid
        return None

    def _on_click(self, event):
        """A click on a title glyph grows or restores its panel."""
        pid = self._glyph_at(event.x, event.y)
        if pid is not None:
            self.set_maximized(None if pid == self.maximized else pid)

    def _on_double_click(self, event):
        """A double-click on a panel toggles its maximized state (#66)."""
        pid = self._panel_at(event.x, event.y)
        if pid is not None:
            self.set_maximized(None if pid == self.maximized else pid)
            return 'break'
        return None

    # -- drawing ------------------------------------------------------------------

    def refresh(self):
        """Repaint now - the plan changed, or the panels did."""
        self._redraw_pending = False
        self._redraw_now()

    def _size(self):
        """
        How big the canvas is to draw into.

        DEVELOPMENT NOTES:
        ------------------
        winfo_width answers 1 until Tk has laid the widget out, so two
        things stand in for it: the size the last Configure reported, and
        then the size the canvas was asked for. In the application the
        first of those is the real answer, and the second is what lets
        the drawing be checked without putting a window on somebody's
        screen, since Tk delivers no Configure to a widget that was
        never mapped.
        """
        width, height = (self.canvas.winfo_width(),
                         self.canvas.winfo_height())
        if width > 1 and height > 1:
            return width, height
        if self._last_size[0] > 1 and self._last_size[1] > 1:
            return self._last_size
        return (self.canvas.winfo_reqwidth(),
                self.canvas.winfo_reqheight())

    def _redraw_now(self):
        self._redraw_pending = False
        canvas = self.canvas
        try:
            if not canvas.winfo_exists():
                return
        except tk.TclError:
            return
        canvas.delete('all')
        width, height = self._size()

        canvas.configure(background=theme.now(theme.DASH_BOARD_BG))
        palette = theme.view_palette()
        pen = CanvasPen(canvas)
        pen.rect(0, 0, width, height, fill=palette['bg'])

        if width < self.MIN_USEFUL_PX or height < self.MIN_USEFUL_PX:
            # Still being laid out, or dragged too narrow to read; the
            # Configure that follows draws it.
            logger.debug("Dashboard not drawn at %sx%s; too small",
                         width, height)
            self._panel_rects = {}
            self._glyph_rects = {}
            return

        try:
            rows = dashboard_rows(self._get_project())
            landed = boardrender.render_dashboard(
                pen, rows, palette, self.enabled, self.maximized,
                width=width, height=height)
        except Exception:
            logger.exception("Could not draw the dashboard")
            self._panel_rects = {}
            self._glyph_rects = {}
            return

        self._panel_rects = {p['id']: p['rect'] for p in landed}
        self._glyph_rects = {}
        for panel in landed:
            self._draw_glyph(panel)

    def set_project(self, project):
        """Point the dashboard at a different plan - the old API, kept."""
        self._get_project = (lambda p=project: p)
        self.refresh()

    def _draw_glyph(self, panel):
        """
        The small window icon on a panel's title - the visible way to
        maximize it (double-click is the other, and invisible). Drawn as
        a window outline with a filled title bar; while the panel owns
        the board the same glyph reads as restore.
        """
        x0, y0, x1, y1 = panel['rect']
        gx, gy = x1 - 20, y0 + 6
        colour = theme.now(theme.DASH_TITLE_TEXT)
        # A window: outline with its title bar filled in.
        self.canvas.create_rectangle(gx, gy, gx + 13, gy + 12,
                                     outline=colour, width=1)
        self.canvas.create_rectangle(gx, gy, gx + 13, gy + 3.5,
                                     fill=colour, outline='')
        # A padded hit box - the drawn 13px is small to aim at.
        self._glyph_rects[panel['id']] = (gx - 4, gy - 4,
                                          gx + 17, gy + 16)

    # -- theme -------------------------------------------------------------------

    def apply_theme(self):
        """Re-paint for the appearance that is now in force."""
        self.header.configure(fg_color=theme.pair(theme.HEADER_MONTH_BG))
        self.hint_label.configure(
            text_color=theme.pair(theme.MUTED_TEXT))
        try:
            self.canvas.configure(bg=theme.now(theme.DASH_BOARD_BG))
        except tk.TclError:
            pass
        self.refresh()
