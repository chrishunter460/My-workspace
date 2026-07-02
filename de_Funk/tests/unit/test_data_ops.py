"""Tests for DataOps (DuckDBOps) and SqlOps (DuckDBSql) — Phase 2."""
import pytest
import pandas as pd


@pytest.fixture
def ops():
    from de_funk.core.ops import DuckDBOps
    return DuckDBOps(memory_limit="256MB")


@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "id": [1, 2, 3, 3],
        "name": ["Alice", "Bob", "Charlie", "Charlie"],
        "value": [10.0, 20.0, 30.0, 30.0],
        "group": ["A", "B", "A", "A"],
    })


@pytest.fixture
def second_df():
    return pd.DataFrame({
        "id": [1, 2, 4],
        "category": ["X", "Y", "Z"],
    })


class TestDuckDBOpsReadWrite:
    def test_write_and_read(self, ops, sample_df, tmp_path):
        path = str(tmp_path / "test_table")
        ops.write(sample_df, path)
        result = ops.read(path, format="parquet")
        assert len(result) == 4
        assert "name" in result.columns

    def test_create_df(self, ops):
        df = ops.create_df(
            [[1, "a"], [2, "b"]],
            [("id", "int"), ("code", "string")],
        )
        assert len(df) == 2
        assert list(df.columns) == ["id", "code"]


class TestDuckDBOpsColumnOps:
    def test_select(self, ops, sample_df):
        result = ops.select(sample_df, ["id", "name"])
        assert list(result.columns) == ["id", "name"]

    def test_drop(self, ops, sample_df):
        result = ops.drop(sample_df, ["value"])
        assert "value" not in result.columns
        assert "id" in result.columns

    def test_derive(self, ops, sample_df):
        result = ops.derive(sample_df, "doubled", "value * 2")
        assert "doubled" in result.columns
        assert result["doubled"].iloc[0] == 20.0


class TestDuckDBOpsRowOps:
    def test_filter(self, ops, sample_df):
        result = ops.filter(sample_df, ["value > 15"])
        assert len(result) == 3  # Bob=20, Charlie=30, Charlie=30

    def test_dedup(self, ops, sample_df):
        result = ops.dedup(sample_df, ["name"])
        assert len(result) == 3  # Alice, Bob, Charlie


class TestDuckDBOpsCombineOps:
    def test_join(self, ops, sample_df, second_df):
        result = ops.join(sample_df, second_df, on=["id"], how="inner")
        assert "category" in result.columns
        assert len(result) == 2  # inner: ids 1 and 2 match

    def test_union(self, ops, sample_df):
        df2 = pd.DataFrame({"id": [5], "name": ["Eve"], "value": [50.0], "group": ["B"]})
        result = ops.union([sample_df, df2])
        assert len(result) == 5

    def test_unpivot(self, ops):
        df = pd.DataFrame({"id": [1, 2], "q1": [10, 20], "q2": [30, 40]})
        result = ops.unpivot(df, id_cols=["id"], value_cols=["q1", "q2"],
                             var_name="quarter", val_name="amount")
        assert len(result) == 4
        assert "quarter" in result.columns


class TestDuckDBOpsWindowOps:
    def test_window(self, ops, sample_df):
        result = ops.window(sample_df, partition=["group"], order=["id"],
                            expr="ROW_NUMBER()", alias="rn")
        assert "rn" in result.columns
        assert len(result) == 4


class TestDuckDBOpsAnalyticalOps:
    def test_pivot(self, ops, sample_df):
        result = ops.pivot(sample_df, rows=["group"], cols=[],
                           measures=[{"aggregation": "SUM", "field": "value", "name": "total"}])
        assert "total" in result.columns

    def test_aggregate(self, ops, sample_df):
        result = ops.aggregate(sample_df, group_by=["group"],
                               aggs=[{"func": "SUM", "col": "value", "alias": "total"}])
        assert len(result) == 2  # groups A and B
        assert "total" in result.columns


class TestDuckDBOpsInspection:
    def test_count(self, ops, sample_df):
        assert ops.count(sample_df) == 4

    def test_to_pandas(self, ops, sample_df):
        result = ops.to_pandas(sample_df)
        assert isinstance(result, pd.DataFrame)

    def test_columns(self, ops, sample_df):
        assert ops.columns(sample_df) == ["id", "name", "value", "group"]


class TestSparkOpsInterface:
    def test_spark_ops_has_all_methods(self):
        from de_funk.core.ops import SparkOps, DataOps
        import inspect
        abstract_methods = {name for name, _ in inspect.getmembers(DataOps)
                           if not name.startswith("_") and callable(getattr(DataOps, name, None))}
        spark_methods = {name for name, _ in inspect.getmembers(SparkOps)
                        if not name.startswith("_") and callable(getattr(SparkOps, name, None))}
        for method in abstract_methods:
            assert method in spark_methods, f"SparkOps missing method: {method}"
