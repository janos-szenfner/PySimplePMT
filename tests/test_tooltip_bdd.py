"""
pytest-bdd tests for tooltip functionality.

Run with:
    python3 -m pytest tests/test_tooltip_bdd.py -v
"""

import customtkinter as ctk
from pytest_bdd import given, parsers, scenarios, then, when
import pytest

from gantt_app.views.tooltip import Tooltip, attach


# Load the Gherkin scenarios
scenarios("features/tooltip.feature")


def _display_available() -> bool:
    """Whether a usable Tk display is present."""
    try:
        root = ctk.CTk()
        root.destroy()
        return True
    except Exception:
        return False


HAVE_DISPLAY = _display_available()


# SCENARIO: Attaching tooltip to button
@pytest.mark.skipif(not HAVE_DISPLAY, reason="needs a display")
@given("a button with tooltip for attachment", target_fixture="button_with_tooltip")
def button_with_tooltip():
    root = ctk.CTk()
    root.withdraw()
    button = ctk.CTkButton(root, text="Indent")
    button.pack()
    tooltip = attach(button, "Indent Task")
    root.update_idletasks()
    return button, tooltip, root


@pytest.mark.skipif(not HAVE_DISPLAY, reason="needs a display")
@then("attaching should return a Tooltip instance")
def check_tooltip_instance(button_with_tooltip):
    _, tooltip, _ = button_with_tooltip
    assert isinstance(tooltip, Tooltip)


@pytest.mark.skipif(not HAVE_DISPLAY, reason="needs a display")
@then("the tooltip should contain the specified text")
def check_tooltip_text(button_with_tooltip):
    _, tooltip, _ = button_with_tooltip
    assert tooltip.text == "Indent Task"


# SCENARIO: Nothing is attached without text
@pytest.mark.skipif(not HAVE_DISPLAY, reason="needs a display")
@given("a button with empty tooltip", target_fixture="button_empty")
def button_empty():
    root = ctk.CTk()
    root.withdraw()
    button = ctk.CTkButton(root, text="x")
    return button, root


@pytest.mark.skipif(not HAVE_DISPLAY, reason="needs a display")
@then("attaching should return None")
def check_no_tooltip_attached(button_empty):
    button, root = button_empty
    result = attach(button, "")
    assert result is None
    root.destroy()


# SCENARIO: Showing tooltip creates window
@pytest.mark.skipif(not HAVE_DISPLAY, reason="needs a display")
@given("a button with tooltip for display", target_fixture="button_display")
def button_display():
    root = ctk.CTk()
    root.withdraw()
    button = ctk.CTkButton(root, text="Indent")
    button.pack()
    tooltip = attach(button, "Indent Task")
    root.update_idletasks()
    return button, tooltip, root


@pytest.mark.skipif(not HAVE_DISPLAY, reason="needs a display")
@when("the tooltip is shown", target_fixture="shown_tooltip")
def shown_tooltip(button_display):
    _, tooltip, root = button_display
    tooltip._show()
    root.update_idletasks()
    return tooltip, root


@pytest.mark.skipif(not HAVE_DISPLAY, reason="needs a display")
@then("the tooltip window should be created")
def check_tooltip_window_created(shown_tooltip):
    tooltip, _ = shown_tooltip
    assert tooltip.window is not None


@pytest.mark.skipif(not HAVE_DISPLAY, reason="needs a display")
@then("the tooltip window should display the caption text")
def check_tooltip_window_text(shown_tooltip):
    tooltip, _ = shown_tooltip
    label = tooltip.window.winfo_children()[0]
    assert label.cget('text') == "Indent Task"


# SCENARIO: Leaving destroys tooltip window
@pytest.mark.skipif(not HAVE_DISPLAY, reason="needs a display")
@given("a button with tooltip for hide", target_fixture="button_hide")
def button_hide():
    root = ctk.CTk()
    root.withdraw()
    button = ctk.CTkButton(root, text="Indent")
    button.pack()
    tooltip = attach(button, "Indent Task")
    root.update_idletasks()
    return button, tooltip, root


@pytest.mark.skipif(not HAVE_DISPLAY, reason="needs a display")
@when("the tooltip is hidden", target_fixture="hidden_tooltip")
def hidden_tooltip(button_hide):
    _, tooltip, root = button_hide
    tooltip._show()
    root.update_idletasks()
    tooltip._on_leave()
    root.update_idletasks()
    return tooltip


@pytest.mark.skipif(not HAVE_DISPLAY, reason="needs a display")
@then("the tooltip window should be destroyed")
def check_tooltip_window_destroyed(hidden_tooltip):
    tooltip = hidden_tooltip
    assert tooltip.window is None


# SCENARIO: Canvas has Enter and Leave bindings
@pytest.mark.skipif(not HAVE_DISPLAY, reason="needs a display")
@given("a button with tooltip for bindings", target_fixture="button_bindings")
def button_bindings():
    root = ctk.CTk()
    root.withdraw()
    button = ctk.CTkButton(root, text="Indent")
    button.pack()
    attach(button, "Indent Task")
    root.update_idletasks()
    return button, root


@pytest.mark.skipif(not HAVE_DISPLAY, reason="needs a display")
@then("the canvas should have Enter binding")
def check_canvas_has_enter_binding(button_bindings):
    button, _ = button_bindings
    canvas = button.winfo_children()[0]
    bound = canvas.bind()
    assert '<Enter>' in bound


@pytest.mark.skipif(not HAVE_DISPLAY, reason="needs a display")
@then("the canvas should have Leave binding")
def check_canvas_has_leave_binding(button_bindings):
    button, _ = button_bindings
    canvas = button.winfo_children()[0]
    bound = canvas.bind()
    assert '<Leave>' in bound