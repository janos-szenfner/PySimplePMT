"""
Tests for the application logging utility.
"""

import logging
import os
import tempfile
import unittest
from pathlib import Path

from gantt_app.utils import log as log_module
from gantt_app.utils.log import (
    LOGGER_NAME, MemoryLogHandler, setup_logging, get_logger, get_log_text,
    get_log_records, count_records, clear_log, save_log_to, reset_logging,
    get_log_directory, get_log_file_path, install_exception_hook
)


class TestMemoryLogHandler(unittest.TestCase):
    """Tests for the in-memory buffer that backs the Log window."""

    def setUp(self):
        """Set up a handler with a formatter."""
        self.handler = MemoryLogHandler(capacity=5)
        self.handler.setFormatter(logging.Formatter('%(levelname)s:%(message)s'))

    def _record(self, level, message):
        """Build a log record at the given level."""
        return logging.LogRecord(
            name='test', level=level, pathname=__file__, lineno=1,
            msg=message, args=(), exc_info=None
        )

    def test_records_are_stored_formatted(self):
        """Emitted records are kept as formatted strings."""
        self.handler.emit(self._record(logging.INFO, "hello"))

        self.assertEqual(self.handler.get_records(), ["INFO:hello"])

    def test_capacity_is_bounded(self):
        """The buffer discards the oldest records beyond its capacity."""
        for index in range(8):
            self.handler.emit(self._record(logging.INFO, f"message {index}"))

        records = self.handler.get_records()
        self.assertEqual(len(records), 5)
        self.assertIn("message 7", records[-1])
        self.assertNotIn("message 0", " ".join(records))

    def test_level_filtering(self):
        """Records below the requested level are excluded."""
        self.handler.emit(self._record(logging.DEBUG, "debug"))
        self.handler.emit(self._record(logging.WARNING, "warning"))
        self.handler.emit(self._record(logging.ERROR, "error"))

        self.assertEqual(len(self.handler.get_records()), 3)
        self.assertEqual(len(self.handler.get_records(logging.WARNING)), 2)
        self.assertEqual(len(self.handler.get_records(logging.ERROR)), 1)

    def test_count(self):
        """Counting honours the level filter."""
        self.handler.emit(self._record(logging.INFO, "info"))
        self.handler.emit(self._record(logging.ERROR, "error"))

        self.assertEqual(self.handler.count(), 2)
        self.assertEqual(self.handler.count(logging.ERROR), 1)

    def test_clear(self):
        """Clearing empties the buffer."""
        self.handler.emit(self._record(logging.INFO, "hello"))
        self.handler.clear()

        self.assertEqual(self.handler.get_records(), [])

    def test_bad_record_does_not_raise(self):
        """A record that cannot be formatted is swallowed, not raised."""
        record = self._record(logging.INFO, "%d items")
        record.args = ("not a number",)

        try:
            self.handler.emit(record)
        except Exception as e:
            self.fail(f"emit() raised {e}")


class TestSetupLogging(unittest.TestCase):
    """Tests for configuring the application logger."""

    def setUp(self):
        """Start from a clean logging state."""
        reset_logging()

    def tearDown(self):
        """Leave logging unconfigured for the next test."""
        reset_logging()

    def test_setup_returns_application_logger(self):
        """The configured logger is the application root."""
        logger = setup_logging(to_file=False, to_stderr=False)

        self.assertEqual(logger.name, LOGGER_NAME)
        self.assertFalse(logger.propagate)

    def test_messages_reach_the_buffer(self):
        """A logged message shows up in the buffer."""
        setup_logging(to_file=False, to_stderr=False)
        get_logger('demo').error("something broke")

        self.assertIn("something broke", get_log_text())
        self.assertEqual(count_records(logging.ERROR), 1)

    def test_repeated_setup_does_not_stack_handlers(self):
        """Calling setup twice leaves the handler count unchanged."""
        first = setup_logging(to_file=False, to_stderr=False)
        count = len(first.handlers)
        second = setup_logging(to_file=False, to_stderr=False)

        self.assertIs(first, second)
        self.assertEqual(len(second.handlers), count)

    def test_level_is_respected(self):
        """Records below the configured level are not kept."""
        setup_logging(level=logging.WARNING, to_file=False, to_stderr=False)
        logger = get_logger('demo')
        logger.debug("quiet")
        logger.warning("loud")

        text = get_log_text()
        self.assertNotIn("quiet", text)
        self.assertIn("loud", text)

    def test_file_logging_writes_to_disk(self):
        """A log file is created and receives records."""
        with tempfile.TemporaryDirectory() as directory:
            original = os.environ.get('XDG_STATE_HOME')
            os.environ['XDG_STATE_HOME'] = directory
            try:
                reset_logging()
                setup_logging(to_file=True, to_stderr=False)
                path = get_log_file_path()

                if path is None:
                    self.skipTest("file logging unavailable on this platform")

                get_logger('demo').error("written to disk")
                for handler in logging.getLogger(LOGGER_NAME).handlers:
                    handler.flush()

                self.assertTrue(Path(path).exists())
                self.assertIn("written to disk",
                              Path(path).read_text(encoding='utf-8'))
            finally:
                if original is None:
                    os.environ.pop('XDG_STATE_HOME', None)
                else:
                    os.environ['XDG_STATE_HOME'] = original

    def test_unwritable_log_directory_does_not_raise(self):
        """Startup survives a log directory that cannot be created."""
        original = log_module.get_log_directory

        def broken_directory():
            """Stand in for a directory that cannot be created."""
            raise OSError("read-only file system")

        log_module.get_log_directory = broken_directory
        try:
            logger = setup_logging(to_file=True, to_stderr=False)
            logger.info("still works")
            self.assertIn("still works", get_log_text())
            self.assertIsNone(get_log_file_path())
        finally:
            log_module.get_log_directory = original


class TestLogHelpers(unittest.TestCase):
    """Tests for the helpers the Log window relies on."""

    def setUp(self):
        """Configure logging in memory only."""
        reset_logging()
        setup_logging(to_file=False, to_stderr=False)

    def tearDown(self):
        """Leave logging unconfigured for the next test."""
        reset_logging()

    def test_get_logger_namespaces_modules(self):
        """A module name is placed under the application logger."""
        self.assertEqual(get_logger('gantt_app.utils.thing').name,
                         'gantt_app.utils.thing')
        self.assertEqual(get_logger('thing').name, 'gantt_app.thing')
        self.assertEqual(get_logger(None).name, LOGGER_NAME)
        self.assertEqual(get_logger(LOGGER_NAME).name, LOGGER_NAME)

    def test_placeholder_when_empty(self):
        """An empty buffer reports a placeholder rather than a blank string."""
        self.assertIn("No log entries", get_log_text())

    def test_clear_log_leaves_a_marker(self):
        """Clearing empties the buffer and records that it happened."""
        get_logger('demo').error("first")
        clear_log()

        text = get_log_text()
        self.assertNotIn("first", text)
        self.assertIn("Log cleared", text)

    def test_get_log_records_returns_lines(self):
        """Records are available as a list as well as a block of text."""
        get_logger('demo').warning("careful")

        records = get_log_records(logging.WARNING)
        self.assertEqual(len(records), 1)
        self.assertIn("careful", records[0])

    def test_save_log_to_file(self):
        """The buffered log can be written out with a header."""
        get_logger('demo').error("saved entry")

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'nested', 'log.txt')
            self.assertTrue(save_log_to(path))

            content = Path(path).read_text(encoding='utf-8')
            self.assertIn("PySimplePMT log export", content)
            self.assertIn("saved entry", content)

    def test_save_log_to_bad_path(self):
        """Saving to an impossible path reports failure instead of raising."""
        self.assertFalse(save_log_to('/proc/definitely/not/writable/log.txt'))

    def test_exception_logging_includes_traceback(self):
        """logger.exception records the traceback for debugging."""
        logger = get_logger('demo')
        try:
            raise ValueError("boom")
        except ValueError:
            logger.exception("caught it")

        text = get_log_text()
        self.assertIn("caught it", text)
        self.assertIn("ValueError", text)
        self.assertIn("Traceback", text)

    def test_install_exception_hook_is_reversible(self):
        """The hook chains to whatever was installed before it."""
        import sys

        original = sys.excepthook
        try:
            install_exception_hook()
            self.assertIsNot(sys.excepthook, original)
        finally:
            sys.excepthook = original


class TestLogDirectory(unittest.TestCase):
    """Tests for where the log file is placed."""

    def test_directory_is_absolute(self):
        """The log directory is a usable absolute path."""
        directory = get_log_directory()

        self.assertTrue(directory.is_absolute())
        self.assertIn('ysimplepmt', str(directory).lower())


class TestImportersLogFailures(unittest.TestCase):
    """Tests that importer failures reach the log rather than stdout."""

    def setUp(self):
        """Configure logging in memory only."""
        reset_logging()
        setup_logging(to_file=False, to_stderr=False)

    def tearDown(self):
        """Leave logging unconfigured for the next test."""
        reset_logging()

    def test_missing_file_is_logged(self):
        """A missing import file is recorded."""
        from gantt_app.utils.gan_importer import import_gan_file

        self.assertIsNone(import_gan_file('/nonexistent/plan.gan'))
        self.assertIn('/nonexistent/plan.gan', get_log_text())

    def test_absent_optional_dependency_is_not_an_error(self):
        """A missing optional MPP reader does not register as an error."""
        from gantt_app.utils.mpp_importer import import_mpp_file

        try:
            import tasklib  # noqa: F401
            self.skipTest("tasklib is installed, so nothing is reported")
        except ImportError:
            pass

        self.assertIsNone(import_mpp_file('/nonexistent/plan.mpp'))

        # The Log window's error count and Error filter must stay meaningful
        self.assertEqual(count_records(logging.ERROR), 0)
        self.assertNotIn('Traceback', get_log_text())
        self.assertIn('tasklib', get_log_text().lower())

    def test_malformed_file_logs_a_traceback(self):
        """A parse failure is logged at error level with its traceback."""
        from gantt_app.utils.gan_importer import import_gan_file

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'bad.gan')
            with open(path, 'w', encoding='utf-8') as handle:
                handle.write('<project><tasks></project>')

            self.assertIsNone(import_gan_file(path))

        self.assertGreaterEqual(count_records(logging.ERROR), 1)
        self.assertIn('Traceback', get_log_text(logging.ERROR))


if __name__ == '__main__':
    unittest.main()
