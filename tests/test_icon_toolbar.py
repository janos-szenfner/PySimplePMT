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

    def test_icon_toolbar_button_count(self):
        """Test that IconToolbar creates the expected number of buttons."""
        toolbar = IconToolbar(self.root, self.project)
        # We expect: open, new_project, save, edit, task, subtask, milestone,
        # cut, copy, paste, delete, undo, redo = 13 buttons
        self.assertEqual(len(toolbar.icon_buttons), 13)
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

    def test_buttons_have_emoji_text(self):
        """Test that buttons display emoji characters."""
        for icon_name, btn in self.toolbar.icon_buttons.items():
            btn_text = btn.cget("text")
            expected_emoji = ICON_EMOJIS.get(icon_name, '?')
            self.assertEqual(btn_text, expected_emoji,
                          f"Button '{icon_name}' has incorrect text")

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
    """Test icon toolbar button actions."""

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

    def test_new_project_action(self):
        """Test new project action."""
        self.assertTrue(callable(self.toolbar.new_project))

    def test_load_project_action(self):
        """Test load project action."""
        self.assertTrue(callable(self.toolbar.load_project))

    def test_save_project_action(self):
        """Test save project action."""
        self.assertTrue(callable(self.toolbar.save_project))

    def test_edit_project_info_action(self):
        """Test edit project info action."""
        self.assertTrue(callable(self.toolbar.edit_project_info))

    def test_add_task_action(self):
        """Test add task action."""
        self.assertTrue(callable(self.toolbar.add_task))

    def test_add_subtask_action(self):
        """Test add subtask action."""
        self.assertTrue(callable(self.toolbar.add_subtask))

    def test_add_milestone_action(self):
        """Test add milestone action."""
        self.assertTrue(callable(self.toolbar.add_milestone))

    def test_cut_tasks_action(self):
        """Test cut tasks action."""
        self.assertTrue(callable(self.toolbar.cut_tasks))

    def test_copy_tasks_action(self):
        """Test copy tasks action."""
        self.assertTrue(callable(self.toolbar.copy_tasks))

    def test_paste_tasks_action(self):
        """Test paste tasks action."""
        self.assertTrue(callable(self.toolbar.paste_tasks))

    def test_delete_selected_action(self):
        """Test delete selected action."""
        self.assertTrue(callable(self.toolbar.delete_selected))

    def test_undo_action(self):
        """Test undo action."""
        self.assertTrue(callable(self.toolbar.undo))

    def test_redo_action(self):
        """Test redo action."""
        self.assertTrue(callable(self.toolbar.redo))


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
