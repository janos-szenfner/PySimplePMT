"""
Tests for the new Windows-style menu system.

This module tests the CTkDropdownMenu, CustomMenuBar, and the enhanced
toolbar functionality including copy/paste/cut operations.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from types import SimpleNamespace
import tkinter as tk
import inspect

from gantt_app.views.toolbar import Toolbar, CustomMenuBar, CTkDropdownMenu
from gantt_app.models import Project


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


class TestMenuClassesExist(unittest.TestCase):
    """Tests that the new menu classes exist and are importable."""

    def test_ctk_dropdown_menu_class_exists(self):
        """Test that CTkDropdownMenu class exists."""
        self.assertTrue(hasattr(Toolbar, 'CTkDropdownMenu') or 'CTkDropdownMenu' in globals())
        # Check it's available in the module
        from gantt_app.views.toolbar import CTkDropdownMenu as DirectImport
        self.assertIsNotNone(DirectImport)

    def test_custom_menu_bar_class_exists(self):
        """Test that CustomMenuBar class exists."""
        from gantt_app.views.toolbar import CustomMenuBar as DirectImport
        self.assertIsNotNone(DirectImport)

    def test_menu_classes_have_required_attributes(self):
        """Test that menu classes have required attributes."""
        self.assertTrue(hasattr(CTkDropdownMenu, '__init__'))
        self.assertTrue(hasattr(CTkDropdownMenu, '_create_widgets'))
        self.assertTrue(hasattr(CTkDropdownMenu, '_create_menu_item'))
        
        self.assertTrue(hasattr(CustomMenuBar, '__init__'))
        self.assertTrue(hasattr(CustomMenuBar, '_build_bar'))
        self.assertTrue(hasattr(CustomMenuBar, '_show_dropdown'))


class TestToolbarCopyPaste(unittest.TestCase):
    """Tests for the copy/paste/cut functionality in Toolbar."""

    def setUp(self):
        """Set up test fixtures."""
        self.project = Project("Test Project")
        
    def test_toolbar_has_copy_paste_methods(self):
        """Test that Toolbar class has copy/paste/cut methods."""
        # Test class methods exist without creating instances
        self.assertTrue(hasattr(Toolbar, 'copy_tasks'))
        self.assertTrue(hasattr(Toolbar, 'cut_tasks'))
        self.assertTrue(hasattr(Toolbar, 'paste_tasks'))
        self.assertTrue(hasattr(Toolbar, 'set_task_list'))
        self.assertTrue(callable(getattr(Toolbar, 'copy_tasks', None)))
        self.assertTrue(callable(getattr(Toolbar, 'cut_tasks', None)))
        self.assertTrue(callable(getattr(Toolbar, 'paste_tasks', None)))
        self.assertTrue(callable(getattr(Toolbar, 'set_task_list', None)))

    def test_toolbar_accepts_clipboard_manager_parameter(self):
        """Test that Toolbar constructor accepts clipboard_manager parameter."""
        # Test by examining the __init__ signature
        sig = inspect.signature(Toolbar.__init__)
        params = list(sig.parameters.keys())
        self.assertIn('clipboard_manager', params, 
                     "Toolbar.__init__ should accept clipboard_manager parameter")

    def test_copy_paste_methods_have_proper_signatures(self):
        """Test that copy/paste methods have the expected signatures."""
        # Check copy_tasks method
        copy_sig = inspect.signature(Toolbar.copy_tasks)
        copy_params = list(copy_sig.parameters.keys())
        self.assertEqual(len(copy_params), 1)  # Only self
        
        # Check cut_tasks method  
        cut_sig = inspect.signature(Toolbar.cut_tasks)
        cut_params = list(cut_sig.parameters.keys())
        self.assertEqual(len(cut_params), 1)  # Only self
        
        # Check paste_tasks method
        paste_sig = inspect.signature(Toolbar.paste_tasks)
        paste_params = list(paste_sig.parameters.keys())
        self.assertEqual(len(paste_params), 1)  # Only self
        
        # Check set_task_list method
        set_task_sig = inspect.signature(Toolbar.set_task_list)
        set_task_params = list(set_task_sig.parameters.keys())
        self.assertEqual(len(set_task_params), 2)  # self and task_list


class TestToolbarCopyPaste(unittest.TestCase):
    """Tests for the copy/paste/cut functionality in Toolbar."""

    def setUp(self):
        """Set up test fixtures."""
        self.project = Project("Test Project")
        
    def test_toolbar_has_copy_paste_methods(self):
        """Test that Toolbar class has copy/paste/cut methods."""
        # Test class methods exist without creating instances
        self.assertTrue(hasattr(Toolbar, 'copy_tasks'))
        self.assertTrue(hasattr(Toolbar, 'cut_tasks'))
        self.assertTrue(hasattr(Toolbar, 'paste_tasks'))
        self.assertTrue(hasattr(Toolbar, 'set_task_list'))
        self.assertTrue(callable(getattr(Toolbar, 'copy_tasks', None)))
        self.assertTrue(callable(getattr(Toolbar, 'cut_tasks', None)))
        self.assertTrue(callable(getattr(Toolbar, 'paste_tasks', None)))
        self.assertTrue(callable(getattr(Toolbar, 'set_task_list', None)))

    def test_toolbar_accepts_clipboard_manager_parameter(self):
        """Test that Toolbar constructor accepts clipboard_manager parameter."""
        # Test by examining the __init__ signature
        import inspect
        sig = inspect.signature(Toolbar.__init__)
        params = list(sig.parameters.keys())
        self.assertIn('clipboard_manager', params, 
                     "Toolbar.__init__ should accept clipboard_manager parameter")

    def test_copy_paste_methods_have_proper_signatures(self):
        """Test that copy/paste methods have the expected signatures."""
        import inspect
        
        # Check copy_tasks method
        copy_sig = inspect.signature(Toolbar.copy_tasks)
        copy_params = list(copy_sig.parameters.keys())
        self.assertEqual(len(copy_params), 1)  # Only self
        
        # Check cut_tasks method  
        cut_sig = inspect.signature(Toolbar.cut_tasks)
        cut_params = list(cut_sig.parameters.keys())
        self.assertEqual(len(cut_params), 1)  # Only self
        
        # Check paste_tasks method
        paste_sig = inspect.signature(Toolbar.paste_tasks)
        paste_params = list(paste_sig.parameters.keys())
        self.assertEqual(len(paste_params), 1)  # Only self
        
        # Check set_task_list method
        set_task_sig = inspect.signature(Toolbar.set_task_list)
        set_task_params = list(set_task_sig.parameters.keys())
        self.assertEqual(len(set_task_params), 2)  # self and task_list


class TestMenuStructure(unittest.TestCase):
    """Tests for the menu structure in Toolbar."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock toolbar instance to access menu definitions
        self.stub = SimpleNamespace(**{
            name: getattr(Toolbar, name)
            for name in dir(Toolbar)
            if callable(getattr(Toolbar, name, None)) and not name.startswith('__')
        })

    def test_edit_menu_has_copy_paste_cut(self):
        """Test that Edit menu includes Cut, Copy, Paste."""
        menu_tree = Toolbar._menu_definitions(self.stub)
        
        edit_menu = None
        for menu in menu_tree:
            if menu['text'] == 'Edit':
                edit_menu = menu
                break
        
        self.assertIsNotNone(edit_menu, "Edit menu not found")
        
        edit_items = [item['text'] for item in edit_menu['items']]
        
        self.assertIn('Cut', edit_items, "Cut not found in Edit menu")
        self.assertIn('Copy', edit_items, "Copy not found in Edit menu")
        self.assertIn('Paste', edit_items, "Paste not found in Edit menu")
        self.assertIn('Undo', edit_items, "Undo not found in Edit menu")
        self.assertIn('Redo', edit_items, "Redo not found in Edit menu")

    def test_actions_menu_has_create_submenu(self):
        """Test that Actions menu has Create submenu with work item types."""
        menu_tree = Toolbar._menu_definitions(self.stub)
        
        actions_menu = None
        for menu in menu_tree:
            if menu['text'] == 'Actions':
                actions_menu = menu
                break
        
        self.assertIsNotNone(actions_menu, "Actions menu not found")
        
        # Find Create submenu
        create_item = None
        for item in actions_menu['items']:
            if item['text'] == 'Create':
                create_item = item
                break
        
        self.assertIsNotNone(create_item, "Create item not found in Actions menu")
        self.assertIn('submenu', create_item, "Create should be a submenu")
        
        # Check work item types in Create submenu
        create_items = [item['text'] for item in create_item['submenu']]
        self.assertIn('Task...', create_items, "Task... not found in Create submenu")
        self.assertIn('Subtask...', create_items, "Subtask... not found in Create submenu")
        self.assertIn('Milestone...', create_items, "Milestone... not found in Create submenu")

    def test_menu_order_is_preserved(self):
        """Test that the order of top-level menus is preserved."""
        menu_tree = Toolbar._menu_definitions(self.stub)
        
        menu_texts = [menu['text'] for menu in menu_tree]
        expected_order = ['Project', 'File', 'Actions', 'Edit', 'View']
        
        self.assertEqual(menu_texts, expected_order, 
                        f"Menu order incorrect. Expected: {expected_order}, Got: {menu_texts}")

    def test_menu_conversion_preserves_structure(self):
        """Test that menu conversion preserves the structure."""
        toolbar = Toolbar.__new__(Toolbar)  # Create without calling __init__
        toolbar.project = Project("Test")
        toolbar.undo_redo_manager = None
        toolbar.clipboard_manager = None
        
        # This will test the conversion method directly
        converted = toolbar._convert_to_new_menu_format()
        
        # Check that all expected top-level menus are present
        self.assertIn('Project', converted)
        self.assertIn('File', converted)
        self.assertIn('Actions', converted)
        self.assertIn('Edit', converted)
        self.assertIn('View', converted)
        
        # Check that Edit menu has all items
        edit_items = [item.get('label', item.get('text', '')) for item in converted['Edit']]
        self.assertIn('Undo', edit_items)
        self.assertIn('Redo', edit_items)
        self.assertIn('Cut', edit_items)
        self.assertIn('Copy', edit_items)
        self.assertIn('Paste', edit_items)


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestSubmenusOpen(unittest.TestCase):
    """
    Choosing a menu entry that has a submenu opens it.

    WHY THESE EXIST:
    ================
    File and Actions hold nothing but submenus - Import, Export, Create - so
    when the parent menu closed itself the instant its submenu took focus,
    those two menus did nothing at all. The submenu went with the parent,
    being its child.
    """

    def setUp(self):
        """A toolbar with its menu bar."""
        import customtkinter as ctk
        from gantt_app.models import Project
        from gantt_app.views.toolbar import Toolbar

        self.root = ctk.CTk()
        self.root.withdraw()
        self.toolbar = Toolbar(self.root, Project(name="Test Project"))
        self.toolbar.pack(fill="x")
        self.root.update_idletasks()

    def tearDown(self):
        """Tear the root window down."""
        try:
            self.root.destroy()
        except Exception:
            pass

    def open_menu(self, title):
        """Open a menu from the bar and return its dropdown."""
        bar = self.toolbar.menu_bar
        button = next(b for b in bar.menu_buttons
                      if str(b.cget('text')) == title)
        button.invoke()
        self.root.update_idletasks()
        return bar.active_dropdown

    def submenu_rows(self, dropdown):
        """The rows of a dropdown that open a submenu."""
        import customtkinter as ctk

        rows = []
        for container in dropdown.winfo_children():
            for row in container.winfo_children():
                for widget in row.winfo_children():
                    if (isinstance(widget, ctk.CTkButton)
                            and getattr(widget, 'submenu_items', None)):
                        rows.append(widget)
        return rows

    def test_file_offers_import_and_export(self):
        """Both are submenus, and both are there to be opened."""
        dropdown = self.open_menu('File')

        labels = [str(w.cget('text')).strip()
                  for w in self.submenu_rows(dropdown)]

        self.assertEqual(labels, ['Import', 'Export'])

    def test_opening_a_submenu_leaves_its_parent_alive(self):
        """
        Which is what stopped it appearing at all.

        The parent closed on losing focus to its own submenu, and the
        submenu is the parent's child, so both vanished together.
        """
        dropdown = self.open_menu('File')
        self.submenu_rows(dropdown)[0].invoke()
        self.root.update_idletasks()

        self.assertTrue(dropdown.winfo_exists(),
                        "the parent menu closed itself")
        self.assertIsNotNone(dropdown._submenu)
        self.assertTrue(dropdown._submenu.winfo_exists())

    def test_the_actions_create_submenu_opens(self):
        """Actions holds Create, which is where the work items are made."""
        dropdown = self.open_menu('Actions')
        rows = self.submenu_rows(dropdown)

        self.assertEqual([str(w.cget('text')).strip() for w in rows],
                         ['Create'])

        rows[0].invoke()
        self.root.update_idletasks()

        self.assertTrue(dropdown._submenu.winfo_exists())


if __name__ == '__main__':
    unittest.main()
