# PySimplePMT — agent notes

## Changelog convention

`CHANGELOG.md` has **no `## Unreleased` section**. New entries are added as
bullets directly under the top version section (currently `## 1.72.0`). The BDD
test `test_the_real_changelog_loads_with_the_latest_first` asserts the first
section heading starts with the released version — an `Unreleased` heading
breaks it.

## Tests

- Full suite: `python3 -m pytest tests/ -q` (~2.5 min, ~3300 tests)
- BDD tests pair `tests/features/*.feature` with `tests/test_*_bdd.py`
- Display-gated scenarios need a real display (Tk); they skip headless

## Tk/CustomTkinter gotchas

- Do not `pack` children into `ScrollFrame` — it `grid`s its canvas internally;
  put children in `box.content` (pack/grid can't mix in one parent).
- `CTkFrame` already owns a `_draw` method — don't reuse that name in
  subclasses (see `BoardRedrawMixin._draw_content`).
- `root.update()` spins forever while a `CTkToplevel` exists (its polling
  `after` keeps the queue non-empty) — drive popup callbacks directly in tests.
- Popups registered via `watch_for_click_elsewhere` must call
  `stop_watching_for_click_elsewhere` on destroy, or the watcher list pins
  them in memory.

## Logging

- `logger = get_logger(__name__)` from `gantt_app.utils.log` everywhere except
  `core/models.py` and `core/deliverable.py` (stdlib logging — circular import).
- Warn on **present-but-malformed** persisted/imported values; stay silent on
  absent optional fields and on `tk.TclError` teardown guards.

## File writes

Exporters and project saves go through `atomic_write(filepath, write)` in
`gantt_app/utils/file_io.py` — temp file, `.bak` roll, `os.replace`, cleanup.
Don't reimplement it.
