"""
pytest-bdd tests for the re-entrancy guard on GanttApp.update_all.

Run with:
    python3 -m pytest tests/test_update_all_bdd.py -q

The real update_all method is borrowed onto a minimal stand-in, so the
guard itself is what is exercised rather than a copy of it. No display
is needed - nothing here builds a widget.
"""
from types import SimpleNamespace

import pytest
from pytest_bdd import given, scenarios, then, when

from gantt_app.main import GanttApp

pytestmark = [
    pytest.mark.update_all,
]

scenarios("features/update_all.feature")


class _FakeApp:
    """Just enough app to run the real update_all against."""

    # The guard under test, borrowed rather than re-implemented.
    update_all = GanttApp.update_all

    def __init__(self, nested_calls=0):
        self.calls = 0
        self.depth = 0
        self.max_depth = 0
        self._nested_calls_left = nested_calls

    def _update_all_now(self):
        """A rebuild that 'changes the plan' part-way through."""
        self.depth += 1
        self.max_depth = max(self.max_depth, self.depth)
        try:
            self.calls += 1
            while self._nested_calls_left:
                self._nested_calls_left -= 1
                self.update_all()
        finally:
            self.depth -= 1


# ------------------------------------------------------------------
# GIVEN
# ------------------------------------------------------------------

@given("a refresh whose rebuild raises one more change",
       target_fixture="ctx")
def a_refresh_raising_one_change():
    return SimpleNamespace(app=_FakeApp(nested_calls=1))


@given("a refresh whose rebuild raises two more changes",
       target_fixture="ctx")
def a_refresh_raising_two_changes():
    return SimpleNamespace(app=_FakeApp(nested_calls=2))


@given("a refresh whose rebuild raises nothing", target_fixture="ctx")
def a_quiet_refresh():
    return SimpleNamespace(app=_FakeApp(nested_calls=0))


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------

@when("update_all runs")
def update_all_runs(ctx):
    ctx.app.update_all()


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@then("the rebuild ran exactly once")
def the_rebuild_ran_once(ctx):
    assert ctx.app.calls == 1


@then("the rebuild ran exactly twice")
def the_rebuild_ran_twice(ctx):
    assert ctx.app.calls == 2


@then("the second run was not inside the first")
def the_second_run_was_not_nested(ctx):
    # The rebuild's own depth counter never passed one: the second pass
    # began only after the first had finished.
    assert ctx.app.max_depth == 1
