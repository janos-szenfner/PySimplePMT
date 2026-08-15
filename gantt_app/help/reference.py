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

    #: The window currently open, if any. Each subclass keeps its own, so
    #: the editor's reference and the dependency one can both be up at once.
    _open_window = None

    #: Colours, kept close to the task list's palette.
    HEADING_COLOR = '#1f6aa5'
    BODY_COLOR = '#1a1a1a'
    BACKGROUND = '#ffffff'

    def __init__(self, master=None):
        super().__init__(master)

        self.title(self.TITLE)
        self.geometry(self.GEOMETRY)
        self.minsize(*self.MINSIZE)
        if master is not None:
            self.transient(master)
        self.protocol("WM_DELETE_WINDOW", self.close)

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
        self.grid_rowconfigure(0, weight=1)

        frame = ctk.CTkFrame(self)
        frame.grid(row=0, column=0, sticky=tk.NSEW, padx=12, pady=(12, 6))
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        self.text = tk.Text(
            frame, wrap=tk.WORD, relief=tk.FLAT, borderwidth=0,
            padx=18, pady=14, background=self.BACKGROUND,
            foreground=self.BODY_COLOR, highlightthickness=0,
            cursor='arrow',
        )
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL,
                                  command=self.text.yview)
        self.text.configure(yscrollcommand=scrollbar.set)

        self.text.grid(row=0, column=0, sticky=tk.NSEW)
        scrollbar.grid(row=0, column=1, sticky=tk.NS)

        self.text.tag_configure(
            'heading', foreground=self.HEADING_COLOR,
            font=('TkDefaultFont', 13, 'bold'), spacing1=14, spacing3=6,
        )
        self.text.tag_configure(
            'body', font=('TkDefaultFont', 11), spacing1=2, spacing3=8,
            lmargin1=4, lmargin2=4,
        )

        buttons = ctk.CTkFrame(self, fg_color='transparent')
        buttons.grid(row=1, column=0, sticky=tk.EW, padx=12, pady=(0, 12))
        ctk.CTkButton(buttons, text="Close", width=90,
                      command=self.close).pack(side=tk.RIGHT)

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
