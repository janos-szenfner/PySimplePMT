"""
pytest-bdd tests for application startup behavior.

Run with:
    python3 -m pytest tests/test_application_startup_bdd.py -q

These tests require a display because they build the full GanttApp.
"""
import tkinter as tk

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.views.gantt_chart import CHART_TOP_MARGIN


def _display_available() -> bool:
    try:
        root = tk.Tk()
    except Exception:
        return False
    root.destroy()
    return True


HAVE_DISPLAY = _display_available()

pytestmark = [
    pytest.mark.skipif(not HAVE_DISPLAY, reason="needs a display"),
]

scenarios("features/application_startup.feature")


# GIVEN FIXTURES

@given("the application is started", target_fixture="app")
def the_application_is_started():
    """Start the application without showing it."""
    from gantt_app.main import GanttApp

    app = GanttApp()
    app.withdraw()
    app.update_idletasks()
    yield app
    try:
        app.destroy()
    except tk.TclError:
        pass


def _open_on_screen(app, width, height, scaling=None):
    """
    Reopen the application on a screen of a given size.

    PARAMETERS:
    -----------
    app : GanttApp
        The one the Background opened. It is closed first.
    width, height : int
        What the window manager will say the usable area is.
    scaling : Optional[float]
        The desktop scaling factor, when the scenario sets one.

    RETURNS:
    --------
    GanttApp
        The reopened application, on the screen described.

    DEVELOPMENT NOTES:
    ------------------
    The Background's application is closed before this one is built, and
    that is not tidiness. Two live Tk roots break the second one:
    CustomTkinter draws with PIL, and an ImageTk.PhotoImage made without a
    master belongs to whatever tkinter._default_root points at - the first
    root, while it lives - so the second root's buttons are handed images
    its own interpreter has never heard of and Tk answers "image pyimageN
    doesn't exist". These scenarios opened a second application beside the
    first and failed on exactly that; see tests/conftest.py.
    """
    from gantt_app.main import GanttApp

    _close(app)

    class Fixed(GanttApp):
        """An application on a screen of the scenario's choosing."""

        def wm_maxsize(self, *_args):
            return (width, height)

        if scaling is not None:
            def _window_scaling(self):
                return scaling

    opened = Fixed()
    opened.withdraw()
    opened.update_idletasks()
    return opened


def _close(app):
    """Take an application down without raising."""
    try:
        app.destroy()
    except tk.TclError:
        pass


# WHEN FIXTURES

@when("the application is given a work area of 0x0",
      target_fixture="sized_app")
def the_application_is_given_no_work_area(app):
    """A window manager that answers 0x0, which means it will not say."""
    opened = _open_on_screen(app, 0, 0)
    yield opened
    _close(opened)


@when(parsers.parse(
    'the application is given a work area of {width:d}x{height:d}'),
    target_fixture="sized_app")
def the_application_is_given_a_work_area(app, width, height):
    """Reopen it on a screen of this size."""
    opened = _open_on_screen(app, width, height)
    yield opened
    _close(opened)


@when(parsers.parse(
    'the application is given a work area of {width:d}x{height:d} '
    'with scaling {scaling:g}'),
    target_fixture="sized_app")
def the_application_is_given_a_scaled_work_area(app, width, height, scaling):
    """Reopen it on a scaled desktop of this size."""
    opened = _open_on_screen(app, width, height, scaling)
    yield opened
    _close(opened)


@when(parsers.parse('the application is given work areas of {areas}'),
      target_fixture="screen_sizes")
def the_application_is_given_work_areas(app, areas):
    """
    Open it on each screen in turn, and keep what each one measured.

    DEVELOPMENT NOTES:
    ------------------
    One at a time, and the measurements are kept rather than the windows.
    Opening all three together is the two-roots fault again, and there is
    nothing in the scenario that needs them alive at once - it asks only
    that each window fits the screen it was opened on.
    """
    sizes = []
    current = app
    for area in areas.replace(' and ', ' ').split(','):
        width, height = (int(part) for part in area.strip().split('x'))
        current = _open_on_screen(current, width, height)
        sizes.append({
            'min_width': current._min_width,
            'min_height': current._min_height,
            'width': current._current_width,
            'height': current._current_height,
        })
    yield sizes
    _close(current)


@when("the chart draws")
def the_chart_draws(app):
    """Draw the chart."""
    app.gantt_chart.draw_chart()
    app.update_idletasks()


@when("the application updates all")
def the_application_updates_all(app):
    """Update the application."""
    app.update_all()
    app.update_idletasks()


@when("the chart redraws")
def the_chart_redraws(app):
    """Redraw the chart."""
    app.gantt_chart.draw_chart()
    app.update_idletasks()


@when("the task list selection is set to the first visible row")
def the_task_list_selection_is_set_to_first_row(app):
    """Set selection to first visible row."""
    visible_rows = app.task_list.visible_rows()
    if visible_rows:
        app.task_list.tree.selection_set(visible_rows[0])


# THEN FIXTURES

@then(parsers.parse("the window should be sized to {width:d}x{height:d}"))
def check_window_size(sized_app, width, height):
    """
    The window fills the screen it was opened on.

    One step for the plain and the scaled scenarios both. There were two,
    written identically and registered under the same name, so whichever
    pytest-bdd kept was the only one either scenario could reach.
    """
    assert (sized_app._current_width, sized_app._current_height) == (
        width, height)


@then("the usable screen area should match window manager max size")
def check_usable_screen_area_matches_wm_maxsize(app):
    """Check that usable screen area matches window manager max size."""
    assert app._usable_screen_area() == app.wm_maxsize()


@then(parsers.parse(
    "the minimum width should be less than or equal to {max_width:d}"))
def check_min_width_less_than_or_equal(sized_app, max_width):
    """A small screen gets a smaller minimum."""
    assert sized_app._min_width <= max_width


@then(parsers.parse(
    "the minimum height should be less than or equal to {max_height:d}"))
def check_min_height_less_than_or_equal(sized_app, max_height):
    """The same, the other way up."""
    assert sized_app._min_height <= max_height


@then("the minimum dimensions should match the preferred minimum")
def check_min_dimensions_match_preferred(sized_app):
    """A large screen keeps the designed minimum."""
    assert (sized_app._min_width,
            sized_app._min_height) == sized_app.PREFERRED_MINIMUM


@then("for each screen the minimum width should be less than or equal to "
      "the current width")
def check_min_width_per_screen(screen_sizes):
    """No screen gets a window it cannot fit."""
    for size in screen_sizes:
        assert size['min_width'] <= size['width'], size


@then("for each screen the minimum height should be less than or equal to "
      "the current height")
def check_min_height_per_screen(screen_sizes):
    """The same, the other way up."""
    for size in screen_sizes:
        assert size['min_height'] <= size['height'], size


@then("the usable screen area should fallback to screen dimensions")
def check_fallback_to_screen_dimensions(sized_app):
    """A window manager that answers 0x0 is not taken at its word."""
    assert sized_app._usable_screen_area() == (
        sized_app.winfo_screenwidth(),
        sized_app.winfo_screenheight()
    )


@then(parsers.parse("the application should have {part}"))
def check_application_has_part(app, part):
    """Check that the application has the specified part."""
    assert hasattr(app, part), f"the application has no {part}"


@then("the chart task list should be the same as the application task list")
def check_chart_knows_task_list(app):
    """Check that the chart knows the task list."""
    assert app.gantt_chart.task_list is app.task_list


@then("the toolbar task list should be the same as the application task list")
def check_toolbar_knows_task_list(app):
    """Check that the toolbar knows the task list."""
    assert app.toolbar.task_list is app.task_list


@then("the toolbar gantt chart should be the same as the application "
      "gantt chart")
def check_toolbar_knows_chart(app):
    """Check that the toolbar knows the chart."""
    assert app.toolbar.gantt_chart is app.gantt_chart


@then("the clipboard manager should have a clipboard widget")
def check_clipboard_has_widget(app):
    """Check that the clipboard manager has a widget."""
    assert app.clipboard_manager.service.clipboard_widget is not None


@then("the chart drawn rows should match the task list visible rows")
def check_chart_drawn_rows_match(app):
    """Check that chart drawn rows match task list visible rows."""
    assert app.gantt_chart._drawn_rows == app.task_list.visible_rows()


@then("the chart top margin should remain consistent across draws")
def check_chart_top_margin_consistency(app):
    """Check that the chart top margin remains consistent across draws."""
    chart = app.gantt_chart
    # Store the settled margin
    settled = chart._drawn_top_margin

    # Set selection and update
    visible_rows = app.task_list.visible_rows()
    if visible_rows:
        app.task_list.tree.selection_set(visible_rows[0])
    app.update_all()
    app.update_idletasks()
    after_a_click = chart._drawn_top_margin

    # Redraw
    chart.draw_chart()
    app.update_idletasks()
    after_a_redraw = chart._drawn_top_margin

    assert [settled, settled] == [after_a_click, after_a_redraw], \
        "the chart's first row moved between draws"


@then("the chart top margin should be greater than or equal to the chart "
      "top margin constant")
def check_chart_top_margin_geq_constant(app):
    """Check that the chart top margin is >= CHART_TOP_MARGIN."""
    app.gantt_chart.draw_chart()
    app.update_idletasks()
    assert app.gantt_chart._drawn_top_margin >= CHART_TOP_MARGIN


@then("the chart drawn rows should still match the task list visible rows")
def check_chart_drawn_rows_still_match(app):
    """The rows still line up after the list has been rebuilt."""
    app.update_all()
    app.update_idletasks()
    assert app.gantt_chart._drawn_rows == app.task_list.visible_rows()