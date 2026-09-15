"""
pytest-bdd tests for the test runner's own rule about who loads what.

Run with:
    python3 -m pytest tests/test_test_runner_bdd.py -q

Converted from test_test_runner.py - every case carried over. Where the
original checked its own name was absent from the pytest-only list, this
module checks its own name is present: importing pytest_bdd makes it one
of the modules it is describing, so the self-check keeps its force by
pointing the other way.
"""
import ast
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

import run_tests

pytestmark = [
    pytest.mark.test_runner,
]

scenarios("features/test_runner.feature")

TESTS_DIR = Path(__file__).parent


# ------------------------------------------------------------------
# WHEN
# ------------------------------------------------------------------

@when("the pytest-only module list is read", target_fixture="listed")
def the_pytest_only_list_is_read():
    return run_tests.pytest_only_modules()


@when("an empty module list is run", target_fixture="ran")
def an_empty_module_list_is_run():
    return run_tests.run_pytest_modules([])


# ------------------------------------------------------------------
# THEN
# ------------------------------------------------------------------

@then("it matches what each test module's own source imports")
def it_matches_what_the_source_imports(listed):
    expected = set()
    for path in TESTS_DIR.glob('test_*.py'):
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
    assert set(listed) == expected


@then(parsers.parse('"{name}" is not in it'))
def the_name_is_not_in_it(listed, name):
    assert name not in listed


@then("the module carrying these steps is in it")
def the_module_carrying_these_steps_is_in_it(listed):
    assert Path(__file__).stem in listed


@then("it is sorted")
def it_is_sorted(listed):
    assert listed == sorted(listed)


@then(parsers.parse('no name in it carries the "{prefix}" prefix'))
def no_name_carries_the_prefix(listed, prefix):
    for name in listed:
        assert not name.startswith(prefix), name


@then(parsers.parse('no name in it ends with "{suffix}"'))
def no_name_ends_with(listed, suffix):
    for name in listed:
        assert not name.endswith(suffix), name


@then("every name in it is a file in the tests directory")
def every_name_is_a_file_that_exists(listed):
    for name in listed:
        assert (TESTS_DIR / f"{name}.py").is_file(), name


@then("it is reported a success")
def it_is_reported_a_success(ran):
    assert ran is True
