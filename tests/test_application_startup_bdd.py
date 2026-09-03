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


@given(parsers.parse('the application is given a work area of {width:d}x{height:d}'),
       target_fixture="app_with_work_area")
def the_application_is_given_a_work_area(width, height):
    """Create application with a specific work area."""
    from gantt_app.main import GanttApp

    class Fixed(GanttApp):
        def wm_maxsize(self, *_args):
            return (width, height)

    app = Fixed()
    app.withdraw()
    app.update_idletasks()
    yield app
    try:
        app.destroy()
    except tk.TclError:
        pass


@given(parsers.parse('the application is given a work area of {width:d}x{height:d} with scaling {scaling:g}'),
       target_fixture="app_with_scaling")
def the_application_is_given_a_work_area_with_scaling(width, height, scaling):
    """Create application with a specific work area and scaling."""
    from gantt_app.main import GanttApp

    class Fixed(GanttApp):
        def wm_maxsize(self, *_args):
            return (width, height)

        def _window_scaling(self):
            return scaling

    app = Fixed()
    app.withdraw()
    app.update_idletasks()
    yield app
    try:
        app.destroy()
    except tk.TclError:
        pass


@given(parsers.parse('the application is given work areas of {areas}'),
       target_fixture="apps_with_areas")
def the_application_is_given_work_areas(areas):
    """Create applications with multiple work areas."""
    from gantt_app.main import GanttApp

    area_list = [tuple(map(int, area.split('x'))) for area in areas.split(', ')]
    apps = []

    for width, height in area_list:
        class Fixed(GanttApp):
            def wm_maxsize(self, *_args):
                return (width, height)

        app = Fixed()
        app.withdraw()
        app.update_idletasks()
        apps.append(app)

    yield apps

    # Cleanup all apps
    for app in apps:
        try:
            app.destroy()
        except tk.TclError:
            pass


@given("the application is given a work area of 0x0",
       target_fixture="app_zero_work_area")
def the_application_is_given_zero_work_area():
    """Create application with zero work area."""
    from gantt_app.main import GanttApp

    class Fixed(GanttApp):
        def wm_maxsize(self, *_args):
            return (0, 0)

    app = Fixed()
    app.withdraw()
    app.update_idletasks()
    yield app
    try:
        app.destroy()
    except tk.TclError:
        pass


# WHEN FIXTURES

@when(parsers.parse('the application is given a work area of {width:d}x{height:d}'))
def use_work_area_app(app_with_work_area):
    """Use the application with the specified work area."""
    return app_with_work_area


@when(parsers.parse('the application is given a work area of {width:d}x{height:d} with scaling {scaling:g}'))
def use_scaled_app(app_with_scaling):
    """Use the application with the specified work area and scaling."""
    return app_with_scaling


@when("the application is given a work area of 0x0")
def use_zero_work_area_app(app_zero_work_area):
    """Use the application with zero work area."""
    return app_zero_work_area


@when(parsers.parse('the application is given work areas of {areas}'))
def use_apps_with_areas(apps_with_areas):
    """Use the applications with the specified work areas."""
    return apps_with_areas


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
def check_window_size(app_with_work_area, width, height):
    """Check that the window is sized to the expected dimensions."""
    assert (app_with_work_area._current_width, app_with_work_area._current_height) == (width, height)


@then("the usable screen area should match window manager max size")
def check_usable_screen_area_matches_wm_maxsize(app):
    """Check that usable screen area matches window manager max size."""
    assert app._usable_screen_area() == app.wm_maxsize()


@then(parsers.parse("the minimum width should be less than or equal to {max_width:d}"))
def check_min_width_less_than_or_equal(app_with_work_area, max_width):
    """Check that minimum width is less than or equal to the given value."""
    assert app_with_work_area._min_width <= max_width


@then(parsers.parse("the minimum height should be less than or equal to {max_height:d}"))
def check_min_height_less_than_or_equal(app_with_work_area, max_height):
    """Check that minimum height is less than or equal to the given value."""
    assert app_with_work_area._min_height <= max_height


@then("the minimum dimensions should match the preferred minimum")
def check_min_dimensions_match_preferred(app_with_work_area):
    """Check that minimum dimensions match the preferred minimum."""
    assert (app_with_work_area._min_width, app_with_work_area._min_height) == app_with_work_area.PREFERRED_MINIMUM


@then("for each screen the minimum width should be less than or equal to the current width")
def check_min_width_per_screen(apps_with_areas):
    """Check that for each app, min width <= current width."""
    for app in apps_with_areas:
        assert app._min_width <= app._current_width


@then("for each screen the minimum height should be less than or equal to the current height")
def check_min_height_per_screen(apps_with_areas):
    """Check that for each app, min height <= current height."""
    for app in apps_with_areas:
        assert app._min_height <= app._current_height


@then(parsers.parse("the window should be sized to {width:d}x{height:d}"))
def check_scaled_window_size(app_with_scaling, width, height):
    """Check that the scaled window is sized to the expected dimensions."""
    assert (app_with_scaling._current_width, app_with_scaling._current_height) == (width, height)


@then("the usable screen area should fallback to screen dimensions")
def check_fallback_to_screen_dimensions(app_zero_work_area):
    """Check that usable screen area falls back to screen dimensions when wm_maxsize returns 0x0."""
    assert app_zero_work_area._usable_screen_area() == (
        app_zero_work_area.winfo_screenwidth(),
        app_zero_work_area.winfo_screenheight()
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


@then("the toolbar gantt chart should be the same as the application gantt chart")
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

    assert [settled, settled] == [after_a_click, after_a_redraw], "the chart's first row moved between draws"


@then("the chart top margin should be greater than or equal to the chart top margin constant")
def check_chart_top_margin_geq_constant(app):
    """Check that the chart top margin is >= CHART_TOP_MARGIN."""
    app.gantt_chart.draw_chart()
    app.update_idletasks()
    assert app.gantt_chart._drawn_top_margin >= CHART_TOP_MARGIN


@then("the chart drawn rows should still match the task list visible rows")
def check_chart_drawn_rows_still_match(app):
    """Check that chart drawn rows still match task list visible rows after updates."""
    app.update_all()
    app.update_idletasks()
    assert app.gantt_chart._drawn_rows == app.task_list.visible_rows()