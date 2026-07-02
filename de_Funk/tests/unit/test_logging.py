#!/usr/bin/env python
"""
Unit tests for the centralized logging framework.

Tests:
- Logger initialization
- Log levels
- Colored output detection
- Log file rotation
- Structured JSON logging
- LogTimer context manager

Usage:
    python -m pytest scripts/test/unit/test_logging.py -v
    # or directly:
    python scripts/test/unit/test_logging.py
"""

import sys
import os
import tempfile
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from de_funk.config.logging import (
    setup_logging,
    get_logger,
    LogConfig,
    LogTimer,
    ColoredFormatter,
    StructuredFormatter,
    log_function_call,
)


class TestLogConfig:
    """Tests for LogConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = LogConfig()

        assert config.console_level == "INFO"
        assert config.file_level == "DEBUG"
        assert config.log_file == "de_funk.log"
        assert config.max_bytes == 10 * 1024 * 1024  # 10 MB
        assert config.backup_count == 5
        assert config.enable_json is False

    def test_from_env_defaults(self):
        """Test LogConfig.from_env() with no environment variables."""
        with patch.dict(os.environ, {}, clear=True):
            config = LogConfig.from_env()
            assert config.console_level == "INFO"
            assert config.enable_json is False

    def test_from_env_with_overrides(self):
        """Test LogConfig.from_env() with environment variable overrides."""
        env = {
            "LOG_LEVEL": "DEBUG",
            "LOG_FILE_LEVEL": "WARNING",
            "LOG_JSON": "true",
        }
        with patch.dict(os.environ, env, clear=True):
            config = LogConfig.from_env()
            assert config.console_level == "DEBUG"
            assert config.file_level == "WARNING"
            assert config.enable_json is True


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_returns_logger(self):
        """Test that get_logger returns a Logger instance."""
        logger = get_logger(__name__)
        assert isinstance(logger, logging.Logger)

    def test_get_logger_uses_name(self):
        """Test that logger uses the provided name."""
        logger = get_logger("test.module.name")
        assert logger.name == "test.module.name"

    def test_different_loggers_are_independent(self):
        """Test that different module names get different loggers."""
        logger1 = get_logger("module.one")
        logger2 = get_logger("module.two")
        assert logger1 is not logger2
        assert logger1.name != logger2.name


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_creates_log_directory(self):
        """Test that setup_logging creates the log directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"
            config = LogConfig()
            config.log_dir = log_dir

            # Reset initialization flag for test
            import config.logging as log_module
            log_module._logging_initialized = False

            setup_logging(config)
            assert log_dir.exists()

    def test_idempotent(self):
        """Test that setup_logging is idempotent (only runs once)."""
        import config.logging as log_module

        with tempfile.TemporaryDirectory() as tmpdir:
            config = LogConfig()
            config.log_dir = Path(tmpdir)

            # Reset initialization flag
            log_module._logging_initialized = False

            # First call should initialize
            setup_logging(config)
            assert log_module._logging_initialized is True

            # Get handler count after first setup
            root_logger = logging.getLogger()
            handler_count = len(root_logger.handlers)

            # Second call should be no-op
            setup_logging(config)
            assert len(root_logger.handlers) == handler_count


class TestColoredFormatter:
    """Tests for ColoredFormatter class."""

    def test_color_codes_defined(self):
        """Test that color codes are defined for all levels."""
        formatter = ColoredFormatter("%(message)s")
        assert "DEBUG" in formatter.COLORS
        assert "INFO" in formatter.COLORS
        assert "WARNING" in formatter.COLORS
        assert "ERROR" in formatter.COLORS
        assert "CRITICAL" in formatter.COLORS

    def test_supports_color_detection(self):
        """Test color support detection."""
        # Test when stdout is not a TTY
        with patch.object(sys.stdout, 'isatty', return_value=False):
            assert ColoredFormatter._supports_color() is False

        # Test when NO_COLOR is set
        with patch.dict(os.environ, {"NO_COLOR": "1"}):
            assert ColoredFormatter._supports_color() is False


class TestStructuredFormatter:
    """Tests for StructuredFormatter (JSON logging)."""

    def test_format_produces_valid_json(self):
        """Test that format produces valid JSON."""
        import json

        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )

        result = formatter.format(record)
        parsed = json.loads(result)

        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test"
        assert parsed["message"] == "Test message"
        assert "timestamp" in parsed

    def test_includes_extra_fields(self):
        """Test that extra fields are included in JSON output."""
        import json

        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.ticker = "AAPL"
        record.model = "stocks"

        result = formatter.format(record)
        parsed = json.loads(result)

        assert parsed.get("ticker") == "AAPL"
        assert parsed.get("model") == "stocks"


class TestLogTimer:
    """Tests for LogTimer context manager."""

    def test_logs_start_and_completion(self):
        """Test that LogTimer logs start and completion."""
        mock_logger = MagicMock()

        with LogTimer(mock_logger, "Test operation"):
            pass

        # Should have logged twice: start and completion
        assert mock_logger.log.call_count == 2

    def test_logs_failure_on_exception(self):
        """Test that LogTimer logs error on exception."""
        mock_logger = MagicMock()

        try:
            with LogTimer(mock_logger, "Failing operation"):
                raise ValueError("Test error")
        except ValueError:
            pass

        # Should have called error for the exception
        mock_logger.error.assert_called_once()

    def test_does_not_suppress_exception(self):
        """Test that LogTimer does not suppress exceptions."""
        mock_logger = MagicMock()

        try:
            with LogTimer(mock_logger, "Test"):
                raise RuntimeError("Test error")
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert str(e) == "Test error"


class TestLogFunctionCall:
    """Tests for log_function_call decorator."""

    def test_logs_entry_and_exit(self):
        """Test that decorator logs function entry and exit."""
        mock_logger = MagicMock()

        @log_function_call(mock_logger)
        def test_func():
            return 42

        result = test_func()

        assert result == 42
        assert mock_logger.log.call_count == 2

    def test_logs_exit_on_exception(self):
        """Test that decorator logs exit even on exception."""
        mock_logger = MagicMock()

        @log_function_call(mock_logger)
        def failing_func():
            raise ValueError("Test")

        try:
            failing_func()
        except ValueError:
            pass

        # Should log entry and exit (with exception)
        assert mock_logger.log.call_count == 2


def run_tests():
    """Run all tests and print results."""
    import traceback

    test_classes = [
        TestLogConfig,
        TestGetLogger,
        TestSetupLogging,
        TestColoredFormatter,
        TestStructuredFormatter,
        TestLogTimer,
        TestLogFunctionCall,
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
    # Try to import pytest for better test running
    try:
        import pytest
        sys.exit(pytest.main([__file__, "-v"]))
    except ImportError:
        print("Running tests without pytest...")
        print()
        success = run_tests()
        sys.exit(0 if success else 1)
