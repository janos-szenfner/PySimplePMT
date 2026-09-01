"""
Tests for the test runner's own rule about which runner loads what.

WHY THIS MODULE EXISTS:
======================
The suite has two kinds of test in it now: the unittest modules, and the
pytest-bdd scenarios that only pytest can load. Handing the second kind to
unittest does not fail politely - pytest_bdd's scenarios() reads the
configuration of the pytest session that is running, so importing one of
those modules outside a pytest run raises IndexError on an empty CONFIG_STACK
even when every package is installed. CI reported that as a failing test with
a traceback about list indices.

The rule that keeps the two apart is read out of each module's own imports
rather than written down as a list of filenames, so it cannot go stale when
somebody adds another. That is worth a test of its own, because when it goes
wrong the whole suite reports the wrong thing.

DEVELOPMENT NOTES:
------------------
This module deliberately does not import pytest, which would make it one of
the modules it is describing.
"""

import ast
import unittest
from pathlib import Path

import run_tests


class TestWhichModulesNeedPytest(unittest.TestCase):
    """The rule, against the tests that are actually in the directory."""

    def test_it_finds_the_modules_that_import_pytest(self):
        """Read out of the source, so a new one is picked up on its own."""
        expected = set()
        for path in Path('tests').glob('test_*.py'):
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = {alias.name.split('.')[0] for alias in node.names}
                elif isinstance(node, ast.ImportFrom):
                    names = {(node.module or '').split('.')[0]}
                else:
                    continue
                if names & set(run_tests.PYTEST_ONLY_IMPORTS):
                    expected.add(path.stem)
                    break

        self.assertEqual(set(run_tests.pytest_only_modules()), expected)

    def test_an_ordinary_test_module_is_not_one_of_them(self):
        """Or the unittest half of the suite would stop being run."""
        self.assertNotIn('test_models', run_tests.pytest_only_modules())
        self.assertNotIn('test_test_runner', run_tests.pytest_only_modules())

    def test_the_answer_is_sorted_and_carries_no_prefix(self):
        """It is printed, and used to build both a name and a path."""
        found = run_tests.pytest_only_modules()

        self.assertEqual(found, sorted(found))
        for name in found:
            self.assertFalse(name.startswith('tests.'), name)
            self.assertFalse(name.endswith('.py'), name)

    def test_every_named_module_is_a_file_that_exists(self):
        """The names are turned back into paths for pytest to be given."""
        for name in run_tests.pytest_only_modules():
            self.assertTrue((Path('tests') / f"{name}.py").is_file(), name)


class TestRunningNoneOfThem(unittest.TestCase):
    """The case where the directory holds no pytest-only module at all."""

    def test_nothing_to_run_is_not_a_failure(self):
        """
        And does not reach for pytest to find that out - a checkout with
        no scenarios in it must not need pytest installed.
        """
        self.assertTrue(run_tests.run_pytest_modules([]))


if __name__ == '__main__':
    unittest.main()
