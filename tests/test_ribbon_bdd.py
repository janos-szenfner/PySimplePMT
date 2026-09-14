"""
pytest-bdd tests for the ribbon.

The ribbon is the tabbed command band that took the place of the menu row
and the icon row. These steps exercise the chrome around the commands -
the tabs, the captioned groups, the galleries, the backstage and the fold
- rather than the commands themselves, which the toolbar's own tests cover.

Run with:
    python3 -m pytest tests/test_ribbon_bdd.py -v
"""

import re

import customtkinter as ctk
from pytest_bdd import given, parsers, scenarios, then, when
import pytest


scenarios("features/ribbon.feature")


def _display_available() -> bool:
    """Whether a usable Tk display is present."""
    try:
        root = ctk.CTk()
        root.destroy()
        return True
    except Exception:
        return False


HAVE_DISPLAY = _display_available()
needs_display = pytest.mark.skipif(not HAVE_DISPLAY,
                                   reason="needs a display")


def _quoted(text: str):
    """The quoted words of a step's list: '"a", "b" and "c"' -> [a, b, c]."""
    return re.findall(r'"([^"]+)"', text)


def _descendants(widget):
    """Every widget under this one, the widget itself first."""
    yield widget
    for child in widget.winfo_children():
        yield from _descendants(child)


@pytest.fixture
def ribbon_root():
    """A window to hang the toolbar off, closed after the scenario."""
    root = ctk.CTk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


@needs_display
@given("a toolbar over an open plan", target_fixture="toolbar")
def a_toolbar_over_an_open_plan(ribbon_root):
    """The whole top of the window: the ribbon, and the menus behind it."""
    from gantt_app.models import Project
    from gantt_app.views.toolbar import Toolbar

    toolbar = Toolbar(ribbon_root, Project(name="Plan"))
    ribbon_root.update_idletasks()
    return toolbar


# ---- the tabs -------------------------------------------------------------

@then(parsers.re(r'the ribbon offers the tabs (?P<tabs>.*)'))
def ribbon_offers_tabs(toolbar, tabs):
    """The strip's tabs, in order."""
    assert list(toolbar.icon_toolbar._tab_buttons) == _quoted(tabs)


@then(parsers.parse('the "{name}" tab is showing'))
def tab_is_showing(toolbar, name):
    """Its page is packed into the band and its tab is the marked one."""
    ribbon = toolbar.icon_toolbar
    assert ribbon._active_tab == name
    assert ribbon._pages[name].winfo_manager() == 'pack'


@when(parsers.parse('the user picks the "{name}" tab'))
def user_picks_tab(toolbar, name):
    toolbar.icon_toolbar.select_tab(name)


@then(parsers.parse("the \"{name}\" tab's page is not shown"))
def tab_page_not_shown(toolbar, name):
    assert toolbar.icon_toolbar._pages[name].winfo_manager() == ''


# ---- the groups -------------------------------------------------------------

@then(parsers.re(r'the "(?P<tab>[^"]+)" tab has the groups (?P<groups>.*)'))
def tab_has_groups(toolbar, tab, groups):
    """The captioned groups stand in the order the ribbon declares."""
    expected = _quoted(groups)
    actual = [caption for (t, caption)
              in toolbar.icon_toolbar._groups if t == tab]
    assert actual == expected


@then(parsers.parse('the "{group}" group holds the formatting bar'))
def group_holds_formatting_bar(toolbar, group):
    """The StyleBar is mounted in the group, not beside it."""
    ribbon_group = toolbar.icon_toolbar._groups[('Task', group)]
    assert toolbar.icon_toolbar.style_bar.master is ribbon_group.body


@then(parsers.parse('the "{group}" group holds the progress controls'))
def group_holds_progress_controls(toolbar, group):
    ribbon_group = toolbar.icon_toolbar._groups[('Task', group)]
    assert toolbar.icon_toolbar.progress_group.master is ribbon_group.body


# ---- the strip ---------------------------------------------------------------

@then(parsers.re(r'the strip offers the icons (?P<icons>.*)'))
def strip_offers_icons(toolbar, icons):
    """The quick-access buttons, drawn on the strip rather than the band."""
    strip = toolbar.icon_toolbar._strip
    for name in _quoted(icons):
        widget = toolbar.icon_toolbar.icon_buttons[name]
        while widget is not None and widget is not strip:
            widget = getattr(widget, 'master', None)
        assert widget is strip, name


# ---- a press reaches the action ------------------------------------------------

@when(parsers.parse('the "{name}" button is pressed'),
      target_fixture="pressed")
def press_button(toolbar, name):
    """
    A spy stands in for the handler, so the press is measured rather than
    its effect - the effects have their own tests.
    """
    ribbon = toolbar.icon_toolbar
    action = next(
        spec['action']
        for _tab, groups in ribbon.RIBBON
        for _caption, contents in groups
        if not isinstance(contents, str)
        for spec in contents
        if spec['key'] == name and spec.get('action'))
    called = []
    setattr(ribbon, action, lambda: called.append(True))
    ribbon.icon_buttons[name].invoke()
    return called


@then(parsers.parse('the "{handler}" handler ran'))
def handler_ran(toolbar, pressed, handler):
    assert pressed, f"{handler} was not called"


# ---- the galleries -------------------------------------------------------------

def _open_dropdown_labels(toolbar):
    """What the gallery the ribbon has open is offering."""
    menu = toolbar.icon_toolbar._open_dropdown
    assert menu is not None and menu.winfo_exists()
    return [item['label'] for item in menu.items]


@when('the "New Task" arrow is pressed')
def press_new_task_arrow(toolbar):
    """The drop-down half of the split button, not the command half."""
    toolbar.icon_toolbar.icon_buttons['task'].split_arrow.invoke()


@then(parsers.re(r'a drop-down offers (?P<labels>.*)'))
def dropdown_offers(toolbar, labels):
    assert _open_dropdown_labels(toolbar) == _quoted(labels)


@when('the "Compare" gallery is opened')
def open_compare_gallery(toolbar):
    toolbar.icon_toolbar.icon_buttons['baseline_compare'].invoke()


@then(parsers.re(r'it offers (?P<labels>.*)'))
def gallery_offers(toolbar, labels):
    assert _open_dropdown_labels(toolbar) == _quoted(labels)


# ---- the backstage -------------------------------------------------------------

@when('the user opens the File backstage')
def open_backstage(toolbar):
    toolbar.icon_toolbar.toggle_backstage()


@then('the backstage is showing')
def backstage_showing(toolbar):
    backstage = toolbar.icon_toolbar._backstage
    assert backstage is not None and backstage.winfo_exists()


@then(parsers.re(r'the backstage offers (?P<labels>.*)'))
def backstage_offers(toolbar, labels):
    backstage = toolbar.icon_toolbar._backstage
    texts = [w.cget('text') for w in _descendants(backstage)
             if isinstance(w, ctk.CTkButton)]
    for label in _quoted(labels):
        assert any(label in text for text in texts), label


@when('the user goes back')
def user_goes_back(toolbar):
    toolbar.icon_toolbar._backstage.close()


@then('the backstage is gone')
def backstage_gone(toolbar):
    backstage = toolbar.icon_toolbar._backstage
    assert backstage is None or not backstage.winfo_exists()


# ---- the fold -------------------------------------------------------------

@when('the ribbon is folded')
def fold_ribbon(toolbar):
    toolbar.icon_toolbar.set_collapsed(True)


@then('the band is not shown')
def band_not_shown(toolbar):
    assert toolbar.icon_toolbar._band.winfo_manager() == ''


@when('the ribbon is unfolded')
def unfold_ribbon(toolbar):
    toolbar.icon_toolbar.set_collapsed(False)


# ---- the wiring -------------------------------------------------------------

@then('every action the ribbon names resolves to a callable')
def every_action_resolves(toolbar):
    """
    No button may name an action nobody connected.

    The check that used to catch the critical-path icon doing nothing,
    read off the ribbon's own list so the two cannot drift apart.
    """
    missing = [
        action for action in toolbar.icon_toolbar.action_names()
        if not callable(getattr(toolbar.icon_toolbar, action, None))
    ]
    assert not missing, missing


# ---- the menus behind it ------------------------------------------------------

@then(parsers.parse('the menu bar still offers "{item}" under "{menu}"'))
def menu_still_offers(toolbar, item, menu):
    """
    The menu bar is not drawn any more, but it is still built: the
    baseline's active marker and the tests that read menu_config ask it,
    not the ribbon.
    """
    def find(entries):
        for entry in entries:
            if entry.get('label') == item:
                return True
            if find(entry.get('items', [])):
                return True
        return False

    assert find(toolbar.menu_bar.menu_config.get(menu, []))
