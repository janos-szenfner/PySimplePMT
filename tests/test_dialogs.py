"""
Tests for the message boxes and file choosers.

DEVELOPMENT NOTES:
------------------
The platform is stubbed rather than detected, so both branches are covered
wherever the suite runs: the machine building this is not necessarily the one
the behaviour is for. Tk's own dialogs and the external choosers are patched
out - nothing here opens a window that would need dismissing.
"""

import unittest
from unittest import mock

from gantt_app.views import dialogs

from tests import restore_dialogs, stand_dialogs_down


def setUpModule():
    """
    Put the real dialog functions back for this file.

    This is the dialog layer's own test, and the suite stands those functions
    down on import - see tests/__init__.py. Everything here patches the
    internals instead: _show, _run and _chooser, so nothing opens.
    """
    restore_dialogs()


def tearDownModule():
    """Stand them down again for whatever runs next."""
    stand_dialogs_down()



def _display_available() -> bool:
    """Whether a usable Tk display is present."""
    try:
        import tkinter
        root = tkinter.Tk()
    except Exception:
        return False
    root.destroy()
    return True


HAVE_DISPLAY = _display_available()


class TestPlatformRouting(unittest.TestCase):
    """
    Tk is kept where Tk is already native.

    DEVELOPMENT NOTES:
    ------------------
    tkinter.messagebox and tkinter.filedialog call the platform's own dialogs
    on macOS and Windows. Replacing those would be a step backwards, so only
    X11 - where Tk draws its own - is changed.
    """

    def native(self, system):
        """Pretend the application is running on a given windowing system."""
        return mock.patch.object(dialogs, 'windowing_system',
                                 return_value=system)

    def test_macos_uses_tk_message_boxes(self):
        """Tk's box is the macOS box."""
        with self.native('aqua'), \
                mock.patch.object(dialogs, 'tk_messagebox') as tk_mb:
            dialogs.showerror("T", "m")

            self.assertTrue(tk_mb.showerror.called)

    def test_windows_uses_tk_message_boxes(self):
        """Same on Windows."""
        with self.native('win32'), \
                mock.patch.object(dialogs, 'tk_messagebox') as tk_mb:
            dialogs.askyesno("T", "m")

            self.assertTrue(tk_mb.askyesno.called)

    def test_macos_uses_tk_file_dialogs(self):
        """Tk's chooser is the macOS chooser."""
        with self.native('aqua'), \
                mock.patch.object(dialogs, 'tk_filedialog') as tk_fd:
            dialogs.askopenfilename(title="Open")

            self.assertTrue(tk_fd.askopenfilename.called)

    def test_x11_draws_its_own_message_box(self):
        """On X11 Tk's box is Tk's own, so the application draws one."""
        with self.native('x11'), \
                mock.patch.object(dialogs, 'tk_messagebox') as tk_mb, \
                mock.patch.object(dialogs.MessageDialog, 'ask',
                                  return_value=True):
            dialogs.askyesno("T", "m")

            self.assertFalse(tk_mb.askyesno.called)

    def test_an_unknown_system_is_treated_as_x11(self):
        """The conservative answer: it is the only one that changes."""
        with mock.patch.object(dialogs.tk, '_default_root', None):
            self.assertEqual(dialogs.windowing_system(), 'x11')


class TestMessageAnswers(unittest.TestCase):
    """What each question offers and returns on X11."""

    def ask(self, function, **kwargs):
        """Call a message function on X11, capturing the dialog's arguments."""
        with mock.patch.object(dialogs, 'windowing_system',
                               return_value='x11'), \
                mock.patch.object(dialogs.MessageDialog, 'ask') as ask:
            ask.return_value = kwargs.pop('answer', None)
            result = function("Title", "Message", **kwargs)
            return result, ask.call_args[0]

    def test_yes_no_offers_two_buttons(self):
        """No first, so it is what closing the window falls back to."""
        _result, args = self.ask(dialogs.askyesno, answer=True)

        self.assertEqual([label for label, _v in args[4]], ["No", "Yes"])

    def test_yes_no_cancel_offers_three(self):
        """Cancel first, for the same reason."""
        _result, args = self.ask(dialogs.askyesnocancel, answer=None)

        self.assertEqual([label for label, _v in args[4]],
                         ["Cancel", "No", "Yes"])

    def test_yes_returns_true(self):
        """The value comes back unchanged."""
        result, _args = self.ask(dialogs.askyesno, answer=True)

        self.assertIs(result, True)

    def test_cancel_returns_none(self):
        """Distinguishable from No, as tkinter does it."""
        result, _args = self.ask(dialogs.askyesnocancel, answer=None)

        self.assertIsNone(result)

    def test_the_icons_match_the_severity(self):
        """An error is not dressed as a question."""
        for function, icon in ((dialogs.showinfo, dialogs.INFO),
                               (dialogs.showwarning, dialogs.WARNING),
                               (dialogs.showerror, dialogs.ERROR)):
            _result, args = self.ask(function)

            self.assertEqual(args[3], icon)


class TestChooserSelection(unittest.TestCase):
    """Which external chooser is picked, and what it is asked."""

    def x11_with(self, available, desktop=''):
        """Pretend X11 with a given set of tools and desktop."""
        return (
            mock.patch.object(dialogs, 'windowing_system', return_value='x11'),
            mock.patch.object(dialogs.shutil, 'which',
                              side_effect=lambda t: f'/usr/bin/{t}'
                              if t in available else None),
            mock.patch.dict(dialogs.os.environ,
                            {'XDG_CURRENT_DESKTOP': desktop,
                             'KDE_FULL_SESSION': ''}, clear=False),
        )

    def test_gnome_prefers_zenity(self):
        """GTK's chooser on a GTK desktop."""
        patches = self.x11_with({'zenity', 'kdialog'}, 'GNOME')
        with patches[0], patches[1], patches[2]:
            self.assertEqual(dialogs._chooser(), 'zenity')

    def test_kde_prefers_kdialog(self):
        """Qt's chooser on a Qt desktop."""
        patches = self.x11_with({'zenity', 'kdialog'}, 'KDE')
        with patches[0], patches[1], patches[2]:
            self.assertEqual(dialogs._chooser(), 'kdialog')

    def test_whichever_is_installed_is_used(self):
        """Only one present means that one, whatever the desktop."""
        patches = self.x11_with({'kdialog'}, 'GNOME')
        with patches[0], patches[1], patches[2]:
            self.assertEqual(dialogs._chooser(), 'kdialog')

    def test_neither_installed_falls_back_to_tk(self):
        """
        Nothing breaks without them.

        They are a recommendation on the package, not a dependency.
        """
        patches = self.x11_with(set())
        with patches[0], patches[1], patches[2], \
                mock.patch.object(dialogs, 'tk_filedialog') as tk_fd:
            dialogs.askopenfilename(title="Open")

            self.assertTrue(tk_fd.askopenfilename.called)


class TestChooserArguments(unittest.TestCase):
    """The command line each chooser is given."""

    def run_with(self, function, tool='zenity', returns='/tmp/plan.json',
                 **kwargs):
        """Call a chooser on X11 and capture the command."""
        with mock.patch.object(dialogs, 'windowing_system',
                               return_value='x11'), \
                mock.patch.object(dialogs, '_chooser', return_value=tool), \
                mock.patch.object(dialogs, '_run',
                                  return_value=returns) as run:
            result = function(**kwargs)
            return result, run.call_args[0][0]

    def test_saving_asks_before_overwriting(self):
        """The chooser confirms, so the application need not."""
        _result, command = self.run_with(dialogs.asksaveasfilename,
                                         title="Save")

        self.assertIn('--confirm-overwrite', command)

    def test_filters_are_translated(self):
        """Tk's filetypes reach zenity in its own syntax."""
        _result, command = self.run_with(
            dialogs.asksaveasfilename, title="Save",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
        )

        self.assertIn('--file-filter=JSON Files | *.json', command)
        self.assertIn('--file-filter=All Files | *.*', command)

    def test_a_folder_chooser_asks_for_a_directory(self):
        """askdirectory is a different flag, not a different tool."""
        _result, command = self.run_with(dialogs.askdirectory,
                                         returns='/tmp', title="Where")

        self.assertIn('--directory', command)

    def test_kdialog_gets_its_own_filter_syntax(self):
        """Different tool, different spelling."""
        _result, command = self.run_with(
            dialogs.asksaveasfilename, tool='kdialog', title="Save",
            filetypes=[("JSON Files", "*.json")],
        )

        self.assertIn('*.json|JSON Files', command)

    def test_the_default_extension_is_added(self):
        """
        Tk appends it; the external choosers return what was typed.

        A name saved without its extension would have its format guessed
        wrong when it was opened again.
        """
        result, _command = self.run_with(
            dialogs.asksaveasfilename, returns='/tmp/plan',
            defaultextension='.json',
        )

        self.assertEqual(result, '/tmp/plan.json')

    def test_an_existing_extension_is_left_alone(self):
        """No doubling up."""
        result, _command = self.run_with(
            dialogs.asksaveasfilename, returns='/tmp/plan.json',
            defaultextension='.json',
        )

        self.assertEqual(result, '/tmp/plan.json')

    def test_cancelling_returns_an_empty_string(self):
        """Callers test the result for truth, as they do with Tk."""
        result, _command = self.run_with(dialogs.asksaveasfilename,
                                         returns=None)

        self.assertEqual(result, '')


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestMessageDialogWidget(unittest.TestCase):
    """The dialog the application draws for itself."""

    def setUp(self):
        """Build a root window."""
        import customtkinter as ctk

        self.root = ctk.CTk()
        self.root.withdraw()

    def tearDown(self):
        """Tear the root window down."""
        try:
            self.root.destroy()
        except Exception:
            pass

    def dialog(self, buttons=(("No", False), ("Yes", True))):
        """A message dialog over the root window."""
        widget = dialogs.MessageDialog(self.root, "Title", "Message",
                                       dialogs.QUESTION, buttons)
        widget.update_idletasks()
        return widget

    def test_it_builds(self):
        """The window opens with its message."""
        self.assertTrue(self.dialog().winfo_exists())

    def test_choosing_returns_the_value(self):
        """The button's value is what the caller gets."""
        widget = self.dialog()

        widget._choose(True)

        self.assertIs(widget.result, True)

    def test_closing_returns_the_first_option(self):
        """
        Dismissing a question must not read as agreeing to it.

        The first button is the cancelling one in every layout here, so it
        is what closing the window falls back to.
        """
        widget = self.dialog()

        widget._dismiss()

        self.assertIs(widget.result, False)

    def test_it_closes_after_a_choice(self):
        """The dialog goes away once answered."""
        widget = self.dialog()

        widget._choose(True)

        self.assertFalse(widget.winfo_exists())


if __name__ == '__main__':
    unittest.main()
