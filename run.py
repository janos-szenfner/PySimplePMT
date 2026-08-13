#!/usr/bin/env python3
"""
Entry point for the Gantt Project Management Tool.

Run this file to start the application.

Options:
    --version       Print the version and exit.
    --self-check    Verify that every bundled dependency imports, then exit.
    --log-file      Print the path of the log file and exit.
"""

import sys
import os

# Add the current directory to Python path so we can import gantt_app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

#: Packages the application cannot run without.
REQUIRED_PACKAGES = [
    ('customtkinter', 'user interface'),
    ('tkinter', 'user interface toolkit'),
    ('matplotlib', 'Gantt chart rendering, PNG and PDF export'),
    ('numpy', 'chart maths'),
    ('openpyxl', 'Excel import and export'),
]

#: Packages that improve the app but whose absence is handled gracefully.
OPTIONAL_PACKAGES = [
    ('tkinterdnd2', 'enhanced drag-and-drop'),
    ('tasklib', 'MS Project import'),
]


def self_check() -> int:
    """
    Verify that the bundled dependencies are importable.

    RETURNS:
    --------
    int
        0 when every required package imports, 1 otherwise.

    DEVELOPMENT NOTES:
    ------------------
    This is what the packaging pipeline runs against the built artifact. A
    frozen build can install cleanly and still be missing a pure-Python
    dependency that only gets imported on a menu action, which would not
    surface until a user tried to open a spreadsheet.
    """
    import importlib

    from gantt_app import __version__

    print(f"PySimplePMT {__version__} self-check")
    print(f"Python {sys.version.split()[0]}")
    print(f"Frozen build: {getattr(sys, 'frozen', False)}")
    print()

    failures = []

    print("Required:")
    for name, purpose in REQUIRED_PACKAGES:
        try:
            module = importlib.import_module(name)
            version = getattr(module, '__version__', '')
            suffix = f" {version}" if version else ""
            print(f"  OK       {name}{suffix}  ({purpose})")
        except Exception as e:
            print(f"  MISSING  {name}  ({purpose}): {e}")
            failures.append(name)

    print()
    print("Optional:")
    for name, purpose in OPTIONAL_PACKAGES:
        try:
            importlib.import_module(name)
            print(f"  OK       {name}  ({purpose})")
        except Exception:
            print(f"  absent   {name}  ({purpose}) - feature disabled")

    print()
    if failures:
        print(f"FAILED: {len(failures)} required package(s) missing: "
              f"{', '.join(failures)}")
        return 1

    print("PASSED: all required dependencies are available.")
    return 0


def main_cli() -> int:
    """Handle command line options, then start the application."""
    args = sys.argv[1:]

    if '--version' in args:
        from gantt_app import __version__
        print(f"PySimplePMT {__version__}")
        return 0

    if '--self-check' in args:
        return self_check()

    if '--log-file' in args:
        from gantt_app.utils.log import setup_logging, get_log_file_path
        setup_logging(to_stderr=False)
        print(get_log_file_path() or "File logging is unavailable")
        return 0

    from gantt_app.main import main
    main()
    return 0


if __name__ == "__main__":
    sys.exit(main_cli())
