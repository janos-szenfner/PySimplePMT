"""
pytest-bdd tests for the About PySimplePMT window.

Run with:
    python3 -m pytest tests/test_about_window_bdd.py -v
"""

from pytest_bdd import given, scenarios, then, when
import pytest

from gantt_app import __version__


scenarios("features/about_window.feature")


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

pytestmark = pytest.mark.skipif(not HAVE_DISPLAY, reason="needs a display")


def _all_label_text(widget):
    """Every label string in the window, walked recursively."""
    texts = []
    try:
        text = widget.cget('text')
        if isinstance(text, str) and text:
            texts.append(text)
    except Exception:
        pass
    for child in widget.winfo_children():
        texts.extend(_all_label_text(child))
    return texts


@given("a Tk root window", target_fixture="tk_root")
def tk_root():
    import customtkinter as ctk

    root = ctk.CTk()
    root.withdraw()
    yield root
    # Drop any About window still open, then the root.
    from gantt_app.views.aboutwindow import AboutWindow
    if AboutWindow._open_window is not None:
        try:
            AboutWindow._open_window.destroy()
        except Exception:
            pass
        AboutWindow._open_window = None
    try:
        root.destroy()
    except Exception:
        pass


@when("the About window is opened", target_fixture="about_window")
def open_about(tk_root):
    from gantt_app.views.aboutwindow import show_about

    window = show_about(tk_root)
    tk_root.update_idletasks()
    return window


@when("the About window is opened again", target_fixture="about_window_again")
def open_about_again(tk_root):
    from gantt_app.views.aboutwindow import show_about

    window = show_about(tk_root)
    tk_root.update_idletasks()
    return window


@then("the About window should exist")
def about_exists(about_window):
    assert about_window is not None
    assert about_window.winfo_exists()


@then("the About window should show the application version")
def about_shows_version(about_window):
    texts = _all_label_text(about_window)
    assert any(__version__ in text for text in texts), texts


@then("the About window should carry the logo image")
def about_has_logo(about_window):
    assert about_window._logo_image is not None


@then("both handles should be the same window")
def about_single_instance(about_window, about_window_again):
    assert about_window is about_window_again
