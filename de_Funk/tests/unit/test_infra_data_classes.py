"""Tests for infrastructure data classes — Phase 1."""
import pytest
from de_funk.config.data_classes import (
    RootsConfig, ApiLimits, TablePath,
    ClusterConfig, RetryConfig, RunConfig,
)


class TestRootsConfig:
    def test_defaults(self):
        r = RootsConfig()
        assert r.raw == "storage/raw"
        assert r.bronze == "storage/bronze"
        assert r.silver == "storage/silver"
        assert r.models == "storage/models"

    def test_from_dict(self):
        r = RootsConfig.from_dict({
            "raw": "/mnt/raw",
            "bronze": "/shared/bronze",
            "silver": "/shared/silver",
            "models": "/shared/models",
        })
        assert r.raw == "/mnt/raw"
        assert r.silver == "/shared/silver"

    def test_from_dict_partial(self):
        r = RootsConfig.from_dict({"bronze": "/custom/bronze"})
        assert r.bronze == "/custom/bronze"
        assert r.silver == "storage/silver"


class TestApiLimits:
    def test_defaults(self):
        a = ApiLimits()
        assert a.duckdb_memory_limit == "3GB"
        assert a.max_sql_rows == 30000
        assert a.max_dimension_values == 10000
        assert a.max_response_mb == 4.0

    def test_from_dict(self):
        a = ApiLimits.from_dict({
            "duckdb_memory_limit": "8GB",
            "max_sql_rows": 50000,
        })
        assert a.duckdb_memory_limit == "8GB"
        assert a.max_sql_rows == 50000
        assert a.max_dimension_values == 10000  # default


class TestTablePath:
    def test_full_path(self):
        t = TablePath(root="silver", rel="temporal/dims/dim_calendar")
        assert t.full_path == "silver/temporal/dims/dim_calendar"

    def test_from_dict(self):
        t = TablePath.from_dict({"root": "bronze", "rel": "seeds/calendar", "partitions": []})
        assert t.root == "bronze"
        assert t.rel == "seeds/calendar"
        assert t.partitions == []

    def test_empty_rel(self):
        t = TablePath(root="silver")
        assert t.full_path == "silver"


class TestClusterConfig:
    def test_defaults(self):
        c = ClusterConfig()
        assert c.spark_master == "auto"
        assert c.fallback_to_local is True
        assert c.task_batch_size == 50

    def test_from_dict(self):
        c = ClusterConfig.from_dict({"spark_master": "spark://host:7077", "fallback_to_local": False})
        assert c.spark_master == "spark://host:7077"
        assert c.fallback_to_local is False


class TestRetryConfig:
    def test_defaults(self):
        r = RetryConfig()
        assert r.max_retries == 3
        assert r.retry_delay_seconds == 2.0
        assert r.exponential_backoff is True

    def test_from_dict(self):
        r = RetryConfig.from_dict({"max_retries": 5, "exponential_backoff": False})
        assert r.max_retries == 5
        assert r.exponential_backoff is False


class TestRunConfig:
    def test_composes_cluster_retry(self):
        rc = RunConfig(
            cluster=ClusterConfig(spark_master="local"),
            retry=RetryConfig(max_retries=1),
        )
        assert rc.cluster.spark_master == "local"
        assert rc.retry.max_retries == 1

    def test_from_dict(self):
        rc = RunConfig.from_dict({
            "defaults": {"max_tickers": 10},
            "providers": {"alpha_vantage": {"enabled": True}},
            "silver_models": {"models": ["temporal", "stocks"]},
            "cluster": {"spark_master": "auto", "task_batch_size": 100},
            "retry": {"max_retries": 5},
            "profiles": {"dev": {"max_tickers": 5}},
        })
        assert rc.defaults["max_tickers"] == 10
        assert rc.silver_models == ["temporal", "stocks"]
        assert rc.cluster.task_batch_size == 100
        assert rc.retry.max_retries == 5
        assert "dev" in rc.profiles
