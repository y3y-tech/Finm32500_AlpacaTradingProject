#!/usr/bin/env python
"""
Test runner for Financial Signal Processing strategies.

Runs all tests and provides a summary report.
"""

import unittest
import sys
import time


def run_all_tests():
    """Run all test suites and provide summary."""
    print("=" * 80)
    print("FINANCIAL SIGNAL PROCESSING - TEST SUITE")
    print("=" * 80)
    print()

    # Discover and run all tests
    loader = unittest.TestLoader()
    suite = loader.discover("tests", pattern="test_*.py")

    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2)
    start_time = time.time()
    result = runner.run(suite)
    end_time = time.time()

    # Print summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Total tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Execution time: {end_time - start_time:.2f}s")
    print("=" * 80)

    # Return exit code
    return 0 if result.wasSuccessful() else 1


def run_specific_suite(suite_name):
    """Run a specific test suite."""
    loader = unittest.TestLoader()

    if suite_name == "correctness":
        suite = loader.loadTestsFromName("tests.test_strategy_correctness")
        print("Running CORRECTNESS tests...\n")
    elif suite_name == "performance":
        suite = loader.loadTestsFromName("tests.test_performance")
        print("Running PERFORMANCE tests...\n")
    elif suite_name == "profiling":
        suite = loader.loadTestsFromName("tests.test_profiling")
        print("Running PROFILING tests...\n")
    else:
        print(f"Unknown test suite: {suite_name}")
        print("Available suites: correctness, performance, profiling")
        return 1

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Run specific suite
        suite_name = sys.argv[1]
        exit_code = run_specific_suite(suite_name)
    else:
        # Run all tests
        exit_code = run_all_tests()

    sys.exit(exit_code)
