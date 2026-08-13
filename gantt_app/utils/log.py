"""
Application-wide logging for the Gantt Project Management Tool.

Provides a single configured logger tree rooted at 'gantt_app', writing to
three places at once:

  * a rotating log file on disk, for reporting a problem after the fact,
  * an in-memory buffer, which is what the Log window displays, and
  * stderr, for when the app is started from a terminal.

DEVELOPMENT NOTES:
------------------
The in-memory buffer is the reason this module exists rather than a bare
logging.basicConfig call. A packaged desktop build has no console, so an error
printed to stdout is simply lost; keeping the recent records in a bounded
deque lets the UI show them without reading the file back.

Nothing here raises. Logging that fails - an unwritable directory, a full
disk - must never take the application down with it, so file setup degrades
to memory-and-stderr only.
"""

import logging
import logging.handlers
import os
import sys
import threading
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Deque, List, Optional

#: Root logger name for the whole application.
LOGGER_NAME = 'gantt_app'

#: How many records the in-memory buffer keeps for the Log window.
MEMORY_CAPACITY = 5000

#: Rotating file handler settings.
MAX_LOG_BYTES = 1024 * 1024
BACKUP_COUNT = 3

#: Format shared by every handler.
LOG_FORMAT = '%(asctime)s  %(levelname)-8s  %(name)s  %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

_configured = False
_configure_lock = threading.Lock()
_memory_handler: Optional['MemoryLogHandler'] = None
_log_file_path: Optional[Path] = None


class MemoryLogHandler(logging.Handler):
    """
    Keeps the most recent log records in memory for display in the UI.

    DEVELOPMENT NOTES:
    ------------------
    Records are formatted on arrival rather than stored raw. A LogRecord holds
    references to its arguments, and keeping thousands of them alive would pin
    whatever those arguments point at - potentially entire Project objects.
    Formatting up front keeps the buffer to plain strings.
    """

    def __init__(self, capacity: int = MEMORY_CAPACITY):
        super().__init__()
        self.capacity = capacity
        self._records: Deque[tuple] = deque(maxlen=capacity)
        self._lock_records = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        """Format and store a record, never raising on failure."""
        try:
            message = self.format(record)
        except Exception:
            try:
                message = f"<unformattable log record: {record.msg!r}>"
            except Exception:
                return

        with self._lock_records:
            self._records.append((record.levelno, message))

    def get_records(self, min_level: int = logging.NOTSET) -> List[str]:
        """
        Get the buffered messages at or above a level.

        PARAMETERS:
        -----------
        min_level : int, optional
            Minimum level to include, e.g. logging.WARNING.

        RETURNS:
        --------
        List[str]
            Formatted messages, oldest first.
        """
        with self._lock_records:
            snapshot = list(self._records)
        return [text for level, text in snapshot if level >= min_level]

    def clear(self) -> None:
        """Discard every buffered record."""
        with self._lock_records:
            self._records.clear()

    def count(self, min_level: int = logging.NOTSET) -> int:
        """Count buffered records at or above a level."""
        with self._lock_records:
            snapshot = list(self._records)
        return sum(1 for level, _ in snapshot if level >= min_level)


def get_log_directory() -> Path:
    """
    Get the directory the log file lives in.

    RETURNS:
    --------
    Path
        A per-user, per-platform location: %LOCALAPPDATA% on Windows,
        ~/Library/Logs on macOS, and $XDG_STATE_HOME (or ~/.local/state)
        elsewhere.
    """
    if sys.platform == 'win32':
        base = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
        return Path(base) / 'PySimplePMT' / 'logs'

    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Logs' / 'PySimplePMT'

    state_home = os.environ.get('XDG_STATE_HOME')
    base = Path(state_home) if state_home else Path.home() / '.local' / 'state'
    return base / 'pysimplepmt'


def get_log_file_path() -> Optional[Path]:
    """
    Get the path of the active log file.

    RETURNS:
    --------
    Optional[Path]
        The log file, or None when file logging could not be set up.
    """
    return _log_file_path


def setup_logging(level: int = logging.INFO,
                  to_file: bool = True,
                  to_stderr: bool = True) -> logging.Logger:
    """
    Configure the application logger. Safe to call more than once.

    PARAMETERS:
    -----------
    level : int, optional
        Minimum level written to the log file and stderr (default INFO). The
        in-memory buffer behind the Log window always keeps DEBUG and above,
        so the window's level filter has something to filter.
    to_file : bool, optional
        Whether to write a rotating log file (default True).
    to_stderr : bool, optional
        Whether to echo records to stderr (default True).

    RETURNS:
    --------
    logging.Logger
        The configured 'gantt_app' logger.
    """
    global _configured, _memory_handler, _log_file_path

    with _configure_lock:
        logger = logging.getLogger(LOGGER_NAME)

        if _configured:
            logger.setLevel(level)
            return logger

        # The logger itself passes everything through and each handler
        # filters. Without this the logger dropped DEBUG records before they
        # reached the buffer, so the Log window's Debug filter had nothing to
        # show no matter what the application did.
        logger.setLevel(logging.DEBUG)
        # Records are handled here, not by the root logger
        logger.propagate = False

        formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

        _memory_handler = MemoryLogHandler()
        _memory_handler.setFormatter(formatter)
        _memory_handler.setLevel(logging.DEBUG)
        logger.addHandler(_memory_handler)

        if to_stderr and sys.stderr is not None:
            stream_handler = logging.StreamHandler(sys.stderr)
            stream_handler.setFormatter(formatter)
            stream_handler.setLevel(level)
            logger.addHandler(stream_handler)

        if to_file:
            try:
                directory = get_log_directory()
                directory.mkdir(parents=True, exist_ok=True)
                path = directory / 'pysimplepmt.log'

                file_handler = logging.handlers.RotatingFileHandler(
                    path, maxBytes=MAX_LOG_BYTES, backupCount=BACKUP_COUNT,
                    encoding='utf-8'
                )
                file_handler.setFormatter(formatter)
                file_handler.setLevel(level)
                logger.addHandler(file_handler)
                _log_file_path = path
            except Exception as e:
                # File logging is a convenience - never fail startup over it
                _log_file_path = None
                logger.warning("File logging unavailable: %s", e)

        _configured = True
        logger.debug("Logging initialised (level=%s, file=%s)",
                     logging.getLevelName(level), _log_file_path)
        return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger for a module.

    PARAMETERS:
    -----------
    name : Optional[str]
        Usually __name__. A bare module name is placed under 'gantt_app'.

    RETURNS:
    --------
    logging.Logger
        A logger whose records reach the application's handlers.

    DEVELOPMENT NOTES:
    ------------------
    Calling this before setup_logging still works: the returned logger is
    simply quiet until the handlers are attached, which is the standard
    library's behaviour and avoids import-order constraints.
    """
    if not name or name == LOGGER_NAME:
        return logging.getLogger(LOGGER_NAME)

    if name.startswith(LOGGER_NAME + '.'):
        return logging.getLogger(name)

    return logging.getLogger(f"{LOGGER_NAME}.{name}")


def get_log_text(min_level: int = logging.NOTSET) -> str:
    """
    Get the buffered log as a single block of text.

    PARAMETERS:
    -----------
    min_level : int, optional
        Minimum level to include, e.g. logging.WARNING.

    RETURNS:
    --------
    str
        Formatted log lines, oldest first, or a placeholder when empty.
    """
    if _memory_handler is None:
        return "Logging has not been initialised."

    records = _memory_handler.get_records(min_level)
    if not records:
        return "No log entries at this level yet."
    return "\n".join(records)


def get_log_records(min_level: int = logging.NOTSET) -> List[str]:
    """Get the buffered log lines at or above a level."""
    if _memory_handler is None:
        return []
    return _memory_handler.get_records(min_level)


def count_records(min_level: int = logging.NOTSET) -> int:
    """Count buffered records at or above a level."""
    if _memory_handler is None:
        return 0
    return _memory_handler.count(min_level)


def clear_log() -> None:
    """Discard the buffered records shown in the Log window."""
    if _memory_handler is not None:
        _memory_handler.clear()
        get_logger(__name__).info("Log cleared by user")


def save_log_to(filepath: str, min_level: int = logging.NOTSET) -> bool:
    """
    Write the buffered log to a file.

    RETURNS:
    --------
    bool
        True on success, False if the file could not be written.
    """
    try:
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        header = (
            f"PySimplePMT log export\n"
            f"Exported: {datetime.now().strftime(DATE_FORMAT)}\n"
            f"Source log file: {_log_file_path or 'not available'}\n"
            f"{'-' * 70}\n"
        )
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write(header)
            handle.write(get_log_text(min_level))
            handle.write("\n")
        return True
    except Exception as e:
        get_logger(__name__).error("Could not save log to %s: %s", filepath, e)
        return False


def install_exception_hook() -> None:
    """
    Route uncaught exceptions into the log instead of losing them.

    DEVELOPMENT NOTES:
    ------------------
    A packaged build has no console, so an unhandled traceback would vanish
    entirely. KeyboardInterrupt is passed through to the previous hook so
    Ctrl-C still behaves normally when run from a terminal.
    """
    previous_hook = sys.excepthook

    def handle_exception(exc_type, exc_value, exc_traceback):
        """Log an uncaught exception, then defer to the previous hook."""
        if issubclass(exc_type, KeyboardInterrupt):
            previous_hook(exc_type, exc_value, exc_traceback)
            return

        get_logger(__name__).critical(
            "Uncaught exception",
            exc_info=(exc_type, exc_value, exc_traceback)
        )
        previous_hook(exc_type, exc_value, exc_traceback)

    sys.excepthook = handle_exception


def reset_logging() -> None:
    """
    Tear down the configured handlers.

    DEVELOPMENT NOTES:
    ------------------
    Exists so tests can configure logging repeatedly without stacking
    handlers onto the same logger.
    """
    global _configured, _memory_handler, _log_file_path

    with _configure_lock:
        logger = logging.getLogger(LOGGER_NAME)
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass

        _configured = False
        _memory_handler = None
        _log_file_path = None
