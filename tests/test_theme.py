"""
Tests for the theme: the parts that need a window.

WHY THIS MODULE EXISTS:
======================
The controller, the palette, and the drawn icons are exercised without a
display in tests/test_theme_bdd.py (features/theme.feature). What is left
here is what genuinely needs one: the toolbar's sun/moon control, the
sync button, and the panes repainting under a live application.

detect_system_appearance is patched throughout. The desktop this runs on
has a setting of its own and the tests must not depend on which.
"""

import unittest
from unittest import mock

from gantt_app.views import theme


def _shut_down(root) -> None:
    """
    Take a root down, children first, without raising.

    Destroying a root while a Toplevel is still on it leaves Tk running
    ttk::ThemeChanged against an interpreter that has already gone, which
    floods stderr with "can't invoke event" tracebacks.
    """
    try:
        for child in list(root.children.values()):
            try:
                child.destroy()
            except Exception:
                pass
        root.destroy()
    except Exception:
        pass



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
        from gantt_app.core.models import Project
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
            _shut_down(self.root)
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

    def test_sync_is_an_icon_rather_than_a_sentence(self):
        """
        "Sync with system" written out was 124 pixels of text in a row of
        36-pixel icons, and the widest thing on the right-hand side - so the
        search box beside it sat that much further from the edge.
        """
        sync = self.icons.theme_sync_button

        self.assertEqual(sync.cget('text'), '')
        self.assertIsNotNone(getattr(sync, 'icon_image', None))

    def test_sync_says_what_it_does_on_hover(self):
        """Which is where the words went."""
        self.assertEqual(self.icons.theme_sync_button.tooltip,
                         "Sync with the System")

    def test_sync_has_a_drawing_to_show(self):
        """Without one the button would fall back to a letter."""
        from gantt_app.resources.icons import ICON_STROKES, draw_icon

        self.assertIn('sync', ICON_STROKES)
        self.assertIsNotNone(draw_icon('sync', 20))

    def test_sync_sits_beside_the_day_night_toggle(self):
        """
        Wherever in the session it is asked for.

        It is packed when an appearance is chosen rather than when the row is
        built, and side="right" alone appends to the end of the right-hand
        group - which by then is past the search box. So it appeared at the
        far left of the row, against undo and redo, a long way from the
        control it belongs to.

        On the ribbon the right-hand group is the strip's own right-edge
        frame; the buttons' shared parent is what the ordering is read off.
        """
        self.toolbar.use_light_theme()
        self.icons.update_idletasks()

        parent = self.icons.theme_button.master
        right = [w for w in parent.pack_slaves()
                 if w.pack_info().get('side') == 'right']
        toggle = right.index(self.icons.theme_button)
        sync = right.index(self.icons.theme_sync_button)

        # Packed right to left, so the next one along is immediately left
        self.assertEqual(sync, toggle + 1)

    def test_the_help_button_is_the_far_right_of_the_row(self):
        """The rightmost of the right-edge cluster on the strip."""
        right = [w for w in self.icons.help_button.master.pack_slaves()
                 if w.pack_info().get('side') == 'right']

        self.assertIs(right[0], self.icons.help_button)

    def test_the_control_is_set_apart_by_a_divider(self):
        """
        Set apart from the tabs and the actions.

        DEVELOPMENT NOTES:
        ------------------
        On the icon row this was a hairline divider either side of the
        day/night control. The ribbon holds the three right-edge controls -
        help, appearance, search - in a frame of their own at the strip's
        right end, which is the same separation said a different way.
        """
        parent = self.icons.help_button.master
        self.assertIs(parent, self.icons.theme_button.master)
        self.assertIs(parent, self.icons.search_box.master)
        self.assertEqual(parent.pack_info().get('side'), 'right')

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

    def assert_same_colour(self, actual, expected):
        """
        The two name the same colour, however each is spelt.

        Compared as RGB rather than as strings: ttk resolves #ffffff to the
        named colour White on macOS, so a string check said the grid had not
        followed when it had. winfo_rgb reads both to the same triple.
        """
        self.assertEqual(self.app.winfo_rgb(actual),
                         self.app.winfo_rgb(expected),
                         f"{actual!r} is not {expected!r}")

    def test_the_task_list_follows_the_appearance(self):
        """It was the largest thing in the window that did not."""
        self.app.theme_controller.set_mode(theme.MODE_LIGHT)
        light = self.grid_colour()

        self.app.theme_controller.set_mode(theme.MODE_DARK)
        dark = self.grid_colour()

        self.assert_same_colour(light, theme.GRID_ROW_BG[0])
        self.assert_same_colour(dark, theme.GRID_ROW_BG[1])

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

    def test_the_resource_grid_style_follows_the_appearance(self):
        """
        The Resource settings DataGrid stayed dark on a switch to day.

        Its window is opened on its own and the application does not hold it,
        so it has no apply_theme; the shared ttk style is re-coloured for it
        instead. The dark value is checked, not the light one, because ttk
        resolves #ffffff to the named colour White on macOS and the test
        should say whether the code works, not which platform ran it.
        """
        from tkinter import ttk

        self.app.theme_controller.set_mode(theme.MODE_LIGHT)
        light = ttk.Style().lookup('DataGrid.Treeview', 'fieldbackground')

        self.app.theme_controller.set_mode(theme.MODE_DARK)
        dark = ttk.Style().lookup('DataGrid.Treeview', 'fieldbackground')

        self.assertEqual(dark, theme.GRID_ROW_BG[1])
        self.assertNotEqual(light, dark)

    def test_the_resource_grid_rows_follow_the_appearance(self):
        """
        The DataGrid's banding is per-instance tag colour, not the style.

        Re-styling the shared style fixes the empty field but not the rows,
        which the window re-tags through _configure_style. The dark banding
        colour is unambiguous, so it is the one checked.
        """
        from gantt_app.views.resourcesettings import DataGrid

        columns = (("A", 80, 1, "w"), ("B", 80, 1, "w"))
        grid = DataGrid(self.app, columns, on_select=lambda _i: None)

        self.app.theme_controller.set_mode(theme.MODE_DARK)
        grid._configure_style()

        self.assertEqual(
            str(grid.tree.tag_configure('even', 'background')),
            theme.GRID_ROW_BG[1])

    def test_the_chart_container_follows_the_appearance(self):
        """
        The frame behind the chart canvas is themed, not left to Tk.

        A bare frame keeps a fixed colour, and the square where the two
        scrollbars meet and a hairline round the edges show it - which framed
        the chart in black after a switch to day. Rebuilt with the chart, so
        it follows; the dark value is checked for the reason above.
        """
        self.app.theme_controller.set_mode(theme.MODE_DARK)
        self.app.update_idletasks()

        canvas = self.app.gantt_chart._chart_canvas
        self.assertIsNotNone(canvas)
        container = canvas.master
        self.assertEqual(str(container.cget('background')), theme.CHART_BG[1])

    def test_going_back_to_day_restores_the_original_colours(self):
        """The light appearance has to be unchanged, to the value."""
        self.app.theme_controller.set_mode(theme.MODE_DARK)
        self.app.theme_controller.set_mode(theme.MODE_LIGHT)

        self.assert_same_colour(self.grid_colour(), '#ffffff')
        self.assert_same_colour(
            self.app.gantt_chart.screen_settings()['bg_color'], '#ffffff')
        self.assert_same_colour(
            self.app.gantt_chart.screen_settings()['text_color'], '#000000')

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




if __name__ == '__main__':
    unittest.main()
