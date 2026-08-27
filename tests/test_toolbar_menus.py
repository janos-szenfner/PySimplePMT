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
        """Project, File, Actions, Edit, then View last."""
        self.assertEqual([menu['text'] for menu in self.tree],
                         ['Project', 'File', 'Actions', 'Edit', 'View'])

    def test_view_is_last(self):
        """View stays at the end of the list."""
        self.assertEqual(self.tree[-1]['text'], 'View')


class TestMenuContents(unittest.TestCase):
    """What sits under each menu."""

    def setUp(self):
        """Set up test fixtures."""
        self.tree = menu_tree()

    def test_project_menu(self):
        """Project holds the file lifecycle actions."""
        self.assertEqual(
            labels(find(self.tree, 'Project')['items']),
            ['New Project...', 'Load Project...', 'Save Project...',
             'Save Project As...'])

    def test_file_menu_nests_import_and_export(self):
        """File carries Import and Export as submenus."""
        items = find(self.tree, 'File')['items']

        self.assertEqual(labels(items), ['Import', 'Export'])
        for item in items:
            self.assertIn('submenu', item)
            self.assertTrue(item['submenu'])

    def test_import_submenu_formats(self):
        """Every import format is reachable under File > Import."""
        items = find(self.tree, 'File')['items']
        imports = next(i for i in items if i['text'] == 'Import')

        self.assertEqual(labels(imports['submenu']),
                         ['MS Project...', 'GAN...', 'Mermaid...', 'XLSX...'])

    def test_export_submenu_formats(self):
        """Every export format is reachable under File > Export."""
        items = find(self.tree, 'File')['items']
        exports = next(i for i in items if i['text'] == 'Export')

        self.assertEqual(labels(exports['submenu']),
                         ['GAN...', 'MS Project...', 'Mermaid...', 'HTML...',
                          'SVG...', 'PNG...', 'PDF...', 'XLSX...'])

    def test_actions_holds_the_settings_for_the_plan(self):
        """
        What is set about the plan as a whole, and the analysis of it.

        Create moved to Edit - making a row is an edit - and how the chart
        is drawn came here from View, because that is a setting of the plan
        rather than of this window.
        """
        items = find(self.tree, 'Actions')['items']

        self.assertEqual(labels(items),
                         ['Project Settings...', 'Calendar Settings...',
                          'Gantt Settings...', 'Critical Path...'])
        for item in items:
            self.assertNotIn('submenu', item)

    def test_calendar_settings_sits_directly_under_actions(self):
        """
        Choosing which days the plan works is not a create action.

        It belongs beside Project Title: both change something about the whole
        project rather than adding a row to it.
        """
        items = find(self.tree, 'Actions')['items']
        entry = next(i for i in items if i['text'] == 'Calendar Settings...')

        self.assertNotIn('submenu', entry)
        self.assertTrue(callable(entry['command']))

    def test_create_submenu_holds_only_the_create_actions(self):
        """Create offers the things that can be created, nothing else."""
        create = find(self.tree, 'Edit')['items'][0]

        self.assertEqual(labels(create['submenu']),
                         ['Phase...', 'Deliverable...', 'Task...',
                          'Subtask...', 'Milestone...'])

    def test_project_settings_sits_directly_under_actions(self):
        """
        The settings that apply to the whole plan are reachable in one step.

        This entry used to sit inside Create, which put a rename next to the
        three create actions and behind an extra hop. It used to be called
        Project Title and ask for one; it opens the panel the title now sits
        on, with the rest of what a plan is built from.
        """
        items = find(self.tree, 'Actions')['items']
        settings = next(i for i in items if i['text'] == 'Project Settings...')

        self.assertNotIn('submenu', settings)
        self.assertTrue(callable(settings['command']))

    def test_project_info_left_the_view_menu(self):
        """View no longer offers Project Info."""
        view = labels(find(self.tree, 'View')['items'])

        # The chart's settings went to Actions, beside the plan's other
        # settings; what is left here is about this window
        self.assertEqual(view, ['System UI mode', 'Help'])
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
