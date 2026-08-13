#!/usr/bin/env python3
"""
Test runner for the Gantt Project Management Tool.

Run all tests with: python3 run_tests.py
Run specific tests with: python3 run_tests.py test_module
"""

import sys
import os
import unittest
from pathlib import Path

# Add project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)


def run_all_tests():
    """Run all tests in the tests directory."""
    # Discover and run all tests
    test_loader = unittest.TestLoader()
    test_suite = test_loader.discover('tests', pattern='test_*.py')
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    return result.wasSuccessful()


def run_specific_test(test_module: str):
    """Run a specific test module."""
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
