"""
Tests that the desktop entry and the application agree with each other.

WHY THIS MODULE EXISTS:
======================
The application installed from the .deb showed a generic cog rather than its
own icon. Two things have to line up for a desktop to draw the right one, and
neither of them is exercised by anything that runs the application:

  * the `Icon=` key names an icon that is installed under exactly that name,
    in a directory the icon theme looks in; and
  * `StartupWMClass` matches the WM_CLASS the window actually sets, or the
    desktop cannot tell which entry the running window belongs to and falls
    back to a generic icon in the dock and the switcher whatever the menu
    shows.

The second was wrong: the entry declared `pysimplepmt` while Tk, given no
class name, called every window `Tk` - the same as every other Tk application
on the machine.

DEVELOPMENT NOTES:
------------------
These read the packaged files as text rather than installing anything, so they
run anywhere. What they cannot check - that the files reach the right place
inside the .deb - is checked by the release workflow against the installed
package.
"""

import re
import unittest
from pathlib import Path

PACKAGING = Path(__file__).resolve().parent.parent / 'packaging'
DESKTOP_ENTRY = PACKAGING / 'pysimplepmt.desktop'
BUILD_SCRIPT = PACKAGING / 'build_deb.sh'


def entry_keys():
    """The desktop entry as a dictionary of key to value."""
    found = {}
    for line in DESKTOP_ENTRY.read_text().splitlines():
        if '=' in line and not line.startswith('['):
            key, _, value = line.partition('=')
            found[key.strip()] = value.strip()
    return found


class TestTheDesktopEntry(unittest.TestCase):
    """What the launcher tells the desktop."""

    def setUp(self):
        """Read the entry."""
        self.keys = entry_keys()

    def test_it_names_an_icon_by_a_bare_name(self):
        """
        Not a path.

        The icon theme is keyed by name; a path bypasses the theme, so the
        desktop cannot pick the size it wants and some implementations
        ignore it outright.
        """
        icon = self.keys.get('Icon')

        self.assertEqual(icon, 'pysimplepmt')
        self.assertNotIn('/', icon)
        self.assertFalse(icon.endswith('.png'))

    def test_the_package_installs_that_icon(self):
        """The build writes the name the entry asks for."""
        script = BUILD_SCRIPT.read_text()

        self.assertIn(
            'icons/hicolor/${ICON_SIZE}x${ICON_SIZE}/apps/${PACKAGE_NAME}.png',
            script
        )
        self.assertIn('pixmaps/${PACKAGE_NAME}.png', script)

    def test_it_is_installed_at_every_size_the_theme_asks_for(self):
        """
        One 256 pixel file leaves menus scaling it down themselves.

        The sizes are the ones the hicolor theme declares, so the desktop
        always finds one it does not have to resample.
        """
        script = BUILD_SCRIPT.read_text()
        sizes = re.search(r'ICON_SIZES="([^"]+)"', script).group(1).split()

        self.assertEqual(sizes, ['16', '24', '32', '48', '64', '128', '256'])

    def test_the_build_refuses_to_ship_without_the_icons(self):
        """
        An icon nobody can see is a silent failure otherwise.

        The launcher works, the menu entry appears, and it wears a cog - and
        nothing in the build says why.
        """
        script = BUILD_SCRIPT.read_text()

        self.assertIn('was not written', script)
        self.assertIn('Checking the icons are where the desktop entry will look',
                      script)

    def test_it_depends_on_the_icon_theme(self):
        """
        Without hicolor-icon-theme the directory it installs into is not a
        theme at all, and everything in it is ignored.
        """
        self.assertIn('hicolor-icon-theme', BUILD_SCRIPT.read_text())

    def test_the_categories_are_ones_the_menu_knows(self):
        """An unregistered category can have the entry filed nowhere."""
        categories = self.keys.get('Categories', '').strip(';').split(';')

        self.assertIn('Office', categories)
        for category in categories:
            self.assertTrue(category, "empty category in the list")


class TestTheWindowMatchesItsEntry(unittest.TestCase):
    """
    The half of the icon that has nothing to do with the icon file.

    A desktop shows the dock and switcher icon by matching the window's
    WM_CLASS to a .desktop file. Get that wrong and the menu icon is perfect
    while the running application is a generic cog - which is exactly what
    was happening.
    """

    def test_the_application_sets_a_window_class(self):
        """Rather than leaving it as Tk, which everything else is called."""
        from gantt_app.main import GanttApp

        self.assertEqual(GanttApp.WM_CLASS_NAME, 'pysimplepmt')

    def test_the_entry_declares_the_class_tk_will_produce(self):
        """
        Tk capitalises the class name it is given, so the entry has to name
        the capitalised form. Declaring the lower-case one matches nothing.
        """
        from gantt_app.main import GanttApp

        self.assertEqual(entry_keys().get('StartupWMClass'),
                         GanttApp.WM_CLASS_NAME.capitalize())


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
class TestTheRealWindow(unittest.TestCase):
    """Built for real, because the class name can only be set at construction."""

    def test_the_window_reports_the_declared_class(self):
        """
        Tk takes className when the interpreter is created and never again.

        Setting it afterwards is not possible, so a regression here can only
        be caught by building the window.
        """
        from gantt_app.main import GanttApp

        app = GanttApp()
        app.withdraw()
        app.update_idletasks()
        try:
            self.assertEqual(app.winfo_class(),
                             entry_keys().get('StartupWMClass'))
        finally:
            app.destroy()


if __name__ == '__main__':
    unittest.main()
