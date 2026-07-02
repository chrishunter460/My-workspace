#!/usr/bin/env python
"""
Unit tests for error handling utilities.

Tests:
- @handle_exceptions decorator
- @retry_on_exception decorator
- ErrorContext context manager
- safe_call utility function
- ensure_not_none utility

Usage:
    python -m pytest scripts/test/unit/test_error_handling.py -v
    # or directly:
    python scripts/test/unit/test_error_handling.py
"""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from de_funk.core.error_handling import (
    handle_exceptions,
    retry_on_exception,
    ErrorContext,
    safe_call,
    ensure_not_none,
)


class TestHandleExceptions:
    """Tests for @handle_exceptions decorator."""

    def test_returns_value_on_success(self):
        """Test that decorator returns function result on success."""
        @handle_exceptions(ValueError)
        def successful_func():
            return 42

        assert successful_func() == 42

    def test_returns_default_on_exception(self):
        """Test that decorator returns default on caught exception."""
        @handle_exceptions(ValueError, default_return="default")
        def failing_func():
            raise ValueError("test error")

        assert failing_func() == "default"

    def test_catches_specified_exception_types(self):
        """Test that decorator catches specified exception types."""
        @handle_exceptions(ValueError, KeyError, default_return=None)
        def multi_fail(error_type):
            if error_type == "value":
                raise ValueError("value error")
            elif error_type == "key":
                raise KeyError("key error")
            return "success"

        assert multi_fail("value") is None
        assert multi_fail("key") is None
        assert multi_fail("none") == "success"

    def test_does_not_catch_unspecified_exceptions(self):
        """Test that decorator does not catch unspecified exceptions."""
        @handle_exceptions(ValueError, default_return=None)
        def wrong_exception():
            raise TypeError("wrong type")

        try:
            wrong_exception()
            assert False, "Should have raised TypeError"
        except TypeError:
            pass

    def test_reraise_option(self):
        """Test that reraise=True logs and reraises exception."""
        @handle_exceptions(ValueError, reraise=True)
        def reraise_func():
            raise ValueError("test")

        try:
            reraise_func()
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

    def test_preserves_function_metadata(self):
        """Test that decorator preserves function metadata."""
        @handle_exceptions(ValueError)
        def documented_func():
            """This is a docstring."""
            pass

        assert documented_func.__name__ == "documented_func"
        assert "docstring" in documented_func.__doc__


class TestRetryOnException:
    """Tests for @retry_on_exception decorator."""

    def test_returns_on_first_success(self):
        """Test that function returns immediately on success."""
        call_count = [0]

        @retry_on_exception(ValueError, max_retries=3, delay_seconds=0.01)
        def success_func():
            call_count[0] += 1
            return "success"

        result = success_func()
        assert result == "success"
        assert call_count[0] == 1

    def test_retries_on_exception(self):
        """Test that function retries on exception."""
        call_count = [0]

        @retry_on_exception(ValueError, max_retries=3, delay_seconds=0.01)
        def eventual_success():
            call_count[0] += 1
            if call_count[0] < 3:
                raise ValueError("not yet")
            return "success"

        result = eventual_success()
        assert result == "success"
        assert call_count[0] == 3

    def test_raises_after_max_retries(self):
        """Test that exception is raised after max retries."""
        call_count = [0]

        @retry_on_exception(ValueError, max_retries=2, delay_seconds=0.01)
        def always_fails():
            call_count[0] += 1
            raise ValueError("always fails")

        try:
            always_fails()
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

        # Should have tried 3 times (initial + 2 retries)
        assert call_count[0] == 3

    def test_exponential_backoff(self):
        """Test that delay increases exponentially."""
        delays = []
        original_sleep = time.sleep

        def mock_sleep(seconds):
            delays.append(seconds)

        call_count = [0]

        @retry_on_exception(ValueError, max_retries=3, delay_seconds=0.1, backoff_factor=2.0)
        def always_fails():
            call_count[0] += 1
            raise ValueError("fail")

        with patch('time.sleep', mock_sleep):
            try:
                always_fails()
            except ValueError:
                pass

        # Check backoff pattern
        assert len(delays) == 3
        assert delays[0] < delays[1] < delays[2]

    def test_respects_max_delay(self):
        """Test that delay respects max_delay limit."""
        delays = []

        @retry_on_exception(ValueError, max_retries=5, delay_seconds=10.0, backoff_factor=10.0, max_delay=30.0)
        def always_fails():
            raise ValueError("fail")

        with patch('time.sleep', lambda s: delays.append(s)):
            try:
                always_fails()
            except ValueError:
                pass

        # All delays should be <= max_delay
        for delay in delays:
            assert delay <= 30.0

    def test_on_retry_callback(self):
        """Test that on_retry callback is called."""
        retry_info = []

        def on_retry(attempt, exc):
            retry_info.append((attempt, str(exc)))

        call_count = [0]

        @retry_on_exception(ValueError, max_retries=2, delay_seconds=0.01, on_retry=on_retry)
        def eventually_succeeds():
            call_count[0] += 1
            if call_count[0] < 3:
                raise ValueError("retry me")
            return "done"

        eventually_succeeds()

        assert len(retry_info) == 2
        assert retry_info[0][0] == 0  # First retry (attempt 0)
        assert retry_info[1][0] == 1  # Second retry (attempt 1)


class TestErrorContext:
    """Tests for ErrorContext context manager."""

    def test_logs_start_and_completion(self):
        """Test that ErrorContext logs operation lifecycle."""
        # Just verify it doesn't raise
        with ErrorContext("Test operation"):
            pass

    def test_logs_failure_on_exception(self):
        """Test that ErrorContext logs failure on exception."""
        try:
            with ErrorContext("Failing operation"):
                raise ValueError("test error")
        except ValueError:
            pass

    def test_does_not_suppress_exception(self):
        """Test that ErrorContext does not suppress exceptions."""
        try:
            with ErrorContext("Test"):
                raise RuntimeError("Should propagate")
            assert False, "Exception should have propagated"
        except RuntimeError as e:
            assert str(e) == "Should propagate"

    def test_accepts_context_kwargs(self):
        """Test that ErrorContext accepts keyword context."""
        # Just verify it doesn't raise
        with ErrorContext("Test", model="stocks", ticker="AAPL"):
            pass


class TestSafeCall:
    """Tests for safe_call utility function."""

    def test_returns_result_on_success(self):
        """Test that safe_call returns function result on success."""
        result = safe_call(int, "42")
        assert result == 42

    def test_returns_default_on_exception(self):
        """Test that safe_call returns default on exception."""
        result = safe_call(int, "not_a_number", default=0)
        assert result == 0

    def test_default_is_none(self):
        """Test that default default is None."""
        result = safe_call(int, "not_a_number")
        assert result is None

    def test_passes_kwargs(self):
        """Test that safe_call passes kwargs to function."""
        def greet(name, greeting="Hello"):
            return f"{greeting}, {name}!"

        result = safe_call(greet, "World", greeting="Hi")
        assert result == "Hi, World!"

    def test_log_errors_option(self):
        """Test that log_errors can be disabled."""
        # Should not raise even with logging disabled
        result = safe_call(int, "bad", default=-1, log_errors=False)
        assert result == -1


class TestEnsureNotNone:
    """Tests for ensure_not_none utility function."""

    def test_returns_value_if_not_none(self):
        """Test that value is returned if not None."""
        result = ensure_not_none(42, "value")
        assert result == 42

    def test_accepts_falsy_non_none_values(self):
        """Test that falsy values other than None are accepted."""
        assert ensure_not_none(0, "value") == 0
        assert ensure_not_none("", "value") == ""
        assert ensure_not_none([], "value") == []
        assert ensure_not_none(False, "value") is False

    def test_raises_for_none(self):
        """Test that ValueError is raised for None."""
        try:
            ensure_not_none(None, "config")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "config" in str(e)

    def test_custom_message(self):
        """Test that custom message can be provided."""
        try:
            ensure_not_none(None, "value", message="Custom error message")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert str(e) == "Custom error message"


class TestIntegration:
    """Integration tests combining multiple utilities."""

    def test_handle_exceptions_with_error_context(self):
        """Test combining decorator with context manager."""
        @handle_exceptions(ValueError, default_return="failed")
        def wrapped_operation():
            with ErrorContext("Inner operation"):
                raise ValueError("test")
            return "success"

        result = wrapped_operation()
        assert result == "failed"

    def test_retry_with_safe_call(self):
        """Test retry with safe_call for double protection."""
        attempts = [0]

        @retry_on_exception(ValueError, max_retries=1, delay_seconds=0.01)
        def flaky_operation():
            attempts[0] += 1
            raise ValueError("always fails")

        # Use safe_call to catch the final exception after retries exhausted
        result = safe_call(flaky_operation, default="safe_default")
        assert result == "safe_default"
        assert attempts[0] == 2  # Initial + 1 retry


def run_tests():
    """Run all tests and print results."""
    import traceback

    test_classes = [
        TestHandleExceptions,
        TestRetryOnException,
        TestErrorContext,
        TestSafeCall,
        TestEnsureNotNone,
        TestIntegration,
    ]

    passed = 0
    failed = 0
    errors = []

    for test_class in test_classes:
        instance = test_class()
        for method_name in dir(instance):
            if method_name.startswith("test_"):
                try:
                    method = getattr(instance, method_name)
                    method()
                    print(f"  ✓ {test_class.__name__}.{method_name}")
                    passed += 1
                except Exception as e:
                    print(f"  ✗ {test_class.__name__}.{method_name}: {e}")
                    errors.append((test_class.__name__, method_name, traceback.format_exc()))
                    failed += 1

    print()
    print(f"Results: {passed} passed, {failed} failed")

    if errors:
        print("\nFailure details:")
        for cls, method, tb in errors:
            print(f"\n{cls}.{method}:")
            print(tb)

    return failed == 0


if __name__ == "__main__":
    try:
        import pytest
        sys.exit(pytest.main([__file__, "-v"]))
    except ImportError:
        print("Running tests without pytest...")
        print()
        success = run_tests()
        sys.exit(0 if success else 1)
