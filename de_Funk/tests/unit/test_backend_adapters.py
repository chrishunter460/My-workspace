"""
Unit tests for backend adapters.

Tests DuckDB and Spark adapter implementations.
"""

import sys
from pathlib import Path

# Add repository root to Python path
REPO_ROOT = get_repo_root().resolve()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest
import pandas as pd
from de_funk.models.base.backend.duckdb_adapter import DuckDBAdapter
from de_funk.models.base.backend.adapter import QueryResult


class TestDuckDBAdapter:
    """Test DuckDB backend adapter."""

    def test_get_dialect(self, mock_model):
        """Test dialect detection."""
        adapter = DuckDBAdapter(mock_model.connection, mock_model)
        assert adapter.get_dialect() == 'duckdb'

    def test_execute_sql(self, mock_model):
        """Test SQL execution."""
        adapter = DuckDBAdapter(mock_model.connection, mock_model)

        sql = "SELECT COUNT(*) as cnt FROM fact_prices"
        result = adapter.execute_sql(sql)

        assert isinstance(result, QueryResult)
        assert result.backend == 'duckdb'
        assert result.rows > 0
        assert result.query_time_ms > 0
        assert isinstance(result.data, pd.DataFrame)

    def test_get_table_reference_missing_table(self, mock_model):
        """Test error handling for missing table."""
        adapter = DuckDBAdapter(mock_model.connection, mock_model)

        with pytest.raises(ValueError, match="not found in model"):
            adapter.get_table_reference('nonexistent_table')

    def test_supports_feature(self, mock_model):
        """Test feature support checks."""
        adapter = DuckDBAdapter(mock_model.connection, mock_model)

        assert adapter.supports_feature('window_functions') is True
        assert adapter.supports_feature('cte') is True
        assert adapter.supports_feature('qualify') is True
        assert adapter.supports_feature('unknown_feature') is False

    def test_format_limit(self, mock_model):
        """Test LIMIT clause formatting."""
        adapter = DuckDBAdapter(mock_model.connection, mock_model)
        assert adapter.format_limit(10) == "LIMIT 10"

    def test_format_date_literal(self, mock_model):
        """Test date literal formatting."""
        adapter = DuckDBAdapter(mock_model.connection, mock_model)
        assert adapter.format_date_literal('2024-01-01') == "DATE '2024-01-01'"

    def test_get_null_safe_divide(self, mock_model):
        """Test null-safe division."""
        adapter = DuckDBAdapter(mock_model.connection, mock_model)
        result = adapter.get_null_safe_divide('a', 'b')
        assert result == 'a / NULLIF(b, 0)'


class TestSQLBuilder:
    """Test SQL builder utilities."""

    def test_build_simple_aggregate(self, mock_model):
        """Test simple aggregation SQL generation."""
from de_funk.models.base.backend.sql_builder import SQLBuilder
from de_funk.models.base.backend.duckdb_adapter import DuckDBAdapter

        adapter = DuckDBAdapter(mock_model.connection, mock_model)
        builder = SQLBuilder(adapter)

        sql = builder.build_simple_aggregate(
            table_name='fact_prices',
            value_column='close',
            agg_function='AVG',
            group_by=['ticker'],
            limit=10
        )

        assert 'AVG(close)' in sql
        assert 'GROUP BY ticker' in sql
        assert 'LIMIT 10' in sql
        assert 'WHERE close IS NOT NULL' in sql

    def test_build_weighted_aggregate(self, mock_model):
        """Test weighted aggregation SQL generation."""
from de_funk.models.base.backend.sql_builder import SQLBuilder
from de_funk.models.base.backend.duckdb_adapter import DuckDBAdapter

        adapter = DuckDBAdapter(mock_model.connection, mock_model)
        builder = SQLBuilder(adapter)

        sql = builder.build_weighted_aggregate(
            table_name='fact_prices',
            value_column='close',
            weight_expression='volume',
            group_by=['trade_date']
        )

        assert 'SUM(close * volume)' in sql
        assert 'NULLIF(SUM(volume), 0)' in sql
        assert 'GROUP BY trade_date' in sql
        assert 'WHERE close IS NOT NULL' in sql
        assert 'volume > 0' in sql

    def test_build_cte_query(self, mock_model):
        """Test CTE query building."""
from de_funk.models.base.backend.sql_builder import SQLBuilder
from de_funk.models.base.backend.duckdb_adapter import DuckDBAdapter

        adapter = DuckDBAdapter(mock_model.connection, mock_model)
        builder = SQLBuilder(adapter)

        ctes = {
            'avg_prices': 'SELECT ticker, AVG(close) as avg_close FROM fact_prices GROUP BY ticker',
            'max_prices': 'SELECT ticker, MAX(close) as max_close FROM fact_prices GROUP BY ticker'
        }

        main_query = 'SELECT * FROM avg_prices JOIN max_prices USING (ticker)'

        sql = builder.build_cte_query(ctes, main_query)

        assert 'WITH' in sql
        assert 'avg_prices AS' in sql
        assert 'max_prices AS' in sql
        assert main_query in sql
