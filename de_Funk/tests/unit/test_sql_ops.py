"""Tests for SqlOps (DuckDBSql) — Phase 2."""
import pytest
import pandas as pd
import tempfile
from pathlib import Path


@pytest.fixture
def sql():
    from de_funk.core.sql import DuckDBSql
    import duckdb
    conn = duckdb.connect()
    conn.execute("SET memory_limit='256MB'")
    return DuckDBSql(conn, max_sql_rows=1000, max_dimension_values=500)


@pytest.fixture
def sample_table(tmp_path):
    """Write a parquet table and return path."""
    df = pd.DataFrame({
        "id": [1, 2, 3],
        "name": ["Alice", "Bob", "Charlie"],
        "value": [10.0, 20.0, 30.0],
    })
    path = str(tmp_path / "test_table")
    import os
    os.makedirs(path, exist_ok=True)
    df.to_parquet(f"{path}/data.parquet", index=False)
    return path


class TestDuckDBSqlExecute:
    def test_execute_sql(self, sql):
        result = sql.execute_sql("SELECT 1 AS x, 2 AS y")
        assert len(result) == 1
        assert result[0][0] == 1

    def test_execute_sql_with_limit(self, sql):
        result = sql.execute_sql("SELECT * FROM range(100)", max_rows=10)
        assert len(result) == 10


class TestDuckDBSqlScan:
    def test_scan_parquet(self, sql, sample_table):
        expr = sql.scan(sample_table)
        assert "parquet" in expr or "delta" in expr

    def test_scan_caching(self, sql, sample_table):
        expr1 = sql.scan(sample_table)
        expr2 = sql.scan(sample_table)
        assert expr1 == expr2


class TestDuckDBSqlBuildFrom:
    def test_single_table(self, sql, sample_table):
        result = sql.build_from({"test_table": sample_table})
        assert '"test_table"' in result

    def test_no_tables_raises(self, sql):
        with pytest.raises(ValueError):
            sql.build_from({})

    def test_multiple_tables_cross_join(self, sql, sample_table):
        result = sql.build_from({
            "t1": sample_table,
            "t2": sample_table,
        })
        assert "CROSS JOIN" in result


class TestDuckDBSqlBuildWhere:
    def test_empty_filters(self, sql):
        assert sql.build_where([], resolver=None) == []


class TestDuckDBSqlDistinctValues:
    def test_distinct_values(self, sql, sample_table):
        class MockResolved:
            table_name = "t"
            column = "name"
            silver_path = ""

        mock = MockResolved()
        mock.silver_path = sample_table
        result = sql.distinct_values(mock)
        assert len(result) == 3
        assert "Alice" in result


class TestSparkSqlInterface:
    def test_spark_sql_has_all_methods(self):
        from de_funk.core.sql import SparkSql, SqlOps
        import inspect
        abstract_methods = {name for name, _ in inspect.getmembers(SqlOps)
                           if not name.startswith("_") and callable(getattr(SqlOps, name, None))}
        spark_methods = {name for name, _ in inspect.getmembers(SparkSql)
                        if not name.startswith("_") and callable(getattr(SparkSql, name, None))}
        for method in abstract_methods:
            assert method in spark_methods, f"SparkSql missing method: {method}"
