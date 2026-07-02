"""
Error Handling Utilities for de_Funk.

Provides decorators and context managers for consistent error handling:
- @handle_exceptions: Log and optionally suppress specific exceptions
- @retry_on_exception: Automatic retry with exponential backoff
- ErrorContext: Context manager for detailed error reporting

Usage:
from de_funk.core.error_handling import handle_exceptions, retry_on_exception, ErrorContext
    from de_funk.config.logging import get_logger

    logger = get_logger(__name__)

    # Log and return default on failure
    @handle_exceptions(ValueError, KeyError, default_return=[])
    def parse_data(raw):
        ...

    # Log and reraise (for debugging)
    @handle_exceptions(reraise=True)
    def must_succeed():
        ...

    # Automatic retry for transient failures
    @retry_on_exception(ConnectionError, requests.RequestException, max_retries=3)
    def fetch_from_api():
        ...

    # Detailed context on failure
    with ErrorContext("Loading model", model_name=name):
        model = load_model(name)
"""

import functools
import time
from typing import Callable, Type, Tuple, Optional, Any, Union
from datetime import datetime

from de_funk.config.logging import get_logger

logger = get_logger(__name__)


def handle_exceptions(
    *exception_types: Type[Exception],
    default_return: Any = None,
    log_level: str = 'error',
    reraise: bool = False,
    message: Optional[str] = None
) -> Callable:
    """
    Decorator for consistent exception handling.

    Catches specified exceptions, logs them, and either returns a default
    value or reraises them.

    Args:
        *exception_types: Exception types to catch. Defaults to (Exception,).
        default_return: Value to return on exception (if not reraising).
        log_level: Level to log at ('debug', 'info', 'warning', 'error', 'critical').
        reraise: If True, log the exception then reraise it.
        message: Optional custom log message prefix.

    Returns:
        Decorated function

    Examples:
        # Return empty list on ValueError or KeyError
        @handle_exceptions(ValueError, KeyError, default_return=[])
        def risky_function():
            ...

        # Log and reraise for debugging
        @handle_exceptions(reraise=True)
        def must_succeed():
            ...

        # Custom log message
        @handle_exceptions(IOError, message="Failed to read file")
        def read_file():
            ...
    """
    if not exception_types:
        exception_types = (Exception,)

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exception_types as e:
                # Build log message
                func_name = func.__qualname__
                exc_type = type(e).__name__
                exc_msg = str(e)

                if message:
                    log_msg = f"{message}: {exc_type}: {exc_msg} (in {func_name})"
                else:
                    log_msg = f"Exception in {func_name}: {exc_type}: {exc_msg}"

                # Log at appropriate level
                log_func = getattr(logger, log_level)
                log_func(log_msg, exc_info=True)

                if reraise:
                    raise
                return default_return

        return wrapper
    return decorator


def retry_on_exception(
    *exception_types: Type[Exception],
    max_retries: int = 3,
    delay_seconds: float = 1.0,
    backoff_factor: float = 2.0,
    max_delay: float = 60.0,
    on_retry: Optional[Callable[[int, Exception], None]] = None
) -> Callable:
    """
    Decorator for automatic retry with exponential backoff.

    Retries the function on specified exceptions, with increasing delay
    between attempts.

    Args:
        *exception_types: Exception types to retry on. Defaults to (Exception,).
        max_retries: Maximum number of retries (0 means try once, no retries).
        delay_seconds: Initial delay between retries in seconds.
        backoff_factor: Multiply delay by this factor after each retry.
        max_delay: Maximum delay between retries.
        on_retry: Optional callback called before each retry: on_retry(attempt, exception)

    Returns:
        Decorated function

    Examples:
        # Retry network errors up to 3 times
        @retry_on_exception(ConnectionError, TimeoutError, max_retries=3)
        def fetch_data():
            ...

        # Custom retry callback
        def log_retry(attempt, exc):
            logger.warning(f"Retry {attempt} due to: {exc}")

        @retry_on_exception(IOError, max_retries=5, on_retry=log_retry)
        def read_with_retry():
            ...
    """
    if not exception_types:
        exception_types = (Exception,)

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            delay = delay_seconds
            func_name = func.__qualname__

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exception_types as e:
                    last_exception = e
                    exc_type = type(e).__name__

                    if attempt < max_retries:
                        # Log retry attempt
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries + 1} failed for "
                            f"{func_name}: {exc_type}: {e}. Retrying in {delay:.1f}s..."
                        )

                        # Call retry callback if provided
                        if on_retry:
                            try:
                                on_retry(attempt, e)
                            except Exception as callback_err:
                                logger.warning(f"Retry callback failed: {callback_err}")

                        # Wait before retry
                        time.sleep(delay)

                        # Increase delay for next retry
                        delay = min(delay * backoff_factor, max_delay)
                    else:
                        # Final attempt failed
                        logger.error(
                            f"All {max_retries + 1} attempts failed for {func_name}",
                            exc_info=True
                        )

            # Reraise the last exception
            raise last_exception

        return wrapper
    return decorator


class ErrorContext:
    """
    Context manager for detailed error reporting.

    Logs entry and exit of operations, with detailed context on failures.
    Does NOT suppress exceptions - they propagate after being logged.

    Usage:
        with ErrorContext("Loading model", model_name=name):
            model = load_model(name)

        # On success: logs "Completed: Loading model"
        # On failure: logs "Failed: Loading model" with exception details

    Args:
        operation: Description of the operation
        log_level: Level for success/start logs (default: DEBUG)
        **context: Additional context fields to include in logs
    """

    def __init__(
        self,
        operation: str,
        log_level: int = None,
        **context
    ):
        """
        Initialize ErrorContext.

        Args:
            operation: Human-readable description of the operation
            log_level: Logging level for non-error messages (default: logging.DEBUG)
            **context: Additional context to include in log messages
        """
        import logging
        self.operation = operation
        self.log_level = log_level if log_level is not None else logging.DEBUG
        self.context = context
        self.start_time = None

    def __enter__(self):
        """Log operation start."""
        self.start_time = datetime.now()
        logger.log(
            self.log_level,
            f"Starting: {self.operation}",
            extra=self.context
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Log operation result."""
        duration_ms = (datetime.now() - self.start_time).total_seconds() * 1000

        if exc_type:
            # Operation failed
            logger.error(
                f"Failed: {self.operation} ({duration_ms:.2f}ms)",
                exc_info=True,
                extra={
                    **self.context,
                    'duration_ms': duration_ms,
                    'exception_type': exc_type.__name__,
                    'exception_message': str(exc_val),
                }
            )
        else:
            # Operation succeeded
            logger.log(
                self.log_level,
                f"Completed: {self.operation} ({duration_ms:.2f}ms)",
                extra={**self.context, 'duration_ms': duration_ms}
            )

        # Never suppress exceptions - let them propagate
        return False


def safe_call(
    func: Callable,
    *args,
    default: Any = None,
    log_errors: bool = True,
    **kwargs
) -> Any:
    """
    Call a function safely, returning a default on any exception.

    This is a functional alternative to the @handle_exceptions decorator
    for one-off calls.

    Args:
        func: Function to call
        *args: Positional arguments for the function
        default: Value to return if function raises exception
        log_errors: Whether to log exceptions (default: True)
        **kwargs: Keyword arguments for the function

    Returns:
        Function result or default value

    Example:
        # Instead of try/except for simple cases
        result = safe_call(parse_json, raw_data, default={})

        # Disable logging for expected failures
        result = safe_call(risky_op, log_errors=False, default=None)
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        if log_errors:
            func_name = getattr(func, '__qualname__', str(func))
            logger.warning(f"safe_call: {func_name} raised {type(e).__name__}: {e}")
        return default


def ensure_not_none(value: Any, name: str, message: Optional[str] = None) -> Any:
    """
    Ensure a value is not None, raising ValueError if it is.

    Args:
        value: Value to check
        name: Name of the value (for error message)
        message: Optional custom error message

    Returns:
        The value if not None

    Raises:
        ValueError: If value is None

    Example:
        config = ensure_not_none(get_config(), "config")
    """
    if value is None:
        if message:
            raise ValueError(message)
        raise ValueError(f"{name} must not be None")
    return value
