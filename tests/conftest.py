"""
Keeping the tests to one Tk root at a time.

WHY THIS MODULE EXISTS:
======================
Two live Tk roots break the second one. CustomTkinter draws its buttons with
PIL, and an ImageTk.PhotoImage created without a master belongs to whatever
tkinter._default_root points at - which is the *first* root ever made and
stays that way while it lives. A widget in the second root is then handed an
image its own interpreter has never heard of, and Tk answers:

    _tkinter.TclError: image "pyimage28" doesn't exist

Nothing about that message says "two roots", which is why it cost a whole
suite. A run of the tests together failed 464 times on it, spread across
thirty modules that had not been touched - because one module leaving a root
behind poisons every module that runs after it, and the module that broke is
never the module that leaked.

So the leak is closed here, once, rather than trusted to every fixture in
the suite. A test that leaves a root alive gets it cleaned up before the next
one starts.

DEVELOPMENT NOTES:
------------------
Only tkinter._default_root can be found afterwards; Tk keeps no register of
its roots. That is enough in practice - the leaked root is the one that was
made first, and that is exactly the one _default_root holds - and it costs
nothing when a test cleaned up after itself, which is the common case.

The children go first. Destroying a root with a Toplevel still on it leaves
Tk executing ttk::ThemeChanged against an interpreter that has gone, which
prints a Tcl traceback to stderr and tells nobody anything.

This runs under pytest only. The unittest modules tear their own roots down
in tearDown; see run_tests.py for how the two halves of the suite are run.
"""

import tkinter as tk

import pytest


def _shut_down(root) -> None:
    """Take a root down, children first, without raising."""
    try:
        for child in list(root.children.values()):
            try:
                child.destroy()
            except tk.TclError:
                pass
        root.destroy()
    except tk.TclError:
        pass


@pytest.fixture(autouse=True)
def one_tk_root_at_a_time():
    """
    Close any root the test left open, before the next test opens one.

    Autouse: the point is the tests that do not know they need it. A module
    that leaks a root breaks the modules after it and passes itself, so
    asking each of them to opt in would mean the ones that matter never do.
    """
    yield

    root = getattr(tk, '_default_root', None)
    if root is None:
        return

    try:
        alive = bool(root.winfo_exists())
    except (tk.TclError, AttributeError):
        alive = False

    if alive:
        _shut_down(root)

    # Whether it was alive or already half gone, the next root must be the
    # one that PIL binds its images to
    tk._default_root = None
