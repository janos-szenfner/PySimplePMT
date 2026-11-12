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
import tkinter.ttk as ttk
from typing import Callable, Dict, List, Optional

import customtkinter as ctk

from gantt_app.utils import boardrender
from gantt_app.utils.boardrender import (
    DASHBOARD_PANELS, MAX_PANELS,
    dashboard_rows, deliverable_rows, duration_by_type, kpi_metrics,
    weighted_progress,
)
from gantt_app.utils.drawpen import CanvasPen
from gantt_app.utils.log import get_logger
from gantt_app.views import theme
from gantt_app.views.boardframe import BoardRedrawMixin

logger = get_logger(__name__)

__all__ = [
    'dashboard_rows', 'deliverable_rows', 'duration_by_type',
    'kpi_metrics', 'weighted_progress', 'ProjectDashboardFrame',
    'DASHBOARD_PANELS', 'MAX_PANELS',
]


class ProjectDashboardFrame(BoardRedrawMixin, ctk.CTkFrame):
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
        # A maximized panel wider than the board draws its restore glyph
        # with the rest of the content - which scrolls it off the screen
        # and out of reach. While that is so the glyph is pinned to the
        # viewport's edge instead; _pinned remembers what to move.
        self._pinned = None
        self._viewport_w = 0
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

        # Shown only while a maximized panel wants more width than the
        # board has - the one place the drawing is wider than the canvas.
        self._hscroll = ttk.Scrollbar(self, orient=tk.HORIZONTAL,
                                      command=self.canvas.xview)
        theme.style_scrollbar(self._hscroll)
        self.canvas.configure(xscrollcommand=self._on_xscroll)
        for seq in ('<MouseWheel>', '<Shift-MouseWheel>',
                    '<Button-4>', '<Button-5>',
                    '<Shift-Button-4>', '<Shift-Button-5>'):
            self.canvas.bind(seq, self._on_wheel, add='+')

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

    def _on_wheel(self, event):
        """
        The wheel pans a maximized panel that outgrew the board.

        Bound only so the scrollbar is not the sole way sideways; it does
        nothing while the drawing fits the canvas, which is all of the
        grid mode and every panel but an overgrown one.
        """
        if not self._hscroll.winfo_ismapped():
            return
        delta = getattr(event, 'delta', 0)
        if delta:
            steps = -1 if delta > 0 else 1
            if abs(delta) >= 120:
                steps = int(-delta / 120)
        else:
            steps = -1 if event.num == 4 else 1
        self.canvas.xview_scroll(steps * 3, 'units')

    def _on_xscroll(self, first, last):
        """
        The canvas's view report: to the scrollbar, and to the pinned
        glyph that has to follow the viewport the scroll just moved.
        """
        self._hscroll.set(first, last)
        self._repin_glyph()

    def _repin_glyph(self):
        """
        Hold the maximized panel's restore glyph on the screen's edge.

        The glyph is drawn with the panel, and a panel wider than the
        board carries it right off the end of the scroll region - an
        enlarged chart the reader then had no handle to close. While the
        board scrolls the glyph is put back where the viewport's right
        edge is, and its hit box moves with it.
        """
        if self._pinned is None:
            return
        pid, items, gy = self._pinned
        try:
            gx = self.canvas.canvasx(0) + self._viewport_w - 20
            rect_item, title_item = items
            self.canvas.coords(rect_item, gx, gy, gx + 13, gy + 12)
            self.canvas.coords(title_item, gx, gy, gx + 13, gy + 3.5)
            self._glyph_rects[pid] = (gx - 4, gy - 4, gx + 17, gy + 16)
        except tk.TclError:
            pass

    def _on_motion(self, event):
        """The pointer over a maximize glyph says so by becoming a hand."""
        x = self.canvas.canvasx(event.x)
        for rect in self._glyph_rects.values():
            if rect[0] <= x <= rect[2] and rect[1] <= event.y <= rect[3]:
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
        pid = self._glyph_at(self.canvas.canvasx(event.x),
                             self.canvas.canvasy(event.y))
        if pid is not None:
            self.set_maximized(None if pid == self.maximized else pid)

    def _on_double_click(self, event):
        """
        A double-click on a panel toggles its maximized state (#66).

        A click arrives before its double does, so a double-click meant
        for the restore glyph has already restored by the time this runs -
        answering the panel under it as well would re-maximize what the
        first click just closed, an enlarged chart that could not be left.
        """
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        if self._glyph_at(x, y) is not None:
            return 'break'
        pid = self._panel_at(x, y)
        if pid is not None:
            self.set_maximized(None if pid == self.maximized else pid)
            return 'break'
        return None

    # -- drawing ------------------------------------------------------------------

    def _on_too_small(self):
        """No picture, no hit-testing: the glyph and panel rects go with it."""
        self._panel_rects = {}
        self._glyph_rects = {}

    def _draw_content(self, width, height):
        """The panels - the board's content; the skeleton lives in the mixin."""
        canvas = self.canvas
        canvas.configure(background=theme.now(theme.DASH_BOARD_BG))
        palette = theme.view_palette()
        pen = CanvasPen(canvas)

        try:
            project = self._get_project()
            rows = dashboard_rows(project)
            # A maximized panel may want more room than the board has -
            # the workload's band-per-row on a long plan. Drawing it at
            # the width it wants and scrolling is what enlarging it is
            # for; squeezing it back into the viewport would draw the
            # same unreadable smear bigger.
            content_w = width
            if self.maximized:
                content_w = boardrender.panel_content_width(
                    self.maximized, rows, width)
            pen.rect(0, 0, content_w, height, fill=palette['bg'])
            landed = boardrender.render_dashboard(
                pen, rows, palette, self.enabled, self.maximized,
                width=content_w, height=height,
                deliverables=boardrender.deliverable_rows(project))
        except Exception:
            # A failed draw must not leave the hit-test rects pointing at
            # a picture that is not there.
            self._panel_rects = {}
            self._glyph_rects = {}
            self._pinned = None
            raise

        # The scrollbar appears only while the drawing is wider than the
        # canvas, and the reader's place survives a redraw that rebuilds
        # the items underneath it.
        keep = canvas.xview()[0] if content_w > width else 0.0
        if content_w > width:
            canvas.configure(scrollregion=(0, 0, content_w, height))
            if not self._hscroll.winfo_ismapped():
                self._hscroll.pack(side='bottom', fill='x')
            canvas.xview_moveto(keep)
        else:
            # Back to a drawing the size of the canvas - the view goes
            # home with it. Tk does not re-clamp the offset when the
            # scroll region shrinks, so a reader who had panned deep into
            # a maximized panel would otherwise restore to empty space
            # past the end of everything.
            canvas.configure(scrollregion='')
            canvas.xview_moveto(0.0)
            self._hscroll.pack_forget()

        self._panel_rects = {p['id']: p['rect'] for p in landed}
        self._glyph_rects = {}
        self._viewport_w = width
        self._pinned = None
        for panel in landed:
            items, gy = self._draw_glyph(panel)
            if content_w > width and panel['id'] == self.maximized:
                self._pinned = (panel['id'], items, gy)
        self._repin_glyph()

    def set_project(self, project):
        """Point the dashboard at a different plan - the old API, kept."""
        self._get_project = (lambda p=project: p)
        self.refresh()

    # -- a footer view's obligations (issue #122) ---------------------------

    def focus_view(self):
        """
        Take the keyboard when the Dashboard tab comes to the top.

        There is no grid to hand it to - the canvas carries the clicks -
        but a view that takes no focus leaves the last view's grid
        answering keystrokes for a window that is no longer showing.
        """
        try:
            self.canvas.focus_force()
        except tk.TclError:
            pass

    def selection_status(self):
        """
        What the status bar says while the Dashboard is on top.

        The board has no selection of its own to describe, so the line
        says what the view is made of - how many of the panels it knows
        are on show.
        """
        return (f"Dashboard - {len(self.enabled)} of "
                f"{len(DASHBOARD_PANELS)} panels shown")

    def _draw_glyph(self, panel):
        """
        The small window icon on a panel's title - the visible way to
        maximize it (double-click is the other, and invisible). Drawn as
        a window outline with a filled title bar; while the panel owns
        the board the same glyph reads as restore.

        Answers the two items it made and where their top sits, so a
        pinned glyph can be slid sideways without being redrawn.
        """
        x0, y0, x1, y1 = panel['rect']
        gx, gy = x1 - 20, y0 + 6
        colour = theme.now(theme.DASH_TITLE_TEXT)
        # A window: outline with its title bar filled in.
        rect_item = self.canvas.create_rectangle(
            gx, gy, gx + 13, gy + 12, outline=colour, width=1)
        title_item = self.canvas.create_rectangle(
            gx, gy, gx + 13, gy + 3.5, fill=colour, outline='')
        # A padded hit box - the drawn 13px is small to aim at.
        self._glyph_rects[panel['id']] = (gx - 4, gy - 4,
                                          gx + 17, gy + 16)
        return (rect_item, title_item), gy

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
