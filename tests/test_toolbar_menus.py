"""
Tests for the arrangement of the toolbar menus.

DEVELOPMENT NOTES:
------------------
The menu tree is read from Toolbar._menu_definitions rather than by building
a Toolbar, which would need a display. The method only returns data, so the
structure can be checked directly while the commands it names are verified to
exist on the class.
"""

import unittest
from types import SimpleNamespace

from gantt_app.views.toolbar import Toolbar


def menu_tree():
    """Get the toolbar's menu definitions without constructing a widget."""
    # Every command is a bound method, so a stand-in with the same attributes
    # is enough to collect the structure
    stub = SimpleNamespace(**{
        name: getattr(Toolbar, name)
        for name in dir(Toolbar)
        if callable(getattr(Toolbar, name, None)) and not name.startswith('__')
    })
    return Toolbar._menu_definitions(stub)


def labels(items):
    """Get the visible text of a list of menu entries."""
    return [item['text'] for item in items]


def find(tree, text):
    """Find a top-level menu by its label."""
    return next(menu for menu in tree if menu['text'] == text)


class TestMenuOrder(unittest.TestCase):
    """The order the menus appear in, left to right."""

    def setUp(self):
        """Set up test fixtures."""
        self.tree = menu_tree()

    def test_top_level_order(self):
        """File, Actions, Settings, Edit, then View last."""
        self.assertEqual([menu['text'] for menu in self.tree],
                         ['File', 'Actions', 'Settings', 'Edit', 'View'])

    def test_file_comes_first(self):
        """
        Where every other application puts it.

        A second menu called Project used to hold the new/open/save, so the
        one place a reader looks first for Save was the one place it was
        not.
        """
        self.assertEqual(self.tree[0]['text'], 'File')

    def test_nothing_is_called_project_any_more(self):
        """Its entries are under File; the empty menu went with them."""
        self.assertNotIn('Project', [menu['text'] for menu in self.tree])

    def test_view_is_last(self):
        """View stays at the end of the list."""
        self.assertEqual(self.tree[-1]['text'], 'View')


class TestMenuContents(unittest.TestCase):
    """What sits under each menu."""

    def setUp(self):
        """Set up test fixtures."""
        self.tree = menu_tree()

    def test_file_menu(self):
        """File holds the file lifecycle actions."""
        self.assertEqual(
            labels(find(self.tree, 'File')['items']),
            ['New Project...', 'Load Project...', 'Save Project...',
             'Save Project As...'])

    def test_actions_menu_nests_import_and_export(self):
        """Actions carries Import and Export as submenus."""
        items = find(self.tree, 'Actions')['items']

        self.assertEqual(labels(items), ['Import', 'Export'])
        for item in items:
            self.assertIn('submenu', item)
            self.assertTrue(item['submenu'])

    def test_import_submenu_formats(self):
        """Every import format is reachable under Actions > Import."""
        items = find(self.tree, 'Actions')['items']
        imports = next(i for i in items if i['text'] == 'Import')

        self.assertEqual(labels(imports['submenu']),
                         ['MS Project...', 'GAN...', 'Mermaid...', 'XLSX...'])

    def test_export_submenu_formats(self):
        """Every export format is reachable under Actions > Export."""
        items = find(self.tree, 'Actions')['items']
        exports = next(i for i in items if i['text'] == 'Export')

        self.assertEqual(labels(exports['submenu']),
                         ['GAN...', 'MS Project...', 'Mermaid...', 'HTML...',
                          'SVG...', 'PNG...', 'PDF...', 'XLSX...'])

    def test_settings_holds_what_is_set_about_the_plan(self):
        """
        Three settings panels and nothing else.

        Create moved to Edit - making a row is an edit - and Critical Path
        moved to View, which is where something that changes what the window
        shows belongs.
        """
        items = find(self.tree, 'Settings')['items']

        self.assertEqual(labels(items),
                         ['Project Settings...', 'Calendar Settings...',
                          'Gantt Settings...'])
        for item in items:
            self.assertNotIn('submenu', item)

    def test_calendar_settings_sits_directly_under_settings(self):
        """
        Choosing which days the plan works is not a create action.

        It belongs beside Project Settings: both change something about the
        whole project rather than adding a row to it.
        """
        items = find(self.tree, 'Settings')['items']
        entry = next(i for i in items if i['text'] == 'Calendar Settings...')

        self.assertNotIn('submenu', entry)
        self.assertTrue(callable(entry['command']))

    def test_create_submenu_holds_only_the_create_actions(self):
        """Create offers the things that can be created, nothing else."""
        create = find(self.tree, 'Edit')['items'][0]

        self.assertEqual(labels(create['submenu']),
                         ['Phase...', 'Task...', 'Subtask...',
                          'Milestone...'])

    def test_project_settings_sits_directly_under_settings(self):
        """
        The settings that apply to the whole plan are reachable in one step.

        This entry used to sit inside Create, which put a rename next to the
        three create actions and behind an extra hop. It used to be called
        Project Title and ask for one; it opens the panel the title now sits
        on, with the rest of what a plan is built from.
        """
        items = find(self.tree, 'Settings')['items']
        settings = next(i for i in items if i['text'] == 'Project Settings...')

        self.assertNotIn('submenu', settings)
        self.assertTrue(callable(settings['command']))

    def test_the_view_menu_is_what_this_window_shows(self):
        """
        The appearance, the critical path, and the guide.

        The chart's own settings went to Settings, beside the plan's other
        settings. Critical Path came the other way: it changes what the
        window shows rather than what the plan says.
        """
        view = labels(find(self.tree, 'View')['items'])

        self.assertEqual(view,
                         ['System UI mode', 'Critical Path...', 'Help'])
        self.assertNotIn('Project Info', view)

    def test_the_theme_modes_sit_under_system_ui_mode(self):
        """
        All three, so the choice is visible rather than a hidden toggle.

        The old entry was a single Toggle Theme that flipped whatever was on
        screen, with no way to say "follow the desktop again" and no sign of
        which of the two you were in.
        """
        view = find(self.tree, 'View')['items']
        entry = next(i for i in view if i['text'] == 'System UI mode')

        self.assertEqual(labels(entry['submenu']),
                         ['Sync with system', 'Always Day (light)',
                          'Always Night (dark)'])

    def test_edit_menu(self):
        """
        Create, Undo, Redo, Cut, Copy, and Paste are available under Edit.

        Create leads, because everything under it acts on a row that has to
        exist already. The clipboard entries name the key they answer to, in
        this platform's notation - see gantt_app.shortcuts.
        """
        from gantt_app.shortcuts import accelerator

        self.assertEqual(labels(find(self.tree, 'Edit')['items']),
                         ['Create', 'Undo', 'Redo',
                          f"Cut  ({accelerator('X')})",
                          f"Copy  ({accelerator('C')})",
                          f"Paste  ({accelerator('V')})"])


class TestMenuCommands(unittest.TestCase):
    """Every entry must lead somewhere."""

    def test_every_leaf_names_a_real_method(self):
        """No menu entry points at a command the toolbar does not have."""
        missing = []

        def walk(items, path):
            for item in items:
                where = f"{path} > {item['text']}"
                if 'submenu' in item:
                    walk(item['submenu'], where)
                    continue
                command = item.get('command')
                if command is None:
                    missing.append(f"{where} has no command")
                elif not hasattr(Toolbar, getattr(command, '__name__', '')):
                    missing.append(f"{where} -> {command}")

        for menu in menu_tree():
            walk(menu['items'], menu['text'])

        self.assertEqual(missing, [])

    def test_no_leaf_is_also_a_submenu(self):
        """An entry either runs a command or opens a submenu, never both."""
        def walk(items):
            for item in items:
                if 'submenu' in item:
                    self.assertNotIn('command', item, item['text'])
                    walk(item['submenu'])
                else:
                    self.assertIn('command', item, item['text'])

        for menu in menu_tree():
            walk(menu['items'])


if __name__ == '__main__':
    unittest.main()


class TestTheNewTaskHotkeyIsWired(unittest.TestCase):
    """The keyboard reaches the task list's own create action."""

    def test_the_toolbar_has_a_handler(self):
        """Bound in _bind_style_hotkeys, beside the other window hotkeys."""
        from gantt_app.views.toolbar import Toolbar

        self.assertTrue(callable(getattr(Toolbar, '_hotkey_new_task', None)))

    def test_it_asks_the_task_list_to_create_one(self):
        """And does nothing at all before the list exists."""
        from unittest import mock

        from gantt_app.views.toolbar import Toolbar

        stub = Toolbar.__new__(Toolbar)
        stub.task_list = None
        self.assertEqual(Toolbar._hotkey_new_task(stub), 'break')

        stub.task_list = mock.Mock(spec=['create_task_at_cursor'])
        Toolbar._hotkey_new_task(stub)
        stub.task_list.create_task_at_cursor.assert_called_once_with()
