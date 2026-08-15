"""
Tests for the scrolling container the task form is built in.

WHY THIS MODULE EXISTS:
======================
ScrollFrame replaced CTkScrollableFrame, whose scrollbar forces a full layout
pass of the window on every draw - see gantt_app/views/scrollframe.py. A
replacement for something that worked has to be shown to work, so what the
form actually relies on is checked here: that widgets put in it are inside
the scrolling area, that the region follows the form as it grows, that the
scrollbar comes and goes with the need for it, and that the wheel is given
back when the pointer leaves.

DEVELOPMENT NOTES:
------------------
The module skips without a display; CI provides one through xvfb.
"""

import unittest
import tkinter as tk


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


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class ScrollFrameTestCase(unittest.TestCase):
    """A window with a scrolling frame in it."""

    def setUp(self):
        """Build a root window and a frame to scroll."""
        import customtkinter as ctk
        from gantt_app.views.scrollframe import ScrollFrame

        self.ctk = ctk
        self.root = ctk.CTk()
        self.root.withdraw()
        self.root.geometry("400x200")

        self.frame = ScrollFrame(self.root)
        self.frame.pack(fill=tk.BOTH, expand=True)
        self.root.update_idletasks()

    def tearDown(self):
        """Tear the root window down."""
        try:
            self.root.destroy()
        except Exception:
            pass

    def fill(self, rows):
        """Put that many rows of fields in, as the task form does."""
        for row in range(rows):
            self.ctk.CTkLabel(self.frame.content, text=f"Field {row}:").grid(
                row=row, column=0, sticky=tk.W, pady=5)
            self.ctk.CTkEntry(self.frame.content).grid(
                row=row, column=1, sticky=tk.EW, pady=5)
        self.root.update_idletasks()


class TestWhatItHolds(ScrollFrameTestCase):
    """Widgets go in the scrolling area, not beside it."""

    def test_content_is_inside_the_canvas(self):
        """
        Fields go into content, which the canvas scrolls over.

        Gridding into the ScrollFrame itself would put a field beside the
        scrollbar and outside anything that scrolls.
        """
        self.assertIs(self.frame.content.master, self.frame.canvas)

    def test_the_form_is_as_wide_as_the_canvas(self):
        """
        A field set to stretch has the full width to stretch into.

        The frame inside a canvas sits at its requested width unless it is
        told otherwise, which would leave every field bunched to the left.

        DEVELOPMENT NOTES:
        ------------------
        The resize is fired rather than waited for, and what the canvas was
        told is what is checked. Tk delivers <Configure> from the event
        queue, which update_idletasks does not run, and it re-lays the frame
        inside the canvas out from the same queue - so a test window that is
        never shown reaches neither on its own.
        """
        self.frame.content.columnconfigure(1, weight=1)
        self.fill(2)
        self.frame.canvas.event_generate('<Configure>', width=400, height=200)

        self.assertEqual(
            int(self.frame.canvas.itemcget(self.frame._window, 'width')), 400)


class TestTheScrollbar(ScrollFrameTestCase):
    """
    It appears when there is something to scroll, and not before.

    DEVELOPMENT NOTES:
    ------------------
    Driven through _scrolled, which is what the canvas calls with the slice
    of the form on show. A window that is never mapped has no real height to
    compare a form against - under xvfb the canvas stands at one pixel, so
    two rows overflow it and a form that fits on any desktop looked here as
    though it did not.
    """

    def test_a_form_that_fits_shows_no_scrollbar(self):
        """All of it on show, so nothing to show a scrollbar for."""
        self.frame._scrolled('0.0', '1.0')

        self.assertEqual(self.frame.scrollbar.winfo_manager(), "")

    def test_a_form_that_does_not_fit_shows_one(self):
        """Half of it on show gets a scrollbar beside it."""
        self.frame._scrolled('0.0', '0.5')

        self.assertEqual(self.frame.scrollbar.winfo_manager(), "grid")
        self.assertEqual(int(self.frame.scrollbar.grid_info()['column']), 1)

    def test_it_goes_away_again(self):
        """A form that stops needing one stops showing one."""
        self.frame._scrolled('0.0', '0.5')
        self.frame._scrolled('0.0', '1.0')

        self.assertEqual(self.frame.scrollbar.winfo_manager(), "")

    def test_the_region_follows_the_form(self):
        """
        The canvas scrolls over the whole form, however tall it has grown.

        The region is worked out at the idle moment after a burst of
        resizes, so this is what update_idletasks is settling.
        """
        self.fill(30)
        self.root.update_idletasks()

        region = [int(part) for part in
                  str(self.frame.canvas.cget('scrollregion')).split()]

        self.assertTrue(region, "the canvas was left with no scrollregion")
        self.assertGreaterEqual(region[3],
                                self.frame.content.winfo_reqheight())


class TestTheWheel(ScrollFrameTestCase):
    """It is claimed over the form and given back outside it."""

    def bound(self):
        """Whether anything is bound to the wheel application-wide."""
        return bool(self.frame.canvas.bind_all('<MouseWheel>'))

    def test_it_is_claimed_when_the_pointer_arrives(self):
        """Entering the form binds the wheel to it."""
        self.frame._take_the_wheel()

        self.assertTrue(self.bound())

    def test_it_is_given_back_when_the_pointer_leaves(self):
        """
        Leaving unbinds it, so the chart keeps its own wheel handling.

        The pointer is nowhere near the withdrawn test window, so the check
        _let_go_of_the_wheel makes finds it outside.
        """
        self.frame._take_the_wheel()
        self.frame._let_go_of_the_wheel()

        self.assertFalse(self.bound())

    def test_it_is_given_back_when_the_frame_goes(self):
        """A destroyed form does not leave a binding behind pointing at it."""
        self.frame._take_the_wheel()
        self.frame.destroy()

        self.assertFalse(self.bound())

    def wheel_event(self, **fields):
        """
        A wheel event as one platform or another delivers it.

        DEVELOPMENT NOTES:
        ------------------
        Built rather than generated: <MouseWheel> cannot be fired at a window
        that was never mapped, and what matters here is how a delta is read,
        not how it arrived.
        """
        event = tk.Event()
        for name, value in fields.items():
            setattr(event, name, value)
        return event

    def scrolls(self, event):
        """What _wheel asks the canvas to do with an event."""
        asked = []
        self.frame._scrollable = lambda: True
        self.frame.canvas.yview_scroll = (
            lambda steps, what: asked.append((steps, what))
        )
        self.frame._wheel(event)
        return asked

    def test_a_windows_notch_moves_one_step(self):
        """Windows sends multiples of 120, one notch at a time."""
        self.assertEqual(self.scrolls(self.wheel_event(delta=-120)),
                         [(1, 'units')])

    def test_a_macos_delta_moves_one_step(self):
        """macOS sends small numbers, whose sign is all that is read."""
        self.assertEqual(self.scrolls(self.wheel_event(delta=2)),
                         [(-1, 'units')])

    def test_x11_buttons_move_either_way(self):
        """X11 sends Button-4 for up and Button-5 for down, with no delta."""
        self.assertEqual(self.scrolls(self.wheel_event(delta=0, num=4)),
                         [(-1, 'units')])
        self.assertEqual(self.scrolls(self.wheel_event(delta=0, num=5)),
                         [(1, 'units')])

    def test_a_form_that_fits_does_not_move(self):
        """
        The wheel over a form with nothing to scroll leaves it alone.

        The verdict is supplied rather than measured: an unmapped window has
        no height to hold a form against.
        """
        asked = []
        self.frame._scrollable = lambda: False
        self.frame.canvas.yview_scroll = (
            lambda steps, what: asked.append((steps, what))
        )

        self.frame._wheel(self.wheel_event(delta=-120))

        self.assertEqual(asked, [])


if __name__ == '__main__':
    unittest.main()
