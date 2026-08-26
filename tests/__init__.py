"""
Unit tests for the Gantt Project Management Tool.

Run tests with: python3 run_tests.py, or python3 -m unittest discover -s tests

NO TEST MAY OPEN A DIALOG:
==========================
A test that opens one stops and waits for somebody to click it. There is
nobody to click it on a build machine, so the run hangs until it is killed -
and while it waits, every window the suite goes on to tear down prints its
pending callbacks to the log, so the first sign of trouble is pages of noise
nowhere near the test that caused it.

That has happened twice. Once from a test that put a window on screen and
waited for it to map, and once from a test of the dependency chooser that
asked it to link to a task that was not there, which is answered with a
prompt. The second hung the macOS build and buried the Ubuntu one.

So importing this package stands the blocking dialogs down: calling one
raises, names itself, and says what to do instead. A test that means to
exercise a prompt patches it, which is what the ones that do already did:

    with mock.patch('gantt_app.views.task_list.messagebox.askyesno',
                    return_value=True):
        ...

Patching replaces the raising stub for the length of the test and puts it
back afterwards, so the two arrangements do not fight.

Here rather than in a conftest, because conftest.py is pytest's and this
suite is run with unittest - see run_tests.py, which is what the build runs.
A guard that only holds under a runner nobody uses is not a guard, and the
pytest import it needed broke the build outright.

The file that tests the dialogs themselves lifts this for its own length;
see tests.test_dialogs and REAL_DIALOGS below.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gantt_app.views import dialogs  # noqa: E402


#: Everything here waits for a person. None of them may run unattended.
BLOCKING = (
    'showinfo', 'showwarning', 'showerror',
    'askyesno', 'askyesnocancel', 'askokcancel',
    'askopenfilename', 'asksaveasfilename', 'askdirectory',
)

#: The real ones, kept so the dialog layer's own tests can put them back.
REAL_DIALOGS = {name: getattr(dialogs, name) for name in BLOCKING}


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


def stand_dialogs_down():
    """Make every blocking dialog raise instead of opening."""
    for name in BLOCKING:
        setattr(dialogs, name, _refuse(name))


def restore_dialogs():
    """Put the real ones back. For the tests of the dialogs themselves."""
    for name, function in REAL_DIALOGS.items():
        setattr(dialogs, name, function)


stand_dialogs_down()
