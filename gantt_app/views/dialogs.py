"""
Message boxes and file choosers that look right on the desktop they open on.

WHY THIS MODULE EXISTS:
======================
tkinter.messagebox and tkinter.filedialog are genuinely native on macOS and
Windows: Tk calls the platform's own dialogs. On X11 there are none to call,
so Tk draws its own - the grey, square-cornered boxes and the file browser
with a text field for a path, both unchanged since the nineties. Against a
CustomTkinter window they look like something from another application, and
they ignore the light/dark setting entirely.

So this module keeps Tk where Tk is already native and replaces it only on
X11:

  * message boxes are rebuilt in CustomTkinter, so they match the window
    they interrupt and follow its theme
  * file and folder choosers hand off to zenity or kdialog, which are the
    desktop's own choosers - GTK's on GNOME, Qt's on KDE - and fall back to
    Tk's when neither is installed

DEVELOPMENT NOTES:
------------------
The function names and signatures mirror the two standard modules, so calling
code reads the same and the modules can be swapped in with an import alias
rather than editing every call site.

zenity and kdialog are separate processes, and waiting on one with a plain
subprocess.run would freeze the window behind it: Tk stops redrawing while
the call blocks. The event loop is pumped while waiting instead, so the
application stays alive behind the chooser exactly as it does behind Tk's own.

Neither tool is a dependency. Nothing breaks when they are absent - the .deb
lists zenity only as a recommendation - and both are already present on a
stock GNOME or KDE desktop.
"""

import os
import shutil
import subprocess
import time
import tkinter as tk
from tkinter import filedialog as tk_filedialog
from tkinter import messagebox as tk_messagebox
from typing import Optional, Sequence

import customtkinter as ctk

from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


#: Re-exported so callers can keep passing messagebox.WARNING and friends.
INFO = tk_messagebox.INFO
WARNING = tk_messagebox.WARNING
ERROR = tk_messagebox.ERROR
QUESTION = tk_messagebox.QUESTION

#: How long to wait between pumping the event loop while a chooser is open.
POLL_SECONDS = 0.02

#: The glyph shown beside each kind of message.
ICONS = {
    INFO: ('i', '#1f6aa5'),
    QUESTION: ('?', '#1f6aa5'),
    WARNING: ('!', '#f39c12'),
    ERROR: ('!', '#e74c3c'),
}


def windowing_system(widget=None) -> str:
    """
    Which windowing system Tk is running on.

    RETURNS:
    --------
    str
        'aqua', 'win32' or 'x11'. Falls back to 'x11' when there is no
        window to ask, which is the conservative answer: it is the only one
        where this module changes anything.
    """
    target = widget or getattr(tk, '_default_root', None)
    if target is None:
        return 'x11'
    try:
        return target.tk.call('tk', 'windowingsystem')
    except (tk.TclError, AttributeError):
        return 'x11'


def _is_native(widget=None) -> bool:
    """Whether Tk's own dialogs are already the platform's."""
    return windowing_system(widget) in ('aqua', 'win32')


# ---------------------------------------------------------------------------
# Message boxes
# ---------------------------------------------------------------------------

class MessageDialog(ctk.CTkToplevel):
    """
    A message box drawn with the same toolkit as the rest of the window.

    PARAMETERS:
    -----------
    master : widget
        The window to open over.
    title : str
        Window title.
    message : str
        The body text.
    icon : str
        One of INFO, WARNING, ERROR or QUESTION.
    buttons : Sequence[tuple]
        (label, value) pairs, left to right. The last is the default.

    DEVELOPMENT NOTES:
    ------------------
    Modal by grab, and it waits, so the call returns a value the way
    tkinter.messagebox does and callers need no rewriting.

    The window closing without a choice returns the first button's value,
    which is the cancelling one in every layout here - closing a question
    must never read as saying yes to it.
    """

    def __init__(self, master, title: str, message: str,
                 icon: str = INFO, buttons: Sequence[tuple] = (("OK", True),)):
        super().__init__(master)

        self.result = buttons[0][1]
        self._chosen = False

        self.title(title)
        self.resizable(False, False)
        if master is not None:
            self.transient(master)
        self.protocol("WM_DELETE_WINDOW", self._dismiss)
        self.bind('<Escape>', lambda _e: self._dismiss())

        self._build(message, icon, buttons)
        self._centre(master)

        # Grab after mapping; on X11 grabbing an unmapped window fails
        self.after(10, self._grab)

    def _build(self, message: str, icon: str, buttons: Sequence[tuple]):
        """Lay out the glyph, the text and the buttons."""
        body = ctk.CTkFrame(self, fg_color='transparent')
        body.pack(fill=tk.BOTH, expand=True, padx=20, pady=(20, 10))

        glyph, colour = ICONS.get(icon, ICONS[INFO])
        ctk.CTkLabel(body, text=glyph, width=44, height=44,
                     fg_color=colour, corner_radius=22,
                     text_color='#ffffff',
                     font=ctk.CTkFont(size=22, weight='bold')
                     ).pack(side=tk.LEFT, padx=(0, 16), anchor=tk.N)

        ctk.CTkLabel(body, text=message, justify=tk.LEFT, anchor=tk.W,
                     wraplength=380).pack(side=tk.LEFT, fill=tk.BOTH,
                                          expand=True)

        row = ctk.CTkFrame(self, fg_color='transparent')
        row.pack(fill=tk.X, padx=20, pady=(0, 16))

        # Packed right to left so the list reads left to right on screen,
        # with the default - the last entry - furthest right
        for index, (label, value) in enumerate(reversed(buttons)):
            default = index == 0
            button = ctk.CTkButton(
                row, text=label, width=90,
                fg_color=None if default else '#6b7280',
                hover_color=None if default else '#4b5563',
                command=lambda v=value: self._choose(v),
            )
            button.pack(side=tk.RIGHT, padx=5)
            if default:
                button.focus_set()
                self.bind('<Return>', lambda _e, v=value: self._choose(v))

    def _grab(self):
        """Take the pointer, so the dialog is modal."""
        try:
            self.grab_set()
        except tk.TclError:
            pass

    def _centre(self, master):
        """Open over the middle of the window it interrupts."""
        try:
            self.update_idletasks()
            width, height = self.winfo_width(), self.winfo_height()
            if master is not None and master.winfo_exists():
                x = master.winfo_rootx() + (master.winfo_width() - width) // 2
                y = master.winfo_rooty() + (master.winfo_height() - height) // 3
            else:
                x = (self.winfo_screenwidth() - width) // 2
                y = (self.winfo_screenheight() - height) // 3
            self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        except tk.TclError:
            pass

    def _choose(self, value):
        """Record a choice and close."""
        self.result = value
        self._chosen = True
        self._close()

    def _dismiss(self):
        """Close without choosing; the first button's value stands."""
        self._close()

    def _close(self):
        """Release the grab and go."""
        try:
            self.grab_release()
        except tk.TclError:
            pass
        try:
            self.destroy()
        except tk.TclError:
            pass

    @classmethod
    def ask(cls, master, title, message, icon, buttons):
        """Show the dialog and wait for an answer."""
        dialog = cls(master, title, message, icon, buttons)
        dialog.wait_window()
        return dialog.result


def _show(title, message, icon, buttons, parent=None):
    """Show a message box, native where Tk already is."""
    parent = parent or getattr(tk, '_default_root', None)
    return MessageDialog.ask(parent, title or '', message or '', icon, buttons)


def showinfo(title=None, message=None, **kwargs):
    """Tell the user something."""
    if _is_native(kwargs.get('parent')):
        return tk_messagebox.showinfo(title, message, **kwargs)
    _show(title, message, INFO, (("OK", 'ok'),), kwargs.get('parent'))
    return 'ok'


def showwarning(title=None, message=None, **kwargs):
    """Warn the user about something."""
    if _is_native(kwargs.get('parent')):
        return tk_messagebox.showwarning(title, message, **kwargs)
    _show(title, message, WARNING, (("OK", 'ok'),), kwargs.get('parent'))
    return 'ok'


def showerror(title=None, message=None, **kwargs):
    """Report a failure."""
    if _is_native(kwargs.get('parent')):
        return tk_messagebox.showerror(title, message, **kwargs)
    _show(title, message, ERROR, (("OK", 'ok'),), kwargs.get('parent'))
    return 'ok'


def askyesno(title=None, message=None, **kwargs):
    """Ask a yes or no question. True for yes."""
    if _is_native(kwargs.get('parent')):
        return tk_messagebox.askyesno(title, message, **kwargs)
    icon = kwargs.get('icon', QUESTION)
    return _show(title, message, icon,
                 (("No", False), ("Yes", True)), kwargs.get('parent'))


def askyesnocancel(title=None, message=None, **kwargs):
    """Ask yes, no or cancel. True, False, or None for cancel."""
    if _is_native(kwargs.get('parent')):
        return tk_messagebox.askyesnocancel(title, message, **kwargs)
    icon = kwargs.get('icon', QUESTION)
    return _show(title, message, icon,
                 (("Cancel", None), ("No", False), ("Yes", True)),
                 kwargs.get('parent'))


def askokcancel(title=None, message=None, **kwargs):
    """Ask for confirmation. True for OK."""
    if _is_native(kwargs.get('parent')):
        return tk_messagebox.askokcancel(title, message, **kwargs)
    icon = kwargs.get('icon', QUESTION)
    return _show(title, message, icon,
                 (("Cancel", False), ("OK", True)), kwargs.get('parent'))


# ---------------------------------------------------------------------------
# File and folder choosers
# ---------------------------------------------------------------------------

def _chooser() -> Optional[str]:
    """
    The desktop's own file chooser, if one is installed.

    RETURNS:
    --------
    Optional[str]
        'zenity' or 'kdialog', preferring whichever matches the running
        desktop, or None to leave it to Tk.
    """
    desktop = (os.environ.get('XDG_CURRENT_DESKTOP', '')
               + os.environ.get('KDE_FULL_SESSION', '')).lower()

    order = ('kdialog', 'zenity') if 'kde' in desktop else ('zenity', 'kdialog')
    for tool in order:
        if shutil.which(tool):
            return tool
    return None


def _run(command: Sequence[str], parent=None) -> Optional[str]:
    """
    Run a chooser and wait, keeping the window behind it alive.

    RETURNS:
    --------
    Optional[str]
        What the tool printed, or None when the user cancelled or the tool
        could not be run.

    DEVELOPMENT NOTES:
    ------------------
    subprocess.run would block the Tk event loop, so the window behind the
    chooser would stop redrawing and the desktop would mark it unresponsive.
    Pumping the loop while polling keeps it drawing, which is what happens
    behind Tk's own dialog.
    """
    root = parent or getattr(tk, '_default_root', None)

    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, text=True)
    except (OSError, ValueError):
        logger.exception("Could not start %s", command[0])
        return None

    while process.poll() is None:
        if root is not None:
            try:
                root.update()
            except tk.TclError:
                break
        time.sleep(POLL_SECONDS)

    stdout, _ = process.communicate()
    if process.returncode != 0:
        return None                     # cancelled, or the tool gave up
    return (stdout or '').strip() or None


def _zenity_filters(filetypes) -> list:
    """Turn Tk filetypes into zenity --file-filter arguments."""
    args = []
    for entry in filetypes or ():
        try:
            label, patterns = entry
        except (TypeError, ValueError):
            continue
        if isinstance(patterns, str):
            patterns = [patterns]
        globs = ' '.join(p if '*' in p else f'*{p}' for p in patterns)
        args.append(f'--file-filter={label} | {globs}')
    return args


def _kdialog_filter(filetypes) -> str:
    """Turn Tk filetypes into a kdialog filter string."""
    parts = []
    for entry in filetypes or ():
        try:
            label, patterns = entry
        except (TypeError, ValueError):
            continue
        if isinstance(patterns, str):
            patterns = [patterns]
        globs = ' '.join(p if '*' in p else f'*{p}' for p in patterns)
        parts.append(f'{globs}|{label}')
    return '\n'.join(parts)


def _with_extension(path: Optional[str], defaultextension: str) -> Optional[str]:
    """
    Add the default extension when the chooser did not.

    Tk's save dialog appends defaultextension itself; zenity and kdialog
    return exactly what was typed, so a name entered without one would be
    saved without it and the format guessed wrong on the way back in.
    """
    if not path or not defaultextension:
        return path
    if os.path.splitext(path)[1]:
        return path
    return path + defaultextension


def askopenfilename(**kwargs):
    """Choose an existing file. Returns '' when cancelled, as Tk does."""
    parent = kwargs.get('parent')
    tool = None if _is_native(parent) else _chooser()
    if tool is None:
        return tk_filedialog.askopenfilename(**kwargs)

    title = kwargs.get('title') or "Open"
    filetypes = kwargs.get('filetypes')

    if tool == 'zenity':
        command = ['zenity', '--file-selection', f'--title={title}']
        command += _zenity_filters(filetypes)
    else:
        command = ['kdialog', '--getopenfilename', os.path.expanduser('~'),
                   _kdialog_filter(filetypes), '--title', title]

    return _run(command, parent) or ''


def asksaveasfilename(**kwargs):
    """Choose where to save. Returns '' when cancelled, as Tk does."""
    parent = kwargs.get('parent')
    tool = None if _is_native(parent) else _chooser()
    if tool is None:
        return tk_filedialog.asksaveasfilename(**kwargs)

    title = kwargs.get('title') or "Save As"
    filetypes = kwargs.get('filetypes')
    initial = kwargs.get('initialfile') or ''

    if tool == 'zenity':
        command = ['zenity', '--file-selection', '--save',
                   '--confirm-overwrite', f'--title={title}']
        if initial:
            command.append(f'--filename={initial}')
        command += _zenity_filters(filetypes)
    else:
        command = ['kdialog', '--getsavefilename',
                   initial or os.path.expanduser('~'),
                   _kdialog_filter(filetypes), '--title', title]

    chosen = _run(command, parent)
    return _with_extension(chosen, kwargs.get('defaultextension') or '') or ''


def askdirectory(**kwargs):
    """Choose a folder. Returns '' when cancelled, as Tk does."""
    parent = kwargs.get('parent')
    tool = None if _is_native(parent) else _chooser()
    if tool is None:
        return tk_filedialog.askdirectory(**kwargs)

    title = kwargs.get('title') or "Select Folder"

    if tool == 'zenity':
        command = ['zenity', '--file-selection', '--directory',
                   f'--title={title}']
    else:
        command = ['kdialog', '--getexistingdirectory',
                   os.path.expanduser('~'), '--title', title]

    return _run(command, parent) or ''
