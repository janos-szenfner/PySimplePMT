"""
pytest-bdd tests for the arrangement of the toolbar menus.

Run with:
    python3 -m pytest tests/test_toolbar_menus_bdd.py -q

The menu tree is read from Toolbar._menu_definitions rather than by
building a Toolbar, which would need a display. The keyboard tests
stand in events as SimpleNamespaces; nothing here opens a window.
"""
from functools import partial
from types import SimpleNamespace
from unittest import mock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.utils.shortcuts import (
    ALT, COMMAND_BIT, IS_MACOS, MAC_KEYCODES, MODIFIER, OPTION_BIT,
    accelerator, any_key_with, is_key,
)
from gantt_app.views.toolbar import Toolbar

pytestmark = [
    pytest.mark.toolbar_menus,
]

scenarios("features/toolbar_menus.feature")


def menu_tree():
    """Get the toolbar's menu definitions without a widget."""
    stub = SimpleNamespace(**{
        name: getattr(Toolbar, name)
        for name in dir(Toolbar)
        if callable(getattr(Toolbar, name, None))
        and not name.startswith('__')
    })
    return Toolbar._menu_definitions(stub)


def labels(items):
    return [item['text'] for item in items]


def find(tree, text):
    return next(menu for menu in tree if menu['text'] == text)


@pytest.fixture
def ctx():
    return SimpleNamespace(stub=None, result=None, create=None)


def _key_event(**fields):
    fields.setdefault('keysym', '')
    fields.setdefault('char', '')
    fields.setdefault('keycode', 0)
    fields.setdefault('state', 0)
    return SimpleNamespace(**fields)


# ------------------------------------------------------------------
# order
# ------------------------------------------------------------------

@then(parsers.parse('the menus read "{names}"'))
def the_menus_read(names):
    assert [m['text'] for m in menu_tree()] == names.split(', ')


@then(parsers.parse('"{text}" leads the menus'))
def a_menu_leads(text):
    assert menu_tree()[0]['text'] == text


@then(parsers.parse('"{text}" is not a menu'))
def not_a_menu(text):
    assert text not in [m['text'] for m in menu_tree()]


@then(parsers.parse('"{text}" ends the menus'))
def a_menu_ends(text):
    assert menu_tree()[-1]['text'] == text


@then(parsers.parse('"{text}" sits second from the end'))
def second_from_the_end(text):
    assert menu_tree()[-2]['text'] == text


# ------------------------------------------------------------------
# contents
# ------------------------------------------------------------------

@then(parsers.parse('"{menu}" holds "{items}"'))
def a_menu_holds(menu, items):
    assert labels(find(menu_tree(), menu)['items']) == \
        items.split(', ')


@then(parsers.parse('"{submenu}" under "{menu}" holds "{items}"'))
def a_submenu_holds(submenu, menu, items):
    parent = find(menu_tree(), menu)
    entry = next(i for i in parent['items'] if i['text'] == submenu)
    assert labels(entry['submenu']) == items.split(', ')


@then(parsers.parse('"{first}", "{second}" and "{third}" open submenus'))
def they_open_submenus(first, second, third):
    items = find(menu_tree(), 'Actions')['items']
    for text in (first, second, third):
        entry = next(i for i in items if i['text'] == text)
        assert entry['submenu']


@then(parsers.parse('"{entry}" under "{menu}" runs a command'))
def an_entry_runs_a_command(entry, menu):
    items = find(menu_tree(), menu)['items']
    item = next(i for i in items if i['text'] == entry)
    assert 'submenu' not in item
    assert callable(item['command'])


@then(parsers.parse('"{first}" and "{second}" are real methods'))
def they_are_real_methods(first, second):
    assert callable(getattr(Toolbar, first, None))
    assert callable(getattr(Toolbar, second, None))


@then(parsers.parse('"{method}" is a real method'))
def it_is_a_real_method(method):
    assert callable(getattr(Toolbar, method, None))


@then(parsers.parse('"{menu}" does not hold "{first}" or "{second}"'))
def a_menu_does_not_hold_either(menu, first, second):
    view = labels(find(menu_tree(), menu)['items'])
    assert first not in view
    assert second not in view


@then(parsers.parse('"{menu}" does not hold "{entry}"'))
def a_menu_does_not_hold(menu, entry):
    assert entry not in labels(find(menu_tree(), menu)['items'])


@then('"Edit" holds Create, the clipboard entries and the history '
      'entries')
def edit_menu_contents():
    expected = [
        'Create',
        f"Undo  ({accelerator('Z')})",
        f"Redo  ({accelerator('Z', shift=True)})",
        f"Cut  ({accelerator('X')})",
        f"Copy  ({accelerator('C')})",
        f"Paste  ({accelerator('V')})",
    ]
    assert labels(find(menu_tree(), 'Edit')['items']) == expected


# ------------------------------------------------------------------
# every entry leads somewhere
# ------------------------------------------------------------------

@then("every leaf command names a method the toolbar has")
def every_leaf_names_a_method():
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
            else:
                name = getattr(command, '__name__', '')
                if not name and isinstance(command, partial):
                    name = getattr(getattr(command, 'func', None),
                                   '__name__', '')
                if not hasattr(Toolbar, name):
                    missing.append(f"{where} -> {command}")

    for menu in menu_tree():
        walk(menu['items'], menu['text'])
    assert missing == []


@then("every item is a command or a submenu, never both")
def every_item_is_one_or_the_other():
    def walk(items):
        for item in items:
            if 'submenu' in item:
                assert 'command' not in item, item['text']
                walk(item['submenu'])
            else:
                assert 'command' in item, item['text']

    for menu in menu_tree():
        walk(menu['items'])


# ------------------------------------------------------------------
# the hotkey and the menu's New Task
# ------------------------------------------------------------------

@given("a toolbar stub with no task list")
def a_stub_with_no_task_list(ctx):
    ctx.stub = Toolbar.__new__(Toolbar)
    ctx.stub.task_list = None


@given("a toolbar stub whose task list listens")
def a_stub_whose_task_list_listens(ctx):
    ctx.stub = Toolbar.__new__(Toolbar)
    ctx.stub.task_list = mock.Mock(spec=['create_task_at_cursor'])


@when("the hotkey is pressed")
def the_hotkey_is_pressed(ctx):
    ctx.result = Toolbar._hotkey_new_task(ctx.stub)


@when("the menu's New Task runs")
def the_menus_new_task_runs(ctx):
    with mock.patch.object(Toolbar, '_create_of_type') as make:
        ctx.result = Toolbar.add_task(ctx.stub)
    ctx.create = make


@then(parsers.parse('"{text}" answers'))
def the_answer_is(ctx, text):
    assert ctx.result == text


@then("nothing answers")
def nothing_answers(ctx):
    assert ctx.result is None


@then("the task list is asked to create at the cursor")
def the_task_list_is_asked(ctx):
    ctx.stub.task_list.create_task_at_cursor.assert_called_once_with()
    ctx.stub.task_list.reset_mock()


@then("the task list is not asked again")
def the_task_list_is_not_asked_again(ctx):
    ctx.stub.task_list.create_task_at_cursor.assert_not_called()


@then("the task list is not asked")
def the_task_list_is_not_asked(ctx):
    ctx.stub.task_list.create_task_at_cursor.assert_not_called()


@then(parsers.parse('a plain "{kind}" is created instead'))
def a_plain_task_is_created(ctx, kind):
    ctx.create.assert_called_once_with(kind)


# ------------------------------------------------------------------
# Option is a compose key
# ------------------------------------------------------------------

@then(parsers.parse('a key event with keysym "{keysym}" and char '
                    '"{char}" answers "{key}"'))
def the_key_event_answers(keysym, char, key):
    assert is_key(_key_event(keysym=keysym, char=char), key)


@then(parsers.parse('a key event with keysym "{keysym}", char "{char}" '
                    'and the "{key}" keycode answers "{key2}"'))
def the_dead_key_answers(keysym, char, key, key2):
    if not IS_MACOS:
        pytest.skip("the keycode fallback is macOS only")
    event = _key_event(keysym=keysym, char=char,
                       keycode=MAC_KEYCODES[key])
    assert is_key(event, key2)


@then(parsers.parse('a key event with keysym "{keysym}" and char '
                    '"{char}" does not answer "{key}"'))
def the_key_event_does_not_answer(keysym, char, key):
    event = _key_event(keysym=keysym, char=char, keycode=38)
    assert not is_key(event, key)


@then('"any_key_with" alt names the Command-Option keypress')
def the_catch_all_names_the_modifiers():
    assert any_key_with(alt=True) == f"<{MODIFIER}-{ALT}-KeyPress>"


@when(parsers.parse('"{char}" is pressed with Option'))
def a_key_is_pressed_with_option(ctx, char):
    keysym = 'period' if char == 'period' else char
    event = _key_event(keysym=keysym,
                       char='.' if char == 'period' else char,
                       keycode=0 if char == 'period' else 38)
    ctx.result = Toolbar._alt_key_pressed(ctx.stub, event)


# ------------------------------------------------------------------
# the net under the shortcut
# ------------------------------------------------------------------

def _press_the_net(ctx, keysym, char, keycode, state):
    """Run _any_key_pressed with the platform branch forced on."""
    from gantt_app.utils import shortcuts

    event = _key_event(keysym=keysym, char=char, keycode=keycode,
                       state=state)
    with mock.patch.object(shortcuts, 'IS_MACOS', True):
        ctx.result = Toolbar._any_key_pressed(ctx.stub, event)


@when(parsers.parse('"{keysym}" is pressed under Command and Option '
                    'with the "{key}" keycode'))
def pressed_under_command_option(ctx, keysym, key):
    keycode = MAC_KEYCODES[key] << 16 if key == '.' else 38
    _press_the_net(ctx, keysym, '…' if key == '.' else '∆', keycode,
                   COMMAND_BIT | OPTION_BIT)


@when(parsers.parse('"{keysym}" is pressed under Command alone with '
                    'the "{key}" keycode'))
def pressed_under_command_alone(ctx, keysym, key):
    _press_the_net(ctx, keysym, '…', MAC_KEYCODES[key], COMMAND_BIT)


@when(parsers.parse('"{char}" is pressed with nothing held'))
def pressed_with_nothing_held(ctx, char):
    keysym, keycode = ('period', MAC_KEYCODES['.']) if char == '.' \
        else (char, 0)
    _press_the_net(ctx, keysym, char, keycode, 0)
