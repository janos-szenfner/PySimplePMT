"""
Tests for the hover text on the toolbar buttons.

WHY THIS MODULE EXISTS:
======================
Every icon in the row carried a caption from the beginning and not one of
them was ever shown: the string was set on the button as an attribute and
nothing read it. The row was therefore readable only to whoever drew it, and
a test asserting the attribute existed - there was one - passed the whole
time.

So what is checked here is that the text reaches the screen: that the pointer
resting on a button produces a window with the caption in it, and that moving
away takes it off again.

The binding is the part that is easy to get wrong. A CTkButton is a frame
holding a canvas and a label, so the pointer is never over the button itself;
what makes binding the button work anyway is that CTkButton.bind forwards to
those children. That is what the binding test checks - on the canvas, where
the pointer will be, rather than on the button, where it will not.

It is checked by reading the bindings rather than by generating <Enter>.
Tk does not deliver synthetic crossing events to an unmapped window, and
every window in a test run is withdrawn, so an event-driven version of these
tests would pass by never firing anything.

Nothing here needs the toolbar; a bare button is enough.
"""

import unittest

import customtkinter as ctk

from gantt_app.views.tooltip import Tooltip, attach


class TooltipTestCase(unittest.TestCase):
    """One button, one caption."""

    def setUp(self):
        """A withdrawn window holding a button with hover text."""
        self.root = ctk.CTk()
        self.root.withdraw()
        self.button = ctk.CTkButton(self.root, text="Indent")
        self.button.pack()
        self.tooltip = attach(self.button, "Indent Task")
        self.root.update_idletasks()

    def tearDown(self):
        """Close the window."""
        self.root.destroy()

    def test_attaching_returns_a_tooltip(self):
        """And it holds the text it was given."""
        self.assertIsInstance(self.tooltip, Tooltip)
        self.assertEqual(self.tooltip.text, "Indent Task")

    def test_nothing_is_attached_without_text(self):
        """A caller may pass whatever a table gave it without checking."""
        self.assertIsNone(attach(ctk.CTkButton(self.root, text="x"), ""))

    def test_showing_puts_the_caption_on_screen(self):
        """A real window, with the text in it."""
        self.tooltip._show()
        self.root.update_idletasks()

        self.assertIsNotNone(self.tooltip.window)
        label = self.tooltip.window.winfo_children()[0]
        self.assertEqual(label.cget('text'), "Indent Task")

    def test_leaving_takes_it_away(self):
        """And the window is destroyed rather than left hidden."""
        self.tooltip._show()
        self.root.update_idletasks()
        window = self.tooltip.window

        self.tooltip._on_leave()
        self.root.update_idletasks()

        self.assertIsNone(self.tooltip.window)
        self.assertFalse(window.winfo_exists())

    def test_showing_twice_makes_one_window(self):
        """The pointer re-entering a child must not stack them up."""
        self.tooltip._show()
        first = self.tooltip.window
        self.tooltip._show()

        self.assertIs(self.tooltip.window, first)

    def test_the_pointer_reaches_the_widget_it_will_be_over(self):
        """
        The binding that is easy to miss.

        A CTkButton is a frame holding a canvas and a label, and the pointer
        is over one of those rather than over the button. Binding the button
        works because CTkButton.bind forwards - so the canvas is where the
        binding has to end up, and where this looks for it.
        """
        canvas = self.button.winfo_children()[0]
        bound = canvas.bind()

        for sequence in ('<Enter>', '<Leave>'):
            self.assertIn(sequence, bound, f"{sequence} never reached the canvas")

    def test_the_binding_is_not_doubled(self):
        """
        Walking into winfo_children() as well binds the canvas twice.

        The handler survives being called twice, so nothing visibly breaks -
        which is exactly why it is worth a test rather than a comment.

        Measured against what one plain binding costs rather than against a
        number written here: a CTkButton binds <Enter> for its own hover
        before any of this, and Tk writes several lines of script per
        callback, so neither figure is one this test can know up front.
        """
        button = ctk.CTkButton(self.root, text="Outdent")
        canvas = button.winfo_children()[0]

        def lines():
            return len(canvas.bind('<Enter>').strip().splitlines())

        before = lines()
        attach(button, "Outdent Task")
        after_tooltip = lines()

        button.bind('<Enter>', lambda _event: None, add='+')
        cost_of_one = lines() - after_tooltip

        self.assertEqual(after_tooltip - before, cost_of_one)

    def test_entering_starts_the_clock(self):
        """The caption waits for the pointer to settle before appearing."""
        self.tooltip._on_enter()

        self.assertIsNotNone(self.tooltip._after_id)
        self.assertIsNone(self.tooltip.window,
                          "it should not appear until the delay is up")

    def test_leaving_cancels_a_tooltip_that_had_not_appeared(self):
        """Crossing the row on the way elsewhere stays quiet."""
        self.tooltip._on_enter()
        self.assertIsNotNone(self.tooltip._after_id)

        self.tooltip._on_leave()

        self.assertIsNone(self.tooltip._after_id)
        self.assertIsNone(self.tooltip.window)

    def test_pressing_the_button_takes_the_caption_away(self):
        """
        Hover text over a menu the button just opened would be in the way.

        Bound to <ButtonPress> on the same widget as the hover itself; the
        binding is checked here because a press cannot be delivered to an
        unmapped window either.
        """
        canvas = self.button.winfo_children()[0]

        # Tk stores a ButtonPress binding under its short name
        self.assertIn('<Button>', canvas.bind())

    def test_attaching_again_reuses_the_tooltip(self):
        """
        The day/night control is rebuilt whenever the mode changes.

        Attaching a second time would bind <Enter> again with add='+', so the
        button would gain a binding on every toggle.
        """
        self.button.tooltip_widget = self.tooltip

        again = attach(self.button, "Dark mode")

        self.assertIs(again, self.tooltip)
        self.assertEqual(self.tooltip.text, "Dark mode")

    def test_a_destroyed_widget_does_not_raise(self):
        """A dialog closing under the pointer is not an error."""
        self.button.destroy()

        self.tooltip._show()

        self.assertIsNone(self.tooltip.window)


class ToolbarCaptionsTestCase(unittest.TestCase):
    """That every button on the row actually got one."""

    def setUp(self):
        """A toolbar over an empty plan."""
        from gantt_app.models import Project
        from gantt_app.views.toolbar import IconToolbar

        self.root = ctk.CTk()
        self.root.withdraw()
        self.toolbar = IconToolbar(self.root, Project(name="Demo"))
        self.root.update_idletasks()

    def tearDown(self):
        """Close the window."""
        self.root.destroy()

    def test_every_icon_has_hover_text_on_screen(self):
        """Not merely an attribute nobody reads."""
        for name, button in self.toolbar.icon_buttons.items():
            tooltip = getattr(button, 'tooltip_widget', None)
            self.assertIsInstance(tooltip, Tooltip, name)
            self.assertTrue(tooltip.text.strip(), name)

    def test_the_caption_says_what_the_button_does(self):
        """
        Read from ICON_ACTIONS, so the two cannot drift.

        The row and the captions were separate lists once and drifted the
        first time an icon was added.
        """
        captions = {name: tip for name, tip, _action
                    in self.toolbar.ICON_ACTIONS if tip}

        for name, expected in captions.items():
            self.assertEqual(
                self.toolbar.icon_buttons[name].tooltip_widget.text, expected)


if __name__ == '__main__':
    unittest.main()
