"""
Tests for the theme: who decides light or dark, and the colours that follow.

WHY THIS MODULE EXISTS:
======================
Two things are being pinned down and they fail in different ways.

The *controller* fails loudly: a toggle that does not detach from the system,
a sync that does not reattach, a poll that keeps running after the user has
taken manual control. All of that is testable without a display, because the
controller takes the function that applies the appearance as an argument.

The *palette* fails silently, and worse. A colour written as one string is
used in both appearances by CustomTkinter, so it looks right to whoever wrote
it and is unreadable to half the people who use it. The check for that is
mechanical - every entry is a pair - and mechanical is exactly what it needs
to be, because eyes are what missed it the first time.

DEVELOPMENT NOTES:
------------------
detect_system_appearance is patched throughout. The desktop this runs on has
a setting of its own and the tests must not depend on which.
"""

import unittest
from unittest import mock

from gantt_app import theme


class ThemeControllerTestCase(unittest.TestCase):
    """
    A controller over a desktop this test decides, for the whole test.

    DEVELOPMENT NOTES:
    ------------------
    The patch runs from setUp to cleanup rather than around the construction
    of the controller, and that is the whole point of this class. It used to
    be a `with` block inside a helper that returned the controller - so the
    patch expired as the helper returned, and every later call went to the
    real detector.

    Nothing noticed until CI: sync_with_system re-reads the desktop, so
    test_syncing_gives_the_decision_back passed on a machine whose desktop
    happened to be dark and failed on the light one CI runs. A test that
    depends on the developer's desktop is a test that reports where it ran.

    The fake reads self.desktop each time it is called rather than being
    pinned to one value, so a test can also move the desktop underneath a
    running controller - which is what following the system actually means.
    """

    def setUp(self):
        """Put a fake desktop and a fake settings file in place."""
        self.desktop = 'light'
        self.applied = []

        detector = mock.patch.object(theme, 'detect_system_appearance',
                                     side_effect=lambda: self.desktop)
        detector.start()
        self.addCleanup(detector.stop)

        saver = mock.patch.object(theme, 'save_mode', return_value=True)
        saver.start()
        self.addCleanup(saver.stop)

    def controller(self, desktop='light', mode=theme.MODE_SYSTEM):
        """A controller over a named desktop, recording what it applies."""
        self.desktop = desktop
        return theme.ThemeController(mode=mode, apply=self.applied.append,
                                     persist=False)


class TestTheModes(ThemeControllerTestCase):
    """Following the desktop, or overriding it."""

    def test_system_mode_takes_the_desktop_s_appearance(self):
        """Which is the default, and the whole point of the mode."""
        controller = self.controller(desktop='dark')

        self.assertEqual(controller.mode, theme.MODE_SYSTEM)
        self.assertEqual(controller.appearance, theme.DARK)
        self.assertTrue(controller.following_system)

    def test_an_explicit_mode_ignores_the_desktop(self):
        """A light choice on a dark desktop stays light."""
        controller = self.controller(desktop='dark', mode=theme.MODE_LIGHT)

        self.assertEqual(controller.appearance, theme.LIGHT)
        self.assertFalse(controller.following_system)

    def test_toggling_flips_what_is_on_screen(self):
        """
        Not the mode, which may not be naming an appearance at all.

        Pressing the button while following a dark desktop asks for light -
        a manual light. Read off the mode instead, `system` is neither light
        nor dark and there is nothing to flip.
        """
        controller = self.controller(desktop='dark')

        self.assertEqual(controller.toggle(), theme.LIGHT)

        self.assertEqual(controller.mode, theme.MODE_LIGHT)
        self.assertFalse(controller.following_system)

    def test_toggling_twice_returns_to_the_appearance_but_not_the_mode(self):
        """The user is still in manual control, which is what they asked for."""
        controller = self.controller(desktop='dark')
        controller.toggle()
        controller.toggle()

        self.assertEqual(controller.appearance, theme.DARK)
        self.assertEqual(controller.mode, theme.MODE_DARK)
        self.assertFalse(controller.following_system)

    def test_syncing_gives_the_decision_back(self):
        """And picks up whatever the desktop says now."""
        controller = self.controller(desktop='dark')
        controller.toggle()

        self.assertTrue(controller.sync_with_system())

        self.assertTrue(controller.following_system)
        self.assertEqual(controller.appearance, theme.DARK)

    def test_an_unknown_mode_is_refused(self):
        """Rather than guessed at, which would be a silent theme change."""
        controller = self.controller()

        self.assertFalse(controller.set_mode('sepia'))
        self.assertEqual(controller.mode, theme.MODE_SYSTEM)

    def test_the_appearance_is_applied_only_when_it_changes(self):
        """
        Reapplying it is a full redraw of every widget in the window.

        Choosing 'always dark' while already dark changes who decides, not
        what is on screen.
        """
        controller = self.controller(desktop='dark')
        self.applied.clear()

        controller.set_mode(theme.MODE_DARK)

        self.assertEqual(self.applied, [])


class TestWhatTheControlSays(ThemeControllerTestCase):
    """The caption, the icon, and the status line."""

    def test_it_names_the_appearance_it_is_in(self):
        """A sun labelled Night would be nonsense."""
        self.assertEqual(self.controller('light').button_text(), "Day")
        self.assertEqual(self.controller('dark').button_text(), "Night")

    def test_the_icon_follows_the_appearance(self):
        """Sun by day, moon by night."""
        self.assertEqual(self.controller('light').icon_name(), 'sun')
        self.assertEqual(self.controller('dark').icon_name(), 'moon')

    def test_following_the_system_says_nothing(self):
        """
        The default is the quiet case.

        A permanent "Following system" badge is chrome nobody reads after the
        first day.
        """
        self.assertEqual(self.controller().status_text(), "")

    def test_a_manual_choice_says_so(self):
        """Which is when it is telling the user something they may have forgotten."""
        controller = self.controller('light')
        controller.toggle()

        self.assertIn("Manual", controller.status_text())


class TestFollowingTheDesktop(unittest.TestCase):
    """The poll, and when it is allowed to run."""

    class FakeWidget:
        """A widget that records what was scheduled on it."""

        def __init__(self):
            self.scheduled = []
            self.cancelled = []
            self._next = 0

        def after(self, _ms, callback):
            self._next += 1
            self.scheduled.append((self._next, callback))
            return self._next

        def after_cancel(self, identifier):
            self.cancelled.append(identifier)

    def test_system_mode_schedules_a_poll(self):
        """Or the window never notices the desktop changing."""
        widget = self.FakeWidget()
        with mock.patch.object(theme, 'detect_system_appearance',
                               return_value='light'):
            controller = theme.ThemeController(mode=theme.MODE_SYSTEM,
                                               apply=lambda _a: None,
                                               persist=False)
            controller.start_watching(widget)

        self.assertEqual(len(widget.scheduled), 1)

    def test_an_explicit_mode_schedules_nothing(self):
        """There is nothing for a poll to discover once the user has chosen."""
        widget = self.FakeWidget()
        with mock.patch.object(theme, 'detect_system_appearance',
                               return_value='light'):
            controller = theme.ThemeController(mode=theme.MODE_DARK,
                                               apply=lambda _a: None,
                                               persist=False)
            controller.start_watching(widget)

        self.assertEqual(widget.scheduled, [])

    def test_taking_manual_control_stops_the_poll(self):
        """
        And it is cancelled, not merely left to fire and do nothing.

        A poll that goes on being rescheduled runs `gsettings` in a
        subprocess on Linux for the life of the application.
        """
        widget = self.FakeWidget()
        with mock.patch.object(theme, 'detect_system_appearance',
                               return_value='light'), \
             mock.patch.object(theme, 'save_mode', return_value=True):
            controller = theme.ThemeController(mode=theme.MODE_SYSTEM,
                                               apply=lambda _a: None,
                                               persist=False)
            controller.start_watching(widget)
            controller.toggle()

        self.assertEqual(widget.cancelled, [1])

    def test_syncing_again_starts_it_back_up(self):
        """The window has to resume following the desktop."""
        widget = self.FakeWidget()
        with mock.patch.object(theme, 'detect_system_appearance',
                               return_value='light'), \
             mock.patch.object(theme, 'save_mode', return_value=True):
            controller = theme.ThemeController(mode=theme.MODE_SYSTEM,
                                               apply=lambda _a: None,
                                               persist=False)
            controller.start_watching(widget)
            controller.toggle()
            controller.sync_with_system()

        self.assertEqual(len(widget.scheduled), 2)

    def test_the_window_follows_a_desktop_that_changes(self):
        """The behaviour the whole poll exists for."""
        applied = []
        widget = self.FakeWidget()
        with mock.patch.object(theme, 'detect_system_appearance',
                               return_value='light'):
            controller = theme.ThemeController(mode=theme.MODE_SYSTEM,
                                               apply=applied.append,
                                               persist=False)
            controller.start_watching(widget)

        # The desktop goes dark, and the poll fires
        with mock.patch.object(theme, 'detect_system_appearance',
                               return_value='dark'):
            widget.scheduled[0][1]()

        self.assertEqual(applied, ['dark'])
        self.assertEqual(controller.appearance, theme.DARK)

    def test_a_poll_that_finds_nothing_changes_nothing(self):
        """And still reschedules, or it would only ever follow once."""
        applied = []
        widget = self.FakeWidget()
        with mock.patch.object(theme, 'detect_system_appearance',
                               return_value='light'):
            controller = theme.ThemeController(mode=theme.MODE_SYSTEM,
                                               apply=applied.append,
                                               persist=False)
            controller.start_watching(widget)
            widget.scheduled[0][1]()

        self.assertEqual(applied, [])
        self.assertEqual(len(widget.scheduled), 2)


class TestListeners(unittest.TestCase):
    """Telling the toolbar to redraw its control."""

    def test_a_change_reaches_the_listeners(self):
        """With both halves: the mode and what it resolved to."""
        seen = []
        with mock.patch.object(theme, 'detect_system_appearance',
                               return_value='light'), \
             mock.patch.object(theme, 'save_mode', return_value=True):
            controller = theme.ThemeController(mode=theme.MODE_SYSTEM,
                                               apply=lambda _a: None,
                                               persist=False)
            controller.subscribe(lambda mode, appearance:
                                 seen.append((mode, appearance)))
            controller.toggle()

        self.assertEqual(seen, [(theme.MODE_DARK, theme.DARK)])

    def test_one_failing_listener_does_not_stop_the_rest(self):
        """
        A listener is a widget, and a destroyed widget raises when written to.

        One dead toolbar must not keep the theme from reaching the window.
        """
        seen = []
        with mock.patch.object(theme, 'detect_system_appearance',
                               return_value='light'), \
             mock.patch.object(theme, 'save_mode', return_value=True):
            controller = theme.ThemeController(mode=theme.MODE_SYSTEM,
                                               apply=lambda _a: None,
                                               persist=False)
            controller.subscribe(lambda *_a: (_ for _ in ()).throw(
                RuntimeError("dead widget")))
            controller.subscribe(lambda *_a: seen.append(True))
            controller.toggle()

        self.assertEqual(seen, [True])


class TestThePreference(unittest.TestCase):
    """The choice has to outlive the process."""

    def test_a_saved_mode_is_read_back(self):
        """Which is what makes an override durable."""
        with mock.patch.object(theme, 'settings_directory') as directory:
            import tempfile
            from pathlib import Path
            with tempfile.TemporaryDirectory() as folder:
                directory.return_value = Path(folder)

                self.assertTrue(theme.save_mode(theme.MODE_DARK))
                self.assertEqual(theme.load_mode(), theme.MODE_DARK)

    def test_no_file_means_following_the_system(self):
        """The right default to fall to."""
        with mock.patch.object(theme, 'settings_directory') as directory:
            import tempfile
            from pathlib import Path
            with tempfile.TemporaryDirectory() as folder:
                directory.return_value = Path(folder) / 'nothing-here'

                self.assertEqual(theme.load_mode(), theme.MODE_SYSTEM)

    def test_an_unreadable_preference_is_not_fatal(self):
        """A preference is not worth failing to start over."""
        with mock.patch.object(theme, 'settings_directory') as directory:
            import tempfile
            from pathlib import Path
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder)
                directory.return_value = path
                (path / theme.SETTINGS_FILE).write_text('not json at all')

                self.assertEqual(theme.load_mode(), theme.MODE_SYSTEM)

    def test_a_mode_this_version_does_not_know_is_ignored(self):
        """Rather than set, which would be an unreachable state."""
        with mock.patch.object(theme, 'settings_directory') as directory:
            import tempfile
            import json
            from pathlib import Path
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder)
                directory.return_value = path
                (path / theme.SETTINGS_FILE).write_text(
                    json.dumps({'theme_mode': 'sepia'}))

                self.assertEqual(theme.load_mode(), theme.MODE_SYSTEM)

    def test_a_stand_in_controller_never_writes(self):
        """
        Or running the test suite changes the preference of whoever ran it.

        A toolbar built without a controller makes one of its own. That
        controller belongs to nobody, and it used to write every mode change
        to the user's real settings file - so a test that toggled the theme
        left the application pinned to whatever it had toggled to.
        """
        with mock.patch.object(theme, 'save_mode') as saver, \
             mock.patch.object(theme, 'detect_system_appearance',
                               return_value='light'):
            controller = theme.ThemeController(apply=lambda _a: None,
                                               persist=False)
            controller.toggle()
            controller.sync_with_system()

        saver.assert_not_called()

    def test_an_owned_controller_does_write(self):
        """The preference is durable for the application that owns one."""
        with mock.patch.object(theme, 'save_mode') as saver, \
             mock.patch.object(theme, 'detect_system_appearance',
                               return_value='light'):
            controller = theme.ThemeController(apply=lambda _a: None)
            controller.toggle()

        saver.assert_called_once_with(theme.MODE_DARK)

    def test_an_unwritable_directory_does_not_raise(self):
        """The theme still works for this run; it just is not remembered."""
        with mock.patch.object(theme, 'settings_directory') as directory:
            from pathlib import Path
            directory.return_value = Path('/proc/nowhere/PySimplePMT')

            self.assertFalse(theme.save_mode(theme.MODE_DARK))


class TestThePaletteIsAlwaysAPair(unittest.TestCase):
    """
    The failure that eyes miss.

    A colour written as one string is used in *both* appearances, so it reads
    perfectly to whoever wrote it and is unreadable to half the people who
    use it - which is exactly how the task form came to have near-black
    labels on a near-black panel.
    """

    #: Every colour the palette offers, by name.
    PALETTE = (
        'TEXT', 'MUTED_TEXT', 'WARNING_TEXT', 'FIELD_BG', 'FIELD_TEXT',
        'FIELD_BG_DISABLED', 'FIELD_TEXT_DISABLED', 'SEPARATOR', 'ROW_BG',
        'POSITIVE_TEXT', 'NEGATIVE_TEXT', 'MENU_BG', 'MENU_HOVER',
        'MENU_TEXT', 'DROPDOWN_BG', 'ICON_SEPARATOR',
        'GRID_ROW_BG', 'GRID_ROW_ALT', 'GRID_HEADING_BG', 'GRID_TEXT',
        'GRID_LINE', 'GRID_SELECT_BG', 'GRID_CUT_TEXT', 'GRID_CRITICAL_BG',
        'GRID_TIGHT_BG', 'CHART_BG', 'CHART_TEXT', 'CHART_GRID',
        'HEADER_MONTH_BG', 'HEADER_CELL_BG', 'HEADER_RULE',
        'HEADER_WEEK_RULE', 'HEADER_MONTH_TEXT', 'HEADER_DAY_TEXT',
        'HEADER_NON_WORKING', 'HEADER_TODAY_BG', 'HEADER_TODAY_TEXT',
    )

    def test_the_list_covers_every_pair_in_the_module(self):
        """
        Or a colour added later is never checked.

        The guard is only worth having while it is complete, and a pair
        added without being listed here is exactly the colour that will be
        wrong in one appearance.
        """
        declared = {
            name for name in dir(theme)
            if name.isupper() and isinstance(getattr(theme, name), tuple)
            and len(getattr(theme, name)) == 2
            and all(isinstance(half, str) for half in getattr(theme, name))
        }

        self.assertEqual(declared - set(self.PALETTE), set())

    def test_every_entry_has_two_halves(self):
        """One colour is legible in one mode and not the other."""
        for name in self.PALETTE:
            colour = getattr(theme, name)
            self.assertIsInstance(colour, tuple, name)
            self.assertEqual(len(colour), 2, name)

    def test_the_two_halves_differ(self):
        """A pair of identical colours is a single colour with extra steps."""
        for name in self.PALETTE:
            light, dark = getattr(theme, name)
            self.assertNotEqual(light, dark, name)

    def test_every_half_is_a_colour(self):
        """Catches a stray label or None finding its way in."""
        for name in self.PALETTE:
            for half in getattr(theme, name):
                self.assertRegex(half, r'^#[0-9a-fA-F]{6}$', name)

    def test_pair_refuses_a_single_colour(self):
        """The guard that says why, rather than failing in dark mode."""
        with self.assertRaises(TypeError):
            theme.pair('#ffffff')

    def test_resolve_picks_the_right_half(self):
        """For the places that need a colour rather than a pair."""
        self.assertEqual(theme.resolve(theme.TEXT, theme.LIGHT),
                         theme.TEXT[0])
        self.assertEqual(theme.resolve(theme.TEXT, theme.DARK),
                         theme.TEXT[1])


class TestTheDarkPaletteIsReadable(unittest.TestCase):
    """
    Contrast, measured rather than eyeballed.

    The point of the dark appearance is that it is *readable*, and the way
    that was got wrong before was by nobody checking.
    """

    @staticmethod
    def contrast(first: str, second: str) -> float:
        """The WCAG contrast ratio between two hex colours."""
        def luminance(value):
            value = value.lstrip('#')
            channels = [int(value[i:i + 2], 16) / 255 for i in (0, 2, 4)]
            adjusted = [c / 12.92 if c <= 0.03928
                        else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
            return (0.2126 * adjusted[0] + 0.7152 * adjusted[1]
                    + 0.0722 * adjusted[2])

        high, low = sorted((luminance(first), luminance(second)),
                           reverse=True)
        return (high + 0.05) / (low + 0.05)

    #: (text, background) pairs that a reader has to be able to read, and
    #: the ratio each must clear. 4.5 is WCAG AA for body text.
    READABLE = (
        ('GRID_TEXT', 'GRID_ROW_BG', 4.5),
        ('GRID_TEXT', 'GRID_ROW_ALT', 4.5),
        ('GRID_TEXT', 'GRID_HEADING_BG', 4.5),
        ('GRID_TEXT', 'GRID_SELECT_BG', 4.5),
        ('GRID_TEXT', 'GRID_CRITICAL_BG', 4.5),
        ('GRID_TEXT', 'GRID_TIGHT_BG', 4.5),
        ('CHART_TEXT', 'CHART_BG', 4.5),
        ('HEADER_DAY_TEXT', 'HEADER_CELL_BG', 4.5),
        ('HEADER_DAY_TEXT', 'HEADER_NON_WORKING', 4.5),
        ('HEADER_MONTH_TEXT', 'HEADER_MONTH_BG', 4.5),
        ('HEADER_TODAY_TEXT', 'HEADER_TODAY_BG', 4.5),
        ('FIELD_TEXT', 'FIELD_BG', 4.5),
        ('FIELD_TEXT', 'DROPDOWN_BG', 4.5),
        ('MUTED_TEXT', 'DROPDOWN_BG', 4.5),
        ('WARNING_TEXT', 'DROPDOWN_BG', 4.5),
        ('MENU_TEXT', 'MENU_BG', 4.5),
        ('POSITIVE_TEXT', 'ROW_BG', 4.5),
        ('NEGATIVE_TEXT', 'ROW_BG', 4.5),
    )

    def test_both_appearances_are_readable(self):
        """Light was; dark has to be too, which is the whole exercise."""
        failures = []
        for index, appearance in ((0, 'light'), (1, 'dark')):
            for text_name, background_name, wanted in self.READABLE:
                text = getattr(theme, text_name)[index]
                background = getattr(theme, background_name)[index]
                ratio = self.contrast(text, background)
                if ratio < wanted:
                    failures.append(
                        f"{appearance}: {text_name} on {background_name} "
                        f"is {ratio:.2f}, wanted {wanted}")

        self.assertEqual(failures, [])

    def test_a_disabled_field_is_visibly_quieter(self):
        """
        It has to read as "not yours to fill in" without being invisible.

        Deliberately below the body-text ratio - that is what makes it look
        inactive - but not so far below that it cannot be read at all.
        """
        for index, appearance in ((0, 'light'), (1, 'dark')):
            ratio = self.contrast(theme.FIELD_TEXT_DISABLED[index],
                                  theme.FIELD_BG_DISABLED[index])
            live = self.contrast(theme.FIELD_TEXT[index],
                                 theme.FIELD_BG[index])
            self.assertLess(ratio, live, appearance)
            self.assertGreater(ratio, 2.0, appearance)


class TestTheDrawnIcons(unittest.TestCase):
    """The sun and the moon, drawn rather than fetched."""

    def test_both_are_drawn(self):
        """Nothing is bundled, so nothing can be missing at runtime."""
        from gantt_app.resources.icons import draw_icon

        for name in ('sun', 'moon'):
            icon = draw_icon(name, size=20)
            self.assertIsNotNone(icon, name)
            self.assertEqual(icon.size, (20, 20), name)

    def test_they_are_drawn_in_the_ink_asked_for(self):
        """
        Two drawings per icon is what makes them visible in both appearances.

        Handed the same near-black drawing for both, every icon on the bar
        disappeared into the toolbar the moment the window went dark.
        """
        from gantt_app.resources.icons import draw_icon

        light = draw_icon('sun', size=20, color=theme.ICON_INK_LIGHT)
        dark = draw_icon('sun', size=20, color=theme.ICON_INK_DARK)

        self.assertNotEqual(list(light.getdata()), list(dark.getdata()))

    def test_the_moon_is_a_crescent(self):
        """
        A disc with a bite out of it, not a disc.

        The bite is taken by writing transparent pixels over the disc, which
        is the only way to get a crescent with no arc primitive - and it is
        the kind of thing that silently becomes a full circle.
        """
        from gantt_app.resources.icons import draw_icon

        moon = draw_icon('moon', size=40, color=(0, 0, 0))
        disc = draw_icon('sun', size=40, color=(0, 0, 0))
        opaque = lambda image: sum(1 for pixel in image.getdata()
                                   if pixel[3] > 128)

        # A crescent covers less than the disc it was cut from, and is not
        # empty either - both of which a broken cut-out would break.
        self.assertGreater(opaque(moon), 0)
        self.assertLess(opaque(moon), 40 * 40 * 0.5)
        self.assertGreater(opaque(moon), opaque(disc) * 0.3)


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
class TestTheToolbarControl(unittest.TestCase):
    """The sun/moon button, and the way back to the desktop."""

    def setUp(self):
        """A toolbar over a controller with a known desktop."""
        import customtkinter as ctk
        from gantt_app.models import Project
        from gantt_app.views.toolbar import Toolbar

        self.root = ctk.CTk()
        self.root.withdraw()

        self._patches = [
            mock.patch.object(theme, 'detect_system_appearance',
                              return_value='light'),
            mock.patch.object(theme, 'save_mode', return_value=True),
        ]
        for patch in self._patches:
            patch.start()

        self.controller = theme.ThemeController(mode=theme.MODE_SYSTEM,
                                                apply=lambda _a: None,
                                                persist=False)
        self.toolbar = Toolbar(self.root, Project(name="P"),
                               theme_controller=self.controller)
        self.toolbar.update_idletasks()
        self.icons = self.toolbar.icon_toolbar

    def tearDown(self):
        """Tear the window down and stop the patches."""
        for patch in self._patches:
            patch.stop()
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_the_button_names_the_current_appearance(self):
        """Day while light."""
        self.assertIn("Day", self.icons.theme_button.cget('text'))

    def test_pressing_it_switches_to_night(self):
        """And the caption follows immediately."""
        self.icons.theme_button.invoke()
        self.icons.update_idletasks()

        self.assertIn("Night", self.icons.theme_button.cget('text'))
        self.assertEqual(self.controller.appearance, theme.DARK)

    def test_pressing_it_takes_manual_control(self):
        """Which is what detaches the window from the desktop."""
        self.icons.theme_button.invoke()

        self.assertFalse(self.controller.following_system)

    def test_sync_is_hidden_while_following_the_system(self):
        """The default is the quiet case; see _create_theme_control."""
        self.assertFalse(self.icons.theme_sync_button.winfo_manager())

    def test_sync_appears_once_a_manual_choice_is_made(self):
        """Its presence is the status indicator."""
        self.icons.theme_button.invoke()
        self.icons.update_idletasks()

        self.assertTrue(self.icons.theme_sync_button.winfo_manager())

    def test_sync_puts_it_back_and_hides_itself(self):
        """Graceful restoration, without the window being rebuilt."""
        self.icons.theme_button.invoke()
        self.icons.update_idletasks()

        self.icons.theme_sync_button.invoke()
        self.icons.update_idletasks()

        self.assertTrue(self.controller.following_system)
        self.assertFalse(self.icons.theme_sync_button.winfo_manager())

    def test_the_view_menu_modes_drive_the_same_control(self):
        """However the mode is chosen, the button says the same thing."""
        self.toolbar.use_dark_theme()
        self.icons.update_idletasks()

        self.assertIn("Night", self.icons.theme_button.cget('text'))
        self.assertTrue(self.icons.theme_sync_button.winfo_manager())

        self.toolbar.use_system_theme()
        self.icons.update_idletasks()

        self.assertFalse(self.icons.theme_sync_button.winfo_manager())

    def test_the_control_is_set_apart_by_a_divider(self):
        """It is a setting, not an action on the plan."""
        self.assertEqual(len(self.icons.separators), 8)

    def test_a_destroyed_toolbar_does_not_break_the_theme(self):
        """
        The toolbar subscribes, and subscriptions outlive widgets.

        Writing to a destroyed widget raises, and one dead toolbar must not
        stop the theme reaching the rest of the window.
        """
        self.toolbar.destroy()

        self.controller.toggle()      # must not raise

        self.assertEqual(self.controller.appearance, theme.DARK)


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestThePanesFollowTheTheme(unittest.TestCase):
    """
    The two big panes are not CustomTkinter and do not follow on their own.

    DEVELOPMENT NOTES:
    ------------------
    The task list is a ttk Treeview, whose style resolves its colours once
    and keeps them. The chart is a picture drawn with Pillow, with the old
    colours baked into it. Both stayed white inside a dark window until they
    were told.
    """

    def setUp(self):
        """The whole application, over a fake settings file."""
        from gantt_app.main import GanttApp

        saver = mock.patch.object(theme, 'save_mode', return_value=True)
        saver.start()
        self.addCleanup(saver.stop)

        self.app = GanttApp()
        self.app.update_idletasks()
        self.addCleanup(self._destroy)

        # Pinned, so nothing in this class depends on the desktop it runs
        # on. Left to the ambient setting, these tests report where they
        # were run rather than whether the code works - which is how a
        # green suite on a dark machine failed on CI's light one.
        self.app.theme_controller.set_mode(theme.MODE_LIGHT)
        self.app.update_idletasks()

    def _destroy(self):
        """Tear the application down."""
        try:
            self.app.destroy()
        except Exception:
            pass

    def grid_colour(self, part='background'):
        """What the task list's style currently resolves to."""
        from tkinter import ttk
        return ttk.Style().lookup('Gantt.Treeview', part)

    def test_the_task_list_follows_the_appearance(self):
        """It was the largest thing in the window that did not."""
        self.app.theme_controller.set_mode(theme.MODE_LIGHT)
        light = self.grid_colour()

        self.app.theme_controller.set_mode(theme.MODE_DARK)
        dark = self.grid_colour()

        self.assertEqual(light, theme.GRID_ROW_BG[0])
        self.assertEqual(dark, theme.GRID_ROW_BG[1])

    def test_the_grid_headings_follow_too(self):
        """A dark grid under a light heading strip reads as broken."""
        from tkinter import ttk

        self.app.theme_controller.set_mode(theme.MODE_DARK)

        self.assertEqual(
            ttk.Style().lookup('Gantt.Treeview.Heading', 'background'),
            theme.GRID_HEADING_BG[1])

    def test_the_chart_follows_the_appearance(self):
        """Background and text together, or one of them is unreadable."""
        self.app.theme_controller.set_mode(theme.MODE_DARK)
        settings = self.app.gantt_chart.screen_settings()

        self.assertEqual(settings['bg_color'], theme.CHART_BG[1])
        self.assertEqual(settings['text_color'], theme.CHART_TEXT[1])

    def test_going_back_to_day_restores_the_original_colours(self):
        """The light appearance has to be unchanged, to the value."""
        self.app.theme_controller.set_mode(theme.MODE_DARK)
        self.app.theme_controller.set_mode(theme.MODE_LIGHT)

        self.assertEqual(self.grid_colour(), '#ffffff')
        self.assertEqual(self.app.gantt_chart.screen_settings()['bg_color'],
                         '#ffffff')
        self.assertEqual(self.app.gantt_chart.screen_settings()['text_color'],
                         '#000000')

    def test_an_exported_chart_stays_light(self):
        """
        A PNG or a PDF is shared and printed.

        A dark chart on paper is a page of ink, so the export settings do not
        follow the window - see GanttChartView.screen_settings.
        """
        self.app.theme_controller.set_mode(theme.MODE_DARK)

        exported = self.app.gantt_chart.current_settings()

        self.assertEqual(exported['bg_color'], '#ffffff')
        self.assertEqual(exported['text_color'], '#000000')

    def test_a_colour_the_user_picked_beats_the_theme(self):
        """Their choice in View > Settings is not a default to be overridden."""
        self.app.gantt_chart.chart_settings['bg_color'] = '#fffbe6'

        self.app.theme_controller.set_mode(theme.MODE_DARK)

        self.assertEqual(self.app.gantt_chart.screen_settings()['bg_color'],
                         '#fffbe6')

    def test_a_missing_pane_does_not_stop_the_other(self):
        """
        This runs from the desktop poll as well as from the button.

        So it can fire while the window is being torn down, and one pane
        that has already gone must not stop the other being repainted.
        """
        self.app.task_list = None

        # The appearance is changed for real rather than announced, because
        # _theme_changed only repaints - it is told what happened, it does
        # not make it happen.
        self.app.theme_controller.set_mode(theme.MODE_DARK)

        self.assertEqual(self.app.gantt_chart.screen_settings()['bg_color'],
                         theme.CHART_BG[1])

    def test_repainting_survives_a_pane_that_has_been_destroyed(self):
        """Not merely absent - destroyed, which is what raises."""
        self.app.task_list.destroy()

        self.app.theme_controller.set_mode(theme.MODE_DARK)  # must not raise

        self.assertEqual(self.app.gantt_chart.screen_settings()['bg_color'],
                         theme.CHART_BG[1])


class TestSubscriptionsDoNotPileUp(ThemeControllerTestCase):
    """
    The controller belongs to the application and outlives its widgets.

    DEVELOPMENT NOTES:
    ------------------
    A listener is normally a closure over a toolbar, so the controller
    holding it holds the whole widget tree behind it. Five toolbars built and
    destroyed left five dead listeners and five trees that could never be
    collected. An owner is named now, and a subscription goes when its owner
    does.
    """

    class Owner:
        """Something that can be destroyed, standing in for a widget."""

        def __init__(self):
            self.alive = True

        def winfo_exists(self):
            return self.alive

    def test_a_listener_without_an_owner_is_kept(self):
        """The old behaviour, for a caller that names none."""
        controller = self.controller()
        controller.subscribe(lambda *_a: None)

        controller.toggle()

        self.assertEqual(len(controller._listeners), 1)

    def test_a_listener_goes_when_its_owner_does(self):
        """Which is what stops the list growing for the life of the app."""
        controller = self.controller()
        owner = self.Owner()
        controller.subscribe(lambda *_a: None, owner=owner)

        owner.alive = False
        controller.toggle()

        self.assertEqual(controller._listeners, [])

    def test_a_dead_listener_is_not_called(self):
        """Writing to a destroyed widget raises; it is dropped instead."""
        controller = self.controller()
        owner = self.Owner()
        seen = []
        controller.subscribe(lambda *_a: seen.append(True), owner=owner)

        owner.alive = False
        controller.toggle()

        self.assertEqual(seen, [])

    def test_subscribing_clears_the_ones_that_have_gone(self):
        """
        Rather than waiting for the next theme change.

        A toolbar being rebuilt should clear the one it replaces, in an
        application whose theme never moves - which is most of them.
        """
        controller = self.controller()
        for _ in range(5):
            owner = self.Owner()
            controller.subscribe(lambda *_a: None, owner=owner)
            owner.alive = False

        controller.subscribe(lambda *_a: None, owner=self.Owner())

        self.assertEqual(len(controller._listeners), 1)

    def test_a_collected_owner_takes_its_listener_with_it(self):
        """Held weakly, so an owner Tk never hears about still counts."""
        import gc

        controller = self.controller()
        owner = self.Owner()
        controller.subscribe(lambda *_a: None, owner=owner)

        del owner
        gc.collect()
        controller.toggle()

        self.assertEqual(controller._listeners, [])

    def test_one_can_be_detached_by_hand(self):
        """For anything that has to go earlier than its owner."""
        controller = self.controller()
        listener = lambda *_a: None
        controller.subscribe(listener)

        self.assertTrue(controller.unsubscribe(listener))
        self.assertFalse(controller.unsubscribe(listener))
        self.assertEqual(controller._listeners, [])


if __name__ == '__main__':
    unittest.main()
