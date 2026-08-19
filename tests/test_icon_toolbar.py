"""
Tests for the IconToolbar class in the Gantt Project Management Tool.

This module tests the graphical icon toolbar functionality including:
- IconToolbar creation and initialization
- Icon button creation and properties
- Active/inactive state management
- Button action connections
- Integration with project state
"""

import unittest
import tkinter as tk
import customtkinter as ctk
from unittest.mock import MagicMock, patch

from gantt_app.models import Project, Task
from gantt_app.views.toolbar import IconToolbar, Toolbar
from gantt_app.resources.icons import (
    ICON_EMOJIS, ICON_NAMES, SVG_PATHS,
    ALWAYS_ACTIVE, ACTIVE_WHEN_PROJECT_OPEN, WORK_ITEM_CREATION_ICONS
)


class TestIconDefinitions(unittest.TestCase):
    """Test icon definitions and resources."""

    def test_icon_emojis_exist(self):
        """Test that all expected icon emojis are defined."""
        expected_icons = [
            'open', 'new_project', 'save', 'edit',
            'task', 'subtask', 'milestone', 'phase', 'deliverable',
            'cut', 'copy', 'paste', 'delete', 'undo', 'redo'
        ]
        for icon_name in expected_icons:
            self.assertIn(icon_name, ICON_EMOJIS,
                        f"Icon '{icon_name}' not found in ICON_EMOJIS")

    def test_icon_emojis_are_strings(self):
        """Test that all icon emojis are valid strings."""
        for icon_name, emoji in ICON_EMOJIS.items():
            self.assertIsInstance(emoji, str, 
                               f"Icon '{icon_name}' is not a string")
            self.assertGreater(len(emoji), 0,
                             f"Icon '{icon_name}' is empty")

    def test_svg_paths_exist(self):
        """Test that all expected SVG paths are defined."""
        expected_icons = [
            'open', 'new_project', 'save', 'edit',
            'task', 'subtask', 'milestone', 'phase', 'deliverable',
            'cut', 'copy', 'paste', 'delete', 'undo', 'redo'
        ]
        for icon_name in expected_icons:
            self.assertIn(icon_name, SVG_PATHS,
                        f"SVG path for '{icon_name}' not found")

    def test_svg_paths_are_non_empty(self):
        """Test that all SVG paths are non-empty strings."""
        for icon_name, path in SVG_PATHS.items():
            self.assertIsInstance(path, str,
                               f"SVG path for '{icon_name}' is not a string")
            self.assertGreater(len(path), 0,
                             f"SVG path for '{icon_name}' is empty")

    def test_icon_groups(self):
        """Test icon group definitions."""
        # Test ALWAYS_ACTIVE group
        self.assertIn('open', ALWAYS_ACTIVE)
        self.assertEqual(len(ALWAYS_ACTIVE), 1, 
                        "Only 'open' should be always active")

        # Test ACTIVE_WHEN_PROJECT_OPEN group
        expected_active_icons = [
            'new_project', 'save', 'edit',
            'task', 'subtask', 'milestone', 'phase', 'deliverable',
            'cut', 'copy', 'paste', 'delete', 'undo', 'redo'
        ]
        for icon_name in expected_active_icons:
            self.assertIn(icon_name, ACTIVE_WHEN_PROJECT_OPEN,
                        f"'{icon_name}' should be in ACTIVE_WHEN_PROJECT_OPEN")

        # Test WORK_ITEM_CREATION_ICONS group
        expected_work_items = ['task', 'subtask', 'milestone', 'phase', 'deliverable']
        for icon_name in expected_work_items:
            self.assertIn(icon_name, WORK_ITEM_CREATION_ICONS,
                        f"'{icon_name}' should be in WORK_ITEM_CREATION_ICONS")

    def test_icon_names_list(self):
        """Test that ICON_NAMES contains all defined icons."""
        self.assertEqual(len(ICON_NAMES), len(ICON_EMOJIS))
        for icon_name in ICON_EMOJIS.keys():
            self.assertIn(icon_name, ICON_NAMES)


class TestIconToolbarCreation(unittest.TestCase):
    """Test IconToolbar creation and initialization."""

    def setUp(self):
        """Set up test fixtures."""
        self.root = tk.Tk()
        self.root.withdraw()
        self.project = Project(name="Test Project")

    def tearDown(self):
        """Clean up after tests."""
        if hasattr(self, 'toolbar'):
            self.toolbar.destroy()
        self.root.destroy()

    def test_icon_toolbar_creation(self):
        """Test that IconToolbar can be created."""
        toolbar = IconToolbar(self.root, self.project)
        self.assertIsNotNone(toolbar)
        self.toolbar = toolbar

    def test_icon_toolbar_has_correct_height(self):
        """Test that IconToolbar has the expected height."""
        toolbar = IconToolbar(self.root, self.project)
        self.assertEqual(toolbar.cget("height"), 40)
        self.toolbar = toolbar

    def test_icon_toolbar_has_correct_background(self):
        """Test that IconToolbar has the Windows menu bar background color."""
        from gantt_app.views.toolbar import WIN_MENU_BG
        toolbar = IconToolbar(self.root, self.project)
        self.assertEqual(toolbar.cget("fg_color"), WIN_MENU_BG)
        self.toolbar = toolbar

    def test_icon_toolbar_creates_buttons(self):
        """Test that IconToolbar creates icon buttons."""
        toolbar = IconToolbar(self.root, self.project)
        expected_icons = [
            'open', 'new_project', 'save', 'edit',
            'task', 'subtask', 'milestone',
            'cut', 'copy', 'paste', 'delete', 'undo', 'redo'
        ]
        for icon_name in expected_icons:
            self.assertIn(icon_name, toolbar.icon_buttons,
                        f"Icon button '{icon_name}' not created")
        self.toolbar = toolbar

    def test_a_button_is_made_for_every_icon(self):
        """
        One button per icon named, and none for the dividers.

        Counted against ICON_ACTIONS rather than against a number written
        here, which went stale the moment Phase and Deliverable were added.
        """
        toolbar = IconToolbar(self.root, self.project)
        expected = [name for name, _tip, _action in toolbar.ICON_ACTIONS
                    if name != toolbar.SEPARATOR]

        self.assertEqual(list(toolbar.icon_buttons), expected)
        self.toolbar = toolbar

    def test_the_dividers_are_not_buttons(self):
        """A divider is a hairline, not something to press."""
        toolbar = IconToolbar(self.root, self.project)

        self.assertNotIn(toolbar.SEPARATOR, toolbar.icon_buttons)
        # Five: after the file actions, one on each side of the critical
        # path analysis - which belongs to neither group beside it - and one
        # on each side of the search box, which is neither an action on the
        # plan nor one of the settings it sits between.
        self.assertEqual(len(toolbar.separators), 5)
        self.toolbar = toolbar

    def test_the_dividers_fall_between_the_groups(self):
        """
        Making things is held apart from moving them about.

        One divider after the file actions, one after the work items, so the
        row reads as three groups rather than one long run of buttons.
        """
        toolbar = IconToolbar(self.root, self.project)
        names = [name for name, _tip, _action in toolbar.ICON_ACTIONS]

        self.assertEqual(names.index(toolbar.SEPARATOR),
                         names.index('save') + 1)
        self.assertEqual(names[names.index('milestone') + 1],
                         toolbar.SEPARATOR)
        self.toolbar = toolbar


class TestIconToolbarButtonProperties(unittest.TestCase):
    """Test properties of icon toolbar buttons."""

    def setUp(self):
        """Set up test fixtures."""
        self.root = tk.Tk()
        self.root.withdraw()
        self.project = Project(name="Test Project")
        self.toolbar = IconToolbar(self.root, self.project)

    def tearDown(self):
        """Clean up after tests."""
        self.toolbar.destroy()
        self.root.destroy()

    def test_buttons_have_correct_size(self):
        """Test that all buttons have the expected size."""
        for icon_name, btn in self.toolbar.icon_buttons.items():
            self.assertEqual(btn.cget("width"), self.toolbar.BUTTON_SIZE)
            self.assertEqual(btn.cget("height"), self.toolbar.BUTTON_SIZE)

    def test_buttons_have_transparent_background(self):
        """Test that all buttons have transparent background."""
        for icon_name, btn in self.toolbar.icon_buttons.items():
            self.assertEqual(btn.cget("fg_color"), "transparent")

    def test_buttons_have_hover_color(self):
        """Test that all buttons have hover color."""
        from gantt_app.views.toolbar import WIN_MENU_HOVER
        for icon_name, btn in self.toolbar.icon_buttons.items():
            self.assertEqual(btn.cget("hover_color"), WIN_MENU_HOVER)

    def test_every_button_carries_a_drawn_icon(self):
        """
        The picture is drawn, so no font has to have it.

        The buttons used to be set in "Segoe UI Emoji" with an emoji
        character on each. That font ships with Windows and with nothing
        else, so on a stock Linux desktop every button on the row came out
        blank - a row of empty rectangles where the toolbar should be.
        """
        for icon_name, btn in self.toolbar.icon_buttons.items():
            self.assertIsNotNone(btn.cget("image"),
                                 f"Button '{icon_name}' has no drawing")

    def test_a_drawn_button_carries_no_text(self):
        """The picture says it; a letter beside it would only crowd it."""
        for icon_name, btn in self.toolbar.icon_buttons.items():
            self.assertEqual(btn.cget("text"), "",
                             f"Button '{icon_name}' shows text as well")

    def test_the_drawing_is_kept_from_the_collector(self):
        """
        A CTkImage that is collected takes the picture off the button.

        Held only by the call that made it, the icons vanished the moment
        Python got round to tidying up.
        """
        for icon_name, btn in self.toolbar.icon_buttons.items():
            self.assertIsNotNone(getattr(btn, 'icon_image', None),
                                 f"Button '{icon_name}' does not hold its image")

    def test_buttons_have_tooltips(self):
        """Test that buttons have tooltip information."""
        expected_tooltips = {
            'open': 'Open Project',
            'new_project': 'New Project',
            'save': 'Save Project',
            'edit': 'Edit',
            'task': 'Create Task',
            'subtask': 'Create Subtask',
            'milestone': 'Create Milestone',
            'cut': 'Cut',
            'copy': 'Copy',
            'paste': 'Paste',
            'delete': 'Delete',
            'undo': 'Undo',
            'redo': 'Redo'
        }
        for icon_name, expected_tooltip in expected_tooltips.items():
            btn = self.toolbar.icon_buttons[icon_name]
            self.assertTrue(hasattr(btn, 'tooltip'))
            self.assertEqual(btn.tooltip, expected_tooltip)


class TestIconToolbarStateManagement(unittest.TestCase):
    """Test icon toolbar state management (active/inactive)."""

    def setUp(self):
        """Set up test fixtures."""
        self.root = tk.Tk()
        self.root.withdraw()

    def tearDown(self):
        """Clean up after tests."""
        if hasattr(self, 'toolbar'):
            self.toolbar.destroy()
        self.root.destroy()

    def test_open_button_always_active_with_project(self):
        """Test that open button is active when project exists."""
        project = Project(name="Test Project")
        toolbar = IconToolbar(self.root, project)
        self.assertEqual(toolbar.icon_buttons['open'].cget("state"), "normal")
        self.toolbar = toolbar

    def test_open_button_always_active_without_project(self):
        """Test that open button is active even without project."""
        toolbar = IconToolbar(self.root, None)
        self.assertEqual(toolbar.icon_buttons['open'].cget("state"), "normal")
        self.toolbar = toolbar

    def test_other_buttons_active_with_project(self):
        """Test that other buttons are active when project exists."""
        project = Project(name="Test Project")
        toolbar = IconToolbar(self.root, project)
        
        # All buttons except 'open' should be active when project exists
        for icon_name in ['save', 'edit', 'task', 'subtask', 'milestone',
                        'cut', 'copy', 'paste', 'delete', 'undo', 'redo']:
            self.assertEqual(
                toolbar.icon_buttons[icon_name].cget("state"), "normal",
                f"Button '{icon_name}' should be active with project"
            )
        self.toolbar = toolbar

    def test_buttons_inactive_without_project(self):
        """Test that buttons (except open) are inactive without project."""
        toolbar = IconToolbar(self.root, None)
        
        # All buttons except 'open' should be disabled when no project
        for icon_name in ['save', 'edit', 'new_project', 'task', 'subtask',
                        'milestone', 'cut', 'copy', 'paste', 'delete', 'undo', 'redo']:
            self.assertEqual(
                toolbar.icon_buttons[icon_name].cget("state"), "disabled",
                f"Button '{icon_name}' should be disabled without project"
            )
        self.toolbar = toolbar

    def test_set_task_list_updates_state(self):
        """Test that setting task list triggers state update."""
        project = Project(name="Test Project")
        toolbar = IconToolbar(self.root, project)
        
        # Create mock task list
        mock_task_list = MagicMock()
        toolbar.set_task_list(mock_task_list)
        
        # State should still be correct
        self.assertEqual(toolbar.icon_buttons['open'].cget("state"), "normal")
        self.assertEqual(toolbar.icon_buttons['save'].cget("state"), "normal")
        
        self.toolbar = toolbar


class TestIconToolbarActions(unittest.TestCase):
    """
    What the icons do, and what they do when nothing is behind them.

    WHY THESE LOOK LIKE THIS:
    =========================
    They used to assert that IconToolbar had a method of each action's name,
    which was true only because it carried a handler of its own for every
    icon - its own file choosers, its own task creation. None of those ever
    ran: Toolbar replaces every one of them once the row is built. Asserting
    they existed was asserting that the dead copy was still there.

    What matters is that every icon names an action, that pressing one with
    nothing connected is harmless, and that pressing one with a handler
    connected calls it - which is the thing that was broken, the buttons
    having kept the methods they were built with.
    """

    def setUp(self):
        """Set up test fixtures."""
        self.root = tk.Tk()
        self.root.withdraw()
        self.project = Project(name="Test Project")
        self.toolbar = IconToolbar(self.root, self.project)

    def tearDown(self):
        """Clean up after tests."""
        self.toolbar.destroy()
        self.root.destroy()

    def test_every_icon_names_an_action(self):
        """No icon is drawn with nothing to invoke. Dividers are not icons."""
        for icon_name, tooltip, action in self.toolbar.ICON_ACTIONS:
            if icon_name == self.toolbar.SEPARATOR:
                continue
            self.assertTrue(action, f"{icon_name} names no action")

    def test_the_row_offers_the_expected_actions(self):
        """The actions Toolbar connects are the actions the row asks for."""
        actions = [action for icon, _tip, action in self.toolbar.ICON_ACTIONS
                   if icon != self.toolbar.SEPARATOR]

        self.assertEqual(actions, [
            'load_project', 'new_project', 'save_project',
            'edit_project_info',
            'add_phase', 'add_deliverable', 'add_task', 'add_subtask',
            'add_milestone',
            'show_critical_path',
            'cut_tasks', 'copy_tasks', 'paste_tasks', 'delete_selected',
            'undo', 'redo',
        ])

    def test_an_unconnected_action_does_nothing(self):
        """
        A row built without a Toolbar has nothing behind its buttons.

        It says so in the log rather than half-doing the action, which is
        what the handlers it used to carry did: Create Task added a task
        called "New Task" with no dialog and no undo behind it.
        """
        self.toolbar._perform('add_task')

        self.assertEqual(len(self.project.tasks), 0)

    def test_a_connected_action_is_called(self):
        """
        What Toolbar connects is what the button runs.

        The buttons used to be built with this class's own bound methods, so
        connecting the real handlers afterwards changed nothing they could
        see and every icon ran the wrong thing.
        """
        called = []
        self.toolbar.add_task = lambda: called.append('add_task')

        self.toolbar._perform('add_task')

        self.assertEqual(called, ['add_task'])

    def test_pressing_the_button_runs_the_connected_action(self):
        """The same, through the button rather than past it."""
        called = []
        self.toolbar.add_task = lambda: called.append('add_task')

        self.toolbar.icon_buttons['task'].invoke()

        self.assertEqual(called, ['add_task'])


class TestIconToolbarIntegration(unittest.TestCase):
    """Test IconToolbar integration with Toolbar."""

    def setUp(self):
        """Set up test fixtures."""
        self.root = ctk.CTk()
        self.root.withdraw()
        self.project = Project(name="Test Project")

    def tearDown(self):
        """Clean up after tests."""
        if hasattr(self, 'toolbar'):
            self.toolbar.destroy()
        self.root.destroy()

    def test_toolbar_creates_icon_toolbar(self):
        """Test that Toolbar creates an IconToolbar."""
        from gantt_app.utils.undoredo import UndoRedoManager
        
        undo_redo_manager = UndoRedoManager()
        toolbar = Toolbar(
            self.root, self.project,
            undo_redo_manager=undo_redo_manager
        )
        self.assertTrue(hasattr(toolbar, 'icon_toolbar'))
        self.assertIsInstance(toolbar.icon_toolbar, IconToolbar)
        self.toolbar = toolbar

    def test_icon_toolbar_has_correct_icons(self):
        """Test that the icon toolbar in Toolbar has the expected icons."""
        from gantt_app.utils.undoredo import UndoRedoManager
        
        undo_redo_manager = UndoRedoManager()
        toolbar = Toolbar(
            self.root, self.project,
            undo_redo_manager=undo_redo_manager
        )
        
        expected_icons = [
            'open', 'new_project', 'save', 'edit',
            'task', 'subtask', 'milestone',
            'cut', 'copy', 'paste', 'delete', 'undo', 'redo'
        ]
        for icon_name in expected_icons:
            self.assertIn(icon_name, toolbar.icon_toolbar.icon_buttons)
        
        self.toolbar = toolbar

    def test_toolbar_set_task_list_updates_icon_toolbar(self):
        """Test that setting task list on Toolbar also updates IconToolbar."""
        from gantt_app.utils.undoredo import UndoRedoManager
        
        undo_redo_manager = UndoRedoManager()
        toolbar = Toolbar(
            self.root, self.project,
            undo_redo_manager=undo_redo_manager
        )
        
        # Create mock task list
        mock_task_list = MagicMock()
        toolbar.set_task_list(mock_task_list)
        
        # Check that icon_toolbar also has the task list reference
        self.assertEqual(toolbar.icon_toolbar.task_list, mock_task_list)
        
        self.toolbar = toolbar


class TestSVGIconGeneration(unittest.TestCase):
    """Test SVG icon generation functionality."""

    def test_get_icon_svg_returns_valid_svg(self):
        """Test that get_icon_svg returns valid SVG XML."""
        from gantt_app.resources.icons import get_icon_svg
        
        svg = get_icon_svg('edit')
        self.assertIn('<svg', svg)
        self.assertIn('xmlns="http://www.w3.org/2000/svg"', svg)
        self.assertIn('<path', svg)
        self.assertIn('</svg>', svg)

    def test_get_icon_svg_with_custom_viewbox(self):
        """Test that get_icon_svg respects custom viewbox."""
        from gantt_app.resources.icons import get_icon_svg
        
        svg = get_icon_svg('edit', viewbox="0 0 48 48")
        self.assertIn('viewBox="0 0 48 48"', svg)

    def test_get_icon_svg_returns_empty_for_unknown(self):
        """Test that get_icon_svg returns empty string for unknown icon."""
        from gantt_app.resources.icons import get_icon_svg
        
        svg = get_icon_svg('unknown_icon')
        self.assertEqual(svg, '')

    def test_get_icon_emoji_returns_emoji(self):
        """Test that get_icon_emoji returns emoji character."""
        from gantt_app.resources.icons import get_icon_emoji
        
        emoji = get_icon_emoji('edit')
        self.assertIsInstance(emoji, str)
        self.assertGreater(len(emoji), 0)

    def test_get_icon_emoji_returns_question_mark_for_unknown(self):
        """Test that get_icon_emoji returns '?' for unknown icon."""
        from gantt_app.resources.icons import get_icon_emoji
        
        emoji = get_icon_emoji('unknown_icon')
        self.assertEqual(emoji, '?')


if __name__ == '__main__':
    unittest.main()
