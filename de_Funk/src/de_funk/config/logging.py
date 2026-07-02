"""
Centralized Logging Configuration for de_Funk.

This module provides a unified logging system that:
- Replaces scattered print statements with structured logging
- Supports multiple output handlers (console, file, JSON)
- Provides colored console output for better readability
- Includes log rotation to prevent disk space issues
- Allows module-specific log levels for noisy dependencies

Usage:
    # In main entry point (run_app.py, scripts, etc.)
    from de_funk.config.logging import setup_logging
    setup_logging()

    # In any module
    from de_funk.config.logging import get_logger
    logger = get_logger(__name__)
    logger.info("Processing started", extra={'ticker': 'AAPL'})

Configuration:
    Set these environment variables to customize logging:
    - LOG_LEVEL: Console log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - LOG_FILE_LEVEL: File log level (defaults to DEBUG)
    - LOG_DIR: Directory for log files (defaults to 'logs/')
    - LOG_JSON: Enable JSON logging (true/false)
"""

import logging
import logging.handlers
import sys
import json
import os
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class LogConfig:
    """
    Logging configuration with sensible defaults.

    All settings can be overridden via environment variables or explicit parameters.
    """

    # Log levels
    console_level: str = "INFO"
    file_level: str = "DEBUG"

    # Output settings
    log_dir: Path = field(default_factory=lambda: Path("logs"))
    log_file: str = "de_funk.log"
    json_log_file: str = "de_funk.json"

    # Rotation settings
    max_bytes: int = 10 * 1024 * 1024  # 10 MB
    backup_count: int = 5

    # Format settings
    console_format: str = "%(asctime)s [%(levelname)8s] %(name)s: %(message)s"
    file_format: str = "%(asctime)s [%(levelname)8s] %(name)s (%(filename)s:%(lineno)d): %(message)s"
    date_format: str = "%Y-%m-%d %H:%M:%S"

    # Structured logging
    enable_json: bool = False

    # Module-specific levels (for noisy modules)
    module_levels: Dict[str, str] = field(default_factory=lambda: {
        'urllib3': 'WARNING',
        'urllib3.connectionpool': 'WARNING',
        'duckdb': 'WARNING',
        'pyspark': 'WARNING',
        'py4j': 'WARNING',
        'streamlit': 'WARNING',
        'watchdog': 'WARNING',
        'fsevents': 'WARNING',
        'httpx': 'WARNING',
        'httpcore': 'WARNING',
        'numexpr': 'WARNING',
        'numexpr.utils': 'WARNING',
    })

    @classmethod
    def from_env(cls, repo_root: Optional[Path] = None) -> "LogConfig":
        """
        Create LogConfig from environment variables.

        Args:
            repo_root: Optional repo root for relative log_dir paths

        Returns:
            LogConfig instance with environment overrides applied
        """
        config = cls()

        # Override from environment
        if os.getenv("LOG_LEVEL"):
            config.console_level = os.getenv("LOG_LEVEL").upper()
        if os.getenv("LOG_FILE_LEVEL"):
            config.file_level = os.getenv("LOG_FILE_LEVEL").upper()
        if os.getenv("LOG_DIR"):
            config.log_dir = Path(os.getenv("LOG_DIR"))
        if os.getenv("LOG_JSON", "").lower() == "true":
            config.enable_json = True

        # Make log_dir relative to repo_root if provided and not absolute
        if repo_root and not config.log_dir.is_absolute():
            config.log_dir = repo_root / config.log_dir

        return config


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }

        # Add extra fields if present
        extra_fields = ['ticker', 'model', 'duration_ms', 'provider', 'endpoint',
                        'record_count', 'operation', 'table', 'path']
        for field_name in extra_fields:
            if hasattr(record, field_name):
                log_data[field_name] = getattr(record, field_name)

        # Add exception info
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_data)


class ColoredFormatter(logging.Formatter):
    """Colored console output for better readability."""

    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'

    def __init__(self, fmt: str, datefmt: str = None, use_colors: bool = True):
        super().__init__(fmt, datefmt)
        self.use_colors = use_colors and self._supports_color()

    @staticmethod
    def _supports_color() -> bool:
        """Check if the terminal supports color output."""
        # Check if stdout is a TTY
        if not hasattr(sys.stdout, 'isatty') or not sys.stdout.isatty():
            return False
        # Check for NO_COLOR environment variable
        if os.getenv('NO_COLOR'):
            return False
        return True

    def format(self, record: logging.LogRecord) -> str:
        """Format with optional colors."""
        if self.use_colors:
            color = self.COLORS.get(record.levelname, '')
            # Create a copy to avoid modifying the original
            record = logging.makeLogRecord(record.__dict__)
            record.levelname = f"{color}{record.levelname:8s}{self.RESET}"
        else:
            record = logging.makeLogRecord(record.__dict__)
            record.levelname = f"{record.levelname:8s}"
        return super().format(record)


# Module-level flag to track initialization
_logging_initialized = False


def setup_logging(config: Optional[LogConfig] = None, repo_root: Optional[Path] = None) -> None:
    """
    Configure logging for the application.

    Should be called once at application startup (e.g., in run_app.py).
    Subsequent calls are no-ops to prevent duplicate handlers.

    Args:
        config: Optional LogConfig. If not provided, creates from environment.
        repo_root: Optional repo root for resolving relative paths.
    """
    global _logging_initialized

    if _logging_initialized:
        return

    if config is None:
        config = LogConfig.from_env(repo_root)

    # Create log directory
    config.log_dir.mkdir(parents=True, exist_ok=True)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Clear existing handlers (prevents duplicates on re-init)
    root_logger.handlers.clear()

    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, config.console_level))
    console_handler.setFormatter(ColoredFormatter(
        config.console_format,
        datefmt=config.date_format
    ))
    root_logger.addHandler(console_handler)

    # File handler with rotation
    file_path = config.log_dir / config.log_file
    file_handler = logging.handlers.RotatingFileHandler(
        file_path,
        maxBytes=config.max_bytes,
        backupCount=config.backup_count,
        encoding='utf-8',
    )
    file_handler.setLevel(getattr(logging, config.file_level))
    file_handler.setFormatter(logging.Formatter(
        config.file_format,
        datefmt=config.date_format
    ))
    root_logger.addHandler(file_handler)

    # JSON handler (optional)
    if config.enable_json:
        json_path = config.log_dir / config.json_log_file
        json_handler = logging.handlers.RotatingFileHandler(
            json_path,
            maxBytes=config.max_bytes,
            backupCount=config.backup_count,
            encoding='utf-8',
        )
        json_handler.setLevel(logging.DEBUG)
        json_handler.setFormatter(StructuredFormatter())
        root_logger.addHandler(json_handler)

    # Set module-specific levels to reduce noise
    for module, level in config.module_levels.items():
        logging.getLogger(module).setLevel(getattr(logging, level))

    _logging_initialized = True

    # Log startup (at DEBUG level to not spam INFO logs)
    logger = logging.getLogger(__name__)
    logger.debug(f"Logging initialized: console={config.console_level}, file={config.file_level}, dir={config.log_dir}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for the given module.

    This is the primary way to get a logger in de_Funk code.

    Usage:
        from de_funk.config.logging import get_logger
        logger = get_logger(__name__)

        logger.debug("Detailed info for debugging")
        logger.info("Normal operation info")
        logger.warning("Something unexpected but handled")
        logger.error("Something failed", exc_info=True)
        logger.critical("System is unusable")

    Args:
        name: Logger name, typically __name__ of the calling module.

    Returns:
        logging.Logger instance
    """
    return logging.getLogger(name)


class LogTimer:
    """
    Context manager for timing operations with automatic logging.

    Usage:
        with LogTimer(logger, "Loading model"):
            model = load_model()

        # Output: Starting: Loading model
        # Output: Completed: Loading model (125.3ms)

        # Or with extra context:
        with LogTimer(logger, "Processing ticker", ticker="AAPL"):
            process(ticker)
    """

    def __init__(
        self,
        logger: logging.Logger,
        operation: str,
        level: int = logging.DEBUG,
        **context
    ):
        """
        Initialize LogTimer.

        Args:
            logger: Logger to use
            operation: Description of the operation being timed
            level: Log level for timing messages (default: DEBUG)
            **context: Additional context to include in log messages
        """
        self.logger = logger
        self.operation = operation
        self.level = level
        self.context = context
        self.start_time = None

    def __enter__(self):
        """Start the timer."""
        self.start_time = datetime.now()
        self.logger.log(
            self.level,
            f"Starting: {self.operation}",
            extra=self.context
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop the timer and log results."""
        duration_ms = (datetime.now() - self.start_time).total_seconds() * 1000

        if exc_type:
            self.logger.error(
                f"Failed: {self.operation} ({duration_ms:.2f}ms)",
                exc_info=True,
                extra={**self.context, 'duration_ms': duration_ms}
            )
        else:
            self.logger.log(
                self.level,
                f"Completed: {self.operation} ({duration_ms:.2f}ms)",
                extra={**self.context, 'duration_ms': duration_ms}
            )

        # Don't suppress exceptions
        return False


def log_function_call(logger: logging.Logger, level: int = logging.DEBUG):
    """
    Decorator to log function entry and exit.

    Usage:
        @log_function_call(logger)
        def my_function(arg1, arg2):
            ...

    Args:
        logger: Logger to use
        level: Log level (default: DEBUG)
    """
    import functools

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            func_name = func.__qualname__
            logger.log(level, f"Entering: {func_name}")
            try:
                result = func(*args, **kwargs)
                logger.log(level, f"Exiting: {func_name}")
                return result
            except Exception:
                logger.log(level, f"Exiting (with exception): {func_name}")
                raise
        return wrapper
    return decorator
