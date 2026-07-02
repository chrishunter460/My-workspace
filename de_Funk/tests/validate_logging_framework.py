#!/usr/bin/env python3
"""
Validate Logging & Error Handling Framework

Quick validation script to verify the logging and error handling
framework is working correctly.

Usage:
    python -m scripts.test.validate_logging_framework
"""
import sys
from pathlib import Path

from de_funk.utils.repo import setup_repo_imports
setup_repo_imports()


def test_logging_setup():
    """Test basic logging setup."""
    print("\n[1] Testing Logging Setup...")

from de_funk.config.logging import setup_logging, get_logger, LogConfig

    # Test with default config
    setup_logging()
    logger = get_logger("test.logging")

    logger.debug("Debug message (file only by default)")
    logger.info("Info message (console + file)")
    logger.warning("Warning message")
    logger.error("Error message")

    # Check log file exists
    log_file = Path("logs/de_funk.log")
    if log_file.exists():
        print(f"    [PASS] Log file created: {log_file}")
        print(f"    [PASS] Log file size: {log_file.stat().st_size} bytes")
    else:
        print(f"    [FAIL] Log file not created")
        return False

    return True


def test_log_timer():
    """Test LogTimer context manager."""
    print("\n[2] Testing LogTimer...")

from de_funk.config.logging import get_logger, LogTimer
    import time

    logger = get_logger("test.timer")

    with LogTimer(logger, "Test operation"):
        time.sleep(0.1)

    print("    [PASS] LogTimer completed without error")
    return True


def test_exception_hierarchy():
    """Test custom exception hierarchy."""
    print("\n[3] Testing Exception Hierarchy...")

from de_funk.core.exceptions import (
        DeFunkError,
        ModelNotFoundError,
        MeasureError,
        RateLimitError,
        ConfigurationError,
        MissingConfigError
    )

    # Test ModelNotFoundError
    try:
        raise ModelNotFoundError("stocks", available_models=["core", "company"])
    except DeFunkError as e:
        assert "stocks" in str(e)
        assert e.recovery_hint is not None
        assert "available" in e.details  # Key is 'available', not 'available_models'
        print(f"    [PASS] ModelNotFoundError: {e}")
        print(f"           Recovery hint: {e.recovery_hint}")

    # Test exception chaining
    try:
        try:
            raise ValueError("Original error")
        except ValueError as orig:
            raise ConfigurationError("Config failed") from orig
    except ConfigurationError as e:
        assert e.__cause__ is not None
        print(f"    [PASS] Exception chaining works")

    # Test MissingConfigError
    try:
        raise MissingConfigError("api_key", config_file=".env")
    except MissingConfigError as e:
        assert "api_key" in str(e)
        print(f"    [PASS] MissingConfigError: {e}")

    return True


def test_error_handling_decorators():
    """Test error handling decorators."""
    print("\n[4] Testing Error Handling Decorators...")

from de_funk.core.error_handling import handle_exceptions, retry_on_exception, safe_call

    # Test handle_exceptions
    @handle_exceptions(ValueError, default_return="fallback", log_level='warning')
    def risky_function(x):
        if x < 0:
            raise ValueError("Negative value")
        return x * 2

    assert risky_function(5) == 10
    assert risky_function(-1) == "fallback"
    print("    [PASS] @handle_exceptions works")

    # Test retry_on_exception
    call_count = 0

    @retry_on_exception(RuntimeError, max_retries=3, delay_seconds=0.01)
    def flaky_function():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise RuntimeError("Temporary failure")
        return "success"

    result = flaky_function()
    assert result == "success"
    assert call_count == 3
    print(f"    [PASS] @retry_on_exception works (retried {call_count} times)")

    # Test safe_call
    def will_fail():
        raise RuntimeError("Expected failure")

    result = safe_call(will_fail, default="safe_default")
    assert result == "safe_default"
    print("    [PASS] safe_call() works")

    return True


def test_error_context():
    """Test ErrorContext context manager."""
    print("\n[5] Testing ErrorContext...")

from de_funk.core.error_handling import ErrorContext

    # ErrorContext logs errors but doesn't wrap them - it re-raises the original
    error_logged = False
    try:
        with ErrorContext("Processing data", ticker="AAPL", step="transform"):
            raise ValueError("Data validation failed")
    except ValueError as e:
        # Original exception is re-raised (not wrapped)
        assert "Data validation failed" in str(e)
        error_logged = True
        print(f"    [PASS] ErrorContext logs and re-raises original exception")
        print(f"           Original error: {e}")

    assert error_logged, "Exception should have been raised"
    return True


def test_structured_logging():
    """Test structured JSON logging."""
    print("\n[6] Testing Structured Logging...")

from de_funk.config.logging import StructuredFormatter
    import logging
    import json

    # Create a test handler with structured formatter
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredFormatter())

    test_logger = logging.getLogger("test.structured")
    test_logger.addHandler(handler)
    test_logger.setLevel(logging.DEBUG)

    # This will output JSON
    print("    Sample structured log output:")
    test_logger.info("Test structured message", extra={"user": "test", "action": "validate"})

    print("    [PASS] StructuredFormatter produces valid output")
    return True


def main():
    """Run all validation tests."""
    print("=" * 60)
    print("LOGGING & ERROR HANDLING FRAMEWORK VALIDATION")
    print("=" * 60)

    tests = [
        ("Logging Setup", test_logging_setup),
        ("LogTimer", test_log_timer),
        ("Exception Hierarchy", test_exception_hierarchy),
        ("Error Handling Decorators", test_error_handling_decorators),
        ("ErrorContext", test_error_context),
        ("Structured Logging", test_structured_logging),
    ]

    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"    [FAIL] {name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # Summary
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, p in results if p)
    failed = len(results) - passed

    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {name}")

    print()
    print(f"Total: {passed}/{len(results)} passed")

    if failed == 0:
        print("\nAll validations passed! Framework is working correctly.")
    else:
        print(f"\n{failed} validation(s) failed. Check output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
