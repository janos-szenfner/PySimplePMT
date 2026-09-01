#!/usr/bin/env python3
"""
Test runner for the Gantt Project Management Tool.

Run all tests with: python3 run_tests.py
Run specific tests with: python3 run_tests.py test_module
"""

import ast
import sys
import os
import unittest
from pathlib import Path

# Add project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

#: Where the tests live, and what a test module is called.
TESTS_DIR = Path(project_root) / 'tests'
TEST_PATTERN = 'test_*.py'

#: Packages that mean a test module can only be loaded by pytest.
PYTEST_ONLY_IMPORTS = ('pytest', 'pytest_bdd')


def pytest_only_modules():
    """
    Test modules unittest must not import, by what they import themselves.

    RETURNS:
    --------
    list[str]
        Module names, without the tests. prefix, sorted.

    DEVELOPMENT NOTES:
    ------------------
    Read out of the source rather than kept as a list of filenames here,
    which would be a list nobody updates.

    These cannot be loaded by unittest at all, and not because the package
    might be missing: pytest_bdd's scenarios() reads the configuration of
    the pytest session that is running, so importing one of these outside
    a pytest run raises IndexError on an empty CONFIG_STACK even when
    every package is installed. Handing them to unittest.discover turns
    that into a failing test with a traceback about list indices, which is
    what CI reported and is nobody's idea of a clue.
    """
    found = []
    for path in sorted(TESTS_DIR.glob(TEST_PATTERN)):
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except (OSError, SyntaxError):
            continue                    # let unittest report it properly
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name.split('.')[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [(node.module or '').split('.')[0]]
            else:
                continue
            if any(name in PYTEST_ONLY_IMPORTS for name in names):
                found.append(path.stem)
                break
    return found


def run_pytest_modules(modules):
    """
    Run the pytest-only modules, with pytest.

    PARAMETERS:
    -----------
    modules : list[str]
        Module names, as pytest_only_modules returns them.

    RETURNS:
    --------
    bool
        True when they all passed, and when pytest is not installed to run
        them - a checkout without the development requirements is not a
        failing test run, it is a smaller one. It says so rather than
        passing quietly, because a suite that skips itself and reports
        success is the one way this can go wrong unnoticed.
    """
    if not modules:
        return True

    try:
        import pytest
    except ImportError:
        print("=" * 50)
        print("SKIPPED, pytest is not installed: "
              + ", ".join(modules))
        print("These need pytest and pytest-bdd:")
        print("    pip install -r requirements-dev.txt")
        return True

    print("=" * 50)
    print("Running with pytest: " + ", ".join(modules))
    paths = [str(TESTS_DIR / f"{name}.py") for name in modules]
    return pytest.main(['-q', *paths]) == 0


def run_all_tests():
    """
    Run every test in the tests directory.

    DEVELOPMENT NOTES:
    ------------------
    Two runners, because the suite has two kinds of test in it. The
    unittest modules are loaded by name rather than by discover() so the
    pytest-only ones can be left out; discover() takes a directory and a
    pattern and would import every file matching it, which is the whole
    problem.
    """
    excluded = set(pytest_only_modules())
    names = [f"tests.{path.stem}"
             for path in sorted(TESTS_DIR.glob(TEST_PATTERN))
             if path.stem not in excluded]

    test_loader = unittest.TestLoader()
    test_suite = test_loader.loadTestsFromNames(names)

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)

    # Both halves run whatever the other did, so one failure does not hide
    # the other's results
    passed_pytest = run_pytest_modules(sorted(excluded))

    return result.wasSuccessful() and passed_pytest


def run_specific_test(test_module: str):
    """
    Run one named test module.

    DEVELOPMENT NOTES:
    ------------------
    A pytest-only module is handed to pytest here too. Naming one on the
    command line is the obvious thing to do after seeing it in the output,
    and importing it under unittest fails in a way that reads as a broken
    test rather than as the wrong runner.
    """
    if test_module in pytest_only_modules():
        return run_pytest_modules([test_module])

    try:
        # Import and run the specific test module
        module = __import__(f'tests.{test_module}', fromlist=[''])
        test_loader = unittest.TestLoader()
        test_suite = test_loader.loadTestsFromModule(module)
        
        # Run tests
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(test_suite)
        
        return result.wasSuccessful()
    except ImportError as e:
        print(f"Error: Could not import test module '{test_module}': {e}")
        return False


def main():
    """Main entry point for test runner."""
    print("Gantt Project Management Tool - Test Runner")
    print("=" * 50)
    
    if len(sys.argv) > 1:
        # Run specific test module
        test_module = sys.argv[1]
        print(f"Running tests from: {test_module}")
        success = run_specific_test(test_module)
    else:
        # Run all tests
        print("Running all tests...")
        success = run_all_tests()
    
    print("=" * 50)
    if success:
        print("All tests passed!")
        sys.exit(0)
    else:
        print("Some tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
