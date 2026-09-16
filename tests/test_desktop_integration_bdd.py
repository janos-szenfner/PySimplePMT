"""
pytest-bdd tests for the desktop entry agreeing with the application.

Run with:
    python3 -m pytest tests/test_desktop_integration_bdd.py -q

The packaged files are read as text, so most scenarios run anywhere;
building the real window skips without a display. Converted from
test_desktop_integration.py - every case carried over.
"""
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

pytestmark = [
    pytest.mark.desktop_integration,
]

scenarios("features/desktop_integration.feature")

PACKAGING = Path(__file__).resolve().parent.parent / 'packaging'
DESKTOP_ENTRY = PACKAGING / 'pysimplepmt.desktop'
BUILD_SCRIPT = PACKAGING / 'build_deb.sh'


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


def _entry_keys():
    """The desktop entry as a dictionary of key to value."""
    found = {}
    for line in DESKTOP_ENTRY.read_text().splitlines():
        if '=' in line and not line.startswith('['):
            key, _, value = line.partition('=')
            found[key.strip()] = value.strip()
    return found


# ------------------------------------------------------------------
# GIVEN
# ------------------------------------------------------------------

@given("the packaged desktop entry and build script", target_fixture="ctx")
def the_packaged_files():
    return SimpleNamespace(keys=_entry_keys(),
                           script=BUILD_SCRIPT.read_text())


# ------------------------------------------------------------------
# WHEN - needs a display
# ------------------------------------------------------------------

@when("the real application window is built")
def the_real_application_window_is_built(ctx):
    if not HAVE_DISPLAY:
        pytest.skip("needs a display")
    from gantt_app.main import GanttApp

    app = GanttApp()
    app.withdraw()
    app.update_idletasks()
    ctx.app = app


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@then(parsers.parse('the Icon key is "{name}"'))
def the_icon_key_is(ctx, name):
    assert ctx.keys.get('Icon') == name


@then("the Icon key is a bare name, not a path or a file")
def the_icon_key_is_a_bare_name(ctx):
    icon = ctx.keys['Icon']
    assert '/' not in icon
    assert not icon.endswith('.png')


@then("the build script installs the hicolor and pixmaps icons")
def the_build_installs_the_icons(ctx):
    assert ('icons/hicolor/${ICON_SIZE}x${ICON_SIZE}/apps/'
            '${PACKAGE_NAME}.png') in ctx.script
    assert 'pixmaps/${PACKAGE_NAME}.png' in ctx.script


@then("the build script lists the seven hicolor sizes")
def the_build_lists_the_sizes(ctx):
    sizes = re.search(r'ICON_SIZES="([^"]+)"', ctx.script).group(1).split()
    assert sizes == ['16', '24', '32', '48', '64', '128', '256']


@then("the build script checks the icons were written")
def the_build_checks_the_icons(ctx):
    assert 'was not written' in ctx.script
    assert ('Checking the icons are where the desktop entry will look'
            in ctx.script)


@then("the build script depends on hicolor-icon-theme")
def the_build_depends_on_the_theme(ctx):
    assert 'hicolor-icon-theme' in ctx.script


@then("the Categories include Office and none are empty")
def the_categories_are_known(ctx):
    categories = ctx.keys.get('Categories', '').strip(';').split(';')
    assert 'Office' in categories
    for category in categories:
        assert category, "empty category in the list"


@then(parsers.parse('the application declares WM_CLASS "{name}"'))
def the_application_declares_wm_class(ctx, name):
    from gantt_app.main import GanttApp
    assert GanttApp.WM_CLASS_NAME == name


@then("the StartupWMClass is the capitalised application class")
def the_startup_wm_class_matches(ctx):
    from gantt_app.main import GanttApp
    assert ctx.keys.get('StartupWMClass') == \
        GanttApp.WM_CLASS_NAME.capitalize()


@then("the window's class matches the StartupWMClass")
def the_windows_class_matches(ctx):
    try:
        assert ctx.app.winfo_class() == ctx.keys.get('StartupWMClass')
    finally:
        _shut_down(ctx.app)
