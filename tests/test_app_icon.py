"""
Tests for the application icon.

WHY THIS MODULE EXISTS:
======================
The icon is drawn from code rather than shipped as a file, which buys one
property worth protecting: the window, the desktop entry and the packaged
build all come from the same drawing, so they cannot drift apart. That only
holds while the drawing keeps working - and an icon that fails to build is
invisible, since every caller steps over the failure rather than letting it
stop the application.

DEVELOPMENT NOTES:
------------------
The image itself is not compared against a reference: an icon is a drawing
and pinning its pixels would fail on every deliberate change to it. What is
checked is that it builds, at the sizes the desktop asks for, in the colours
it is meant to use, with its corners cut - and that the Tk conversion the
window uses returns something.
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


class TestTheIconIsDrawn(unittest.TestCase):
    """It builds, at every size, and looks like what it claims to be."""

    def test_it_builds_at_the_packaged_sizes(self):
        """Every size the hicolor theme is given in build_deb.sh."""
        from gantt_app.resources.appicon import draw_icon

        for size in (16, 24, 32, 48, 64, 128, 256):
            with self.subTest(size=size):
                image = draw_icon(size)
                self.assertEqual(image.size, (size, size))
                self.assertEqual(image.mode, 'RGBA')

    def test_the_corners_are_cut(self):
        """
        A square icon in a round-cornered world reads as a bug.

        The very corner pixel must be transparent; the middle must not.
        """
        from gantt_app.resources.appicon import draw_icon

        image = draw_icon(128)

        self.assertEqual(image.getpixel((0, 0))[3], 0)
        self.assertEqual(image.getpixel((127, 0))[3], 0)
        self.assertEqual(image.getpixel((64, 64))[3], 255)

    def test_it_is_drawn_in_the_python_colours(self):
        """
        Both blues and both yellows are present.

        The palette is the point: this is an icon for a Python application,
        and the colours are the Python Software Foundation's published ones.
        """
        from gantt_app.resources.appicon import (
            draw_icon, BLUE_DARK, BLUE_LIGHT, YELLOW, YELLOW_LIGHT,
        )

        colours = {colour for _count, colour
                   in draw_icon(256).getcolors(maxcolors=1 << 20)}

        for expected in (BLUE_DARK, BLUE_LIGHT, YELLOW, YELLOW_LIGHT):
            with self.subTest(colour=expected):
                self.assertIn(expected, colours)

    def test_it_is_the_same_drawing_every_time(self):
        """
        Nothing in it depends on the machine it is drawn on.

        A font would: the same script would then produce a different icon
        wherever it was packaged. Every stroke is geometry for that reason.
        """
        from gantt_app.resources.appicon import draw_icon

        self.assertEqual(draw_icon(64).tobytes(), draw_icon(64).tobytes())

    def test_the_packaging_script_draws_the_same_icon(self):
        """
        One drawing, so the packaged icon and the window's cannot differ.

        packaging/make_icon.py used to carry a drawing of its own, which is
        how a project ends up with two icons that are nearly the same.
        """
        from pathlib import Path

        source = (Path(__file__).resolve().parent.parent
                  / 'packaging' / 'make_icon.py').read_text()

        self.assertIn('from gantt_app.resources.appicon import draw_icon',
                      source)


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestTheWindowWearsIt(unittest.TestCase):
    """What the running application does with it."""

    def setUp(self):
        """A root window to hang images off."""
        import tkinter as tk

        self.root = tk.Tk()
        self.root.withdraw()

    def tearDown(self):
        """Tear it down."""
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_it_converts_to_a_tk_image(self):
        """
        Through PNG, or through GIF where Tk is too old to read PNG.

        Tk gained PNG in 8.6. Some macOS system builds still ship 8.5, and an
        icon that only worked on one of them would be missing exactly where
        nobody testing it would notice.
        """
        from gantt_app.resources.appicon import icon_photo

        photo = icon_photo(self.root, 64)

        self.assertIsNotNone(photo)
        self.assertEqual((photo.width(), photo.height()), (64, 64))


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestTheApplicationWindowWearsIt(unittest.TestCase):
    """
    The real window, built as the application builds it.

    DEVELOPMENT NOTES:
    ------------------
    No root window of its own: GanttApp *is* the root, and standing a second
    Tk interpreter up beside it is what makes the toolbar fail to build.
    """

    def test_it_is_set_and_kept(self):
        """
        A reference is held, or Tk collects the image and the window goes
        blank - which is the whole of the bug this guards against.
        """
        from gantt_app.main import GanttApp

        app = GanttApp()
        app.withdraw()
        app.update_idletasks()
        try:
            icon = getattr(app, '_icon', None)
            self.assertIsNotNone(icon)
            self.assertEqual((icon.width(), icon.height()), (64, 64))
        finally:
            app.destroy()


if __name__ == '__main__':
    unittest.main()
