"""
The reference window every Help button opens.

WHY THIS MODULE EXISTS:
======================
There are two reference windows - one behind the Dependency tab's Help
button, one behind the editor's - and they are the same window with different
words in it: a scrolling read-only body, a Close button, and one instance kept
at a time so a repeatedly clicked button does not stack up copies.

Written out twice, the second copy came out subtly wrong: its scrollbar was
packed after a body that had already claimed the whole frame, so it was
squeezed to nothing and the text could not be scrolled at all - which is the
one thing a reference window has to do. Both now share this, so there is one
layout to get right and one place to fix it.

DEVELOPMENT NOTES:
------------------
Subclasses supply nothing but a title, a size and their text. Content is a
plain data structure rather than markup so it stays readable in the source and
can be re-presented elsewhere - a printed sheet, a web page - without
unpicking formatting.

The text is written in the source rather than fetched, so the window works
with no network and nothing to download: the same rule the rest of the
application follows.
"""

import tkinter as tk
from tkinter import ttk

import customtkinter as ctk

from gantt_app import theme
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


class ReferenceWindow(ctk.CTkToplevel):
    """
    A scrollable read-only reference, opened by a Help button.

    PARAMETERS:
    -----------
    master : widget
        The window to open over.

    DEVELOPMENT NOTES:
    ------------------
    Deliberately not modal. It is meant to be read beside the window that
    opened it, so grabbing the pointer would defeat it.

    The body is a tk.Text rather than a label so it scrolls, wraps and can be
    selected and copied. It is disabled after filling, which leaves it
    readable and selectable but not editable.
    """

    #: What the window is called, how big it opens, and how small it goes.
    TITLE = "Help"
    GEOMETRY = "720x640"
    MINSIZE = (480, 360)

    #: The reference text, as (heading, [paragraph, ...]).
    SECTIONS = ()

    #: Whether the window carries a search box across the top.
    #:
    #: Off by default. The two short references behind the editor's and the
    #: dependency tab's Help buttons are a screen or two each and searching
    #: one is slower than reading it; the full guide is thirty sections and
    #: cannot be read that way.
    SEARCHABLE = False

    #: The window currently open, if any. Each subclass keeps its own, so
    #: the editor's reference and the dependency one can both be up at once.
    _open_window = None

    #: Colours, kept close to the task list's palette.
    #:
    #: Resolved to one colour rather than held as (light, dark) pairs,
    #: because the body is a tk.Text - a plain Tk widget, which knows nothing
    #: about appearance modes and takes a single colour. Written as one
    #: colour each, the reference opened as black text on white however dark
    #: the rest of the window was.
    HEADING_COLOR = ('#1f6aa5', '#5aa9e6')
    BODY_COLOR = theme.TEXT
    BACKGROUND = ('#ffffff', '#232529')

    #: What a search hit is painted with.
    MATCH_BG = ('#ffe08a', '#7a5c12')
    CURRENT_MATCH_BG = ('#f59e0b', '#c2410c')

    def __init__(self, master=None):
        super().__init__(master)

        self.title(self.TITLE)
        self.geometry(self.GEOMETRY)
        self.minsize(*self.MINSIZE)
        if master is not None:
            self.transient(master)
        self.protocol("WM_DELETE_WINDOW", self.close)

        #: Where every hit of the current search is, and which one the view
        #: is sitting on. Empty until something is searched for.
        self._matches = []
        self._match_index = 0
        #: What was last searched for. Held rather than read back off the
        #: box, so the status line is right for a caller that searches
        #: directly - which is what the tests do, and what said "no matches"
        #: as an empty string when it should have said the count.
        self._needle = ''

        self._build_ui()
        self._fill()

    @classmethod
    def show(cls, master=None):
        """
        Open the window, or raise the one already open.

        RETURNS:
        --------
        ReferenceWindow
            The visible window, or None when it could not be built.
        """
        existing = cls._open_window
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.deiconify()
                    existing.lift()
                    existing.focus_set()
                    return existing
            except tk.TclError:
                pass

        try:
            cls._open_window = cls(master)
        except tk.TclError:
            logger.exception("Could not open %s", cls.__name__)
            cls._open_window = None
        return cls._open_window

    def _build_ui(self):
        """
        Lay out the text area, its scrollbar and the close button.

        DEVELOPMENT NOTES:
        ------------------
        Laid out with grid rather than pack. A body that fills its frame and a
        scrollbar beside it are two columns of one row, which is what grid
        says; packing them means the body claims the frame and the scrollbar
        is left with whatever is over, which is nothing.
        """
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        if self.SEARCHABLE:
            self._build_search()

        frame = ctk.CTkFrame(self)
        frame.grid(row=1, column=0, sticky=tk.NSEW, padx=12, pady=(12, 6))
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        self.text = tk.Text(
            frame, wrap=tk.WORD, relief=tk.FLAT, borderwidth=0,
            padx=18, pady=14, background=self._colour(self.BACKGROUND),
            foreground=self._colour(self.BODY_COLOR), highlightthickness=0,
            cursor='arrow',
        )
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL,
                                  command=self.text.yview)
        self.text.configure(yscrollcommand=scrollbar.set)

        self.text.grid(row=0, column=0, sticky=tk.NSEW)
        scrollbar.grid(row=0, column=1, sticky=tk.NS)

        self.text.tag_configure(
            'heading', foreground=self._colour(self.HEADING_COLOR),
            font=('TkDefaultFont', 13, 'bold'), spacing1=14, spacing3=6,
        )
        self.text.tag_configure(
            'body', font=('TkDefaultFont', 11), spacing1=2, spacing3=8,
            lmargin1=4, lmargin2=4,
        )
        # Every hit, then the one being looked at on top of it. Configured
        # even when there is no search box, so the tags exist to be cleared.
        self.text.tag_configure('match', background=self._colour(self.MATCH_BG))
        self.text.tag_configure(
            'current_match',
            background=self._colour(self.CURRENT_MATCH_BG),
            foreground=self._colour(('#1a1a1a', '#ffffff')),
        )

        buttons = ctk.CTkFrame(self, fg_color='transparent')
        buttons.grid(row=2, column=0, sticky=tk.EW, padx=12, pady=(0, 12))
        ctk.CTkButton(buttons, text="Close", width=90,
                      command=self.close).pack(side=tk.RIGHT)

    @staticmethod
    def _colour(value):
        """
        One colour from a (light, dark) pair, for a plain Tk widget.

        tk.Text takes a single colour and knows nothing about appearance
        modes, so the half in force is chosen here. A pair handed to it
        straight raises; a single colour written into the class is used in
        both appearances, which is the bug this avoids.
        """
        import customtkinter

        if isinstance(value, str):
            return value
        appearance = str(customtkinter.get_appearance_mode()).lower()
        return theme.resolve(value, appearance)

    # ---- searching -------------------------------------------------------

    def _build_search(self):
        """
        The search box across the top, and the way through the hits.

        DEVELOPMENT NOTES:
        ------------------
        Hits are highlighted where they are rather than the guide being
        filtered down to matching sections. A reference is read for its
        context - the paragraph a number sits in is usually the answer - and
        filtering throws exactly that away.
        """
        bar = ctk.CTkFrame(self, fg_color='transparent')
        bar.grid(row=0, column=0, sticky=tk.EW, padx=12, pady=(12, 0))
        bar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(bar, text="Search:").grid(row=0, column=0, padx=(0, 8))

        self.search_var = ctk.StringVar()
        self.search_var.trace_add('write', self._on_search_typed)
        self.search_entry = ctk.CTkEntry(
            bar, textvariable=self.search_var,
            placeholder_text="Any word or number in the guide...")
        self.search_entry.grid(row=0, column=1, sticky=tk.EW)
        # Enter walks the hits, which is what every other search box does
        self.search_entry.bind('<Return>', lambda _e: self.next_match())
        self.search_entry.bind('<Shift-Return>',
                               lambda _e: self.previous_match())
        self.search_entry.bind('<Escape>', lambda _e: self.clear_search())

        ctk.CTkButton(bar, text="\u2191", width=34,
                      command=self.previous_match).grid(row=0, column=2,
                                                        padx=(8, 0))
        ctk.CTkButton(bar, text="\u2193", width=34,
                      command=self.next_match).grid(row=0, column=3,
                                                    padx=(4, 0))
        ctk.CTkButton(bar, text="Clear", width=60,
                      command=self.clear_search).grid(row=0, column=4,
                                                      padx=(8, 0))

        self.search_status = ctk.CTkLabel(bar, text="", width=90,
                                          anchor=tk.E,
                                          text_color=theme.MUTED_TEXT)
        self.search_status.grid(row=0, column=5, padx=(8, 0))

    def _on_search_typed(self, *_args):
        """Re-run the search as the box is typed in."""
        self.search(self.search_var.get())

    def search(self, needle: str) -> int:
        """
        Highlight every occurrence of a string, and go to the first.

        PARAMETERS:
        -----------
        needle : str
            What to look for. Matched without regard to case, so "float"
            finds "Float", and taken literally, so "2026-08-18" and "5d"
            find themselves rather than being read as patterns.

        RETURNS:
        --------
        int
            How many hits there were.
        """
        self.text.tag_remove('match', '1.0', tk.END)
        self.text.tag_remove('current_match', '1.0', tk.END)
        self._matches = []
        self._match_index = 0

        needle = (needle or '').strip()
        self._needle = needle
        if not needle:
            self._update_search_status()
            return 0

        start = '1.0'
        while True:
            # nocase for a reader who types lower case; exact so a date or a
            # duration is looked for as itself and not as a pattern.
            found = self.text.search(needle, start, stopindex=tk.END,
                                     nocase=True, exact=True)
            if not found:
                break
            end = f"{found}+{len(needle)}c"
            self.text.tag_add('match', found, end)
            self._matches.append((found, end))
            start = end

        if self._matches:
            self._show_match(0)
        self._update_search_status()
        return len(self._matches)

    def _show_match(self, index: int):
        """Move the view to one hit and mark it as the current one."""
        if not self._matches:
            return

        self.text.tag_remove('current_match', '1.0', tk.END)
        self._match_index = index % len(self._matches)
        start, end = self._matches[self._match_index]
        self.text.tag_add('current_match', start, end)
        self.text.see(start)
        self._update_search_status()

    def next_match(self):
        """Go to the hit after the current one, wrapping at the end."""
        if self._matches:
            self._show_match(self._match_index + 1)

    def previous_match(self):
        """Go to the hit before the current one, wrapping at the start."""
        if self._matches:
            self._show_match(self._match_index - 1)

    def clear_search(self):
        """Empty the box and take the highlighting off."""
        if hasattr(self, 'search_var'):
            self.search_var.set('')

    def _update_search_status(self):
        """Say how many hits there are, and which one is showing."""
        status = getattr(self, 'search_status', None)
        if status is None:
            return
        try:
            if not status.winfo_exists():
                return
        except tk.TclError:
            return

        if not self._needle:
            status.configure(text="")
        elif not self._matches:
            status.configure(text="No matches")
        else:
            status.configure(
                text=f"{self._match_index + 1} of {len(self._matches)}")

    def _fill(self):
        """Write the reference text into the body."""
        self.text.configure(state=tk.NORMAL)
        self.text.delete('1.0', tk.END)

        for heading, paragraphs in self.SECTIONS:
            self.text.insert(tk.END, heading + '\n', 'heading')
            for paragraph in paragraphs:
                self.text.insert(tk.END, paragraph + '\n', 'body')

        # Readable and selectable, but not editable
        self.text.configure(state=tk.DISABLED)

    def close(self):
        """Close the window and forget it."""
        if type(self)._open_window is self:
            type(self)._open_window = None
        try:
            self.destroy()
        except tk.TclError:
            pass
