"""
pytest-bdd tests for the built-in and custom style presets (REQ-UI-020).

Run with:
    python3 -m pytest tests/test_preset_manager_bdd.py -q

Every manager here is built with its own settings file. The application shares
one manager that reads the real user settings.json; a test must neither depend
on what is in it nor write to it, so none of these touches it.

The display scenarios build the toolbar's item list and the settings grid
directly rather than opening the floating preset window, which is topmost and
watches for clicks - not something a headless test should drive.
"""
import os
import tempfile
import tkinter as tk

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.presets import PresetManager
from gantt_app.taskstyle import TaskStyle


def _display_available() -> bool:
    try:
        root = tk.Tk()
    except Exception:
        return False
    root.destroy()
    return True


HAVE_DISPLAY = _display_available()

scenarios("features/preset_manager.feature")


BUILTIN_NAMES = ["Financial Milestone", "Work Complete",
                 "Phase Gate / Approval", "Summary Phase"]


# ---------------------------------------------------------------------------
# The manager and its guardrails
# ---------------------------------------------------------------------------

@given("a preset manager with an isolated settings file",
       target_fixture="ctx")
def a_preset_manager(tmp_path):
    """A manager, its file, and a place to keep what a step needs later."""
    path = str(tmp_path / "settings.json")
    return {"path": path, "manager": PresetManager(settings_path=path),
            "calls": 0, "custom_id": None, "menu_items": None,
            "refused": None}


@given("a listener subscribed to the manager")
def a_listener_subscribed(ctx):
    """A listener that only counts how often it is told."""
    def listener():
        ctx["calls"] += 1
    ctx["manager"].subscribe(listener)


@then(parsers.parse("the built-in presets are {names}"))
def check_builtins_named(ctx, names):
    """The four that ship, in order."""
    wanted = [n.strip() for n in names.replace(" and ", ", ").split(", ")]
    assert [p.name for p in ctx["manager"].builtin()] == wanted


@when("a built-in preset is deleted")
def delete_a_builtin(ctx):
    """Financial Milestone, which must not go."""
    ctx["refused"] = not ctx["manager"].delete_custom("financial")


@when("a built-in preset is renamed")
def rename_a_builtin(ctx):
    """Phase Gate, which must not change."""
    ctx["refused"] = not ctx["manager"].update_custom("gate", name="Changed")


@then("the deletion is refused")
@then("the change is refused")
def check_refused(ctx):
    """The guardrail answered False."""
    assert ctx["refused"] is True


@then("the four built-ins are still present")
def check_four_builtins(ctx):
    assert [p.name for p in ctx["manager"].builtin()] == BUILTIN_NAMES


@then("the built-in keeps its name")
def check_builtin_name_kept(ctx):
    gate = ctx["manager"].get("gate")
    assert gate is not None and gate.name == "Phase Gate / Approval"


# ---------------------------------------------------------------------------
# Custom presets
# ---------------------------------------------------------------------------

@when(parsers.parse('a custom preset "{name}" is added'))
def add_a_custom(ctx, name):
    """Added through the manager, as the editor's Save would."""
    style = TaskStyle(fill_color="#fff2cc", text_color="#b9770e", bold=True)
    preset = ctx["manager"].add_custom(name, style, "◆", "#b9770e")
    ctx["custom_id"] = preset.id


@when("the manager is reloaded from the same file")
def reload_the_manager(ctx):
    """A second manager over the same file, as a restart would build."""
    ctx["manager"] = PresetManager(settings_path=ctx["path"])


@when(parsers.parse('that custom preset is renamed to "{name}"'))
def rename_the_custom(ctx, name):
    assert ctx["manager"].update_custom(ctx["custom_id"], name=name)


@when("that custom preset is deleted")
def delete_the_custom(ctx):
    assert ctx["manager"].delete_custom(ctx["custom_id"])


@then("the manager holds one custom preset")
def check_one_custom(ctx):
    assert len(ctx["manager"].custom()) == 1


@then("the manager holds no custom presets")
def check_no_custom(ctx):
    assert ctx["manager"].custom() == []


@then(parsers.parse('"{name}" appears after the built-ins'))
def check_custom_after_builtins(ctx, name):
    names = [p.name for p in ctx["manager"].all()]
    assert names[:4] == BUILTIN_NAMES
    assert names[-1] == name


@then(parsers.parse(
    'the reloaded manager holds a custom preset named "{name}"'))
@then(parsers.parse('the manager holds a custom preset named "{name}"'))
def check_named_custom(ctx, name):
    assert [p.name for p in ctx["manager"].custom()] == [name]


@then("the listener was told once")
def check_told_once(ctx):
    assert ctx["calls"] == 1


@then("the listener was told three times")
def check_told_thrice(ctx):
    assert ctx["calls"] == 3


# ---------------------------------------------------------------------------
# The toolbar menu
# ---------------------------------------------------------------------------

@pytest.fixture
def bar_root():
    import customtkinter as ctk

    root = ctk.CTk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except tk.TclError:
        pass


@given("a style bar reading that manager")
def a_style_bar_reading_that_manager(ctx, bar_root):
    """A bar whose menu items are built from this manager."""
    from gantt_app.views.stylebar import StyleBar

    bar = StyleBar(bar_root, on_apply=lambda _k, _v: None)
    bar.enabled = True
    ctx["bar"] = bar


@when("the preset menu items are built")
def build_menu_items(ctx):
    ctx["menu_items"] = ctx["bar"]._preset_menu_items(ctx["manager"])


def _headers(items):
    return [i.get("text") for i in items if i.get("type") == "header"]


@then(parsers.parse('there is a "{header}" header'))
def check_header_present(ctx, header):
    assert header in _headers(ctx["menu_items"])


@then(parsers.parse('there is no "{header}" header'))
def check_header_absent(ctx, header):
    assert header not in _headers(ctx["menu_items"])


@then(parsers.parse('a preview row named "{name}" is in the menu'))
def check_preview_named(ctx, name):
    names = [i.get("text") for i in ctx["menu_items"]
             if i.get("type") == "preview"]
    assert name in names


# ---------------------------------------------------------------------------
# The Settings tab
# ---------------------------------------------------------------------------

@given("a style-presets settings tab reading that manager")
def a_settings_tab(ctx, bar_root):
    from gantt_app.views.presetsettings import StylePresetsTab

    tab = StylePresetsTab(bar_root, ctx["manager"])
    tab.update_idletasks()
    ctx["tab"] = tab


def _labels(widget):
    import customtkinter as ctk

    found = []

    def walk(node):
        for child in node.winfo_children():
            if isinstance(child, ctk.CTkLabel):
                found.append(str(child.cget("text")))
            walk(child)

    walk(widget)
    return found


def _buttons(widget):
    import customtkinter as ctk

    found = []

    def walk(node):
        for child in node.winfo_children():
            if isinstance(child, ctk.CTkButton):
                found.append(str(child.cget("text")))
            walk(child)

    walk(widget)
    return found


@then("every built-in row shows a locked badge")
def check_locked_badges(ctx):
    labels = _labels(ctx["tab"].grid_frame)
    assert labels.count("🔒 Locked") == 4, labels


@then("no built-in row offers Edit or Delete")
def check_no_builtin_actions(ctx):
    # With no custom presets, no Edit or Delete button exists at all.
    buttons = _buttons(ctx["tab"].grid_frame)
    assert "Edit" not in buttons and "Delete" not in buttons, buttons


@then(parsers.parse('the settings grid shows a row named "{name}"'))
def check_grid_row(ctx, name):
    ctx["tab"].update_idletasks()
    assert name in _labels(ctx["tab"].grid_frame)


@then("that row offers Edit and Delete")
def check_custom_actions(ctx):
    buttons = _buttons(ctx["tab"].grid_frame)
    assert "Edit" in buttons and "Delete" in buttons, buttons
