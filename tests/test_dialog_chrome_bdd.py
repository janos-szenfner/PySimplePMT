"""
pytest-bdd tests for dialog chrome: wiring, contrast and grabs.

Run with:
    python3 -m pytest tests/test_dialog_chrome_bdd.py -q

The source-inspection scenarios run anywhere; the widget ones skip
without a display. Converted from test_dialog_chrome.py - every case
carried over.
"""
from types import SimpleNamespace
from unittest import mock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

pytestmark = [
    pytest.mark.dialog_chrome,
]

scenarios("features/dialog_chrome.feature")


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


def _shut_down(root) -> None:
    """Take a root down, children first, without raising."""
    try:
        for child in list(root.children.values()):
            try:
                child.destroy()
            except Exception:
                pass
        root.destroy()
    except Exception:
        pass


def _buttons(widget, found=None):
    """Every CTkButton inside a widget."""
    import customtkinter as ctk

    found = [] if found is None else found
    for child in widget.winfo_children():
        if isinstance(child, ctk.CTkButton):
            found.append(child)
        _buttons(child, found)
    return found


def _named(widget, label):
    """One button by its label."""
    for button in _buttons(widget):
        if button.cget('text') == label:
            return button
    raise AssertionError(f"no {label!r} button")


# ------------------------------------------------------------------
# GIVEN
# ------------------------------------------------------------------

@given("a holiday dialog is open", target_fixture="ctx")
def a_holiday_dialog_is_open():
    if not HAVE_DISPLAY:
        pytest.skip("needs a display")
    import customtkinter as ctk
    from gantt_app.views.holidaydialog import HolidayDialog

    root = ctk.CTk()
    root.withdraw()
    window = HolidayDialog(root, [], lambda codes: None)
    window.update_idletasks()

    yield SimpleNamespace(root=root, window=window)

    _shut_down(root)


@given("a critical path window is open over an empty plan",
       target_fixture="ctx")
def a_critical_path_window_is_open():
    if not HAVE_DISPLAY:
        pytest.skip("needs a display")
    import customtkinter as ctk
    from gantt_app.core.models import Project
    from gantt_app.views.criticalpath import CriticalPathWindow

    root = ctk.CTk()
    root.withdraw()
    window = CriticalPathWindow(root, Project(name="Empty"))
    window.update_idletasks()

    yield SimpleNamespace(root=root, window=window)

    _shut_down(root)


@given("a dialog holding the grab", target_fixture="ctx")
def a_dialog_holding_the_grab():
    if not HAVE_DISPLAY:
        pytest.skip("needs a display")
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    dialog = tk.Toplevel(root)
    dialog.deiconify()
    dialog.update_idletasks()
    try:
        dialog.grab_set()
    except tk.TclError:
        _shut_down(root)
        pytest.skip("this display will not take a grab")

    yield SimpleNamespace(root=root, dialog=dialog)

    _shut_down(root)


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------

@when("the real application is built", target_fixture="ctx")
def the_real_application_is_built():
    if not HAVE_DISPLAY:
        pytest.skip("needs a display")
    from gantt_app.main import GanttApp

    app = GanttApp()
    app.withdraw()
    app.update_idletasks()

    yield SimpleNamespace(app=app)

    _shut_down(app)


@when("a popup over it takes the grab")
def a_popup_takes_the_grab(ctx):
    import tkinter as tk
    from gantt_app.views.modal import take_grab

    popup = tk.Toplevel(ctx.dialog)
    popup.deiconify()
    popup.update_idletasks()
    take_grab(popup)
    popup.update_idletasks()
    ctx.popup = popup


@when("the popup is destroyed")
def the_popup_is_destroyed(ctx):
    ctx.popup.destroy()
    ctx.root.update_idletasks()


@when("a child inside the popup is destroyed")
def a_child_inside_the_popup_is_destroyed(ctx):
    import tkinter as tk

    inside = tk.Frame(ctx.popup)
    inside.pack()
    ctx.popup.update_idletasks()
    inside.destroy()
    ctx.root.update_idletasks()


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@then("every icon action resolves to a callable toolbar method")
def every_icon_action_resolves():
    from gantt_app.views.toolbar import IconToolbar, Toolbar

    missing = []
    for _icon, _tooltip, action in IconToolbar.ICON_ACTIONS:
        if not action:
            continue                    # a divider
        name = Toolbar.ICON_HANDLER_OVERRIDES.get(action, action)
        if not callable(getattr(Toolbar, name, None)):
            missing.append(f"{action} -> {name}")
    assert missing == []


@then(parsers.parse('"{action}" is an action with a handler'))
def the_action_has_a_handler(action):
    from gantt_app.views.toolbar import IconToolbar, Toolbar

    actions = [a for _i, _t, a in IconToolbar.ICON_ACTIONS]
    assert action in actions
    assert callable(getattr(Toolbar, action, None))


@then("every icon on its toolbar reaches a callable handler")
def every_icon_reaches_a_handler(ctx):
    row = ctx.app.toolbar.icon_toolbar
    missing = [action for _i, _t, action in row.ICON_ACTIONS
               if action and not callable(getattr(row, action, None))]
    assert missing == []


@then(parsers.parse('its "{label}" button is filled and its text '
                    'coloured'))
def the_button_is_filled(ctx, label):
    button = _named(ctx.window, label)
    assert button.cget('fg_color') != 'transparent'
    assert button.cget('text_color') is not None


@then(parsers.parse('its "{label}" button is not filled like its '
                    '"{other}" button'))
def the_button_differs_from_the_primary(ctx, label, other):
    assert _named(ctx.window, label).cget('fg_color') != \
        _named(ctx.window, other).cget('fg_color')


@then("the secondary fill and text are distinct light-dark pairs")
def the_secondary_colours_are_pairs():
    from gantt_app.views.buttonstyle import (
        SECONDARY_FILL, SECONDARY_TEXT,
    )

    for pair in (SECONDARY_FILL, SECONDARY_TEXT):
        assert len(pair) == 2
        assert pair[0] != pair[1]


@then("the popup holds the grab")
def the_popup_holds_the_grab(ctx):
    assert ctx.popup.grab_current() == ctx.popup


@then("the dialog holds the grab again")
def the_dialog_holds_the_grab_again(ctx):
    assert ctx.dialog.grab_current() == ctx.dialog


@then("the calendar popup's constructor takes the grab")
def the_calendar_popup_takes_the_grab():
    import inspect
    from gantt_app.views import datepicker

    assert 'take_grab' in inspect.getsource(
        datepicker.CalendarPopup.__init__)
