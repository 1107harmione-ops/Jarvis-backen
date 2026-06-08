#!/usr/bin/env python3
"""
Run the JARVIS V3 test suite.
Usage: python backend/tests/run_tests.py [options]
"""
import sys
import pytest


def main():
    """Run tests with proper configuration."""
    args = [
        "backend/tests/",
        "-v",
        "--tb=short",
        "-p", "no:cacheprovider",
    ]

    # Add any command-line args
    args.extend(sys.argv[1:])

    sys.exit(pytest.main(args))


if __name__ == "__main__":
    main()
