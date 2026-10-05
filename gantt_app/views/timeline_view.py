"""
The timeline as a window frame - a shell around a picked style.

WHAT THIS FILE IS:
==================
The timeline's drawing - which rows it reads, the styles it can wear -
lives in utils.boardrender, because the drawing runs twice: onto this
canvas, and into a Pillow image for PNG/PDF export. What is left here
is the shell: the header strip with the style picker, the canvas, and
apply_theme (issue #83).

A task joins the timeline when its Show in timeline switch is on -
the checkbox finally means what its name says. With nothing flagged,
the board says so rather than drawing an axis over empty space.

DEVELOPMENT NOTES:
------------------
The picked style is the frame's only state. It is handed in as a
boardrender style id and told back through on_style_changed when the
picker changes it; main.py persists it in settings.json, so the look
is "my timeline", not something a project file carries.

The style picker reuses the menu rows with the ✓ gutter - a toggle row
whose variable is a shared BooleanVar does not radio, so the picker
marks the current style in the label and commands set the rest.
"""

import tkinter as tk
from typing import Callable, Optional

import customtkinter as ctk

from gantt_app.utils import boardrender
from gantt_app.utils.drawpen import CanvasPen
from gantt_app.utils.log import get_logger
from gantt_app.views import theme
from gantt_app.views.boardframe import BoardRedrawMixin

logger = get_logger(__name__)


class TimelineFrame(BoardRedrawMixin, ctk.CTkFrame):
    """
    The timeline shell: a header, a canvas, and which style is showing.

    PARAMETERS:
    -----------
    master : widget
        The pane the timeline sits in.
    get_project : callable
        Hands the drawing the plan to read - the same object the rest
        of the window is showing.
    style_id : str, optional
        The style to start with - one of boardrender's TIMELINE_STYLES
        ids. An id the registry does not know starts with the default.
    on_style_changed : callable, optional
        Called with the style id whenever the picker changes it -
        main.py writes that to the application settings.
    """

    HEADER_H = 34
    #: Below this the canvas is too small to say anything; the Configure
    #: that follows a real layout draws it then.
    MIN_USEFUL_PX = 200

    def __init__(self, master, get_project: Callable = None,
                 style_id: Optional[str] = None,
                 on_style_changed: Optional[Callable] = None,
                 **kwargs):
        super().__init__(master, corner_radius=0,
                         fg_color="transparent", **kwargs)

        if callable(get_project):
            self._get_project = get_project
        else:
            self._get_project = (lambda p=get_project: p)
        self._on_style_changed = on_style_changed
        known = boardrender.timeline_style_ids()
        self.style_id = (style_id if style_id in known
                         else boardrender.DEFAULT_TIMELINE_STYLE)
        self._redraw_pending = False
        #: The size the last Configure reported - a canvas that was never
        #: mapped answers winfo 1, so it stands in then (see _size).
        self._last_size = (0, 0)

        self._build_header()

        self.canvas = tk.Canvas(self, bd=0, highlightthickness=0)
        self.canvas.configure(background=theme.now(theme.DASH_BOARD_BG))
        self.canvas.pack(fill='both', expand=True)
        self.canvas.bind('<Configure>', self._on_configure)

    # -- the header ------------------------------------------------------------

    def _build_header(self):
        """The thin strip above the canvas: name, the style picker."""
        self.header = ctk.CTkFrame(self, height=self.HEADER_H,
                                   corner_radius=0,
                                   fg_color=theme.pair(theme.HEADER_MONTH_BG))
        self.header.pack(fill='x')
        self.header.pack_propagate(False)

        ctk.CTkLabel(
            self.header, text="Timeline",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(side='left', padx=(12, 4), pady=4)

        # The style picker - the clickable part of issue #83: the label
        # names the style on show, and the menu swaps it.
        self.style_btn = ctk.CTkButton(
            self.header, width=130, height=24,
            font=ctk.CTkFont(size=11), corner_radius=6,
            command=self._styles_menu)
        self.style_btn.pack(side='left', padx=6, pady=4)
        self._name_the_style()

        ctk.CTkLabel(
            self.header,
            text="rows with “Show in timeline” appear here",
            font=ctk.CTkFont(size=10),
            text_color=theme.pair(theme.MUTED_TEXT),
        ).pack(side='right', padx=10, pady=4)

    def _name_the_style(self):
        """The picker's label reads the style it would change from."""
        label = next(
            (label for sid, label, _d in boardrender.TIMELINE_STYLES
             if sid == self.style_id), self.style_id.title())
        self.style_btn.configure(text=f"Style: {label} ▾")

    def _styles_menu(self):
        """The clickable list of styles - a tick marks the one on show."""
        from gantt_app.views.toolbar import CTkDropdownMenu

        items = []
        for sid, label, _draw in boardrender.TIMELINE_STYLES:
            mark = "✓ " if sid == self.style_id else "   "
            items.append({'type': 'action', 'text': f"{mark}{label}",
                          'command': (lambda s=sid: self.set_style(s))})

        menu = CTkDropdownMenu(self, items=items, opener=self.style_btn)
        x = self.style_btn.winfo_rootx()
        y = (self.style_btn.winfo_rooty()
             + self.style_btn.winfo_height() + 2)
        menu.geometry(f"+{x}+{y}")
        try:
            menu.lift()
        except tk.TclError:
            pass

    # -- the style ------------------------------------------------------------

    def set_style(self, style_id: str):
        """Swap the look - the picker's click lands here."""
        if style_id not in boardrender.timeline_style_ids():
            return
        if style_id == self.style_id:
            return
        self.style_id = style_id
        logger.info("Timeline style changed to %r", style_id)
        self._name_the_style()
        if self._on_style_changed:
            try:
                self._on_style_changed(style_id)
            except Exception:
                logger.exception("Could not save the timeline style")
        self.refresh()

    # -- drawing ------------------------------------------------------------------

    def _draw_content(self, width, height):
        """The picked style - the board's content; the skeleton is the mixin's."""
        self.canvas.configure(background=theme.now(theme.DASH_BOARD_BG))
        try:
            boardrender.render_timeline(
                CanvasPen(self.canvas), self._get_project(), self.style_id,
                theme.view_palette(), width=width, height=height)
        except Exception:
            logger.exception("Could not draw the %r timeline",
                             self.style_id)

    def set_project(self, project):
        """Point the timeline at a different plan - same API as the rest."""
        self._get_project = (lambda p=project: p)
        self.refresh()

    # -- theme -------------------------------------------------------------------

    def apply_theme(self):
        """Re-paint for the appearance that is now in force."""
        self.header.configure(fg_color=theme.pair(theme.HEADER_MONTH_BG))
        try:
            self.canvas.configure(bg=theme.now(theme.DASH_BOARD_BG))
        except tk.TclError:
            pass
        self.refresh()
