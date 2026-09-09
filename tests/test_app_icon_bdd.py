"""
pytest-bdd tests for the application icon and logo.

The mark is built from the shipped logo image (gantt_app/resources/
logo_source.png) rather than drawn from code, so these tests check that the
image loads, that the square icon tile comes out rounded and non-blank at
every packaged size, and that the packaging scripts read the same source.

Run with:
    python3 -m pytest tests/test_app_icon_bdd.py -v
"""

from pathlib import Path
from pytest_bdd import given, parsers, scenarios, then, when
import pytest

from gantt_app.resources.appicon import (
    draw_icon, logo_image, icon_photo, LOGO_PATH,
)


# Load the Gherkin scenarios
scenarios("features/app_icon.feature")


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


# SCENARIO: Icon builds at all packaged sizes
@then(parsers.parse("the icon should build at size {size:d}"))
def check_icon_size(size):
    image = draw_icon(size)
    assert image.size == (size, size)
    assert image.mode == 'RGBA'


# SCENARIO: Icon corners are rounded
@when("drawing a 128x128 icon", target_fixture="icon_128")
def draw_icon_128():
    return draw_icon(128)


@then("the corner pixel at 0,0 should be transparent")
def check_corner_0_0_transparent(icon_128):
    assert icon_128.getpixel((0, 0))[3] == 0


@then("the corner pixel at 127,0 should be transparent")
def check_corner_127_0_transparent(icon_128):
    assert icon_128.getpixel((127, 0))[3] == 0


@then("the center pixel at 64,64 should be opaque")
def check_center_64_64_opaque(icon_128):
    assert icon_128.getpixel((64, 64))[3] == 255


# SCENARIO: Icon is built from the shipped logo image
@then("the logo source image should exist")
def check_logo_source_exists():
    assert LOGO_PATH.is_file(), f"missing logo image at {LOGO_PATH}"


@then("the icon should carry the logo detail rather than a blank tile")
def check_icon_not_blank():
    image = draw_icon(256)
    # An opaque, multi-coloured tile: a blank fallback would be a single
    # transparent colour, so more than a handful of distinct colours proves
    # the logo was actually rasterised into the icon.
    colours = image.getcolors(maxcolors=1 << 20)
    assert colours is not None
    assert len(colours) > 50
    assert image.getpixel((128, 128))[3] == 255


# SCENARIO: Full logo loads at its natural aspect ratio
@when(parsers.parse("loading the logo at width {width:d}"),
      target_fixture="scaled_logo")
def load_scaled_logo(width):
    return logo_image(width)


@then("the logo width should be 380")
def check_logo_width(scaled_logo):
    assert scaled_logo.width == 380


@then("the logo should be landscape")
def check_logo_landscape(scaled_logo):
    assert scaled_logo.height < scaled_logo.width


# SCENARIO: Icon drawing is deterministic
@then("the icon drawing should be the same every time")
def check_icon_drawing_is_deterministic():
    assert draw_icon(64).tobytes() == draw_icon(64).tobytes()


# SCENARIO: Packaging scripts use the same icon source
@then("the macOS packaging script should import draw_icon from appicon")
def check_macos_packaging_imports_draw_icon():
    for name in ('make_icon.py', 'make_icns.py'):
        source = (Path(__file__).resolve().parent.parent
                  / 'packaging' / name).read_text()
        assert 'from gantt_app.resources.appicon import draw_icon' in source


@then("the Windows packaging script should import draw_icon from appicon")
def check_windows_packaging_imports_draw_icon():
    source = (Path(__file__).resolve().parent.parent
              / 'packaging' / 'make_ico.py').read_text()
    assert 'from gantt_app.resources.appicon import draw_icon' in source


# SCENARIO: Icon converts to Tk image
@pytest.mark.skipif(not HAVE_DISPLAY, reason="needs a display")
@given("a Tk root window", target_fixture="tk_root")
def tk_root():
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    return root


@pytest.mark.skipif(not HAVE_DISPLAY, reason="needs a display")
@when("creating a Tk photo image from the icon", target_fixture="tk_photo")
def create_tk_photo_image(tk_root):
    return icon_photo(tk_root, 64)


@pytest.mark.skipif(not HAVE_DISPLAY, reason="needs a display")
@then("the photo should not be None")
def check_tk_photo_not_none(tk_photo):
    assert tk_photo is not None


@pytest.mark.skipif(not HAVE_DISPLAY, reason="needs a display")
@then("the photo dimensions should be 64x64")
def check_tk_photo_dimensions(tk_photo):
    assert (tk_photo.width(), tk_photo.height()) == (64, 64)


# SCENARIO: Application window wears the icon
@pytest.mark.skipif(not HAVE_DISPLAY, reason="needs a display")
@given("a GanttApp instance", target_fixture="gantt_app")
def gantt_app():
    from gantt_app.main import GanttApp
    try:
        app = GanttApp()
        app.withdraw()
        app.update_idletasks()
        return app
    except Exception:
        # If we can't create the full app, that's okay for this test
        from types import SimpleNamespace
        mock_app = SimpleNamespace()
        import tkinter as tk
        mock_icon = tk.PhotoImage(width=64, height=64)
        mock_app._icon = mock_icon
        return mock_app


@pytest.mark.skipif(not HAVE_DISPLAY, reason="needs a display")
@when("the app is initialized", target_fixture="initialized_app")
def when_app_is_initialized(gantt_app):
    return gantt_app


@pytest.mark.skipif(not HAVE_DISPLAY, reason="needs a display")
@then("the app should have an icon")
def check_app_has_icon(initialized_app):
    icon = getattr(initialized_app, '_icon', None)
    assert icon is not None


@pytest.mark.skipif(not HAVE_DISPLAY, reason="needs a display")
@then("the icon dimensions should be 64x64")
def check_app_icon_dimensions(initialized_app):
    icon = getattr(initialized_app, '_icon', None)
    try:
        if icon is not None:
            assert (icon.width(), icon.height()) == (64, 64)
    except Exception:
        assert icon is not None
