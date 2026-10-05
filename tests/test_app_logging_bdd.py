"""
pytest-bdd tests for the application logging utility
(gantt_app/utils/log.py).

Run with:
    python3 -m pytest tests/test_app_logging_bdd.py -q

Nothing here needs a display.
"""
import logging
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.utils import log as log_module
from gantt_app.utils.log import (
    LOGGER_NAME, MemoryLogHandler, clear_log, count_records,
    get_log_directory, get_log_file_path, get_log_records, get_log_text,
    get_logger, install_exception_hook, reset_logging, save_log_to,
    setup_logging,
)

pytestmark = [
    pytest.mark.app_logging,
]

scenarios("features/app_logging.feature")

LEVELS = {
    'DEBUG': logging.DEBUG, 'INFO': logging.INFO,
    'WARNING': logging.WARNING, 'ERROR': logging.ERROR,
}


@pytest.fixture
def ctx():
    context = SimpleNamespace(handler=None, records=[], error=None,
                              ran=[], logger=None, saved=None,
                              text=None, counts={}, result=None,
                              first_logger=None, handler_count=None,
                              gallery=None, directory=None)
    yield context
    # Whatever the scenario configured, leave logging unconfigured for
    # the next one - the same discipline the unittest tearDowns kept.
    reset_logging()
    saved = getattr(context, '_saved_xdg', '__unset__')
    if saved != '__unset__':
        if saved is None:
            os.environ.pop('XDG_STATE_HOME', None)
        else:
            os.environ['XDG_STATE_HOME'] = saved


def _record(level, message):
    return logging.LogRecord(
        name='test', level=level, pathname=__file__, lineno=1,
        msg=message, args=(), exc_info=None)


# ------------------------------------------------------------------
# GIVEN - the buffer
# ------------------------------------------------------------------

@given(parsers.parse('a memory handler holding {capacity:d} records'))
def a_memory_handler(ctx, capacity):
    ctx.handler = MemoryLogHandler(capacity=capacity)
    ctx.handler.setFormatter(
        logging.Formatter('%(levelname)s:%(message)s'))


@given(parsers.parse('a {level} record "{message}" is emitted'))
@given(parsers.parse('an {level} record "{message}" is emitted'))
def a_record_is_emitted(ctx, level, message):
    ctx.handler.emit(_record(LEVELS[level], message))


@when(parsers.parse('an {level} record "{message}" is emitted'))
def when_a_record_is_emitted(ctx, level, message):
    a_record_is_emitted(ctx, level, message)


@when(parsers.parse('{count:d} numbered INFO records are emitted'))
def numbered_records_are_emitted(ctx, count):
    for index in range(count):
        ctx.handler.emit(_record(logging.INFO, f"message {index}"))


@when("a malformed record is emitted")
def a_malformed_record_is_emitted(ctx):
    record = _record(logging.INFO, "%d items")
    record.args = ("not a number",)
    try:
        ctx.handler.emit(record)
    except Exception as error:
        ctx.error = error


@when("the buffer is cleared")
def the_buffer_is_cleared(ctx):
    ctx.handler.clear()


# ------------------------------------------------------------------
# GIVEN - logger setup
# ------------------------------------------------------------------

@given("logging is reset")
def logging_is_reset(ctx):
    reset_logging()


@given("logging is set up in memory only")
def logging_in_memory(ctx):
    reset_logging()
    ctx.logger = setup_logging(to_file=False, to_stderr=False)


@given("logging is set up in memory only at WARNING")
def logging_in_memory_at_warning(ctx):
    reset_logging()
    ctx.logger = setup_logging(level=logging.WARNING,
                               to_file=False, to_stderr=False)


@when("logging is set up in memory only")
def when_logging_in_memory(ctx):
    ctx.logger = setup_logging(to_file=False, to_stderr=False)


@when("logging is set up in memory only again")
def logging_again(ctx):
    ctx.first_logger = ctx.logger
    ctx.handler_count = len(ctx.logger.handlers)
    ctx.logger = setup_logging(to_file=False, to_stderr=False)


@given("a temporary state directory")
def a_temporary_state_directory(ctx, tmp_path):
    ctx.state_dir = str(tmp_path)
    ctx._saved_xdg = os.environ.get('XDG_STATE_HOME')
    os.environ['XDG_STATE_HOME'] = ctx.state_dir


@given("logging is set up to file")
def logging_to_file(ctx):
    reset_logging()
    ctx.logger = setup_logging(to_file=True, to_stderr=False)


@when("logging is set up to file")
def when_logging_to_file(ctx):
    logging_to_file(ctx)


@given("the log directory cannot be created")
def the_log_directory_cannot_be_created(ctx, monkeypatch):
    def broken_directory():
        raise OSError("read-only file system")
    monkeypatch.setattr(log_module, 'get_log_directory',
                        broken_directory)


# ------------------------------------------------------------------
# WHEN - logging, clearing, saving
# ------------------------------------------------------------------

@when(parsers.parse('the module "{name}" logs the {level} "{message}"'))
def the_module_logs(ctx, name, level, message):
    getattr(get_logger(name), level)(message)


@given(parsers.parse('the module "{name}" logs the {level} "{message}"'))
def given_the_module_logs(ctx, name, level, message):
    the_module_logs(ctx, name, level, message)


@when("the log is cleared")
def the_log_is_cleared(ctx):
    clear_log()


@when("the log is saved to a nested file")
def the_log_is_saved_nested(ctx, tmp_path):
    ctx.saved = save_log_to(str(tmp_path / 'nested' / 'log.txt'))
    ctx.saved_path = tmp_path / 'nested' / 'log.txt'


@when(parsers.parse('the log is saved to "{path}"'))
def the_log_is_saved_to(ctx, path):
    ctx.saved = save_log_to(path)


@when(parsers.parse('a ValueError is logged with "{message}"'))
def a_value_error_is_logged(ctx, message):
    try:
        raise ValueError("boom")
    except ValueError:
        get_logger('demo').exception(message)


@when("the exception hook is installed")
def the_exception_hook_is_installed(ctx):
    import sys
    ctx.original_hook = sys.excepthook
    install_exception_hook()


@when(parsers.parse('a command wrapped as "{label}" runs'))
def a_wrapped_command_runs(ctx, label):
    from gantt_app.views.ribbon import RibbonBar
    wrapped = RibbonBar._logged_command(label,
                                        lambda: ctx.ran.append(True))
    wrapped()


@when("the gallery items run")
def the_gallery_items_run(ctx):
    from gantt_app.views.ribbon import RibbonBar
    items = [
        {'label': 'PNG...', 'command': lambda: ctx.ran.append('png')},
        {'label': 'More', 'submenu': [
            {'label': 'Deep', 'command': lambda: ctx.ran.append('deep')},
        ]},
        {'label': 'Separator'},
    ]
    ctx.gallery = RibbonBar._logged_items(items, 'Export')
    ctx.gallery[0]['command']()
    ctx.gallery[1]['submenu'][0]['command']()


# ------------------------------------------------------------------
# WHEN - the imports that fail
# ------------------------------------------------------------------

@when(parsers.parse('a GAN file is imported from "{path}"'))
def a_gan_file_is_imported(ctx, path):
    from gantt_app.utils.gan_importer import import_gan_file
    ctx.result = import_gan_file(path)


@when("a binary MPP file is imported")
def a_binary_mpp_is_imported(ctx, tmp_path):
    from gantt_app.utils.mpp_importer import (
        OLE2_SIGNATURE, import_mpp_file,
    )
    path = tmp_path / 'binary.mpp'
    path.write_bytes(OLE2_SIGNATURE + b'\x00' * 64)
    ctx.result = import_mpp_file(str(path))


@when("a malformed GAN file is imported")
def a_malformed_gan_file_is_imported(ctx, tmp_path):
    from gantt_app.utils.gan_importer import import_gan_file
    path = tmp_path / 'bad.gan'
    path.write_text('<project><tasks></project>', encoding='utf-8')
    ctx.result = import_gan_file(str(path))


# ------------------------------------------------------------------
# THEN - the buffer
# ------------------------------------------------------------------

@then(parsers.parse('the buffer reads "{line}"'))
def the_buffer_reads(ctx, line):
    assert ctx.handler.get_records() == [line]


@then(parsers.parse('the buffer holds {count:d} records'))
def the_buffer_holds(ctx, count):
    assert len(ctx.handler.get_records()) == count


@then(parsers.parse('the buffer holds {count:d} records at {level}'))
def the_buffer_holds_at_level(ctx, count, level):
    assert len(ctx.handler.get_records(LEVELS[level])) == count


@then(parsers.parse('the buffer counts {count:d} records'))
def the_buffer_counts(ctx, count):
    assert ctx.handler.count() == count


@then(parsers.parse('the buffer counts {count:d} records at {level}'))
def the_buffer_counts_at_level(ctx, count, level):
    assert ctx.handler.count(LEVELS[level]) == count


@then(parsers.parse('the buffer\'s last record says "{text}"'))
def the_last_record_says(ctx, text):
    assert text in ctx.handler.get_records()[-1]


@then(parsers.parse('the buffer does not hold "{text}"'))
def the_buffer_does_not_hold(ctx, text):
    assert text not in " ".join(ctx.handler.get_records())


@then("nothing was raised")
def nothing_was_raised(ctx):
    assert ctx.error is None


# ------------------------------------------------------------------
# THEN - setup
# ------------------------------------------------------------------

@then("the logger is the application root")
def the_logger_is_the_application_root(ctx):
    assert ctx.logger.name == LOGGER_NAME


@then("it does not propagate")
def it_does_not_propagate(ctx):
    assert not ctx.logger.propagate


@then("it is the same logger")
def it_is_the_same_logger(ctx):
    assert ctx.logger is ctx.first_logger


@then("the handler count is unchanged")
def the_handler_count_is_unchanged(ctx):
    assert len(ctx.logger.handlers) == ctx.handler_count


@then("the log file exists")
def the_log_file_exists(ctx):
    path = get_log_file_path()
    if path is None:
        pytest.skip("file logging unavailable on this platform")
    for handler in logging.getLogger(LOGGER_NAME).handlers:
        handler.flush()
    assert Path(path).exists()
    ctx.log_file = path


@then(parsers.parse('the log file holds "{text}"'))
def the_log_file_holds(ctx, text):
    assert text in Path(ctx.log_file).read_text(encoding='utf-8')


@then("there is no log file path")
def there_is_no_log_file_path(ctx):
    assert get_log_file_path() is None


# ------------------------------------------------------------------
# THEN - the text and records helpers
# ------------------------------------------------------------------

@then(parsers.parse('the log text holds "{text}"'))
def the_log_text_holds(ctx, text):
    assert text in get_log_text()


@then(parsers.parse('the log text does not hold "{text}"'))
def the_log_text_does_not_hold(ctx, text):
    assert text not in get_log_text()


@then(parsers.parse('the log text at {level} holds "{text}"'))
def the_log_text_at_level_holds(ctx, level, text):
    assert text in get_log_text(LEVELS[level])


@then(parsers.parse('the log text at {level} does not hold "{text}"'))
def the_log_text_at_level_does_not_hold(ctx, level, text):
    assert text not in get_log_text(LEVELS[level])


@then(parsers.parse('the log counts {count:d} record at {level}'))
@then(parsers.parse('the log counts {count:d} records at {level}'))
def the_log_counts(ctx, count, level):
    assert count_records(LEVELS[level]) == count


@then(parsers.parse('the log counts at least {count:d} record at '
                    '{level}'))
def the_log_counts_at_least(ctx, count, level):
    assert count_records(LEVELS[level]) >= count


@then(parsers.parse('the logger for "{name}" is "{expected}"'))
def the_logger_for_is(ctx, name, expected):
    assert get_logger(name).name == expected


@then("the logger for nothing is the application root")
def the_logger_for_nothing(ctx):
    assert get_logger(None).name == LOGGER_NAME


@then("the logger for the application root is the application root")
def the_logger_for_the_root(ctx):
    assert get_logger(LOGGER_NAME).name == LOGGER_NAME


@then(parsers.parse('{count:d} record comes back at {level}'))
@then(parsers.parse('{count:d} records come back at {level}'))
def records_come_back(ctx, count, level):
    ctx.records = get_log_records(LEVELS[level])
    assert len(ctx.records) == count


@then(parsers.parse('it says "{text}"'))
def it_says(ctx, text):
    assert text in ctx.records[0]


@then("the save reported success")
def the_save_reported_success(ctx):
    assert ctx.saved is True


@then("the save reported failure")
def the_save_reported_failure(ctx):
    assert ctx.saved is False


@then(parsers.parse('the saved file holds "{text}"'))
def the_saved_file_holds(ctx, text):
    assert text in ctx.saved_path.read_text(encoding='utf-8')


@then("it is not the original hook")
def it_is_not_the_original_hook(ctx):
    import sys
    try:
        assert sys.excepthook is not ctx.original_hook
    finally:
        sys.excepthook = ctx.original_hook


# ------------------------------------------------------------------
# THEN - the ribbon labels
# ------------------------------------------------------------------

@then(parsers.parse('the icon action "{action}" is labelled "{label}"'))
def the_icon_action_is_labelled(ctx, action, label):
    from gantt_app.views.toolbar import IconToolbar
    assert IconToolbar._collect_action_labels()[action] == label


@then(parsers.parse('the ribbon action "{action}" is labelled '
                    '"{label}"'))
def the_ribbon_action_is_labelled(ctx, action, label):
    from gantt_app.views.ribbon import RibbonBar
    assert RibbonBar._collect_action_labels()[action] == label


@then("the command ran")
def the_command_ran(ctx):
    assert ctx.ran == [True]


@then("both gallery commands ran")
def both_gallery_commands_ran(ctx):
    assert ctx.ran == ['png', 'deep']


@then("the separator stayed a separator")
def the_separator_stayed_a_separator(ctx):
    assert 'command' not in ctx.gallery[2]


# ------------------------------------------------------------------
# THEN - the directory
# ------------------------------------------------------------------

@then("the log directory is absolute")
def the_log_directory_is_absolute(ctx):
    ctx.directory = get_log_directory()
    assert ctx.directory.is_absolute()


@then(parsers.parse('the log directory mentions "{text}"'))
def the_log_directory_mentions(ctx, text):
    assert text in str(ctx.directory).lower()


# ------------------------------------------------------------------
# THEN - the imports
# ------------------------------------------------------------------

@then("nothing came back")
def nothing_came_back(ctx):
    assert ctx.result is None
