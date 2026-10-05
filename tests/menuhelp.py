"""
Reading the toolbar's menu tree without a widget.

The tree is read from Toolbar._menu_definitions over a stub rather than
by building a Toolbar, which would need a display. Shared between the
menu-arrangement BDD suite and the modules that check where their
feature is offered.
"""
from types import SimpleNamespace

from gantt_app.views.toolbar import Toolbar


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
