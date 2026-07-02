"""Tests for Engine — Phase 3."""
import pytest
import pandas as pd


@pytest.fixture
def engine():
    from de_funk.core.engine import Engine
    return Engine.for_duckdb(memory_limit="256MB")


@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "id": [1, 2, 3],
        "name": ["Alice", "Bob", "Charlie"],
        "value": [10.0, 20.0, 30.0],
    })


class TestEngineCreation:
    def test_for_duckdb(self, engine):
        assert engine.backend == "duckdb"
        assert engine._ops is not None
        assert engine._sql is not None

    def test_for_duckdb_has_ops(self, engine):
        from de_funk.core.ops import DuckDBOps
        from de_funk.core.sql import DuckDBSql
        assert isinstance(engine._ops, DuckDBOps)
        assert isinstance(engine._sql, DuckDBSql)

    def test_repr(self, engine):
        assert "duckdb" in repr(engine)


class TestEngineDelegatesDataOps:
    def test_read_write(self, engine, sample_df, tmp_path):
        path = str(tmp_path / "test")
        engine.write(sample_df, path)
        result = engine.read(path, format="parquet")
        assert len(result) == 3

    def test_create_df(self, engine):
        df = engine.create_df([[1, "a"]], [("id", "int"), ("code", "string")])
        assert len(df) == 1

    def test_select(self, engine, sample_df):
        result = engine.select(sample_df, ["id", "name"])
        assert list(result.columns) == ["id", "name"]

    def test_drop(self, engine, sample_df):
        result = engine.drop(sample_df, ["value"])
        assert "value" not in result.columns

    def test_derive(self, engine, sample_df):
        result = engine.derive(sample_df, "doubled", "value * 2")
        assert "doubled" in result.columns

    def test_filter(self, engine, sample_df):
        result = engine.filter(sample_df, ["value > 15"])
        assert len(result) == 2

    def test_dedup(self, engine, sample_df):
        df = pd.concat([sample_df, sample_df])
        result = engine.dedup(df, ["id"])
        assert len(result) == 3

    def test_join(self, engine, sample_df):
        right = pd.DataFrame({"id": [1, 2], "grade": ["A", "B"]})
        result = engine.join(sample_df, right, on=["id"])
        assert len(result) == 2
        assert "grade" in result.columns

    def test_union(self, engine, sample_df):
        result = engine.union([sample_df, sample_df])
        assert len(result) == 6

    def test_count(self, engine, sample_df):
        assert engine.count(sample_df) == 3

    def test_to_pandas(self, engine, sample_df):
        result = engine.to_pandas(sample_df)
        assert isinstance(result, pd.DataFrame)

    def test_columns(self, engine, sample_df):
        assert engine.columns(sample_df) == ["id", "name", "value"]


class TestEngineDelegatesSqlOps:
    def test_execute_sql(self, engine):
        result = engine.execute_sql("SELECT 42 AS answer")
        assert result[0][0] == 42

    def test_scan(self, engine, tmp_path):
        path = str(tmp_path / "scan_test")
        import os
        os.makedirs(path)
        pd.DataFrame({"x": [1]}).to_parquet(f"{path}/data.parquet")
        expr = engine.scan(path)
        assert "parquet" in expr or "delta" in expr

    def test_build_from_single(self, engine, tmp_path):
        path = str(tmp_path / "from_test")
        import os
        os.makedirs(path)
        pd.DataFrame({"x": [1]}).to_parquet(f"{path}/data.parquet")
        result = engine.build_from({"t": path})
        assert '"t"' in result


class TestEngineBackwardCompat:
    def test_get_query_engine_exists(self, engine):
        # Should not crash — returns None or QueryEngine
        qe = engine.get_query_engine()
        # It creates a new QueryEngine (separate connection)
        assert qe is not None
