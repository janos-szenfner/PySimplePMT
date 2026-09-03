"""
pytest-bdd tests for the visual style-preset menu.

Run with:
    python3 -m pytest tests/test_style_presets_bdd.py -q

WHY THIS MODULE EXISTS:
======================
Issue #9: the preset dropdown listed plain names, so a reader had to apply a
preset to find out what it looked like. Issue #10: putting a tried preset back
meant leaving the menu for the Clear button beside it. The menu now shows each
preset as a live preview and heads the list with a Default entry.

DEVELOPMENT NOTES:
------------------
The scenarios that open the menu patch CTkDropdownMenu with a recorder rather
than letting the real floating window build. The item list is what carries the
badges, the previews and the commands, and the Toplevel that would draw them is
topmost, borderless and watches for clicks - none of which a headless test
wants to drive. The one scenario that checks the drawing builds a real menu
from preview items and reads its widgets back, the way test_menu_dismissal
does, settling it with update_idletasks rather than a full update.
"""
import os
import tempfile
import tkinter as tk

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.taskstyle import (
    DEFAULT_BADGE, PRESETS, preset_badge,
)


def _display_available() -> bool:
    try:
        root = tk.Tk()
    except Exception:
        return False
    root.destroy()
    return True


HAVE_DISPLAY = _display_available()

scenarios("features/style_presets.feature")


class RecordingMenu:
    """A stand-in for CTkDropdownMenu that keeps the items it was handed."""

    def __init__(self, master, items, **kwargs):
        self.items = items

    def geometry(self, *_args):
        """The real menu positions itself; this ignores it."""


# ---------------------------------------------------------------------------
# The badges, which need no display
# ---------------------------------------------------------------------------

@then("every preset should have a badge glyph and colour")
def check_every_preset_has_a_badge():
    """A shape and a colour to know each preset by; see issue #9."""
    for name, _style in PRESETS:
        glyph, colour = preset_badge(name)
        assert glyph, name
        assert colour.startswith('#'), (name, colour)


@then("the badge for an unknown preset should be the hollow default")
def check_unknown_falls_back():
    """A missing badge is decoration, never a reason a menu cannot draw."""
    assert preset_badge("Nothing named this") == DEFAULT_BADGE


# ---------------------------------------------------------------------------
# The menu the style bar builds
# ---------------------------------------------------------------------------

@pytest.fixture
def bar_root():
    """A window for the style bar to live in."""
    import customtkinter as ctk

    root = ctk.CTk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except tk.TclError:
        pass


@pytest.fixture
def manager():
    """
    A preset manager with its own settings file and no custom presets.

    Isolated on purpose: the toolbar uses the application-wide default
    manager, which reads the real user settings.json - a test must neither
    depend on what is in it nor write to it.
    """
    from gantt_app.presets import PresetManager

    path = os.path.join(tempfile.mkdtemp(), 'settings.json')
    return PresetManager(settings_path=path)


@given("a style bar with a selection", target_fixture="bar")
def a_style_bar_with_a_selection(bar_root):
    """
    A bar that reports what it is asked to apply.

    Built on its own rather than through a whole toolbar: _open_presets needs
    the bar enabled and its own preset button, and nothing else.
    """
    from gantt_app.views.stylebar import StyleBar

    applied = []
    bar = StyleBar(bar_root, on_apply=lambda kind, value:
                   applied.append((kind, value)))
    bar.enabled = True
    bar._applied = applied
    return bar


@when("the preset menu is opened", target_fixture="menu_items")
def the_preset_menu_is_opened(bar, manager):
    """
    The rows _open_presets would hand the floating window.

    Built through the real item builder against an isolated manager, rather
    than opening the topmost window, which watches for clicks and does not
    want driving from a headless test. See the module note.
    """
    return bar._preset_menu_items(manager)


@when(parsers.parse('the "{label}" entry is chosen'))
def the_entry_is_chosen(bar, menu_items, label):
    """Run the row's command, as a click on it would."""
    item = next(i for i in menu_items if i.get('text') == label)
    item['command']()


@then(parsers.parse('the first entry should be "{label}"'))
def check_first_entry(menu_items, label):
    """Default heads the list, where the eye already is; see issue #10."""
    previews = [i for i in menu_items if i.get('type') == 'preview']
    assert previews[0]['text'] == label


@then("a preview row should follow for every preset")
def check_a_preview_per_preset(menu_items):
    """Every preset is a preview row, plus the Default one ahead of them."""
    previews = [i for i in menu_items if i.get('type') == 'preview']
    names = [i['text'] for i in previews]
    for preset_name, _style in PRESETS:
        assert preset_name in names, preset_name
    # Default entry plus one per preset
    assert len(previews) == len(PRESETS) + 1


@then(parsers.parse('the "{label}" preview should match its style'))
def check_named_preview_matches(menu_items, label):
    """The chip is drawn from the very style the click applies."""
    style = dict(PRESETS)[label]
    item = next(i for i in menu_items if i.get('text') == label)
    preview = item['preview']

    assert preview.get('fill') == style.fill_color
    assert preview.get('text_color') == style.text_color
    assert preview.get('bold') == bool(style.bold)
    assert preview.get('italic') == bool(style.italic)
    assert preview.get('underline') == bool(style.underline)


@then("every preview chip should match the style it applies")
def check_every_preview_matches(menu_items):
    """No preset's preview may promise a look its click does not deliver."""
    by_name = dict(PRESETS)
    for item in menu_items:
        if item.get('type') != 'preview':
            continue
        name = item['text']
        if name not in by_name:
            continue                    # the Default entry has no style
        style = by_name[name]
        preview = item['preview']
        assert preview.get('fill') == style.fill_color, name
        assert preview.get('text_color') == style.text_color, name
        assert preview.get('bold') == bool(style.bold), name


@then(parsers.parse('the style bar should apply the "{label}" preset'))
def check_preset_applied(bar, label):
    """The command hands _apply the preset's own TaskStyle."""
    style = dict(PRESETS)[label]
    assert ('preset', style) in bar._applied


@then("the style bar should clear the formatting")
def check_formatting_cleared(bar):
    """Default is the way back to no style; see issue #10."""
    assert ('reset', None) in bar._applied


# ---------------------------------------------------------------------------
# The drawing itself
# ---------------------------------------------------------------------------

@given("a preview menu for the presets", target_fixture="preview_menu")
def a_preview_menu_for_the_presets(bar_root):
    """
    A real dropdown built from preview items.

    Settled with update_idletasks, not update: the menu is topmost and
    watches for clicks, and a full update pumps that machinery. See the
    module note.
    """
    from gantt_app.taskstyle import preset_badge
    from gantt_app.views.toolbar import CTkDropdownMenu

    items = []
    for name, style in PRESETS:
        glyph, colour = preset_badge(name)
        items.append({
            "type": "preview", "text": name,
            "badge": glyph, "badge_color": colour,
            "preview": {
                "sample": "Sample",
                "fill": style.fill_color,
                "text_color": style.text_color,
                "bold": bool(style.bold),
                "italic": bool(style.italic),
                "underline": bool(style.underline),
            },
            "command": lambda: None,
        })

    menu = CTkDropdownMenu(bar_root, items=items)
    menu.update_idletasks()
    yield menu
    try:
        menu.destroy()
    except tk.TclError:
        pass


@then(parsers.parse(
    'the "{label}" row should show its badge, name and chip'))
def check_row_shows_all_three(preview_menu, label):
    """Three columns: a badge, the name, and a chip drawn in the style."""
    import customtkinter as ctk

    from gantt_app.taskstyle import preset_badge

    def walk(widget):
        for kid in widget.winfo_children():
            yield kid
            yield from walk(kid)

    labels = [w for w in walk(preview_menu) if isinstance(w, ctk.CTkLabel)]
    texts = [str(w.cget('text')) for w in labels]

    glyph, _colour = preset_badge(label)
    assert glyph in texts, f"no badge for {label}: {texts}"
    assert any('Sample' in t for t in texts), f"no chip: {texts}"

    # The name is a button, so it is not among the labels above
    buttons = [w for w in walk(preview_menu) if isinstance(w, ctk.CTkButton)]
    assert any(label in str(b.cget('text')) for b in buttons), label
