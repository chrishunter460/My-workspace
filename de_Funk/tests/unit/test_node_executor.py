"""Tests for NodeExecutor — Phase 6."""
import pytest
import pandas as pd
from de_funk.core.executor import NodeExecutor
from de_funk.core.sessions import BuildSession


@pytest.fixture
def session():
    from de_funk.core.engine import Engine
    engine = Engine.for_duckdb(
        storage_config={"roots": {"bronze": "/bronze", "silver": "/silver"}},
        memory_limit="256MB",
    )
    return BuildSession(engine=engine, models={}, storage_config={
        "roots": {"bronze": "/bronze", "silver": "/silver"},
    })


@pytest.fixture
def executor(session):
    return NodeExecutor(session)


@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "id": [1, 2, 3, 3],
        "name": ["Alice", "Bob", "Charlie", "Charlie"],
        "value": [10.0, 20.0, 30.0, 30.0],
        "category": ["A", "B", "A", "A"],
    })


class TestOpRegistry:
    def test_builtins_registered(self, executor):
        ops = executor.list_ops()
        assert "filter" in ops
        assert "join" in ops
        assert "select" in ops
        assert "derive" in ops
        assert "dedup" in ops
        assert "drop" in ops
        assert "hook" in ops
        assert "enrich" in ops
        assert "window" in ops
        assert "unpivot" in ops
        assert "pivot" in ops
        assert "aggregate" in ops

    def test_register_custom_op(self, executor):
        def my_op(df, step):
            return df
        executor.register_op("my_custom", my_op)
        assert executor.get_op("my_custom") is my_op
        assert "my_custom" in executor.list_ops()

    def test_get_unknown_op(self, executor):
        assert executor.get_op("nonexistent") is None


class TestOpFilter:
    def test_filter(self, executor, sample_df):
        result = executor._op_filter(sample_df, {"conditions": ["value > 15"]})
        assert len(result) == 3

    def test_filter_no_conditions(self, executor, sample_df):
        result = executor._op_filter(sample_df, {})
        assert len(result) == 4


class TestOpSelect:
    def test_select(self, executor, sample_df):
        result = executor._op_select(sample_df, {"columns": ["id", "name"]})
        assert list(result.columns) == ["id", "name"]


class TestOpDerive:
    def test_derive(self, executor, sample_df):
        result = executor._op_derive(sample_df, {
            "expressions": {"doubled": "value * 2"}
        })
        assert "doubled" in result.columns


class TestOpDedup:
    def test_dedup(self, executor, sample_df):
        result = executor._op_dedup(sample_df, {"keys": ["name"]})
        assert len(result) == 3


class TestOpDrop:
    def test_drop(self, executor, sample_df):
        result = executor._op_drop(sample_df, {"columns": ["value"]})
        assert "value" not in result.columns


class TestOpHook:
    def test_hook_missing_fn(self, executor, sample_df):
        result = executor._op_hook(sample_df, {})
        assert len(result) == 4  # returns df unchanged


class TestExecutePipeline:
    def test_single_step(self, executor, sample_df):
        result = executor.execute_pipeline(sample_df, [
            {"op": "filter", "conditions": ["value > 15"]}
        ])
        assert len(result) == 3

    def test_multi_step(self, executor, sample_df):
        result = executor.execute_pipeline(sample_df, [
            {"op": "filter", "conditions": ["value > 15"]},
            {"op": "dedup", "keys": ["name"]},
        ])
        assert len(result) == 2  # Bob and Charlie

    def test_unknown_op_skipped(self, executor, sample_df):
        result = executor.execute_pipeline(sample_df, [
            {"op": "nonexistent_op"},
        ])
        assert len(result) == 4  # unchanged


class TestExecuteNode:
    def test_seed_node(self, executor):
        result = executor.execute_node("test_seed", {
            "type": "seed",
            "data": [[1, "a"], [2, "b"]],
            "schema": [("id", "int"), ("code", "string")],
        }, {})
        assert len(result) == 2

    def test_node_from_built(self, executor, sample_df):
        built = {"source_node": sample_df}
        result = executor.execute_node("derived", {
            "from": "source_node",
            "pipeline": [{"op": "filter", "conditions": ["value > 15"]}],
        }, built)
        assert len(result) == 3

    def test_union_node(self, executor):
        df1 = pd.DataFrame({"x": [1, 2]})
        df2 = pd.DataFrame({"x": [3, 4]})
        built = {"a": df1, "b": df2}
        result = executor.execute_node("combined", {
            "type": "union",
            "sources": ["a", "b"],
        }, built)
        assert len(result) == 4


class TestExecuteAll:
    def test_execute_all(self, executor):
        nodes = {
            "seed_data": {
                "type": "seed",
                "data": [[1, "a"], [2, "b"], [3, "c"]],
                "schema": [("id", "int"), ("code", "string")],
            },
            "filtered": {
                "from": "seed_data",
                "pipeline": [{"op": "select", "columns": ["id"]}],
            },
        }
        results = executor.execute_all(nodes)
        assert "seed_data" in results
        assert "filtered" in results
        assert len(results["seed_data"]) == 3
        assert list(results["filtered"].columns) == ["id"]
