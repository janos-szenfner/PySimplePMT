"""
Tests for the parts of a dialog that are neither its data nor its layout.

WHY THIS MODULE EXISTS:
======================
Four separate reports, all of the same kind: a control that is drawn, looks
right in the code, and does nothing.

  * The critical path icon was in the toolbar row, enabled, with nothing
    connected behind it - the handlers were assigned by hand in a list that
    had to mirror the row's own definition, and it drifted the first time an
    icon was added. The same action worked from the menu, which is what makes
    this kind of bug so confusing to report.
  * Cancel in the holiday picker and Recalculate in the critical path window
    were `fg_color='transparent'`, which leaves CustomTkinter's white button
    text on the window's own background: white on white, and invisible.
  * The colour palette and the calendar are separate windows opened over a
    dialog that holds a grab. A grab is exclusive, so neither received a
    single click: no colour could be picked and Close did not close.

None of it is caught by testing what the widgets contain, which is why these
test how they are wired instead.
"""

import unittest


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


class TestEveryIconHasAHandler(unittest.TestCase):
    """
    The toolbar row and the methods behind it cannot drift apart.

    They were two lists maintained by hand, and adding an icon to one and
    forgetting the other produced a button that logged a line and did
    nothing.
    """

    def test_every_action_names_a_method_on_the_toolbar(self):
        """Including the overrides, which are named rather than assumed."""
        from gantt_app.views.toolbar import IconToolbar, Toolbar

        missing = []
        for _icon, _tooltip, action in IconToolbar.ICON_ACTIONS:
            if not action:
                continue                    # a divider
            name = Toolbar.ICON_HANDLER_OVERRIDES.get(action, action)
            if not callable(getattr(Toolbar, name, None)):
                missing.append(f"{action} -> {name}")

        self.assertEqual(missing, [])

    def test_the_critical_path_icon_is_among_them(self):
        """The one that was missing, named so the regression is obvious."""
        from gantt_app.views.toolbar import IconToolbar, Toolbar

        actions = [action for _i, _t, action in IconToolbar.ICON_ACTIONS]

        self.assertIn('show_critical_path', actions)
        self.assertTrue(callable(getattr(Toolbar, 'show_critical_path', None)))


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestTheIconsAreConnectedForReal(unittest.TestCase):
    """Against the built application, which is where the wiring happens."""

    def test_every_icon_reaches_a_handler(self):
        """
        Built, not inspected.

        _connect_icon_toolbar assigns onto the row at runtime, so only a real
        application says whether a button has anything behind it.
        """
        from gantt_app.main import GanttApp

        app = GanttApp()
        app.withdraw()
        app.update_idletasks()
        try:
            row = app.toolbar.icon_toolbar
            missing = [action for _i, _t, action in row.ICON_ACTIONS
                       if action and not callable(getattr(row, action, None))]
            self.assertEqual(missing, [])
        finally:
            app.destroy()


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestSecondaryButtonsAreVisible(unittest.TestCase):
    """
    A quieter button is still a button.

    `fg_color='transparent'` keeps the theme's button text colour, which is
    white because it is meant to sit on the filled blue. On a light window
    that is white on white.
    """

    def setUp(self):
        """A root to build dialogs over."""
        import customtkinter as ctk

        self.root = ctk.CTk()
        self.root.withdraw()

    def tearDown(self):
        """Tear it down."""
        try:
            self.root.destroy()
        except Exception:
            pass

    def buttons(self, widget, found=None):
        """Every CTkButton inside a widget."""
        import customtkinter as ctk

        found = [] if found is None else found
        for child in widget.winfo_children():
            if isinstance(child, ctk.CTkButton):
                found.append(child)
            self.buttons(child, found)
        return found

    def named(self, widget, label):
        """One button by its label."""
        for button in self.buttons(widget):
            if button.cget('text') == label:
                return button
        self.fail(f"no {label!r} button")

    def test_the_holiday_pickers_cancel_is_drawn(self):
        """It was white on white, and read as empty space."""
        from gantt_app.views.holidaydialog import HolidayDialog

        window = HolidayDialog(self.root, [], lambda codes: None)
        window.update_idletasks()

        cancel = self.named(window, "Cancel")
        self.assertNotEqual(cancel.cget('fg_color'), 'transparent')
        self.assertIsNotNone(cancel.cget('text_color'))

    def test_the_critical_path_recalculate_is_drawn(self):
        """The same button in the same state, in the other window."""
        from gantt_app.models import Project
        from gantt_app.views.criticalpath import CriticalPathWindow

        window = CriticalPathWindow(self.root, Project(name="Empty"))
        window.update_idletasks()

        recalculate = self.named(window, "Recalculate")
        self.assertNotEqual(recalculate.cget('fg_color'), 'transparent')
        self.assertIsNotNone(recalculate.cget('text_color'))

    def test_a_secondary_button_differs_from_the_primary_one(self):
        """
        Or the two are equally loud and the wrong one gets pressed.

        Being visible is not the whole requirement: Apply and Cancel side by
        side in the same filled blue is its own problem.
        """
        from gantt_app.views.holidaydialog import HolidayDialog

        window = HolidayDialog(self.root, [], lambda codes: None)
        window.update_idletasks()

        self.assertNotEqual(self.named(window, "Cancel").cget('fg_color'),
                            self.named(window, "Apply").cget('fg_color'))

    def test_it_carries_a_colour_for_each_appearance_mode(self):
        """
        One colour is legible in one mode and not the other.

        CustomTkinter takes a (light, dark) pair, and giving it a single
        value is the same bug with an extra step.
        """
        from gantt_app.views.buttonstyle import (
            SECONDARY_FILL, SECONDARY_TEXT,
        )

        for pair in (SECONDARY_FILL, SECONDARY_TEXT):
            with self.subTest(pair=pair):
                self.assertEqual(len(pair), 2)
                self.assertNotEqual(pair[0], pair[1])


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestAPopupOverADialogGetsItsClicks(unittest.TestCase):
    """
    A grab is exclusive, so a popup has to take it.

    The task form holds one. The colour palette and the calendar are separate
    windows rather than children of it, so without taking the grab they
    received nothing at all - every swatch dead, and Close doing nothing.
    """

    def setUp(self):
        """A root and a dialog that holds a grab."""
        import tkinter as tk

        self.root = tk.Tk()
        self.root.withdraw()
        self.dialog = tk.Toplevel(self.root)
        self.dialog.deiconify()
        self.dialog.update_idletasks()
        try:
            self.dialog.grab_set()
        except tk.TclError:
            self.skipTest("this display will not take a grab")

    def tearDown(self):
        """Tear it down."""
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_the_popup_takes_the_grab(self):
        """Otherwise every click goes to the dialog underneath it."""
        import tkinter as tk
        from gantt_app.views.modal import take_grab

        popup = tk.Toplevel(self.dialog)
        popup.deiconify()
        popup.update_idletasks()

        take_grab(popup)
        popup.update_idletasks()

        self.assertIs(popup.grab_current(), popup)

    def test_it_hands_the_grab_back(self):
        """
        Or the dialog underneath is left non-modal - the same bug one level
        up, and harder to notice.
        """
        import tkinter as tk
        from gantt_app.views.modal import take_grab

        popup = tk.Toplevel(self.dialog)
        popup.deiconify()
        popup.update_idletasks()
        take_grab(popup)
        popup.update_idletasks()

        popup.destroy()
        self.root.update_idletasks()

        self.assertIs(self.dialog.grab_current(), self.dialog)

    def test_a_child_being_destroyed_does_not_hand_it_back(self):
        """
        <Destroy> fires for everything inside the window as well.

        Restoring on a child's teardown would give the grab away while the
        popup was still up, which is the original bug returning by another
        route.
        """
        import tkinter as tk
        from gantt_app.views.modal import take_grab

        popup = tk.Toplevel(self.dialog)
        popup.deiconify()
        inside = tk.Frame(popup)
        inside.pack()
        popup.update_idletasks()
        take_grab(popup)
        popup.update_idletasks()

        inside.destroy()
        self.root.update_idletasks()

        self.assertIs(popup.grab_current(), popup)


class TestThePopupsAskForIt(unittest.TestCase):
    """Both windows that open over the task form take the grab."""

    def test_the_colour_picker_does(self):
        """Read as source: building it needs the form it opens over."""
        import inspect
        from gantt_app.views import colorpicker

        self.assertIn('take_grab',
                      inspect.getsource(colorpicker.ColorPickerPopup.__init__))

    def test_the_calendar_does(self):
        """It has the same shape and had the same bug."""
        import inspect
        from gantt_app.views import datepicker

        self.assertIn('take_grab',
                      inspect.getsource(datepicker.CalendarPopup.__init__))


if __name__ == '__main__':
    unittest.main()
