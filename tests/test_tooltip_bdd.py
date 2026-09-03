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

# ---------------------------------------------------------------------------
# When the caption appears, and when it goes away
#
# Restored from test_tooltip.py. The conversion kept attaching, showing and
# hiding, and left behind the timing - which is the half that can be wrong
# without looking wrong: a caption that appears the instant the pointer
# crosses a row, or one left waiting after the pointer has gone.
#
# These use a fixture that closes its window, rather than the Givens above
# that open a root each and leave it; see tests/conftest.py for what a
# leaked root does to every module that runs after it.
# ---------------------------------------------------------------------------

@pytest.fixture
def hover_root():
    """A window to hang the buttons off."""
    root = ctk.CTk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


@given("a button with hover text", target_fixture="hover")
def a_button_with_hover_text(hover_root):
    """A button carrying a caption, and the tooltip that draws it."""
    button = ctk.CTkButton(hover_root, text="Indent")
    button.pack()
    tooltip = attach(button, "Indent Task")
    hover_root.update_idletasks()
    return button, tooltip


@given("a fresh button", target_fixture="fresh_button")
def a_fresh_button(hover_root):
    """One that has never been given a caption."""
    button = ctk.CTkButton(hover_root, text="Outdent")
    button.pack()
    hover_root.update_idletasks()
    return button


@given("an icon toolbar over an empty plan", target_fixture="icon_toolbar")
def an_icon_toolbar_over_an_empty_plan(hover_root):
    """The row of buttons every caption is meant to be on."""
    from gantt_app.models import Project
    from gantt_app.views.toolbar import IconToolbar

    toolbar = IconToolbar(hover_root, Project(name="Demo"))
    hover_root.update_idletasks()
    return toolbar


@when("the tooltip is shown twice", target_fixture="two_windows")
def the_tooltip_is_shown_twice(hover):
    """The pointer re-entering a child must not stack them up."""
    _button, tooltip = hover
    tooltip._show()
    first = tooltip.window
    tooltip._show()
    return first, tooltip.window


@when("the pointer enters the button")
def the_pointer_enters_the_button(hover):
    """Which starts the wait rather than drawing anything."""
    _button, tooltip = hover
    tooltip._on_enter()


@when("the pointer leaves the button")
def the_pointer_leaves_the_button(hover):
    """Crossing the row on the way somewhere else."""
    _button, tooltip = hover
    tooltip._on_leave()


@when(parsers.parse('the same button is given the text "{text}"'),
      target_fixture="reattached")
def the_same_button_is_given_the_text(hover, text):
    """
    The day/night control is rebuilt whenever the mode changes.

    Attaching a second time would bind <Enter> again with add='+', so the
    button would gain a binding on every toggle.

    The reference is put on the button first because that is what the caller
    does with it - attach returns the tooltip "kept by the caller so it is
    not collected", and the toolbar keeps it there. attach looks for it under
    that name to decide whether it has been here before.
    """
    button, tooltip = hover
    button.tooltip_widget = tooltip
    return attach(button, text)


@when("the button is given hover text", target_fixture="binding_cost")
def the_button_is_given_hover_text(fresh_button):
    """
    Measured against what one plain binding costs.

    Not against a number written here: a CTkButton binds <Enter> for its own
    hover before any of this, and Tk writes several lines of script per
    callback, so neither figure is one this test can know up front.
    """
    canvas = fresh_button.winfo_children()[0]

    def lines():
        return len(canvas.bind('<Enter>').strip().splitlines())

    before = lines()
    attach(fresh_button, "Outdent Task")
    after_tooltip = lines()

    fresh_button.bind('<Enter>', lambda _event: None, add='+')
    return after_tooltip - before, lines() - after_tooltip


@when("the button is destroyed and the tooltip shown")
def the_button_is_destroyed_and_the_tooltip_shown(hover):
    """A dialog closing under the pointer is not an error."""
    button, tooltip = hover
    button.destroy()
    tooltip._show()


@then("both shows should be the same window")
def check_one_window(two_windows):
    """One caption, however many times the pointer crosses it."""
    first, second = two_windows
    assert first is second


@then("a caption should be waiting to appear")
def check_a_caption_is_waiting(hover):
    """The wait is what stops it flashing up as the pointer passes."""
    _button, tooltip = hover
    assert tooltip._after_id is not None


@then("nothing should be waiting to appear")
def check_nothing_is_waiting(hover):
    """Leaving calls the wait off."""
    _button, tooltip = hover
    assert tooltip._after_id is None


@then("no tooltip window should exist yet")
def check_no_window_yet(hover):
    """Nothing is drawn until the delay is up."""
    _button, tooltip = hover
    assert tooltip.window is None


@then("the canvas should have a button press binding")
def check_button_press_binding(hover):
    """
    Hover text over a menu the button just opened would be in the way.

    The binding is checked rather than the press delivered: a press cannot
    be delivered to an unmapped window either. Tk stores a ButtonPress
    binding under its short name.
    """
    button, _tooltip = hover
    canvas = button.winfo_children()[0]
    assert '<Button>' in canvas.bind()


@then("the same tooltip should be returned")
def check_same_tooltip_returned(hover, reattached):
    """Rather than a second one bound alongside the first."""
    _button, tooltip = hover
    assert reattached is tooltip


@then(parsers.parse('the tooltip text should be "{text}"'))
def check_tooltip_text(hover, text):
    """And it says the new thing."""
    _button, tooltip = hover
    assert tooltip.text == text


@then("it should cost one binding on the canvas")
def check_binding_not_doubled(binding_cost):
    """
    Walking into winfo_children() as well binds the canvas twice.

    The handler survives being called twice, so nothing visibly breaks -
    which is exactly why it is worth a test rather than a comment.
    """
    added_by_attach, cost_of_one = binding_cost
    assert added_by_attach == cost_of_one


@then("every icon button should carry a non-empty caption")
def check_every_icon_has_a_caption(icon_toolbar):
    """Not merely an attribute nobody reads."""
    for name, button in icon_toolbar.icon_buttons.items():
        tooltip = getattr(button, 'tooltip_widget', None)
        assert isinstance(tooltip, Tooltip), name
        assert tooltip.text.strip(), name


@then("every caption should match the one ICON_ACTIONS declares")
def check_captions_match_icon_actions(icon_toolbar):
    """
    Read from ICON_ACTIONS, so the two cannot drift.

    The row and the captions were separate lists once, and drifted the first
    time an icon was added.
    """
    captions = {name: tip for name, tip, _action
                in icon_toolbar.ICON_ACTIONS if tip}
    for name, expected in captions.items():
        assert icon_toolbar.icon_buttons[name].tooltip_widget.text == expected
