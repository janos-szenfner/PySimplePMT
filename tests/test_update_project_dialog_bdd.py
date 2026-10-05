"""
pytest-bdd tests for the Update Project window.

Run with:
    python3 -m pytest tests/test_update_project_dialog_bdd.py -q

The scenarios drive the real dialog, so they skip without a display.
What the dialog's answer does to a plan is covered by
test_update_project_bdd.py.
"""
from datetime import datetime
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("features/update_project_dialog.feature")


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
    """
    Take a root down, children first, without raising.

    Destroying a root while a Toplevel is still on it leaves Tk running
    ttk::ThemeChanged against an interpreter that has already gone, which
    floods stderr with "can't invoke event" tracebacks.
    """
    try:
        for child in list(root.children.values()):
            try:
                child.destroy()
            except Exception:
                pass
        root.destroy()
    except Exception:
        pass


# ------------------------------------------------------------------
# GIVEN - needs a display
# ------------------------------------------------------------------

@given(parsers.parse('a plan with a status date of "{iso}"'),
       target_fixture="ctx")
def a_plan_with_a_status_date(iso):
    from gantt_app.core.models import Project
    return SimpleNamespace(
        project=Project(name="Plan", status_date=datetime.fromisoformat(iso)),
        heard=[])


@given('a plan with no status date', target_fixture="ctx")
def a_plan_with_no_status_date():
    from gantt_app.core.models import Project
    return SimpleNamespace(
        project=Project(name="Plan"), heard=[])


def _open(ctx, listening=True):
    if not HAVE_DISPLAY:
        pytest.skip("needs a display")
    import customtkinter as ctk
    from gantt_app.views.updateproject import UpdateProjectDialog

    ctx.root = ctk.CTk()
    ctx.root.withdraw()
    on_update = ctx.heard.append if listening else None
    ctx.window = UpdateProjectDialog(
        ctx.root, ctx.project, on_update=on_update)
    ctx.root.update_idletasks()


@when('the window opens')
def the_window_opens(ctx):
    _open(ctx)
    yield ctx
    _shut_down(ctx.root)


@given('the window is open', target_fixture="ctx")
def the_window_is_open(ctx):
    _open(ctx)
    yield ctx
    _shut_down(ctx.root)


@given('the window is open with nobody listening', target_fixture="ctx")
def the_window_is_open_with_nobody_listening(ctx):
    _open(ctx, listening=False)
    yield ctx
    _shut_down(ctx.root)


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------

@when(parsers.parse('the box is set to "{iso}" and OK is pressed'))
def the_box_is_set_and_ok_is_pressed(ctx, iso):
    ctx.window._date_entry.set_date(datetime.fromisoformat(iso))
    ctx.window._on_ok()
    ctx.root.update_idletasks()


@when('OK is pressed')
def ok_is_pressed(ctx):
    ctx.window._on_ok()
    ctx.root.update_idletasks()


@when('the box is emptied and OK is pressed')
def the_box_is_emptied_and_ok_is_pressed(ctx, monkeypatch):
    from gantt_app.views import updateproject
    ctx.warned = []
    monkeypatch.setattr(updateproject.messagebox, 'showwarning',
                        lambda *a, **k: ctx.warned.append(a))
    ctx.window._date_entry.delete(0, 'end')
    ctx.window._on_ok()
    ctx.root.update_idletasks()


@when('Cancel is pressed')
def cancel_is_pressed(ctx):
    ctx.window.destroy()
    ctx.root.update_idletasks()


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@then(parsers.parse('the box holds "{text}"'))
def the_box_holds(ctx, text):
    assert ctx.window._date_entry.get() == text


@then("the box holds today's date")
def the_box_holds_todays_date(ctx):
    assert ctx.window._date_entry.get_date() is not None
    assert ctx.window._date_entry.get_date().date() == datetime.now().date()


@then(parsers.parse('the date "{iso}" came back'))
def the_date_came_back(ctx, iso):
    assert len(ctx.heard) == 1
    assert ctx.heard[0].date() == datetime.fromisoformat(iso).date()


@then('the window is gone')
def the_window_is_gone(ctx):
    assert not ctx.window.winfo_exists()


@then('the window is still up')
def the_window_is_still_up(ctx):
    assert ctx.window.winfo_exists()


@then('a warning was shown')
def a_warning_was_shown(ctx):
    assert ctx.warned


@then('nothing came back')
def nothing_came_back(ctx):
    assert ctx.heard == []
