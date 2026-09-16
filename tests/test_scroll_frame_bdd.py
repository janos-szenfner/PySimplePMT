"""
pytest-bdd tests for the scrolling container the task form is built in.

Run with:
    python3 -m pytest tests/test_scroll_frame_bdd.py -q

Display-gated the same way the unittest was: the Given builds a real
CTk root, so the whole module skips without a display (CI provides one
through xvfb). Converted from test_scroll_frame.py - every case
carried over.
"""
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

pytestmark = [
    pytest.mark.scroll_frame,
]

scenarios("features/scroll_frame.feature")


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
    ttk::ThemeChanged against an interpreter that has already gone,
    which floods stderr with "can't invoke event" tracebacks.
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


def _fill(ctx, rows):
    """Put that many rows of fields in, as the task form does."""
    import tkinter as tk

    for row in range(rows):
        ctx.ctk.CTkLabel(ctx.frame.content,
                         text=f"Field {row}:").grid(
            row=row, column=0, sticky=tk.W, pady=5)
        ctx.ctk.CTkEntry(ctx.frame.content).grid(
            row=row, column=1, sticky=tk.EW, pady=5)
    ctx.root.update_idletasks()


def _wheel_event(**fields):
    """
    A wheel event as one platform or another delivers it.

    Built rather than generated: <MouseWheel> cannot be fired at a
    window that was never mapped, and what matters here is how a delta
    is read, not how it arrived.
    """
    import tkinter as tk

    event = tk.Event()
    for name, value in fields.items():
        setattr(event, name, value)
    return event


def _scrolls(ctx, event, scrollable=True):
    """What _wheel asks the canvas to do with an event."""
    asked = []
    ctx.frame._scrollable = lambda: scrollable
    ctx.frame.canvas.yview_scroll = (
        lambda steps, what: asked.append((steps, what))
    )
    ctx.frame._wheel(event)
    return asked


# ------------------------------------------------------------------
# GIVEN
# ------------------------------------------------------------------

@given("a window with a scrolling frame", target_fixture="ctx")
def a_window_with_a_scrolling_frame():
    """Build a root window and a frame to scroll."""
    if not HAVE_DISPLAY:
        pytest.skip("needs a display")
    import tkinter as tk

    import customtkinter as ctk
    from gantt_app.views.scrollframe import ScrollFrame

    ctx = SimpleNamespace(ctk=ctk)
    ctx.root = ctk.CTk()
    ctx.root.withdraw()
    ctx.root.geometry("400x200")

    ctx.frame = ScrollFrame(ctx.root)
    ctx.frame.pack(fill=tk.BOTH, expand=True)
    ctx.root.update_idletasks()
    try:
        yield ctx
    finally:
        _shut_down(ctx.root)


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------

@when(parsers.parse("{rows:d} rows of fields are put in and the canvas "
                    "resizes to {width:d} wide"))
def rows_then_resize(ctx, rows, width):
    ctx.frame.content.columnconfigure(1, weight=1)
    _fill(ctx, rows)
    ctx.frame.canvas.event_generate('<Configure>', width=width, height=200)


@when(parsers.parse("{rows:d} rows of fields are put in"))
def rows_of_fields(ctx, rows):
    _fill(ctx, rows)
    ctx.root.update_idletasks()


@when("the canvas reports the whole form on show")
def the_whole_form_on_show(ctx):
    ctx.frame._scrolled('0.0', '1.0')


@when("the canvas reports the top half of the form on show")
def the_top_half_on_show(ctx):
    ctx.frame._scrolled('0.0', '0.5')


@when("the canvas reports half then the whole form on show")
def half_then_whole_on_show(ctx):
    ctx.frame._scrolled('0.0', '0.5')
    ctx.frame._scrolled('0.0', '1.0')


@when("the pointer arrives over the frame")
def the_pointer_arrives(ctx):
    ctx.frame._take_the_wheel()


@when("the pointer arrives and then leaves the frame")
def the_pointer_arrives_and_leaves(ctx):
    ctx.frame._take_the_wheel()
    ctx.frame._let_go_of_the_wheel()


@when("the pointer arrives and the frame is destroyed")
def the_pointer_arrives_and_the_frame_goes(ctx):
    ctx.frame._take_the_wheel()
    ctx.frame.destroy()


@when(parsers.parse("a wheel delta of {delta:d} arrives over a scrollable "
                    "form"))
def a_wheel_delta_over_scrollable(ctx, delta):
    ctx.asked = _scrolls(ctx, _wheel_event(delta=delta))


@when(parsers.parse("wheel button {num:d} arrives over a scrollable form"))
def a_wheel_button_over_scrollable(ctx, num):
    ctx.asked = _scrolls(ctx, _wheel_event(delta=0, num=num))


@when(parsers.parse("a wheel delta of {delta:d} arrives over a fitting "
                    "form"))
def a_wheel_delta_over_fitting(ctx, delta):
    ctx.asked = _scrolls(ctx, _wheel_event(delta=delta), scrollable=False)


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@then("the content frame sits inside the canvas")
def the_content_frame_sits_inside_the_canvas(ctx):
    assert ctx.frame.content.master is ctx.frame.canvas


@then(parsers.parse("the canvas holds the window {width:d} wide"))
def the_canvas_holds_the_window(ctx, width):
    assert int(ctx.frame.canvas.itemcget(ctx.frame._window,
                                         'width')) == width


@then("no scrollbar is managed")
def no_scrollbar_is_managed(ctx):
    assert ctx.frame.scrollbar.winfo_manager() == ""


@then(parsers.parse("the scrollbar is gridded in column {column:d}"))
def the_scrollbar_is_gridded(ctx, column):
    assert ctx.frame.scrollbar.winfo_manager() == "grid"
    assert int(ctx.frame.scrollbar.grid_info()['column']) == column


@then("the scrollregion covers the form's height")
def the_scrollregion_covers_the_form(ctx):
    region = [int(part) for part in
              str(ctx.frame.canvas.cget('scrollregion')).split()]
    assert region, "the canvas was left with no scrollregion"
    assert region[3] >= ctx.frame.content.winfo_reqheight()


@then("the wheel is bound application-wide")
def the_wheel_is_bound(ctx):
    assert ctx.frame.canvas.bind_all('<MouseWheel>')


@then("the wheel is not bound application-wide")
def the_wheel_is_not_bound(ctx):
    assert not ctx.frame.canvas.bind_all('<MouseWheel>')


@then(parsers.parse("the canvas was asked to scroll {steps:d} units"))
def the_canvas_was_asked_to_scroll(ctx, steps):
    assert ctx.asked == [(steps, 'units')]


@then("the canvas was asked nothing")
def the_canvas_was_asked_nothing(ctx):
    assert ctx.asked == []
