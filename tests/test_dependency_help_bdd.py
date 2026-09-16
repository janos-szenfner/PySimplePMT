"""
pytest-bdd tests for the dependency reference window and the Help
button that opens it.

Run with:
    python3 -m pytest tests/test_dependency_help_bdd.py -q

The content scenarios read HELP_SECTIONS as data and need no display;
the window and button scenarios build real widgets and skip without
one (CI provides one through xvfb). Converted from
test_dependency_help.py - every case carried over.
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.core.models import Project, Task, DEPENDENCY_TYPE_LABELS
from gantt_app.help.dependencyhelp import HELP_SECTIONS

pytestmark = [
    pytest.mark.dependency_help,
]

scenarios("features/dependency_help.feature")


def _all_text():
    """Every heading and paragraph run together."""
    parts = []
    for heading, paragraphs in HELP_SECTIONS:
        parts.append(heading)
        parts.extend(paragraphs)
    return '\n'.join(parts)


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


def _close_open_help_window():
    """Close the remembered help window, if there is one."""
    from gantt_app.help.dependencyhelp import DependencyHelpWindow

    if DependencyHelpWindow._open_window is not None:
        DependencyHelpWindow._open_window.close()


def _labels(widget, found=None):
    """Every label's text, recursively."""
    import customtkinter as ctk

    found = [] if found is None else found
    for child in widget.winfo_children():
        if isinstance(child, ctk.CTkLabel):
            found.append(str(child.cget('text')))
        _labels(child, found)
    return found


def _buttons(widget, found=None):
    """Every button's text, recursively."""
    import customtkinter as ctk

    found = [] if found is None else found
    for child in widget.winfo_children():
        if isinstance(child, ctk.CTkButton):
            found.append(str(child.cget('text')))
        _buttons(child, found)
    return found


# ------------------------------------------------------------------
# GIVEN
# ------------------------------------------------------------------

@given("a root window", target_fixture="ctx")
def a_root_window():
    """Build a root window."""
    if not HAVE_DISPLAY:
        pytest.skip("needs a display")
    import customtkinter as ctk

    root = ctk.CTk()
    root.withdraw()
    try:
        yield SimpleNamespace(root=root)
    finally:
        _close_open_help_window()
        _shut_down(root)


@given("an edit dialog over a two-task project", target_fixture="ctx")
def an_edit_dialog_over_a_two_task_project():
    """Open an edit dialog over a small project."""
    if not HAVE_DISPLAY:
        pytest.skip("needs a display")
    import customtkinter as ctk
    from gantt_app.views.taskdialogs import EditTaskDialog

    root = ctk.CTk()
    root.withdraw()

    project = Project(name="Test Project")
    base = datetime(2026, 1, 1)
    for index in (1, 2):
        project.add_task(Task(
            id=f"00{index}", name=f"Task {index}",
            start_date=base, end_date=base + timedelta(days=3),
        ))

    dialog = EditTaskDialog(
        root, project.tasks[0], project,
        on_save=lambda task: None, on_delete=lambda task_id: None,
    )
    try:
        yield SimpleNamespace(root=root, project=project, dialog=dialog,
                              editor=dialog.dependency_editor)
    finally:
        _close_open_help_window()
        _shut_down(root)


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------

@when("the dependency help is shown")
def the_dependency_help_is_shown(ctx):
    from gantt_app.help.dependencyhelp import DependencyHelpWindow

    ctx.window = DependencyHelpWindow.show(ctx.root)


@when("the dependency help is shown twice")
def the_dependency_help_is_shown_twice(ctx):
    from gantt_app.help.dependencyhelp import DependencyHelpWindow

    ctx.first = DependencyHelpWindow.show(ctx.root)
    ctx.second = DependencyHelpWindow.show(ctx.root)


@when("the dependency help is shown and closed")
def the_dependency_help_is_shown_and_closed(ctx):
    from gantt_app.help.dependencyhelp import DependencyHelpWindow

    window = DependencyHelpWindow.show(ctx.root)
    window.close()


@when("the dependency help is shown, closed and shown again")
def the_dependency_help_is_reopened(ctx):
    from gantt_app.help.dependencyhelp import DependencyHelpWindow

    ctx.first = DependencyHelpWindow.show(ctx.root)
    ctx.first.close()
    ctx.second = DependencyHelpWindow.show(ctx.root)


@when("the editor is asked for help")
def the_editor_is_asked_for_help(ctx):
    ctx.editor.show_help()


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@then("every dependency type label has a section heading")
def every_type_is_explained():
    headings = [heading for heading, _paragraphs in HELP_SECTIONS]
    for label in DEPENDENCY_TYPE_LABELS.values():
        assert any(label in heading for heading in headings), \
            f"no section explains {label}"


@then(parsers.parse('the help text mentions "{first}" and "{second}"'))
def the_help_text_mentions(first, second):
    text = _all_text()
    assert first.lower() in text.lower()
    assert second.lower() in text.lower()


@then(parsers.parse('the help text contains no "{word}"'))
def the_help_text_contains_no(word):
    assert word not in _all_text()


@then("every help section has non-empty paragraphs")
def every_section_has_content():
    for heading, paragraphs in HELP_SECTIONS:
        assert paragraphs, f"{heading} has no text"
        for paragraph in paragraphs:
            assert paragraph.strip()


@then("the help window exists")
def the_help_window_exists(ctx):
    assert ctx.window.winfo_exists()


@then("the help body carries every section heading")
def the_help_body_carries_every_heading(ctx):
    import tkinter as tk

    body = ctx.window.text.get('1.0', tk.END)
    for heading, _paragraphs in HELP_SECTIONS:
        assert heading in body


@then("the help body is disabled")
def the_help_body_is_disabled(ctx):
    import tkinter as tk

    assert str(ctx.window.text.cget('state')) == tk.DISABLED


@then("the same window came back")
def the_same_window_came_back(ctx):
    assert ctx.first is ctx.second


@then("no open help window is remembered")
def no_open_help_window_is_remembered():
    from gantt_app.help.dependencyhelp import DependencyHelpWindow

    assert DependencyHelpWindow._open_window is None


@then("a fresh help window exists")
def a_fresh_help_window_exists(ctx):
    assert ctx.second.winfo_exists()
    assert ctx.second is not ctx.first


@then(parsers.parse("every label on the dependency editor is shorter than "
                    "{limit:d} characters"))
def only_field_labels_remain(ctx, limit):
    labels = _labels(ctx.editor)
    assert labels
    for text in labels:
        assert len(text) < limit, f"{text!r} reads like prose"


@then(parsers.parse('a "{text}" button is on the dependency editor'))
def a_button_is_on_the_editor(ctx, text):
    assert text in _buttons(ctx.editor)


@then("an open help window is remembered")
def an_open_help_window_is_remembered():
    from gantt_app.help.dependencyhelp import DependencyHelpWindow

    assert DependencyHelpWindow._open_window is not None
