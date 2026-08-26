"""
Shared setup for the test suite.

WHY THIS FILE EXISTS:
=====================
A test that opens a real dialog stops and waits for somebody to click it.
There is nobody to click it on a build machine, so the run hangs until it is
killed - and while it waits, every window the suite goes on to tear down
prints its own pending callbacks to the log, so the first sign of trouble is
pages of noise nowhere near the test that caused it.

That has happened twice. Once from a test that put a window on screen and
waited for it to map, and once from a test of the dependency chooser that
asked it to link to a task that was not there, which is answered with a
prompt. The second one hung the macOS build and buried the Ubuntu one.

So the dialogs are stood down for the whole suite: calling one raises,
naming itself and saying what to do instead. A test that means to exercise
a prompt patches it, which is what the ones that do already did:

    with mock.patch('gantt_app.views.task_list.messagebox.askyesno',
                    return_value=True):
        ...

Patching replaces the raising stub for the length of the test and puts it
back afterwards, so the two arrangements do not fight.

The one file that tests the dialogs themselves says so, and is left alone:

    pytestmark = pytest.mark.real_dialogs
"""

import pytest

from gantt_app.views import dialogs


#: Everything here waits for a person. None of them may run unattended.
BLOCKING = (
    'showinfo', 'showwarning', 'showerror',
    'askyesno', 'askyesnocancel', 'askokcancel',
    'askopenfilename', 'asksaveasfilename', 'askdirectory',
)


class DialogOpenedInATest(RuntimeError):
    """A test asked for a dialog that would wait for somebody to answer."""


def _refuse(name):
    """Build a stand-in for one dialog function."""
    def refusing(*args, **kwargs):
        """Raise rather than wait for a click nobody is there to give."""
        raise DialogOpenedInATest(
            f"dialogs.{name} was called during a test, which would wait for "
            f"somebody to answer it. Patch it for the length of the test - "
            f"mock.patch('<module under test>.messagebox.{name}') - and "
            f"assert on the call instead."
        )
    return refusing


def pytest_configure(config):
    """Register the opt-out, so asking for it is not a warning."""
    config.addinivalue_line(
        "markers",
        "real_dialogs: this test exercises the dialog layer itself, so the "
        "blocking dialogs are left in place. It must not open one.")


@pytest.fixture(autouse=True)
def no_dialogs(request, monkeypatch):
    """Stand every blocking dialog down for the length of each test."""
    if request.node.get_closest_marker('real_dialogs'):
        return
    for name in BLOCKING:
        monkeypatch.setattr(dialogs, name, _refuse(name), raising=True)
