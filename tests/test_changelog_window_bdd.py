"""
pytest-bdd tests for the About > Changelog window.

Run with:
    python3 -m pytest tests/test_changelog_window_bdd.py -q

The parsing scenarios need no display; the window ones skip without
one, like the other help windows. Converted from
test_changelog_window.py - every case carried over.
"""
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.help.changelog import (
    CHANGELOG_SECTIONS,
    parse_changelog,
    show_changelog,
)

pytestmark = [
    pytest.mark.changelog_window,
]

scenarios("features/changelog_window.feature")


def _display_available() -> bool:
    try:
        import tkinter
        root = tkinter.Tk()
    except Exception:
        return False
    root.destroy()
    return True


HAVE_DISPLAY = _display_available()

SAMPLE = """# Changelog

## 2.0.0 - 2026-09-09

- A **bold** change with a `code` bit.
- A bullet wrapped
  over two lines.

## 1.0.0 - 2026-01-01

- The first release.
"""


# ------------------------------------------------------------------
# WHEN - parsing
# ------------------------------------------------------------------

@when("the sample changelog is parsed", target_fixture="ctx")
def the_sample_changelog_is_parsed():
    return SimpleNamespace(sections=parse_changelog(SAMPLE))


@when("a changelog holding only a title is parsed", target_fixture="ctx")
def an_empty_changelog_is_parsed():
    return SimpleNamespace(sections=parse_changelog("# Changelog\n"))


# ------------------------------------------------------------------
# THEN - parsing
# ------------------------------------------------------------------

@then(parsers.parse('the section headings are "{first}" and "{second}"'))
def the_section_headings_are(ctx, first, second):
    headings = [h for h, _ in ctx.sections]
    assert headings == [first, second]


@then(parsers.parse('no section is headed "{heading}"'))
def no_section_is_headed(ctx, heading):
    assert heading not in [h for h, _ in ctx.sections]


@then(parsers.parse('the first section carries "{text}"'))
def the_first_section_carries(ctx, text):
    assert text in ctx.sections[0][1]


@then("there is at least one section")
def there_is_at_least_one_section(ctx):
    assert ctx.sections


# ------------------------------------------------------------------
# THEN - the shipped file
# ------------------------------------------------------------------

@then(parsers.parse('the shipped changelog\'s first section starts with '
                    '"{version}"'))
def the_real_changelog_loads(version):
    assert CHANGELOG_SECTIONS
    # The newest entry heads the file, so it heads the sections.
    assert CHANGELOG_SECTIONS[0][0].startswith(version)


# ------------------------------------------------------------------
# The window - needs a display
# ------------------------------------------------------------------

@given("a running application shell", target_fixture="ctx")
def a_running_application_shell():
    if not HAVE_DISPLAY:
        pytest.skip("needs a display")
    import customtkinter as ctk
    root = ctk.CTk()
    root.withdraw()
    ctx = SimpleNamespace(root=root)
    yield ctx
    from gantt_app.help.changelog import ChangelogWindow
    if ChangelogWindow._open_window is not None:
        try:
            ChangelogWindow._open_window.destroy()
        except Exception:
            pass
        ChangelogWindow._open_window = None
    try:
        root.destroy()
    except Exception:
        pass


@when("the changelog window is shown")
def the_changelog_window_is_shown(ctx):
    ctx.window = show_changelog(ctx.root)
    ctx.root.update_idletasks()


@when("the changelog window is shown twice")
def the_changelog_window_is_shown_twice(ctx):
    ctx.first = show_changelog(ctx.root)
    ctx.second = show_changelog(ctx.root)


@then(parsers.parse('its title is "{title}"'))
def its_title_is(ctx, title):
    assert ctx.window.title() == title


@then("both are the same window")
def both_are_the_same_window(ctx):
    assert ctx.first is ctx.second
