"""
Centralized filter engine for applying filters across different backends.

This module provides a unified interface for filter application that works
with both Spark and DuckDB backends, eliminating code duplication across
the codebase.
"""

from typing import Dict, Any, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from pyspark.sql import DataFrame as SparkDataFrame
    from pyspark.sql import functions as F
else:
    try:
        from pyspark.sql import DataFrame as SparkDataFrame, functions as F
    except ImportError:
        SparkDataFrame = None
        F = None


class FilterEngine:
    """
    Centralized filter application for all backends.

    Consolidates filter logic that was previously duplicated in:
    - models/base/service.py (BaseAPI._apply_filters)
    - app/notebook/api/notebook_session.py (_build_filters)
    - app/services/storage_service.py (filter application)

    Usage:
        # Detect backend and apply filters
        backend = session.backend  # 'spark' or 'duckdb'
        filtered_df = FilterEngine.apply_filters(df, filters, backend)

        # Or use with UniversalSession directly
        filtered_df = FilterEngine.apply_from_session(df, filters, session)
    """

    @staticmethod
    def _convert_date_to_date_id(date_str: str) -> int | None:
        """
        Convert a date string to date_id integer format (YYYYMMDD).

        Args:
            date_str: Date string in various formats (YYYY-MM-DD, YYYY/MM/DD, etc.)

        Returns:
            Integer date_id (e.g., 20260120) or None if conversion fails
        """
        import re
        # Try to extract YYYY, MM, DD from common date formats
        match = re.match(r'(\d{4})[-/]?(\d{2})[-/]?(\d{2})', str(date_str))
        if match:
            year, month, day = match.groups()
            return int(f"{year}{month}{day}")
        return None

    @staticmethod
    def _format_sql_value(value: Any) -> str:
        """
        Format a value for SQL, quoting strings but NOT numbers.

        Args:
            value: Value to format

        Returns:
            SQL-safe string representation

        Examples:
            >>> FilterEngine._format_sql_value(1000000)
            '1000000'
            >>> FilterEngine._format_sql_value('AAPL')
            "'AAPL'"
            >>> FilterEngine._format_sql_value('2024-01-01')
            "'2024-01-01'"
        """
        if value is None:
            return 'NULL'
        elif isinstance(value, bool):
            return 'TRUE' if value else 'FALSE'
        elif isinstance(value, (int, float)):
            return str(value)
        else:
            # Strings, dates, and everything else gets quoted
            # Escape single quotes in the value
            escaped = str(value).replace("'", "''")
            return f"'{escaped}'"

    @staticmethod
    def apply_filters(
        df: Any,
        filters: Dict[str, Any],
        backend: str
    ) -> Any:
        """
        Apply filters based on backend type.

        Args:
            df: DataFrame (SparkDataFrame or DuckDB relation)
            filters: Filter specifications mapping column names to filter values
            backend: Backend type ('spark' or 'duckdb')

        Returns:
            Filtered DataFrame

        Raises:
            ValueError: If backend is unknown

        Filter Specification Format:
            {
                'column_name': value,              # Exact match
                'column_name': [val1, val2],       # IN clause
                'column_name': {                   # Range filter
                    'min': value,
                    'max': value,
                    'operator': 'gte' | 'lte' | 'gt' | 'lt'
                }
            }

        Examples:
            # Exact match
            filters = {'ticker': 'AAPL'}

            # IN clause
            filters = {'ticker': ['AAPL', 'GOOGL', 'MSFT']}

            # Range filter
            filters = {
                'trade_date': {
                    'min': '2024-01-01',
                    'max': '2024-12-31'
                }
            }

            # Combined filters
            filters = {
                'ticker': ['AAPL', 'GOOGL'],
                'trade_date': {'min': '2024-01-01'},
                'volume': {'min': 1000000}
            }
        """
        if backend == 'spark':
            if F is None:
                raise RuntimeError("PySpark is required for Spark backend but not installed")
            return FilterEngine._apply_spark_filters(df, filters)
        elif backend == 'duckdb':
            return FilterEngine._apply_duckdb_filters(df, filters)
        else:
            raise ValueError(f"Unknown backend: {backend}")

    @staticmethod
    def apply_from_session(df: Any, filters: Dict[str, Any], session) -> Any:
        """
        Apply filters using session's backend detection.

        Convenience method that automatically detects backend from session.

        Args:
            df: DataFrame
            filters: Filter specifications
            session: Session instance with backend property

        Returns:
            Filtered DataFrame
        """
        backend = session.backend
        return FilterEngine.apply_filters(df, filters, backend)

    @staticmethod
    def _apply_spark_filters(df: SparkDataFrame, filters: Dict[str, Any]) -> SparkDataFrame:
        """
        Apply filters to Spark DataFrame.

        Args:
            df: Spark DataFrame
            filters: Filter specifications

        Returns:
            Filtered Spark DataFrame
        """
        for col_name, value in filters.items():
            if isinstance(value, dict):
                # Range filter
                if 'min' in value:
                    df = df.filter(F.col(col_name) >= value['min'])
                if 'max' in value:
                    df = df.filter(F.col(col_name) <= value['max'])
                if 'gt' in value:
                    df = df.filter(F.col(col_name) > value['gt'])
                if 'lt' in value:
                    df = df.filter(F.col(col_name) < value['lt'])
                if 'gte' in value:
                    df = df.filter(F.col(col_name) >= value['gte'])
                if 'lte' in value:
                    df = df.filter(F.col(col_name) <= value['lte'])

            elif isinstance(value, list):
                # IN filter
                if value:  # Only apply if list is not empty
                    df = df.filter(F.col(col_name).isin(value))

            elif value is not None:
                # Exact match (ignore None values)
                df = df.filter(F.col(col_name) == value)

        return df

    @staticmethod
    def _apply_duckdb_filters(df: Any, filters: Dict[str, Any]) -> Any:
        """
        Apply filters to DuckDB relation or pandas DataFrame.

        Handles both DuckDB relations (SQL-style) and pandas DataFrames
        (already converted from DuckDB).

        Args:
            df: DuckDB relation
            filters: Filter specifications

        Returns:
            Filtered DuckDB relation
        """
        # Get available columns to skip filters for non-existent columns
        try:
            available_columns = set(df.columns)
        except Exception:
            available_columns = None

        conditions = []

        # Check for period overlap case (company model tables with fiscal periods)
        has_period_columns = (
            available_columns is not None and
            'period_start_date_id' in available_columns and
            'period_end_date_id' in available_columns
        )

        for col_name, value in filters.items():
            # Handle period overlap for date filters on tables with period columns
            # When filtering on 'date' but table has period_start/end_date_id columns,
            # we need: period_start_date_id <= end AND period_end_date_id >= start
            if col_name == 'date' and has_period_columns and isinstance(value, dict):
                if 'start' in value and 'end' in value:
                    start_int = FilterEngine._convert_date_to_date_id(value['start'])
                    end_int = FilterEngine._convert_date_to_date_id(value['end'])
                    if start_int and end_int:
                        # Period overlap logic: fiscal period overlaps with filter range
                        # A period overlaps when: period_start <= filter_end AND period_end >= filter_start
                        conditions.append(f"period_start_date_id <= {end_int}")
                        conditions.append(f"period_end_date_id >= {start_int}")
                    continue
                elif 'start' in value:
                    start_int = FilterEngine._convert_date_to_date_id(value['start'])
                    if start_int:
                        conditions.append(f"period_end_date_id >= {start_int}")
                    continue
                elif 'end' in value:
                    end_int = FilterEngine._convert_date_to_date_id(value['end'])
                    if end_int:
                        conditions.append(f"period_start_date_id <= {end_int}")
                    continue

            # Translate 'date' filter to 'date_id' if table has date_id but not date
            # This allows notebooks to use human-friendly 'date' filters that work
            # with star schema tables using integer date_id (YYYYMMDD format)
            if col_name == 'date' and available_columns is not None:
                if 'date' not in available_columns and 'date_id' in available_columns:
                    col_name = 'date_id'

            # Skip filter if column doesn't exist in this table
            if available_columns is not None and col_name not in available_columns:
                continue

            # Check if this is a date_id column (integer YYYYMMDD format)
            is_date_id_col = col_name == 'date_id'

            if isinstance(value, dict):
                # Range filter - support both min/max AND start/end formats
                # Date ranges use start/end, numeric ranges use min/max
                if 'start' in value and 'end' in value:
                    if is_date_id_col:
                        # Convert date strings to integers for date_id column
                        start_int = FilterEngine._convert_date_to_date_id(value['start'])
                        end_int = FilterEngine._convert_date_to_date_id(value['end'])
                        if start_int and end_int:
                            conditions.append(f"{col_name} >= {start_int}")
                            conditions.append(f"{col_name} <= {end_int}")
                    else:
                        # Date range format - quote dates as strings
                        conditions.append(f"{col_name} >= '{value['start']}'")
                        conditions.append(f"{col_name} <= '{value['end']}'")
                elif 'min' in value:
                    # Use _format_sql_value to handle numeric vs string values
                    conditions.append(f"{col_name} >= {FilterEngine._format_sql_value(value['min'])}")
                if 'max' in value:
                    conditions.append(f"{col_name} <= {FilterEngine._format_sql_value(value['max'])}")
                if 'gt' in value:
                    conditions.append(f"{col_name} > {FilterEngine._format_sql_value(value['gt'])}")
                if 'lt' in value:
                    conditions.append(f"{col_name} < {FilterEngine._format_sql_value(value['lt'])}")
                if 'gte' in value:
                    conditions.append(f"{col_name} >= {FilterEngine._format_sql_value(value['gte'])}")
                if 'lte' in value:
                    conditions.append(f"{col_name} <= {FilterEngine._format_sql_value(value['lte'])}")

            elif isinstance(value, list):
                # IN filter
                if value:
                    formatted_values = ", ".join(FilterEngine._format_sql_value(v) for v in value)
                    conditions.append(f"{col_name} IN ({formatted_values})")

            elif value is not None:
                # Exact match (ignore None values)
                conditions.append(f"{col_name} = {FilterEngine._format_sql_value(value)}")

        # Apply SQL conditions to DuckDB relation
        if conditions:
            where_clause = " AND ".join(conditions)
            df = df.filter(where_clause)

        return df

    @staticmethod
    def build_filter_sql(filters: Dict[str, Any]) -> str:
        """
        Build SQL WHERE clause from filter specifications.

        Useful for generating SQL queries with filters.

        Args:
            filters: Filter specifications

        Returns:
            SQL WHERE clause (without 'WHERE' keyword)

        Example:
            >>> filters = {'ticker': ['AAPL', 'GOOGL'], 'volume': {'min': 1000000}}
            >>> FilterEngine.build_filter_sql(filters)
            "ticker IN ('AAPL', 'GOOGL') AND volume >= 1000000"
        """
        conditions = []

        for col_name, value in filters.items():
            if isinstance(value, dict):
                # Range filter - support both min/max AND start/end formats
                # Date ranges use start/end, numeric ranges use min/max
                if 'start' in value and 'end' in value:
                    # Date range format - always quote dates
                    conditions.append(f"{col_name} >= '{value['start']}'")
                    conditions.append(f"{col_name} <= '{value['end']}'")
                elif 'min' in value:
                    # Use _format_sql_value to handle numeric vs string values
                    conditions.append(f"{col_name} >= {FilterEngine._format_sql_value(value['min'])}")
                if 'max' in value:
                    conditions.append(f"{col_name} <= {FilterEngine._format_sql_value(value['max'])}")
                if 'gt' in value:
                    conditions.append(f"{col_name} > {FilterEngine._format_sql_value(value['gt'])}")
                if 'lt' in value:
                    conditions.append(f"{col_name} < {FilterEngine._format_sql_value(value['lt'])}")
                if 'gte' in value:
                    conditions.append(f"{col_name} >= {FilterEngine._format_sql_value(value['gte'])}")
                if 'lte' in value:
                    conditions.append(f"{col_name} <= {FilterEngine._format_sql_value(value['lte'])}")

            elif isinstance(value, list):
                # IN filter with proper value formatting
                if value:
                    formatted_values = ", ".join(FilterEngine._format_sql_value(v) for v in value)
                    conditions.append(f"{col_name} IN ({formatted_values})")

            elif value is not None:
                # Exact match
                conditions.append(f"{col_name} = {FilterEngine._format_sql_value(value)}")

        return " AND ".join(conditions) if conditions else "1=1"
