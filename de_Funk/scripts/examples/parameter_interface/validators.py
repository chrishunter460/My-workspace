"""
Parameter validation module.

Provides validation functions for calculation parameters.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime


class ParameterError(Exception):
    """Exception raised for invalid parameters."""
    pass


def validate_date(date_str: str, param_name: str) -> None:
    """
    Validate a date string.

    Args:
        date_str: Date string in YYYY-MM-DD format
        param_name: Name of the parameter (for error messages)

    Raises:
        ParameterError: If date is invalid
    """
    if not date_str:
        return

    try:
        datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        raise ParameterError(
            f"Invalid {param_name}: '{date_str}'. "
            f"Expected format: YYYY-MM-DD"
        )


def validate_tickers(tickers: Any) -> None:
    """
    Validate ticker list.

    Args:
        tickers: Ticker list or single ticker

    Raises:
        ParameterError: If tickers are invalid
    """
    if tickers is None:
        return

    if isinstance(tickers, str):
        if not tickers.strip():
            raise ParameterError("Ticker cannot be empty string")
        return

    if not isinstance(tickers, list):
        raise ParameterError(
            f"Tickers must be a list or string, got: {type(tickers).__name__}"
        )

    if not tickers:
        raise ParameterError("Ticker list cannot be empty")

    if not all(isinstance(t, str) for t in tickers):
        raise ParameterError("All tickers must be strings")


def validate_backend(backend: str) -> None:
    """
    Validate backend parameter.

    Args:
        backend: Backend name

    Raises:
        ParameterError: If backend is invalid
    """
    valid_backends = ['duckdb', 'spark']
    if backend not in valid_backends:
        raise ParameterError(
            f"Invalid backend: '{backend}'. "
            f"Valid options: {', '.join(valid_backends)}"
        )


def validate_limit(limit: Any) -> None:
    """
    Validate limit parameter.

    Args:
        limit: Limit value

    Raises:
        ParameterError: If limit is invalid
    """
    if limit is None:
        return

    if not isinstance(limit, int):
        raise ParameterError(
            f"Limit must be an integer, got: {type(limit).__name__}"
        )

    if limit <= 0:
        raise ParameterError(f"Limit must be positive, got: {limit}")


def validate_params(params: Dict[str, Any]) -> None:
    """
    Validate calculation parameters.

    Args:
        params: Parameter dictionary

    Raises:
        ParameterError: If any parameter is invalid

    Example:
        try:
            validate_params({
                'model': 'equity',
                'measure': 'avg_close_price',
                'tickers': ['AAPL', 'MSFT'],
                'start_date': '2024-01-01',
                'end_date': '2024-12-31',
                'backend': 'duckdb',
                'limit': 10
            })
        except ParameterError as e:
            print(f"Validation error: {e}")
    """
    # Required parameters
    if 'model' not in params:
        raise ParameterError("Missing required parameter: 'model'")

    if 'measure' not in params:
        raise ParameterError("Missing required parameter: 'measure'")

    # Validate model name
    if not isinstance(params['model'], str) or not params['model'].strip():
        raise ParameterError("Model must be a non-empty string")

    # Validate measure name
    if not isinstance(params['measure'], str) or not params['measure'].strip():
        raise ParameterError("Measure must be a non-empty string")

    # Validate optional parameters
    if 'start_date' in params:
        validate_date(params['start_date'], 'start_date')

    if 'end_date' in params:
        validate_date(params['end_date'], 'end_date')

    # Validate date range
    if 'start_date' in params and 'end_date' in params:
        start = datetime.strptime(params['start_date'], '%Y-%m-%d')
        end = datetime.strptime(params['end_date'], '%Y-%m-%d')
        if start > end:
            raise ParameterError(
                f"start_date ({params['start_date']}) must be before "
                f"end_date ({params['end_date']})"
            )

    if 'tickers' in params:
        validate_tickers(params['tickers'])

    if 'backend' in params:
        validate_backend(params['backend'])

    if 'limit' in params:
        validate_limit(params['limit'])

    if 'entity_column' in params:
        if not isinstance(params['entity_column'], str):
            raise ParameterError(
                f"entity_column must be a string, got: {type(params['entity_column']).__name__}"
            )


def get_validation_hints(param_name: str) -> str:
    """
    Get helpful hints for a parameter.

    Args:
        param_name: Name of the parameter

    Returns:
        String with validation hints

    Example:
        print(get_validation_hints('start_date'))
        # Output: "Date string in YYYY-MM-DD format (e.g., '2024-01-01')"
    """
    hints = {
        'model': "Model name (e.g., 'equity', 'corporate', 'macro')",
        'measure': "Measure name (e.g., 'avg_close_price', 'volume_weighted_index')",
        'tickers': "List of ticker symbols (e.g., ['AAPL', 'MSFT']) or single ticker string",
        'start_date': "Date string in YYYY-MM-DD format (e.g., '2024-01-01')",
        'end_date': "Date string in YYYY-MM-DD format (e.g., '2024-12-31')",
        'entity_column': "Column name for grouping (e.g., 'ticker', 'date')",
        'limit': "Positive integer for limiting results (e.g., 10, 100)",
        'backend': "Backend name: 'duckdb' (fast, recommended) or 'spark' (distributed)",
        'additional_filters': "Dictionary of additional filter parameters",
    }

    return hints.get(param_name, f"No hints available for '{param_name}'")


def suggest_fixes(error: ParameterError) -> List[str]:
    """
    Suggest fixes for a parameter error.

    Args:
        error: ParameterError exception

    Returns:
        List of suggested fixes

    Example:
        try:
            validate_params(params)
        except ParameterError as e:
            for fix in suggest_fixes(e):
                print(f"  - {fix}")
    """
    error_msg = str(error).lower()
    suggestions = []

    if 'missing required parameter' in error_msg:
        if "'model'" in error_msg:
            suggestions.append("Add 'model' parameter (e.g., 'equity', 'corporate', 'macro')")
        if "'measure'" in error_msg:
            suggestions.append("Add 'measure' parameter (e.g., 'avg_close_price')")

    elif 'invalid' in error_msg and 'date' in error_msg:
        suggestions.append("Use YYYY-MM-DD format for dates (e.g., '2024-01-01')")
        suggestions.append("Check that the date is valid (e.g., no month 13 or day 32)")

    elif 'ticker' in error_msg:
        suggestions.append("Provide tickers as a list: ['AAPL', 'MSFT']")
        suggestions.append("Or as a single string: 'AAPL'")
        suggestions.append("Ensure ticker symbols are valid")

    elif 'backend' in error_msg:
        suggestions.append("Use 'duckdb' for fast queries (recommended)")
        suggestions.append("Use 'spark' for distributed processing")

    elif 'limit' in error_msg:
        suggestions.append("Ensure limit is a positive integer")
        suggestions.append("Example: limit=10")

    elif 'start_date' in error_msg and 'end_date' in error_msg:
        suggestions.append("Ensure start_date is before end_date")

    else:
        suggestions.append("Check parameter format and try again")
        suggestions.append("Use get_validation_hints(param_name) for parameter help")

    return suggestions
